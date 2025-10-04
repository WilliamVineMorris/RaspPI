# XMP Sidecar Files for Photogrammetry

## What are XMP Sidecar Files?

XMP (Extensible Metadata Platform) sidecar files are separate `.xmp` files that contain metadata for images. They're the **industry standard** for storing camera positions in photogrammetry workflows.

### Why XMP Sidecar Files?

✅ **Portable**: Transfer anywhere, no absolute paths  
✅ **Auto-Detection**: RealityScan/RealityCapture reads them automatically  
✅ **Non-Destructive**: Doesn't modify original images  
✅ **Professional Standard**: Used by Adobe, RealityCapture, and other tools  
✅ **Future-Proof**: Works after transferring between computers  

## How It Works

The scanner system exports camera positions as **XMP sidecar files** in a separate folder:

```
scan_session_folder/
├── images/
│   ├── scan_point_000_cam0.jpg
│   ├── scan_point_000_cam1.jpg
│   ├── scan_point_001_cam0.jpg
│   └── scan_point_001_cam1.jpg
│
└── xmp_sidecar_files/          ← NEW: Separate XMP folder
    ├── scan_point_000_cam0.xmp  ← Matches cam0 image
    ├── scan_point_000_cam1.xmp  ← Matches cam1 image
    ├── scan_point_001_cam0.xmp
    └── scan_point_001_cam1.xmp
```

## XMP File Contents

Each XMP file contains:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description>
      
      <!-- Camera Position (X, Y, Z in millimeters) -->
      <xcr:Position>
        <rdf:Seq>
          <rdf:li>190.000000</rdf:li>  <!-- X -->
          <rdf:li>-80.000000</rdf:li>  <!-- Y -->
          <rdf:li>20.000000</rdf:li>   <!-- Z -->
        </rdf:Seq>
      </xcr:Position>
      
      <!-- Camera Orientation (Omega, Phi, Kappa in degrees) -->
      <xcr:Rotation>
        <rdf:Seq>
          <rdf:li>0.000000</rdf:li>    <!-- Omega (roll) -->
          <rdf:li>-33.690068</rdf:li>  <!-- Phi (pitch) -->
          <rdf:li>10.000000</rdf:li>   <!-- Kappa (yaw) -->
        </rdf:Seq>
      </xcr:Rotation>
      
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
```

## Usage Workflow

### After Scanning on Raspberry Pi:

The system automatically creates:
1. **Images** in session folder
2. **XMP files** in `xmp_sidecar_files/` subfolder
3. **Text files** (camera_positions_*.txt) for backup

### Transfer to PC:

**Option A: Keep Separate (Recommended for Testing)**
```
1. Copy entire scan folder to PC
2. In RealityScan: Import images from images/ folder
3. If positions don't load, manually copy XMP files:
   - Copy all .xmp files from xmp_sidecar_files/
   - Paste into images/ folder (next to .jpg files)
4. Re-import images or restart RealityScan
```

**Option B: Merge Before Transfer (Production Workflow)**
```
On Raspberry Pi before transfer:
1. Copy all .xmp files from xmp_sidecar_files/ into images/
2. Transfer images/ folder to PC
3. In RealityScan: Import images folder
   → XMP metadata loads automatically
```

## RealityScan Import Steps

### Method 1: Auto-Detection (When XMP in Same Folder)

1. **Ensure XMP files are in same folder as JPG images**
2. **Open RealityScan**
3. **Import Images**:
   - `WORKFLOW` → `Inputs` → `Add Imagery`
   - Or drag-drop images folder
4. **RealityScan auto-reads XMP metadata**
5. **Check prior poses**:
   - Select an image
   - Look for "Prior Pose" indicator
   - Should show X, Y, Z coordinates

### Method 2: Manual XMP Import (If Auto-Detection Fails)

1. Import images first
2. `ALIGNMENT` → `Import & Metadata`
3. Look for "Import XMP" or "Import Metadata" option
4. Select the xmp_sidecar_files folder or individual XMP files

## Verifying XMP Import

After importing images with XMP metadata:

### Check 1: Prior Pose Panel
- Select any image
- Look for "Prior Pose" information panel
- Should display:
  - Position: local1 - Euclidean
  - X: (value)
  - Y: (value)
  - Z: (value) ← Should NOT be 0.000000

### Check 2: 3D View
- Switch to 3D scene view
- Camera positions should be visible in 3D space
- Cameras should be arranged in turntable pattern

### Check 3: Alignment Settings
- Check if "Use Prior Poses" option is available
- This confirms RealityScan detected camera positions

## File Management

### Keep XMP Files Separate:
**Pros:**
- ✅ Clean images folder
- ✅ Easy to identify which files are metadata
- ✅ Can choose when to apply metadata

**Cons:**
- ❌ Extra manual step to copy files
- ❌ Must remember to copy before import

### Merge XMP with Images:
**Pros:**
- ✅ RealityScan auto-detects immediately
- ✅ One-step import
- ✅ Works reliably across software

**Cons:**
- ❌ More files in images folder
- ❌ Must copy XMP files manually

## Troubleshooting

### Problem: RealityScan doesn't detect XMP metadata

**Solution 1: Verify File Naming**
```bash
# XMP and JPG must have matching basenames:
✅ scan_point_000_cam0.jpg
✅ scan_point_000_cam0.xmp

