# Meshroom Camera Poses & GPS EXIF Removal

## Changes Made

### 1. ✅ Removed GPS EXIF Metadata
**File**: `scanning/scan_orchestrator.py`

**What was removed:**
- GPS coordinates (GPSLatitude, GPSLongitude, GPSAltitude)
- GPS orientation fields (GPSImgDirection, GPSDestBearing)
- All GPS reference fields

**Why removed:**
- GPS EXIF metadata was causing issues with photogrammetry software
- Not compatible with Cartesian coordinate systems (X, Y, Z in mm)
- Photogrammetry software expects proper camera pose files, not EXIF hacks

**What remains:**
- ✅ UserComment: Human-readable orientation (omega, phi, kappa)
- ✅ MakerNote: Machine-readable pose data for debugging
- ✅ Standard EXIF: Camera settings, exposure, flash, etc.

---

### 2. ✅ Added Meshroom SFM Export
**File**: `core/stereo_camera_position.py`

**New Method**: `export_meshroom_sfm()`

Exports camera poses in Meshroom's **ImportKnownPoses** format:
- File extension: `.sfm` (avoids JSON parsing bugs)
- Format: Newline-delimited JSON objects
- Content: `{"pose": [x, y, z], "forward": [fx, fy, fz], "up": [ux, uy, uz]}`

**Key Features:**
1. **Euler → Vector Conversion**: Converts (omega, phi, kappa) to direction vectors
2. **Coordinate Transform**: Applies Meshroom's Y-up convention
3. **Unit Vector Normalization**: Ensures forward/up are unit vectors
4. **Sorted Output**: Images ordered alphabetically (required by Meshroom)

---

## File Formats Exported

After a scan completes, you'll find these files in the session directory:

```
sessions/{session_id}/
├── images/
│   ├── scan_point_001_cam0.jpg
│   ├── scan_point_001_cam1.jpg
│   └── ...
│
├── camera_positions_realitycapture.txt     # RealityCapture format
├── camera_positions_meshroom.txt           # Simple TXT (reference only)
├── camera_poses_meshroom.sfm              # 🆕 Meshroom ImportKnownPoses format
├── camera_positions_full.json              # Complete data (archival)
│
└── xmp_sidecar_files/                      # RealityScan XMP files
    ├── scan_point_001_cam0.jpg.xmp
    └── ...
```

---

## Meshroom SFM Format Details

### **File Structure**
```json
{"pose": [45.123, 150.000, -12.345], "forward": [0.866, 0.000, 0.500], "up": [0.000, 1.000, 0.000]}
{"pose": [55.678, 150.000, -12.345], "forward": [0.866, 0.000, -0.500], "up": [0.000, 1.000, 0.000]}
```

Each line represents one camera pose with:

### **1. Pose Vector** `[x, y, z]`
- Camera position in world coordinates
- Units: millimeters
- After Meshroom coordinate transform (X, Z, -Y)

### **2. Forward Vector** `[fx, fy, fz]`
- Unit vector pointing where camera is looking
- Derived from Euler angles (omega, phi, kappa)
- Normalized to length 1.0

### **3. Up Vector** `[ux, uy, uz]`
- Unit vector pointing "up" for the camera
- Orthogonal to forward vector
- Normalized to length 1.0

---

## Coordinate System Transformation

Your scanner uses **Z-up** convention:
```
Scanner Coordinates:
- X: Horizontal (left/right)
- Y: Horizontal (forward/back)
- Z: Vertical (up/down)
```

Meshroom uses **Y-up** convention:
```
Meshroom Coordinates:
- X: Horizontal (left/right)
- Y: Vertical (up/down)
- Z: Horizontal (forward/back)
```

**Transformation Applied:**
```python
# Scanner (X, Y, Z) → Meshroom (X, Z, -Y)
meshroom_x = scanner_x
meshroom_y = scanner_z
meshroom_z = -scanner_y
```

This is applied to:
- ✅ Camera position (pose)
- ✅ Forward direction vector
- ✅ Up direction vector

---

## Euler Angles to Direction Vectors

Your system stores orientation as **Euler angles**:
- **omega**: Roll around X-axis (degrees)
- **phi**: Pitch around Y-axis (degrees)  
- **kappa**: Yaw around Z-axis (degrees)

Meshroom needs **direction vectors**:

### **Forward Vector Calculation**
```python
# Camera looking direction (initially along +Z)
forward_x = cos(phi) * sin(kappa)
forward_y = -sin(phi)
forward_z = cos(phi) * cos(kappa)
```

### **Up Vector Calculation**
```python
# Camera "up" direction (initially along -Y)
up_x = sin(omega) * sin(phi) * sin(kappa) + cos(omega) * cos(kappa)
up_y = sin(omega) * cos(phi)
up_z = sin(omega) * sin(phi) * cos(kappa) - cos(omega) * sin(kappa)
```

Both vectors are then **normalized** to unit length:
```python
length = sqrt(x² + y² + z²)
unit_vector = [x/length, y/length, z/length]
```

---

## Using in Meshroom

### **Method 1: ImportKnownPoses Node** (Recommended)
1. Open Meshroom
2. Add **ImportKnownPoses** node to your pipeline
3. Set **SfM File** input to: `camera_poses_meshroom.sfm`
4. Connect to CameraInit or StructureFromMotion node
5. Run pipeline

**Advantages:**
- ✅ Skips camera pose estimation
- ✅ Uses your precise scanner positions
- ✅ Faster reconstruction
- ✅ Better alignment

