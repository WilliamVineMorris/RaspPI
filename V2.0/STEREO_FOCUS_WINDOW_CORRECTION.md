# Stereo Camera Focus Window Configuration - CORRECTED

**Date**: 2025-10-07  
**Issue**: Focus windows need to match stereo camera setup + use Macro range for close objects (<40cm)

---

## Stereo Camera Setup Understanding

Based on the screenshot showing the dragon **slightly to the LEFT** in Camera 0's view:

```
TOP VIEW (looking down at turntable):

         Camera 0                    Camera 1
        (Left Cam)                  (Right Cam)
             ◄──────────────────────────►
             |   140mm stereo baseline  |
             ↓                          ↓
         
         ╔═══════╗                 ╔═══════╗
         ║ Cam 0 ║                 ║ Cam 1 ║
         ╚═══════╝                 ╚═══════╝
              ╲                       ╱
               ╲                     ╱
                ╲     10° toe-in    ╱
                 ╲                 ╱
                  ╲               ╱
                   ╲             ╱
                    ╲           ╱
                     ╲         ╱
                      ╲       ╱
                       ╲     ╱
                        ╲   ╱
                         ╲ ╱
                        ┌───┐
                        │ 🐉│  ← Dragon on turntable
                        └───┘
```

---

## Camera 0 View (Screenshot Analysis)

```
┌──────────────────────────────────────┐
│                                      │ ← Cardboard background
│     Dragon is SLIGHTLY LEFT          │
│        ┌─────┐                       │
│        │ 🐉  │                       │
│        └─────┘                       │
│    ◄──────────►                      │
│   Object appears                     │
│   LEFT of center                     │
│                                      │
└──────────────────────────────────────┘
   0%        50%         100% horizontal
```

**Why dragon appears LEFT:**
- Camera 0 is the LEFT stereo camera
- Views object from the LEFT side
- Object appears OFFSET TO THE LEFT in the frame

---

## Camera 1 View (Mirrored)

```
┌──────────────────────────────────────┐
│                                      │ ← Cardboard background
│          Dragon is SLIGHTLY RIGHT    │
│                       ┌─────┐        │
│                       │  🐉 │        │
│                       └─────┘        │
│                      ◄──────────►    │
│                   Object appears     │
│                   RIGHT of center    │
│                                      │
└──────────────────────────────────────┘
   0%        50%         100% horizontal
```

**Why dragon appears RIGHT (mirrored):**
- Camera 1 is the RIGHT stereo camera
- Views object from the RIGHT side
- Object appears OFFSET TO THE RIGHT in the frame (opposite of Camera 0)

---

## Focus Window Configuration

### ✅ **CORRECTED: Camera 0 (LEFT stereo camera)**

```yaml
camera_0:
  window: [0.25, 0.30, 0.35, 0.35]  # LEFT-shifted focus
  # Covers: 25-60% horizontal (shifted LEFT)
  #         30-65% vertical (centered vertically)
```

**Visual representation:**
```
┌──────────────────────────────────────┐
│                                      │
│  ╔════════════╗                     │ ← Focus window
│  ║ 🐉         ║                     │    SHIFTED LEFT
│  ╚════════════╝                     │    (25-60% horiz)
│                                      │
└──────────────────────────────────────┘
  25%      60%              100%
```

---

### ✅ **CORRECTED: Camera 1 (RIGHT stereo camera) - MIRRORED**

```yaml
camera_1:
  window: [0.40, 0.30, 0.35, 0.35]  # RIGHT-shifted focus
  # Covers: 40-75% horizontal (shifted RIGHT)
  #         30-65% vertical (centered vertically)
```

**Visual representation:**
```
┌──────────────────────────────────────┐
│                                      │
│                     ╔════════════╗  │ ← Focus window
│                     ║         🐉 ║  │    SHIFTED RIGHT
│                     ╚════════════╝  │    (40-75% horiz)
│                                      │
└──────────────────────────────────────┘
  0%              40%      75%    100%
```

---

## Horizontal Mirroring Math

To properly mirror horizontally:

**Camera 0**: Left-shifted window  
- Start: 25% (0.25)
- Width: 35% (0.35)
- End: 60% (0.25 + 0.35)

