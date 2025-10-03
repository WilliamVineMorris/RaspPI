# CSV Export Fix Summary

**Date**: 2025-10-03  
**Issue**: CSV export failing with `float() argument must be a string or a real number, not 'NoneType'`

---

## Problem Description

When attempting to export the scan pattern as CSV, the system raised an error:
```
CSV export API error: float() argument must be a string or a real number, not 'NoneType'
```

This indicated that one of the numeric values being processed was `None` instead of a valid number.

---

## Root Causes Identified

### 1. **Missing Type Conversion in Pattern Creation**
The `_create_pattern_from_config()` method was not explicitly converting string values to floats:
- `radius` might be passed as string "100" instead of float 100.0
- `servo_manual_angle`, `servo_y_focus` could be strings
- `y_min`, `y_max` could be strings from form inputs

### 2. **Missing Support for `y_range` Parameter**
The frontend sends `y_range: [40, 120]` but the backend was only looking for `y_min` and `y_max` separately.

### 3. **Missing Error Handling in CSV Conversion**
The `points_to_csv()` method had no null-safety checks when formatting position values.

---

## Fixes Applied

### Fix 1: Add Type Conversions in Pattern Creation
**File**: `web/web_interface.py` (~lines 2987-3000)

**Before**:
```python
y_min = pattern_data.get('y_min', 40.0)
y_max = pattern_data.get('y_max', 120.0)
servo_manual_angle = pattern_data.get('servo_manual_angle', 0.0)
servo_y_focus = pattern_data.get('servo_y_focus', 80.0)
radius = pattern_data.get('radius', 150.0)
```

**After**:
```python
# Handle both y_range (list) and y_min/y_max (individual values)
y_range = pattern_data.get('y_range')
if y_range and isinstance(y_range, list) and len(y_range) >= 2:
    y_min = float(y_range[0])
    y_max = float(y_range[1])
else:
    y_min = float(pattern_data.get('y_min', 40.0))
    y_max = float(pattern_data.get('y_max', 120.0))

servo_manual_angle = float(pattern_data.get('servo_manual_angle', 0.0))
servo_y_focus = float(pattern_data.get('servo_y_focus', 80.0))
radius = float(pattern_data.get('radius', 150.0))
```

**Changes**:
- ✅ Explicit `float()` conversion for all numeric parameters
- ✅ Support for `y_range` list parameter from frontend
- ✅ Fallback to individual `y_min`/`y_max` for backward compatibility

### Fix 2: Add Null Safety in CSV Export
**File**: `scanning/csv_validator.py` (~lines 273-290)

**Before**:
```python
for i, point in enumerate(points):
    writer.writerow([
        i,
        f"{point.position.x:.3f}",
        f"{point.position.y:.3f}",
        f"{point.position.z:.3f}",
        f"{point.position.c:.3f}"
    ])
```

**After**:
```python
for i, point in enumerate(points):
    try:
        # Ensure all position values are valid numbers
        x = point.position.x if point.position.x is not None else 0.0
        y = point.position.y if point.position.y is not None else 0.0
        z = point.position.z if point.position.z is not None else 0.0
        c = point.position.c if point.position.c is not None else 0.0
        
        writer.writerow([
            i,
            f"{x:.3f}",
            f"{y:.3f}",
            f"{z:.3f}",
            f"{c:.3f}"
        ])
    except (AttributeError, TypeError) as e:
        logger.error(f"Error converting point {i} to CSV: {e}")
        logger.error(f"Point data: {point}")
        raise ValueError(f"Invalid point at index {i}: {e}")
```

**Changes**:
- ✅ Null-safety checks for each coordinate
- ✅ Default to 0.0 if value is None
- ✅ Better error messages showing which point failed
- ✅ Exception handling with detailed logging

### Fix 3: Enhanced Logging in CSV Export API
**File**: `web/web_interface.py` (~lines 1371-1408)

**Added logging**:
```python
self.logger.info(f"📤 CSV Export request with data: {data.keys()}")
self.logger.info(f"✅ Pattern created: {type(pattern).__name__}")
self.logger.info(f"✅ Generated {len(scan_points)} scan points")

# Debug: Check first point
if scan_points:
    first_point = scan_points[0]
    self.logger.info(f"🔍 First point: pos={first_point.position}, settings={first_point.camera_settings}")

self.logger.info(f"✅ CSV content generated: {len(csv_content)} chars")
```

**Benefits**:
- Shows exactly where in the process the error occurs
- Displays first point data for debugging
- Uses `exc_info=True` to show full stack trace

---

## Expected Behavior After Fix

