# Camera-Specific Focus Zones - Dual-Camera Configuration

## Overview

For dual-camera turntable scanning systems, the cameras view the turntable from **different horizontal angles**. To optimize autofocus accuracy, each camera can have its own **horizontally offset focus zone** that aligns with its viewing perspective.

## Configuration

### Location
`config/scanner_config.yaml` → `cameras.focus_zone`

### Camera-Specific Focus Zones

```yaml
cameras:
  focus_zone:
    enabled: true
    
    # Camera 0: LEFT side viewing angle
    camera_0:
      window: [0.15, 0.25, 0.5, 0.5]  # Shifted LEFT (starts at 15% instead of 25%)
      description: "Left camera - focus zone shifted left"
    
    # Camera 1: RIGHT side viewing angle (MIRRORED)
    camera_1:
      window: [0.35, 0.25, 0.5, 0.5]  # Shifted RIGHT (starts at 35% instead of 25%)
      description: "Right camera - focus zone shifted right (mirrored)"
    
    use_crop: false
    crop_margin: 0.1
```

## Visual Representation

### Camera 0 (Left viewing angle)
```
┌─────────────────────────────────────┐
│                                     │
│   ┌─────────────┐                  │  ← Camera 0 image
│   │             │                  │  Focus zone shifted LEFT
│   │   FOCUS     │                  │  (15% start instead of 25%)
│   │   ZONE      │                  │
│   │             │                  │
│   └─────────────┘                  │
│                                     │
└─────────────────────────────────────┘
  15%           65%              100%
```

### Camera 1 (Right viewing angle - MIRRORED)
```
┌─────────────────────────────────────┐
│                                     │
│                  ┌─────────────┐   │  ← Camera 1 image
│                  │             │   │  Focus zone shifted RIGHT
│                  │     FOCUS   │   │  (35% start - mirrored)
│                  │     ZONE    │   │
│                  │             │   │
│                  └─────────────┘   │
│                                     │
└─────────────────────────────────────┘
  0%            35%           85%  100%
```

### Turntable Top View (Dual-Camera Setup)
```
         Camera 0                 Camera 1
         (Left view)              (Right view)
              ↓                        ↓
              📷                      📷
               \                    /
                \                  /
                 \                /
            Focus zone      Focus zone
            offset LEFT     offset RIGHT
                  \          /
                   \        /
                    \      /
                     \    /
                      ┌──┐
                      │🎯│  ← Turntable center (object)
                      └──┘
                      
Both cameras focus on turntable center, but from different angles
```

## Window Format

```
window: [x_start, y_start, width, height]
```

All values are **fractions** (0.0 to 1.0) of image dimensions:

| Parameter | Description | Camera 0 (Left) | Camera 1 (Right) |
|-----------|-------------|-----------------|------------------|
| `x_start` | Horizontal start position | `0.15` (15% from left) | `0.35` (35% from left) |
| `y_start` | Vertical start position | `0.25` (25% from top) | `0.25` (25% from top - **same**) |
| `width` | Focus zone width | `0.5` (50% of image) | `0.5` (50% of image) |
| `height` | Focus zone height | `0.5` (50% of image) | `0.5` (50% of image) |

### Offset Calculation

For mirrored horizontal positioning:
- **Offset amount**: `0.10` (10% of image width)
- **Camera 0 (left)**: `x_start = 0.25 - 0.10 = 0.15`
- **Camera 1 (right)**: `x_start = 0.25 + 0.10 = 0.35`
- **Vertical position**: Both use `y_start = 0.25` (same height)

## Implementation Details

### Code Flow