### **Method 2: Manual Import**
1. Load images in Meshroom
2. Use **Import Cameras** feature
3. Select `.sfm` file
4. Meshroom will lock camera poses

---

## Verification

### **Check SFM File Format**
```bash
# View first few lines
head -n 3 camera_poses_meshroom.sfm
```

Expected output:
```json
{"pose": [45.123, 150.000, -12.345], "forward": [0.866, 0.000, 0.500], "up": [0.000, 1.000, 0.000]}
{"pose": [55.678, 150.000, -12.345], "forward": [0.866, 0.000, -0.500], "up": [0.000, 1.000, 0.000]}
```

### **Check Vector Properties**
```python
import json
import math

with open('camera_poses_meshroom.sfm') as f:
    for line in f:
        data = json.loads(line)
        
        # Check forward is unit vector
        forward = data['forward']
        forward_len = math.sqrt(sum(x**2 for x in forward))
        assert abs(forward_len - 1.0) < 0.0001, "Forward not normalized!"
        
        # Check up is unit vector
        up = data['up']
        up_len = math.sqrt(sum(x**2 for x in up))
        assert abs(up_len - 1.0) < 0.0001, "Up not normalized!"
        
        # Check forward and up are orthogonal
        dot = sum(f*u for f, u in zip(forward, up))
        assert abs(dot) < 0.0001, "Forward and up not orthogonal!"
```

---

## Troubleshooting

### **Issue: Meshroom can't parse SFM file**
- **Check**: File extension must be `.sfm` (not `.json`)
- **Check**: Each line is valid JSON
- **Check**: No trailing comma or extra newlines

### **Issue: Cameras appear in wrong orientation**
- **Check**: Coordinate transform applied correctly
- **Check**: Forward/up vectors are normalized
- **Check**: Euler angle convention matches

### **Issue: Images not aligned with poses**
- **Check**: Image filenames match exactly
- **Check**: Images sorted in same order as poses
- **Check**: All images have corresponding pose lines

### **Issue: GPS EXIF still present in images**
- **Check**: Using latest code version
- **Check**: GPS tags removed from EXIF dict
- **Verify**: Use `exiftool image.jpg | grep GPS` (should be empty)

---

## Log Messages

During scan completion, you'll see:
```
📐 Exported RealityCapture camera positions: .../camera_positions_realitycapture.txt
📐 Exported Meshroom TXT (reference): .../camera_positions_meshroom.txt
📐 Exported Meshroom SFM (ImportKnownPoses): .../camera_poses_meshroom.sfm
💡 Use this file in Meshroom's ImportKnownPoses node
📐 Exported XMP sidecar files to: .../xmp_sidecar_files
📐 Exported JSON camera positions: .../camera_positions_full.json
```

---

## Files Modified

1. **`scanning/scan_orchestrator.py`**
   - Removed GPS EXIF writing (lines ~4400-4420)
   - Added Meshroom SFM export call (lines ~4595-4610)
   - Kept UserComment and MakerNote for debugging

2. **`core/stereo_camera_position.py`**
   - Added `export_meshroom_sfm()` method (~100 lines)
   - Euler → direction vector conversion
   - Coordinate system transformation
   - Unit vector normalization

---

## Testing Recommendations

### **Test 1: Verify GPS Removed**
```bash
# Check EXIF data
exiftool scan_point_001_cam0.jpg | grep GPS
# Should return nothing (or "GPS" not found)
```

### **Test 2: Verify SFM Format**
```bash
# Check file exists and has content
cat camera_poses_meshroom.sfm | wc -l
# Should match number of images

# Validate JSON
python3 -m json.tool camera_poses_meshroom.sfm
# Should parse without errors
```

### **Test 3: Import in Meshroom**
1. Create new Meshroom project
2. Load your scan images
3. Add ImportKnownPoses node
4. Load `camera_poses_meshroom.sfm`
5. Verify cameras appear in 3D view
6. Check poses are "locked" (not estimated)

---

## Future Enhancements

### **Camera Intrinsics** (Optional)
Could add camera calibration data:
- Focal length (pixels)
- Principal point (cx, cy)
- Distortion coefficients
- Sensor size

### **Full SfM_Data.json** (Advanced)
Could export complete AliceVision format:
- Views (image metadata)
- Intrinsics (per-camera calibration)
- Poses (with transformation matrices)
- Landmarks (optional, if known)

### **Bundle Adjustment** (Research)
Could export pre-optimized poses:
- Bundle adjustment on scanner positions
- Refine using known stereo geometry
- Reduce Meshroom's computation time

---

## References

- **Meshroom Docs**: https://meshroom-manual.readthedocs.io/
- **AliceVision**: https://github.com/alicevision/AliceVision
- **ImportKnownPoses**: Node for loading external camera poses
- **Coordinate Systems**: OpenGL (Y-up) vs Z-up conventions
- **Euler Angles**: ZYX convention (yaw-pitch-roll)

---

## Summary

✅ **GPS EXIF Removed**: No longer writing problematic GPS metadata to images

✅ **Meshroom SFM Added**: Proper format for ImportKnownPoses node

✅ **Coordinate Transform**: Correctly converts Z-up → Y-up for Meshroom

✅ **Vector Conversion**: Euler angles → normalized forward/up vectors

✅ **Backward Compatible**: All existing formats still exported (RealityCapture, XMP, JSON)

Your scanner now exports camera poses in the correct format for Meshroom's ImportKnownPoses feature!
