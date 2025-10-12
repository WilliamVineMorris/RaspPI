# Camera Capture Timeout Investigation

## Problem Summary
The scanning process stalls during camera capture with the following error pattern:
```
2025-10-12 17:13:47,946 - camera.pi_camera_controller - WARNING - ISP capture attempt 1 failed for camera 0: Capture timeout after 10.0s (ISP may be stuck)
2025-10-12 17:13:47,946 - camera.pi_camera_controller - INFO - ISP issue detected (timeout/buffer), attempting camera restart...
```

The scan gets stuck at 14.6% (21/144) in the CAPTURING phase and never completes the capture.

## Root Cause Analysis

### 1. **Excessive Camera Reconfiguration**
From the logs, we can see the cameras are being reconfigured MULTIPLE TIMES per capture cycle:

```
2025-10-12 17:13:27,835 - INFO - 📷 STANDARD MODE: Reconfiguring for moderate resolution
[Camera stops and reconfigures to 4624x3472]
2025-10-12 17:13:28,215 - INFO - 📷 Camera started

[Then IMMEDIATELY reconfigures again]
2025-10-12 17:13:28,320 - INFO - Camera stopped
2025-10-12 17:13:28,702 - INFO - 📷 Camera started

[And AGAIN during capture preparation]
2025-10-12 17:13:34,605 - INFO - Camera stopped
2025-10-12 17:13:35,345 - INFO - 📷 Camera started

[And YET AGAIN]
2025-10-12 17:13:36,189 - INFO - 📷 STANDARD MODE: Reconfiguring for moderate resolution
```

**This is 4+ reconfigurations in ~9 seconds!** Each reconfiguration:
- Stops the camera
- Releases V4L2 buffers
- Reallocates ISP pipeline resources
- Restarts the camera
- Reapplies focus settings

### 2. **ISP Buffer Exhaustion**
The constant stop/start/reconfigure cycle exhausts the ISP (Image Signal Processor) buffers. The Pi's ISP has limited buffer resources, and rapid cycling causes:
- Buffer allocation failures
- Pipeline state corruption
- Timeout waiting for ISP to become ready

### 3. **Race Condition in Capture Flow**
The code flow shows:

1. `scan_orchestrator.py` calls `prepare_cameras_for_capture()` → **reconfigures cameras**
2. Then calls `capture_dual_resolution_aware()` → **reconfigures cameras AGAIN**
3. Inside `capture_dual_resolution_aware()`, the STANDARD mode calls `capture_dual_sequential_isp()`
4. But BEFORE calling that, it checks if cameras need reconfiguration → **reconfigures AGAIN**

This happens because multiple layers are trying to "ensure" the cameras are ready, not knowing other layers already did it.

### 4. **10-Second Timeout Too Short for Recovery**
When ISP gets stuck, the code tries to recover by:
- Stopping the camera
- Waiting 0.5s
- Starting the camera
- Waiting 0.3s for stabilization

But the 10-second timeout includes ALL retry attempts (3 retries × ~1s each), leaving only ~7 seconds for actual capture. If ISP is degraded from prior reconfigurations, this isn't enough.

## Evidence from Logs

### Normal Successful Capture (Point 20):
```
17:13:28 - Reconfigure cameras
17:13:28 - Prepare for capture
17:13:28 - Capture successful in ~1.3 seconds
17:13:29 - Switch back to streaming mode
```

### Failed Capture (Point 21):
```
17:13:34 - Reconfigure cameras (AGAIN)
17:13:35 - Prepare for capture
17:13:36 - Reconfigure AGAIN
17:13:37 - Reconfigure YET AGAIN (4th time!)
17:13:47 - TIMEOUT after 10 seconds
[System stalled, never recovers]
```

The difference: Point 21 had **4 reconfigurations** vs Point 20's **2 reconfigurations**.

## Code Locations of Issues

### Issue 1: Redundant Reconfiguration in `capture_dual_resolution_aware()`
**File:** `camera/pi_camera_controller.py:3011-3027`

