# YOLO11n NCNN Installation Checklist

Use this checklist to ensure proper installation and testing on Raspberry Pi.

---

## Pre-Installation

- [ ] Raspberry Pi 5 (or Pi 4 with 4GB+ RAM)
- [ ] Python 3.10+ installed
- [ ] Scanner V2.0 codebase present
- [ ] At least 200MB free disk space
- [ ] Internet connection for downloads

---

## Step 1: Install Dependencies

### 1.1 Install OpenCV
```bash
pip install opencv-python
```

**Verify**:
```bash
python3 -c "import cv2; print(f'OpenCV: {cv2.__version__}')"
```

Expected output: `OpenCV: 4.x.x`

- [ ] OpenCV installed and verified

### 1.2 Install NCNN

**Option A: pip install (Quick)**
```bash
pip install ncnn
```

**Option B: Build from source (Best Performance - Recommended)**
```bash
cd ~
git clone https://github.com/Tencent/ncnn.git
cd ncnn
mkdir build && cd build

cmake -DCMAKE_BUILD_TYPE=Release \
      -DNCNN_VULKAN=OFF \
      -DNCNN_BUILD_EXAMPLES=OFF \
      -DNCNN_OPENMP=ON \
      ..

make -j4
sudo make install

cd ../python
pip install .
```

**Verify**:
```bash
python3 -c "import ncnn; print(f'NCNN: {ncnn.__version__}')"
```

Expected output: `NCNN: 1.0.x`

- [ ] NCNN installed and verified

---

## Step 2: Download YOLO11n Model

### 2.1 Run Setup Script
```bash
cd ~/scanner/V2.0
bash setup_yolo_model.sh
```

**Manual method (if script fails)**:
```bash
cd ~/scanner/V2.0
mkdir -p models/yolo11n_ncnn

wget -O models/yolo11n_ncnn.zip \
  "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n_ncnn_model.zip"

unzip models/yolo11n_ncnn.zip -d models/yolo11n_ncnn/
rm models/yolo11n_ncnn.zip
```

### 2.2 Verify Model Files
```bash
ls -lh models/yolo11n_ncnn/
```

Expected files:
- `yolo11n.param` (~15 KB)
- `yolo11n.bin` (~5-10 MB)

- [ ] Model files downloaded
- [ ] File sizes correct
- [ ] No extraction errors

---

## Step 3: Run Tests

### 3.1 Basic Detector Test
```bash
cd ~/scanner/V2.0
python3 test_yolo_detection.py
```

**Expected output**:
```
============================================================
YOLO11n NCNN Detection Test
============================================================

[1/6] Checking NCNN installation...
✅ NCNN installed: version 1.0.x

[2/6] Checking OpenCV installation...
✅ OpenCV installed: version 4.x.x

[3/6] Checking YOLO11n model files...
✅ Model files found:
   - yolo11n.param: 15.x KB
   - yolo11n.bin: 6.x MB

[4/6] Loading YOLO11n detector...
✅ Detector initialized
✅ Model loaded successfully

[5/6] Testing detection on sample image...
...

[6/6] Cleaning up...
✅ Model unloaded successfully

============================================================
✅ All tests passed!
============================================================
```

- [ ] All 6 test steps passed
- [ ] No errors in output

### 3.2 Camera Test (Hardware Required)
```bash
python3 test_yolo_detection.py --with-camera
```

**Expected output**:
```
============================================================
Testing YOLO Detection with Pi Cameras
============================================================

[1/3] Loading configuration...
[2/3] Initializing camera controller...
✅ Camera controller initialized

[3/3] Running calibration (triggers YOLO detection)...
✅ Calibration complete!
   Focus: 0.xxx
   Exposure: xxxxx
   Gain: x.xx

📷 Check detection visualization:
   ls -lh calibration/focus_detection/
```

- [ ] Camera initialization successful
- [ ] Calibration completed
- [ ] Detection visualization saved

---

## Step 4: Verify Detection Output

### 4.1 Check Detection Images
```bash
ls -lh calibration/focus_detection/
```

Expected files:
- `camera0_detection_YYYYMMDD_HHMMSS.jpg`
- `camera1_detection_YYYYMMDD_HHMMSS.jpg` (if dual camera)

**View images** (transfer to PC or use image viewer on Pi):
```bash
# On Pi with desktop
xdg-open calibration/focus_detection/camera0_detection_*.jpg

# Or transfer to PC
scp pi@raspberrypi:~/scanner/V2.0/calibration/focus_detection/*.jpg ./
```

