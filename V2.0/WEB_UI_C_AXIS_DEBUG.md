# Web UI C-Axis Display Debug Investigation

## Problem
The web UI dashboard shows `C: 0.0°` despite FluidNC correctly reporting C-axis values (e.g., C=25.000 or C=-25.000). The correct value "flashes" briefly before resetting to 0.

## Debug Logs Analysis
From user's logs:
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,0.000,0.000,25.000' → 6 coordinates
🔍 PARSED (6 axes): [200.000, 137.500, 0.000, 0.000, 0.000, 25.000] → C=25.000
```

**FluidNC is correctly reporting C=25.000** - the parsing is working perfectly.

## Investigation Path

### Backend Position Update (CONFIRMED WORKING)
- `simplified_fluidnc_controller_fixed.py` line 1219-1229: Using FluidNC C value ✅
- `simplified_fluidnc_protocol_fixed.py` line 619: Parsing C from position [5] ✅
- Motion controller's `current_position` should have correct C value ✅

### Web UI Position Display (UNDER INVESTIGATION)
The `/api/status` endpoint is responsible for sending position to the dashboard.

**Code Path:**
1. `web_interface.py` line 447: `/api/status` endpoint
2. `web_interface.py` line 2327: `_get_system_status()` method
3. `web_interface.py` line 2391: Gets `position = motion_controller.current_position`
4. `web_interface.py` line 2463: Converts Position4D to dict for JSON

## Debug Logging Added

### Location 1: Position Retrieval (Line 2391-2396)
```python
position = motion_controller.current_position

# DEBUG: Log the C-axis value being sent to web UI
c_value = getattr(position, 'c', 0.0) if position else 0.0
self.logger.info(f"🔍 STATUS API: Sending C-axis to web UI: {c_value}° (full position: {position})")
```

### Location 2: Position Dict Creation (Line 2463-2483)
```python
# DEBUG: Log extracted values before putting in dict
x_val = getattr(position, 'x', 0.0)
y_val = getattr(position, 'y', 0.0)
z_val = getattr(position, 'z', 0.0)
c_val = getattr(position, 'c', 0.0)

self.logger.info(f"🔍 STATUS API: Extracted position values - X:{x_val}, Y:{y_val}, Z:{z_val}, C:{c_val}")

position_dict = {'x': x_val, 'y': y_val, 'z': z_val, 'c': c_val, ...}

self.logger.info(f"🔍 STATUS API: Final position_dict being sent: {position_dict}")
```

## What to Look For in Logs

### Expected Output (if backend is correct):
```
🔍 STATUS API: Sending C-axis to web UI: 25.0° (full position: Position4D(x=200.00, y=137.50, z=0.00, c=25.00))
🔍 STATUS API: Extracted position values - X:200.0, Y:137.5, Z:0.0, C:25.0
🔍 STATUS API: Final position_dict being sent: {'x': 200.0, 'y': 137.5, 'z': 0.0, 'c': 25.0, ...}
```

### Problem Indicators:
1. **If C shows 0 in these logs** → Backend issue (position object has wrong C value)
2. **If C shows correct value in logs but UI shows 0** → Frontend issue (JavaScript not updating)
3. **If position is None** → Motion controller not initialized properly

## Testing Steps

1. **Restart web interface**:
   ```bash
   python run_web_interface.py
   ```

2. **Execute C-axis jog command** (e.g., +25°):
   - Watch terminal for debug logs
   - Watch web UI dashboard for position update

3. **Check debug log sequence**:
   ```
   🔍 RAW FluidNC MPos: '...' → 6 coordinates     (from protocol)
   🔍 PARSED (6 axes): [...] → C=25.000           (from protocol)
   🎯 Fresh position after jog: Position(C:25.000) (from jog API)
   🔍 STATUS API: Sending C-axis to web UI: 25.0° (from status API)
   🔍 STATUS API: Extracted position values - C:25.0
   🔍 STATUS API: Final position_dict - c: 25.0
   ```

## Possible Issues

### Theory 1: Position Object Reset
If `motion_controller.current_position` returns correct value immediately after jog but wrong value in status API, something is resetting it between calls.

**Check for:**
- Race condition between position update and status API call
- Multiple position update sources overwriting each other
- Cached position being cleared

### Theory 2: Frontend JavaScript Issue
If backend sends correct C value but UI displays 0:
- JavaScript might not be updating C field
- Position update might be asynchronous in frontend
- DOM element might be reverting to initial 0 value

### Theory 3: JSON Serialization Issue
If Position4D object isn't serializing correctly:
- Check that `getattr(position, 'c', 0.0)` actually works
- Verify Position4D has proper `c` attribute
- Confirm dict conversion is correct

## Next Steps Based on Results

### If logs show C=0:
- Check `motion_controller.current_position` property
- Verify position update is being called
- Check for race conditions

### If logs show C=25 but UI shows C=0:
- Investigate frontend JavaScript (dashboard.html)
- Check `/api/status` response in browser network tab
- Verify position update code in dashboard

### If position is None:
- Motion controller initialization issue
- Check orchestrator setup
- Verify hardware connection

## Files Modified
1. `web/web_interface.py` (lines 2391-2396, 2463-2483)
   - Added comprehensive debug logging to status API

## Resolution Path
Once we see the debug logs, we'll know exactly where the C value is being lost:
- **Backend**: Fix position update/retrieval
- **API**: Fix JSON serialization
- **Frontend**: Fix JavaScript update logic
