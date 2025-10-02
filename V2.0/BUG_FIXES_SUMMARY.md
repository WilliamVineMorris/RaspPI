# 🐛 Bug Fixes Applied - Visualizer & CSV Export

## Issues Identified

### 1. ❌ Visualizer Not Appearing
**Problem**: 3D visualization area shows but is empty (blank white box)
**Root Cause**: Plotly.js not loading (likely Pi has no internet access)

### 2. ❌ CSV Export Failed
**Error Log**:
```
2025-10-02 22:31:25,881 - web_interface - ERROR - CSV export API error: 
'ConfigManager' object has no attribute 'get_axes_config'
```
**Root Cause**: Wrong method name in `web_interface.py`

### 3. ❌ CSV Import Would Fail Too
**Problem**: Backend expects `'csv_file'` but frontend sends `'file'`
**Root Cause**: Mismatched field names between frontend and backend

## Fixes Applied

### ✅ Fix 1: CSV Export Backend Error
**File**: `web/web_interface.py` (Line ~1388)

**Changed:**
```python
axes_config = config_manager.get_axes_config() if config_manager else {}
```

**To:**
```python
axes_config = config_manager.get_all_axes() if config_manager else {}
```

**Reason**: `ConfigManager` has `get_all_axes()` method, not `get_axes_config()`

### ✅ Fix 2: CSV Import Backend Error
**File**: `web/web_interface.py` (Line ~1422)

**Changed:**
```python
axes_config = config_manager.get_axes_config() if config_manager else {}
```

**To:**
```python
axes_config = config_manager.get_all_axes() if config_manager else {}
```

### ✅ Fix 3: CSV Import Field Name Mismatch
**File**: `web/web_interface.py` (Line ~1407-1410)

**Changed:**
```python
if 'csv_file' not in request.files:
    raise BadRequest("No CSV file provided")

file = request.files['csv_file']
```

**To:**
```python
if 'file' not in request.files:
    raise BadRequest("No CSV file provided")

file = request.files['file']
```

**Reason**: Frontend JavaScript sends `formData.append('file', file)`, not `'csv_file'`

### ✅ Fix 4: Plotly Loading Detection
**File**: `web/templates/scans.html` (Line ~2781)

**Added before visualization code:**
```javascript
// Check if Plotly is loaded
if (typeof Plotly === 'undefined') {
    console.error('Plotly.js is not loaded! Check internet connection or install locally.');
    document.getElementById('scan-path-3d-plot').innerHTML = `
        <div style="text-align: center; padding: 2rem; color: #d63031; background: #fff5f5;">
            <h4>⚠️ Plotly.js Not Loaded</h4>
            <p>The 3D visualization library could not be loaded.</p>
            <details>
                <summary>Troubleshooting Steps</summary>
                <ol>
                    <li><strong>Check Internet:</strong> Pi needs internet to load Plotly from CDN</li>
                    <li><strong>Or Install Locally:</strong> Download plotly-2.27.0.min.js to web/static/js/</li>
                    <li><strong>Update base.html:</strong> Change CDN link to local file</li>
                </ol>
            </details>
        </div>
    `;
    return;
}
```

**Benefits**:
- User gets clear error message if Plotly doesn't load
- Provides actionable troubleshooting steps
- Prevents JavaScript errors from undefined `Plotly` object

## Testing After Fixes

### 1. Test CSV Export
**Expected behavior**:
1. Navigate to http://localhost:5000/scans
2. Configure cylindrical scan parameters
3. Click "💾 Export CSV"
4. File should download: `scan_export_TIMESTAMP.csv`

**Console should show**:
```
✅ No error about 'get_axes_config'
✅ CSV file downloads successfully
```

### 2. Test CSV Import
**Expected behavior**:
1. Create simple CSV:
```csv
index,x,y,z,c
0,150.0,80.0,0.0,-25.0
1,150.0,100.0,90.0,-30.0
2,150.0,120.0,180.0,-35.0
```
2. Click "📁 Import CSV"
3. Select file
4. Should show success or validation errors

**Console should show**:
```
✅ No error about 'csv_file' not found
✅ Validation runs correctly
```

### 3. Test Plotly Loading
**If Pi HAS internet**:
- Visualizer should show 3D plot immediately
- Interactive rotation/zoom should work

**If Pi DOES NOT have internet**:
- Clear error message appears in visualizer area
- Message explains: "Plotly.js Not Loaded"
- Shows troubleshooting steps with expandable details

## Next Steps

### If Visualizer Still Not Showing:

**Option A: Enable Internet on Pi** (Quick Fix)
```bash
# Test internet connectivity
ping -c 3 cdn.plotly.ly

# If working, just refresh browser
```

**Option B: Install Plotly Locally** (Recommended for Production)
See detailed guide: `PLOTLY_LOCAL_INSTALL.md`

Quick steps:
```bash
cd ~/RaspPI/V2.0/web
mkdir -p static/js
wget https://cdn.plotly.ly/plotly-2.27.0.min.js -O static/js/plotly-2.27.0.min.js
```

Then edit `web/templates/base.html` line 11:
```html
<!-- Change from: -->
<script src="https://cdn.plotly.ly/plotly-2.27.0.min.js"></script>

<!-- To: -->
<script src="{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}"></script>
```

Restart web server:
```bash
python3 run_web_interface.py
```

## Verification Checklist

After restarting web server, verify:

- [ ] **CSV Export Works**
  - No console errors
  - File downloads successfully
  - CSV has correct format (`index,x,y,z,c`)

- [ ] **CSV Import Works**
  - No console errors about 'csv_file'
  - Validation messages display correctly
  - Valid CSV visualizes points

- [ ] **Plotly Loading**
  - Browser console: `typeof Plotly` returns `"object"`
  - OR helpful error message displays if Plotly missing
  - 3D plot appears when Plotly loads

- [ ] **Visualization**
  - 3D scatter plot appears
  - Blue→red color gradient visible
  - Can drag to rotate, scroll to zoom
  - Hover shows point details

## Files Modified

1. **`web/web_interface.py`** (3 changes)
   - Line ~1388: Fix CSV export `get_all_axes()`
   - Line ~1422: Fix CSV import `get_all_axes()`
   - Line ~1407: Fix field name from `'csv_file'` to `'file'`

2. **`web/templates/scans.html`** (1 change)
   - Line ~2781: Add Plotly loading check with error message

## Expected Console Logs

### Successful CSV Export:
```
📊 Using standard profiles - Quality: medium Speed: medium
Generated 24 valid points for cylindrical pattern
✅ CSV file download triggered
```

### Successful CSV Import:
```
📁 Imported CSV points: 3
📊 Visualizing custom CSV points: 3
```

### Plotly Loading (Success):
```
📊 Visualizing generated scan path: 24 points
Plotly.newPlot completed successfully
```

### Plotly Loading (Failure):
```
❌ Plotly.js is not loaded! Check internet connection or install locally.
```

## Summary

✅ **CSV Export**: Fixed by correcting method name `get_all_axes()`
✅ **CSV Import**: Fixed by correcting field name `'file'`
✅ **Plotly Detection**: Added helpful error message with troubleshooting

**All backend errors resolved!** The visualizer will now show either:
- Working 3D plot (if Plotly loads)
- Clear error message with fix instructions (if Plotly doesn't load)

**Next**: Test on Pi and install Plotly locally if needed (see `PLOTLY_LOCAL_INSTALL.md`)
