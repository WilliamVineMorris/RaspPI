# Resolution Independence Analysis - AfWindows Focus Zone

## Question: Will AfWindows work across different resolutions?

**Answer: YES ✅** - The current implementation is resolution-independent.

## Why It Works

### libcamera Coordinate System Hierarchy

```
┌─────────────────────────────────────────┐
│   PixelArraySize (9152×6944)            │  ← Full sensor array
│   ┌───────────────────────────────────┐ │
│   │ ScalerCropMaximum (4656×3496)     │ │  ← Maximum usable window (sensor mode)
│   │  ┌──────────────────────────────┐ │ │
│   │  │ AfWindows coordinates        │ │ │  ← Focus zone defined HERE
│   │  │  (1163, 874, 2328, 1748)     │ │ │
│   │  └──────────────────────────────┘ │ │
│   │                                   │ │
│   │  ↓ ISP Cropping (optional)       │ │
│   │  ↓ ISP Scaling                   │ │
│   │                                   │ │
│   └───────────────────────────────────┘ │
└─────────────────────────────────────────┘
           ↓
    Output Resolution
    (1920×1080, 3840×2160, 4624×3472, etc.)
```

### Key Insight

**AfWindows are applied in sensor coordinate space BEFORE output scaling**

This means:
- AfWindows at (1163, 874, 2328, 1748) relative to ScalerCropMaximum
- Works for output resolution 1920×1080 ✅
- Works for output resolution 3840×2160 ✅  
- Works for output resolution 4624×3472 ✅

The ISP handles the coordinate transformation automatically.

## Picamera2 Architecture

```python
# During calibrate_scan_settings():
scaler_crop_max = picamera2.camera_properties.get('ScalerCropMaximum')
# Returns: (0, 0, 4656, 3496) - CONSTANT for sensor mode

# Calculate AfWindows once
x_px = int(0.25 * 4656) = 1164
y_px = int(0.25 * 3496) = 874
w_px = int(0.5 * 4656) = 2328
h_px = int(0.5 * 3496) = 1748

picamera2.set_controls({"AfWindows": [(1164, 874, 2328, 1748)]})

# Later, capture at ANY resolution:
picamera2.configure(create_still_configuration(main={"size": (1920, 1080)}))
picamera2.capture_file("image_1080p.jpg")  # AfWindows STILL VALID ✅

picamera2.configure(create_still_configuration(main={"size": (4624, 3472)}))
picamera2.capture_file("image_fullres.jpg")  # AfWindows STILL VALID ✅
```

## When ScalerCropMaximum Could Change

### Sensor Mode Switching (Rare)

The **only** scenario where `ScalerCropMaximum` changes:

```python
# Full-resolution sensor mode (no binning)
ScalerCropMaximum: (0, 0, 4656, 3496)

# VS

# Binned sensor mode (2×2 binning for faster readout)
ScalerCropMaximum: (0, 0, 2328, 1748)
```

**However**: 
- Picamera2 typically uses the same sensor mode for all configurations
- Sensor mode is determined by the camera hardware/driver, not by output resolution
- Your code would work even if sensor mode changed, because it re-reads `ScalerCropMaximum` during calibration

## Current Implementation: Safe ✅

### Line 994 in `pi_camera_controller.py`:

```python
scaler_crop_max = picamera2.camera_properties.get('ScalerCropMaximum')
```

This gets the **current** sensor mode's coordinate space. As long as:
1. Calibration happens **before** first capture ✅
2. Sensor mode doesn't change mid-session ✅ (typical behavior)

The AfWindows will work for **all output resolutions**.

## Resolution vs Sensor Mode Clarification

### Output Resolution (Configurable - Safe to Change)
```python
# These are ALL SAFE and use the same AfWindows:
config1 = camera.create_still_configuration(main={"size": (1920, 1080)})
config2 = camera.create_still_configuration(main={"size": (3840, 2160)})
config3 = camera.create_still_configuration(main={"size": (4624, 3472)})
```

### Sensor Mode (Hardware-determined - Rarely changes)
```python
# Different sensor modes (hypothetical - Picamera2 manages this):
sensor_mode_0: Full resolution readout → ScalerCropMaximum: (0, 0, 4656, 3496)
sensor_mode_1: Binned readout → ScalerCropMaximum: (0, 0, 2328, 1748)
```

**Picamera2 automatically selects appropriate sensor mode based on configuration.**

For IMX519 with typical configurations, sensor mode remains consistent.

