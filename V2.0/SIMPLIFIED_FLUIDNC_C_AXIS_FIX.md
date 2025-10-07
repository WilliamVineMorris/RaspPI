# SimplifiedFluidNCControllerFixed C-Axis Tracking Fix

## Issue Discovered
User reported C-axis always shows 0° despite servo physically responding to commands.

### Log Evidence:
```
G0 X200.000 Y137.500 Z0.000 C-25.000  ← Command sent with C=-25°
...
Fresh position after jog: Position(X:200.000, Y:137.500, Z:0.000, C:0.000)  ← Position shows C=0!
```

## Root Cause
The system uses `SimplifiedFluidNCControllerFixed` (NOT `EnhancedFluidNCController`), which was reading C-axis from FluidNC's status response:

```python
# OLD CODE (Line 1209):
c=status.position.get('a', 0.0)  # FluidNC uses 'a' for 4th axis
```

**Problem**: RC servos have NO position feedback → FluidNC always reports c=0

## Solution Applied

### 1. Added C-Axis Tracking Variable (Line ~75)
```python
# C-axis tracking: RC servos have no position feedback, must track commanded position
self._commanded_c_position: float = 0.0
```

### 2. Updated Position Reading (Line ~1219)
```python
# NOTE: C-axis uses tracked commanded position since RC servos have no feedback
self.current_position = Position4D(
    x=status.position.get('x', 0.0),
    y=status.position.get('y', 0.0),
    z=status.position.get('z', 0.0),
    c=self._commanded_c_position  # Use tracked C position (servo has no feedback)
)
```

### 3. Track C Position in Absolute Moves (Line ~292)
```python
if success:
    # Track commanded C-axis position (servo has no position feedback)
    self._commanded_c_position = position.c
    
    self.target_position = position.copy()
    # ... rest of move completion logic
```

### 4. Track C Position in Relative Moves (Line ~366)
```python
if success:
    # Track commanded C-axis position (servo has no position feedback)
    self._commanded_c_position = target.c
    
    self.target_position = target.copy()
    # ... rest of move completion logic
```

## Files Modified
- ✅ `motion/simplified_fluidnc_controller_fixed.py` (Lines ~75, ~1219, ~292, ~366)

## Testing Instructions

### 1. Restart Web Interface on Pi
```bash
# Stop current instance (Ctrl+C)
# Restart
python run_web_interface.py
```

### 2. Test C-Axis Movement
1. Open dashboard in browser
2. Use manual controls to move C-axis (e.g., +30°)
3. **Check logs** - should see:
   ```
   G0 X... Y... Z... C30.000  ← Command sent
   Fresh position: Position(X:..., Y:..., Z:..., C:30.000)  ← Should show 30.0!
   ```
4. **Check dashboard** - "C-Axis Tilt" should display 30.0°
5. **Check 3D visualization** - camera marker should rotate

### 3. Verify During Scan
1. Create scan pattern with varying C-axis angles
2. Start scan
3. Monitor position updates - C values should match pattern
4. Check visualization shows correct tilt angles

## Expected Log Output After Fix
```
📤 Sending G-code: 'G0 X200.000 Y137.500 Z0.000 C-25.000'
✅ Motion completed
🎯 Fresh position after jog: Position(X:200.000, Y:137.500, Z:0.000, C:-25.000)  ← C=-25 now!
```

## Success Criteria
✅ Dashboard position display shows commanded C-axis values  
✅ Logs show correct C position after jog commands  
✅ 3D visualization rotates camera marker based on C angle  
✅ Scan patterns display correct servo tilt throughout scan  

## Technical Details

### Why This Works:
- **X/Y/Z axes**: Stepper motors with encoders → FluidNC provides real feedback
- **C axis**: RC servo without encoder → No feedback available → Must track commanded values

### Position Flow:
```
User Command (Web UI jog)
  ↓
SimplifiedFluidNCControllerFixed.move_relative()
  ↓ Sends G-code
G0 X200 Y137.5 Z0 C-25
  ↓ Tracks command
self._commanded_c_position = -25.0
  ↓ Updates position
self.current_position.c = self._commanded_c_position
  ↓ Read by web interface
/api/status → Position(C:-25.000)
  ↓ Displayed
Dashboard: "C-Axis Tilt: -25.00°"
```

## Controller Architecture Notes

The codebase has multiple motion controllers:
- **EnhancedFluidNCController**: Full async, not currently used
- **SimplifiedFluidNCControllerFixed**: CURRENTLY USED for hardware
- **MockMotionController**: Used for development mode

The C-axis tracking has now been added to BOTH:
- ✅ SimplifiedFluidNCControllerFixed (this fix)
- ✅ MockMotionController (previous fix in start_web_interface.py)

## Deployment Status
- ✅ Code changes committed
- ⏳ Awaiting Pi hardware testing
- ⏳ User to restart web interface and verify
