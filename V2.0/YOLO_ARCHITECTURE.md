# YOLO11n Auto-Focus Detection - System Architecture

## Overview Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Camera Calibration Process                        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                    ┌───────────────────────────┐
                    │ auto_calibrate_camera()   │
                    │ in pi_camera_controller   │
                    └───────────┬───────────────┘
                                │
                                ▼
                    ┌───────────────────────────┐
                    │ Check focus_zone.mode     │
                    │ in scanner_config.yaml    │
                    └───────────┬───────────────┘
                                │
                ┌───────────────┴───────────────┐
                │                               │
            mode='static'                  mode='yolo_detect'
                │                               │
                ▼                               ▼
    ┌───────────────────────┐      ┌──────────────────────────┐
    │ Use Static Window     │      │ Load YOLO11n NCNN Model  │
    │ from config           │      │ (First time: ~500ms)     │
    └───────────┬───────────┘      └───────────┬──────────────┘
                │                               │
                │                               ▼
                │                  ┌──────────────────────────┐
                │                  │ Capture Preview Frame    │
                │                  │ (RGB from camera)        │
                │                  └───────────┬──────────────┘
                │                               │
                │                               ▼
                │                  ┌──────────────────────────┐
                │                  │ Run YOLO11n Inference    │
                │                  │ (~250ms on Pi 5)         │
                │                  └───────────┬──────────────┘
                │                               │
                │                               ▼
                │                  ┌──────────────────────────┐
                │                  │ Post-Process Detections  │
                │                  │ - Apply NMS              │
                │                  │ - Filter by class        │
                │                  │ - Validate size/conf     │
                │                  └───────────┬──────────────┘
                │                               │
                │                   ┌───────────┴──────────┐
                │                   │                      │
                │              Object Found          No Object / Error
                │                   │                      │
                │                   ▼                      ▼
                │       ┌──────────────────────┐  ┌──────────────────┐
                │       │ Select Best Object   │  │ Fallback to      │
                │       │ Add Padding          │  │ Static Window    │
                │       │ Convert to Fractions │  │ (if enabled)     │
                │       └──────────┬───────────┘  └────────┬─────────┘
                │                  │                       │
                │                  ▼                       │
                │       ┌──────────────────────┐          │
                │       │ Save Visualization   │          │
                │       │ Image with Boxes     │          │
                │       └──────────┬───────────┘          │
                │                  │                       │
                └──────────────────┴───────────────────────┘
                                   │
                                   ▼
                    ┌──────────────────────────┐
                    │ Convert to AfWindows     │
                    │ Pixel Coordinates        │
                    │ (relative to             │
                    │  ScalerCropMaximum)      │
                    └───────────┬──────────────┘
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ Set libcamera Controls   │
                    │ - AfMetering = Windows   │
                    │ - AfWindows = (x,y,w,h)  │
                    └───────────┬──────────────┘
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ Perform Autofocus        │
                    │ (existing logic)         │
                    └───────────┬──────────────┘
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ Unload YOLO Model        │
                    │ (Free ~100MB memory)     │
                    └───────────┬──────────────┘
                                │
                                ▼
                    ┌──────────────────────────┐
                    │ Return Calibration       │
                    │ Results                  │
                    └──────────────────────────┘
