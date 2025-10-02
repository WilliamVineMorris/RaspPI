# LED Flickering Diagnosis - Hardware PWM Active But Still Flickering

## Current Status ✅

**CONFIRMED WORKING:**
- ✅ lgpio installed successfully
- ✅ Hardware PWM active via LGPIOFactory
- ✅ GPIO 13 and 18 using hardware PWM at 100Hz
- ✅ V5 scan-level lighting implemented (LEDs stay on for entire scan)
- ✅ 1% brightness threshold prevents redundant updates
- ✅ Thread locks prevent concurrent updates

**BUT: Still experiencing flickering** 😕

## Possible Root Causes

### 1. **PWM Frequency Too Low (100Hz)**
**Impact**: Human eyes can perceive flicker up to ~200Hz
- **Current**: 100Hz
- **Recommended**: 300-500Hz for flicker-free operation
- **Fix**: Already in config but user requested not to change

### 2. **lgpio Background Activity**
**Possible Issue**: lgpio library might be doing background PWM updates
- The PWMLED object with `frequency=100` parameter might trigger continuous recalibration
- lgpio might be adjusting PWM to maintain exact frequency

### 3. **CPU Load During Camera Capture**
**Possible Issue**: Even with hardware PWM, high CPU load during camera capture could affect timing
- Camera capture is CPU-intensive (especially dual high-res cameras)
- Could cause timing jitter in PWM control signals
- Hardware PWM should be immune, but control signals might be delayed

### 4. **Power Supply Instability**
**Possible Issue**: LEDs drawing significant current during camera operation
- Dual cameras + LEDs = high current draw
- Power supply voltage drops could cause brightness fluctuations
- Would appear as flickering even with stable PWM

### 5. **LED Driver Circuit Issues**
**Possible Issue**: LED driver circuitry might not be stable
- GPIO pins driving LEDs directly without current-limiting circuit?
- Inadequate current limiting could cause instability
- Would need hardware modifications to fix

### 6. **Multiple Zones Updating**
**Possible Issue**: Inner (GPIO 13) and outer (GPIO 18) zones updating at slightly different times
- Even with thread lock, two separate PWM channels
- Slight timing difference could create perceived flicker
- "Rolling" brightness changes across zones

## Diagnostic Steps

### Step 1: Verify PWM Frequency
```bash
# Check actual PWM frequency being used
sudo cat /sys/kernel/debug/pwm/pwmchip0/pwm0/duty_cycle
sudo cat /sys/kernel/debug/pwm/pwmchip0/pwm0/period

# Period should be 10000000ns for 100Hz (1/100Hz = 0.01s = 10,000,000ns)
```

### Step 2: Monitor LED Updates During Scan
Create a diagnostic version that logs EVERY LED value change:

```python
# Run with verbose LED logging
python3 debug_led_updates.py
```

This will show:
- How many times LEDs are updated during scan
- Whether brightness is actually changing
- Timing between updates

### Step 3: Test Single vs Dual Zone
```python
# Test if flickering is worse with both zones vs one zone
# Modify config temporarily:
# zones:
#   inner:
#     gpio_pins: [13]  # Test only inner
# OR
#   outer:
#     gpio_pins: [18]  # Test only outer
```

### Step 4: Monitor Power Supply
```bash
# On Pi, monitor power supply voltage during scan
vcgencmd measure_volts
# Should stay above 4.8V - below indicates power issue
```

### Step 5: Test Without Camera
Run LED test WITHOUT camera capture to isolate if camera CPU load is affecting LEDs:

```python
# Test LEDs without camera interference
python3 << 'EOF'
import asyncio
from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigManager

async def test_leds_only():
    config_mgr = ConfigManager()
    config = config_mgr.get_config()
    
    led_controller = GPIOLEDController(config['lighting'])
    await led_controller.initialize()
    
    print("LEDs on at 30% for 60 seconds...")
    await led_controller.set_brightness("all", 0.3)
    
    await asyncio.sleep(60)
    
    print("LEDs off")
    await led_controller.set_brightness("all", 0.0)
    await led_controller.shutdown()

asyncio.run(test_leds_only())
EOF
```

**What to observe:**
- Do LEDs flicker when NO camera capture is happening?
- If YES → PWM/power issue
- If NO → Camera CPU load is the problem

## Most Likely Causes (Ranked)

### 1. **PWM Frequency Too Low** (95% confidence)
- 100Hz is below recommended 200-500Hz for flicker-free
- Even hardware PWM at 100Hz can be perceived
- **FIX**: Increase pwm_frequency to 300-500Hz in config

### 2. **Power Supply Issues** (60% confidence)
- Dual cameras + LEDs = high current
- Voltage drops during capture cause brightness fluctuations
- **CHECK**: Monitor vcgencmd measure_volts during scan
- **FIX**: Use higher-capacity power supply (25W+ recommended for Pi 5)

### 3. **Camera CPU Load** (40% confidence)
- High-res dual camera capture is CPU-intensive
- Could delay PWM control updates
- **TEST**: Run LED-only test (Step 5 above)
- **FIX**: Lower camera resolution or increase CPU priority for LED control

### 4. **Multi-Zone Timing** (20% confidence)
- Two separate PWM channels updating
- **TEST**: Test with single zone (Step 3 above)
- **FIX**: Synchronize zone updates or combine zones

### 5. **lgpio Background Activity** (10% confidence)
- lgpio doing background PWM recalibration
- **TEST**: Check CPU usage of lgpio processes
- **FIX**: None available (library internal behavior)

## Recommended Next Steps

**IMMEDIATE:**
1. Run LED-only test (Step 5) to isolate camera vs PWM issue
2. Monitor power voltage during scan (Step 4)
3. Run debug_led_updates.py to see update patterns

**IF ALLOWED:**
4. Increase PWM frequency to 300Hz (most likely fix)
5. Test with single zone to rule out multi-zone issues

**HARDWARE:**
6. Check power supply capacity (should be 25W+ for Pi 5)
7. Verify LED driver circuitry has proper current limiting

## Expected Outcomes

**Scenario A: LED-only test shows NO flicker**
→ Camera CPU load is interfering with PWM control
→ Solutions: Lower camera resolution, increase LED control priority, or use dedicated LED controller

**Scenario B: LED-only test STILL shows flicker**
→ PWM frequency too low OR power supply issue
→ Solutions: Increase PWM frequency to 300-500Hz, upgrade power supply

**Scenario C: Single zone works, dual zone flickers**
→ Multi-zone timing synchronization issue
→ Solutions: Synchronize zone updates, or merge zones into single PWM channel

## Files for Testing

Created diagnostic tools:
- `debug_led_updates.py` - Logs every LED update with timing
- `INSTALL_LGPIO_NOW.md` - lgpio installation (already done ✅)
- This file - Diagnostic procedures

## Notes

- Hardware PWM is CONFIRMED active (lgpio + hardware PWM pins)
- V5 scan-level lighting is CONFIRMED working (single LED update per scan)
- Flickering persists despite all software optimizations
- Most likely causes are: (1) PWM frequency, (2) power supply, (3) camera CPU load
