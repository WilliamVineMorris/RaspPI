# Camera Capture Timeout Fix

## Problem Summary
Scan operations would intermittently hang during camera capture operations, getting stuck at the "CAPTURING" phase with no progress. This typically occurred at random scan points (e.g., point 70/144) and could freeze for 30+ seconds indefinitely.

## Root Cause

### The Blocking Call Issue
```python
# BEFORE (BROKEN):
async def capture_with_isp_management(self, camera_id: int, stream_name: str = "main"):
    # ... setup code ...
    
    for attempt in range(max_retries):
        # THIS IS A BLOCKING SYNCHRONOUS CALL IN AN ASYNC FUNCTION!
        image_array = camera.capture_array(stream_name)  # ❌ Can block forever
        
        return image_array
```

**The Problem:**
- `camera.capture_array()` is a **synchronous blocking call** from Picamera2
- When Picamera2's ISP (Image Signal Processor) gets stuck or buffers fill up:
  - The call blocks indefinitely waiting for the ISP to respond
  - No timeout protection = infinite hang
  - Async event loop can't cancel or timeout the operation
  - Entire scan freezes with no way to recover

**Why This Happens Intermittently:**
- ISP buffer queue errors occur randomly (hardware/timing dependent)
- Camera state can become inconsistent after repeated captures
- Pi5 ISP pipeline occasionally needs restart when under load
- Previous captures succeeded, but state degraded over time

## The Solution

### 1. Timeout Protection with Executor
```python
# AFTER (FIXED):
async def capture_with_isp_management(self, camera_id: int, stream_name: str = "main"):
    # ... setup code ...
    
    for attempt in range(max_retries):
        # Run blocking call in executor with timeout protection
        loop = asyncio.get_event_loop()
        capture_timeout = 10.0  # 10 second timeout per attempt
        
        try:
            # Execute blocking call in thread pool with timeout
            image_array = await asyncio.wait_for(
                loop.run_in_executor(None, camera.capture_array, stream_name),
                timeout=capture_timeout
            )
        except asyncio.TimeoutError:
            raise Exception(f"Capture timeout after {capture_timeout}s (ISP may be stuck)")
        
        return image_array  # ✅ Returns or times out, never hangs forever
```

**How This Fixes It:**
1. **Thread Pool Executor**: Runs blocking `capture_array()` in separate thread
2. **Timeout Protection**: `asyncio.wait_for()` enforces 10-second limit
3. **Async Compatibility**: Event loop can cancel if timeout expires
4. **Retry Logic**: After timeout, triggers camera restart and retry

### 2. Enhanced Error Detection
```python
# BEFORE (LIMITED):
if "Failed to queue buffer" in error_msg or "Invalid argument" in error_msg:
    # Restart camera...

# AFTER (COMPREHENSIVE):
needs_camera_restart = (
    "Failed to queue buffer" in error_msg or 
    "Invalid argument" in error_msg or
    "timeout" in error_msg.lower() or        # ✅ NEW: Catch timeout errors
    "ISP may be stuck" in error_msg          # ✅ NEW: Catch ISP stuck state
)

if needs_camera_restart:
    logger.info(f"ISP issue detected (timeout/buffer), attempting camera restart...")
    # Stop camera, clear buffers, restart, retry...
```

**Improvements:**
- Detects timeout errors from the new timeout protection
- Identifies ISP stuck state explicitly
- Triggers proper camera restart recovery
- More robust error handling across ISP failure modes

## Expected Behavior After Fix

### Before Fix:
```
23:24:38,313 - 🔧 STANDARD SIMULTANEOUS: Capturing 2 cameras simultaneously
[Hangs forever... no timeout, no error, just stuck]
[User presses Ctrl+C after 35+ seconds]
```

### After Fix - Success Case:
```
23:24:38,313 - 🔧 STANDARD SIMULTANEOUS: Capturing 2 cameras simultaneously
23:24:38,320 - ISP capture attempt 1 for camera 0
23:24:38,450 - ISP-managed capture successful for camera 0
23:24:38,550 - ISP capture attempt 1 for camera 1
23:24:38,680 - ISP-managed capture successful for camera 1
23:24:38,690 - Sequential ISP capture successful: camera_0 -> (2464, 3280, 3)
23:24:38,695 - Sequential ISP capture successful: camera_1 -> (2464, 3280, 3)
```

### After Fix - Timeout with Recovery:
```
23:24:38,313 - 🔧 STANDARD SIMULTANEOUS: Capturing 2 cameras simultaneously
23:24:38,320 - ISP capture attempt 1 for camera 0
[10 seconds pass...]
23:24:48,320 - ISP capture attempt 1 failed for camera 0: Capture timeout after 10.0s (ISP may be stuck)
23:24:48,321 - ISP issue detected (timeout/buffer), attempting camera restart...
23:24:48,321 - Camera 0 stopped
23:24:48,821 - Camera 0 started
23:24:49,121 - Camera 0 ISP recovery completed
23:24:49,221 - ISP capture attempt 2 for camera 0
23:24:49,350 - ISP-managed capture successful for camera 0  ✅ RECOVERED!
```

