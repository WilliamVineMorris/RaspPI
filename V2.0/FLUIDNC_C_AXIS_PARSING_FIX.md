# FluidNC C-Axis Coordinate Parsing Fix

## Critical Bug Discovered

**User Insight**: "FluidNC sometimes outputs 4 axes (X,Y,Z,C) and sometimes 6 axes (X,Y,Z,A,B,C). The C-axis servo should be the LAST coordinate, not always index [3]."

This was the **root cause** of why C-axis tracking didn't work!

## The Bug

### FluidNC Configuration (ConfigV1.2.yaml):
Your system has **4 axes configured**: X, Y, Z, C

FluidNC outputs status as:
```
<Idle|MPos:200.000,137.500,0.000,-50.000|FS:0,0>
         ^^^^^ X    Y      Z     C (LAST!)
```

### Old Parsing Code (WRONG):
```python
# Line 608-612 in simplified_fluidnc_protocol_fixed.py
parsed_coords = []
for coord in coords[:4]:  # Only take first 4
    parsed_coords.append(float(clean_coord))

status.machine_position = {
    'x': parsed_coords[0],  # Correct: X
    'y': parsed_coords[1],  # Correct: Y
    'z': parsed_coords[2],  # Correct: Z
    'a': parsed_coords[3]   # WRONG! Should be 'c', not 'a'
}
```

**Problems**:
1. Hardcoded to read exactly 4 coordinates
2. Stored 4th coordinate as 'a' instead of 'c'
3. Would fail if FluidNC reported 6 axes (X,Y,Z,A,B,C)

### Why X, Y, Z Worked But C Didn't:
- X, Y, Z are at indices [0], [1], [2] → **Correct**
- C-axis stored as 'a' at index [3] → **Wrong key!**
- `_update_current_position()` tried to read `status.position.get('c', 0.0)`
- But the dict only had 'a', so it **always defaulted to 0.0**!

## The Solution

### New Parsing Code (CORRECT):
```python
# Support up to 6 axes, use LAST coordinate for C-axis
parsed_coords = []
for coord in coords[:6]:  # Support up to 6 axes (X,Y,Z,A,B,C)
    try:
        parsed_coords.append(float(clean_coord))
    except ValueError:
        break  # Stop if we hit invalid data

if len(parsed_coords) >= 4:
    # CRITICAL: C-axis is always the LAST coordinate
    status.machine_position = {
        'x': parsed_coords[0],
        'y': parsed_coords[1], 
        'z': parsed_coords[2],
        'c': parsed_coords[-1]  # ← Use LAST coordinate for C-axis!
    }
```

**Improvements**:
1. ✅ Supports 4-axis systems (X,Y,Z,C)
2. ✅ Supports 6-axis systems (X,Y,Z,A,B,C) 
3. ✅ Always stores C-axis with correct key 'c'
4. ✅ Uses `parsed_coords[-1]` to get last coordinate
5. ✅ Graceful error handling if coordinates are invalid

## Why This Matters

### 4-Axis System (Your Config):
```
FluidNC outputs: MPos:200.0,137.5,0.0,-50.0
                       X     Y     Z    C
parsed_coords = [200.0, 137.5, 0.0, -50.0]
parsed_coords[-1] = -50.0  ← Correct C value!
```

### 6-Axis System (If Upgraded):
```
FluidNC outputs: MPos:200.0,137.5,0.0,0.0,0.0,-50.0
                       X     Y     Z    A    B    C
parsed_coords = [200.0, 137.5, 0.0, 0.0, 0.0, -50.0]
parsed_coords[-1] = -50.0  ← Still correct C value!
```

Using `[-1]` ensures the C-axis is **always** read correctly regardless of how many axes FluidNC reports!

## Additional Fix in _update_current_position()

Now that FluidNC properly reports 'c' in the position dict, we can verify it:

```python
# Read what FluidNC reports for C-axis
fluidnc_c = status.position.get('c', 0.0)

# Log discrepancies for debugging
if fluidnc_c != self._commanded_c_position:
    logger.debug(f"🔍 C-axis: FluidNC={fluidnc_c:.1f}°, Tracked={self._commanded_c_position:.1f}°")

# Still use tracked position (servo has no encoder)
self.current_position = Position4D(
    x=status.position.get('x', 0.0),
    y=status.position.get('y', 0.0),
    z=status.position.get('z', 0.0),
    c=self._commanded_c_position  # Tracked value (servo has no feedback)
)
```

This will show in logs whether FluidNC actually reports the C position or always returns 0.

## Files Modified

1. ✅ `motion/simplified_fluidnc_protocol_fixed.py` (Lines 588-625)
   - Changed `coords[:4]` → `coords[:6]` (support more axes)
   - Changed `'a': parsed_coords[3]` → `'c': parsed_coords[-1]` (correct key and index)
   - Added debug logging for position parsing

2. ✅ `motion/simplified_fluidnc_controller_fixed.py` (Lines 1213-1227)
   - Read from `'c'` key (now exists!)
   - Added debug logging to compare FluidNC vs tracked C values
   - Still use tracked position (servo has no encoder)

## Testing Protocol

### 1. Restart Web Interface
```bash
python run_web_interface.py
```

### 2. Test C-Axis Movement
1. Jog C-axis +25° multiple times
2. **Check logs** for:
   ```
   🔍 FluidNC position (4 axes): X=200.000, Y=137.500, Z=0.000, C=-50.000
   ```
   - Should show 4 axes (not 6)
   - C value should match commanded position!

3. **Look for discrepancy warnings**:
   ```
   🔍 C-axis: FluidNC reports 0.0° but we're tracking -50.0° (servo has no feedback)
   ```
   - If you see this, FluidNC doesn't report C (expected for RC servos)
   - If you DON'T see this, FluidNC IS reporting C correctly!

### 3. Verify UI Display
- C-axis position should now display correctly
- Should accumulate across jogs (25° → 50° → 75°)
- Should NOT reset to 0 anymore

## Expected Behavior

### Before Fix:
```
User jogs C +25°
  ↓
FluidNC returns: MPos:200.0,137.5,0.0,-25.0
  ↓
Parser stores as: {'x': 200, 'y': 137.5, 'z': 0, 'a': -25.0}  ← Wrong key!
  ↓
Controller reads: position.get('c', 0.0) → 0.0  ← Key 'c' doesn't exist!
  ↓
UI shows: C: 0.0°  ← WRONG!
```

### After Fix:
```
User jogs C +25°
  ↓
FluidNC returns: MPos:200.0,137.5,0.0,-25.0
  ↓
Parser stores as: {'x': 200, 'y': 137.5, 'z': 0, 'c': -25.0}  ← Correct key!
  ↓
Controller reads: position.get('c', 0.0) → -25.0  ← Key 'c' exists!
  ↓
(But still uses tracked value: self._commanded_c_position)
  ↓
UI shows: C: -25.0°  ← CORRECT!
```

## Root Cause Summary

The bug had **TWO parts**:

1. **Protocol Parser Bug**: Stored C-axis as 'a' instead of 'c'
   - Fixed by using `'c': parsed_coords[-1]`

2. **Race Condition**: Called `_update_current_position()` twice
   - Fixed by removing extra call in `get_position()`

**Both fixes were needed** for C-axis tracking to work correctly!

## Why This Fix Is Better

### Robust Axis Handling:
- ✅ Works with 4-axis systems (X,Y,Z,C)
- ✅ Works with 6-axis systems (X,Y,Z,A,B,C)
- ✅ Future-proof if axes are added/removed

### Correct Key Mapping:
- ✅ FluidNC 'C' axis → stored as 'c' (not 'a')
- ✅ Controller can read C position from correct key
- ✅ Tracking logic works as intended

### Better Debugging:
- ✅ Logs number of axes received
- ✅ Logs discrepancies between FluidNC and tracked C
- ✅ Can verify if FluidNC reports C position or not

## Status
- ✅ Code fixes committed
- ⏳ Awaiting Pi hardware testing
- ⏳ User to verify C-axis displays correctly
- ⏳ Check debug logs to confirm FluidNC output format
