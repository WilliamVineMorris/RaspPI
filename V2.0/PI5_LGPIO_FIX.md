# Raspberry Pi 5 Hardware PWM Fix

## THE PROBLEM: pigpio Doesn't Support Pi 5!

Your error log shows:
```
pigpiod: unknown rev code (c04170)
Sorry, this system does not appear to be a raspberry pi.
```

**pigpio is NOT compatible with Raspberry Pi 5!** It doesn't recognize the Pi 5 hardware revision.

## THE SOLUTION: Use lgpio Instead

The modern replacement for pigpio on Pi 5 is **lgpio**, which is built into gpiozero and works perfectly!

### Step 1: Install lgpio (if not already installed)

```bash
sudo apt-get update
sudo apt-get install python3-lgpio
pip3 install lgpio --break-system-packages
```

### Step 2: Verify Your Config

Your `config/scanner_config.yaml` should have:
```yaml
lighting:
  controller_type: "gpiozero"
  use_pigpio_factory: true  # On Pi 5, this will use lgpio automatically!
  pwm_frequency: 300
  
  zones:
    inner:
      gpio_pins: [13]  # Hardware PWM capable
    outer:
      gpio_pins: [18]  # Hardware PWM capable
```

**Note**: The setting is still called `use_pigpio_factory` for backward compatibility, but on Pi 5 it will automatically use lgpio!

### Step 3: Test the Scanner

```bash
cd ~/Documents/RaspPI/V2.0
python3 run_web_interface.py
```

Look for these success messages in the logs:
```
⚡⚡⚡ SUCCESS: Using gpiozero with LGPIO FACTORY (Pi 5 compatible!) ⚡⚡⚡
⚡ Hardware PWM enabled on GPIO 12, 13, 18, 19 at 300Hz
⚡⚡⚡ GPIO 13 using HARDWARE PWM via LGPIOFactory (FLICKER-FREE!)
⚡⚡⚡ GPIO 18 using HARDWARE PWM via LGPIOFactory (FLICKER-FREE!)
```

### Step 4: Verify No Flickering

The LEDs should now be **completely flicker-free** because:
- ✅ lgpio provides true hardware PWM on Pi 5
- ✅ No daemon required (unlike pigpio)
- ✅ Immune to CPU load
- ✅ Perfect 300Hz PWM signal

## Why This Works

### Old Way (pigpio - doesn't work on Pi 5):
```
pigpio → pigpiod daemon → hardware PWM
         ❌ daemon won't start on Pi 5!
```

### New Way (lgpio - works on Pi 5):
```
lgpio → direct hardware PWM
        ✅ works perfectly on Pi 5!
```

## Comparison

| Feature | pigpio | lgpio |
|---------|--------|-------|
| Pi 5 Support | ❌ NO | ✅ YES |
| Requires Daemon | ✅ pigpiod | ❌ No daemon |
| Hardware PWM | ✅ Yes | ✅ Yes |
| Setup Complexity | High | Low |

## Troubleshooting

### "lgpio not found" error
```bash
sudo apt-get install python3-lgpio
pip3 install lgpio --break-system-packages
```

### Still using SOFTWARE PWM?
Check logs - should say "LGPIOFactory" not "RPiGPIOPin"

If it says "RPiGPIOPin", verify:
1. `use_pigpio_factory: true` in config
2. lgpio is installed
3. GPIO pins are 12, 13, 18, or 19

### Still flickering?
If you see "HARDWARE PWM via LGPIOFactory" in logs but still have flicker:
1. Try different PWM frequency (500Hz or 1000Hz)
2. Check power supply stability
3. Verify no other processes using GPIO

## Summary

- ✅ Updated code to use lgpio instead of pigpio for Pi 5
- ✅ lgpio works out-of-the-box, no daemon needed
- ✅ Provides true hardware PWM on GPIO 12, 13, 18, 19
- ✅ Should eliminate ALL flickering on Pi 5

**Install lgpio and run the scanner - flickering should be completely gone!** 🎉
