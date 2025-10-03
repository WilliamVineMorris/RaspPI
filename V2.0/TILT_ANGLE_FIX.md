# Servo Tilt Angle Calculation Fix

**Date**: 2025-10-03  
**Issue**: Incorrect sign in servo tilt angle calculation

---

## Problem Description

The servo tilt angles were being calculated with **inverted signs**, causing:
- Higher camera positions to show **smaller** downward angles
- Lower camera positions to show **larger** downward angles

**Example** (Focus at 20mm, Radius 100mm):
- Camera at **120mm** (100mm above focus): Showed **-21.8°** ❌ (should be more negative)
- Camera at **66.7mm** (46.7mm above focus): Showed **-7.6°** ❌ (should be less negative)

The angles were backwards!

---

## Root Cause

Both backend and frontend had an **unnecessary negative sign** in the calculation:

```python
# WRONG - Had extra negative sign
tilt_angle = -math.atan2(vertical_dist, horizontal_dist) * 180 / math.pi
```

This inverted the natural result from `atan2()`:
- When camera is **above** focus: `vertical_dist = focus_y - camera_y` is **negative**
- `atan2(negative, positive)` naturally returns **negative angle** ✓
- Adding `-` sign made it **positive** ❌ (backwards!)

---

## Solution

### Fix 1: Remove Negative Sign from Backend Calculation
**File**: `web/web_interface.py` (~line 2995)

**Before**:
```python
tilt_angle = -math.atan2(vertical_dist, horizontal_dist) * 180 / math.pi
```

**After**:
```python
tilt_angle = math.atan2(vertical_dist, horizontal_dist) * 180 / math.pi
```

**Explanation**:
- `vertical_dist = servo_y_focus - y_pos`
- When camera is **above** focus (y_pos > focus): `vertical_dist` is **negative** → `atan2()` returns **negative** (down) ✓
- When camera is **below** focus (y_pos < focus): `vertical_dist` is **positive** → `atan2()` returns **positive** (up) ✓
- Hardware convention: **Negative = down, Positive = up** ✓

### Fix 2: Simplify Frontend to Use Backend Value
**File**: `web/templates/scans.html` (~line 2931-2950)

**Before**:
```javascript
let actualTiltAngle = p.c; // Default from point data

if (servoTiltMode === 'manual') {
    actualTiltAngle = manualAngle;
} else if (servoTiltMode === 'focus_point') {
    // Recalculate angle (was overriding backend value)
    actualTiltAngle = -Math.atan2(dz, horizontalDist) * 180 / Math.PI;
} else if (servoTiltMode === 'none') {
    actualTiltAngle = 0;
}
```

**After**:
```javascript
// Use tilt angle from backend (already calculated correctly)
let actualTiltAngle = p.c;
```

**Explanation**:
- Backend now correctly calculates `c_angles` for all modes
- Frontend should **trust the backend value** instead of recalculating
- Eliminates duplicate logic and potential inconsistencies

---

## Expected Behavior After Fix

**Scenario**: Focus point at 20mm, Radius 100mm

| Camera Height | Vertical Distance | Expected Angle | Calculation |
|--------------|-------------------|----------------|-------------|
| **120mm** | 20 - 120 = **-100mm** | **~-45°** (steep down) | `atan2(-100, 100) = -45°` |
| **80mm** | 20 - 80 = **-60mm** | **~-31°** (moderate down) | `atan2(-60, 100) = -31°` |
| **40mm** | 20 - 40 = **-20mm** | **~-11°** (gentle down) | `atan2(-20, 100) = -11°` |
| **20mm** | 20 - 20 = **0mm** | **0°** (horizontal) | `atan2(0, 100) = 0°` |
| **10mm** | 20 - 10 = **+10mm** | **~+6°** (gentle up) | `atan2(10, 100) = +6°` |

**Key Points**:
- ✅ Higher positions → **More negative angles** (steeper downward tilt)
- ✅ Lower positions → **Less negative angles** (gentler downward tilt)
- ✅ At focus height → **Zero angle** (horizontal)
- ✅ Below focus → **Positive angles** (upward tilt)

