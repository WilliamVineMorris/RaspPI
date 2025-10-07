# Manual Focus - Quick Reference

**Status**: ✅ Autofocus disabled, manual focus enabled  
**Default Lens Position**: 8.0 (optimized for ~30-40cm objects)

---

## What Changed

**Before:**
- ❌ Autofocus with YOLO detection
- ❌ Unreliable focus results
- ❌ Slow autofocus cycles
- ❌ Focus hunting issues

**After:**
- ✅ Fixed manual lens position
- ✅ Consistent focus every time
- ✅ Fast (no autofocus delay)
- ✅ Configurable in YAML

---

## Configuration

Edit `config/scanner_config.yaml`:

```yaml
cameras:
  focus:
    mode: "manual"
    manual_lens_position: 8.0  # Adjust this value for optimal focus
```

**Lens Position Values:**
- **6.0** - Objects at ~50cm (farther)
- **8.0** - Objects at ~30-40cm (**default** ✅)
- **10.0** - Objects at ~20cm (closer)

**How to find optimal value:**
1. Use web UI manual focus slider
2. Find sharpest position
3. Note slider value
4. Set that value in config as `manual_lens_position`

---

## Testing

1. Restart system to load new config
2. Capture test image
3. Check logs for:
   ```
   ✅ Camera camera_0 manual focus set: LensPosition=8.0 (from config, no autofocus)
   ```
4. Verify image sharpness
5. Adjust `manual_lens_position` if needed

---

## Future Features (Planned)

### Per-Point Focus (Not Yet Implemented)
```yaml
# Future: Different focus for each scan point
scan_points:
  - {x: 100, y: 100, z: 0, lens: 8.0}
  - {x: 100, y: 100, z: 45, lens: 9.0}
```

### Focus Stacking (Already Possible!)
Duplicate scan points with different lens values:
```yaml
scan_points:
  # Same position, different focus planes
  - {x: 100, y: 100, z: 0, lens: 6.0}   # Far focus
  - {x: 100, y: 100, z: 0, lens: 8.0}   # Mid focus
  - {x: 100, y: 100, z: 0, lens: 10.0}  # Near focus
```

---

## Benefits

- ✅ **Reliable**: Same focus every capture
- ✅ **Fast**: No autofocus cycle delay (~4 seconds saved per point!)
- ✅ **Simple**: One config value controls all captures
- ✅ **Predictable**: Know exactly what focus you'll get
- ✅ **Web UI Compatible**: Slider value = config value

---

**Default setting (8.0) should work well for the dragon figure at typical scanning distance!**

See `MANUAL_FOCUS_IMPLEMENTATION.md` for full documentation.
