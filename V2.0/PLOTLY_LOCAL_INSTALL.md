# 🔧 Plotly.js Local Installation Guide

## Issue
The 3D visualizer requires Plotly.js, which is currently loaded from CDN (internet required).
If your Pi doesn't have internet access, the visualizer won't load.

## Solution: Install Plotly Locally

### Option 1: Quick Fix (If Pi Has Internet)
Just ensure the Pi has internet access and refresh the page. The CDN will load Plotly automatically.

### Option 2: Local Installation (No Internet Needed)

#### Step 1: Create Static Directory
```bash
cd ~/RaspPI/V2.0/web
mkdir -p static/js
```

#### Step 2: Download Plotly.js
On a computer with internet:
1. Go to: https://cdn.plotly.ly/plotly-2.27.0.min.js
2. Save the file as `plotly-2.27.0.min.js`
3. Transfer to Pi: `~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js`

Or using wget on Pi (if it has temporary internet):
```bash
cd ~/RaspPI/V2.0/web/static/js
wget https://cdn.plotly.ly/plotly-2.27.0.min.js
```

#### Step 3: Update base.html
Edit: `~/RaspPI/V2.0/web/templates/base.html`

**Change line 11 from:**
```html
<script src="https://cdn.plotly.ly/plotly-2.27.0.min.js"></script>
```

**To:**
```html
<script src="{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}"></script>
```

#### Step 4: Restart Web Interface
```bash
# Stop current server (Ctrl+C)
python3 run_web_interface.py
```

#### Step 5: Test
1. Navigate to http://localhost:5000/scans
2. Select "Cylindrical Scan"
3. You should see the 3D visualization appear!

## Verification

### Check if Plotly is Loaded
Open browser console (F12 → Console tab) and type:
```javascript
typeof Plotly
```

- **Expected**: `"object"` (Plotly loaded ✅)
- **If you see**: `"undefined"` (Plotly not loaded ❌)

### Check Network Tab
1. Open F12 → Network tab
2. Refresh page
3. Look for `plotly-2.27.0.min.js` in the list
4. Should show **200 OK** status

## File Structure After Installation
```
RaspPI/V2.0/
├── web/
│   ├── static/
│   │   └── js/
│   │       └── plotly-2.27.0.min.js  ← Downloaded file (~3.5 MB)
│   ├── templates/
│   │   ├── base.html                  ← Updated script tag
│   │   └── scans.html
│   └── web_interface.py
```

## Alternative: Use Different CDN
If the primary CDN is blocked, try these alternatives in `base.html`:

**jsDelivr CDN:**
```html
<script src="https://cdn.jsdelivr.net/npm/plotly.js@2.27.0/dist/plotly.min.js"></script>
```

**unpkg CDN:**
```html
<script src="https://unpkg.com/plotly.js@2.27.0/dist/plotly.min.js"></script>
```

## Troubleshooting

### Error: "Plotly.js Not Loaded"
**Symptoms**: Red warning message in visualizer area
**Cause**: Plotly library not accessible
**Fix**: Follow local installation steps above

### Network Error in Console
**Symptoms**: Console shows "Failed to load resource: net::ERR_NAME_NOT_RESOLVED"
**Cause**: Pi cannot reach CDN
**Fix**: Install Plotly locally (Option 2 above)

### File Not Found (404)
**Symptoms**: After local install, still shows error
**Possible causes**:
1. File path incorrect → Check: `/web/static/js/plotly-2.27.0.min.js` exists
2. Flask not serving static files → Check: `web_interface.py` has static folder configured
3. Wrong URL in base.html → Use: `{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}`

## Flask Static File Configuration

Verify `web_interface.py` has static folder configured:
```python
self.app = Flask(__name__, 
                 template_folder='templates',
                 static_folder='static')  # ← Should be present
```

If not present, add it when creating the Flask app.

## Quick Test Commands

### Check if file exists:
```bash
ls -lh ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
```

### Check file size (should be ~3.5 MB):
```bash
du -h ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
```

### Test direct access:
```bash
# While web server is running, try:
curl http://localhost:5000/static/js/plotly-2.27.0.min.js | head -n 5
```

Should show JavaScript code starting with:
```javascript
/**
* plotly.js v2.27.0
* Copyright 2012-2023, Plotly, Inc.
...
```

## Summary

**CDN Loading (Current)**:
- ✅ No installation needed
- ✅ Automatic updates
- ❌ Requires internet
- ❌ ~3.5 MB loaded each page visit

**Local Loading (Recommended for Pi)**:
- ✅ Works offline
- ✅ Faster page loads (cached)
- ✅ No external dependencies
- ❌ Manual updates needed
- ❌ One-time 3.5 MB storage

For a production Pi system without reliable internet, **local installation is recommended**.
