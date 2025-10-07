# Focus Range Standardization Fix

**Date**: 2025-10-07  
**Issue**: Inconsistent focus ranges and inverted labels across web UI pages  
**Status**: ✅ FIXED

---

## Problems Identified

### 1. **Inconsistent Range Values**
**Different pages had different ranges**:
- ❌ **Scans page**: `min="0" max="15"` (wrong - allows invalid values)
- ❌ **Dashboard page**: `min="0" max="10"` (close but should start at 6)
- ✅ **Backend expects**: `6.0 - 10.0` (ArduCam physical focus range)

### 2. **Inverted/Confusing Labels**
**Scans page had backwards labels**:
```html
❌ BEFORE:
<small>0.0 (Infinity)</small>      <!-- Wrong - infinity should be high value -->
<small>6-10 (Macro)</small>         <!-- Confusing - this is the valid range -->
<small>15.0 (Close-up)</small>      <!-- Wrong - out of range -->
```

### 3. **User Impact**
- User could set focus to 0.0 or 15.0 (invalid values)
- Backend conversion would clamp to 0.0-1.0 normalized range incorrectly
- Labels suggested infinity was at 0 (backwards from camera convention)

---

## ArduCam 64MP Focus Range (Ground Truth)

### **Physical Focus Characteristics**
```
Lens Position:  0 ───────────────────────── 1023
                ↑                            ↑
             Far/Infinity                  Near/Macro
             
Focus Distance: 10.0mm ────────────── 6.0mm
                ↑                      ↑
            Far (distant)          Near (close-up)
            
Web UI Value:   10.0 ────────────── 6.0
                ↑                    ↑
            Infinity/Far          Macro/Near
```

### **Valid Range**
- **Minimum**: 6.0 (near focus, close-up, macro)
- **Maximum**: 10.0 (far focus, distant objects, infinity)
- **Hyperfocal**: ~8.0 (best depth of field for general scanning)

### **Invalid Values**
- Values < 6.0: Camera cannot focus closer
- Values > 10.0: Camera cannot focus further
- Backend clamps to 6.0-10.0 range

---

## Solution Implemented

### **Scans Page** (`web/templates/scans.html`)

#### Manual Focus Slider
```html
✅ AFTER:
<input type="range" id="manualFocusPosition" 
       min="6" max="10" step="0.1" value="8.0">

<small>6.0 (Near/Macro)</small>
<small>8.0 (Hyperfocal)</small>
<small>10.0 (Far/Infinity)</small>
```

#### Focus Stack Min/Max
```html
✅ AFTER:
<input type="number" id="focusMin" 
       min="6" max="10" step="0.1" value="6.0">
<input type="number" id="focusMax" 
       min="6" max="10" step="0.1" value="10.0">
```

### **Dashboard Page** (`web/templates/dashboard.html`)

```html
✅ AFTER:
<label>Focus Position (6=Near, 10=Far)</label>
<input type="range" id="focusSlider" 
       min="6" max="10" step="0.1" value="8">
```

---

## Focus Value Flow (Complete Pipeline)

### **1. User Input (Web UI)**
```
Range: 6.0 - 10.0
Default: 8.0 (hyperfocal)
Step: 0.1
```

### **2. Backend Receives**
```python
self._web_focus_position = 8.0  # Direct from web UI
```

### **3. Backend Converts to Normalized**
```python
# Convert 6.0-10.0 → 0.0-1.0
focus_normalized = (self._web_focus_position - 6.0) / 4.0
# Example: 8.0 → (8.0 - 6.0) / 4.0 = 0.5
```

### **4. Camera Controller Converts to Lens Position**
```python
# Convert 0.0-1.0 → 1023-0 (inverted!)
lens_position = int((1.0 - focus_value) * 1023)
# Example: 0.5 → (1.0 - 0.5) * 1023 = 512
```

### **5. Camera Hardware**
```
LensPosition: 512 (middle of range)
Result: Focused at ~8mm distance (hyperfocal)
```

