# CSV Import/Export Fix - Multi-Format Support

## Issues Resolved

### 1. CSV Import Crash (NoneType Error)
**Problem**: Exported CSV files couldn't be re-imported
- Export was using new multi-format handler (camera-relative coordinates: `radius, height, rotation, tilt`)
- Import was using old validator (expecting FluidNC coordinates: `x, y, z, c`)
- Column mismatch caused `float() argument must be a string or a real number, not 'NoneType'` error

**Solution**: Updated CSV import to use `MultiFormatCSVHandler` with auto-format detection

### 2. Preview Switching Between Cylindrical and Custom CSV
**Problem**: How does the preview handle switching between generated cylindrical patterns and imported CSV patterns?

**Solution**: The preview checks for `custom_points` in the pattern data and handles both cases appropriately

## How It Works Now

### CSV Export Flow

```
User clicks "Export CSV"
    ↓
Collect scan parameters (radius, heights, rotations, tilt)
    ↓
Generate ScanPoints (FluidNC coordinates internally)
    ↓
MultiFormatCSVHandler.export_to_csv()
    ↓
Format: CAMERA_RELATIVE (default)
    ↓
CSV with columns: index, radius, height, rotation, tilt
    ↓
Download file
```

### CSV Import Flow (Fixed)

```
User uploads CSV file
    ↓
Read CSV content
    ↓
MultiFormatCSVHandler.import_from_csv()
    ↓
Auto-detect format from headers:
  - camera-relative: radius, height, rotation, tilt
  - FluidNC: x, y, z, c (machine coordinates)
  - Cartesian: x, y, z, c (world coordinates)
    ↓
Convert to ScanPoints (FluidNC internal format)
    ↓
Convert back to camera-relative for preview
    ↓
Return preview points: x=radius, y=height, z=rotation, c=tilt
    ↓
Store in sessionStorage as 'customScanPoints'
    ↓
Visualization updates
```

### Preview Pattern Switching

The `_generate_preview_points()` function handles both cases:

**Case 1: Custom CSV Pattern**
```python
if 'custom_points' in pattern_data:
    # CSV import - return points directly
    return pattern_data['custom_points']
```
- Uses points from imported CSV
- No pattern generation needed
- Points already in correct format for frontend

**Case 2: Cylindrical Pattern**
```python
else:
    # Generate preview directly from user input
    # Calculate points based on radius, heights, rotations
    for rotation in z_rotations:
        for height_idx, y_pos in enumerate(y_positions):
            preview_points.append({
                'x': radius,
                'y': y_pos,
                'z': rotation,
                'c': c_angles[height_idx]
            })
```
- Generates points from UI parameters
- Matches actual scan order (rotation first, then height)
- Shows exactly what will be scanned

## Code Changes

### File: `web/web_interface.py`

#### CSV Import API (Lines 1450-1545)

**Before:**
```python
# Used old csv_validator expecting x,y,z,c columns
validator = ScanPointValidator(axes_config)
validation_result = validator.validate_csv_file(csv_content)
```

**After:**
```python
# Uses multi-format CSV handler with auto-detection
if self.csv_handler:
    import_result = self.csv_handler.import_from_csv(csv_content)
    
    # Convert ScanPoints to preview format
    for i, scan_point in enumerate(import_result.points):
        if self.coord_transformer:
            camera_pos = self.coord_transformer.fluidnc_to_camera(scan_point.position)
            preview_points.append({
                'x': camera_pos.radius,
                'y': camera_pos.height,
                'z': camera_pos.rotation,
                'c': camera_pos.tilt
            })
```

## Coordinate Format Support

### Camera-Relative (Default Export)
```csv
index,radius,height,rotation,tilt
0,30.0,40.0,0.0,8.5
1,30.0,66.7,0.0,2.2
2,30.0,93.3,0.0,-4.0
3,30.0,120.0,0.0,-10.3
```
**Use**: User-friendly, matches UI parameters

### FluidNC (Machine Coordinates)
```csv
index,x,y,z,c
0,60.0,30.0,0.0,8.5
1,60.0,56.7,0.0,2.2
2,60.0,83.3,0.0,-4.0
3,60.0,110.0,0.0,-10.3
```
**Use**: Direct machine commands (with offsets applied)

### Cartesian (World Coordinates)
```csv
index,x,y,z,c
0,60.0,0.0,20.0,8.5
1,60.0,0.0,46.7,2.2
2,60.0,0.0,73.3,-4.0
3,60.0,0.0,100.0,-10.3
```
**Use**: 3D spatial analysis, external software

## Frontend Data Flow

### Session Storage Management

**After CSV Import:**
```javascript
// Store custom points in session storage
sessionStorage.setItem('customScanPoints', JSON.stringify(result.points));

// Trigger visualization update
updateScanVisualizer();
```

**Collecting Scan Parameters:**
```javascript
const customPointsJSON = sessionStorage.getItem('customScanPoints');
if (customPointsJSON) {
    const customPoints = JSON.parse(customPointsJSON);
    return {
        pattern_type: 'custom_csv',
        custom_points: customPoints,
        // ...other parameters
    };
}
```

**Switching Back to Cylindrical:**
```javascript
// Clear custom points to return to cylindrical pattern
sessionStorage.removeItem('customScanPoints');
updateScanVisualizer(); // Will regenerate from UI parameters
```

## Usage Workflow

### Export → Import Cycle

1. **Configure cylindrical scan**: radius=30mm, heights=40-120mm, 6 rotations
2. **Generate preview**: Shows 24 points in correct order
3. **Export CSV**: Downloads camera-relative format
4. **Edit CSV** (optional): Modify parameters in spreadsheet
5. **Import CSV**: Upload modified file
6. **Auto-detection**: System detects camera-relative format
7. **Preview updates**: Shows imported points
8. **Run scan**: Uses imported coordinates

### Switching Between Patterns

**To use custom CSV:**
- Import CSV file
- Preview automatically shows imported points
- "Start Scan" button uses custom pattern

**To return to cylindrical:**
- Clear session storage: `sessionStorage.removeItem('customScanPoints')`
- Or refresh the page
- Configure cylindrical parameters
- Preview regenerates from UI

## Benefits

✅ **Format Flexibility**: Export/import in 3 different coordinate systems  
✅ **Auto-Detection**: No need to specify format, automatically detected from headers  
✅ **Round-Trip**: Export → Edit → Import → Scan workflow works perfectly  
✅ **Preview Accuracy**: Shows exactly what will be scanned (camera-relative coords)  
✅ **Backward Compatible**: Falls back to old validator if new handler unavailable  
✅ **Error Handling**: Clear error messages for format mismatches

## Testing

### Test CSV Import/Export
1. Configure scan: radius=30mm, heights=40-120mm, 6 rotations
2. Export CSV
3. Open in text editor → verify headers: `index,radius,height,rotation,tilt`
4. Import same CSV
5. Verify preview shows identical pattern
6. Check console: should show `format_detected: 'camera_relative'`

### Test Pattern Switching
1. Configure cylindrical scan → preview shows generated pattern
2. Import CSV → preview switches to custom points
3. Refresh page → preview returns to cylindrical (session cleared)
4. Import CSV again → back to custom points

---

**Status**: ✅ Fixed - CSV import now works with exported files  
**Format Support**: Camera-relative (default), FluidNC, Cartesian  
**Auto-Detection**: Yes - recognizes format from column headers  
**Preview Switching**: Automatic based on `custom_points` presence
