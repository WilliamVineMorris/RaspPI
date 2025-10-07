# Testing Guide: Web UI Focus Integration

## Pre-Testing Checklist

### Files Modified (Verify Changes Deployed)
- ✅ `web/templates/scans.html` - Web UI with focus controls
- ✅ `scanning/scan_orchestrator.py` - Backend focus handling

### Git Deployment
```bash
# On development PC
git add web/templates/scans.html
git add scanning/scan_orchestrator.py
git commit -m "Add web UI focus control integration"
git push origin Test

# On Raspberry Pi
cd ~/RaspPI/V2.0
git pull origin Test
```

## Test Suite

### Test 1: Manual Focus Mode
**Objective**: Verify single focus position applied to all points

**Steps**:
1. Open web interface: `http://raspberrypi.local:5000`
2. Navigate to Scans tab
3. Configure cylindrical scan (any parameters)
4. In Quality Settings → Focus Control:
   - Select "Manual Focus"
   - Set position to 8.0
5. Click "Apply Custom Settings"
6. Start scan

**Expected Results**:
- ✅ Backend logs: `📸 Applied web UI focus settings: mode=manual, position=8.0`
- ✅ Backend logs: `📸 Applied manual focus position 8.0 to X points`
- ✅ All images captured at lens position 8.0
- ✅ Metadata includes `focus_position: 8.0`

**Validation**:
```bash
# Check scan logs
journalctl -u scanner-service | grep "focus"

# Check image metadata
exiftool ~/scanner_data/sessions/latest/*/image_*.jpg | grep LensPosition
```

---

### Test 2: Autofocus Initial (Calibration)
**Objective**: Verify AF triggered once at start

**Steps**:
1. In Quality Settings → Focus Control:
   - Select "Autofocus Initial (Calibration)"
2. Apply settings and start scan

**Expected Results**:
- ✅ Backend logs: `📸 Applied autofocus_initial to X points`
- ✅ Camera performs AF at first position only
- ✅ Subsequent captures use same focus value
- ✅ Faster scan than continuous AF

**Validation**:
```bash
# Check for single AF event
grep "Autofocus triggered" ~/scanner_data/sessions/latest/scan.log

# Verify all images have same focus value
exiftool ~/scanner_data/sessions/latest/*/image_*.jpg | grep LensPosition | sort -u
# Should show only 1-2 unique values
```

---

### Test 3: Continuous Autofocus
**Objective**: Verify AF triggered before each capture

**Steps**:
1. In Quality Settings → Focus Control:
   - Select "Continuous Autofocus"
2. Apply settings and start scan

**Expected Results**:
- ✅ Backend logs: `📸 Applied continuous autofocus to X points`
- ✅ Camera performs AF before every capture
- ✅ Focus adapts to object distance changes
- ✅ Slower scan due to AF overhead

**Validation**:
```bash
# Count AF events (should match point count)
grep -c "Autofocus triggered" ~/scanner_data/sessions/latest/scan.log

# Verify varied focus values
exiftool ~/scanner_data/sessions/latest/*/image_*.jpg | grep LensPosition | sort -u
# Should show multiple different values
```

---

### Test 4: Manual Focus Stacking (Critical Test)
**Objective**: Verify focus stacking with interpolated positions

**Test 4a: 2 Steps (3 Levels)**
**Steps**:
1. In Quality Settings → Focus Control:
   - Select "Manual Focus Stacking"
   - Stack Steps: 2
   - Min Focus: 6.0
   - Max Focus: 10.0
2. Verify live preview shows: "Focus Positions: 6.0, 8.0, 10.0"
3. Verify capture count shows: "3 captures per point"
4. Apply settings and start scan with 10 positions

