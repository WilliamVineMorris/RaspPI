# Autofocus Range Configuration

## Overview
The autofocus system has been configured to use **Macro mode**, which focuses on the closest part of the range (approximately 8cm to 1m), preventing the cameras from trying to focus at infinity and ensuring consistent focus on nearby scanning objects.

## Current Settings
- **Mode**: Macro (AfRangeEnum.Macro)
- **Focus Range**: ~8cm to ~1m (closest objects only)
- **Excludes**: Far distances and infinity focus

## AfRange Modes Available

The libcamera `AfRange` control accepts these enum values:

### 1. **Macro** (Current Setting) ✅
- **Range**: 8cm to ~1m
- **Use Case**: Scanning nearby objects
- **Speed**: Fast (small search range)
- **Perfect for**: Object scanning at close range

### 2. **Normal** 
- **Range**: ~30cm to infinity (may exclude very closest objects)
- **Use Case**: General photography
- **Speed**: Medium
- **Not ideal for**: Close-up scanning (excludes <30cm)

### 3. **Full**
- **Range**: 8cm to infinity (entire range)
- **Use Case**: When object distance is unknown
- **Speed**: Slowest (searches entire range)
- **Not recommended for**: Consistent scanning (too slow)

## Camera Specifications (ArduCam 64MP)
- **Focal Length**: 5.1mm
- **F-Stop**: F1.8
- **Physical Focus Range**: 8cm to infinity
- **Lens Type**: Auto/Manual focus

## Adjusting the Focus Mode

If you need to change the focus mode, edit these two locations in `camera/pi_camera_controller.py`:

### Location 1: `auto_focus()` method (around line 550)
```python
try:
    from libcamera import controls
    af_mode_auto = controls.AfModeEnum.Auto
    af_range_macro = controls.AfRangeEnum.Macro  # Change this
except ImportError:
    af_mode_auto = 1
    af_range_macro = 1  # Change this (0=Normal, 1=Macro, 2=Full)

picamera2.set_controls({
    "AfMode": af_mode_auto,
    "AfRange": af_range_macro  # Uses Macro mode
})
```

### Location 2: `auto_focus_and_get_value()` method (around line 820)
```python
try:
    from libcamera import controls
    af_mode_auto = controls.AfModeEnum.Auto
    af_range_macro = controls.AfRangeEnum.Macro  # Change this
except ImportError:
    af_mode_auto = 1
    af_range_macro = 1  # Change this (0=Normal, 1=Macro, 2=Full)

picamera2.set_controls({
    "AfMode": af_mode_auto,
    "AfRange": af_range_macro  # Uses Macro mode
})
```

## Example Configurations

### For Normal range (30cm-infinity, excludes close objects):
```python
from libcamera import controls
af_range_normal = controls.AfRangeEnum.Normal
# Or numeric: af_range_normal = 0
```

### For Macro range (8cm-1m, closest objects only) - CURRENT:
```python
from libcamera import controls
af_range_macro = controls.AfRangeEnum.Macro
# Or numeric: af_range_macro = 1
```

### For Full range (8cm-infinity, everything):
```python
from libcamera import controls
af_range_full = controls.AfRangeEnum.Full
# Or numeric: af_range_full = 2
```

## Why Use Macro Mode?

1. **Speed**: Small search range = fastest autofocus
2. **Accuracy**: Optimized for close objects (8cm-1m)
3. **Consistency**: Prevents focus hunting at far distances
4. **Perfect for Scanning**: Objects are typically 10-50cm away
5. **No Infinity Focus**: Won't accidentally focus on background

## Verification

After starting autofocus, look for this log message:
```
📷 Camera camera0 AF range set to Macro (8cm-1m, closest objects only)
```

The actual focus value achieved will be shown as:
```
🎯 Camera camera0 SUCCESS: Returning focus value 0.686 (raw: 6.857...)
```

## Troubleshooting

### If objects are too far away (>1m) and won't focus:
- Switch to `AfRangeEnum.Normal` or `AfRangeEnum.Full`
- Normal range starts at ~30cm and goes to infinity

### If autofocus is too slow:
- Keep using Macro mode (already the fastest)
- Ensure adequate lighting (30% flash during calibration helps)

### If focus is inconsistent:
- Macro mode should be most consistent for close objects
- Ensure object distance is within 8cm-1m range
- Verify object has sufficient contrast/texture for autofocus
- Check that lighting is adequate

### If getting "Unable to cast Python instance" errors:
- This was fixed - AfRange now uses enum values (Macro/Normal/Full)
- NOT custom numeric ranges like [3.0, 10.0]

## Technical Notes

- `AfRange` expects `AfRangeEnum` values (Normal=0, Macro=1, Full=2)
- Macro mode is hardware-optimized for close-range focus
- The exact distance ranges may vary slightly between camera modules
- Macro mode typically covers 8cm to approximately 1m
- For objects beyond 1m, use Normal or Full mode
