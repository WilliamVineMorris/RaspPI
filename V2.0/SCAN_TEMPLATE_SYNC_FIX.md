# Scan Template Synchronization Fix - Summary

## Problem Identified
The scan positions file (e.g., `52352_20250927_225230_scan_positions.json`) contained template/default camera settings that didn't match the actual calibrated values used during scanning:

**Before Fix (Template Values):**
```json
"camera_settings": {
  "exposure_time": 0.1,        // Template default
  "iso": 200,                  // Template default  
  "resolution": [4624, 3472]   // Wrong resolution
}
```

**After Fix (Actual Values):**
```json
"camera_settings": {
  "exposure_time": "1/30s",    // Real calibrated value
  "iso": 800,                  // Real calibrated value
  "resolution": [4608, 2592]   // Correct ArduCam 64MP resolution
}
```

## Changes Made

### 1. Enhanced `_generate_scan_positions_file()` Method
- **File**: `scanning/scan_orchestrator.py`
- **New Function**: `_get_actual_camera_settings()` 
- **Purpose**: Retrieves actual calibrated camera settings instead of template values

### 2. Improved Camera Settings Retrieval
- Reads calibrated settings from `camera_controller._calibrated_settings`
- Converts microsecond exposure times to readable fractions (e.g., 32746μs → "1/30s")
- Converts analogue gain to ISO equivalent (e.g., 8.0 → 800 ISO)
- Provides sensible fallbacks when calibration not available

### 3. Resolution Correction
- **Files**: `core/types.py`, `scanning/scan_patterns.py`
- **Changed**: `(4624, 3472)` → `(4608, 2592)`
- **Reason**: Match actual ArduCam 64MP hardware specifications

### 4. Enhanced Metadata Traceability
Added `camera_settings_info` section to track source of camera settings:
```json
"camera_settings_info": {
  "settings_source": "camera_calibrated",
  "settings_generated_at": "2025-09-27T...",
  "note": "Camera settings reflect actual calibrated values from scan execution, not template defaults"
}
```

## Benefits

### 1. Accurate Documentation
- Scan positions file now accurately reflects real camera settings used
- No more confusion between template and actual values
- Proper scientific documentation for reproducibility

### 2. Troubleshooting Aid
- Easy to verify if calibration was actually used
- Clear indication of settings source (calibrated vs default vs error)
- Helps identify if exposure consistency issues are from calibration problems

### 3. Future Scan Planning
- Can use previous scan's actual settings as reference
- Better estimation of scan quality and lighting conditions
- Enables more accurate scan replication

## Calibration Source Types
The system now tracks and reports the source of camera settings:

- `"camera_calibrated"` - Settings from successful camera calibration
- `"no_calibration_available"` - No calibration found, using sensible defaults
- `"controller_unavailable"` - Camera controller not accessible
- `"default_values"` - Using system default values
- `"error_<ErrorType>"` - Error occurred during settings retrieval

## Example Output
When generating scan positions file, the system now logs:
```
📋 Scan positions saved to: /path/to/52352_20250927_225230_scan_positions.json
📸 Camera settings in scan positions file: Exposure: 1/30s, ISO: 800, Resolution: [4608, 2592], Source: camera_calibrated
```

## Testing on Pi Hardware
To verify the fix works correctly:

1. **Start a new scan** after calibration
2. **Check the scan positions file** for correct settings
3. **Verify consistency** between positions file and actual image metadata
4. **Confirm resolution** matches actual camera output (4608x2592)

The scan positions file should now perfectly match the actual camera settings used during scanning, eliminating the template vs reality discrepancy identified in the metadata analysis.