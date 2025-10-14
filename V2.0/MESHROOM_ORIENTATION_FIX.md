# Meshroom Coordinate Orientation Fix - October 14, 2025

## Problem Identified from Screenshot

The Meshroom viewport showed three critical issues:
1. **All cameras in negative vertical plane** - Cameras below horizontal (negative Y in Meshroom)
2. **Wrong camera orientations** - Camera frustums pointing in incorrect directions
3. **Scattered arrangement** - Cameras not forming coherent circular scanning pattern

## Root Cause Analysis

### Previous Incorrect Transformation
```python
# OLD (WRONG):
meshroom_pose = [
    pos.x * scale_factor,        # X: OK
    pos.z * scale_factor,        # Y: OK (Z_scanner → Y_meshroom)
    -pos.y * scale_factor        # Z: WRONG! (negative flip)
]
```

**The Problem:** The `-pos.y` flip was causing cameras to appear in negative Z space in Meshroom, which combined with the Y-up orientation made them appear below/behind the scene.

### Scanner Coordinate System
Your scanner uses **Z-up convention**:
```
Scanner System (Right-handed, Z-up):
     Z (vertical, height)
     ↑
     |
     |___→ Y (horizontal, depth from front)
    /
   /
  X (horizontal, left-right)

- Origin: Turntable center, bed surface
- X, Y: 0-200mm horizontal positions
- Z: 0-200mm vertical height
- Cameras: Face INWARD toward origin
- Turntable: Rotates around Z axis
```

### Meshroom Coordinate System
Meshroom/OpenMVG uses **Y-up convention**:
```
Meshroom System (Right-handed, Y-up):
     Y (vertical, up)
     ↑
     |
     |___→ Z (horizontal, depth/forward)
    /
   /
  X (horizontal, left-right)

- Standard photogrammetry convention
- Y: Vertical "up" axis
- Z: Depth/forward axis
- X: Lateral/width axis
```

## Corrected Transformation

### Fixed Coordinate Mapping
```python
# NEW (CORRECT):
meshroom_pose = [
    pos.x * scale_factor,        # X → X (lateral, same)
    pos.z * scale_factor,        # Z → Y (height becomes up)
    pos.y * scale_factor         # Y → Z (depth, NO negative flip)
]
```

**Key Change:** Removed the negative sign on the Y→Z mapping. This keeps cameras in positive coordinate space where they should be.

### Visual Representation
```
Scanner (X, Y, Z):          Meshroom (X, Y, Z):
(100, 50, 75) mm      →     (0.1, 0.075, 0.05) m
 ↓    ↓   ↓                  ↓     ↓      ↓
 X    Y   Z                  X     Y      Z
lateral depth height    lateral up    depth

Camera at:                  Camera at:
X=100mm (right)      →      X=0.1m (right)
Y=50mm (forward)     →      Z=0.05m (forward)  
Z=75mm (up)          →      Y=0.075m (up)      ✓ Positive!
```

### Direction Vectors (Forward/Up)
The same transformation applies to orientation vectors:

```python
# Forward vector (camera looking direction)
meshroom_forward = [
    forward_x,    # X component: unchanged
    forward_z,    # Y component: from Z (vertical → up)
    forward_y     # Z component: from Y (NO flip)
]

# Up vector (camera top direction)
meshroom_up = [
    up_x,         # X component: unchanged  
    up_z,         # Y component: from Z (vertical → up)
    up_y          # Z component: from Y (NO flip)
]
```

## Why the Previous Transformation Was Wrong

### The Negative Flip Issue
```python
# WRONG: -pos.y
# This caused:
pos.y = 50mm  →  meshroom_z = -0.05m  ❌

# If camera is at Y=50mm (forward on scanner bed)
# It would appear at Z=-0.05m in Meshroom
# This is BEHIND the origin, not forward!
```

### Camera Orientation Confusion
With negative Z coordinates:
- Cameras appeared scattered in negative space
- Forward vectors pointed wrong directions
- Up vectors inverted relative to scene
- Meshroom couldn't establish proper viewing geometry

## Expected Results After Fix

### Camera Positions in Meshroom
```
Scanner Scan Pattern:
- Turntable center at origin (0,0,0)
- Cameras orbit in circle around origin
- Height typically 50-150mm above bed
- All Y positions positive (0-200mm)

Meshroom View (after fix):
✓ Cameras form circular pattern around origin
✓ All at positive Y height (0.05-0.15m above ground plane)
✓ All at positive Z depth (0.05-0.20m forward)
✓ Camera frustums point INWARD toward origin
✓ Up vectors point toward +Y (sky)
```