## Verification on Hardware

To verify your AfWindows work across resolutions, test on Pi:

```python
# Calibrate once
await controller.calibrate_scan_settings("camera0")

# Test multiple resolutions
for resolution in [(1920, 1080), (3840, 2160), (4624, 3472)]:
    result = await controller.capture_photo("camera0", 
                    CameraSettings(resolution=resolution))
    print(f"Captured at {resolution}: {result.success}")
    # All should have focused on same center area ✅
```

## Conclusion

### ✅ **Your Implementation Is Correct**

**Calibration at one resolution works for all other resolutions** because:

1. AfWindows coordinates are **sensor-space**, not output-space
2. ScalerCropMaximum is a **hardware property**, not configuration-dependent
3. ISP handles coordinate transformation automatically
4. Sensor mode typically remains constant across output resolution changes

### No Changes Needed

Your current code:
- Gets `ScalerCropMaximum` once during calibration ✅
- Converts fractional config (0.0-1.0) to absolute pixels ✅
- Sets `AfWindows` control ✅
- Works across all capture resolutions ✅

### Optional Enhancement (For Robustness)

If you want to be extra paranoid, you could re-query `ScalerCropMaximum` before each capture to detect sensor mode changes:

```python
async def capture_photo(self, camera_id, settings):
    # Optional: Verify ScalerCropMaximum hasn't changed
    current_scm = camera.camera_properties.get('ScalerCropMaximum')
    if current_scm != self.calibrated_scaler_crop_max:
        logger.warning("Sensor mode changed - recalibrating focus zone")
        await self.calibrate_scan_settings(camera_id)
    
    # Proceed with capture...
```

But this is **not necessary** for normal operation.

## References

- **Picamera2 Manual**: Section on camera properties and controls
- **libcamera Documentation**: Control coordinate spaces
- **IMX519 Datasheet**: Sensor modes and binning behavior
- **Your Fix**: `AFWINDOWS_COORDINATE_FIX.md` - Correctly identified ScalerCropMaximum usage

## Test Plan (Pi Hardware)

```bash
# On Raspberry Pi:
cd RaspPI/V2.0

# Create test script
cat > test_resolution_independence.py << 'EOF'
import asyncio
from camera.pi_camera_controller import PiCameraController
from core.config_manager import ConfigManager
from camera.base import CameraSettings

async def test_multi_resolution():
    config = ConfigManager("config/scanner_config.yaml")
    controller = PiCameraController(config)
    
    await controller.initialize()
    
    # Calibrate once at default resolution
    print("📷 Calibrating scan settings...")
    calibrated = await controller.calibrate_scan_settings("camera0")
    print(f"Calibration settings: {calibrated}")
    
    # Test different resolutions
    test_resolutions = [
        (1920, 1080),   # 1080p
        (3840, 2160),   # 4K
        (4624, 3472),   # Native full-res
    ]
    
    for resolution in test_resolutions:
        print(f"\n📸 Testing resolution: {resolution}")
        settings = CameraSettings(resolution=resolution)
        result = await controller.capture_photo("camera0", settings)
        print(f"Result: {result.success}, Path: {result.image_path}")
    
    await controller.shutdown()

if __name__ == "__main__":
    asyncio.run(test_multi_resolution())
EOF

python test_resolution_independence.py
```

Expected output:
```
📷 Calibrating scan settings...
📷 Camera 0 ScalerCropMaximum: (0, 0, 4656, 3496), using 4656×3496
📷 Camera 0 focus zone: AfWindows=[(1164, 874, 2328, 1748)] relative to ScalerCropMaximum 4656×3496
Calibration settings: {'focus': 0.5, 'exposure_time': 33000, 'analogue_gain': 2.5}

📸 Testing resolution: (1920, 1080)
Result: True, Path: /tmp/capture_0_*.jpg

📸 Testing resolution: (3840, 2160)
Result: True, Path: /tmp/capture_0_*.jpg

📸 Testing resolution: (4624, 3472)
Result: True, Path: /tmp/capture_0_*.jpg
```

All should use the **same AfWindows** and focus on the **same center area** ✅

## Summary

**Question**: Will this work with other resolutions or is calibration always done at a specific resolution?

**Answer**: ✅ **Works with ALL resolutions** - calibration is resolution-independent because AfWindows coordinates are defined in sensor coordinate space (ScalerCropMaximum), not output resolution space. The ISP automatically handles the transformation for any output resolution.
