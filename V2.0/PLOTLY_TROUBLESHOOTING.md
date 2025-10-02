# 🔧 Plotly.js Troubleshooting Guide

## Current Situation
- ✅ Error detection is working (showing "Plotly.js Not Loaded" message)
- ❌ Plotly.js is not loading from CDN
- 🔍 Need to identify why and fix it

## Quick Diagnosis

### Step 1: Check Browser Console
**On the Pi browser (Chromium), press F12 → Console tab**

Look for errors related to:
- `plotly` 
- `Failed to load resource`
- `net::ERR_*` errors

### Step 2: Check Network Tab
**F12 → Network tab → Refresh page**

Look for: `plotly-2.27.0.min.js`
- **Status 200**: File loaded ✅
- **Status 404**: File not found ❌
- **Status failed**: Network/CDN blocked ❌

## Solutions (Try in Order)

### Solution 1: Download Plotly Locally (Recommended)

**On the Raspberry Pi, run:**
```bash
cd ~/RaspPI/V2.0
python3 download_plotly.py
```

This script will:
1. Create `web/static/js/` directory
2. Download Plotly.js from CDN (~3.5 MB)
3. Save it locally
4. Verify the download

**Expected output:**
```
📦 Downloading Plotly.js...
   Progress: 100% (3,500,000 / 3,500,000 bytes)
✅ Download complete! (3,500,000 bytes)
✅ File verified - appears to be valid JavaScript
```

**If download succeeds:**
```bash
# Restart web server
python3 run_web_interface.py
```

The updated `base.html` will now:
1. Try to load from CDN first
2. If CDN fails, automatically fallback to local file
3. Visualizer should work!

### Solution 2: Manual Download (If Script Fails)

**If the download script fails, manually download:**

```bash
# Create directory
mkdir -p ~/RaspPI/V2.0/web/static/js

# Download using wget
wget https://cdn.plotly.ly/plotly-2.27.0.min.js \
     -O ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js

# Verify download
ls -lh ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
# Should show ~3.5 MB file
```

### Solution 3: Try Different CDN

**If CDN is the issue, try alternative CDNs:**

Edit `web/templates/base.html` line 12-14:

**Option A - jsDelivr:**
```html
<script src="https://cdn.jsdelivr.net/npm/plotly.js@2.27.0/dist/plotly.min.js"
        onerror="this.onerror=null; this.src='{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}'">
</script>
```

**Option B - unpkg:**
```html
<script src="https://unpkg.com/plotly.js@2.27.0/dist/plotly.min.js"
        onerror="this.onerror=null; this.src='{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}'">
</script>
```

**Option C - Use local file only:**
```html
<script src="{{ url_for('static', filename='js/plotly-2.27.0.min.js') }}"></script>
```

### Solution 4: Check Flask Static Configuration

Verify Flask is serving static files correctly:

**Check `web/web_interface.py`:**
```python
# Should have static_folder configured
self.app = Flask(__name__, 
                 template_folder='templates',
                 static_folder='static')
```

**Test static file serving:**
```bash
# While web server is running:
curl http://localhost:5000/static/js/plotly-2.27.0.min.js | head -n 5
```

Should show JavaScript code starting with:
```javascript
/**
* plotly.js v2.27.0
```

## Verification Steps

### After Applying Fix:

1. **Restart web server:**
   ```bash
   python3 run_web_interface.py
   ```

2. **Clear browser cache:**
   - Ctrl+Shift+R (hard refresh)
   - Or Ctrl+Shift+Delete → Clear cached images and files

3. **Open browser console (F12):**
   ```javascript
   // Type this in console:
   typeof Plotly
   ```
   - **Expected**: `"object"` ✅
   - **If undefined**: Still not loaded ❌

4. **Check page load logs:**
   ```
   📊 Initializing 3D visualizer...
      Plotly status: LOADED ✅
   ```

5. **Test visualization:**
   - Navigate to Scans page
   - Select "Cylindrical Scan"
   - Change parameters → Should see 3D plot

## Common Issues & Fixes

### Issue 1: "Download failed: URLError"
**Cause**: Pi cannot reach CDN
**Fix**: 
- Check internet: `ping cdn.plotly.ly`
- Use manual download method
- Or download on PC and transfer via USB/SCP

### Issue 2: File downloads but still shows error
**Cause**: File corrupted or wrong location
**Fix**:
```bash
# Check file size
ls -lh ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
# Should be ~3.5 MB

# Check first line
head -n 1 ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
# Should show JavaScript code
```

### Issue 3: 404 when accessing /static/js/plotly...
**Cause**: Flask not configured to serve static files
**Fix**: Check `web_interface.py` has `static_folder='static'`

### Issue 4: Browser shows mixed content warning
**Cause**: HTTP/HTTPS mismatch
**Fix**: Use local file (Solution 3, Option C)

### Issue 5: File exists but browser cache old error
**Cause**: Browser cached the "not loaded" state
**Fix**: 
- Hard refresh: Ctrl+Shift+R
- Or clear browser cache completely

## Debug Commands

### Check if Plotly.js exists:
```bash
find ~/RaspPI/V2.0 -name "*plotly*"
```

### Check file size:
```bash
du -h ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js
```

### Test Flask serving it:
```bash
# Start web server, then:
wget http://localhost:5000/static/js/plotly-2.27.0.min.js -O /tmp/test.js
head -n 1 /tmp/test.js
```

### Check browser console for Plotly:
```javascript
// In browser console (F12):
console.log('Plotly loaded:', typeof Plotly !== 'undefined');
console.log('Plotly version:', typeof Plotly !== 'undefined' ? Plotly.BUILD : 'N/A');
```

## Expected File Structure

```
RaspPI/V2.0/
├── web/
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   │       ├── plotly-2.27.0.min.js  ← 3.5 MB file
│   │       ├── dashboard.js
│   │       ├── manual-control.js
│   │       ├── scans.js
│   │       └── scanner-base.js
│   ├── templates/
│   │   ├── base.html  ← Updated with fallback
│   │   └── scans.html
│   └── web_interface.py
└── download_plotly.py  ← Helper script
```

## Success Checklist

- [ ] Plotly.js file exists (~3.5 MB)
- [ ] File location: `web/static/js/plotly-2.27.0.min.js`
- [ ] Web server restarted
- [ ] Browser cache cleared
- [ ] Console shows: `Plotly status: LOADED ✅`
- [ ] 3D visualization appears on Scans page
- [ ] Can rotate/zoom the 3D plot

## If Still Not Working

**Collect diagnostic info:**
```bash
# Run on Pi:
echo "=== File Check ===" 
ls -lh ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js

echo "=== First Line ===" 
head -n 1 ~/RaspPI/V2.0/web/static/js/plotly-2.27.0.min.js

echo "=== Flask Test ===" 
curl -I http://localhost:5000/static/js/plotly-2.27.0.min.js
```

**Browser console screenshot showing:**
- Console tab errors
- Network tab showing plotly request
- Application tab → Session Storage

**Share this info for further troubleshooting!**

## Quick Fix Summary

**Fastest solution for Pi with internet:**
```bash
cd ~/RaspPI/V2.0
python3 download_plotly.py
python3 run_web_interface.py
# Then refresh browser with Ctrl+Shift+R
```

**If that works, you're done! ✅**
