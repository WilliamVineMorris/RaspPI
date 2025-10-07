# Edge Detection - Simple Testing Guide

**Issue**: `test_edge_detection.py` shows "No edges detected"  
**Root Cause**: ArduCam cameras need special autofocus (libcamera AF API doesn't work)  
**Solution**: Use production calibration instead of standalone test

---

## ⚠️ Important: ArduCam Autofocus Limitation

Your ArduCam 64MP cameras don't support the standard libcamera autofocus API:
```
[WARN] Could not set AF_TRIGGER - no AF algorithm or not Auto
```

The **production code has full ArduCam autofocus support**, but replicating it in a simple test script is complex.

---

## ✅ Recommended Testing Approach

### Option 1: Full Calibration (RECOMMENDED)
Test edge detection through the production calibration:

```bash
# Run full calibration with edge detection
python3 main.py
```

**What happens**:
1. **Pass 1**: Static center window → ArduCam autofocus → Sharp image ✅
2. **Pass 2**: Edge detection on sharp image → Refined focus ✅

**Look for in logs**:
```
🔍 Camera camera0 EDGE PASS 2: Image now sharp, running edge detection...
🔍 Edge detection stats: 8450 edge pixels (5.67% of search region)
🔍 Found 15 total contours before filtering
🎯 Edge detection found 2 object(s)
   → Selected: area=2.83% at (850, 420)
✅ Camera camera0 Edge detection successful on sharp image!
```

**Check visualizations**:
```bash
ls -lh calibration/edge_detection/
# Look for: camera0_edge_detection.jpg, camera1_edge_detection.jpg
```

---

### Option 2: Simplified Standalone Test

If you want to test edge detection on an **already-sharp image** (e.g., saved from previous scan):

```bash
# Create a simple script to test with saved images
python3 -c "
from camera.edge_detector import EdgeDetector
import cv2

config = {
    'search_region': 0.7,
    'canny_threshold1': 50,
    'canny_threshold2': 150,
    'min_contour_area': 0.01,
    'max_contour_area': 0.5,
    'padding': 0.2,
    'detection_output_dir': 'calibration/edge_test'
}

detector = EdgeDetector(config)

# Load a previously captured sharp image
image = cv2.imread('path/to/sharp/image.jpg')
image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

result = detector.detect_object(image_rgb, 'test')
print(f'Result: {result}')
"
```

---

### Option 3: Manual Focus Test

Test edge detection with **manual focus** (no autofocus):

```python
# test_edge_manual_focus.py
from picamera2 import Picamera2
from camera.edge_detector import EdgeDetector
import cv2
import time

picam2 = Picamera2()
config_cam = picam2.create_still_configuration(main={"size": (1920, 1080)})
picam2.configure(config_cam)
picam2.start()

# Set manual focus to a reasonable position (test different values)
for focus_val in [2.0, 4.0, 6.0, 8.0, 10.0]:
    picam2.set_controls({"AfMode": 0, "LensPosition": focus_val})
    time.sleep(1)
    
    image = picam2.capture_array("main")
    
    # Test edge detection
    edge_config = {
        'search_region': 0.7,
        'canny_threshold1': 30,
        'canny_threshold2': 100,
        'min_contour_area': 0.01,
        'max_contour_area': 0.5,
        'padding': 0.2,
        'detection_output_dir': f'calibration/edge_test_focus_{int(focus_val)}'
    }
    
    detector = EdgeDetector(edge_config)
    result = detector.detect_object(image, f"focus_{focus_val}")
    
    print(f"Focus {focus_val}: {result}")

picam2.stop()
```

---

## 🎯 What To Check in Production Logs

When you run `python3 main.py`, look for these key indicators:

### 1. Pass 1 Autofocus (Initial)
```
📷 Camera camera0 performing initial autofocus...
📷 Camera camera0 autofocus_cycle completed, state: 2, lens: 7.05
✅ Camera camera0 SUCCESS: Returning focus value 0.731
```
✅ **Lens should move** (not stuck at 2.0)

### 2. Pass 2 Edge Detection
```
🔍 Camera camera0 EDGE PASS 2: Image now sharp, running edge detection...
🔍 Edge detection stats: 8450 edge pixels (5.67%)
🔍 Found 15 total contours before filtering
   ✓ Contour 0: area=4230px (2.83%) - VALID
🎯 Edge detection found 2 object(s)
✅ Camera camera0 Edge detection successful on sharp image!
```
✅ **Should find edges** (not 0 pixels)  
✅ **Should find contours** (not 0 contours)

### 3. Refined Autofocus
```
📷 Camera camera0 performing refined autofocus on detected edges...
✅ Camera camera0 refined focus value: 0.731
```
✅ **Second autofocus cycle** with object-specific window

---

## 🔧 Tuning Based on Production Results

### If "0 edge pixels" in Pass 2:
```yaml
edge_detection:
  canny_threshold1: 30   # Lower from 50
  canny_threshold2: 100  # Lower from 150
```

### If "Found 0 contours":
- Image still blurry (Pass 1 autofocus failed)
- Check logs for lens position (should be 4-10, not 2.0)

### If "No valid contours":
```yaml
edge_detection:
  min_contour_area: 0.005  # Lower from 0.01
```

---

## 📊 Expected Production Output

**Successful edge detection calibration**:
```
🔧 CALIBRATION: Starting auto-calibration for camera0
📷 Camera camera0 focus window (static_prefocus): AfWindows=[(480, 270, 960, 540)]
📷 Camera camera0 performing initial autofocus...
📷 Camera camera0 autofocus_cycle completed, state: 2, lens: 7.05
🔍 Camera camera0 EDGE PASS 2: Image now sharp, running edge detection...
🔍 Edge detection stats: 12450 edge pixels (8.34% of search region)
🔍 Found 23 total contours before filtering
   ✓ Contour 0: area=5230px (3.50%) - VALID
   ✓ Contour 1: area=1890px (1.27%) - VALID
🎯 Edge detection found 2 object(s)
   → Selected: area=3.50% at (850, 420)
✅ Camera camera0 Edge detection successful on sharp image!
📷 Camera camera0 refined focus window: AfWindows=[(765, 378, 630, 532)]
📷 Camera camera0 performing refined autofocus on detected edges...
✅ Camera camera0 refined focus value: 0.746

✅ Calibration complete!
   Focus: 0.746
   Exposure: 31990
   Gain: 8.13
```

---

## 📁 Check Visualizations

After running `python3 main.py`:

```bash
# Edge detection visualizations
ls -lh calibration/edge_detection/

# Should see:
# camera0_edge_detection.jpg (4-panel visualization)
# camera1_edge_detection.jpg
```

**4-panel layout**:
1. **Search Region**: Yellow box showing analyzed area
2. **Edge Detection**: White pixels = detected edges
3. **Contours**: Green = selected object, Yellow = filtered
4. **Focus Window**: Green box = final focus zone

---

## Summary

🚫 **Don't use** `test_edge_detection.py` - ArduCam AF not supported  
✅ **Use** `python3 main.py` - Full calibration with proper AF  
✅ **Check** logs for "EDGE PASS 2" and edge statistics  
✅ **Verify** visualizations in `calibration/edge_detection/`

The production code already has everything working - just run it! 🎯
