# C-Axis Position Tracking Fix

## Problem
The C-axis (camera servo tilt) position was always showing as 0° in the dashboard visualization and position displays, even though the servo was moving to different angles during scans.

## Root Cause
FluidNC **does not provide position feedback for RC servos**. Unlike stepper motors which can report their actual position, servos are commanded to move but don't have encoders to report where they actually are.

When the motion controller queried FluidNC for the current position (`?` status report), FluidNC's `mpos` (machine position) always returned `c=0` for the servo axis because there's no position sensor.

## Solution
Implemented **local C-axis position tracking** in the `EnhancedFluidNCController`:

### Changes Made

**File: `motion/enhanced_fluidnc_controller.py`**

1. **Added C-axis position tracking variable** (line ~70):
   ```python
   # C-axis position tracking (FluidNC servo doesn't report position)
   self._commanded_c_position: float = 0.0
   ```

2. **Updated status handler to preserve tracked C position** (line ~268):
   ```python
   async def _on_status_update(self, message: FluidNCMessage):
       # ... extract position from FluidNC ...
       
       # WORKAROUND: FluidNC servos don't have position feedback, so C-axis always reports 0
       # Preserve the commanded C position from our tracking
       if hasattr(self, '_commanded_c_position'):
           new_position = Position4D(
               x=new_position.x,
               y=new_position.y,
               z=new_position.z,
               c=self._commanded_c_position  # Use tracked C position instead of FluidNC's 0
           )
   ```

3. **Track C position on absolute moves** (line ~348):
   ```python
   async def move_to_position(self, position: Position4D, feedrate: float = 100.0) -> bool:
       # ... validation and setup ...
       
       # Track commanded C position (servo doesn't report feedback)
       self._commanded_c_position = position.c
       
       # Send movement command...
   ```

4. **Track C position on relative moves** (line ~430):
   ```python
   async def move_relative(self, delta: Position4D, feedrate: float = 100.0) -> bool:
       # Calculate target position
       target = Position4D(...)
       
       # Track commanded C position (servo doesn't report feedback)
       self._commanded_c_position = target.c
       
       # Send relative movement...
   ```

## How It Works

1. **Initialization**: C-axis position starts at 0°
2. **Movement Commands**: When `move_to_position()` or `move_relative()` is called, the commanded C-axis value is stored in `_commanded_c_position`
3. **Status Updates**: When FluidNC reports position (every status poll), the system:
   - Reads X, Y, Z from FluidNC's actual stepper positions
   - **Replaces** the C value (which FluidNC reports as 0) with the tracked `_commanded_c_position`
4. **Result**: `current_position.c` now reflects the actual commanded servo angle

## Impact

✅ **Dashboard visualization** now correctly shows servo tilt angle  
✅ **Position displays** show accurate C-axis values  
✅ **Scan progress** correctly tracks camera tilt changes  
✅ **No hardware changes needed** - pure software fix  

## Technical Notes

- This is a **command-based tracking** system (not sensor-based)
- Assumes the servo accurately follows commands (true for RC servos)
- Position is only updated when motion controller commands movement
- External servo movements (not via motion controller) won't be tracked
- Initial position on startup is 0° (servo home position)

## Alternative Solutions Considered

1. **Add servo position sensor**: Hardware modification - rejected as too complex
2. **Use separate servo controller with feedback**: Would require major architecture changes
3. **Track all G-code sent to FluidNC**: More complex, wouldn't catch external changes anyway
4. **Accept C=0 always**: Unacceptable for user experience and scan visualization

## Testing

**Before Fix:**
- C-axis position: Always 0°
- Dashboard visualization: Current position marker offset from scan path
- Scan position display: C always showed 0.0°

**After Fix:**
- C-axis position: Matches commanded values (-90° to +90°)
- Dashboard visualization: Current position aligns with scan path
- Scan position display: Shows actual servo angles (e.g., C:-31.4°)

## Files Modified
- `motion/enhanced_fluidnc_controller.py` (4 changes)

## Date
October 7, 2025
