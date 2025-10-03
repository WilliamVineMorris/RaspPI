# Hardware PWM Implementation - Complete Solution

## Problem Summary

✅ **Direct GPIO control works**: GPIO 18 HIGH=ON, LOW=OFF  
❌ **Hardware PWM doesn't work**: PWM signals generated but LEDs don't light up  

## Root Cause

Your `/boot/firmware/config.txt` has **incorrect alternate function values**:

```bash
# WRONG (current):
dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4

# CORRECT (needed):
dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5
```

**Why this matters**:
- `func=2` and `func=4` are **wrong alternate functions** for Pi 5
- GPIO pins stay in GPIO mode, can't access hardware PWM peripheral
- PWM chip generates signals, but they don't route to GPIO pins
- Result: Direct GPIO works, hardware PWM doesn't

**Correct values**:
- `func=5` = **ALT5** mode = Connects GPIO to PWM0 peripheral
- GPIO 18 → PWM0 Channel 0 (via ALT5)
- GPIO 13 → PWM0 Channel 1 (via ALT5)

## Quick Fix (3 Steps)

### Step 1: Run Automated Fix Script

```bash
cd ~/RaspPI/V2.0
chmod +x fix_hardware_pwm.sh
./fix_hardware_pwm.sh
```

This will:
- ✅ Backup your current config.txt
- ✅ Fix the dtoverlay line
- ✅ Remove GPIO conflicts
- ✅ Offer to reboot

### Step 2: Reboot

```bash
sudo reboot
```

### Step 3: Test Hardware PWM

After reboot:

```bash
# Quick manual test
echo 0 | sudo tee /sys/class/pwm/pwmchip0/export
echo 2500000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/period
echo 1250000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/duty_cycle
echo 1 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable

# LED on GPIO 18 should light up at 50%!
```

If LED lights up: **✅ Hardware PWM is working!**

Clean up:
```bash
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable
echo 0 | sudo tee /sys/class/pwm/pwmchip0/unexport
```

### Step 4: Start Scanner System

```bash
cd ~/RaspPI/V2.0
python run_web_interface.py
```

Expected logs:
```
✅ Using rpi-hardware-pwm library (HARDWARE PWM via dtoverlay)
⚡⚡⚡ GPIO 18 -> PWM CHIP 0 CHANNEL 0 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 18 (chip 0, channel 0) at 400Hz
```

Test from dashboard:
- Open: `http://3dscanner:5000`
- Click: "Test Lighting" button
- **LEDs should flash at 30%!**

## Manual Fix (If Script Fails)

```bash
# 1. Backup config
sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.backup

# 2. Edit config
sudo nano /boot/firmware/config.txt

# 3. Find this line:
#    dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4

# 4. Change to:
#    dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5

# 5. Save (Ctrl+O, Enter, Ctrl+X)

# 6. Reboot
sudo reboot
```

## Why This Works

### Pi 5 GPIO Alternate Functions

Each GPIO pin has multiple alternate functions (ALT0-ALT5):

**GPIO 18 Alternate Functions:**
- Standard GPIO: Input/Output control
- ALT0: PCM_CLK
- ALT1: SDA6
- ALT2: SPI6_CE_N
- ALT3: SPI1_CE_N
- ALT4: PWM1_0 (PWM1 peripheral, channel 0)
- **ALT5: PWM0_0** (PWM0 peripheral, channel 0) ← **We need this!**

**GPIO 13 Alternate Functions:**
- Standard GPIO: Input/Output control
- ALT0: PWM0_1 (PWM0 peripheral, channel 1) ← Alternative
- ALT1: SCL5
- ALT2: SPI5_MISO
- ALT3: SPI1_MISO
- ALT4: PWM1_1 (PWM1 peripheral, channel 1)
- **ALT5: PWM0_1** (PWM0 peripheral, channel 1) ← **We need this!**

Setting `func=5` activates **ALT5**, which connects both GPIOs to the **PWM0 peripheral**.

## Verification

### Check Boot Config
```bash
grep "dtoverlay=pwm" /boot/firmware/config.txt

# Should show:
# dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5
```

### Check PWM Chips
```bash
ls -la /sys/class/pwm/

# Should show:
# pwmchip0 -> ../../devices/platform/soc/1f00098000.pwm/pwm/pwmchip0
```

### Check PWM Status
```bash
sudo cat /sys/kernel/debug/pwm

# During operation should show:
# pwm-0   (sysfs): requested enabled period: 2500000 ns duty: XXXXX ns polarity: normal
```

### Check Pinmux (Advanced)
```bash
./check_pwm_pinmux.sh

# Should show GPIO 18 and 13 assigned to PWM function
```

## Troubleshooting

### If Manual Test Still Fails

Try PWM1 peripheral (ALT0) instead:

```bash
sudo nano /boot/firmware/config.txt

# Change to:
dtoverlay=pwm-2chan,pin=18,func=4,pin2=13,func2=4

# Reboot and test again
sudo reboot
```

### If Both Channels Conflict

Use single-channel overlays:

```bash
sudo nano /boot/firmware/config.txt

# Remove pwm-2chan line, add:
dtoverlay=pwm,pin=18,func=5
dtoverlay=pwm,pin=13,func=5

# Save, reboot, test
```

### If Permission Errors

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Create udev rule
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

## Expected Final State

**Boot configuration:**
```
dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5
```

**Manual test result:**
- ✅ LED on GPIO 18 lights up at 50% brightness

**Scanner system logs:**
```
✅ Using rpi-hardware-pwm library (HARDWARE PWM via dtoverlay)
⚡⚡⚡ GPIO 18 -> PWM CHIP 0 CHANNEL 0 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 18 (chip 0, channel 0) at 400Hz
⚡⚡⚡ GPIO 13 -> PWM CHIP 0 CHANNEL 1 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 13 (chip 0, channel 1) at 400Hz
```

**Dashboard test:**
- ✅ "Test Lighting" button lights up LEDs at 30%
- ✅ Smooth brightness transitions
- ✅ No flickering under CPU load
- ✅ Perfect camera-flash synchronization

## Benefits of True Hardware PWM

- ✅ **CPU-independent timing** - Dedicated hardware timer
- ✅ **Zero jitter** - Microsecond precision
- ✅ **No flickering** - Immune to system load
- ✅ **Reliable sync** - Perfect for camera flash timing
- ✅ **Low CPU usage** - No software PWM overhead

## Summary

**The fix is simple**: Change `func=2,pin2=13,func2=4` to `func=5,pin2=13,func2=5` in `/boot/firmware/config.txt`.

This one-line change properly routes hardware PWM signals to your GPIO pins!

Run the automated script or make the change manually, reboot, and enjoy flicker-free hardware PWM! 🎉
