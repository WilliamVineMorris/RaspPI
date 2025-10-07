# YOLO Detection Results - Where to Find Them

## 🔍 Current Status: YOLO Detection NOT Running

### Why No Detection Images Were Created

The calibration **completed successfully** but did NOT use YOLO detection because:

**Configuration Setting**: `config/scanner_config.yaml` line 163
```yaml
focus_zone:
  mode: 'static'  # ← Currently using STATIC mode
```

When `mode: 'static'`:
- ✅ Calibration works normally
- ✅ Uses predefined focus windows
- ❌ YOLO detector is NOT loaded
- ❌ NO detection images are saved

---

## 🎯 How to Enable YOLO Detection

### Step 1: Check NCNN Model Exists

First, verify you have the converted NCNN model:

```bash
ls -lh models/yolo11n_ncnn_model/
```

**Expected output**:
```
model.ncnn.param  (~15 KB)
model.ncnn.bin    (~6 MB)
```

**If files don't exist**, convert the model:
```bash
python3 convert_yolo_to_ncnn.py
```

---

### Step 2: Enable YOLO Mode in Config

Edit `config/scanner_config.yaml`:

```bash
nano config/scanner_config.yaml
```

**Find line 163** and change:
```yaml
# BEFORE:
mode: 'static'

# AFTER:
mode: 'yolo_detect'
```

**Save and exit** (Ctrl+O, Enter, Ctrl+X)

---

### Step 3: Run Calibration Again

```bash
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate
python3 test_yolo_detection.py --with-camera
```

---

## 📁 Where Detection Images Are Saved

Once YOLO mode is enabled, detection visualization images will be saved to:

```
calibration/focus_detection/
```

### File Naming Convention

```
camera0_detection_YYYYMMDD_HHMMSS.jpg
camera1_detection_YYYYMMDD_HHMMSS.jpg
```

Example:
```
calibration/focus_detection/
├── camera0_detection_20251007_143052.jpg
└── camera1_detection_20251007_143053.jpg
```

### Finding Detection Images

```bash
# List detection images
ls -lh calibration/focus_detection/

# View most recent detection
ls -lt calibration/focus_detection/ | head -5

# View image count
ls calibration/focus_detection/*.jpg | wc -l
```

---

## 🖼️ What Detection Images Show

Each detection visualization includes:

### Color-Coded Bounding Boxes

- **🔵 Blue boxes**: All detected objects (confidence > threshold)
- **🟢 Green box**: Selected object for focus (largest/best)
- **🟡 Yellow dashed box**: Calculated focus window (with padding)

### Text Annotations

- Object class name (e.g., "bottle", "vase", "person")
- Confidence score (e.g., "0.87")
- Focus window coordinates

### Example Visualization

```
┌─────────────────────────────────────┐
│                                     │
│     🔵 bottle (0.45)                │
│     ┌──────┐                        │
│     │      │  🟢 vase (0.87) ←     │
│     └──────┘  ┌────────────┐       │
│               │            │       │
│               │  ╔══════╗  │       │
│               │  ║ YOLO ║  │ ← 🟡 Focus Window
│               │  ║Window║  │       │
│               │  ╚══════╝  │       │
│               │            │       │
│               └────────────┘       │
│                                     │
└─────────────────────────────────────┘
```

---

## 🔄 Complete Workflow

### 1. Verify Prerequisites

```bash
# Check NCNN model exists
ls models/yolo11n_ncnn_model/model.ncnn.param
ls models/yolo11n_ncnn_model/model.ncnn.bin

# If not, convert:
python3 convert_yolo_to_ncnn.py
```

### 2. Enable YOLO Detection

```bash
# Edit config
nano config/scanner_config.yaml

# Change line 163:
#   mode: 'static'  →  mode: 'yolo_detect'

# Save: Ctrl+O, Enter, Ctrl+X
```

### 3. Run Test with YOLO Enabled

```bash
# Activate environment
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate

# Run test (will now use YOLO)
python3 test_yolo_detection.py --with-camera
```

### 4. View Detection Results

```bash
# List detection images
ls -lh calibration/focus_detection/

# View most recent
eog calibration/focus_detection/camera0_detection_*.jpg &
```

---

## 🎛️ Configuration Options

### YOLO Detection Settings (scanner_config.yaml lines 176-195)

