# Manual Focus Fix - Quick Reference

## Problem
Scan manual focus setting 8.1mm but camera autofocusing to 0.985 (lens position 15) instead of 0.525 (lens position 485).

## Root Cause
`auto_calibrate_camera()` with `skip_autofocus=True` still calls `capture_metadata()` which triggers ArduCam firmware autofocus, resetting the lens position.

## Solution
Use dashboard's simple approach - just set focus without calibration.

## Code Changed
**File:** `scanning/scan_orchestrator.py`  
**Method:** `_setup_focus_at_first_scan_point()`  
**Lines:** ~3514-3547

**Changed from:** Calling `auto_calibrate_camera()` after setting focus  
**Changed to:** Only calling `set_focus_value()` (like dashboard does)

## Expected Behavior After Fix

### Logs:
```
✅ Set web UI manual focus for camera0: 8.100mm (normalized: 0.525)
📸 camera0 will use auto-exposure during scan (manual focus locked)
✅ Manual focus setup complete - using dashboard approach (no calibration)
```

### Metadata:
- Focus: **0.525** (not 0.985) ✅
- LensPosition: **485** (not 15) ✅

### Images:
- Sharp at 8.1mm focus distance ✅
- Auto-exposure works during scan ✅

## Testing on Pi
1. Pull latest code from GitHub
2. Restart scanner service
3. Set manual focus to 8.1mm in web UI
4. Start scan
5. Check logs for "using dashboard approach"
6. Verify images are sharp at expected distance

## What Changed
- **Before:** Set focus → Calibrate exposure (breaks focus) → Focus broken ❌
- **After:** Set focus → Done (like dashboard) → Focus works ✅

## Why This Works
Dashboard manual focus works perfectly because it's simple - just sets the focus and doesn't call calibration functions that trigger the ArduCam firmware bug.

The scan now does the same thing!
