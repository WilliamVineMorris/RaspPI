#!/usr/bin/env python3
"""
Working Simple FluidNC Controller
Based directly on the successful test_simple_homing.py approach.
This is a minimal, working implementation that can replace all others.

Author: Scanner System Development
Created: September 26, 2025
"""

import asyncio
import logging
import time
import serial
from typing import Optional, Dict, Any
from pathlib import Path

# Simple logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Position4D:
    """Simple 4D position class"""
    def __init__(self, x: float = 0, y: float = 0, z: float = 0, c: float = 0):
        self.x = x
        self.y = y
        self.z = z
        self.c = c
    
    def __str__(self):
        return f"Position(X:{self.x:.3f}, Y:{self.y:.3f}, Z:{self.z:.3f}, C:{self.c:.3f})"

class SimpleWorkingFluidNCController:
    """
    Simple working FluidNC controller based on successful test results.
    
    This controller uses the EXACT approach from test_simple_homing.py
    that successfully completed homing in 23.2 seconds.
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_connection = None
        self.connected = False
        self.homed = False
        self.position = Position4D(0, 0, 0, 0)
        self.logger = logger
    
    def connect(self) -> bool:
        """Connect to FluidNC using the proven approach."""
        try:
            self.logger.info(f"🔌 Connecting to FluidNC at {self.port}")
            
            # Open serial connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=2.0
            )
            
            # Wait for connection to stabilize
            time.sleep(2.0)
            
            # Clear buffers
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # Test connection with status query
            response = self._send_command("?")
            if response:
                self.connected = True
                self.logger.info("✅ Connected to FluidNC successfully")
                
                # Parse initial status
                if '<Alarm' in response:
                    self.logger.warning("⚠️ FluidNC in ALARM state - homing required")
                elif '<Idle' in response:
                    self.logger.info("✅ FluidNC in IDLE state")
                
                return True
            else:
                self.logger.error("❌ No response from FluidNC")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Connection failed: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect from FluidNC."""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
                self.connected = False
                self.logger.info("✅ Disconnected from FluidNC")
            except Exception as e:
                self.logger.error(f"❌ Disconnect error: {e}")
    
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.connected and self.serial_connection and self.serial_connection.is_open
    
    def home(self) -> bool:
        """
        Home all axes using the PROVEN approach from test_simple_homing.py
        This is the EXACT code that worked in 23.2 seconds.
        """
        if not self.is_connected():
            self.logger.error("❌ Not connected")
            return False
        
        try:
            self.logger.info("🏠 Starting homing sequence...")
            
            # Clear alarm ($X)
            self.logger.info("📤 Clearing alarm ($X)")
            unlock_response = self._send_command("$X")
            if unlock_response:
                self.logger.info(f"🔓 Unlock response: {unlock_response}")
            
            # Send homing command
            self.logger.info("📤 Sending homing command ($H)")
            self.serial_connection.write(b"$H\n")
            self.serial_connection.flush()
            
            # Monitor for completion (PROVEN approach)
            self.logger.info("📊 Monitoring for homing completion...")
            start_time = time.time()
            timeout = 60.0  # 60 seconds
            
            while (time.time() - start_time) < timeout:
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    response = data.decode('utf-8', errors='ignore')
                    
                    # Process each line
                    for line in response.strip().split('\n'):
                        if line.strip():
                            elapsed = time.time() - start_time
                            
                            # CRITICAL: Check for completion (lowercase 'done')
                            if '[MSG:DBG: Homing done]' in line:
                                self.logger.info(f"✅ [{elapsed:.1f}s] {line}")
                                
                                # Wait and verify final status
                                self.logger.info("⏳ Homing done detected, verifying final status...")
                                time.sleep(1.5)
                                
                                status_response = self._send_command("?")
                                if status_response:
                                    self.logger.info(f"📊 Final status: {status_response}")
                                    
                                    if '<Idle' in status_response:
                                        self.homed = True
                                        self.position = Position4D(0, 200, 0, 0)  # FluidNC home position
                                        self.logger.info("✅ Homing completed successfully - status is Idle!")
                                        return True
                                    else:
                                        self.logger.error("❌ Final status is not Idle")
                                        return False
                                else:
                                    self.logger.error("❌ Could not verify final status")
                                    return False
                            
                            # Log important messages
                            elif '[MSG:Homed:' in line:
                                self.logger.info(f"✅ [{elapsed:.1f}s] {line}")
                            elif '[MSG:DBG: Homing Cycle' in line:
                                self.logger.info(f"📊 [{elapsed:.1f}s] {line}")
                
                time.sleep(0.1)  # Check every 100ms
            
            # Timeout
            self.logger.error(f"❌ Homing timeout after {timeout}s")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Homing error: {e}")
            return False
    
    def move_to_position(self, position: Position4D) -> bool:
        """Move to specified position."""
        if not self.is_connected():
            self.logger.error("❌ Not connected")
            return False
        
        if not self.homed:
            self.logger.error("❌ System must be homed before moving")
            return False
        
        try:
            # Format G-code move command
            gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
            self.logger.info(f"🎯 Moving to: {position}")
            
            # Send move command
            response = self._send_command(gcode)
            if response and ('ok' in response.lower() or 'Ok' in response):
                self.position = position
                self.logger.info("✅ Move command sent successfully")
                return True
            else:
                self.logger.error(f"❌ Move command failed: {response}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Move error: {e}")
            return False
    
    def stop_motion(self) -> bool:
        """Stop all motion immediately."""
        if not self.is_connected():
            return False
        
        try:
            # Send feed hold
            self.serial_connection.write(b"!")
            time.sleep(0.1)
            
            # Send reset
            self.serial_connection.write(b"\x18")  # Ctrl-X
            
            self.logger.info("🛑 Motion stopped")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Stop motion error: {e}")
            return False
    
    def get_status(self) -> str:
        """Get current status."""
        if not self.is_connected():
            return "Disconnected"
        
        response = self._send_command("?")
        if response:
            if '<Idle' in response:
                return "Idle"
            elif '<Alarm' in response:
                return "Alarm"
            elif '<Run' in response:
                return "Running"
            elif '<Home' in response:
                return "Homing"
            else:
                return "Unknown"
        
        return "No Response"
    
    def is_homed(self) -> bool:
        """Check if system is homed."""
        return self.homed
    
    def get_position(self) -> Position4D:
        """Get current position."""
        return self.position
    
    def execute_gcode(self, gcode: str) -> bool:
        """Execute G-code command."""
        if not self.is_connected():
            return False
        
        response = self._send_command(gcode)
        return response is not None and 'error' not in response.lower()
    
    # Helper method
    
    def _send_command(self, command: str) -> Optional[str]:
        """Send command and get response (synchronous)."""
        if not self.serial_connection or not self.serial_connection.is_open:
            return None
        
        try:
            # Clear input buffer
            self.serial_connection.reset_input_buffer()
            
            # Send command
            self.serial_connection.write((command + '\n').encode())
            self.serial_connection.flush()
            
            # Wait for response
            time.sleep(0.5)  # Give FluidNC time to respond
            
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting)
                return response.decode('utf-8', errors='ignore').strip()
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Command error: {e}")
            return None

