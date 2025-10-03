# Complete Hardware PWM Implementation Guide for Raspberry Pi 5

## Problem Analysis

You've confirmed:
- ✅ Direct GPIO control works (HIGH=ON, LOW=OFF)
- ❌ Hardware PWM doesn't light LEDs despite PWM signals being generated

**Root cause**: GPIO pins need to be configured in **PWM alternate function mode**, not standard GPIO mode.

## Hardware PWM Architecture on Pi 5

The Raspberry Pi 5 has two PWM peripherals:

### PWM0 Peripheral (at 0x1f00098000)
- **Channel 0**: Can use GPIO 12 (ALT0) or GPIO 18 (ALT5)
- **Channel 1**: Can use GPIO 13 (ALT0) or GPIO 19 (ALT5)

### PWM1 Peripheral (at 0x1f0009c000)  
- **Channel 0**: GPIO 12 (ALT5) or GPIO 18 (ALT0)
- **Channel 1**: GPIO 13 (ALT5) or GPIO 19 (ALT0)

## Current Issue

Your dtoverlay configuration is:
```
dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4
```

**Problem**: `func=2` and `func=4` are **incorrect alternate function values** for Pi 5!

The correct values are:
- GPIO 18: ALT5 = **func=5** (for PWM0 channel 0)
- GPIO 13: ALT5 = **func=5** (for PWM0 channel 1)

OR:
- GPIO 18: ALT0 = **func=4** (for PWM1 channel 0) 
- GPIO 13: ALT0 = **func=4** (for PWM1 channel 1)

## Complete Fix - Step by Step

### Step 1: Correct Boot Configuration

Edit `/boot/firmware/config.txt`:

```bash
sudo nano /boot/firmware/config.txt
```

**Find this line:**
```
dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4
```

**Replace with:**
```
dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5
```

**Explanation**: `func=5` sets GPIO to ALT5 mode, which connects to PWM0 peripheral.

**Save** (Ctrl+O, Enter, Ctrl+X)

### Step 2: Verify No GPIO Conflicts

Make sure no other software is claiming GPIO 18/13:

```bash
# Check if GPIOs are exported
ls /sys/class/gpio/

# If you see gpio18 or gpio13, unexport them:
echo 18 | sudo tee /sys/class/gpio/unexport 2>/dev/null
echo 13 | sudo tee /sys/class/gpio/unexport 2>/dev/null
```

### Step 3: Reboot to Apply Changes

```bash
sudo reboot
```

### Step 4: Verify Hardware PWM After Reboot

```bash
# Check PWM chips exist
ls -la /sys/class/pwm/

# Should show:
# pwmchip0 -> ../../devices/platform/soc/1f00098000.pwm/pwm/pwmchip0
# pwmchip1 -> ../../devices/platform/soc/1f0009c000.pwm/pwm/pwmchip1

# Check PWM status
sudo cat /sys/kernel/debug/pwm

# Channels should be available (not in use by gpio)
```

### Step 5: Test Hardware PWM Manually

```bash
# Export PWM channel 0 (GPIO 18)
echo 0 | sudo tee /sys/class/pwm/pwmchip0/export
sleep 0.5

# Set period (400Hz = 2,500,000 ns)
echo 2500000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/period

# Set duty cycle (50% = 1,250,000 ns)
echo 1250000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/duty_cycle

# Enable PWM
echo 1 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable

# LED on GPIO 18 should light up at 50% brightness!
```

**CRITICAL TEST**: Does the LED light up now?

- ✅ **YES** → Hardware PWM is working! Proceed to Step 6
- ❌ **NO** → GPIO pinmux still wrong, see troubleshooting below

### Step 6: Clean Up Test

```bash
# Turn off and unexport
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable
echo 0 | sudo tee /sys/class/pwm/pwmchip0/unexport
```

### Step 7: Update Scanner Configuration

Your `scanner_config.yaml` should already be correct:

```yaml
lighting:
  controller_type: "gpiozero"       # Keep this
  use_pigpio_factory: true          # Keep this (enables hardware PWM detection)
  pwm_frequency: 400
  
  flash_mode: true
  idle_brightness: 0.10
  calibration_brightness: 0.20
  capture_brightness: 0.30
  
  zones:
    inner:
      gpio_pins: [13]      # Hardware PWM channel 1
    outer:
      gpio_pins: [18]      # Hardware PWM channel 0
```

