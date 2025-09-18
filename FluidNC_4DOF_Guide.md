# FluidNC 4DOF Camera Positioning System

This system has been upgraded from #### C-axis (Camera Tilt):
- Command: `G1 C90` → Sets camera to 0° tilt (level)
- Range: 0-180mm = -90° to +90° tilt
- Center position (90mm) = 0° tilt
- Command mapping: `tilt_angle_degrees + 90 = command_mm`
- ConfigV1.2: Uses 0-180mm range with soft limits and homing cycle 03DOF to FluidNC 4DOF to support advanced camera positioning with:

## Hardware Configuration

### Axes Definition:
- **X-axis**: Horizontal linear movement (0-200mm)
- **Y-axis**: Vertical linear movement (0-200mm)  
- **Z-axis**: Rotational turntable (0-360°, mapped as 0-360mm in commands)
- **C-axis**: Camera tilt servo (0-180mm, where 90mm = 0° tilt, range is ±90°)

### Key Differences from GRBL Version:

1. **4DOF Support**: Added C-axis for camera tilt control
2. **Rotational Z-axis**: Z-axis is now a turntable instead of linear
3. **FluidNC Controller**: More advanced motion control with better servo support
4. **Enhanced Scanning**: New scan patterns utilizing rotation and tilt

## Usage Examples

### Basic 4DOF Movement
```python
from integrated_camera_system import IntegratedCameraSystem

# Initialize with FluidNC (default)
system = IntegratedCameraSystem(use_fluidnc=True)
system.initialize_positioning_system()

# Move to position with camera tilt
system.camera_controller.move_to_capture_position(
    x=100,      # 100mm horizontal
    y=150,      # 150mm vertical  
    z=45,       # 45° turntable rotation
    c=15        # 15° camera tilt
)
```

### Advanced Scanning Patterns

#### Rotational Scan (Turntable)
```python
# Scan object at multiple angles
base_position = Point(100, 100, 0, 0)  # X, Y, Z, C
angles = [0, 45, 90, 135, 180, 225, 270, 315]  # 8 angles
system.camera_controller.rotational_scan(base_position, angles, c_angle=0)
```

#### Camera Tilt Scan
```python
# Scan with different camera angles
position = Point(100, 100, 90, 0)  # Fixed XYZ, vary C
tilt_angles = [-30, -15, 0, 15, 30]  # ±30° range
system.camera_controller.tilt_scan(position, tilt_angles)
```

#### Spherical Scan (Combined)
```python
# Complete spherical scan combining rotation and tilt
center = Point(100, 100, 0, 0)
z_angles = [0, 60, 120, 180, 240, 300]  # Turntable positions
c_angles = [-20, 0, 20]  # Camera tilt angles
system.camera_controller.spherical_scan(center, radius=50, z_angles=z_angles, c_angles=c_angles)
```

## Configuration Files

### FluidNC Configuration
- `ConfigV1.1_4DOF.yaml` - Complete 4DOF FluidNC configuration
- Updated axis limits and servo control for C-axis
- Proper steps/mm for rotational Z-axis

### Coordinate System Mapping

#### Z-axis (Turntable):
- Command: `G1 Z180` → Rotates turntable to 180°
- Full rotation: 0-360mm = 0-360°
- 1mm = 1° rotation

#### C-axis (Camera Tilt):
- Command: `G1 C90` → Sets camera to 0° tilt (level)
- Range: 0-180mm = -90° to +90° tilt
- Center position (90mm) = 0° tilt
- Command mapping: `tilt_angle_degrees + 90 = command_mm`

## Safety Features

### Axis Limits Validation
The system automatically validates all movements:
- X: 0-200mm
- Y: 0-200mm  
- Z: 0-360° (0-360mm commands)
- C: 0-180mm (±90° tilt, where 90mm = 0° tilt)

### Error Handling
- Invalid positions are rejected before movement
- Servo limits are enforced for C-axis
- Rotational limits prevent over-rotation

## Migration from GRBL

If migrating from the old GRBL 3DOF system:

1. **Hardware**: Add turntable motor to Z-axis, servo to C-axis
2. **Configuration**: Use `ConfigV1.1_4DOF.yaml` instead of GRBL settings
3. **Code**: Update Point objects to include C-axis: `Point(x, y, z, c)`
4. **Controller**: Initialize with `use_fluidnc=True`

### Backward Compatibility
The system maintains some backward compatibility:
- 3DOF Points work (C-axis defaults to 0)
- GRBL controller can still be used with `use_fluidnc=False`
- Existing scan patterns work with additional DOF parameters

## Troubleshooting

### Common Issues:
1. **"Axis limits exceeded"**: Check coordinate ranges
2. **"Controller not connected"**: Verify FluidNC serial connection
3. **"Servo not responding"**: Check C-axis servo wiring and limits

### Debug Mode:
Enable detailed logging to see movement commands:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Performance Notes

- **Rotational movements**: Slower than linear (Z-axis max: 500mm/min)
- **Servo movements**: Fast response (C-axis max: 5000mm/min)  
- **Combined moves**: All 4 axes move simultaneously for efficiency
- **Scanning speeds**: Adjust feedrates for stability vs speed trade-off