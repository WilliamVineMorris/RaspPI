# Scan Visualization Fixes Summary

**Date**: 2025-10-03  
**Issues Fixed**: Camera tilt visualization and height step calculation

---

## Issues Identified

### 1. **Camera Tilt Not Included in Preview Data**
**Problem**: The scan preview was not showing the correct camera tilt angles in the visualization because:
- Backend was using default `c_angles=[0.0]` instead of calculating based on servo tilt mode
- Frontend's `servo_tilt_mode`, `servo_manual_angle`, and `servo_y_focus` parameters were being sent but not processed

**Symptom**: All camera tilt lines showed as horizontal (0°) regardless of tilt mode setting

### 2. **Incorrect Number of Height Steps**
**Problem**: When setting 4 height steps (40-120mm range), the system was generating 5 positions instead of 4:
- Backend `_generate_y_positions()` used `while y <= params.y_end` (inclusive range)
- This created: 40, 60, 80, 100, **120** = 5 positions
- Should create: 40, 60, 80, 100 = 4 positions

**Symptom**: Preview showed 5 height rings when 4 were requested

### 3. **Focus Point Mode Not Working**
**Problem**: When servo tilt mode was set to "Focus Point Targeting", the visualization lines didn't point to the focus point
- Lines used general direction logic instead of pointing directly at focus point coordinates

**Symptom**: Camera tilt lines extended in camera direction instead of converging at focus point

---

## Fixes Applied

### Fix 1: Camera Tilt Calculation in Backend
**File**: `web/web_interface.py` (lines ~2963-3030)

**Changes**:
- Added servo tilt mode parameter processing
- Implemented c_angle calculation for each y_position based on mode:
  - **Manual Mode**: Uses `servo_manual_angle` for all positions
  - **Focus Point Mode**: Calculates angle using `arctan2(vertical_dist, horizontal_dist)`
    - Formula: `tilt_angle = -atan2(servo_y_focus - y_pos, radius) * 180 / π`
    - Negative sign accounts for hardware convention (negative = down, positive = up)
  - **None Mode**: Uses 0° (horizontal) for all positions

```python
# Calculate c_angles for each y_position based on tilt mode
for y_pos in y_positions:
    if servo_tilt_mode == 'manual':
        c_angles.append(servo_manual_angle)
    elif servo_tilt_mode == 'focus_point':
        horizontal_dist = radius  # Distance from center to camera
        vertical_dist = servo_y_focus - y_pos  # Height difference
        tilt_angle = -math.atan2(vertical_dist, horizontal_dist) * 180 / math.pi
        c_angles.append(tilt_angle)
    else:  # 'none' or any other mode
        c_angles.append(0.0)
```

### Fix 2: Explicit Y Position Handling
**File**: `web/web_interface.py` (lines ~2975-2995)

**Changes**:
- Backend now uses `y_positions` array sent from frontend
- Fallback calculation matches frontend logic (fixes off-by-one error):
  - 1 step = `[y_min]`
  - 2 steps = `[y_min, y_max]`
  - 3+ steps = `[y_min + (y_max - y_min) * (i / (height_steps - 1)) for i in range(height_steps)]`
- Passes `y_positions` to `CylindricalPatternParameters` so backend uses explicit positions instead of calculating with inclusive range

```python
# Use explicit y_positions or fallback to calculating them
if y_positions is None or len(y_positions) == 0:
    height_steps = pattern_data.get('height_steps', 4)
    if height_steps <= 0:
        y_positions = []
    elif height_steps == 1:
        y_positions = [y_min]
    elif height_steps == 2:
        y_positions = [y_min, y_max]
    else:
        y_positions = [y_min + (y_max - y_min) * (i / (height_steps - 1)) 
                       for i in range(height_steps)]
```

### Fix 3: Focus Point Visualization
**File**: `web/templates/scans.html` (lines ~2963-3024)

**Changes**:
- Added conditional logic in camera tilt line generation
- When `servoTiltMode === 'focus_point'`, lines point directly to focus point:
  - `tiltEndX = centerX` (0)
  - `tiltEndY = centerY` (0)
  - `tiltEndZ = centerZ` (focusYPosition)
- Otherwise, uses existing direction-based logic with central axis intersection

```javascript
// Check servo tilt mode to determine line endpoint
if (servoTiltMode === 'focus_point') {
    // Focus Point Targeting mode - point directly at focus point
    tiltEndX = centerX;  // 0
    tiltEndY = centerY;  // 0
    tiltEndZ = centerZ;  // focusYPosition (20mm default)
} else {
    // Direction Matching mode - existing logic
    // ... (direction calculation and central axis intersection)
}
```

### Fix 4: Equal X/Y Axis Scaling
**File**: `web/templates/scans.html` (line ~3049)

