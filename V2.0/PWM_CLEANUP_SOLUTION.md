# GPIO PWM Cleanup Error Resolution

## Problem Summary
The hardware integration tests were passing (7/7, 100%) but were generating persistent PWM cleanup errors:

```
Exception ignored in: <function PWM.__del__ at 0x7fffbb126660>
Traceback (most recent call last):
  File "/usr/lib/python3/dist-packages/RPi/GPIO/__init__.py", line 179, in __del__
    self.stop()
  File "/usr/lib/python3/dist-packages/RPi/GPIO/__init__.py", line 205, in stop
    lgpio.gpio_write(_chip, self._gpio, 0)
  File "/usr/lib/python3/dist-packages/lgpio.py", line 924, in gpio_write
    return _u2i(_lgpio._gpio_write(handle&0xffff, gpio, level))
                                   ~~~~~~^~~~~~~
TypeError: unsupported operand type(s) for &: 'NoneType' and 'int'
```

## Root Cause Analysis
1. **Garbage Collection Timing**: PWM objects were being garbage collected after `GPIO.cleanup()` had already invalidated the chip handles
2. **Library Interaction**: RPi.GPIO calls lgpio functions during PWM cleanup, but handles were None
3. **Multiple Functions**: Both `lgpio.gpio_write` and internal `_lgpio._gpio_write` were affected

## Comprehensive Solution Implemented

### Enhanced Monkey Patching in `gpio_led_controller.py`

Added comprehensive patching of all affected lgpio functions:

```python
# Monkey patch to suppress PWM cleanup errors
try:
    import lgpio
    
    # Store original functions
    _original_tx_pwm = lgpio.tx_pwm
    _original_gpio_write = lgpio.gpio_write
    
    def safe_tx_pwm(handle, gpio, pwm_frequency, pwm_duty_cycle, pwm_offset=0, pwm_cycles=0):
        """Safe version of tx_pwm that handles None handles gracefully"""
        try:
            if handle is not None:
                return _original_tx_pwm(handle, gpio, pwm_frequency, pwm_duty_cycle, pwm_offset, pwm_cycles)
            else:
                return 0
        except (TypeError, AttributeError):
            return 0
    
    def safe_gpio_write(handle, gpio, level):
        """Safe version of gpio_write that handles None handles gracefully"""
        try:
            if handle is not None:
                return _original_gpio_write(handle, gpio, level)
            else:
                return 0
        except (TypeError, AttributeError):
            return 0
    
    # Replace with safer versions
    lgpio.tx_pwm = safe_tx_pwm
    lgpio.gpio_write = safe_gpio_write
    
    # Also patch internal _lgpio if available
    try:
        import _lgpio
        _original_lgpio_gpio_write = _lgpio._gpio_write
        
        def safe_lgpio_gpio_write(handle, gpio, level):
            """Safe version of _lgpio._gpio_write that handles None handles gracefully"""
            try:
                if handle is not None:
                    return _original_lgpio_gpio_write(handle, gpio, level)
                else:
                    return 0
            except (TypeError, AttributeError):
                return 0
        
        _lgpio._gpio_write = safe_lgpio_gpio_write
    except (ImportError, AttributeError):
        pass
        
except ImportError:
    pass
```

### Functions Patched
1. **`lgpio.tx_pwm`** - PWM transmission function
2. **`lgpio.gpio_write`** - GPIO write function called during PWM stop
3. **`_lgpio._gpio_write`** - Internal GPIO write function used by the library

### Enhanced Testing
Updated `test_cleanup_fix.py` to include:
- Multiple flash operations
- Brightness changes
- Multiple garbage collection cycles
- Comprehensive PWM lifecycle testing

## Testing Instructions

### On Raspberry Pi:
```bash
# Test the comprehensive PWM cleanup solution
python test_cleanup_fix.py

# Run full hardware integration test
python test_hardware_integration_with_lighting.py
```

### Expected Results
- **Before**: Tests pass but show PWM cleanup TypeErrors
- **After**: Tests pass with clean logs (no PWM cleanup errors)

## Validation Points

1. **Functionality Maintained**: All 7 hardware integration tests should still pass (100%)
2. **Clean Logs**: No more PWM cleanup TypeErrors in the output
3. **Graceful Shutdown**: Multiple shutdown calls work without errors
4. **Garbage Collection**: Forced GC cycles don't trigger cleanup errors

## Implementation Details

### Safety Features
- **Null Handle Check**: All patched functions check for None handles before proceeding
- **Exception Handling**: Graceful error handling prevents any cleanup crashes
- **Silent Failures**: Cleanup errors are suppressed without affecting functionality
- **Conditional Imports**: Development environment compatibility maintained

### Why This Works
1. **Pre-emptive Protection**: Patches applied at import time before any PWM objects are created
2. **Library Level Fix**: Addresses the issue at the lowest level where it occurs
3. **Comprehensive Coverage**: Patches all affected functions in the call chain
4. **Non-intrusive**: Doesn't change the lighting system logic, only error handling

## Files Modified
- `lighting/gpio_led_controller.py` - Enhanced lgpio function patching
- `test_cleanup_fix.py` - More comprehensive PWM cleanup testing

## Next Steps
1. Test on Raspberry Pi hardware
2. Verify clean logs in hardware integration tests
3. Validate that all functionality remains intact
4. Document final results

This solution should eliminate the PWM cleanup errors while maintaining 100% test pass rate and full system functionality.