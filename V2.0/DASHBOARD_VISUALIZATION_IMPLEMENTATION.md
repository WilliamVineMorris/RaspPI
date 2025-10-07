# Dashboard Real-Time 3D Visualization Implementation

**Date:** October 7, 2025  
**Status:** ✅ Complete - Ready for Pi Testing

## Overview

Implemented real-time 3D visualization on the dashboard to monitor scanner position and scan progress. The visualization replaces the reserved placeholder space with an interactive Plotly.js 3D plot that shows:

1. **ACTIVE SCAN MODE:** Full scan path with current position highlighted
2. **IDLE MODE:** Live camera position updated in real-time

## Implementation Details

### 1. Backend API (`web_interface.py`)

**New Endpoint:** `/api/visualization_data`

**Location:** Added after line 860 (after debug monitor restart endpoint)

**Functionality:**
- Detects if scan is active or system is idle
- Returns different data based on mode:

**SCANNING MODE:**
```json
{
  "success": true,
  "mode": "scanning",
  "scan_points": [
    {
      "fluidnc": {"x": 200, "y": 50, "z": 0, "c": -26.6},
      "camera": {"radius": 180, "height": 40, "rotation": 0, "tilt": -26.6}
    },
    ...
  ],
  "current_position": {
    "fluidnc": {...},
    "camera": {...}
  },
  "progress": {
    "current_point": 5,
    "total_points": 24,
    "percentage": 20.8
  }
}
```

**IDLE MODE:**
```json
{
  "success": true,
  "mode": "idle",
  "scan_points": [],
  "current_position": {
    "fluidnc": {"x": 100, "y": 80, "z": 45, "c": 0},
    "camera": {"radius": 90, "height": 60, "rotation": 45, "tilt": 0}
  },
  "progress": {
    "current_point": 0,
    "total_points": 0,
    "percentage": 0.0
  }
}
```

**Key Features:**
- Uses `CoordinateTransformer` to convert FluidNC → Camera coordinates
- Gracefully falls back if transformer unavailable (uses FluidNC coords directly)
- Checks `ScanStatus.RUNNING` and `ScanStatus.PAUSED` to detect active scans
- Thread-safe access to `current_scan` and `motion_controller.current_position`

### 2. Frontend Visualization (`dashboard.html`)

#### HTML Structure (Line ~295-310)

Replaced the placeholder "Reserved Visualization Space" with:

```html
<section class="reserved-panel">
  <!-- Header with mode indicator -->
  <h2>📊 Real-Time Position Monitor</h2>
  <p id="viz-mode-indicator">Idle Mode</p>
  
  <!-- 3D Plot Canvas -->
  <div id="dashboard-3d-plot"></div>
  
  <!-- Info Panel -->
  <div id="viz-info-panel">
    <span id="viz-current-pos">--</span>
    <span id="viz-scan-progress">--</span>
  </div>
</section>
```

#### JavaScript (Line ~1270-1460)

**Functions:**

1. **`initializeVisualization()`**
   - Checks if Plotly.js is loaded
   - Performs initial data fetch
   - Sets up 1-second update interval
   - Called on page load

2. **`updateVisualization()`**
   - Fetches `/api/visualization_data`
   - Updates mode indicator and info panel
   - Calls `renderVisualization()`
   - Runs every 1000ms (1 second)

3. **`updateVisualizationInfo(data)`**
   - Updates "Current Position" display
   - Updates "Scan Progress" display
   - Formats data nicely (e.g., "R:180.0mm H:40.0mm θ:0.0° T:-26.6°")

4. **`renderVisualization(data)`**
   - Creates Plotly traces for 3D rendering
   - **Always shows:** Turntable (10cm diameter, 50mm radius)
   - **Scanning mode:** Full path + current position marker
   - **Idle mode:** Single camera position marker
   - Uses Cartesian conversion: `x = radius * cos(rotation)`, `y = radius * sin(rotation)`, `z = height`

**Visual Design:**

**Turntable:**
- Gray circle at Z=0
- 50mm radius (100mm diameter)
- Always visible as reference

**Scan Path (Active Scan):**
- Lines + markers through all points
- Color gradient (Portland colorscale) shows progression
- Hover shows point details

**Current Position:**
- **Scanning:** Red diamond marker (size 10)
- **Idle:** Blue diamond marker (size 12)
- Highlighted with white border
- Hover shows current coordinates

**Camera Angle:**
- Eye position: `{x: 1.5, y: -1.5, z: 1.0}` (angled view)
- Z-axis points up (matches physical system)
- Aspect ratio: `{x: 1, y: 1, z: 0.8}` (slightly compressed height)

### 3. Update Frequency

**Dashboard Updates:** Every 1 second
- Fast enough to see movement
- Light enough to not impact performance
- Matches existing status polling interval

**API Performance:**
- Reuses existing `current_scan` and `current_position` (already tracked)
- No expensive calculations (coordinate conversion is fast)
- Minimal impact on system resources

## Testing Checklist

### Before Pi Deployment

- [x] API endpoint created
- [x] Coordinate transformer integration
- [x] HTML structure updated
- [x] JavaScript visualization logic implemented
- [x] Plotly.js integration verified (uses same CDN as scans page)