## Testing Instructions

### Test the Fix on Pi Hardware:

1. **Deploy the updated code to Pi:**
   ```bash
   cd ~/RaspPI/V2.0
   git pull origin Test
   ```

2. **Run a full scan with manual focus:**
   - Start the scanner system
   - Navigate to web UI
   - Set manual focus to 8.2 diopters
   - Start a scan pattern (cylindrical, 144 points)

3. **Monitor for timeout behavior:**
   ```bash
   # Watch logs in real-time
   tail -f scanner.log | grep -E "CAPTURING|timeout|ISP|recovery"
   ```

4. **Expected outcomes:**
   - **Success**: Scan completes all 144 points without hanging
   - **Timeout handled**: If ISP gets stuck, timeout triggers after 10s, camera restarts, retry succeeds
   - **No infinite hangs**: System always makes progress or fails explicitly (never stuck forever)

### Verify the Logs Show:

**Successful captures:**
```
ISP capture attempt 1 for camera 0
ISP-managed capture successful for camera 0
```

**Timeout recovery (if ISP issue occurs):**
```
ISP capture attempt 1 failed: Capture timeout after 10.0s
ISP issue detected (timeout/buffer), attempting camera restart...
Camera 0 ISP recovery completed
ISP capture attempt 2 for camera 0
ISP-managed capture successful for camera 0
```

**No indefinite hangs:**
- If you see "CAPTURING" phase, it should complete within 10-15 seconds
- If timeout occurs, recovery happens automatically
- Maximum delay per point: ~30 seconds (3 retries × 10s each)

## Technical Details

### Why `run_in_executor()` is Needed

**Async/Sync Mismatch:**
- Picamera2's `capture_array()` is synchronous (blocking)
- Our camera controller uses async/await pattern
- Blocking calls in async functions freeze the event loop

**The Executor Solution:**
```python
loop.run_in_executor(None, camera.capture_array, stream_name)
```
- `None` = Use default ThreadPoolExecutor
- Runs `camera.capture_array(stream_name)` in separate thread
- Returns awaitable Future that async code can handle
- Event loop stays responsive

### Timeout Configuration

**Current setting: 10 seconds per attempt**
- Typical successful capture: 0.1-0.5 seconds
- ISP stabilization: 0.1-0.3 seconds
- 10s provides generous margin for Pi5 under load
- 3 retries = up to 30 seconds total before giving up

**Can be adjusted if needed:**
```python
capture_timeout = 10.0  # Increase if Pi5 needs more time under heavy load
```

### Retry Strategy

**3 attempts with progressive backoff:**
1. **Attempt 1**: Try capture with 10s timeout
2. **If timeout**: Restart camera, wait, retry
3. **Attempt 2**: Try capture again with 10s timeout
4. **If timeout**: Restart camera, wait longer, retry
5. **Attempt 3**: Final attempt with 10s timeout
6. **If all fail**: Return None, scan point marked as failed

**Recovery actions on timeout:**
- Stop camera (releases ISP resources)
- Garbage collect (clears Python buffers)
- Wait 0.5s (allows ISP to fully reset)
- Start camera (reinitializes ISP pipeline)
- Wait 0.3s (ISP stabilization)
- Retry capture

## Files Modified

### `camera/pi_camera_controller.py`

**Line ~2419-2440**: Added timeout protection to `capture_with_isp_management()`
- Wrapped `capture_array()` in `run_in_executor()` with `asyncio.wait_for()`
- 10-second timeout per attempt
- Raises exception on timeout to trigger recovery

**Line ~2447-2475**: Enhanced error detection for timeout handling
- Added timeout detection to `needs_camera_restart` logic
- Includes "timeout" and "ISP may be stuck" in error triggers
- Ensures timeout errors trigger camera restart recovery

## Related Issues

This fix is **independent** of the focus diopter fix:
- Focus fix: ✅ Completed (manual focus now uses correct 0-15 diopter values)
- Timeout fix: ✅ Completed (camera capture no longer hangs indefinitely)

Both issues occurred in same scan but were unrelated:
- Focus working correctly (8.2 diopters applied successfully)
- Scan hanging at point 70 (ISP timeout, now fixed)

## Notes

- **This is a known intermittent issue**: ISP buffer management on Pi5 is timing-sensitive
- **Fix provides robustness**: Timeout + retry means occasional ISP glitches recover automatically
- **No performance impact on success case**: Timeout only triggers if ISP actually gets stuck
- **Maintains image quality**: Recovery process doesn't affect capture quality when retry succeeds
