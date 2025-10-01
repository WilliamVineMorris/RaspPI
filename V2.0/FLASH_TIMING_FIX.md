# Flash Timing Improvements - Resolution-Independent Lighting

## Problem Identified
The previous flash synchronization used a fixed 2.7-second delay which worked well for high-resolution captures but triggered too late for lower resolutions. Camera preparation time varies with resolution, making time-based synchronization unreliable.

## Solution Implemented

### Two-Mode Approach

#### 1. **Constant Lighting Mode** (Default, Recommended) ✅
- **How it works**: LEDs turn on at 30% brightness BEFORE capture starts and stay on during entire capture
- **Resolution-independent**: Works correctly regardless of camera resolution or timing
- **Brightness**: 30% (configurable)
- **Advantages**:
  - No timing issues across different resolutions
  - More consistent lighting
  - Simpler and more reliable
  - Better for video/preview mode compatibility

#### 2. **Timed Flash Mode** (Legacy)
- **How it works**: Uses fixed 2.7s delay then fires 650ms flash at 70% brightness
- **Resolution-dependent**: Timing calibrated for high-resolution captures only
- **Advantages**:
  - Higher brightness (70%)
  - Shorter duration
- **Disadvantages**:
  - May miss timing at lower resolutions
  - More complex synchronization

## Implementation Details

### Code Changes

#### 1. LightingSettings Updated (`lighting/base.py`)
```python
class LightingSettings:
    brightness: float = 0.5
    duration_ms: Optional[float] = None
    constant_mode: bool = False  # NEW: Enable constant lighting mode
    
    # Auto-enable constant mode if duration_ms = 0
    def __post_init__(self):
        if self.duration_ms == 0:
            self.constant_mode = True
```

#### 2. GPIOLEDController Enhanced (`lighting/gpio_led_controller.py`)
```python
async def trigger_for_capture(self, camera_controller, zone_ids, settings):
    """Two strategies based on settings.constant_mode"""
    if settings.constant_mode or settings.duration_ms == 0:
        return await self._constant_lighting_capture(...)
    else:
        return await self._timed_flash_capture(...)  # Legacy mode

async def _constant_lighting_capture(...):
    """Turn LEDs on, capture, then turn off"""
    # Turn on LEDs at specified brightness
    for zone_id in zone_ids:
        await self.set_brightness(zone_id, settings.brightness)
    
    # Capture with LEDs on
    capture_result = await camera_controller.capture_both_cameras_simultaneously()
    
    # Turn off LEDs
    await self.turn_off_all()
    
    return FlashResult(...)
```

#### 3. Scan Orchestrator Updated (`scanning/scan_orchestrator.py`)
```python
# NEW default settings - constant mode at 30%
flash_settings = LightingSettings(
    brightness=0.3,      # 30% constant lighting
    duration_ms=0,       # 0 = constant mode
    constant_mode=True   # Explicit flag
)
```

**OLD settings** (commented out for reference):
```python
# flash_settings = LightingSettings(
#     brightness=0.7,      # 70% flash
#     duration_ms=650      # Timed flash
# )
```

## Configuration Options

### Using Constant Mode (Default)
```python
flash_settings = LightingSettings(
    brightness=0.3,       # 30% brightness (adjustable 0.1-0.5)
    duration_ms=0,        # 0 = constant mode
    constant_mode=True
)
```

### Using Legacy Timed Flash Mode
```python
flash_settings = LightingSettings(
    brightness=0.7,       # 70% brightness
    duration_ms=650,      # Flash duration in milliseconds
    constant_mode=False   # Timed flash mode
)
```

### Adjusting Constant Mode Brightness

For different lighting conditions:
- **Bright ambient light**: `brightness=0.2` (20%)
- **Normal conditions**: `brightness=0.3` (30%) ✅ Default
- **Dark conditions**: `brightness=0.4` (40%)
- **Very dark**: `brightness=0.5` (50%)

**Warning**: Don't exceed 50% for constant mode as it's on for longer duration.

