# Independent Camera Focus System - Implementation Summary

## 🎯 Problem Solved
**Issue**: Camera 1 was out of focus because the system was only autofocusing camera 0 and copying that value to camera 1, which doesn't account for:
- Different optical characteristics between cameras
- Slight positioning differences
- Individual lens variations
- Distance variations to the subject

## ✅ Solution: Independent Autofocus System

### **Key Improvements**

#### 1. **Independent Autofocus by Default**
- Each camera now performs its own autofocus operation
- Camera 0 and Camera 1 get individually optimized focus values
- No assumption that both cameras need the same focus setting

#### 2. **Flexible Focus Modes**
- **Independent Mode** (Default): Each camera autofocuses individually
- **Synchronized Mode**: Camera 0 autofocuses, value copied to Camera 1
- **Manual Individual**: Set different focus values per camera
- **Manual Unified**: Set same focus value for both cameras

#### 3. **Enhanced Web API**
- `/api/scan/focus/sync` - Enable/disable synchronization
- `/api/scan/focus/individual` - Set per-camera focus values
- Updated `/api/scan/focus/settings` - Returns detailed focus info

### **Expected Behavior Now**

#### During Scan Start:
```
1. Home system
2. Move to first scan position
3. 🎯 Independent autofocus mode activated
4. Camera 0 performs autofocus → gets optimal focus value (e.g., 0.823)
5. Camera 1 performs autofocus → gets optimal focus value (e.g., 0.891)  
6. Both cameras now properly focused on the object
7. Continue scan with individual optimized focus values
```

#### Log Output:
```
INFO - 🎯 Independent focus mode: Performing autofocus on each camera
INFO - Performing autofocus on camera0...
INFO - ✅ Autofocus completed for camera0: 0.823
INFO - Performing autofocus on camera1...  
INFO - ✅ Autofocus completed for camera1: 0.891
INFO - 📊 Independent focus values: camera0: 0.823, camera1: 0.891
INFO - Focus setup completed. Mode: auto, Sync: disabled, Values: camera0: 0.823, camera1: 0.891
```

## 🔧 Technical Implementation

### **Data Structure Changes**
```python
# OLD (single focus value)
self._scan_focus_value = 0.993  # Applied to both cameras

# NEW (per-camera focus values)
self._scan_focus_values = {
    'camera0': 0.823,
    'camera1': 0.891
}
self._focus_sync_enabled = False  # Independent by default
```

### **Focus Setup Logic**
```python
if self._focus_mode == 'auto':
    if self._focus_sync_enabled:
        # Synchronized: camera0 autofocus, copy to camera1
        primary_focus = autofocus(camera0)
        set_focus(camera1, primary_focus)
    else:
        # Independent: each camera autofocuses individually
        for camera_id in cameras:
            focus_value = autofocus(camera_id)
            store_focus(camera_id, focus_value)
```

### **New API Endpoints**

#### **Enable Focus Synchronization**
```bash
curl -X POST http://pi-ip:5000/api/scan/focus/sync \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'  # Independent mode (default)
```

#### **Set Individual Focus Values**
```bash
curl -X POST http://pi-ip:5000/api/scan/focus/individual \
  -H "Content-Type: application/json" \
  -d '{"camera_values": {"camera0": 0.8, "camera1": 0.9}}'
```

#### **Get Focus Status**
```bash
curl http://pi-ip:5000/api/scan/focus/settings
# Returns:
{
  "success": true,
  "data": {
    "focus_mode": "auto",
    "sync_enabled": false,
    "primary_value": null,
    "camera_values": {
      "camera0": 0.823,
      "camera1": 0.891
    }
  }
}
```

## 🚀 Benefits

### **Image Quality**
- ✅ **Both cameras properly focused** on the scan subject
- ✅ **Sharp images from both viewpoints**
- ✅ **No more out-of-focus Camera 1 images**

### **Flexibility**
- 🔄 **Switch between independent and synchronized modes**
- ⚙️ **Manual control for specific use cases**
- 🎛️ **Fine-tune individual camera focus**

### **Future-Proof**
- 📈 **Ready for focus stacking** (multiple focus positions)
- 🔧 **Easy to add new focus algorithms**
- 🎯 **Supports different camera types/lenses**

## 📋 Testing Plan

### **1. Independent Autofocus Test**
- Start a scan with default settings
- Verify both cameras autofocus at first position
- Check that focus values are different for each camera
- Confirm both cameras produce sharp images

### **2. Synchronized Mode Test**
```bash
# Enable sync mode
curl -X POST http://pi-ip:5000/api/scan/focus/sync -d '{"enabled": true}'

# Start scan - should see identical focus values
```

### **3. Manual Individual Focus Test**
```bash
# Set different focus for each camera
curl -X POST http://pi-ip:5000/api/scan/focus/individual \
  -d '{"camera_values": {"camera0": 0.7, "camera1": 0.8}}'
```

## 🎉 Status: Ready for Pi Testing!

The enhanced focus system is now implemented and should resolve the Camera 1 focus issue. Both cameras will now get properly focused on the actual scan object at the first position, resulting in sharp images from both viewpoints throughout the entire scan.

**Please test this on the Pi hardware** to verify both cameras now focus properly on the scan object! 🎯📸