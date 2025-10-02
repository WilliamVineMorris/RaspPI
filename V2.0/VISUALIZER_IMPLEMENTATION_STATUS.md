# Scan Path Visualizer - Implementation Status

## ✅ COMPLETED - Backend Implementation

### 1. CSV Validation Module (`scanning/csv_validator.py`)
- ✅ `ScanPointValidator` class created
- ✅ Hardware limits validation against `scanner_config.yaml` axes
- ✅ CSV parsing and format validation
- ✅ Error reporting (max 5 errors displayed)
- ✅ Warning system for points close to limits
- ✅ Conversion between ScanPoint objects and CSV format

### 2. Custom CSV Pattern (`scanning/scan_patterns.py`)
- ✅ `CustomCSVPattern` class added
- ✅ Extends base `ScanPattern` class
- ✅ Loads points from validated CSV data
- ✅ Integrates with existing pattern system
- ✅ Generates ScanPoint objects from CSV dictionaries

### 3. Backend API Endpoints (`web/web_interface.py`)
- ✅ `/api/scan/preview` (POST) - Generate preview points for visualization
- ✅ `/api/scan/export_csv` (POST) - Export current pattern as CSV download
- ✅ `/api/scan/import_csv` (POST) - Upload and validate CSV file
- ✅ Helper methods:
  - `_create_pattern_from_config()` - Create pattern objects from web config
  - `_generate_preview_points()` - Generate points for visualization

## ⏳ PENDING - Frontend Implementation

### 1. Add Plotly.js to Base Template
**File**: `web/templates/base.html`
**Action**: Add CDN link in `<head>` section

```html
<!-- Add before closing </head> tag -->
<script src="https://cdn.plotly.ly/plotly-2.27.0.min.js"></script>
```

### 2. Update Cylindrical Scan Panel Layout
**File**: `web/templates/cylindrical_scan_panel.html`

**Changes Needed**:
1. **Split into 2-column layout**:
   - Left column: Existing scan parameters
   - Right column: 3D visualizer + CSV controls

2. **Add CSV Import/Export Buttons**:
   ```html
   <div class="csv-controls">
       <input type="file" id="csv-upload" accept=".csv" style="display:none" onchange="handleCSVUpload(event)">
       <button onclick="document.getElementById('csv-upload').click()">📁 Import CSV</button>
       <button onclick="exportScanCSV()">💾 Export CSV</button>
   </div>
   ```

3. **Add 3D Visualizer Container**:
   ```html
   <div class="scan-visualizer-column">
       <div id="scan-path-3d-plot" style="width:100%; height:500px;"></div>
       <div class="visualizer-info">
           <span>Points: <strong id="viz-point-count">0</strong></span>
           <span>Range: <span id="viz-range-info">-</span></span>
       </div>
   </div>
   ```

