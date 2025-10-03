# Coordinate Offset Integration Fix

## Problem
FluidNC was receiving camera-relative coordinates instead of offset-corrected machine coordinates during actual scans.

**Symptom:**
```
G0 X130.000 Y60.000 Z0.000 C-17.103
```
This sent radius=130mm directly to FluidNC, but FluidNC needed to receive the position adjusted for camera and turntable offsets.

## Root Cause
The `ScanOrchestrator._move_to_point()` method was using scan point positions directly without coordinate transformation:
```python
# OLD CODE (WRONG):
motion_pos = MotionPosition4D(
    x=point.position.x,  # This is camera-relative radius!
    y=point.position.y,  # This is camera-relative height!
    z=point.position.z,
    c=point.position.c
)
```

## Solution
Integrated `CoordinateTransformer` into scan orchestrator to convert camera-relative coordinates to FluidNC machine coordinates before motion commands.

### Changes Made

#### 1. Import CoordinateTransformer (scan_orchestrator.py, line ~26)
```python
from core.coordinate_transform import CoordinateTransformer, CameraRelativePosition
```

#### 2. Initialize transformer in `__init__` (line ~2431)
```python
# Initialize coordinate transformer for camera-relative to FluidNC conversion
self.coord_transformer = CoordinateTransformer(config_manager)
self.logger.info("✅ Coordinate transformer initialized for offset compensation")
```

#### 3. Convert coordinates in `_move_to_point()` (line ~3760)
```python
# Convert camera-relative coordinates to FluidNC machine coordinates
camera_pos = CameraRelativePosition(
    radius=point.position.x,
    height=point.position.y,
    rotation=point.position.z,
    tilt=point.position.c
)
fluidnc_pos = self.coord_transformer.camera_to_fluidnc(camera_pos)

self.logger.info(f"📐 Camera position: radius={camera_pos.radius:.1f}mm, height={camera_pos.height:.1f}mm, rotation={camera_pos.rotation:.1f}°, tilt={camera_pos.tilt:.1f}°")
self.logger.info(f"🔧 FluidNC position: X={fluidnc_pos.x:.1f}, Y={fluidnc_pos.y:.1f}, Z={fluidnc_pos.z:.1f}°, C={fluidnc_pos.c:.1f}°")

# OPTIMIZED: Move to full 4D position with optional servo tilt calculation
try:
    from motion.base import Position4D as MotionPosition4D
    motion_pos = MotionPosition4D(
        x=fluidnc_pos.x,  # NOW USING OFFSET-CORRECTED COORDINATES
        y=fluidnc_pos.y,
        z=fluidnc_pos.z,
        c=fluidnc_pos.c
    )
```

## Expected Behavior After Fix

### Example with offsets from scanner_config.yaml:
- Camera offset: X=-10mm, Y=20mm
- Turntable offset: X=30mm, Y=-10mm

### Scan Configuration:
- Radius: 130mm
- Height: 60mm
- Rotation: 0°
- Tilt: -17.1°

### Before Fix (WRONG):
```
📐 Moving to scan point: X=130.0, Y=60.0, Z=0.0°, C=-17.1°
G0 X130.000 Y60.000 Z0.000 C-17.103
```
Camera would be at wrong position (130mm from turntable center instead of accounting for offsets).

### After Fix (CORRECT):
```
📐 Camera position: radius=130.0mm, height=60.0mm, rotation=0.0°, tilt=-17.1°
🔧 FluidNC position: X=150.0, Y=70.0, Z=0.0°, C=-17.1°
G0 X150.000 Y70.000 Z0.000 C-17.103
```
FluidNC receives offset-corrected coordinates:
- X: 130mm (radius) + 30mm (turntable X offset) - 10mm (camera X offset) = **150mm**
- Y: 60mm (height) + 20mm (camera Y offset) - 10mm (turntable Y offset) = **70mm**

## Coordinate System Understanding

### Camera-Relative (User Input/CSV):
- **Radius**: Distance from turntable center to camera
- **Height**: Vertical distance above turntable surface
- **Rotation**: Turntable angle
- **Tilt**: Camera servo angle

### FluidNC Machine Coordinates:
- **X**: Radial position (camera-relative radius + offsets)
- **Y**: Vertical position (camera-relative height + offsets)
- **Z**: Turntable rotation angle (same as camera-relative)
- **C**: Camera tilt servo angle (same as camera-relative)

**Critical Understanding**: FluidNC uses cylindrical-like coordinates, NOT Cartesian!
- FluidNC X is radial distance (like radius in cylindrical coords)
- No trigonometric conversion needed between camera-relative and FluidNC
- Simple offset arithmetic: `fluidnc_x = radius + camera_offset_x + turntable_offset_x`

## Verification

After running a scan, check the logs for:
```
📐 Camera position: radius=130.0mm, height=60.0mm, rotation=0.0°, tilt=-17.1°
🔧 FluidNC position: X=150.0, Y=70.0, Z=0.0°, C=-17.1°
```

The FluidNC position should show offset-corrected values, not the raw camera-relative coordinates.

## Testing on Pi Hardware

**IMPORTANT**: Test on actual Raspberry Pi with FluidNC connected:

1. Configure a simple scan (single point)
2. Check terminal logs for coordinate conversion messages
3. Verify FluidNC receives offset-corrected commands
4. **Physically measure** camera position to confirm accuracy
5. Compare expected vs actual camera position

### Expected Results:
- FluidNC G-code commands show offset-corrected coordinates
- Camera physically moves to correct position relative to turntable
- Preview visualization still shows camera-relative coordinates (user-friendly)
- CSV export shows camera-relative coordinates (user-configured values)

## Related Files
- `core/coordinate_transform.py`: Coordinate conversion logic
- `scanning/scan_orchestrator.py`: Scan execution with coordinate transformation
- `web/web_interface.py`: Preview generation (already using transformer)
- `config/scanner_config.yaml`: Hardware offset configuration

## Date
2025-10-03

## Status
✅ **IMPLEMENTED** - Ready for Pi hardware testing
