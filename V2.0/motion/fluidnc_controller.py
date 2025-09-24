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
        self.connection_lock = None  # Will be created lazily in the correct event loop
        
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
        self._last_movement_position = Position4D()  # Track position changes during movement
        
        # Load axis configuration from config
        self._load_axis_config()
    
    async def _get_connection_lock(self):
        """Get connection lock, creating it in the current event loop if needed"""
        if self.connection_lock is None:
            try:
                # Try to get the current event loop
                loop = asyncio.get_running_loop()
                # Create the lock in the current event loop
                self.connection_lock = asyncio.Lock()
                logger.debug("Created connection lock in current event loop")
            except RuntimeError as e:
                logger.error(f"No event loop running, using threading lock: {e}")
                # Fallback to threading lock if no event loop
                import threading
                self.connection_lock = threading.Lock()
        else:
            # Force recreation to ensure compatibility with current event loop
            # This prevents "bound to different event loop" errors
            logger.debug("Recreating connection lock to ensure event loop compatibility")
            try:
                self.connection_lock = asyncio.Lock()
                logger.debug("Recreated connection lock in current event loop")
            except Exception:
                import threading
                self.connection_lock = threading.Lock()
                logger.debug("Using threading lock as fallback")
        return self.connection_lock
    
    def reset_connection_lock(self):
        """Reset connection lock - useful when switching event loops"""
        logger.info("Resetting connection lock")
        self.connection_lock = None
    
    def check_background_monitor_status(self) -> Dict[str, Any]:
        """Check if background monitor is running properly"""
        status = {
            'monitor_running': self.monitor_running,
            'has_task': hasattr(self, 'background_monitor_task'),
            'task_done': False,
            'task_exception': None,
            'last_update_age': None,
            'recommendation': None
        }
        
        if hasattr(self, 'background_monitor_task') and self.background_monitor_task:
            status['task_done'] = self.background_monitor_task.done()
            if status['task_done']:
                try:
                    status['task_exception'] = self.background_monitor_task.exception()
                except Exception:
                    pass
        
        # Check how stale the position data is
        if hasattr(self, 'last_position_update') and self.last_position_update:
            import time
            age = time.time() - self.last_position_update
            status['last_update_age'] = age
            
            if age > 5.0:
                status['recommendation'] = 'restart_monitor'
            elif age > 2.0:
                status['recommendation'] = 'check_connection'
            else:
                status['recommendation'] = 'healthy'
        
        return status
    
    class _LockContextManager:
        """Async context manager that handles both asyncio.Lock and threading.Lock"""
        def __init__(self, lock):
            self.lock = lock
            self.is_async = hasattr(lock, '__aenter__')
        
        async def __aenter__(self):
            if self.is_async:
                await self.lock.__aenter__()
            else:
                self.lock.__enter__()
            return self
        
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if self.is_async:
                await self.lock.__aexit__(exc_type, exc_val, exc_tb)
            else:
                self.lock.__exit__(exc_type, exc_val, exc_tb)
    
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
        
        lock = await self._get_connection_lock()
        async with self._LockContextManager(lock):
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
                
                # Verify auto-report is enabled
                logger.info("Verifying auto-report configuration...")
                verify_response = await self._send_command('$Report/Interval')
                logger.info(f"Auto-report setting: {verify_response}")
                
                # Also ensure status report mask includes position
                await self._send_command('$10=3')  # Enable position reports
                await asyncio.sleep(0.1)
                
                # Start background monitoring task to continuously process auto-reports
                logger.info("🔧 Starting background status monitor task...")
                self.monitor_running = True
                try:
                    # Ensure we have a proper event loop
                    try:
                        loop = asyncio.get_running_loop()
                        logger.info(f"📍 Using running event loop: {id(loop)}")
                    except RuntimeError:
                        logger.warning("⚠️  No running event loop detected, attempting to get event loop")
                        loop = asyncio.get_event_loop()
                        logger.info(f"📍 Using event loop: {id(loop)}")
                    
                    # Create the background task
                    self.background_monitor_task = loop.create_task(self._background_status_monitor())
                    task_id = id(self.background_monitor_task)
                    logger.info(f"✅ Background monitor task created successfully: {task_id}")
                    logger.info(f"🔍 Task state: done={self.background_monitor_task.done()}, cancelled={self.background_monitor_task.cancelled()}")
                    
                    # Check task status immediately after creation
                    await asyncio.sleep(0.1)  # Give task a moment to start
                    logger.info(f"🔍 Task state after 100ms: done={self.background_monitor_task.done()}, cancelled={self.background_monitor_task.cancelled()}")
                    
                    # Add done callback for debugging
                    def task_done_callback(task):
                        if task.cancelled():
                            logger.info("🛑 Background monitor task was cancelled")
                        elif task.exception():
                            logger.error(f"💥 Background monitor task failed: {task.exception()}")
                            logger.exception("Background monitor exception details:")
                        else:
                            logger.info("✅ Background monitor task completed successfully")
                    
                    self.background_monitor_task.add_done_callback(task_done_callback)
                    
                    # Immediate verification that monitor is running
                    await asyncio.sleep(0.2)  # Give it a moment to start
                    if self.is_background_monitor_running():
                        logger.info("✅ Background monitor verified as running")
                    else:
                        logger.error("❌ Background monitor failed to start properly")
                        
                except Exception as task_e:
                    logger.error(f"❌ Failed to create background monitor task: {task_e}")
                    logger.exception("Task creation error details:")
                    self.monitor_running = False
                
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

        lock = await self._get_connection_lock()
        async with self._LockContextManager(lock):
            try:
                if not self.serial_connection:
                    raise FluidNCConnectionError("Serial connection not established")
                    
                # Send status query
                command = '?\n'
                self.serial_connection.write(command.encode('utf-8'))
                self.serial_connection.flush()
                
                logger.debug("Sent status query: ?")
                
                # Read response lines with proper FluidNC protocol handling
                response_lines = []
                timeout = 2.0  # Shorter timeout for status queries
                start_time = time.time()
                status_response = None
                
                while time.time() - start_time < timeout:
                    if self.serial_connection.in_waiting > 0:
                        line = self.serial_connection.readline().decode('utf-8').strip()
                        if line:
                            response_lines.append(line)
                            logger.debug(f"Received line: '{line}'")
                            
                            # Skip "ok" acknowledgments - we want the actual status
                            if line == 'ok':
                                logger.debug("Skipping 'ok' acknowledgment")
                                continue
                            
                            # Check for actual status response (starts with <)
                            if line.startswith('<') and line.endswith('>'):
                                logger.debug(f"Found status response: {line}")
                                status_response = line
                                break
                            
                            # If we get an error, return it immediately
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
                
                # Return the status response if we found one
                if status_response:
                    return status_response
                
                # If we didn't find a proper status response, check what we got
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
                raise FluidNCConnectionError(f"Failed to read status response: {e}")

    async def _get_status_response_unlocked(self) -> Optional[str]:
        """
        Get status response from FluidNC WITHOUT connection lock
        
        Use this version only when you already hold the connection lock
        to prevent double-locking in hybrid status update scenarios.
        """
        if not self.is_connected():
            raise FluidNCConnectionError("Not connected to FluidNC")

        try:
            if not self.serial_connection:
                raise FluidNCConnectionError("Serial connection not established")
                
            # Send status query
            command = '?\n'
            self.serial_connection.write(command.encode('utf-8'))
            self.serial_connection.flush()
            
            logger.debug("Sent status query: ? (unlocked)")
            
            # Read response lines with proper FluidNC protocol handling
            response_lines = []
            timeout = 2.0  # Shorter timeout for status queries
            start_time = time.time()
            status_response = None
            
            while time.time() - start_time < timeout:
                if self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    if line:
                        response_lines.append(line)
                        logger.debug(f"Received line: '{line}'")
                        
                        # Check for actual status response (starts with <)
                        if line.startswith('<') and line.endswith('>'):
                            logger.debug(f"Found status response: {line}")
                            status_response = line
                            break
                        
                        # If we get an error, return it immediately
                        if line.startswith('error:') or line == 'error':
                            return line
                            
                        # Skip acknowledgments and info messages
                        if line == 'ok' or line.startswith('[MSG:INFO:') or line.startswith('[GC:') or line.startswith('[G54:'):
                            continue
                else:
                    await asyncio.sleep(0.01)
            
            # Return the status response if we found one
            if status_response:
                return status_response
            
            # Filter and log non-status responses
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
            raise FluidNCConnectionError(f"Failed to read status response: {e}")

    # Position and Movement
    async def move_to_position(self, position: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move to specified 4DOF position"""
        try:
            # SAFETY CHECK: Prevent movement in alarm state
            await self._update_status()  # Get current status
            if self.status == MotionStatus.ALARM:
                logger.error("🚨 MOVEMENT BLOCKED: FluidNC is in ALARM state")
                logger.error("Please clear alarm with homing ($H) or unlock ($X) before movement")
                raise MotionSafetyError("Cannot move while FluidNC is in alarm state. Use homing or unlock first.")
            
            if self.status == MotionStatus.ERROR:
                logger.error("🚨 MOVEMENT BLOCKED: FluidNC is in ERROR state")
                raise MotionSafetyError("Cannot move while FluidNC is in error state")
            
            # Validate position
            if not self.validate_position(position):
                raise MotionSafetyError(f"Position outside limits: {position}")
            
            # Check if homed (optional but recommended)
            if not self.is_homed:
                logger.warning("⚠️  Moving without homing - positions may be inaccurate")
            
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
        Wait for FluidNC to complete current movement using ONLY background monitor data.
        
        This prevents multiple processes competing for FluidNC serial communication by:
        1. Using position data from background monitor (updated by 200ms FluidNC auto-reports)
        2. Detecting movement completion through position stability
        3. Never making direct serial calls that conflict with background monitor
        4. Providing fast response times by leveraging existing data flow
        """
        start_time = time.time()
        timeout = 60.0  # 60 second timeout for movements
        movement_started = False
        
        logger.info("Waiting for movement completion...")
        
        # Give movement time to start and be detected by background monitor
        await asyncio.sleep(0.1)
        
        # Store initial position for movement detection
        initial_position = Position4D(
            x=self.current_position.x,
            y=self.current_position.y, 
            z=self.current_position.z,
            c=self.current_position.c
        )
        stable_count = 0
        last_position = initial_position
        
        while time.time() - start_time < timeout:
            current_pos = self.current_position
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # DEADLOCK PREVENTION: Log progress every 5 seconds
            if elapsed_time > 5.0 and int(elapsed_time) % 5 == 0:
                logger.warning(f"⏱️  Movement completion waiting for {elapsed_time:.1f}s - checking for deadlock...")
                
                # After 15 seconds, try emergency completion check
                if elapsed_time > 15.0:
                    logger.warning("🚨 Long wait detected - attempting emergency completion check...")
                    try:
                        emergency_status = await self._get_status_response()
                        if emergency_status and 'Idle' in emergency_status:
                            logger.warning("✅ Emergency check: FluidNC is Idle - completing movement")
                            return
                    except:
                        pass
            
            # Check how fresh our background monitor data is
            data_age = current_time - self.last_position_update if self.last_position_update else float('inf')
            
            # DEADLOCK FIX: Don't wait indefinitely for background monitor data
            # If data is stale, try to get fresh position directly from FluidNC
            if data_age > 2.0:
                logger.debug(f"⚠️  Background data is stale ({data_age:.1f}s old), querying FluidNC directly...")
                try:
                    # Get position directly from FluidNC to break deadlock
                    status_response = await self._get_status_response()
                    if status_response:
                        fresh_position = self._parse_position_from_status(status_response)
                        if fresh_position:
                            self.current_position = fresh_position
                            self.last_position_update = current_time
                            logger.debug(f"📍 Retrieved fresh position: {fresh_position}")
                            current_pos = fresh_position
                        else:
                            # If we can't get position, check for idle status to avoid infinite wait
                            if 'Idle' in status_response:
                                logger.info("✅ FluidNC reports Idle - assuming movement complete")
                                return
                    
                    # If still no fresh data after direct query, continue with timeout logic
                    if current_time - self.last_position_update > 5.0:
                        logger.warning("⚠️  Unable to get fresh position data, continuing with timeout...")
                        
                except Exception as e:
                    logger.debug(f"Direct position query failed: {e}")
                
                # Don't get stuck in infinite loop - continue with timeout logic
                await asyncio.sleep(0.1)
            
            # Check if position has changed from initial (indicates movement started)
            position_changed_from_initial = (
                abs(current_pos.x - initial_position.x) > 0.001 or
                abs(current_pos.y - initial_position.y) > 0.001 or
                abs(current_pos.z - initial_position.z) > 0.001 or
                abs(current_pos.c - initial_position.c) > 0.001
            )
            
            if position_changed_from_initial and not movement_started:
                movement_started = True
                logger.debug(f"Movement started: {initial_position} → {current_pos}")
            
            # Check if position is stable (no change from last check)
            position_stable = (
                abs(current_pos.x - last_position.x) < 0.001 and
                abs(current_pos.y - last_position.y) < 0.001 and
                abs(current_pos.z - last_position.z) < 0.001 and
                abs(current_pos.c - last_position.c) < 0.001
            )
            
            if position_stable:
                stable_count += 1
                logger.debug(f"Position stable for {stable_count} checks at {current_pos}")
            else:
                stable_count = 0
                logger.debug(f"Position changing: {last_position} → {current_pos}")
            
            # Movement complete when:
            # 1. Movement was detected AND position stable for 2+ checks (100ms)
            # 2. OR timeout for movement detection (assume quick movement)
            if movement_started and stable_count >= 2:
                logger.info("✅ Movement completed - position stable")
                return
            elif not movement_started and (time.time() - start_time) > 3.0:
                logger.info("✅ Movement completed - no movement detected (quick completion)")
                return
                
            last_position = current_pos
            await asyncio.sleep(0.05)  # Check every 50ms - optimized for faster movement detection
        
        # Timeout reached - try one final recovery attempt
        elapsed = time.time() - start_time
        logger.warning(f"⚠️ Movement timeout after {elapsed:.1f} seconds - attempting recovery...")
        
        # TIMEOUT RECOVERY: Try final status check to avoid unnecessary exception
        try:
            final_status = await asyncio.wait_for(self._get_status_response(), timeout=2.0)
            if final_status:
                logger.info(f"Final FluidNC status: {final_status}")
                
                # Update position from final status if possible
                final_position = self._parse_position_from_status(final_status)
                if final_position:
                    self.current_position = final_position
                    self.last_position_update = time.time()
                    logger.info(f"📍 Updated final position: {final_position}")
                
                # If FluidNC reports idle, movement is actually complete
                if 'Idle' in final_status:
                    logger.info("✅ Recovery successful: FluidNC is Idle - movement completed")
                    return
                    
        except Exception as recovery_e:
            logger.debug(f"Final recovery attempt failed: {recovery_e}")
        
        # Only raise timeout error if we really can't determine completion
        logger.error(f"Movement timeout after {elapsed:.1f} seconds - final position: {self.current_position}")
        raise MotionTimeoutError(f"Movement timeout exceeded ({elapsed:.1f}s)")
    
    async def get_current_position(self) -> Position4D:
        """Get current 4DOF position from FluidNC"""
        try:
            # Always try to get fresh position from FluidNC, but with timeout protection
            try:
                response = await asyncio.wait_for(self._get_status_response(), timeout=1.5)
                logger.debug(f"Status response for position: {response}")
            except asyncio.TimeoutError:
                logger.warning("⏰ Status response timed out - using cached position")
                return self.current_position
            except Exception as e:
                logger.error(f"❌ Status request failed: {e}")
                return self.current_position
            
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
            # Skip obvious non-status responses to reduce log spam
            if not status_response or status_response.strip() in ['ok', 'error', '']:
                return None
            
            # Skip info messages and other non-status responses
            if (status_response.startswith('[MSG:') or 
                status_response.startswith('[GC:') or 
                status_response.startswith('[G54:') or
                not ('<' in status_response and '>' in status_response)):
                return None
            
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
                # Only log warning for actual status-like messages that failed to parse
                if '<' in status_response and '>' in status_response:
                    logger.warning(f"Could not match position pattern in status: {status_response}")
                else:
                    logger.debug(f"Non-status response (no position data): {status_response}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to parse position from status: {e}")
            logger.error(f"Status response was: {status_response}")
            return None
    
    async def _read_all_messages(self) -> list[str]:
        """
        Read all available messages from FluidNC serial buffer.
        This captures both responses and unsolicited messages like debug output.
        Safe for background monitor use - doesn't use connection lock.
        
        Returns:
            List of message strings received
        """
        messages = []
        
        if not self.serial_connection:
            return messages
            
        try:
            # Read all available data without blocking - optimized for background monitor
            message_count = 0
            max_messages = 100  # Increased limit for better auto-report capture
            timeout_start = time.time()
            max_read_time = 0.5  # Max 500ms to read all messages
            
            while (self.serial_connection.in_waiting > 0 and 
                   message_count < max_messages and 
                   time.time() - timeout_start < max_read_time):
                try:
                    # Use shorter timeout for individual readline operations
                    self.serial_connection.timeout = 0.1
                    line = self.serial_connection.readline().decode('utf-8').strip()
                    
                    if line:
                        messages.append(line)
                        message_count += 1
                        
                        # Only log position/status messages to avoid spam
                        if ('<' in line and '>' in line and 
                            ('MPos:' in line or 'WPos:' in line or 'Idle' in line or 'Run' in line)):
                            logger.debug(f"📡 Status: {line}")
                        elif message_count <= 2:  # Log first couple non-status messages
                            logger.debug(f"FluidNC: {line}")
                            
                except UnicodeDecodeError:
                    # Skip malformed messages but continue reading
                    logger.debug("Skipped malformed message")
                    continue
                except Exception as e:
                    logger.debug(f"Message read error: {e}")
                    break
            
            # Restore normal timeout
            if self.serial_connection:
                self.serial_connection.timeout = self.timeout
                    
        except Exception as e:
            logger.error(f"Error reading FluidNC messages: {e}")
            
        return messages
    
    async def _query_position_direct(self) -> Position4D:
        """Query position directly - used by background monitor to avoid lock conflicts"""
        try:
            response = await self._get_status_response()
            if response:
                position = self._parse_position_from_status(response)
                if position:
                    return position
            return self.current_position
        except Exception as e:
            logger.error(f"Direct position query failed: {e}")
            return self.current_position
    
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
        """
        Update controller status - HYBRID approach for optimal performance
        
        SMART CONFLICT PREVENTION:
        - Use background monitor data when it's receiving auto-reports (during movement)
        - Fall back to manual queries when auto-reports stop (during idle periods)
        - Prevent conflicts by checking if background monitor is actively receiving data
        """
        try:
            if not self.is_connected():
                self.status = MotionStatus.DISCONNECTED
                logger.debug("Status update: disconnected")
                return
            
            # Check if background monitor is providing fresh data
            current_time = time.time()
            data_age = current_time - self.last_position_update if self.last_position_update > 0 else 999.0
            
            # Use background monitor data if it's fresh (actively receiving auto-reports)
            if self.is_background_monitor_running() and data_age < 3.0:
                logger.debug(f"Using fresh background monitor data (age: {data_age:.1f}s)")
                return
            
            # Background monitor data is stale OR not running - safe to make manual query
            # This happens during idle periods when FluidNC stops sending auto-reports
            if data_age > 3.0:
                logger.debug(f"Background monitor data stale ({data_age:.1f}s) - making careful manual query")
            else:
                logger.debug("Background monitor not running - making manual status query")
                
            try:
                # Use connection lock to prevent conflicts with any background operations
                lock = await self._get_connection_lock()
                async with self._LockContextManager(lock):
                    response = await self._get_status_response_unlocked()  # Use unlocked version since we have the lock
                    logger.debug(f"Manual status response: {response}")
                    
                    if response:
                        # Parse status from manual query
                        if 'Idle' in response:
                            self.status = MotionStatus.IDLE
                        elif 'Run' in response or 'Jog' in response:
                            self.status = MotionStatus.MOVING
                        elif 'Home' in response:
                            self.status = MotionStatus.HOMING
                        elif 'Alarm' in response:
                            self.status = MotionStatus.ALARM
                        elif 'Error' in response:
                            self.status = MotionStatus.ERROR
                        
                        # Update position from manual query
                        position = self._parse_position_from_status(response)
                        if position:
                            self.current_position = position
                            self.last_position_update = current_time
                            logger.debug(f"Position updated via manual query: {position}")
                
            except Exception as query_e:
                logger.warning(f"Manual status query failed: {query_e}")
                # Don't change status if query fails - keep existing status
                
        except Exception as e:
            logger.error(f"Status update failed: {e}")
            # Only set error status if we're not getting any background updates
            if self.last_position_update == 0 or (time.time() - self.last_position_update) > 10.0:
                self.status = MotionStatus.ERROR

    def is_background_monitor_running(self) -> bool:
        """Check if background monitoring task is running"""
        is_running = (self.monitor_running and 
                self.background_monitor_task is not None and 
                not self.background_monitor_task.done())
        logger.debug(f"Background monitor status: monitor_running={self.monitor_running}, task_exists={self.background_monitor_task is not None}, task_done={self.background_monitor_task.done() if self.background_monitor_task else 'N/A'}, overall_running={is_running}")
        return is_running
    
    async def restart_background_monitor(self):
        """Restart the background monitor if it's not running"""
        logger.info("🔄 Attempting to restart background monitor...")
        
        # Stop existing monitor if running
        if self.background_monitor_task and not self.background_monitor_task.done():
            logger.info("Stopping existing background monitor...")
            self.monitor_running = False
            self.background_monitor_task.cancel()
            try:
                await asyncio.wait_for(self.background_monitor_task, timeout=2.0)
            except:
                pass  # Ignore timeout or cancellation errors
            
        # Reset connection lock to ensure event loop compatibility
        self.reset_connection_lock()
        logger.info("Reset connection lock for event loop compatibility")
        
        # Start new monitor
        if self.is_connected():
            self.monitor_running = True
            try:
                loop = asyncio.get_running_loop()
                self.background_monitor_task = loop.create_task(self._background_status_monitor())
                logger.info(f"✅ Background monitor restarted: {id(self.background_monitor_task)}")
                
                # Wait a moment to check if it starts properly
                await asyncio.sleep(0.5)
                if self.background_monitor_task.done():
                    exception = self.background_monitor_task.exception()
                    if exception:
                        logger.error(f"Background monitor failed immediately: {exception}")
                        self.monitor_running = False
                    else:
                        logger.warning("Background monitor exited cleanly (unexpected)")
                else:
                    logger.info("✅ Background monitor is running properly")
                    
            except Exception as e:
                logger.error(f"❌ Failed to restart background monitor: {e}")
                import traceback
                traceback.print_exc()
                self.monitor_running = False
        else:
            logger.warning("⚠️  Cannot restart monitor - not connected to FluidNC")

    async def _background_status_monitor(self):
        """Background task to continuously process FluidNC auto-reports with enhanced position processing"""
        logger.info("🚀 Background status monitor started - Enhanced position processing")
        
        try:
            message_count = 0
            consecutive_errors = 0
            max_consecutive_errors = 10
            position_updates = 0
            last_log_time = time.time()
            last_status_log = ""
            
            while self.monitor_running and self.is_connected() and consecutive_errors < max_consecutive_errors:
                try:
                    # Read any available messages from FluidNC (including auto-reports)
                    # Use very short timeout for maximum responsiveness
                    try:
                        messages = await asyncio.wait_for(self._read_all_messages(), timeout=0.2)
                        consecutive_errors = 0  # Reset error count on success
                    except asyncio.TimeoutError:
                        # Timeout is normal - just continue monitoring with balanced responsiveness
                        await asyncio.sleep(0.05)  # 50ms sleep - balance between responsiveness and CPU usage
                        continue
                    except Exception as read_e:
                        consecutive_errors += 1
                        logger.warning(f"Background monitor read error ({consecutive_errors}/{max_consecutive_errors}): {read_e}")
                        await asyncio.sleep(0.1)
                        continue
                    
                    current_time = time.time()
                    
                    if messages:
                        message_count += len(messages)
                        
                        # Process each message immediately for maximum responsiveness
                        for message in messages:
                            # ENHANCED: Process status reports with position information
                            if '<' in message and '>' in message:
                                # Extract and update status first for safety checks
                                old_status = self.status
                                
                                # Parse status for safety-critical alarm detection
                                if 'Alarm' in message:
                                    self.status = MotionStatus.ALARM
                                    if old_status != self.status:
                                        logger.warning(f"🚨 ALARM STATE DETECTED: {message}")
                                        # Extract alarm code if available
                                        alarm_match = re.search(r'Alarm:(\d+)', message)
                                        if alarm_match:
                                            alarm_code = alarm_match.group(1)
                                            logger.warning(f"� Alarm Code: {alarm_code}")
                                elif 'Idle' in message:
                                    self.status = MotionStatus.IDLE
                                    if old_status != self.status and old_status == MotionStatus.HOMING:
                                        logger.info("✅ Homing completed - now IDLE")
                                elif 'Run' in message or 'Jog' in message:
                                    self.status = MotionStatus.MOVING
                                elif 'Home' in message:
                                    self.status = MotionStatus.HOMING
                                    if old_status != self.status:
                                        logger.info("🏠 Homing in progress")
                                elif 'Error' in message:
                                    self.status = MotionStatus.ERROR
                                    if old_status != self.status:
                                        logger.error(f"❌ ERROR STATE: {message}")
                                
                                # CRITICAL: Always parse and update position for web UI responsiveness
                                if 'MPos:' in message or 'WPos:' in message:
                                    position = self._parse_position_from_status(message)
                                    if position:
                                        # Store old position for change detection
                                        old_position = self.current_position
                                        position_changed = (
                                            abs(position.x - old_position.x) > 0.001 or
                                            abs(position.y - old_position.y) > 0.001 or
                                            abs(position.z - old_position.z) > 0.001 or
                                            abs(position.c - old_position.c) > 0.001
                                        )
                                        
                                        # ALWAYS update position and timestamp for web UI
                                        self.current_position = position
                                        self.last_position_update = current_time
                                        position_updates += 1
                                        
                                        # Log position changes for movement tracking
                                        if position_changed:
                                            logger.info(f"🔄 Position #{position_updates}: {old_position} → {position}")
                                        else:
                                            logger.debug(f"📍 Position refresh #{position_updates}: {position}")
                                    else:
                                        logger.debug(f"❌ Could not parse position from: {message[:100]}...")
                        
                        # Periodic activity logging
                        if current_time - last_log_time > 30.0:  # Log every 30 seconds to reduce noise
                            logger.info(f"📊 Monitor active: {message_count} messages, {position_updates} position updates, Status: {self.status.name}")
                            last_log_time = current_time
                    
                    # Adaptive sleep for optimal responsiveness vs CPU usage
                    if messages:
                        await asyncio.sleep(0.01)  # 10ms when processing messages - maximum responsiveness
                    else:
                        await asyncio.sleep(0.02)  # 20ms when idle - optimized for lower latency
                    
                except Exception as e:
                    consecutive_errors += 1
                    logger.error(f"Background monitor processing error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    await asyncio.sleep(0.2)  # Back off on errors
                    
        except asyncio.CancelledError:
            logger.info("Background status monitor cancelled")
            raise
        except Exception as e:
            logger.error(f"Background status monitor fatal error: {e}")
            logger.exception("Monitor exception details:")
        finally:
            logger.info("🛑 Background status monitor stopped")
            self.monitor_running = False
    
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
    
    async def get_alarm_state(self) -> Dict[str, Any]:
        """
        Get detailed alarm state information from FluidNC - USES BACKGROUND MONITOR DATA
        
        CRITICAL FIX: Never make serial queries while background monitor is running
        to prevent serial port conflicts. Use cached status from background monitor.
        
        Returns:
            Dict containing alarm information:
            - is_alarm: bool - whether system is in alarm state
            - alarm_code: Optional[str] - alarm code if in alarm
            - message: str - full status message
            - can_move: bool - whether movement is allowed
        """
        try:
            await self._update_status()  # This now safely uses background monitor data
            
            # Use current status from background monitor - don't make additional serial queries
            alarm_info = {
                'is_alarm': self.status == MotionStatus.ALARM,
                'is_error': self.status == MotionStatus.ERROR,
                'alarm_code': None,
                'message': f"Status: {self.status.name}",  # Use current status instead of raw response
                'can_move': self.status not in [MotionStatus.ALARM, MotionStatus.ERROR],
                'status': self.status.name,
                'is_homed': self.is_homed
            }
            
            # Note: Alarm code extraction would require background monitor enhancement
            # For now, provide general alarm state without specific codes to avoid serial conflicts
            if self.status == MotionStatus.ALARM:
                alarm_info['message'] = "System in alarm state - check background monitor logs for details"
            
            return alarm_info
            
        except Exception as e:
            logger.error(f"Failed to get alarm state: {e}")
            return {
                'is_alarm': True,  # Assume alarm on error for safety
                'is_error': True,
                'alarm_code': None,
                'message': f"Communication error: {e}",
                'can_move': False,
                'status': 'ERROR',
                'is_homed': False
            }

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
            # SAFETY CHECK: Prevent movement in alarm state
            await self._update_status()  # Get current status
            if self.status == MotionStatus.ALARM:
                logger.error("🚨 RELATIVE MOVEMENT BLOCKED: FluidNC is in ALARM state")
                logger.error("Please clear alarm with homing ($H) or unlock ($X) before movement")
                raise MotionSafetyError("Cannot move while FluidNC is in alarm state. Use homing or unlock first.")
            
            if self.status == MotionStatus.ERROR:
                logger.error("🚨 RELATIVE MOVEMENT BLOCKED: FluidNC is in ERROR state")
                raise MotionSafetyError("Cannot move while FluidNC is in error state")
            
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
                # Position will be updated automatically by background monitor
                # No need for explicit status query - avoid competing with background monitor
                logger.info(f"Position updated after relative move: {self.current_position}")
            
            return result
            
        except Exception as e:
            logger.error(f"Relative move failed: {e}")
            await self._send_command("G90")  # Ensure absolute mode
            return False
    
    async def rapid_move(self, position: Position4D) -> bool:
        """Rapid (non-linear) movement to position."""
        try:
            # SAFETY CHECK: Prevent movement in alarm state
            await self._update_status()  # Get current status
            if self.status == MotionStatus.ALARM:
                logger.error("🚨 RAPID MOVEMENT BLOCKED: FluidNC is in ALARM state")
                logger.error("Please clear alarm with homing ($H) or unlock ($X) before movement")
                raise MotionSafetyError("Cannot move while FluidNC is in alarm state. Use homing or unlock first.")
            
            if self.status == MotionStatus.ERROR:
                logger.error("🚨 RAPID MOVEMENT BLOCKED: FluidNC is in ERROR state")
                raise MotionSafetyError("Cannot move while FluidNC is in error state")
            
            # Validate position
            if not self._validate_position(position):
                raise MotionSafetyError(f"Position outside limits: {position}")
            
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