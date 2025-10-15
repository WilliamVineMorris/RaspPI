# Pi Hotspot Offline Setup Guide

## Problem
When connecting directly to Pi hotspot without internet, external CDN resources fail to load, causing incomplete webpage functionality.

## Solution
This setup ensures the web interface works completely offline when connected to Pi hotspot.

## 1. Download Offline Dependencies

Run this on Pi when connected to internet:

```bash
cd ~/scanner/RaspPI/V2.0/web/
python3 download_offline_dependencies.py
```

This downloads:
- Socket.IO library (real-time communication)
- Latest Plotly.js (3D visualization)

## 2. Verify Downloads

Check that files were created:

```bash
ls -la static/js/
# Should show:
# socket.io.min.js
# plotly-2.27.1.min.js
```

## 3. Test Offline Operation

1. **Disconnect Pi from internet**
2. **Connect device to Pi hotspot**
3. **Browse to Pi web interface**
4. **Verify functionality:**
   - ✅ Dashboard loads completely
   - ✅ Manual controls work
   - ✅ Camera streams load
   - ✅ Settings accessible
   - ⚠️ Real-time updates may be limited (HTTP polling only)

## 4. Offline Mode Indicators

When operating offline:
- Orange banner shows "📡 Offline Mode"
- Console logs indicate offline operation
- Basic functionality preserved
- Real-time features may be reduced

## 5. Re-enabling Online Features

When Pi reconnects to internet:
- Remove offline banner (refresh page)
- Full real-time features restored
- CDN resources available again

## Technical Details

### Resource Loading Priority:
1. **Local files first** (always work offline)
2. **CDN fallbacks** (when internet available)
3. **Graceful degradation** (if all sources fail)

### What Works Offline:
- ✅ All basic web interface functionality
- ✅ Manual motion controls
- ✅ Camera streaming
- ✅ Scan management
- ✅ Settings configuration
- ✅ File downloads

### What's Limited Offline:
- ⚠️ Real-time WebSocket updates (falls back to HTTP polling)
- ⚠️ External library updates (uses cached versions)

## Troubleshooting

### If dependencies fail to download:
```bash
# Check internet connection
ping google.com

# Install requests if missing
pip3 install requests

# Run download script with verbose output
python3 download_offline_dependencies.py
```

### If pages still don't load offline:
1. Clear browser cache
2. Hard refresh (Ctrl+F5)
3. Check browser console for errors
4. Verify static files exist in `/static/js/`

## Maintenance

### Update offline dependencies:
```bash
# When Pi has internet connection
cd ~/scanner/RaspPI/V2.0/web/
python3 download_offline_dependencies.py
```

### Monitor offline performance:
- Check browser console for "offline mode" messages
- Verify all UI elements load properly
- Test core functionality without internet

This setup ensures your Pi scanner works completely independently as a self-contained hotspot system.