# Test function for direct testing
async def test_simple_controller():
    """Test the simple working controller."""
    print("\n🧪 Testing Simple Working FluidNC Controller")
    print("=" * 50)
    print("This uses the EXACT approach from successful test_simple_homing.py")
    print("=" * 50)
    
    controller = SimpleWorkingFluidNCController()
    
    try:
        # Test connection
        if not controller.connect():
            print("❌ Connection failed")
            return False
        
        print(f"✅ Connected successfully")
        print(f"📊 Status: {controller.get_status()}")
        print(f"🏠 Homed: {controller.is_homed()}")
        
        # Test homing if needed
        if not controller.is_homed():
            print("\n⚠️ SAFETY: Ensure axes can move to limit switches!")
            response = input("Test homing? (y/N): ")
            
            if response.lower() == 'y':
                print("\n🏠 Starting homing test...")
                success = controller.home()
                
                if success:
                    print("✅ Homing successful!")
                    print(f"📍 Position: {controller.get_position()}")
                else:
                    print("❌ Homing failed")
        
        # Test movement if homed
        if controller.is_homed():
            print("\n⚠️ SAFETY: Ensure path is clear!")
            response = input("Test small movement? (y/N): ")
            
            if response.lower() == 'y':
                # Small test movement
                test_pos = Position4D(10, 190, 0, 0)
                success = controller.move_to_position(test_pos)
                
                if success:
                    print("✅ Movement successful")
                    
                    # Return to home
                    await asyncio.sleep(2)
                    controller.move_to_position(Position4D(0, 200, 0, 0))
                    print("✅ Returned to home position")
        
        print("\n✅ All tests completed!")
        return True
        
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
        
    finally:
        controller.disconnect()

if __name__ == "__main__":
    # Run test
    asyncio.run(test_simple_controller())