**Camera 1**: Right-shifted window (mirrored)  
- We want the window to be the same distance from the opposite edge
- Distance from left edge in Cam0: 25%
- Distance from right edge in Cam1: 25%
- Start: 100% - 25% - 35% = **40%** (0.40)
- Width: 35% (0.35) - same size
- End: 75% (0.40 + 0.35)

**Result**: Windows are **horizontally mirrored** with 25% margin from outer edges

```
Camera 0:  |<--25%-->|<----35%---->|           |
           0%       25%           60%         100%

Camera 1:  |           |<----35%---->|<--25%-->|
           0%                      40%        75%      100%
```

---

## AfRange Setting: Macro (RESTORED)

### ✅ **Using Macro Range for Close Objects (<40cm)**

```python
af_range_setting = controls.AfRangeEnum.Macro
# Focus range: 8cm to 1m (100cm)
```

**Why Macro is correct for your setup:**
- ✅ User confirmed: objects always <40cm away
- ✅ Macro range: 8cm to 1m (100cm) - INCLUDES 40cm
- ✅ Optimized for close-up photography
- ✅ Better focus accuracy at short distances
- ✅ Excludes infinity/far backgrounds (helps ignore cardboard)

**Comparison:**
- **Macro**: 8cm to 100cm ← **PERFECT for <40cm objects** ✅
- **Normal**: 30cm to infinity (includes distant backgrounds) ❌
- **Full**: 8cm to infinity (too broad, less accurate) ❌

---

## YOLO Detection Configuration

The YOLO detection remains enabled and will:
1. Detect the dragon automatically
2. Create a tight bounding box around it
3. Override the static window positions if object is detected
4. Fall back to the static windows if detection fails

**Static windows act as fallback** when YOLO doesn't detect an object.

---

## Expected Behavior

### **Camera 0 (Left stereo camera):**
1. Static window: LEFT-shifted (25-60% horizontal)
2. YOLO detects dragon: Creates tight box around dragon position
3. Autofocus: Macro range (8cm-1m), focuses on dragon at ~30-40cm
4. Result: Sharp dragon, matches stereo geometry

### **Camera 1 (Right stereo camera):**
1. Static window: RIGHT-shifted (40-75% horizontal) - mirrored from Cam0
2. YOLO detects dragon: Creates tight box around dragon position
3. Autofocus: Macro range (8cm-1m), focuses on dragon at ~30-40cm
4. Result: Sharp dragon, matches stereo geometry

---

## Verification

**To verify the configuration is correct:**

1. Check focus window positions in logs:
   ```
   📷 Camera camera_0 focus window (static): [0.25, 0.30, 0.35, 0.35]
   📷 Camera camera_1 focus window (static): [0.40, 0.30, 0.35, 0.35]
   ```

2. Visual check in captured images:
   - Camera 0: Focus region should be LEFT-shifted (matching screenshot)
   - Camera 1: Focus region should be RIGHT-shifted (mirrored)

3. Stereo correspondence:
   - Same dragon feature should appear in LEFT of Cam0 and RIGHT of Cam1
   - Focus windows should align with object position in each view
   - Both cameras should achieve sharp focus on the dragon

---

## Configuration Summary

| Setting | Camera 0 (Left) | Camera 1 (Right) | Notes |
|---------|----------------|------------------|-------|
| **Horizontal Start** | 25% | 40% | Mirrored with 25% margin from outer edges |
| **Horizontal End** | 60% | 75% | Same 35% width |
| **Vertical Start** | 30% | 30% | Identical (no vertical mirroring) |
| **Vertical End** | 65% | 65% | Same 35% height |
| **Window Size** | 35% × 35% | 35% × 35% | Both same size (square) |
| **AfRange** | Macro (8cm-1m) | Macro (8cm-1m) | Perfect for <40cm objects |
| **YOLO Mode** | yolo_detect | yolo_detect | Auto-detects dragon position |

---

## Testing Checklist

- [x] AfRange restored to Macro (8cm-1m) for objects <40cm
- [x] Camera 0 window shifted LEFT to match screenshot (25-60%)
- [x] Camera 1 window shifted RIGHT as mirror (40-75%)
- [x] Horizontal mirroring correct (25% margin from outer edges)
- [x] Vertical position identical (30-65% on both cameras)
- [x] YOLO detection enabled for automatic object finding
- [x] Window size appropriate (35% square vs previous 50%)

**Ready for testing on Pi hardware!** 🐉✨

The dragon should now be properly focused in both cameras with correct stereo geometry.
