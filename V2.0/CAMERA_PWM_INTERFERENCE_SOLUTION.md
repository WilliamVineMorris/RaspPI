# Camera-PWM Interference Solution

## Diagnostic Results ✅

**Test 1 (gpiozero PWMLED):** ✅ Stable - no background updates
**Test 2 (direct lgpio):** ❌ Needs GPIO setup fix (will retest)

## Root Cause Identified 🎯

Since gpiozero value remains stable (no background polling), the flickering must be caused by:

1. **Camera DMA interference** - Camera and PWM share DMA channels
2. **CPU load during capture** - High CPU usage affects PWM clock timing
3. **libcamera interference** - Pi 5's new camera stack may conflict with PWM

## Solutions (Ordered by Effectiveness)

### Solution 1: Increase PWM Frequency to 1-2kHz ⭐⭐⭐⭐⭐
**Status:** Easy to test, likely to work

**Why:** Higher frequency makes timing jitter negligible
- Current: 400Hz (2.5ms period)
- Proposed: 2000Hz (0.5ms period)
- Jitter becomes 5x less noticeable

**Implementation:**
```yaml
# config/scanner_config.yaml
lighting:
  pwm_frequency: 2000  # 2kHz - timing jitter becomes imperceptible
```

**Test:**
```bash
# Update config, then run
python3 test_led_only_no_camera.py
```

### Solution 2: PWM Priority & CPU Isolation ⭐⭐⭐⭐
**Status:** Requires code changes

**Why:** Ensure PWM updates get CPU priority over camera

**Implementation:** Modify LED controller to:
1. Run PWM updates in high-priority thread
2. Use CPU affinity to isolate PWM from camera processes
3. Disable CPU frequency scaling during LED operation

### Solution 3: Disable Camera DMA Conflicts ⭐⭐⭐
**Status:** System configuration change

**Why:** Force camera to use different DMA channels than PWM

**Implementation:**
Add to `/boot/firmware/config.txt`:
```ini
# Prevent camera DMA from interfering with PWM
avoid_pwm_pll=1
force_turbo=0
```

Reboot after change.

### Solution 4: Software PWM with High Priority ⭐⭐
**Status:** Fallback if hardware PWM can't work

**Why:** Sometimes software PWM with guaranteed CPU time is more stable than hardware PWM with DMA conflicts

### Solution 5: External PWM Controller (Hardware) ⭐⭐⭐⭐⭐
**Status:** 100% reliable but requires hardware

**What:** PCA9685 16-channel I2C PWM controller (~$10)

**Why:** 
- Completely independent from Pi's PWM/DMA
- Dedicated PWM chip with crystal oscillator
- I2C control (no DMA conflicts)
- Works up to 1.6kHz PWM

## Immediate Action: Test Higher Frequency

Since you already have 400Hz working, let's try 2kHz:

### Step 1: Update Config
```bash
# Edit config/scanner_config.yaml
# Change: pwm_frequency: 400
# To:     pwm_frequency: 2000
```

### Step 2: Test Without Camera
```bash
python3 test_led_only_no_camera.py
# Watch for 60 seconds - should be rock solid
```

### Step 3: Test With Camera
```bash
python3 run_web_interface.py
# Run actual scan, observe LEDs during camera capture
```

## Expected Outcomes

### If 2kHz works:
✅ **Problem solved!** Timing jitter is now negligible at 2kHz
- 2000Hz = 0.5ms period
- Even 10% timing variation is only 0.05ms (imperceptible)

### If 2kHz still flickers:
→ DMA conflict is severe, need Solution 3 or 5:
1. Try boot config changes (disable camera DMA conflicts)
2. Consider external PWM controller

## Why Higher Frequency Works

**At 100Hz:**
- Period = 10ms
- 5% jitter = 0.5ms variation
- Human eye detects this as flicker

**At 400Hz:**
- Period = 2.5ms  
- 5% jitter = 0.125ms variation
- Still sometimes visible

**At 2000Hz:**
- Period = 0.5ms
- 5% jitter = 0.025ms variation
- Completely imperceptible to human eye

Even if camera DMA causes timing jitter, at 2kHz it becomes invisible!

## Implementation

Would you like me to:
1. ✅ **Update config to 2kHz** (recommended - test first)
2. ⚙️ **Implement high-priority PWM thread** (if 2kHz not enough)
3. 🔧 **Add boot config DMA fixes** (system-level solution)
4. 🛠️ **Create PCA9685 driver** (hardware solution)

Let's start with #1 - it's the easiest and most likely to work!
