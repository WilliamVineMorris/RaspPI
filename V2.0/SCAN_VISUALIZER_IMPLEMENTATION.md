# Scan Path Visualizer & CSV Import/Export Implementation

## Overview
Adding 3D path visualization with Plotly.js and CSV import/export functionality to the scanner web interface.

## Features Implemented

### 1. CSV Import/Export
- **Simple CSV format**: `index,x,y,z,c`
- **Export**: Download current scan pattern as CSV
- **Import**: Upload custom CSV with validation
- **Validation**: Check against hardware limits, reject with detailed errors (max 5 shown)
- **Session storage**: No persistence, cleared on page refresh

### 2. 3D Path Visualizer (Plotly.js)
- **Coordinate system**: Cylindrical (X=horizontal, Y=vertical, Z=rotation around Y-axis)
- **Conversion**: Cylindrical → Cartesian for Plotly display
- **Path visualization**: Lines connecting points in sequence order
- **Color coding**: Gradient from blue (start) to red (end)
- **Camera tilt**: Shown as lines from point to central axis
- **Updates**: On parameter change or CSV upload (not continuous)

### 3. UI Layout Changes
- **2-column layout** for scan configuration
- **Left column**: Scan parameters and controls
- **Right column**: 3D visualizer (top) 
- **No point table**: Points not displayed (can be extensive)

## Architecture

### Backend Changes

#### 1. New Endpoints (`web/web_interface.py`)
```python
@app.route('/api/scan/export_csv', methods=['POST'])
- Takes current scan configuration
- Generates points using pattern
- Returns CSV file download

@app.route('/api/scan/import_csv', methods=['POST'])
- Accepts CSV file upload
- Validates all points against hardware limits
- Returns validation results + point data for visualizer

@app.route('/api/scan/preview', methods=['POST'])
- Takes scan configuration (pattern or CSV)
- Generates preview points
- Returns point data for visualization (no execution)
```

#### 2. CSV Validation Module (`scanning/csv_validator.py`)
```python
class ScanPointValidator:
    def __init__(self, hardware_limits: Dict):
        # Load from scanner_config.yaml axes limits
        
    def validate_points(self, points: List[Dict]) -> ValidationResult:
        # Check each point against X, Y, Z, C limits
        # Return errors (max 5), warnings, valid points
        
    def points_to_csv(self, points: List[ScanPoint]) -> str:
        # Convert ScanPoint objects to CSV string
        
    def csv_to_points(self, csv_data: str) -> List[Dict]:
        # Parse CSV, validate format
        # Return list of point dictionaries
```

#### 3. Custom CSV Pattern (`scanning/scan_patterns.py`)
```python
class CustomCSVPattern(ScanPattern):
    def __init__(self, points: List[Dict], pattern_id: str = "custom_csv"):
        # Store points from CSV
        self.custom_points = points
        
    def generate_points(self) -> List[ScanPoint]:
        # Convert dict points to ScanPoint objects
        # Apply safety validation
        # Return scan-ready points
```

### Frontend Changes

#### 1. UI Layout (`templates/cylindrical_scan_panel.html`)
```html
<div class="scan-config-container">
    <!-- Left Column: Parameters -->
    <div class="scan-params-column">
        <!-- Existing scan configuration -->
        <!-- Add CSV upload/download buttons -->
    </div>
    
    <!-- Right Column: Visualizer -->
    <div class="scan-visualizer-column">
        <div id="scan-path-3d-plot"></div>
        <div class="visualizer-info">
            Points: <span id="viz-point-count"></span>
            Range: <span id="viz-range-info"></span>
        </div>
    </div>
</div>
```

