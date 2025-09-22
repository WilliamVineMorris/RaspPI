"""
FluidNC Motion Controller Implementation

Concrete implementation of the MotionController interface for FluidNC-based
4DOF motion control. Communicates via USB serial using G-code commands.

Hardware Setup:
- FluidNC controller connected via USB (/dev/ttyUSB0)
- 4 axes configured: X (linear), Y (linear), Z (rotational), C (tilt)
- Endstops and limits configured in FluidNC firmware

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import time
import re
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
import serial
import serial.tools.list_ports

from motion.base import (
    MotionController, Position4D, MotionStatus, AxisType,
    MotionLimits, MotionCapabilities
)
from core.exceptions import (
    FluidNCError, FluidNCConnectionError, FluidNCCommandError,
    MotionSafetyError, MotionTimeoutError, MotionControlError
)
from core.events import ScannerEvent, EventPriority
from core.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class FluidNCController(MotionController):
    """
    FluidNC-based motion controller for 4DOF scanner system
    
    Implements the MotionController interface using FluidNC firmware
    over USB serial communication with G-code commands.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Serial connection settings
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baudrate = config.get('baudrate', 115200)
        self.timeout = config.get('timeout', 10.0)
        
        # Serial connection
        self.serial_connection: Optional[serial.Serial] = None
        self.connection_lock = asyncio.Lock()
        
        # Motion state
        self.current_position = Position4D()
        self.target_position = Position4D()
        self.is_homed = False
        self.axis_limits: Dict[str, MotionLimits] = {}
        
        # Communication
        self.command_queue = asyncio.Queue()
        self.response_cache: Dict[str, str] = {}
        self.status_update_interval = 0.1  # seconds
        
        # Load axis configuration from config
        self._load_axis_config()
    
    def _load_axis_config(self):
        """Load axis configuration from system config"""
        try:
            axes_config = self.config.get('axes', {})
            
            # Configure each axis with limits
            axis_configs = {
                'x': axes_config.get('x_axis', {}),
                'y': axes_config.get('y_axis', {}),
                'z': axes_config.get('z_axis', {}),
                'c': axes_config.get('c_axis', {})
            }
            
            for axis_name, axis_config in axis_configs.items():
                self.axis_limits[axis_name] = MotionLimits(
                    min_limit=axis_config.get('min_limit', 0.0),
                    max_limit=axis_config.get('max_limit', 200.0),
                    max_feedrate=axis_config.get('max_feedrate', 1000.0)
                )
            
            logger.info("Loaded axis configuration from system config")
            
        except Exception as e:
            logger.error(f"Failed to load axis config: {e}")
            # Use default limits
            self.axis_limits = {
                'x': MotionLimits(min_limit=0.0, max_limit=200.0, max_feedrate=1000.0),
                'y': MotionLimits(min_limit=0.0, max_limit=200.0, max_feedrate=1000.0),
                'z': MotionLimits(min_limit=-999999.0, max_limit=999999.0, max_feedrate=360.0),
                'c': MotionLimits(min_limit=-90.0, max_limit=90.0, max_feedrate=180.0)
            }
    
    # Connection Management
    async def initialize(self) -> bool:
        """Initialize FluidNC connection and configure axes"""
        try:
            logger.info(f"Initializing FluidNC controller on {self.port}")
            
            # Open serial connection
            if not await self._connect_serial():
                return False
            
            # Wait for FluidNC startup
            await asyncio.sleep(2.0)
            
            # Send initial configuration
            await self._send_startup_commands()
            
            # Get current status
            await self._update_status()
            
            self.status = MotionStatus.IDLE
            self._notify_event("motion_initialized", {
                "port": self.port,
                "status": self.status.value
            })
            
            logger.info("FluidNC controller initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize FluidNC controller: {e}")
            self.status = MotionStatus.ERROR
            return False
    
    async def shutdown(self) -> bool:
        """Shutdown FluidNC connection"""
        try:
            logger.info("Shutting down FluidNC controller")
            
            # Stop any ongoing motion
            if self.status == MotionStatus.MOVING:
                await self.emergency_stop()
            
            # Close serial connection
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.serial_connection = None
            
            self.status = MotionStatus.DISCONNECTED
            self._notify_event("motion_shutdown")
            
            logger.info("FluidNC controller shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"Error during FluidNC shutdown: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if FluidNC is connected"""
        # During initialization, check serial connection first
        # Status might still be DISCONNECTED during setup
        if self.serial_connection and self.serial_connection.is_open:
            # If we're not in an error state, consider connected
            return self.status not in [MotionStatus.ERROR, MotionStatus.EMERGENCY_STOP]
        return False
    
    # Serial Communication
    async def _connect_serial(self) -> bool:
        """Establish serial connection to FluidNC"""
        try:
            # Try to find FluidNC device if port is auto
            if self.port == 'auto':
                detected_port = await self._detect_fluidnc_port()
                if not detected_port:
                    raise FluidNCConnectionError("Could not detect FluidNC device")
                self.port = detected_port
            
            # Open serial connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            
            logger.info(f"Serial connection established: {self.port} @ {self.baudrate}")
            return True
            
        except serial.SerialException as e:
            raise FluidNCConnectionError(f"Serial connection failed: {e}")
        except Exception as e:
            raise FluidNCError(f"Unexpected connection error: {e}")
    
    async def _detect_fluidnc_port(self) -> Optional[str]:
        """Auto-detect FluidNC device port"""
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            # Look for common FluidNC identifiers
            if any(identifier in (port.description or '').lower() for identifier in 
                   ['fluidnc', 'esp32', 'arduino', 'usb serial']):
                logger.info(f"Detected potential FluidNC device: {port.device}")
                return port.device
        
        logger.warning("No FluidNC device detected")
        return None
    
    async def _send_command(self, command: str, wait_for_response: bool = True) -> Optional[str]:
        """Send G-code command to FluidNC"""
        if not self.is_connected():
            raise FluidNCConnectionError("Not connected to FluidNC")
        
        async with self.connection_lock:
            try:
                if not self.serial_connection:
                    raise FluidNCConnectionError("Serial connection not established")
                    
                # Add newline if not present
                if not command.endswith('\n'):
                    command += '\n'
                
                # Send command
                self.serial_connection.write(command.encode('utf-8'))
                self.serial_connection.flush()
                
                logger.debug(f"Sent command: {command.strip()}")
                
                if wait_for_response:
                    response = await self._read_response()
                    logger.debug(f"Received response: {response}")
                    return response
                
                return None
                
            except serial.SerialException as e:
                raise FluidNCCommandError(f"Command transmission failed: {e}")
            except Exception as e:
                raise FluidNCError(f"Unexpected command error: {e}")
    
    async def _read_response(self, timeout_override: Optional[float] = None) -> str:
        """Read response from FluidNC"""
        if not self.serial_connection:
            raise FluidNCConnectionError("Serial connection not established")
            
        response_lines = []
        timeout = timeout_override or self.timeout
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line:
                        response_lines.append(line)
                        
                        # Check for completion indicators
                        if line in ['ok', 'error']:
                            break
                        if line.startswith('error:'):
                            break
                        # Also check for status responses
                        if line.startswith('<') and line.endswith('>'):
                            # This is a status response, it's complete
                            break
                else:
                    await asyncio.sleep(0.01)  # Small delay to prevent busy waiting
            
            response = '\n'.join(response_lines)
            
            # Check for timeout
            if not response:
                logger.warning("No response received within timeout")
                return ""
            
            # Check for errors
            if 'error' in response.lower() and not response.startswith('['):
                # Don't treat informational messages as errors
                raise FluidNCCommandError(f"FluidNC error: {response}")
            
            return response
            
        except asyncio.CancelledError:
            logger.warning("Response reading was cancelled")
            raise
        except Exception as e:
            logger.error(f"Error reading response: {e}")
            raise FluidNCConnectionError(f"Failed to read response: {e}")
    
    async def _send_startup_commands(self):
        """Send initial configuration commands to FluidNC"""
        try:
            # First, check status and clear any alarms
            status_response = await self._send_command('?', wait_for_response=True)
            logger.info(f"Initial status: {status_response}")
            
            # If in alarm state, unlock first
            if status_response and 'Alarm' in status_response:
                logger.info("System in alarm state, unlocking...")
                await self._send_command('$X')  # Unlock
                await asyncio.sleep(0.5)
            
            # Enable stepper motors - critical for movement
            try:
                logger.info("Enabling stepper motors...")
                await self._send_command('M17')  # Enable steppers
                await asyncio.sleep(0.2)
            except FluidNCCommandError as e:
                logger.warning(f"M17 command failed, trying alternative: {e}")
                # Some FluidNC versions may not support M17
            
            # Set basic G-code modes first (these should work even without homing)
            basic_commands = [
                'G90',  # Absolute positioning
                'G21',  # Millimeter units 
                'G94',  # Feed rate per minute
            ]
            
            for command in basic_commands:
                try:
                    await self._send_command(command)
                    await asyncio.sleep(0.1)
                except FluidNCCommandError as e:
                    logger.warning(f"Basic command failed: {command} - {e}")
            
            # Note: Homing ($H) is intentionally NOT done here during initialization
            # It should be done separately via the home() method when needed
            logger.info("Basic FluidNC configuration complete - ready for homing")
            
        except Exception as e:
            logger.error(f"Startup command sequence failed: {e}")
            raise
    
    # Position and Movement
    async def move_to_position(self, position: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move to specified 4DOF position"""
        try:
            # Validate position
            if not self.validate_position(position):
                raise MotionSafetyError(f"Position outside limits: {position}")
            
            # Set status to moving
            self.status = MotionStatus.MOVING
            self.target_position = position
            
            # Build G-code move command
            if feedrate is None:
                feedrate = 1000  # Default feedrate
            
            command = f"G1 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f} F{feedrate}"
            
            # Send move command
            await self._send_command(command)
            
            # Wait for movement completion
            await self._wait_for_movement_complete()
            
            # Update current position
            self.current_position = position
            self.status = MotionStatus.IDLE
            
            self._notify_event("position_reached", {
                "position": position.to_dict(),
                "feedrate": feedrate
            })
            
            logger.info(f"Moved to position: {position}")
            return True
            
        except Exception as e:
            self.status = MotionStatus.ERROR
            logger.error(f"Move to position failed: {e}")
            raise
    
    async def _wait_for_movement_complete(self):
        """Wait for FluidNC to complete current movement"""
        start_time = time.time()
        timeout = 60.0  # 60 second timeout for movements
        
        while time.time() - start_time < timeout:
            # Check status
            status_response = await self._send_command('?')
            
            # Parse status response
            if status_response and 'Idle' in status_response:
                return  # Movement complete
            elif status_response and ('Run' in status_response or 'Jog' in status_response):
                await asyncio.sleep(0.1)  # Still moving
                continue
            elif status_response and 'Alarm' in status_response:
                raise MotionSafetyError("FluidNC in alarm state")
            elif status_response and 'Error' in status_response:
                raise FluidNCCommandError("FluidNC error during movement")
            
            await asyncio.sleep(0.1)
        
        raise MotionTimeoutError("Movement timeout exceeded")
    
    async def get_current_position(self) -> Position4D:
        """Get current 4DOF position from FluidNC"""
        try:
            # Send position query
            response = await self._send_command('?')
            
            # Parse position from status response
            if response:
                position = self._parse_position_from_status(response)
                if position:
                    self.current_position = position
                    return position
            
            # Fallback to cached position
            return self.current_position
            
        except Exception as e:
            logger.error(f"Failed to get current position: {e}")
            return self.current_position
    
    def _parse_position_from_status(self, status_response: str) -> Optional[Position4D]:
        """Parse position from FluidNC status response"""
        try:
            # FluidNC status format: <Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0>
            match = re.search(r'MPos:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)', status_response)
            if match:
                x, y, z, c = map(float, match.groups())
                return Position4D(x=x, y=y, z=z, c=c)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse position from status: {e}")
            return None
    
    # Homing Operations
    async def home_all_axes(self) -> bool:
        """Home all axes to their home positions"""
        try:
            logger.info("Starting homing sequence")
            self.status = MotionStatus.HOMING
            
            # Ensure motors are enabled before homing
            try:
                logger.info("Ensuring motors are enabled...")
                await self._send_command('M17')  # Enable steppers
                await asyncio.sleep(0.5)
            except FluidNCCommandError as e:
                logger.warning(f"Motor enable command failed: {e}")
            
            # Check system status before homing
            status_response = await self._send_command('?', wait_for_response=True)
            logger.info(f"Pre-homing status: {status_response}")
            
            if status_response and 'Alarm' in status_response:
                logger.error("Cannot home - system in alarm state")
                raise MotionSafetyError("System in alarm state before homing")
            
            # Send homing command
            logger.info("Sending homing command...")
            await self._send_command('$H')
            
            # Wait for homing completion with better monitoring
            await self._wait_for_homing_complete()
            
            # Update position to home
            home_position = Position4D(
                x=self.axis_limits['x'].min_limit if 'x' in self.axis_limits else 0.0,
                y=self.axis_limits['y'].min_limit if 'y' in self.axis_limits else 0.0,
                z=0.0,  # Z-axis homes to 0 degrees
                c=0.0   # C-axis homes to 0 degrees
            )
            
            self.current_position = home_position
            self.is_homed = True
            self.status = MotionStatus.IDLE
            
            self._notify_event("homing_complete", {
                "home_position": home_position.to_dict()
            })
            
            logger.info("Homing sequence completed")
            return True
            
        except Exception as e:
            self.status = MotionStatus.ERROR
            logger.error(f"Homing failed: {e}")
            return False
    
    async def _wait_for_homing_complete(self):
        """Wait for homing sequence to complete with better monitoring"""
        start_time = time.time()
        timeout = 120.0  # 2 minute timeout for homing
        last_status = None
        status_unchanged_count = 0
        
        logger.info("Monitoring homing progress...")
        
        while time.time() - start_time < timeout:
            try:
                status_response = await self._send_command('?', wait_for_response=True)
                
                if status_response:
                    # Log status changes
                    if status_response != last_status:
                        logger.info(f"Homing status: {status_response}")
                        last_status = status_response
                        status_unchanged_count = 0
                    else:
                        status_unchanged_count += 1
                    
                    # Check for completion
                    if 'Idle' in status_response:
                        logger.info("Homing completed - system idle")
                        return  # Homing complete
                    elif 'Home' in status_response:
                        await asyncio.sleep(1.0)  # Still homing, check less frequently
                        continue
                    elif 'Alarm' in status_response:
                        raise MotionSafetyError("Alarm during homing - check endstops and motor power")
                    
                    # Detect potential hanging
                    if status_unchanged_count > 30:  # Status unchanged for 30+ checks
                        logger.warning(f"Homing may be hanging - status unchanged: {status_response}")
                        
                        # Try to get more detailed status
                        settings_check = await self._send_command('$$', wait_for_response=True)
                        if settings_check:
                            logger.info("FluidNC is responding to commands")
                        else:
                            raise MotionTimeoutError("FluidNC not responding during homing")
                    
                else:
                    logger.warning("No status response from FluidNC")
                
                await asyncio.sleep(1.0)
                
            except Exception as e:
                logger.error(f"Error monitoring homing: {e}")
                await asyncio.sleep(1.0)
        
        # Timeout reached
        logger.error(f"Homing timeout after {timeout} seconds")
        logger.error("This usually indicates:")
        logger.error("  1. Motors not powered/enabled")
        logger.error("  2. Endstops not wired correctly")
        logger.error("  3. Motor drivers not configured")
        logger.error("  4. Power supply issues")
        
        raise MotionTimeoutError(f"Homing timeout after {timeout} seconds")
    
    # Safety and Emergency
    async def emergency_stop(self) -> bool:
        """Immediately stop all motion"""
        try:
            logger.warning("Emergency stop activated")
            
            # Send emergency stop command (feed hold + reset)
            if self.serial_connection:
                self.serial_connection.write(b'!')  # Feed hold
                await asyncio.sleep(0.1)
                self.serial_connection.write(b'\x18')  # Ctrl-X (reset)
            
            self.status = MotionStatus.EMERGENCY_STOP
            
            self._notify_event("emergency_stop", {
                "reason": "Manual emergency stop"
            })
            
            return True
            
        except Exception as e:
            logger.critical(f"Emergency stop failed: {e}")
            return False
    
    async def reset_controller(self) -> bool:
        """Reset FluidNC controller"""
        try:
            logger.info("Resetting FluidNC controller")
            
            # Send reset command
            await self._send_command('\x18')  # Ctrl-X
            await asyncio.sleep(2.0)  # Wait for reset
            
            # Reinitialize
            await self._send_startup_commands()
            
            self.status = MotionStatus.IDLE
            self.is_homed = False
            
            logger.info("FluidNC controller reset complete")
            return True
            
        except Exception as e:
            logger.error(f"Controller reset failed: {e}")
            return False
    
    # Status Updates
    async def _update_status(self):
        """Update controller status from FluidNC"""
        try:
            if not self.is_connected():
                self.status = MotionStatus.DISCONNECTED
                return
            
            # Get status from FluidNC
            response = await self._send_command('?')
            
            # Parse status
            if response and 'Idle' in response:
                self.status = MotionStatus.IDLE
            elif response and ('Run' in response or 'Jog' in response):
                self.status = MotionStatus.MOVING
            elif response and 'Home' in response:
                self.status = MotionStatus.HOMING
            if response and 'Alarm' in response:
                self.status = MotionStatus.ALARM
            elif response and 'Error' in response:
                self.status = MotionStatus.ERROR
            
            # Update position if available
            if response:
                position = self._parse_position_from_status(response)
                if position:
                    self.current_position = position
                
        except Exception as e:
            logger.error(f"Status update failed: {e}")
            self.status = MotionStatus.ERROR
    
    async def get_status(self) -> MotionStatus:
        """Get current motion controller status"""
        await self._update_status()
        return self.status
    
    async def get_last_error(self) -> Optional[str]:
        """Get last error message from FluidNC"""
        try:
            # FluidNC doesn't store error history, return current alarm state
            response = await self._send_command('?')
            if response and ('Alarm' in response or 'Error' in response):
                return response
            return None
        except Exception:
            return "Communication error"

    # Additional abstract methods implementation
    async def connect(self) -> None:
        """Connect to the FluidNC controller."""
        await self.initialize()
    
    async def disconnect(self) -> None:
        """Disconnect from the FluidNC controller."""
        await self.shutdown()
    
    async def get_position(self) -> Position4D:
        """Get current position."""
        await self._update_status()
        return self.current_position
    
    async def get_capabilities(self) -> MotionCapabilities:
        """Get motion controller capabilities."""
        # Get max feedrate from first available axis
        max_feedrate = 10000.0
        if self.axis_limits:
            first_axis = next(iter(self.axis_limits.values()))
            max_feedrate = first_axis.max_feedrate
            
        return MotionCapabilities(
            axes_count=4,
            supports_homing=True,
            supports_soft_limits=True,
            supports_probe=True,
            max_feedrate=max_feedrate,
            position_resolution=0.001  # 1 micron resolution
        )
    
    async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move relative to current position."""
        try:
            # Calculate target position
            target = Position4D(
                x=self.current_position.x + delta.x,
                y=self.current_position.y + delta.y,
                z=self.current_position.z + delta.z,
                c=self.current_position.c + delta.c
            )
            
            # Validate target position
            if not self._validate_position(target):
                return False
            
            # Set relative mode and execute
            await self._send_command("G91")  # Relative positioning
            feed_str = f" F{feedrate}" if feedrate else ""
            gcode = f"G0 X{delta.x:.3f} Y{delta.y:.3f} Z{delta.z:.3f} C{delta.c:.3f}{feed_str}"
            result = await self.execute_gcode(gcode)
            await self._send_command("G90")  # Back to absolute positioning
            
            return result
            
        except Exception as e:
            logger.error(f"Relative move failed: {e}")
            await self._send_command("G90")  # Ensure absolute mode
            return False
    
    async def rapid_move(self, position: Position4D) -> bool:
        """Rapid (non-linear) movement to position."""
        try:
            # Use G0 for rapid movement
            gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
            return await self.execute_gcode(gcode)
            
        except Exception as e:
            logger.error(f"Rapid move failed: {e}")
            return False
    
    async def home_axis(self, axis: str) -> bool:
        """Home specific axis."""
        try:
            if axis.upper() in ['X', 'Y', 'Z', 'C']:
                gcode = f"$H{axis.upper()}"
                return await self.execute_gcode(gcode)
            else:
                logger.error(f"Invalid axis: {axis}")
                return False
                
        except Exception as e:
            logger.error(f"Home axis {axis} failed: {e}")
            return False
    
    async def pause_motion(self) -> bool:
        """Pause current motion."""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'!')  # Feed hold
                return True
            return False
            
        except Exception as e:
            logger.error(f"Pause motion failed: {e}")
            return False
    
    async def resume_motion(self) -> bool:
        """Resume paused motion."""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'~')  # Resume
                return True
            return False
            
        except Exception as e:
            logger.error(f"Resume motion failed: {e}")
            return False
    
    async def cancel_motion(self) -> bool:
        """Cancel current motion."""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'\x18')  # Ctrl-X (reset)
                return True
            return False
            
        except Exception as e:
            logger.error(f"Cancel motion failed: {e}")
            return False
    
    async def set_motion_limits(self, axis: str, limits: MotionLimits) -> bool:
        """Set motion limits for an axis."""
        try:
            axis_lower = axis.lower()
            if axis_lower in ['x', 'y', 'z', 'c']:
                self.axis_limits[axis_lower] = limits
                # Update FluidNC settings if needed
                return True
            else:
                logger.error(f"Invalid axis: {axis}")
                return False
                
        except Exception as e:
            logger.error(f"Set motion limits failed: {e}")
            return False
    
    async def get_motion_limits(self, axis: str) -> MotionLimits:
        """Get motion limits for an axis."""
        axis_lower = axis.lower()
        if axis_lower in self.axis_limits:
            return self.axis_limits[axis_lower]
        else:
            raise MotionControlError(f"Invalid axis: {axis}")
    
    async def wait_for_motion_complete(self, timeout: Optional[float] = None) -> bool:
        """Wait for all motion to complete."""
        try:
            start_time = time.time()
            timeout = timeout or 300.0  # 5 minute default timeout
            
            while time.time() - start_time < timeout:
                await self._update_status()
                if self.status == MotionStatus.IDLE:
                    return True
                elif self.status in [MotionStatus.ALARM, MotionStatus.ERROR]:
                    return False
                
                await asyncio.sleep(0.1)
            
            logger.warning("Motion completion timeout")
            return False
            
        except Exception as e:
            logger.error(f"Wait for motion complete failed: {e}")
            return False

    async def set_position(self, position: Position4D) -> bool:
        """Set current position without moving."""
        # FluidNC doesn't typically support setting position directly
        # This would need to be done through coordinate system offsets
        logger.warning("set_position not implemented for FluidNC")
        return False

    async def execute_gcode(self, gcode: str) -> bool:
        """Execute raw G-code command."""
        try:
            response = await self._send_command(gcode)
            return response is not None and 'error' not in response.lower()
        except Exception as e:
            logger.error(f"G-code execution failed: {e}")
            return False

    def _validate_position(self, position: Position4D) -> bool:
        """Validate position is within limits."""
        try:
            axes = {'x': position.x, 'y': position.y, 'z': position.z, 'c': position.c}
            
            for axis_name, pos_value in axes.items():
                if axis_name in self.axis_limits:
                    limits = self.axis_limits[axis_name]
                    if not limits.is_within_limits(pos_value):
                        logger.error(f"Position {pos_value} out of limits for {axis_name}: {limits.min_limit} to {limits.max_limit}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Position validation failed: {e}")
            return False


# Utility functions for FluidNC operations
def create_fluidnc_controller(config_manager: ConfigManager) -> FluidNCController:
    """Create FluidNC controller from configuration"""
    motion_config = config_manager.get('motion', {})
    controller_config = motion_config.get('controller', {})
    
    # Add axis configuration
    controller_config['axes'] = config_manager.get('motion.axes', {})
    
    return FluidNCController(controller_config)


def format_gcode_position(position: Position4D) -> str:
    """Format position as G-code coordinates"""
    return f"X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"


def parse_fluidnc_version(response: str) -> Optional[str]:
    """Parse FluidNC version from response"""
    match = re.search(r'FluidNC\s+([\d\.]+)', response)
    return match.group(1) if match else None