4. **Add JavaScript Functions**:
   ```javascript
   // Cylindrical to Cartesian conversion
   function cylindricalToCartesian(x, y, z_rotation) {
       const z_rad = z_rotation * Math.PI / 180;
       return {
           x: x * Math.cos(z_rad),
           y: y,
           z: x * Math.sin(z_rad)
       };
   }
   
   // Main visualization function
   function visualizeScanPath(points) {
       // Convert to Cartesian
       const cartesian = points.map(p => cylindricalToCartesian(p.x, p.y, p.z));
       
       // Extract coordinates
       const x_coords = cartesian.map(p => p.x);
       const y_coords = cartesian.map(p => p.y);
       const z_coords = cartesian.map(p => p.z);
       
       // Color gradient (blue to red)
       const colors = points.map((p, i) => i / (points.length - 1));
       
       // Create trace
       const trace = {
           x: x_coords,
           y: y_coords,
           z: z_coords,
           mode: 'lines+markers',
           type: 'scatter3d',
           marker: {
               size: 4,
               color: colors,
               colorscale: 'Portland',
               showscale: true,
               colorbar: {title: 'Scan Progress'}
           },
           line: {
               color: colors,
               colorscale: 'Portland',
               width: 2
           },
           hovertemplate: '<b>Point %{pointNumber}</b><br>' +
                          'X: %{x:.1f}mm<br>' +
                          'Y: %{y:.1f}mm<br>' +
                          'Z: %{z:.1f}mm<br>' +
                          '<extra></extra>'
       };
       
       // Layout
       const layout = {
           title: '3D Scan Path Preview',
           scene: {
               xaxis: {title: 'X (mm) - Horizontal'},
               yaxis: {title: 'Y (mm) - Vertical'},
               zaxis: {title: 'Z (mm) - Rotation Plane'},
               camera: {
                   eye: {x: 1.5, y: 1.5, z: 1.2}
               }
           },
           height: 500,
           margin: {l: 0, r: 0, b: 0, t: 40}
       };
       
       Plotly.newPlot('scan-path-3d-plot', [trace], layout);
       
       // Update info
       document.getElementById('viz-point-count').textContent = points.length;
       const x_range = `X: [${Math.min(...points.map(p=>p.x)).toFixed(1)}, ${Math.max(...points.map(p=>p.x)).toFixed(1)}]mm`;
       const y_range = `Y: [${Math.min(...points.map(p=>p.y)).toFixed(1)}, ${Math.max(...points.map(p=>p.y)).toFixed(1)}]mm`;
       document.getElementById('viz-range-info').textContent = `${x_range}, ${y_range}`;
   }
   
   // Update visualizer when parameters change
   function updateVisualizerFromConfig() {
       const config = getCylindricalScanConfig();
       
       fetch('/api/scan/preview', {
           method: 'POST',
           headers: {'Content-Type': 'application/json'},
           body: JSON.stringify(config)
       })
       .then(response => response.json())
       .then(data => {
           if (data.success) {
               visualizeScanPath(data.points);
           }
       })
       .catch(error => console.error('Visualization error:', error));
   }
   
   // CSV Export
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
           a.download = `scan_${config.scan_name || 'pattern'}_${Date.now()}.csv`;
           document.body.appendChild(a);
           a.click();
           document.body.removeChild(a);
           window.URL.revokeObjectURL(url);
           displayNotification('✅ CSV exported successfully!', 'success');
       })
       .catch(error => {
           displayNotification(`❌ Export failed: ${error.message}`, 'error');
       });
   }
   
   // CSV Import
   function handleCSVUpload(event) {
       const file = event.target.files[0];
       if (!file) return;
       
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
               
               // Show warnings if any
               if (data.warnings && data.warnings.length > 0) {
                   let warnings = data.warnings.map(w => `Row ${w.row}: ${w.message}`).join('\n');
                   console.warn('CSV Import Warnings:\n' + warnings);
               }
               
               // Visualize imported points
               visualizeScanPath(data.points);
               
               // Store in session for scanning
               sessionStorage.setItem('custom_scan_points', JSON.stringify(data.points));
               
           } else {
               // Show validation errors (max 5)
               let errorMsg = `❌ CSV validation failed (${data.error_count} errors):\n\n`;
               data.errors.forEach((err, i) => {
                   errorMsg += `Row ${err.row}, ${err.column}: ${err.message}\n`;
               });
               if (data.error_count > 5) {
                   errorMsg += `\n... and ${data.error_count - 5} more errors`;
               }
               alert(errorMsg);
           }
       })
       .catch(error => {
           displayNotification(`❌ Import failed: ${error.message}`, 'error');
       });
       
       // Reset file input
       event.target.value = '';
   }
   
   // Hook into existing parameter change events
   document.addEventListener('DOMContentLoaded', function() {
       // Update visualizer when "Preview Scan" button is clicked
       const previewBtn = document.getElementById('preview-scan');
       if (previewBtn) {
           previewBtn.addEventListener('click', function(e) {
               e.preventDefault();
               updateVisualizerFromConfig();
           });
       }
       
       // Initial visualization
       updateVisualizerFromConfig();
   });
   ```

### 3. CSS Styling for 2-Column Layout
**File**: `web/templates/cylindrical_scan_panel.html` (or shared CSS file)