### Example Transformation
```
Scan Point at Scanner Position:
- X = 100mm (center laterally)
- Y = 80mm (80mm forward from back edge)
- Z = 120mm (120mm above bed)
- Camera facing turntable center

After Correct Transform:
- X = 0.100m (100mm right of center) ✓
- Y = 0.120m (120mm above ground) ✓ POSITIVE!
- Z = 0.080m (80mm forward) ✓ POSITIVE!
- Forward vector: points toward origin ✓
- Up vector: points toward +Y (sky) ✓
```

## Verification Checklist

### 1. Camera Positions (Numeric)
Open `.sfm` file and check first line:
```bash
head -1 camera_poses_meshroom.sfm
```

**Should see:**
```json
{"pose": [0.095, 0.120, 0.085], ...}
```
- **All values positive** ✓
- **X range: 0.0-0.2** (scanner 0-200mm X) ✓
- **Y range: 0.05-0.15** (scanner 50-150mm Z height) ✓
- **Z range: 0.05-0.15** (scanner 50-150mm Y depth) ✓

**Should NOT see:**
```json
{"pose": [0.095, 0.120, -0.085], ...}  ❌ Negative Z!
```

### 2. Meshroom 3D Viewport
After loading poses:
- [ ] Cameras visible above ground plane (positive Y)
- [ ] Cameras form circular/arc pattern
- [ ] Camera frustums (blue wireframes) point toward center
- [ ] Up vectors (green lines) point upward (+Y)
- [ ] No cameras in negative Y space (below ground)
- [ ] No cameras in negative Z space (behind scene)

### 3. Camera Spacing
Check distance between sequential cameras:
```python
# Calculate spacing between cameras
import json

with open('camera_poses_meshroom.sfm', 'r') as f:
    poses = [json.loads(line)['pose'] for line in f]

import math
def distance(p1, p2):
    return math.sqrt(sum((a-b)**2 for a,b in zip(p1,p2)))

spacing = [distance(poses[i], poses[i+1]) for i in range(len(poses)-1)]
print(f"Camera spacing: {min(spacing):.4f}m to {max(spacing):.4f}m")
```

**Expected:** 0.005-0.020m (5-20mm typical scan spacing)

### 4. Camera Orientation Vectors
Check forward vectors point toward origin:
```python
import json
import math

with open('camera_poses_meshroom.sfm', 'r') as f:
    data = [json.loads(line) for line in f]

# For each camera, check if forward vector points toward origin
for i, cam in enumerate(data):
    pose = cam['pose']
    forward = cam['forward']
    
    # Vector from camera to origin
    to_origin = [-p for p in pose]
    
    # Normalize
    to_origin_len = math.sqrt(sum(x**2 for x in to_origin))
    to_origin_norm = [x/to_origin_len for x in to_origin]
    
    # Dot product (should be close to 1.0 if aligned)
    dot = sum(a*b for a,b in zip(forward, to_origin_norm))
    
    print(f"Camera {i}: forward·to_origin = {dot:.3f}")
    # Should be 0.8-1.0 (pointing toward center)
```

## Technical Details

### Why No Negative Flip?

**Both scanner and Meshroom use right-handed coordinate systems:**

Scanner: +X (right), +Y (forward), +Z (up) - Right-handed ✓
Meshroom: +X (right), +Y (up), +Z (forward) - Right-handed ✓

**To convert between right-handed systems, you only need axis swapping, NOT sign flipping:**
- Scanner +Y (forward) → Meshroom +Z (forward) ✓
- Scanner +Z (up) → Meshroom +Y (up) ✓
- Scanner +X stays +X ✓

**Negative flip would create left-handed system:**
```python
# WRONG transformation:
(X, Y, Z) → (X, Z, -Y)  # Results in left-handed system! ❌

# CORRECT transformation:
(X, Y, Z) → (X, Z, Y)   # Maintains right-handed system ✓
```

### Mathematical Proof

**Right-hand rule test:**
```
Scanner: X × Y = Z
  î × ĵ = k̂  ✓

Meshroom: X × Z = Y  (after rotation)
  î × k̂ = ĵ  ✓

If we used -Y:
  î × (-ĵ) = -k̂  ❌ (left-handed!)
```

### Rotation Matrix Representation
The transformation is equivalent to a 90° rotation around X axis:

