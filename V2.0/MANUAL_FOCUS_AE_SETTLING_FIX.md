# Manual Focus Reset During AE Settling - Critical Fix

**Date**: October 7, 2025  
**Status**: ✅ FIXED - Ready for Pi testing (Enhanced)  
**Issue**: Manual focus reset multiple times during calibration

---

## Problem Discovery Timeline

### Test 1 Result: Partial Success ⚠️

Your logs showed:
```
2025-10-07 20:53:23,292 - 🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) after exposure controls  ✅ WORKING!
2025-10-07 20:53:24,494 - 📷 Camera camera0 letting auto-exposure settle...
2025-10-07 20:53:25,398 - 📷 Camera camera0 read current manual focus from metadata: 0.985 (lens position: 15.0)  ❌ RESET AGAIN!
```

**The fix worked, but then focus was reset AGAIN!**

### Root Cause: Multiple Reset Points

The camera resets manual focus at **THREE different points**:

1. ✅ **Initial set_controls()** - We fixed this with first reapplication
2. ❌ **During AE settling loop** - Camera resets during `capture_metadata()` calls
3. ✅ **After reapplication** - We added delay to prevent this

**The missing fix**: Reapply focus **AFTER** the AE settling loop completes!

---

## The Complete Fix

### Modified File: `camera/pi_camera_controller.py`

**Lines 1260-1277** - First reapplication (EXISTING FIX):
```python
# Set all controls
picamera2.set_controls(control_dict)

# CRITICAL: If skip_autofocus=True (manual focus mode), reapply manual focus
if skip_autofocus:
    cam_id = int(camera_id.replace('camera', ''))
    cam_id_str = f"camera{cam_id}"
    if hasattr(self, '_stored_focus_values') and cam_id_str in self._stored_focus_values:
        stored_focus = self._stored_focus_values[cam_id_str]
        lens_position_manual = int((1.0 - stored_focus) * 1023)
        picamera2.set_controls({
            "AfMode": 0,
            "LensPosition": lens_position_manual
        })
        logger.info(f"🔄 REAPPLIED manual focus {stored_focus:.3f} (lens {lens_position_manual}) after exposure controls")
        await asyncio.sleep(0.2)

# Allow time for auto-exposure to settle
await asyncio.sleep(1.0)
```

**Lines 1293-1318** - Second reapplication after AE settling (NEW FIX):
```python
# Step 2: Capture a few frames to let AE settle
logger.info(f"📷 Camera {camera_id} letting auto-exposure settle...")
settle_timeout = 5.0
settle_start = time.time()

try:
    for i in range(3):
        if time.time() - settle_start > settle_timeout:
            logger.warning(f"⚠️ Camera {camera_id} AE settling timeout")
            break
        
        metadata = picamera2.capture_metadata()
        exposure = metadata.get('ExposureTime', 33000)
        gain = metadata.get('AnalogueGain', 1.0)
        logger.debug(f"📷 Camera {camera_id} AE settle frame {i+1}: exposure={exposure}, gain={gain:.2f}")
        await asyncio.sleep(0.3)
        
except Exception as settle_error:
    logger.error(f"❌ Camera {camera_id} AE settling failed: {settle_error}")

# CRITICAL: Reapply manual focus AGAIN after AE settling (reset during frame captures)
if skip_autofocus:
    cam_id = int(camera_id.replace('camera', ''))
    cam_id_str = f"camera{cam_id}"
    if hasattr(self, '_stored_focus_values') and cam_id_str in self._stored_focus_values:
        stored_focus = self._stored_focus_values[cam_id_str]
        lens_position_manual = int((1.0 - stored_focus) * 1023)
        picamera2.set_controls({
            "AfMode": 0,
            "LensPosition": lens_position_manual
        })
        logger.info(f"🔄 REAPPLIED manual focus {stored_focus:.3f} (lens {lens_position_manual}) AFTER AE settling")
        await asyncio.sleep(0.2)
```

---

## Why Double Reapplication Is Needed

### Camera Behavior During Calibration

```
Timeline of Focus Reset Issues:

1. Set manual focus → Lens position 511 ✅
   
2. set_controls(exposure_dict) → Lens RESET to 15 ❌
   
3. REAPPLY focus #1 → Lens position 511 ✅
   
4. AE settling loop (3 frames):
   - capture_metadata() frame 1 → Lens RESET to 15 ❌
   - capture_metadata() frame 2 → Lens still 15 ❌
   - capture_metadata() frame 3 → Lens still 15 ❌
   
5. REAPPLY focus #2 → Lens position 511 ✅✅
   
6. Final metadata capture → Reads lens 511 ✅✅
```

### Why Each Frame Capture Resets Focus

