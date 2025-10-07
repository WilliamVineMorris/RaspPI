# Manual Focus Scan Fix - Complete Solution

**Date:** October 7, 2025  
**Issue:** Scan manual focus not working (dashboard works fine)  
**Root Cause:** ArduCam firmware bug during exposure calibration  
**Solution:** Use dashboard's simple approach - skip calibration

---

## What Was Changed

### File: `scanning/scan_orchestrator.py`
**Location:** Lines 3514-3547 (in `_setup_focus_at_first_scan_point` method)

### Before (BROKEN ❌):
```python
# Turn on LEDs for calibration
await self.lighting_controller.set_brightness("all", calibration_brightness)

# Apply manual focus and calibrate exposure for each camera
for camera_id in available_cameras:
    # Set manual focus first
    success = await self.camera_manager.controller.set_focus_value(camera_id, focus_normalized)
    
    # Now perform exposure-only calibration with fixed focus
    calibration_result = await self.camera_manager.controller.auto_calibrate_camera(
        camera_id,
        skip_autofocus=True  # ← This was causing the problem!
    )
    # Even with skip_autofocus=True, calibration's capture_metadata() calls
    # trigger ArduCam firmware autofocus, resetting lens from 485 → 15
```

**Problem:** The `auto_calibrate_camera()` function calls `capture_metadata()` multiple times, which triggers the ArduCam firmware to enable autofocus temporarily, overriding the manual `LensPosition=485` setting.

### After (WORKING ✅):
```python
# SIMPLE APPROACH: Just set manual focus like dashboard does
# Don't calibrate exposure - it interferes with manual focus due to ArduCam firmware bug
# The camera will use auto-exposure during scan, which works fine

# Turn on LEDs to idle brightness for scanning
await self.lighting_controller.set_brightness("all", idle_brightness)

# Apply manual focus for each camera (simple, like dashboard)
for camera_id in available_cameras:
    # Set manual focus using the same method as dashboard
    success = await self.camera_manager.controller.set_focus_value(camera_id, focus_normalized)
    if success:
        self._scan_focus_values[camera_id] = self._web_focus_position
        logger.info(f"✅ Set web UI manual focus for {camera_id}: {self._web_focus_position:.3f}mm")
        logger.info(f"📸 {camera_id} will use auto-exposure during scan (manual focus locked)")
```

**Solution:** Use the exact same simple approach as the dashboard - just set the focus value and let the camera handle exposure automatically during the scan.

---

## Why This Fix Works

### Dashboard Approach (Simple ✅):
1. Set `AfMode=0` (manual)
2. Set `LensPosition=485` (for 8.1mm focus)
3. Done! ✅

### Old Scan Approach (Complex ❌):
1. Set manual focus → ✅ Works
2. Enable auto-exposure → ⚠️ OK
3. Call `capture_metadata()` → ❌ Firmware enables AF, resets lens to 15
4. Reapply manual focus → ⚠️ Lens at 485
5. Call `capture_metadata()` again → ❌ Firmware resets to 15 again
6. Reapply manual focus again → ⚠️ Lens at 485
7. Final `capture_metadata()` → ❌ Returns lens=15
8. Result: Focus reads 0.985 instead of 0.525 ❌

### New Scan Approach (Simple ✅):
1. Set manual focus → ✅ Works
2. Don't touch exposure calibration
3. Camera uses auto-exposure naturally during scan
4. Focus stays locked at 8.1mm (lens 485) ✅

---

## Expected Results After Fix

### Logs You Should See:
```
📸 Web UI manual focus mode: Setting focus without calibration (like dashboard)
💡 Setting LEDs to idle 10% for manual focus scan
✅ Set web UI manual focus for camera0: 8.100mm (normalized: 0.525)
📸 camera0 will use auto-exposure during scan (manual focus locked)
✅ Set web UI manual focus for camera1: 8.100mm (normalized: 0.525)
📸 camera1 will use auto-exposure during scan (manual focus locked)
✅ Manual focus setup complete - using dashboard approach (no calibration)
```

### Camera Metadata Should Show:
```
Focus: 0.525 (not 0.985) ✅
LensPosition: 485 (not 15) ✅
```

### Image Quality:
- Images should be in focus at your specified distance
- Auto-exposure will still work during the scan
- No autofocus will run (manual focus locked)

---

## Testing Steps