**Expected Results**:
- ✅ Web UI preview: `6.0, 8.0, 10.0` (3 levels)
- ✅ Backend logs: `📸 Applied focus stacking to 10 points:`
- ✅ Backend logs: `Steps: 2, Levels: 3`
- ✅ Backend logs: `Positions: ['6.0', '8.0', '10.0']`
- ✅ Backend logs: `Total captures: 30`
- ✅ Each position has 3 images
- ✅ Total images: 10 positions × 3 levels = 30 images

**Validation**:
```bash
# Check total image count
find ~/scanner_data/sessions/latest -name "*.jpg" | wc -l
# Should be 30

# Check focus values in metadata
exiftool ~/scanner_data/sessions/latest/*/image_*.jpg | grep LensPosition | sort
# Should show 3 unique values: 6.0, 8.0, 10.0
# Each value should appear 10 times

# Verify each position has 3 images
for dir in ~/scanner_data/sessions/latest/position_*/; do
    count=$(ls "$dir"/*.jpg 2>/dev/null | wc -l)
    echo "$(basename $dir): $count images"
done
# Each should show: position_XXXX: 3 images
```

**Test 4b: 5 Steps (6 Levels)**
**Steps**:
1. Change settings:
   - Stack Steps: 5
   - Min Focus: 4.0
   - Max Focus: 12.0
2. Verify preview: `4.0, 5.6, 7.2, 8.8, 10.4, 12.0`
3. Start scan with 5 positions

**Expected Results**:
- ✅ 6 interpolated positions
- ✅ Total images: 5 positions × 6 levels = 30 images
- ✅ Focus values: 4.0, 5.6, 7.2, 8.8, 10.4, 12.0

---

### Test 5: Preset Save/Load
**Objective**: Verify focus settings persist in profiles

**Steps**:
1. Configure focus settings (any mode)
2. Save as custom profile: "Test_Focus_Profile"
3. Change to different focus settings
4. Load "Test_Focus_Profile"

**Expected Results**:
- ✅ Focus mode dropdown updates
- ✅ Focus position slider updates (if manual)
- ✅ Stack settings update (if manual_stack)
- ✅ Display values update correctly
- ✅ Correct panels shown/hidden

---

### Test 6: Reset to Defaults
**Objective**: Verify reset functionality

**Steps**:
1. Configure any focus settings
2. Click "Reset to Defaults"

**Expected Results**:
- ✅ Focus mode: Manual
- ✅ Focus position: 8.0
- ✅ Stack steps: 1
- ✅ Min focus: 6.0
- ✅ Max focus: 10.0
- ✅ Display values update
- ✅ Manual panel shown

---

### Test 7: Grid Pattern Integration
**Objective**: Verify focus works with grid scans

**Steps**:
1. Create grid scan pattern
2. Configure focus stacking (2 steps)
3. Start scan

**Expected Results**:
- ✅ Focus applied to all grid points
- ✅ Each grid position has 3 images
- ✅ Total images = grid_points × 3

---

### Test 8: CSV Export
**Objective**: Verify focus columns in exported CSV

**Steps**:
1. Run scan with focus stacking
2. Export scan data to CSV

**Expected Results**:
- ✅ CSV has `FocusMode` column
- ✅ CSV has `FocusValues` column
- ✅ Values match scan configuration
- ✅ Can re-import CSV and reproduce scan

**Validation**:
```bash
# Check CSV columns
head -1 ~/scanner_data/sessions/latest/scan_points.csv
# Should include: ...,FocusMode,FocusValues

# Check values
cat ~/scanner_data/sessions/latest/scan_points.csv | cut -d',' -f<focus_column>
# Should show: manual, manual, manual... or stack values
```

---

## Performance Tests

### Test 9: Scan Duration Comparison
**Objective**: Measure impact of different focus modes

**Setup**: Same cylindrical scan, 50 positions

**Modes to Test**:
1. Manual focus
2. Autofocus initial
3. Continuous autofocus
4. Manual stack (2 steps)

