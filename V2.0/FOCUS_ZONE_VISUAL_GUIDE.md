# Focus Zone Visual Guide

## Before: Full-Frame Autofocus (Problem)

```
┌────────────────────────────────────────┐
│  Wall                            Wall  │
│                                        │
│  Background          Background        │
│         ╔══════════════════╗          │
│         ║   Turntable      ║          │
│         ║      ┌────┐      ║          │
│         ║      │OBJ │ ←────╫──────────┤ Object you want to scan
│         ║      └────┘      ║          │
│         ║                  ║          │
│         ╚══════════════════╝          │
│  Background          Background        │
│                                        │
│  Floor                          Floor  │
└────────────────────────────────────────┘

Problem: Camera considers EVERYTHING
- May focus on wall (furthest)
- May focus on floor (nearest)
- May focus on background clutter
- Inconsistent exposure (bright wall vs dark object)
```

---

## After: Focus Zone Autofocus (Solution)

```
┌────────────────────────────────────────┐
│  Wall                            Wall  │
│                                        │
│  Background          Background        │
│  ┌──────────────────────────────────┐ │
│  │      Turntable                   │ │
│  │    ╔═══════════════╗             │ │
│  │    ║  ┌────┐       ║ ← FOCUS     │ │
│  │    ║  │OBJ │       ║   ZONE      │ │
│  │    ║  └────┘       ║             │ │
│  │    ╚═══════════════╝             │ │
│  │                                  │ │
│  └──────────────────────────────────┘ │
│  Background          Background        │
│                                        │
│  Floor                          Floor  │
└────────────────────────────────────────┘

Solution: Camera ONLY considers focus zone
✅ Always focuses on turntable center
✅ Ignores walls, floor, background
✅ Faster autofocus (smaller area)
✅ Consistent exposure on object
```

---

## Configuration Window Examples

### 1. Default: Center 50% (Recommended)
```
window: [0.25, 0.25, 0.5, 0.5]

┌────────────────────────┐
│                        │
│    ┌──────────┐        │
│    │          │        │
│    │  ┌────┐  │        │
│    │  │ZONE│  │ ← 50% │
│    │  └────┘  │        │
│    │          │        │
│    └──────────┘        │
│                        │
└────────────────────────┘

Good for: Most objects
Coverage: Half image width/height
Balance: Focus accuracy + scene context
```

---

### 2. Tight Focus: Center 40%
```
window: [0.3, 0.3, 0.4, 0.4]

┌────────────────────────┐
│                        │
│                        │
│     ┌────────┐         │
│     │ ┌────┐ │         │
│     │ │ZONE│ │ ← 40%  │
│     │ └────┘ │         │
│     └────────┘         │
│                        │
│                        │
└────────────────────────┘

Good for: Small objects, jewelry
Coverage: 40% of image
Advantage: Very precise focus
Tradeoff: Object must be centered
```

---

### 3. Very Tight: Center 30%
```
window: [0.35, 0.35, 0.3, 0.3]

┌────────────────────────┐
│                        │
│                        │
│                        │
│      ┌──────┐          │
│      │ ZONE │ ← 30%   │
│      └──────┘          │
│                        │
│                        │
│                        │
└────────────────────────┘

Good for: Tiny objects (coins, rings)
Coverage: 30% of image
Advantage: Maximum precision
Tradeoff: Very sensitive to centering
```

---

### 4. Wide Horizontal: 60% × 40%
```
window: [0.2, 0.3, 0.6, 0.4]

┌────────────────────────┐
│                        │
│                        │
│   ┌────────────────┐   │
│   │                │   │
│   │  ZONE (WIDE)   │ ← 60% × 40%
│   │                │   │
│   └────────────────┘   │
│                        │
│                        │
└────────────────────────┘

Good for: Elongated objects (bottles, tools)
Coverage: 60% width, 40% height
Advantage: Captures wider objects
Tradeoff: Less vertical precision
```

---

### 5. Disabled: Full Frame
```
focus_zone.enabled: false

┌────────────────────────┐
│████████████████████████│
│████████████████████████│
│████████████████████████│
│████████████████████████│
│████████ZONE████████████│ ← 100% (entire image)
│████████████████████████│
│████████████████████████│
│████████████████████████│
│████████████████████████│
└────────────────────────┘

Good for: Large objects filling frame
Coverage: Entire image
Advantage: Maximum coverage
Tradeoff: May focus on background
```

---

## Coordinate System

```
Image dimensions: 1920 × 1080 pixels

(0,0) ────────────────────────────► X (1920)
  │
  │  window: [0.25, 0.25, 0.5, 0.5]
  │
  │  ┌───────────────────────────┐
  │  │                           │
  │  │   (480,270)               │
  │  │      ↓                    │
  ▼  │      ┌─────────┐          │
  Y  │      │         │          │
(1080)│      │  ZONE   │ ← 960×540 pixels
     │      │         │          │
     │      └─────────┘          │
     │                (1440,810) │
     │                           │
     └───────────────────────────┘

Calculation:
  x_start = 0.25 × 1920 = 480 px
  y_start = 0.25 × 1080 = 270 px
  width   = 0.5 × 1920 = 960 px
  height  = 0.5 × 1080 = 540 px
  
  Zone: (480, 270, 960, 540) pixels
```

---

## Turntable Alignment

### Correctly Aligned (Good):
```
┌────────────────────────┐
│                        │
│     ┌────────┐         │
│     │ ╔════╗ │         │
│     │ ║ OBJ║ │ ← Object centered
│     │ ╚════╝ │         │
│     └────────┘         │
│                        │
└────────────────────────┘

✅ Object in focus zone
✅ Good focus and exposure
✅ Consistent results
```

