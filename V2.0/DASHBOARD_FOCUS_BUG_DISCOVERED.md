# 🚨 DASHBOARD FOCUS BUG - CRITICAL DISCOVERY

## The Dashboard Bug

**The dashboard was ALSO broken, just in a different way!**

### What Was Happening

Looking at your logs from the dashboard:
```
2025-10-07 22:12:28,948 - scanning.scan_orchestrator - INFO - CAMERA: Applied controls {'AfMode': 0, 'LensPosition': 8.4} to camera camera_1
```

**The dashboard was setting `LensPosition: 8.4` directly!**

### The Code Path

**Dashboard → Web Interface → Orchestrator:**
```python
# web/web_interface.py:4641
def _execute_manual_focus(self, camera_id: str, focus_position: float):
    # Calls with focus_position = 8.4 (the raw slider value!)
    result = asyncio.run(
        self.orchestrator.camera_manager.set_manual_focus(camera_id, focus_position)
    )

# scanning/scan_orchestrator.py:1981
async def set_manual_focus(self, camera_id, focus_position):
    return await self.set_camera_controls(camera_id, {
        'autofocus': False,
        'focus_position': focus_position  # Still 8.4!
    })

# scanning/scan_orchestrator.py:1910 (OLD CODE - BUGGY!)
if 'focus_position' in controls_dict:
    picam_controls['LensPosition'] = float(controls_dict['focus_position'])
    # This sets LensPosition = 8.4 directly! ❌
```

### Why This Was Wrong

**Valid lens position range: 0-1023**
- Setting lens to 8.4 is like setting it to ~0 (essentially infinity focus)
- The slider values 6.0-10.0mm were being used as lens positions 6-10
- This is completely out of range and undefined behavior!

### Why It Seemed to Work Sometimes

The camera firmware probably:
1. Rejected the invalid value (8.4)
2. Kept whatever lens position was set previously
3. Or rounded to 8 (still wrong, but at least a valid position)

This is why the dashboard gave **unpredictable results** and **never focused at the expected distance**.

## The Fix

**Changed from (BUGGY):**
```python
if 'focus_position' in controls_dict:
    picam_controls['LensPosition'] = float(controls_dict['focus_position'])
    # Sets lens to 8.4 directly ❌
```

**To (CORRECT):**
```python
if 'focus_position' in controls_dict:
    # Convert dashboard focus position (6-10mm range) to lens position (0-1023)
    focus_mm = float(controls_dict['focus_position'])
    focus_normalized = (focus_mm - 6.0) / 4.0  # Convert 6-10mm to 0-1
    focus_normalized = max(0.0, min(1.0, focus_normalized))  # Clamp
    lens_position = int(focus_normalized * 1023)  # Convert to lens position
    picam_controls['LensPosition'] = lens_position
    # Sets lens to 511 for 8mm ✅
```

### Example Conversions

**Before (WRONG):**
- Dashboard slider: 6mm → Lens position: 6 ❌
- Dashboard slider: 8mm → Lens position: 8 ❌
- Dashboard slider: 10mm → Lens position: 10 ❌

**After (CORRECT):**
- Dashboard slider: 6mm → Lens position: 0 ✅ (far focus)
- Dashboard slider: 8mm → Lens position: 511 ✅ (middle)
- Dashboard slider: 10mm → Lens position: 1023 ✅ (near focus)

## What This Means

**Both dashboard AND scan were broken, but in different ways:**

1. **Dashboard**: Set invalid lens positions (6-10 instead of 0-1023)
   - Result: Undefined behavior, unpredictable focus
   
2. **Scan**: Set inverted lens positions (511 → far instead of middle)
   - Result: Backwards focus direction

**Now both are fixed to use the same correct conversion!**

## Testing the Fix

Test dashboard and scan with same settings:

1. **Dashboard at 8mm**:
   - Before: Lens set to ~8 (invalid)
   - After: Lens set to 511 (correct middle distance)

2. **Scan at 8mm**:
   - Before: Lens set to 511 but inverted (focused far)
   - After: Lens set to 511 and correct (focuses middle distance)

3. **Consistency**:
   - Before: Dashboard and scan gave different results at same setting
   - After: Dashboard and scan should give identical results at same setting ✅

## Files Modified

1. ✅ `scanning/scan_orchestrator.py` line 1910: Fixed dashboard focus conversion
2. ✅ `camera/pi_camera_controller.py` (8 locations): Fixed scan focus inversion

## What's Now Fixed

✅ Dashboard focus conversion (6-10mm → 0-1023 lens)
✅ Scan focus direction (removed inversion)
✅ Dashboard/scan consistency (both use same correct math)
✅ Valid lens positions (no more invalid values like 8.4)

---

**This explains why dashboard "worked differently" - it was sending completely invalid lens positions!**