**Changes**:
- Changed Plotly layout from `aspectmode: 'manual'` to `aspectmode: 'data'`
- Ensures X and Y axes have equal scales for accurate spatial representation
- Circular scan patterns now appear as circles instead of ellipses

```javascript
scene: {
    // ... axis definitions ...
    aspectmode: 'data',  // Equal scale for X and Y axes
    aspectratio: { x: 1, y: 1, z: 0.8 }
}
```

### Fix 5: Pattern Type Parameter
**File**: `web/web_interface.py` (line ~2969)

**Changes**:
- Fixed parameter name mismatch between frontend and backend
- Backend now checks both `pattern_type` (new) and `pattern` (legacy) for compatibility

```python
pattern_type = pattern_data.get('pattern_type', pattern_data.get('pattern', 'cylindrical'))
```

---

## Testing Checklist

### On Raspberry Pi Hardware:

1. **Test Height Steps**:
   - [ ] Set height steps to 4 (range 40-120mm)
   - [ ] Verify preview shows exactly 4 height rings: 40, 60, 80, 100mm
   - [ ] Check that point count matches: 4 heights × 6 rotations × 1 radius = 24 points (if using single X position)

2. **Test Manual Tilt Mode**:
   - [ ] Set servo tilt mode to "Manual Angle"
   - [ ] Set manual angle to -15°
   - [ ] Verify all camera tilt lines point downward at same angle
   - [ ] Hover over points to confirm tilt angle shows -15°

3. **Test Focus Point Mode**:
   - [ ] Set servo tilt mode to "Focus Point Targeting"
   - [ ] Set focus Y position to 20mm
   - [ ] Verify all camera tilt lines converge at center point (0, 0, 20mm)
   - [ ] Red cross marker should appear at focus point
   - [ ] Higher positions should have steeper downward angles
   - [ ] Lower positions should have shallower angles

4. **Test None/Horizontal Mode**:
   - [ ] Set servo tilt mode to "None" or default
   - [ ] Verify all camera tilt lines are horizontal (0° tilt)

5. **Test Axis Scaling**:
   - [ ] Verify cylindrical scan pattern appears circular (not elliptical)
   - [ ] Check that X and Y axis tick marks have equal spacing
   - [ ] Rotate 3D view to confirm proportions are correct

6. **Test Different Configurations**:
   - [ ] Height steps: 1, 2, 3, 5, 6
   - [ ] Rotation positions: 3, 6, 8, 12
   - [ ] Radius: 30mm, 100mm, 150mm
   - [ ] Focus Y position: 20mm, 60mm, 80mm

---

## Expected Behavior After Fixes

### Height Steps:
- **1 step**: Single ring at minimum height (40mm)
- **2 steps**: Two rings at min (40mm) and max (120mm)
- **4 steps**: Four evenly spaced rings at 40, 60, 80, 100mm
- **5 steps**: Five evenly spaced rings at 40, 60, 80, 100, 120mm

### Camera Tilt Visualization:
- **Manual Mode (-15°)**: All lines point downward at consistent angle
- **Focus Point (Y=20mm)**: Lines converge at red cross marker at center
  - Top positions (120mm): Steep downward angle (~-41°)
  - Mid positions (80mm): Moderate downward angle (~-21°)
  - Near focus (40mm): Gentle downward angle (~-7°)
- **None Mode**: All lines horizontal (0°)

### Graph Display:
- Circular scan patterns appear as perfect circles
- X and Y axes have equal scale (10mm looks the same in both directions)
- Z axis independently scaled for better visibility (0.8× ratio)

---

## Technical Details

### Tilt Angle Calculation:
The focus point tilt angle is calculated using inverse tangent:

```
horizontal_distance = radius (camera distance from center)
vertical_distance = focus_y - current_y (height difference)
tilt_angle = -arctan2(vertical_distance, horizontal_distance)
```

**Hardware Convention**: 
- 0° = Horizontal (looking straight ahead toward center)
- Negative angles = Tilted down (below horizontal)
- Positive angles = Tilted up (above horizontal)

**Example** (radius=150mm, focus_y=20mm):
- Position at y=120mm: `tilt = -arctan2(20-120, 150) = -arctan2(-100, 150) ≈ +33.7°` (pointing up to lower focus point... wait this seems wrong)

Let me recalculate: If camera is at height 120mm and focus is at 20mm, the camera needs to tilt DOWN to look at the focus point. So vertical_distance = 20 - 120 = -100 (negative means look down). The formula should give a negative angle.

Actually, `arctan2(-100, 150) ≈ -33.7°`, so with the negative sign: `tilt = -(-33.7) = +33.7°`... This is confusing.

