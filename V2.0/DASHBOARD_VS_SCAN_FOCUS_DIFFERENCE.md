# Dashboard vs Scan Focus: Why One Works and One Doesn't

## Summary
**Dashboard manual focus works perfectly**, but **scan manual focus fails** because they use **completely different code paths**.

---

## Dashboard Manual Focus (WORKS ✅)

### Path:
1. User adjusts focus slider on dashboard
2. Frontend calls `/api/camera/focus` 
3. Backend calls `camera_manager.set_manual_focus()`
4. This calls orchestrator's `set_manual_focus()` (line 1981)
5. Which calls camera controller's `set_focus_value()` (line 803)

### What `set_focus_value()` does:
```python
async def set_focus_value(self, camera_id: str, focus_value: float) -> bool:
    # Simple, direct approach
    picamera2.set_controls({
        "AfMode": 0,  # Manual focus
        "LensPosition": lens_position
    })
    
    # Store for later
    self._stored_focus_values[camera_id] = focus_value
    
    # Wait for lens to move
    await asyncio.sleep(0.2)
    return True
```

**Result:** Camera immediately sets lens to position, works perfectly! ✅

---

## Scan Manual Focus (FAILS ❌)

### Path:
1. User sets manual focus in scan UI
2. Scan starts, orchestrator calls `_setup_focus_at_first_scan_point()` (line 3490)
3. This calls `camera_manager.controller.set_focus_value()` ✅ (SAME as dashboard!)
4. **BUT THEN** calls `auto_calibrate_camera()` with `skip_autofocus=True` ❌
5. Calibration code **fights** the manual focus setting

### What `auto_calibrate_camera()` does in manual mode:

```python
async def auto_calibrate_camera(camera_id, skip_autofocus=True):
    # Step 1: Enable auto-exposure (AE)
    control_dict = {
        "AeEnable": True,
        "AwbEnable": True,
        # ... other exposure controls
    }
    
    # ATTEMPT 1: Add manual focus to control_dict atomically
    if skip_autofocus and stored_focus exists:
        control_dict["AfMode"] = 0
        control_dict["LensPosition"] = 485  # For 8.1mm focus
        logger.info("Adding manual focus to control_dict")
    
    picamera2.set_controls(control_dict)  # Set everything together
    await asyncio.sleep(0.3)
    
    # Step 2: Let auto-exposure settle
    await asyncio.sleep(1.0)
    for i in range(3):
        metadata = picamera2.capture_metadata()  # PROBLEM: This may reset focus!
        await asyncio.sleep(0.3)
    
    # ATTEMPT 2: Reapply manual focus after AE settling
    if skip_autofocus:
        picamera2.set_controls({
            "AfMode": 0,
            "LensPosition": 485
        })
        logger.info("REAPPLIED manual focus AFTER AE settling")
        await asyncio.sleep(0.2)
    
    # ATTEMPT 3: Reapply manual focus BEFORE final metadata
    if skip_autofocus:
        picamera2.set_controls({
            "AfMode": 0,
            "LensPosition": 485
        })
        logger.info("REAPPLIED manual focus BEFORE final metadata")
        await asyncio.sleep(0.5)  # Longer wait for lens motor
        
        # Verify lens moved
        verification = picamera2.capture_metadata()
        actual_pos = verification.get('LensPosition', None)
        if abs(actual_pos - 485) > 50:  # PROBLEM DETECTED HERE!
            logger.warning("Lens position mismatch! Reapplying again...")
            picamera2.set_controls({
                "AfMode": 0,
                "LensPosition": 485
            })
            await asyncio.sleep(0.5)
    
    # Final metadata capture
    final_metadata = picamera2.capture_metadata()
    
    # Read back focus value
    lens_position_raw = final_metadata.get('LensPosition', None)  # Returns 15.0 ❌
    focus_value = 1.0 - (lens_position_raw / 1023.0)  # Converts to 0.985 ❌
```

### The Problem:

**THREE attempts to set `LensPosition=485`, but camera firmware keeps resetting it to `15`!**

Your logs show:
```
2025-10-07 21:44:21,429 - camera.pi_camera_controller - INFO - Adding manual focus: LensPosition=485
2025-10-07 21:44:23,633 - camera.pi_camera_controller - INFO - REAPPLIED manual focus (lens 485) AFTER AE settling
2025-10-07 21:44:23,834 - camera.pi_camera_controller - INFO - REAPPLIED manual focus (lens 485) BEFORE final metadata
2025-10-07 21:44:24,336 - camera.pi_camera_controller - WARNING - Lens position mismatch! Reapplying again...
2025-10-07 21:44:24,837 - camera.pi_camera_controller - INFO - Read from metadata: 0.985 (lens: 15.0) ❌
```

---

## Root Cause Analysis

### Why Dashboard Works But Scan Doesn't:

