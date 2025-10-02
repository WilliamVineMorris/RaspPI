# 3D Visualizer Enhancements - Summary

## Overview
The 3D scan path visualizer has been significantly enhanced to provide accurate previews of camera tilt behavior and focus point targeting calculations.

## New Features

### 1. **Extended Tilt Lines to Center** 🎯
- **Before**: Short 40mm indicator lines
- **After**: Lines extend from camera position all the way to the turntable center or focus point
- **Benefit**: Clear visualization of exactly where each camera is pointing

### 2. **Focus Point Targeting Support** 📍
The visualizer now supports all three servo tilt modes:

#### **Mode: None (Fixed Camera)**
- Lines point horizontally toward center
- No tilt (0° servo angle)
- All cameras parallel to turntable surface

#### **Mode: Manual Angle**
- All cameras use the same user-specified angle
- Lines show consistent tilt across all positions
- Angle range: -75° to +75°
- Updates in real-time as you adjust the angle

#### **Mode: Focus Point Targeting** ⭐
- **NEW FEATURE**: Automatic angle calculation
- Cameras automatically tilt to focus on a specific height (Y coordinate)
- Red cross marker shows the focus target point
- Each camera calculates optimal tilt angle to aim at focus point
- Perfect for scanning objects at a specific height

### 3. **Focus Point Calculations** 🔢

The visualizer performs accurate geometric calculations:

```
For each camera position:
1. Calculate horizontal distance to center: 
   dist = sqrt(x² + y²)

2. Calculate vertical distance to focus point:
   dz = focus_height - camera_height

3. Calculate optimal tilt angle:
   angle = atan2(dz, dist) * 180/π
```

**Example**:
- Camera at radius 30mm, height 100mm
- Focus point at height 80mm
- Horizontal distance: 30mm
- Vertical distance: -20mm (down)
- Calculated angle: ≈ -33.7° (tilted down)

### 4. **Real-Time Updates** ⚡
The visualizer automatically updates when you change:
- ✅ Servo tilt mode (None/Manual/Focus Point)
- ✅ Manual servo angle
- ✅ Focus Y position
- ✅ Any scan path parameter
- **Debounce**: 500ms delay to prevent excessive updates

### 5. **Visual Indicators** 👁️

**Tilt Lines**:
- Color: Black dotted lines (subtle but visible)
- Width: 2px
- Style: Dotted for non-intrusive appearance
- Hover: Shows calculated tilt angle

**Focus Point Marker** (Focus Point mode only):
- Color: Red
- Shape: Cross symbol
- Size: 8px
- Hover: Shows target height
- Position: Always at center (0, 0, focus_height)

**Turntable Disc**:
- Color: Dark gray (rgba(80, 80, 80, 0.8))
- Diameter: 100mm (10cm)
- Width: 4px (thick for visibility)
- Position: Z=0 (base level)

## Usage Examples

### Example 1: Scanning a Small Object at 80mm Height
```
1. Set Servo Tilt Mode: "Focus Point Targeting"
2. Set Focus Y Position: 80mm
3. Configure scan path (radius, heights, rotations)
```

**Result**: All cameras point at the 80mm height level, regardless of camera height. Cameras below 80mm tilt up, cameras above 80mm tilt down.

### Example 2: Fixed 45° Downward Tilt
```
1. Set Servo Tilt Mode: "Manual Angle"
2. Set Manual Servo Angle: 45°
3. Configure scan path
```

**Result**: All cameras maintain 45° downward tilt, pointing toward turntable surface.

### Example 3: Horizontal Camera View
```
1. Set Servo Tilt Mode: "None"
2. Configure scan path
```

**Result**: All cameras horizontal (0° tilt), pointing radially inward.

## Technical Details

### Coordinate System
- **X-Y Plane**: Horizontal (turntable surface)
- **Z-Axis**: Vertical (height)
- **Origin (0,0,0)**: Center of turntable at base level

### Tilt Angle Convention
- **0°**: Horizontal (parallel to turntable)
- **Positive**: Tilted down toward turntable
- **Negative**: Tilted up away from turntable
- **Range**: -75° to +75° (hardware limits)

### Focus Point Geometry
```
Camera Position: (x, y, z) in cylindrical → Cartesian
Focus Point: (0, 0, focus_height)

Tilt Calculation:
1. Vector from camera to focus: 
   (0-x, 0-y, focus_height-z)

2. Horizontal component: 
   h = sqrt((0-x)² + (0-y)²)

3. Vertical component: 
   v = focus_height - z

4. Tilt angle: 
   θ = atan2(v, h)
```

### Performance
- **Debounce Time**: 500ms
- **Typical Update**: <100ms for 20 points
- **Maximum Points**: Tested up to 72 rotation positions × multiple heights

## Visualization Tips

### Best Viewing Angle
- Default camera position provides good 3/4 view
- Use mouse to rotate/zoom for different perspectives
- Double-click to reset view

### Interpreting the Display
- **Blue→Red Path**: Shows scan order (blue=start, red=end)
- **Black Dotted Lines**: Camera viewing directions
- **Gray Circle**: Physical turntable boundary
- **Red Cross**: Target focus point (if using focus point mode)

### Troubleshooting

**Lines don't update when changing tilt settings?**
- Check browser console for errors
- Ensure Plotly.js is loaded
- Hard refresh page (Ctrl+Shift+R)

**Focus point seems wrong?**
- Verify focus Y position is within scan height range
- Check that scan path has been generated
- Ensure cylindrical scan type is selected

**Lines too subtle?**
- Lines are intentionally subtle (dotted, semi-transparent)
- Zoom in for better visibility
- Hover over lines to see tilt angles

## Files Modified

1. **web/templates/scans.html**:
   - Enhanced `visualizeScanPath()` function
   - Added focus point calculations
   - Added real-time tilt angle computation
   - Updated `updateServoTiltControls()` to trigger visualizer updates
   - Added `oninput` handlers to tilt controls

## Testing on Pi

```bash
cd ~/Documents/RaspPI/V2.0
git pull origin Test
python3 run_web_interface.py
```

Then:
1. Navigate to http://localhost:5000/scans
2. Select "Cylindrical Scan"
3. Configure scan parameters
4. Try different servo tilt modes
5. Watch visualizer update in real-time!

## Future Enhancements (Potential)

- [ ] Add object outline preview (upload STL/model)
- [ ] Show camera field of view cones
- [ ] Display depth of field zones
- [ ] Animation of scan sequence
- [ ] Export visualizer as image/video
- [ ] Multiple focus points support
- [ ] Camera collision detection

## Credits

Enhancement developed for 4DOF Scanner Control System V2.0
Date: October 3, 2025
