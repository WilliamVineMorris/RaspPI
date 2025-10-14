# Meshroom ImportKnownPoses Known Issues & Workarounds

## Known Issues with Meshroom ImportKnownPoses Node

### Issue 1: Format Incompatibility (Most Common)
**Problem:** Meshroom's ImportKnownPoses node has had various format parsing bugs across versions.

**Symptoms:**
- Cameras load but positions ignored
- Reconstruction fails or produces scattered results
- Node shows green but doesn't actually use the poses

**Versions Affected:** Meshroom 2019.x - 2021.x (varies by build)

### Issue 2: Coordinate System Misinterpretation
**Problem:** Even with correct format, Meshroom may misinterpret coordinate system conventions.

**Symptoms:**
- Cameras appear in correct positions but reconstruction quality poor
- Scale issues persist even with correct units
- Bundle adjustment "undoes" the locked poses

### Issue 3: Intrinsics Mismatch
**Problem:** ImportKnownPoses requires exact intrinsics match or reconstruction fails.

**Symptoms:**
- Feature matching fails
- Sparse reconstruction empty or minimal
- Cameras "disconnect" from reconstruction

## Recommended Workarounds

### Option 1: Use AliceVision Sensor Database (Most Reliable)

Instead of ImportKnownPoses, embed the camera poses directly in the image EXIF using **GPS coordinates**:

**Advantages:**
✓ Works with all Meshroom versions
✓ No special nodes needed
✓ More reliable reconstruction

**Disadvantages:**
✗ Requires GPS coordinate conversion
✗ Less precise (GPS coordinate quantization)

### Option 2: Use RealityCapture Instead

RealityCapture handles external camera poses much more reliably:

**Format:** CSV file with columns:
```
#name,x,y,z,omega,phi,kappa
image_001_cam0.jpg,0.190,0.020,0.080,0.0,-12.0,0.0
image_001_cam1.jpg,0.190,0.020,-0.060,0.0,-12.0,0.0
```

**Import Process:**
1. File → Import → Import Camera Calibrations
2. Select CSV file
3. Lock camera positions
4. Run reconstruction

### Option 3: Use Metashape Python API

Metashape (formerly PhotoScan) has excellent Python scripting:

```python
import Metashape

doc = Metashape.Document()
chunk = doc.addChunk()

# Add photos
chunk.addPhotos(["image_001.jpg", "image_002.jpg", ...])

# Set camera positions
for camera in chunk.cameras:
    camera.reference.location = (x, y, z)  # Meters
    camera.reference.rotation = (omega, phi, kappa)  # Degrees
    camera.reference.location_enabled = True
    camera.reference.rotation_enabled = True

# Run workflow
chunk.matchPhotos()
chunk.alignCameras()
chunk.buildDepthMaps()
chunk.buildModel()
```

### Option 4: Meshroom SfM JSON Format (Advanced)

Create a complete `.sfm` JSON structure that Meshroom expects:

**Full format includes:**
- Version info
- Intrinsics groups
- Views (images with metadata)
- Poses (position + rotation as matrices)
- Intrinsics (sensor info)

This is complex but most compatible. See below for generator script.

## Testing Your Current File

First, let's diagnose what's actually happening:

### Test 1: Check Meshroom Log
**Location:** Look in Meshroom's cache folder for logs
```
C:\Users\[username]\AppData\Local\Temp\Meshroom\[cache_folder]\
```

**Look for:**
- "ImportKnownPoses" node logs
- Errors about "parsing" or "invalid format"
- Warnings about "intrinsics"

### Test 2: Verify Format Parsing
Run this to check if your file format is valid:

```python
import json

with open('camera_poses_meshroom_corrected.sfm', 'r') as f:
    for i, line in enumerate(f, 1):
        try:
            data = json.loads(line)
            assert 'pose' in data
            assert 'forward' in data
            assert 'up' in data
            assert len(data['pose']) == 3
            assert len(data['forward']) == 3
            assert len(data['up']) == 3
        except Exception as e:
            print(f"Line {i} invalid: {e}")
```

