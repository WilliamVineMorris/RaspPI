# LED Cleanup on Script Exit - Implementation Guide

## Problem
When the scanner script exits (normally or via Ctrl+C), the PWM signals can remain HIGH, leaving LEDs stuck ON. This wastes power and can potentially damage LEDs over time.

## Solution
Automatic cleanup handlers that turn off all LEDs when the script exits, ensuring safe shutdown.

## Implementation

### 1. Cleanup Handler Registration (`__init__`)
```python
# Register cleanup handlers to turn off LEDs on exit
atexit.register(self._cleanup_on_exit)
signal.signal(signal.SIGTERM, self._signal_handler)
signal.signal(signal.SIGINT, self._signal_handler)
```

**Handlers registered:**
- `atexit`: Normal script exit (e.g., `sys.exit()`, end of `main()`)
- `SIGTERM`: Termination signal (e.g., `kill <pid>`)
- `SIGINT`: Interrupt signal (e.g., Ctrl+C)

### 2. Cleanup Method (`_cleanup_on_exit`)
Comprehensive cleanup that handles all GPIO library types:

**Hardware PWM:**
```python
for zone_id, pwm_list in self.hardware_pwm_objects.items():
    for pwm in pwm_list:
        pwm.change_duty_cycle(0)  # Set to 0% before stopping
        pwm.stop()
```

**gpiozero:**
```python
for pwm_obj in pwm_list:
    if pwm_obj['type'] == 'gpiozero':
        pwm_obj['led'].off()
        pwm_obj['led'].close()
```

**pigpio:**
```python
for pin in zone_config.gpio_pins:
    self.pi.set_PWM_dutycycle(pin, 0)
self.pi.stop()
```

**RPi.GPIO:**
```python
GPIO.cleanup()
```

### 3. Signal Handler (`_signal_handler`)
Handles Ctrl+C and termination signals:
```python
def _signal_handler(self, signum, frame):
    logger.info(f"🛡️  Received signal {signum} - cleaning up...")
    self._cleanup_on_exit()
    sys.exit(0)
```

## Expected Behavior

### Normal Exit
```bash
$ python run_web_interface.py
# ... script runs ...
# User exits with Ctrl+C

🛡️  Received signal 2 - cleaning up...
🛡️  Cleanup: Turning off all LEDs before exit...
✅ Cleanup complete - all LEDs turned off
```

### Crash/Exception
```bash
$ python run_web_interface.py
# ... script runs ...
# Exception occurs

🛡️  Cleanup: Turning off all LEDs before exit...
✅ Cleanup complete - all LEDs turned off
```

### Kill Signal
```bash
$ kill <pid>
# OR
$ sudo systemctl stop scanner.service

🛡️  Received signal 15 - cleaning up...
🛡️  Cleanup: Turning off all LEDs before exit...
✅ Cleanup complete - all LEDs turned off
```

## Testing

### Test Script: `test_led_cleanup.py`
Automated test that:
1. Initializes LED controller
2. Turns on LEDs at 50% brightness
3. Waits 5 seconds
4. Exits (cleanup should turn off LEDs)

**Run test:**
```bash
cd ~/RaspPI/V2.0
python test_led_cleanup.py
```

**Expected output:**
```
LED Cleanup Test
================

1. Initializing LED controller...
   ✅ Controller initialized

2. Turning on LEDs at 50% brightness...
   💡 Zone 'inner' ON at 50%
   💡 Zone 'outer' ON at 50%

3. LEDs are ON - waiting 5 seconds...
   Exiting in 1...

4. Exiting script now...
   🛡️  Cleanup handlers should turn off LEDs automatically

🛡️  Cleanup: Turning off all LEDs before exit...
💡 LED UPDATE: Zone 'inner' 50.0% → 0.0% (state: OFF)
💡 LED UPDATE: Zone 'outer' 50.0% → 0.0% (state: OFF)
✅ Cleanup complete - all LEDs turned off

🔍 Check if LEDs are OFF now!
```

### Manual Test
1. Start web interface:
   ```bash
   python run_web_interface.py
   ```

2. Click "Test Lighting" to turn on LEDs

3. Press Ctrl+C to exit

4. **Verify:** LEDs should turn OFF immediately

