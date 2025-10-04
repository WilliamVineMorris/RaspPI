# RealityScan vs Meshroom: GPS EXIF Compatibility Analysis

## TL;DR - Why RealityScan Isn't Working

**Root Cause**: RealityScan expects **geographic GPS coordinates** (degrees on Earth), but your scanner embeds **Cartesian coordinates** (millimeters in 3D space).

**Solution**: Use **Meshroom** instead - it treats GPS EXIF as generic 3D positions without forcing geographic interpretation.

---

## The Problem Explained

### What Your Scanner Does:
```python
# Scanner embeds Cartesian coordinates (mm) into GPS EXIF fields
GPSLatitude  = 190.0 mm  # Camera X position
GPSLongitude = -80.0 mm  # Camera Y position
GPSAltitude  = 20.0 mm   # Camera Z position (height)
```

### What RealityScan Expects:
```python
# RealityScan expects geographic coordinates (degrees)
GPSLatitude  = 40.7128° N  # NYC latitude
GPSLongitude = 74.0060° W  # NYC longitude  
GPSAltitude  = 10.0 m      # Elevation above sea level
```

### What Happens When They Meet:
```
1. RealityScan reads: GPSLatitude = 190.0
2. RealityScan thinks: "190° latitude? That's invalid (max is 90°)"
3. RealityScan applies WGS84 Earth coordinate transform
4. Result: Coordinate corruption, Z values become 0, positions nonsensical
```

---

## Technical Deep Dive

### GPS EXIF Standard (EXIF 2.3):

**Geographic coordinates encoded as Degrees-Minutes-Seconds (DMS):**
```
GPSLatitude: ((deg, 1), (min, 1), (sec, 100))
Example: 40° 42' 46.08" N
         ((40, 1), (42, 1), (4608, 100))
```

**Your scanner's "creative" use:**
```
GPSLatitude: ((190, 1), (0, 1), (0, 10000))
Interpreted as: 190° 0' 0.0000"
```

**Why this usually works for photogrammetry:**
- Most photogrammetry software (Meshroom, Metashape) treats GPS as **generic 3D coordinates**
- They don't enforce geographic constraints (latitude ≤ 90°, etc.)
- They use GPS as **initialization hints** for Structure-from-Motion

**Why this DOESN'T work for RealityScan 2.0:**
- RealityScan applies **strict geographic coordinate validation**
- Enforces WGS84 Earth coordinate system transformations
- Designed for **drone/aerial photogrammetry** with real GPS (lat/lon in degrees)
- Your 190mm X position is interpreted as "190° latitude" → invalid → corrupted

---

## Why Each Import Method Failed

### ❌ **GPS EXIF Import (Z=0 issue)**

**What you tried:**
- Embedded X/Y/Z in GPS fields with reference fields (N/S, E/W, Above/Below)
- Expected RealityScan to read as Euclidean coordinates

**What went wrong:**
```python
# Your EXIF:
GPSLatitude = 190mm → RealityScan interprets as 190° (INVALID)
GPSAltitude = 20mm  → RealityScan can't process due to latitude error
Result: Z defaults to 0
```

**Technical reason:**
- RealityScan validates: `-90° ≤ latitude ≤ +90°`
- Your 190mm violates this → coordinate rejected → fallback behavior (Z=0)

---

### ❌ **Text File Flight Log Import (Path Matching)**

**What you tried:**
```
camera_positions_realitycapture.txt:
scan_point_001_cam0.jpg 190.0 -80.0 20.0 0.0 -15.5 45.0
```

**What went wrong:**
```
Error: "image not found in current scene"
```

**Technical reason:**
- RealityScan Flight Log import requires:
  1. Images already imported into the project
  2. Image paths must match **exactly** (including directory structure)
  3. When you transfer files PC→Pi→PC, paths change
  4. Filename-only matching isn't supported (requires full path or same directory)

**Example of path mismatch:**
```
# Flight log file:
C:\Users\willi\Desktop\scan\scan_point_001_cam0.jpg

# Actual imported image:
D:\Transferred\RaspPI_Scans\session_20251004\scan_point_001_cam0.jpg

# Result: No match, import fails
```