### Test 3: Check Image Name Matching
ImportKnownPoses requires **exact filename match**:

```bash
# List images in scan
ls scan_images/*.jpg | sort

# List poses in file
wc -l camera_poses_meshroom_corrected.sfm

# Count MUST match exactly
```

## Alternative: Full AliceVision SfM Format

The ImportKnownPoses node expects a **simplified format**, but Meshroom's core expects a **full SfM structure**. Here's a generator for the complete format:

```python
import json

def create_full_sfm_structure(poses, intrinsics, output_path):
    """
    Create complete AliceVision SfM JSON structure.
    
    Args:
        poses: List of dicts with 'filename', 'pose', 'forward', 'up'
        intrinsics: Camera intrinsics dict
        output_path: Output .sfm file path
    """
    
    # Convert pose/forward/up to rotation matrix
    import numpy as np
    
    sfm_data = {
        "version": ["1", "2", "3"],
        "featuresFolders": [],
        "matchesFolders": [],
        "views": [],
        "intrinsics": [],
        "poses": []
    }
    
    # Add intrinsics (one per camera sensor)
    intrinsic_id = 0
    sfm_data["intrinsics"].append({
        "intrinsicId": intrinsic_id,
        "width": intrinsics['width'],
        "height": intrinsics['height'],
        "sensorWidth": intrinsics['sensor_width'],
        "sensorHeight": intrinsics['sensor_height'],
        "serialNumber": intrinsics['serial'],
        "type": "pinhole",
        "principalPoint": [intrinsics['width']/2, intrinsics['height']/2],
        "focalLength": intrinsics['focal_length'],
        "distortionParams": []
    })
    
    # Add views and poses
    for view_id, pose_data in enumerate(poses):
        # Add view (image reference)
        sfm_data["views"].append({
            "viewId": view_id,
            "poseId": view_id,
            "intrinsicId": intrinsic_id,
            "path": pose_data['filename'],
            "width": intrinsics['width'],
            "height": intrinsics['height'],
            "metadata": {}
        })
        
        # Convert forward/up to rotation matrix
        forward = np.array(pose_data['forward'])
        up = np.array(pose_data['up'])
        right = np.cross(forward, up)
        
        # Rotation matrix: [right, up, -forward] (camera looks along -Z)
        R = np.column_stack([right, up, -forward])
        
        # Center (camera position in world space)
        C = np.array(pose_data['pose'])
        
        # Add pose
        sfm_data["poses"].append({
            "poseId": view_id,
            "pose": {
                "transform": {
                    "rotation": R.flatten().tolist(),
                    "center": C.tolist()
                },
                "locked": "1"  # Lock pose for reconstruction
            }
        })
    
    # Write to file
    with open(output_path, 'w') as f:
        json.dump(sfm_data, f, indent=2)
    
    print(f"Created full SfM structure: {output_path}")
```

## Recommended Next Steps

### Immediate Action: Try RealityCapture Format

Since Meshroom's ImportKnownPoses is buggy, I recommend generating **RealityCapture CSV** format:

1. Export your poses as CSV
2. Try reconstruction in RealityCapture
3. If that works, the poses are correct
4. If not, issue is with pose calculation itself

### Generate RealityCapture CSV

Would you like me to create a script that converts your corrected `.sfm` file to RealityCapture CSV format? This will:
- Use the same poses (already corrected)
- Export in RealityCapture's proven format
- Let you test if the poses work in more reliable software

### Debug Meshroom Further

Alternatively, we can:
1. Check Meshroom version you're using
2. Look at actual log files
3. Try the full AliceVision SfM JSON format
4. Test with a minimal example (2-3 images)

## Quick Diagnostic Questions

To help debug further, can you tell me:

1. **Meshroom Version:** What version are you running? (Help → About)
2. **Node Status:** Is ImportKnownPoses node green/completed?
3. **Image Count Match:** Do you have exactly 48 images for 48 poses?
4. **Image Names:** Do image filenames match exactly? (e.g., `scan_point_001_cam0.jpg`)
5. **Log Errors:** Any errors in Meshroom's log tab?

Based on your answers, I can provide a more targeted fix!
