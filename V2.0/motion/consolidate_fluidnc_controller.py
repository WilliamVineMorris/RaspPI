"""
Consolidated FluidNC Motion Controller
This is the SINGLE working implementation that combines all proven fixes.
Based on successful tests from 2025-09-26.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import serial
import re

from motion.base import MotionController, MotionStatus, Position4D
from core.config_manager import ConfigManager
from core.events import EventBus, Event, EventPriority
from core.exceptions import HardwareError, MotionError

class ConsolidatedFluidNCController(MotionController):
    """
    Consolidated FluidNC controller with all fixes applied.
    
    Key fixes included:
    - Proper homing completion detection (waits for "Homing done")
    - Graceful alarm state handling
    - All abstract methods implemented
    - Simple, proven serial communication
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the consolidated FluidNC controller."""
        super().__init__(config_manager)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Serial connection parameters
        self.port = config_manager.get_hardware_config().get('motion', {}).get('port', '/dev/ttyUSB0')
        self.baudrate = config_manager.get_hardware_config().get('motion', {}).get('baudrate', 115200)
        self.timeout = 2.0
        
        # Connection state
        self.serial_connection = None
        self._connected = False
        self._homed = False
        self._position = Position4D(0, 0, 0, 0)
        self._status = MotionStatus.UNKNOWN
        
        # Event bus
        self.event_bus = EventBus()
        
    def initialize_sync(self) -> bool:
        """Synchronous initialization for compatibility."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        return loop.run_until_complete(self.initialize())
    
    async def initialize(self) -> bool:
        """Initialize the controller and connect to FluidNC."""
        self.logger.info(f"🔌 Connecting to FluidNC at {self.port}")
        
        try:
            # Open serial connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            time.sleep(2)  # Wait for connection to stabilize
            
            # Clear buffers
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # Check status
            response = self._send_command_sync("?")
            if response:
                self._parse_status(response)
                self._connected = True
                
                # Handle alarm state gracefully
                if self._status == MotionStatus.ALARM:
                    self.logger.warning("⚠️ FluidNC in ALARM state - homing required")
                    self.logger.info("💡 Use home() method or web interface to clear alarm")
                
                self.logger.info(f"✅ Connected to FluidNC (status: {self._status})")
                return True
            else:
                self.logger.error("❌ No response from FluidNC")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to connect: {e}")
            self._connected = False
            return False
    
    async def shutdown(self) -> None:
        """Shutdown the controller and close connection."""
        self.logger.info("🔌 Disconnecting from FluidNC")
        
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
            except:
                pass
        
        self._connected = False
        self.logger.info("✅ Disconnected")
    
    def is_connected(self) -> bool:
        """Check if controller is connected."""
        return self._connected and self.serial_connection and self.serial_connection.is_open
    
    async def get_status(self) -> MotionStatus:
        """Get current motion status."""
        if not self.is_connected():
            return MotionStatus.UNKNOWN
            
        response = self._send_command_sync("?")
        if response:
            self._parse_status(response)
        
        return self._status
    
    def get_position(self) -> Position4D:
        """Get current position."""
        return self._position
    
    async def home(self) -> bool:
        """
        Home all axes using the PROVEN simple approach.
        Based on successful test_simple_homing.py
        """
        if not self.is_connected():
            self.logger.error("❌ Not connected")
            return False
        
        self.logger.info("🏠 Starting homing sequence...")
        
        try:
            # Clear alarm if needed
            if self._status == MotionStatus.ALARM:
                self.logger.info("🔓 Clearing alarm state...")
                self._send_command_sync("$X")
                time.sleep(0.5)
            
            # Send homing command
            self.logger.info("📤 Sending homing command ($H)")
            self.serial_connection.write(b"$H\n")
            self.serial_connection.flush()
            
            # Monitor for completion (proven approach)
            self.logger.info("📊 Monitoring for homing completion...")
            start_time = time.time()
            timeout = 60.0  # 60 seconds max for homing
            
            while (time.time() - start_time) < timeout:
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    response = data.decode('utf-8', errors='ignore')
                    
                    # Log progress
                    for line in response.strip().split('\n'):
                        if line:
                            elapsed = time.time() - start_time
                            
                            # Check for completion (CRITICAL: lowercase 'done')
                            if '[MSG:DBG: Homing done]' in line:
                                self.logger.info(f"✅ [{elapsed:.1f}s] Homing completed!")
                                
                                # Wait a moment and verify status
                                time.sleep(1.5)
                                status_response = self._send_command_sync("?")
                                if status_response and '<Idle' in status_response:
                                    self._homed = True
                                    self._position = Position4D(0, 0, 0, 0)
                                    self._status = MotionStatus.IDLE
                                    self.logger.info("✅ Homing successful - system ready")
                                    return True
                            
                            # Log important messages
                            elif '[MSG:Homed:' in line:
                                self.logger.info(f"✅ [{elapsed:.1f}s] {line}")
                            elif '[MSG:DBG: Homing Cycle' in line:
                                self.logger.info(f"🔄 [{elapsed:.1f}s] {line}")
                
                time.sleep(0.1)  # Check every 100ms
            
            self.logger.error(f"❌ Homing timeout after {timeout}s")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Homing error: {e}")
            return False
    
    async def move_to_position(self, position: Position4D) -> bool:
        """Move to specified position."""
        if not self.is_connected():
            return False
        
        # Validate position
        if not self.validate_position(position):
            self.logger.error(f"❌ Invalid position: {position}")
            return False
        
        # Format G-code command
        gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
        
        # Send command
        response = self._send_command_sync(gcode)
        if response and 'ok' in response.lower():
            self._position = position
            return True
        
        return False
    
    async def stop_motion(self) -> bool:
        """Stop all motion immediately."""
        if not self.is_connected():
            return False
        
        # Send feed hold
        self.serial_connection.write(b"!")
        time.sleep(0.1)
        
        # Then reset
        self.serial_connection.write(b"\x18")  # Ctrl-X
        
        self._status = MotionStatus.IDLE
        self.logger.info("🛑 Motion stopped")
        return True
    
    async def set_feed_rate(self, rate: float) -> bool:
        """Set feed rate override percentage."""
        if not self.is_connected():
            return False
        
        # Clamp rate to valid range
        rate = max(10, min(200, rate))
        
        # Send feed rate override
        response = self._send_command_sync(f"F{rate}")
        return response is not None
    
    def is_homed(self) -> bool:
        """Check if system is homed."""
        return self._homed
    
    async def emergency_stop(self) -> None:
        """Trigger emergency stop."""
        self.logger.warning("🚨 EMERGENCY STOP")
        
        if self.serial_connection and self.serial_connection.is_open:
            # Send reset immediately
            self.serial_connection.write(b"\x18")  # Ctrl-X
            
        self._status = MotionStatus.ALARM
        self._homed = False
        
        # Notify via event bus
        await self.event_bus.publish(Event(
            type="emergency_stop",
            source="motion_controller",
            priority=EventPriority.CRITICAL
        ))
    
    async def clear_alarm(self) -> bool:
        """Clear alarm state."""
        if not self.is_connected():
            return False
        
        response = self._send_command_sync("$X")
        if response:
            time.sleep(0.5)
            await self.get_status()
            return self._status != MotionStatus.ALARM
        
        return False
    
    async def execute_gcode(self, gcode: str) -> bool:
        """Execute arbitrary G-code command."""
        if not self.is_connected():
            return False
        
        response = self._send_command_sync(gcode)
        return response is not None and 'error' not in response.lower()
    
    async def wait_for_motion_complete(self, timeout: float = 30.0) -> bool:
        """Wait for current motion to complete."""
        if not self.is_connected():
            return False
        
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            status = await self.get_status()
            
            if status == MotionStatus.IDLE:
                return True
            elif status == MotionStatus.ALARM:
                return False
            
            await asyncio.sleep(0.1)
        
        return False
    
    # Helper methods
    
    def _send_command_sync(self, command: str) -> Optional[str]:
        """Send command and wait for response (synchronous)."""
        if not self.serial_connection or not self.serial_connection.is_open:
            return None
        
        try:
            # Clear input buffer
            self.serial_connection.reset_input_buffer()
            
            # Send command
            self.serial_connection.write((command + '\n').encode())
            self.serial_connection.flush()
            
            # Wait for response
            time.sleep(0.1)
            response = ""
            wait_time = 0
            
            while wait_time < 2.0:  # 2 second timeout
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    response += data.decode('utf-8', errors='ignore')
                    
                    # Check if we have a complete response
                    if 'ok' in response or 'error' in response or '>' in response:
                        break
                
                time.sleep(0.05)
                wait_time += 0.05
            
            return response if response else None
            
        except Exception as e:
            self.logger.error(f"Command error: {e}")
            return None
    
    def _parse_status(self, response: str):
        """Parse status response from FluidNC."""
        if '<Alarm' in response:
            self._status = MotionStatus.ALARM
        elif '<Idle' in response:
            self._status = MotionStatus.IDLE
        elif '<Run' in response or '<Jog' in response:
            self._status = MotionStatus.MOVING
        elif '<Home' in response or '<Homing' in response:
            self._status = MotionStatus.HOMING
        elif '<Hold' in response:
            self._status = MotionStatus.IDLE
        else:
            self._status = MotionStatus.UNKNOWN
        
        # Parse position if available
        match = re.search(r'MPos:([-\d.]+),([-\d.]+),([-\d.]+)', response)
        if match:
            try:
                x = float(match.group(1))
                y = float(match.group(2))
                z = float(match.group(3))
                # C axis might not be in status
                self._position = Position4D(x, y, z, self._position.c)
            except:
                pass