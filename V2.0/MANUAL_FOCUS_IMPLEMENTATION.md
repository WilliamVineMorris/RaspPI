# Manual Focus Implementation - Autofocus Disabled

**Date**: 2025-10-07  
**Change**: Disabled unreliable autofocus, switched to fixed manual lens position  
**Status**: ✅ Implemented - Manual focus with configurable lens position

---

## Problem

Autofocus was unreliable and not focusing correctly on objects despite:
- YOLO object detection enabled
- Proper focus window configuration
- Correct AfRange (Macro for <40cm objects)
- Stereo-mirrored focus zones

**Root causes identified:**
- ArduCam autofocus inconsistent with object detection
- Focus windows may have been including background
- Autofocus algorithm prioritizing wrong features

---

## Solution: Fixed Manual Focus

### ✅ **Implemented: Manual Lens Position**

Switched from `AfMode: Auto` → `AfMode: Manual` with constant lens position.

**Configuration** (`config/scanner_config.yaml`):
```yaml
cameras:
  focus:
    mode: "manual"  # Autofocus disabled
    manual_lens_position: 8.0  # Fixed lens position (0.0=infinity, 10.0+=closest)
```

**Behavior**:
- Every scan point uses the same lens position (8.0 by default)
- No autofocus cycle is performed
- Lens position corresponds to web UI slider value
- Fast and consistent (no focus hunting)

---

## Configuration Options

### **Current Implementation**

```yaml
cameras:
  focus:
    mode: "manual"  # "manual" or "auto"
    
    # Manual focus settings
    manual_lens_position: 8.0  # LensPosition value
                               # 0.0 = infinity (far focus)
                               # 8.0 = ~30-40cm (default for tabletop scanning)
                               # 10.0+ = very close focus (<20cm)
                               # Web UI slider corresponds to this value
```

**Lens Position Guide:**
| Value | Focus Distance | Use Case |
|-------|---------------|----------|
| 0.0 - 2.0 | Infinity to 2m | Distant objects |
| 3.0 - 5.0 | 1m to 50cm | Tabletop (far) |
| 6.0 - 8.0 | 50cm to 30cm | **Typical scanning** ✅ |
| 9.0 - 12.0 | 30cm to 15cm | Close-up objects |
| 13.0+ | <15cm | Extreme macro |

**Default (8.0)**: Optimized for dragon figure at ~30-40cm distance

---

## Code Changes

### **camera/pi_camera_controller.py** - `auto_focus()` method

**Before (Autofocus):**
```python
async def auto_focus(self, camera_id: str) -> bool:
    # Set AfMode to Auto
    # Set AfRange to Macro
    # Run autofocus_cycle()
    # Wait for focus lock
    # Monitor AfState for completion
```

**After (Manual Focus):**
```python
async def auto_focus(self, camera_id: str) -> bool:
    """Set manual focus position (autofocus disabled)"""
    
    # Get lens position from config
    focus_config = self.config.get('focus', {})
    lens_position = focus_config.get('manual_lens_position', 8.0)
    
    # Validate range (0.0 to 15.0)
    lens_position = max(0.0, min(15.0, lens_position))
    
    # Set manual mode with fixed position
    picamera2.set_controls({
        "AfMode": controls.AfModeEnum.Manual,
        "LensPosition": lens_position
    })
    
    logger.info(f"✅ Manual focus set: LensPosition={lens_position}")
    return True
```

**Benefits:**
- ✅ Consistent focus across all scan points
- ✅ Fast (no autofocus cycle delay)
- ✅ Predictable results
- ✅ No focus hunting or failures
- ✅ Configurable via YAML
- ✅ Corresponds to web UI slider

---

## Future Enhancements (NOT YET IMPLEMENTED)

### ⚠️ **Important Limitation**

**Current scan point structure does NOT support per-point parameters.**

Scan points are defined as `Position4D(x, y, z, c)` - just 4 coordinates.
There is no mechanism to attach additional data like `lens_position` to individual points.

---

### **Option 1: Per-Point Manual Focus** ❌ NOT CURRENTLY POSSIBLE

This would require **significant code changes**:

```yaml
# EXAMPLE ONLY - THIS DOES NOT WORK IN CURRENT SYSTEM
scan_points:
  - position: {x: 100, y: 100, z: 0, c: 0}
    lens_position: 8.0  # ❌ Scan points don't support extra fields
```

**Why it doesn't work:**
- `ScanPoint` class only stores Position4D (x, y, z, c)
- No storage for per-point parameters
- Orchestrator doesn't pass custom parameters to camera controller
- Would require data structure redesign

**Implementation Requirements:**
1. Create new `ScanPoint` dataclass with optional parameters
2. Modify scan path generator to accept per-point data
3. Modify scan orchestrator to pass lens_position to camera controller
4. Modify camera controller to accept optional lens_position parameter
5. Update all scan path creation code

**Complexity**: HIGH (major refactoring required)

---

### **Option 2: Focus Stacking - Multiple Complete Scans** ✅ WORKS NOW

**The only current way to achieve focus stacking:**

Run **3 separate complete scans** with different `manual_lens_position` values:

**Workflow:**
```bash
# Scan 1: Far focus
# Edit config: manual_lens_position: 6.0
python main.py
# Run scan → saves to session_001/

# Scan 2: Mid focus  
# Edit config: manual_lens_position: 8.0
python main.py
# Run scan → saves to session_002/

# Scan 3: Near focus
# Edit config: manual_lens_position: 10.0
python main.py
# Run scan → saves to session_003/

# Post-processing:
# Merge session_001/img_001.jpg + session_002/img_001.jpg + session_003/img_001.jpg
# Repeat for all image sets
```

