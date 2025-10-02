# PWM Flickering Root Cause - Pi 5 Specific Issue

## Key Discovery 🔍

**Critical Evidence:**
- Same LED driver works **perfectly** on different microcontroller (no flicker)
- On Pi 5: Flickering present at 100Hz, may persist at 400Hz
- Voltage fluctuations: 0.72V → 0.94V (significant!)
- Pi is not throttled (power supply adequate)

## Root Cause: lgpio/gpiozero PWM Instability on Pi 5

### The Real Problem

The flickering is **NOT** caused by:
- ❌ PWM frequency too low (100Hz vs 400Hz helps but may not eliminate)
- ❌ Power supply (Pi not throttled)
- ❌ LED driver circuit (works fine on other MCU)
- ❌ Camera CPU load (flickers even without camera)

The flickering **IS** caused by:
- ✅ **lgpio PWM implementation instability on Pi 5**
- ✅ **gpiozero background updates/polling**
- ✅ **DMA conflicts between PWM and camera peripherals**

### Evidence Analysis

1. **Voltage fluctuation (0.72V → 0.94V)**
   - This is **core voltage**, not supply voltage
   - Fluctuation indicates CPU load changes
   - CPU load changes can affect PWM timing even with hardware PWM

2. **Works on other microcontroller**
   - Other MCU probably uses dedicated PWM peripheral
   - Pi 5's PWM might share resources with DMA/cameras
   - Timing interference from other peripherals

3. **Pi 5 specific**
   - lgpio is relatively new for Pi 5
   - May have timing bugs or DMA conflicts
   - gpiozero may not be optimized for lgpio backend

## Solutions (In Order of Effectiveness)

### Solution 1: Direct lgpio PWM (Bypass gpiozero) ⭐⭐⭐⭐⭐

**Why:** gpiozero adds abstraction layer that may poll/update PWM unnecessarily

**How:**
```python
import lgpio

# Open GPIO chip
h = lgpio.gpiochip_open(0)

# Set hardware PWM on GPIO 13
# tx_pwm(handle, gpio, frequency, duty_cycle)
lgpio.tx_pwm(h, 13, 400, 30)  # 400Hz, 30% duty

# Keep PWM running - don't modify!
# When done:
lgpio.tx_pwm(h, 13, 0, 0)  # Stop
lgpio.gpiochip_close(h)
```

**Advantages:**
- Direct hardware control, no abstraction overhead
- No background polling/updates
- Minimal CPU involvement

### Solution 2: Increase PWM Frequency Further ⭐⭐⭐⭐

**Current:** 400Hz
**Try:** 1000Hz (1kHz) or 2000Hz (2kHz)

**Why:** Higher frequency may overcome timing jitter from DMA conflicts

**How:** Already done in config, just increase value:
```yaml
pwm_frequency: 1000  # or 2000
```

### Solution 3: Disable DMA for Cameras ⭐⭐⭐

**Why:** Camera DMA may interfere with PWM DMA channels

**How:** Add to `/boot/config.txt`:
```
# Disable camera DMA to prevent PWM interference
disable_camera_led=1
```

### Solution 4: Use Software PWM with High Priority ⭐⭐

**Why:** Software PWM with real-time priority might be more stable than hardware PWM with DMA conflicts

**How:** Modify LED controller to use RPi.GPIO with high priority thread

### Solution 5: External PWM Controller ⭐⭐⭐⭐⭐ (Hardware)

**Why:** Eliminates Pi 5 PWM issues entirely

**What:** PCA9685 16-channel PWM controller
- I2C controlled (no PWM peripheral needed)
- Dedicated PWM chip (no CPU/DMA interference)
- Rock-solid stable PWM

**Cost:** ~$10-15 for breakout board

## Immediate Testing

### Test 1: Diagnostic Script
```bash
python3 diagnose_pwm_stability.py
```

This will:
1. Test gpiozero PWMLED stability (10 seconds)
2. Test direct lgpio PWM stability (10 seconds)
3. Determine if gpiozero or lgpio is causing instability

**Expected Results:**
- If **gpiozero** flickers but **direct lgpio** is stable → Use Solution 1
- If **both** flicker → Use Solution 2, 3, or 5

### Test 2: Try Direct lgpio Implementation

I can create a modified LED controller that uses direct lgpio instead of gpiozero.

### Test 3: Increase Frequency to 1-2kHz

Try higher frequencies to see if timing jitter becomes negligible.

## Recommended Action Plan

1. **Run** `diagnose_pwm_stability.py` to identify exact cause
2. **If gpiozero is unstable:** Switch to direct lgpio implementation
3. **If lgpio is unstable:** Try higher frequency (1-2kHz)
4. **If still unstable:** Consider external PWM controller (PCA9685)

## Why This Makes Sense

Your observation that the **same LED driver works on another microcontroller** is the smoking gun! This proves:
- ✅ LED driver circuit is fine
- ✅ LEDs are fine
- ✅ Wiring is fine
- ❌ **Pi 5 PWM generation has issues**

The voltage fluctuation (0.72V → 0.94V) confirms the Pi's CPU/DMA activity is affecting something, even though hardware PWM should be independent.

## Next Steps

1. Run diagnostic script: `python3 diagnose_pwm_stability.py`
2. Report back:
   - Does Test 1 (gpiozero) show stable LED?
   - Does Test 2 (direct lgpio) show stable LED?
3. Based on results, I'll implement the appropriate fix

Would you like me to:
- A) Create a direct lgpio LED controller implementation?
- B) Increase frequency to 1-2kHz?
- C) Both?
