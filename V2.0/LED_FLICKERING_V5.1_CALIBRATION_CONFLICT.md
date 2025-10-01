# LED Flickering V5.1 Fix - Calibration Conflict Resolution

**Date**: October 2, 2025  
**Status**: ✅ IMPLEMENTED  
**Version**: V5.1 (hotfix on top of V5.0)

## Executive Summary

**ROOT CAUSE DISCOVERED**: The calibration code had a `finally` block that turned LEDs OFF after camera calibration completed. This conflicted with the V5 scan-level lighting which had already turned LEDs ON for the entire scan duration.

**RESULT**: LEDs turned OFF after calibration, then back ON when scan started → **visible flicker between calibration and first scan point**.

## User Log Evidence

```
2025-10-02 00:00:16,536 - 💡 SCAN: LEDs on at 30% - will remain on for all scan points  ← V5: LEDs ON
... (calibration happens for ~11 seconds) ...
2025-10-02 00:00:27,855 - 💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)  ← CONFLICT!
2025-10-02 00:00:27,855 - 💡 CALIBRATION: Disabled flash after all camera calibrations
2025-10-02 00:00:27,856 - ⏱️ Waiting 50ms for LED settling after calibration...
2025-10-02 00:00:27,906 - 📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← But LEDs are OFF!
```

**Analysis**: 
- Line 1: V5 code turns LEDs on at 30% for entire scan
- Line 3: Calibration finally block turns LEDs OFF (conflict!)
- Line 6: V5 capture assumes LEDs are on, but they're actually OFF
- Result: LEDs had to turn back ON, causing flicker

## The V5.1 Fix

### File: `scanning/scan_orchestrator.py`

**Lines 3638-3642** (old code - REMOVED):
```python
finally:
    # 🔥 FIX: Turn off flash ONCE after all camera calibrations (prevents flickering)
    try:
        await self.lighting_controller.turn_off_all()
        self.logger.info(f"💡 CALIBRATION: Disabled flash after all camera calibrations")
    except Exception as flash_off_error:
        self.logger.warning(f"⚠️ CALIBRATION: Could not disable flash: {flash_off_error}")
```

**Lines 3638-3640** (new code - FIXED):
```python
finally:
    # 🔥 V5.1: DO NOT turn off LEDs here - scan-level lighting manages LED state
    # The scan has already turned LEDs on and will turn them off at the end
    self.logger.info(f"💡 CALIBRATION: Completed (scan-level lighting remains active)")
```

**Key Change**: Removed the `turn_off_all()` call that was conflicting with scan-level LED management.

### Updated Settling Delay Comment

**Line 3668** (old comment):
```python
# 🔥 FIX: Add settling delay after calibration LEDs turn off (prevents flicker when scan LEDs turn on)
self.logger.info("⏱️ Waiting 50ms for LED settling after calibration...")
await asyncio.sleep(0.05)  # 50ms delay to prevent rapid OFF→ON flicker
```

**Line 3668** (new comment):
```python
# 🔥 V5.1: Add settling delay after calibration to stabilize camera settings
self.logger.info("⏱️ Waiting 50ms for camera settling after calibration...")
await asyncio.sleep(0.05)  # 50ms delay for camera exposure/focus to stabilize
```

**Key Change**: Updated comment to reflect true purpose (camera stabilization, not LED settling).

## V5.1 LED Control Flow (CORRECTED)

### 1. Scan Start
```python
# scan_orchestrator.py line 3686-3696
await self.lighting_controller.set_brightness("all", 0.3)  # ON ONCE
self.logger.info("💡 SCAN: LEDs on at 30% - will remain on for all scan points")
await asyncio.sleep(0.05)  # 50ms settling
```

### 2. Camera Calibration (FIXED)
```python
# scan_orchestrator.py line 3638-3640
finally:
    # V5.1: NO LED CONTROL HERE - scan-level manages state
    self.logger.info("💡 CALIBRATION: Completed (scan-level lighting remains active)")
```

### 3. Scan Points (No Change)
```python
# scan_orchestrator.py line 3894-3901
self.logger.info("📸 V5: Capturing with scan-level lighting (LEDs already on)...")
result = await self.camera_manager.capture_both_cameras_simultaneously(...)
self.logger.info("✅ V5: Camera capture successful with scan-level lighting")
```

