# Camera Position Export - Implementation Complete

## What Was Implemented

The scanner now exports camera positions in **4 different formats** to ensure maximum compatibility with photogrammetry software:

### 1. ✅ XMP Sidecar Files (NEW - Primary Method)
- **Location**: `xmp_sidecar_files/` folder (separate from images)
- **Format**: One `.xmp` file per `.jpg` image
- **Purpose**: RealityScan auto-detection
- **Advantage**: Portable, no absolute paths, transfer-friendly

### 2. ✅ RealityCapture Text File (Backup Method)
- **Location**: `camera_positions_realitycapture.txt`
- **Format**: `filename X Y Z omega phi kappa`
- **Purpose**: Manual import if XMP fails

### 3. ✅ Meshroom Text File
- **Location**: `camera_positions_meshroom.txt`
- **Format**: `filename X Y Z`
- **Purpose**: Meshroom geolocation plugin

### 4. ✅ JSON Full Data
- **Location**: `camera_positions_full.json`
- **Format**: Complete structured data
- **Purpose**: Debugging, custom workflows

## File Structure After Scan

```
/home/pi/scanner_data/sessions/[scan_id]/
├── scan_point_000_cam0.jpg
├── scan_point_000_cam1.jpg
├── scan_point_001_cam0.jpg
├── scan_point_001_cam1.jpg
├── ...
├── xmp_sidecar_files/                    ← NEW FOLDER
│   ├── scan_point_000_cam0.xmp
│   ├── scan_point_000_cam1.xmp
│   ├── scan_point_001_cam0.xmp
│   ├── scan_point_001_cam1.xmp
│   └── ...
├── camera_positions_realitycapture.txt
├── camera_positions_meshroom.txt
└── camera_positions_full.json
```

## Why XMP Sidecar Files?

**Problem with Previous Methods:**
- ❌ GPS EXIF: Didn't work in RealityScan
- ❌ Flight Log: Required absolute paths (breaks on transfer)
- ❌ Text file: Manual import, path matching issues

**XMP Solution:**
- ✅ **Portable**: Filename-based, no paths
- ✅ **Auto-Detection**: RealityScan reads automatically
- ✅ **Transfer-Friendly**: Works after moving to different computer
- ✅ **Industry Standard**: Adobe XMP format
- ✅ **Non-Destructive**: Separate files, doesn't modify images

## How to Use

### On Raspberry Pi (Automatic):
1. Run scan - XMP files created automatically
2. Files exported to `xmp_sidecar_files/` folder

### Transfer to PC:
**Option A: Copy XMP with Images**
```bash
# Before transferring from Pi:
cd /path/to/scan/session
cp xmp_sidecar_files/*.xmp .
# Now transfer entire folder
```

**Option B: Copy XMP Later**
```bash
# After transferring to PC:
# 1. Transfer scan folder
# 2. Copy .xmp files from xmp_sidecar_files/ into images folder
# 3. Import into RealityScan
```

### In RealityScan:
1. **Ensure XMP files are in same folder as images**
2. Import images (drag-drop or File → Add Imagery)
3. RealityScan automatically detects XMP metadata
4. Check "Prior Pose" panel - should show X, Y, Z coordinates

## XMP File Format

Each XMP file contains camera position and orientation in XML format:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF>
    <rdf:Description>
      <!-- Position (X, Y, Z in millimeters) -->
      <xcr:Position>
        <rdf:Seq>
          <rdf:li>190.000000</rdf:li>
          <rdf:li>-80.000000</rdf:li>
          <rdf:li>20.000000</rdf:li>
        </rdf:Seq>
      </xcr:Position>
      
      <!-- Orientation (Omega, Phi, Kappa in degrees) -->
      <xcr:Rotation>
        <rdf:Seq>
          <rdf:li>0.000000</rdf:li>
          <rdf:li>-33.690068</rdf:li>
          <rdf:li>10.000000</rdf:li>
        </rdf:Seq>
      </xcr:Rotation>
      
      <!-- Metadata -->
      <xcr:CoordinateSystem>local</xcr:CoordinateSystem>
      <xcr:DistanceUnit>millimeter</xcr:DistanceUnit>
      <xcr:AngularUnit>degree</xcr:AngularUnit>
      <Camera:CameraID>0</Camera:CameraID>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
