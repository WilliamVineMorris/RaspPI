# Meshroom GPS EXIF Photogrammetry Guide

## Quick Start

Your scanner's GPS EXIF metadata should work **automatically** in Meshroom! Here's how:

### Step 1: Import Images into Meshroom
1. Open Meshroom
2. **Drag-and-drop** all scan images into the Images panel
3. Meshroom's **CameraInit** node automatically reads GPS EXIF

### Step 2: Verify GPS Data Detected
1. Select **CameraInit** node in the graph
2. Check the log output for:
   ```
   [info] Found GPS metadata for X images
   [info] GPS positions detected
   ```
3. Look in the **3D Viewer** - camera positions should appear in 3D space

### Step 3: Enable GPS Constraint (Optional)
If cameras appear scattered or you want to use GPS as positioning constraint:

1. Click **StructureFromMotion** node
2. Find parameter: `Use GPS Constraint`
3. Set to **True**
4. This tells Meshroom to trust your GPS positions during alignment

---

## Understanding GPS Coordinates in Meshroom

### How Your Scanner Uses GPS EXIF:

Your stereo scanner embeds **Cartesian coordinates (X, Y, Z in millimeters)** into GPS EXIF fields:

```
GPS Latitude  = Camera X position (mm)
GPS Longitude = Camera Y position (mm)  
GPS Altitude  = Camera Z position (mm)
```

**Example from your scans:**
- Camera 0 (left):  X=190mm, Y=-80mm, Z=20mm
- Camera 1 (right): X=190mm, Y=+80mm, Z=20mm

### How Meshroom Interprets GPS:

Meshroom's AliceVision CameraInit node:
1. **Reads GPS EXIF** automatically (GPSLatitude, GPSLongitude, GPSAltitude)
2. **Converts to 3D coordinates** (treats as Euclidean space, not geographic)
3. **Initializes camera positions** in the reconstruction
4. **Uses as constraints** during Structure-from-Motion if enabled

**This works because:**
- AliceVision treats GPS coordinates as **generic 3D positions**
- Unlike RealityScan, it doesn't force WGS84 geographic coordinate system
- You can work in **any coordinate system** (millimeters, meters, feet, etc.)

---

## Advanced: Manual Text File Import

If GPS EXIF doesn't work for some reason, use the text file:

### Option 1: Via Geolocation Plugin (If Installed)
```
Meshroom → Plugins → Geolocation Import
Select: camera_positions_meshroom.txt
```

### Option 2: Manual SfM Initialization
1. Import images without GPS
2. Let Meshroom auto-align
3. Use `ConvertSfMFormat` node to import `camera_positions_meshroom.txt`
4. Transform reconstruction to match your coordinate system

---

## Troubleshooting

### "GPS metadata not detected"
**Check EXIF is embedded:**
```bash
# On Raspberry Pi or PC:
pip install piexif
python3 -c "
import piexif
exif = piexif.load('scan_point_001_cam0.jpg')
gps = exif.get('GPS', {})
print('GPS Latitude:', gps.get(piexif.GPSIFD.GPSLatitude))
print('GPS Longitude:', gps.get(piexif.GPSIFD.GPSLongitude))
print('GPS Altitude:', gps.get(piexif.GPSIFD.GPSAltitude))
"
```

**Expected output:**
```
GPS Latitude: ((190, 1), (0, 1), (0, 10000))
GPS Longitude: ((80, 1), (0, 1), (0, 10000))
GPS Altitude: ((20, 1), (0, 1), (0, 10000))
```

If this shows `None`, EXIF wasn't embedded - redeploy code to Pi and rescan.

---

### "Camera positions seem wrong in Meshroom"
**Coordinate system orientation:**

Meshroom uses different axis conventions than your scanner. You may need to:

1. **Check axis mapping** in CameraInit log
2. **Apply transform** using `ConvertSfMFormat` node
3. **Manually set coordinate system** in Meshroom preferences