### 4. Scan End (No Change)
```python
# scan_orchestrator.py line 3730-3737
finally:
    try:
        await self.lighting_controller.turn_off_all()  # OFF ONCE
        self.logger.info("💡 SCAN: LEDs turned off after complete scan")
    except Exception as e:
        self.logger.error(f"Failed to turn off LEDs after scan: {e}")
```

## Expected Behavior After V5.1

### LED Transitions Per 8-Point Scan
- **Before V5**: 16+ transitions (on/off for each point)
- **After V5**: 4 transitions (on for calibration, off, on for scan, off)
- **After V5.1**: 2 transitions (on once, off once) ✅ OPTIMAL

### Log Output (Expected)
```
💡 SCAN: LEDs on at 30% - will remain on for all scan points  ← ON ONCE
... calibration logs ...
💡 CALIBRATION: Completed (scan-level lighting remains active)  ← NO LED OFF
⏱️ Waiting 50ms for camera settling after calibration...
📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← Point 0
✅ V5: Camera capture successful with scan-level lighting
... (no LED updates between points) ...
📸 V5: Capturing with scan-level lighting (LEDs already on)...  ← Point 7
✅ V5: Camera capture successful with scan-level lighting
💡 SCAN: LEDs turned off after complete scan  ← OFF ONCE
```

### What Should NOT Appear
❌ `💡 LED UPDATE: Zone 'inner' 30.0% → 0.0%` between calibration and scan  
❌ `💡 CALIBRATION: Disabled flash after all camera calibrations`  
❌ Any LED state changes between scan points  

## LED Controller Robustness (Already Implemented)

The LED controller (`lighting/gpio_led_controller.py`) already has triple protection against redundant PWM updates:

### 1. 1% Brightness Threshold (Line 944-946)
```python
if abs(current_brightness - brightness) < 0.01:  # 1% tolerance
    return True  # No update needed
```

### 2. State Tracking (Line 949-953)
```python
is_on = brightness > 0.01
was_on = self._led_active.get(zone_id, False)
if is_on == was_on and abs(current_brightness - brightness) < 0.02:  # 2% for state transitions
    logger.debug(f"Zone '{zone_id}' already in state (on={is_on}), skipping update")
    return True
```

### 3. Thread Lock (Line 956)
```python
with self._led_update_lock:
    # All PWM updates happen here - prevents concurrent writes
```

### 4. Selective Logging (Line 978-979)
```python
if abs(current_brightness - brightness) > 0.05:  # Log 5%+ changes
    logger.info(f"💡 LED UPDATE: Zone '{zone_id}' {current_brightness*100:.1f}% → {brightness*100:.1f}%")
```

**Result**: The LED controller ALREADY prevents redundant PWM updates. The V5.1 fix ensures the scan orchestrator doesn't request conflicting LED states.

## Testing Protocol

### 1. Restart Scanner
```bash
sudo pkill -f run_web_interface
cd ~/RaspPI/V2.0
python3 run_web_interface.py
```

### 2. Monitor Logs
```bash
tail -f logs/scanner.log | grep -E "💡|📸|CALIBRATION"
```

### 3. Run Multi-Point Scan
- Use cylindrical pattern (8 points)
- Watch for LED state transitions
- Expected: Only 2 transitions per scan

### 4. Success Criteria
✅ Logs show: `💡 CALIBRATION: Completed (scan-level lighting remains active)`  
✅ NO "💡 LED UPDATE: Zone 'inner' 30.0% → 0.0%" between calibration and scan  
✅ Only 2 LED transitions total: ON at scan start, OFF at scan end  
✅ No visible flickering throughout entire scan workflow  

## Files Modified

1. **scanning/scan_orchestrator.py**:
   - Line 3638-3640: Removed `turn_off_all()` from calibration finally block
   - Line 3668: Updated settling delay comment

## Implementation Status

- ✅ Code changes applied
- ⏳ User testing pending (requires scanner restart)

## Version History

- **V5.0**: Scan-level lighting (LEDs on once for scan, off once at end)
- **V5.1**: Removed calibration LED OFF conflict (this document)

## Next Steps

1. User restarts scanner to load V5.1 code
2. User runs multi-point scan and monitors logs
3. Verify only 2 LED transitions per scan
4. Confirm no visible flickering

---

**Note**: If flickering persists after V5.1, the issue is likely hardware-related (power supply, LED driver frequency, electrical noise) rather than software PWM updates.
