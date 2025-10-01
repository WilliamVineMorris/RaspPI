# LED Flickering V5.1 - COMPLETE ROOT CAUSE FIX

**Date**: October 2, 2025  
**Status**: ✅ FULLY IMPLEMENTED  
**Version**: V5.1 (complete hotfix)

## 🔍 CRITICAL DISCOVERY

The V5.1 fix was **INCOMPLETE**! There were **THREE** `turn_off_all()` calls in the calibration code, and we only fixed ONE:

### All Three Calibration LED Control Points:

1. **Synchronized Focus - Primary Camera** (line 3486)
   - `turn_off_all()` after primary camera calibration
   - Status: ✅ FIXED in this update

2. **Synchronized Focus - Secondary Cameras** (line 3561)
   - `turn_off_all()` after secondary camera calibrations  
   - Status: ✅ FIXED in this update

3. **Independent Focus - All Cameras** (line 3638)
   - `turn_off_all()` after all camera calibrations
   - Status: ✅ FIXED in previous V5.1 update

### Plus THREE `set_brightness` ON Calls:

1. **Synchronized Focus - Primary** (line 3476): `set_brightness("all", 0.3)`
2. **Synchronized Focus - Secondary** (line 3535): `set_brightness("all", 0.3)`
3. **Independent Focus** (line 3578): `set_brightness("all", 0.3)`

**ALL REMOVED** - scan-level lighting already has LEDs on at 30%

## Complete LED Control Flow (FINAL)

### Before V5.1 Complete (THE PROBLEM):
```
SCAN START
├─ [LED ON 30%] ──────── Scan-level: Turn ON
├─ CALIBRATION
│   ├─ [LED ON 30%] ──── Calibration: Turn ON (redundant!)
│   ├─ ... cameras ...
│   └─ [LED OFF] ──────── Calibration: Turn OFF (CONFLICT!)
├─ [LED ON 30%] ──────── Implicit: Need ON for scan (FLICKER!)
├─ SCAN POINTS
│   └─ [LEDs stay ON]
└─ [LED OFF] ───────────── Scan-level: Turn OFF

LED TRANSITIONS: 4+ (ON, ON, OFF, ON, OFF) = FLICKERING!
```

### After V5.1 Complete (THE FIX):
```
SCAN START
├─ [LED ON 30%] ──────── Scan-level: Turn ON ONCE
├─ CALIBRATION
│   ├─ [NO ACTION] ────── Calibration: Use scan-level lighting
│   └─ ... cameras ...    LEDs remain ON throughout
├─ 50ms settling
├─ SCAN POINTS
│   └─ [LEDs stay ON]    LEDs remain ON throughout
└─ [LED OFF] ───────────── Scan-level: Turn OFF ONCE

LED TRANSITIONS: 2 (ON, OFF) = NO FLICKERING! ✅
```

## Files Modified (Complete List)

**File**: `scanning/scan_orchestrator.py`

### 1. Synchronized Focus - Primary Camera (Lines 3473-3480)
**OLD**:
```python
# Enable flash at 30% brightness for the entire calibration process
try:
    await self.lighting_controller.set_brightness("all", 0.3)
    self.logger.info("💡 CALIBRATION: Enabled 30% flash for calibration process")
except Exception as flash_error:
    self.logger.warning(f"⚠️ CALIBRATION: Could not enable flash: {flash_error}")
```

**NEW**:
```python
# 🔥 V5.1: DO NOT turn LEDs on - scan-level lighting already has them on at 30%
self.logger.info("💡 CALIBRATION: Using scan-level lighting (already on at 30%)")
```

### 2. Synchronized Focus - Primary Finally Block (Lines 3478-3480)
**OLD**:
```python
finally:
    # Always turn off the flash after calibration, even if it fails
    try:
        await self.lighting_controller.turn_off_all()
        self.logger.info("💡 CALIBRATION: Disabled flash after calibration")
    except Exception as flash_off_error:
        self.logger.warning(f"⚠️ CALIBRATION: Could not disable flash: {flash_off_error}")
```

**NEW**:
```python
finally:
    # 🔥 V5.1: DO NOT turn off LEDs - scan-level lighting manages state
    self.logger.info("💡 CALIBRATION: Primary camera completed (scan-level lighting remains active)")
```

