# Quick Fix: Install NCNN Package

## Error
```
❌ Failed to initialize YOLO detector: name 'ncnn' is not defined
```

## Solution (One Command)

```bash
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate
pip install ncnn
```

## Verify Installation

```bash
python3 -c "import ncnn; print('✅ NCNN OK')"
```

## Then Test YOLO

```bash
python3 test_yolo_detection.py --with-camera
```

## Expected Output

```
[2/3] Initializing camera controller...
🎯 YOLO11n NCNN object detection enabled for autofocus windows
🎯 YOLO11n NCNN Detector initialized
✅ Camera controller initialized

[3/3] Running calibration (triggers YOLO detection)...
📂 Loading YOLO11n NCNN model from models/yolo11n_ncnn_model
✅ YOLO11n NCNN model loaded successfully
🎯 YOLO detection found X objects
💾 Saved detection visualization: calibration/focus_detection/camera0_detection_TIMESTAMP.jpg
```

## Check Results

```bash
ls -lh calibration/focus_detection/
```

---

## Alternative: Use Installation Script

```bash
chmod +x install_ncnn.sh
./install_ncnn.sh
```

---

**TL;DR**: `pip install ncnn` then run test again