The Picamera2/libcamera system appears to reset manual focus during metadata capture when:
- Auto-exposure is enabled (`AeEnable: True`)
- Metadata is captured while AE is settling
- Focus mode might default back to auto during these captures

**Solution**: Re-assert manual focus **after** all AE settling operations complete.

---

## Expected Log Output (After Complete Fix)

```
2025-10-07 XX:XX:XX - INFO - Set focus value 0.500 (lens position 511) for camera0
2025-10-07 XX:XX:XX - INFO - 🔧 CALIBRATION: Starting exposure-only calibration for camera0
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 enabling auto-exposure controls...
2025-10-07 XX:XX:XX - INFO - 🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) after exposure controls  ← FIX #1
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 letting auto-exposure settle...
2025-10-07 XX:XX:XX - DEBUG - 📷 Camera camera0 AE settle frame 1: exposure=20000, gain=1.60
2025-10-07 XX:XX:XX - DEBUG - 📷 Camera camera0 AE settle frame 2: exposure=19992, gain=1.60
2025-10-07 XX:XX:XX - DEBUG - 📷 Camera camera0 AE settle frame 3: exposure=19992, gain=1.60
2025-10-07 XX:XX:XX - INFO - 🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling  ← FIX #2 (NEW!)
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 SKIPPING autofocus - manual focus mode
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 read current manual focus from metadata: 0.500 (lens position: 511)  ← FIXED!
2025-10-07 XX:XX:XX - INFO - ✅ Camera camera0 calibration complete: Focus: 0.500  ← CORRECT!
```

**Key Differences**:
- **Two reapplication logs**: One after exposure controls, one after AE settling
- **Final metadata reads 511** (not 15!)
- **Calibration reports 0.500** (not 0.985!)

---

## Testing Checklist

**Before Testing**:
- [ ] Pull latest code to Raspberry Pi
- [ ] Restart scanner system

**Test: Manual Focus Calibration**:
- [ ] Set focus mode: Manual
- [ ] Set focus position: 8.0
- [ ] Start scan
- [ ] **Verify logs**: "REAPPLIED manual focus 0.500 (lens 511) after exposure controls"
- [ ] **Verify logs**: "REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling" ← NEW!
- [ ] **Verify logs**: "read current manual focus from metadata: 0.500 (lens position: 511)" ← Should be 511, not 15!
- [ ] **Check images**: Sharp and in focus throughout scan

**Validation**:
- [ ] Lens position stays at 511 (not 15)
- [ ] Focus value reads 0.500 (not 0.985)
- [ ] All images are sharp
- [ ] Manual focus preserved across all scan points

---

## Success Criteria

✅ **First Reapplication**: Lens set to 511 after exposure controls  
✅ **Second Reapplication**: Lens set to 511 AFTER AE settling (NEW!)  
✅ **Metadata Reading**: Reports lens position **511** (not 15)  
✅ **Focus Value**: Calibration uses **0.500** (not 0.985)  
✅ **Sharp Images**: All images consistently sharp at position 8  
✅ **Scan Consistency**: Focus maintained throughout entire scan  

---

## Technical Analysis

### Why This Problem Exists

The Picamera2 library's interaction with libcamera has a quirk:
- When `AeEnable: True` is set, the camera takes control of exposure
- During `capture_metadata()` calls in the settling loop:
  - Camera may briefly switch to auto mode to evaluate exposure
  - Manual focus settings can be lost during these evaluations
  - Lens position resets to a default value (15 for ArduCam)

### Why Double Reapplication Works

**Reapplication #1** (after set_controls):
- Prevents immediate reset from exposure control setup
- Gets lens to correct position for AE settling

**Reapplication #2** (after AE settling):
- Restores lens position after frame captures
- Ensures metadata reading gets correct value
- Final assertion before calibration metadata capture

### Alternative Approaches Considered

1. **Include AfMode/LensPosition in control_dict**: Doesn't work - still gets overridden
2. **Disable AE during settling**: Defeats purpose of exposure calibration
3. **Single reapplication with longer delay**: Doesn't address reset during frame captures
4. **Lock controls after setting**: Not supported by Picamera2 API

**Chosen solution** (double reapplication) is the most reliable approach.

---

## Related Files

- **Modified**: `camera/pi_camera_controller.py` (lines 1260-1318)
- **Related**: `MANUAL_FOCUS_COMPLETE_FIX.md` (skip_autofocus parameter)
- **Related**: `MANUAL_FOCUS_CALIBRATION_RESET_FIX.md` (first reapplication fix)

---

## Rollback Plan

If issues occur, revert the second reapplication (lines 1303-1318):
- First reapplication will remain (helps but not complete)
- System will behave like previous test (0.985 instead of 0.500)

To fully rollback:
- Remove both reapplication blocks
- System returns to original behavior (autofocus override bug)
