# Lighting Status Display Fix

## Date: 2025-10-03

## Problem
Lighting controller was working perfectly (2 zones: 'inner' and 'outer' on GPIO 13 and 18), but dashboard showed:
- ❌ "Zones: 0" 
- ❌ Red indicator (error state)
- ❌ Status: "available" but indicator didn't match

## Root Cause
Backend API (`web_interface.py` line 2435) was calling non-existent method `get_sync_status()` on the lighting controller, causing it to fall back to returning empty zones array.

## Evidence from Logs
```
2025-10-03 14:36:39,683 - lighting.gpio_led_controller - INFO - Zone 'inner' initialized with 1 pins
2025-10-03 14:36:39,683 - lighting.gpio_led_controller - INFO - Zone 'outer' initialized with 1 pins
2025-10-03 14:36:39,683 - scanning.scan_orchestrator - INFO - ✅ Lighting controller initialized with zones: ['inner', 'outer']
```

Lighting was working, but web interface couldn't read the zone information.

## Solution

### Backend Fix (`web_interface.py`)

**Old Code** (lines 2432-2446):
```python
if hasattr(self.orchestrator.lighting_controller, 'get_sync_status'):
    lighting_status = self.orchestrator.lighting_controller.get_sync_status()
    status['lighting'].update({
        'zones': list(lighting_status.get('zones', {}).keys()),
        'status': lighting_status.get('status', 'unknown')
    })
else:
    # Fallback for other lighting controllers
    status['lighting'].update({
        'zones': [],
        'status': 'sync_method_unavailable'
    })
```

**New Code**:
```python
lighting_ctrl = self.orchestrator.lighting_controller
# Use zone_configs property to get available zones
if hasattr(lighting_ctrl, 'zone_configs'):
    zone_ids = list(lighting_ctrl.zone_configs.keys())
    # Check if lighting is initialized and available
    is_available = hasattr(lighting_ctrl, 'status') and lighting_ctrl.status != 'error'
    status['lighting'].update({
        'zones': zone_ids,
        'status': 'available' if is_available and zone_ids else 'no_zones_configured'
    })
    self.logger.debug(f"Lighting status: zones={zone_ids}, available={is_available}")
```

### Frontend Fix (`dashboard.html`)

**Already fixed in previous update** - properly unwraps API response and checks multiple status conditions:
```javascript
const isAvailable = status.lighting.status && 
                  (status.lighting.status.toLowerCase() === 'available' ||
                   status.lighting.status.toLowerCase() === 'ready' ||
                   status.lighting.zones && status.lighting.zones.length > 0);
```

## Expected Result

After fix, dashboard should show:
- ✅ "Zones: 2" (inner, outer)
- ✅ "Status: available"
- ✅ Green indicator (ready state)

## Testing

### 1. Refresh Dashboard
Press "Refresh Status" button or reload page

### 2. Check Console
Should see:
```
Lighting status: {zones: ['inner', 'outer'], status: 'available'}
Lighting zones count: 2
Lighting state: available
Lighting indicator: ready (green)
```

### 3. Test Lighting
Click "⚡ Test Lighting" button - should trigger flash and show green success notification

## API Response Format

**Before Fix**:
```json
{
  "data": {
    "lighting": {
      "zones": [],
      "status": "sync_method_unavailable"
    }
  }
}
```

**After Fix**:
```json
{
  "data": {
    "lighting": {
      "zones": ["inner", "outer"],
      "status": "available"
    }
  }
}
```

## Files Modified

1. **`web/web_interface.py`** (lines 2432-2451)
   - Removed call to non-existent `get_sync_status()`
   - Access `zone_configs` property directly
   - Proper status determination

2. **`web/templates/dashboard.html`** (already fixed in previous update)
   - Unwrap API response from `data` field
   - Enhanced status checking logic
   - Added console debugging

## Hardware Context

Lighting controller configuration from logs:
- **Library**: gpiozero with LGPIO factory (Pi 5 compatible)
- **Zone 'inner'**: GPIO 13, Hardware PWM, max brightness 0.9
- **Zone 'outer'**: GPIO 18, Hardware PWM, max brightness 0.9
- **PWM Frequency**: 400Hz
- **Status**: Fully operational with hardware PWM (flicker-free)
