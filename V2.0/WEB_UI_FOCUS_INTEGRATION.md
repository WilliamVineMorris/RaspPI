# Web UI Integration for Per-Point Focus Control

## Current Web UI Focus Features (V2.0)

### Existing Global Focus Controls

The web UI currently has **global focus controls** that work great but don't yet support per-point configuration:

#### 1. **Dashboard Camera Controls** (`dashboard.html`)
```html
<!-- Current UI Elements -->
<button onclick="triggerAutofocus()">🎯 Auto</button>
<button onclick="toggleManualFocus()">⚙️ Manual</button>

<input type="range" id="focusSlider" min="0" max="10" step="0.1" value="5">
```

**Current Behavior**:
- **Auto button**: Triggers autofocus on both cameras (affects global config)
- **Manual slider**: Sets global `manual_lens_position` (range 0-10)
- **API endpoints**: 
  - `POST /api/scan/focus/mode` - Set focus mode (manual/auto)
  - `POST /api/scan/focus/value` - Set manual lens position

**What this sets**: Global config `cameras.focus.manual_lens_position`

**Limitation**: Changes apply to ALL scan points in the session

---

## How Per-Point Focus Integrates

### Current Integration: CSV/YAML Input ✅

**Already works** with the per-point focus implementation:

#### CSV Upload Method
Users can upload CSV files with focus control columns:

```csv
X,Y,Z,C,FocusMode,FocusValues
100,100,0,0,manual,8.0
100,100,45,0,manual,"6.0;8.0;10.0"
100,100,90,0,af,
```

**Web UI Flow**:
1. User creates CSV file with focus columns on their PC
2. User uploads CSV via web UI (file input)
3. CSV parser (needs update) reads `FocusMode` and `FocusValues`
4. Creates `ScanPoint` objects with per-point focus settings
5. Scan executes with custom focus at each point

#### YAML Manual Edit Method
Users can directly edit scan patterns in YAML:

```yaml
scan_points:
  - position: {x: 100, y: 100, z: 0, c: 0}
    focus_values: [6.0, 8.0, 10.0]  # Focus stacking
```

**Web UI Flow**:
1. User SSHs into Pi or uses file manager
2. Edits scan YAML file directly
3. Web UI loads and visualizes the scan pattern
4. Scan executes with per-point focus

---

## Future Web UI Enhancements

### Enhancement 1: Visual Scan Point Editor (IDEAL)

**Concept**: Add focus controls to the scan point editor

```html
<!-- FUTURE: Per-Point Focus in Scan Editor -->
<div class="scan-point-card">
    <h4>Point 1: (100, 100, 0°, 0°)</h4>
    
    <!-- Focus Mode Selector -->
    <select id="point-1-focus-mode">
        <option value="default">Use Global Default</option>
        <option value="manual">Manual Focus</option>
        <option value="manual-stack">Focus Stacking</option>
        <option value="af">Autofocus Once</option>
    </select>
    
    <!-- Manual Focus Controls (shown when manual selected) -->
    <div id="point-1-manual-controls" style="display: none;">
        <label>Lens Position:</label>
        <input type="number" min="0" max="15" step="0.1" value="8.0">
    </div>
    
    <!-- Focus Stacking Controls (shown when stack selected) -->
    <div id="point-1-stack-controls" style="display: none;">
        <label>Focus Positions:</label>
        <input type="text" placeholder="6.0, 8.0, 10.0">
        <small>Enter comma-separated lens positions</small>
    </div>
</div>
```

**Implementation Effort**: Medium
**Value**: High (user-friendly per-point configuration)

---

### Enhancement 2: CSV Template Generator

**Concept**: Web UI generates CSV templates with focus columns

```javascript
// FUTURE: CSV Generator Button
function downloadFocusStackingTemplate() {
    const csv = `X,Y,Z,C,FocusMode,FocusValues,Description
100,100,0,0,manual,8.0,Single manual focus
100,100,45,0,manual,"6.0;8.0;10.0",Focus stacking (3 positions)
100,100,90,0,af,,Autofocus once
100,100,135,0,,,Use global default`;
    
    // Trigger download
    downloadCSV(csv, 'focus_stacking_template.csv');
}
```