```
[X']   [1   0   0] [X]
[Y'] = [0   0   1] [Y]  (Rotation around X by +90°)
[Z']   [0   1   0] [Z]

Example:
[0.1]   [1 0 0] [0.1]   [0.1]
[0.12] = [0 0 1] [0.08] = [0.12]  ✓ All positive
[0.08]   [0 1 0] [0.12]   [0.08]
```

## Files Modified

### `core/stereo_camera_position.py`
**Changed lines ~475-495:**

```python
# BEFORE (incorrect):
meshroom_pose = [
    pos.x * scale_factor,
    pos.z * scale_factor,
    -pos.y * scale_factor  # ❌ Negative flip
]

meshroom_forward = [forward_x, forward_z, -forward_y]  # ❌
meshroom_up = [up_x, up_z, -up_y]  # ❌

# AFTER (correct):
meshroom_pose = [
    pos.x * scale_factor,
    pos.z * scale_factor,
    pos.y * scale_factor   # ✓ No flip, positive coordinates
]

meshroom_forward = [forward_x, forward_z, forward_y]  # ✓
meshroom_up = [up_x, up_z, up_y]  # ✓
```

## Common Issues and Solutions

### Issue: Cameras Still in Wrong Place
**Check:** Did you regenerate the `.sfm` file after the code fix?

**Solution:** Re-run a scan or manually export camera positions:
```bash
# Old .sfm file will still have negative Z coordinates
rm camera_poses_meshroom.sfm
# Run new scan or trigger export
```

### Issue: Cameras Upside Down
**Possible Cause:** Camera mount is inverted on physical scanner

**Solution:** Check Euler angles (omega, phi, kappa) in calculation. If cameras are physically mounted upside down, you may need:
```python
omega = 180.0  # Roll 180° to flip camera upright
```

### Issue: Forward Vectors Point Wrong Direction
**Check:** Is convergence angle correct?

**Debug:** Print forward vector and vector-to-origin:
```python
print(f"Forward: {forward}")
print(f"To origin: {[-p for p in pose]}")
# Should be similar directions (dot product ~1.0)
```

### Issue: Scale Still Wrong
**Check:** Did you apply the /1000 scale factor?

**Verify:**
```bash
grep "pose" camera_poses_meshroom.sfm | head -1
# Values should be 0.0-0.2 range (meters), not 0-200 (mm)
```

## Meshroom Settings

### ImportKnownPoses Node
```
Enabled: Yes
Poses File: camera_poses_meshroom.sfm
Coordinate System: Y-up (default) ✓
Apply Transform: No (coordinates already transformed) ✓
Lock Poses: Yes (don't re-optimize positions) ✓
```

### CameraInit Node
```
Use ImportKnownPoses: Yes
Intrinsics: Auto-detect from EXIF ✓
```

### Expected Behavior
After importing poses:
1. Green camera frustums appear in 3D view
2. All cameras form circular pattern around origin
3. Cameras point inward toward center
4. Scene bounds: ~0.2×0.2×0.2m cube
5. Object at origin ready for reconstruction

## Testing Recommendations

### Quick Visual Check
1. Load `.sfm` file in Meshroom ImportKnownPoses
2. Switch to 3D view
3. Look for circular camera arrangement
4. Verify cameras above ground plane (positive Y)
5. Check camera frustums point toward center

### Numeric Validation
```bash
# Extract all pose Y coordinates (should all be positive)
cat camera_poses_meshroom.sfm | \
  python3 -c "import sys, json; poses=[json.loads(l)['pose'][1] for l in sys.stdin]; print(f'Y range: {min(poses):.4f} to {max(poses):.4f}')"

# Expected output:
# Y range: 0.0500 to 0.1500  ✓ All positive, reasonable height
```

### Reconstruction Quality Test
Run Meshroom pipeline with locked poses:
- **Feature Matching**: Should work normally
- **Bundle Adjustment**: Should converge quickly (poses locked)
- **Depth Maps**: Should generate cleanly
- **Meshing**: Should produce complete model

If reconstruction fails, camera orientations may still need adjustment.

---

**Fix Status:** ✅ Complete - Removed negative flip, cameras now in positive coordinate space

**Critical Change:** `pos.y * scale_factor` instead of `-pos.y * scale_factor`

**Test:** Generate new scan, verify positive Y and Z coordinates in `.sfm` file

**Meshroom View:** Cameras should form circular pattern above ground plane pointing inward
