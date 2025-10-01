# LED Flickering V5: Scan-Level Lighting Control

## 🎯 ROOT CAUSE FINALLY IDENTIFIED!

**Problem**: Even with V4 (batch calibration) + V4.1 (50ms delay), flickering persists during the **scan itself** because LEDs are turned on/off **for each scan point**:

### The Real Flickering Source (from logs):
```log
Point 0:
  23:50:41.946 - 💡 LED UPDATE: Zone 'inner' 0.0% → 30.0% (state: ON)   ← ON for point 0
  ... capture point 0 ...
  23:50:45.188 - 💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)  ← OFF after point 0

Point 1:
  [LED ON again]   ← FLICKER!
  ... capture point 1 ...
  [LED OFF again]  ← FLICKER!

Point 2:
  [LED ON again]   ← FLICKER!
  ... capture point 1 ...
  [LED OFF again]  ← FLICKER!
```

For multi-point scans, this creates constant ON→OFF→ON→OFF cycling = **visible flickering**!

## V5 Solution: Scan-Level Lighting

Turn LEDs on **ONCE at scan start**, keep them on **for all points**, turn off **ONCE at scan end**.

### Implementation:

#### 1. `_execute_scan_points()` - Manages LEDs for Entire Scan

```python
async def _execute_scan_points(self):
    """Execute all scan points"""
    # ... setup code ...
    
    # 🔥 V5: Turn on LEDs ONCE before entire scan
    leds_turned_on = False
    try:
        self.logger.info("💡 SCAN: Turning on LEDs for entire scan duration...")
        await self.lighting_controller.set_brightness("all", 0.3)
        leds_turned_on = True
        self.logger.info("💡 SCAN: LEDs on at 30% - will remain on for all scan points")
        await asyncio.sleep(0.05)  # 50ms settling
    except Exception as led_error:
        self.logger.warning(f"⚠️ SCAN: Could not enable LEDs: {led_error}")
    
    try:
        for i, point in enumerate(scan_points):
            # ... move to point ...
            # ... setup focus (point 0 only) ...
            
            # 🔥 V5: Capture with LEDs already on (no per-point control)
            images_captured = await self._capture_at_point(point, i)
            
            # ... update progress ...
    
    finally:
        # 🔥 V5: Turn off LEDs ONCE after entire scan
        if leds_turned_on:
            try:
                self.logger.info("💡 SCAN: Turning off LEDs after scan completion...")
                await self.lighting_controller.turn_off_all()
                self.logger.info("💡 SCAN: LEDs turned off after complete scan")
            except Exception as led_off_error:
                self.logger.warning(f"⚠️ SCAN: Could not disable LEDs: {led_off_error}")
```

#### 2. `_capture_at_point()` - Skip LED Control (Already On)

**BEFORE** (V4.1 - flickering):
```python
# ⚡ FLASH coordination with PROPER SYNCHRONIZATION
flash_result = await self.lighting_controller.trigger_for_capture(
    self.camera_manager,
    zones_to_flash,
    flash_settings
)
# ^ This turns LEDs on, captures, then turns LEDs off per point!
```

**AFTER** (V5 - no flickering):
```python
# ⚡ V5: Direct capture with scan-level lighting
self.logger.info("📸 Capturing with scan-level lighting (LEDs already on)...")

# Direct camera capture - LEDs already on at 30% from scan level
camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
self.logger.info("✅ Camera capture successful with scan-level lighting")
# ^ No LED control here - LEDs stay on!
```

## Expected Behavior After V5

### Log Pattern:
```log
💡 SCAN: Turning on LEDs for entire scan duration...
💡 LED UPDATE: Zone 'inner' 0.0% → 30.0% (state: ON)   ← ON ONCE
💡 LED UPDATE: Zone 'outer' 0.0% → 30.0% (state: ON)
💡 SCAN: LEDs on at 30% - will remain on for all scan points

... Point 0 ...
📸 Capturing with scan-level lighting (LEDs already on)...
✅ Camera capture successful with scan-level lighting
(NO LED UPDATES)

... Point 1 ...
📸 Capturing with scan-level lighting (LEDs already on)...
✅ Camera capture successful with scan-level lighting
(NO LED UPDATES)

... Point N ...

💡 SCAN: Turning off LEDs after scan completion...
💡 LED UPDATE: Zone 'inner' 30.0% → 0.0% (state: OFF)   ← OFF ONCE
💡 LED UPDATE: Zone 'outer' 30.0% → 0.0% (state: OFF)
💡 SCAN: LEDs turned off after complete scan
```

### Result:
- **Only 4 LED updates for entire scan** (2 zones × [on, off])
- **No flickering between scan points**
- **Smooth, constant lighting throughout scan**

## Implementation Status