## Testing Results Expected

### With Constant Mode (30% brightness)
```
💡 Using CONSTANT LIGHTING mode: zones=['inner', 'outer'], brightness=0.3
💡 CONSTANT LIGHTING: Turning on LEDs before capture...
💡 LEDs on at 30% brightness, starting camera capture...
📸 Waiting for camera capture to complete...
✅ Camera capture completed
💡 CONSTANT LIGHTING: Turning off LEDs after capture...
✅ CONSTANT LIGHTING capture successful
```

### Resolution Independence Test
Test at different resolutions - constant mode should work consistently:
- High resolution (4624x3472): ✅ LEDs on during entire capture
- Medium resolution (1920x1080): ✅ LEDs on during entire capture  
- Low resolution (640x480): ✅ LEDs on during entire capture

## Advantages of Constant Mode

1. **Resolution-Independent**: Works with any camera resolution
2. **Simpler Logic**: No timing calculations needed
3. **More Reliable**: No risk of early/late flash trigger
4. **Better Integration**: Compatible with video/preview modes
5. **Consistent Results**: Same lighting for all capture types
6. **Lower Brightness**: 30% is sufficient when on for entire capture

## Safety Considerations

### Constant Mode Safety
- **30% brightness** for longer duration stays well below 90% duty cycle limit
- LEDs are only on during actual capture (~3-5 seconds)
- `turn_off_all()` called in finally block ensures LEDs turn off even if capture fails
- Hardware safety limits still enforced in `set_brightness()`

### Thermal Considerations
- 30% constant for 3-5 seconds: ✅ Safe (much less heat than 70% flash)
- Multiple scans in sequence: ✅ Safe (LEDs off between captures)
- Calibration mode: ✅ Already uses 30% constant lighting successfully

## Migration Path

### Current Implementation
- ✅ Constant mode enabled by default in scan orchestrator
- ✅ Calibration already uses constant mode (working well)
- ✅ Both modes available for flexibility

### Future Enhancements
1. Make mode configurable via web UI
2. Add resolution-based auto-selection
3. Add brightness presets for different scenarios
4. Implement dynamic brightness adjustment based on camera exposure

## Troubleshooting

### If Images Are Too Dark
- Increase `brightness` from 0.3 to 0.4 or 0.5
- Check LED hardware connections
- Verify both 'inner' and 'outer' zones are working

### If Images Are Overexposed
- Decrease `brightness` from 0.3 to 0.2
- Check camera exposure settings
- Consider shorter exposure time in camera config

### If Wanting to Use Old Flash Mode
```python
# Change in scan_orchestrator.py line ~3847
flash_settings = LightingSettings(
    brightness=0.7,
    duration_ms=650,      # Non-zero = timed flash mode
    constant_mode=False
)
```

### If Flash Timing Still Off (Legacy Mode)
- Adjust delay in `_timed_flash_capture()` method
- Current: `await asyncio.sleep(2.7)`
- For faster resolutions: Try `2.5` or `2.3`
- For slower resolutions: Try `2.9` or `3.0`

## Performance Comparison

| Metric | Constant Mode (30%) | Timed Flash (70%) |
|--------|-------------------|-------------------|
| Resolution Independence | ✅ Works all resolutions | ❌ High-res only |
| Timing Reliability | ✅ Perfect sync | ⚠️ May drift |
| Brightness | 30% (sufficient) | 70% (brighter) |
| Power Usage | Lower (30%) | Higher (70%) |
| Complexity | Simple | Complex timing |
| Calibration Match | ✅ Same as calibration | ❌ Different mode |

## Conclusion

**Constant lighting mode at 30% is now the default and recommended approach** because:
1. It solves the resolution-dependent timing issue
2. It matches the calibration mode lighting (consistency)
3. It's simpler and more reliable
4. It provides adequate lighting for quality captures
5. It's safer for hardware (lower continuous brightness)

The legacy timed flash mode remains available for special cases but is not recommended for general use.
