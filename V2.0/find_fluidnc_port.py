#!/usr/bin/env python3
"""
FluidNC Port Detection Script

Automatically detect which port FluidNC is connected to by testing common ports.

Usage:
    python find_fluidnc_port.py

Author: Scanner System Development  
Created: September 2025
"""

import serial
import serial.tools.list_ports
import time
import sys
import asyncio

def list_all_ports():
    """List all available serial ports"""
    print("🔍 Available Serial Ports:")
    ports = list(serial.tools.list_ports.comports())
    
    if not ports:
        print("   No serial ports found")
        return []
    
    for port in ports:
        print(f"   {port.device}: {port.description}")
        if port.hwid:
            print(f"     Hardware ID: {port.hwid}")
        print()
    
    return [port.device for port in ports]

def test_port_basic(port_name, baudrate=115200, timeout=3):
    """Test if a port responds like FluidNC"""
    try:
        print(f"   Testing {port_name} at {baudrate} baud...")
        
        # Open serial connection
        ser = serial.Serial(port_name, baudrate, timeout=timeout)
        time.sleep(1)  # Let it settle
        
        # Clear any existing data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        
        # Try to get FluidNC status
        test_commands = [
            b'?\r\n',           # Status query
            b'$$\r\n',          # Settings query  
            b'$I\r\n',          # Build info
            b'$X\r\n'           # Clear alarm (safe)
        ]
        
        responses = []
        for cmd in test_commands:
            ser.write(cmd)
            time.sleep(0.5)
            
            response = b''
            start_time = time.time()
            while time.time() - start_time < 2:
                if ser.in_waiting > 0:
                    chunk = ser.read(ser.in_waiting)
                    response += chunk
                    if b'\n' in chunk:
                        break
                time.sleep(0.1)
            
            if response:
                responses.append(response.decode('utf-8', errors='ignore').strip())
        
        ser.close()
        
        # Check if responses look like FluidNC/GRBL
        fluidnc_indicators = ['fluidnc', 'grbl', 'ok', 'idle', 'run', 'hold', 'alarm']
        response_text = ' '.join(responses).lower()
        
        matches = [indicator for indicator in fluidnc_indicators if indicator in response_text]
        
        if matches:
            print(f"   ✅ {port_name} responds like FluidNC/GRBL!")
            print(f"      Detected keywords: {matches}")
            if responses:
                print(f"      Sample response: {responses[0][:100]}...")
            return True, responses
        else:
            print(f"   ❓ {port_name} responds but doesn't look like FluidNC")
            if responses:
                print(f"      Response: {responses[0][:50]}...")
            return False, responses
            
    except serial.SerialException as e:
        print(f"   ❌ {port_name} failed: {e}")
        return False, None
    except Exception as e:
        print(f"   ❌ {port_name} error: {e}")
        return False, None

def find_fluidnc_port():
    """Find FluidNC port automatically"""
    print("🔍 FluidNC Port Detection")
    print("=" * 50)
    
    # List all ports first
    available_ports = list_all_ports()
    
    if not available_ports:
        print("❌ No serial ports found. Check USB connections.")
        return None
    
    print(f"\n🧪 Testing {len(available_ports)} ports for FluidNC...")
    
    # Test common FluidNC ports first
    priority_ports = ['/dev/ttyUSB0', '/dev/ttyACM0', '/dev/ttyUSB1', '/dev/ttyACM1']
    test_ports = []
    
    # Add priority ports that exist
    for port in priority_ports:
        if port in available_ports:
            test_ports.append(port)
    
    # Add remaining ports
    for port in available_ports:
        if port not in test_ports:
            test_ports.append(port)
    
    fluidnc_ports = []
    
    for port in test_ports:
        is_fluidnc, responses = test_port_basic(port)
        if is_fluidnc:
            fluidnc_ports.append((port, responses))
    
    print("\n" + "=" * 50)
    print("📋 RESULTS:")
    
    if fluidnc_ports:
        print(f"✅ Found {len(fluidnc_ports)} FluidNC-like port(s):")
        for port, responses in fluidnc_ports:
            print(f"   • {port}")
            if responses and responses[0]:
                print(f"     Response: {responses[0][:60]}...")
        
        print(f"\n💡 Recommended: Use --port {fluidnc_ports[0][0]} for tests")
        return fluidnc_ports[0][0]
    else:
        print("❌ No FluidNC ports found")
        print("\nTroubleshooting:")
        print("• Check USB cable connection")
        print("• Verify FluidNC is powered on") 
        print("• Try different USB port")
        print("• Check if device is in bootloader mode")
        return None

def main():
    """Main function"""
    try:
        port = find_fluidnc_port()
        
        if port:
            print(f"\n🚀 Test your FluidNC connection:")
            print(f"python test_motion_only.py --port {port} --verbose")
            print(f"python run_pi_tests.py --motion-port {port}")
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()