```yaml
yolo_detection:
  enabled: true
  
  # Model paths
  model_param: 'models/yolo11n_ncnn_model/model.ncnn.param'
  model_bin: 'models/yolo11n_ncnn_model/model.ncnn.bin'
  
  # Detection tuning
  confidence_threshold: 0.30  # Lower = more detections, higher = fewer but more confident
  iou_threshold: 0.45         # Non-max suppression threshold
  target_class: null          # null = any object, or 'bottle', 'vase', 'person', etc.
  
  # Focus window sizing
  padding: 0.15               # 15% padding around object
  min_area: 0.05              # Ignore tiny objects (<5% of image)
  
  # Output
  detection_output_dir: 'calibration/focus_detection'
  
  # Safety
  fallback_to_static: true    # Use static window if detection fails
```

### Adjusting Detection Behavior

**To detect more objects**:
```yaml
confidence_threshold: 0.20  # Lower threshold
```

**To detect specific objects only**:
```yaml
target_class: 'bottle'  # Only detect bottles
```

**To increase focus window size**:
```yaml
padding: 0.25  # 25% padding (larger window)
```

---

## 🔬 Testing Detection Without Full Calibration

You can also test YOLO detection in isolation:

```bash
# Test just the detector (no camera calibration)
python3 test_yolo_detection.py
```

This will:
1. Load NCNN model
2. Test with sample image
3. Save detection visualization
4. Show detection statistics

---

## 🐛 Troubleshooting

### No Detection Images After Enabling YOLO

**Check 1: Verify mode is actually 'yolo_detect'**
```bash
grep "mode:" config/scanner_config.yaml | head -1
```
Should show: `mode: 'yolo_detect'`

**Check 2: Check if directory exists but is empty**
```bash
ls -la calibration/
ls -la calibration/focus_detection/
```

**Check 3: Check logs for YOLO initialization**
Look for:
```
🎯 YOLO11n NCNN Detector initialized
📂 Loading YOLO11n NCNN model
✅ YOLO11n NCNN model loaded successfully
```

### Directory Doesn't Exist

YOLO detector creates directory automatically. If it doesn't exist:

```bash
# Create manually
mkdir -p calibration/focus_detection

# Check permissions
ls -ld calibration/focus_detection/
```

### Model Not Found Errors

```bash
# Verify model files
ls -lh models/yolo11n_ncnn_model/

# If missing, convert:
python3 convert_yolo_to_ncnn.py
```

---

## 📊 Expected Console Output with YOLO Enabled

When YOLO detection is **enabled** and **working**, you'll see:

```
============================================================
Testing YOLO Detection with Pi Cameras
============================================================

[1/3] Loading configuration...
[2/3] Initializing camera controller...
🎯 YOLO11n NCNN Detector initialized: confidence=0.30, padding=0.15
✅ Camera controller initialized

[3/3] Running calibration (triggers YOLO detection)...
📂 Loading YOLO11n NCNN model from models/yolo11n_ncnn_model
✅ YOLO11n NCNN model loaded successfully
🎯 YOLO detection found 2 objects
   → Selected: vase (confidence=0.87, area=24.3%)
   → Focus window: [0.25, 0.30, 0.45, 0.50]
💾 Saved detection visualization: calibration/focus_detection/camera0_detection_20251007_143052.jpg
🗑️ YOLO11n NCNN model unloaded

✅ Calibration complete!
   Focus: 0.6373610973358155
   Exposure: 31990
   Gain: 8.126984596252441

📷 Check detection visualization:
   ls -lh calibration/focus_detection/
```

---

## 📋 Quick Reference

### Current Status
```bash
# Check current mode
grep "mode:" config/scanner_config.yaml | grep -A0 "focus_zone" | tail -1
```

### Enable YOLO
```bash
sed -i "s/mode: 'static'/mode: 'yolo_detect'/" config/scanner_config.yaml
```

### Disable YOLO
```bash
sed -i "s/mode: 'yolo_detect'/mode: 'static'/" config/scanner_config.yaml
```

### View Detection Images
```bash
ls -lht calibration/focus_detection/ | head -5
eog calibration/focus_detection/*.jpg &
```

---

## Summary

**Current Situation**:
- ✅ Calibration works perfectly
- ✅ YOLO detector code is ready
- ❌ YOLO detection is **disabled** in config
- ❌ No detection images saved (mode='static')

**To Get Detection Images**:
1. Change `mode: 'static'` → `mode: 'yolo_detect'` in `config/scanner_config.yaml`
2. Run calibration again: `python3 test_yolo_detection.py --with-camera`
3. Check images: `ls -lh calibration/focus_detection/`

**Location**: `calibration/focus_detection/*.jpg`

---

**Date**: October 7, 2025  
**Status**: Configuration fix needed  
**Action Required**: Enable YOLO mode in config file
