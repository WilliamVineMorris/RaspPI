# 3D Scanner Hardware Test Guide

## 🚀 Quick Start for Hardware Testing

### 1. **Pre-Test Setup**
```bash
cd ~/Documents/RaspPI/V2.0
python test_hardware_connectivity.py
```

### 2. **Start Hardware Web Interface**
```bash
# Method 1: Use setup script
python web/hardware_test_setup.py
python start_hardware_interface.py

# Method 2: Direct start
python web/start_web_interface.py --mode hardware --debug
```

### 3. **Access Web Interface**
- **Local**: http://localhost:5000
- **Network**: http://192.168.1.138:5000 (replace with Pi IP)

## 🔧 Hardware Requirements Checklist

### **Motion Control (FluidNC)**
- ✅ FluidNC board connected via USB
- ✅ USB device appears as `/dev/ttyUSB0`
- ✅ Baud rate: 115200
- ✅ G-code communication working

### **Cameras (Dual Pi Cameras)**
- ✅ Primary camera on port 0
- ✅ Secondary camera on port 1  
- ✅ libcamera interface active
- ✅ Both cameras sync-capable

### **LED Lighting (GPIO PWM)**
- ✅ GPIO pins connected to LED drivers
- ✅ pigpio daemon running (`sudo pigpiod`)
- ✅ PWM duty cycle limited to 90%
- ✅ Emergency shutdown capable

### **System Resources**
- ✅ Python 3.8+ 
- ✅ Free disk space >1GB
- ✅ Network connectivity
- ✅ Proper file permissions

## 📋 Test Sequence

### **Phase 1: Connectivity Verification**
1. Run hardware connectivity test
2. Verify all components detected
3. Check communication protocols

### **Phase 2: Web Interface Testing**
1. Start web interface in hardware mode
2. Navigate through all pages:
   - Dashboard (status monitoring)
   - Manual Control (motion testing)
   - Scan Management (operation testing)
   - Settings (configuration)

### **Phase 3: Component Testing**
1. **Motion Control**:
   - Test axis movements (X, Y, Z, C)
   - Verify position feedback
   - Test safety limits

2. **Camera System**:
   - Test individual camera feeds
   - Verify dual-camera sync
   - Test capture operations

3. **LED Control**:
   - Test individual LED zones
   - Verify PWM control
   - Test safety shutdowns

## ⚠️ Safety Considerations

### **Motion Safety**
- Always test in open area
- Verify emergency stop works
- Check axis travel limits
- Monitor for mechanical binding

### **Electrical Safety**  
- Verify GPIO voltage levels
- Check LED current limits
- Monitor temperature levels
- Test emergency shutdowns

### **Software Safety**
- Validate input ranges
- Test error handling
- Verify communication timeouts
- Check status monitoring

## 🐛 Troubleshooting

### **Common Issues**

**FluidNC not detected:**
```bash
ls /dev/ttyUSB*  # Check USB devices
sudo dmesg | tail  # Check system logs
```

**Cameras not working:**
```bash
libcamera-still --list-cameras  # List cameras
sudo raspi-config  # Enable camera interface
```

**GPIO access denied:**
```bash
sudo pigpiod  # Start pigpio daemon
sudo usermod -a -G gpio $USER  # Add user to gpio group
```

**Web interface errors:**
```bash
# Check logs
tail -f /var/log/scanner.log

# Check port availability
netstat -tulpn | grep :5000
```

## 📊 Expected Test Results

### **Successful Hardware Test Output:**
```
🔬 3D Scanner Hardware Connectivity Test
========================================
System Resources:        ✅ PASS
FluidNC Motion Controller: ✅ PASS  
Pi Cameras:              ✅ PASS
GPIO/LED Control:        ✅ PASS

🎉 ALL TESTS PASSED - Hardware ready for web interface!
```

### **Successful Web Interface Startup:**
```
🔬 3D Scanner Web Interface
Mode: hardware
🚀 Starting web interface on http://0.0.0.0:5000
✅ FluidNC controller connected
✅ Cameras initialized
✅ GPIO lighting ready
✅ All systems operational
```

## 📞 Support

If hardware tests fail:
1. Check all physical connections
2. Verify power supplies
3. Review system logs
4. Test components individually
5. Consult hardware documentation

Ready for hardware testing! 🚀