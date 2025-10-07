# Manual Focus Complete Fix - Resolution & Autofocus Issues

**Date**: October 7, 2025  
**Status**: ✅ FIXED - Ready for Pi testing  
**Issues**: Manual focus running autofocus, custom resolution being rejected

---

## Problems Identified

### Problem 1: Custom Resolution Rejected ❌

**Symptom**:
```
2025-10-07 20:34:26,509 - WARNING - Failed to create custom quality profile: QualityProfile.__init__() got an unexpected keyword argument 'focus'
```

**Root Cause**:
The web UI sends quality settings with a `focus` dictionary:
```python
quality_settings = {
    'resolution': [4624, 3472],  # User's desired resolution
    'jpeg_quality': 100,
    'focus': {'mode': 'manual', 'position': 8}  # ← QualityProfile doesn't accept this!
}
```

When `create_custom_quality_profile()` receives this dictionary, it fails because `QualityProfile.__init__()` doesn't have a `focus` parameter. This causes the **entire quality profile creation to fail**, falling back to default `medium` profile (2312x1736) instead of the user's requested 4624x3472.

**Solution**:
Remove the `'focus'` key from quality_settings **before** passing to `create_custom_quality_profile()`:

```python
# Create a COPY and remove 'focus' key (focus handled separately)
quality_settings_for_profile = quality_settings.copy()
if 'focus' in quality_settings_for_profile:
    del quality_settings_for_profile['focus']

# Now create profile without 'focus' parameter
custom_quality_profile = self.profile_manager.create_custom_quality_profile(
    base_profile='medium',
    modifications=quality_settings_for_profile,  # No 'focus' key
    custom_name='temp_custom_quality'
)
```

---

### Problem 2: Autofocus Running Despite Manual Focus Mode ❌

**Symptom**:
```
2025-10-07 20:34:37,406 - INFO - 📸 Web UI manual focus mode: Using position 8
2025-10-07 20:34:37,406 - INFO - Set focus value 0.500 (lens position 511) for camera0
2025-10-07 20:34:39,513 - INFO - 📷 Camera camera0 performing initial autofocus...  ← WRONG!
2025-10-07 20:34:41,849 - INFO - ✅ Camera camera0 autofocus_cycle completed, lens: 7.153  ← OVERWROTE MANUAL FOCUS!
```

**Root Cause**:
The scan orchestrator correctly:
1. Sets manual focus to position 8 (normalized 0.500)
2. Calls `auto_calibrate_camera()` to calibrate **exposure only**

BUT `auto_calibrate_camera()` is hardcoded to **ALWAYS run autofocus**, regardless of whether manual focus was already set:

```python
# camera/pi_camera_controller.py, line ~1295
async def auto_calibrate_camera(self, camera_id: str) -> Dict[str, float]:
    # ... exposure setup ...
    
    # Step 3: Perform autofocus (ALWAYS runs!)
    focus_value = await self.auto_focus_and_get_value(camera_id)  # ← Overwrites manual focus!
```

This means:
- Orchestrator sets manual focus: **0.500** (position 8)
- Calibration runs autofocus: **0.715** (overwrites manual setting)
- Focus restoration restores: **0.500** (but images were calibrated at 0.715!)
- **Result**: Images are out of focus because exposure was calibrated at wrong focus distance

**Solution**:
Add `skip_autofocus` parameter to `auto_calibrate_camera()`:

```python
async def auto_calibrate_camera(self, camera_id: str, skip_autofocus: bool = False) -> Dict[str, float]:
    """
    Args:
        skip_autofocus: If True, skip autofocus and only calibrate exposure (for manual focus mode)
    """
    # ... exposure setup ...
    
    # Step 3: Perform autofocus ONLY if not in manual focus mode
    if skip_autofocus:
        logger.info(f"📷 Camera {camera_id} SKIPPING autofocus - manual focus mode")
        focus_value = None  # Will read current lens position from metadata
    else:
        logger.info(f"📷 Camera {camera_id} performing initial autofocus...")
        focus_value = await self.auto_focus_and_get_value(camera_id)
    
    # If autofocus was skipped, read current lens position from metadata
    if skip_autofocus and focus_value is None:
        final_metadata = picamera2.capture_metadata()
        lens_position_raw = final_metadata.get('LensPosition', None)
        if lens_position_raw is not None:
            # Convert lens position (0-1023) back to normalized (0-1)
            focus_value = 1.0 - (lens_position_raw / 1023.0)
            logger.info(f"📷 Read manual focus from metadata: {focus_value:.3f}")
```

Then update the orchestrator to pass this parameter:

```python
# scanning/scan_orchestrator.py
calibration_result = await self.camera_manager.controller.auto_calibrate_camera(
    camera_id,
    skip_autofocus=True  # CRITICAL: Skip autofocus in manual mode
)
```

---

## Complete Flow Comparison

### BEFORE (Broken) ❌

```
User selects: Manual focus position 8, Resolution 4624x3472
  ↓
Web UI sends: {'focus': {'mode': 'manual', 'position': 8}, 'resolution': [4624, 3472]}
  ↓
Orchestrator:
  1. Extracts focus: mode=manual, position=8
  2. Tries to create quality profile with 'focus' key
     → FAILS: QualityProfile doesn't accept 'focus'
     → Falls back to 'medium' profile (2312x1736)  ← WRONG RESOLUTION!
  3. Sets manual focus: 0.500 (position 8)
  4. Calls auto_calibrate_camera(camera_id)
     → Runs autofocus: gets 0.715
     → Calibrates exposure at focus 0.715  ← WRONG FOCUS!
  5. Stores focus for restoration: 0.500
  ↓
During scan:
  - Camera reconfigures to 2312x1736 (wrong resolution)
  - Focus restores to 0.500 (correct)
  - But exposure calibrated for 0.715 (wrong)
  → Images are 2312x1736 and out of focus
```

### AFTER (Fixed) ✅

```
User selects: Manual focus position 8, Resolution 4624x3472
  ↓
Web UI sends: {'focus': {'mode': 'manual', 'position': 8}, 'resolution': [4624, 3472]}
  ↓
Orchestrator:
  1. Extracts focus: mode=manual, position=8
  2. Creates COPY of quality settings, removes 'focus' key
  3. Creates quality profile WITHOUT 'focus'
     → SUCCESS: Profile created with resolution 4624x3472  ✅
  4. Sets manual focus: 0.500 (position 8)
  5. Calls auto_calibrate_camera(camera_id, skip_autofocus=True)
     → SKIPS autofocus
     → Reads current lens position: 0.500
     → Calibrates exposure at focus 0.500  ✅
  6. Stores focus for restoration: 0.500
  ↓
During scan:
  - Camera reconfigures to 4624x3472 (correct resolution)
  - Focus restores to 0.500 (correct)
  - Exposure calibrated for 0.500 (correct)
  → Images are 4624x3472 and perfectly focused  ✅
```

---

## Files Modified

### 1. `camera/pi_camera_controller.py`

**Lines 1132-1138**: Added `skip_autofocus` parameter
```python
async def auto_calibrate_camera(self, camera_id: str, skip_autofocus: bool = False) -> Dict[str, float]:
    """
    Args:
        camera_id: Camera identifier
        skip_autofocus: If True, skip autofocus and only calibrate exposure
    """
    mode_desc = "exposure-only" if skip_autofocus else "full (focus+exposure)"
    logger.info(f"🔧 CALIBRATION: Starting {mode_desc} calibration for {camera_id}")
```

**Lines 1295-1321**: Conditional autofocus execution
```python
# Step 3: Perform autofocus ONLY if not in manual focus mode
if skip_autofocus:
    logger.info(f"📷 SKIPPING autofocus - manual focus mode")
    focus_value = None
elif time.time() - calibration_start > calibration_timeout:
    focus_value = 0.5
else:
    logger.info(f"📷 Performing initial autofocus...")
    focus_value = await self.auto_focus_and_get_value(camera_id)

# Step 3.5: TWO-PASS DETECTION - ONLY if autofocus was performed
if not skip_autofocus and focus_zone_enabled and window_source == 'static_prefocus':
    # Run YOLO/edge detection and refine autofocus
```

**Lines 1436-1451**: Read lens position when autofocus skipped
```python
# If autofocus was skipped (manual mode), read current lens position
if skip_autofocus and focus_value is None:
    lens_position_raw = final_metadata.get('LensPosition', None)
    if lens_position_raw is not None:
        # Convert lens position (0-1023) to normalized (0-1)
        focus_value = 1.0 - (lens_position_raw / 1023.0)
        logger.info(f"📷 Read manual focus: {focus_value:.3f} (lens: {lens_position_raw})")
    else:
        focus_value = 0.5
        logger.warning(f"⚠️ Could not read lens position, using default 0.5")
```

### 2. `scanning/scan_orchestrator.py`

**Lines 2697-2712**: Remove 'focus' key before creating quality profile
```python
if quality_settings:
    self.logger.info(f"🎯 Creating temporary custom quality profile with settings: {quality_settings}")
    try:
        # Create COPY and remove 'focus' key (QualityProfile doesn't accept it)
        quality_settings_for_profile = quality_settings.copy()
        if 'focus' in quality_settings_for_profile:
            del quality_settings_for_profile['focus']
        
        # Create profile without 'focus' parameter
        custom_quality_profile = self.profile_manager.create_custom_quality_profile(
            base_profile='medium',
            modifications=quality_settings_for_profile,  # No 'focus' key
            custom_name='temp_custom_quality'
        )
```