```css
.scan-config-container {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1.5rem;
    margin-top: 1rem;
}

.scan-params-column {
    /* Existing parameter controls */
}

.scan-visualizer-column {
    background: white;
    border-radius: 8px;
    padding: 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.csv-controls {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
}

.csv-controls button {
    padding: 0.5rem 1rem;
    border: 1px solid #ddd;
    border-radius: 4px;
    background: white;
    cursor: pointer;
    transition: all 0.2s;
}

.csv-controls button:hover {
    background: #f5f5f5;
    border-color: #667eea;
}

.visualizer-info {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: #f8f9fa;
    border-radius: 4px;
    font-size: 0.9rem;
    display: flex;
    justify-content: space-between;
}

#scan-path-3d-plot {
    border: 1px solid #e0e0e0;
    border-radius: 4px;
}
```

## 🧪 Testing Plan

### Backend Testing
1. **Test CSV Export**:
   ```bash
   curl -X POST http://localhost:5000/api/scan/preview \
     -H "Content-Type: application/json" \
     -d '{"pattern":"cylindrical","radius":150,"y_min":80,"y_max":120,"height_steps":2,"rotation_positions":4,"c_angles":[0]}'
   ```

2. **Test CSV Import** (create test.csv first):
   ```csv
   index,x,y,z,c
   0,150.0,80.0,0.0,-25.0
   1,150.0,120.0,0.0,-36.3
   2,150.0,80.0,90.0,-25.0
   ```

### Frontend Testing
1. Open web interface at `http://localhost:5000/scans`
2. Configure cylindrical scan parameters
3. Click "Preview Scan" - should show 3D visualization
4. Click "Export CSV" - should download CSV file
5. Click "Import CSV" - upload the exported file, should visualize and validate

## 📝 User Workflow

### Standard Pattern Workflow:
1. User configures scan parameters (radius, height, rotations)
2. Click "Preview Scan" → See 3D visualization
3. Adjust parameters → Preview updates
4. Click "Export CSV" → Save pattern for later
5. Click "Start Scan" → Execute scan

### Custom CSV Workflow:
1. User creates CSV file externally (Excel, Python, etc.)
2. Click "Import CSV" → Upload file
3. System validates against hardware limits
4. If valid → Show 3D visualization
5. Click "Start Scan" → Execute custom pattern

## 🔧 Integration with Existing Scan Start

The scan start flow needs minor modification to support CSV-imported patterns:

```javascript
// In startCylindricalScan() function:
function startCylindricalScan() {
    // Check if we have custom CSV points in session
    const customPoints = sessionStorage.getItem('custom_scan_points');
    
    let config;
    if (customPoints) {
        // Use custom CSV pattern
        config = {
            pattern: 'custom',
            custom_points: JSON.parse(customPoints),
            scan_name: document.getElementById('scan-name')?.value || 'Custom_CSV_Scan'
        };
    } else {
        // Use standard cylindrical pattern
        config = getCylindricalScanConfig();
    }
    
    // Send to backend (existing code continues...)
    fetch('/api/scan/start', {...});
}
```

## 📚 Documentation for Users

### CSV Format Specification
```
Required columns: index, x, y, z, c
- index: Sequential point number (0, 1, 2, ...)
- x: Horizontal position in mm (0-200)
- y: Vertical position in mm (0-200)
- z: Rotation angle in degrees (0-360)
- c: Camera tilt angle in degrees (-90 to +90)

Example:
index,x,y,z,c
0,150.0,80.0,0.0,-25.0
1,150.0,120.0,0.0,-36.3
2,150.0,80.0,90.0,-25.0
```

### Hardware Limits (from scanner_config.yaml)
- X axis: 0-200mm
- Y axis: 0-200mm
- Z axis: 0-360° (rotational)
- C axis: -90 to +90° (camera tilt)

Points exceeding these limits will be rejected during CSV import.

## 🎯 Next Steps

1. **Implement frontend changes** in `cylindrical_scan_panel.html`
2. **Test on Pi hardware** with real scanner
3. **User acceptance testing** with sample CSV files
4. **Future enhancements**:
   - Camera tilt visualization (lines from points to axis)
   - Real-time position tracking during scans
   - Path optimization algorithms
   - Collision detection warnings

## ⚠️ Remember Testing Protocol
As per project guidelines:
- **NEVER run Pi-specific code locally**
- **ALWAYS wait for user testing on actual Pi hardware**
- **Backend is ready** - frontend needs implementation and testing on Pi