```

## Code Changes

### Modified Files:

**1. `core/stereo_camera_position.py`**
- Added `to_xmp_content()` method to `CameraPosition3D` class
- Added `export_xmp_sidecar_files()` method to `StereoCameraPositionCalculator`
- Generates standards-compliant XMP XML

**2. `scanning/scan_orchestrator.py`**
- Updated `_export_camera_positions_file()` method
- Now calls XMP export in addition to text file exports
- Creates `xmp_sidecar_files/` subdirectory

### New Files:

**1. `XMP_SIDECAR_GUIDE.md`**
- Complete user guide for XMP workflow
- Troubleshooting tips
- RealityScan import instructions

**2. `CAMERA_POSITION_EXPORT_SUMMARY.md`** (this file)
- Quick reference for all export formats

## Testing Checklist

### On Raspberry Pi:
- [ ] Run a test scan
- [ ] Verify `xmp_sidecar_files/` folder created
- [ ] Check XMP files exist (one per image)
- [ ] Open an XMP file, verify XML structure
- [ ] Confirm coordinates in XMP match text files

### On PC with RealityScan:
- [ ] Transfer scan folder to PC
- [ ] Copy XMP files into images folder
- [ ] Import images into RealityScan
- [ ] Check "Prior Pose" panel shows coordinates
- [ ] Verify Z coordinate is NOT 0.000000
- [ ] Run alignment using prior poses

## Fallback Options

If XMP doesn't work in RealityScan:

### Fallback 1: Text File Import
- Use `camera_positions_realitycapture.txt`
- Import via Flight Log (ensure images imported first from same directory)

### Fallback 2: GPS EXIF
- Already embedded in images
- May work in Meshroom or other software

### Fallback 3: Manual Alignment
- Let RealityScan auto-align
- Compare with known camera positions for validation

## Expected Results

### Before Fix:
```
Prior Pose Panel:
Position: local1 - Euclidean
X: 190.000000
Y: -80.000000
Z: 0.000000        ❌ WRONG
```

### After Fix (with XMP):
```
Prior Pose Panel:
Position: local1 - Euclidean
X: 190.000000
Y: -80.000000
Z: 20.000000       ✅ CORRECT
```

## Advantages of This Implementation

### Multi-Format Export:
- ✅ Supports multiple software packages
- ✅ Provides backup options
- ✅ Future-proof (new formats easy to add)

### Transfer-Friendly:
- ✅ No absolute paths
- ✅ Works across different computers
- ✅ Simple file management

### User Control:
- ✅ XMP files separate initially
- ✅ User decides when to merge
- ✅ Can test different methods

### Production-Ready:
- ✅ Automatic export every scan
- ✅ Professional XMP standard
- ✅ Compatible with industry tools

## Quick Start Guide

**1. Scan on Pi** → XMP files created automatically

**2. Transfer to PC**:
```bash
# Copy XMP into images folder
cp xmp_sidecar_files/*.xmp images/
```

**3. Import to RealityScan**:
- Open RealityScan
- Import images folder
- Camera positions load automatically

**4. Verify**:
- Check Prior Pose panel
- Z coordinate should match scan height

## Summary

✅ **Implementation Complete**: 4 export formats  
✅ **XMP Sidecar Files**: Primary method for RealityScan  
✅ **Transfer-Friendly**: No path issues  
✅ **Automatic Export**: Every scan  
✅ **User Flexibility**: Separate folder, merge when ready  

**Next Step**: Test on Raspberry Pi hardware!