```

---

## Component Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Scanner System                              │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                  ┌──────────────┴───────────────┐
                  │                              │
                  ▼                              ▼
    ┌─────────────────────────┐    ┌─────────────────────────┐
    │   PiCameraController    │    │   ConfigManager         │
    │   (pi_camera_controller │    │   (config_manager.py)   │
    │    .py)                 │    │                         │
    │                         │◄───│ - scanner_config.yaml   │
    │ - __init__()            │    │ - focus_zone settings   │
    │ - auto_calibrate_camera │    │ - yolo_detection config │
    │ - _get_focus_window     │    └─────────────────────────┘
    │ - shutdown()            │
    └────────────┬────────────┘
                 │
                 │ uses (if mode='yolo_detect')
                 │
                 ▼
    ┌─────────────────────────┐
    │  YOLO11nNCNNDetector    │
    │  (yolo11n_ncnn_detector │
    │   .py)                  │
    │                         │
    │ - __init__()            │
    │ - load_model()          │
    │ - detect_object()       │
    │ - _preprocess_image()   │
    │ - _postprocess_detect() │
    │ - _save_visualization() │
    │ - unload_model()        │
    └────────────┬────────────┘
                 │
                 │ uses
                 │
    ┌────────────┴────────────┐
    │                         │
    ▼                         ▼
┌──────────┐         ┌─────────────────┐
│   NCNN   │         │  OpenCV (cv2)   │
│ Library  │         │  - Image I/O    │
│          │         │  - Preprocessing│
│ - Model  │         │  - Visualization│
│   Load   │         │  - NMS          │
│ - Infer  │         └─────────────────┘
└──────────┘
```

---

## Data Flow

```
┌────────────────────┐
│  Camera Preview    │
│  Frame (RGB)       │
│  e.g., 3280×2464   │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  YOLO Preprocessing│
│  - Resize to 640×640│
│  - Letterbox pad   │
│  - Normalize [0,1] │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  NCNN Inference    │
│  Input: 640×640×3  │
│  Output: 8400×84   │
│  (detections)      │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Post-Processing   │
│  - Parse outputs   │
│  - Filter conf     │
│  - Apply NMS       │
│  - Select best     │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Bounding Box      │
│  [x, y, w, h]      │
│  in pixels         │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Add Padding       │
│  - Expand by 15%   │
│  - Clamp to [0,1]  │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Fractional Coords │
│  [0.342, 0.189,    │
│   0.312, 0.445]    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Save Visualization│
│  - Draw all boxes  │
│  - Highlight best  │
│  - Show focus zone │
│  - Save to file    │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  Convert to Pixels │
│  Relative to       │
│  ScalerCropMaximum │
│  e.g., (1592, 661, │
│        1453, 1556) │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐
│  AfWindows Control │
│  Applied to camera │
└────────────────────┘
```

---

## File System Layout

```
V2.0/
│
├── camera/                         # Camera modules
│   ├── base.py                     # Abstract camera interface
│   ├── pi_camera_controller.py    # Pi camera implementation
│   └── yolo11n_ncnn_detector.py   # ✨ NEW: YOLO detector
│
├── config/                         # Configuration
│   └── scanner_config.yaml         # ✨ UPDATED: Added YOLO config
│
├── models/                         # ✨ NEW: Model files
│   └── yolo11n_ncnn/
│       ├── yolo11n.param           # Model structure (~15KB)
│       └── yolo11n.bin             # Model weights (~6MB)
│
├── calibration/                    # ✨ NEW: Calibration outputs
│   └── focus_detection/            # Detection visualizations
│       ├── camera0_detection_YYYYMMDD_HHMMSS.jpg
│       └── camera1_detection_YYYYMMDD_HHMMSS.jpg
│
├── logs/                           # System logs
│   └── scanner.log                 # YOLO logs appear here
│
├── Documentation/                  # ✨ NEW: YOLO docs
│   ├── YOLO_README.md
│   ├── YOLO_QUICK_REFERENCE.md
│   ├── YOLO11N_SETUP_GUIDE.md
│   └── YOLO11N_IMPLEMENTATION_SUMMARY.md
│
├── Scripts/                        # ✨ NEW: Helper scripts
│   ├── test_yolo_detection.py     # Test script
│   └── setup_yolo_model.sh        # Model download
│
└── requirements.txt                # ✨ UPDATED: NCNN notes
```

---

## State Diagram