### Off-Center (Bad):
```
┌────────────────────────┐
│                        │
│     ┌────────┐         │
│     │        │         │
│     │        │         │ ╔════╗ ← Object outside zone
│     └────────┘         │ ║ OBJ║
│                        │ ╚════╝
└────────────────────────┘

❌ Object outside focus zone
❌ May not focus correctly
❌ Need to realign turntable OR use wider window
```

---

## ScalerCrop (Digital Zoom) - Optional

### Without Crop (Normal):
```
Sensor readout: 1920×1080
┌────────────────────────┐
│                        │
│     ┌────────┐         │
│     │ ┌────┐ │         │
│     │ │OBJ │ │         │
│     │ └────┘ │         │
│     └────────┘         │
│                        │
└────────────────────────┘
Output: 1920×1080 full image
```

### With Crop (Zoom):
```
Sensor crop: ~1150×750
   ┌──────────────┐
   │  ┌────────┐  │
   │  │ ┌────┐ │  │
   │  │ │OBJ │ │  │
   │  │ └────┘ │  │
   │  └────────┘  │
   └──────────────┘
Output: 1150×750 cropped image
```

**use_crop: false** (recommended)
- ✅ Full resolution
- ✅ Scene context preserved
- ✅ Can crop in post-processing

**use_crop: true** (advanced)
- ❌ Reduced resolution
- ✅ Higher object detail per pixel
- ✅ Smaller file sizes

---

## Real-World Example

### Scanning a Small Figurine

**Object**: 50mm tall figurine  
**Turntable**: 200mm diameter  
**Camera resolution**: 1920×1080

#### Setup:
```yaml
focus_zone:
  enabled: true
  window: [0.3, 0.3, 0.4, 0.4]  # 40% center zone
  use_crop: false
```

#### Result:
```
┌────────────────────────────┐
│  Turntable edge            │
│   ┌──────────────┐         │
│   │              │         │
│   │   ┌─────┐    │         │
│   │   │ ▲▲  │ ← Zone 768×432 px
│   │   │ ││  │              │
│   │   │ ││  │              │
│   │   └─────┘              │
│   │      ↑                 │
│   │   Figurine             │
│   └──────────────┘         │
│                            │
└────────────────────────────┘

✅ Autofocus locked on figurine
✅ Exposure optimized for object
✅ Background ignored
✅ Fast AF convergence (~1s)
```

---

## Comparison: Focus Methods

### Method 1: Full-Frame AF (Old)
```
┌─────────────────────────┐
│█████████████████████████│ ← Entire image analyzed
│█████████████████████████│
│██████┌────┐█████████████│
│██████│OBJ │█████████████│
│██████└────┘█████████████│
│█████████████████████████│
└─────────────────────────┘

Analysis: ~2 million pixels
Time: 2-4 seconds
Reliability: Low (distracted by background)
```

### Method 2: Focus Zone (New)
```
┌─────────────────────────┐
│                         │
│     ╔═════════╗         │ ← Only zone analyzed
│     ║ ┌────┐  ║         │
│     ║ │OBJ │  ║         │
│     ║ └────┘  ║         │
│     ╚═════════╝         │
└─────────────────────────┘

Analysis: ~500K pixels (zone only)
Time: 0.5-1.5 seconds
Reliability: High (focused on target)
```

### Method 3: Object Detection (Not Used)
```
┌─────────────────────────┐
│          ┌─────┐        │
│          │Detect│ ← ML inference
│      ┌───┴─────┴───┐   │
│      │   ┌────┐     │   │
│      │   │OBJ │     │   │
│      │   └────┘     │   │
│      └──────────────┘   │
└─────────────────────────┘

Analysis: Full image + ML model
Time: 0.5-2 seconds (detection + AF)
Reliability: Medium (depends on model)
Complexity: High (TensorFlow, training)
CPU: High (ML inference)

❌ Not recommended for turntable scanning
```

---

## Decision Tree

```
Is object always on turntable center?
│
├─ YES → Use Focus Zone ✅
│         └─ Object size?
│             ├─ Small (< 30% of image) → window: [0.3, 0.3, 0.4, 0.4]
│             ├─ Medium (30-60%)       → window: [0.25, 0.25, 0.5, 0.5] (default)
│             └─ Large (> 60%)         → window: [0.2, 0.2, 0.6, 0.6] or disable
│
└─ NO → Disable focus zone or use object detection
         └─ Turntable off-center?
             ├─ Slightly off → Adjust window position
             └─ Very off    → enabled: false (full-frame AF)
```

---

## Summary Diagram

```
┌────────────────────────────────────────────────────────────┐
│                     CAMERA VIEW                             │
│                                                             │
│  Background clutter ════════════ Ignored                    │
│                                                             │
│           ╔═════════════════════════╗                      │
│           ║   FOCUS ZONE            ║                      │
│           ║                         ║                      │
│           ║    ┌────────────┐       ║                      │
│           ║    │ Turntable  │       ║  ← AfWindows region │
│           ║    │  ┌──────┐  │       ║                      │
│           ║    │  │Object│  │       ║  ← What camera sees │
│           ║    │  └──────┘  │       ║     for autofocus   │
│           ║    └────────────┘       ║                      │
│           ║                         ║                      │
│           ╚═════════════════════════╝                      │
│                                                             │
│  Background clutter ════════════ Ignored                    │
│                                                             │
└────────────────────────────────────────────────────────────┘

Result: Fast, reliable focus on scanning object
```

---

**Visual guide for turntable-optimized autofocus**  
**See FOCUS_ZONE_CONFIGURATION.md for full technical details**
