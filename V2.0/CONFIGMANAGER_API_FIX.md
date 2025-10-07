# ConfigManager API Fix - test_yolo_detection.py

## Issue
```
AttributeError: 'ConfigManager' object has no attribute 'get_section'
```

## Root Cause
The test script `test_yolo_detection.py` was calling a non-existent method:
```python
camera_config = config.get_section('cameras')  # ❌ Wrong - no such method
```

## Fix Applied
Updated to use the correct `get()` method:
```python
camera_config = config.get('cameras', {})  # ✅ Correct API
```

---

## ConfigManager API Reference

The `ConfigManager` class provides these methods for accessing configuration:

### Core Methods

#### `get(key: str, default: Any = None) -> Any`
Get configuration value using **dot notation**.

**Examples**:
```python
# Get nested values with dots
port = config.get('motion.controller.port')  # '/dev/ttyUSB0'
debug = config.get('system.debug_mode', False)  # False if not set

# Get entire sections as dictionaries
cameras = config.get('cameras', {})  # Returns full cameras dict
motion = config.get('motion', {})    # Returns full motion dict
lighting = config.get('lighting')    # Returns lighting config or None
```

#### `get_axis_config(axis_name: str) -> AxisConfig`
Get **typed** axis configuration as `AxisConfig` dataclass.

**Example**:
```python
x_axis = config.get_axis_config('x_axis')
print(x_axis.type)          # 'linear'
print(x_axis.min_limit)     # 0.0
print(x_axis.max_limit)     # 200.0
print(x_axis.max_feedrate)  # 5000.0
```

#### `get_camera_config(camera_name: str) -> CameraConfig`
Get **typed** camera configuration as `CameraConfig` dataclass.

**Example**:
```python
cam1 = config.get_camera_config('camera_1')
print(cam1.port)                # 0
print(cam1.capture_resolution)  # (4608, 2592)
print(cam1.quality)             # 95
```

#### `get_led_zone_config(zone_name: str) -> LEDZoneConfig`
Get **typed** LED zone configuration as `LEDZoneConfig` dataclass.

**Example**:
```python
inner = config.get_led_zone_config('inner')
print(inner.gpio_pin)      # 12
print(inner.max_intensity) # 0.9
```

### Convenience Methods

#### `get_all_axes() -> Dict[str, AxisConfig]`
Get all axis configurations as dictionary of typed objects.

**Example**:
```python
axes = config.get_all_axes()
for axis_name, axis_config in axes.items():
    print(f"{axis_name}: {axis_config.min_limit} - {axis_config.max_limit}")
```

#### `get_all_cameras() -> Dict[str, CameraConfig]`
Get all camera configurations (excludes system-level keys).

**Example**:
```python
cameras = config.get_all_cameras()
for cam_name, cam_config in cameras.items():
    print(f"{cam_name}: Port {cam_config.port}")
```

#### `get_all_led_zones() -> Dict[str, LEDZoneConfig]`
Get all LED zone configurations.

**Example**:
```python
zones = config.get_all_led_zones()
for zone_name, zone_config in zones.items():
    print(f"{zone_name}: GPIO {zone_config.gpio_pin}")
```

### Status Methods

#### `is_simulation_mode() -> bool`
Check if system is in simulation mode.

**Example**:
```python
if config.is_simulation_mode():
    print("Running in simulation - no hardware required")
```

#### `is_debug_mode() -> bool`
Check if debug mode is enabled.

**Example**:
```python
if config.is_debug_mode():
    logging.basicConfig(level=logging.DEBUG)
```

#### `get_fluidnc_port() -> str`
Get FluidNC controller port (convenience method).

**Example**:
```python
port = config.get_fluidnc_port()  # '/dev/ttyUSB0'
```

#### `get_web_port() -> int`
Get web interface port (convenience method).

**Example**:
```python
port = config.get_web_port()  # 5000
```

### Maintenance Methods

#### `reload() -> bool`
Reload configuration from file (auto-detects changes).