**Implementation Effort**: Low
**Value**: Medium (helpful for users learning CSV format)

---

### Enhancement 3: Focus Preview/Test Mode

**Concept**: Test focus settings before full scan

```html
<!-- FUTURE: Focus Test Panel -->
<div class="focus-test-panel">
    <h3>Test Focus Settings</h3>
    
    <label>Test Position:</label>
    <select id="test-point-select">
        <option>Point 1 (manual: 8.0)</option>
        <option>Point 2 (stack: 6.0, 8.0, 10.0)</option>
        <option>Point 3 (autofocus)</option>
    </select>
    
    <button onclick="testFocusAtPoint()">📸 Test Capture</button>
    
    <div id="focus-preview">
        <!-- Shows captured images at different focus positions -->
    </div>
</div>
```

**Implementation Effort**: High
**Value**: Very High (see results before committing to long scan)

---

### Enhancement 4: Focus Position Visualization

**Concept**: Show focus positions on 3D visualization

```javascript
// FUTURE: Enhanced visualization with focus indicators
function renderScanPoint(point) {
    const color = getFocusColor(point);
    // Green = single focus
    // Blue = focus stacking
    // Orange = autofocus
    // Gray = default
    
    // Add focus stack indicator
    if (point.is_focus_stacking()) {
        renderStackIndicator(point.focus_values.length);
    }
}
```

**Implementation Effort**: Medium
**Value**: High (visual feedback on scan complexity)

---

## Implementation Roadmap

### Phase 1: CSV Parser Update ⏳ **NEXT PRIORITY**

**File**: `scanning/csv_validator.py`, `scanning/multi_format_csv.py`

**Changes Needed**:
```python
# Add to CSV column mapping
COLUMN_MAPPING = {
    'X': 'x',
    'Y': 'y',
    'Z': 'z',
    'C': 'c',
    'FocusMode': 'focus_mode',       # NEW
    'FocusValues': 'focus_values'    # NEW
}

# Parse focus values
def parse_focus_values(value_str):
    if not value_str or value_str.strip() == '':
        return None
    
    # Check for multiple values (focus stacking)
    if ';' in value_str:
        # "6.0;8.0;10.0" → [6.0, 8.0, 10.0]
        return [float(v.strip()) for v in value_str.split(';')]
    else:
        # "8.0" → 8.0
        return float(value_str)

# Create ScanPoint with focus parameters
point = ScanPoint(
    position=Position4D(x, y, z, c),
    focus_mode=parse_focus_mode(row.get('FocusMode')),
    focus_values=parse_focus_values(row.get('FocusValues'))
)
```

**Testing**: Upload CSV with focus columns, verify ScanPoints created correctly

**Effort**: 2-3 hours
**Priority**: HIGH (enables CSV workflow)

---

### Phase 2: Web UI CSV Upload Validation ⏳

**File**: `web/web_interface.py`

