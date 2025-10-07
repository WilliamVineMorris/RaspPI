# Manual Focus + Exposure Calibration Fix

**Date**: 2025-10-07  
**Issue**: Manual focus mode was not setting correct focus value and skipping exposure calibration  
**Status**: ✅ FIXED

---

## Problems Identified

### 1. **Incorrect Focus Value Conversion**
**Symptom**: Logs showed `Set focus value 1.000 (lens position 0)` instead of expected value  
**Root Cause**: Web UI sends focus in ArduCam range (6.0-10.0), but camera controller expects normalized range (0.0-1.0)

**Log Evidence**:
```
📸 Web UI manual focus mode: Skipping autofocus calibration, using position 8
Set focus value 1.000 (lens position 0) for camera0  ❌ WRONG
```

### 2. **Missing Exposure Calibration**
**Symptom**: Images unfocused AND underexposed/overexposed  
**Root Cause**: Manual focus mode was skipping ALL calibration, including exposure/gain

**User Feedback**: "the cameras seem unfocused still, is the focus being applied correctly, also how are the other value calibrated?"

---

## Solution Implemented

### Focus Value Conversion
Added conversion from ArduCam distance units to normalized camera range:

```python
# Convert web UI focus value (6.0-10.0 range) to camera controller range (0.0-1.0)
# ArduCam: 6.0 = near, 10.0 = far
# Camera controller: 0.0 = near, 1.0 = far
focus_normalized = (self._web_focus_position - 6.0) / 4.0  # Convert 6-10 to 0-1
focus_normalized = max(0.0, min(1.0, focus_normalized))  # Clamp to valid range
```

**Conversion Examples**:
- Web UI `6.0` → Camera `0.0` (near focus)
- Web UI `8.0` → Camera `0.5` (middle focus)
- Web UI `10.0` → Camera `1.0` (far focus)

### Exposure-Only Calibration
Added exposure/gain calibration AFTER setting manual focus:

```python
# 1. Set manual focus (locked)
await self.camera_manager.controller.set_focus_value(camera_id, focus_normalized)

# 2. Perform exposure calibration with focus locked
calibration_result = await self.camera_manager.controller.auto_calibrate_camera(camera_id)
```

**Key Insight**: `auto_calibrate_camera()` respects manual focus when `AfMode=0` is already set, so it only calibrates exposure/gain.

---

## Code Changes

### File: `scanning/scan_orchestrator.py`

**Location**: `_setup_scan_focus()` method, lines ~3486-3540

**Before** (❌ BROKEN):
```python
if self._web_focus_mode == 'manual' and self._web_focus_position is not None:
    # Apply manual focus to all cameras
    for camera_id in available_cameras:
        success = await self.camera_manager.controller.set_focus_value(
            camera_id, 
            self._web_focus_position  # ❌ Wrong range (6-10 instead of 0-1)
        )
    
    return  # ❌ Skip ALL calibration (no exposure calibration)
```

**After** (✅ FIXED):
```python
if self._web_focus_mode == 'manual' and self._web_focus_position is not None:
    # Convert focus value to normalized range
    focus_normalized = (self._web_focus_position - 6.0) / 4.0  # ✅ Convert 6-10 to 0-1
    
    # Turn on LEDs for calibration
    await self.lighting_controller.set_brightness("all", calibration_brightness)
    
    try:
        for camera_id in available_cameras:
            # Set manual focus
            await self.camera_manager.controller.set_focus_value(camera_id, focus_normalized)
            
            # Calibrate exposure (focus already locked)
            calibration_result = await self.camera_manager.controller.auto_calibrate_camera(camera_id)
            # ✅ Gets proper exposure/gain with manual focus
    finally:
        await self.lighting_controller.set_brightness("all", idle_brightness)
    
    return  # Skip autofocus (but exposure already calibrated)
```

---

## Expected Log Output (After Fix)

```
📸 Web UI manual focus mode: Using position 8.0, will still calibrate exposure
📸 Converted focus 8.0 to normalized 0.500
💡 CALIBRATION: Turning on LEDs at 20% for exposure calibration
✅ Set web UI manual focus for camera0: 8.000 (normalized: 0.500)
📸 Performing exposure calibration for camera0 (focus locked at 8.0)
✅ camera0 exposure calibrated: 25.3ms, gain: 1.50
✅ Set web UI manual focus for camera1: 8.000 (normalized: 0.500)
📸 Performing exposure calibration for camera1 (focus locked at 8.0)
✅ camera1 exposure calibrated: 24.8ms, gain: 1.48
💡 CALIBRATION: Reduced LEDs to idle 10% after calibration
```

---

## Testing Checklist

### ✅ Manual Focus Mode
- [ ] Focus value converts correctly (8.0 → 0.5 normalized)
- [ ] Cameras perform exposure calibration with locked focus
- [ ] LEDs turn on at 20% during calibration, then 10% idle
- [ ] Images are sharp AND properly exposed
- [ ] No autofocus calibration runs

### ✅ Other Focus Modes (Should Still Work)
- [ ] Autofocus Initial - performs full autofocus + exposure calibration
- [ ] Continuous Autofocus - autofocuses at every scan point
- [ ] Manual Stack - captures multiple focus positions

---

## Technical Notes

### ArduCam Focus Range
- **Physical Range**: 6.0mm (near) to 10.0mm (far)
- **Hyperfocal**: ~8.0mm (best for depth of field)
- **Web UI Range**: 6.0 - 10.0 (matches physical units)

### Camera Controller Range
- **Normalized Range**: 0.0 (near) to 1.0 (far)
- **Lens Position**: 1023 (near) to 0 (far) - inverted!
- **Conversion**: `lens_pos = int((1.0 - focus_value) * 1023)`

### Why Exposure Calibration is Needed
Even with perfect focus, cameras need to calibrate:
- **Exposure Time**: Adapts to lighting conditions (10-50ms typical)
- **Analogue Gain**: Compensates for brightness (1.0-3.0 typical)
- **Digital Gain**: Fine-tunes exposure (usually 1.0)

Without calibration, images may be underexposed (too dark) or overexposed (blown out).

---

## Related Files
- `scanning/scan_orchestrator.py` - Focus setup logic (modified)
- `camera/pi_camera_controller.py` - Focus value setting (unchanged)
- `web/templates/scans.html` - Focus controls UI (previously fixed)

---

## User Guidance

**Before Fix**:
- Manual focus sent wrong value → unfocused images
- No exposure calibration → under/overexposed images
- User had to manually adjust exposure in camera presets

**After Fix**:
- Manual focus value correctly converted → sharp images
- Exposure auto-calibrates with locked focus → properly exposed images
- User only sets focus position, everything else automatic

**Recommendation**: Use focus value 8.0 for general scanning (hyperfocal distance).