### 3. Synchronized Focus - Secondary Cameras (Lines 3522-3527)
**OLD**:
```python
# 🔥 FIX: Enable flash ONCE before all secondary camera calibrations (prevents flickering)
secondary_cameras = [cam for cam in available_cameras if cam != primary_camera]
if secondary_cameras:
    try:
        await self.lighting_controller.set_brightness("all", 0.3)
        self.logger.info(f"💡 CALIBRATION: Enabled 30% flash for secondary camera calibrations")
    except Exception as flash_error:
        self.logger.warning(f"⚠️ CALIBRATION: Could not enable flash: {flash_error}")
```

**NEW**:
```python
# 🔥 V5.1: DO NOT turn LEDs on - scan-level lighting already has them on at 30%
secondary_cameras = [cam for cam in available_cameras if cam != primary_camera]
if secondary_cameras:
    self.logger.info(f"💡 CALIBRATION: Secondary cameras using scan-level lighting (already on at 30%)")
```

### 4. Synchronized Focus - Secondary Finally Block (Lines 3546-3548)
**OLD**:
```python
finally:
    # 🔥 FIX: Turn off flash ONCE after all secondary calibrations (prevents flickering)
    try:
        await self.lighting_controller.turn_off_all()
        self.logger.info(f"💡 CALIBRATION: Disabled flash after all secondary camera calibrations")
    except Exception as flash_off_error:
        self.logger.warning(f"⚠️ CALIBRATION: Could not disable flash: {flash_off_error}")
```

**NEW**:
```python
finally:
    # 🔥 V5.1: DO NOT turn off LEDs - scan-level lighting manages state
    self.logger.info(f"💡 CALIBRATION: Secondary cameras completed (scan-level lighting remains active)")
```

### 5. Independent Focus - All Cameras (Lines 3560-3567)
**OLD**:
```python
# 🔥 FIX: Enable flash ONCE before all camera calibrations (prevents flickering)
try:
    await self.lighting_controller.set_brightness("all", 0.3)
    self.logger.info(f"💡 CALIBRATION: Enabled 30% flash for all camera calibrations")
except Exception as flash_error:
    self.logger.warning(f"⚠️ CALIBRATION: Could not enable flash: {flash_error}")
```

**NEW**:
```python
# 🔥 V5.1: DO NOT turn LEDs on - scan-level lighting already has them on at 30%
self.logger.info(f"💡 CALIBRATION: All cameras using scan-level lighting (already on at 30%)")
```

### 6. Independent Focus - Finally Block (Line 3622)
**OLD**:
```python
finally:
    # 🔥 V5.1: DO NOT turn off LEDs here - scan-level lighting manages LED state
    # The scan has already turned LEDs on and will turn them off at the end
    self.logger.info(f"💡 CALIBRATION: Completed (scan-level lighting remains active)")
```

**NEW**: (Already fixed in previous V5.1)
```python
finally:
    # 🔥 V5.1: DO NOT turn off LEDs here - scan-level lighting manages LED state
    # The scan has already turned LEDs on and will turn them off at the end
    self.logger.info(f"💡 CALIBRATION: Completed (scan-level lighting remains active)")
```

### 7. Settling Delay Comment (Line 3641-3643)
**UPDATED**:
```python
# 🔥 V5.1: Add settling delay after calibration (LEDs remain on from scan-level control)
self.logger.info("⏱️ V5.1: Waiting 50ms for camera settling (LEDs remain on at 30%)...")
await asyncio.sleep(0.05)  # 50ms delay for camera exposure/focus to stabilize
```

## Expected Log Output (After Complete V5.1)

