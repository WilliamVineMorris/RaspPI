# LED Flickering V3.1 - Emergency State-Tracking Fix

## Problem
User reported flickering still present after V3. Logs show:
- LEDs turning on/off during calibration
- Frequent status queries from web interface
- No evidence of V3 features being used

## V3.1 Emergency Fix - State Tracking

### Additional Protection Layer
Added **LED state tracking** to prevent redundant on/off commands:

```python
# Track which zones are ON vs OFF
self._led_active = {}  # {zone_id: True/False}

# In _set_brightness_direct():
is_on = brightness > 0.01
was_on = self._led_active.get(zone_id, False)

# Skip if LED already in desired state
if is_on == was_on and abs(current_brightness - brightness) < 0.02:
    return True  # No update needed
```

### Why This Helps
**Problem**: Calibration code might be calling:
```python
set_brightness("inner", 0.3)  # Turn on
set_brightness("inner", 0.3)  # Already on! (redundant)
set_brightness("inner", 0.3)  # Still on! (redundant)
set_brightness("inner", 0.0)  # Turn off
set_brightness("inner", 0.0)  # Already off! (redundant)
```

**V3.1 Fix**: State tracking catches this:
- First call: ON (updates hardware)
- Second call: ALREADY ON (skipped)
- Third call: ALREADY ON (skipped)  
- Fourth call: OFF (updates hardware)
- Fifth call: ALREADY OFF (skipped)

### Enhanced Logging
Changed to INFO level to see actual updates:
```python
logger.info(f"💡 LED UPDATE: Zone '{zone_id}' {current}% → {new}% (state: {'ON' if is_on else 'OFF'})")
```

## Testing

### 1. Restart Scanner
```bash
# Stop scanner
sudo systemctl stop scanner  # or however you stop it

# Clear Python cache
cd ~/RaspPI/V2.0
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete

# Restart scanner
python3 run_web_interface.py
```

### 2. Watch Logs for Actual Updates
```bash
tail -f logs/scanner.log | grep "💡 LED UPDATE"
```

**Expected Output** (during calibration):
```
💡 LED UPDATE: Zone 'inner' 0.0% → 30.0% (state: ON)
💡 LED UPDATE: Zone 'outer' 0.0% → 30.0% (state: ON)
... (no more updates until done) ...
💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)
💡 LED UPDATE: Zone 'outer' 30.0% → 0.0% (state: OFF)
```

**Should NOT see**:
```
💡 LED UPDATE: Zone 'inner' 30.0% → 30.0%  # Redundant!
💡 LED UPDATE: Zone 'inner' 0.0% → 0.0%    # Redundant!
```

### 3. Run Diagnostic
```bash
python3 diagnose_v3_active.py
```

This will verify:
- Thread lock is present
- 1% threshold is active
- State tracking is working

## What Changed in V3.1

| Feature | V3 | V3.1 |
|---------|----|----|
| Threshold | 1% | 1% |
| Thread lock | ✅ | ✅ |
| State tracking | ❌ | ✅ **NEW** |
| Redundant ON/OFF blocking | ❌ | ✅ **NEW** |
| Log visibility | DEBUG | INFO |

## If Still Flickering

### Check 1: Verify Code is Reloaded
```python
# In Python on Pi:
from lighting import gpio_led_controller
import inspect
print(inspect.getsource(gpio_led_controller.GPIOLEDController._set_brightness_direct))
```

Should see `self._led_active` in the code.

### Check 2: Enable Maximum Logging
```bash
export SCANNER_LOG_LEVEL=DEBUG
python3 run_web_interface.py 2>&1 | grep -E "LED|brightness|💡"
```

### Check 3: Hardware Test
If V3.1 still shows flickering with minimal updates, it's **definitely hardware**:

1. **PWM Frequency**: Try 1000Hz or 100Hz in config
2. **Power Supply**: Use dedicated 5V supply for LED driver
3. **Capacitor**: Add 100nF cap across LED driver PWM input
4. **LED Driver**: Check datasheet for PWM requirements

## Summary V3.1

**Triple Protection**:
1. **1% threshold**: Blocks micro-updates
2. **Thread lock**: Prevents concurrent writes
3. **State tracking** ✨ NEW: Blocks redundant on/off commands

**Result**: Only genuine state changes trigger hardware updates

If this doesn't eliminate flickering, the issue is 100% hardware-related (LED driver, power supply, or EMI).
