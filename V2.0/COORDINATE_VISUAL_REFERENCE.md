# Coordinate System Visual Reference

## Before vs After the Fix

### BEFORE (Incorrect - Showing FluidNC Coordinates)
```
User sets: radius = 150mm
           ↓
Preview showed: X = 116mm, Y = 166mm  ❌ CONFUSING!
           ↓
FluidNC received: X = 116mm, Y = 166mm
           ↓
Camera moved to: radius = 150mm (physically correct, but preview was misleading)
```

### AFTER (Correct - Showing Camera-Relative Coordinates)
```
User sets: radius = 150mm
           ↓
Preview shows: radius = 150mm  ✅ MATCHES INPUT!
           ↓
FluidNC receives: X = 116mm, Y = 166mm (with offsets)
           ↓
Camera moves to: radius = 150mm (matches preview!)
```

## Coordinate System Diagram

```
                     WORLD SPACE (Top View)
                           
    Y (FluidNC)                    Y (Camera-Relative)
        ↑                               ↑
        |                               |
        |    Turntable                  |    Turntable
        |    Center                     |    Center
        |      ●━━━━━━150mm━━━━━━●      |      ●━━━━━━150mm━━━━━━●
        |                    Camera     |                    Camera
        |                               |
    ────┼────────────→ X (FluidNC)  ────┼────────────→ X (Camera-Relative)
        |                               |
    Origin                          Turntable
  (FluidNC 0,0)                       Center
                                     (0,0)
```

### Offset Relationships

**Camera Offset from FluidNC:**
- X: -10mm (camera is 10mm LEFT of FluidNC X carriage)
- Y: +20mm (camera is 20mm ABOVE FluidNC Y carriage)

**Turntable Offset from World Origin:**
- X: +30mm (turntable center is 30mm RIGHT of world origin)
- Y: -10mm (turntable surface is 10mm BELOW world origin)

## Example Calculation

### User Input (Camera-Relative):
- Radius: 150mm
- Height: 80mm
- Rotation: 0° (camera at X+ side of turntable)
- Tilt: 0° (horizontal)

### FluidNC Coordinates (Machine):
1. **Camera position in world space:**
   - Camera X = turntable_X + radius = 30 + 150 = 180mm
   - Camera Y = turntable_Y + height = -10 + 80 = 70mm

2. **FluidNC carriage position (accounting for camera offset):**
   - FluidNC X = Camera_X - camera_offset_X = 180 - (-10) = 190mm
   - FluidNC Y = Camera_Y - camera_offset_Y = 70 - 20 = 50mm

### What You See vs What FluidNC Gets:

| Coordinate | Camera-Relative (Preview) | FluidNC (Actual Command) |
|------------|---------------------------|-------------------------|
| X          | 150mm (radius)            | 190mm                   |
| Y          | 80mm (height)             | 50mm                    |
| Z          | 0° (rotation)             | 0°                      |
| C          | 0° (tilt)                 | 0°                      |

## Preview Display Format

The 3D visualization now shows **three representations** of the same point:

### 1. Cartesian Coordinates (for Plotly 3D graph)
```javascript
{
  x: 150.0,      // X position from turntable center (mm)
  y: 0.0,        // Y position from turntable center (mm)
  z: 80.0,       // Height above turntable surface (mm)
  c: 0.0         // Camera tilt angle (degrees)
}
```

### 2. Camera-Relative Coordinates (stored for tooltips)
```javascript
{
  radius: 150.0,    // Distance from turntable center (mm)
  height: 80.0,     // Height above turntable surface (mm)
  rotation: 0.0,    // Turntable rotation angle (degrees)
  tilt: 0.0         // Camera tilt angle (degrees)
}
```

### 3. FluidNC Coordinates (NOT shown to user, used internally)
```javascript
{
  x: 190.0,      // FluidNC X carriage position (mm)
  y: 50.0,       // FluidNC Y carriage position (mm)
  z: 0.0,        // FluidNC Z rotation (degrees)
  c: 0.0         // FluidNC C servo tilt (degrees)
}
```

## Why This Matters

### User Experience
❌ **Before**: "I set 150mm radius, but the preview shows 116mm. Is something broken?"  
✅ **After**: "I set 150mm radius, preview shows 150mm. Perfect!"

### Hardware Accuracy
✅ FluidNC still receives the correct offset-compensated coordinates  
✅ Camera physically moves to the displayed position  
✅ Offsets are transparent to the user

### Coordinate System Integrity
✅ Camera-relative: User-friendly specification  
✅ FluidNC: Hardware-accurate positioning  
✅ Cartesian: 3D visualization and spatial analysis

## Testing Verification

### Visual Test
1. Set "Camera Distance" = 150mm
2. Look at 3D preview
3. Measure distance from center (0,0) to camera points
4. Should show 150mm radius ✅

### Hardware Test  
1. Start scan with radius = 150mm
2. Measure actual camera distance from turntable center
3. Should be 150mm ✅
4. FluidNC logs show different X/Y (with offsets)

### Tooltip Test
1. Hover over point in preview
2. Tooltip shows: "Radius: 150.0mm, Height: 80.0mm"
3. Matches your input ✅

---

**Visual Status**: ✅ Preview matches user input  
**Hardware Status**: ✅ FluidNC receives offset-corrected coordinates  
**Transparency**: ✅ Offsets applied behind the scenes
