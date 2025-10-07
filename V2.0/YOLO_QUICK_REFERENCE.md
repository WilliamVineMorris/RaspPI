# YOLO11n Auto-Focus Detection - Quick Reference

## Quick Start

### 1. Install NCNN
```bash
pip install ncnn
```

### 2. Download YOLO11n Model
```bash
mkdir -p models/yolo11n_ncnn
wget -O models/yolo11n_ncnn.zip \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n_ncnn_model.zip
unzip models/yolo11n_ncnn.zip -d models/yolo11n_ncnn/
```

### 3. Enable in Config
Edit `config/scanner_config.yaml`:
```yaml
cameras:
  focus_zone:
    mode: 'yolo_detect'  # Change from 'static'
```

### 4. Test
```bash
python3 test_yolo_detection.py
python3 test_yolo_detection.py --with-camera  # Test with real cameras
```

---

## Configuration Options

| Parameter | Description | Default | Range |
|-----------|-------------|---------|-------|
| `mode` | Detection mode | `'static'` | `'static'` or `'yolo_detect'` |
| `confidence_threshold` | Min detection confidence | `0.30` | `0.0-1.0` |
| `iou_threshold` | NMS overlap threshold | `0.45` | `0.0-1.0` |
| `target_class` | Filter by class | `null` | Class name or `null` |
| `padding` | Extra space around object | `0.15` | `0.0-0.5` |
| `min_area` | Min object size | `0.05` | `0.0-1.0` |
| `fallback_to_static` | Use static if detection fails | `true` | `true`/`false` |

---

## Common COCO Classes

Use these for `target_class`:
- `bottle`, `cup`, `vase`, `bowl`
- `potted plant`, `book`, `clock`
- `teddy bear`, `person`, `chair`
- `null` - detect any object

---

## Output Locations

| Item | Location | Description |
|------|----------|-------------|
| Detection images | `calibration/focus_detection/` | Visualization with bounding boxes |
| Model files | `models/yolo11n_ncnn/` | NCNN param and bin files |
| Logs | `logs/scanner.log` | Detection logs and results |

---

## Visualization Legend

Detection images show:
- 🔵 **Light blue boxes** - All detected objects
- 🟢 **Green box (thick)** - Selected object for focus
- 🟡 **Yellow dashed box** - Final focus window with padding

---

## Troubleshooting Quick Fixes

| Issue | Quick Fix |
|-------|-----------|
| No objects detected | Lower `confidence_threshold` to `0.20` |
| Wrong object selected | Set `target_class` to filter |
| Object too small | Lower `min_area` to `0.03` |
| Detection too slow | Check NCNN installation (rebuild from source) |
| Model not found | Download and extract to `models/yolo11n_ncnn/` |

---

## Performance

| Device | Inference Time | Memory |
|--------|---------------|--------|
| Pi 5 | ~200-400ms | ~100MB |
| Pi 4 | ~500-800ms | ~100MB |

---

## Disable YOLO Detection

Return to static mode:
```yaml
cameras:
  focus_zone:
    mode: 'static'
```

---

## File Structure

```
V2.0/
├── camera/
│   └── yolo11n_ncnn_detector.py  # Detector implementation
├── models/
│   └── yolo11n_ncnn/
│       ├── yolo11n.param         # Model structure
│       └── yolo11n.bin           # Model weights
├── calibration/
│   └── focus_detection/          # Detection visualizations
└── config/
    └── scanner_config.yaml       # Enable here
```

---

## Log Messages

### Success:
```
✅ Object detected: bottle (confidence=0.87, area=23.4%)
   Focus window: [0.342, 0.189, 0.312, 0.445]
💾 Saved detection visualization: calibration/focus_detection/camera0_detection_*.jpg
```

### Fallback:
```
⚠️ No objects detected in image
🔄 Camera camera0 falling back to static window
```

---

## Best Practices

1. ✅ **Always enable fallback** - Set `fallback_to_static: true`
2. ✅ **Check visualizations** - Review detection images regularly
3. ✅ **Start with defaults** - Tune parameters only if needed
4. ✅ **Good lighting** - Ensure well-lit calibration environment
5. ✅ **Center object** - Position scan subject in camera view

---

## Testing Commands

```bash
# Basic detector test
python3 test_yolo_detection.py

# Test with cameras
python3 test_yolo_detection.py --with-camera

# View detection images
ls -lh calibration/focus_detection/

# Check logs
tail -f logs/scanner.log | grep -E "YOLO|detection"
```

---

## Support

For detailed setup instructions, see:
- `YOLO11N_SETUP_GUIDE.md` - Complete installation guide
- `logs/scanner.log` - Detailed logs with detection info

---

**Last Updated**: October 7, 2025