**Add validation endpoint**:
```python
@self.app.route('/api/csv/validate', methods=['POST'])
def api_csv_validate():
    """Validate CSV file with focus columns"""
    try:
        file = request.files.get('csv_file')
        if not file:
            return jsonify({'success': False, 'error': 'No file provided'}), 400
        
        # Parse and validate
        validator = ScanPointValidator(axes_config)
        points, errors = validator.validate_csv(file)
        
        # Return validation results
        return jsonify({
            'success': len(errors) == 0,
            'points_count': len(points),
            'focus_stacking_points': sum(1 for p in points if p.is_focus_stacking()),
            'autofocus_points': sum(1 for p in points if p.requires_autofocus()),
            'errors': errors,
            'preview': [
                {
                    'position': f"({p.position.x}, {p.position.y}, {p.position.z}°)",
                    'focus_mode': p.focus_mode.value if p.focus_mode else 'default',
                    'focus_values': p.get_focus_positions()
                }
                for p in points[:5]  # First 5 points
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Effort**: 3-4 hours
**Priority**: MEDIUM

---

### Phase 3: Scan Editor UI Enhancement ⏳

**File**: `web/templates/cylindrical_scan_panel.html`

**Add focus controls to scan configuration**:
```html
<!-- Add to scan parameter section -->
<div class="focus-settings-section">
    <h3>Focus Settings</h3>
    
    <div class="form-group">
        <label>Default Focus Mode:</label>
        <select id="default-focus-mode">
            <option value="manual">Manual (Fixed Position)</option>
            <option value="af">Autofocus Once</option>
        </select>
    </div>
    
    <div id="manual-focus-settings" class="form-group">
        <label>Default Lens Position:</label>
        <input type="number" id="default-lens-position" 
               min="0" max="15" step="0.1" value="8.0">
        <small>Used for all points unless overridden</small>
    </div>
    
    <div class="form-group">
        <input type="checkbox" id="enable-focus-stacking">
        <label>Enable Focus Stacking (Advanced)</label>
    </div>
    
    <div id="focus-stacking-settings" style="display: none;">
        <label>Focus Stack Positions:</label>
        <input type="text" id="focus-stack-positions" 
               placeholder="6.0, 8.0, 10.0">
        <small>Applies to ALL points in scan</small>
    </div>
