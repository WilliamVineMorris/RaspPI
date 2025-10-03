# Hardware PWM Fix - Implementation Summary

## Problem Root Cause

The `sudo cat /sys/kernel/debug/pwm` output revealed that **hardware PWM channels were NOT active**:
```
pwm-0   ((null)              ): period: 0 ns duty: 0 ns polarity: normal
```

**Why?** The system was using `gpiozero` with `lgpio` factory, which:
- Does NOT automatically use dtoverlay-configured PWM channels
- Defaults to software PWM (CPU-dependent timing)
- Ignores `/sys/class/pwm/pwmchipX` hardware channels

## Solution: rpi-hardware-pwm Library

Added direct hardware PWM access via `rpi-hardware-pwm` library, which:
- ✅ Directly controls `/sys/class/pwm/pwmchipX` channels (same as dtoverlay)
- ✅ Uses TRUE hardware PWM timers (not CPU-based)
- ✅ Compatible with dtoverlay configuration
- ✅ Pi 5 native support
- ✅ No daemon required

## Code Changes

### 1. Updated `requirements.txt`
```diff
+ rpi-hardware-pwm>=0.2.0  # Direct hardware PWM access via dtoverlay
```

### 2. Modified `lighting/gpio_led_controller.py`

**Import hardware PWM library (lines ~20-25)**:
```python
try:
    from rpi_hardware_pwm import HardwarePWM
    HARDWARE_PWM_AVAILABLE = True
    GPIO_LIBRARY = 'rpi_hardware_pwm'
except ImportError:
    HARDWARE_PWM_AVAILABLE = False
    HardwarePWM = None
```

**Added hardware PWM pin mapping (lines ~240-250)**:
```python
# Hardware PWM pin mapping (dtoverlay=pwm-2chan configures these)
self.hardware_pwm_mapping = {
    18: (0, 0),  # PWM chip 0, channel 0
    13: (0, 1),  # PWM chip 0, channel 1
    12: (1, 0),  # PWM chip 1, channel 0 (alternative)
    19: (1, 1),  # PWM chip 1, channel 1 (alternative)
}
```

**Prioritize hardware PWM (lines ~254-260)**:
```python
if HARDWARE_PWM_AVAILABLE:
    self._use_hardware_pwm = True
    self._use_gpiozero = False
    self._use_pigpio = False
    logger.info("✅ Using rpi-hardware-pwm library (HARDWARE PWM via dtoverlay)")
```

**Initialize hardware PWM channels (lines ~450-475)**:
```python
if self._use_hardware_pwm:
    if pin not in self.hardware_pwm_mapping:
        raise LEDError(f"Pin {pin} not compatible with hardware PWM")
    
    chip, channel = self.hardware_pwm_mapping[pin]
    logger.info(f"⚡⚡⚡ GPIO {pin} -> PWM CHIP {chip} CHANNEL {channel}")
    
    pwm = HardwarePWM(pwm_channel=channel, hz=self.pwm_frequency, chip=chip)
    pwm.start(0)  # Start with 0% duty cycle
    
    pwm_objects.append({
        'type': 'hardware_pwm', 
        'pin': pin, 
        'pwm': pwm, 
        'chip': chip, 
        'channel': channel
    })
```

**Control hardware PWM brightness (lines ~1105-1110)**:
```python
if pwm_obj['type'] == 'hardware_pwm':
    # TRUE HARDWARE PWM - direct hardware register write
    pwm = pwm_obj['pwm']
    pwm.change_duty_cycle(duty_cycle)
```

**Cleanup hardware PWM on shutdown (lines ~565-570)**:
```python
if pwm_obj['type'] == 'hardware_pwm':
    pwm = pwm_obj['pwm']
    pwm.stop()  # Stops PWM and releases channel
    logger.debug(f"Stopped hardware PWM on GPIO {pwm_obj['pin']}")
```

## Testing on Raspberry Pi

### 1. Install Library
```bash
cd ~/RaspPI/V2.0
pip install rpi-hardware-pwm
```

### 2. Start System
```bash
python run_web_interface.py
```

### 3. Expected Logs
```
✅ Using rpi-hardware-pwm library (HARDWARE PWM via dtoverlay)
⚡⚡⚡ GPIO 18 -> PWM CHIP 0 CHANNEL 0 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 18 (chip 0, channel 0) at 1000Hz
⚡⚡⚡ GPIO 13 -> PWM CHIP 0 CHANNEL 1 (TRUE HARDWARE PWM)
✅ HARDWARE PWM initialized on GPIO 13 (chip 0, channel 1) at 1000Hz
```

### 4. Verify Hardware PWM Active
```bash
sudo cat /sys/kernel/debug/pwm
```

Should show **ACTIVE PWM** (not `period: 0 ns`):
```
0: platform/1f00098000.pwm, 4 PWM devices
 pwm-0   (rpi_hardware_pwm    ): requested enabled period: 1000000 ns duty: 200000 ns polarity: normal
 pwm-1   (rpi_hardware_pwm    ): requested enabled period: 1000000 ns duty: 200000 ns polarity: normal
```

**Success indicators**:
- ✅ `requested enabled` - PWM is active
- ✅ `period: 1000000 ns` - 1kHz frequency
- ✅ `duty: XXXXXX ns` - Non-zero duty cycle
- ✅ Owner: `rpi_hardware_pwm` (library name)

## Benefits

### Before (Software PWM)
- ❌ CPU-dependent timing (flickering under load)
- ❌ Inconsistent brightness during scans
- ❌ PWM channels show `period: 0 ns` (inactive)
- ❌ No dtoverlay utilization

### After (Hardware PWM)
- ✅ Dedicated hardware timer (immune to CPU load)
- ✅ Zero flickering even under heavy load
- ✅ PWM channels show `requested enabled` (active)
- ✅ Direct dtoverlay hardware utilization
- ✅ Microsecond-precision timing
- ✅ Perfect camera-flash synchronization

## Verification Checklist

- [ ] Install: `pip install rpi-hardware-pwm`
- [ ] Start: `python run_web_interface.py`
- [ ] Check logs: "Using rpi-hardware-pwm library"
- [ ] Verify PWM: `sudo cat /sys/kernel/debug/pwm`
- [ ] Test lighting: Dashboard → "Test Lighting" button
- [ ] Run scan: Verify smooth brightness transitions
- [ ] Monitor: `watch -n 1 'sudo cat /sys/kernel/debug/pwm'`

## Next Steps

Please test this on the Pi hardware:
1. Install the library
2. Restart the web interface
3. Check the PWM debug output
4. Report if you see `requested enabled` with active duty cycles!

This should completely resolve the hardware PWM issue and eliminate any LED flickering during scans.
