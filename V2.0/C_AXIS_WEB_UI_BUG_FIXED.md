# C-Axis Web UI Display Bug - ROOT CAUSE FOUND AND FIXED

## Problem Summary
Web UI dashboard displayed `C: 0.0°` despite FluidNC correctly reporting C-axis position (e.g., C=-25.000). The value would "flash" briefly to the correct value after a jog command, then reset to 0.

## Root Cause Discovery

### Debug Logging Revealed
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,0.000,0.000,-25.000' → 6 coordinates  ✅ Correct
🔍 PARSED (6 axes): [200.000, 137.500, 0.000, 0.000, 0.000, -25.000] → C=-25.000  ✅ Correct
🎯 Fresh position after jog: Position(X:200.000, Y:137.500, Z:0.000, C:-25.000)   ✅ Correct
🔍 STATUS API: Sending C-axis to web UI: 0.0° (Position C:0.000)                  ❌ WRONG!
```

### Timeline of Bug
1. **User jogs C-axis** → G-code command sent
2. **move_relative() executes** → Calls `_update_current_position()`
3. **_update_current_position()** → Correctly sets `C=-25.0` using FluidNC value ✅
4. **Jog completion log** shows correct C=-25.0 ✅
5. **BUT THEN...**
6. **FluidNC sends status update** → Triggers `_on_status_update()` callback
7. **_on_status_update()** uses **WRONG KEY** → `c=status.position.get('a', 0.0)` ❌
8. **Position C value reset to 0** because key 'a' doesn't exist in dictionary!
9. **Status API reads position** → Shows C=0.0 ❌

## The Bug: Wrong Dictionary Key

### File: `motion/simplified_fluidnc_controller_fixed.py`
### Location: Line 1316 in `_on_status_update()` method

**BEFORE (WRONG):**
```python
def _on_status_update(self, status: FluidNCStatus):
    """Handle status updates from protocol"""
    try:
        if status.position:
            self.current_position = Position4D(
                x=status.position.get('x', 0.0),
                y=status.position.get('y', 0.0),
                z=status.position.get('z', 0.0),
                c=status.position.get('a', 0.0)  # ❌ WRONG KEY! 'a' doesn't exist
            )
```

**AFTER (FIXED):**
```python
def _on_status_update(self, status: FluidNCStatus):
    """Handle status updates from protocol"""
    try:
        if status.position:
            # CRITICAL FIX: Use 'c' key, not 'a'! FluidNC reports C at last position (index [5])
            # The parser correctly extracts it as 'c', so we must use 'c' here too
            self.current_position = Position4D(
                x=status.position.get('x', 0.0),
                y=status.position.get('y', 0.0),
                z=status.position.get('z', 0.0),
                c=status.position.get('c', 0.0)  # ✅ CORRECT KEY!
            )
```

## Why Other Axes (X, Y, Z) Worked But C Didn't

### X, Y, Z Axes
- Parser: `'x': parsed_coords[0]` ✅
- _update_current_position(): `x=status.position.get('x', 0.0)` ✅
- **_on_status_update()**: `x=status.position.get('x', 0.0)` ✅
- **Result**: Consistent key usage across all code paths ✅

### C Axis (BEFORE FIX)
- Parser: `'c': parsed_coords[-1]` ✅
- _update_current_position(): `c=status.position.get('c', 0.0)` ✅
- **_on_status_update()**: `c=status.position.get('a', 0.0)` ❌ **WRONG KEY!**
- **Result**: Inconsistent key usage caused reset to 0 ❌

## Why the "Flash" Behavior Happened

1. **Jog executes** → `move_relative()` → `_update_current_position()` → Sets C=-25 ✅
2. **Jog API returns** → Logs show C=-25 ✅
3. **Web UI briefly displays C=-25** (from jog response) ✅
4. **FluidNC sends next status update** (happens continuously)
5. **_on_status_update() triggered** → Uses key 'a' → Gets None → Defaults to 0 ❌
6. **Web UI updates from status API** → Shows C=0 ❌
7. **User sees "flash"** - value changes from -25 back to 0 within 1 second

## The Fix

Changed one line in `_on_status_update()`:
```python
# OLD: c=status.position.get('a', 0.0)  # Wrong key
# NEW: c=status.position.get('c', 0.0)  # Correct key
```

This ensures the status callback uses the **same key 'c'** that the parser creates.

## Why This Bug Was Hard to Find

1. **FluidNC parsing was correct** - Used 'c' key ✅
2. **Position update was correct** - Used 'c' key ✅
3. **Jog completion was correct** - Showed C=-25 ✅
4. **But status callback was wrong** - Used 'a' key ❌

The callback ran **after** the jog completed, silently resetting C to 0 every time FluidNC sent a status update (which happens continuously in the background).

## Files Modified

1. **motion/simplified_fluidnc_controller_fixed.py** (Line ~1316)
   - Fixed `_on_status_update()` to use 'c' instead of 'a'

2. **web/web_interface.py** (Lines ~2380-2410)
   - Added debug logging (can be removed after verification)

## Testing

Restart web interface and test:
```bash
python run_web_interface.py
```

**Expected Behavior:**
1. Jog C-axis (e.g., +25°)
2. Dashboard shows C: 25.0° ✅
3. Value **persists** (no reset to 0) ✅
4. Logs show:
   ```
   🔍 PARSED [...] → C=25.000
   🎯 Fresh position after jog: Position(C:25.000)
   🔍 STATUS API: Sending C-axis to web UI: 25.0°
   ```

## Historical Context

This bug existed because:
- Original code assumed FluidNC used 'a' for 4th axis (common convention)
- Parser was updated to use 'c' (following FluidNC's actual 6-axis output)
- _update_current_position() was updated to use 'c'
- **But _on_status_update() was never updated** ← THE BUG

The status callback is called **frequently** by FluidNC status messages, so it continuously overwrote the correct C value with 0.

## Lesson Learned

When updating coordinate parsing logic:
1. ✅ Update parser (simplified_fluidnc_protocol_fixed.py)
2. ✅ Update position update method (_update_current_position)
3. ❌ **MISSED** Update status callback (_on_status_update) ← CRITICAL

**Always search for ALL places that access position dictionaries when changing key names!**
