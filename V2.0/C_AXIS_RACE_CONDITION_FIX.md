# C-Axis Position Reset Bug Fix

## Issue Observed
C-axis tracking was partially working but position would reset to 0 after jog commands.

### User Logs:
```
✅ Relative move: Position4D(x=0.00, y=0.00, z=0.00, c=-25.00)
🎯 Fresh position after jog: Position(X:200.000, Y:137.500, Z:0.000, C:-50.000)  ← Correct!
...but then resets to C:0.000 in UI
```

**Symptom**: Position tracking worked (could move beyond initial range), but UI display kept resetting to 0.

## Root Cause: Race Condition

The problem was a **double position update** in `relative_move_sync()`:

### Sequence of Events:
1. `move_relative(delta)` executes ✅
   - Line 366: Sets `self._commanded_c_position = -50` ✅
   - Line 381: Calls `_update_current_position()` ✅
   - Position correctly shows C=-50 ✅

2. `relative_move_sync()` calls `get_current_position()` 
   - Line 955: `loop.run_until_complete(self.get_current_position())`

3. `get_current_position()` calls `get_position()`
   - **Line 232 (OLD CODE)**: `await self._update_current_position()` ⚠️
   - This queries FluidNC status **AGAIN**

4. **FluidNC status query returns stale/incomplete data**
   - FluidNC hasn't updated its internal state yet
   - OR servo feedback is still c=0 (no position sensor)
   - `_update_current_position()` overwrites the tracked C position

5. UI receives the reset position (C=0)

### The Bug:
```python
# OLD CODE (Line 229-234):
async def get_position(self) -> Position4D:
    """Get current position (from machine feedback)"""
    await self._update_current_position()  # ← Unnecessary extra query!
    return self.current_position.copy()
```

This caused `_update_current_position()` to be called:
- Once in `move_relative()` (correct)
- Again in `get_position()` (causes race condition)

## Solution Applied

**File**: `motion/simplified_fluidnc_controller_fixed.py`

### Changed Line 229-237:
```python
# NEW CODE:
async def get_position(self) -> Position4D:
    """Get current position (from cached value updated after moves)"""
    # DON'T call _update_current_position() here - it causes race conditions
    # The position is already updated after every move in move_to_position() and move_relative()
    # Calling it again here can overwrite the tracked C-axis position before FluidNC status updates
    return self.current_position.copy()

async def get_current_position(self) -> Position4D:
    """Get current position (alias)"""
    return await self.get_position()
```

### Rationale:
- `current_position` is **already updated** after every move:
  - In `move_to_position()` at line 300
  - In `move_relative()` at line 381
- The tracked C-axis value is set **before** the position update
- No need to query FluidNC again in `get_position()` - just return cached value
- Eliminates race condition where stale FluidNC data overwrites fresh tracking

## Testing Instructions

### 1. Restart Web Interface on Pi
```bash
# Stop current instance (Ctrl+C)
python run_web_interface.py
```

### 2. Test C-Axis Jog Commands
1. Open dashboard
2. Click C-axis jog button multiple times (e.g., +25° three times)
3. **Check logs** - should see cumulative values:
   ```
   Jog 1: C:25.000
   Jog 2: C:50.000  
   Jog 3: C:75.000  ← NOT resetting to 0!
   ```

4. **Check UI** - "C-Axis Tilt" display should:
   - Show 25.0° after first jog
   - Show 50.0° after second jog
   - Show 75.0° after third jog
   - **NOT reset to 0** between jogs

5. **Check 3D visualization** - camera marker should:
   - Rotate smoothly
   - Maintain position between jogs
   - Not snap back to 0° orientation

### 3. Test During Scan
1. Create scan pattern with varying C-axis
2. Start scan
3. Monitor position updates
4. Verify C values match scan pattern points
5. Check visualization shows correct progressive tilt

## Expected Behavior After Fix

### Before Fix:
```
Jog C +25° → UI shows 25° → Jog C +25° → UI shows 0° (reset!)
```

### After Fix:
```
Jog C +25° → UI shows 25° → Jog C +25° → UI shows 50° (cumulative!)
```

## Technical Details

### Position Update Flow (After Fix):
```
User jogs C +25°
  ↓
move_relative() called
  ↓ Line 366
self._commanded_c_position = target.c (e.g., 50)
  ↓ Line 381
_update_current_position() 
  → Uses self._commanded_c_position
  → self.current_position.c = 50
  ↓
relative_move_sync() calls get_current_position()
  ↓
get_position() returns cached value
  → NO extra _update_current_position() call
  → Returns self.current_position.copy()
  → C still = 50 ✅
  ↓
Web interface receives position
  ↓
UI displays C: 50.0° ✅
```

### Why This Works:
1. **Single source of truth**: `self.current_position` is updated once per move
2. **Tracked C preserved**: `self._commanded_c_position` set before update
3. **No race condition**: Only one update per move, no conflicting queries
4. **Consistent state**: Cached value remains stable between moves

## Files Modified
✅ `motion/simplified_fluidnc_controller_fixed.py` (Lines 229-237)

## Success Criteria
✅ C-axis position accumulates across multiple jog commands  
✅ UI displays correct cumulative C-axis values  
✅ Logs show consistent C position without resets  
✅ 3D visualization rotates progressively without snapping  
✅ Scan patterns maintain correct C-axis throughout execution  

## Related Issues Fixed
- Original issue: C-axis always showed 0 (no tracking)
- First fix: Added `_commanded_c_position` tracking
- This fix: Eliminated race condition that reset tracked value

## Status
- ✅ Code changes committed
- ⏳ Awaiting Pi hardware testing
- ⏳ User to verify C-axis position persistence