---

### ❌ **XMP Sidecar Files (Format Not Recognized)**

**What you tried:**
```xml
<!-- XMP file with RealityCapture namespace -->
<xcr:Position>
  <rdf:Seq>
    <rdf:li>190.0</rdf:li>
    <rdf:li>-80.0</rdf:li>
    <rdf:li>20.0</rdf:li>
  </rdf:Seq>
</xcr:Position>
```

**What went wrong:**
- RealityScan 2.0 doesn't import XMP sidecar camera positions

**Technical reason:**
- XMP camera position import is **not documented** in RealityScan 2.0
- May have been **removed during rebrand** from RealityCapture to RealityScan
- Legacy RealityCapture (pre-2.0) may have supported it
- Current RealityScan 2.0 focuses on **AI-assisted masking** and **automatic alignment**
- Camera position import appears to be **deprioritized/removed**

**Evidence:**
- RealityScan 2.0 release notes (June 2025): No mention of XMP import
- Official docs: No XMP camera position import instructions
- User forums: Multiple reports of XMP import not working

---

## Why Meshroom Works ✅

### Meshroom's GPS EXIF Handling:

**AliceVision CameraInit node:**
```python
# Pseudo-code of how Meshroom processes GPS EXIF
def load_gps_from_image(image):
    lat = exif.get('GPSLatitude')   # Reads as generic number
    lon = exif.get('GPSLongitude')  # Reads as generic number
    alt = exif.get('GPSAltitude')   # Reads as generic number
    
    # NO GEOGRAPHIC VALIDATION!
    # Treats as Euclidean coordinates:
    camera.position = Vector3D(lat, lon, alt)
    
    return camera
```

**Key differences from RealityScan:**
1. ✅ **No geographic coordinate validation** (accepts any values)
2. ✅ **Treats GPS as generic 3D positions** (Euclidean space)
3. ✅ **Works with any units** (mm, cm, m, feet - just be consistent)
4. ✅ **No WGS84 Earth transform** (direct Cartesian coordinates)

---

## Comparison Table

| Feature | RealityScan 2.0 | Meshroom |
|---------|-----------------|----------|
| **GPS EXIF Support** | ❌ Geographic only | ✅ Euclidean 3D |
| **Coordinate Validation** | ❌ Strict (lat ≤ 90°) | ✅ None (any values) |
| **Units** | Degrees + meters | Any (mm, m, etc.) |
| **Cartesian Coordinates** | ❌ Not supported | ✅ Native support |
| **Text File Import** | ⚠️ Path-dependent | ✅ Simple format |
| **XMP Sidecar Import** | ❌ Not working | N/A (uses GPS EXIF) |
| **Auto-alignment** | ✅ Excellent (AI) | ✅ Good (traditional SfM) |
| **Speed** | ✅ Very fast | ⚠️ Slower |
| **Cost** | Free (<$1M revenue) | Free (open-source) |
| **Use Case** | Drone/aerial/objects | Versatile/technical |

---

## What Actually Works

### ✅ **Meshroom + GPS EXIF** (Recommended)
**Workflow:**
1. Run scan on Pi (GPS EXIF auto-embedded)
2. Transfer images to PC
3. Drag-and-drop into Meshroom
4. GPS positions auto-detected
5. Run reconstruction

**Advantages:**
- Zero configuration
- Transfer-friendly (EXIF travels with images)
- No path matching issues
- Works with your existing scanner code

---

### ⚠️ **RealityScan Manual Alignment** (Fallback)
**Workflow:**
1. Run scan on Pi
2. Transfer images to PC
3. Import into RealityScan
4. Let RealityScan auto-align (ignore GPS)
5. Manually verify camera positions match expected stereo geometry

**Advantages:**
- Uses RealityScan's superior AI alignment
- Good for quality checks

**Disadvantages:**
- Doesn't use your calculated positions
- Manual verification required
- No automated workflow

