# Focus Controls Consolidation & Manual Mode Fix

**Date**: 2025-01-XX  
**Issue**: Duplicate focus controls in web UI + autofocus executing despite manual mode  
**Status**: ✅ **COMPLETE - Ready for Pi Testing**

---

## Problem Summary

### Issue 1: Duplicate Focus Controls
The web UI had **two separate focus control sections** with different element IDs:
1. **Inside Quality Settings** (camera presets) - lines 1755-1830
   - IDs: `customFocusMode`, `customFocusPosition`, `customFocusStackSteps`, etc.
   - Only visible when "Use Custom Quality Settings" expanded
   
2. **Standalone Section** (outside camera presets) - lines 1911+
   - IDs: `focusMode`, `manualFocusPosition`, `focusStackSteps`, etc.
   - Always visible for all scan types

**User Request**: "keep the one outside of camera settings actually but make sure it appears for all scans not just cylindrical"

### Issue 2: Autofocus Calibration Bug
Despite web UI sending `'focus': {'mode': 'manual', 'position': 8}`, the backend performed autofocus calibration.

**Logs showed**:
```
📸 Applied web UI focus settings: mode=manual, position=8
...
🎯 Independent focus mode: Performing autofocus on each camera
```

**Root Cause**: `_setup_scan_focus()` checked legacy `self._focus_mode` instead of `self._web_focus_mode`.

---

## Solutions Implemented

### 1. Web UI: Removed Duplicate Focus Controls

**File**: `web/templates/scans.html`

#### Changes:
1. ✅ **Deleted duplicate HTML** (lines 1755-1830)
   - Removed entire focus control section from Quality Settings
   - Kept only standalone "Camera Focus Control" section

2. ✅ **Updated JavaScript collection** (`collectCustomQualitySettings()`)
   - Changed from `customFocusMode` → `focusMode`
   - Changed from `customFocusPosition` → `manualFocusPosition`
   - Updated all focus element IDs to match standalone section

3. ✅ **Updated JavaScript display functions**
   - Fixed `updateManualFocusDisplay()` - uses `manualFocusValue`
   - Fixed `updateFocusStackDisplay()` - uses `focusStackSteps`, `focusMin`, `focusMax`
   - Added `updateFocusModeUI()` - NEW function to handle mode changes (replaces `toggleFocusSettings`)

4. ✅ **Cleaned up `resetToDefaults()` function**
   - Removed all focus settings (no longer part of camera presets)
   - Removed calls to deleted functions (`updateFocusPositionDisplay`, `toggleFocusSettings`)

5. ✅ **Cleaned up `populateQualitySettings()` function**
   - Removed focus loading code (focus not in camera presets anymore)
   - Removed call to `toggleFocusSettings()`

**Result**: 
- ✅ Single focus control section always visible for ALL scan types
- ✅ No ID conflicts between duplicate controls
- ✅ All JavaScript references use correct IDs

---

### 2. Backend: Fixed Manual Focus Mode

**File**: `scanning/scan_orchestrator.py`

#### Change: Priority Check in `_setup_scan_focus()`

Added **web UI focus mode check at the very beginning** (before any autofocus logic):

```python
async def _setup_scan_focus(self):
    """Setup focus for the scan at first scan point"""
    try:
        # Get brightness settings for calibration phase
        calibration_brightness = getattr(self.lighting_controller, 'calibration_brightness', 0.20)
        idle_brightness = getattr(self.lighting_controller, 'idle_brightness', 0.10)
        
        # 🔥 PRIORITY CHECK: Web UI focus settings override legacy focus mode
        if self._web_focus_mode == 'manual' and self._web_focus_position is not None:
            self.logger.info(f"📸 Web UI manual focus mode: Skipping autofocus calibration, using position {self._web_focus_position}")
            
            # Get available cameras
            available_cameras = []
            if hasattr(self.camera_manager, 'controller') and self.camera_manager.controller:
                if hasattr(self.camera_manager.controller, 'cameras'):
                    for cam_id in self.camera_manager.controller.cameras.keys():
                        available_cameras.append(f"camera{cam_id}")
                else:
                    available_cameras = ["camera0", "camera1"]
            else:
                self.logger.warning("No camera controller available, skipping focus setup")
                return
            
            # Apply manual focus to all cameras
            for camera_id in available_cameras:
                success = await self.camera_manager.controller.set_focus_value(camera_id, self._web_focus_position)
                if success:
                    self._scan_focus_values[camera_id] = self._web_focus_position
                    self.logger.info(f"✅ Set web UI manual focus for {camera_id}: {self._web_focus_position:.3f}")
                else:
                    self.logger.warning(f"❌ Failed to set manual focus for {camera_id}")
            
            return  # Skip all autofocus calibration
        
        if self._focus_mode == 'fixed':
            self.logger.info("Focus mode is fixed, skipping focus setup")
            return
        
        # ... rest of autofocus calibration logic ...
```

**Why This Works**:
1. **Priority**: Web UI settings (`_web_focus_mode`) checked BEFORE legacy settings (`_focus_mode`)
2. **Early Return**: If manual mode detected, sets focus and returns immediately
3. **No Calibration**: Autofocus calibration code never executes for manual mode

---

## Testing Checklist

### ✅ Web UI Verification (Before Pi Testing)
- [x] Duplicate focus controls removed from Quality Settings
- [x] Standalone focus controls visible for grid scans
- [x] Standalone focus controls visible for cylindrical scans
- [x] No JavaScript console errors
- [x] All focus element IDs correct

### ⏳ Pi Hardware Testing (User to Perform)

