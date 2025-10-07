# Two-Pass YOLO Calibration - Solving the Focus-Detection Paradox

## 🔄 The Problem: Chicken and Egg

### Original Issue
- 🔍 **YOLO needs sharp images** to detect objects accurately
- 📷 **Autofocus needs to know WHERE** to focus (which YOLO provides)
- ❌ **Paradox**: Can't detect objects in blurry images, can't focus without knowing where the object is!

### User's Screenshot Evidence
The teddy bear detection failed because the image was **completely out of focus** - YOLO couldn't reliably detect the blurred object.

---

## ✅ Solution: Two-Pass Calibration

### Pass 1: Initial Sharp Focus (Static Center Window)
1. **Use static center window** ([0.25, 0.25, 0.5, 0.5])
2. **Run autofocus** on center of image
3. **Get sharp image** (even if object isn't perfectly centered)

**Purpose**: Overcome the initial blur problem

### Pass 2: YOLO Detection + Refined Focus
1. **Capture sharp image** from Pass 1
2. **Run YOLO detection** on sharp image (now works!)
3. **Update AfWindows** to detected object location
4. **Re-run autofocus** on detected object for precise focus

**Purpose**: Precisely focus on the actual object

---

## 🎯 Implementation Details

### Workflow
```
START
  ↓
[1] Set static center window for autofocus
  ↓
[2] Run initial autofocus (camera now sharp)
  ↓
[3] Capture sharp RGB frame
  ↓
[4] Run YOLO detection on sharp frame
  ↓
  ├─ Detection SUCCESS?
  │    ↓ YES
  │   [5] Update AfWindows to detected object
  │    ↓
  │   [6] Re-run autofocus on object (refined focus)
  │    ↓
  └─ Detection FAILED?
       ↓ NO
      [7] Keep center window focus
       ↓
END (calibration complete)
```

### Code Changes

#### Step 1: Initial Window Selection (`lines 1063-1077`)
```python
if mode == 'yolo_detect' and self.yolo_detector:
    logger.info(f"🎯 Camera {camera_id} YOLO mode: Starting with static center window for initial focus...")
    # Use center window for initial autofocus
    focus_window = [0.25, 0.25, 0.5, 0.5]
    window_source = 'static_prefocus'
else:
    # Static mode - get window directly
    focus_window, window_source = self._get_focus_window_for_camera(camera_id, picamera2)
```

**Purpose**: In YOLO mode, start with static center window to get initial sharp image.

#### Step 2: YOLO Pass 2 (`lines 1198-1245`)
```python
# Step 3.5: TWO-PASS YOLO CALIBRATION
if focus_zone_enabled and mode == 'yolo_detect' and self.yolo_detector and window_source == 'static_prefocus':
    logger.info(f"🎯 Camera {camera_id} YOLO PASS 2: Image now sharp, running object detection...")
    
    # Capture sharp image for YOLO detection
    preview_array = picamera2.capture_array("main")
    
    # Run YOLO detection on sharp image
    detected_window = self.yolo_detector.detect_object(preview_array, camera_id)
    
    if detected_window:
        # Update AfWindows with detected object location
        focus_window = list(detected_window)
        window_source = 'yolo_detected'
        
        # Set new focus window
        picamera2.set_controls({
            "AfMetering": controls.AfMeteringEnum.Windows,
            "AfWindows": [(x_px, y_px, w_px, h_px)]
        })
        
        # Re-run autofocus with refined window
        refined_focus = await self.auto_focus_and_get_value(camera_id)
        if refined_focus is not None:
            focus_value = refined_focus
```

**Purpose**: After initial autofocus makes image sharp, run YOLO detection and refine focus on detected object.

---

## 📊 Expected Console Output

### With Two-Pass Calibration
```
[3/3] Running calibration (triggers YOLO detection)...

📷 Camera camera0 enabling auto-exposure controls...
🎯 Camera camera0 YOLO mode: Starting with static center window for initial focus...
📷 Camera camera0 focus window (static_prefocus): AfWindows=[(480, 270, 960, 540)]

📷 Camera camera0 letting auto-exposure settle...
📷 Camera camera0 performing initial autofocus...
✅ Camera camera0 initial focus complete: 0.64

🎯 Camera camera0 YOLO PASS 2: Image now sharp, running object detection...
📂 Loading YOLO11n model from models/yolo11n.pt
✅ YOLO11n model loaded successfully
🎯 YOLO detection found 1 suitable object(s)
   → 1. teddy bear (conf=0.85, area=28.3%)
✅ Camera camera0 YOLO detection successful on sharp image!
📷 Camera camera0 refined focus window: AfWindows=[(320, 180, 640, 720)]

📷 Camera camera0 performing refined autofocus on detected object...
✅ Camera camera0 refined focus value: 0.652

💾 Saved detection visualization: calibration/focus_detection/camera0_detection_20251007_230145.jpg

✅ Calibration complete!
   Focus: 0.652
   Exposure: 31990
   Gain: 8.126984596252441
```

---

## 🎨 Visual Difference

### Before (Single-Pass - Failed)
```
Blurry image → YOLO detection fails → Fallback to static window
Result: ❌ No object detection, poor focus
```

### After (Two-Pass - Success)
```
Pass 1: Static center → Autofocus → Sharp image
         ↓
Pass 2: Sharp image → YOLO detection → Refined focus on object
Result: ✅ Accurate detection, precise focus on object
```

---

## ⚙️ Configuration

No config changes needed! The two-pass approach is **automatic** when:
- `focus_zone.mode` = `'yolo_detect'`
- `focus_zone.yolo_detection.enabled` = `true`
- YOLO detector successfully initializes

### Current Config (`scanner_config.yaml`)
```yaml
cameras:
  focus_zone:
    enabled: true
    mode: 'yolo_detect'  # ← Triggers two-pass calibration
    
    yolo_detection:
      enabled: true
      model_path: 'models/yolo11n.pt'
      confidence_threshold: 0.30
      padding: 0.15
      # ... other settings ...
```

---

## 🚀 Testing

### Run Calibration Test
```bash
python3 test_yolo_detection.py --with-camera
```

### What to Look For

#### Success Indicators
1. **Initial focus**: "performing initial autofocus..."
2. **YOLO Pass 2**: "YOLO PASS 2: Image now sharp, running object detection..."
3. **Detection success**: "YOLO detection found X suitable object(s)"
4. **Refined focus**: "performing refined autofocus on detected object..."
5. **Visualization saved**: Check `calibration/focus_detection/` for images

#### Detection Visualization
The saved image will show:
- 🎯 **Sharp, in-focus object** (from Pass 1)
- 🟢 **Green bounding box** around detected object
- 🟡 **Yellow focus window** with padding

---

## 📈 Performance Impact

### Timing Breakdown
| Stage | Time | Purpose |
|-------|------|---------|
| Pass 1: Initial AE + Autofocus | ~3-4s | Get sharp image |
| Pass 2: YOLO Detection | ~0.5s | Detect object in sharp image |
| Pass 2: Refined Autofocus | ~2-3s | Precise focus on object |
| **Total** | **~6-8s** | Complete calibration |

**Trade-off**: Slightly longer calibration time (~3s extra) but **much better results** when objects aren't centered.

---

## 🎯 When Two-Pass Helps Most

### Scenarios Where It's Critical
1. **Off-center objects** (object not in middle of frame)
2. **Small objects** (needs precise focus window)
3. **Complex scenes** (multiple objects, need to focus on specific one)
4. **Variable object placement** (scanning different items)

### When Single-Pass Would Work
1. **Object always centered** (static scenes)
2. **Large objects** (fills most of frame)
3. **Simple backgrounds** (no distractions)
4. **Pre-focused cameras** (rare in practice)

---

## 🔧 Fallback Behavior

### If YOLO Detection Fails in Pass 2
```python
if detected_window:
    # Use YOLO window
else:
    logger.warning("YOLO detection failed - keeping static window")
    # Keep Pass 1 center window focus
```

**Result**: Still have sharp, focused image from Pass 1 (center window). System **never fails** completely.

---

## 💡 Benefits Summary

### Before Two-Pass
- ❌ YOLO failed on blurry images
- ❌ Objects had to be perfectly centered
- ❌ Poor detection accuracy
- ❌ Fallback to static windows

### After Two-Pass
- ✅ YOLO runs on sharp images
- ✅ Works with off-center objects
- ✅ High detection accuracy
- ✅ Precise object-focused autofocus
- ✅ Graceful fallback if detection fails

---

## 🎉 Summary

**Problem**: YOLO couldn't detect objects in blurry out-of-focus images

**Solution**: Two-pass calibration
1. **Pass 1**: Quick center-window autofocus → sharp image
2. **Pass 2**: YOLO detection on sharp image → refined object-focused autofocus

**Result**: Reliable object detection and precise autofocus, even with off-center objects!

---

**Files Modified**:
- `camera/pi_camera_controller.py` (lines 1063-1245)

**Status**: ✅ Ready to test
**Expected Improvement**: YOLO detection should now work reliably on your teddy bear!
