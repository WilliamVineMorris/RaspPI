#!/usr/bin/env python3
"""
Simple hardware check - find FluidNC port and verify cameras
"""

import os
import sys
from pathlib import Path
import serial.tools.list_ports

def check_serial_ports():
    """Check for available serial ports"""
    print("🔌 Checking Serial Ports...")
    
    ports = list(serial.tools.list_ports.comports())
    print(f"📡 Found {len(ports)} serial ports:")
    
    usb_ports = []
    for port in ports:
        print(f"   • {port.device}: {port.description}")
        if 'USB' in port.device or 'ACM' in port.device or 'ttyUSB' in port.device:
            usb_ports.append(port.device)
            print(f"     → Potential FluidNC port: {port.device}")
    
    if usb_ports:
        print(f"✅ Found {len(usb_ports)} potential FluidNC ports")
        return usb_ports[0]  # Return first USB port
    else:
        print("❌ No USB serial ports found")
        print("💡 Connect FluidNC via USB and try again")
        return None

def check_cameras():
    """Check camera availability using libcamera"""
    print("\n📷 Checking Cameras...")
    
    try:
        # Use libcamera-hello to test cameras
        result = os.system("libcamera-hello --list-cameras > /tmp/camera_check.txt 2>&1")
        
        if os.path.exists("/tmp/camera_check.txt"):
            with open("/tmp/camera_check.txt", "r") as f:
                output = f.read()
            
            if "Available cameras" in output:
                lines = output.split('\n')
                camera_count = 0
                for line in lines:
                    if ": " in line and "imx" in line.lower() or "arducam" in line.lower():
                        camera_count += 1
                        print(f"   ✅ Found camera: {line.strip()}")
                
                if camera_count > 0:
                    print(f"✅ Total cameras available: {camera_count}")
                    return True
                else:
                    print("❌ No cameras detected in libcamera output")
                    return False
            else:
                print("❌ No cameras found by libcamera")
                print("Output:", output[:200])
                return False
        else:
            print("❌ Could not check cameras")
            return False
            
    except Exception as e:
        print(f"❌ Camera check error: {e}")
        return False

def update_config_port(fluidnc_port):
    """Update config file with correct FluidNC port"""
    print(f"\n🔧 Updating config with FluidNC port: {fluidnc_port}")
    
    config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
    
    if not config_file.exists():
        print("❌ Config file not found")
        return False
    
    try:
        # Read config
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Replace port line
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            if 'port: "/dev/tty' in line:
                indent = line[:len(line) - len(line.lstrip())]
                updated_lines.append(f'{indent}port: "{fluidnc_port}"  # Auto-detected')
                print(f"   Updated: {line.strip()} → port: \"{fluidnc_port}\"")
            else:
                updated_lines.append(line)
        
        # Write back
        with open(config_file, 'w') as f:
            f.write('\n'.join(updated_lines))
        
        print("✅ Config updated successfully")
        return True
        
    except Exception as e:
        print(f"❌ Config update failed: {e}")
        return False

def main():
    """Main hardware check"""
    print("🚀 Hardware Connection Check")
    print("=" * 40)
    
    # Check serial ports
    fluidnc_port = check_serial_ports()
    
    # Check cameras  
    cameras_ok = check_cameras()
    
    # Update config if FluidNC port found
    if fluidnc_port:
        update_config_port(fluidnc_port)
    
    print(f"\n📊 Hardware Summary:")
    print(f"   • FluidNC: {'✅ Port found' if fluidnc_port else '❌ No port found'}")
    print(f"   • Cameras: {'✅ Available' if cameras_ok else '❌ Not available'}")
    
    if fluidnc_port and cameras_ok:
        print("\n🎉 Hardware ready!")
        print("✅ Start web interface:")
        print("   python3 run_web_interface_fixed.py --mode production")
    elif fluidnc_port or cameras_ok:
        print("\n⚠️  Partial hardware available")
        print("🔧 Web interface will work with available hardware")
        print("   python3 run_web_interface_fixed.py --mode production")
    else:
        print("\n❌ Hardware issues detected")
        print("💡 Check connections:")
        print("   • Connect FluidNC via USB")
        print("   • Ensure cameras are properly connected")
        print("   • Try: lsusb and libcamera-hello --list-cameras")

if __name__ == "__main__":
    main()