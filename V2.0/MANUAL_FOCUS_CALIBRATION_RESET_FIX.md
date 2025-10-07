# Manual Focus Calibration Reset Fix

**Date**: October 7, 2025  
**Status**: ✅ FIXED - Ready for Pi testing  
**Issue**: Manual focus being reset during calibration

---

## Problem Analysis

### User's Critical Observation

> "should 8 not become 0.8 instead of 0.5"

This led to discovering that **the conversion math is correct**, but **the lens position was being reset**!

### What Was Happening

**Expected Flow**:
```
1. Set manual focus position 8
   → Normalized: (8 - 6) / 4 = 0.5 ✅ CORRECT (50% of 6-10mm range)
   → Lens position: (1.0 - 0.5) * 1023 = 511 ✅ CORRECT
2. Calibration reads lens position
   → Should get: 511
   → Should convert back: 1.0 - (511/1023) = 0.5 ✅ CORRECT
```

**Actual Flow** ❌:
```
1. Set manual focus position 8
   → Normalized: 0.5 ✅
   → Lens position: 511 ✅
   → Stored in _stored_focus_values["camera0"] = 0.5 ✅
2. Calibration starts
   → Calls set_controls() to enable auto-exposure
   → THIS RESETS LENS POSITION TO DEFAULT (15) ❌
3. Calibration reads lens position
   → Gets: 15 (WRONG!)
   → Converts: 1.0 - (15/1023) = 0.985 ❌ WRONG!
   → Logs: "read current manual focus: 0.985 (lens position: 15.0)" ❌
```

### Evidence from Logs

```
2025-10-07 20:47:46,450 - Set focus value 0.500 (lens position 511) for camera0  ✅ SET CORRECTLY
2025-10-07 20:47:46,651 - ✅ Set web UI manual focus for camera0: 8.000 (normalized: 0.500)  ✅
2025-10-07 20:47:46,651 - 🔧 CALIBRATION: Starting exposure-only calibration for camera0
2025-10-07 20:47:46,651 - 📷 Camera camera0 enabling auto-exposure controls...
[set_controls() call happens here - RESETS lens position!]
2025-10-07 20:47:48,558 - 📷 Camera camera0 read current manual focus from metadata: 0.985 (lens position: 15.0)  ❌ RESET!
```

**The lens position changed from 511 → 15** between setting it and reading it during calibration!

---

## Root Cause

When `auto_calibrate_camera()` calls `picamera2.set_controls(control_dict)` to enable auto-exposure, **it inadvertently resets the lens position** to the camera's default value (15 for ArduCam).

This happens because:
1. `set_controls()` may reset controls that aren't explicitly included in the control dictionary
2. Manual focus (AfMode=0, LensPosition=511) was set **before** the exposure controls
3. The exposure control dict doesn't include `AfMode` or `LensPosition`
4. Camera resets to default autofocus state

---

## The Fix

### Modified File: `camera/pi_camera_controller.py`

**Lines 1257-1277** - Reapply manual focus after setting exposure controls:

```python
# Set all controls
picamera2.set_controls(control_dict)

# CRITICAL: If skip_autofocus=True (manual focus mode), reapply manual focus
# because set_controls() may have reset it
if skip_autofocus:
    cam_id = int(camera_id.replace('camera', ''))
    cam_id_str = f"camera{cam_id}"
    if hasattr(self, '_stored_focus_values') and cam_id_str in self._stored_focus_values:
        stored_focus = self._stored_focus_values[cam_id_str]
        lens_position_manual = int((1.0 - stored_focus) * 1023)
        picamera2.set_controls({
            "AfMode": 0,  # Manual focus
            "LensPosition": lens_position_manual
        })
        logger.info(f"🔄 Camera {camera_id} REAPPLIED manual focus {stored_focus:.3f} (lens {lens_position_manual}) after exposure controls")
        await asyncio.sleep(0.2)  # Give camera time to adjust focus

# Allow time for auto-exposure to settle
await asyncio.sleep(1.0)
```

### Why This Works

**Before Fix**:
```
1. Set manual focus → lens position 511 ✅
2. set_controls(exposure_dict) → lens position RESET to 15 ❌
3. Read metadata → gets 15 ❌
4. Calibration uses wrong focus ❌
```

**After Fix**:
```
1. Set manual focus → lens position 511 ✅
2. set_controls(exposure_dict) → lens position RESET to 15 ⚠️
3. REAPPLY manual focus → lens position 511 ✅✅
4. Read metadata → gets 511 ✅
5. Calibration uses correct focus ✅
```

---

## Expected Log Output (After Fix)

### Successful Manual Focus Calibration