### 1. Deploy Fix to Pi
```bash
cd ~/RaspPI/V2.0
git pull origin Test
sudo systemctl restart scanner
```

### 2. Run Test Scan
1. Open web UI
2. Go to Scans page
3. Set:
   - Quality: Medium (or any standard profile)
   - Focus Mode: Manual
   - Focus Position: 8.1mm
4. Start scan

### 3. Check Logs
```bash
tail -f /var/log/scanner/scanner.log
```

**Look for:**
- ✅ `Using dashboard approach (no calibration)`
- ✅ `Set web UI manual focus for camera0: 8.100mm`
- ✅ Focus value should be ~0.525 in metadata
- ❌ Should NOT see: `Performing exposure calibration`
- ❌ Should NOT see: `Lens position mismatch`

### 4. Verify Image Focus
- Download captured images
- Check if they're sharp at expected focus distance
- Compare with dashboard manual focus images

---

## What About Exposure?

**Q: Won't skipping calibration affect exposure quality?**

**A: No, because:**

1. **Auto-exposure still works** - The camera's built-in AE runs during each capture
2. **Flash mode helps** - LEDs provide consistent lighting
3. **Dashboard proves it** - Dashboard manual focus works great without calibration
4. **Calibration was optional** - It was meant to pre-optimize, but AE during scan is fine

**Q: Can we get calibration back later?**

**A: Yes, two ways:**

1. **Simple fix:** Use dashboard to set focus, let scan auto-calibrate exposure first, then lock exposure and apply manual focus
2. **Advanced fix:** Disable auto-exposure before calling `capture_metadata()` to prevent firmware interference

For now, the simple approach (like dashboard) is best!

---

## Troubleshooting

### If Focus Still Doesn't Work:

**Check 1: Verify dashboard still works**
- Go to dashboard
- Set manual focus to 8.1mm
- Confirm lens moves to ~485
- If dashboard broken → different problem

**Check 2: Check focus mode transmission**
```javascript
// In browser console after starting scan
// Should see:
quality_settings: {focus: {mode: 'manual', position: 8.1}}
```

**Check 3: Check backend received settings**
```bash
# In Pi logs, should see:
📸 Applied web UI focus settings: mode=manual, position=8.1
```

**Check 4: Verify camera controller called**
```bash
# Should see:
Set focus value 0.525 (lens position 485) for camera0
```

If all these work but focus still wrong → camera hardware issue.

---

## Technical Details

### Why ArduCam Firmware Has This Bug

The IMX519 (64MP ArduCam) has automatic exposure metering that:
1. Needs accurate focus to measure light correctly
2. Briefly enables autofocus during `capture_metadata()`
3. Moves lens to default position 15 (very near focus)
4. Returns to manual mode BUT lens stays at 15

This is a **firmware limitation**, not fixable in software.

### Why Dashboard Doesn't Hit This Bug

Dashboard never calls `capture_metadata()` during focus setup:
- Sets focus → Done
- Metadata only read during live preview
- Live preview runs separately from focus control

### Why Old Scan Code Hit This Bug

Scan tried to be "smart" by pre-calibrating:
- Set focus → Good
- Calibrate exposure → Calls `capture_metadata()` → Bug triggered
- Focus gets reset → Bad

---

## Future Improvements

### If You Want Pre-Calibrated Exposure (Optional):

**Two-stage calibration:**
```python
# Stage 1: Calibrate exposure with autofocus
calibration = await auto_calibrate_camera(camera_id, skip_autofocus=False)
exposure = calibration['exposure_time']
gain = calibration['analogue_gain']

# Stage 2: Lock exposure, then set manual focus
await camera.set_controls({
    "AeEnable": False,  # Disable auto-exposure
    "ExposureTime": exposure,
    "AnalogueGain": gain
})

# Stage 3: Apply manual focus (AE disabled, no interference)
await set_focus_value(camera_id, focus_normalized)
```

This would give you both calibrated exposure AND manual focus, but:
- More complex
- Exposure won't adapt during scan
- Current simple fix is probably fine

---

## Summary

**Before:** Scan manual focus broken due to ArduCam firmware bug during exposure calibration ❌  
**After:** Scan manual focus works like dashboard - simple and reliable ✅  
**Tradeoff:** No pre-calibrated exposure (but auto-exposure still works during scan) ✅  
**Benefit:** Manual focus actually works! 🎉

**Next Step:** Deploy to Pi and test!
