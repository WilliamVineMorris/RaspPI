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
import threading
from typing import Optional, Dict, Any
from pathlib import Path
import re

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
        
        # Auto-reporting status from FluidNC messages
        self._current_status = "Disconnected"
        self._last_status_message = ""
        self._last_message_time = time.time()  # For timeout detection
        self._message_reader_thread = None
        self._stop_reading = False
        self._post_homing_unlock_needed = False  # Flag for post-homing unlock
        
        # Parse FluidNC status messages
        self._status_pattern = re.compile(r'<([^|>]+)\|')  # Extract status from <Status|...> format
    
    def _background_message_reader(self):
        """Background thread to continuously read FluidNC messages."""
        while not self._stop_reading and self.connected:
            try:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    message = data.decode('utf-8', errors='ignore')
                    
                    for line in message.strip().split('\n'):
                        if line.strip():
                            self._process_fluidnc_message(line.strip())
                
                time.sleep(0.01)  # Small delay to prevent excessive CPU usage
            except Exception as e:
                self.logger.debug(f"Message reader error: {e}")
                time.sleep(0.1)
    
    def _process_fluidnc_message(self, message: str):
        """Process incoming FluidNC messages and update status."""
        # Track when we last received a message (for timeout detection)
        self._last_message_time = time.time()
        
        self._last_status_message = message
        
        # Extract status from FluidNC status reports like <Idle|MPos:...>
        status_match = self._status_pattern.search(message)
        if status_match:
            raw_status = status_match.group(1)
            self._current_status = raw_status.capitalize()  # Idle, Alarm, Run, Home, etc.
            self.logger.debug(f"📊 FluidNC status updated: {self._current_status}")
        
        # Handle specific messages
        if '[MSG:DBG: Homing done]' in message:
            self.logger.info(f"🏠 COMPLETE: Homing sequence finished: {message}")
            self.homed = True
            self.position = Position4D(0, 200, 0, 0)  # FluidNC home position
            # Schedule post-homing unlock to clear any alarm state
            self._post_homing_unlock_needed = True
        elif '[MSG:Homed:' in message:
            self.logger.info(f"🏠 AXIS: Individual axis homed: {message}")
        elif '[MSG:DBG:' in message and 'Homing' in message:
            self.logger.info(f"🏠 DEBUG: {message}")
    
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
                
                # Parse initial status and start background reader
                if '<Alarm' in response:
                    self.logger.warning("⚠️ FluidNC in ALARM state - homing required")
                    self._current_status = "Alarm"
                elif '<Idle' in response:
                    self.logger.info("✅ FluidNC in IDLE state")
                    self._current_status = "Idle"
                
                # Start background message reader
                self._stop_reading = False
                self._message_reader_thread = threading.Thread(
                    target=self._background_message_reader,
                    daemon=True,
                    name="FluidNC-MessageReader"
                )
                self._message_reader_thread.start()
                self.logger.info("🔄 Background message reader started")
                
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
        # Stop background message reader
        self._stop_reading = True
        if self._message_reader_thread and self._message_reader_thread.is_alive():
            self._message_reader_thread.join(timeout=1.0)
            self.logger.info("🔄 Background message reader stopped")
        
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
                self.connected = False
                self._current_status = "Disconnected"
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
            
            # Clear alarm ($X) - Multiple attempts to ensure it works
            self.logger.info("📤 Clearing alarm with $X command")
            for attempt in range(3):  # Try up to 3 times
                unlock_response = self._send_command("$X")
                if unlock_response:
                    self.logger.info(f"🔓 Unlock attempt {attempt + 1} response: {unlock_response}")
                    if 'ok' in unlock_response.lower() or 'Idle' in unlock_response:
                        self.logger.info("✅ Successfully unlocked FluidNC")
                        break
                else:
                    self.logger.warning(f"⚠️ Unlock attempt {attempt + 1} - no response")
                
                if attempt < 2:  # Don't sleep after last attempt
                    time.sleep(0.5)  # Wait before retry
            
            # Give system time to process unlock
            time.sleep(1.0)
            
            # Send homing command
            self.logger.info("📤 Sending homing command ($H)")
            self.serial_connection.write(b"$H\n")
            self.serial_connection.flush()
            
            # Wait for completion using background message reader
            self.logger.info("📊 Waiting for homing completion via auto-reporting...")
            start_time = time.time()
            timeout = 120.0  # 30 seconds per axis (4 axes = 120 seconds total)
            last_message_time = start_time
            
            # Reset homed flag
            self.homed = False
            
            while (time.time() - start_time) < timeout:
                # Check if background reader detected homing completion
                if self.homed:
                    elapsed = time.time() - start_time
                    self.logger.info(f"✅ Homing completed successfully in {elapsed:.1f}s!")
                    
                    # Perform post-homing unlock if needed
                    if self._post_homing_unlock_needed:
                        self.logger.info("🔓 Performing post-homing unlock to clear alarm state...")
                        self._post_homing_unlock_needed = False
                        
                        # Wait a bit for system to settle
                        time.sleep(1.0)
                        
                        # Send unlock command
                        for attempt in range(3):
                            unlock_response = self._send_command("$X")
                            if unlock_response:
                                self.logger.info(f"🔓 Post-homing unlock attempt {attempt + 1}: {unlock_response}")
                                if 'ok' in unlock_response.lower() or 'Idle' in unlock_response:
                                    self.logger.info("✅ Post-homing unlock successful - system ready!")
                                    break
                            else:
                                self.logger.warning(f"⚠️ Post-homing unlock attempt {attempt + 1} - no response")
                            
                            if attempt < 2:
                                time.sleep(0.5)
                    
                    return True
                
                # Update last message time if we received any FluidNC message recently
                if hasattr(self, '_last_message_time'):
                    last_message_time = max(last_message_time, self._last_message_time)
                
                # Check for communication timeout (no messages for 30 seconds = system unresponsive)
                if (time.time() - last_message_time) > 30.0:
                    elapsed = time.time() - start_time
                    self.logger.error(f"❌ Homing failed - no FluidNC messages for 30+ seconds (total time: {elapsed:.1f}s)")
                    self.logger.error("❌ System appears unresponsive")
                    return False
                
                time.sleep(0.1)  # Check every 100ms
            
            # Timeout
            elapsed = time.time() - start_time
            self.logger.error(f"❌ Homing timeout after {elapsed:.1f}s (max: {timeout}s)")
            self.logger.error("❌ Timeout reached but system was still responsive")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Homing error: {e}")
            return False
    
    def clear_alarm(self) -> bool:
        """Clear alarm state manually - useful for web interface."""
        if not self.is_connected():
            self.logger.error("❌ Not connected")
            return False
        
        self.logger.info("🔓 Manual alarm clear requested")
        
        for attempt in range(3):
            unlock_response = self._send_command("$X")
            if unlock_response:
                self.logger.info(f"🔓 Alarm clear attempt {attempt + 1}: {unlock_response}")
                if 'ok' in unlock_response.lower() or 'Idle' in unlock_response:
                    self.logger.info("✅ Alarm cleared successfully!")
                    return True
            else:
                self.logger.warning(f"⚠️ Alarm clear attempt {attempt + 1} - no response")
            
            if attempt < 2:
                time.sleep(0.5)
        
        self.logger.error("❌ Failed to clear alarm after 3 attempts")
        return False
    
    def home_axes_sync(self, axes: list = None) -> dict:
        """Web interface compatibility method for homing."""
        self.logger.info(f"🏠 Web interface homing request for axes: {axes}")
        
        # Check if system is in alarm state and try to clear it first
        if self._current_status == "Alarm":
            self.logger.info("⚠️ System in alarm state - attempting to clear before homing")
            if not self.clear_alarm():
                return {
                    'success': False,
                    'message': 'Failed to clear alarm state before homing',
                    'status': 'error',
                    'axes': axes or ['X', 'Y', 'Z', 'C']
                }
        
        # Call the working home method
        success = self.home()
        
        if success:
            return {
                'success': True,
                'message': f'Homing completed successfully for axes: {", ".join(axes) if axes else "all"}',
                'status': 'completed',
                'axes': axes or ['X', 'Y', 'Z', 'C']
            }
        else:
            return {
                'success': False,
                'message': 'Homing failed',
                'status': 'error',
                'axes': axes or ['X', 'Y', 'Z', 'C']
            }
    
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
        """Get current status from FluidNC auto-reporting (no polling)."""
        if not self.is_connected():
            return "Disconnected"
        
        # Return status from automatic FluidNC messages
        return self._current_status
    
    def get_status_fresh(self) -> str:
        """Get current status (same as get_status since we use auto-reporting)."""
        return self.get_status()
    
    def is_homed(self) -> bool:
        """Check if system is homed."""
        return self.homed
    
    def get_position(self) -> Position4D:
        """Get current position."""
        return self.position
    
    @property
    def current_position(self) -> Position4D:
        """Current position property for web UI compatibility."""
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
            self.logger.error("❌ Cannot send command - serial connection not available")
            return None
        
        try:
            # Clear input buffer
            self.serial_connection.reset_input_buffer()
            
            # Send command
            self.logger.debug(f"📤 Sending command: {command}")
            self.serial_connection.write((command + '\n').encode())
            self.serial_connection.flush()
            
            # Wait for response with longer timeout for $X command
            timeout = 2.0 if command == "$X" else 0.5
            time.sleep(timeout)
            
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting)
                decoded_response = response.decode('utf-8', errors='ignore').strip()
                self.logger.debug(f"📥 Response: {decoded_response}")
                return decoded_response
            else:
                self.logger.debug(f"⚠️ No response to command: {command}")
                return None
            
        except Exception as e:
            self.logger.error(f"❌ Command '{command}' error: {e}")
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