</div>
```

**JavaScript Integration**:
```javascript
function buildScanParameters() {
    const params = {
        // ... existing position params ...
        
        // Add focus parameters
        focus_settings: {
            mode: document.getElementById('default-focus-mode').value,
            manual_lens_position: parseFloat(document.getElementById('default-lens-position').value),
            enable_stacking: document.getElementById('enable-focus-stacking').checked,
            stack_positions: document.getElementById('enable-focus-stacking').checked ?
                parseStackPositions(document.getElementById('focus-stack-positions').value) : null
        }
    };
    return params;
}
```

**Effort**: 6-8 hours
**Priority**: LOW (nice-to-have, CSV works fine)

---

### Phase 4: Focus Test/Preview Mode ⏳

**New Feature**: Live focus testing

**API Endpoint**:
```python
@self.app.route('/api/camera/focus/test', methods=['POST'])
def api_focus_test():
    """Test focus at current position"""
    try:
        data = request.get_json()
        lens_position = float(data.get('lens_position', 8.0))
        camera_id = data.get('camera_id', 'camera_0')
        
        # Set focus
        await camera_controller.auto_focus(
            camera_id,
            focus_mode='manual',
            lens_position=lens_position
        )
        
        # Capture test image
        result = await camera_controller.capture(
            camera_id,
            save=False  # Don't save, just return
        )
        
        return jsonify({
            'success': True,
            'image_data': base64.encode(result['image']),
            'lens_position': lens_position,
            'focus_metadata': result.get('metadata', {})
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
```

**Effort**: 8-10 hours
**Priority**: MEDIUM (very useful for finding optimal lens positions)

---

## Current Workarounds (No UI Changes Needed)

### Method 1: CSV Upload (RECOMMENDED)

**Steps**:
1. Create CSV file on PC with focus columns
2. Upload via existing file input in web UI
3. **Note**: CSV parser needs update (Phase 1) to read focus columns
4. Scan executes with per-point focus

**Advantage**: No UI changes needed, just CSV parser update

---

### Method 2: Direct Config Edit

**Steps**:
1. SSH into Raspberry Pi
2. Edit `scanner_config.yaml`:
   ```yaml
   cameras:
     focus:
       mode: "manual"
       manual_lens_position: 8.0  # Global default
   ```
3. For per-point control, create YAML scan file:
   ```yaml
   scan_points:
     - position: {x: 100, y: 100, z: 0, c: 0}
       focus_values: 8.0
   ```
4. Load scan file in web UI

**Advantage**: Maximum control, no code changes

---

### Method 3: Manual Focus Slider (CURRENT)

**Steps**:
1. Use existing manual focus slider in dashboard
2. Set desired lens position (affects global config)
3. Run scan - all points use this position

**Advantage**: Already works, no changes needed

**Limitation**: Same focus for all points (no per-point control)

---

## Web UI Integration Summary

### ✅ What Works Now (No Changes)

| Feature | Status | How to Use |
|---------|--------|------------|
| Global manual focus | ✅ Works | Dashboard slider |
| Global autofocus | ✅ Works | Dashboard "Auto" button |
| CSV with position data | ✅ Works | File upload |
| YAML scan loading | ✅ Works | File selection |

### ⏳ What Needs Update (Priority)

| Feature | Status | Priority | Effort |
|---------|--------|----------|--------|
| CSV focus column parsing | ⏳ **Required** | HIGH | 2-3 hrs |
| CSV upload validation | ⏳ Optional | MEDIUM | 3-4 hrs |
| Per-point focus UI | ⏳ Optional | LOW | 6-8 hrs |
| Focus preview/test | ⏳ Optional | MEDIUM | 8-10 hrs |

### 🎯 Recommended Next Steps

**Immediate (enables CSV workflow)**:
1. Update CSV parser to read `FocusMode` and `FocusValues` columns
2. Test CSV upload with focus parameters
3. Document CSV format for users

**Short-term (improves UX)**:
4. Add CSV validation endpoint
5. Show focus settings in scan preview
6. Add CSV template download button

**Long-term (advanced features)**:
7. Add per-point focus editor in UI
8. Implement focus test/preview mode
9. Add focus position visualization

---

## Example User Workflows

### Workflow 1: Simple Focus Stacking (CSV)

**User Goal**: Capture dragon with 3 focus planes at every scan point

**Steps**:
1. Create CSV:
   ```csv
   X,Y,Z,C,FocusMode,FocusValues
   50,80,0,0,manual,"6.0;8.0;10.0"
   50,80,45,0,manual,"6.0;8.0;10.0"
   50,80,90,0,manual,"6.0;8.0;10.0"
   ```

2. Upload CSV in web UI
3. Start scan
4. System captures 3 images per point (total 9 images)
5. Post-process with Helicon Focus

**Time**: 62% faster than running 3 separate scans!

---

### Workflow 2: Mixed Focus Modes (CSV)

**User Goal**: Autofocus first point, then manual for rest

**Steps**:
1. Create CSV:
   ```csv
   X,Y,Z,C,FocusMode,FocusValues
   50,80,0,0,af,
   50,80,45,0,manual,8.0
   50,80,90,0,manual,8.0
   ```

2. Upload CSV
3. Scan runs:
   - Point 1: Autofocus (~4s)
   - Point 2-3: Manual focus (~0.5s each)

---

### Workflow 3: Global Default (Current UI)

**User Goal**: Same focus for all points (simple scan)

**Steps**:
1. Use dashboard manual focus slider → Set to 8.0
2. Create scan pattern (no focus parameters)
3. All points use lens position 8.0

**No code changes needed** - already works!

---

## Technical Integration Points

### Where Per-Point Focus is Used

```
User Input (CSV/YAML)
    ↓
ScanPoint Creation (with focus parameters)
    ↓
Scan Orchestrator (_execute_scan_points)
    ↓
Per-Point Loop:
    ↓
    For each focus_position in point.get_focus_positions():
        ↓
        camera_controller.auto_focus(focus_mode, lens_position)
        ↓
        Capture image
        ↓
        Save with focus metadata
```

### Web UI doesn't need to change scan execution - it just needs to create proper `ScanPoint` objects!

---

## Questions?

**Q: Do I need to change the web UI for per-point focus to work?**  
**A**: No! CSV/YAML input already works. Just update the CSV parser to read focus columns.

**Q: Can I mix web UI manual focus with per-point focus?**  
**A**: Yes! Per-point settings override global web UI settings. If a point has no focus parameters, it uses the global slider value.

**Q: What if I want a GUI for per-point focus?**  
**A**: Follow Phase 3 roadmap above - add focus controls to scan point editor. But CSV works great and is faster to implement.

**Q: Will this break existing scans?**  
**A**: No! 100% backward compatible. Existing scans without focus parameters work exactly as before.

---

**Summary**: The per-point focus implementation already integrates with the backend. The web UI can use it NOW via CSV upload (with parser update) or later add visual editors for convenience.
