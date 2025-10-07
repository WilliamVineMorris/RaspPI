# FluidNC Position Parsing Debug Enhancement

## Issue Investigation

User reported that C-axis tracking still has issues despite previous fixes. Concern raised about FluidNC potentially outputting variable number of fields in status reports.

### User's Critical Question:
**"Are the parsed coordinates containing all the values in a message or only the relevant ones?"**

Example FluidNC status from documentation:
```
<Idle|MPos:0.000,0.000,0.000|FS:0,0|Ov:100,100,100>
      └─────────┬──────────┘  └──┬─┘  └─────┬────┘
              MPos           FS      Ov (override)
```

**Concern**: If parser reads all commas, might it pick up values from FS or Ov fields?

## Code Analysis

### Current Parser Logic:
```python
# Line 574: Split by pipe first
content = status_line[1:-1]  # Remove < >
parts = content.split('|')

# parts = ["Idle", "MPos:0.000,0.000,0.000,25.000", "FS:0,0", "Ov:100,100,100"]

# Line 587: Process only MPos part
if part.startswith('MPos:'):
    coords = part[5:].split(',')
    # coords = ["0.000", "0.000", "0.000", "25.000"]
```

**Answer**: Parser is **CORRECT** - it splits by `|` first, so each field is isolated. The MPos coordinates cannot include values from FS or Ov.

### Potential Issues:
1. **Unknown**: Does FluidNC always output the same number of axes?
2. **Unknown**: Does FluidNC report actual C-axis position or always 0?
3. **Unknown**: Which coordinate index is actually the C-axis?

## Debug Logging Added

### 1. Raw FluidNC String (Line 593):
```python
coords_str = part[5:]  # Remove "MPos:"
logger.info(f"🔍 RAW FluidNC MPos: '{coords_str}' → {len(coords)} coordinates")
```

**Purpose**: See EXACTLY what FluidNC sends
**Expected output**:
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,25.000' → 4 coordinates
```

### 2. Parsed Coordinates (Line 621):
```python
all_coords = ', '.join([f"{c:.3f}" for c in parsed_coords])
logger.info(f"🔍 PARSED ({len(parsed_coords)} axes): [{all_coords}] → X={parsed_coords[0]:.3f}, Y={parsed_coords[1]:.3f}, Z={parsed_coords[2]:.3f}, C={parsed_coords[-1]:.3f}")
```

**Purpose**: Verify parsing and see all coordinate values
**Expected output**:
```
🔍 PARSED (4 axes): [200.000, 137.500, 0.000, 25.000] → X=200.000, Y=137.500, Z=0.000, C=25.000
```

### 3. Position Comparison (in controller):
```python
fluidnc_c = status.position.get('c', 0.0)
if fluidnc_c != self._commanded_c_position:
    logger.debug(f"🔍 C-axis: FluidNC reports {fluidnc_c:.1f}° but we're tracking {self._commanded_c_position:.1f}°")
```

**Purpose**: Compare FluidNC value vs tracked value
**Expected output** (if servo has no feedback):
```
🔍 C-axis: FluidNC reports 0.0° but we're tracking 25.0°
```

**OR** (if FluidNC does report position):
```
🔍 C-axis: FluidNC reports 25.0° but we're tracking 25.0°
```

## What the Logs Will Reveal

### Scenario 1: FluidNC Always Reports 4 Axes
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,25.000' → 4 coordinates
🔍 PARSED (4 axes): [200.000, 137.500, 0.000, 25.000] → C=25.000
```
**Result**: Using `[-1]` is correct

### Scenario 2: FluidNC Sometimes Reports 6 Axes
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,0.000,0.000,25.000' → 6 coordinates
🔍 PARSED (6 axes): [200.000, 137.500, 0.000, 0.000, 0.000, 25.000] → C=25.000
```
**Result**: Using `[-1]` is still correct

### Scenario 3: FluidNC Reports C=0 (No Feedback)
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,0.000' → 4 coordinates
🔍 PARSED (4 axes): [200.000, 137.500, 0.000, 0.000] → C=0.000
🔍 C-axis: FluidNC reports 0.0° but we're tracking 25.0°
```
**Result**: Tracking is necessary (expected for RC servos)

### Scenario 4: FluidNC Reports Actual C Position
```
🔍 RAW FluidNC MPos: '200.000,137.500,0.000,25.000' → 4 coordinates
🔍 PARSED (4 axes): [200.000, 137.500, 0.000, 25.000] → C=25.000
(No discrepancy warning)
```
**Result**: FluidNC does provide C feedback (unexpected but good!)

## Files Modified
✅ `motion/simplified_fluidnc_protocol_fixed.py` (Lines 587-627)
   - Added raw MPos string logging
   - Added parsed coordinates logging with all values
   - Changed debug → info level for visibility

## Testing Instructions

### 1. Restart Web Interface
```bash
python run_web_interface.py
```

### 2. Move C-Axis
Jog C-axis +25° and watch the logs for:

```
🔍 RAW FluidNC MPos: '...' → X coordinates
🔍 PARSED (X axes): [...] → X=..., Y=..., Z=..., C=...
```

### 3. Analyze Output

**Question 1**: How many coordinates does FluidNC report?
- 4 axes: X, Y, Z, C
- 6 axes: X, Y, Z, A, B, C

**Question 2**: What value does FluidNC report for C-axis?
- Always 0.000 → Servo has no feedback (expected)
- Actual position (e.g., 25.000) → Servo provides feedback (surprising!)

**Question 3**: Does the C value match commanded position?
- If yes → Can use FluidNC value directly
- If no → Must use tracked value

### 4. Report Findings
Please share the log lines that show:
1. `🔍 RAW FluidNC MPos:` - to see exact FluidNC output
2. `🔍 PARSED` - to see how we interpret it
3. Any `🔍 C-axis:` warnings - to see discrepancies

## Expected Resolution

Based on the debug logs, we'll know:
1. ✅ If parser is reading correct coordinates (no FS/Ov contamination)
2. ✅ If FluidNC reports 4 or 6 axes
3. ✅ If C-axis is at correct index (last position)
4. ✅ If FluidNC reports actual C position or always 0

This will definitively answer whether the parsing is correct or needs further fixes.

## Current Hypothesis

Based on user logs showing correct X, Y, Z but incorrect C:
- **Most Likely**: FluidNC reports C=0 (no servo feedback), tracking is working but gets overwritten
- **Possible**: FluidNC reports 6 axes and we're reading wrong index
- **Unlikely**: Parser is reading FS or Ov values (pipe splitting prevents this)

The debug logs will prove which hypothesis is correct.

## Status
- ✅ Debug logging added
- ⏳ Awaiting Pi hardware testing
- ⏳ User to provide raw FluidNC MPos output
- ⏳ Determine if additional fixes needed based on actual data