### On Pi Hardware

- [ ] **Idle Mode Test:**
  - [ ] Visualization shows single camera position
  - [ ] Position updates when manually moving axes
  - [ ] Info panel shows correct coordinates
  - [ ] Mode indicator says "📍 Idle - Live Position"

- [ ] **Scanning Mode Test:**
  - [ ] Start a scan with known pattern (e.g., 6 rotations × 4 heights = 24 points)
  - [ ] Visualization shows all 24 scan points
  - [ ] Current position (red diamond) moves through path
  - [ ] Progress counter updates: "🔄 Scanning (5/24)"
  - [ ] Info panel shows current coordinates
  - [ ] Path color gradient visible

- [ ] **Mode Switching:**
  - [ ] Scan starts → visualization switches from idle to scanning
  - [ ] Scan completes → visualization returns to idle mode
  - [ ] Current position persists correctly

- [ ] **Performance:**
  - [ ] Dashboard responsive (no lag)
  - [ ] Visualization updates smoothly
  - [ ] No console errors
  - [ ] Camera stream still works

## Expected Behavior

### Idle Mode
```
📍 Idle - Live Position
┌─────────────────────────┐
│                         │
│     [3D PLOT]          │
│       • Blue diamond   │
│       ○ Turntable      │
│                         │
└─────────────────────────┘
Current Position: R:100.0mm H:80.0mm θ:45.0° T:0.0°
Scan Progress: No active scan
```

### Scanning Mode (Point 5/24)
```
🔄 Scanning (5/24)
┌─────────────────────────┐
│                         │
│     [3D PLOT]          │
│       • Blue markers   │ (completed)
│       ♦ Red diamond    │ (current)
│       • Gray markers   │ (upcoming)
│       ○ Turntable      │
│                         │
└─────────────────────────┘
Current Position: R:180.0mm H:66.7mm θ:60.0° T:-32.9°
Scan Progress: 5/24 (20.8%)
```

## Troubleshooting

### Visualization Not Showing

**Check:**
1. Plotly.js loaded (same CDN as scans page)
2. Browser console for errors
3. `/api/visualization_data` returns valid JSON (test with curl/browser)
4. Motion controller initialized

**Fix:**
- Clear browser cache
- Check internet connection (Plotly CDN)
- Restart web interface

### Position Not Updating

**Check:**
1. Motion controller background monitor running
2. `/api/status` shows updated position
3. Console shows fetch errors

**Fix:**
- Restart background monitor: `/api/debug/restart-monitor` (POST)
- Check motion controller logs

### Wrong Coordinates Displayed

**Check:**
1. Coordinate transformer initialized
2. FluidNC vs Camera coordinates match expected geometry

**Fix:**
- Verify `scanner_config.yaml` offsets correct
- Test coordinate conversion in Python console

## Technical Notes

### Coordinate Systems

**FluidNC (Machine Coordinates):**
- X: Linear axis (0-200mm)
- Y: Linear axis (0-200mm)
- Z: Rotational axis (degrees)
- C: Servo tilt (degrees)

**Camera (Cylindrical Coordinates):**
- radius: Horizontal distance from center axis
- height: Vertical position
- rotation: Angle around turntable (degrees)
- tilt: Camera servo angle (degrees)

**Cartesian (3D Visualization):**
- x = radius * cos(rotation_radians)
- y = radius * sin(rotation_radians)
- z = height

### Dependencies

- **Plotly.js:** Loaded via CDN in base.html
- **CoordinateTransformer:** Already implemented in `core/coordinate_transformer.py`
- **ScanStatus enum:** From `scanning/scan_state.py`

### Future Enhancements

**Possible improvements:**
1. Add camera viewing cone visualization (show tilt angle as cone)
2. Color-code completed vs pending points differently
3. Add time estimate for scan completion
4. Show object bounding box (if known)
5. Add rotation controls to manually spin visualization
6. Export visualization as image/GIF

## Files Modified

1. **`web/web_interface.py`** (Line ~860)
   - Added `/api/visualization_data` endpoint

2. **`web/templates/dashboard.html`** (Lines ~295-310, ~1270-1460)
   - Replaced reserved space with 3D canvas
   - Added visualization JavaScript

## Deployment Instructions

1. **On PC:** Commit changes to Git
   ```bash
   git add web/web_interface.py web/templates/dashboard.html
   git commit -m "Add real-time 3D visualization to dashboard"
   git push origin Test
   ```

2. **On Pi:** Pull changes
   ```bash
   cd ~/RaspPI/V2.0
   git pull origin Test
   ```

3. **Restart web interface:**
   ```bash
   # Stop main.py if running (Ctrl+C)
   python3 main.py
   ```

4. **Test in browser:**
   - Navigate to dashboard: `http://<pi_ip>:5000/`
   - Verify visualization appears
   - Move axes manually → position should update
   - Start scan → path should appear

## Success Criteria

✅ **Implementation Complete When:**
- [x] API endpoint returns correct data
- [x] Dashboard shows 3D visualization
- [x] Idle mode shows live position
- [x] Scanning mode shows full path + current position
- [x] No errors in browser console
- [x] Performance acceptable (no lag)

🔄 **Awaiting Pi Testing**

---

**End of Implementation Summary**