```python
# In pi_camera_controller.py -> calibrate_scan_settings()

# 1. Check for camera-specific configuration
camera_key = f'camera_{camera_id}'  # e.g., "camera_0" or "camera_1"

if camera_key in focus_zone_config:
    # Use camera-specific window
    focus_window = focus_zone_config[camera_key].get('window')
else:
    # Fallback to global window (backward compatibility)
    focus_window = focus_zone_config.get('window', [0.25, 0.25, 0.5, 0.5])

# 2. Convert fractional to absolute pixels (ScalerCropMaximum coordinates)
x_px = int(focus_window[0] * max_width)
y_px = int(focus_window[1] * max_height)
w_px = int(focus_window[2] * max_width)
h_px = int(focus_window[3] * max_height)

# 3. Apply to camera controls
control_dict["AfWindows"] = [(x_px, y_px, w_px, h_px)]
picamera2.set_controls(control_dict)
```

### Absolute Pixel Conversion (Example)

For IMX519 sensor with `ScalerCropMaximum: (0, 0, 4656, 3496)`:

**Camera 0 (Left)**:
```
x_px = int(0.15 × 4656) = 698
y_px = int(0.25 × 3496) = 874
w_px = int(0.5 × 4656) = 2328
h_px = int(0.5 × 3496) = 1748

AfWindows: [(698, 874, 2328, 1748)]
```

**Camera 1 (Right)**:
```
x_px = int(0.35 × 4656) = 1630
y_px = int(0.25 × 3496) = 874    ← Same vertical position
w_px = int(0.5 × 4656) = 2328
h_px = int(0.5 × 3496) = 1748

AfWindows: [(1630, 874, 2328, 1748)]
```

## Tuning Guidelines

### Adjusting Horizontal Offset

**Increase offset** (more separation):
```yaml
camera_0:
  window: [0.10, 0.25, 0.5, 0.5]  # Further left (10%)
camera_1:
  window: [0.40, 0.25, 0.5, 0.5]  # Further right (40%)
# Offset: 0.15 (15% shift)
```

**Decrease offset** (less separation):
```yaml
camera_0:
  window: [0.20, 0.25, 0.5, 0.5]  # Closer to center (20%)
camera_1:
  window: [0.30, 0.25, 0.5, 0.5]  # Closer to center (30%)
# Offset: 0.05 (5% shift)
```

**No offset** (both cameras centered - backward compatible):
```yaml
camera_0:
  window: [0.25, 0.25, 0.5, 0.5]
camera_1:
  window: [0.25, 0.25, 0.5, 0.5]
# Offset: 0.00 (no shift)
```

### Adjusting Focus Zone Size

**Tighter focus** (smaller objects):
```yaml
camera_0:
  window: [0.25, 0.35, 0.3, 0.3]  # 30% box, left-shifted
camera_1:
  window: [0.45, 0.35, 0.3, 0.3]  # 30% box, right-shifted (mirrored)
```

**Wider focus** (larger objects):
```yaml
camera_0:
  window: [0.10, 0.20, 0.6, 0.6]  # 60% box, left-shifted
camera_1:
  window: [0.30, 0.20, 0.6, 0.6]  # 60% box, right-shifted (mirrored)
```

### Adjusting Vertical Position

If the turntable platform is higher/lower in the frame:
```yaml
camera_0:
  window: [0.15, 0.30, 0.5, 0.5]  # Shifted down (30% from top)
camera_1:
  window: [0.35, 0.30, 0.5, 0.5]  # Shifted down (30% from top)
# Vertical: 30% (lower in frame)
```

## Backward Compatibility

If camera-specific configurations are not found, the code falls back to the global `window` setting:

```yaml
cameras:
  focus_zone:
    enabled: true
    window: [0.25, 0.25, 0.5, 0.5]  # Global fallback - both cameras use this
    use_crop: false
```

This ensures existing configurations continue to work without modification.

## Testing on Raspberry Pi

### Verify Camera-Specific Zones