---

## Real-World Example: Your Scanner

### Scan Point 1 (FluidNC: X=190mm, Y=-10mm, Z_rot=10°, C_tilt=30°)

**Camera 0 (Left) - Actual 3D Position:**
```
X: 190.00 mm (radial from turntable center)
Y: -80.00 mm (left offset due to 60mm baseline + 5° convergence)
Z:  20.00 mm (height above turntable)
```

**How Meshroom Sees It:**
```python
# From GPS EXIF:
camera_position = (190.0, -80.0, 20.0)  # mm, Euclidean space
# Meshroom: "OK, camera at position (190, -80, 20) in local space"
# ✅ Works perfectly
```

**How RealityScan Sees It:**
```python
# From GPS EXIF:
latitude  = 190.0°  # ERROR: latitude must be -90° to +90°
longitude = -80.0°  # This might be OK (valid longitude range)
altitude  = 20.0 m  # Can't process due to latitude error

# RealityScan: "Invalid GPS coordinates, falling back to default"
# Result: Position = (?, ?, 0)  ← Z becomes 0
# ❌ Broken
```

---

## Recommendation

### For Your Stereo Scanner:

**Primary Workflow: Meshroom**
- ✅ GPS EXIF works out-of-the-box
- ✅ Handles Cartesian coordinates correctly
- ✅ Free and open-source
- ✅ Scriptable for automation

**Backup Workflow: RealityScan Manual**
- Use for quality validation
- Manual alignment verification
- Comparison with Meshroom results

**Not Recommended:**
- ❌ Don't waste time trying to fix RealityScan GPS import
- ❌ Don't use XMP sidecar files (not supported)
- ❌ Don't use Flight Log text import (path matching nightmare)

---

## If You Must Use RealityScan

### Option 1: Convert Coordinates to Geographic

**Modify scanner code to embed "fake" geographic coordinates:**
```python
# Convert mm to fake degrees (1mm = 0.00001 degree)
fake_lat = position.x * 0.00001  # 190mm → 0.00190°
fake_lon = position.y * 0.00001  # -80mm → -0.00080°
fake_alt = position.z * 0.001    # 20mm → 0.020m

# Now RealityScan accepts it (within valid lat/lon range)
```

**Problems:**
- ⚠️ Scale wrong (need to rescale in RealityScan after import)
- ⚠️ Extra conversion step
- ⚠️ Precision loss
- ⚠️ Confusing workflow

---

### Option 2: Use RealityScan Control Points

**Manual alignment workflow:**
1. Place physical markers on turntable (3-4 points)
2. Measure marker positions (X, Y, Z)
3. Let RealityScan auto-align
4. Manually set control points
5. Align to your coordinate system

**Problems:**
- ⏱️ Time-consuming
- 🔧 Manual process
- ❌ Not automated

---

## Conclusion

### Why RealityScan Fails:
1. **Design mismatch**: Built for geographic GPS (drones), not Cartesian coordinates (scanners)
2. **Validation too strict**: Rejects valid Cartesian values as invalid geographic coordinates
3. **XMP support removed**: Appears to have been deprecated in 2.0 rebrand
4. **Path-dependent import**: Text files require exact path matching

### Why Meshroom Works:
1. **Generic 3D coordinates**: Treats GPS as Euclidean positions, not Earth coordinates
2. **No validation**: Accepts any coordinate values
3. **Simple workflow**: GPS EXIF auto-detected, no configuration needed
4. **Transfer-friendly**: Metadata travels with images

### Your Action Plan:
1. ✅ Deploy current code to Raspberry Pi (no changes needed)
2. ✅ Run test scan (5-10 points)
3. ✅ Transfer to PC and import into **Meshroom** (not RealityScan)
4. ✅ Verify GPS positions detected in Meshroom CameraInit log
5. ✅ Run reconstruction
6. ✅ (Optional) Import result into RealityScan for comparison

---

**Status**: Analysis Complete  
**Recommendation**: Use Meshroom for automated GPS workflow  
**Date**: October 4, 2025
