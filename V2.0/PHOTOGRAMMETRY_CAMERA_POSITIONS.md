# Photogrammetry Camera Position Export Implementation

## Overview

The scanner now exports accurate 3D camera positions for both **RealityCapture** and **Meshroom** photogrammetry software. This enables professional 3D reconstruction with proper camera positioning constraints.

## Features Implemented

### 1. **Stereo Camera Configuration** (`scanner_config.yaml`)

Added stereo camera array parameters:

```yaml
cameras:
  stereo:
    enabled: true
    baseline_mm: 60.0          # Distance between camera centers
    convergence_angle_deg: 5.0 # Inward rotation angle (toe-in)
```

**Adjustable Parameters:**
- `baseline_mm`: Horizontal distance between cameras (default: 60mm)
- `convergence_angle_deg`: Angle cameras rotate inward toward target (default: 5°)

### 2. **Stereo Position Calculator** (`core/stereo_camera_position.py`)

New module that calculates true 3D positions for each camera in the stereo array.

**Key Features:**
- Calculates **Cartesian 3D coordinates** (X, Y, Z in mm)
- Computes **camera orientation** (omega, phi, kappa Euler angles)
- Handles stereo baseline offset geometry
- Accounts for convergence (toe-in) angles
- Exports in multiple formats

**Stereo Geometry:**
```
Turntable rotation: θ

Left Camera (Camera 0):
  X = X_center - (baseline/2) * cos(θ + 90°)
  Y = Y_center - (baseline/2) * sin(θ + 90°)
  Z = Z_center
  Yaw = θ + convergence_angle

Right Camera (Camera 1):
  X = X_center + (baseline/2) * cos(θ + 90°)
  Y = Y_center + (baseline/2) * sin(θ + 90°)
  Z = Z_center
  Yaw = θ - convergence_angle
```

### 3. **GPS EXIF Embedding** (Enhanced)

Camera positions now embedded in JPEG EXIF GPS fields using **actual camera positions** (not scan point positions).

**Before:**
```python
# Old: Machine coordinates (not useful for photogrammetry)
GPSLatitude = FluidNC_X
GPSLongitude = FluidNC_Y
GPSAltitude = FluidNC_Z_rotation
```

**After:**
```python
# New: True 3D Cartesian camera position (stereo-corrected)
GPSLatitude = Camera_Position_X (mm)
GPSLongitude = Camera_Position_Y (mm)
GPSAltitude = Camera_Position_Z (mm)
```

Additional metadata in EXIF `UserComment`:
```
"Stereo Cam0 Orient: ω=0.00° φ=-15.50° κ=45.00°"
```

### 4. **External Camera Files** (New)

Three files exported automatically after each scan:

#### **A. `camera_positions_realitycapture.txt`**
Full format with orientation (6DOF):
```
# RealityCapture Camera Import Format
# filename X Y Z omega phi kappa
# Coordinates in mm, angles in degrees
#
scan_point_001_cam0.jpg 150.234567 -30.123456 180.000000 0.000000 -15.500000 50.000000
scan_point_001_cam1.jpg 150.234567 30.123456 180.000000 0.000000 -15.500000 40.000000
scan_point_002_cam0.jpg 145.678901 -29.876543 180.000000 0.000000 -15.500000 55.000000
...
```

**Usage in RealityCapture:**
1. Import images normally
2. Alignment → Import Camera Positions
3. Select `camera_positions_realitycapture.txt`
4. Choose coordinate system: Millimeters, +Z up

#### **B. `camera_positions_meshroom.txt`**
Simplified format (3DOF position only):
```
# Meshroom Geolocation Format
# filename X Y Z
# Coordinates in mm
#
scan_point_001_cam0.jpg 150.234567 -30.123456 180.000000
scan_point_001_cam1.jpg 150.234567 30.123456 180.000000
...
```

**Usage in Meshroom:**
1. Import images via drag-and-drop
2. Use Geolocation plugin (if installed)
3. Import `camera_positions_meshroom.txt`
4. Or let Meshroom use GPS EXIF automatically

#### **C. `camera_positions_full.json`**
Complete data for debugging/archival:
```json
{
  "scan_point_001_cam0.jpg": {
    "0": {
      "x": 150.234567,
      "y": -30.123456,
      "z": 180.000000,
      "omega": 0.0,
      "phi": -15.5,
      "kappa": 50.0,
      "camera_id": 0
    }
  },
  ...
}
```

## How It Works

### During Scanning:

1. **For each scan point:**
   - FluidNC moves to scan position
   - System calculates **stereo camera positions**:
     - Camera 0 (left): Offset left by baseline/2
     - Camera 1 (right): Offset right by baseline/2
   - Both cameras rotated inward by convergence angle

2. **During image capture:**
   - Calculate 3D position for specific camera
   - Embed in GPS EXIF fields
   - Add orientation to UserComment
   - Store position in export dictionary

3. **After scan completes:**
   - Export all positions to 3 files
   - Files saved in session directory with images

### Coordinate System:

