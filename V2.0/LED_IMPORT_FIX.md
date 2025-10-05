# LED Controller Import Error Fix

**Date**: October 5, 2025  
**Issue**: ImportError when running LED strobe scripts  
**Status**: ✅ FIXED

## Problem

```
ImportError: cannot import name 'LightingError' from 'core.exceptions'
```

The `gpiozero_led_controller.py` was trying to import exception classes that didn't exist in `core/exceptions.py`.

## Root Cause

The LED controller was importing:
- `LightingError` (doesn't exist)
- `SafetyViolationError` (doesn't exist)

But `core/exceptions.py` actually defines:
- `LEDError` (base LED exception class)
- `LEDSafetyError` (LED safety violations)
- `LEDInitializationError` (LED init failures)
- `LEDTimingError` (LED timing issues)
- `GPIOError` (GPIO-specific errors)

## Fixes Applied

### 1. Fixed Exception Imports (`lighting/gpiozero_led_controller.py`)

**Before:**
```python
from core.exceptions import (
    HardwareError, 
    LightingError,          # ❌ Doesn't exist
    SafetyViolationError,   # ❌ Doesn't exist
    ConfigurationError
)
```

**After:**
```python
from core.exceptions import (
    HardwareError, 
    LEDError,              # ✅ Correct
    LEDSafetyError,        # ✅ Correct
    ConfigurationError
)
```

### 2. Replaced Exception Usage Throughout File

Replaced all 6 instances of `LightingError` with `LEDError`:

| Location | Old | New |
|----------|-----|-----|
| Line ~123 | `raise LightingError(f"LED initialization failed")` | `raise LEDError(...)` |
| Line ~130 | `raise LightingError(f"Zone '{zone_id}' not found")` | `raise LEDError(...)` |
| Line ~150 | `raise LightingError(f"Zone intensity control failed")` | `raise LEDError(...)` |
| Line ~165 | `raise LightingError(f"All zones intensity control failed")` | `raise LEDError(...)` |
| Line ~185 | `raise LightingError(f"Zone flash failed")` | `raise LEDError(...)` |
| Line ~205 | `raise LightingError(f"All zones flash failed")` | `raise LEDError(...)` |

### 3. Fixed LED Strobe Script API Calls (`simple_led_strobe.py`)

**Issue**: Script was calling methods that don't exist on `GPIOZeroLEDController`

**Fixes:**

| Wrong Call | Correct Call | Reason |
|------------|--------------|--------|
| `set_all_brightness(x)` | `set_all_zones_intensity(x)` | Method name mismatch |
| `set_zone_brightness(z, x)` | `set_zone_intensity(z, x)` | Method name mismatch |
| `get_zones()` | `list(led_ctrl.led_objects.keys())` | No getter method |
| `set_all_off()` | `set_all_zones_intensity(0.0)` | No dedicated off method |

**Constructor Fix:**
```python
# Before ❌
config = ConfigManager("config/scanner_config.yaml")
event_bus = EventBus()
led_ctrl = GPIOZeroLEDController(config, event_bus)

# After ✅
config_mgr = ConfigManager("config/scanner_config.yaml")
lighting_config = config_mgr.get('lighting', {})
led_ctrl = GPIOZeroLEDController(lighting_config)
```

## Exception Hierarchy Reference

```
ScannerSystemError (base)
├── HardwareError
│   ├── LEDError (LED base class)
│   │   ├── LEDInitializationError
│   │   ├── LEDSafetyError        ← Use this for safety violations
│   │   ├── LEDTimingError
│   │   └── GPIOError
│   ├── MotionControlError
│   ├── CameraError
│   └── ...
├── ConfigurationError
└── ...
```

## Files Modified

1. ✅ `lighting/gpiozero_led_controller.py`
   - Fixed exception imports (2 classes)
   - Replaced 6 exception usages

2. ✅ `simple_led_strobe.py`
   - Fixed 8 method calls to `set_all_zones_intensity()`
   - Fixed 2 calls to `set_zone_intensity()`
   - Fixed zones list access (2 places)
   - Fixed controller initialization

3. ✅ `test_led_strobe.py` (companion script)
   - Same API fixes as simple script

## Testing Status

**Scripts Ready:**
- ✅ `simple_led_strobe.py` - Quick LED testing tool
- ✅ `test_led_strobe.py` - Comprehensive test suite

**Usage:**
```bash
# Simple quick test
python simple_led_strobe.py fast 5

# Run all patterns
python simple_led_strobe.py all

# Comprehensive test suite
python test_led_strobe.py
```

**Expected Results on Pi:**
- Import errors should be resolved
- LED controller should initialize properly
- All strobe patterns should run without method errors
- GPIOs 13 and 18 should control LEDs at 250Hz PWM

## Validation Checklist

- [x] Exception classes exist in `core/exceptions.py`
- [x] All imports use correct exception names
- [x] All exception raises use correct exception types
- [x] LED controller methods match actual implementation
- [x] Strobe scripts use correct API calls
- [x] Constructor takes correct parameters (dict, not ConfigManager)
- [ ] Test on Pi hardware (pending user deployment)

## Next Steps

1. **Deploy to Raspberry Pi**:
   ```bash
   cd /home/user/Documents/RaspPI/V2.0
   git pull origin Test
   ```

2. **Test LED strobe script**:
   ```bash
   python simple_led_strobe.py fast 5
   ```

3. **Verify no import errors**

4. **Test camera focus zones** (from previous fix):
   - Check logs for "✅ Camera camera0 using camera-specific focus zone"
   - Verify AfWindows coordinates are correct

## Related Fixes

This fix complements the recent **camera focus zone bug fix** where `camera_key` was incorrectly constructed. Both issues are now resolved and ready for Pi testing.

**Summary**: Camera-specific focus zones + LED strobe testing ready for deployment! 🎉
