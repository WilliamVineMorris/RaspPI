# LED PWM Update Trace - Debugging Guide

## How to Verify V5.1 Complete is Working

### Expected Log Pattern (SUCCESS):

```
00:10:17.569 - 💡 SCAN: Turning on LEDs for entire scan duration...
00:10:17.569 - 💡 LED UPDATE: Zone 'inner' 0.0% → 30.0% (state: ON)   ← TRANSITION #1 (ONLY ON)
00:10:17.569 - 💡 LED UPDATE: Zone 'outer' 0.0% → 30.0% (state: ON)
00:10:17.569 - 💡 SCAN: LEDs on at 30% - will remain on for all scan points

... motion to first point ...

💡 CALIBRATION: Using scan-level lighting (already on at 30%)  ← NO LED CONTROL
... or ...
💡 CALIBRATION: All cameras using scan-level lighting (already on at 30%)

... calibration happens ...

💡 CALIBRATION: Primary camera completed (scan-level lighting remains active)  ← NO LED CONTROL
💡 CALIBRATION: Secondary cameras completed (scan-level lighting remains active)  ← NO LED CONTROL

⏱️ V5.1: Waiting 50ms for camera settling (LEDs remain on at 30%)...

📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← Point 0
✅ V5: Camera capture successful

... (NO LED TRANSITIONS HERE) ...

📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← Point 7
✅ V5: Camera capture successful

💡 SCAN: Turning off LEDs after complete scan...
💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)  ← TRANSITION #2 (ONLY OFF)
💡 LED UPDATE: Zone 'outer' 30.0% → 0.0% (state: OFF)
```

**LED TRANSITION COUNT**: 2 (4 total log lines: inner/outer ON, inner/outer OFF)

---

### Failed V5.1 Pattern (PROBLEM - Old Code Still Running):

If you see ANY of these, V5.1 is NOT loaded:

```
❌ 💡 CALIBRATION: Enabled 30% flash for calibration process
❌ 💡 CALIBRATION: Enabled 30% flash for secondary camera calibrations  
❌ 💡 CALIBRATION: Disabled flash after calibration
❌ 💡 CALIBRATION: Disabled flash after all secondary camera calibrations
❌ 💡 LED UPDATE between calibration and scan start
```

**Action Required**: Python is still running old code. Restart scanner:
```bash
sudo pkill -9 -f run_web_interface
cd ~/RaspPI/V2.0
python3 run_web_interface.py
```

---

## PWM Update Chain Analysis

### LED Controller (`lighting/gpio_led_controller.py`)

**Entry Points** (all lead to same PWM update):
1. `set_brightness(zone_id, brightness)` → `_set_brightness_direct()`
2. `turn_off_all()` → calls `_turn_off_direct()` for each zone → `_set_brightness_direct()`
3. `flash_zone()` → calls `set_brightness()` → `_set_brightness_direct()`

**Single PWM Update Path** (`_set_brightness_direct()`):
```python
Line 926: def _set_brightness_direct(self, zone_id: str, brightness: float) -> bool:
    # PROTECTION LAYER 1: 1% threshold
    Line 944: if abs(current_brightness - brightness) < 0.01:
        return True  # NO UPDATE - difference too small
    
    # PROTECTION LAYER 2: State tracking
    Line 949-953: if is_on == was_on and abs(current_brightness - brightness) < 0.02:
        return True  # NO UPDATE - already in correct state
    
    # PROTECTION LAYER 3: Thread lock (prevents concurrent updates)
    Line 956: with self._led_update_lock:
        # ACTUAL PWM UPDATE HAPPENS HERE (lines 961-969)
        Line 961-965: for pwm_obj in self.pwm_controllers[zone_id]:
            if pwm_obj['type'] == 'gpiozero':
                led.value = brightness  # ← HARDWARE PWM UPDATE
```

**Key Insight**: The controller has perfect protection. The problem was **callers** sending conflicting commands (ON, OFF, ON).

---

### Scan Orchestrator LED Call Points (COMPLETE LIST)

#### ✅ SCAN-LEVEL CONTROL (Correct - Keep These):

**Line 3668**: `await self.lighting_controller.set_brightness("all", 0.3)`
- Location: `_execute_scan_points()` start
- Purpose: Turn LEDs ON for entire scan
- Status: ✅ CORRECT - This is the ONLY LED ON call

**Line 3728**: `await self.lighting_controller.turn_off_all()`
- Location: `_execute_scan_points()` finally block
- Purpose: Turn LEDs OFF after entire scan
- Status: ✅ CORRECT - This is the ONLY LED OFF call

