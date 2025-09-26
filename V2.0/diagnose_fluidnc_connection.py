#!/usr/bin/env python3
"""
FluidNC Connection Diagnostic Tool

Tests FluidNC communication with detailed debugging to identify timeout issues.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import serial
import serial.tools.list_ports
import logging
from motion.simplified_fluidnc_protocol_fixed import SimplifiedFluidNCProtocolFixed

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def find_fluidnc_ports():
    """Find all potential FluidNC serial ports"""
    print("🔍 Scanning for FluidNC devices...")
    
    ports = serial.tools.list_ports.comports()
    fluidnc_ports = []
    
    for port in ports:
        print(f"  📱 Found port: {port.device}")
        print(f"     Description: {port.description}")
        print(f"     VID:PID: {port.vid}:{port.pid}")
        print(f"     Manufacturer: {port.manufacturer}")
        
        # Check for FluidNC indicators
        if any(indicator in str(port.description).lower() for indicator in ['usb', 'serial', 'ch340', 'cp210', 'ftdi']):
            fluidnc_ports.append(port.device)
            print(f"     ✅ Potential FluidNC device")
        else:
            print(f"     ❌ Unlikely FluidNC device")
        print()
    
    return fluidnc_ports

def test_raw_serial_connection(port, baudrate=115200):
    """Test raw serial connection without protocol layer"""
    print(f"🔌 Testing raw serial connection: {port} at {baudrate} baud")
    
    try:
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=2.0,
            write_timeout=2.0,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        
        print(f"✅ Serial port opened successfully")
        print(f"   Port: {ser.name}")
        print(f"   Baudrate: {ser.baudrate}")
        print(f"   Timeout: {ser.timeout}")
        
        # Clear any existing data
        ser.reset_input_buffer()
        ser.reset_output_buffer()
        time.sleep(0.1)
        
        # Test basic command
        test_commands = ['?', '$I', '$$']
        
        for cmd in test_commands:
            print(f"\n📤 Sending: '{cmd}'")
            ser.write(f"{cmd}\n".encode('utf-8'))
            ser.flush()
            
            # Wait for response
            start_time = time.time()
            response_lines = []
            
            while (time.time() - start_time) < 3.0:
                if ser.in_waiting > 0:
                    try:
                        line = ser.readline().decode('utf-8').strip()
                        if line:
                            response_lines.append(line)
                            print(f"📥 Response: '{line}'")
                            
                            # Check for completion indicators
                            if line in ['ok', 'error', 'alarm'] or line.startswith('['):
                                break
                    except Exception as e:
                        print(f"❌ Error reading response: {e}")
                        break
                time.sleep(0.01)
            
            if not response_lines:
                print(f"❌ No response to '{cmd}' after 3 seconds")
            else:
                print(f"✅ Got {len(response_lines)} response lines")
        
        ser.close()
        return True
        
    except Exception as e:
        print(f"❌ Failed to open serial port: {e}")
        return False

def test_fluidnc_protocol(port):
    """Test FluidNC protocol layer"""
    print(f"\n🔧 Testing FluidNC Protocol Layer: {port}")
    
    try:
        protocol = SimplifiedFluidNCProtocolFixed(
            port=port,
            baudrate=115200,
            command_timeout=5.0  # Reduced timeout for testing
        )
        
        if not protocol.connect():
            print("❌ Failed to connect to FluidNC")
            return False
        
        print("✅ Protocol connected successfully")
        
        # Test status query
        print("\n📊 Testing status query...")
        success, response = protocol.send_command("?", priority="high")
        if success:
            print(f"✅ Status query successful: {response}")
        else:
            print(f"❌ Status query failed: {response}")
        
        # Test info query  
        print("\n📋 Testing info query...")
        success, response = protocol.send_command("$I", priority="high")
        if success:
            print(f"✅ Info query successful: {response}")
        else:
            print(f"❌ Info query failed: {response}")
        
        protocol.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Protocol test failed: {e}")
        return False

def main():
    """Main diagnostic routine"""
    print("🔧 FluidNC Connection Diagnostic Tool")
    print("=" * 50)
    
    # Find potential ports
    ports = find_fluidnc_ports()
    
    if not ports:
        print("❌ No potential FluidNC ports found!")
        print("   Check USB connection and drivers")
        return
    
    print(f"📱 Found {len(ports)} potential FluidNC ports: {ports}")
    
    # Test each port
    for port in ports:
        print(f"\n{'='*50}")
        print(f"🔍 Testing port: {port}")
        print('='*50)
        
        # Test raw serial
        if test_raw_serial_connection(port):
            # Test protocol layer
            test_fluidnc_protocol(port)
        
        print(f"\n{'='*50}")
        
    print(f"\n✅ Diagnostic complete!")
    print("💡 If all tests fail:")
    print("   1. Check FluidNC power and USB cable")  
    print("   2. Verify correct USB drivers installed")
    print("   3. Try different baud rates (9600, 38400, 115200)")
    print("   4. Check FluidNC firmware is running")

if __name__ == "__main__":
    main()