#!/usr/bin/env python3
"""
FluidNC Motor Power Diagnostic Tool

Check motor enable status and power supply connectivity.
Helps diagnose why homing sequences hang.

Usage:
    python debug_motors.py
    python debug_motors.py --test-enable
    python debug_motors.py --test-power

Author: Scanner System Development
Created: September 2025
"""

import sys
import asyncio
import time
import serial
import serial.tools.list_ports
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


class MotorDiagnostics:
    """Diagnostic tools for FluidNC motor power issues"""
    
    def __init__(self, port='/dev/ttyUSB0', baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None
    
    async def connect(self):
        """Connect to FluidNC"""
        try:
            self.serial_connection = serial.Serial(
                self.port, 
                self.baudrate, 
                timeout=2.0
            )
            await asyncio.sleep(1.0)  # Allow connection to stabilize
            
            # Clear any buffered data
            self.serial_connection.flushInput()
            self.serial_connection.flushOutput()
            
            print(f"✅ Connected to FluidNC on {self.port}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            return False
    
    async def send_command(self, command: str, wait_for_ok=True):
        """Send command and get response"""
        if not self.serial_connection:
            raise Exception("Not connected")
        
        try:
            # Send command
            full_command = command + '\n'
            self.serial_connection.write(full_command.encode())
            
            # Read response
            response_lines = []
            start_time = time.time()
            
            while time.time() - start_time < 5.0:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode().strip()
                    if line:
                        response_lines.append(line)
                        if wait_for_ok and (line == 'ok' or line.startswith('error:')):
                            break
                        elif not wait_for_ok and line.startswith('<'):
                            break
                else:
                    await asyncio.sleep(0.1)
            
            return response_lines
            
        except Exception as e:
            print(f"❌ Command failed: {e}")
            return []
    
    async def check_system_status(self):
        """Check overall system status"""
        print("\n🔍 Checking System Status")
        print("=" * 40)
        
        # Get status
        status_lines = await self.send_command('?', wait_for_ok=False)
        
        for line in status_lines:
            if line.startswith('<'):
                print(f"Status: {line}")
                
                # Parse status for key information
                if 'Alarm' in line:
                    print("⚠️  System is in ALARM state")
                    print("   This prevents motor movement")
                    return 'alarm'
                elif 'Idle' in line:
                    print("✅ System is IDLE - ready for commands")
                    return 'idle'
                elif 'Home' in line:
                    print("🏠 System is HOMING")
                    return 'homing'
                else:
                    print("❓ Unknown system state")
                    return 'unknown'
        
        print("❌ No status response received")
        return 'no_response'
    
    async def check_motor_enable_settings(self):
        """Check motor enable settings in FluidNC"""
        print("\n⚙️  Checking Motor Enable Settings")
        print("=" * 40)
        
        # Check stepper enable settings
        enable_commands = [
            '$Stepper/Enable/Delay_us',
            '$Stepper/Disable/Delay_us', 
            '$Stepper/Enable/Invert'
        ]
        
        for cmd in enable_commands:
            response = await self.send_command(cmd)
            if response:
                print(f"{cmd}: {' '.join(response)}")
            else:
                print(f"{cmd}: No response")
        
        # Check individual axis enable pins
        axis_commands = [
            '$X/Motor/Enable_Pin',
            '$Y/Motor/Enable_Pin',
            '$Z/Motor/Enable_Pin', 
            '$C/Motor/Enable_Pin'
        ]
        
        for cmd in axis_commands:
            response = await self.send_command(cmd)
            if response:
                print(f"{cmd}: {' '.join(response)}")
            else:
                print(f"{cmd}: No response")
    
    async def test_motor_enable(self):
        """Test motor enable functionality"""
        print("\n🔧 Testing Motor Enable")
        print("=" * 40)
        
        # First unlock if in alarm
        status = await self.check_system_status()
        if status == 'alarm':
            print("🔓 Unlocking system...")
            await self.send_command('$X')
            await asyncio.sleep(0.5)
        
        # Try to enable steppers manually
        print("🔌 Attempting to enable steppers...")
        
        # Some FluidNC variants use M17 to enable steppers
        response = await self.send_command('M17')
        if response:
            print(f"M17 response: {' '.join(response)}")
        
        # Check if status changed
        await asyncio.sleep(0.5)
        new_status = await self.check_system_status()
        
        return new_status == 'idle'
    
    async def test_small_movement(self):
        """Test very small movement to check if motors respond"""
        print("\n🎯 Testing Small Movement")
        print("=" * 40)
        
        # Ensure system is ready
        status = await self.check_system_status()
        if status != 'idle':
            print("❌ System not ready for movement")
            return False
        
        print("⚠️  CAUTION: About to move motors!")
        print("   Make sure machine is safe to move")
        
        # Wait for user confirmation in real scenario
        await asyncio.sleep(2)
        
        # Try very small relative movement
        print("📐 Attempting 1mm relative movement on X-axis...")
        
        # Set to relative mode and move 1mm
        await self.send_command('G91')  # Relative positioning
        await self.send_command('G1 X1 F100')  # Move 1mm at slow speed
        
        # Wait and check if movement happened
        await asyncio.sleep(2)
        
        # Return to absolute mode
        await self.send_command('G90')
        
        # Check final status
        final_status = await self.check_system_status()
        return final_status == 'idle'
    
    async def diagnose_power_supply(self):
        """Check for power supply related issues"""
        print("\n⚡ Power Supply Diagnostics")
        print("=" * 40)
        
        # Check if we can get voltage readings (if available)
        voltage_commands = [
            '$Report/Build',
            '$Report/VerboseErrors'
        ]
        
        for cmd in voltage_commands:
            response = await self.send_command(cmd)
            if response:
                print(f"{cmd}:")
                for line in response:
                    print(f"  {line}")
        
        print("\n💡 Power Supply Checklist:")
        print("  1. ✓ Check external power supply is connected (12V/24V)")
        print("  2. ✓ Check power LED on FluidNC board")
        print("  3. ✓ Check stepper driver LED indicators")
        print("  4. ✓ Verify ground connections")
        print("  5. ✓ Check enable pin wiring")
    
    def close(self):
        """Close serial connection"""
        if self.serial_connection:
            self.serial_connection.close()
            print("🔌 Disconnected from FluidNC")


async def main():
    """Main diagnostic routine"""
    print("🔧 FluidNC Motor Power Diagnostic Tool")
    print("=" * 50)
    
    # Detect FluidNC port
    ports = list(serial.tools.list_ports.comports())
    fluidnc_port = None
    
    for port in ports:
        if 'USB' in port.device or 'ttyUSB' in port.device:
            fluidnc_port = port.device
            break
    
    if not fluidnc_port:
        print("❌ No USB serial device found")
        print("   Check FluidNC USB connection")
        return
    
    print(f"🔍 Found potential FluidNC at: {fluidnc_port}")
    
    # Initialize diagnostics
    diagnostics = MotorDiagnostics(fluidnc_port)
    
    try:
        # Connect
        if not await diagnostics.connect():
            return
        
        # Run diagnostic sequence
        print("\n🔬 Running Motor Power Diagnostics...")
        
        # 1. Check system status
        status = await diagnostics.check_system_status()
        
        # 2. Check motor enable settings
        await diagnostics.check_motor_enable_settings()
        
        # 3. Test motor enable
        enable_success = await diagnostics.test_motor_enable()
        
        # 4. Power supply diagnostics
        await diagnostics.diagnose_power_supply()
        
        # 5. Small movement test (if enabled)
        if '--test-movement' in sys.argv:
            movement_success = await diagnostics.test_small_movement()
        else:
            print("\n⚠️  Skipping movement test (use --test-movement to enable)")
            movement_success = None
        
        # Summary
        print("\n📊 Diagnostic Summary")
        print("=" * 30)
        print(f"System Status: {status}")
        print(f"Enable Test: {'✅ PASS' if enable_success else '❌ FAIL'}")
        if movement_success is not None:
            print(f"Movement Test: {'✅ PASS' if movement_success else '❌ FAIL'}")
        
        # Recommendations
        print("\n💡 Recommendations:")
        if status == 'alarm':
            print("  • System in alarm - check endstops and safety systems")
        if not enable_success:
            print("  • Motor enable failed - check power supply and enable pins")
            print("  • Verify stepper driver power connections")
            print("  • Check FluidNC configuration for enable pins")
        
    except Exception as e:
        print(f"❌ Diagnostic failed: {e}")
    
    finally:
        diagnostics.close()


if __name__ == "__main__":
    asyncio.run(main())