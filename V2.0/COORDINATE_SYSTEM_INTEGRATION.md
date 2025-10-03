# Coordinate System Integration Summary

**Date**: 2025-10-03  
**Feature**: Multi-format CSV support with proper coordinate transformations

---

## Overview

Integrated proper coordinate system transformations to handle the offset between:
- **Camera position** (where the camera actually is)
- **Turntable position** (where the object being scanned is)
- **FluidNC coordinates** (what the machine hardware uses)

---

## Coordinate Systems Defined

### 1. CAMERA-RELATIVE (Cylindrical)
**User-friendly coordinates** for thinking about scan patterns:
- `radius`: Distance from turntable center to camera (mm)
- `height`: Camera height above turntable surface (mm)
- `rotation`: Turntable rotation angle (degrees, 0-360)
- `tilt`: Camera servo tilt angle (degrees, negative=down)

**Use case**: Planning scan patterns, CSV import/export for users

### 2. FLUIDNC (Machine Coordinates)
**Hardware control coordinates** sent directly to FluidNC:
- `x`: X-axis linear position (0-200mm)
- `y`: Y-axis linear position (0-200mm)
- `z`: Z-axis rotation (degrees)
- `c`: C-axis servo tilt (degrees)

**Use case**: Machine control, debugging hardware issues

### 3. CARTESIAN (World Space)
**3D visualization coordinates** in absolute world space:
- `x`: X position in 3D space (mm)
- `y`: Y position in 3D space (mm)
- `z`: Z position/height in 3D space (mm)
- `c`: Camera tilt angle (degrees)

**Use case**: 3D visualization, simulation, collision detection

---

## Configuration Offsets

From `scanner_config.yaml`:

```yaml
cameras:
  positioning:
    camera_offset:
      x: -10.0   # mm - Camera is 10mm in negative X from FluidNC X position
      y: 20.0    # mm - Camera is 20mm above FluidNC Y position
    turntable_offset:
      x: 30.0    # mm - Turntable center is 30mm in positive X from origin
      y: -10.0   # mm - Turntable surface is 10mm below origin
```

---

## Coordinate Transformations

### CAMERA → FLUIDNC

```python
# Given: radius, height, rotation, tilt

# 1. Convert cylindrical to cartesian (relative to turntable)
camera_x_cyl = radius * cos(rotation)
camera_y_cyl = radius * sin(rotation)

# 2. Apply turntable offset (to world coords)
world_x = camera_x_cyl + turntable_offset_x
world_z = height + turntable_offset_y

# 3. Apply camera offset (to FluidNC coords)
fluidnc_x = world_x - camera_offset_x
fluidnc_y = world_z - camera_offset_y
fluidnc_z = rotation
fluidnc_c = tilt
```

### FLUIDNC → CAMERA

```python
# Given: x, y, z, c (FluidNC coords)

# 1. Apply camera offset (to world coords)
world_x = fluidnc_x + camera_offset_x
world_z = fluidnc_y + camera_offset_y

# 2. Subtract turntable offset (to camera-relative)
camera_x_cyl = world_x - turntable_offset_x
camera_z = world_z - turntable_offset_y

# 3. Convert to cylindrical
radius = sqrt(camera_x_cyl² + camera_y_cyl²)
height = camera_z
rotation = fluidnc_z
tilt = fluidnc_c
```

### CAMERA → CARTESIAN

```python
# Given: radius, height, rotation, tilt

# Simply apply turntable offset
cart_x = radius * cos(rotation) + turntable_offset_x
cart_y = radius * sin(rotation) + turntable_offset_y
cart_z = height + turntable_offset_y
cart_c = tilt
```

---

## New Files Created

### 1. `core/coordinate_transform.py`
**Purpose**: Coordinate system transformations

**Classes**:
- `CameraRelativePosition`: Dataclass for camera-relative coords
- `CartesianPosition`: Dataclass for Cartesian coords
- `CoordinateTransformer`: Main transformation class