---

## Testing Checklist

### Visual Verification (3D Preview):
- [ ] Point 11 (120mm height) shows **MORE negative** tilt than Point 9 (66.7mm)
- [ ] Camera tilt lines **converge** at focus point (red cross marker)
- [ ] Angles increase in magnitude as camera gets further from focus height
- [ ] No unexpected reversals or discontinuities in angle progression

### Numerical Verification (Hover Tooltips):
For **Focus Y = 20mm, Radius = 100mm**:
- [ ] Height 120mm → Tilt ≈ **-45°** (was -21.8°)
- [ ] Height 100mm → Tilt ≈ **-39°** (new)
- [ ] Height 80mm → Tilt ≈ **-31°** (new)
- [ ] Height 66.7mm → Tilt ≈ **-25°** (was -7.6°)
- [ ] Height 40mm → Tilt ≈ **-11°** (new)
- [ ] Height 20mm → Tilt ≈ **0°** (horizontal at focus)

### Manual Mode Test:
- [ ] Set manual angle to **-15°**
- [ ] All points show **exactly -15°** regardless of height
- [ ] Lines are parallel and point in same direction

### None Mode Test:
- [ ] All points show **0°** (horizontal)
- [ ] Lines are parallel to XY plane

---

## Mathematical Verification

### Correct Formula:
```
tilt_angle = atan2(vertical_distance, horizontal_distance) * 180 / π

where:
  vertical_distance = focus_y - camera_y
  horizontal_distance = radius
```

### Example Calculation (Point 11):
```
Camera at: (100mm radius, 120mm height)
Focus at: (0, 0, 20mm)

vertical_distance = 20 - 120 = -100mm
horizontal_distance = 100mm

tilt_angle = atan2(-100, 100) * 180 / π
           = atan2(-1, 1) * 180 / π
           = -45° ✓

Result: -45° (pointing down toward focus) ✓
```

### Example Calculation (Point 9):
```
Camera at: (100mm radius, 66.7mm height)
Focus at: (0, 0, 20mm)

vertical_distance = 20 - 66.7 = -46.7mm
horizontal_distance = 100mm

tilt_angle = atan2(-46.7, 100) * 180 / π
           ≈ -25° ✓

Result: -25° (less steep down than Point 11) ✓
```

---

## Files Modified

1. **`web/web_interface.py`**: Line ~2995
   - Removed negative sign from `tilt_angle` calculation
   - Added clearer comments explaining the hardware convention

2. **`web/templates/scans.html`**: Lines ~2931-2950
   - Removed frontend angle recalculation for all modes
   - Frontend now trusts backend `p.c` value
   - Eliminates duplicate logic

---

## Impact on Other Modes

### Manual Mode:
- ✅ No change - backend uses `servo_manual_angle` directly
- ✅ All points get same angle as before

### None Mode:
- ✅ No change - backend uses 0° for all points
- ✅ All points horizontal as before

### Focus Point Mode:
- ✅ **FIXED** - angles now have correct signs
- ✅ Steeper angles for positions further from focus

---

## Related Documentation

See **`VISUALIZATION_FIXES_SUMMARY.md`** for the complete set of visualization fixes including:
- Height step calculation correction
- Focus point line endpoint visualization
- Equal X/Y axis scaling

---

## Hardware Convention Reference

**Servo Tilt Hardware Convention**:
- **0°** = Horizontal (camera looking straight ahead toward center)
- **Negative angles** (e.g., -45°) = Tilted **DOWN** (below horizontal)
- **Positive angles** (e.g., +30°) = Tilted **UP** (above horizontal)
- **Valid range**: Typically -75° to +75° (check hardware specs)

This convention matches the natural output of `atan2()` when:
- Looking **down** at something below → negative vertical distance → negative angle ✓
- Looking **up** at something above → positive vertical distance → positive angle ✓