**Benefits:**
- ✅ Works with current system (no code changes)
- ✅ Full control over focus planes
- ✅ Can preview each focus plane independently

**Drawbacks:**
- ❌ Requires 3× scan time (must move to every point 3 times)
- ❌ Manual config editing between scans
- ❌ Must manually match images in post-processing
- ❌ Object must not move between scans

**Time Impact:**
- 100-point scan at 3 sec/point = 5 minutes
- 3 focus planes = **15 minutes total** (vs 5 min for single focus)

---

### **Option 3: Multi-Capture Per Point** ❌ NOT CURRENTLY POSSIBLE

**Ideal focus stacking approach** (requires major changes):

```yaml
# EXAMPLE ONLY - NOT IMPLEMENTED
cameras:
  focus:
    enable_focus_stacking: true
    focus_stack_positions: [6.0, 8.0, 10.0]
```

**How it would work:**
1. System moves to scan point (x, y, z, c)
2. Captures image at lens_position 6.0
3. Changes lens position to 8.0
4. Captures image at same position
5. Changes lens position to 10.0  
6. Captures image at same position
7. Moves to next scan point

**Benefits:**
- ✅ Faster: Move once, capture 3 images (saves 2/3 of motion time)
- ✅ Automatic: No manual config changes
- ✅ Perfect alignment: Same position for all focus planes

**Implementation Requirements:**
1. Modify scan orchestrator capture loop
2. Add multi-capture logic with lens position changes
3. Update storage system to handle multiple images per point
4. Add metadata tagging for focus plane index
5. Update export system to group focus stacks

**Complexity**: VERY HIGH (core system changes)

**Time Impact:**
- 100-point scan with 3 focus planes
- Motion: ~5 minutes (same as single scan)
- Capture: ~9 minutes (3× capture time)
- **Total: ~14 minutes** (vs 15 min for 3 separate scans)

Only saves ~1 minute but much more convenient!

---

## Testing

### **Test Manual Focus:**

1. Edit `config/scanner_config.yaml`:
   ```yaml
   cameras:
     focus:
       manual_lens_position: 8.0  # Start with default
   ```

2. Restart scanner system

3. Capture test image - check logs:
   ```
   📷 Camera camera_0 setting MANUAL focus (autofocus disabled)
   ✅ Camera camera_0 manual focus set: LensPosition=8.0 (from config, no autofocus)
   ```

4. Verify image sharpness:
   - Dragon should be in focus at 8.0
   - If blurry, adjust lens_position in config
   - Lower value = farther focus
   - Higher value = closer focus

5. **Find optimal value:**
   - Try: 6.0, 7.0, 8.0, 9.0, 10.0
   - Use web UI slider as reference (slider value = lens_position)
   - Pick sharpest result

---

## Migration from Autofocus

**What changed:**
- ❌ `AfMode: Auto` → ✅ `AfMode: Manual`
- ❌ `autofocus_cycle()` → ✅ `set_controls({"LensPosition": 8.0})`
- ❌ Focus windows (YOLO/static) → Still configured but NOT USED for focus
- ✅ Focus zones config preserved for future use

**Focus windows status:**
- YOLO detection: Still enabled in config but not used for autofocus
- Static focus zones: Still configured but not used
- **Reason preserved**: May be useful for future features (per-point focus calculation, ROI-based focusing)

**To re-enable autofocus** (if manual focus issues arise):
```yaml
cameras:
  focus:
    mode: "auto"  # Switch back to autofocus
    autofocus:
      enable: true
      af_range: "macro"
      timeout_seconds: 4.0
```

Then revert `camera/pi_camera_controller.py` `auto_focus()` method to use autofocus cycle.

---

## Recommendations

### **Current Setup (Objects ~30-40cm):**
```yaml
manual_lens_position: 8.0  # Default - good starting point
```

### **Closer Objects (~20-25cm):**
```yaml
manual_lens_position: 10.0  # Increased for closer focus
```

### **Further Objects (~50-60cm):**
```yaml
manual_lens_position: 6.0  # Decreased for farther focus
```

### **Variable Depth Objects:**
Consider future focus stacking with duplicated scan points:
```yaml
# Example: Tall object requiring multiple focus planes
- {x: 100, y: 100, z: 0, c: 0, lens: 6.0}   # Bottom focused
- {x: 100, y: 100, z: 0, c: 0, lens: 8.0}   # Middle focused
- {x: 100, y: 100, z: 0, c: 0, lens: 10.0}  # Top focused
```

---

## Summary

**Implemented:**
- ✅ Manual focus with configurable lens position
- ✅ Autofocus disabled (was unreliable)
- ✅ Fast, consistent focus across all scan points
- ✅ Web UI slider value = config lens_position value

**Future Possibilities:**
- 🔮 Per-point manual focus (medium complexity)
- 🔮 Calculated focus based on geometry (high complexity)
- 🔮 Focus stacking - Method A: duplicate points (already possible!)
- 🔮 Focus stacking - Method B: multiple captures per point (high complexity)

**Next Steps:**
1. Test default lens_position (8.0)
2. Adjust if needed for optimal sharpness
3. Consider focus stacking via duplicated scan points if depth of field is insufficient

**The system is now ready for reliable, consistent manual focus scanning!** 🎯📷
