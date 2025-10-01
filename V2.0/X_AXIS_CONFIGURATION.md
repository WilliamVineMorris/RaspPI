# X-Axis Configuration for Cylindrical Scanning

## Overview
The X-axis controls the horizontal camera position (radius from turntable center) and is configured with:
- **Hardware Range**: 0-200mm (physical X-axis travel)
- **Scanning Range**: 30-200mm (safe operational range with 30mm minimum clearance from center)

## Current Configuration

### Hardware Limits (scanner_config.yaml)
```yaml
axes:
  x_axis:
    type: "linear"
    units: "mm"
    min_limit: 0.0                # Hardware minimum
    max_limit: 200.0              # Hardware maximum travel
    home_position: 0.0
    max_feedrate: 1000            # mm/min
    steps_per_mm: 800
    has_limits: true
    homing_required: true
```

### Scanning Range Limits
- **Minimum Radius**: 30mm (safety margin from turntable center)
- **Maximum Radius**: 200mm (X-axis hardware limit)
- **Reason for 30mm minimum**: Prevents camera collision with turntable center, ensures safe clearance

### Cylindrical Scanning Usage
For cylindrical scans, the X-axis is used to set the **fixed camera radius** (distance from object center):

- **Radius Parameter**: X-axis position (30-200mm scanning range)
- **Fixed Position**: X-axis stays at one position during scan
- **Turntable Rotates**: Z-axis rotates the object at this fixed radius

## Validation Points

### 1. Web Interface (`web/web_interface.py`)
```python
# Validates radius parameter from user
if not (30.0 <= radius <= 200.0):
    raise ValueError(f"Camera radius {radius}mm outside valid range [30, 200]")
```

### 2. Pattern Parameters (`scanning/scan_patterns.py`)
```python
class CylindricalPatternParameters:
    x_start: float = 50.0   # Default camera radius (mm)
    x_end: float = 50.0     # Same as start for fixed radius
    
    # Validation in __post_init__:
    if self.x_start < 30.0 or self.x_start > 200.0:
        raise ValueError(f"x_start {self.x_start}mm outside valid range [30, 200]mm")
    if self.x_end < 30.0 or self.x_end > 200.0:
        raise ValueError(f"x_end {self.x_end}mm outside valid range [30, 200]mm")
```

### 3. Scan Orchestrator (`scanning/scan_orchestrator.py`)
```python
def create_cylindrical_pattern(self, radius: float, ...):
    """
    Args:
        radius: Fixed camera radius (X-axis position, 30-200mm scanning range)
    """
    # Validate radius is within safe scanning range
    if radius < 30.0 or radius > 200.0:
        raise ValueError(f"Camera radius {radius}mm outside valid range [30, 200]mm")
```

## Default Values

### Pattern Defaults
- **Default Radius**: 50mm (safe distance for typical objects)
- **Web UI Default**: 50mm (configurable in request)
- **Valid Range**: 30-200mm (enforced at all levels)

### Typical Usage Ranges
- **Small Objects (5-10cm)**: 40-60mm radius
- **Medium Objects (10-20cm)**: 70-120mm radius  
- **Large Objects (20-30cm)**: 130-180mm radius
- **Maximum**: 200mm (hardware limit)

## How X-Axis is Used in Cylindrical Scans

### Scan Pattern Generation
1. User specifies **radius** (camera distance from object)
2. System sets `x_start = x_end = radius` (fixed position)
3. Camera moves to X-axis position = radius
4. Y-axis moves vertically (height changes)
5. Z-axis rotates turntable (angular changes)
6. C-axis tilts camera (servo angle)

### Example Scan Configuration
```python
radius = 80.0          # Camera at 80mm from center
y_range = (20, 120)    # Height from 20mm to 120mm
y_step = 20.0          # 5 vertical positions
z_rotations = [0, 60, 120, 180, 240, 300]  # 6 rotation angles

Result:
- X-axis: Fixed at 80mm
- Y-axis: 5 positions (20, 40, 60, 80, 100, 120mm)
- Z-axis: 6 rotations (every 60°)
- Total: 5 × 6 = 30 scan positions
```

## Modifying X-Axis Limits

### If Hardware Changes Require Different Limits:

1. **Update Config File** (`config/scanner_config.yaml`):
```yaml
axes:
  x_axis:
    min_limit: 0.0        # Hardware minimum (don't change)
    max_limit: 300.0      # New maximum (if hardware upgraded)
```

2. **Update Web Interface Validation** (`web/web_interface.py` line ~271):
```python
if not (30.0 <= radius <= 300.0):  # Keep 30mm safety minimum, update maximum
    raise ValueError(f"Camera radius {radius}mm outside valid range [30, 300]")
```

3. **Update Pattern Validation** (`scanning/scan_patterns.py` line ~319):
```python
if self.x_start < 30.0 or self.x_start > 300.0:  # Keep 30mm minimum
    raise ValueError(f"x_start outside valid range [30, 300]mm")
```

4. **Update Orchestrator Validation** (`scanning/scan_orchestrator.py` line ~4680):
```python
if radius < 30.0 or radius > 300.0:  # Keep 30mm minimum
    raise ValueError(f"Camera radius outside valid range [30, 300]mm")
```

### Adjusting the Minimum Radius Safety Margin:

If you need a different minimum (e.g., 20mm or 40mm), update all validation points:
- Web interface: `if not (NEW_MIN <= radius <= 200.0)`
- Pattern parameters: `if self.x_start < NEW_MIN or self.x_start > 200.0`
- Orchestrator: `if radius < NEW_MIN or radius > 200.0`

**Warning**: Setting minimum below 30mm may cause camera-turntable collision!

## Safety Considerations

### Hardware Protection
- Homing required before movement
- Limit switches at 0mm and 200mm
- Software limits prevent overshoot
- Emergency stop available

### Validation Hierarchy
1. **Config** defines physical limits
2. **Web UI** validates user input
3. **Pattern** validates parameters
4. **Orchestrator** validates before execution
5. **Motion Controller** enforces hardware limits

## Testing X-Axis Range

### Manual Test Positions
```python
# Test positions within safe scanning range (30-200mm)
test_positions = [
    30.0,   # Minimum safe radius
    50.0,   # Small object distance
    80.0,   # Medium object distance
    120.0,  # Large object distance
    160.0,  # Very large object distance
    200.0   # Maximum hardware limit
]
```

### Scan Test Pattern
```python
# Small test scan at safe mid-range position
radius = 80.0   # Safe mid-range position
y_range = (30, 80)
z_rotations = [0, 90, 180, 270]  # 4 angles
```

## Troubleshooting

### "Radius outside valid range" Error
- Check requested radius value
- Must be between 30-200mm (not 0-29mm)
- 30mm minimum prevents collision with turntable center
- 200mm maximum is hardware limit

### "X-axis limit exceeded" Error
- System prevented unsafe movement
- Check if radius is below 30mm (too close to center)
- Verify radius doesn't exceed 200mm (hardware limit)
- Verify homing was successful

### Camera Too Close/Far from Object
- Adjust radius parameter (X-axis position)
- Typical range: 30-150mm for most objects
- Test with manual positioning first

## Related Configuration

### Y-Axis (Vertical)
- Range: 0-200mm
- Used for vertical camera height
- Independent of X-axis radius

### Z-Axis (Turntable)
- Range: 0-360° (continuous)
- Rotates object at fixed X radius
- No physical limits

### C-Axis (Servo Tilt)
- Range: -90° to +90°
- Camera angle adjustment
- Independent of X-axis position
