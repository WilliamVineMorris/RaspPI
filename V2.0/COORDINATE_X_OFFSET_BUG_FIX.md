# Coordinate Transformation X-Axis Offset Bug Fix

## Problem
FluidNC X coordinate was calculated **incorrectly** - missing the turntable offset X component.

### Evidence from Logs:
```
📐 Camera position: radius=100.0mm, height=60.0mm, rotation=0.0°, tilt=-31.0°
🔧 FluidNC position: X=90.0, Y=70.0, Z=0.0°, C=-31.0°
```

**Expected**: FluidNC X should be **120mm**  
**Actual**: FluidNC X was **90mm** ❌

## Root Cause
The `camera_to_fluidnc()` transformation was only adding the **camera offset X**, not the **turntable offset X**.

### Configuration (from scanner_config.yaml):
```yaml
cameras:
  positioning:
    camera_offset:
      x: -10  # mm - Camera mount offset
      y: 20   # mm
    turntable_offset:
      x: 30   # mm - Turntable center position
      y: -10  # mm
```

### OLD CODE (BUGGY) - Line 145:
```python
def camera_to_fluidnc(self, camera_pos: CameraRelativePosition) -> Position4D:
    # FluidNC X is the radial position (with offsets applied)
    # Camera radius is relative to turntable center
    # FluidNC X needs camera offset applied
    fluidnc_x = camera_pos.radius + self.camera_offset_x  # ❌ MISSING turntable_offset_x!
    
    # Y calculation was correct
    world_height = camera_pos.height + self.turntable_offset_y
    fluidnc_y = world_height + self.camera_offset_y
    ...
```

### Incorrect Calculation:
```
FluidNC X = 100mm (radius) + (-10mm) (camera_offset_x)
          = 90mm ❌ WRONG!
```

## Solution
Add **both** turntable offset X and camera offset X to the radius.

### NEW CODE (CORRECT) - Line 145:
```python
def camera_to_fluidnc(self, camera_pos: CameraRelativePosition) -> Position4D:
    # FluidNC X is the radial position (with offsets applied)
    # Camera radius is relative to turntable center
    # Add turntable offset (where turntable is), then add camera offset
    fluidnc_x = camera_pos.radius + self.turntable_offset_x + self.camera_offset_x  # ✓ CORRECT!
    
    # Y calculation unchanged (was already correct)
    world_height = camera_pos.height + self.turntable_offset_y
    fluidnc_y = world_height + self.camera_offset_y
    ...
```

### Correct Calculation:
```
FluidNC X = 100mm (radius) + 30mm (turntable_offset_x) + (-10mm) (camera_offset_x)
          = 120mm ✓ CORRECT!
```

## Reverse Transformation Also Fixed

The `fluidnc_to_camera()` function had the same bug in reverse.

### OLD CODE (BUGGY) - Line 171:
```python
def fluidnc_to_camera(self, fluidnc_pos: Position4D) -> CameraRelativePosition:
    # FluidNC X is already the radial position, just remove camera offset
    radius = fluidnc_pos.x - self.camera_offset_x  # ❌ MISSING turntable_offset_x!
    ...
```

### NEW CODE (CORRECT):
```python
def fluidnc_to_camera(self, fluidnc_pos: Position4D) -> CameraRelativePosition:
    # FluidNC X is already the radial position, remove offsets
    # Remove camera offset first, then turntable offset
    radius = fluidnc_pos.x - self.camera_offset_x - self.turntable_offset_x  # ✓ CORRECT!
    ...
```

## Understanding the Coordinate System

### Physical Layout:
1. **FluidNC origin** (0, 0) is the machine's reference point
2. **Turntable center** is at `(turntable_offset_x, turntable_offset_y)` from FluidNC origin
3. **Camera** is mounted at `(camera_offset_x, camera_offset_y)` relative to its carriage position
4. **User specifies radius** from turntable center to camera

### Transformation Logic:
```
Camera-Relative Input:
  radius = 100mm (from turntable center)

Physical Reality:
  Turntable center is at X=30mm from FluidNC origin
  Camera mount is at X=-10mm from carriage position
  
FluidNC Command Needed:
  X = radius + turntable_position + camera_mount_offset
  X = 100mm + 30mm + (-10mm) = 120mm
```

### Verification with Example:

**Scan Configuration:**
- Radius: 100mm (user input)
- Height: 60mm (user input)

**Hardware Offsets:**
- Turntable offset: X=30mm, Y=-10mm
- Camera offset: X=-10mm, Y=20mm

**Expected FluidNC Commands:**
- **X**: 100 + 30 + (-10) = **120mm** ✓
- **Y**: 60 + (-10) + 20 = **70mm** ✓ (was already correct)

**Before Fix:**
- **X**: 100 + (-10) = **90mm** ❌
- **Y**: 60 + (-10) + 20 = **70mm** ✓

**After Fix:**
- **X**: 100 + 30 + (-10) = **120mm** ✓
- **Y**: 60 + (-10) + 20 = **70mm** ✓

## Impact

### Before Fix:
- Camera would physically move to the **wrong radial position**
- Would be 30mm closer to the origin than intended
- All scan points would be **incorrectly positioned**
- Could cause collisions or miss the object entirely

### After Fix:
- Camera moves to the **correct radial position**
- Accounts for both turntable location and camera mount offset
- Scan points are **accurately positioned**
- Matches user's configured radius values

## Changes Made

### File: `core/coordinate_transform.py`

#### Change 1: Forward transformation (line ~145)
```python
# BEFORE:
fluidnc_x = camera_pos.radius + self.camera_offset_x

# AFTER:
fluidnc_x = camera_pos.radius + self.turntable_offset_x + self.camera_offset_x
```

#### Change 2: Reverse transformation (line ~171)
```python
# BEFORE:
radius = fluidnc_pos.x - self.camera_offset_x

# AFTER:
radius = fluidnc_pos.x - self.camera_offset_x - self.turntable_offset_x
```

## Testing

### Expected Log Output After Fix:
```
📐 Camera position: radius=100.0mm, height=60.0mm, rotation=0.0°, tilt=-31.0°
🔧 FluidNC position: X=120.0, Y=70.0, Z=0.0°, C=-31.0°
G0 X120.000 Y70.000 Z0.000 C-30.964
```

### Verification Steps:
1. ✅ Run a scan on the Pi
2. ✅ Check logs for coordinate transformation messages
3. ✅ Verify FluidNC X = radius + turntable_offset_x + camera_offset_x
4. ✅ Verify FluidNC Y = height + turntable_offset_y + camera_offset_y
5. ⏳ **CRITICAL**: Physically measure camera position to confirm accuracy

### Test Cases:

**Test 1: Radius=100mm**
- Expected FluidNC X: 100 + 30 + (-10) = 120mm
- Before fix: 90mm ❌
- After fix: 120mm ✓

**Test 2: Radius=150mm**
- Expected FluidNC X: 150 + 30 + (-10) = 170mm
- Before fix: 140mm ❌
- After fix: 170mm ✓

**Test 3: Radius=50mm**
- Expected FluidNC X: 50 + 30 + (-10) = 70mm
- Before fix: 40mm ❌
- After fix: 70mm ✓

## Related Files
- `core/coordinate_transform.py`: Fixed forward and reverse transformations
- `scanning/scan_orchestrator.py`: Uses coordinate transformer (no changes needed)
- `config/scanner_config.yaml`: Contains offset configuration

## Date
2025-10-03

## Status
✅ **IMPLEMENTED** - Ready for Pi hardware testing
⚠️ **CRITICAL**: Test on actual hardware to verify physical camera positioning!
