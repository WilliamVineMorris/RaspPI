# Meshroom Coordinate Scale Fix - October 14, 2025

## Problem Identified

When loading camera poses into Meshroom, the scale appeared extremely large and the orientation was difficult to verify. This was caused by **unit mismatch**:

- **Scanner coordinates**: Millimeters (0-200mm range)
- **Meshroom expectation**: Meters (standard photogrammetry convention)
- **Result**: Positions interpreted as 1000× too large (200mm shown as 200m!)

## Root Cause: Unit Mismatch

### Scanner Hardware Specs
```yaml
# From scanner_config.yaml
x_axis: 0-200 mm
y_axis: 0-200 mm  
z_axis: 0-360 degrees (continuous rotation)
c_axis: ±90 degrees (camera tilt)
```

### Photogrammetry Software Convention
- **Meshroom**: Expects meters (following computer vision standards)
- **RealityCapture**: Can handle both, but prefers meters
- **Metashape**: Expects meters
- **OpenMVG**: Expects meters

### What Happened
When your scanner exported `x=100, y=150, z=50` (in mm):
- Meshroom interpreted this as 100m, 150m, 50m
- Actual real-world size: 0.1m, 0.15m, 0.05m
- **Scale error: 1000× too large!**

## Solution Implemented

### 1. Automatic Unit Conversion
Added `scale_to_meters` parameter to convert mm → m:

```python
def export_meshroom_sfm(
    self,
    positions_dict: Dict[str, Dict[int, CameraPosition3D]],
    output_path: str,
    scale_to_meters: bool = True  # NEW: Default converts mm to meters
) -> bool:
```

**Conversion Formula:**
```python
# Scale factor for unit conversion
scale_factor = 0.001 if scale_to_meters else 1.0  # mm → m = ÷1000

# Apply to all position coordinates
meshroom_pose = [
    pos.x * scale_factor,      # 100mm → 0.1m
    pos.z * scale_factor,      # 150mm → 0.15m
    -pos.y * scale_factor      # 50mm → 0.05m
]
```

### 2. Configuration Control
Added setting to `scanner_config.yaml`:

```yaml
scanning:
  position_export:
    # Convert coordinates from mm to meters for photogrammetry software
    # Most photogrammetry software (Meshroom, RealityCapture, etc.) expects meters
    scale_to_meters: true  # Default: true (convert to meters)
```

### 3. Logging Clarity
Export now logs the units being used:

```
📐 Converting coordinates from millimeters to meters (÷1000)
📐 Exported Meshroom SFM (ImportKnownPoses): camera_poses_meshroom.sfm
📏 Coordinate units: meters
💡 Use this file in Meshroom's ImportKnownPoses node
```

## Before vs After

### Before (Millimeters)
```json
{"pose": [100, 50, -150], "forward": [0.0, -1.0, 0.0], "up": [0.0, 0.0, 1.0]}
```
- Position: 100mm, 50mm, 150mm
- Meshroom interprets as: **100m, 50m, 150m** ❌
- Scene appears **1000× too large** in viewport

### After (Meters)
```json
{"pose": [0.1, 0.05, -0.15], "forward": [0.0, -1.0, 0.0], "up": [0.0, 0.0, 1.0]}
```
- Position: 0.1m, 0.05m, 0.15m
- Meshroom interprets as: **0.1m, 0.05m, 0.15m** ✅
- Scene appears at **correct scale** in viewport

## Coordinate System Details

### Scanner Native Coordinates (Z-up, Right-handed)
```
     Z (rotation axis)
     ↑
     |
     |
     +---→ X (linear)
    /
   /
  Y (linear)
```

### Meshroom Coordinates (Y-up, Right-handed)
```
     Y (up)
     ↑
     |
     |
     +---→ X (same)
    /
   /
  Z (depth)
```

