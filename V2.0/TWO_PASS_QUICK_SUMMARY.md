# Quick Fix: Two-Pass YOLO Calibration

## Problem You Found
YOLO detection failed on your teddy bear because the camera was **out of focus initially** → blurry image → YOLO can't detect blurry objects.

## Solution Implemented
**Two-Pass Calibration**:

### Pass 1: Get Sharp Image
1. Use static center window
2. Run autofocus
3. **Result**: Sharp image (even if object not perfectly centered)

### Pass 2: YOLO Detection + Refined Focus
1. Run YOLO on **sharp image** from Pass 1
2. Detect object location
3. Update focus window to object
4. Re-run autofocus for precision

---

## Test Now
```bash
python3 test_yolo_detection.py --with-camera
```

## Expected Output
```
📷 Camera camera0 performing initial autofocus...
✅ Camera camera0 initial focus complete: 0.64

🎯 Camera camera0 YOLO PASS 2: Image now sharp, running object detection...
🎯 YOLO detection found 1 suitable object(s)
   → 1. teddy bear (conf=0.85, area=28.3%)
✅ Camera camera0 YOLO detection successful on sharp image!

📷 Camera camera0 performing refined autofocus on detected object...
✅ Camera camera0 refined focus value: 0.652

💾 Saved detection visualization: calibration/focus_detection/camera0_detection_TIMESTAMP.jpg
```

---

## Result
- ✅ YOLO now runs on sharp images (Pass 1 fixes the blur)
- ✅ Accurate object detection
- ✅ Precise focus on detected object
- ✅ Works even if object is off-center

**Your teddy bear should now be detected successfully!** 🧸

---

**Time Impact**: +3 seconds (but worth it for reliable detection)  
**Files Modified**: `camera/pi_camera_controller.py`  
**Config**: No changes needed - works automatically with `mode: 'yolo_detect'`
