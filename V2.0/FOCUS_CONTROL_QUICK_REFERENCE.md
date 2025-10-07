# Per-Point Focus Control - Quick Reference Card

## CSV Format

```csv
X,Y,Z,C,FocusMode,FocusValues
100,100,0,0,manual,8.0
100,100,45,0,manual,"6.0;8.0;10.0"
100,100,90,0,af,
100,100,135,0,,
```

## YAML Format

```yaml
scan_points:
  # Single manual focus
  - position: {x: 100, y: 100, z: 0, c: 0}
    focus_values: 8.0
  
  # Focus stacking (3 images at one point)
  - position: {x: 100, y: 100, z: 45, c: 0}
    focus_values: [6.0, 8.0, 10.0]
  
  # Autofocus once
  - position: {x: 100, y: 100, z: 90, c: 0}
    focus_mode: "af"
  
  # Use global config default
  - position: {x: 100, y: 100, z: 135, c: 0}
```

## Focus Modes

| Mode | CSV Value | Behavior | Speed | Use When |
|------|-----------|----------|-------|----------|
| **Manual (single)** | `manual` + `8.0` | Fixed lens position | 0.45s | Known distance |
| **Focus stacking** | `manual` + `"6.0;8.0;10.0"` | Multiple captures | 1.35s | Extended DOF |
| **Autofocus once** | `af` | Trigger AF, lock | 4.3s | Unknown distance |
| **Continuous AF** | `ca` | Continuous AF | 0.8s | Not recommended |
| **Global default** | (empty) | Use config | 0.45s | Standard scans |

## Lens Position Guide

| Value | Distance | Use Case |
|-------|----------|----------|
| 6.0 - 7.0 | 40-50cm | Far focus |
| **8.0 - 9.0** | **30-40cm** | **Default** |
| 10.0 - 12.0 | 20-30cm | Close-up |

## Focus Stacking Presets

| Depth | Positions | CSV Format |
|-------|-----------|------------|
| Standard | 3 | `"7.0;8.5;10.0"` |
| Extended | 4 | `"6.0;7.5;9.0;10.5"` |
| Maximum | 5 | `"5.0;7.0;9.0;11.0;13.0"` |

## Time Comparison

**100-point scan with 3 focus planes:**

| Method | Time | Savings |
|--------|------|---------|
| Old (3 scans) | 25 min | - |
| **New (stacking)** | **9.5 min** | **62% faster** |

## Output Files

**Single focus:**
```
scan_point_0001_camera_0.jpg
scan_point_0001_camera_1.jpg
```

**Focus stacking (3 positions):**
```
scan_point_0001_stack_0_camera_0.jpg  (lens 6.0)
scan_point_0001_stack_0_camera_1.jpg
scan_point_0001_stack_1_camera_0.jpg  (lens 8.0)
scan_point_0001_stack_1_camera_1.jpg
scan_point_0001_stack_2_camera_0.jpg  (lens 10.0)
scan_point_0001_stack_2_camera_1.jpg
```

## Metadata in EXIF

```json
{
  "lens_position": 8.0,
  "focus_stack_index": 0,
  "focus_stack_total": 3
}
```

## Common Patterns

**Pattern 1: Single scan with varying focus**
```csv
X,Y,Z,C,FocusMode,FocusValues
100,100,0,0,manual,8.0
100,100,90,0,manual,9.0
100,100,180,0,manual,8.5
```

**Pattern 2: Focus stack only where needed**
```csv
X,Y,Z,C,FocusMode,FocusValues
100,100,0,0,manual,8.0
100,100,90,0,manual,"7.0;8.5;10.0"
100,100,180,0,manual,8.0
```

**Pattern 3: Autofocus first, manual rest**
```csv
X,Y,Z,C,FocusMode,FocusValues
100,100,0,0,af,
100,100,90,0,manual,8.0
100,100,180,0,manual,8.0
```

## Configuration Default

**scanner_config.yaml:**
```yaml
cameras:
  focus:
    mode: "manual"
    manual_lens_position: 8.0
    autofocus:
      enable: true
      af_range: "macro"
```

## Quick Test Commands

```bash
# View focus metadata
exiftool session_*/scan_point_*.jpg | grep -i focus

# Count images
ls -l session_*/*.jpg | wc -l

# Check for focus stacking
ls -l session_*/scan_point_*_stack_*.jpg

# Watch logs
tail -f scanner.log | grep -E "(focus|stacking)"
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Images blurry | Increase lens position by 1.0 |
| Too much depth | Use focus stacking |
| AF unreliable | Switch to manual with known position |
| Stack not aligned | Use smaller position steps |

## See Also

- **PER_POINT_FOCUS_CONTROL.md** - Complete documentation
- **PER_POINT_FOCUS_IMPLEMENTATION_SUMMARY.md** - Technical details
- **scanner_config.yaml** - Configuration reference
