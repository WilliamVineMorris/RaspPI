# 🚀 Quick Start - 3D Scan Visualizer Testing

## What Changed?
The 3D scan path visualizer is now integrated into `scans.html` (the actual scans page).

## Where to Test
**URL**: http://localhost:5000/scans

## What You'll See
1. **Navigate to Scans page**
2. **Select "Cylindrical Scan"** type
3. **Look right side** → 3D visualization appears!

## Visual Layout
```
┌─────────────────────────────────────────────────────┐
│                   Scans Page                        │
├───────────────────────┬─────────────────────────────┤
│   LEFT COLUMN         │   RIGHT COLUMN              │
│                       │                             │
│   📐 Camera Distance  │   📊 3D Scan Path Preview   │
│   [    30 mm    ]     │   ┌───────────────────────┐ │
│                       │   │                       │ │
│   📏 Height Range     │   │   Interactive 3D      │ │
│   Start: [ 40 mm ]    │   │   Plotly Graph        │ │
│   End:   [120 mm ]    │   │                       │ │
│                       │   │   (rotate, zoom,      │ │
│   📐 Height Steps     │   │    pan with mouse)    │ │
│   [     4      ]      │   │                       │ │
│                       │   └───────────────────────┘ │
│   🔄 Rotations        │                             │
│   [     6      ]      │   Total Points: 24          │
│                       │   X Range: -30 to 30 mm     │
│   🎯 Servo Tilt       │   Y Range: 40 to 120 mm     │
│   [  None  ▼  ]       │   Z Range: -30 to 30 mm     │
│                       │                             │
│                       │   ┌──────┐  ┌──────┐        │
│                       │   │ 📁   │  │ 💾   │        │
│                       │   │Import│  │Export│        │
│                       │   └──────┘  └──────┘        │
└───────────────────────┴─────────────────────────────┘
```

## Quick Test Sequence

### Test 1: Auto-Update (30 seconds)
1. Open scans page
2. See default visualization (24 points)
3. Move **radius slider** → visualization updates
4. Change **height steps** to 8 → more points appear
5. ✅ SUCCESS: Visualization updates automatically

### Test 2: CSV Export (1 minute)
1. Configure custom pattern (e.g., 12 steps, 8 rotations)
2. Click **"💾 Export CSV"** button
3. File downloads: `scan_pattern_TIMESTAMP.csv`
4. Open in text editor
5. ✅ SUCCESS: See CSV with index,x,y,z,c columns

### Test 3: CSV Import (2 minutes)
1. Edit exported CSV (change some values)
2. Click **"📁 Import CSV"** button
3. Select modified file
4. Visualization updates with new points
5. ✅ SUCCESS: Custom pattern visualized

### Test 4: Scan Execution (3 minutes)
1. Import custom CSV (from Test 3)
2. Click **"Start Scan Now"**
3. Check console logs for "Using custom CSV points"
4. OR configure standard pattern (no CSV)
5. Click **"Start Scan Now"**
6. Check logs for "Using standard cylindrical pattern"
7. ✅ SUCCESS: Scan executes correct pattern type

## Expected Console Logs

### On Page Load
```
📊 Visualizing generated scan path: 24 points
```

### On Parameter Change
```
📊 Visualizing generated scan path: 48 points
```

### On CSV Import
```
📁 Imported CSV points: (16) [{…}, {…}, ...]
📊 Visualizing custom CSV points: 16
```

### On Scan Start (with CSV)
```
📁 Using custom CSV points: 16
✅ Added speed_settings to CYLINDRICAL scan data: {...}
🏠 Checking system status before scan...
```

### On Scan Start (without CSV)
```
📊 Using standard profiles - Quality: medium Speed: medium
✅ Added speed_settings to CYLINDRICAL scan data: {...}
🏠 Checking system status before scan...
```

## Troubleshooting Quick Checks

### ❌ No Visualization Showing
- **Check**: Is "Cylindrical Scan" selected? (Card should be highlighted)
- **Check**: Browser console for errors (F12 → Console tab)
- **Fix**: Refresh page, select Cylindrical Scan again

### ❌ Parameters Don't Update Visualization
- **Check**: Console shows "📊 Visualizing..." when you change sliders?
- **Check**: Wait 500ms after changing (debounced)
- **Fix**: Clear browser cache, refresh page

### ❌ CSV Import Shows Errors
- **Check**: CSV format exactly: `index,x,y,z,c` with header row
- **Check**: Values within limits (X: 0-200, Y: 0-200, Z: 0-360, C: -90 to 90)
- **Fix**: Use exported CSV as template

### ❌ Scan Doesn't Use Custom CSV
- **Check**: sessionStorage has 'customScanPoints' (F12 → Application → Session Storage)
- **Check**: Console shows "📁 Using custom CSV points"
- **Fix**: Re-import CSV file

## File Locations

### On Pi:
```
/home/pi/RaspPI/V2.0/web/templates/scans.html  ← Modified file
/home/pi/RaspPI/V2.0/web/templates/base.html   ← Has Plotly.js CDN
```

### Modified Sections in scans.html:
- **Lines ~338-430**: CSS for 2-column layout
- **Lines ~1817-1879**: HTML for visualizer column
- **Lines ~2720-2990**: JavaScript visualization functions

## Hardware Limits (from config)
```yaml
X (radius):      0-200 mm
Y (height):      0-200 mm  
Z (rotation):    0-360 degrees
C (camera tilt): -90 to +90 degrees
```

## CSV Format Example
```csv
index,x,y,z,c
0,150.0,80.0,0.0,-25.0
1,150.0,80.0,90.0,-25.0
2,150.0,80.0,180.0,-25.0
3,150.0,80.0,270.0,-25.0
4,150.0,120.0,0.0,-36.3
5,150.0,120.0,90.0,-36.3
```

## Success Criteria

✅ **Visual**: 3D plot appears on right side of scans page
✅ **Interactive**: Can rotate/zoom/pan the 3D visualization
✅ **Responsive**: Parameters update visualization automatically
✅ **Export**: CSV file downloads with correct format
✅ **Import**: CSV validation works, shows errors or visualizes
✅ **Execution**: Scans use custom CSV or standard pattern correctly

## If Everything Works...
You should see:
- Beautiful 3D visualization of scan path
- Blue→red color gradient showing scan order
- Hover tooltips with coordinate info
- Auto-updating when you change parameters
- CSV export/import working smoothly
- Scans executing with correct patterns

**🎉 That's it! The visualizer is fully integrated and ready to use!**

## Next Steps After Testing
1. Report any issues found
2. Test with different scan patterns
3. Create library of useful CSV patterns
4. Consider adding per-point settings (focus, exposure, LED)

---

**Remember**: This runs on the Pi, not on your local machine!
All changes are ready - just test on the actual hardware.