### Transformation Applied
```python
# Standard (X, Y, Z) in mm → Meshroom (X, Z, -Y) in meters
meshroom_x = scanner_x * 0.001  # mm → m
meshroom_y = scanner_z * 0.001  # Z becomes Y (up axis)
meshroom_z = -scanner_y * 0.001 # Y becomes -Z (flip direction)
```

**Example Conversion:**
- Scanner: (100mm, 50mm, 75mm)
- Step 1 (coordinate swap): (100, 75, -50)
- Step 2 (scale to meters): **(0.1m, 0.075m, -0.05m)**

## Expected Scan Dimensions

For a typical scan on your 200×200mm scanner bed:

### In Scanner Units (mm)
```
X range: 0-200 mm (linear travel)
Y range: 0-200 mm (linear travel)
Z range: 0-360° (turntable - affects X/Y via trig)
Object size: ~50-150 mm typical
```

### In Meshroom (meters)
```
X range: 0.0-0.2 m
Y range: 0.0-0.2 m (becomes Z in Meshroom)
Z range: 0.0-0.2 m (becomes -Y in Meshroom)
Object size: ~0.05-0.15 m typical
```

### Viewport Appearance
- Camera positions form a **0.2m × 0.2m × 0.2m** volume (20cm cube)
- Camera spacing: **5-20mm** → **0.005-0.02m** between poses
- Object at center: **~0.1m** dimensions (10cm) ✅ Reasonable!

## Meshroom Settings Recommendations

### 1. ImportKnownPoses Node
```
Enabled: Yes
Poses File: camera_poses_meshroom.sfm
Coordinate System: Y-up (default)
Units: Meters (matches our export)
```

### 2. CameraInit Node
```
Sensor Database: Use your camera's sensor specs
Focal Length: Should match image EXIF
Principal Point: Center of image
```

### 3. Scale Verification in Meshroom

After loading poses, verify scale in 3D viewport:
- **Camera spacing**: Should be 5-20mm (0.005-0.02m)
- **Total volume**: ~200×200×200mm (0.2×0.2×0.2m cube)
- **Camera icons**: Should be tiny relative to scene

**If scale still looks wrong:**
1. Check "Display → Camera Size" slider in Meshroom
2. Verify camera spacing between poses
3. Look at numeric coordinates in pose file

## Troubleshooting

### Issue: Scale Still Too Large
**Check:**
```bash
# Look at actual values in .sfm file
cat camera_poses_meshroom.sfm | head -1
```

**Should see:**
```json
{"pose": [0.123, 0.045, -0.089], ...}  # Values 0.0-0.2 range ✅
```

**NOT:**
```json
{"pose": [123, 45, -89], ...}  # Values 0-200 range ❌
```

**Fix:** Set `scale_to_meters: true` in scanner_config.yaml

### Issue: Scale Too Small (Camera Poses Invisible)
**Check:** Meshroom viewport zoom - camera poses might be correctly sized but zoomed out

**Test:** Click a camera icon - if coordinates show 0.0-0.2 range, scale is correct

### Issue: Vertical Direction Inverted
**Symptoms:** Object appears upside-down after reconstruction

**Explanation:** This is correct! The coordinate transform flips Y to -Z:
- Scanner +Y (up) → Meshroom -Z (into screen)
- Scanner +Z (turntable axis) → Meshroom +Y (up)

**Fix:** In Meshroom, rotate the final model 180° around X-axis after reconstruction