```
┌─────────────┐
│   System    │
│   Startup   │
└──────┬──────┘
       │
       ▼
┌─────────────┐      mode='static'
│   Check     ├──────────────────┐
│   Config    │                  │
│   Mode      │                  ▼
└──────┬──────┘           ┌─────────────┐
       │                  │ No YOLO     │
       │ mode='yolo'      │ Detector    │
       │                  └─────────────┘
       ▼
┌─────────────┐
│ Initialize  │
│ YOLO        │
│ Detector    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Detector    │
│ Ready       │
│ (Model Not  │
│  Loaded)    │
└──────┬──────┘
       │
       │ Calibration starts
       │
       ▼
┌─────────────┐
│ Load Model  │
│ (~500ms)    │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Model       │
│ Loaded      │
│ (~100MB)    │
└──────┬──────┘
       │
       │ Capture frame
       │
       ▼
┌─────────────┐
│ Running     │
│ Inference   │
│ (~250ms)    │
└──────┬──────┘
       │
       │ Detection complete
       │
       ▼
┌─────────────┐
│ Unload      │
│ Model       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Detector    │
│ Ready       │
│ (Idle)      │
└─────────────┘
```

---

## Memory Usage Timeline

```
Memory (MB)
  │
200│
   │
150│
   │                    ┌─────┐
100│                    │INFER│
   │                    │     │
 50│                ┌───┴─────┴───┐
   │                │LOAD    UNLOAD│
   │                │              │
  0├────────────────┴──────────────┴────────────────────────►
   │  System    Calib   Detect   Calib    Scanning
   │  Startup   Start           Complete
   │
   Time →
   
Legend:
┌────┐  YOLO model in memory
│    │  
└────┘
```

---

## Detection Workflow - Detailed

```
START: auto_calibrate_camera('camera0')
│
├─► Check camera state
│   └─► Start camera if needed
│
├─► Enable auto-exposure controls
│
├─► Get focus window
│   │
│   ├─► Mode = 'static'?
│   │   └─► Use configured window [0.40, 0.25, 0.5, 0.5]
│   │
│   └─► Mode = 'yolo_detect'?
│       │
│       ├─► Load YOLO model (if not loaded)
│       │   └─► NCNN initialization
│       │       ├─► Load .param file
│       │       ├─► Load .bin file
│       │       └─► Optimize for ARM
│       │
│       ├─► Capture preview frame
│       │   └─► picamera2.capture_array("main")
│       │       └─► RGB format, full resolution
│       │
│       ├─► Preprocess image
│       │   ├─► Calculate scale factor
│       │   ├─► Resize to 640×640
│       │   ├─► Add letterbox padding
│       │   ├─► Convert BGR→RGB
│       │   └─► Normalize to [0,1]
│       │
│       ├─► Run inference
│       │   ├─► net.input("in0", mat)
│       │   └─► net.extract("out0")
│       │       └─► Output: [1, 84, 8400]
│       │
│       ├─► Post-process detections
│       │   ├─► Transpose to [8400, 84]
│       │   ├─► Extract boxes [x,y,w,h]
│       │   ├─► Get class scores
│       │   ├─► Filter by confidence > 0.30
│       │   ├─► Filter by target_class (if set)
│       │   ├─► Apply NMS (IOU < 0.45)
│       │   └─► Select highest confidence
│       │
│       ├─► Validate detection
│       │   ├─► Check object area > 5%
│       │   └─► Valid? Continue : Fallback
│       │
│       ├─► Add padding
│       │   ├─► Expand box by 15%
│       │   └─► Clamp to image bounds
│       │
│       ├─► Save visualization
│       │   ├─► Draw all detections (blue)
│       │   ├─► Draw best detection (green)
│       │   ├─► Draw focus window (yellow)
│       │   └─► Save to calibration/focus_detection/
│       │
│       └─► Return focus window
│           └─► [x_frac, y_frac, w_frac, h_frac]
│
├─► Convert to pixel coordinates
│   ├─► Get ScalerCropMaximum
│   ├─► x_px = x_frac × max_width
│   ├─► y_px = y_frac × max_height
│   ├─► w_px = w_frac × max_width
│   └─► h_px = h_frac × max_height
│
├─► Set camera controls
│   ├─► AfMetering = Windows
│   └─► AfWindows = [(x_px, y_px, w_px, h_px)]
│
├─► Wait for AE to settle
│   └─► 3 frames @ 0.3s = 0.9s
│
├─► Perform autofocus
│   └─► Existing autofocus logic
│
├─► Capture final metadata
│   └─► Exposure, gain, lens position
│
├─► Unload YOLO model
│   └─► Free ~100MB memory
│
└─► Return calibration results
    └─► {focus, exposure_time, analogue_gain}

END
```