**Scanner coordinate system:**
- Origin: Turntable center
- +X: Radial distance from center
- +Y: Tangential (left/right)
- +Z: Up (vertical)
- Units: Millimeters

**If reconstruction is rotated/flipped:**
- This is normal - Meshroom auto-detects orientation from image content
- GPS positions are still correct **relative to each other**
- Final model can be rotated in post-processing (Blender, MeshLab, etc.)

---

### "Images don't align even with GPS"
GPS positions are **initialization hints**, not absolute truth. If alignment fails:

1. **Ensure sufficient image overlap** (60-80% between adjacent images)
2. **Check lighting consistency** (LED flicker fixed?)
3. **Verify camera calibration** (lens parameters)
4. **Try without GPS first** - let Meshroom auto-align, then check if positions match

**Debug workflow:**
1. Import 2-3 scan points only (6-12 images)
2. Let Meshroom auto-align WITHOUT GPS constraint
3. Check camera positions in 3D viewer
4. Compare with `camera_positions_meshroom.txt` values
5. If close match → GPS working correctly
6. If very different → coordinate system mismatch

---

## Expected Results

### In Meshroom 3D Viewer:
- **Before StructureFromMotion**: Cameras at GPS positions (scattered in 3D space)
- **After StructureFromMotion**: Cameras refined, point cloud visible
- **Stereo pairs visible**: Left and right cameras 60mm apart (your baseline)

### Camera Position Verification:
```
Camera scan_point_001_cam0.jpg:
  Position: (190.00, -80.00, 20.00)  ← Left camera

Camera scan_point_001_cam1.jpg:
  Position: (190.00, +80.00, 20.00)  ← Right camera (60mm Y offset)
```

---

## Why Meshroom > RealityScan for Your Use Case

### Advantages:
✅ **Free and open-source** (no licensing issues)  
✅ **Better GPS EXIF support** (Euclidean coordinates)  
✅ **Scriptable pipeline** (Python, command-line)  
✅ **Active development** (AliceVision framework)  
✅ **Works with text files** (no path matching issues)

### Disadvantages:
❌ **Slower than RealityScan** (no GPU acceleration for all steps)  
❌ **Steeper learning curve** (node-based interface)  
❌ **Requires more manual tuning** (not as "automatic")

---

## Files Your Scanner Generates

### For Meshroom (Primary):
1. **GPS EXIF in JPEGs** ← Automatic, works best
2. **`camera_positions_meshroom.txt`** ← Backup if GPS fails
3. **`camera_positions_full.json`** ← Complete data for debugging

### For RealityScan (Fallback):
1. **`camera_positions_realitycapture.txt`** ← May work with manual import
2. **`xmp_sidecar_files/*.xmp`** ← Unlikely to work in RealityScan 2.0

---

## Next Steps

### On Raspberry Pi:
1. **Deploy this version** to Pi (code ready)
2. **Run test scan** (5-10 points, 20-40 images)
3. **Transfer images to PC** (copy entire session folder)

### On PC with Meshroom:
1. **Install Meshroom** (if not installed): https://alicevision.org/#meshroom
2. **Drag-and-drop images** into Meshroom
3. **Check CameraInit log** for GPS detection
4. **Run reconstruction** (Start button)
5. **Verify camera positions** in 3D viewer match expected stereo array

### If GPS Works:
🎉 You're done! Meshroom will use GPS positions automatically.

### If GPS Doesn't Work:
1. Check EXIF verification script above
2. Try manual text file import
3. Report back with Meshroom log output

---

## References

- **Meshroom Manual**: https://meshroom-manual.readthedocs.io/
- **AliceVision Framework**: https://github.com/alicevision/AliceVision
- **GPS EXIF in Photogrammetry**: https://github.com/alicevision/Meshroom/issues/1449
- **Geolocation Plugin**: (community plugins, may need separate install)

---

**Status**: ✅ Ready for Pi deployment and Meshroom testing  
**Date**: October 4, 2025  
**Version**: V2.0