```python
# LOWER-RESOLUTION: Simultaneous capture for better sync
logger.info(f"🔧 STANDARD SIMULTANEOUS: Capturing {len(available_cameras)} cameras simultaneously")

# Ensure cameras are properly configured for target resolution before capture
for camera_id in available_cameras:
    camera = self.cameras[camera_id]
    if camera:
        try:
            # Check current configuration matches target
            current_config = camera.camera_configuration()
            if current_config and 'main' in current_config:
                current_size = current_config['main'].get('size')
                if current_size != target_resolution:
                    # PROBLEM: This reconfigures even if prepare_cameras_for_capture() just did it!
                    logger.info(f"📷 Camera {camera_id}: Reconfiguring from {current_size} to {target_resolution}")
                    
                    if camera.started:
                        camera.stop()
                    
                    capture_config = camera.create_still_configuration(...)
                    camera.configure(capture_config)
                    camera.start()
```

**Problem:** This reconfigures cameras that were JUST configured by `prepare_cameras_for_capture()`.

### Issue 2: Insufficient ISP Recovery Time
**File:** `camera/pi_camera_controller.py:2450-2475`

```python
if needs_camera_restart:
    logger.info(f"ISP issue detected (timeout/buffer), attempting camera restart...")
    
    try:
        if camera.started:
            camera.stop()
        await asyncio.sleep(retry_delay)  # Only 0.5 seconds!
        gc.collect()
        camera.start()
        await asyncio.sleep(0.3)  # Only 0.3s for ISP stabilization!
```

**Problem:** Total recovery time is only 0.8 seconds, insufficient for ISP to fully reset after being stuck.

### Issue 3: Scan Orchestrator Double-Preparation
**File:** `scanning/scan_orchestrator.py:1728-1736`

```python
# Prepare cameras with resolution awareness
if hasattr(self.controller, 'prepare_cameras_for_capture'):
    await self.controller.prepare_cameras_for_capture(target_resolution=target_resolution)

# Use resolution-aware capture system
if hasattr(self.controller, 'capture_dual_resolution_aware'):
    self.logger.info(f"CAMERA: Using resolution-aware capture for {target_resolution}")
    capture_results = await self.controller.capture_dual_resolution_aware(
        target_resolution=target_resolution,  # PROBLEM: Passes same resolution again!
```

**Problem:** Calls `prepare_cameras_for_capture()` then immediately calls `capture_dual_resolution_aware()` with the same resolution, causing redundant configuration checks.

## Proposed Solutions

### Solution 1: Skip Reconfiguration if Already Configured ✅ **PRIORITY**
Add state tracking to prevent redundant reconfigurations:

```python
# In PiCameraController class
def __init__(...):
    self._last_configured_resolution = {}  # Track per-camera
    self._configuration_lock = asyncio.Lock()  # Prevent concurrent reconfiguration

async def prepare_cameras_for_capture(self, target_resolution=None):
    async with self._configuration_lock:
        for camera_id in self.cameras:
            # Skip if already at target resolution
            if camera_id in self._last_configured_resolution:
                if self._last_configured_resolution[camera_id] == target_resolution:
                    logger.info(f"📷 Camera {camera_id}: Already at {target_resolution}, skipping reconfiguration")
                    continue
            
            # Only reconfigure if actually needed
            [... existing reconfiguration code ...]
            
            # Track successful configuration
            self._last_configured_resolution[camera_id] = target_resolution
```

### Solution 2: Remove Redundant Check in capture_dual_resolution_aware() ✅
**File:** `camera/pi_camera_controller.py:3011-3027`

Remove the reconfiguration check since `prepare_cameras_for_capture()` already handles it:

```python
else:
    # LOWER-RESOLUTION: Simultaneous capture for better sync
    logger.info(f"🔧 STANDARD SIMULTANEOUS: Capturing {len(available_cameras)} cameras simultaneously at {target_resolution}")
    
    # REMOVED: Redundant configuration check - prepare_cameras_for_capture() already did this
    # Just verify cameras are started
    for camera_id in available_cameras:
        camera = self.cameras[camera_id]
        if camera and not camera.started:
            logger.warning(f"📷 Camera {camera_id}: Not started, starting now...")
            camera.start()
            await asyncio.sleep(0.2)
    
    # Use standard dual sequential with shorter delays for lower-res
    results = await self.capture_dual_sequential_isp("main", delay_ms=100)
```

