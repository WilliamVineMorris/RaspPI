# Autofocus Improvement for Dragon Figure

**Date**: 2025-10-07  
**Issue**: Autofocus not focusing correctly on dragon figure despite focus region appearing correct  
**Root Cause**: Focus window too large + wrong AF range + static mode not ideal for small objects

---

## Problem Analysis

Looking at the dragon figure on the turntable, three issues were identified:

### 1. **Focus Windows Too Large (50% of image)**
- **Previous settings**:
  - Camera 0: `[0.30, 0.25, 0.5, 0.5]` = 30-80% horizontal, 25-75% vertical (50% coverage)
  - Camera 1: `[0.20, 0.25, 0.5, 0.5]` = 20-70% horizontal, 25-75% vertical (50% coverage)

- **Problem**: 
  - Dragon figure is relatively small (~15-20% of image)
  - Large focus window includes cardboard background, turntable edge, and empty space
  - Autofocus gets confused by multiple high-contrast areas (cardboard texture, turntable edge, dragon)
  - Camera may focus on background instead of object

### 2. **Wrong AfRange Setting (Macro)**
- **Previous**: `AfRange: Macro` (8cm to 1m)
- **Problem**: 
  - If cameras are >1m from turntable, Macro range excludes the correct focus distance
  - Macro is for extreme close-up photography (8-100cm)
  - Typical tabletop scanning uses 30cm-150cm distance

### 3. **Static Mode Not Ideal**
- **Previous**: `mode: 'static'` - fixed focus window
- **Problem**:
  - Object position and size varies
  - Static window must be large to accommodate all objects
  - Doesn't adapt to different object sizes (dragon is small, but window is large)

---

## Solutions Implemented

### ✅ **Solution 1: Enable YOLO Object Detection (PRIMARY FIX)**

**Changed in `config/scanner_config.yaml` line ~166:**
```yaml
# BEFORE:
mode: 'static'

# AFTER:
mode: 'yolo_detect'  # Automatically detects dragon and creates tight focus window
```

**How it works:**
1. YOLO11n detects the dragon in the image (confidence_threshold: 0.15)
2. Creates a tight bounding box around the detected object
3. Adds 15% padding for safety margin
4. Sets AfWindows to focus ONLY on the dragon (not background)

**Benefits:**
- ✅ Automatically adapts to object size
- ✅ Ignores background/turntable (excluded: 'bed', 'dining table', 'table')
- ✅ Centers on object regardless of position
- ✅ Works for different object sizes

**Configuration:**
```yaml
yolo_detection:
  enabled: true
  model_path: 'models/yolo11n.pt'
  confidence_threshold: 0.15      # Low threshold to detect any object
  target_class: null              # Accept ANY object (not just specific class)
  exclude_classes: ['bed', 'dining table', 'table']  # Ignore turntable
  padding: 0.15                   # 15% margin around detected object
  min_area: 0.03                  # Minimum 3% of image
  fallback_to_static: true        # Use static if detection fails
```

---

### ✅ **Solution 2: Reduced Static Window Size (FALLBACK)**

**Changed in `config/scanner_config.yaml` lines ~169-178:**
```yaml
# BEFORE (large windows):
camera_0:
  window: [0.30, 0.25, 0.5, 0.5]   # 50% coverage (30-80% horiz, 25-75% vert)
camera_1:
  window: [0.20, 0.25, 0.5, 0.5]   # 50% coverage (20-70% horiz, 25-75% vert)

# AFTER (tight windows):
camera_0:
  window: [0.35, 0.30, 0.35, 0.35]  # 35% coverage (35-70% horiz, 30-65% vert)
camera_1:
  window: [0.30, 0.30, 0.35, 0.35]  # 35% coverage (30-65% horiz, 30-65% vert)
```

**Reduction**: 50% → 35% square window
- Old: 2500 pixels² (at 100×100 reference)
- New: 1225 pixels² (51% smaller area)

**Benefits:**
- ✅ Focuses on central area where object sits
- ✅ Reduces background inclusion
- ✅ Better for small objects like the dragon
- ✅ Still large enough for object variation

---

### ✅ **Solution 3: Changed AfRange from Macro to Normal**

**Changed in `camera/pi_camera_controller.py` lines ~587-609:**
```python
# BEFORE:
af_range_macro = controls.AfRangeEnum.Macro  # 8cm to 1m
picamera2.set_controls({
    "AfMode": af_mode_auto,
    "AfRange": af_range_macro
})
logger.info(f"AF range set to Macro (8cm-1m, closest objects only)")

# AFTER:
af_range_setting = controls.AfRangeEnum.Normal  # 30cm to infinity
picamera2.set_controls({
    "AfMode": af_mode_auto,
    "AfRange": af_range_setting
})
logger.info(f"AF range set to Normal (30cm-infinity, typical scanning distance)")
```