#### ❌ CALIBRATION CONTROL (Incorrect - REMOVED):

**~~Line 3476~~**: ~~`await self.lighting_controller.set_brightness("all", 0.3)`~~
- Location: Synchronized focus primary calibration
- Status: ✅ REMOVED in V5.1 complete

**~~Line 3486~~**: ~~`await self.lighting_controller.turn_off_all()`~~
- Location: Synchronized focus primary finally block
- Status: ✅ REMOVED in V5.1 complete

**~~Line 3535~~**: ~~`await self.lighting_controller.set_brightness("all", 0.3)`~~
- Location: Synchronized focus secondary calibrations
- Status: ✅ REMOVED in V5.1 complete

**~~Line 3561~~**: ~~`await self.lighting_controller.turn_off_all()`~~
- Location: Synchronized focus secondary finally block
- Status: ✅ REMOVED in V5.1 complete

**~~Line 3578~~**: ~~`await self.lighting_controller.set_brightness("all", 0.3)`~~
- Location: Independent focus all cameras
- Status: ✅ REMOVED in V5.1 complete

**~~Line 3638~~**: ~~`await self.lighting_controller.turn_off_all()`~~
- Location: Independent focus finally block
- Status: ✅ REMOVED in V5.1 initial (first fix)

---

## Debugging Steps

### Step 1: Count LED Transitions
```bash
tail -f logs/scanner.log | grep "💡 LED UPDATE"
```

**Expected Output** (for 8-point scan):
```
💡 LED UPDATE: Zone 'inner' 0.0% → 30.0% (state: ON)
💡 LED UPDATE: Zone 'outer' 0.0% → 30.0% (state: ON)
... (NO OTHER LED UPDATES) ...
💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)
💡 LED UPDATE: Zone 'outer' 30.0% → 0.0% (state: OFF)
```

**Total Lines**: 4 (2 ON, 2 OFF)

If you see MORE than 4 lines, V5.1 is not fully loaded or there's another LED call point.

### Step 2: Check Calibration Messages
```bash
tail -f logs/scanner.log | grep "CALIBRATION.*flash"
```

**Expected Output** (V5.1 complete):
```
💡 CALIBRATION: Using scan-level lighting (already on at 30%)
💡 CALIBRATION: Primary camera completed (scan-level lighting remains active)
💡 CALIBRATION: Secondary cameras completed (scan-level lighting remains active)
```

**MUST NOT contain**:
- "Enabled 30% flash"
- "Disabled flash"

### Step 3: Verify Python Process Restart
```bash
ps aux | grep run_web_interface
```

Check the start time - it should be AFTER you made the code changes.

### Step 4: Confirm Code Changes Loaded
```bash
cd ~/RaspPI/V2.0
grep -n "V5.1: DO NOT turn" scanning/scan_orchestrator.py | head -5
```

**Expected Output** (should show multiple matches):
```
3473:    # 🔥 V5.1: DO NOT turn LEDs on - scan-level lighting already has them on at 30%
3479:        # 🔥 V5.1: DO NOT turn off LEDs - scan-level lighting manages state
3523:        # 🔥 V5.1: DO NOT turn LEDs on - scan-level lighting already has them on at 30%
3547:            # 🔥 V5.1: DO NOT turn off LEDs - scan-level lighting manages state
3560:    # 🔥 V5.1: DO NOT turn LEDs on - scan-level lighting already has them on at 30%
```

---

## Hardware PWM Verification

The raw PWM test works perfectly, proving hardware is good. If flickering persists with V5.1 complete:

### Check 1: LED Driver Frequency Response
Some LED drivers don't respond well to certain PWM frequencies:
```python
# In gpio_led_controller.py line 193:
self.pwm_frequency = 300  # Try: 100, 500, 1000
```

### Check 2: Power Supply Stability
- LEDs should have dedicated 5V supply (not Pi's 5V rail)
- Check voltage under load (should be 4.8-5.2V)
- Add bulk capacitor (100-1000µF) if voltage drops

### Check 3: PWM Signal Integrity
- Keep PWM signal wires SHORT (<10cm)
- Use shielded cable if longer
- Add 100nF capacitor at LED driver PWM input

### Check 4: Ground Loops
- Ensure Pi GND and LED driver GND are connected
- Single ground point (star grounding)

---

## Summary

**V5.1 Complete removes ALL LED control from calibration code.**

**Total changes**: 6 LED control points removed (3 ON calls, 3 OFF calls)

**Result**: Only scan-level code controls LEDs. Calibration is completely passive.

**Success indicator**: Exactly 4 "💡 LED UPDATE" log lines per scan (2 zones × 2 transitions)
