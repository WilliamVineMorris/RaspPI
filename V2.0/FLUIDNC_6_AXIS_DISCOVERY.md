# BREAKTHROUGH: FluidNC Reports 6 Axes with Correct C Position!

## Critical Discovery from Debug Logs

User provided debug output showing:
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,0.000,0.000,25.000' → 6 coordinates
🔍 PARSED (6 axes): [200.000, 137.500, 0.000, 0.000, 0.000, 25.000] → C=25.000
```

## Key Findings

### 1. FluidNC Outputs 6 Axes, Not 4!
```
Position[0] = 200.000  → X-axis (linear)
Position[1] = 137.500  → Y-axis (linear)  
Position[2] = 0.000    → Z-axis (rotation)
Position[3] = 0.000    → A-axis (unused?)
Position[4] = 0.000    → B-axis (unused?)
Position[5] = 25.000   → C-axis (SERVO!)
```

**FluidNC Configuration Mystery**: 
- Config file shows 4 axes (X, Y, Z, C)
- But FluidNC **outputs 6 axes** in MPos
- Extra axes (A, B) are always 0.000
- C-axis is position [5] (last coordinate)

### 2. C-Axis IS Reported Correctly!
FluidNC **DOES** report the actual C-axis position (25.000), not 0!

**This contradicts the assumption that RC servos have no position feedback.**

**Possible Explanations**:
1. FluidNC internally tracks commanded servo position (not actual physical feedback)
2. The servo has some form of feedback we didn't know about
3. FluidNC's G-code parser maintains a virtual position for all axes

**Most Likely**: FluidNC tracks the **commanded** position for all axes, including servos, even without physical encoders.

### 3. Parser Using [-1] Was CORRECT!
```python
'c': parsed_coords[-1]  # Last coordinate = C-axis
```

Using `[-1]` (last coordinate) correctly extracts the C-axis regardless of:
- 4-axis systems: parsed_coords[-1] = position[3]
- 6-axis systems: parsed_coords[-1] = position[5]

**This was the right fix!**

## Why UI Still Showed 0

The parsing was **working perfectly**. The problem was:

1. ✅ FluidNC reports: `C=25.000`
2. ✅ Parser extracts: `'c': 25.000`
3. ✅ Stores in: `status.position['c'] = 25.000`
4. ❌ `_update_current_position()` **ignored** FluidNC value
5. ❌ Used `self._commanded_c_position` instead (which might be stale)

### Old Logic (WRONG):
```python
# We assumed FluidNC always reports C=0 (no servo feedback)
c=self._commanded_c_position  # Always use tracked
```

### New Logic (CORRECT):
```python
# FluidNC DOES report C correctly - use it!
fluidnc_c = status.position.get('c', 0.0)
c=fluidnc_c  # Use FluidNC value
```

## The Fix

**File**: `motion/simplified_fluidnc_controller_fixed.py` (Lines 1219-1229)

### Changed From:
```python
# Always use tracked position for C-axis (servo has no encoder)
c=self._commanded_c_position  # Wrong!
```

### Changed To:
```python
# FluidNC DOES report C-axis correctly
fluidnc_c = status.position.get('c', 0.0)
c=fluidnc_c  # Use FluidNC value
```

## Why This Works Now

### Complete Position Update Flow:
```
1. User jogs C +25°
   ↓
2. G0 C25.000 sent to FluidNC
   ↓
3. FluidNC executes command
   ↓
4. FluidNC status reports: MPos:200,137.5,0,0,0,25
   ↓
5. Parser extracts 6 coordinates
   ↓
6. C-axis = parsed_coords[-1] = 25.000 ✅
   ↓
7. Stored as: status.position['c'] = 25.000 ✅
   ↓
8. _update_current_position() reads it ✅
   ↓
9. Sets: self.current_position.c = 25.000 ✅
   ↓
10. Web UI reads current_position ✅
   ↓
11. Displays: C: 25.0° ✅
```

## Testing Verification

### Expected Log Output:
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,0.000,0.000,25.000' → 6 coordinates
🔍 PARSED (6 axes): [200.000, 137.500, 0.000, 0.000, 0.000, 25.000] → C=25.000
```

### Expected UI Display:
- After jog C +25°: **C: 25.0°** (not 0!)
- After jog C -50°: **C: -50.0°** (cumulative)

### Warning Logs (if mismatch):
```
🔍 C-axis mismatch: FluidNC=25.0° vs Tracked=0.0°
```
This would indicate tracking isn't working, but FluidNC value is still used.

## FluidNC 6-Axis Mystery

**Question**: Why does FluidNC output 6 axes when only 4 are configured?

**Investigation Needed**:
1. Check FluidNC firmware version
2. Review full FluidNC config for hidden axis definitions
3. Verify if A/B axes are placeholders or actually configured

**Current Understanding**:
- FluidNC always reports in 6-axis format (X,Y,Z,A,B,C)
- Unused axes report 0.000
- C-axis (servo) is always last coordinate
- This is consistent behavior we can rely on

## Implications

### Good News:
✅ Don't need manual position tracking (FluidNC does it)  
✅ Parser works correctly with variable axis counts  
✅ C-axis position is accurate and reliable  
✅ Simpler code - just use FluidNC values  

### Simplified Architecture:
- **Before**: Track C-axis manually, ignore FluidNC
- **After**: Trust FluidNC completely, use reported values

### Code Cleanup Opportunity:
Can remove `_commanded_c_position` tracking since FluidNC reports correctly. But keeping it for now as fallback/validation.

## Files Modified

1. ✅ `motion/simplified_fluidnc_protocol_fixed.py`
   - Parser correctly extracts C from last coordinate
   - Debug logging confirms 6-axis output

2. ✅ `motion/simplified_fluidnc_controller_fixed.py`
   - Changed to use FluidNC C value instead of tracked value
   - Added mismatch warning for debugging

## Testing Protocol

### 1. Restart Web Interface
```bash
python run_web_interface.py
```

### 2. Test C-Axis Movement
1. Jog C-axis +25° → UI should show 25.0°
2. Jog C-axis +25° again → UI should show 50.0°
3. Jog C-axis -75° → UI should show -25.0°

### 3. Monitor Debug Logs
Look for:
- `🔍 RAW FluidNC MPos:` - Should show 6 coordinates
- `🔍 PARSED (6 axes):` - Should show C value matching jog
- No `🔍 C-axis mismatch:` warnings (values should match)

## Success Criteria
✅ UI displays correct C-axis position  
✅ Position accumulates correctly across jogs  
✅ No resets to 0 between moves  
✅ FluidNC reports 6 axes consistently  
✅ C-axis is last coordinate (position [5])  
✅ No mismatch warnings in logs  

## Root Cause Summary

**Three interconnected bugs**:

1. ❌ **Parser stored C as 'a'** → Fixed by using 'c' key
2. ❌ **Used index [3] instead of [-1]** → Fixed by using last coordinate
3. ❌ **Ignored FluidNC C value** → Fixed by using FluidNC value instead of tracking

**All three had to be fixed together for C-axis to work!**

## Status
- ✅ All parsing bugs fixed
- ✅ Using FluidNC C value directly
- ⏳ Awaiting final Pi hardware testing
- ⏳ User to confirm UI displays correctly