**Example**:
```python
if config.has_changed():
    config.reload()
```

#### `has_changed() -> bool`
Check if config file modified since last load.

**Example**:
```python
if config.has_changed():
    print("Configuration file updated!")
    config.reload()
```

#### `validate() -> bool`
Validate all configuration sections.

**Example**:
```python
try:
    config.validate()
    print("✅ Configuration valid")
except ConfigurationValidationError as e:
    print(f"❌ Invalid config: {e}")
```

#### `get_summary() -> Dict[str, Any]`
Get configuration summary for logging/debugging.

**Example**:
```python
summary = config.get_summary()
print(f"Config file: {summary['config_file']}")
print(f"Validated: {summary['validated']}")
print(f"Camera count: {summary['camera_count']}")
```

---

## Common Usage Patterns

### Pattern 1: Get Section as Dictionary
```python
# Get entire section
cameras = config.get('cameras', {})

# Access nested values
camera1_port = cameras.get('camera_1', {}).get('port', 0)

# OR use dot notation
camera1_port = config.get('cameras.camera_1.port', 0)
```

### Pattern 2: Get Typed Configuration Objects
```python
# For type safety, use typed getters
camera1 = config.get_camera_config('camera_1')
print(camera1.port)  # IDE autocomplete works!
print(camera1.capture_resolution)  # Type checked!

# Instead of raw dict access
cameras = config.get('cameras')
print(cameras['camera_1']['port'])  # No type safety
```

### Pattern 3: Initialize Components
```python
# Pass section to component constructors
from camera.pi_camera_controller import PiCameraController

config = ConfigManager('config/scanner_config.yaml')
cameras = config.get('cameras', {})

controller = PiCameraController(cameras)
```

### Pattern 4: Environment Overrides
```python
# These environment variables auto-override config
# SCANNER_SIMULATION=true → system.simulation_mode
# SCANNER_DEBUG=true → system.debug_mode
# FLUIDNC_PORT=/dev/ttyACM0 → motion.controller.port

config = ConfigManager('config/scanner_config.yaml')
# Overrides already applied automatically!
```

---

## Migration Guide

If you have code using non-existent methods:

### ❌ Old (Incorrect)
```python
cameras = config.get_section('cameras')
motion = config.get_config('motion')
axis_x = config.fetch('x_axis')
```

### ✅ New (Correct)
```python
cameras = config.get('cameras', {})
motion = config.get('motion', {})
axis_x = config.get_axis_config('x_axis')
```

---

## Error Handling

### Handling Missing Configuration
```python
# Use defaults for optional values
port = config.get('web_interface.port', 5000)

# Raise error for required values
try:
    motion_port = config.get('motion.controller.port')
    if not motion_port:
        raise ConfigurationError("Motion controller port not configured")
except Exception as e:
    logger.error(f"Configuration error: {e}")
```

### Catching Validation Errors
```python
from core.exceptions import (
    ConfigurationError,
    ConfigurationNotFoundError,
    ConfigurationValidationError
)

try:
    config = ConfigManager('config/scanner_config.yaml')
except ConfigurationNotFoundError as e:
    print(f"❌ Config file not found: {e}")
except ConfigurationValidationError as e:
    print(f"❌ Invalid configuration: {e}")
except ConfigurationError as e:
    print(f"❌ Configuration error: {e}")
```

---

## Files Updated

1. ✅ **test_yolo_detection.py** - Fixed `get_section()` → `get()`

---

## Testing After Fix

```bash
# Should now work correctly
python3 test_yolo_detection.py --with-camera
```

Expected output:
```
============================================================
Testing YOLO Detection with Pi Cameras
============================================================

[1/3] Loading configuration...
[2/3] Initializing camera controller...
✅ Camera controller initialized

[3/3] Running calibration (triggers YOLO detection)...
```

---

**Status**: ✅ Fixed  
**Impact**: Test script now uses correct ConfigManager API  
**Breaking Changes**: None (only test code affected)