---

## Visualization Image Layout

```
┌──────────────────────────────────────────────────────────┐
│  camera0_detection_20251007_143522.jpg                   │
│  3280 × 2464 pixels                                      │
├──────────────────────────────────────────────────────────┤
│                                                          │
│    ┌─────────────┐                                      │
│    │ person: 0.45│  ← Light blue box (not selected)     │
│    └─────────────┘                                      │
│                                                          │
│              ┏━━━━━━━━━━━━━━━━━━━┓                       │
│              ┃ SELECTED:         ┃                       │
│              ┃ bottle (0.87)     ┃  ← Green thick box   │
│              ┃                   ┃                       │
│              ┃                   ┃                       │
│              ┃       ┌ ─ ─ ─ ─ ─┐┃                       │
│              ┃       │           │┃  ← Yellow dashed     │
│              ┃       │ FOCUS     │┃     (padded box)     │
│              ┃       │ WINDOW    │┃                       │
│              ┃       └ ─ ─ ─ ─ ─┘┃                       │
│              ┗━━━━━━━━━━━━━━━━━━━┛                       │
│                                                          │
│                      ┌──────────┐                        │
│                      │chair:0.52│  ← Light blue box     │
│                      └──────────┘                        │
│                                                          │
└──────────────────────────────────────────────────────────┘

Legend:
  Light Blue Boxes  = All detected objects
  Green Thick Box   = Selected object (highest confidence)
  Yellow Dashed Box = Final focus window with padding
```

---

## Performance Profile

```
Total Calibration Time Breakdown:

┌─────────────────────────────────────────────────┐
│ Static Mode (Baseline)                          │
├─────────────────────────────────────────────────┤
│ Camera setup:        200ms ████                 │
│ AE settle:           900ms ██████████████       │
│ Autofocus:           800ms ███████████          │
│ Metadata capture:    100ms ██                   │
├─────────────────────────────────────────────────┤
│ TOTAL:              2000ms                      │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ YOLO Detection Mode                             │
├─────────────────────────────────────────────────┤
│ Camera setup:        200ms ████                 │
│ Load model (1st):    500ms ████████ (cached)    │
│ Capture frame:        50ms █                    │
│ Detection:           250ms ████                 │
│ Visualization:        50ms █                    │
│ AE settle:           900ms ██████████████       │
│ Autofocus:           800ms ███████████          │
│ Metadata capture:    100ms ██                   │
│ Unload model:         50ms █                    │
├─────────────────────────────────────────────────┤
│ TOTAL (1st run):    2900ms                      │
│ TOTAL (cached):     2400ms                      │
└─────────────────────────────────────────────────┘

Overhead: +400ms average (20% increase)
```

---

## Configuration Decision Tree

```
          Start
            │
            ▼
      ┌─────────────┐
      │ What are you│
      │ scanning?   │
      └──────┬──────┘
             │
       ┌─────┴─────┐
       │           │
  Always same  Different objects
  object type    each time
       │           │
       ▼           ▼
  Use Static   Use YOLO
  mode='static' mode='yolo_detect'
       │           │
       │           ▼
       │      ┌─────────────┐
       │      │ Specific    │
       │      │ object type?│
       │      └──────┬──────┘
       │             │
       │        ┌────┴────┐
       │        │         │
       │       Yes       No
       │        │         │
       │        ▼         ▼
       │   Set target  target_class:
       │   _class:     null
       │   'bottle'    (detect any)
       │        │         │
       └────────┴─────────┘
                │
                ▼
           Configure
           confidence,
           padding, etc.
```

---

**This architecture enables flexible, automatic focus window detection while maintaining the reliability and simplicity of static window configuration.**
