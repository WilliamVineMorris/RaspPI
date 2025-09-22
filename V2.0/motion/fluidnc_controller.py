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
    async def initialize(self, auto_unlock: bool = False) -> bool:
        """
        Initialize FluidNC connection and configure axes
        
        Args:
            auto_unlock: If True, automatically unlock alarm states with $X.
                        If False, leave alarm states for user to handle (recommended for homing)
        """
        try:
            logger.info(f"Initializing FluidNC controller on {self.port}")
            
            # Open serial connection
            if not await self._connect_serial():
                return False
            
            # Wait for FluidNC startup
            await asyncio.sleep(2.0)
            
            # Send initial configuration
            await self._send_startup_commands(auto_unlock=auto_unlock)
            
            # Get current status (may fail in alarm state, that's OK)
            try:
                await self._update_status()
            except Exception as e:
                logger.warning(f"Status update failed during initialization (may be in alarm state): {e}")
                # Continue initialization - status will be updated after homing
            
            # Set status based on initialization success
            # Don't force IDLE if we might be in alarm state
            if self.status == MotionStatus.DISCONNECTED:
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
                
                logger.info(f"Sent command: {command.strip()}")
                
                if wait_for_response:
                    response = await self._read_response()
                    logger.info(f"Received response: {response}")
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
    
    async def _send_startup_commands(self, auto_unlock: bool = False):
        """
        Send initial configuration commands to FluidNC
        
        Args:
            auto_unlock: If True, automatically unlock alarm states with $X.
                        If False, leave alarm states for user to handle.
        """
        try:
            # First, check status and clear any alarms
            status_response = await self._get_status_response()
            logger.info(f"Initial status: {status_response}")
            
            # If in alarm state, handle based on auto_unlock setting
            if status_response and 'Alarm' in status_response:
                if auto_unlock:
                    logger.info("System in alarm state, auto-unlocking...")
                    await self._send_command('$X')  # Unlock
                    await asyncio.sleep(0.5)
                else:
                    logger.warning("System in alarm state - use homing ($H) or unlock ($X) to clear")
                    # Don't automatically unlock - let user decide
                    # Skip motor commands as they will fail in alarm state
                    logger.info("Basic FluidNC configuration complete - ready for homing")
                    return
            
            # Stepper motors are enabled by default in FluidNC - no need for M17
            # Only send basic G-code mode commands that work in any state
            
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
            
            # Enable auto-report for efficient status monitoring
            try:
                logger.info("Enabling auto-report interval for status updates...")
                await self._send_command('$Report/Interval=200')  # 200ms auto-report for responsive monitoring
                await asyncio.sleep(0.2)
            except FluidNCCommandError as e:
                logger.warning(f"Auto-report setup failed: {e}")
                # Continue without auto-report - fall back to polling
            
            # Note: Homing ($H) is intentionally NOT done here during initialization
            # It should be done separately via the home() method when needed
            logger.info("Basic FluidNC configuration complete - ready for homing")
            
        except Exception as e:
            logger.error(f"Startup command sequence failed: {e}")
            raise
    
    async def unlock(self) -> bool:
        """
        Manually unlock FluidNC from alarm state using $X command
        
        Returns:
            bool: True if unlock successful, False otherwise
        """
        try:
            logger.info("Manually unlocking FluidNC from alarm state")
            await self._send_command('$X')
            await asyncio.sleep(0.5)
            
            # Check if unlock was successful
            status_response = await self._send_command('?', wait_for_response=True)
            if status_response and 'Alarm' not in status_response:
                logger.info("FluidNC unlocked successfully")
                return True
            else:
                logger.warning("FluidNC may still be in alarm state after unlock")
                return False
                
        except Exception as e:
            logger.error(f"Failed to unlock FluidNC: {e}")
            return False
    
    async def _get_status_response(self) -> Optional[str]:
        """
        Get status response from FluidNC, handling the ok acknowledgment properly
        
        FluidNC responds to ? queries with:
        1. "ok" (command acknowledgment)
        2. "<status>" (actual status)
        
        We want to return only the actual status line.
        """
        if not self.is_connected():
            raise FluidNCConnectionError("Not connected to FluidNC")
        
        async with self.connection_lock:
            try:
                if not self.serial_connection:
                    raise FluidNCConnectionError("Serial connection not established")
                    
                # Send status query
                command = '?\n'
                self.serial_connection.write(command.encode('utf-8'))
                self.serial_connection.flush()
                
                logger.debug("Sent status query: ?")
                
                # Read response lines
                response_lines = []
                timeout = self.timeout
                start_time = time.time()
                
                while time.time() - start_time < timeout:
                    if self.serial_connection.in_waiting > 0:
                        line = self.serial_connection.readline().decode('utf-8').strip()
                        if line:
                            response_lines.append(line)
                            logger.debug(f"Received line: {line}")
                            
                            # Check for actual status response (starts with <)
                            if line.startswith('<') and line.endswith('>'):
                                logger.debug(f"Found status response: {line}")
                                return line
                            
                            # If we get an error, return it
                            if line.startswith('error:') or line == 'error':
                                return line
                                
                            # Continue reading if we just got "ok" acknowledgment
                            if line == 'ok':
                                continue
                    else:
                        await asyncio.sleep(0.01)
                
                # If we got here, we didn't find a proper status response
                all_response = '\n'.join(response_lines)
                logger.warning(f"No status response found, got: {all_response}")
                return all_response if all_response else None
                
            except Exception as e:
                logger.error(f"Error reading status response: {e}")
                raise FluidNCConnectionError(f"Failed to read status response: {e}")
    
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
            
            logger.info(f"Sending movement command: {command}")
            
            # Send move command
            response = await self._send_command(command)
            logger.debug(f"Movement command response: {response}")
            
            # Wait for movement completion
            await self._wait_for_movement_complete()
            
            # Read actual position from FluidNC after movement
            actual_position = await self.get_current_position()
            self.status = MotionStatus.IDLE
            
            self._notify_event("position_reached", {
                "position": actual_position.to_dict(),
                "feedrate": feedrate
            })
            
            logger.info(f"Moved to position: {actual_position}")
            return True
            
        except Exception as e:
            self.status = MotionStatus.ERROR
            logger.error(f"Move to position failed: {e}")
            raise
    
    async def _wait_for_movement_complete(self):
        """
        Wait for FluidNC to complete current movement
        
        This method properly waits for movement completion by:
        1. Waiting briefly to ensure movement starts before checking completion
        2. Using _get_status_response() to avoid "ok" acknowledgment confusion
        3. Monitoring for 'Idle' state which indicates movement completion
        4. Handling intermediate states like 'Run' during movement execution
        5. Providing detailed progress logging
        """
        start_time = time.time()
        timeout = 60.0  # 60 second timeout for movements
        last_status = None
        movement_started = False
        
        logger.info("Waiting for movement completion...")
        
        # Give the movement time to start (FluidNC needs time to process G-code)
        await asyncio.sleep(0.5)
        
        while time.time() - start_time < timeout:
            try:
                # Get actual status (not just "ok" acknowledgment)
                status_response = await self._get_status_response()
                
                if status_response:
                    # Log status changes for debugging
                    if status_response != last_status:
                        logger.debug(f"Movement status: {status_response}")
                        last_status = status_response
                    
                    # Check if movement has started
                    if 'Run' in status_response or 'Jog' in status_response:
                        movement_started = True
                        logger.debug("Movement in progress...")
                        await asyncio.sleep(0.2)  # Check every 200ms during movement
                        continue
                    
                    # Check for completion - system idle (only after movement started)
                    if 'Idle' in status_response:
                        if movement_started:
                            logger.info("✅ Movement completed - system idle")
                            return  # Movement complete
                        else:
                            # System was already idle - movement may have completed too quickly
                            # or command may not have been processed. Wait a bit more.
                            elapsed = time.time() - start_time
                            if elapsed > 2.0:  # After 2 seconds, assume movement is done
                                logger.info("✅ Movement completed - system idle (quick completion)")
                                return
                            await asyncio.sleep(0.2)
                            continue
                        
                    # Check for active movement states
                    elif 'Run' in status_response or 'Jog' in status_response:
                        logger.debug("Movement in progress...")
                        await asyncio.sleep(0.2)  # Check every 200ms during movement
                        continue
                        
                    # Check for error conditions
                    elif 'Alarm' in status_response:
                        logger.error(f"Alarm during movement: {status_response}")
                        raise MotionSafetyError(f"FluidNC in alarm state: {status_response}")
                        
                    elif 'Error' in status_response or 'error:' in status_response:
                        logger.error(f"Error during movement: {status_response}")
                        raise FluidNCCommandError(f"FluidNC error during movement: {status_response}")
                        
                    # Handle other states (Hold, etc.)
                    elif 'Hold' in status_response:
                        logger.warning(f"Hold state during movement: {status_response}")
                        await asyncio.sleep(0.5)
                        continue
                        
                    else:
                        # Unknown state - log and continue monitoring
                        logger.debug(f"Unknown movement state: {status_response}")
                        await asyncio.sleep(0.2)
                        continue
                        
                else:
                    logger.warning("No status response during movement monitoring")
                    await asyncio.sleep(0.5)
                    
            except Exception as e:
                logger.error(f"Error monitoring movement completion: {e}")
                await asyncio.sleep(0.5)
        
        # Timeout reached
        elapsed = time.time() - start_time
        logger.error(f"Movement timeout after {elapsed:.1f} seconds")
        raise MotionTimeoutError(f"Movement timeout exceeded ({elapsed:.1f}s)")
    
    async def get_current_position(self) -> Position4D:
        """Get current 4DOF position from FluidNC"""
        try:
            # Get actual status response (not just "ok")
            response = await self._get_status_response()
            logger.debug(f"Status response for position: {response}")
            
            # Parse position from status response
            if response:
                position = self._parse_position_from_status(response)
                if position:
                    self.current_position = position
                    logger.debug(f"Current position: {position}")
                    return position
                else:
                    logger.warning(f"Could not parse position from: {response}")
            
            # Fallback to cached position
            logger.warning(f"Using cached position: {self.current_position}")
            return self.current_position
            
        except Exception as e:
            logger.error(f"Failed to get current position: {e}")
            return self.current_position
    
    def _parse_position_from_status(self, status_response: str) -> Optional[Position4D]:
        """Parse position from FluidNC status response"""
        try:
            # FluidNC status format: <Idle|MPos:0.000,0.000,0.000,0.000,0.000,0.000|FS:0,0>
            # Try work coordinates first (WPos), then machine coordinates (MPos)
            # Work coordinates are what G-code uses, machine coordinates are absolute
            
            # First try work coordinates (WPos)
            wpos_match = re.search(r'WPos:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,[\d\.-]+,[\d\.-]+)?', status_response)
            if wpos_match:
                x, y, z, c = map(float, wpos_match.groups())
                logger.debug(f"Parsed work position from status: X={x}, Y={y}, Z={z}, C={c}")
                return Position4D(x=x, y=y, z=z, c=c)
            
            # Fallback to machine coordinates (MPos)
            mpos_match = re.search(r'MPos:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,[\d\.-]+,[\d\.-]+)?', status_response)
            if mpos_match:
                x, y, z, c = map(float, mpos_match.groups())
                
                # Check if we have work coordinate offsets (WCO)
                wco_match = re.search(r'WCO:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,[\d\.-]+,[\d\.-]+)?', status_response)
                if wco_match:
                    # Calculate work position by subtracting offsets from machine position
                    wco_x, wco_y, wco_z, wco_c = map(float, wco_match.groups())
                    x -= wco_x
                    y -= wco_y  
                    z -= wco_z
                    c -= wco_c
                    logger.debug(f"Applied work coordinate offsets: WCO=({wco_x},{wco_y},{wco_z},{wco_c})")
                
                logger.debug(f"Parsed machine position from status: X={x}, Y={y}, Z={z}, C={c}")
                return Position4D(x=x, y=y, z=z, c=c)
            else:
                logger.warning(f"Could not match position pattern in: {status_response}")
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to parse position from status: {e}")
            logger.error(f"Status response was: {status_response}")
            return None
    
    async def _read_all_messages(self) -> list[str]:
        """
        Read all available messages from FluidNC serial buffer.
        This captures both responses and unsolicited messages like debug output.
        
        Returns:
            List of message strings received
        """
        messages = []
        
        if not self.serial_connection:
            return messages
            
        try:
            # Read all available data without blocking
            while self.serial_connection.in_waiting > 0:
                try:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line:
                        messages.append(line)
                        logger.debug(f"FluidNC message: {line}")
                except UnicodeDecodeError:
                    # Skip malformed messages
                    continue
                except Exception as e:
                    logger.warning(f"Error reading message: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error reading FluidNC messages: {e}")
            
        return messages
    
    # Homing Operations
    async def home(self) -> bool:
        """
        Home all axes using the standard FluidNC $H command.
        This executes the standard homing sequence defined in FluidNC configuration.
        All axes home simultaneously according to the configured homing order.
        """
        return await self.home_all_axes()
    
    async def home_all_axes(self) -> bool:
        """
        Home all axes to their home positions using standard FluidNC $H command.
        
        This method sends the $H command which:
        - Homes all axes simultaneously according to FluidNC configuration
        - Follows the homing sequence defined in the FluidNC YAML config
        - Does NOT home axes individually
        - Uses the standard G-code homing protocol
        
        Returns:
            bool: True if homing completed successfully, False otherwise
        """
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
            status_response = await self._get_status_response()
            logger.info(f"Pre-homing status: {status_response}")
            
            if status_response and 'Alarm' in status_response:
                logger.info("System in alarm state - homing will clear alarms")
                # FluidNC allows homing to clear alarm states, so we proceed
            
            # Send homing command
            logger.info("Sending homing command...")
            await self._send_command('$H')
            
            # Wait for homing completion with better monitoring
            await self._wait_for_homing_complete()
            
            # Reset Z-axis position to 0 (continuous rotation axis)
            logger.info("Resetting Z-axis position to 0° (continuous rotation axis)...")
            try:
                # First, clear any existing work coordinate offsets
                await self._send_command('G10 L2 P1 Z0')  # Set Z offset to 0 in coordinate system 1
                await asyncio.sleep(0.5)
                
                # Use G92 to set current Z position to 0 in work coordinates
                await self._send_command('G92 Z0')  # Set current Z position to 0
                await asyncio.sleep(1.0)  # Give FluidNC time to process coordinate change
                
                # Select coordinate system to ensure changes take effect
                await self._send_command('G54')  # Select coordinate system 1 (default)
                await asyncio.sleep(0.5)
                
                # Verify the reset worked
                status_response = await self._get_status_response()
                if status_response:
                    logger.info(f"Z-axis reset status: {status_response}")
                
                logger.info("Z-axis position reset to 0°")
            except Exception as e:
                logger.warning(f"Failed to reset Z-axis position: {e}")
                # Continue anyway - Z-axis reset is not critical for basic operation
            
            # Get actual position from FluidNC after homing
            logger.info("Reading actual home position from FluidNC...")
            await asyncio.sleep(1.0)  # Give FluidNC time to settle
            
            # Query actual position from FluidNC
            actual_position = await self.get_current_position()
            if actual_position:
                self.current_position = actual_position
                logger.info(f"Actual home position from FluidNC: {actual_position}")
                final_position = actual_position
            else:
                # Fallback to known home positions (X=0, Y=200, Z=0, C=0)
                logger.warning("Could not read position from FluidNC, using known home positions")
                home_position = Position4D(
                    x=0.0,    # X homes to minimum limit
                    y=200.0,  # Y homes to maximum limit
                    z=0.0,    # Z-axis defaults to 0 degrees (doesn't actually home)
                    c=0.0     # C-axis defaults to 0 degrees (doesn't home)
                )
                self.current_position = home_position
                final_position = home_position
            
            # Check if system is still in alarm state after homing
            await asyncio.sleep(0.5)  # Brief pause before status check
            final_status = await self._get_status_response()
            
            if final_status and 'Alarm' in final_status:
                logger.warning("⚠️  System still in alarm state after homing completion")
                logger.warning(f"Final status: {final_status}")
                
                # Offer user the option to unlock
                if await self._offer_post_homing_unlock():
                    logger.info("System unlocked successfully after homing")
                else:
                    logger.warning("System remains in alarm state - some operations may be restricted")
                    # Don't fail homing - let user decide what to do
                    
            self.is_homed = True
            self.status = MotionStatus.IDLE
            
            self._notify_event("homing_complete", {
                "home_position": final_position.to_dict()
            })
            
            logger.info("Homing sequence completed")
            return True
            
        except Exception as e:
            self.status = MotionStatus.ERROR
            logger.error(f"Homing failed: {e}")
            return False
    
    async def _wait_for_homing_complete(self):
        """
        Wait for homing sequence to complete, accounting for delayed status output.
        FluidNC status can lag significantly (20+ seconds) behind actual machine movement.
        
        Homing strategy:
        1. Detect when homing starts (Home state appears)
        2. Monitor for position stability indicating completion
        3. Use timeout-based detection when status lags
        4. Handle 2-cycle homing (Y-axis first, then X-axis)
        """
        start_time = time.time()
        timeout = 180.0  # 3 minute timeout for dual-cycle homing
        homing_started = False
        
        logger.info("Monitoring homing progress via FluidNC messages...")
        logger.info("Note: FluidNC status may lag significantly behind actual movement")
        
        # Track status for lag detection
        last_status = None
        status_unchanged_count = 0
        last_position = None
        position_stable_count = 0
        homing_phase_start = None
        
        while time.time() - start_time < timeout:
            try:
                # First priority: Check for homing messages from FluidNC
                messages = await self._read_all_messages()
                current_time = time.time()
                
                # Process any homing-related messages
                homing_message_received = False
                for message in messages:
                    if any(keyword in message.lower() for keyword in ['homing', 'home', 'dbg:']):
                        logger.info(f"Homing message: {message}")
                        homing_message_received = True
                        homing_started = True
                        homing_phase_start = current_time
                        
                        # Track individual axis completion
                        if 'homed:' in message.lower():
                            axis = message.split(':')[-1].strip(' ]')
                            logger.info(f"Axis {axis} homing completed")
                            # Don't return yet - wait for all axes and final completion
                        
                        # Check for final completion messages (after all axes)
                        elif 'homing done' in message.lower():
                            logger.info("✅ Homing completion detected via final 'homing done' message")
                            return  # Homing complete!
                
                # If we received homing messages, continue monitoring messages
                if homing_message_received:
                    await asyncio.sleep(0.2)  # Quick check for more messages
                    continue
                
                # If no homing messages for 2+ seconds, fall back to status polling
                time_since_message_start = current_time - (homing_phase_start or start_time)
                if homing_started and time_since_message_start >= 2.0:
                    logger.info("No homing messages for 2+ seconds, checking status...")
                    
                    # Get status response for completion check
                    status_response = await self._get_status_response()
                    
                    if status_response:
                        # Log status if it changed
                        if status_response != last_status:
                            logger.info(f"Homing status: {status_response}")
                            last_status = status_response
                            status_unchanged_count = 0
                        else:
                            status_unchanged_count += 1
                        
                        # Parse current position
                        current_position = self._parse_position_from_status(status_response)
                        
                        # Track position stability
                        if current_position and last_position:
                            if (abs(current_position.x - last_position.x) < 0.1 and 
                                abs(current_position.y - last_position.y) < 0.1):
                                position_stable_count += 1
                            else:
                                position_stable_count = 0
                                last_position = current_position
                        elif current_position:
                            last_position = current_position
                        
                        # Check completion patterns when messages have stopped
                        
                        # Pattern 1: Transition from Home to Idle state (most reliable)
                        if 'Idle' in status_response and homing_started:
                            logger.info("✅ Homing completed (Home→Idle transition detected)")
                            return  # Homing complete!
                        
                        # Pattern 2: Alarm state with correct position (common after homing)
                        elif 'Alarm' in status_response and current_position:
                            if self._verify_home_position(current_position) and position_stable_count >= 3:
                                logger.info(f"✅ Homing completed (Alarm state with correct position): {current_position}")
                                return  # Homing complete!
                        
                        # Pattern 3: Position stable at home for extended time in Home state
                        elif 'Home' in status_response and position_stable_count >= 5 and current_position:  # 5 * 2 seconds = 10 seconds stable
                            if self._verify_home_position(current_position):
                                logger.info(f"✅ Homing completed (Home state with stable position): {current_position}")
                                return  # Homing complete!
                        
                        # Pattern 4: Status unchanged for very long time (indicates completion lag)
                        elif status_unchanged_count >= 8 and current_position:  # 8 * 2 seconds = 16 seconds
                            if self._verify_home_position(current_position):
                                logger.info(f"✅ Homing completed (status lag pattern): {current_position}")
                                return  # Homing complete!
                
                # If homing hasn't started yet, check status to detect start
                if not homing_started:
                    status_response = await self._get_status_response()
                    if status_response and ('Home' in status_response or 'Homing' in status_response):
                        logger.info("Homing sequence actively running...")
                        homing_started = True
                        homing_phase_start = current_time
                
                # Polling interval: frequent during message phase, less frequent during status phase
                if homing_message_received:
                    await asyncio.sleep(0.5)  # Fast polling when getting messages
                else:
                    await asyncio.sleep(2.0)  # Slower polling when monitoring status
                
            except Exception as e:
                logger.error(f"Error monitoring homing: {e}")
                await asyncio.sleep(1.0)
        
        # Timeout reached
        logger.error(f"Homing timeout after {timeout} seconds")
        raise MotionTimeoutError(f"Homing did not complete within {timeout} seconds")
    
    def _verify_home_position(self, position: Position4D) -> bool:
        """
        Verify that the position looks like a proper home position
        
        Args:
            position: Position to verify
            
        Returns:
            bool: True if position appears to be a valid home position
        """
        try:
            # Expected home positions (with tolerance)
            expected_x = 0.0      # X homes to minimum
            expected_y = 200.0    # Y homes to maximum  
            tolerance = 5.0       # 5mm tolerance
            
            x_ok = abs(position.x - expected_x) <= tolerance
            y_ok = abs(position.y - expected_y) <= tolerance
            
            logger.info(f"Home position verification:")
            logger.info(f"  X: {position.x:.3f}mm (expected {expected_x}±{tolerance}mm) {'✅' if x_ok else '❌'}")
            logger.info(f"  Y: {position.y:.3f}mm (expected {expected_y}±{tolerance}mm) {'✅' if y_ok else '❌'}")
            logger.info(f"  Z: {position.z:.3f}° (continuous, any value OK)")
            logger.info(f"  C: {position.c:.3f}° (servo, any value OK)")
            
            # Only X and Y axes actually home, so only verify those
            return x_ok and y_ok
            
        except Exception as e:
            logger.error(f"Error verifying home position: {e}")
            return False
    
    async def _offer_post_homing_unlock(self) -> bool:
        """
        Offer user the option to unlock the system after homing if still in alarm state.
        This is a non-interactive version that logs the recommendation.
        
        Returns:
            bool: True if unlock was attempted, False otherwise
        """
        try:
            logger.info("💡 System is in alarm state after homing completion")
            logger.info("💡 This sometimes happens and can be cleared with an unlock command")
            logger.info("💡 Attempting automatic unlock...")
            
            # Try automatic unlock
            response = await self._send_command('$X')
            await asyncio.sleep(0.5)
            
            # Check if unlock was successful
            status_after_unlock = await self._get_status_response()
            if status_after_unlock and 'Idle' in status_after_unlock:
                logger.info("✅ Automatic unlock successful - system is now ready")
                return True
            else:
                logger.warning(f"⚠️  Unlock attempted but system still shows: {status_after_unlock}")
                logger.warning("💡 You may need to check:")
                logger.warning("   - Limit switch wiring")
                logger.warning("   - Motor driver status") 
                logger.warning("   - Power supply connections")
                logger.warning("   - Manual unlock with: $X command")
                return False
                
        except Exception as e:
            logger.error(f"Error during post-homing unlock: {e}")
            return False
    
    async def unlock_system(self) -> bool:
        """
        Unlock the FluidNC system from alarm state using $X command.
        
        Returns:
            bool: True if unlock was successful, False otherwise
        """
        try:
            logger.info("Unlocking FluidNC system from alarm state...")
            
            # Check current status
            current_status = await self._get_status_response()
            logger.info(f"Current status before unlock: {current_status}")
            
            if current_status and 'Alarm' not in current_status:
                logger.info("System is not in alarm state - unlock not needed")
                return True
            
            # Send unlock command
            response = await self._send_command('$X')
            await asyncio.sleep(0.5)
            
            # Verify unlock was successful
            status_after_unlock = await self._get_status_response()
            logger.info(f"Status after unlock: {status_after_unlock}")
            
            if status_after_unlock and 'Idle' in status_after_unlock:
                logger.info("✅ System unlocked successfully")
                self.status = MotionStatus.IDLE
                return True
            elif status_after_unlock and 'Alarm' in status_after_unlock:
                logger.warning("⚠️  System still in alarm state after unlock attempt")
                logger.warning("This may indicate a hardware issue that needs attention")
                return False
            else:
                logger.warning(f"Unexpected status after unlock: {status_after_unlock}")
                return False
                
        except Exception as e:
            logger.error(f"Error during system unlock: {e}")
            return False
    
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
            elif response and 'Alarm' in response:
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
    async def connect(self, auto_unlock: bool = False) -> bool:
        """
        Connect to the FluidNC controller.
        
        Args:
            auto_unlock: If True, automatically unlock alarm states with $X.
                        If False, leave alarm states for user to handle (recommended for homing)
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        return await self.initialize(auto_unlock=auto_unlock)
    
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