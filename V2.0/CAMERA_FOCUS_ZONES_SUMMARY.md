# Camera-Specific Focus Zones - Quick Summary

## What Changed

Added support for **camera-specific autofocus zones** in dual-camera turntable scanning.

## Configuration (scanner_config.yaml)

```yaml
cameras:
  focus_zone:
    enabled: true
    
    # Camera 0: Focus zone shifted LEFT (15% start)
    camera_0:
      window: [0.15, 0.25, 0.5, 0.5]
      
    # Camera 1: Focus zone shifted RIGHT (35% start) - MIRRORED
    camera_1:
      window: [0.35, 0.25, 0.5, 0.5]
```

## Visual Layout

```
Camera 0 (Left view)          Camera 1 (Right view)
┌───────────────────┐         ┌───────────────────┐
│ ┌─────────┐       │         │       ┌─────────┐ │
│ │ FOCUS   │       │         │       │  FOCUS  │ │
│ └─────────┘       │         │       └─────────┘ │
└───────────────────┘         └───────────────────┘
  15%      65%                        35%      85%
  
  ↓                              ↓
  Both converge on turntable center from different angles
```

## Key Points

- **Horizontal offset**: 10% (camera_0 at 15%, camera_1 at 35%)
- **Vertical position**: Same for both (25% from top)
- **Zone size**: Same for both (50% width × 50% height)
- **Mirrored**: camera_1 offset is mirror of camera_0

## Code Changes

**File**: `camera/pi_camera_controller.py`

Added camera-specific configuration lookup:
```python
camera_key = f'camera_{camera_id}'
if camera_key in focus_zone_config:
    focus_window = focus_zone_config[camera_key].get('window')
else:
    focus_window = focus_zone_config.get('window', [0.25, 0.25, 0.5, 0.5])
```

## Tuning

**More offset** (cameras further apart):
```yaml
camera_0: { window: [0.10, 0.25, 0.5, 0.5] }  # 10% start
camera_1: { window: [0.40, 0.25, 0.5, 0.5] }  # 40% start
# Offset: 15%
```

**Less offset** (cameras closer):
```yaml
camera_0: { window: [0.20, 0.25, 0.5, 0.5] }  # 20% start
camera_1: { window: [0.30, 0.25, 0.5, 0.5] }  # 30% start
# Offset: 5%
```

**No offset** (backward compatible):
```yaml
focus_zone:
  window: [0.25, 0.25, 0.5, 0.5]  # Both cameras use same zone
```

## Testing

```bash
cd RaspPI/V2.0
python -c "
import asyncio
from camera.pi_camera_controller import PiCameraController
from core.config_manager import ConfigManager

async def test():
    cfg = ConfigManager('config/scanner_config.yaml')
    ctrl = PiCameraController(cfg)
    await ctrl.initialize()
    
    # Calibrate both cameras - should show different AfWindows
    await ctrl.calibrate_scan_settings('camera0')  # Left zone
    await ctrl.calibrate_scan_settings('camera1')  # Right zone
    
    await ctrl.shutdown()

asyncio.run(test())
"
```

**Expected log**:
```
Camera 0 focus zone: AfWindows=[(698, 874, 2328, 1748)]   ← Left shift (x=698)
Camera 1 focus zone: AfWindows=[(1630, 874, 2328, 1748)]  ← Right shift (x=1630)
```

## Benefits

✅ Each camera focuses on its actual viewing angle  
✅ Better autofocus accuracy for turntable scanning  
✅ Reduces background/edge focus issues  
✅ Maintains vertical alignment (same height)  
✅ Backward compatible (falls back to global window)

## Files Modified

1. `config/scanner_config.yaml` - Added `camera_0` and `camera_1` focus zones
2. `camera/pi_camera_controller.py` - Added camera-specific config lookup
3. `CAMERA_SPECIFIC_FOCUS_ZONES.md` - Full documentation (new)
4. `CAMERA_FOCUS_ZONES_SUMMARY.md` - This quick reference (new)

## Related Documentation

- `FOCUS_ZONE_CONFIGURATION.md` - Original focus zone system
- `AFWINDOWS_COORDINATE_FIX.md` - Coordinate system details
- `RESOLUTION_INDEPENDENCE_ANALYSIS.md` - How focus zones work across resolutions
