# YOLO11n NCNN Conversion Guide

## Quick Start

You already have `yolo11n.pt` in the `models/` directory. Now convert it to NCNN format:

### Method 1: Automated Script (Recommended)

```bash
cd ~/scanner/V2.0

# Ensure ultralytics is installed
pip install ultralytics

# Run conversion script
python3 convert_yolo_to_ncnn.py

# Or use shell script
bash setup_yolo_model.sh
```

### Method 2: Manual Conversion

```bash
cd ~/scanner/V2.0

# Install ultralytics
pip install ultralytics

# Convert manually
python3 -c "from ultralytics import YOLO; YOLO('models/yolo11n.pt').export(format='ncnn')"

# Move to models directory
mv yolo11n_ncnn_model models/
```

---

## What Gets Created

After conversion, you'll have:

```
models/
├── yolo11n.pt                    # Original PyTorch model (you already have this)
└── yolo11n_ncnn_model/          # Created by conversion
    ├── model.ncnn.param          # NCNN model structure (~15 KB)
    └── model.ncnn.bin            # NCNN model weights (~6 MB)
```

---

## Conversion Process

```
┌─────────────────┐
│  yolo11n.pt     │  ← You have this (PyTorch model)
│  (~6 MB)        │
└────────┬────────┘
         │
         │ ultralytics.export(format='ncnn')
         │
         ▼
┌─────────────────┐
│ yolo11n_ncnn_   │
│ model/          │
│  ├─ model.ncnn. │
│  │  param       │  ← NCNN structure
│  └─ model.ncnn. │
│     bin         │  ← NCNN weights
└─────────────────┘
```

---

## Verify Conversion

```bash
# Check files were created
ls -lh models/yolo11n_ncnn_model/

# Expected output:
# model.ncnn.param  (~15 KB)
# model.ncnn.bin    (~6 MB)
```

---

## Configuration

The config file is already set up to use the converted model:

```yaml
# config/scanner_config.yaml
cameras:
  focus_zone:
    yolo_detection:
      model_param: 'models/yolo11n_ncnn_model/model.ncnn.param'
      model_bin: 'models/yolo11n_ncnn_model/model.ncnn.bin'
```

---

## Test Conversion

```bash
# Test YOLO detection
python3 test_yolo_detection.py

# Expected output:
# ✅ NCNN installed
# ✅ Model files found
# ✅ Model loaded successfully
```

---

## Troubleshooting

### Issue: "ultralytics not installed"

```bash
pip install ultralytics
```

### Issue: "yolo11n.pt not found"

Make sure `yolo11n.pt` is in `models/` directory:
```bash
ls models/yolo11n.pt
```

If missing, download it:
```bash
wget -O models/yolo11n.pt \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt
```

### Issue: Conversion fails

Try manual conversion with verbose output:
```bash
python3 -c "
from ultralytics import YOLO
import logging
logging.basicConfig(level=logging.DEBUG)
model = YOLO('models/yolo11n.pt')
model.export(format='ncnn', imgsz=640)
"
```

### Issue: "NCNN files not found"

Check where ultralytics created the output:
```bash
find . -name "model.ncnn.param"
```

Move to correct location if needed:
```bash
mv yolo11n_ncnn_model models/
```

---

## Why NCNN?

| Format | Size | Speed on Pi 5 | Notes |
|--------|------|---------------|-------|
| PyTorch (.pt) | 6 MB | Very slow (~2s) | Not optimized for ARM |
| ONNX | 6 MB | Medium (~800ms) | Good compatibility |
| **NCNN** | **6 MB** | **Fast (~250ms)** | **Best for Pi** |
| TensorFlow Lite | 6 MB | Medium (~600ms) | Good performance |

**NCNN is the best choice for Raspberry Pi** due to ARM optimizations.

---

## Summary

1. ✅ You already have `yolo11n.pt`
2. ⚡ Run `python3 convert_yolo_to_ncnn.py`
3. ✅ NCNN model created in `models/yolo11n_ncnn_model/`
4. 🎯 Ready to use for auto-focus detection!

**Total time**: ~30-60 seconds for conversion

---

**Last Updated**: October 7, 2025
