# Edge Detection Debugging Guide

**Issue**: Edge detection not finding objects  
**Root Cause**: Needs sharp image (autofocus first) + proper thresholds

---

## Test Results Analysis

### Problem: "⚠️ No edges detected in test_camera image"

This happens when:
1. **Image is blurry** (no autofocus before capture)
2. **Canny thresholds too high** (missing weak edges)
3. **Object outside search region** (center 70% doesn't contain object)
4. **Contours filtered out** (size constraints too strict)

---

## Updated Test Script

### What Changed:
✅ **Autofocus before capture** (2 second settle time)  
✅ **Multiple sensitivity tests** (Very Sensitive, Default, Maximum)  
✅ **Raw image saved** (inspect what camera actually sees)  
✅ **Better diagnostics** (edge pixel count, contour statistics)

### Run Test:
```bash
python3 test_edge_detection.py
```

### Expected Output:
```
🔍 Running autofocus to get sharp image...
   Autofocus state: Focused, lens: 7.05
💾 Saved raw capture: calibration/edge_detection_test/raw_capture.jpg

🔍 Testing different edge detection sensitivities...
   ✅ Very Sensitive (Canny 30/100): FOUND object at (850, 420, 450, 380)
   ✅ Default (Canny 50/150): FOUND object at (850, 420, 450, 380)
   ⚠️ Maximum Sensitivity (Canny 20/80): No detection

✅ BEST RESULT: Very Sensitive
```

---

## Debugging in Production

### Enhanced Logging:
The edge detector now provides detailed diagnostics:

```
🔍 Edge detection stats: 12450 edge pixels (8.34% of search region)
🔍 Found 23 total contours before filtering
   ✓ Contour 0: area=5230px (3.50%) - VALID
   ✓ Contour 1: area=1890px (1.27%) - VALID
   ✗ Contour 2: area=156px (0.10%) - filtered (too small)
   ✗ Contour 3: area=89234px (59.82%) - filtered (too large)
🎯 Edge detection found 2 object(s)
   → Selected: area=3.50% at (850, 420)
```

### What to Check:

1. **Edge Pixel Count**:
   - `< 1%`: Image too blurry or thresholds too high
   - `1-10%`: Good range
   - `> 20%`: Too noisy, increase thresholds

2. **Total Contours**:
   - `0`: No edges detected → lower Canny thresholds
   - `1-50`: Good range
   - `> 100`: Too sensitive → raise Canny thresholds

3. **Valid Contours After Filtering**:
   - `0`: Adjust `min_contour_area` / `max_contour_area`
   - `1-10`: Good range
   - `> 20`: Scene too complex, increase `min_contour_area`

---

## Tuning Guide

### If "No edges detected":
```yaml
edge_detection:
  canny_threshold1: 30  # Lower from 50
  canny_threshold2: 100  # Lower from 150
```

### If "No valid contours found":
```yaml
edge_detection:
  min_contour_area: 0.005  # Lower from 0.01 (0.5% instead of 1%)
  max_contour_area: 0.7    # Raise from 0.5 (70% instead of 50%)
```

### If detecting turntable instead of object:
```yaml
edge_detection:
  search_region: 0.6       # Smaller center region
  max_contour_area: 0.3    # Reject very large areas
```

### If detecting noise/small details:
```yaml
edge_detection:
  min_contour_area: 0.02   # Raise from 0.01 (2% minimum)
  gaussian_blur: 7         # More blur = less noise
```

---

## Visualization Analysis

Check saved images to understand detections:

### Panel 1: Search Region
- Yellow box shows area analyzed
- Should contain your object
- If not, increase `search_region`

### Panel 2: Edge Detection
- White pixels = detected edges
- Should outline object shape
- If blank, lower Canny thresholds
- If too noisy, raise Canny thresholds

### Panel 3: Contours Found
- Yellow = filtered out contours
- Green = selected contour
- Should highlight main object
- If highlighting turntable, adjust `max_contour_area`

### Panel 4: Focus Window
- Green box = final focus window
- Should frame object with padding
- If too tight/loose, adjust `padding`

---

## Comparison: Standalone Test vs. Production

### Standalone Test (`test_edge_detection.py`):
- **Purpose**: Quick hardware validation
- **Autofocus**: Basic continuous mode (2s settle)
- **Sensitivity**: Tests 3 different threshold combinations
- **Output**: Multiple visualizations for comparison

### Production (`main.py` calibration):
- **Purpose**: Full scanning workflow
- **Autofocus**: Two-pass calibration (static → object-focused)
- **Sensitivity**: Single configured threshold
- **Output**: One visualization per camera

**Key Difference**: Production has better autofocus (dedicated calibration routine), standalone is quicker but simpler.

---

## Common Issues & Solutions

### Issue: "Image shape: (1080, 1920, 3)" but no edges
**Cause**: Image is blurry (autofocus didn't work)  
**Solution**: 
- Check `AfState` in logs (should be "Focused" not "Idle")
- Increase autofocus settle time from 2s to 5s
- Run full calibration instead (`python3 main.py`)

### Issue: Edge detection works in test, fails in production
**Cause**: Different autofocus behavior between modes  
**Solution**: 
- Use production calibration (`main.py`)
- Check two-pass calibration logs for "EDGE PASS 2"
- Verify focus window source is "edge_detected" not "fallback"

### Issue: Detects turntable platform instead of object
**Cause**: Turntable has edges (wood grain, circular rim)  
**Solution**:
- Reduce `search_region` to 0.6 (smaller center area)
- Increase `min_contour_area` to 0.02 (ignore platform details)
- Reduce `max_contour_area` to 0.3 (reject very large areas)

---

## Next Steps After Test

1. **Check raw_capture.jpg**: Verify image is sharp and object is visible
2. **Check visualization panels**: Understand what edge detector sees
3. **Tune thresholds**: Based on diagnostic output
4. **Run full calibration**: `python3 main.py` for production testing
5. **Verify two-pass**: Look for "EDGE PASS 2" in calibration logs

---

## Files to Check

- **Raw capture**: `calibration/edge_detection_test/raw_capture.jpg`
- **Default test**: `calibration/edge_detection_test/test_camera_edge_detection.jpg`
- **Sensitive test**: `calibration/edge_test_Very_Sensitive/camera_Very_Sensitive_edge_detection.jpg`
- **Production output**: `calibration/edge_detection/camera0_edge_detection.jpg`

---

## Summary

✅ **Updated test script with autofocus**  
✅ **Multiple sensitivity levels tested**  
✅ **Enhanced diagnostic logging**  
✅ **Raw image saved for inspection**  
✅ **Tuning guide for production**

**Recommendation**: Run `python3 test_edge_detection.py` on Pi to see diagnostic output, then adjust thresholds in `scanner_config.yaml` based on results! 🔍
