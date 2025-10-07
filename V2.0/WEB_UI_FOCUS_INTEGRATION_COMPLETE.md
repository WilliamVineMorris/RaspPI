# Web UI Focus Integration - Complete Implementation

## Overview
Successfully integrated per-point focus control from the web UI through to the scanner backend. Users can now configure focus settings in the web interface camera presets, and these settings are automatically applied to all scan points during execution.

## Architecture Flow

```
Web UI (scans.html)
  ↓ [User configures focus in Quality Settings]
  ↓ [collectCustomQualitySettings() gathers focus object]
  ↓
API Endpoint (/api/scan/start)
  ↓ [Receives quality_settings with focus object]
  ↓
ScanOrchestrator.apply_custom_scan_settings()
  ↓ [Extracts and stores focus settings]
  ↓ [Stores in _web_focus_mode, _web_focus_position, _web_focus_stack_settings]
  ↓
ScanOrchestrator.create_*_pattern()
  ↓ [Creates pattern (grid or cylindrical)]
  ↓ [Calls _apply_web_focus_to_pattern()]
  ↓
_apply_web_focus_to_pattern()
  ↓ [Modifies all ScanPoints with focus settings]
  ↓ [Sets focus_mode and focus_values on each point]
  ↓
Scan Execution
  ↓ [Camera controller reads focus_mode/focus_values from ScanPoint]
  ↓ [Applies focus before capture at each point]
```

## Focus Modes Implemented

### 1. Manual Focus
**Web UI Setting**: `mode: 'manual', position: 8.0`
**Backend Behavior**: 
- Sets `point.focus_mode = FocusMode.MANUAL`
- Sets `point.focus_values = 8.0` (single value)
- All points use same fixed lens position

### 2. Autofocus Initial (Calibration)
**Web UI Setting**: `mode: 'autofocus_initial'`
**Backend Behavior**:
- Sets `point.focus_mode = FocusMode.AUTOFOCUS_ONCE`
- Camera performs autofocus once at scan start
- Resulting focus value used for all subsequent points

### 3. Continuous Autofocus
**Web UI Setting**: `mode: 'continuous'`
**Backend Behavior**:
- Sets `point.focus_mode = FocusMode.CONTINUOUS_AF`
- Camera performs autofocus before every capture
- Adapts to changing object distance/features

### 4. Manual Focus Stacking
**Web UI Setting**: 
```javascript
{
  mode: 'manual_stack',
  stack_steps: 2,        // Number of intervals
  min_focus: 6.0,        // Near focus position
  max_focus: 10.0        // Far focus position
}
```
**Backend Behavior**:
- Calculates focus positions: `levels = steps + 1`
- 1 step = 2 levels [6.0, 10.0]
- 2 steps = 3 levels [6.0, 8.0, 10.0]
- Sets `point.focus_mode = FocusMode.MANUAL`
- Sets `point.focus_values = [6.0, 8.0, 10.0]` (list of values)
- Updates `point.capture_count = 3` (one capture per focus level)
- Total scan captures multiplied by number of focus levels

## Files Modified

### 1. `web/templates/scans.html` (Web UI)
**Lines ~1750-1820**: Added focus control UI
- Focus mode dropdown (4 options)
- Manual focus slider (0-15 range)
- Focus stack controls (steps, min, max)
- Live preview of focus positions and capture count

**Lines ~3932-3980**: Added JavaScript functions
- `updateFocusPositionDisplay(value)` - Updates manual focus display
- `updateFocusStackDisplay()` - Calculates and displays interpolated positions
- `toggleFocusSettings()` - Shows/hides appropriate panels based on mode

**Lines ~4161-4195**: Updated `collectCustomQualitySettings()`
- Collects focus settings into quality_settings object
- Sends to backend in this format:
```javascript
quality_settings: {
  // ...other settings...
  focus: {
    mode: 'manual' | 'autofocus_initial' | 'continuous' | 'manual_stack',
    position: 8.0,           // for manual mode
    stack_steps: 2,          // for manual_stack mode
    min_focus: 6.0,          // for manual_stack mode
    max_focus: 10.0          // for manual_stack mode
  }
}
```

**Lines ~4266**: Updated `populateQualitySettings()`
- Loads focus settings from saved presets
- Populates all focus UI controls
- Calls `toggleFocusSettings()` to show correct panel

**Lines ~4126**: Updated `resetToDefaults()`
- Resets focus to defaults: manual mode, position 8.0
- Resets stack settings to steps=1, range=6.0-10.0

### 2. `scanning/scan_orchestrator.py` (Backend)
**Lines ~2469-2477**: Added web focus settings storage
```python
self._web_focus_mode: Optional[str] = None
self._web_focus_position: Optional[float] = None
self._web_focus_stack_settings: Optional[Dict[str, Any]] = None
```

**Lines ~2656-2690**: Updated `apply_custom_scan_settings()`
- Extracts focus settings from `quality_settings['focus']`
- Stores in orchestrator instance variables
- Logs focus configuration for debugging

**Lines ~4857-4945**: Added `_apply_web_focus_to_pattern()`
- Post-processes generated scan points
- Applies focus settings to each point based on mode
- Handles all 4 focus modes with appropriate ScanPoint configuration
- Calculates interpolated positions for focus stacking
- Modifies pattern's `generate_points()` to return modified points

**Lines ~4989-4994**: Updated `create_grid_pattern()`
- Calls `_apply_web_focus_to_pattern()` before returning pattern

**Lines ~5089-5096**: Updated `create_cylindrical_pattern()`
- Calls `_apply_web_focus_to_pattern()` before returning pattern

## Data Flow Example

