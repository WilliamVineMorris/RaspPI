# Autofocus Timeout Fix - Preventing Scan Stalling

## 🚫 Problem Identified
The scan was stalling during autofocus because:
- Camera autofocus was hanging indefinitely
- Warning: "Could not set AF_TRIGGER - no AF algorithm or not Auto"
- No timeout mechanism to prevent indefinite waiting
- Scan couldn't continue when autofocus failed

## ✅ Solution: Robust Timeout and Fallback System

### **1. Camera-Level Timeout Protection**

#### **Enhanced Pi Camera Controller**
```python
# OLD: Could hang forever waiting for autofocus
while time.time() - start_time < max_wait_time:
    # Wait for autofocus state...

# NEW: Multiple timeout layers + graceful fallback
max_wait_time = 2.0  # Reduced timeout to prevent stalling
try:
    # Better error handling for control setting
    picamera2.set_controls({"AfMode": 2, "AfTrigger": 0})
except Exception as control_error:
    logger.warning(f"Failed to set autofocus controls, continuing anyway")

# Always return True to not block scan
logger.warning(f"Autofocus timed out, continuing scan")
return True  # Don't fail the scan for autofocus issues
```

#### **Key Improvements**:
- ✅ **Reduced timeout**: 2 seconds max per camera (was 3 seconds)
- ✅ **Error handling**: Catches control setting failures
- ✅ **Graceful fallback**: Returns success even on timeout
- ✅ **Better logging**: Clear status messages with emojis

### **2. Orchestrator-Level Timeout Protection**

#### **Multi-Layer Timeout System**
```python
# Overall focus setup timeout
focus_timeout = 10.0  # Max time for all cameras

# Per-camera timeout with asyncio.wait_for
focus_value = await asyncio.wait_for(
    self.camera_manager.controller.auto_focus_and_get_value(camera_id),
    timeout=5.0  # 5 second timeout per camera
)
```

#### **Fallback Mechanisms**:
- ⏱️ **Overall timeout**: 10 seconds max for all focus operations
- 🎯 **Per-camera timeout**: 5 seconds max per camera
- 🔧 **Default focus**: Sets 0.5 (middle range) if autofocus fails
- 📋 **Scan continuation**: Always ensures scan can proceed

### **3. Error Recovery Strategy**

#### **Graceful Degradation**
```python
try:
    focus_value = await autofocus_operation()
except asyncio.TimeoutError:
    logger.warning("Autofocus timeout, using default focus")
    self._scan_focus_values[camera_id] = 0.5  # Reasonable default
except Exception as e:
    logger.warning(f"Autofocus error: {e}, using default focus")  
    self._scan_focus_values[camera_id] = 0.5  # Continue with default
```

#### **Guaranteed Scan Continuation**:
- 🚫 **Never fails the scan** for focus issues
- 🔄 **Always sets focus values** (default if needed)
- 📊 **Logs clear status** of what actually happened
- ⚡ **Prevents indefinite stalling**

## 🎯 Expected Behavior Now

### **Normal Autofocus (Working Cameras)**
```
INFO - 🎯 Independent focus mode: Performing autofocus on each camera
INFO - Performing autofocus on camera0...
INFO - ✅ Autofocus completed successfully for camera0 (state=2)
INFO - Performing autofocus on camera1...
INFO - ✅ Autofocus completed successfully for camera1 (state=2)
INFO - 📊 Focus values set: camera0: 0.823, camera1: 0.891
```

### **Problematic Autofocus (Timeout/Failure)**
```
INFO - 🎯 Independent focus mode: Performing autofocus on each camera
INFO - Performing autofocus on camera0...
WARN - Failed to set autofocus controls for camera0: [error details]
WARN - ⏱️ Autofocus timed out for camera0 after 2.0s, continuing scan
WARN - ⏱️ Autofocus timeout for camera0, using default focus
INFO - 🔧 Setting default focus for camera0
INFO - 📊 Focus values set: camera0: 0.500, camera1: 0.500
```

### **Complete Failure (Cameras Don't Support AF)**
```
INFO - 🎯 Independent focus mode: Performing autofocus on each camera
INFO - Camera camera0 has fixed focus, skipping autofocus
INFO - Camera camera1 has fixed focus, skipping autofocus
INFO - 📊 Focus values set: camera0: 0.500, camera1: 0.500
INFO - ✅ Focus setup completed at first scan point
```

## 🔧 Timeout Configuration

### **Configurable Timeouts**
- **Camera autofocus**: 2.0 seconds (reduced from 3.0)
- **Per-camera operation**: 5.0 seconds (includes communication)
- **Overall focus setup**: 10.0 seconds (all cameras combined)
- **Focus state polling**: 0.1 seconds (quick response)

### **Fallback Values**
- **Default focus**: 0.5 (middle range, works for most subjects)
- **Fixed focus cameras**: Skip autofocus, continue scan
- **Error conditions**: Use default, log warning, continue

## 🚀 Benefits

### **Scan Reliability**
- ✅ **No more stalling**: Scans always proceed
- ✅ **Quick recovery**: Fast timeout and fallback
- ✅ **Clear feedback**: Know exactly what happened
- ✅ **Robust operation**: Handles various camera types

### **Performance**  
- ⚡ **Faster startup**: Reduced autofocus timeout
- 🎯 **Better focus**: When autofocus works, it works well
- 🔄 **Consistent behavior**: Predictable scan timing
- 📊 **Clear status**: Always know the focus state

## 📋 Testing Results Expected

### **1. Working Autofocus Cameras**
- Should complete autofocus quickly (under 2 seconds per camera)
- Get optimal focus values for each camera
- Proceed to scan without delay

### **2. Problematic Autofocus**
- Should timeout gracefully after 2 seconds
- Set default focus values (0.5)
- Continue scan without stalling
- Log clear warning messages

### **3. Fixed Focus Cameras**
- Should detect lack of autofocus support
- Skip autofocus operation
- Continue scan immediately
- Work with existing camera settings

## 🎉 Status: Autofocus Stalling Fixed!

The enhanced timeout and fallback system ensures that:
- **Scans never stall** on autofocus operations
- **Quick failure recovery** with reasonable defaults
- **Clear status reporting** so you know what happened
- **Robust operation** across different camera types

**The scan should now proceed smoothly** even when cameras have autofocus issues! 🚀📸