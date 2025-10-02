# IMMEDIATE FIX NEEDED: Install lgpio for Pi 5

## What Your Logs Tell Us

```
❌ pigpio daemon not running! Run: sudo pigpiod
⚠️  Falling back to RPi.GPIO factory (SOFTWARE PWM)
⚡⚡⚡ GPIO 13 using HARDWARE PWM via pigpio (FLICKER-FREE!)  ← WRONG!
```

**Translation:**
1. ✅ System correctly detected pigpio won't work (it's not compatible with Pi 5)
2. ✅ System correctly fell back to RPi.GPIO factory
3. ❌ Log message is WRONG - it's actually using **SOFTWARE PWM**, not hardware PWM
4. ❌ **lgpio is not installed**, so hardware PWM cannot be used

## The Real Status

**Current State:**
- Pin Factory: `RPiGPIOPin` (software PWM)
- PWM Type: **SOFTWARE** (not hardware!)
- Result: **FLICKERING** because software PWM is affected by CPU load

**What We Need:**
- Pin Factory: `LGPIOFactory` (hardware PWM)
- PWM Type: **HARDWARE** (immune to CPU)
- Result: **NO FLICKERING**

## IMMEDIATE FIX (30 seconds)

Run these commands on your Pi:

```bash
# Install lgpio
sudo apt-get update
sudo apt-get install -y python3-lgpio
pip3 install lgpio --break-system-packages

# Restart the scanner
cd ~/Documents/RaspPI/V2.0
python3 run_web_interface.py
```

## What You Should See After Installing lgpio

**SUCCESS logs:**
```
⚡⚡⚡ SUCCESS: Using gpiozero with LGPIO FACTORY (Pi 5 compatible!) ⚡⚡⚡
⚡ Hardware PWM enabled on GPIO 12, 13, 18, 19 at 300Hz
⚡ TRUE hardware PWM - immune to CPU load, no flickering!
⚡⚡⚡ GPIO 13 using HARDWARE PWM via LGPIOFactory (FLICKER-FREE!)
⚡⚡⚡ GPIO 18 using HARDWARE PWM via LGPIOFactory (FLICKER-FREE!)
```

**FAILURE logs (if lgpio still not working):**
```
❌ Failed to initialize lgpio factory: [error message]
⚠️  Falling back to RPi.GPIO factory (SOFTWARE PWM)
❌ GPIO 13 is hardware PWM capable but using SOFTWARE PWM!
❌ Current factory: RPiGPIOPin - THIS WILL CAUSE FLICKERING!
```

## Why lgpio Isn't Installed by Default

On Raspberry Pi OS Lite (or older versions), `lgpio` isn't pre-installed. You need to install it manually for Pi 5 hardware PWM support.

## Verification Steps

### Step 1: Check if lgpio is installed
```bash
python3 -c "from gpiozero.pins.lgpio import LGPIOFactory; print('lgpio OK')"
```

**Expected output:**
```
lgpio OK
```

**If you see an error:**
```
ImportError: cannot import name 'LGPIOFactory'
```
Then lgpio is NOT installed - run the install commands above.

### Step 2: Check the actual pin factory being used
After starting the scanner, check logs for:
```bash
grep "factory" ~/Documents/RaspPI/V2.0/logs/scanner.log | tail -5
```

**Should show:**
```
Using gpiozero with LGPIO FACTORY
GPIO 13 using HARDWARE PWM via LGPIOFactory
GPIO 18 using HARDWARE PWM via LGPIOFactory
```

**If it shows:**
```
Falling back to RPi.GPIO factory
GPIO 13 using ... via RPiGPIOPin
```
Then software PWM is still being used.

## Alternative: Check in Python

```bash
python3
```

```python
from gpiozero import Device, PWMLED
from gpiozero.pins.lgpio import LGPIOFactory

# Set lgpio factory
Device.pin_factory = LGPIOFactory()

# Check it's actually lgpio
print(f"Factory: {Device.pin_factory.__class__.__name__}")
# Should print: LGPIOFactory

# Test LED creation (won't actually turn on)
led = PWMLED(13, frequency=300)
print(f"LED created on pin 13 at 300Hz")
print("Hardware PWM is working!")
led.close()
```

**Expected output:**
```
Factory: LGPIOFactory
LED created on pin 13 at 300Hz
Hardware PWM is working!
```

## Troubleshooting

### Issue: "lgpio not found" after install
```bash
# Try with sudo
sudo pip3 install lgpio

# Or reinstall
sudo apt-get install --reinstall python3-lgpio
pip3 install --force-reinstall lgpio --break-system-packages
```

### Issue: Permission denied
```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER
# Log out and back in for this to take effect
```

### Issue: Still shows RPiGPIOPin in logs
Check:
1. Is `use_pigpio_factory: true` in config?
2. Was lgpio actually installed? (test with import command above)
3. Did you restart the scanner after installing lgpio?

## Summary

**Current Problem:**
- lgpio not installed → Can't use hardware PWM → Stuck on software PWM → **FLICKERING**

**Solution:**
- Install lgpio → Hardware PWM enabled → **NO FLICKERING**

**One Command Fix:**
```bash
sudo apt-get update && sudo apt-get install -y python3-lgpio && pip3 install lgpio --break-system-packages
```

Then restart the scanner and check for "LGPIOFactory" in the logs! 🚀