- **Origin**: Turntable center
- **X-axis**: Forward/back from turntable
- **Y-axis**: Left/right from turntable
- **Z-axis**: Vertical (height), positive up
- **Units**: Millimeters
- **Orientation**: Euler angles (ω, φ, κ) in degrees

### File Locations:

```
sessions/
  └── scan_session_20251004_133822/
      ├── scan_point_001_cam0.jpg  (with GPS EXIF)
      ├── scan_point_001_cam1.jpg  (with GPS EXIF)
      ├── scan_point_002_cam0.jpg
      ├── ...
      ├── camera_positions_realitycapture.txt
      ├── camera_positions_meshroom.txt
      └── camera_positions_full.json
```

## Photogrammetry Software Compatibility

### ✅ **RealityCapture**
- **EXIF GPS**: Initial rough positioning
- **Camera File**: Precise positioning with orientation
- **Import**: Alignment → Import Camera Positions
- **Best format**: `camera_positions_realitycapture.txt`

### ✅ **Meshroom (AliceVision)**
- **EXIF GPS**: Automatic detection
- **Camera File**: Via Geolocation plugin
- **Import**: Drag-and-drop or geolocation import
- **Best format**: `camera_positions_meshroom.txt` or GPS EXIF

### ✅ **Other Software**
- **Metashape/PhotoScan**: Reads GPS EXIF
- **3DF Zephyr**: Reads GPS EXIF
- **COLMAP**: Can import camera files with custom script

## Configuration Guide

### Measuring Your Stereo Array:

**1. Baseline Distance:**
```
Measure center-to-center distance between camera lenses
Example: 60mm for cameras spaced 6cm apart
```

**2. Convergence Angle:**
```
Measure how much cameras rotate inward
Typical: 3-7° for desktop scanning
Calculate: tan(angle) = offset / distance_to_target
```

**3. Update `scanner_config.yaml`:**
```yaml
cameras:
  stereo:
    enabled: true
    baseline_mm: <your_measurement>      # e.g., 60.0
    convergence_angle_deg: <your_angle>  # e.g., 5.0
```

### Calibration Tips:

- **Test scan**: Do small test scan (3-5 points)
- **Check exports**: Verify camera position files created
- **Import test**: Import into RealityCapture/Meshroom
- **Adjust**: Fine-tune baseline/convergence if needed

## API Reference

### `StereoCameraPositionCalculator`

```python
from core.stereo_camera_position import StereoCameraPositionCalculator

calc = StereoCameraPositionCalculator(config_manager)

# Calculate positions for both cameras
positions = calc.calculate_stereo_camera_positions(fluidnc_pos)
# Returns: {0: CameraPosition3D, 1: CameraPosition3D}

# Calculate single camera position
pos = calc.calculate_single_camera_position(fluidnc_pos, camera_id=0)

# Export to file
calc.export_camera_positions_txt(
    positions_dict, 
    "output.txt", 
    format_type="realitycapture"
)
```

### `CameraPosition3D`

```python
@dataclass
class CameraPosition3D:
    x: float           # mm - X position in world space
    y: float           # mm - Y position in world space
    z: float           # mm - Z position (height)
    omega: float       # degrees - Roll (rotation around X)
    phi: float         # degrees - Pitch/tilt (around Y)
    kappa: float       # degrees - Yaw/heading (around Z)
    camera_id: int     # Camera identifier (0 or 1)
```

## Testing on Pi

**⚠️ IMPORTANT: Test on actual hardware before production use**

1. Deploy changes to Raspberry Pi
2. Run test scan with 5-10 points
3. Check generated files:
   ```bash
   ls -la sessions/latest_scan/camera_positions_*
   ```
4. Verify GPS EXIF:
   ```bash
   exiftool scan_point_001_cam0.jpg | grep GPS
   ```
5. Import into RealityCapture/Meshroom
6. Adjust config if positions incorrect

## Troubleshooting

### Camera positions seem wrong:
- Check baseline measurement (measure again)
- Verify convergence angle calculation
- Ensure cameras aligned with tilt axis

### Files not generated:
- Check scan completed successfully
- Verify `stereo.enabled: true` in config
- Check log for export errors

### RealityCapture import fails:
- Verify file format (space-separated)
- Check coordinate units (mm)
- Ensure image filenames match exactly

### Meshroom doesn't use positions:
- Verify GPS EXIF embedded: `exiftool image.jpg`
- Try manual import via Geolocation plugin
- Check Meshroom supports GPS import

## Future Enhancements

Potential improvements:
- [ ] Camera calibration matrix export
- [ ] Lens distortion parameters
- [ ] Bundle adjustment integration
- [ ] Scale bar/reference object detection
- [ ] Automatic coordinate system alignment
- [ ] Export to more photogrammetry formats

## References

- RealityCapture camera import: https://support.capturingreality.com/
- Meshroom documentation: https://meshroom-manual.readthedocs.io/
- AliceVision geolocation: https://github.com/alicevision/geolocation
- EXIF GPS specification: https://www.awaresystems.be/imaging/tiff/tifftags/privateifd/gps.html

---

**Implementation Date**: October 4, 2025  
**Version**: V2.0  
**Status**: ✅ Complete - Ready for Pi Hardware Testing
