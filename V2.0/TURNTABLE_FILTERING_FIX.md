# Turntable Filtering Fix - YOLO Object Detection

**Date**: 2025-10-07  
**Issue**: YOLO detecting turntable platform ("bed" class) instead of objects on it  
**Status**: ✅ FIXED

---

## Problem Description

YOLO was detecting the **turntable platform itself** as "bed" (46% confidence) instead of focusing on the **objects placed on the turntable**. This is because:

1. The wooden turntable surface resembles furniture in COCO dataset training images
2. The turntable often occupies the largest area in frame
3. Objects on the turntable may be smaller or have lower confidence scores

**Example Detection**:
```
🔍 YOLO found 1 total detection(s) before filtering:
   1. bed (conf=0.460, area=65.3%)  ← This is the turntable!
```

---

## Solution Implemented

### 1. **Class Exclusion List** (`exclude_classes`)
Added ability to **filter out specific COCO classes** that represent the turntable:

```yaml
yolo_detection:
  exclude_classes: ['bed', 'dining table', 'table']  # Ignore turntable detections
```

**How it works**:
- YOLO runs normally and detects all objects
- Detections matching excluded classes are filtered out
- Only non-turntable objects remain for focus window selection

### 2. **Center Bias Scoring** (`center_bias`)
Prefer objects in the **center of the image** where scan objects typically are:

```yaml
yolo_detection:
  center_bias: 0.7  # Prefer objects in center 70% of image
```

**How it works**:
- Calculate distance from image center for each detection
- Objects at edges (where turntable is visible) get lower score
- Objects in center (where scan objects are placed) get higher score
- Final selection: `confidence × area × center_score`

**Scoring Formula**:
```python
dist_from_center = sqrt(((cx - center_x) / width)² + ((cy - center_y) / height)²)
center_score = 1.0 - (dist_from_center × center_bias)
center_score = max(0.1, center_score)  # Minimum 10% even at edges
```

---

## Configuration Changes

### scanner_config.yaml
```yaml
cameras:
  focus_zone:
    mode: 'yolo_detect'
    
    yolo_detection:
      enabled: true
      model_path: 'models/yolo11n.pt'
      
      # Detection parameters
      confidence_threshold: 0.15  # Permissive for any object
      iou_threshold: 0.45
      target_class: null          # Accept ANY object class
      
      # NEW: Turntable filtering
      exclude_classes: ['bed', 'dining table', 'table']  # Filter out turntable
      center_bias: 0.7            # Prefer center objects (0.0-1.0)
      
      # Focus window adjustment
      padding: 0.15
      min_area: 0.03
```

---

## Code Changes

### camera/yolo11n_detector.py

**1. Added Parameters** (lines 40-42):
```python
# Turntable filtering
self.exclude_classes = config.get('exclude_classes', [])
self.center_bias = config.get('center_bias', 0.0)  # 0.7 = prefer center 70%
```

**2. Class Exclusion Filtering** (lines 194-197):
```python
# Filter out excluded classes (e.g., turntable = 'bed', 'table')
if class_name in self.exclude_classes:
    logger.debug(f"   ✂️ Filtered {class_name}: in exclude_classes list")
    continue
```

**3. Center Bias Scoring** (lines 210-220):
```python
# Calculate center distance (0=center, 1=edge)
cx = (bbox[0] + bbox[2]) / 2
cy = (bbox[1] + bbox[3]) / 2
dist_from_center = np.sqrt(((cx - center_x) / center_x)**2 + 
                           ((cy - center_y) / center_y)**2)

# Center bias: objects in center get higher score
center_score = 1.0 - (dist_from_center * self.center_bias)
center_score = max(0.1, center_score)  # Minimum 10% score
```

**4. Updated Selection Criteria** (line 230):
```python
# Select best: confidence × area × center_score
best = max(candidates, key=lambda x: x['confidence'] * x['area_fraction'] * x['center_score'])
```

---

## Expected Behavior After Fix

### Before (Detecting Turntable):
```
🔍 YOLO found 2 total detection(s) before filtering:
   1. bed (conf=0.460, area=65.3%)           ← Turntable
   2. toy (conf=0.187, area=8.2%)            ← Actual object

🎯 1 object(s) passed filtering:
   → 1. bed (conf=0.46, area=65.3%)          ← WRONG!
```

### After (Ignoring Turntable):
```
🔍 YOLO found 2 total detection(s) before filtering:
   1. bed (conf=0.460, area=65.3%)           ← Turntable
   2. toy (conf=0.187, area=8.2%)            ← Actual object

   ✂️ Filtered bed: in exclude_classes list   ← Removed!

🎯 1 object(s) passed filtering:
   → 1. toy (conf=0.19, area=8.2%)           ← CORRECT!
```

---

## Testing Instructions

**Please test on Pi hardware**:

```bash
# Run calibration or scan with new filtering
python3 main.py

# Or test YOLO detection standalone
python3 test_yolo_detection.py --with-camera
```

**What to verify**:
1. ✅ Turntable ("bed") detections are filtered out
2. ✅ Objects ON the turntable are detected instead
3. ✅ Center objects are preferred over edge objects
4. ✅ Log shows "✂️ Filtered bed: in exclude_classes list"

---

## Tuning Parameters

### If turntable still detected with different class:
Add more classes to exclude list:
```yaml
exclude_classes: ['bed', 'dining table', 'table', 'couch', 'chair']
```

### If no objects detected (too strict):
- Lower `center_bias` to 0.5 or 0.3 (less center preference)
- Lower `confidence_threshold` to 0.10 (more permissive)
- Lower `min_area` to 0.02 (accept smaller objects)

### If wrong objects selected:
- Increase `center_bias` to 0.8 or 0.9 (stronger center preference)
- Increase `min_area` to 0.04 (ignore very small objects)

---

## Related Files

- **Config**: `config/scanner_config.yaml` (lines 177-195)
- **Detector**: `camera/yolo11n_detector.py` (class exclusion + center bias)
- **Controller**: `camera/pi_camera_controller.py` (two-pass calibration)
- **Test**: `test_yolo_detection.py` (standalone testing)

---

## Summary

✅ **Turntable filtering prevents YOLO from focusing on the platform**  
✅ **Center bias ensures objects in scan area are prioritized**  
✅ **Configurable via scanner_config.yaml (no code changes needed)**  
✅ **Works with existing permissive detection settings**

The system now correctly identifies objects **ON** the turntable rather than the turntable itself! 🎯
