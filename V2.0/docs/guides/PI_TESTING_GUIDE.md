# Pi Hardware Testing Guide

This guide explains how to test your V2.0 modular scanner framework on the Raspberry Pi before proceeding with development.

## Quick Start

Run the comprehensive test suite:
```bash
python run_pi_tests.py
```

## Test Scripts Overview

### 1. `run_pi_tests.py` - Master Test Runner
**Purpose**: Runs all tests with comprehensive reporting
**Usage**:
```bash
# Run all tests
python run_pi_tests.py

# Quick test (no hardware interaction)
python run_pi_tests.py --quick

# Skip specific components
python run_pi_tests.py --skip-motion --skip-camera

# Verbose output
python run_pi_tests.py --verbose
```

### 2. `test_motion_only.py` - Motion Controller Testing
**Purpose**: Tests FluidNC motion controller communication
**Usage**:
```bash
# Basic motion tests
python test_motion_only.py

# Different serial port
python test_motion_only.py --port /dev/ttyACM0

# Interactive testing (sends actual commands!)
python test_motion_only.py --interactive
```

### 3. `test_camera_simple.py` - Camera Testing
**Purpose**: Tests Pi camera detection and capture
**Usage**:
```bash
# Basic camera tests
python test_camera_simple.py

# No actual capture (safer)
python test_camera_simple.py --no-capture

# Verbose output
python test_camera_simple.py --verbose
```

### 4. `test_pi_hardware.py` - Comprehensive Testing
**Purpose**: Full hardware validation with detailed reporting
**Usage**:
```bash
# Full hardware test
python test_pi_hardware.py

# Mock hardware mode
python test_pi_hardware.py --mock-hardware

# Dry run (no actual commands)
python test_pi_hardware.py --dry-run
```

## Pre-Testing Setup

### 1. Dependencies Installation
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python dependencies
pip install -r requirements.txt

# Install Pi-specific packages
pip install picamera2
sudo apt install python3-picamera2

# Enable camera interface
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
```

### 2. Hardware Connections
- **FluidNC Controller**: Connect via USB (typically `/dev/ttyUSB0` or `/dev/ttyACM0`)
- **Pi Cameras**: Connect ribbon cables to CSI ports 0 and 1
- **Power**: Ensure adequate power supply for Pi and peripherals

### 3. Permissions Setup
```bash
# Add user to dialout group for serial access
sudo usermod -a -G dialout $USER

# Reboot to apply changes
sudo reboot
```

## Testing Workflow

### Step 1: Quick Validation
```bash
# Test core system without hardware
python run_pi_tests.py --quick
```
**Expected**: All core module imports and basic functionality should pass.

### Step 2: Motion Controller Testing
```bash
# Test motion controller connection
python test_motion_only.py --verbose
```
**Expected**: 
- ✅ Controller creation successful
- ✅ Position validation working
- ✅ Hardware connection (if FluidNC connected)
- ⚠️ Connection warnings normal if hardware not connected

### Step 3: Camera Testing
```bash
# Test camera detection and initialization
python test_camera_simple.py --no-capture --verbose
```
**Expected**:
- ✅ picamera2 library available (on Pi)
- ✅ Camera detection (number of cameras found)
- ✅ Controller initialization
- ⚠️ Warnings normal if cameras not connected

### Step 4: Full Hardware Testing
```bash
# Comprehensive test with actual hardware
python run_pi_tests.py --verbose
```
**Expected**: Comprehensive report showing status of all components.

## Troubleshooting

### Motion Controller Issues
**Problem**: "Could not connect to FluidNC"
**Solutions**:
- Check USB connection and cable
- Verify FluidNC is powered on
- Try different serial port: `--port /dev/ttyACM0`
- Check permissions: `ls -la /dev/ttyUSB*`

**Problem**: "Permission denied on /dev/ttyUSB0"
**Solutions**:
```bash
sudo usermod -a -G dialout $USER
sudo reboot
```

### Camera Issues
**Problem**: "picamera2 library not available"
**Solutions**:
```bash
pip install picamera2
sudo apt install python3-picamera2
```

**Problem**: "No cameras detected"
**Solutions**:
- Check ribbon cable connections
- Enable camera: `sudo raspi-config`
- Reboot after enabling cameras
- Check camera status: `vcgencmd get_camera`

**Problem**: "Camera initialization failed"
**Solutions**:
- Ensure no other processes using cameras
- Check camera compatibility with Pi model
- Try single camera first

### General Issues
**Problem**: "Module import errors"
**Solutions**:
- Verify all files copied to Pi
- Check Python path and working directory
- Install missing dependencies: `pip install -r requirements.txt`

## Test Results Interpretation

### ✅ All Tests Pass
- Hardware setup is correct
- Ready to proceed with development
- All modules functional

### ⚠️ Partial Pass (Hardware Warnings)
- Core system working
- Some hardware not connected (normal for development)
- Can proceed with software testing

### ❌ Core Test Failures
- Module import issues
- Missing dependencies
- Need to resolve before proceeding

## Interactive Testing

For advanced users who want to test actual hardware movement:

```bash
# CAUTION: This sends real commands to hardware!
python test_motion_only.py --interactive
```

**Interactive Menu Options**:
1. Get current status
2. Get current position  
3. Test home axis (specify axis)
4. Test jog movement (small movement)
5. Send custom G-code
6. Emergency stop
7. Exit

**Safety Notes**:
- Ensure clear movement area
- Start with small movements
- Have emergency stop ready
- Only use if FluidNC is properly configured

## Next Steps

After successful testing:
1. **All tests pass**: Ready for next development phase
2. **Core tests pass**: Can proceed with software development 
3. **Hardware issues**: Address connection problems before continuing

The test results will guide you on whether your Pi setup is ready for the next development phase or if hardware issues need to be resolved first.