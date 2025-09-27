# Controller Unavailable Issue - Fix Summary

## Problem Identified
The scan positions file was showing `"calibration_source": "controller_unavailable"` instead of actual calibrated camera settings. This occurred because:

1. **Timing Issue**: The `_generate_scan_positions_file()` method was called during scan planning, **before** the camera system was initialized
2. **Initialization Order**: Camera controller wasn't accessible when positions file was generated
3. **Template vs Reality**: The system was falling back to default values instead of waiting for calibration

## Root Cause Analysis
```json
{
  "camera_settings_info": {
    "settings_source": "controller_unavailable",  // ← Problem: Camera not initialized yet
    "note": "Camera controller not available during positions file generation - using sensible defaults"
  }
}
```

The positions file was being generated in the scan initialization phase, but the camera calibration happens later in the scan execution phase.

## Solution Implemented

### 1. **Smart Camera Settings Retrieval**
Enhanced `_get_actual_camera_settings()` method with:
- **Multiple Controller Access Paths**: Tries different ways to access camera controller
- **Contextual Behavior**: Different behavior for planning vs execution phases
- **Better Fallbacks**: Intelligent defaults based on context

```python
async def _get_actual_camera_settings(self, prefer_calibrated: bool = True)
```

### 2. **Two-Phase Positions File Generation**

#### **Phase 1: Initial Generation (Planning Stage)**
```python
# Generate initial positions file with planning defaults
positions_metadata = await self._generate_scan_positions_file(
    pattern, Path(output_directory), scan_id, prefer_calibrated=False
)
```

- Uses `prefer_calibrated=False` during scan planning
- Results in `"calibration_source": "planning_stage_defaults"`
- Includes note that settings will be updated during execution

#### **Phase 2: Update After Calibration**
```python
# After successful camera calibration
await self._update_scan_positions_with_calibration(
    self.current_scan.scan_id, scan_output_dir
)
```

- Updates positions file with actual calibrated values
- Changes source to `"camera_calibrated"`
- Preserves original file structure

### 3. **Enhanced Controller Detection**
The system now tries multiple paths to find the camera controller:
- `self.camera_manager.controller` (CameraManagerAdapter)
- `self.camera_manager._controller` (Alternative path)
- `self.camera_manager.camera_controller` (Direct reference)
- `self.camera_manager` (Direct controller instance)

### 4. **Contextual Status Messages**
Different messages based on when the method is called:
- **Planning Stage**: `"planning_stage_defaults"` - "Using planning defaults"
- **Execution Stage**: `"controller_unavailable"` - "Controller not accessible"
- **Post-Calibration**: `"camera_calibrated"` - "Using actual calibrated values"

## Expected Behavior After Fix

### **Initial Positions File (During Planning)**
```json
{
  "camera_settings_info": {
    "settings_source": "planning_stage_defaults",
    "note": "Camera settings are planning defaults - will be updated with calibrated values during scan execution",
    "will_be_updated": true
  },
  "camera_settings": {
    "exposure_time": "1/30s",
    "iso": 800,
    "calibration_source": "planning_stage_defaults"
  }
}
```

### **Updated Positions File (After Calibration)**
```json
{
  "camera_settings_info": {
    "settings_source": "camera_calibrated",
    "note": "Camera settings updated with actual calibrated values after scan calibration",
    "will_be_updated": false
  },
  "camera_settings": {
    "exposure_time": "1/30s",        // ← Real calibrated value
    "iso": 800,                      // ← Real calibrated value
    "calibration_source": "camera_calibrated",
    "calibration_timestamp": 1759006428.123
  }
}
```

## Testing on Pi Hardware

**To verify the fix works correctly:**

1. **Start a new scan** and check the initial positions file
   - Should show `"planning_stage_defaults"` initially
   - Should indicate `"will_be_updated": true`

2. **Monitor during calibration** for log messages:
   ```
   📋 Updated scan positions file with calibrated settings: Exposure: 1/30s, ISO: 800
   ```

3. **Check final positions file** after calibration
   - Should show `"camera_calibrated"` 
   - Should have `"will_be_updated": false`
   - Should contain actual calibrated values

## Benefits of This Approach

1. **Immediate Planning**: Positions file is available immediately for scan planning
2. **Accurate Documentation**: File is updated with real calibrated values during execution  
3. **Transparent Process**: Clear indication of when and how settings are determined
4. **Robust Fallbacks**: Works even when calibration fails or controller isn't available
5. **Backward Compatible**: Doesn't break existing scan workflows

The system now properly handles the timing between scan planning and camera calibration, ensuring the positions file always reflects the most accurate information available at each stage of the scan process.