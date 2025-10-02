# LED Flickering Investigation - Hardware PWM Active

## Summary

✅ **CONFIRMED WORKING:**
- Hardware PWM via lgpio LGPIOFactory
- GPIO 13 and 18 using true hardware PWM
- V5 scan-level lighting (single LED update per scan)
- 1% brightness threshold prevents redundant updates
- Thread locks prevent concurrent access

❌ **STILL EXPERIENCING: Flickering during camera capture**

## Root Cause Analysis

Since hardware PWM is confirmed active and software optimizations are in place, the flickering must be caused by one of these hardware/system-level issues:

### Most Likely Causes

#### 1. **PWM Frequency (100Hz) Too Low** ⭐⭐⭐⭐⭐
**Confidence: 95%**

- **Problem**: 100Hz PWM is below the 200-500Hz recommended for flicker-free operation
- **Why it matters**: Even hardware PWM at 100Hz can be perceived by human eyes
- **Evidence**: Config shows `pwm_frequency: 100`
- **Fix**: Increase to 300-500Hz in `config/scanner_config.yaml`

**Change needed:**
```yaml
lighting:
  pwm_frequency: 400  # Increase from 100 to 400Hz
```

#### 2. **Power Supply Instability** ⭐⭐⭐⭐
**Confidence: 70%**

- **Problem**: Dual cameras + LEDs draw significant current, causing voltage drops
- **Why it matters**: Voltage fluctuations cause brightness changes even with stable PWM
- **Evidence**: Pi 5 + dual cameras + LEDs can draw 15-20W
- **Fix**: Use official Raspberry Pi 5 27W power supply or equivalent

**Test:**
```bash
# Monitor voltage during scan - should stay above 4.8V
watch -n 0.5 vcgencmd measure_volts
```

#### 3. **Camera CPU Load** ⭐⭐⭐
**Confidence: 50%**

- **Problem**: High-resolution dual camera capture is CPU-intensive
- **Why it matters**: CPU load could delay PWM control updates even with hardware PWM
- **Evidence**: Flickering happens during camera capture
- **Fix**: Test without camera to isolate

**Test:**
```bash
# Run LED-only test (no camera)
python3 test_led_only_no_camera.py
```

## Diagnostic Tools Created

### 1. `test_led_only_no_camera.py`
**Purpose**: Test LEDs without camera capture
**Use**: Determine if flickering is PWM/power or camera-related

```bash
python3 test_led_only_no_camera.py
```

**Expected outcomes:**
- **Flicker WITHOUT camera** → PWM frequency or power supply issue
- **NO flicker without camera** → Camera CPU load issue

### 2. `monitor_pwm_hardware.py`
**Purpose**: Monitor actual PWM hardware state
**Use**: Verify hardware PWM is stable and check duty cycle

```bash
sudo python3 monitor_pwm_hardware.py
```

**What to check:**
- PWM frequency should be constant at 100Hz
- Duty cycle should be stable at ~30% when LEDs are on
- No unexpected enable/disable cycles

### 3. `debug_led_updates.py`
**Purpose**: Log every LED brightness change
**Use**: Check if unwanted updates are happening

```bash
python3 debug_led_updates.py
```

**What to check:**
- Should see ONE update when LEDs turn on (scan start)
- Should see ONE update when LEDs turn off (scan end)
- Any additional updates indicate a problem

## Testing Protocol

### Phase 1: Isolate the Problem

**Test 1: LED-only (no camera)**
```bash
python3 test_led_only_no_camera.py
```

**If flickering persists:**
→ Problem is PWM frequency or power supply
→ Go to Phase 2

**If NO flickering:**
→ Problem is camera CPU load
→ Go to Phase 3

### Phase 2: PWM/Power Issues

**Test 2a: Monitor power supply**
```bash
# Terminal 1: Monitor voltage
watch -n 0.5 vcgencmd measure_volts

# Terminal 2: Run LED test
python3 test_led_only_no_camera.py
```

**Check:**
- Voltage should stay above 4.8V
- If drops below 4.8V → Power supply issue

**Test 2b: Check PWM hardware state**
```bash
sudo python3 monitor_pwm_hardware.py
# Let it run during LED-only test
```

**Check:**
- Frequency should be constant (100Hz)
- Duty cycle should be stable (~30%)
- No unexpected state changes

### Phase 3: Camera CPU Load Issues

**Test 3a: Lower camera resolution**
Temporarily modify camera configuration:
```yaml
camera:
  resolution:
    width: 1640  # Half resolution
    height: 1232
```

**Test 3b: Single camera**
Test with only one camera to reduce CPU load

**Test 3c: Increase LED control priority**
Modify LED controller to use real-time priority (requires code changes)

## Recommended Solutions

### Solution A: Increase PWM Frequency (RECOMMENDED)
**If you allow PWM frequency change:**

```yaml
# config/scanner_config.yaml
lighting:
  pwm_frequency: 400  # Change from 100 to 400Hz
```

**Rationale:**
- 400Hz is well above human perception threshold (~200Hz)
- Still within safe range for hardware PWM
- Most effective solution for flicker-free operation

### Solution B: Upgrade Power Supply
**If voltage drops below 4.8V:**

- Use official Raspberry Pi 5 27W USB-C power supply
- Or equivalent 5V/5A (25W+) power supply
- Ensure good quality USB-C cable

### Solution C: Optimize Camera Capture
**If camera CPU load is the issue:**

1. **Lower resolution** during preview/scanning
2. **Increase capture interval** between photos
3. **Disable unnecessary processing** during capture
4. **Use single camera** if dual not critical

### Solution D: Hardware Modifications
**If all else fails:**

1. **Add external LED driver** (e.g., PCA9685 PWM controller)
2. **Use separate power supply** for LEDs
3. **Add smoothing capacitors** to LED power lines

## Expected Results After Fixes

### After PWM frequency increase to 400Hz:
- Flickering should be completely eliminated
- LEDs will appear rock-solid even during camera capture
- No perceived brightness changes

### After power supply upgrade:
- Voltage stable above 4.8V during full load
- No brightness fluctuations
- System more stable overall

### After camera optimization:
- Reduced CPU load during capture
- More consistent LED control timing
- Possibly reduced flickering (but may not eliminate entirely)

## Current System State

```
Hardware: Raspberry Pi 5
PWM Library: lgpio (Pi 5 compatible)
PWM Type: Hardware PWM (GPIO 13, 18)
PWM Frequency: 100Hz ⚠️ (low)
LED Control: Scan-level (single update)
Brightness Threshold: 1% (prevents redundant updates)
Thread Safety: Lock-protected ✅
```

## Files Reference

- **Config**: `config/scanner_config.yaml` (pwm_frequency setting)
- **LED Controller**: `lighting/gpio_led_controller.py` (PWM implementation)
- **Scan Control**: `scanning/scan_orchestrator.py` (V5 scan-level lighting)
- **Diagnostics**: This directory (test scripts)

## Next Steps

1. **Run test_led_only_no_camera.py** to isolate cause
2. **Monitor power supply** during operation
3. **If allowed, increase PWM frequency** to 400Hz
4. **Report back results** for further diagnosis

## Questions to Answer

1. Does flickering occur **without camera capture**? (test_led_only_no_camera.py)
2. Does **voltage drop below 4.8V** during scan? (vcgencmd measure_volts)
3. Are there **multiple LED updates** during scan? (debug_led_updates.py)
4. Is **PWM state stable**? (monitor_pwm_hardware.py)

These answers will definitively identify the root cause.