### Step 8: Restart System and Test

```bash
cd ~/RaspPI/V2.0
python run_web_interface.py
```

**Expected logs:**
```
✅ Using rpi-hardware-pwm library (HARDWARE PWM via dtoverlay)
⚡⚡⚡ GPIO 18 -> PWM CHIP 0 CHANNEL 0 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 18 (chip 0, channel 0) at 400Hz
⚡⚡⚡ GPIO 13 -> PWM CHIP 0 CHANNEL 1 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 13 (chip 0, channel 1) at 400Hz
```

**Test from dashboard:**
- Open: `http://3dscanner:5000`
- Click: "Test Lighting"
- **LEDs should flash at 30%!**

## Troubleshooting

### If LEDs Still Don't Work After func=5 Change

#### Option A: Try PWM1 Peripheral (ALT0)

Edit `/boot/firmware/config.txt`:
```
dtoverlay=pwm-2chan,pin=18,func=4,pin2=13,func2=4
```

This uses PWM1 instead of PWM0. Reboot and test.

#### Option B: Use Single-Channel Overlays

Instead of `pwm-2chan`, use individual overlays:

```
# Remove pwm-2chan line, add:
dtoverlay=pwm,pin=18,func=5
dtoverlay=pwm,pin=13,func=5
```

#### Option C: Check Pinctrl Assignment

Run diagnostic:
```bash
chmod +x check_pwm_pinmux.sh
./check_pwm_pinmux.sh
```

This shows if pins are correctly assigned to PWM function.

### If "Permission Denied" on sysfs

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Create udev rule for PWM access
sudo nano /etc/udev/rules.d/99-pwm.rules
```

Add:
```
SUBSYSTEM=="pwm", ACTION=="add", RUN+="/bin/chgrp -R gpio /sys%p", RUN+="/bin/chmod -R g+w /sys%p"
```

```bash
sudo udevadm control --reload-rules
sudo reboot
```

### If rpi-hardware-pwm Library Conflicts

The library might interfere with dtoverlay. Try using direct sysfs control:

```python
# Instead of HardwarePWM library, control sysfs directly
# This is already implemented in the code as fallback
```

## Alternative: Pigpio Daemon (Legacy Method)

If dtoverlay approach fails completely, use pigpio daemon:

```bash
# Install pigpio
sudo apt install pigpio python3-pigpio

# Start daemon
sudo systemctl enable pigpiod
sudo systemctl start pigpiod

# Update config:
lighting:
  controller_type: "pigpio"  # Change from gpiozero
  # ... rest unchanged
```

**Note**: Pigpio uses DMA for hardware PWM timing, independent of dtoverlay.

## Verification Checklist

After applying the fix:

- [ ] `/boot/firmware/config.txt` has correct `func=5` values
- [ ] System rebooted
- [ ] Manual PWM test lights up LED
- [ ] `sudo cat /sys/kernel/debug/pwm` shows active channels
- [ ] Web interface logs show "TRUE HARDWARE PWM"
- [ ] "Test Lighting" button lights up LEDs
- [ ] Scan calibration shows visible LED brightness

## Expected Final State

**Boot config:**
```
dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5
```

**PWM debug output:**
```
0: platform/1f00098000.pwm, 4 PWM devices
 pwm-0   (sysfs): requested enabled period: 2500000 ns duty: 500000 ns polarity: normal
 pwm-1   (sysfs): requested enabled period: 2500000 ns duty: 500000 ns polarity: normal
```

**LED behavior:**
- ✅ Lights up during manual sysfs test
- ✅ Lights up during software control
- ✅ Smooth brightness transitions
- ✅ No flickering under CPU load

## Summary

The fix is simple: **Change `func=2` and `func2=4` to `func=5` and `func2=5`** in the dtoverlay configuration. This properly routes the hardware PWM signals to GPIO 18 and 13.

After this change and a reboot, hardware PWM will work perfectly with your existing code!