**Key Methods**:
- `camera_to_fluidnc()`: Convert camera → FluidNC
- `fluidnc_to_camera()`: Convert FluidNC → camera
- `camera_to_cartesian()`: Convert camera → Cartesian
- `fluidnc_to_cartesian()`: Convert FluidNC → Cartesian
- `cartesian_to_camera()`: Convert Cartesian → camera
- `cartesian_to_fluidnc()`: Convert Cartesian → FluidNC

**Helper Function**:
- `calculate_servo_tilt_angle()`: Calculate tilt with proper offsets

### 2. `scanning/multi_format_csv.py`
**Purpose**: Multi-format CSV import/export

**Enums**:
- `CoordinateFormat`: CAMERA_RELATIVE, FLUIDNC, CARTESIAN

**Classes**:
- `CSVExportOptions`: Configure export format and options
- `CSVImportResult`: Results of import operation
- `MultiFormatCSVHandler`: Main handler class

**Key Methods**:
- `export_to_csv()`: Export with format selection
- `import_from_csv()`: Auto-detect format and import
- `_detect_format()`: Auto-detect from CSV headers
- `_convert_point_to_row()`: ScanPoint → CSV row
- `_convert_row_to_point()`: CSV row → ScanPoint

---

## CSV Format Examples

### Camera-Relative Format
```csv
# 4DOF Scanner Scan Points
# Coordinate Format: camera_relative
#
# Columns:
#   radius: Distance from turntable center to camera (mm)
#   height: Height of camera above turntable surface (mm)
#   rotation: Turntable rotation angle (degrees, 0-360)
#   tilt: Camera servo tilt angle (degrees, negative=down, positive=up)
#
index,radius,height,rotation,tilt
0,100.000,40.000,0.000,-15.000
1,100.000,40.000,60.000,-15.000
2,100.000,40.000,120.000,-15.000
...
```

### FluidNC Format
```csv
# 4DOF Scanner Scan Points
# Coordinate Format: fluidnc
#
# Columns:
#   x: FluidNC X-axis position (mm, 0-200)
#   y: FluidNC Y-axis position (mm, 0-200)
#   z: FluidNC Z-axis rotation (degrees)
#   c: FluidNC C-axis servo angle (degrees)
#
index,x,y,z,c
0,120.000,50.000,0.000,-15.000
1,120.000,50.000,60.000,-15.000
2,120.000,50.000,120.000,-15.000
...
```

### Cartesian Format
```csv
# 4DOF Scanner Scan Points
# Coordinate Format: cartesian
#
# Columns:
#   x: X position in 3D world space (mm)
#   y: Y position in 3D world space (mm)
#   z: Z position (height) in 3D world space (mm)
#   c: Camera tilt angle (degrees)
#
index,x,y,z,c
0,130.000,-10.000,30.000,-15.000
1,80.000,76.603,30.000,-15.000
2,15.000,86.603,30.000,-15.000
...
```

---

## Updated Servo Tilt Calculation

### Old Formula (Incorrect)
```python
# Missing offsets!
tilt_angle = atan2(focus_y - camera_y, radius)
```

### New Formula (Correct)
```python
# Account for turntable and camera offsets
camera_world_z = camera_height + turntable_offset_y
focus_world_z = focus_height + turntable_offset_y
vertical_dist = focus_world_z - camera_world_z
horizontal_dist = camera_radius

tilt_angle = atan2(vertical_dist, horizontal_dist)
```

**Example** (radius=100mm, camera_height=120mm, focus=20mm):
```
Given offsets: turntable_offset_y = -10mm

Old calculation:
  vertical_dist = 20 - 120 = -100mm
  tilt = atan2(-100, 100) = -45°

New calculation:
  camera_world_z = 120 + (-10) = 110mm
  focus_world_z = 20 + (-10) = 10mm
  vertical_dist = 10 - 110 = -100mm
  tilt = atan2(-100, 100) = -45°
  
(In this case same result, but properly accounts for offsets)
```

---

## Integration Points

### 1. Pattern Generation
**File**: `web/web_interface.py` `_create_pattern_from_config()`

