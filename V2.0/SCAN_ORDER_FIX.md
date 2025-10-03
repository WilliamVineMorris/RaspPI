# Scan Order Fix - Preview Now Matches Actual Scan

## Issue Identified
The preview visualization was showing scan points in a **different order** than the actual scan execution.

### Before Fix
- **Preview order**: Height first (outer loop) → Rotation second (inner loop)
  - All rotations at height 1
  - All rotations at height 2
  - All rotations at height 3
  - All rotations at height 4

- **Actual scan order**: Rotation first (outer loop) → Height second (inner loop)
  - All heights at rotation 0°
  - All heights at rotation 60°
  - All heights at rotation 120°
  - etc.

**Result**: Preview showed blue→red gradient going around the circle at each height, but actual scan would move vertically at each rotation position.

## Fix Applied

Updated `_generate_preview_points()` in `web/web_interface.py` to match the actual scan pattern from `CylindricalScanPattern.generate_points()`.

### Code Change (Lines 3231-3247)

**Before (incorrect order):**
```python
for height_idx, y_pos in enumerate(y_positions):  # Height first
    for rotation in z_rotations:                   # Rotation second
        preview_points.append({...})
```

**After (correct order):**
```python
for rotation in z_rotations:                       # Rotation first (matches actual scan)
    for height_idx, y_pos in enumerate(y_positions):  # Height second
        preview_points.append({...})
```

## Scan Order Explanation

### Actual Cylindrical Scan Pattern
From `scanning/scan_patterns.py` (lines 396-400):

```python
for z_rotation in z_rotations:  # Outer loop: ROTATION FIRST
    for y_pos, c_angle in y_servo_mapping:  # Inner loop: HEIGHT SECOND
        for x_pos in self._generate_x_positions(y_pos):
            # Create scan point at this position
```

**Why this order?**
1. **Minimize Z-axis moves**: Turntable rotation is the slowest/largest movement
2. **Efficient height scanning**: Move camera up/down at each rotation position
3. **Better coverage**: Complete vertical column before rotating
4. **Vibration settling**: Allows settling time after large rotation moves

### Visual Representation

**Correct Order (Rotation First):**
```
Position 1: Rotation=0°   → Heights: 40mm, 66mm, 93mm, 120mm
Position 2: Rotation=60°  → Heights: 40mm, 66mm, 93mm, 120mm
Position 3: Rotation=120° → Heights: 40mm, 66mm, 93mm, 120mm
Position 4: Rotation=180° → Heights: 40mm, 66mm, 93mm, 120mm
Position 5: Rotation=240° → Heights: 40mm, 66mm, 93mm, 120mm
Position 6: Rotation=300° → Heights: 40mm, 66mm, 93mm, 120mm
```

Total points: 6 rotations × 4 heights = 24 points

### Color Gradient Interpretation

The preview uses a blue→red color gradient based on scan order:
- **Blue points** (scan order 0-5): First rotation position, all heights
- **Cyan/Green points** (scan order 6-11): Second rotation position, all heights
- **Yellow/Orange points** (scan order 12-17): Third rotation position, all heights
- **Red points** (scan order 18-23): Last rotation positions, all heights

## Benefits of This Order

✅ **Efficient Motion**: Turntable rotates 6 times (large movements), camera moves vertically 24 times (small movements)  
✅ **Preview Accuracy**: What you see is exactly what will execute  
✅ **Motion Planning**: Rotation → settle → vertical scan → next rotation  
✅ **Predictable Timing**: Easy to estimate scan duration  
✅ **Vibration Management**: Large rotation moves followed by precise vertical captures

## Verification

### Preview Should Show:
1. **Vertical columns** of points changing color together
2. Blue→red gradient moving **around the circle** (rotation by rotation)
3. 6 color-grouped columns (one per rotation position)
4. 4 points per column (one per height)

### Actual Scan Will Execute:
1. Rotate turntable to 0°
2. Scan heights: 40mm → 66mm → 93mm → 120mm
3. Rotate turntable to 60°
4. Scan heights: 40mm → 66mm → 93mm → 120mm
5. Continue for remaining rotation positions

## Testing Confirmation

**Before testing on Pi:**
- Preview should show vertical color transitions (blue at bottom → red at top for each rotation)
- Color gradient should progress **around the circle** not **up the heights**

**During actual scan:**
- Watch FluidNC logs - should see Z rotation commands followed by multiple Y movements
- Camera should move vertically at each rotation position before turntable rotates again

---

**Status**: ✅ Fixed - Preview order now matches actual scan execution  
**Impact**: High - Ensures user expectations match reality  
**Testing**: Required on Pi to confirm FluidNC motion matches preview
