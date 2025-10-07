# Web UI Focus Integration - Visual Flow Diagram

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          WEB UI (scans.html)                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────── Quality Settings Panel ─────────────────────┐   │
│  │                                                                  │   │
│  │  Focus Mode: [Manual ▼]                                         │   │
│  │  ┌────────────────────────────────────────────────────┐        │   │
│  │  │ • Manual            → Fixed lens position          │        │   │
│  │  │ • Autofocus Initial → AF once at start             │        │   │
│  │  │ • Continuous        → AF before each capture       │        │   │
│  │  │ • Manual Stack      → Multiple positions (DOF)     │        │   │
│  │  └────────────────────────────────────────────────────┘        │   │
│  │                                                                  │   │
│  │  [Manual Mode Controls]                                         │   │
│  │  Focus Position: ━━━●━━━━━━ 8.0 (0-15 range)                   │   │
│  │                                                                  │   │
│  │  [Focus Stack Controls]                                         │   │
│  │  Stack Steps:    ━●━━━━━━━━ 2 (1-10)                           │   │
│  │  Min Focus:      [6.0]  (0-15)                                  │   │
│  │  Max Focus:      [10.0] (0-15)                                  │   │
│  │  Positions:      6.0, 8.0, 10.0 (3 levels)                     │   │
│  │  Captures/Point: 3                                              │   │
│  │                                                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  [Apply Custom Settings] ───► collectCustomQualitySettings()          │
│                                        │                                │
└────────────────────────────────────────┼────────────────────────────────┘
                                         │
                                         ▼
                          ┌──────────────────────────────┐
                          │   quality_settings object    │
                          ├──────────────────────────────┤
                          │ {                            │
                          │   resolution: [2312, 1736],  │
                          │   jpeg_quality: 85,          │
                          │   iso_preference: "low",     │
                          │   ...                        │
                          │   focus: {                   │
                          │     mode: "manual_stack",    │
                          │     stack_steps: 2,          │
                          │     min_focus: 6.0,          │
                          │     max_focus: 10.0          │
                          │   }                          │
                          │ }                            │
                          └──────────────────────────────┘
                                         │
                                         │ POST /api/scan/start
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                     WEB INTERFACE (web_interface.py)                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  api_scan_start() ──► validate_scan_pattern()                          │
│                              │                                          │
│                              ▼                                          │
│                    _execute_scan_start(pattern_data)                   │
│                              │                                          │
│                              │ Extracts quality_settings               │
│                              ▼                                          │
│              orchestrator.apply_custom_scan_settings(                  │
│                  quality_settings=quality_settings                     │
│              )                                                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                  SCAN ORCHESTRATOR (scan_orchestrator.py)               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  apply_custom_scan_settings(quality_settings, speed_settings):         │
│  ┌──────────────────────────────────────────────────────────┐         │
│  │ 1. Extract focus from quality_settings['focus']          │         │
│  │ 2. Store focus configuration:                            │         │
│  │    self._web_focus_mode = 'manual_stack'                │         │
│  │    self._web_focus_stack_settings = {                   │         │
│  │        'steps': 2,                                       │         │
│  │        'min_focus': 6.0,                                 │         │
│  │        'max_focus': 10.0                                 │         │
│  │    }                                                     │         │
│  │ 3. Apply other quality/speed settings                   │         │
│  │ 4. Return applied_settings dict                         │         │
│  └──────────────────────────────────────────────────────────┘         │
│                              │                                          │
│  ┌───────────────────────────┴────────────────────────┐               │
│  │                                                     │               │
│  ▼                                                     ▼               │
│  create_grid_pattern(...)              create_cylindrical_pattern(...) │
│  │                                     │                               │
│  │ 1. Create pattern parameters        │ 1. Calculate servo angles    │
│  │ 2. Generate GridScanPattern         │ 2. Create CylindricalPattern │
│  │ 3. Apply focus settings ────────────┼────► _apply_web_focus_to_   │
│  │                                     │       pattern()               │
│  └─────────────────────────────────────┘                               │
│                              │                                          │
│                              ▼                                          │
│  _apply_web_focus_to_pattern(pattern):                                │
│  ┌──────────────────────────────────────────────────────────┐         │
│  │ Get all points: points = pattern.generate_points()       │         │
│  │                                                           │         │
│  │ if mode == 'manual':                                     │         │
│  │     for point in points:                                 │         │
│  │         point.focus_mode = FocusMode.MANUAL             │         │
│  │         point.focus_values = 8.0                        │         │
│  │                                                           │         │
│  │ elif mode == 'autofocus_initial':                       │         │
│  │     for point in points:                                 │         │
│  │         point.focus_mode = FocusMode.AUTOFOCUS_ONCE     │         │
│  │                                                           │         │
│  │ elif mode == 'continuous':                              │         │
│  │     for point in points:                                 │         │
│  │         point.focus_mode = FocusMode.CONTINUOUS_AF      │         │
│  │                                                           │         │
│  │ elif mode == 'manual_stack':                            │         │
│  │     # Calculate interpolated positions                   │         │
│  │     levels = steps + 1  # 3 levels                       │         │
│  │     positions = []                                       │         │
│  │     for i in range(levels):                              │         │
│  │         pos = min + (max-min) * (i/(levels-1))          │         │
│  │         positions.append(pos)                            │         │
│  │     # [6.0, 8.0, 10.0]                                  │         │
│  │                                                           │         │
│  │     for point in points:                                 │         │
│  │         point.focus_mode = FocusMode.MANUAL             │         │
│  │         point.focus_values = [6.0, 8.0, 10.0]          │         │
│  │         point.capture_count = 3                         │         │
│  │                                                           │         │
│  │ Return modified pattern                                  │         │
│  └──────────────────────────────────────────────────────────┘         │
│                              │                                          │
│                              ▼                                          │
│                    Pattern with Focus Settings                         │
│                              │                                          │
└──────────────────────────────┼──────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        SCAN EXECUTION                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  For each point in pattern.generate_points():                          │
│  ┌──────────────────────────────────────────────────────────┐         │
│  │                                                           │         │
│  │  ScanPoint {                                             │         │
│  │    position: Position4D(x=50, y=100, z=0, c=0)          │         │
│  │    focus_mode: FocusMode.MANUAL                         │         │
│  │    focus_values: [6.0, 8.0, 10.0]                       │         │
│  │    capture_count: 3                                      │         │
│  │  }                                                       │         │
│  │                                                           │         │
│  │  1. Move to position (x, y, z, c)                       │         │
│  │  2. For each focus_value in focus_values:               │         │
│  │     a) Set lens position to focus_value                 │         │
│  │     b) Capture image                                     │         │
│  │     c) Save with metadata: focus=6.0, 8.0, or 10.0      │         │
│  │                                                           │         │
│  │  Result: 3 images at this position                      │         │
│  │          scan_0001_f6.0.jpg                             │         │
│  │          scan_0001_f8.0.jpg                             │         │
│  │          scan_0001_f10.0.jpg                            │         │
│  │                                                           │         │
│  └──────────────────────────────────────────────────────────┘         │
│                                                                         │
│  Total Scan Results (example 100 points × 3 focus levels):            │
│  ├─ 300 total images                                                   │
│  ├─ Each with focus metadata                                           │
│  ├─ Organized by position and focus level                             │
│  └─ Ready for focus stacking in post-processing                       │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Integration Points

