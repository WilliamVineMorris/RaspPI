# Fix Plotly.js 3D Visualization Issue

## Problem
The dashboard shows: "⚠️ Plotly.js Not Available" and 3D visualization is disabled.

## Root Cause
Plotly.js library files are missing from the local static directory, and the Pi may not have internet access to load from CDN.

## Solution Options

### Option 1: Python Download Script (Recommended)
```bash
cd ~/scanner/RaspPI/V2.0/web/
python3 download_offline_dependencies.py
```

### Option 2: Shell Script (If Python fails)
```bash
cd ~/scanner/RaspPI/V2.0/web/
bash download_dependencies.sh
```

### Option 3: Manual Download (If scripts fail)
```bash
cd ~/scanner/RaspPI/V2.0/web/static/js/

# Download Plotly.js
wget -O plotly-2.27.1.min.js "https://cdn.plot.ly/plotly-2.27.1.min.js"

# Download Socket.IO (if also missing)
wget -O socket.io.min.js "https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"
```

## Verification Steps

1. **Check files were downloaded:**
   ```bash
   ls -la ~/scanner/RaspPI/V2.0/web/static/js/
   # Should show:
   # plotly-2.27.1.min.js  (several MB)
   # socket.io.min.js      (several hundred KB)
   ```

2. **Restart web server:**
   ```bash
   # Stop current server (Ctrl+C)
   # Restart scanner system
   ```

3. **Test dashboard:**
   - Open dashboard in browser
   - Check browser console (F12)
   - Should see: "✅ Plotly loaded from: /static/js/plotly-2.27.1.min.js"
   - 3D visualization should now work

## Expected Results

### Before Fix:
- ❌ "⚠️ Plotly.js not loaded - visualization disabled"
- ❌ Empty 3D plot area with error message
- ❌ No scan path visualization

### After Fix:
- ✅ "✅ Plotly loaded from: /static/js/plotly-2.27.1.min.js"
- ✅ Working 3D visualization
- ✅ Scan path preview and real-time updates

## Troubleshooting

### If downloads fail:
```bash
# Check internet connection
ping google.com

# Try different download method
curl -o plotly-2.27.1.min.js "https://cdn.plot.ly/plotly-2.27.1.min.js"
```

### If files exist but still not loading:
1. Check file permissions:
   ```bash
   chmod 644 ~/scanner/RaspPI/V2.0/web/static/js/*.js
   ```

2. Clear browser cache (Ctrl+Shift+R)

3. Check browser console for error messages

4. Verify file sizes:
   ```bash
   ls -lh ~/scanner/RaspPI/V2.0/web/static/js/
   # plotly-2.27.1.min.js should be several MB
   # socket.io.min.js should be several hundred KB
   ```

### If internet is not available:
- Transfer files manually from another computer
- Copy files to Pi via USB/SD card
- Use mobile hotspot temporarily for downloads

## File Locations
- **Static directory**: `~/scanner/RaspPI/V2.0/web/static/js/`
- **Expected files**:
  - `plotly-2.27.1.min.js` (for 3D visualization)
  - `socket.io.min.js` (for real-time communication)

This fix enables full offline operation of the Pi hotspot with complete 3D visualization functionality.