# Autofocus Range Configuration

## Overview
The autofocus system has been configured to limit the maximum focus distance to **1 meter**, preventing the cameras from trying to focus at infinity and ensuring consistent focus on nearby scanning objects.

## Current Settings
- **Minimum Focus**: 8cm (closest focus distance)
- **Maximum Focus**: 1m (prevents infinity focus)
- **Lens Position Range**: 3.0 to 10.0
  - Higher values = closer focus (10.0 ≈ 8cm)
  - Lower values = farther focus (3.0 ≈ 1m)

## Camera Specifications (ArduCam 64MP)
- **Focal Length**: 5.1mm
- **F-Stop**: F1.8
- **Physical Focus Range**: 8cm to infinity
- **Lens Type**: Auto/Manual focus

## How Lens Position Maps to Distance

For the ArduCam with 5.1mm focal length:
```
Lens Position    Approximate Distance
─────────────    ───────────────────
0.0              ∞ (infinity)
1.0-2.0          5m - 10m
3.0              ~1m (current max limit)
4.0              ~50cm
6.0              ~20cm
8.0              ~12cm
10.0             ~8cm (minimum focus)
```

## Adjusting the Focus Range

If you need to change the maximum focus distance, edit these two locations in `camera/pi_camera_controller.py`:

### Location 1: `auto_focus()` method (around line 561)
```python
picamera2.set_controls({
    "AfMode": af_mode_auto,
    "AfRange": [3.0, 10.0]  # Adjust these values
})
```

### Location 2: `auto_focus_and_get_value()` method (around line 831)
```python
picamera2.set_controls({
    "AfMode": af_mode_auto,
    "AfRange": [3.0, 10.0]  # Adjust these values
})
```

## Example Configurations

### For 2m maximum focus (wider range):
```python
"AfRange": [2.0, 10.0]  # ~2m to 8cm
```

### For 50cm maximum focus (closer objects):
```python
"AfRange": [4.0, 10.0]  # ~50cm to 8cm
```

### For 20cm maximum focus (very close objects):
```python
"AfRange": [6.0, 10.0]  # ~20cm to 8cm
```

### For full range (no limit - not recommended for scanning):
```python
"AfRange": [0.0, 10.0]  # infinity to 8cm
```

## Why Limit Focus Range?

1. **Speed**: Smaller search range = faster autofocus
2. **Accuracy**: Prevents focus hunting at far distances
3. **Consistency**: Ensures all scans focus on the object, not the background
4. **Object Scanning**: Typical scanning objects are 10-50cm away, well within 1m limit

## Verification

After changing the range, look for this log message during autofocus:
```
📷 Camera camera0 AF range limited to 8cm-1m (lens pos: 3.0-10.0)
```

The actual focus value achieved will be shown as:
```
🎯 Camera camera0 SUCCESS: Returning focus value 0.686 (raw: 6.857...)
```

## Troubleshooting

### If objects are too far away (>1m) and won't focus:
- Increase the minimum AfRange value (e.g., `[2.0, 10.0]` for 2m max)

### If autofocus is too slow:
- Reduce the search range by increasing minimum value (e.g., `[4.0, 10.0]` for 50cm max)

### If focus is inconsistent:
- Ensure adequate lighting (30% flash during calibration helps)
- Check object distance is within the configured range
- Verify object has sufficient contrast/texture for autofocus

## Technical Notes

- The `AfRange` control is a libcamera feature supported by ArduCam drivers
- Values are in lens position units, not physical distance
- The mapping between lens position and distance is approximate and may vary slightly between cameras
- Autofocus algorithm uses contrast detection within the specified range
