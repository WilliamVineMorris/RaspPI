# Quick Fix: YOLO Not Running

## Problem
Config was changed to `mode: 'yolo_detect'` **after** the camera controller was already initialized (without YOLO detector loaded).

## Solution
**Restart the test script**:
```bash
python3 test_yolo_detection.py --with-camera
```

## What to Look For

### ✅ Success Indicators
During initialization:
```
🎯 YOLO11n NCNN object detection enabled for autofocus windows
🎯 YOLO11n NCNN Detector initialized
```

During calibration:
```
📂 Loading YOLO11n NCNN model
🎯 YOLO detection found X objects
💾 Saved detection visualization: calibration/focus_detection/camera0_detection_TIMESTAMP.jpg
```

### ❌ If You Still See Warning
```
⚠️ Camera camera0 unknown focus mode 'yolo_detect', using default
```

Then verify config was actually changed:
```bash
grep "mode:" config/scanner_config.yaml | head -1
```

Should show:
```yaml
mode: 'yolo_detect'  # Options: 'static', 'yolo_detect'
```

If still shows `'static'`, change it:
```bash
sed -i "s/mode: 'static'/mode: 'yolo_detect'/" config/scanner_config.yaml
python3 test_yolo_detection.py --with-camera
```

## Detection Images Location
```bash
ls -lh calibration/focus_detection/
```

---

**TL;DR**: Just run the test again: `python3 test_yolo_detection.py --with-camera`