- [ ] Detection images created
- [ ] Images show bounding boxes correctly
- [ ] Focus window visible (yellow dashed box)
- [ ] Object correctly identified

### 4.2 Check Logs
```bash
tail -100 logs/scanner.log | grep -E "YOLO|detection"
```

**Expected log entries**:
```
🎯 YOLO11n NCNN Detector initialized: confidence=0.30, padding=0.15
📂 Loading YOLO11n NCNN model from models/yolo11n_ncnn
✅ YOLO11n NCNN model loaded successfully
🎯 Camera camera0 attempting YOLO object detection for focus window...
✅ Object detected: bottle (confidence=0.87, area=23.4%)
💾 Saved detection visualization: calibration/focus_detection/...
📷 Camera camera0 focus window (yolo_detected): AfWindows=[...]
```

- [ ] YOLO initialization logged
- [ ] Model loading logged
- [ ] Detection successful logged
- [ ] Visualization saved logged
- [ ] No errors in logs

---

## Step 5: Configure Scanner

### 5.1 Edit Configuration
```bash
nano config/scanner_config.yaml
```

**Change**:
```yaml
cameras:
  focus_zone:
    mode: 'yolo_detect'  # Change from 'static'
```

**Optional tuning**:
```yaml
    yolo_detection:
      confidence_threshold: 0.30  # Adjust if needed
      target_class: null          # or 'bottle', 'vase', etc.
      padding: 0.15               # Adjust padding
      min_area: 0.05              # Minimum object size
```

- [ ] Configuration file updated
- [ ] Mode set to 'yolo_detect'
- [ ] Optional settings tuned (if needed)

### 5.2 Verify Configuration
```bash
python3 -c "
from core.config_manager import ConfigManager
cfg = ConfigManager('config/scanner_config.yaml')
focus_config = cfg.get_section('cameras').get('focus_zone', {})
print(f\"Mode: {focus_config.get('mode')}\")
print(f\"YOLO enabled: {focus_config.get('yolo_detection', {}).get('enabled')}\")
"
```

Expected output:
```
Mode: yolo_detect
YOLO enabled: True
```

- [ ] Configuration loads correctly
- [ ] Mode is 'yolo_detect'
- [ ] YOLO detection enabled

---

## Step 6: Production Testing

### 6.1 Run Full Calibration
```bash
# Start scanner system
python3 main.py

# Or test calibration directly
python3 -c "
import asyncio
from camera.pi_camera_controller import PiCameraController
from core.config_manager import ConfigManager

async def test():
    cfg = ConfigManager('config/scanner_config.yaml')
    ctrl = PiCameraController(cfg.get_section('cameras'))
    await ctrl.initialize()
    
    # Calibrate both cameras
    result0 = await ctrl.auto_calibrate_camera('camera0')
    result1 = await ctrl.auto_calibrate_camera('camera1')
    
    print(f'Camera 0: {result0}')
    print(f'Camera 1: {result1}')
    
    await ctrl.shutdown()

asyncio.run(test())
"
```

- [ ] Both cameras calibrate successfully
- [ ] Detection runs for each camera
- [ ] Visualizations saved for both cameras
- [ ] Calibration time acceptable (<5s per camera)

### 6.2 Monitor Performance
```bash
tail -f logs/scanner.log | grep -E "calibration|YOLO|detection"
```

**Check**:
- [ ] YOLO model loads in <1s
- [ ] Detection runs in <500ms
- [ ] Total calibration <5s per camera
- [ ] Model unloads after calibration

### 6.3 Verify Memory Usage
```bash
# Before calibration
free -h

# During calibration (in another terminal)
watch -n 0.5 free -h

# After calibration
free -h
```

**Expected**:
- Memory increases by ~100MB during calibration
- Memory returns to baseline after calibration

- [ ] Memory increases during calibration
- [ ] Memory freed after calibration
- [ ] No memory leaks

---

## Step 7: Fallback Testing

### 7.1 Test With No Object
Place camera without visible object in frame.

```bash
python3 test_yolo_detection.py --with-camera
```

**Expected**:
```
⚠️ No objects detected in image
🔄 Camera camera0 falling back to static window
📍 Camera camera0 using static focus window: [0.40, 0.25, 0.5, 0.5]
```

- [ ] Fallback triggered when no object
- [ ] Static window used as backup
- [ ] Calibration still completes

### 7.2 Disable Model (Simulate Failure)
Temporarily rename model files:

```bash
mv models/yolo11n_ncnn/yolo11n.bin models/yolo11n_ncnn/yolo11n.bin.bak
python3 test_yolo_detection.py --with-camera
mv models/yolo11n_ncnn/yolo11n.bin.bak models/yolo11n_ncnn/yolo11n.bin
```

**Expected**:
```
❌ NCNN bin file not found: models/yolo11n_ncnn/yolo11n.bin
🔄 Camera camera0 falling back to static window
```

- [ ] Fallback triggered when model unavailable
- [ ] Static window used
- [ ] System remains functional

---

## Step 8: Documentation Review

- [ ] Read `YOLO_README.md` (overview)
- [ ] Read `YOLO_QUICK_REFERENCE.md` (quick commands)
- [ ] Skim `YOLO11N_SETUP_GUIDE.md` (detailed setup)
- [ ] Understand `YOLO_ARCHITECTURE.md` (system design)

---

## Step 9: Cleanup & Maintenance

### 9.1 Set Up Log Rotation (Optional)
```bash
# Prevent detection images from filling disk
# Add to cron (run weekly)
crontab -e

# Add line:
0 0 * * 0 find ~/scanner/V2.0/calibration/focus_detection -mtime +30 -delete
```

- [ ] Log rotation configured (optional)

### 9.2 Create Backup
```bash
# Backup working configuration
cp config/scanner_config.yaml config/scanner_config.yaml.yolo_backup
```

- [ ] Configuration backed up

---

## Troubleshooting Checklist

If something doesn't work:

- [ ] Check NCNN installed: `python3 -c "import ncnn"`
- [ ] Check model files exist: `ls models/yolo11n_ncnn/`
- [ ] Check configuration mode: `grep mode config/scanner_config.yaml`
- [ ] Review logs: `tail -100 logs/scanner.log`
- [ ] Run basic test: `python3 test_yolo_detection.py`
- [ ] Check disk space: `df -h`
- [ ] Restart Pi: `sudo reboot`

---

## Final Verification

### All Systems Go Checklist

- [ ] ✅ NCNN installed and verified
- [ ] ✅ YOLO11n model downloaded
- [ ] ✅ Basic test passed
- [ ] ✅ Camera test passed
- [ ] ✅ Detection images created
- [ ] ✅ Logs show successful detection
- [ ] ✅ Configuration updated
- [ ] ✅ Production calibration works
- [ ] ✅ Performance acceptable
- [ ] ✅ Fallback tested and working
- [ ] ✅ Documentation reviewed

---

## Performance Benchmarks

Record your actual performance:

| Metric | Expected | Actual | Status |
|--------|----------|--------|--------|
| NCNN load time | <1s | _____s | [ ] |
| Detection time | <500ms | _____ms | [ ] |
| Total calibration | <5s | _____s | [ ] |
| Memory usage | ~100MB | _____MB | [ ] |
| Model file size | ~6MB | _____MB | [ ] |

---

## Post-Installation

### Recommended Next Steps

1. [ ] Run several test calibrations with different objects
2. [ ] Fine-tune `confidence_threshold` for your objects
3. [ ] Test with various lighting conditions
4. [ ] Monitor detection quality over multiple sessions
5. [ ] Archive successful detection images as examples
6. [ ] Document any object-specific settings needed

### Optional Enhancements

- [ ] Set up automatic detection image backup
- [ ] Create calibration report generator
- [ ] Add detection statistics logging
- [ ] Implement object class filtering for specific projects

---

## Support Resources

If you encounter issues:

1. **Documentation**: See `YOLO11N_SETUP_GUIDE.md` troubleshooting section
2. **Logs**: Check `logs/scanner.log` for detailed errors
3. **Test script**: Run `python3 test_yolo_detection.py` for diagnostics
4. **Detection images**: Review saved visualizations for clues
5. **Configuration**: Verify `scanner_config.yaml` settings

---

## Installation Complete! 🎉

Once all checkboxes are marked:

✅ **YOLO11n NCNN detection is ready for production use!**

Your scanner can now automatically detect and focus on objects during calibration.

**Remember**:
- Detection runs only during calibration (not every scan)
- Static windows are used as fallback if detection fails
- Model is unloaded after calibration to save memory
- Check `calibration/focus_detection/` for visual confirmation

---

**Installation Date**: _______________  
**Installed By**: _______________  
**Pi Model**: _______________  
**Scanner Version**: V2.0  
**YOLO Version**: YOLO11n NCNN  

**Notes**:
```
(Add any installation-specific notes here)




```