**Expected Results**:
| Mode                | Expected Duration | Images |
|---------------------|-------------------|--------|
| Manual              | ~5 min            | 50     |
| Autofocus Initial   | ~6 min            | 50     |
| Continuous AF       | ~15 min           | 50     |
| Manual Stack (2)    | ~8 min            | 150    |

**Notes**:
- Continuous AF slowest (AF overhead per point)
- Manual stack increases images but not much time
- Autofocus initial good balance

---

### Test 10: Focus Quality Assessment
**Objective**: Verify focus accuracy

**Steps**:
1. Place target with fine details at known distance
2. Run scan with manual focus at calculated position
3. Run scan with continuous AF
4. Compare sharpness

**Metrics**:
- Sharpness score (Laplacian variance)
- Edge definition
- Visual inspection

**Tools**:
```python
# Sharpness calculation
import cv2
image = cv2.imread('image.jpg', cv2.IMREAD_GRAYSCALE)
sharpness = cv2.Laplacian(image, cv2.CV_64F).var()
print(f"Sharpness: {sharpness}")
```

---

## Error Handling Tests

### Test 11: Invalid Focus Values
**Objective**: Verify validation

**Test Cases**:
- [ ] Focus position > 15.0 → Should clamp to 15.0
- [ ] Focus position < 0.0 → Should clamp to 0.0
- [ ] Stack steps < 1 → Should default to 1
- [ ] Min > Max → Should swap or error
- [ ] Missing focus settings → Should use defaults

---

### Test 12: Hardware Failure
**Objective**: Graceful degradation

**Test Cases**:
- [ ] Camera doesn't support AF → Fallback to manual
- [ ] AF fails → Retry or use previous value
- [ ] Invalid lens position → Clamp to valid range

---

## Debug Checklist

If tests fail, check:

1. **Web UI Issues**
   ```javascript
   // Browser console
   console.log("Focus settings:", collectCustomQualitySettings().focus);
   ```

2. **Backend Logs**
   ```bash
   # Check orchestrator logs
   journalctl -u scanner-service -f | grep "📸"
   
   # Check for errors
   journalctl -u scanner-service | grep -i error | tail -20
   ```

3. **Network Traffic**
   ```bash
   # Monitor API requests
   # Browser DevTools → Network → Filter: scan/start
   # Check POST body for focus object
   ```

4. **File Verification**
   ```bash
   # Verify changes deployed
   grep "_apply_web_focus_to_pattern" ~/RaspPI/V2.0/scanning/scan_orchestrator.py
   grep "customFocusMode" ~/RaspPI/V2.0/web/templates/scans.html
   ```

---

## Success Criteria

✅ **All 4 focus modes work correctly**
✅ **Focus stacking produces correct number of images**
✅ **Settings save/load in profiles**
✅ **CSV export includes focus data**
✅ **Works with both grid and cylindrical patterns**
✅ **Performance is acceptable**
✅ **Error handling is graceful**

---

## Reporting Results

**Please test and report using this format:**

```markdown
## Test Results - [Date]

### Test 1: Manual Focus
- Status: ✅ PASS / ❌ FAIL
- Issues: [None / describe]
- Logs: [Attach relevant logs]

### Test 2: Autofocus Initial
- Status: ✅ PASS / ❌ FAIL
- Issues: [None / describe]

... (continue for all tests)

### Overall Assessment
- Ready for production: YES / NO
- Major issues: [List]
- Minor issues: [List]
- Recommendations: [List]
```

---

## Quick Test (5 Minutes)

If time is limited, run this minimal test:

1. **Setup**: Cylindrical scan, 10 positions
2. **Test Manual Stack**: 
   - Mode: Manual Focus Stacking
   - Steps: 1 (2 levels)
   - Min: 7.0, Max: 9.0
3. **Verify**: 
   - Backend logs show focus stacking applied
   - Total images = 10 positions × 2 levels = 20 images
   - Check metadata for focus values 7.0 and 9.0

If this passes, the integration is fundamentally working!
