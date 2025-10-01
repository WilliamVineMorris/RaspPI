# LED Flickering V5.1 - Visual Timeline

## Before V5.1 (THE PROBLEM)

```
SCAN START
│
├─ [LED ON 30%] ──────────────┐ Scan-level control turns LEDs ON
│                              │
├─ CALIBRATION STARTS          │
│   ├─ Camera 0 autofocus      │ LEDs stay ON during calibration
│   ├─ Camera 1 autofocus      │
│   └─ CALIBRATION ENDS        │
│       └─ [LED OFF] ◄─────────┘ CONFLICT! Finally block turns LEDs OFF
│           ▲
│           │ FLICKER HERE! OFF→ON transition visible
│           │
├─ [LED ON 30%] ──────────────┐ Need to turn back ON (implicit)
│                              │
├─ SCAN POINT 0                │
│   └─ [Capture]               │ LEDs ON during capture
│                              │
├─ SCAN POINT 1                │
│   └─ [Capture]               │ LEDs ON during capture
│                              │
├─ ... (points 2-7)            │
│                              │
└─ SCAN END                    │
    └─ [LED OFF] ◄─────────────┘ Turn OFF at scan end

LED TRANSITIONS: 3+ (ON, OFF, ON, OFF) = FLICKERING
```

## After V5.1 (THE FIX)

```
SCAN START
│
├─ [LED ON 30%] ──────────────┐ Scan-level control turns LEDs ON
│                              │
├─ CALIBRATION STARTS          │
│   ├─ Camera 0 autofocus      │ LEDs stay ON during calibration
│   ├─ Camera 1 autofocus      │
│   └─ CALIBRATION ENDS        │
│       └─ [NO ACTION] ────────┤ V5.1: DO NOT turn LEDs OFF here!
│                              │
├─ 50ms settling delay         │ LEDs remain ON
│                              │
├─ SCAN POINT 0                │
│   └─ [Capture]               │ LEDs ON during capture
│                              │
├─ SCAN POINT 1                │
│   └─ [Capture]               │ LEDs ON during capture
│                              │
├─ ... (points 2-7)            │ LEDs stay ON throughout
│                              │
└─ SCAN END                    │
    └─ [LED OFF] ◄─────────────┘ Turn OFF ONCE at scan end

LED TRANSITIONS: 2 (ON, OFF) = NO FLICKERING ✅
```

## Log Comparison

### BEFORE V5.1 (Flickering)
```
00:00:16.536 - 💡 SCAN: LEDs on at 30% - will remain on for all scan points
00:00:27.855 - 💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)  ← PROBLEM!
00:00:27.855 - 💡 CALIBRATION: Disabled flash after all camera calibrations
00:00:27.906 - 📸 V5: Capturing with scan-level lighting (LEDs already on)...
                     └─ But LEDs are actually OFF! Need to turn back on = FLICKER
```

### AFTER V5.1 (No Flickering)
```
00:00:16.536 - 💡 SCAN: LEDs on at 30% - will remain on for all scan points
00:00:27.856 - 💡 CALIBRATION: Completed (scan-level lighting remains active)  ← FIXED!
00:00:27.906 - 📸 V5: Capturing with scan-level lighting (LEDs already on)...
                     └─ LEDs actually ARE on! No state change needed = NO FLICKER
```

## The Code Change (Simplified)

### BEFORE (scan_orchestrator.py line 3638-3642)
```python
finally:
    # Turn off LEDs after calibration
    await self.lighting_controller.turn_off_all()  # ← CONFLICT with scan-level control
    self.logger.info("💡 CALIBRATION: Disabled flash")
```

### AFTER (scan_orchestrator.py line 3638-3640)
```python
finally:
    # V5.1: Scan-level control manages LED state - don't interfere!
    self.logger.info("💡 CALIBRATION: Completed (scan-level lighting remains active)")
```

## LED Controller Protection Layers

Even though the controller has protection, it can't prevent conflicting commands:

```
REQUEST: turn_off_all() from calibration
    ↓
CONTROLLER: "Brightness 30% → 0% is >1% change, updating PWM..."
    ↓
PWM HARDWARE: Duty cycle 30% → 0% (LEDs turn OFF)
    ↓
REQUEST: Need LEDs on for scan (implicit from capture)
    ↓
CONTROLLER: "Brightness 0% → 30% is >1% change, updating PWM..."
    ↓
PWM HARDWARE: Duty cycle 0% → 30% (LEDs turn ON)
    ↓
RESULT: OFF→ON transition = VISIBLE FLICKER
```

**The Fix**: Don't send conflicting OFF request in the first place!

## Why This Works

1. **Scan-level control**: LEDs turn ON once at scan start
2. **No interference**: Calibration doesn't touch LED state
3. **Consistent state**: LEDs stay ON throughout calibration and all scan points
4. **Clean shutdown**: LEDs turn OFF once at scan end

**Result**: Only 2 PWM updates per scan instead of 3+, eliminating flicker.