#### 2. Plotly Visualizer (`templates/cylindrical_scan_panel.html` - JavaScript)
```javascript
// Load Plotly.js from CDN
<script src="https://cdn.plotly.ly/plotly-2.27.0.min.js"></script>

function cylindricalToCartesian(x, y, z_rotation) {
    // Convert scanner coordinates to Cartesian for Plotly
    const z_rad = z_rotation * Math.PI / 180;
    return {
        x: x * Math.cos(z_rad),  // X position in horizontal plane
        y: y,                     // Y stays vertical
        z: x * Math.sin(z_rad)    // Z completes the rotation
    };
}

function visualizeScanPath(points) {
    // Convert points to Cartesian
    const cartesian = points.map(p => cylindricalToCartesian(p.x, p.y, p.z));
    
    // Extract coordinates
    const x_coords = cartesian.map(p => p.x);
    const y_coords = cartesian.map(p => p.y);
    const z_coords = cartesian.map(p => p.z);
    
    // Create color gradient (blue → red)
    const colors = points.map((p, i) => i / (points.length - 1));
    
    // Plot configuration
    const trace = {
        x: x_coords,
        y: y_coords,
        z: z_coords,
        mode: 'lines+markers',
        type: 'scatter3d',
        marker: {
            size: 4,
            color: colors,
            colorscale: 'Portland',  // Blue to red
            showscale: true
        },
        line: {
            color: colors,
            colorscale: 'Portland',
            width: 2
        },
        hovertemplate: 'X: %{x:.1f}mm<br>Y: %{y:.1f}mm<br>Z: %{z:.1f}mm<extra></extra>'
    };
    
    // Camera tilt lines (if needed)
    const tiltLines = addCameraTiltVisualization(points);
    
    const layout = {
        title: '3D Scan Path Preview',
        scene: {
            xaxis: {title: 'X (mm) - Horizontal'},
            yaxis: {title: 'Y (mm) - Vertical'},
            zaxis: {title: 'Z (mm) - Rotation Plane'},
            camera: {
                eye: {x: 1.5, y: 1.5, z: 1.2}  // Nice viewing angle
            }
        },
        height: 500,
        margin: {l: 0, r: 0, b: 0, t: 40}
    };
    
    Plotly.newPlot('scan-path-3d-plot', [trace, ...tiltLines], layout);
}

function updateVisualizerFromConfig() {
    const config = getCylindricalScanConfig();
    
    // Send to preview endpoint
    fetch('/api/scan/preview', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(config)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            visualizeScanPath(data.points);
            updateVisualizerInfo(data.points);
        }
    });
}

function exportScanCSV() {
    const config = getCylindricalScanConfig();
    
    fetch('/api/scan/export_csv', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(config)
    })
    .then(response => response.blob())
    .then(blob => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `scan_${config.scan_name}_${Date.now()}.csv`;
        a.click();
    });
}

function importScanCSV(file) {
    const formData = new FormData();
    formData.append('csv_file', file);
    
    fetch('/api/scan/import_csv', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            displayNotification(`✅ CSV imported: ${data.point_count} valid points`, 'success');
            visualizeScanPath(data.points);
            updateVisualizerInfo(data.points);
            
            // Store in session for scan execution
            sessionStorage.setItem('custom_scan_points', JSON.stringify(data.points));
        } else {
            // Show validation errors (max 5)
            let errorMsg = `❌ CSV validation failed:\n`;
            data.errors.forEach((err, i) => {
                if (i < 5) errorMsg += `\nRow ${err.row}: ${err.message}`;
            });
            if (data.errors.length > 5) {
                errorMsg += `\n... and ${data.errors.length - 5} more errors`;
            }
            alert(errorMsg);
        }
    });
}
```

## File Changes Summary

### New Files
1. `scanning/csv_validator.py` - CSV validation and conversion
2. `SCAN_VISUALIZER_IMPLEMENTATION.md` - This document

### Modified Files
1. `web/web_interface.py` - Add 3 new endpoints
2. `scanning/scan_patterns.py` - Add CustomCSVPattern class
3. `web/templates/cylindrical_scan_panel.html` - 2-column layout + visualizer
4. `web/templates/base.html` - Add Plotly.js CDN link

## CSV Format

### Simple Format (Current Implementation)
```csv
index,x,y,z,c
0,150.0,80.0,0.0,-25.0
1,150.0,120.0,0.0,-36.3
2,150.0,80.0,90.0,-25.0
3,150.0,120.0,90.0,-36.3
```

### Future Extended Format (Easy to Add)
```csv
index,x,y,z,c,focus,exposure_ms,led_brightness,notes
0,150.0,80.0,0.0,-25.0,auto,100,30,first_point
1,150.0,120.0,0.0,-36.3,auto,100,30,
```

## Validation Rules

### Point Validation
- ✅ `x` within `scanner_config.yaml` → `axes.x.limits[min, max]`
- ✅ `y` within `axes.y.limits[min, max]`
- ✅ `z` within `axes.z.limits[min, max]` (typically 0-360°)
- ✅ `c` within `axes.c.limits[min, max]` (typically ±90°)
- ✅ Sequential indices (0, 1, 2... no gaps)
- ⚠️ Warn if points within 1mm of limits
- ❌ Reject entire CSV if any point exceeds limits

### Error Reporting
- Show first 5 validation errors
- Format: `Row X: Y-coordinate 250.0 exceeds maximum limit of 200.0`
- Reject upload if errors found
- Allow upload if only warnings (points close to limits)

## Testing Plan

### 1. CSV Export
- Generate cylindrical pattern
- Export to CSV
- Verify format matches specification
- Check all coordinates match generated points

### 2. CSV Import
- Valid CSV: Should import and visualize
- Invalid CSV (out of bounds): Should reject with clear errors
- Malformed CSV: Should catch parsing errors
- Empty CSV: Should reject

### 3. Visualizer
- Pattern generation: Should show path in 3D
- CSV import: Should update visualization
- Parameter changes: Should trigger re-render
- Camera tilt: Should show tilt indicators

### 4. Scan Execution
- CSV-imported scan should execute correctly
- Points should match CSV values
- Hardware limits should be respected

## Future Enhancements (Not in This Implementation)

- ❌ Editable point table (read-only for now)
- ❌ Per-point focus/exposure settings (CSV format supports, code doesn't use yet)
- ❌ Saved custom patterns (session-only for now)
- ❌ Path optimization algorithms
- ❌ Collision detection visualization
- ❌ Real-time position tracking during scan (would need websocket updates)

## Performance Considerations

### Plotly.js
- **Size**: ~3MB (CDN cached across internet)
- **Rendering**: Hardware accelerated WebGL
- **Points**: Efficient up to ~10,000 points
- **Updates**: Only on user action, not continuous

### CSV Processing
- **Server-side**: Pandas for efficient CSV parsing
- **Validation**: O(n) single pass through points
- **Memory**: Points kept in session storage only

### Browser Compatibility
- Plotly.js works on all modern browsers
- No IE11 support needed (Pi uses Chromium)
- WebGL required (available on Pi browser)
