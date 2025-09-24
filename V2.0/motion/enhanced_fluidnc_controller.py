"""
Enhanced FluidNC Controller using Protocol-Compliant Communication

This is a rebuilt FluidNC controller that properly implements the FluidNC
real-time reporting protocol, eliminating message confusion and improving
response times significantly.

Key improvements:
- Proper separation of immediate vs line-based commands
- Protocol-compliant message handling
- Auto-reporting for real-time updates without polling overhead
- Simplified communication flow without lock contention
- Enhanced movement completion detection

Author: Scanner System Development  
Created: September 2025
"""

import asyncio
import logging
import time
import serial
import serial.tools.list_ports
from typing import Optional, Dict, Any, List
from pathlib import Path

from motion.base import (
    MotionController, Position4D, MotionStatus, AxisType,
    MotionLimits, MotionCapabilities
)
from motion.fluidnc_protocol import FluidNCCommunicator, MessageType, FluidNCMessage
from core.exceptions import (
    FluidNCError, FluidNCConnectionError, FluidNCCommandError,
    MotionSafetyError, MotionTimeoutError, MotionControlError
)
from core.events import ScannerEvent, EventPriority
from core.config_manager import ConfigManager


logger = logging.getLogger(__name__)


class EnhancedFluidNCController(MotionController):
    """
    Enhanced FluidNC Controller using Protocol-Compliant Communication
    
    Features:
    - Proper FluidNC protocol implementation
    - Real-time auto-reporting without polling overhead  
    - Separated immediate and line-based commands
    - Simplified message handling without lock contention
    - Fast movement completion detection
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Serial connection settings
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baudrate = config.get('baudrate', 115200)
        self.timeout = config.get('timeout', 2.0)
        
        # Serial and protocol
        self.serial_connection: Optional[serial.Serial] = None
        self.communicator: Optional[FluidNCCommunicator] = None
        
        # Motion state
        self.current_position = Position4D()
        self.target_position = Position4D()
        self.is_homed = False
        self.axis_limits: Dict[str, MotionLimits] = {}
        
        # Movement tracking
        self.movement_start_time = 0
        self.movement_start_position = Position4D()
        self.position_stable_count = 0
        self.last_position_change = 0
        
        # Load axis configuration
        self._load_axis_config()
    
    def _load_axis_config(self):
        """Load axis configuration with default limits"""
        try:
            # Set default axis limits for 4DOF scanner system
            default_limits = {
                'x': MotionLimits(min_limit=0, max_limit=200, max_feedrate=1000),
                'y': MotionLimits(min_limit=0, max_limit=200, max_feedrate=1000),
                'z': MotionLimits(min_limit=-360, max_limit=360, max_feedrate=500),
                'c': MotionLimits(min_limit=-90, max_limit=90, max_feedrate=300)
            }
            
            self.axis_limits = default_limits
            logger.info(f"Loaded default axis limits: {list(self.axis_limits.keys())}")
        except Exception as e:
            logger.warning(f"Could not load axis configuration: {e}")
    
    async def initialize(self, auto_unlock: bool = False) -> bool:
        """Initialize FluidNC connection using enhanced protocol"""
        try:
            logger.info(f"🚀 Initializing Enhanced FluidNC Controller on {self.port}")
            
            # Open serial connection
            if not await self._connect_serial():
                return False
            
            # Create protocol communicator
            if not self.serial_connection:
                raise FluidNCConnectionError("Serial connection required")
            self.communicator = FluidNCCommunicator(self.serial_connection)
            
            # Register for position updates
            self.communicator.protocol.add_message_handler(
                MessageType.STATUS_REPORT, 
                self._on_status_update
            )
            
            # Start protocol handler
            await self.communicator.start()
            
            # Wait for FluidNC startup
            await asyncio.sleep(2.0)
            
            # Send initial configuration
            await self._configure_fluidnc(auto_unlock=auto_unlock)
            
            # Get initial status
            try:
                status_info = await self.communicator.get_status()
                self.current_position = status_info['position']
                self.status = status_info['status']
            except Exception as e:
                logger.warning(f"Initial status query failed: {e}")
                # Continue - status will update via auto-reports
            
            self._notify_event("motion_initialized", {
                "port": self.port,
                "status": self.status.value,
                "protocol": "enhanced"
            })
            
            logger.info("✅ Enhanced FluidNC Controller initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Enhanced FluidNC Controller: {e}")
            self.status = MotionStatus.ERROR
            return False
    
    async def shutdown(self) -> bool:
        """Shutdown FluidNC connection"""
        try:
            logger.info("🛑 Shutting down Enhanced FluidNC Controller")
            
            # Stop communicator
            if self.communicator:
                await self.communicator.stop()
                self.communicator = None
            
            # Close serial connection
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.serial_connection = None
            
            self.status = MotionStatus.DISCONNECTED
            self._notify_event("motion_shutdown")
            
            logger.info("✅ Enhanced FluidNC Controller shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during Enhanced FluidNC shutdown: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if FluidNC is connected"""
        return (self.serial_connection and 
                self.serial_connection.is_open and 
                self.communicator and 
                self.communicator.protocol.running)
    
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
                timeout=0.1,  # Short timeout for non-blocking reads
                write_timeout=1.0
            )
            
            logger.info(f"✅ Serial connection established: {self.port}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Serial connection failed: {e}")
            return False
    
    async def _detect_fluidnc_port(self) -> Optional[str]:
        """Detect FluidNC device port"""
        try:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                if any(keyword in (port.description or '').lower() 
                      for keyword in ['usb', 'serial', 'cp210', 'ch340', 'ftdi']):
                    logger.info(f"Detected potential FluidNC port: {port.device}")
                    return port.device
        except Exception as e:
            logger.error(f"Port detection failed: {e}")
        
        return None
    
    async def _configure_fluidnc(self, auto_unlock: bool = False):
        """Configure FluidNC for optimal communication"""
        try:
            # Check initial status
            initial_status = await self.communicator.get_status()
            logger.info(f"Initial FluidNC status: {initial_status}")
            
            # Handle alarm state
            if initial_status['status'] == MotionStatus.ALARM:
                if auto_unlock:
                    logger.info("🔓 Auto-unlocking from alarm state...")
                    success = await self.communicator.send_gcode('$X')
                    if success:
                        await asyncio.sleep(0.5)
                        logger.info("✅ FluidNC unlocked")
                    else:
                        logger.warning("⚠️ Auto-unlock failed")
                else:
                    logger.warning("⚠️ FluidNC in alarm state - manual unlock required")
            
            # Configure reporting (already done in communicator.start())
            # Set basic G-code modes
            config_commands = [
                'G21',  # Metric units
                'G90',  # Absolute positioning
                'G94',  # Feed rate in units/minute
                'M5',   # Spindle off
                'M9'    # Coolant off
            ]
            
            for cmd in config_commands:
                try:
                    await self.communicator.send_gcode(cmd)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Config command '{cmd}' failed: {e}")
            
            logger.info("✅ FluidNC configuration complete")
            
        except Exception as e:
            logger.error(f"❌ FluidNC configuration failed: {e}")
    
    async def _on_status_update(self, message: FluidNCMessage):
        """Handle status updates from protocol"""
        if not message.data:
            return
            
        # Extract position
        if 'mpos' in message.data:
            pos_data = message.data['mpos']
            new_position = Position4D(
                x=pos_data.get('x', 0),
                y=pos_data.get('y', 0),
                z=pos_data.get('z', 0),
                c=pos_data.get('c', 0)
            )
            
            # Check for position changes
            if self._position_changed(self.current_position, new_position):
                self.current_position = new_position
                self.last_position_change = time.time()
                self.position_stable_count = 0
                logger.debug(f"📍 Position update: {new_position}")
            else:
                self.position_stable_count += 1
        
        # Extract status
        state = message.data.get('state', '').lower()
        old_status = self.status
        
        if state == 'idle':
            self.status = MotionStatus.IDLE
        elif state in ['run', 'jog']:
            self.status = MotionStatus.MOVING
        elif state == 'alarm':
            self.status = MotionStatus.ALARM
        elif state == 'home':
            self.status = MotionStatus.HOMING
        
        # Log status changes
        if old_status != self.status:
            logger.info(f"🔄 Status: {old_status.name} → {self.status.name}")
    
    def _position_changed(self, pos1: Position4D, pos2: Position4D, threshold: float = 0.001) -> bool:
        """Check if position has changed significantly"""
        return (abs(pos1.x - pos2.x) > threshold or
                abs(pos1.y - pos2.y) > threshold or
                abs(pos1.z - pos2.z) > threshold or
                abs(pos1.c - pos2.c) > threshold)
    
    # Motion Control Methods
    
    async def get_current_position(self) -> Position4D:
        """Get current position (from real-time auto-reports)"""
        # Request fresh status (immediate command)
        await self.communicator.protocol.get_status()
        # Position is updated via auto-reports in real-time
        return self.current_position
    
    async def move_to_position(self, position: Position4D, feedrate: float = 100.0) -> bool:
        """Move to absolute position with enhanced completion detection"""
        try:
            # Validate position
            if not self._validate_position(position):
                raise MotionSafetyError(f"Position outside limits: {position}")
            
            # Check status
            if self.status not in [MotionStatus.IDLE, MotionStatus.MOVING]:
                raise MotionSafetyError(f"Cannot move in status {self.status}")
            
            logger.info(f"🎯 Moving to position: {position} at F{feedrate}")
            
            # Record movement start
            self.movement_start_time = time.time()
            self.movement_start_position = self.current_position
            self.target_position = position
            
            # Send movement command
            success = await self.communicator.move_to_position(position, feedrate)
            if not success:
                logger.error("❌ Movement command failed")
                return False
            
            # Wait for movement completion
            await self._wait_for_movement_complete()
            
            # Get final position
            final_position = await self.get_current_position()
            
            # Verify we reached target
            if self._position_changed(final_position, position, threshold=0.5):
                logger.warning(f"⚠️ Position accuracy warning: target={position}, actual={final_position}")
            
            logger.info(f"✅ Movement complete: {final_position}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Move to position failed: {e}")
            self.status = MotionStatus.ERROR
            return False
    
    async def _wait_for_movement_complete(self):
        """Wait for movement completion using real-time status updates"""
        start_time = time.time()
        timeout = 60.0  # 60 second timeout
        
        logger.debug("⏳ Waiting for movement completion...")
        
        # Wait for movement to start
        while self.status != MotionStatus.MOVING and time.time() - start_time < 5.0:
            await asyncio.sleep(0.05)
        
        if self.status != MotionStatus.MOVING:
            logger.warning("⚠️ Movement never started")
            return
        
        # Wait for movement to complete
        while time.time() - start_time < timeout:
            if self.status == MotionStatus.IDLE:
                # FluidNC reports IDLE, now verify position is stable
                stable_time = 0.5  # Wait for position to stabilize
                stable_start = time.time()
                
                while time.time() - stable_start < stable_time:
                    if self.status != MotionStatus.IDLE:
                        # Movement resumed, continue waiting
                        break
                    await asyncio.sleep(0.05)
                else:
                    # Position was stable for required time
                    movement_time = time.time() - start_time
                    logger.info(f"✅ Movement completed in {movement_time:.3f}s")
                    return
            
            await asyncio.sleep(0.05)  # 50ms polling for responsiveness
        
        # Timeout
        logger.error(f"⏰ Movement timeout after {timeout}s")
        raise MotionTimeoutError("Movement completion timeout")
    
    async def move_relative(self, delta: Position4D, feedrate: float = 100.0) -> bool:
        """Move relative to current position"""
        try:
            # Calculate target position
            current = await self.get_current_position()
            target = Position4D(
                x=current.x + delta.x,
                y=current.y + delta.y,
                z=current.z + delta.z,
                c=current.c + delta.c
            )
            
            logger.info(f"🔄 Relative move: {delta} (current: {current} → target: {target})")
            
            # Switch to relative mode
            await self.communicator.send_gcode('G91')
            
            # Send relative movement
            gcode = f"G1 X{delta.x:.3f} Y{delta.y:.3f} Z{delta.z:.3f} C{delta.c:.3f} F{feedrate}"
            success = await self.communicator.send_gcode(gcode)
            
            # Switch back to absolute mode
            await self.communicator.send_gcode('G90')
            
            if success:
                # Wait for completion
                await self._wait_for_movement_complete()
                
                # Get final position
                final_position = await self.get_current_position()
                logger.info(f"✅ Relative move complete: {final_position}")
                return True
            else:
                logger.error("❌ Relative movement command failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Relative move failed: {e}")
            # Ensure absolute mode
            try:
                await self.communicator.send_gcode('G90')
            except:
                pass
            return False
    
    async def home(self) -> bool:
        """Home all axes"""
        return await self.home_all_axes()
    
    async def home_all_axes(self) -> bool:
        """Home all axes using $H command"""
        try:
            logger.info("🏠 Starting homing sequence")
            self.status = MotionStatus.HOMING
            self.is_homed = False
            
            # Send homing command with extended timeout
            success = await self.communicator.home_all()
            
            if success:
                # Wait for homing to complete
                await self._wait_for_homing_complete()
                
                # Get position after homing
                self.current_position = await self.get_current_position()
                self.is_homed = True
                
                logger.info(f"✅ Homing complete: {self.current_position}")
                
                # Clear work coordinates for continuous rotation axis (Z)
                await self.communicator.send_gcode('G10 L20 P1 Z0')
                
                return True
            else:
                logger.error("❌ Homing command failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Homing failed: {e}")
            self.status = MotionStatus.ERROR
            return False
    
    async def _wait_for_homing_complete(self):
        """Wait for homing to complete"""
        start_time = time.time()
        timeout = 30.0  # 30 second timeout for homing
        
        logger.debug("⏳ Waiting for homing completion...")
        
        while time.time() - start_time < timeout:
            if self.status == MotionStatus.IDLE:
                # Homing complete
                homing_time = time.time() - start_time
                logger.info(f"✅ Homing completed in {homing_time:.3f}s")
                return
            elif self.status == MotionStatus.ALARM:
                raise MotionControlError("Homing failed - alarm state")
            
            await asyncio.sleep(0.1)
        
        # Timeout
        logger.error(f"⏰ Homing timeout after {timeout}s")
        raise MotionTimeoutError("Homing completion timeout")
    
    async def emergency_stop(self) -> bool:
        """Emergency stop using immediate commands"""
        try:
            logger.warning("🚨 Emergency stop activated")
            
            if self.communicator:
                await self.communicator.emergency_stop()
            
            self.status = MotionStatus.EMERGENCY_STOP
            
            self._notify_event("emergency_stop", {
                "reason": "Manual emergency stop"
            })
            
            return True
            
        except Exception as e:
            logger.critical(f"❌ Emergency stop failed: {e}")
            return False
    
    def _validate_position(self, position: Position4D) -> bool:
        """Validate position against axis limits"""
        try:
            axes = {'x': position.x, 'y': position.y, 'z': position.z, 'c': position.c}
            
            for axis_name, value in axes.items():
                if axis_name in self.axis_limits:
                    limits = self.axis_limits[axis_name]
                    if not (limits.min_limit <= value <= limits.max_limit):
                        logger.error(f"Position {axis_name}={value} outside limits [{limits.min_limit}, {limits.max_limit}]")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Position validation error: {e}")
            return False
    
    def get_protocol_stats(self) -> Dict[str, Any]:
        """Get communication protocol statistics"""
        if self.communicator:
            return self.communicator.get_stats()
        return {}
    
    def get_capabilities(self) -> MotionCapabilities:
        """Get motion system capabilities"""
        return MotionCapabilities(
            axes_count=4,
            supports_homing=True,
            supports_soft_limits=True,
            supports_probe=False,
            max_feedrate=1000.0,
            position_resolution=0.001
        )