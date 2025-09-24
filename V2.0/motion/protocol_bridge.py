"""
Integration Bridge: Enhanced FluidNC Protocol → Existing Web Interface

This module provides a compatibility layer that allows the existing web interface
and scanning system to use the new enhanced FluidNC protocol without requiring
major changes to the existing codebase.

Key Features:
- Drop-in replacement for current FluidNCController
- Maintains existing API compatibility
- Provides enhanced performance with new protocol
- Supports all existing motion control operations

Usage:
Replace imports in main.py:
    from motion.fluidnc_controller import FluidNCController
    # Replace with:
    from motion.protocol_bridge import ProtocolBridgeController as FluidNCController

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import time
import serial
import serial.tools.list_ports
from typing import Optional, Dict, Any, List

# Enhanced protocol imports
from motion.fluidnc_protocol import FluidNCCommunicator, MessageType, FluidNCMessage

# Existing interface imports
from motion.base import (
    MotionController, Position4D, MotionStatus, AxisType,
    MotionLimits, MotionCapabilities
)
from core.exceptions import (
    FluidNCError, FluidNCConnectionError, FluidNCCommandError,
    MotionSafetyError, MotionTimeoutError, MotionControlError
)
from core.events import ScannerEvent, EventPriority


logger = logging.getLogger(__name__)


class ProtocolBridgeController(MotionController):
    """
    Bridge Controller: Enhanced Protocol → Existing Interface
    
    This class provides a drop-in replacement for the existing FluidNCController
    while using the new enhanced protocol system underneath for better performance.
    
    Maintains full API compatibility with existing web interface and scanning system.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Serial connection settings
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baudrate = config.get('baudrate', 115200)
        self.timeout = config.get('timeout', 2.0)
        
        # Enhanced protocol components
        self.serial_connection: Optional[serial.Serial] = None
        self.communicator: Optional[FluidNCCommunicator] = None
        
        # State tracking (compatible with existing interface)
        self.current_position = Position4D()
        self.target_position = Position4D()
        self.is_homed = False
        self.homing_in_progress = False
        self.axis_limits: Dict[str, MotionLimits] = {}
        
        # Performance tracking
        self.last_position_update = 0
        self.stats = {
            'commands_sent': 0,
            'movements_completed': 0,
            'avg_movement_time': 0,
            'position_updates': 0
        }
        
        # Load default axis limits
        self._load_default_limits()
    
    def _load_default_limits(self):
        """Load default axis limits for 4DOF scanner"""
        self.axis_limits = {
            'x': MotionLimits(min_limit=0, max_limit=200, max_feedrate=1000),
            'y': MotionLimits(min_limit=0, max_limit=200, max_feedrate=1000),
            'z': MotionLimits(min_limit=-360, max_limit=360, max_feedrate=500),
            'c': MotionLimits(min_limit=-90, max_limit=90, max_feedrate=300)
        }
    
    # EXISTING API COMPATIBILITY METHODS
    
    async def initialize(self, auto_unlock: bool = False) -> bool:
        """Initialize FluidNC connection (existing API)"""
        try:
            logger.info(f"🚀 Initializing Enhanced FluidNC Controller on {self.port}")
            
            # Connect serial
            if not await self._connect_serial():
                return False
            
            # Create enhanced communicator
            if not self.serial_connection:
                raise FluidNCConnectionError("Serial connection required")
            
            self.communicator = FluidNCCommunicator(self.serial_connection)
            
            # Register for status updates
            self.communicator.protocol.add_message_handler(
                MessageType.STATUS_REPORT, 
                self._on_status_update
            )
            
            # Start protocol
            await self.communicator.start()
            
            # Configuration
            await self._configure_fluidnc(auto_unlock=auto_unlock)
            
            # Get initial status
            try:
                await self._update_initial_status()
            except Exception as e:
                logger.warning(f"Initial status update failed: {e}")
            
            self._notify_event("motion_initialized", {
                "port": self.port,
                "status": self.status.value,
                "protocol": "enhanced"
            })
            
            logger.info("✅ Enhanced FluidNC Controller initialized")
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced FluidNC initialization failed: {e}")
            self.status = MotionStatus.ERROR
            return False
    
    async def shutdown(self) -> bool:
        """Shutdown FluidNC connection (existing API)"""
        try:
            logger.info("🛑 Shutting down Enhanced FluidNC Controller")
            
            if self.communicator:
                await self.communicator.stop()
                self.communicator = None
            
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.serial_connection = None
            
            self.status = MotionStatus.DISCONNECTED
            self._notify_event("motion_shutdown")
            
            logger.info("✅ Enhanced FluidNC shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced FluidNC shutdown error: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check connection status (existing API)"""
        return (self.serial_connection and 
                self.serial_connection.is_open and 
                self.communicator and 
                self.communicator.protocol.running)
    
    async def get_current_position(self) -> Position4D:
        """Get current position (existing API)"""
        if self.communicator:
            # Trigger fresh status update
            await self.communicator.protocol.get_status()
            # Position updated via auto-reports
            return self.current_position
        return self.current_position
    
    async def move_to_position(self, position: Position4D, feedrate: float = 100.0) -> bool:
        """Move to absolute position (existing API)"""
        if not self.communicator:
            return False
            
        try:
            logger.info(f"🎯 Moving to: {position} at F{feedrate}")
            
            start_time = time.time()
            success = await self.communicator.move_to_position(position, feedrate)
            
            if success:
                # Wait for completion with enhanced detection
                await self._wait_for_movement_complete()
                
                completion_time = time.time() - start_time
                self.stats['movements_completed'] += 1
                self.stats['avg_movement_time'] = (
                    (self.stats['avg_movement_time'] * (self.stats['movements_completed'] - 1) + completion_time) /
                    self.stats['movements_completed']
                )
                
                logger.info(f"✅ Movement completed in {completion_time:.3f}s")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Move to position failed: {e}")
            return False
    
    async def move_relative(self, delta: Position4D, feedrate: float = 100.0) -> bool:
        """Move relative to current position (existing API)"""
        if not self.communicator:
            return False
            
        try:
            logger.info(f"🔄 Relative move: {delta} at F{feedrate}")
            
            start_time = time.time()
            
            # Calculate target position  
            current = await self.get_current_position()
            target = Position4D(
                x=current.x + delta.x,
                y=current.y + delta.y,
                z=current.z + delta.z,
                c=current.c + delta.c
            )
            
            # Execute relative move
            await self.communicator.send_gcode('G91')  # Relative mode
            gcode = f"G1 X{delta.x:.3f} Y{delta.y:.3f} Z{delta.z:.3f} C{delta.c:.3f} F{feedrate}"
            success = await self.communicator.send_gcode(gcode)
            await self.communicator.send_gcode('G90')  # Absolute mode
            
            if success:
                await self._wait_for_movement_complete()
                
                completion_time = time.time() - start_time
                logger.info(f"✅ Relative move completed in {completion_time:.3f}s")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Relative move failed: {e}")
            # Ensure absolute mode
            try:
                if self.communicator:
                    await self.communicator.send_gcode('G90')
            except:
                pass
            return False
    
    async def home_all_axes(self) -> bool:
        """Home all axes (existing API)"""
        if not self.communicator:
            return False
            
        try:
            logger.info("🏠 Starting homing sequence")
            self.status = MotionStatus.HOMING
            self.is_homed = False
            self.homing_in_progress = True
            
            success = await self.communicator.home_all()
            
            if success:
                await self._wait_for_homing_complete()
                
                self.current_position = await self.get_current_position()
                self.is_homed = True
                self.homing_in_progress = False
                
                # Clear work coordinates for Z-axis (continuous rotation)
                await self.communicator.send_gcode('G10 L20 P1 Z0')
                
                logger.info(f"✅ Homing complete: {self.current_position}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Homing failed: {e}")
            self.status = MotionStatus.ERROR
            self.homing_in_progress = False
            return False
    
    async def emergency_stop(self) -> bool:
        """Emergency stop (existing API)"""
        try:
            logger.warning("🚨 Emergency stop activated")
            
            if self.communicator:
                await self.communicator.emergency_stop()
            
            self.status = MotionStatus.EMERGENCY_STOP
            self._notify_event("emergency_stop", {"reason": "Manual emergency stop"})
            
            return True
            
        except Exception as e:
            logger.critical(f"❌ Emergency stop failed: {e}")
            return False
    
    # INTERNAL METHODS
    
    async def _connect_serial(self) -> bool:
        """Establish serial connection"""
        try:
            if self.port.lower() == 'auto':
                detected_port = await self._detect_fluidnc_port()
                if not detected_port:
                    raise FluidNCConnectionError("Could not detect FluidNC device")
                self.port = detected_port
            
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=0.1,
                write_timeout=1.0
            )
            
            logger.info(f"✅ Serial connection: {self.port}")
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
                    logger.info(f"Detected FluidNC port: {port.device}")
                    return port.device
        except Exception as e:
            logger.error(f"Port detection failed: {e}")
        return None
    
    async def _configure_fluidnc(self, auto_unlock: bool = False):
        """Configure FluidNC"""
        try:
            # Handle alarm state
            status = await self.communicator.get_status()
            if self.communicator.current_status == MotionStatus.ALARM:
                if auto_unlock:
                    logger.info("🔓 Auto-unlocking alarm state")
                    await self.communicator.send_gcode('$X')
                    await asyncio.sleep(0.5)
                else:
                    logger.warning("⚠️ FluidNC in alarm state")
            
            # Basic configuration
            config_commands = ['G21', 'G90', 'G94', 'M5', 'M9']
            for cmd in config_commands:
                try:
                    await self.communicator.send_gcode(cmd)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.warning(f"Config command '{cmd}' failed: {e}")
            
            logger.info("✅ FluidNC configuration complete")
            
        except Exception as e:
            logger.error(f"❌ FluidNC configuration failed: {e}")
    
    async def _update_initial_status(self):
        """Get initial status"""
        if self.communicator:
            status_info = await self.communicator.get_status()
            self.current_position = status_info['position']
            self.status = status_info['status']
    
    async def _on_status_update(self, message: FluidNCMessage):
        """Handle status updates from protocol"""
        if not message.data:
            return
        
        # Update position
        if 'mpos' in message.data:
            pos_data = message.data['mpos']
            self.current_position = Position4D(
                x=pos_data.get('x', 0),
                y=pos_data.get('y', 0),
                z=pos_data.get('z', 0),
                c=pos_data.get('c', 0)
            )
            self.last_position_update = time.time()
            self.stats['position_updates'] += 1
        
        # Update status
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
            logger.debug(f"Status: {old_status.name} → {self.status.name}")
    
    async def _wait_for_movement_complete(self):
        """Wait for movement completion"""
        start_time = time.time()
        timeout = 60.0
        
        # Wait for IDLE status
        while time.time() - start_time < timeout:
            if self.status == MotionStatus.IDLE:
                # Allow position to stabilize
                await asyncio.sleep(0.2)
                if self.status == MotionStatus.IDLE:
                    return
            await asyncio.sleep(0.05)
        
        raise MotionTimeoutError("Movement completion timeout")
    
    async def _wait_for_homing_complete(self):
        """Wait for homing completion"""
        start_time = time.time()
        timeout = 30.0
        
        while time.time() - start_time < timeout:
            if self.status == MotionStatus.IDLE:
                return
            elif self.status == MotionStatus.ALARM:
                raise MotionControlError("Homing failed - alarm state")
            await asyncio.sleep(0.1)
        
        raise MotionTimeoutError("Homing completion timeout")
    
    # ADDITIONAL COMPATIBILITY METHODS
    
    def get_protocol_stats(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        base_stats = self.communicator.get_stats() if self.communicator else {}
        return {**base_stats, **self.stats}
    
    def check_background_monitor_status(self) -> Dict[str, Any]:
        """Check background monitor status (compatibility)"""
        return {
            'monitor_running': self.communicator.protocol.running if self.communicator else False,
            'protocol_type': 'enhanced',
            'performance': self.stats
        }
    
    async def unlock_alarm(self) -> bool:
        """Unlock alarm state (existing API)"""
        if self.communicator:
            try:
                success = await self.communicator.send_gcode('$X')
                await asyncio.sleep(0.5)
                return success
            except Exception as e:
                logger.error(f"Unlock failed: {e}")
        return False
    
    # ABSTRACT METHOD IMPLEMENTATIONS REQUIRED BY MotionController
    
    async def connect(self) -> bool:
        """Connect to FluidNC (abstract method implementation)"""
        return await self.initialize()
    
    async def disconnect(self) -> bool:
        """Disconnect from FluidNC (abstract method implementation)"""
        return await self.shutdown()
    
    async def get_status(self) -> MotionStatus:
        """Get current status (abstract method implementation)"""
        return self.status
    
    async def get_position(self) -> Position4D:
        """Get current position (abstract method implementation)"""
        return await self.get_current_position()
    
    async def get_capabilities(self) -> MotionCapabilities:
        """Get motion capabilities (abstract method implementation)"""
        return MotionCapabilities(
            axes_count=4,
            supports_homing=True,
            supports_soft_limits=True,
            supports_probe=False,
            max_feedrate=1000.0,
            position_resolution=0.001
        )
    
    async def rapid_move(self, position: Position4D) -> bool:
        """Rapid move to position (abstract method implementation)"""
        return await self.move_to_position(position)
    
    async def home_axis(self, axis: str) -> bool:
        """Home specific axis (abstract method implementation)"""
        if not self.communicator:
            return False
        
        try:
            axis_map = {'x': '$HX', 'y': '$HY', 'z': '$HZ', 'c': '$HC'}
            if axis.lower() not in axis_map:
                return False
            
            self.status = MotionStatus.HOMING
            success = await self.communicator.send_gcode(axis_map[axis.lower()])
            
            if success:
                await self._wait_for_homing_complete()
                return True
                
        except Exception as e:
            logger.error(f"Axis {axis} homing failed: {e}")
            
        return False
    
    async def set_position(self, position: Position4D) -> bool:
        """Set current position (abstract method implementation)"""
        if not self.communicator:
            return False
        
        try:
            gcode = f"G92 X{position.x} Y{position.y} Z{position.z} A{position.c}"
            success = await self.communicator.send_gcode(gcode)
            
            if success:
                self.current_position = position
                
            return success
            
        except Exception as e:
            logger.error(f"Set position failed: {e}")
            return False
    

    
    async def pause_motion(self) -> bool:
        """Pause motion (abstract method implementation)"""
        if not self.communicator:
            return False
        
        try:
            await self.communicator.protocol.send_immediate_command('!')
            return True
        except Exception:
            return False
    
    async def resume_motion(self) -> bool:
        """Resume motion (abstract method implementation)"""
        if not self.communicator:
            return False
        
        try:
            await self.communicator.protocol.send_immediate_command('~')
            return True
        except Exception:
            return False
    
    async def cancel_motion(self) -> bool:
        """Cancel motion (abstract method implementation)"""
        if not self.communicator:
            return False
        
        try:
            await self.communicator.protocol.send_immediate_command(chr(24))  # Ctrl-X
            return True
        except Exception:
            return False
    
    async def set_motion_limits(self, axis: str, limits: MotionLimits) -> bool:
        """Set motion limits (abstract method implementation)"""
        if axis.lower() in self.axis_limits:
            self.axis_limits[axis.lower()] = limits
            return True
        return False
    
    async def get_motion_limits(self, axis: str) -> MotionLimits:
        """Get motion limits (abstract method implementation)"""
        return self.axis_limits.get(axis.lower(), 
            MotionLimits(min_limit=0, max_limit=100, max_feedrate=100))
    
    async def execute_gcode(self, gcode: str) -> bool:
        """Execute G-code (abstract method implementation)"""
        if not self.communicator:
            return False
        
        try:
            return await self.communicator.send_gcode(gcode)
        except Exception as e:
            logger.error(f"G-code execution failed: {e}")
            return False
    
    async def wait_for_motion_complete(self, timeout: Optional[float] = None) -> bool:
        """Wait for motion complete (abstract method implementation)"""
        try:
            start_time = time.time()
            wait_timeout = timeout or 60.0
            
            while time.time() - start_time < wait_timeout:
                if self.status == MotionStatus.IDLE:
                    await asyncio.sleep(0.2)  # Stability check
                    if self.status == MotionStatus.IDLE:
                        return True
                await asyncio.sleep(0.05)
            
            return False
            
        except Exception:
            return False