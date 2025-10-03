# LED Hardware Debugging Guide

## Current Status

✅ **Hardware PWM is WORKING!** The PWM debug output shows:
```
pwm-0   (sysfs): requested enabled period: 2500000 ns duty: 500000 ns polarity: normal
pwm-1   (sysfs): requested enabled period: 2500000 ns duty: 500000 ns polarity: normal
```

This confirms:
- ✅ PWM channels are active (`requested enabled`)
- ✅ Correct frequency: 400Hz (1/2500000ns = 400Hz)
- ✅ Correct duty cycle: 20% (500000/2500000 = 20%)
- ✅ Software is controlling hardware PWM correctly

## Problem: LEDs Not Lighting Up

The PWM signals are being generated, but LEDs don't light up. This is a **hardware polarity/wiring issue**.

## Root Causes (Most Likely)

### 1. **Inverted Polarity Needed**
Your LED driver circuit likely uses:
- **N-channel MOSFET** (turns ON when GPIO is LOW)
- **Inverted transistor driver** (common in LED strips)
- **Active-low LED circuit**

With normal polarity:
- HIGH duty cycle = GPIO HIGH = MOSFET OFF = LED OFF ❌
- Need: **INVERTED polarity** so HIGH duty cycle = GPIO LOW = MOSFET ON = LED ON ✅

### 2. **Hardware Wiring**
Check your LED connections:
```
Option A (Common for N-channel MOSFET):
   3.3V ──→ LED+ ──→ LED- ──→ MOSFET Drain
                               MOSFET Source ──→ GND
                               MOSFET Gate ──→ GPIO 13/18
   
   Needs: INVERTED polarity (GPIO LOW = MOSFET ON)

Option B (Direct drive - less common):
   GPIO 13/18 ──→ LED+ ──→ LED- ──→ GND
   
   Needs: NORMAL polarity (GPIO HIGH = LED ON)
```

## Testing Steps

### Step 1: Run Hardware Debug Tool

This will test both polarity modes and direct GPIO control:

```bash
cd ~/RaspPI/V2.0

# Run debug tool (requires sudo for PWM access)
sudo python debug_led_hardware.py
```

**The tool will**:
1. Show current PWM status
2. Test NORMAL polarity at 50% brightness
3. Test INVERTED polarity at 50% brightness
4. Test direct GPIO HIGH/LOW states

**Watch your LEDs** and answer the prompts!

### Step 2: Update Configuration Based on Results

#### If LEDs Light Up with **INVERTED** Polarity

Edit `config/scanner_config.yaml`:

```yaml
lighting:
  controller_type: "gpiozero"
  use_pigpio_factory: true
  pwm_frequency: 400
  pwm_polarity_inverted: true    # ← ADD THIS LINE
  
  flash_mode: true
  # ... rest of config
```

Then restart:
```bash
python run_web_interface.py
```

#### If LEDs Light Up with **NORMAL** Polarity

Your config is already correct! The issue may be:
- Insufficient brightness level (try 100% to test)
- LED power supply issue
- MOSFET not properly biased

#### If LEDs Light Up with **GPIO LOW** (Direct Test)

This confirms inverted driver. Set `pwm_polarity_inverted: true` in config.

#### If LEDs Light Up with **GPIO HIGH** (Direct Test)

Normal polarity is correct. Check:
- PWM duty cycle values in logs
- LED power supply voltage
- Current limiting resistors

### Step 3: Manual PWM Test (Alternative)

If the debug tool doesn't work, test manually:

```bash
# Test INVERTED polarity on GPIO 18
cd /sys/class/pwm/pwmchip0/pwm0

# Set inverted polarity
echo "inversed" | sudo tee polarity

# Set 50% brightness
echo 1250000 | sudo tee duty_cycle

# Check if LED lights up
# (You should see the LED turn ON)

# Try 100% brightness to confirm
echo 2500000 | sudo tee duty_cycle

# Turn off
echo 0 | sudo tee duty_cycle

# Test NORMAL polarity
echo "normal" | sudo tee polarity
echo 1250000 | sudo tee duty_cycle
# (LED should behave opposite to inverted mode)
```

### Step 4: Verify Fix

After updating config with correct polarity:

```bash
# Start system
python run_web_interface.py

# Check logs for polarity setting
# Should show: "⚡ PWM polarity: INVERTED" (if set)

# Test lighting from dashboard
# Open: http://3dscanner:5000
# Click: "Test Lighting" button
# LEDs should flash at 30%

# Check PWM status
sudo cat /sys/kernel/debug/pwm
# Should show active duty cycles with LEDs visibly lit
```

## Expected Configuration

### For N-Channel MOSFET (Most Common)