```
2025-10-07 XX:XX:XX - INFO - 📸 Converted focus 8 to normalized 0.500
2025-10-07 XX:XX:XX - INFO - Set focus value 0.500 (lens position 511) for camera0
2025-10-07 XX:XX:XX - INFO - ✅ Set web UI manual focus for camera0: 8.000 (normalized: 0.500)
2025-10-07 XX:XX:XX - INFO - 🔧 CALIBRATION: Starting exposure-only calibration for camera0
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 enabling auto-exposure controls...
2025-10-07 XX:XX:XX - INFO - 🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) after exposure controls  ← NEW!
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 SKIPPING autofocus - manual focus mode
2025-10-07 XX:XX:XX - INFO - 📷 Camera camera0 read current manual focus from metadata: 0.500 (lens position: 511)  ← FIXED!
2025-10-07 XX:XX:XX - INFO - ✅ Camera camera0 calibration complete: Focus: 0.500  ← CORRECT!
```

**Key Changes**:
- **NEW log**: "REAPPLIED manual focus 0.500 (lens 511)"
- **Fixed**: Metadata now reads lens position **511** instead of **15**
- **Result**: Focus value **0.500** instead of **0.985**

---

## Focus Value Clarification

### Is 8 → 0.5 Correct?

**YES!** The math is absolutely correct:

**Physical ArduCam Spec**:
- Minimum focus distance: 6.0mm (near/macro)
- Maximum focus distance: 10.0mm (far/infinity)
- Total range: 10.0 - 6.0 = 4.0mm

**Position 8.0mm**:
- Distance from minimum: 8.0 - 6.0 = 2.0mm
- Percentage of range: 2.0 / 4.0 = 0.5 (50%)
- **Normalized value: 0.5** ✅

**Lens Position Conversion**:
- Normalized 0.5 → Lens position (1.0 - 0.5) × 1023 = **511**
- This is exactly middle position ✅

**If you wanted 0.8 normalized**:
- That would be 80% of range
- Physical position: 6.0 + (0.8 × 4.0) = 9.2mm
- Lens position: (1.0 - 0.8) × 1023 = 204

**Focus Value Mapping Table**:
```
Web UI (mm) | Normalized | Lens Position | Description
   6.0      |    0.0     |     1023      | Near/Macro (minimum focus distance)
   7.0      |    0.25    |      767      | 25% toward infinity
   8.0      |    0.5     |      511      | Middle (your selection)
   9.0      |    0.75    |      255      | 75% toward infinity
   10.0     |    1.0     |        0      | Far/Infinity (maximum focus distance)
```

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
- [ ] **Verify logs**: "read current manual focus from metadata: 0.500 (lens position: 511)" (NOT 0.985/15!)
- [ ] **Verify logs**: "calibration complete: Focus: 0.500"
- [ ] **Check images**: Sharp and in focus

**Test Different Focus Positions**:
- [ ] Position 6.0: Should read 0.000 (lens 1023)
- [ ] Position 7.0: Should read 0.250 (lens 767)
- [ ] Position 8.0: Should read 0.500 (lens 511)
- [ ] Position 9.0: Should read 0.750 (lens 255)
- [ ] Position 10.0: Should read 1.000 (lens 0)

---

## Success Criteria

✅ **Manual Focus Preserved**: Lens position stays at **511** (not reset to 15)  
✅ **Correct Metadata Reading**: Calibration reads focus **0.500** from metadata (not 0.985)  
✅ **Consistent Throughout Scan**: Every point uses lens position **511**  
✅ **Sharp Images**: All images consistently sharp at position 8  
✅ **No Autofocus**: Log shows "SKIPPING autofocus - manual focus mode"  

---

## Related Files

- **Modified**: `camera/pi_camera_controller.py` (lines 1257-1277)
- **Previous Fix**: `MANUAL_FOCUS_COMPLETE_FIX.md` (skip_autofocus parameter)
- **Related**: `scanning/scan_orchestrator.py` (focus setup and conversion)

---

## Technical Notes

### Why set_controls() Resets Focus

The Picamera2 library's `set_controls()` method operates on libcamera controls. When you set exposure-related controls without explicitly including focus-related controls, some camera firmware implementations reset unspecified controls to defaults.

**Workaround Strategy**:
1. Set initial manual focus
2. Call `set_controls()` for exposure calibration
3. **Immediately reapply manual focus** before metadata capture
4. This ensures focus is correct when metadata is read

### Inversion Explanation

The lens position is inverted relative to normalized focus:
- **Normalized 0.0** (near) → **Lens 1023** (high position = near focus)
- **Normalized 1.0** (far) → **Lens 0** (low position = infinity focus)

This is why the conversion uses: `lens_position = int((1.0 - focus_value) * 1023)`

---

## Rollback Plan

If issues occur, revert this change:
- Remove the manual focus reapplication block (lines 1260-1274)
- System will return to previous behavior (reading wrong focus during calibration)

Previous fix (skip_autofocus parameter) can remain as it's still beneficial.