❌ scan_point_000_cam0.jpg
❌ scan_point_000_cam0.JPG.xmp  ← Wrong!
```

**Solution 2: Check XMP File Location**
- XMP must be in **same folder** as JPG when importing
- Move XMP files from `xmp_sidecar_files/` to `images/`

**Solution 3: Re-import Images**
- Delete images from RealityScan project
- Ensure XMP files are with images
- Re-import images

**Solution 4: Use Text File Fallback**
- If XMP still doesn't work
- Use `camera_positions_realitycapture.txt` (also exported)
- Import via Flight Log method

### Problem: Z coordinates still showing as 0

**Check XMP file contents:**
```bash
# Open .xmp file in text editor
# Verify <xcr:Position> has three values:
<rdf:li>190.000000</rdf:li>  ← X
<rdf:li>-80.000000</rdf:li>  ← Y  
<rdf:li>20.000000</rdf:li>   ← Z (should NOT be 0)
```

If Z is 0 in XMP file → Bug in export, report issue  
If Z is correct in XMP → RealityScan not reading properly, use text file

### Problem: "Camera positions not found" error

This means XMP namespace not recognized. Try:
1. Update RealityScan to latest version
2. Use alternative text file import
3. Check RealityScan documentation for XMP support

## Alternative Formats Also Exported

The system exports **three formats simultaneously**:

### 1. XMP Sidecar Files (Recommended)
- **Location**: `xmp_sidecar_files/`
- **Format**: One .xmp per image
- **Best for**: RealityScan auto-detection

### 2. RealityCapture Text File (Backup)
- **Location**: `camera_positions_realitycapture.txt`
- **Format**: Space-separated: `filename X Y Z omega phi kappa`
- **Best for**: Manual import or if XMP fails

### 3. Meshroom Text File (Alternative Software)
- **Location**: `camera_positions_meshroom.txt`
- **Format**: Space-separated: `filename X Y Z`
- **Best for**: Meshroom geolocation plugin

### 4. JSON File (Developer/Debug)
- **Location**: `camera_positions_full.json`
- **Format**: Complete structured data
- **Best for**: Debugging, custom scripts

## Production Workflow Recommendation

**For Regular Use:**
1. Scan object on Raspberry Pi
2. **Before transferring**, run on Pi:
   ```bash
   cd /path/to/scan/session
   cp xmp_sidecar_files/*.xmp images/
   ```
3. Transfer `images/` folder to PC (now contains both JPG and XMP)
4. Import images folder into RealityScan
5. ✅ Camera positions load automatically

**For Testing/Development:**
1. Keep XMP files separate
2. Copy manually when needed
3. Test different import methods

## Technical Details

### XMP Namespace
- **xcr**: RealityCapture/RealityScan custom namespace
- **Camera**: Camera-specific metadata namespace

### Coordinate System Metadata
- **CoordinateSystem**: `local` (Euclidean, not geographic)
- **DistanceUnit**: `millimeter`
- **AngularUnit**: `degree`

### Euler Angle Convention
- **Omega**: Rotation around X-axis (roll)
- **Phi**: Rotation around Y-axis (pitch/tilt)
- **Kappa**: Rotation around Z-axis (yaw/heading)

Order: Omega → Phi → Kappa (standard photogrammetry convention)

## Summary

✅ **XMP sidecar files are the most reliable method** for transferring camera positions  
✅ **Keep them in separate folder initially** for clean organization  
✅ **Copy to images folder before import** for auto-detection  
✅ **Text files are available as backup** if XMP doesn't work  
✅ **All formats exported automatically** every scan  

**Next Steps**: Test on Raspberry Pi hardware, verify XMP import in RealityScan!
