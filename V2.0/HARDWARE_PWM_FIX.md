# LED Flickering - ROOT CAUSE: Software PWM Instead of Hardware PWM

## The Real Problem

After V5.1 of fixes, you identified the **root cause**: The system is using **SOFTWARE PWM** instead of **HARDWARE PWM**!

### Software PWM vs Hardware PWM

**Software PWM** (what's likely running now):
- ❌ Implemented in software by toggling GPIO on/off rapidly
- ❌ Affected by CPU load - causes flickering
- ❌ Timing depends on kernel scheduling
- ❌ ALL pins can use it, but with poor quality

**Hardware PWM** (what we need):
- ✅ Implemented in dedicated PWM hardware in the chip
- ✅ Immune to CPU load - NO flickering
- ✅ Perfect timing regardless of system load
- ✅ Only available on specific GPIO pins: **12, 13, 18, 19**

## Why Flickering Occurs with Software PWM

Software PWM toggles the GPIO pin in code:
```python
while True:
    gpio.high()
    sleep(duty_cycle)
    gpio.low()
    sleep(1 - duty_cycle)
```

**Problem**: When CPU is busy (camera capture, image processing), the sleep timing becomes irregular → visible flickering!

## Solution: Enable Hardware PWM

### Requirements Checklist

#### 1. ✅ Use Hardware PWM Capable Pins
**Your current pins** (check `scanner_config.yaml`):
```yaml
lighting:
  zones:
    inner:
      gpio_pins: [?]  # Must be 12, 13, 18, or 19
    outer:
      gpio_pins: [?]  # Must be 12, 13, 18, or 19
```

**Hardware PWM pins on Raspberry Pi 5:**
- GPIO 12 (PWM0)
- GPIO 13 (PWM1)
- GPIO 18 (PWM0)
- GPIO 19 (PWM1)

**Action**: Change your LED pins to use GPIO 13 and 18 (or 12 and 19)

#### 2. ✅ Enable pigpio Factory in Config
```yaml
lighting:
  controller_type: "gpiozero"
  use_pigpio_factory: true  # MUST be true for hardware PWM!
  pwm_frequency: 300
```

#### 3. ✅ Install and Start pigpio Daemon
```bash
# Install pigpio
sudo apt-get update
sudo apt-get install pigpio python3-pigpio

# Start pigpio daemon (required for hardware PWM!)
sudo pigpiod

# Make it start on boot
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

#### 4. ✅ Verify Installation
```bash
# Check if pigpiod is running
pgrep pigpiod

# Should return a process ID
# If nothing, run: sudo pigpiod
```

## Updated Code Changes

I've updated `gpio_led_controller.py` to:

### 1. Check pigpio Daemon Connection
```python
# Test pigpio daemon connection first
test_pi = pigpio.pi()
if not test_pi.connected:
    logger.error("❌ pigpio daemon not running! Run: sudo pigpiod")
    # Falls back to software PWM
else:
    # Use hardware PWM!
    Device.pin_factory = PiGPIOFactory()
    logger.info("⚡⚡⚡ SUCCESS: Hardware PWM enabled!")
```

### 2. Verify Hardware PWM During Initialization
```python
factory_name = Device.pin_factory.__class__.__name__
is_using_pigpio = "PiGPIO" in factory_name

if is_hardware_pwm_pin:
    if is_using_pigpio:
        logger.info(f"⚡⚡⚡ GPIO {pin} using HARDWARE PWM (FLICKER-FREE!)")
    else:
        logger.error(f"❌ GPIO {pin} using SOFTWARE PWM - WILL FLICKER!")
```

## Testing Procedure

### Step 1: Run Hardware PWM Diagnostic
```bash
cd ~/RaspPI/V2.0
bash check_hardware_pwm.sh
```

This will check:
- ✅ Is pigpiod running?
- ✅ Is config set to use_pigpio_factory: true?
- ✅ Are LED pins hardware PWM capable?
- ✅ Can system connect to pigpio daemon?

### Step 2: Fix Any Issues Found

**If pigpiod not running:**
```bash
sudo pigpiod
```

**If pins are not hardware PWM capable:**
Edit `config/scanner_config.yaml`:
```yaml
lighting:
  zones:
    inner:
      gpio_pins: [13]  # Change to 13 (hardware PWM)
    outer:
      gpio_pins: [18]  # Change to 18 (hardware PWM)
```

**If use_pigpio_factory is false:**
Edit `config/scanner_config.yaml`:
```yaml
lighting:
  use_pigpio_factory: true  # Enable hardware PWM
```

### Step 3: Restart Scanner and Check Logs
```bash
python3 run_web_interface.py
```

**Look for in logs:**
```
⚡⚡⚡ SUCCESS: Using gpiozero with PIGPIO FACTORY ⚡⚡⚡
⚡ Hardware PWM enabled on GPIO 12, 13, 18, 19 at 300Hz
⚡⚡⚡ GPIO 13 using HARDWARE PWM (FLICKER-FREE!)
⚡⚡⚡ GPIO 18 using HARDWARE PWM (FLICKER-FREE!)
```

**If you see instead:**
```
❌ GPIO 13 is hardware PWM capable but using SOFTWARE PWM!
❌ Current factory: RPiGPIOPin - THIS WILL CAUSE FLICKERING!
```
Then pigpio factory is NOT active - check daemon is running.

## Why This Will Fix Flickering

### Before (Software PWM)
```
CPU Usage:  ████████████████ 80% (camera capture busy)
PWM Timing: ON...OFF.....ON....OFF... (irregular)
LED Output: ▓▓░░▓░░▓▓░░ (visible flickering)
```

### After (Hardware PWM)
```
CPU Usage:  ████████████████ 80% (doesn't matter!)
PWM Timing: ON.OFF.ON.OFF.ON.OFF (perfect 300Hz)
LED Output: ▓▓▓▓▓▓▓▓▓▓▓▓ (smooth, no flicker)
```

Hardware PWM runs **independently of CPU** - it doesn't care if the CPU is busy!

## Recommended Pin Configuration

**Optimal setup for dual LED zones:**
```yaml
lighting:
  controller_type: "gpiozero"
  use_pigpio_factory: true
  pwm_frequency: 300  # Or try 1000 for some LED drivers
  
  zones:
    inner:
      gpio_pins: [13]  # PWM1 channel
      led_type: "white"
      max_brightness: 1.0
      
    outer:
      gpio_pins: [18]  # PWM0 channel
      led_type: "white"
      max_brightness: 1.0
```

**Why GPIO 13 and 18?**
- Both support hardware PWM
- On different PWM channels (PWM0 and PWM1)
- Common and easy to wire

## Troubleshooting

### Issue: "pigpio daemon not running"
**Solution:**
```bash
sudo pigpiod
# Make permanent:
sudo systemctl enable pigpiod
```

### Issue: "Import error: gpiozero.pins.pigpio"
**Solution:**
```bash
sudo apt-get install python3-pigpio
pip3 install pigpio
```

### Issue: Still flickering with hardware PWM
**Try these:**
1. **Different PWM frequency**: Edit config, try 500Hz or 1000Hz
2. **Check LED driver specs**: Some drivers require specific PWM frequency
3. **Power supply**: Ensure stable power (separate supply for LEDs if possible)
4. **Ground loops**: Check for ground connection issues

### Issue: Pins not available (in use)
**Check what's using them:**
```bash
gpio readall  # Shows all GPIO states
```

## Summary

**The flickering is caused by SOFTWARE PWM being used instead of HARDWARE PWM.**

**To fix:**
1. ✅ Change LED pins to GPIO 13 and 18 (hardware PWM capable)
2. ✅ Set `use_pigpio_factory: true` in config
3. ✅ Start pigpio daemon: `sudo pigpiod`
4. ✅ Restart scanner system
5. ✅ Verify "HARDWARE PWM" in logs

**Result**: Flicker-free operation regardless of CPU load! 🎉