```
💡 SCAN: Turning on LEDs for entire scan duration...
💡 LED UPDATE: Zone 'inner' 0.0% → 30.0% (state: ON)  ← ONLY LED TRANSITION #1
💡 LED UPDATE: Zone 'outer' 0.0% → 30.0% (state: ON)
💡 SCAN: LEDs on at 30% - will remain on for all scan points

... movement to first point ...

💡 CALIBRATION: Using scan-level lighting (already on at 30%)  ← NO LED CONTROL
... or ...
💡 CALIBRATION: All cameras using scan-level lighting (already on at 30%)

... camera 0 calibration ...
💡 CALIBRATION: Primary camera completed (scan-level lighting remains active)  ← NO LED CONTROL

... camera 1 calibration ...  
💡 CALIBRATION: Secondary cameras completed (scan-level lighting remains active)  ← NO LED CONTROL

⏱️ V5.1: Waiting 50ms for camera settling (LEDs remain on at 30%)...

📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← Point 0
✅ V5: Camera capture successful with scan-level lighting

... (no LED transitions between points) ...

📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← Point 7
✅ V5: Camera capture successful with scan-level lighting

💡 SCAN: Turning off LEDs after complete scan...
💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)  ← ONLY LED TRANSITION #2
💡 LED UPDATE: Zone 'outer' 30.0% → 0.0% (state: OFF)
```

## What Should NOT Appear

❌ `💡 CALIBRATION: Enabled 30% flash for calibration process`  
❌ `💡 CALIBRATION: Enabled 30% flash for secondary camera calibrations`  
❌ `💡 CALIBRATION: Disabled flash after calibration`  
❌ `💡 CALIBRATION: Disabled flash after all secondary camera calibrations`  
❌ Any `💡 LED UPDATE` messages between initial ON and final OFF  

## Testing Protocol

### 1. Restart Scanner (CRITICAL)
```bash
sudo pkill -f run_web_interface
cd ~/RaspPI/V2.0
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null
python3 run_web_interface.py
```

### 2. Monitor Complete LED Flow
```bash
tail -f logs/scanner.log | grep -E "💡|📸|CALIBRATION"
```

### 3. Run Multi-Point Scan
- Use cylindrical pattern (8 points)
- Watch for LED transitions
- Expected: EXACTLY 2 transitions (ON once, OFF once)

### 4. Success Criteria
✅ Logs show "💡 CALIBRATION: Using scan-level lighting (already on at 30%)"  
✅ NO "💡 CALIBRATION: Enabled 30% flash" messages  
✅ NO "💡 CALIBRATION: Disabled flash" messages  
✅ Only 2 LED UPDATE messages: initial ON, final OFF  
✅ No visible flickering during calibration or scan  

## Why This Completes The Fix

### The Problem
Each calibration mode (synchronized/independent) was independently managing LEDs:
- Turning them ON at 30% (redundant - already on from scan-level)
- Turning them OFF after calibration (conflict - scan-level still needs them)

This created multiple ON→OFF→ON cycles causing flickering.

### The Solution
- Calibration code does **ZERO** LED control
- Scan-level code manages **ALL** LED state
- LEDs turn ON once at scan start
- LEDs stay ON through calibration and all scan points
- LEDs turn OFF once at scan end

### Why Hardware PWM Still Flickered
The hardware PWM was working perfectly! The problem was **software** sending conflicting commands:
- Scan says: "Turn ON at 30%"
- Calibration says: "Turn ON at 30%" (redundant but harmless)
- Calibration says: "Turn OFF" (CONFLICT!)
- Scan implicitly needs: "Turn ON at 30%" (causes flicker!)

With V5.1 complete, calibration never touches LED state.

## Version History

- **V5.0**: Scan-level lighting (LEDs on once for scan, off once at end)
- **V5.1 Initial**: Removed independent focus turn_off_all() (partial fix)
- **V5.1 Complete**: Removed ALL calibration LED control (6 total changes) ← **THIS UPDATE**

## If Flickering STILL Persists After This

If you see flickering after V5.1 complete with only 2 LED transitions, the issue is hardware:

1. **Power Supply**: Use dedicated 5V supply for LED driver (not Pi's 5V rail)
2. **PWM Frequency**: Try different frequencies (100Hz, 1000Hz instead of 300Hz)
3. **Hardware Filter**: Add 10-100nF capacitor across LED driver PWM input
4. **LED Driver**: Check datasheet for PWM frequency requirements
5. **Wiring**: Ensure proper grounding, short PWM signal traces

---

**This is the COMPLETE V5.1 fix. All calibration LED control removed. Scan-level manages everything.**