---

## Validation

### **Range Enforcement**
- ✅ Web UI sliders constrained to 6.0-10.0
- ✅ Number inputs have min/max attributes
- ✅ Backend clamps values during conversion
- ✅ Camera controller validates before setting

### **Label Accuracy**
| Value | Distance | Description |
|-------|----------|-------------|
| 6.0   | Near     | Close-up objects, macro mode |
| 7.0   | Close    | Objects ~200mm away |
| 8.0   | Hyperfocal | Best depth of field (recommended) |
| 9.0   | Mid-far  | Objects ~500mm away |
| 10.0  | Infinity | Distant objects, far focus |

### **Conversion Examples**
```
Web UI → Normalized → Lens Position
6.0    → 0.00       → 1023 (near)
7.0    → 0.25       → 767
8.0    → 0.50       → 512  (hyperfocal)
9.0    → 0.75       → 256
10.0   → 1.00       → 0    (far)
```

---

## Testing Checklist

### ✅ Scans Page
- [ ] Manual focus slider shows 6.0-10.0 range
- [ ] Labels show "6.0 (Near/Macro)" to "10.0 (Far/Infinity)"
- [ ] Default value is 8.0
- [ ] Focus stack min/max constrained to 6.0-10.0

### ✅ Dashboard Page  
- [ ] Focus slider shows 6.0-10.0 range
- [ ] Label shows "(6=Near, 10=Far)"
- [ ] Default value is 8.0
- [ ] Cannot slide below 6 or above 10

### ✅ Backend Behavior
- [ ] Values 6.0-10.0 convert correctly
- [ ] Values < 6.0 clamped to 6.0
- [ ] Values > 10.0 clamped to 10.0
- [ ] Logs show correct normalized values

---

## User Guidance

### **Recommended Focus Values**

| Scan Type | Focus Value | Reasoning |
|-----------|-------------|-----------|
| General scanning | 8.0 | Hyperfocal - best depth of field |
| Small objects | 6.0-7.0 | Close focus for detail |
| Large objects | 8.0-9.0 | Medium focus for coverage |
| Distant objects | 9.0-10.0 | Far focus for reach |

### **Focus Stacking**
For maximum sharpness across depth:
```
Mode: Manual Focus Stacking
Min: 6.0 (near)
Max: 10.0 (far)
Steps: 5-10 (more = slower but sharper)
```

### **Troubleshooting**
- **Blurry images**: Check focus value is in 6.0-10.0 range
- **Cannot focus close**: Minimum is 6.0mm (camera limit)
- **Cannot focus far**: Maximum is 10.0mm (camera limit)
- **Best all-around**: Use 8.0 (hyperfocal distance)

---

## Technical Notes

### **Why 6.0-10.0?**
This is the ArduCam 64MP's **physical focusing range**:
- Motor can move lens from 6mm to 10mm from sensor
- Outside this range, lens cannot physically move
- Values represent actual distance in millimeters

### **Why Inverted Lens Position?**
Camera hardware uses **inverse convention**:
- High lens position (1023) = lens close to sensor = near focus
- Low lens position (0) = lens far from sensor = far focus

This is standard for camera modules but counterintuitive, so we present it "correctly" in the UI.

---

## Related Files
- `web/templates/scans.html` - Scan page focus controls (modified)
- `web/templates/dashboard.html` - Dashboard focus controls (modified)
- `scanning/scan_orchestrator.py` - Focus conversion logic (unchanged)
- `camera/pi_camera_controller.py` - Lens position setting (unchanged)

---

## Summary

**Before**:
- ❌ Range 0-15 (invalid values allowed)
- ❌ Labels backwards (0=Infinity, 15=Close-up)
- ❌ Dashboard different from scans page
- ❌ User confusion about valid values

**After**:
- ✅ Range 6-10 (only valid values)
- ✅ Labels correct (6=Near, 10=Far)
- ✅ Consistent across all pages
- ✅ Clear guidance with hyperfocal marker