### Issue: Cameras Not Appearing at All
**Check:**
1. File format: Must be `.sfm` extension (Meshroom won't parse `.json`)
2. Line format: Each line must be valid JSON
3. Image names: Must match actual image filenames exactly

**Verify:**
```bash
# Check line count matches image count
wc -l camera_poses_meshroom.sfm

# Check JSON validity
cat camera_poses_meshroom.sfm | head -1 | python -m json.tool
```

## Configuration Options

### Keep Millimeters (For Special Cases)
If you need to keep mm for specific software:

```yaml
# scanner_config.yaml
scanning:
  position_export:
    scale_to_meters: false  # Export in millimeters
```

**When to use:**
- Custom scripts that expect mm
- Debugging coordinate calculations
- Non-photogrammetry applications

### Override at Runtime (Future Enhancement)
Could add GUI toggle:
```python
# In web interface or CLI
export_camera_poses(
    format="meshroom",
    units="meters"  # or "millimeters", "inches", "feet"
)
```

## File Changes

### Modified Files
1. **`core/stereo_camera_position.py`**
   - Added `scale_to_meters` parameter to `export_meshroom_sfm()`
   - Added scale factor calculation: `0.001 if scale_to_meters else 1.0`
   - Applied scale to all position coordinates
   - Added logging for unit conversion

2. **`scanning/scan_orchestrator.py`**
   - Read `scale_to_meters` from config
   - Pass parameter to export function
   - Log coordinate units in export summary

3. **`config/scanner_config.yaml`**
   - Added `position_export` section under `scanning`
   - Added `scale_to_meters: true` setting with documentation

## Technical Details

### Precision Considerations

**Original (mm):**
```python
x = 123.456  # mm (sub-mm precision)
```

**Converted (m):**
```python
x = 0.123456  # m (same precision, 6 decimal places)
```

**Float precision:** Python floats have ~15-17 significant digits:
- **Millimeters**: 0.001mm precision at 200mm range
- **Meters**: 0.000001m (1µm) precision at 0.2m range
- **Result**: No precision loss from unit conversion ✅

### Memory/Performance Impact
- **None**: Only affects export, not runtime calculations
- Conversion happens once during export
- No change to internal coordinate system

## Expected Results

### Meshroom 3D Viewport
After loading your `.sfm` file with scale conversion:

```
✅ Camera positions visible at reasonable scale
✅ Camera spacing: 5-20mm (0.005-0.02m)
✅ Scene bounds: ~20cm cube (0.2m × 0.2m × 0.2m)
✅ Camera forward vectors point toward object center
✅ Can click cameras and see position coordinates (0.0-0.2 range)
```

### Reconstruction Quality
Proper scale improves:
- **Feature matching**: Correct scale helps depth estimation
- **Bundle adjustment**: Converges faster with realistic dimensions
- **Meshing**: Proper scale prevents algorithm parameter issues
- **Texture projection**: Correct distances improve texture resolution

## Verification Steps

### 1. Check Export Log
```bash
grep "Converting coordinates" scan_log.txt
# Should see: "Converting coordinates from millimeters to meters (÷1000)"

grep "Coordinate units" scan_log.txt  
# Should see: "Coordinate units: meters"
```

### 2. Inspect SFM File
```bash
head -3 camera_poses_meshroom.sfm
```

**Expected output:**
```json
{"pose": [0.123, 0.045, -0.089], "forward": [0.0, -0.998, 0.062], "up": [0.0, 0.062, 0.998]}
{"pose": [0.134, 0.045, -0.078], "forward": [0.174, -0.985, 0.062], "up": [0.0, 0.062, 0.998]}
{"pose": [0.142, 0.045, -0.065], "forward": [0.342, -0.940, 0.062], "up": [0.0, 0.062, 0.998]}
```

**Key indicators:**
- Values in 0.0-0.2 range ✅
- Decimals present (not integers) ✅
- Negative values for flipped axis ✅

### 3. Meshroom Import
1. Load `.sfm` in ImportKnownPoses node
2. View in 3D viewport
3. Check camera positions numerically
4. Verify object appears at origin with ~0.1m size

### 4. Quick Scale Check
**Rule of thumb:** Camera positions should be:
- **Larger than 0.001** (not microscopic)
- **Smaller than 1.0** (not giant)
- **Around 0.05-0.15** for your scanner

---

**Fix Status:** ✅ Complete - Default converts to meters

**Test Next Scan:** Download new scan and check `.sfm` file has values 0.0-0.2m range

**Configuration:** Edit `scanner_config.yaml` to change `scale_to_meters: false` if needed
