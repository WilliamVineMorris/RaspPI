# Scan Focus Fix - Removed Remaining Conversion

## Problem Found in Logs

From your scan logs:
```
2025-10-07 23:04:00,382 - scanning.scan_orchestrator - INFO - 📸 Converted focus 8.1 to normalized 0.525
2025-10-07 23:04:00,383 - camera.pi_camera_controller - INFO - Set LensPosition to 0.5 diopters for camera0
```

**The scan was still converting 8.1 diopters → 0.525 normalized → 0.5 diopters!**

This is why:
- Dashboard worked (sends diopters directly, no conversion)
- Scan was broken (was doing conversion in scan_orchestrator.py)

## The Fix

**File**: `scanning/scan_orchestrator.py` lines ~3522-3547

**Removed:**
```python
# OLD (WRONG):
focus_normalized = (self._web_focus_position - 6.0) / 4.0  # Convert 6-10 to 0-1
focus_normalized = max(0.0, min(1.0, focus_normalized))
success = await self.camera_manager.controller.set_focus_value(camera_id, focus_normalized)
self._scan_focus_values[camera_id] = self._web_focus_position  # Store original
```

**Replaced with:**
```python
# NEW (CORRECT):
focus_diopters = max(0.0, min(15.0, self._web_focus_position))  # Clamp to diopter range
success = await self.camera_manager.controller.set_focus_value(camera_id, focus_diopters)
self._scan_focus_values[camera_id] = focus_diopters  # Store diopters
```

## What Was Happening

1. **Web UI sends**: 8.1 diopters
2. **scan_orchestrator.py was doing**: `(8.1 - 6.0) / 4.0 = 0.525` ❌
3. **Sent to camera**: 0.525 diopters (WAY too low!)
4. **Result**: Blurry images focused at almost infinity

## What Happens Now

1. **Web UI sends**: 8.1 diopters
2. **scan_orchestrator.py does**: Clamps to 0-15 range ✅
3. **Sent to camera**: 8.1 diopters ✅
4. **Result**: Correctly focused images!

## Expected New Logs

After this fix, you should see:
```
📸 Web UI manual focus mode: Using position 8.1 diopters
📸 Using focus 8.1 diopters (higher = closer focus)
Set LensPosition to 8.1 diopters for camera0 (higher = closer)
✅ Set web UI manual focus for camera0: 8.1 diopters
```

**No more "Converted focus" or "normalized" in the logs!**

## Files Changed

- `RaspPI/V2.0/scanning/scan_orchestrator.py` - Removed 6-10→0-1 conversion logic

## Test on Pi

```bash
sudo systemctl restart scanner
# Then start a scan with manual focus 8.1
# Check logs for "Set LensPosition to 8.1 diopters"
# Images should now match dashboard quality!
```
