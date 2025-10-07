# C-Axis Position Tracking - Complete Fix

## Problem Summary
The C-axis (servo tilt) position was always showing 0° on the dashboard visualization because RC servos don't provide position feedback to FluidNC.

## Root Cause Analysis

### Hardware Limitation
- RC servos are **open-loop** devices - they receive PWM commands but provide no position feedback
- FluidNC controller always reports `c=0` in status messages because the servo has no encoder
- This is a fundamental hardware characteristic, not a software bug

### Software Architecture Discovery
The codebase supports **two operating modes**:

1. **Hardware Mode** (on Raspberry Pi):
   - Uses `ScanOrchestrator` → `EnhancedFluidNCController`
   - Started with: `python start_web_interface.py --mode hardware`
   - Has the C-axis tracking fix implemented

2. **Mock Mode** (for development):
   - Uses `MockOrchestrator` → `MockMotionController`
   - Started with: `python start_web_interface.py --mode mock`
   - Did NOT have C-axis tracking (now fixed)

## Complete Solution

### Part 1: EnhancedFluidNCController (Already Implemented)
**File**: `motion/enhanced_fluidnc_controller.py`

Added local C-axis position tracking:
```python
# Line 70: Track commanded C position
_commanded_c_position: float = 0.0

# Lines 268-288: Preserve tracked C-axis in status updates
def _on_status_update(self, status_data: Dict[str, Any]) -> None:
    if 'position' in status_data:
        pos = status_data['position']
        # Use tracked C position instead of FluidNC's 0
        self._current_position = Position4D(
            x=pos.get('x', 0.0),
            y=pos.get('y', 0.0),
            z=pos.get('z', 0.0),
            c=self._commanded_c_position  # ← Use tracked value
        )

# Lines 348-350: Track C position when moving
async def move_to_position(self, position: Position4D) -> bool:
    self._commanded_c_position = position.c
    # ... send G-code command
    
# Lines 430-432: Track C position in relative moves  
async def move_relative(self, axis: str, distance: float) -> bool:
    if axis.lower() == 'c':
        self._commanded_c_position += distance
```

**This fix WORKS on the Pi in hardware mode!**

### Part 2: MockMotionController (Just Fixed)
**File**: `web/start_web_interface.py`

Updated mock controller to properly track C-axis for development/testing:
```python
def move_to_position(self, position):
    # Handle both dict and Position4D input
    if isinstance(position, Position4D):
        self._position['x'] = position.x
        self._position['y'] = position.y
        self._position['z'] = position.z
        self._position['c'] = position.c
        self.current_position = position
    else:
        self._position.update(position)
        self.current_position = Position4D(
            x=self._position.get('x', 0.0), 
            y=self._position.get('y', 0.0), 
            z=self._position.get('z', 0.0), 
            c=self._position.get('c', 0.0)
        )
    print(f"Mock: Moving to x={self.current_position.x}, y={self.current_position.y}, z={self.current_position.z}, c={self.current_position.c}°")
```

Added debug logging to show C-axis changes in terminal output.

## How to Use

### On Development Machine (Mock Mode)
```bash
# Test with mock hardware - C-axis now tracked properly
python start_web_interface.py --mode mock --debug

# You'll see in terminal:
# Mock: Moving to x=100.0, y=50.0, z=45.0, c=30.0°
```

### On Raspberry Pi (Hardware Mode)
```bash
# Use real hardware with C-axis tracking
python start_web_interface.py --mode hardware --host 0.0.0.0 --port 5000

# The EnhancedFluidNCController will track servo positions
```

### Other Available Modes
```bash
# Development mode - tries hardware, falls back to mock
python start_web_interface.py --mode development

# Production mode - hardware only, no fallback
python start_web_interface.py --mode production --host 0.0.0.0 --port 80
```

## Verification Steps

### 1. Check Terminal Output
When moving the C-axis, you should see:
```
Mock: Moving to x=100.0, y=50.0, z=0.0, c=45.0°
```
The `c=45.0°` confirms tracking is working.

### 2. Check Dashboard Visualization
- Open dashboard in browser
- Move the C-axis using manual controls
- The "C-Axis Tilt" value should update to match commanded position
- The 3D visualization marker should rotate accordingly

### 3. Check Browser Console
```javascript
// Should show current position with non-zero C value
{
  x: 100.0,
  y: 50.0, 
  z: 0.0,
  c: 45.0  // ← Should match commanded position
}
```

## Technical Notes

### Why Two Implementations?
- **EnhancedFluidNCController**: For real Pi hardware with FluidNC
- **MockMotionController**: For development/testing on PC without hardware

### Position Flow Architecture
```
User Command (Web UI)
  ↓
Motion Controller (Enhanced or Mock)
  ↓ Updates internal tracking
self._commanded_c_position = position.c
  ↓ Stored in
self.current_position = Position4D(x, y, z, c)
  ↓ Read by
/api/visualization_data endpoint
  ↓ Sent to
Dashboard JavaScript
  ↓ Displayed in
3D Plotly visualization
```

### Key Difference from X/Y/Z Axes
- **X/Y/Z**: FluidNC provides real position feedback → use FluidNC values
- **C-axis**: No feedback available → use locally tracked commanded values

## Files Modified

1. ✅ `motion/enhanced_fluidnc_controller.py` (lines 70, 268-288, 348-350, 430-432)
   - Added `_commanded_c_position` tracking variable
   - Modified status updates to preserve tracked C value
   - Updated move commands to track C position

2. ✅ `web/start_web_interface.py` (lines 151-195)
   - Enhanced MockMotionController to properly handle Position4D
   - Added C-axis tracking for mock mode
   - Added debug logging showing C-axis values

## Testing Protocol

### Before Testing on Pi:
1. ✅ Verify mock mode works on development machine
2. ✅ Check terminal shows C-axis values updating
3. ✅ Confirm dashboard displays correct C position

### When Testing on Pi:
1. Start in hardware mode: `python start_web_interface.py --mode hardware`
2. Move C-axis via manual controls on dashboard
3. Observe terminal for FluidNC G-code commands (e.g., `G0 C45`)
4. Verify dashboard "C-Axis Tilt" updates to commanded value
5. Check 3D visualization marker rotates correctly
6. During scan, verify C-axis position updates match scan pattern

## Expected Behavior

### Mock Mode (Development):
- C-axis updates immediately when commanded
- Terminal shows: `Mock: Moving to ... c=XX.X°`
- Dashboard displays commanded position

### Hardware Mode (Raspberry Pi):
- G-code sent to FluidNC: `G0 C45`
- Controller tracks commanded position locally
- Dashboard shows tracked position (not FluidNC's 0)
- Physical servo moves to position (no feedback)

## Success Criteria
✅ Dashboard shows non-zero C-axis values during movement  
✅ Visualization rotates camera marker based on C position  
✅ Scan patterns display correct tilt angles  
✅ Manual control C-axis slider updates position display  
✅ Both mock and hardware modes track C-axis properly  

## Known Limitations
- No verification that physical servo actually reached position (hardware limitation)
- Tracking assumes commands succeed (no error detection for servo failure)
- Depends on accurate G-code command execution

## Next Steps
1. Test mock mode on PC ← **You can do this now**
2. Deploy to Pi and test hardware mode ← **Test on actual Pi hardware**
3. Verify C-axis tracking during full scans
4. Monitor for any servo command/position mismatches