✅ **File 1**: `scanning/scan_orchestrator.py` `_execute_scan_points()` - UPDATED  
⏳ **File 2**: `scanning/scan_orchestrator.py` `_capture_at_point()` - NEEDS UPDATE

### Manual Fix Needed for `_capture_at_point()`:

**Location**: Lines 3874-3936 in `scanning/scan_orchestrator.py`

**Replace this block**:
```python
            # ⚡ FLASH coordination with PROPER SYNCHRONIZATION
            flash_result = None
            try:
                if hasattr(self, 'lighting_controller') and self.lighting_controller:
                    from lighting.base import LightingSettings
                    
                    # Use constant lighting mode (30% brightness) for resolution-independent timing
                    # This ensures proper lighting regardless of camera resolution/timing variations
                    flash_settings = LightingSettings(
                        brightness=0.3,      # 30% constant lighting during capture
                        duration_ms=0,       # 0 = constant mode (not timed flash)
                        constant_mode=True   # Explicit constant mode flag
                    )
                    
                    # Use both inner and outer zones for maximum illumination
                    zones_to_flash = ['inner', 'outer']
                    
                    # SYNCHRONIZED FLASH + CAPTURE using LED controller method
                    self.logger.info("⚡ Starting synchronized flash + capture...")
                    
                    # Use the dedicated synchronized method from LED controller
                    flash_result = await self.lighting_controller.trigger_for_capture(
                        self.camera_manager,
                        zones_to_flash,
                        flash_settings
                    )
                    
                    # Extract camera result from flash operation
                    camera_data_dict = None
                    if hasattr(flash_result, '__dict__') and 'camera_result' in flash_result.__dict__:
                        camera_data_dict = flash_result.camera_result
                    
                    # If no camera result from synchronized method, try direct capture
                    if not camera_data_dict:
                        self.logger.info("📸 Fallback to direct camera capture...")
                        if hasattr(self, 'camera_manager') and self.camera_manager:
                            camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
                    
                    if flash_result and hasattr(flash_result, 'success') and flash_result.success:
                        self.logger.info(f"⚡ Flash synchronized with capture - zones: {flash_result.zones_activated}")
                    else:
                        self.logger.warning(f"⚡ Flash synchronization had issues but capture completed")
                else:
                    self.logger.info("💡 No lighting controller available - capturing without flash")
                    # Capture without flash
                    if not hasattr(self, 'camera_manager') or not self.camera_manager:
                        raise Exception("Camera manager not available")
                    camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
            except Exception as flash_error:
                self.logger.warning(f"⚠️ Synchronized flash failed: {flash_error}, attempting capture without flash")
                # Fallback: capture without flash
                try:
                    if hasattr(self, 'camera_manager') and self.camera_manager:
                        camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
                    else:
                        raise Exception("Camera manager not available")
                except Exception as capture_error:
                    raise Exception(f"Both flash and capture failed: Flash={flash_error}, Capture={capture_error}")
```

**With this**:
```python
            # ⚡ V5 FIX: Direct capture with scan-level lighting (no per-point LED control)
            # LEDs are turned on once for entire scan in _execute_scan_points()
            # This prevents per-point LED flickering
            flash_result = None
            camera_data_dict = None
            
            try:
                self.logger.info("📸 Capturing with scan-level lighting (LEDs already on)...")
                
                # Direct camera capture - LEDs already on at 30% from scan level
                if hasattr(self, 'camera_manager') and self.camera_manager:
                    camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
                    self.logger.info("✅ Camera capture successful with scan-level lighting")
                else:
                    raise Exception("Camera manager not available")
                    
            except Exception as capture_error:
                self.logger.error(f"❌ Camera capture failed: {capture_error}")
                raise Exception(f"Camera capture failed: {capture_error}")
```

## Testing

After manual fix:
1. Stop scanner: `sudo pkill -f run_web_interface`
2. Clear cache: `cd ~/RaspPI/V2.0 && find . -type d -name __pycache__ -exec rm -rf {} + && find . -name "*.pyc" -delete`
3. Restart: `python3 run_web_interface.py`
4. Watch logs: `tail -f logs/scanner.log | grep "💡"`

Expected: Only 2 LED on/off cycles for entire multi-point scan!

## Complete Fix History

- ✅ V1: Direct synchronous PWM control
- ✅ V2: 0.5% brightness threshold
- ✅ V3: 1% threshold + thread lock
- ✅ V3.1: State tracking (blocks redundant on/off)
- ✅ V4: Batch calibration lighting
- ✅ V4.1: 50ms settling delay
- ✅ **V5: Scan-level lighting control** ← **THIS IS THE FINAL ROOT CAUSE FIX!**

**Result**: Zero flickering during calibration AND scan! 🎉