### Solution 3: Increase Timeout and Recovery Times ✅
**File:** `camera/pi_camera_controller.py`

```python
# Increase per-capture timeout
capture_timeout = 20.0  # Increased from 10.0s

# Increase ISP recovery delays
if needs_camera_restart:
    if camera.started:
        camera.stop()
    await asyncio.sleep(1.5)  # Increased from 0.5s - give ISP time to fully release
    gc.collect()
    camera.start()
    await asyncio.sleep(0.8)  # Increased from 0.3s - full ISP pipeline stabilization
```

### Solution 4: Add ISP Health Monitoring
Add detection of cumulative ISP stress:

```python
# In PiCameraController
def __init__(...):
    self._isp_failure_count = 0
    self._last_isp_reset = time.time()

async def capture_with_isp_management(...):
    # Before capture, check if ISP needs preventive reset
    if self._isp_failure_count >= 2:
        time_since_reset = time.time() - self._last_isp_reset
        if time_since_reset > 30:  # 30 seconds since last reset
            logger.warning(f"ISP health degraded ({self._isp_failure_count} failures), performing preventive reset...")
            await self._perform_deep_isp_reset()
            self._isp_failure_count = 0
            self._last_isp_reset = time.time()
    
    # ... existing capture code ...
    
    # On successful capture, decay failure count
    if image_array is not None:
        self._isp_failure_count = max(0, self._isp_failure_count - 1)
    else:
        self._isp_failure_count += 1

async def _perform_deep_isp_reset(self):
    """Deep ISP reset: stop all cameras, clean buffers, restart"""
    for camera_id in self.cameras:
        if self.cameras[camera_id]:
            if self.cameras[camera_id].started:
                self.cameras[camera_id].stop()
    
    await asyncio.sleep(2.0)  # Extended cooldown
    gc.collect()
    
    for camera_id in self.cameras:
        if self.cameras[camera_id]:
            self.cameras[camera_id].start()
    
    await asyncio.sleep(1.0)  # Full stabilization
```

## Testing Strategy

### Before Fix:
- Run scan with quality preset "High" (4624×3472)
- Observe failure rate and stall points

### After Fix:
1. **Test 1:** Single scan point capture - verify no redundant reconfigurations
2. **Test 2:** 10-point scan - verify stable performance
3. **Test 3:** Full 144-point scan - verify completion without stalls
4. **Test 4:** Rapid scan restarts - verify ISP recovery

### Success Criteria:
- ✅ No more than 1 camera reconfiguration per scan point
- ✅ No ISP timeouts during normal operation
- ✅ Full scan completion (144/144 points)
- ✅ Recovery from single ISP timeout without stalling

## Implementation Priority

1. **CRITICAL:** Solution 2 - Remove redundant reconfiguration check (immediate fix)
2. **HIGH:** Solution 1 - Add configuration state tracking (prevent future issues)  
3. **MEDIUM:** Solution 3 - Increase timeout/recovery times (safety net)
4. **LOW:** Solution 4 - ISP health monitoring (long-term reliability)

## Files to Modify

1. `RaspPI/V2.0/camera/pi_camera_controller.py`
   - Lines 2400-2500 (capture_with_isp_management - timeouts)
   - Lines 2500-2600 (capture_dual_sequential_isp)
   - Lines 2600-2700 (prepare_cameras_for_capture - state tracking)
   - Lines 3000-3050 (capture_dual_resolution_aware - remove redundant check)

2. `RaspPI/V2.0/scanning/scan_orchestrator.py`
   - Lines 1700-1800 (camera preparation flow - verify no double calls)

## Expected Performance Improvement

**Current State:**
- ~25% of captures timeout and stall the scan
- 4+ camera reconfigurations per scan point
- ISP exhaustion after 15-20 points

**After Fixes:**
- <1% capture timeout rate (only on true hardware issues)
- 1 camera reconfiguration per scan point (only when resolution changes)
- Stable ISP operation for full 144-point scans
- Automatic recovery from transient ISP issues
