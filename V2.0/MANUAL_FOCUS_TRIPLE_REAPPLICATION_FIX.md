# Manual Focus Triple Reapplication Fix - COMPLETE SOLUTION

## Issue Discovery Timeline

### Problem Evolution
User set manual focus position **8.0mm** (normalized **0.5**, lens position **511**) but calibration was reading **0.985** (lens position **15**).

### Discovery Process

**Initial Fix (Single Reapplication):**
- Added first reapplication after `set_controls()` 
- **Result:** Partially successful - logs showed `REAPPLIED manual focus 0.500 (lens 511)` BUT still reading `0.985 (lens position: 15.0)`

**Second Fix (Double Reapplication):**
- Added second reapplication after AE settling loop
- **Result:** Still insufficient - both reapplications worked but final reading still wrong

**Final Discovery (Triple Reapplication - CURRENT):**
- Found THIRD reset point: `capture_metadata()` for final calibration values
- Each `capture_metadata()` call with `AeEnable: True` resets manual focus to camera default (15)

## Root Cause Analysis

### Picamera2/libcamera Behavior
When auto-exposure is enabled (`AeEnable: True`), ANY metadata capture can temporarily reset manual focus settings to the camera's default lens position.

**ArduCam 64MP Default:** Lens position 15 (very near focus, normalized 0.985)

### Complete Reset Timeline

```
1. User sets manual focus: 8.0mm → 0.5 normalized → lens 511 ✅

2. Calibration starts with set_controls(AeEnable=True) → RESET to 15 ❌
   ↓
3. REAPPLICATION #1 (after exposure controls) → lens 511 ✅

4. AE settling loop (3 frames):
   - capture_metadata() #1 → RESET to 15 ❌
   - capture_metadata() #2 → RESET to 15 ❌  
   - capture_metadata() #3 → RESET to 15 ❌
   ↓
5. REAPPLICATION #2 (after AE settling) → lens 511 ✅

6. Final calibration capture_metadata() → RESET to 15 ❌❌
   ↓
7. REAPPLICATION #3 (before final metadata) → lens 511 ✅✅

8. Read metadata → Should now get 511! ✅✅✅
```

## Complete Fix Implementation

### Triple Reapplication Strategy

**Location 1: After Exposure Controls Setup**
```python
# Set all controls including auto-exposure
picamera2.set_controls(control_dict)

# CRITICAL: Reapply manual focus after exposure controls
if skip_autofocus:
    stored_focus = self._stored_focus_values[cam_id_str]
    lens_position_manual = int((1.0 - stored_focus) * 1023)
    picamera2.set_controls({
        "AfMode": 0,
        "LensPosition": lens_position_manual
    })
    logger.info(f"🔄 REAPPLIED manual focus {stored_focus:.3f} (lens {lens_position_manual}) after exposure controls")
    await asyncio.sleep(0.2)
```

**Location 2: After AE Settling Loop**
```python
# AE settling loop (3 frame captures)
for i in range(3):
    metadata = picamera2.capture_metadata()  # Each can reset focus
    await asyncio.sleep(0.3)

# CRITICAL: Reapply manual focus after AE settling
if skip_autofocus:
    stored_focus = self._stored_focus_values[cam_id_str]
    lens_position_manual = int((1.0 - stored_focus) * 1023)
    picamera2.set_controls({
        "AfMode": 0,
        "LensPosition": lens_position_manual
    })
    logger.info(f"🔄 REAPPLIED manual focus {stored_focus:.3f} (lens {lens_position_manual}) AFTER AE settling")
    await asyncio.sleep(0.2)
```

**Location 3: Before Final Metadata Capture (NEW!)**
```python
logger.info(f"📷 Camera {camera_id} capturing final calibration values...")

# CRITICAL: Third and final focus reapplication before metadata capture
if skip_autofocus:
    stored_focus = self._stored_focus_values[cam_id_str]
    lens_position_manual = int((1.0 - stored_focus) * 1023)
    picamera2.set_controls({
        "AfMode": 0,
        "LensPosition": lens_position_manual
    })
    logger.info(f"🔄 REAPPLIED manual focus {stored_focus:.3f} (lens {lens_position_manual}) BEFORE final metadata")
    await asyncio.sleep(0.2)

final_metadata = picamera2.capture_metadata()  # Now won't reset focus
```

## Expected Log Sequence (Fixed)

**What You Should See:**
```
📸 Converted focus 8 to normalized 0.500
📷 Camera camera0 enabling auto-exposure controls...
🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) after exposure controls  ← #1

📷 Camera camera0 letting auto-exposure settle...
🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling  ← #2

📷 Camera camera0 capturing final calibration values...
🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) BEFORE final metadata  ← #3 NEW!

📷 Camera camera0 read current manual focus from metadata: 0.500 (lens position: 511)  ← FIXED!
✅ Camera camera0 calibration complete: Focus: 0.500  ← CORRECT!
```

**What Was Happening Before:**
```
🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) after exposure controls  ✅
🔄 Camera camera0 REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling  ✅
📷 Camera camera0 capturing final calibration values...  ← capture_metadata() resets focus!
📷 Camera camera0 read current manual focus from metadata: 0.985 (lens position: 15.0)  ❌ WRONG!
```