```yaml
lighting:
  controller_type: "gpiozero"
  use_pigpio_factory: true
  pwm_frequency: 400
  pwm_polarity_inverted: true    # INVERTED for N-channel MOSFET
  
  flash_mode: true
  idle_brightness: 0.10
  calibration_brightness: 0.20
  capture_brightness: 0.30
  
  zones:
    inner:
      gpio_pins: [13]
      # ... rest of zone config
```

### For Direct Drive (Less Common)

```yaml
lighting:
  controller_type: "gpiozero"
  use_pigpio_factory: true
  pwm_frequency: 400
  pwm_polarity_inverted: false   # NORMAL for direct drive
  # OR: omit this line (defaults to false)
  
  # ... rest of config
```

## Verification

After applying the fix, you should see:

**In logs:**
```
⚡ PWM polarity: INVERTED (for N-channel MOSFET/inverted drivers)
⚡⚡⚡ GPIO 18 -> PWM CHIP 0 CHANNEL 0 (TRUE HARDWARE PWM)
⚡ GPIO 18 polarity set to INVERTED
✅ HARDWARE PWM initialized on GPIO 18 (chip 0, channel 0) at 400Hz
```

**In PWM debug:**
```bash
sudo cat /sys/kernel/debug/pwm
```
```
pwm-0   (sysfs): requested enabled period: 2500000 ns duty: 500000 ns polarity: inversed
pwm-1   (sysfs): requested enabled period: 2500000 ns duty: 500000 ns polarity: inversed
```
Note: `polarity: inversed` instead of `polarity: normal`

**Visual confirmation:**
- ✅ LEDs light up during "Test Lighting" button press
- ✅ LEDs visible at 20% during calibration
- ✅ LEDs flash bright (30%) during captures
- ✅ LEDs dim (10%) between scan points

## Troubleshooting

### LEDs Still Don't Light Up After Setting Polarity

1. **Check power supply**:
   ```bash
   # Measure voltage at LED terminals
   # Should be 12V or 5V (depending on your LED strips)
   ```

2. **Check MOSFET gate voltage**:
   ```bash
   # With PWM active at 50%, gate should show ~1.65V average
   # (3.3V * 50% duty cycle)
   ```

3. **Test with 100% brightness**:
   ```yaml
   # Temporarily set in config:
   capture_brightness: 1.0  # 100% for testing
   ```

4. **Check current limiting**:
   - Ensure current limiting resistors are correct
   - Verify MOSFET can handle LED current

### Permission Errors

If you see "Permission denied" when setting polarity:

```bash
# Add user to gpio group
sudo usermod -a -G gpio $USER

# Create udev rule
sudo nano /etc/udev/rules.d/99-pwm.rules
```

Add:
```
SUBSYSTEM=="pwm", KERNEL=="pwm*", ACTION=="add", RUN+="/bin/chgrp -R gpio /sys%p", RUN+="/bin/chmod -R g+w /sys%p"
```

```bash
# Reload and reboot
sudo udevadm control --reload-rules
sudo reboot
```

## Hardware Schematic Reference

### N-Channel MOSFET Circuit (Needs INVERTED)
```
     +12V
       │
       ├─── LED Strip (+)
       │
       └─── LED Strip (-)
              │
              └─── MOSFET Drain
                   MOSFET Source ──→ GND
                   MOSFET Gate ←──── GPIO (via resistor)

Logic: GPIO LOW (0V) = MOSFET ON = LED ON
       GPIO HIGH (3.3V) = MOSFET OFF = LED OFF
       
PWM Setting: INVERTED polarity
```

### P-Channel MOSFET Circuit (Needs NORMAL)
```
     +12V ──→ MOSFET Source
              MOSFET Drain ──→ LED Strip (+)
              MOSFET Gate ←─── GPIO (via resistor)
              
              LED Strip (-) ──→ GND

Logic: GPIO HIGH (3.3V) = MOSFET OFF = LED OFF
       GPIO LOW (0V) = MOSFET ON = LED ON... wait, this is also inverted!
       
PWM Setting: Usually still INVERTED
```

### Direct Drive (Needs NORMAL)
```
     GPIO ──→ Current Limit Resistor ──→ LED (+)
     
     LED (-) ──→ GND

Logic: GPIO HIGH (3.3V) = LED ON
       GPIO LOW (0V) = LED OFF
       
PWM Setting: NORMAL polarity
```

## Summary

1. ✅ Hardware PWM is working correctly
2. ✅ PWM signals are being generated at correct frequency and duty cycle
3. ❌ LEDs not lighting up = polarity or wiring issue
4. 🔧 Run `sudo python debug_led_hardware.py` to diagnose
5. 📝 Update `scanner_config.yaml` with `pwm_polarity_inverted: true` if needed
6. ✅ Restart and test

The hardware PWM implementation is perfect - we just need to match the polarity to your LED driver circuit!