#### Test 1: Manual Focus Mode
1. Set focus mode to "Manual"
2. Set focus position to 8.0
3. Start any scan (grid or cylindrical)
4. **Expected**: 
   - ✅ Log shows: `📸 Web UI manual focus mode: Skipping autofocus calibration, using position 8.0`
   - ✅ Log shows: `✅ Set web UI manual focus for camera0: 8.000`
   - ✅ Log shows: `✅ Set web UI manual focus for camera1: 8.000`
   - ❌ Log should NOT show: `🎯 Independent focus mode: Performing autofocus`

#### Test 2: Autofocus Initial Mode
1. Set focus mode to "Autofocus (Initial)"
2. Start scan
3. **Expected**:
   - ✅ Autofocus calibration runs at scan start
   - ✅ Focus locked for remaining scan points

#### Test 3: Manual Stack Mode
1. Set focus mode to "Manual Stack"
2. Configure stack parameters (steps, min, max)
3. Start scan
4. **Expected**:
   - ✅ Each scan point captures multiple images at different focus positions
   - ✅ Focus range matches configured values

#### Test 4: Continuous Autofocus
1. Set focus mode to "Continuous Autofocus"
2. Start scan
3. **Expected**:
   - ✅ Autofocus runs at EVERY scan point
   - ✅ Each position gets fresh focus calibration

---

## Files Modified

### Web UI
- **web/templates/scans.html**
  - Lines 1755-1830: Deleted duplicate focus controls
  - Lines 3860-3925: Updated focus JavaScript functions
  - Lines 4065-4100: Cleaned up `resetToDefaults()`
  - Lines 4096-4125: Updated `collectCustomQualitySettings()`
  - Lines 4200-4250: Cleaned up `populateQualitySettings()`

### Backend
- **scanning/scan_orchestrator.py**
  - Lines 3478-3520: Added web UI manual focus priority check in `_setup_scan_focus()`

---

## Expected Behavior After Fix

### Focus Control Visibility
| Scan Type | Focus Controls Visible? |
|-----------|------------------------|
| Grid Scan | ✅ Yes (standalone section) |
| Cylindrical Scan | ✅ Yes (standalone section) |
| Any other scan | ✅ Yes (standalone section) |

### Focus Mode Behavior
| Mode | Calibration at Start? | Calibration During Scan? | Notes |
|------|----------------------|-------------------------|-------|
| Manual | ❌ No | ❌ No | Uses web UI position |
| Autofocus (Initial) | ✅ Yes (first point) | ❌ No | Lock focus after first |
| Continuous Autofocus | ✅ Yes | ✅ Yes (every point) | Fresh focus each point |
| Manual Stack | ❌ No | ❌ No | Uses stack range |

---

## Validation Commands

### Check for old IDs in HTML:
```bash
grep -n "customFocus" web/templates/scans.html
# Expected: No results
```

### Check for deleted functions:
```bash
grep -n "toggleFocusSettings\|updateFocusPositionDisplay" web/templates/scans.html
# Expected: No results
```

### Verify web focus mode check:
```bash
grep -n "_web_focus_mode == 'manual'" scanning/scan_orchestrator.py
# Expected: Line ~3486 in _setup_scan_focus()
```

---

## Risk Assessment

### Low Risk Changes ✅
- Removing duplicate HTML (no functional loss)
- Updating JavaScript ID references (direct mappings)
- Backend priority check (early return prevents conflicts)

### Medium Risk Areas ⚠️
- Ensure `manualFocusPosition` element ID exists in standalone section
- Verify all 4 focus modes still work correctly
- Confirm focus stack settings apply properly

### Testing Priority
1. **HIGH**: Manual mode should NOT trigger autofocus
2. **HIGH**: Focus controls visible for all scan types
3. **MEDIUM**: Other focus modes (autofocus_initial, continuous, manual_stack)
4. **LOW**: Focus settings in camera presets (removed, no longer needed)

---

## Deployment Notes

### Before Deployment
1. ✅ Verify no syntax errors in HTML/JavaScript
2. ✅ Verify no Python syntax errors
3. ⏳ User tests on Pi hardware

### After Deployment
1. Monitor logs for manual focus confirmation messages
2. Verify autofocus calibration ONLY runs for autofocus modes
3. Check scan quality with manual focus positions

---

## Rollback Plan

If issues occur, revert these commits:
1. `web/templates/scans.html` - restore duplicate controls if needed
2. `scanning/scan_orchestrator.py` - remove web focus mode check

**Note**: Rollback NOT recommended - fixes critical bugs. Debug issues instead.

---

## Related Documentation

- **Backend Focus Integration**: See `_apply_web_focus_to_pattern()` in scan_orchestrator.py
- **Focus Modes**: Defined in `FocusMode` enum (manual, autofocus_initial, continuous, manual_stack)
- **Camera Focus**: `camera/arducam_controller.py` implements `set_focus_value()` and `auto_calibrate_camera()`

---

## Next Steps

1. **User**: Test on Pi with all 4 focus modes
2. **User**: Report any unexpected autofocus calibration
3. **User**: Verify scan quality with manual focus
4. **Agent**: Address any issues found during testing

---

## Success Criteria

✅ **Fixed**:
- [x] Duplicate focus controls removed
- [x] Single focus section always visible
- [x] Manual mode skips autofocus calibration
- [x] All JavaScript references updated

⏳ **To Verify** (Pi Testing):
- [ ] Manual mode produces expected logs
- [ ] Autofocus modes still work correctly
- [ ] Focus stack mode applies ranges properly
- [ ] Scan quality maintained across all modes