**Focus Distance Ranges:**
- **Macro**: 8cm to 100cm (extreme close-up only)
- **Normal**: 30cm to infinity (standard photography) ← **NEW SETTING**
- **Full**: 8cm to infinity (allows any distance)

**Why Normal is Better:**
- ✅ Typical scanner distance: 40-80cm from turntable
- ✅ Macro excludes >1m (may be excluding correct distance)
- ✅ Normal covers typical tabletop scanning range
- ✅ Prevents "out of range" focus failures

---

## Expected Results

### Before Changes:
- ❌ Autofocus on cardboard background (high contrast texture)
- ❌ Autofocus on turntable edge (sharp boundary)
- ❌ Dragon appears soft/blurry
- ❌ Inconsistent focus between captures

### After Changes:
- ✅ YOLO detects dragon and creates tight focus window
- ✅ Autofocus ONLY on dragon figure (not background)
- ✅ Sharp, crisp dragon details
- ✅ Consistent focus across all rotation angles
- ✅ Works for different object sizes (adapts automatically)

---

## Testing Instructions

1. **Restart the scanner system** to load new config:
   ```bash
   cd RaspPI/V2.0
   python main.py
   ```

2. **Test single capture**:
   - Position dragon on turntable
   - Trigger capture via web interface
   - Check console logs for:
     ```
     🎯 Camera camera_0 attempting YOLO object detection for focus window...
     📷 Camera camera_0 focus window (yolo_detected): AfWindows=[(x, y, w, h)]
     ✅ Camera camera_0 async autofocus completed successfully
     ```

3. **Check detection visualization**:
   - Look in `calibration/focus_detection/` directory
   - Should see images with dragon highlighted by bounding box
   - Focus window should tightly surround dragon (not background)

4. **Verify image sharpness**:
   - Captured image should have sharp dragon details
   - Background may be soft (expected if using shallow depth of field)
   - Check dragon edges, text/details are crisp

---

## Fallback Behavior

If YOLO detection fails (object not detected):
1. System automatically falls back to static window mode
2. Uses new smaller static windows (35% vs 50%)
3. Logs warning: `"⚠️ YOLO detection failed, using static fallback"`
4. Still better than original large windows

---

## Alternative Solutions (If Issues Persist)

### If YOLO Detects Wrong Object:
```yaml
# Restrict to specific object class
yolo_detection:
  target_class: 'bird'  # Or 'toy', 'vase', depending on YOLO classification
```

### If Dragon Too Small for YOLO:
```yaml
# Lower minimum area threshold
yolo_detection:
  min_area: 0.01  # Reduce from 3% to 1%
```

### If Focus Still on Background:
```yaml
# Switch to edge detection mode
focus_zone:
  mode: 'edge_detect'  # Uses edge density to find object
```

### If Need Different Focus Distance:
```python
# In pi_camera_controller.py line ~593, change to Full range:
af_range_setting = controls.AfRangeEnum.Full  # 8cm to infinity (any distance)
```

---

## Technical Details

### Focus Window Coordinate System:
- Format: `[x_start, y_start, width, height]`
- Values: 0.0 to 1.0 (fractions of image dimensions)
- Example: `[0.35, 0.30, 0.35, 0.35]` means:
  - Start at 35% from left, 30% from top
  - Extend 35% width, 35% height
  - Covers 35-70% horizontal, 30-65% vertical

### AfWindows vs AfMetering:
- **AfWindows**: Absolute pixel coordinates `[(x, y, w, h)]` relative to ScalerCropMaximum
- **AfMetering**: Set to `Windows` enum to use AfWindows regions
- Conversion: `x_px = int(x_frac * max_width)`

### YOLO Detection Flow:
1. Capture preview frame (1080p)
2. Run YOLO11n inference (~100ms on Pi 5)
3. Filter detections (confidence > 0.15, exclude tables)
4. Select best detection (largest, most centered)
5. Add 15% padding to bounding box
6. Convert to normalized coordinates
7. Set AfWindows to detected region
8. Trigger autofocus cycle

---

## Summary

**Primary Fix**: YOLO object detection automatically finds dragon and creates tight focus window  
**Secondary Fix**: Smaller static windows (35% vs 50%) reduce background interference  
**Tertiary Fix**: Normal AF range (30cm-∞) instead of Macro (8cm-1m) for correct distance  

**Expected Outcome**: Sharp, crisp focus on dragon figure with automatic adaptation to object size and position.

**Test on Pi hardware to confirm improvements!**