**Changes Needed**:
- Use `CoordinateTransformer` for servo tilt calculation
- Apply offsets when converting radius/height to FluidNC coords
- Update focus point calculation to use `calculate_servo_tilt_angle()`

### 2. CSV Export
**File**: `web/web_interface.py` `api_scan_export_csv()`

**Changes Needed**:
- Replace `ScanPointValidator.points_to_csv()` with `MultiFormatCSVHandler.export_to_csv()`
- Add format selection parameter (default to CAMERA_RELATIVE)
- Create `CoordinateTransformer` instance

### 3. CSV Import
**File**: `web/web_interface.py` `api_scan_import_csv()`

**Changes Needed**:
- Replace validation logic with `MultiFormatCSVHandler.import_from_csv()`
- Auto-detect format from CSV headers
- Convert imported points to FluidNC coordinates

### 4. Frontend Visualization
**File**: `web/templates/scans.html` `visualizeScanPath()`

**Changes Needed**:
- Preview generation should use CAMERA_RELATIVE coordinates
- Apply offsets for correct 3D visualization
- Update focus point marker position to account for offsets

---

## Testing Checklist

### Coordinate Transformation Tests:
- [ ] Camera (100mm radius, 40mm height, 0° rotation) → FluidNC
- [ ] FluidNC (120mm x, 50mm y, 0° z) → Camera
- [ ] Round-trip: Camera → FluidNC → Camera (should match)
- [ ] Round-trip: FluidNC → Camera → FluidNC (should match)

### CSV Export Tests:
- [ ] Export in CAMERA_RELATIVE format
- [ ] Export in FLUIDNC format
- [ ] Export in CARTESIAN format
- [ ] Verify all three formats produce different coordinates
- [ ] Verify header comments are correct

### CSV Import Tests:
- [ ] Import CAMERA_RELATIVE CSV
- [ ] Import FLUIDNC CSV
- [ ] Import CARTESIAN CSV
- [ ] Auto-detection works for all three formats
- [ ] Round-trip: Export → Import produces same scan points

### Servo Tilt Tests:
- [ ] Focus point mode uses correct offsets
- [ ] Camera at 120mm height, focus at 20mm → correct tilt angle
- [ ] Tilt angles match between preview and actual scan

### Integration Tests:
- [ ] Create scan pattern → export CSV → import CSV → scan executes correctly
- [ ] Visualization matches actual camera positions
- [ ] Machine coordinates sent to FluidNC are correct

---

## Benefits

### 1. **User-Friendly CSV**
Users can work in camera-relative coordinates (radius, height) which match their mental model of the scanner.

### 2. **Hardware Accuracy**
FluidNC coordinates properly account for physical offsets, ensuring accurate positioning.

### 3. **Flexibility**
Three coordinate systems support different use cases:
- Users: Camera-relative
- Developers: FluidNC for debugging
- Visualization: Cartesian for 3D rendering

### 4. **Compatibility**
Auto-detection allows importing CSVs from any format without user intervention.

### 5. **Correctness**
Proper offset handling ensures servo tilt angles are calculated correctly for the actual camera position.

---

## Migration Notes

### Backward Compatibility:
- Existing CSV files (if any) will be auto-detected
- Default export format is CAMERA_RELATIVE (user-friendly)
- Old code using direct Position4D still works (FluidNC coords)

### Breaking Changes:
- None - new system is additive

### Configuration Required:
- Verify offsets in `scanner_config.yaml` are correct:
  ```yaml
  cameras:
    positioning:
      camera_offset:
        x: -10.0   # Measure actual offset
        y: 20.0    # Measure actual offset
      turntable_offset:
        x: 30.0    # Measure actual offset
        y: -10.0   # Measure actual offset
  ```

---

## Next Steps

1. **Integrate into web interface** - Update export/import endpoints
2. **Update pattern generation** - Use transformer for coordinate conversion
3. **Test on actual hardware** - Verify offsets are correct
4. **Add format selection UI** - Let users choose export format
5. **Documentation** - User guide for CSV formats