### 1. Web UI → Backend API
- **Format**: JSON POST to `/api/scan/start`
- **Key**: `quality_settings.focus` object
- **Validation**: CommandValidator checks structure

### 2. Backend API → Orchestrator
- **Method**: `apply_custom_scan_settings(quality_settings, ...)`
- **Action**: Extracts focus, stores in orchestrator state
- **Result**: Focus settings available for pattern generation

### 3. Orchestrator → Pattern
- **Method**: `_apply_web_focus_to_pattern(pattern)`
- **Action**: Modifies all ScanPoints with focus configuration
- **Timing**: After pattern generation, before scan execution

### 4. Pattern → Camera Hardware
- **Interface**: ScanPoint.focus_mode and ScanPoint.focus_values
- **Action**: Camera controller reads during capture
- **Result**: Hardware lens positioned or AF triggered

## Focus Modes Translation

| Web UI Mode         | Backend FocusMode      | Camera Behavior                    |
|---------------------|------------------------|------------------------------------|
| `manual`            | `FocusMode.MANUAL`     | Set lens to fixed position         |
| `autofocus_initial` | `FocusMode.AUTOFOCUS_ONCE` | AF once, use result for all   |
| `continuous`        | `FocusMode.CONTINUOUS_AF` | AF before every capture        |
| `manual_stack`      | `FocusMode.MANUAL`     | Multiple captures at positions     |

## Example: Focus Stack Scan

**Input**: 
- Pattern: 100 positions (cylindrical scan)
- Focus: Manual stack with 2 steps (3 levels: 6.0, 8.0, 10.0)

**Processing**:
1. Web UI sends: `{focus: {mode: 'manual_stack', stack_steps: 2, min_focus: 6.0, max_focus: 10.0}}`
2. Orchestrator stores: `_web_focus_mode='manual_stack'`, `_web_focus_stack_settings={...}`
3. Pattern generates: 100 ScanPoints (original)
4. Focus applied: Each point gets `focus_values=[6.0, 8.0, 10.0]`, `capture_count=3`
5. Execution: 100 positions × 3 captures = **300 total images**

**Output Structure**:
```
session_12345/
├── position_0001/
│   ├── image_f6.0.jpg  (focus at 6.0mm)
│   ├── image_f8.0.jpg  (focus at 8.0mm)
│   └── image_f10.0.jpg (focus at 10.0mm)
├── position_0002/
│   ├── image_f6.0.jpg
│   ├── image_f8.0.jpg
│   └── image_f10.0.jpg
...
└── metadata.json
```
