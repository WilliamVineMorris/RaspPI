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
        self.homing_in_progress = False  # Track active homing to prevent premature completion
        self.axis_limits: Dict[str, MotionLimits] = {}
        
        # Communication
        self.command_queue = asyncio.Queue()
        self.response_cache: Dict[str, str] = {}
        self.status_update_interval = 0.1  # seconds
        
        # Background monitoring
        self.background_monitor_task = None
        self.monitor_running = False
        self.last_position_update = 0
        
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
            
            # Stop background monitoring task
            if self.background_monitor_task:
                self.monitor_running = False
                try:
                    self.background_monitor_task.cancel()
                    await asyncio.wait_for(self.background_monitor_task, timeout=2.0)
                except asyncio.TimeoutError:
                    logger.warning("Background monitor task did not stop cleanly")
                except asyncio.CancelledError:
                    pass  # Expected
                self.background_monitor_task = None
            
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
            if self.port.lower() == 'auto':
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
        
        # First check common FluidNC ports
        common_ports = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
        for port_name in common_ports:
            if any(port.device == port_name for port in ports):
                logger.info(f"Found FluidNC on common port: {port_name}")
                return port_name
        
        # Then check by device description
        for port in ports:
            # Look for common FluidNC identifiers
            description = (port.description or '').lower()
            if any(identifier in description for identifier in 
                   ['fluidnc', 'esp32', 'arduino', 'usb serial', 'ch340', 'cp210']):
                logger.info(f"Detected potential FluidNC device: {port.device} ({port.description})")
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
                
                # Start background monitoring task to continuously process auto-reports
                self.monitor_running = True
                self.background_monitor_task = asyncio.create_task(self._background_status_monitor())
                logger.info("Started background status monitoring task")
                
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
                                
                            # Skip "ok" acknowledgments - they're not status
                            if line == 'ok':
                                continue
                                
                            # Skip info messages that aren't status
                            if line.startswith('[MSG:INFO:') or line.startswith('[GC:') or line.startswith('[G54:'):
                                continue
                    else:
                        await asyncio.sleep(0.01)
                
                # If we got here, we didn't find a proper status response
                # Filter out non-status responses for logging
                status_lines = [line for line in response_lines 
                              if not (line == 'ok' or line.startswith('[MSG:INFO:') or 
                                     line.startswith('[GC:') or line.startswith('[G54:'))]
                
                if status_lines:
                    all_response = '\n'.join(status_lines)
                    logger.warning(f"No proper status response found, got: {all_response}")
                    return all_response
                else:
                    logger.debug("Only acknowledgment responses received, no status data")
                    return None
                
            except Exception as e:
                logger.error(f"Error reading status response: {e}")
                raise FluidNCConnectionError(f"Failed to read status response: {e}")    # Position and Movement
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
            # Always try to get fresh position from FluidNC
            response = await self._get_status_response()
            logger.debug(f"Status response for position: {response}")
            
            # Parse position from status response
            if response:
                position = self._parse_position_from_status(response)
                if position:
                    # Only update cached position if parsing succeeds and values seem reasonable
                    # Before homing, FluidNC may report arbitrary values, but we still want to show them
                    self.current_position = position
                    logger.debug(f"Updated current position from FluidNC: {position}")
                    return position
                else:
                    logger.warning(f"Could not parse position from: {response}")
            else:
                logger.warning("No status response received from FluidNC")
                
            # If FluidNC is connected but we can't parse position, 
            # still return cached position rather than failing completely
            if self.is_connected():
                logger.debug(f"Using cached position (FluidNC connected): {self.current_position}")
            else:
                logger.warning(f"Using cached position (FluidNC disconnected): {self.current_position}")
                
            return self.current_position
            
        except Exception as e:
            logger.error(f"Failed to get current position: {e}")
            return self.current_position
    
    def _parse_position_from_status(self, status_response: str) -> Optional[Position4D]:
        """Parse position from FluidNC status response"""
        try:
            # FluidNC status format: <Idle|MPos:0.000,0.000,0.000,0.000,0.000,0.000|WPos:0.000,0.000,0.000,0.000,0.000,0.000|FS:0,0>
            
            # Parse both machine (MPos) and work (WPos) coordinates
            mpos_match = re.search(r'MPos:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,[\d\.-]+,[\d\.-]+)?', status_response)
            wpos_match = re.search(r'WPos:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,[\d\.-]+,[\d\.-]+)?', status_response)
            
            # Before homing, work coordinates may not be reliable, so prioritize machine coordinates
            if mpos_match:
                mx, my, mz, mc = map(float, mpos_match.groups())
                
                if wpos_match:
                    # If we have both, use work coordinates for X, Y, C but machine for Z
                    wx, wy, wz, wc = map(float, wpos_match.groups())
                    position = Position4D(
                        x=wx,    # Work coordinate for X
                        y=wy,    # Work coordinate for Y  
                        z=mz,    # Machine coordinate for Z (prevents accumulation)
                        c=wc     # Work coordinate for C
                    )
                    logger.debug(f"Parsed hybrid position - Work X,Y,C: ({wx},{wy},{wc}), Machine Z: {mz}")
                else:
                    # Only machine coordinates available (likely before homing)
                    position = Position4D(x=mx, y=my, z=mz, c=mc)
                    logger.debug(f"Parsed machine position only: X={mx}, Y={my}, Z={mz}, C={mc}")
                
                return position
            else:
                logger.warning(f"Could not match any position pattern in: {status_response}")
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
            self.is_homed = False  # Explicitly clear homed flag at start
            self.homing_in_progress = True  # Set homing in progress flag
            
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
                # Use the aggressive work coordinate reset method
                logger.info("Using aggressive coordinate reset approach...")
                reset_success = await self.reset_work_coordinate_offsets()
                
                if reset_success:
                    logger.info("✅ Z-axis coordinate reset successful")
                else:
                    logger.warning("⚠️  Z-axis coordinate reset had issues")
                    logger.info("Manual power cycle of FluidNC may be required for complete reset")
                
                # Verify final state
                final_status = await self._get_status_response()
                if final_status:
                    logger.info(f"Final position after coordinate reset: {final_status}")
                    
                    if "WCO:0.000,0.000,0.000" in final_status:
                        logger.info("✅ Work coordinate offsets successfully cleared")
                    elif "53.999" in final_status or ("WCO:" in final_status and "0.000,0.000,0.000" not in final_status):
                        logger.warning("⚠️  Work coordinate offsets persist")
                        logger.info("RECOMMENDATION: Manual power cycle of FluidNC controller required")
                        logger.info("WCO offsets are stored in non-volatile memory on some FluidNC versions")
                
                logger.info("Z-axis coordinate reset completed")
                
            except Exception as e:
                logger.warning(f"Failed to reset Z-axis coordinates: {e}")
                logger.info("FALLBACK: Manual power cycle of FluidNC controller recommended")
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
            self.homing_in_progress = False  # Clear homing in progress flag
            self.status = MotionStatus.IDLE
            
            self._notify_event("homing_complete", {
                "home_position": final_position.to_dict()
            })
            
            logger.info("Homing sequence completed")
            return True
            
        except Exception as e:
            self.status = MotionStatus.ERROR
            self.homing_in_progress = False  # Clear flag on error too
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
    
    async def restart_fluidnc(self) -> bool:
        """Restart FluidNC to clear persistent work coordinate offsets"""
        try:
            logger.info("Restarting FluidNC to clear persistent coordinate offsets")
            
            # Send FluidNC-specific restart command
            await self._send_command('$Bye')
            await asyncio.sleep(0.5)
            
            # If $Bye doesn't work, try the system restart command
            await self._send_command('$System/Control=RESTART')
            await asyncio.sleep(2.0)
            
            # Reinitialize connection
            await self._send_startup_commands()
            
            logger.info("FluidNC restart completed")
            return True
            
        except Exception as e:
            logger.error(f"FluidNC restart failed: {e}")
            return False
    
    # Status Updates
    async def _update_status(self):
        """Update controller status from FluidNC"""
        try:
            if not self.is_connected():
                self.status = MotionStatus.DISCONNECTED
                logger.debug("Status update: disconnected")
                return
            
            # Get status from FluidNC
            response = await self._send_command('?')
            logger.debug(f"Status response: {response}")
            
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
            else:
                # If we can't parse status but have a response, assume connected but unknown
                if response:
                    logger.warning(f"Unknown status format: {response}")
                else:
                    logger.warning("No status response received")
            
            # Always attempt to update position if we have a response, even before homing
            if response:
                position = self._parse_position_from_status(response)
                if position:
                    self.current_position = position
                    logger.debug(f"Position updated in status: {position}")
                else:
                    logger.debug("Could not parse position from status response")
                
        except Exception as e:
            logger.error(f"Status update failed: {e}")
            self.status = MotionStatus.ERROR

    def is_background_monitor_running(self) -> bool:
        """Check if background monitoring task is running"""
        return (self.monitor_running and 
                self.background_monitor_task is not None and 
                not self.background_monitor_task.done())

    async def _background_status_monitor(self):
        """Background task to continuously process FluidNC auto-reports"""
        logger.info("🚀 Background status monitor started")
        
        try:
            message_count = 0
            while self.monitor_running and self.is_connected():
                try:
                    # Read any available messages from FluidNC (including auto-reports)
                    messages = await self._read_all_messages()
                    
                    if messages:
                        message_count += len(messages)
                        if message_count % 10 == 0:  # Log every 10th batch of messages
                            logger.info(f"📈 Background monitor processed {message_count} messages so far")
                    
                    current_time = time.time()
                    
                    for message in messages:
                        # Log any status messages we receive
                        if '<' in message and '>' in message:
                            logger.debug(f"📡 Background monitor received: {message}")
                        
                        # Process status reports that contain position information
                        if '<' in message and '>' in message and ('MPos:' in message or 'WPos:' in message):
                            position = self._parse_position_from_status(message)
                            if position:
                                # Always update position immediately during movement
                                old_position = self.current_position
                                position_changed = position != old_position
                                
                                # Update more frequently during active movement
                                is_moving = self.status == MotionStatus.MOVING
                                should_update = (
                                    position_changed or  # Always update if position changed
                                    is_moving or  # Always update during movement
                                    current_time - self.last_position_update > 0.5  # Force update every 500ms
                                )
                                
                                if should_update:
                                    self.current_position = position
                                    self.last_position_update = current_time
                                    
                                    if position_changed:
                                        logger.info(f"🔄 Position changed: {old_position} → {position}")
                                    else:
                                        logger.debug(f"Background monitor refreshed position: {position}")
                            
                            # Update status from the same message
                            if 'Idle' in message:
                                self.status = MotionStatus.IDLE
                            elif 'Run' in message or 'Jog' in message:
                                self.status = MotionStatus.MOVING
                            elif 'Home' in message:
                                self.status = MotionStatus.HOMING
                            elif 'Alarm' in message:
                                self.status = MotionStatus.ALARM
                            elif 'Error' in message:
                                self.status = MotionStatus.ERROR
                    
                    # Sleep briefly to avoid overwhelming the system
                    await asyncio.sleep(0.05)  # 50ms intervals for processing
                    
                except Exception as e:
                    logger.debug(f"Background monitor processing error: {e}")
                    await asyncio.sleep(0.2)  # Back off on errors
                    
        except asyncio.CancelledError:
            logger.info("Background status monitor cancelled")
            raise
        except Exception as e:
            logger.error(f"Background status monitor error: {e}")
        finally:
            logger.info("Background status monitor stopped")
    
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
            
            # Update position after successful movement
            if result:
                # Wait for movement to complete 
                await self._wait_for_movement_complete()
                # Now get the final position
                await self._update_status()
                logger.info(f"Position updated after relative move: {self.current_position}")
            
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

    async def reset_work_coordinate_offsets(self) -> bool:
        """
        Reset work coordinate offsets using aggressive FluidNC commands.
        
        This method attempts multiple approaches to clear WCO offsets:
        1. Software commands ($RST=#, G92.1)
        2. Controller restart if software commands fail
        3. Verification of success
        
        Returns:
            bool: True if reset was successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot reset work coordinates - not connected to FluidNC")
            return False
            
        try:
            logger.info("Resetting work coordinate offsets using aggressive approach...")
            # Phase 1: Document current state
            logger.debug("Current work coordinate state before reset:")
            initial_status = await self._get_status_response()
            if initial_status:
                logger.info(f"Initial status: {initial_status}")
                has_wco_offset = "WCO:" in initial_status and not "WCO:0.000,0.000,0.000" in initial_status
            else:
                has_wco_offset = True  # Assume offset exists if we can't check
            await self._send_command('$#')
            await asyncio.sleep(0.5)
            # Phase 2: Attempt software-based reset
            logger.info("Phase 1: Attempting software-based coordinate reset...")
            try:
                logger.info("Sending $RST=# command...")
                await self._send_command('$RST=#')
                await asyncio.sleep(3.0)
                logger.info("Sending G92.1 command...")
                await self._send_command('G92.1')
                await asyncio.sleep(1.0)
                await self._send_command('G54')
                await asyncio.sleep(0.5)
                logger.info("Software commands completed successfully")
            except Exception as e:
                logger.warning(f"Software reset commands failed: {e}")
                logger.info("Will proceed to verification and potential controller restart")
            # Phase 3: Verify if software reset worked
            logger.info("Phase 2: Verifying coordinate reset success...")
            await asyncio.sleep(1.0)
            verification_status = await self._get_status_response()
            if verification_status:
                logger.info(f"Status after software reset: {verification_status}")
                wco_cleared = "WCO:0.000,0.000,0.000" in verification_status or "WCO:" not in verification_status
                if wco_cleared:
                    logger.info("✅ Software reset successful - WCO offsets cleared")
                    await self._send_command('$#')
                    await asyncio.sleep(0.5)
                    return True
                else:
                    logger.warning("⚠️  Software reset failed - WCO offsets persist")
                    logger.info("Attempting true FluidNC restart using $Bye command...")
                    restart_success = await self.restart_fluidnc()
                    if restart_success:
                        logger.info("✅ FluidNC restart successful - WCO offsets should be cleared")
                        # Verify after restart
                        await asyncio.sleep(2.0)
                        post_restart_status = await self._get_status_response()
                        if post_restart_status and ("WCO:0.000,0.000,0.000" in post_restart_status or "WCO:" not in post_restart_status):
                            logger.info("✅ WCO offsets cleared after restart")
                            return True
                        else:
                            logger.warning("❌ WCO offsets persist even after restart")
                            return False
                    else:
                        logger.error("❌ FluidNC restart failed")
                        return False
            return True
        except Exception as e:
            logger.error(f"Failed to reset work coordinate offsets: {e}")
            return False
    
    async def _restart_controller_for_wco_clear(self) -> bool:
        """
        Restart the FluidNC controller connection to clear persistent WCO offsets.
        
        This simulates a power cycle by:
        1. Disconnecting from controller
        2. Waiting for controller to reset
        3. Reconnecting and reinitializing
        4. Verifying WCO offsets are cleared
        
        Returns:
            bool: True if restart successful and WCO cleared, False otherwise
        """
        try:
            logger.info("Attempting controller restart to clear WCO offsets...")
            
            # Step 1: Disconnect from controller
            logger.info("Disconnecting from FluidNC controller...")
            await self.disconnect()
            
            # Step 2: Wait for controller to fully reset
            logger.info("Waiting for controller reset (simulating power cycle)...")
            await asyncio.sleep(5.0)  # Give controller time to reset
            
            # Step 3: Reconnect to controller
            logger.info("Reconnecting to FluidNC controller...")
            await self.connect()
            
            # Step 4: Verify WCO offsets are cleared
            logger.info("Verifying WCO offsets after controller restart...")
            await asyncio.sleep(2.0)  # Give controller time to stabilize
            
            final_status = await self._get_status_response()
            if final_status:
                logger.info(f"Status after controller restart: {final_status}")
                
                wco_cleared = "WCO:0.000,0.000,0.000" in final_status or "WCO:" not in final_status
                
                if wco_cleared:
                    logger.info("✅ Controller restart cleared WCO offsets successfully")
                    return True
                else:
                    logger.warning("⚠️  WCO offsets persist even after controller restart")
                    logger.info("This may indicate a deeper configuration or hardware issue")
                    return False
            else:
                logger.error("Could not verify status after controller restart")
                return False
                
        except Exception as e:
            logger.error(f"Controller restart failed: {e}")
            try:
                # Attempt to reconnect even if restart failed
                await self.connect()
                logger.info("Reconnected to controller after restart failure")
            except Exception as reconnect_error:
                logger.error(f"Failed to reconnect after restart failure: {reconnect_error}")
            return False
    
    async def complete_system_reset(self) -> bool:
        """
        Perform complete system reset of all work coordinate offsets.
        
        WARNING: This resets ALL coordinate systems (G54-G59) to default values.
        Use with caution as this affects all stored work coordinate systems.
        
        Returns:
            bool: True if reset was successful, False otherwise
        """
        if not self.is_connected():
            logger.error("Cannot perform system reset - not connected to FluidNC")
            return False
            
        try:
            logger.warning("Performing COMPLETE system reset - all coordinate systems will be reset!")
            
            # Reset all work coordinate offsets to defaults
            await self._send_command('$RST=#')
            await asyncio.sleep(2.0)  # Give more time for system reset
            
            # Ensure we're using G54 (default coordinate system)
            await self._send_command('G54')
            await asyncio.sleep(0.5)
            
            # Verify reset
            await self._send_command('$#')  # Show all coordinate systems
            await asyncio.sleep(0.5)
            
            logger.info("Complete system reset performed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to perform complete system reset: {e}")
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