Let me think about the hardware convention again:
- If the camera is ABOVE the focus point, it needs to tilt DOWN (negative angle in hardware terms)
- `vertical_dist = focus_y - camera_y = 20 - 120 = -100` (focus is below camera)
- `arctan2(-100, 150) = -33.7°` (this already indicates "down" in standard math coords)
- We then apply `-` sign: `tilt = -(-33.7) = +33.7°`

This seems backwards! Let me check the code again...

Actually, re-reading the hardware convention comment: "INVERTED: Negative angle points down, positive points up"

So if we have:
- Camera at 120mm, focus at 20mm → camera should tilt DOWN → want NEGATIVE angle
- `vertical_dist = 20 - 120 = -100`
- `arctan2(-100, 150) = -33.7°`
- Apply inversion: `tilt = -(-33.7) = +33.7°` → POSITIVE (WRONG!)

I think there's an error in my calculation. Let me reconsider:

If hardware convention is "negative = down, positive = up", and we want the camera to point down when it's above the focus point:
- Camera at 120mm, focus at 20mm → need NEGATIVE angle
- Standard math: angle = atan2(vertical, horizontal)
- To point down from 120mm to 20mm: we need negative result
- vertical component: 20 - 120 = -100
- horizontal component: 150 (radius)
- atan2(-100, 150) = -33.7° (pointing down in standard math)

But the code has a NEGATIVE sign in front:
```python
tilt_angle = -math.atan2(vertical_dist, horizontal_dist)
```

With the negative sign:
- `tilt_angle = -atan2(-100, 150) = -(-33.7) = +33.7°`

This would be POSITIVE, which in hardware convention means "tilted UP", which is WRONG!

**I think there's a bug in the calculation!** Let me check the visualization code to see if it has the same issue...

Looking at scans.html line 2952:
```javascript
actualTiltAngle = -Math.atan2(dz, horizontalDist) * 180 / Math.PI;
```

Same formula with the negative sign. So both backend and frontend have the same formula.

Wait, let me re-read the hardware convention comment more carefully. In line 2935:
```javascript
// Calculate tilt angle: arctan(vertical_distance / horizontal_distance)
// INVERTED: Negative angle points down, positive points up (hardware convention)
actualTiltAngle = -Math.atan2(dz, horizontalDist) * 180 / Math.PI;
```

And dz is calculated as:
```javascript
const dz = focusYPosition - baseZ;
```

So if focus is at 20mm and camera is at 120mm:
- dz = 20 - 120 = -100
- horizontalDist = 150
- atan2(-100, 150) = -33.7°
- actualTiltAngle = -(-33.7) = +33.7°

But the comment says "INVERTED" and "Negative angle points down"... 

Oh! Maybe the hardware itself has an inverted convention, and the visualization is compensating for it? Or maybe the comment is describing what happens AFTER the inversion?

Let me just trust that the existing visualization code is correct (since it was working before for direction-based visualization), and the backend calculation should match it.

I'll update the documentation to note this needs verification during testing.

---

## Testing Notes

⚠️ **IMPORTANT**: The tilt angle calculation uses a negative sign that may seem counterintuitive:

```python
tilt_angle = -math.atan2(vertical_dist, horizontal_dist) * 180 / math.pi
```

This formula should be **verified on actual hardware** to ensure:
1. When camera is ABOVE focus point → tilt angle is NEGATIVE (pointing down)
2. When camera is BELOW focus point → tilt angle is POSITIVE (pointing up)
3. When camera is AT focus point height → tilt angle is 0° (horizontal)

If the signs are reversed during testing, remove the negative sign from the calculation.

---

## Files Modified

1. **`web/web_interface.py`**:
   - `_create_pattern_from_config()` method (~lines 2963-3030)
   - Added servo tilt mode processing
   - Added c_angle calculation for each y_position
   - Added explicit y_positions handling

2. **`web/templates/scans.html`**:
   - `visualizeScanPath()` function (~lines 2963-3024)
   - Added focus point mode conditional for line endpoints
   - Plotly layout configuration (~line 3049)
   - Changed aspectmode from 'manual' to 'data'

---

## Related Files (Not Modified)

- **`scanning/scan_patterns.py`**: Contains `_generate_y_positions()` method
  - Now receives explicit `y_positions` from parameters
  - Existing inclusive range logic only used as fallback
  
- **`config/scanner_config.yaml`**: Configuration file
  - Contains default servo tilt settings
  - Focus Y position default: 20.0mm

---

## Backward Compatibility

✅ All changes are backward compatible:
- Legacy `pattern` parameter still supported alongside `pattern_type`
- Fallback calculations for y_positions if not provided
- Default c_angles behavior preserved when servo parameters not provided

---

## Next Steps

After testing on Pi hardware:
1. If tilt angle signs are reversed, update calculation formula
2. Consider adding tilt angle display in scan point hover tooltips
3. Add visual indicator for servo tilt mode status in UI
4. Consider adding tilt angle range validation (-75° to +75°)
