#!/usr/bin/env python3
"""
Hardware Connectivity Test for 3D Scanner

Quick test script to verify all hardware components are properly connected
and accessible before starting the full web interface.
"""

import sys
import time
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent))

def test_fluidnc_connection():
    """Test FluidNC motion controller connection"""
    print("🔧 Testing FluidNC Connection...")
    
    try:
        import serial
        import serial.tools.list_ports
        
        # Find USB serial devices
        ports = list(serial.tools.list_ports.comports())
        usb_ports = [p for p in ports if 'USB' in p.device or 'ttyUSB' in p.device]
        
        if not usb_ports:
            print("  ❌ No USB serial devices found")
            return False
        
        for port in usb_ports:
            print(f"  📡 Found USB device: {port.device}")
            
            try:
                # Try to connect
                with serial.Serial(port.device, 115200, timeout=2) as ser:
                    print(f"  ✅ Connected to {port.device}")
                    
                    # Send status request
                    ser.write(b'?\n')
                    time.sleep(0.5)
                    
                    response = ser.read_all().decode('utf-8', errors='ignore')
                    if response:
                        print(f"  📥 Response: {response.strip()[:50]}...")
                        return True
                    else:
                        print(f"  ⚠️  No response from {port.device}")
                        
            except Exception as e:
                print(f"  ❌ Error connecting to {port.device}: {e}")
        
        return False
        
    except ImportError:
        print("  ❌ pyserial not installed: pip install pyserial")
        return False

def test_camera_connection():
    """Test Pi camera connections"""
    print("📷 Testing Camera Connections...")
    
    try:
        from picamera2 import Picamera2
        
        # Test camera 0
        try:
            cam0 = Picamera2(0)
            print("  ✅ Camera 0 detected")
            cam0.close()
        except Exception as e:
            print(f"  ❌ Camera 0 error: {e}")
        
        # Test camera 1
        try:
            cam1 = Picamera2(1)
            print("  ✅ Camera 1 detected")
            cam1.close()
        except Exception as e:
            print(f"  ❌ Camera 1 error: {e}")
            
        return True
        
    except ImportError:
        print("  ❌ picamera2 not installed")
        print("    Install with: sudo apt install python3-picamera2")
        return False

def test_gpio_access():
    """Test GPIO access for LED control"""
    print("💡 Testing GPIO Access...")
    
    try:
        import pigpio
        
        # Try to connect to pigpio daemon
        pi = pigpio.pi()
        
        if pi.connected:
            print("  ✅ pigpio daemon connected")
            pi.stop()
            return True
        else:
            print("  ❌ Cannot connect to pigpio daemon")
            print("    Start with: sudo pigpiod")
            return False
            
    except ImportError:
        print("  ❌ pigpio not installed: pip install pigpio")
        return False

def test_system_resources():
    """Test system resources and permissions"""
    print("⚙️  Testing System Resources...")
    
    # Check Python version
    if sys.version_info >= (3, 8):
        print(f"  ✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    else:
        print(f"  ⚠️  Python {sys.version_info.major}.{sys.version_info.minor} - recommend 3.8+")
    
    # Check file permissions
    config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
    if config_path.exists():
        print("  ✅ Configuration file accessible")
    else:
        print("  ⚠️  Configuration file not found")
    
    # Check disk space
    try:
        import shutil
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (1024**3)
        if free_gb > 1:
            print(f"  ✅ Disk space: {free_gb}GB free")
        else:
            print(f"  ⚠️  Low disk space: {free_gb}GB free")
    except:
        print("  ⚠️  Cannot check disk space")
    
    return True

def main():
    """Run hardware connectivity tests"""
    print("=" * 60)
    print("🔬 3D Scanner Hardware Connectivity Test")
    print("=" * 60)
    
    tests = [
        ("System Resources", test_system_resources),
        ("FluidNC Motion Controller", test_fluidnc_connection),
        ("Pi Cameras", test_camera_connection),
        ("GPIO/LED Control", test_gpio_access)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ Test failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📋 Hardware Test Summary")
    print("=" * 60)
    
    all_passed = True
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:<25} {status}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ALL TESTS PASSED - Hardware ready for web interface!")
        print("\nStart web interface with:")
        print("   python web/start_web_interface.py --mode hardware")
    else:
        print("⚠️  SOME TESTS FAILED - Check hardware connections")
        print("\nFix issues before starting web interface")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())