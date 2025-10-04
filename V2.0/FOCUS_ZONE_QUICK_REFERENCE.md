# Focus Zone Quick Reference

## What It Is
**Constrains camera autofocus/metering to turntable center instead of entire image**

## Why Use It
✅ Focus on object, not background  
✅ Faster autofocus (smaller search area)  
✅ Better exposure metering  
✅ No object detection needed  
✅ Works for any object on turntable

---

## Quick Setup

### 1. Enable in Config (`scanner_config.yaml`):
```yaml
cameras:
  focus_zone:
    enabled: true  # Turn on focus zone
    window: [0.25, 0.25, 0.5, 0.5]  # Center 50%
    use_crop: false  # Don't crop (recommended)
```

### 2. Deploy to Pi and Test

### 3. Check Logs:
```
📷 Camera 0 focus zone: x=480, y=270, w=960, h=540 px (center 50% of image)
```

---

## Presets (Copy-Paste)

### Standard Objects (Default):
```yaml
window: [0.25, 0.25, 0.5, 0.5]  # 50% center
```

### Small Objects:
```yaml
window: [0.3, 0.3, 0.4, 0.4]  # 40% center (tighter)
```

### Tiny Objects:
```yaml
window: [0.35, 0.35, 0.3, 0.3]  # 30% center (very tight)
```

### Wide Objects:
```yaml
window: [0.2, 0.3, 0.6, 0.4]  # 60% width, 40% height
```

### Disable (Full Frame):
```yaml
focus_zone:
  enabled: false
```

---

## Window Format

`[x_start, y_start, width, height]` - All values 0.0-1.0

**Example**: `[0.25, 0.25, 0.5, 0.5]`
- Start at 25% from left and top
- Zone is 50% wide and 50% tall
- Result: Center 50% box

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Object soft focus | Smaller window (tighter zone) |
| Large object cut off | Larger window or disable zone |
| Zone not working | Check `enabled: true` in config |
| Want to see zone | Future: overlay on web preview |

---

## When to Use What

**Use Focus Zone (enabled):**
- ✅ Small to medium objects
- ✅ Automated scanning
- ✅ Consistent turntable positioning

**Disable Focus Zone:**
- ❌ Objects fill entire frame
- ❌ Off-center turntable placement
- ❌ Testing/troubleshooting

---

## Files Modified

- `config/scanner_config.yaml` - Configuration
- `camera/pi_camera_controller.py` - Implementation
- `FOCUS_ZONE_CONFIGURATION.md` - Full docs

---

**Status**: ✅ Ready for Pi testing  
**Default**: Center 50% window  
**Recommendation**: Keep enabled for turntable scanning
