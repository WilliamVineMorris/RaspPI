# Focus Quality Investigation - Scan vs Dashboard

## Problem Report
**User observation:** "The 8 on the scanning page does not give the same quality as the dashboard 8 or does the autofocus not work"

## Current Status After Fix

### ✅ What's Working:
1. Manual focus is being set: `Set focus value 0.525 (lens position 485)`
2. Focus is being restored after camera reconfigurations: `Restored focus 0.525 (lens position 485)`
3. No calibration running (the fix is working as intended)
4. Scan completes successfully

### ❓ What We Need to Verify:
**CRITICAL QUESTION:** Is the lens ACTUALLY at position 485 during image capture, or is it reverting to something else?

The logs show focus being **set** to 485, but we don't know what the **actual** lens position is during capture.

## New Diagnostic Logging Added

I've added critical logging to show the **ACTUAL lens position** from the camera metadata:

### What You'll See Now:
```
🔍 ACTUAL LENS POSITION: 485 → Focus: 0.525 (8.1mm)  ✅ CORRECT
```

Or potentially:
```
🔍 ACTUAL LENS POSITION: 15 → Focus: 0.985 (9.9mm)   ❌ WRONG (default near focus)
```

This will definitively show whether the focus is staying at your setting or reverting.

## Possible Causes for Quality Difference

### 1. Focus Position Actually Different
**Symptom:** Manual focus sets to 485, but reverts to 15 during capture  
**Cause:** Camera mode switches (streaming → capture → streaming) may clear manual focus  
**Evidence:** Would show in new diagnostic log as `ACTUAL LENS POSITION: 15`

### 2. Exposure Settings Different
**Dashboard:** Uses current live settings (may adapt to scene)  
**Scan:** May use different exposure settings between dashboard and scan modes

### 3. LED Lighting Different
**Dashboard:** No LED control, uses ambient/manual lighting  
**Scan:** LEDs at 10% idle, 15% flash during capture  
May affect:
- Depth of field perception
- Exposure balance
- Color temperature

### 4. Camera Configuration Different
**Dashboard:** Live stream mode (1920x1080)  
**Scan:** Switches to capture mode (4624x3472), then back to stream  
Mode switches may affect:
- Focus persistence
- Image processing pipeline
- Sharpness enhancement

## Testing Plan

### Test 1: Verify Actual Lens Position ✅ (NEW LOGGING)
**Run a scan and check logs for:**
```
🔍 ACTUAL LENS POSITION: [value]
```

**Expected:** 485 (focus 8.1mm)  
**If you see:** 15 (focus 9.9mm) → Focus is being reset!

### Test 2: Compare EXIF Data
**Scan images will now include focus in description:**
```
Scan Point 000 at X:200.0 Y:50.0 Z:0.0° C:-33.7° | Focus: 8.1mm (lens 485)
```

**Dashboard images:** Check what focus value is saved

### Test 3: Visual Quality Comparison
Download both:
1. Dashboard capture at focus 8.1mm
2. Scan image from point 0 (should also be 8.1mm)

Compare:
- Sharpness at same focus distance
- Overall clarity
- Color/exposure

### Test 4: LED Lighting Test
Try scan with manual LED control:
- Dashboard: Set LEDs to 15% manually
- Capture image at focus 8.1mm
- Compare to dashboard capture with ambient light

## Hypotheses to Test

### Hypothesis 1: Focus Gets Reset During Mode Switch
**Test:** Check if `ACTUAL LENS POSITION` shows 15 instead of 485  
**Fix if true:** Force reapply focus right before capture (not just after reconfiguration)

### Hypothesis 2: No Focus Reset, But Different Camera Settings
**Test:** Check if `ACTUAL LENS POSITION` shows 485 correctly  
**Analysis:** If focus is correct but quality differs, investigate:
- Exposure differences
- Sharpness/denoise settings
- LED lighting effects

### Hypothesis 3: Capture Mode vs Stream Mode Quality
**Test:** Compare image metadata (exposure, gain, processing)  
**Analysis:** Check if capture mode has different ISP settings than stream mode

## Expected Fix Scenarios

### Scenario A: Lens Position Wrong (15 instead of 485)
**Problem:** Focus reset happening during mode switch  
**Fix:** Add additional focus reapplication right before capture:

```python
# Before capture
await camera.set_controls({
    "AfMode": 0,
    "LensPosition": 485
})
await asyncio.sleep(0.2)
# Then capture
```

### Scenario B: Lens Position Correct (485), Quality Still Different
**Problem:** Different camera settings or processing  
**Investigation needed:**
- Compare exposure time, gain, brightness
- Check LED lighting effect on depth perception
- Verify ISP processing settings match

### Scenario C: Everything Matches, User Preference
**Problem:** Perceived quality difference may be subjective  
**Analysis:** If all technical parameters match, quality may be equal but appear different due to:
- Different scene/object
- Different viewing conditions
- Confirmation bias

## Next Steps

1. **Run scan with new diagnostic logging**
2. **Check actual lens position in logs**
3. **Report findings:**
   - What lens position does log show?
   - Does image look sharp at expected distance?
   - How does it compare to dashboard image?

4. **Based on results:**
   - If lens = 15 → Need to add pre-capture focus reapplication
   - If lens = 485 but quality different → Need to compare exposure/settings
   - If lens = 485 and quality same → May be lighting/scene difference

## Current Code State

### What Was Changed:
**File:** `scanning/scan_orchestrator.py`  
**Added:** Diagnostic logging for actual lens position during capture

**New log line:**
```python
self.logger.info(f"🔍 ACTUAL LENS POSITION: {actual_lens_pos} → Focus: {focus_normalized:.3f} ({focus_mm:.1f}mm)")
```

**EXIF enhancement:**
- Focus value now saved in ImageDescription
- Easy to view in image properties

### What's Next:
Waiting for user testing with new diagnostic output to determine exact cause.