| Feature | Dashboard | Scan Calibration |
|---------|-----------|------------------|
| **Sets manual focus** | ✅ Yes | ✅ Yes |
| **Enables auto-exposure** | ❌ No | ✅ Yes |
| **Calls capture_metadata()** | ❌ No | ✅ Yes (multiple times) |
| **Verification loops** | ❌ No | ✅ Yes |
| **Camera mode switches** | ❌ No | ✅ Yes (streaming→capture) |

### The ArduCam Firmware Bug:

When `AeEnable=True` is active and you call `capture_metadata()`:
1. Camera firmware briefly enters "metering mode" to measure scene
2. This **temporarily enables autofocus** to get accurate exposure reading
3. Autofocus moves lens to position `15` (very near focus)
4. Your `LensPosition=485` command gets **overridden**

### Why Multiple Reapplications Don't Help:

The code pattern is:
```python
set_controls({"LensPosition": 485})
await asyncio.sleep(0.5)
metadata = capture_metadata()  # ← THIS resets lens to 15!
actual_pos = metadata.get('LensPosition')  # Reads 15 ❌
```

The `capture_metadata()` **itself** triggers the reset, so verification always fails!

---

## Solution Options

### Option 1: Disable Auto-Exposure During Manual Focus (SIMPLE) ✅

**Dashboard approach:** Don't calibrate exposure, just set focus and use it.

```python
# In scan calibration, for manual focus mode:
if self._web_focus_mode == 'manual':
    # Set manual focus
    await camera.set_focus_value(camera_id, normalized_focus)
    
    # DON'T call auto_calibrate_camera()!
    # Just use camera's current auto-exposure settings
    # Scan will work with AE enabled at capture time
```

**Pros:**
- Simple fix
- Matches dashboard behavior
- Manual focus will definitely work

**Cons:**
- No pre-calibrated exposure (but auto-exposure still works during scan)

### Option 2: Lock Exposure BEFORE Setting Manual Focus ✅

**Pre-calibrate exposure with autofocus, then switch to manual:**

```python
# Step 1: Auto-calibrate exposure (with autofocus)
calibration = await auto_calibrate_camera(camera_id, skip_autofocus=False)
exposure_time = calibration['exposure_time']
gain = calibration['analogue_gain']

# Step 2: Lock those exposure values
camera.set_controls({
    "AeEnable": False,  # Disable auto-exposure
    "ExposureTime": exposure_time,
    "AnalogueGain": gain
})

# Step 3: NOW set manual focus (AE is off, won't interfere)
await camera.set_focus_value(camera_id, normalized_focus)

# Step 4: Verify it worked
metadata = camera.capture_metadata()
# Should read 485 because AE is disabled ✅
```

**Pros:**
- Best of both worlds
- Pre-calibrated exposure + manual focus
- No firmware interference

**Cons:**
- More complex
- Exposure won't adapt during scan (fixed values)

### Option 3: Use Dashboard's Simple Approach ✅

**Simplest: Just call `set_focus_value()` and skip calibration entirely:**

```python
if self._web_focus_mode == 'manual':
    for camera_id in available_cameras:
        # ONLY set focus, don't calibrate anything
        await self.camera_manager.controller.set_focus_value(camera_id, focus_normalized)
        
        # Store for later
        self._scan_focus_values[camera_id] = self._web_focus_position
        
    # Done! Let camera use its own auto-exposure during scan
```

**Pros:**
- Identical to working dashboard code
- Guaranteed to work
- Simple and clean

**Cons:**
- No exposure pre-calibration (but may not need it)

---

## Recommended Test

**Test Option 3 first** (simplest, matches dashboard exactly):

1. Comment out the `auto_calibrate_camera()` call in manual focus mode
2. Just use `set_focus_value()` like the dashboard does
3. Let the scan use camera's auto-exposure naturally

If that works perfectly (like dashboard), we're done!

If you need pre-calibrated exposure, then implement Option 2.

---

## What To Test On Pi

### Test 1: Verify Dashboard Focus Position
1. Open dashboard
2. Set manual focus to 8.1mm
3. Check browser console for lens position
4. **Expected:** Lens moves to ~485

### Test 2: Verify Scan Uses Same Camera
1. Start scan with manual focus 8.1mm
2. Check if same camera instance
3. **Expected:** Should use same camera object

### Test 3: Quick Fix Test
Temporarily edit `scan_orchestrator.py` line ~3520:

```python
# BEFORE (current code):
calibration_result = await self.camera_manager.controller.auto_calibrate_camera(
    camera_id,
    skip_autofocus=True  # This is causing the problem!
)

# AFTER (test fix):
# Skip calibration entirely, just use the focus we already set!
# calibration_result = await ...
# Instead, do nothing! Let camera use auto-exposure during scan.
```

Run scan and check if focus stays at 8.1mm (lens ~485).

---

## Key Insight

**The dashboard works because it's SIMPLE:**
- Set focus
- Done

**The scan fails because it's COMPLEX:**
- Set focus
- Enable auto-exposure
- Capture metadata (resets focus!)
- Reapply focus
- Capture metadata again (resets focus again!)
- Reapply focus a third time
- Still reads wrong value

**Solution: Be more like the dashboard! 😄**