```bash
cd RaspPI/V2.0

# Create test script
cat > test_camera_focus_zones.py << 'EOF'
import asyncio
from camera.pi_camera_controller import PiCameraController
from core.config_manager import ConfigManager

async def test_focus_zones():
    config = ConfigManager("config/scanner_config.yaml")
    controller = PiCameraController(config)
    
    await controller.initialize()
    
    # Calibrate both cameras
    print("📷 Calibrating Camera 0 (LEFT focus zone)...")
    settings_0 = await controller.calibrate_scan_settings("camera0")
    print(f"Camera 0 calibrated: {settings_0}")
    
    print("\n📷 Calibrating Camera 1 (RIGHT focus zone - mirrored)...")
    settings_1 = await controller.calibrate_scan_settings("camera1")
    print(f"Camera 1 calibrated: {settings_1}")
    
    # Capture test images
    result_0 = await controller.capture_photo("camera0")
    result_1 = await controller.capture_photo("camera1")
    
    print(f"\n✅ Camera 0: {result_0.image_path}")
    print(f"✅ Camera 1: {result_1.image_path}")
    print("\nCheck images to verify focus zones are offset correctly!")
    
    await controller.shutdown()

if __name__ == "__main__":
    asyncio.run(test_focus_zones())
EOF

python test_camera_focus_zones.py
```

### Expected Log Output

```
📷 Camera 0 using camera-specific focus zone from config.camera_0
📷 Camera 0 ScalerCropMaximum: (0, 0, 4656, 3496), using 4656×3496
📷 Camera 0 focus zone: AfWindows=[(698, 874, 2328, 1748)] relative to ScalerCropMaximum 4656×3496

📷 Camera 1 using camera-specific focus zone from config.camera_1
📷 Camera 1 ScalerCropMaximum: (0, 0, 4656, 3496), using 4656×3496
📷 Camera 1 focus zone: AfWindows=[(1630, 874, 2328, 1748)] relative to ScalerCropMaximum 4656×3496
```

**Notice**:
- Camera 0: `x=698` (left-shifted)
- Camera 1: `x=1630` (right-shifted - **932 pixels difference**)
- Both: `y=874` (same vertical position)

## Benefits

### For Dual-Camera Turntable Scanning

1. **Better Focus Accuracy**: Each camera focuses on where it's actually looking
2. **Geometric Alignment**: Focus zones match camera viewing angles
3. **Reduced Background Focus**: Less chance of focusing on background/edges
4. **Symmetric Configuration**: Mirrored zones maintain system symmetry
5. **Turntable-Optimized**: Both zones converge on turntable center from different angles

### Real-World Example

**Without offset** (both cameras center-focused):
- Camera 0 sees turntable slightly to the RIGHT of frame center
- Camera 1 sees turntable slightly to the LEFT of frame center
- Both autofocus on frame center → might miss the actual object

**With horizontal offset** (camera-specific zones):
- Camera 0 focus zone shifted LEFT → aligns with where turntable appears
- Camera 1 focus zone shifted RIGHT → aligns with where turntable appears
- Both autofocus on actual turntable position → better focus accuracy ✅

## Troubleshooting

### Focus zone not applied
Check log for:
```
📷 Camera X using camera-specific focus zone from config.camera_X
```

If you see:
```
📷 Camera X using global focus zone window (no camera-specific config)
```
→ Your YAML key might be wrong (`camera_0` vs `camera0`)

### Both cameras using same zone
Verify YAML structure:
```yaml
focus_zone:
  enabled: true
  camera_0:      # Must be indented under focus_zone
    window: [...]
  camera_1:      # Must be indented under focus_zone
    window: [...]
```

### Focus zones swapped
If Camera 0 focuses right and Camera 1 focuses left, you have the offsets reversed:
```yaml
# FIX: Swap the x_start values
camera_0:
  window: [0.15, ...]  # LEFT shift (smaller x_start)
camera_1:
  window: [0.35, ...]  # RIGHT shift (larger x_start)
```

## Summary

**Camera-specific focus zones** enable each camera in a dual-camera turntable scanning system to focus on the turntable from its own viewing perspective by applying **mirrored horizontal offsets** while maintaining the **same vertical position**.

This results in more accurate autofocus and better image quality for 3D scanning applications.