### Example: Manual Focus Stack
**User Input** (Web UI):
```javascript
{
  mode: 'manual_stack',
  stack_steps: 2,
  min_focus: 6.0,
  max_focus: 10.0
}
```

**Backend Processing**:
```python
# 1. Extracted in apply_custom_scan_settings()
self._web_focus_mode = 'manual_stack'
self._web_focus_stack_settings = {
    'steps': 2,
    'min_focus': 6.0,
    'max_focus': 10.0
}

# 2. Pattern created with 100 points (example)
pattern = create_cylindrical_pattern(...)
# pattern.generate_points() → 100 ScanPoints

# 3. Focus settings applied
_apply_web_focus_to_pattern(pattern)
# Calculates: levels = 2 + 1 = 3
# Positions: [6.0, 8.0, 10.0]

# 4. Each ScanPoint modified:
point.focus_mode = FocusMode.MANUAL
point.focus_values = [6.0, 8.0, 10.0]
point.capture_count = 3

# Result: 100 points × 3 captures = 300 total images
```

## Focus Stacking Calculation

The focus stacking calculation matches the height steps logic from the web UI:

```javascript
// JavaScript (web UI)
const steps = 2;                    // User input
const levels = steps + 1;           // 3 levels
const positions = [];

for (let i = 0; i < levels; i++) {
    const position = min_focus + (max_focus - min_focus) * (i / (levels - 1));
    positions.push(position);
}
// Result: [6.0, 8.0, 10.0]
```

```python
# Python (backend)
steps = 2                           # From web UI
levels = steps + 1                  # 3 levels
focus_positions = []

for i in range(levels):
    if levels == 1:
        pos = (min_focus + max_focus) / 2.0
    else:
        pos = min_focus + (max_focus - min_focus) * (i / (levels - 1))
    focus_positions.append(pos)
# Result: [6.0, 8.0, 10.0]
```

## Integration Points

### Web UI → Backend
1. User configures focus in Quality Settings panel
2. `collectCustomQualitySettings()` creates focus object
3. Sent via `/api/scan/start` POST request
4. Validated by `CommandValidator.validate_scan_pattern()`
5. Passed to `orchestrator.apply_custom_scan_settings()`

### Backend → Camera Hardware
1. ScanPoint contains `focus_mode` and `focus_values`
2. During scan execution, camera controller reads these fields
3. Camera controller's `auto_focus()` method uses `focus_mode` parameter
4. For manual mode, sets lens position to `focus_values`
5. For AF modes, triggers autofocus as specified
6. For focus stacks, captures multiple images at each position

## Testing Checklist

### Web UI Testing
- [x] Focus controls added to Quality Settings panel
- [x] JavaScript functions work correctly
- [x] Manual focus slider updates display
- [x] Focus stack calculation shows correct positions
- [x] Settings save to custom profile
- [x] Settings load from saved profile
- [x] Reset to defaults works

### Backend Testing (To Do on Pi Hardware)
- [ ] Manual focus mode sets correct lens position
- [ ] Autofocus initial triggers AF once at start
- [ ] Continuous AF triggers before each capture
- [ ] Focus stacking creates correct number of captures
- [ ] Focus positions interpolate correctly
- [ ] Total capture count matches expectations
- [ ] All focus modes work with grid pattern
- [ ] All focus modes work with cylindrical pattern
- [ ] CSV export includes focus settings
- [ ] Scan metadata includes focus configuration

## Debug Logging

The implementation includes comprehensive logging for debugging:

```
📸 Applied web UI focus settings: mode=manual_stack, position=None, stack={'steps': 2, 'min_focus': 6.0, 'max_focus': 10.0}
📸 Applying web UI focus settings to scan pattern: mode=manual_stack
📸 Applied focus stacking to 100 points:
   Steps: 2, Levels: 3
   Positions: ['6.0', '8.0', '10.0']
   Total captures: 300
```

## Next Steps

1. **Test on Pi Hardware** - Deploy changes and test all 4 focus modes
2. **Verify Camera Integration** - Ensure camera controller properly reads focus settings
3. **Test CSV Export** - Verify focus columns export correctly
4. **Profile Defaults** - Define default focus settings for quality presets (Low/Medium/High/Ultra)
5. **Documentation** - Update user documentation with focus control guide

## Benefits

✅ **Universal Focus Control** - Works for all scan patterns (grid, cylindrical, future patterns)
✅ **Preset Integration** - Focus settings saved/loaded with camera presets
✅ **Focus Stacking Support** - Enables depth-of-field extension for better 3D reconstruction
✅ **Flexible Modes** - Supports manual, autofocus, and continuous AF workflows
✅ **Per-Point Control** - Backend supports CSV files with different focus at each point
✅ **Live Preview** - Web UI shows calculated focus positions and capture count
✅ **Type Safety** - Uses FocusMode enum for compile-time validation
✅ **Maintainable** - Clean separation between web UI, API, and backend logic

## Known Limitations

1. **Global Mode Only** - Web UI applies same focus mode to all points (CSV files still support per-point)
2. **No Mixed Modes** - Cannot combine autofocus and manual in same scan (by design)
3. **No Focus Bracketing** - Focus stack is manual positions only, not auto-calculated around AF result
4. **Hardware Dependent** - Requires Arducam autofocus cameras, won't work with fixed-focus cameras

## Future Enhancements

- [ ] Add focus bracketing mode (AF + stack around result)
- [ ] Support different focus modes per camera (stereo with different settings)
- [ ] Add focus sweep mode (continuous positions across range)
- [ ] Import/export focus profiles
- [ ] Focus quality metrics in scan results
- [ ] Advanced focus zone configuration from web UI
