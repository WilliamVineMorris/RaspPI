# LED Flickering Fix - Quick Reference

## What Was Fixed (V5.1)

**Problem**: LEDs turned OFF after calibration, causing flicker when scan started  
**Root Cause**: Calibration code's `finally` block called `turn_off_all()`, conflicting with scan-level LED control  
**Solution**: Removed `turn_off_all()` from calibration - scan-level code manages LED state  

## Expected LED Behavior (After V5.1)

### For 8-Point Cylindrical Scan:
1. **Scan Start**: LEDs turn ON at 30% → stays on
2. **Calibration**: LEDs remain ON (no off/on cycle)
3. **Point 0-7**: LEDs stay ON throughout all captures
4. **Scan End**: LEDs turn OFF once

**Total LED transitions**: 2 (ON once, OFF once)

## What You Should See in Logs

✅ **Good** (V5.1):
```
💡 SCAN: LEDs on at 30% - will remain on for all scan points
💡 CALIBRATION: Completed (scan-level lighting remains active)
📸 V5: Capturing with scan-level lighting (LEDs already on)...
📸 V5: Capturing with scan-level lighting (LEDs already on)...
... (repeat for all points) ...
💡 SCAN: LEDs turned off after complete scan
```

❌ **Bad** (would indicate V5.1 not loaded):
```
💡 SCAN: LEDs on at 30%
💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)  ← Should NOT appear
💡 CALIBRATION: Disabled flash after all camera calibrations  ← Old message
```

## To Test V5.1

### 1. Restart Scanner
```bash
sudo pkill -f run_web_interface
cd ~/RaspPI/V2.0
python3 run_web_interface.py
```

### 2. Monitor Logs
```bash
tail -f logs/scanner.log | grep -E "💡|📸"
```

### 3. Run Scan
- Start a multi-point scan (cylindrical pattern)
- Watch for LED transitions in logs
- Expected: Only 2 transitions total

## LED Controller Protections (Already Active)

The LED controller has triple protection against redundant updates:

1. **1% Threshold**: Ignores brightness changes < 1%
2. **State Tracking**: Blocks redundant on/off commands
3. **Thread Lock**: Prevents concurrent PWM updates

These were already working in V5.0 - V5.1 just ensures the scan orchestrator doesn't request conflicting states.

## If Flickering Persists

If you still see flickering after V5.1 with only 2 LED transitions:

1. **Check power supply**: Dedicated 5V supply for LED driver?
2. **Try different PWM frequency**: 1000Hz or 100Hz instead of 300Hz
3. **Hardware capacitor**: 10-100nF across LED driver PWM input
4. **LED driver specs**: Check datasheet for PWM frequency requirements

## Files Changed

- `scanning/scan_orchestrator.py` (lines 3638-3640, 3668)

## Documentation

Full details in: `LED_FLICKERING_V5.1_CALIBRATION_CONFLICT.md`
