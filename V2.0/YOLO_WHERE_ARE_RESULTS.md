# YOLO Detection Results - Quick Answer

## ❌ No Detection Images Because YOLO is DISABLED

Your calibration **succeeded** but **didn't use YOLO** because:

**File**: `config/scanner_config.yaml` (line 163)
```yaml
mode: 'static'  # ← YOLO detection is OFF
```

---

## ✅ How to Enable and Get Detection Images

### 1. Enable YOLO Mode
```bash
nano config/scanner_config.yaml
```

**Change line 163**:
```yaml
# FROM:
mode: 'static'

# TO:
mode: 'yolo_detect'
```

Save: Ctrl+O, Enter, Ctrl+X

### 2. Run Calibration Again
```bash
python3 test_yolo_detection.py --with-camera
```

### 3. Find Detection Images
```bash
ls -lh calibration/focus_detection/
```

**Images will be named**:
```
camera0_detection_20251007_HHMMSS.jpg
camera1_detection_20251007_HHMMSS.jpg
```

---

## 📊 What You'll See With YOLO Enabled

Console output will show:
```
🎯 YOLO11n NCNN Detector initialized
📂 Loading YOLO11n NCNN model
✅ YOLO11n NCNN model loaded successfully
🎯 YOLO detection found 2 objects
   → Selected: vase (confidence=0.87, area=24.3%)
💾 Saved detection visualization: calibration/focus_detection/camera0_detection_20251007_143052.jpg
```

Detection images will show:
- 🔵 **Blue boxes**: All detected objects
- 🟢 **Green box**: Selected object for focus
- 🟡 **Yellow box**: Calculated focus window

---

## Quick Commands

```bash
# Enable YOLO in one command
sed -i "s/mode: 'static'/mode: 'yolo_detect'/" config/scanner_config.yaml

# Run calibration
python3 test_yolo_detection.py --with-camera

# View results
ls -lh calibration/focus_detection/
eog calibration/focus_detection/*.jpg &
```

---

**TL;DR**: Change `mode: 'static'` to `mode: 'yolo_detect'` in config file, then run test again. Images will appear in `calibration/focus_detection/`