**Lines 3523-3527**: Pass `skip_autofocus=True` for manual focus mode
```python
self.logger.info(f"📸 Performing exposure calibration for {camera_id} (focus locked at {self._web_focus_position})")
calibration_result = await self.camera_manager.controller.auto_calibrate_camera(
    camera_id,
    skip_autofocus=True  # CRITICAL: Skip autofocus, only calibrate exposure
)
```

---

## Expected Log Output (After Fix)

### Successful Manual Focus Scan

```
2025-10-07 XX:XX:XX - INFO - 🎯 Creating temporary custom quality profile with settings: {...}
2025-10-07 XX:XX:XX - INFO - ✅ Created custom quality profile: temp_custom_quality  ← Success!
2025-10-07 XX:XX:XX - INFO - 📸 Applied web UI focus settings: mode=manual, position=8
2025-10-07 XX:XX:XX - INFO - 📸 Converted focus 8 to normalized 0.500
2025-10-07 XX:XX:XX - INFO - Set focus value 0.500 (lens position 511) for camera0
2025-10-07 XX:XX:XX - INFO - ✅ Set web UI manual focus for camera0: 8.000 (normalized: 0.500)
2025-10-07 XX:XX:XX - INFO - 📸 Performing exposure calibration for camera0 (focus locked at 8)
2025-10-07 XX:XX:XX - INFO - 🔧 CALIBRATION: Starting exposure-only calibration for camera0  ← Exposure only!
2025-10-07 XX:XX:XX - INFO - 📷 SKIPPING autofocus - manual focus mode  ← No autofocus!
2025-10-07 XX:XX:XX - INFO - 📷 Read manual focus from metadata: 0.500 (lens: 511)  ← Correct focus!
2025-10-07 XX:XX:XX - INFO - ✅ camera0 exposure calibrated: 16.0ms, gain: 1.67
...
2025-10-07 XX:XX:XX - INFO - 📷 STANDARD MODE: Reconfiguring for 4624x3472  ← Correct resolution!
2025-10-07 XX:XX:XX - INFO - 🔄 Reapplying stored focus 0.500 for camera0  ← Focus restored!
2025-10-07 XX:XX:XX - INFO - ✅ Restored focus 0.500 (lens position 511) for camera0
2025-10-07 XX:XX:XX - INFO - ISP-managed capture successful for camera 0
```

---

## Testing Checklist

**Before Testing**:
- [ ] Pull latest code to Raspberry Pi
- [ ] Restart scanner system

**Test 1: Manual Focus with Custom Resolution**:
- [ ] Set focus mode: Manual
- [ ] Set focus position: 8.0
- [ ] Set resolution: 4624x3472
- [ ] Start scan
- [ ] **Verify logs**: "SKIPPING autofocus - manual focus mode"
- [ ] **Verify logs**: "Read manual focus from metadata: 0.500"
- [ ] **Verify logs**: "Reconfiguring for 4624x3472" (not 2312x1736)
- [ ] **Verify logs**: "Restored focus 0.500 (lens position 511)"
- [ ] **Check images**: Sharp focus, correct resolution

**Test 2: All Focus Modes**:
- [ ] Manual: Focus stays at 8.0, no autofocus
- [ ] Autofocus Initial: Runs autofocus once at start
- [ ] Continuous: Runs autofocus at every point
- [ ] Manual Stack: Multiple focus positions per point

**Test 3: Resolution Independence**:
- [ ] 2312x1736: Should work
- [ ] 4624x3472: Should work
- [ ] 9152x6944: Should work (if memory allows)

---

## Success Criteria

✅ **Resolution Applied**: Images are captured at user-selected resolution (e.g., 4624x3472), not default 2312x1736  
✅ **Manual Focus Preserved**: No autofocus runs during calibration when in manual focus mode  
✅ **Correct Calibration**: Exposure calibrated at the same focus distance used for capture  
✅ **Focus Persistence**: Manual focus value (0.500) restored after every camera reconfiguration  
✅ **Sharp Images**: All images in scan are consistently sharp from first to last  

---

## Rollback Plan

If issues occur, revert these changes:
1. `camera/pi_camera_controller.py` - Remove `skip_autofocus` parameter
2. `scanning/scan_orchestrator.py` - Remove `skip_autofocus=True` argument and 'focus' key removal

The system will fall back to previous behavior (autofocus always runs, resolution defaults to medium).
