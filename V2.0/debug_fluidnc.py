#!/usr/bin/env python3
"""
FluidNC Communication Diagnostic Tool

Test FluidNC connection and communication independently
to isolate hardware connectivity issues.

Usage:
    python debug_fluidnc.py [port]
    python debug_fluidnc.py /dev/ttyUSB0

Author: Scanner System Development
Created: September 2025
"""

import sys
import time
import serial
import serial.tools.list_ports
from pathlib import Path


def list_serial_ports():
    """List all available serial ports"""
    print("🔍 Available Serial Ports:")
    ports = serial.tools.list_ports.comports()
    
    if not ports:
        print("   No serial ports found")
        return []
    
    for port in ports:
        print(f"   {port.device}: {port.description}")
        if port.hwid:
            print(f"      Hardware ID: {port.hwid}")
    
    return [port.device for port in ports]


def test_serial_connection(port: str, baudrate: int = 115200):
    """Test basic serial connection"""
    print(f"\n🔌 Testing Serial Connection: {port} @ {baudrate}")
    
    try:
        # Open connection
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=3.0,
            write_timeout=3.0
        )
        
        print(f"   ✅ Serial connection opened successfully")
        print(f"   Port: {ser.port}")
        print(f"   Baudrate: {ser.baudrate}")
        print(f"   Timeout: {ser.timeout}")
        
        # Wait for device startup
        print("   ⏳ Waiting for device startup (3s)...")
        time.sleep(3.0)
        
        # Clear any existing data
        if ser.in_waiting > 0:
            startup_data = ser.read(ser.in_waiting)
            print(f"   📥 Startup data received: {startup_data}")
        
        return ser
        
    except serial.SerialException as e:
        print(f"   ❌ Serial connection failed: {e}")
        return None
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return None


def test_fluidnc_communication(ser: serial.Serial):
    """Test FluidNC communication with various commands"""
    print(f"\n💬 Testing FluidNC Communication:")
    
    test_commands = [
        ("$", "Get settings/version"),
        ("?", "Get status"),
        ("$X", "Unlock/Clear alarm"),
        ("$H", "Home all axes"),
        ("G21", "Set units to mm"),
        ("G90", "Set absolute positioning"),
        ("M114", "Get current position")
    ]
    
    for command, description in test_commands:
        print(f"\n   📤 Sending: '{command}' ({description})")
        
        try:
            # Send command
            command_bytes = f"{command}\n".encode('utf-8')
            ser.write(command_bytes)
            ser.flush()
            
            # Wait for response
            time.sleep(0.5)
            
            # Read response
            response = ""
            start_time = time.time()
            while (time.time() - start_time) < 2.0:  # 2 second timeout
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                    response += data
                    
                    # Check for common FluidNC response endings
                    if any(ending in response for ending in ['ok', 'error', '>', 'Grbl']):
                        break
                time.sleep(0.1)
            
            if response.strip():
                print(f"   📥 Response: {repr(response.strip())}")
                
                # Check for FluidNC/Grbl indicators
                if 'Grbl' in response or 'FluidNC' in response:
                    print(f"   ✅ FluidNC/Grbl detected!")
                elif 'ok' in response.lower():
                    print(f"   ✅ Command acknowledged")
                elif 'error' in response.lower():
                    print(f"   ⚠️  Command error")
                else:
                    print(f"   ℹ️  Response received")
            else:
                print(f"   ❌ No response (timeout)")
        
        except Exception as e:
            print(f"   ❌ Communication error: {e}")


def test_specific_device(port: str):
    """Test specific device at given port"""
    print(f"\n🧪 Testing Device: {port}")
    print("=" * 50)
    
    # Test connection
    ser = test_serial_connection(port)
    if not ser:
        return False
    
    try:
        # Test communication
        test_fluidnc_communication(ser)
        return True
        
    finally:
        ser.close()
        print(f"\n🔒 Serial connection closed")


def auto_detect_fluidnc():
    """Try to auto-detect FluidNC device"""
    print(f"\n🔍 Auto-detecting FluidNC device...")
    
    ports = serial.tools.list_ports.comports()
    
    # Try common FluidNC/Arduino identifiers
    candidates = []
    for port in ports:
        description = (port.description or '').lower()
        if any(identifier in description for identifier in 
               ['fluidnc', 'esp32', 'arduino', 'usb serial', 'ch340', 'cp210']):
            candidates.append(port.device)
            print(f"   🎯 Candidate: {port.device} ({port.description})")
    
    if not candidates:
        print(f"   ⚠️  No obvious FluidNC candidates found")
        # Try all USB serial ports as fallback
        candidates = [port.device for port in ports 
                     if 'usb' in (port.description or '').lower()]
    
    # Test each candidate
    for port in candidates:
        print(f"\n   🧪 Testing candidate: {port}")
        if test_basic_connectivity(port):
            return port
    
    return None


def test_basic_connectivity(port: str):
    """Quick connectivity test"""
    try:
        ser = serial.Serial(port, 115200, timeout=1.0)
        time.sleep(1.0)
        
        # Send simple command
        ser.write(b"?\n")
        ser.flush()
        time.sleep(0.5)
        
        response = ""
        if ser.in_waiting > 0:
            response = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
        
        ser.close()
        
        # Check for any response
        if response.strip():
            print(f"      📥 Quick response: {repr(response.strip()[:50])}")
            return True
        else:
            print(f"      ❌ No response")
            return False
            
    except Exception as e:
        print(f"      ❌ Connection failed: {e}")
        return False


def main():
    """Main diagnostic function"""
    print("🔧 FluidNC Communication Diagnostic Tool")
    print("=" * 50)
    
    # List all ports
    available_ports = list_serial_ports()
    
    if len(sys.argv) > 1:
        # Test specific port
        port = sys.argv[1]
        if port not in available_ports and available_ports:
            print(f"\n⚠️  Warning: {port} not in available ports list")
        test_specific_device(port)
    else:
        # Auto-detect
        detected_port = auto_detect_fluidnc()
        if detected_port:
            print(f"\n🎉 FluidNC detected at: {detected_port}")
            test_specific_device(detected_port)
        else:
            print(f"\n❌ No FluidNC device detected")
            
            if available_ports:
                print(f"\n📋 Available ports to test manually:")
                for port in available_ports:
                    print(f"   python debug_fluidnc.py {port}")


if __name__ == "__main__":
    main()