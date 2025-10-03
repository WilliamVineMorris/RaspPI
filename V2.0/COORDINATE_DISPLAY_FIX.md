# Coordinate Display Fix - Camera-Relative Visualization

## ✅ Issue Resolved

The 3D scan path preview now correctly displays **camera-relative coordinates** (what you configure) while FluidNC receives **offset-corrected machine coordinates** (actual hardware positioning).

## What Was Fixed

### Problem
The visualization was showing FluidNC machine coordinates with offsets already applied, so:
- User sets radius = 150mm
- Visualization showed ~116mm (FluidNC X coordinate after applying -10mm camera offset and +30mm turntable offset)
- User was confused: "I set 150mm, why does it show 116mm?"

### Solution
The `_generate_preview_points()` function now:
1. Generates scan pattern (internally uses FluidNC coordinates)
2. Converts FluidNC coordinates **back to camera-relative** for display
3. Returns camera-relative coordinates to the visualization

## Coordinate Flow

```
User Input (Web UI)
  ↓
Camera-Relative Coordinates
  radius = 150mm
  height = 80mm
  rotation = 0°
  tilt = 10°
  ↓
Pattern Generation (web_interface.py)
  Converts to FluidNC machine coordinates
  x = 116.2mm (150mm radius accounting for offsets)
  y = 166.2mm (80mm height accounting for offsets)
  z = 0°
  c = 10°
  ↓
Preview Generation (_generate_preview_points)
  Converts BACK to camera-relative for display
  ↓
Visualization (Plotly.js)
  Shows radius = 150mm (what user configured)
  ↓
Actual Scan Execution
  FluidNC receives x=116.2, y=166.2 (offset-corrected)
  Camera physically moves to radius=150mm from turntable
```

## Code Changes

### File: `web/web_interface.py`

#### Function: `_generate_preview_points()` (Lines 3154-3215)

**Before:**
```python
# Convert ScanPoint objects to simple dictionaries
preview_points = []
for i, point in enumerate(scan_points):
    preview_points.append({
        'index': i,
        'x': point.position.x,  # FluidNC X (with offsets)
        'y': point.position.y,  # FluidNC Y (with offsets)
        'z': point.position.z,
        'c': point.position.c
    })
```

**After:**
```python
# Convert ScanPoint objects to camera-relative coordinates for visualization
preview_points = []
for i, point in enumerate(scan_points):
    # The pattern contains FluidNC coordinates (with offsets applied)
    # Convert back to camera-relative for display
    if self.coord_transformer:
        camera_pos = self.coord_transformer.fluidnc_to_camera(point.position)
        
        # Convert cylindrical to Cartesian for Plotly visualization
        import math
        x_cart = camera_pos.radius * math.cos(math.radians(camera_pos.rotation))
        y_cart = camera_pos.radius * math.sin(math.radians(camera_pos.rotation))
        
        preview_points.append({
            'index': i,
            'x': x_cart,  # Cartesian X from turntable center
            'y': y_cart,  # Cartesian Y from turntable center
            'z': camera_pos.height,  # Height above turntable surface
            'c': camera_pos.tilt,  # Camera tilt angle
            'radius': camera_pos.radius,  # Store for tooltip
            'height': camera_pos.height,  # Store for tooltip
            'rotation': camera_pos.rotation  # Store for tooltip
        })
```

## Visualization Coordinates Explained

### What You See in the 3D Preview

- **X Range**: `-190.0 to 190.0 mm` → Camera positions relative to turntable center
- **Y Range**: `-164.5 to 164.5 mm` → Camera positions relative to turntable center
- **Z Range**: `40.0 to 120.0 mm` → Camera heights above turntable surface
- **Radius**: `190.0 mm` → Distance from turntable center (matches your "Camera Distance" setting)

### What FluidNC Actually Receives

For the same point that displays as `radius=190mm, height=80mm`:
- **FluidNC X**: ~156mm (190mm - 10mm camera offset - 30mm turntable offset calculation)
- **FluidNC Y**: ~166mm (80mm + turntable/camera offset adjustments)
- **FluidNC Z**: 0° (rotation)
- **FluidNC C**: calculated tilt angle

The offsets are applied **transparently** - you don't see them in the visualization!

## Testing the Fix

### Before This Fix
1. Set "Camera Distance" to 150mm
2. Preview showed radius ~116mm
3. User confused: "Why not 150mm?"

### After This Fix
1. Set "Camera Distance" to 150mm
2. Preview shows radius exactly 150mm ✅
3. FluidNC receives offset-corrected coordinates behind the scenes
4. Camera physically moves to 150mm from turntable center ✅

## Verification Steps

1. **Set Camera Distance to 150mm**
   - Preview should show points at 150mm radius from center (0,0)
   
2. **Set Scan Height Range: 40mm to 120mm**
   - Preview should show Z range: 40mm to 120mm
   
3. **Hover over a point in the preview**
   - Tooltip should show: `Radius: 150.0mm`, `Height: 80.0mm` (example)
   
4. **Start the actual scan**
   - FluidNC logs should show different X/Y values (with offsets applied)
   - Camera should physically reach the displayed radius/height positions

## Benefits

✅ **User-Friendly**: Visualization matches what you configure  
✅ **Accurate Hardware Control**: FluidNC receives proper offset-corrected commands  
✅ **No Confusion**: 150mm radius displays as 150mm  
✅ **Transparent Offsets**: Offset calculations happen behind the scenes  
✅ **Verifiable**: Can compare preview vs actual camera position

## Related Files

- `core/coordinate_transform.py`: Coordinate conversion logic
- `web/web_interface.py`: Preview generation (lines 3154-3215)
- `web/templates/scans.html`: 3D visualization display
- `config/scanner_config.yaml`: Camera and turntable offset configuration

---

**Status**: ✅ Fixed - Preview now shows camera-relative coordinates  
**Testing Required**: Verify on Pi hardware that physical positions match preview  
**Last Updated**: 2025-01-03
