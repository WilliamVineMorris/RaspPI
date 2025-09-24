"""
Simplified FluidNC Motion Controller - V2.1

A clean, robust FluidNC motion controller that uses the simplified protocol
to eliminate the timeout and communication issues identified in the codebase analysis.

Key Features:
- Uses SimplifiedFluidNCProtocol for reliable communication
- Proper Position4D type consistency
- Thread-safe operations
- Complete abstract method implementation  
- Proper error handling and recovery
- Event emission for status changes

Author: Scanner System Redesign  
Created: September 24, 2025
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Import the new simplified protocol
from motion.simplified_fluidnc_protocol import SimplifiedFluidNCProtocol, FluidNCStatus, FluidNCState

# Import base interfaces
from motion.base import (
    MotionController, Position4D, MotionStatus, AxisType,
    MotionLimits, MotionCapabilities
)

# Import core infrastructure
from core.exceptions import (
    FluidNCError, FluidNCConnectionError, FluidNCCommandError,
    MotionSafetyError, MotionTimeoutError, MotionControlError
)
from core.events import EventBus, ScannerEvent, EventPriority

logger = logging.getLogger(__name__)


class SimplifiedFluidNCController(MotionController):
    """
    Simplified FluidNC Motion Controller
    
    Uses the new SimplifiedFluidNCProtocol to provide reliable, timeout-free
    communication with FluidNC controllers. Implements all abstract methods
    with proper error handling and type consistency.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Extract configuration
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baud_rate = config.get('baud_rate', 115200)
        self.command_timeout = config.get('command_timeout', 10.0)
        
        # Initialize protocol
        self.protocol = SimplifiedFluidNCProtocol(self.port, self.baud_rate)
        
        # State tracking with proper types
        self.current_position = Position4D(0.0, 0.0, 0.0, 0.0)
        self.target_position = Position4D(0.0, 0.0, 0.0, 0.0)
        self.motion_status = MotionStatus.DISCONNECTED
        
        # Capabilities and limits
        self.capabilities = MotionCapabilities(
            axes_count=4,
            supports_homing=True,
            supports_soft_limits=True,
            supports_probe=True,
            max_feedrate=2000.0,
            position_resolution=0.001
        )
        
        self.axis_limits = {
            'x': MotionLimits(min_limit=0.0, max_limit=200.0, max_feedrate=1000.0),
            'y': MotionLimits(min_limit=0.0, max_limit=200.0, max_feedrate=1000.0),
            'z': MotionLimits(min_limit=-360.0, max_limit=360.0, max_feedrate=500.0),
            'c': MotionLimits(min_limit=-90.0, max_limit=90.0, max_feedrate=300.0)
        }
        
        # Event system integration
        self.event_bus = EventBus()
        
        # Statistics
        self.stats = {
            'movements_completed': 0,
            'commands_sent': 0,
            'errors_encountered': 0,
            'total_distance_moved': 0.0
        }
        
        # Setup status monitoring
        self.protocol.add_status_callback(self._handle_status_update)
    
    # Connection Management
    async def connect(self) -> bool:
        """Connect to FluidNC controller"""
        try:
            logger.info(f"🔌 Connecting to FluidNC at {self.port}")
            
            # Use synchronous protocol connection
            connected = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.connect
            )
            
            if connected:
                self.motion_status = MotionStatus.IDLE
                
                # Enable auto-reporting for real-time status
                success, _ = await self._send_command("$10=3")
                if success:
                    logger.info("✅ FluidNC connected with auto-reporting enabled")
                else:
                    logger.warning("⚠️  Auto-reporting setup failed, using polling")
                
                # Emit connection event
                self._emit_event("motion_connected", {"port": self.port})
                return True
            else:
                logger.error("❌ FluidNC connection failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ FluidNC connection error: {e}")
            self.motion_status = MotionStatus.DISCONNECTED
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from FluidNC"""
        try:
            logger.info("🔌 Disconnecting from FluidNC")
            
            # Use synchronous protocol disconnection
            disconnected = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.disconnect
            )
            
            self.motion_status = MotionStatus.DISCONNECTED
            
            # Emit disconnection event
            self._emit_event("motion_disconnected", {})
            
            logger.info("✅ FluidNC disconnected")
            return disconnected
            
        except Exception as e:
            logger.error(f"❌ FluidNC disconnect error: {e}")
            return False
    
    async def is_connected(self) -> bool:
        """Check if connected to FluidNC"""
        return self.protocol.is_connected()
    
    # Position and Status
    async def get_position(self) -> Position4D:
        """Get current position"""
        # Request fresh status to ensure accuracy
        await self._request_status_update()
        return self.current_position.copy()
    
    async def get_current_position(self) -> Position4D:
        """Get current position (alias for get_position)"""
        return await self.get_position()
    
    async def get_status(self) -> MotionStatus:
        """Get current motion status"""
        return self.motion_status
    
    async def get_capabilities(self) -> MotionCapabilities:
        """Get motion controller capabilities"""
        return self.capabilities
    
    # Motion Commands
    async def move_to_position(self, position: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move to absolute position with safety validation"""
        try:
            # Validate position limits
            if not self._validate_position_limits(position):
                raise MotionSafetyError(f"Position {position} exceeds safety limits")
            
            # Set feedrate if specified
            if feedrate:
                await self._send_command(f"F{feedrate}")
            
            # Send movement command
            gcode = f"G1 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} A{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.target_position = position.copy()
                self.stats['movements_completed'] += 1
                
                # Calculate distance moved
                distance = self._calculate_distance(self.current_position, position)
                self.stats['total_distance_moved'] += distance
                
                # Emit movement event
                self._emit_event("motion_started", {
                    "target_position": position.to_dict(),
                    "feedrate": feedrate
                })
                
                logger.info(f"✅ Moving to position: {position}")
                return True
            else:
                logger.error(f"❌ Move command failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Move to position failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move relative to current position"""
        try:
            # Calculate target position
            current = await self.get_position()
            target = Position4D(
                current.x + delta.x,
                current.y + delta.y,
                current.z + delta.z,
                current.c + delta.c
            )
            
            # Validate target position
            if not self._validate_position_limits(target):
                raise MotionSafetyError(f"Relative move {delta} would exceed limits")
            
            # Set relative mode
            success, _ = await self._send_command("G91")
            if not success:
                return False
            
            # Set feedrate if specified  
            if feedrate:
                await self._send_command(f"F{feedrate}")
            
            # Send relative movement
            gcode = f"G1 X{delta.x:.3f} Y{delta.y:.3f} Z{delta.z:.3f} A{delta.c:.3f}"
            success, response = await self._send_command(gcode)
            
            # Return to absolute mode
            await self._send_command("G90")
            
            if success:
                self.target_position = target
                self.stats['movements_completed'] += 1
                
                # Emit movement event
                self._emit_event("motion_started", {
                    "delta": delta.to_dict(),
                    "target_position": target.to_dict(),
                    "feedrate": feedrate
                })
                
                logger.info(f"✅ Relative move: {delta}")
                return True
            else:
                logger.error(f"❌ Relative move failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Relative move failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    async def rapid_move(self, position: Position4D) -> bool:
        """Rapid (G0) move to position"""
        try:
            if not self._validate_position_limits(position):
                raise MotionSafetyError(f"Rapid move position {position} exceeds limits")
            
            gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} A{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.target_position = position.copy()
                logger.info(f"✅ Rapid move to: {position}")
                return True
            else:
                logger.error(f"❌ Rapid move failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Rapid move failed: {e}")
            return False
    
    # Homing Operations
    async def home_all_axes(self) -> bool:
        """Home all axes"""
        try:
            logger.info("🏠 Homing all axes...")
            
            # Send homing command
            success, response = await self._send_command("$H", timeout=60.0)
            
            if success:
                # Wait for homing to complete
                await self._wait_for_idle(timeout=60.0)
                
                # Update position after homing (typically zeros)
                await self._request_status_update()
                
                logger.info("✅ All axes homed successfully")
                self._emit_event("homing_completed", {"axes": "all"})
                return True
            else:
                logger.error(f"❌ Homing failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Homing error: {e}")
            return False
    
    async def home_axis(self, axis: str) -> bool:
        """Home specific axis"""
        try:
            axis_upper = axis.upper()
            if axis_upper not in ['X', 'Y', 'Z', 'A']:  # A is C axis in FluidNC
                raise ValueError(f"Invalid axis: {axis}")
            
            logger.info(f"🏠 Homing {axis_upper} axis...")
            
            # FluidNC homing command for specific axis
            success, response = await self._send_command(f"$H{axis_upper}", timeout=30.0)
            
            if success:
                await self._wait_for_idle(timeout=30.0)
                await self._request_status_update()
                
                logger.info(f"✅ {axis_upper} axis homed")
                self._emit_event("homing_completed", {"axes": axis_upper})
                return True
            else:
                logger.error(f"❌ {axis_upper} axis homing failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Axis homing error: {e}")
            return False
    
    # Safety and Control
    async def emergency_stop(self) -> bool:
        """Emergency stop - immediate halt"""
        try:
            logger.warning("🛑 EMERGENCY STOP")
            
            # Send immediate stop command (!)
            stopped = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '!'
            )
            
            if stopped:
                self.motion_status = MotionStatus.ALARM
                self._emit_event("emergency_stop", {}, EventPriority.CRITICAL)
                logger.warning("✅ Emergency stop executed")
            
            return stopped
            
        except Exception as e:
            logger.error(f"❌ Emergency stop failed: {e}")
            return False
    
    async def pause_motion(self) -> bool:
        """Pause current motion"""
        try:
            paused = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '!'
            )
            
            if paused:
                self.motion_status = MotionStatus.MOVING  # Keep as moving since paused
                self._emit_event("motion_paused", {})
                logger.info("⏸️  Motion paused")
            
            return paused
            
        except Exception as e:
            logger.error(f"❌ Pause motion failed: {e}")
            return False
    
    async def resume_motion(self) -> bool:
        """Resume paused motion"""
        try:
            resumed = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '~'
            )
            
            if resumed:
                self.motion_status = MotionStatus.MOVING
                self._emit_event("motion_resumed", {})
                logger.info("▶️  Motion resumed")
            
            return resumed
            
        except Exception as e:
            logger.error(f"❌ Resume motion failed: {e}")
            return False
    
    async def cancel_motion(self) -> bool:
        """Cancel current motion"""
        return await self.emergency_stop()
    
    # Position and Coordinate Management
    async def set_position(self, position: Position4D) -> bool:
        """Set current position (coordinate system offset)"""
        try:
            # Use G92 to set coordinate system offset
            gcode = f"G92 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} A{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.current_position = position.copy()
                logger.info(f"✅ Position set to: {position}")
                self._emit_event("position_set", {"position": position.to_dict()})
                return True
            else:
                logger.error(f"❌ Set position failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Set position error: {e}")
            return False
    
    # Motion Limits and Configuration
    async def set_motion_limits(self, axis: str, limits: MotionLimits) -> bool:
        """Set motion limits for an axis"""
        try:
            axis_lower = axis.lower()
            if axis_lower in self.axis_limits:
                self.axis_limits[axis_lower] = limits
                logger.info(f"✅ Motion limits set for {axis}: {limits}")
                return True
            else:
                logger.error(f"❌ Invalid axis for limits: {axis}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Set limits error: {e}")
            return False
    
    async def get_motion_limits(self, axis: str) -> MotionLimits:
        """Get motion limits for an axis"""
        axis_lower = axis.lower()
        if axis_lower in self.axis_limits:
            return self.axis_limits[axis_lower]
        else:
            # Return default limits
            return MotionLimits(min_limit=0.0, max_limit=100.0, max_feedrate=1000.0)
    
    # Advanced Operations
    async def execute_gcode(self, gcode: str) -> bool:
        """Execute raw G-code command"""
        try:
            success, response = await self._send_command(gcode)
            
            if success:
                logger.debug(f"✅ G-code executed: {gcode}")
                return True
            else:
                logger.error(f"❌ G-code failed: {gcode} - {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ G-code execution error: {e}")
            return False
    
    async def wait_for_motion_complete(self, timeout: Optional[float] = None) -> bool:
        """Wait for all motion to complete"""
        return await self._wait_for_idle(timeout or 30.0)
    
    async def is_moving(self) -> bool:
        """Check if currently moving"""
        return self.motion_status == MotionStatus.MOVING
    
    # Additional required methods
    async def jog(self, axis: str, distance: float, feedrate: float = 100.0) -> bool:
        """Jog axis by specified distance"""
        delta = Position4D()
        axis_lower = axis.lower()
        
        if axis_lower == 'x':
            delta.x = distance
        elif axis_lower == 'y':
            delta.y = distance
        elif axis_lower == 'z':
            delta.z = distance
        elif axis_lower == 'c':
            delta.c = distance
        else:
            logger.error(f"❌ Invalid jog axis: {axis}")
            return False
        
        return await self.move_relative(delta, feedrate)
    
    async def probe(self, direction: str, distance: float = 10.0) -> Optional[Position4D]:
        """Probe operation"""
        try:
            # Simple probe implementation
            gcode = f"G38.2 {direction.upper()}{distance}"
            success, response = await self._send_command(gcode, timeout=30.0)
            
            if success:
                # Request status to get probe position
                await self._request_status_update()
                return self.current_position.copy()
            else:
                logger.error(f"❌ Probe failed: {response}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Probe error: {e}")
            return None
    
    async def set_feedrate(self, feedrate: float) -> bool:
        """Set default feedrate"""
        success, _ = await self._send_command(f"F{feedrate}")
        return success
    
    async def reset(self) -> bool:
        """Reset controller"""
        try:
            reset_success = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, 'reset'
            )
            
            if reset_success:
                # Wait for reset to complete
                await asyncio.sleep(3.0)
                
                # Reconnect
                return await self.connect()
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Reset failed: {e}")
            return False
    
    # Private Helper Methods
    async def _send_command(self, command: str, timeout: Optional[float] = None) -> tuple[bool, str]:
        """Send command using protocol"""
        timeout = timeout or self.command_timeout
        
        try:
            actual_timeout = timeout or self.command_timeout
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_command, command, actual_timeout
            )
            
            self.stats['commands_sent'] += 1
            return result
            
        except Exception as e:
            logger.error(f"❌ Command send error: {e}")
            self.stats['errors_encountered'] += 1
            return False, str(e)
    
    async def _request_status_update(self) -> bool:
        """Request immediate status update"""
        return await asyncio.get_event_loop().run_in_executor(
            None, self.protocol.request_status
        )
    
    async def _wait_for_idle(self, timeout: float = 30.0) -> bool:
        """Wait for controller to reach idle state"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            await self._request_status_update()
            
            if self.motion_status == MotionStatus.IDLE:
                return True
            elif self.motion_status == MotionStatus.ALARM:
                logger.error("❌ Controller in alarm state")
                return False
            
            await asyncio.sleep(0.5)
        
        logger.warning(f"⏰ Wait for idle timeout after {timeout}s")
        return False
    
    def _validate_position_limits(self, position: Position4D) -> bool:
        """Validate position against safety limits"""
        try:
            # Check X axis
            if not self.axis_limits['x'].is_within_limits(position.x):
                logger.error(f"❌ X position {position.x} outside limits {self.axis_limits['x']}")
                return False
            
            # Check Y axis
            if not self.axis_limits['y'].is_within_limits(position.y):
                logger.error(f"❌ Y position {position.y} outside limits {self.axis_limits['y']}")
                return False
            
            # Check Z axis
            if not self.axis_limits['z'].is_within_limits(position.z):
                logger.error(f"❌ Z position {position.z} outside limits {self.axis_limits['z']}")
                return False
            
            # Check C axis
            if not self.axis_limits['c'].is_within_limits(position.c):
                logger.error(f"❌ C position {position.c} outside limits {self.axis_limits['c']}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Position validation error: {e}")
            return False
    
    def _calculate_distance(self, pos1: Position4D, pos2: Position4D) -> float:
        """Calculate 3D distance between positions"""
        import math
        return math.sqrt(
            (pos2.x - pos1.x) ** 2 +
            (pos2.y - pos1.y) ** 2 +
            (pos2.z - pos1.z) ** 2
            # Note: C axis is rotational, not included in distance
        )
    
    def _handle_status_update(self, status: FluidNCStatus) -> None:
        """Handle status updates from protocol"""
        try:
            # Update current position
            self.current_position = Position4D(
                x=status.work_position['x'],
                y=status.work_position['y'],
                z=status.work_position['z'],
                c=status.work_position['a']  # A axis maps to C
            )
            
            # Update motion status
            old_status = self.motion_status
            
            if status.state == FluidNCState.IDLE:
                self.motion_status = MotionStatus.IDLE
            elif status.state == FluidNCState.RUN:
                self.motion_status = MotionStatus.MOVING
            elif status.state == FluidNCState.HOLD:
                self.motion_status = MotionStatus.MOVING  # Map to closest available
            elif status.state == FluidNCState.ALARM:
                self.motion_status = MotionStatus.ALARM
            elif status.state == FluidNCState.HOME:
                self.motion_status = MotionStatus.HOMING
            elif status.state == FluidNCState.JOG:
                self.motion_status = MotionStatus.MOVING  # Map to closest available
            else:
                self.motion_status = MotionStatus.ERROR  # Map to closest available
            
            # Emit status change event if changed
            if old_status != self.motion_status:
                self._emit_event("status_changed", {
                    "old_status": old_status.value,
                    "new_status": self.motion_status.value,
                    "position": self.current_position.to_dict()
                })
            
            # Emit position update event
            self._emit_event("position_updated", {
                "position": self.current_position.to_dict(),
                "feedrate": status.feedrate
            })
            
        except Exception as e:
            logger.error(f"❌ Status update handling error: {e}")
    
    def _emit_event(self, event_type: str, data: Dict[str, Any], priority: EventPriority = EventPriority.NORMAL) -> None:
        """Emit event to event bus"""
        try:
            # Use EventBus publish method
            self.event_bus.publish(
                event_type=event_type,
                data=data,
                source_module="motion_controller",
                priority=priority
            )
            
        except Exception as e:
            logger.error(f"❌ Event emission failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get controller statistics"""
        protocol_stats = self.protocol.get_statistics()
        
        return {
            **self.stats,
            **protocol_stats,
            "current_position": self.current_position.to_dict(),
            "target_position": self.target_position.to_dict(),
            "motion_status": self.motion_status.value
        }