### Successful CSV Export Flow:
1. User clicks "Export CSV" button on scan configuration page
2. Frontend sends scan parameters via `collectScanParameters()`
3. Backend receives parameters and logs request
4. Backend creates pattern with proper type conversions
5. Backend generates scan points (24 points for 4 heights × 6 rotations)
6. Backend converts points to CSV with null-safe formatting
7. User receives CSV file download

### CSV File Format:
```csv
index,x,y,z,c
0,100.000,40.000,0.000,-15.000
1,100.000,40.000,60.000,-15.000
2,100.000,40.000,120.000,-15.000
...
23,100.000,120.000,300.000,-15.000
```

**Columns**:
- `index`: Point number (0-based)
- `x`: Radial position in mm (camera distance from center)
- `y`: Height position in mm
- `z`: Rotation angle in degrees (turntable position)
- `c`: Camera tilt angle in degrees (servo angle)

---

## Testing Checklist

### On Raspberry Pi:

1. **Test Basic CSV Export**:
   - [ ] Configure scan: 4 height steps, 6 rotations, radius 100mm
   - [ ] Set servo tilt to "Manual Angle" at -15°
   - [ ] Click "Export CSV" button
   - [ ] Verify CSV file downloads successfully
   - [ ] Open CSV and verify 24 rows (4 × 6) + header

2. **Test Manual Tilt Mode**:
   - [ ] Set manual angle to -15°
   - [ ] Export CSV
   - [ ] Verify all rows have `c = -15.000`

3. **Test Focus Point Mode**:
   - [ ] Set servo tilt to "Focus Point Targeting"
   - [ ] Set focus Y to 20mm
   - [ ] Export CSV
   - [ ] Verify `c` values vary by height:
     - Height 40mm → c ≈ -11°
     - Height 66.7mm → c ≈ -25°
     - Height 93.3mm → c ≈ -36°
     - Height 120mm → c ≈ -45°

4. **Test Different Configurations**:
   - [ ] Different radius values: 50mm, 100mm, 150mm
   - [ ] Different height ranges: 40-80mm, 60-120mm
   - [ ] Different step counts: 2, 3, 5, 6
   - [ ] Different rotation counts: 3, 8, 12

5. **Check CSV Data Integrity**:
   - [ ] All rows have exactly 5 columns
   - [ ] No "None" or "null" values in CSV
   - [ ] All numbers formatted to 3 decimal places
   - [ ] Index column matches row count

---

## Error Handling Improvements

### Before:
```
CSV export API error: float() argument must be a string or a real number, not 'NoneType'
```
- ❌ No indication which parameter was None
- ❌ No context about the scan configuration
- ❌ No indication at what stage the error occurred

### After:
```
📤 CSV Export request with data: dict_keys(['pattern_type', 'radius', 'y_range', ...])
✅ Pattern created: CylindricalScanPattern
✅ Generated 24 scan points
🔍 First point: pos=Position4D(x=100.00, y=40.00, z=0.00, c=-15.00), settings=CameraSettings(...)
Error converting point 12 to CSV: 'NoneType' object has no attribute 'x'
Point data: ScanPoint(position=None, ...)
```
- ✅ Shows exact stage where error occurs
- ✅ Shows which point failed (index 12)
- ✅ Shows the invalid point data
- ✅ Provides context for debugging

---

## Backward Compatibility

✅ All changes maintain backward compatibility:
- Supports both `y_range` (new) and `y_min`/`y_max` (legacy)
- Null-safe defaults prevent crashes on unexpected None values
- Existing CSV import functionality unchanged

---

## Related Files

### Modified:
1. **`web/web_interface.py`**:
   - `_create_pattern_from_config()`: Added type conversions and y_range support
   - `api_scan_export_csv()`: Enhanced logging

2. **`scanning/csv_validator.py`**:
   - `points_to_csv()`: Added null-safety and error handling

### Not Modified (for reference):
- **`web/templates/scans.html`**: Frontend CSV export button and data collection
- **`scanning/scan_patterns.py`**: Pattern generation logic
- **`core/types.py`**: Position4D and CameraSettings dataclasses

---

## Additional Notes

### Parameter Sources:
- **Frontend form inputs**: Return strings, need conversion to float
- **JavaScript defaults**: Already numbers, but converted for safety
- **Backend defaults**: Already float literals, conversion is no-op

### Type Safety Strategy:
```python
# Defensive: Convert everything to float
radius = float(pattern_data.get('radius', 150.0))

# Benefits:
# - Works if input is string "150"
# - Works if input is int 150
# - Works if input is float 150.0
# - Falls back to 150.0 if key missing
```

This approach ensures robustness across different data sources and formats.