5. Check hardware:
   ```bash
   sudo cat /sys/kernel/debug/pwm
   # All duty cycles should be 0
   ```

## Safety Features

### Idempotent Cleanup
```python
if self._shutdown_complete:
    return  # Already cleaned up
```
Prevents double-cleanup if multiple signals are received.

### Error Isolation
Each zone cleanup is wrapped in try/except to ensure one failure doesn't prevent others:
```python
for zone_id in self.zone_configs:
    try:
        self._set_brightness_direct(zone_id, 0.0)
    except Exception as e:
        logger.error(f"Failed to turn off zone '{zone_id}': {e}")
```

### Library-Specific Cleanup
Handles all GPIO library types correctly:
- **Hardware PWM**: Stops PWM channels via `pwm.stop()`
- **gpiozero**: Closes LED objects with `led.close()`
- **pigpio**: Stops daemon connection with `pi.stop()`
- **RPi.GPIO**: Cleans up GPIO states with `GPIO.cleanup()`

## Systemd Integration

For production deployments, ensure cleanup runs on service stop:

**`/etc/systemd/system/scanner.service`:**
```ini
[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/user/RaspPI/V2.0/run_web_interface.py
KillSignal=SIGTERM
TimeoutStopSec=10s
```

**Behavior:**
1. `systemctl stop scanner` sends SIGTERM
2. Signal handler runs cleanup
3. Script exits cleanly within 10 seconds
4. LEDs turn off automatically

## Troubleshooting

### LEDs Still ON After Exit
**Check if cleanup ran:**
```bash
# Look for cleanup logs
tail -n 20 /var/log/scanner.log | grep -i cleanup
```

**Expected:**
```
🛡️  Cleanup: Turning off all LEDs before exit...
✅ Cleanup complete - all LEDs turned off
```

**If cleanup didn't run:**
- Signal handlers may not be registered (check `__init__` logs)
- Process may have been killed with `kill -9` (SIGKILL - can't be caught)
- Cleanup may have encountered an error (check error logs)

### Manual LED Shutdown
If LEDs are stuck ON, manually turn them off:

**Hardware PWM:**
```bash
# Turn off GPIO 13 (channel 1)
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm1/duty_cycle

# Turn off GPIO 18 (channel 2)
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm2/duty_cycle
```

**Direct GPIO:**
```bash
# Turn off GPIO 13
sudo pinctrl set 13 op dl

# Turn off GPIO 18
sudo pinctrl set 18 op dl
```

### Cleanup Script
Create emergency cleanup script:

**`emergency_led_off.sh`:**
```bash
#!/bin/bash
echo "🚨 Emergency LED shutdown..."

# Hardware PWM cleanup
for pwm in /sys/class/pwm/pwmchip0/pwm*; do
    if [ -d "$pwm" ]; then
        echo 0 | sudo tee $pwm/duty_cycle > /dev/null
    fi
done

# Direct GPIO cleanup
for pin in 13 18; do
    sudo pinctrl set $pin op dl
done

echo "✅ All LEDs should be OFF"
```

## Benefits

✅ **Safety**: LEDs always turn off when script exits
✅ **Power saving**: No wasted power from stuck-ON LEDs  
✅ **Hardware protection**: Prevents prolonged LED operation
✅ **Reliability**: Works with all exit scenarios (normal, Ctrl+C, kill signal)
✅ **Cross-library**: Handles hardware PWM, gpiozero, pigpio, RPi.GPIO
✅ **Idempotent**: Safe to call multiple times
✅ **Error-resistant**: Isolated error handling per zone

## Summary

The LED cleanup system ensures that **no matter how the script exits**, all LEDs are turned off safely:

1. **atexit handler**: Normal script completion
2. **SIGTERM handler**: Service stop, kill command
3. **SIGINT handler**: Ctrl+C, keyboard interrupt
4. **Comprehensive cleanup**: Turns off all PWM channels, closes GPIO objects
5. **Error isolation**: One zone failure doesn't prevent others from cleaning up
6. **Library-aware**: Correct cleanup for hardware PWM, gpiozero, pigpio, RPi.GPIO

**Test it now:** Run `python test_led_cleanup.py` to verify cleanup works! 🛡️✅