## Code Changes

### File: `camera/pi_camera_controller.py`

**Lines ~1458-1470** - Added third reapplication before final metadata capture

## Testing Checklist

### Critical Verification Points

1. **THREE Reapplication Messages:**
   ```
   ✅ "REAPPLIED manual focus 0.500 (lens 511) after exposure controls"
   ✅ "REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling"
   ✅ "REAPPLIED manual focus 0.500 (lens 511) BEFORE final metadata" ← NEW!
   ```

2. **Correct Metadata Reading:**
   ```
   ✅ "read current manual focus from metadata: 0.500 (lens position: 511)"
   NOT: "read current manual focus from metadata: 0.985 (lens position: 15.0)"
   ```

3. **Correct Calibration Result:**
   ```
   ✅ "calibration complete: Focus: 0.500"
   NOT: "calibration complete: Focus: 0.985"
   ```

4. **Image Sharpness:**
   - All 24 images should be sharp and in focus
   - No variation in focus between points
   - Consistent sharpness across entire scan

### Test Procedure

1. Set manual focus mode, position 8.0mm
2. Start cylindrical scan (24 points)
3. Check logs for THREE reapplication messages (one camera at a time)
4. Verify metadata reads lens position **511** (not 15)
5. Verify calibration reports focus **0.500** (not 0.985)
6. Examine captured images for sharpness

### Expected Behavior

**Camera 0:**
```
🔄 REAPPLIED manual focus 0.500 (lens 511) after exposure controls
📷 Camera camera0 letting auto-exposure settle...
🔄 REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling
📷 Camera camera0 capturing final calibration values...
🔄 REAPPLIED manual focus 0.500 (lens 511) BEFORE final metadata
📷 Camera camera0 SKIPPING autofocus - manual focus mode
📷 Camera camera0 read current manual focus: 0.500 (lens position: 511)
✅ Camera camera0 calibration complete: Focus: 0.500
```

**Camera 1:**
```
🔄 REAPPLIED manual focus 0.500 (lens 511) after exposure controls
📷 Camera camera1 letting auto-exposure settle...
🔄 REAPPLIED manual focus 0.500 (lens 511) AFTER AE settling
📷 Camera camera1 capturing final calibration values...
🔄 REAPPLIED manual focus 0.500 (lens 511) BEFORE final metadata
📷 Camera camera1 SKIPPING autofocus - manual focus mode
📷 Camera camera1 read current manual focus: 0.500 (lens position: 511)
✅ Camera camera1 calibration complete: Focus: 0.500
```

## Why Triple Reapplication is Necessary

### Picamera2 Auto-Exposure Behavior

When `AeEnable: True` is set, the camera firmware may:
1. Temporarily enter auto-focus mode for exposure calculation
2. Reset manual lens position to a "safe" default
3. Use default focus for exposure metering

### Metadata Capture Side Effects

`capture_metadata()` with active auto-exposure can trigger:
- Brief auto-focus evaluation
- Lens position reset to camera default
- Control state re-initialization

### Solution: Persistent Re-assertion

The fix ensures manual focus is **the last control applied** before ANY operation that reads camera state:

1. After enabling auto-exposure → Reapply
2. After AE settling loop → Reapply  
3. Before final metadata → Reapply ← **Critical third point**

## Technical Details

### Focus Value Conversion
- **Web UI:** 6.0-10.0mm (physical range)
- **Normalized:** 0.0-1.0 (backend)
- **Lens Position:** 0-1023 (inverted: 1023=near, 0=far)

**Example (Position 8):**
```
Web: 8.0mm
Normalized: (8.0 - 6.0) / 4.0 = 0.5
Lens: int((1.0 - 0.5) × 1023) = 511
```

### ArduCam Default Behavior
- Default lens position: 15 (very near/macro)
- Normalized equivalent: 1.0 - (15 / 1023) = 0.985
- Very close focus, not suitable for most scanning

## Related Documentation
- `MANUAL_FOCUS_AE_SETTLING_FIX.md` - Previous double reapplication attempt
- `MANUAL_FOCUS_CALIBRATION_RESET_FIX.md` - Original single reapplication
- `CAMERA_FOCUS_PERSISTENCE_FIX.md` - Focus restoration after reconfiguration

## Success Criteria

✅ **Fix is successful when:**
1. All three reapplication log messages appear
2. Metadata reads lens position 511 (not 15)
3. Calibration reports focus 0.500 (not 0.985)
4. All scan images are sharp and in focus
5. Focus remains consistent across all 24 points

❌ **Fix has failed if:**
- Missing any of the three reapplication messages
- Metadata still reads lens position 15
- Calibration still reports focus 0.985
- Images are out of focus or vary in sharpness

## Implementation Date
- **Original Issue:** Discovered through user testing logs
- **Double Reapplication:** Previous session
- **Triple Reapplication:** Current session (final fix)
- **Status:** Ready for Pi hardware testing

**Please test this complete fix on the Pi hardware and report the results!**
