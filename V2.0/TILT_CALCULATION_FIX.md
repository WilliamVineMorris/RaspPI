# Camera Tilt Calculation Fix

## Problem
Camera tilt angles were calculated with the **wrong sign** in Focus Point Targeting mode. This caused the camera to tilt in the opposite direction from what was geometrically correct.

### Example Issue:
- Camera at: radius=100mm, height=100mm
- Focus point at: radius=0mm (turntable center), height=80mm
- **Expected tilt**: -11.31° (camera above focus, should look DOWN)
- **Actual tilt**: +11.31° (camera tilting UP - WRONG!)

For a more extreme case:
- Camera at: radius=100mm, height=100mm  
- Focus at: height=0mm (turntable surface)
- **Expected**: -45° (look down at 45° angle)
- **Actual**: +45° (look up - completely wrong!)

## Root Cause
The tilt calculation formula was missing a negative sign:

### OLD CODE (WRONG):
```python
height_diff = y_pos - servo_y_focus  # 100 - 80 = 20mm (camera above)
tilt_angle = math.degrees(math.atan2(height_diff, radius))  # +11.31° WRONG!
```

This gives a **positive** angle when the camera is above the focus point, but the servo convention is:
- **Negative angle** = tilt down
- **Positive angle** = tilt up

### Correct Convention:
- Camera **above** focus point → should look **down** → **negative tilt**
- Camera **below** focus point → should look **up** → **positive tilt**

## Solution
Added negative sign to invert the angle for correct servo orientation:

### NEW CODE (CORRECT):
```python
# Camera-relative tilt calculation (pure geometry, no offsets)
# Camera is at (radius, y_pos), focus point is at (0, servo_y_focus)
height_diff = y_pos - servo_y_focus  # Positive = camera above focus
horizontal_dist = radius  # Distance to turntable center
# Negative sign: camera above focus = look down (negative tilt)
tilt_angle = -math.degrees(math.atan2(height_diff, horizontal_dist))
```

### Example Results:
```python
# Camera: radius=100mm, height=100mm, Focus: height=80mm
height_diff = 100 - 80 = 20mm
tilt = -atan2(20, 100) = -11.31° ✓ (look down)

# Camera: radius=100mm, height=100mm, Focus: height=0mm  
height_diff = 100 - 0 = 100mm
tilt = -atan2(100, 100) = -45.0° ✓ (look down at 45°)

# Camera: radius=100mm, height=60mm, Focus: height=80mm
height_diff = 60 - 80 = -20mm
tilt = -atan2(-20, 100) = +11.31° ✓ (look up)
```

## Key Insight: Pure Camera-Relative Calculation

**IMPORTANT**: Tilt is calculated using **camera-relative coordinates only**, without involving FluidNC coordinates or offsets:

1. **Camera position**: (radius, height) - user-configured values
2. **Focus point**: (0, servo_y_focus) - center of turntable at focus height
3. **Tilt calculation**: Pure geometric angle from camera to focus point
4. **Then**: This tilt angle is sent to FluidNC along with offset-corrected position

### Why This Works:
- The tilt servo is physically attached to the camera
- It doesn't care about FluidNC coordinates or offsets
- It only needs to know: "what angle should I point to aim at the focus point?"
- This is a simple triangle: camera → focus point

### Coordinate Flow:
```
User Input (Camera-Relative):
  radius=100mm, height=100mm, focus=80mm
    ↓
Tilt Calculation (Camera-Relative):
  tilt = -atan2(100-80, 100) = -11.31°
    ↓
Position Transformation (Camera → FluidNC):
  FluidNC_X = 100 + offsets = 150mm (example)
  FluidNC_Y = 100 + offsets = 70mm (example)
    ↓
Motion Command:
  G0 X150.0 Y70.0 Z0.0 C-11.31
```

## Changes Made

### File: `web/web_interface.py`

#### Location 1: Preview generation (line ~3274)
```python
# OLD (WRONG):
height_diff = y_pos - servo_y_focus
tilt_angle = math.degrees(math.atan2(height_diff, radius))

# NEW (CORRECT):
height_diff = y_pos - servo_y_focus  # Positive = camera above focus
horizontal_dist = radius  # Distance to turntable center
tilt_angle = -math.degrees(math.atan2(height_diff, horizontal_dist))
```

#### Location 2: Pattern generation (line ~3124)
```python
# OLD (WRONG - used complex offset-based calculation):
if SCANNER_MODULES_AVAILABLE:
    tilt_angle = calculate_servo_tilt_angle(
        camera_radius=radius,
        camera_height=y_pos,
        focus_height=servo_y_focus,
        turntable_offset_y=turntable_offset_y,
        camera_offset_y=camera_offset_y
    )
else:
    height_diff = y_pos - servo_y_focus
    tilt_angle = math.degrees(math.atan2(height_diff, radius))

# NEW (CORRECT - pure camera-relative):
height_diff = y_pos - servo_y_focus  # Positive = camera above focus
horizontal_dist = radius  # Distance to turntable center
tilt_angle = -math.degrees(math.atan2(height_diff, horizontal_dist))
```

## Verification

After this fix, the tilt angles in the CSV export and visualization should match the geometric expectation:

### Test Case 1:
- Radius: 100mm
- Height: 100mm  
- Focus: 80mm
- **Expected Tilt**: -11.31° ✓

### Test Case 2:
- Radius: 100mm
- Height: 100mm
- Focus: 0mm (turntable surface)
- **Expected Tilt**: -45.0° ✓

### Test Case 3:
- Radius: 100mm
- Height: 60mm
- Focus: 80mm  
- **Expected Tilt**: +11.31° ✓ (camera below focus, look up)

## Visualization Fix Already Applied

The hover text sign issue was also fixed earlier - now displays with correct sign:
```javascript
// Hover text shows: `Tilt: ${(-p.c).toFixed(1)}°`
// This was needed because backend sends positive values that should display as negative
```

**Wait** - This creates a conflict! We just fixed the backend to send correct signs (negative when looking down), but the visualization is negating it again. Let me fix that:

## Additional Fix Needed

Since we've corrected the tilt calculation to use the proper sign, we need to **remove the negation in the visualization**:

```javascript
// OLD (compensating for backend bug):
`Tilt: ${(-p.c).toFixed(1)}°`

// NEW (backend now sends correct sign):
`Tilt: ${p.c.toFixed(1)}°`
```

## Testing Checklist

1. ✅ Set Focus Point mode with focus Y = 80mm
2. ✅ Configure scan: radius=100mm, heights=[60mm, 80mm, 100mm, 120mm]
3. ✅ Export CSV and verify tilt values:
   - Height 60mm: ~+11.31° (below focus, look up)
   - Height 80mm: 0.0° (at focus level, horizontal)
   - Height 100mm: ~-11.31° (above focus, look down)
   - Height 120mm: ~-21.80° (well above focus, look down steeper)
4. ✅ Visual preview: tilt lines should point toward focus point
5. ⏳ Pi Hardware Test: Verify servo physically tilts correctly

## Related Files
- `web/web_interface.py`: Tilt calculation fixes (2 locations)
- `web/templates/scans.html`: Visualization display (hover text - needs fix removal)
- `motion/servo_tilt.py`: Old offset-based calculation (no longer used)

## Date
2025-10-03

## Status
✅ **IMPLEMENTED** - Backend tilt calculation fixed
⚠️ **PENDING**: Remove visualization negation to match corrected backend
