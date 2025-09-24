#!/usr/bin/env python3
"""
Fixed FluidNC Controller with Proper Position Tracking and Motion Completion

This version addresses the key issues found in testing:
1. Properly tracks current position from machine feedback
2. Waits for motion completion before returning
3. Handles coordinate system correctly
4. Better limit checking with current position awareness

Author: Scanner System Redesign  
Created: September 24, 2025
"""

import asyncio
import logging
from typing import Optional, Dict, Any
import time

# Import the fixed protocol
from motion.simplified_fluidnc_protocol_fixed import SimplifiedFluidNCProtocolFixed, FluidNCStatus
from motion.base import MotionController, Position4D, MotionStatus, MotionCapabilities, MotionLimits
from core.events import EventBus
from core.exceptions import MotionError, MotionSafetyError, ConfigurationError

logger = logging.getLogger(__name__)


class SimplifiedFluidNCControllerFixed(MotionController):
    """
    Fixed FluidNC controller with proper position tracking and motion completion
    
    Key improvements:
    - Tracks real machine position from status reports
    - Waits for motion completion before returning
    - Better coordinate system handling
    - Improved limit checking
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize FluidNC controller with configuration"""
        super().__init__(config)
        
        # Configuration
        self.config = config
        self.port = config.get('port', '/dev/ttyUSB0')
        self.baud_rate = config.get('baud_rate', 115200)
        
        # Protocol instance (fixed version)
        self.protocol = SimplifiedFluidNCProtocolFixed(
            port=self.port,
            baud_rate=self.baud_rate,
            command_timeout=config.get('command_timeout', 10.0)
        )
        
        # State management
        self.motion_status = MotionStatus.DISCONNECTED
        self.current_position = Position4D()  # Tracked from machine
        self.target_position = Position4D()
        
        # Capabilities and limits
        self.capabilities = MotionCapabilities(
            max_feedrate=config.get('max_feedrate', 1000.0),
            axes_count=4,
            supports_homing=True,
            supports_soft_limits=True,
            supports_probe=False,
            position_resolution=0.001
        )
        
        # Motion limits - get from config with defaults
        axis_limits = config.get('motion_limits', {})
        self.limits = {
            'x': MotionLimits(
                min_limit=axis_limits.get('x', {}).get('min', 0.0),
                max_limit=axis_limits.get('x', {}).get('max', 200.0),
                max_feedrate=axis_limits.get('x', {}).get('max_feedrate', 1000.0)
            ),
            'y': MotionLimits(
                min_limit=axis_limits.get('y', {}).get('min', 0.0),
                max_limit=axis_limits.get('y', {}).get('max', 200.0),
                max_feedrate=axis_limits.get('y', {}).get('max_feedrate', 1000.0)
            ),
            'z': MotionLimits(
                min_limit=axis_limits.get('z', {}).get('min', -360.0),  # Continuous rotation
                max_limit=axis_limits.get('z', {}).get('max', 360.0),
                max_feedrate=axis_limits.get('z', {}).get('max_feedrate', 1000.0)
            ),
            'c': MotionLimits(
                min_limit=axis_limits.get('c', {}).get('min', -90.0),
                max_limit=axis_limits.get('c', {}).get('max', 90.0),
                max_feedrate=axis_limits.get('c', {}).get('max_feedrate', 1000.0)
            )
        }
        
        # Event system
        self.event_bus = EventBus()
        
        # Statistics
        self.stats = {
            'connection_time': 0.0,
            'commands_sent': 0,
            'movements_completed': 0,
            'errors_encountered': 0
        }
        
        # Setup status monitoring
        self.protocol.add_status_callback(self._on_status_update)
    
    # Connection Management
    async def connect(self) -> bool:
        """Connect to FluidNC controller"""
        try:
            logger.info(f"🔌 Connecting to FluidNC at {self.port}")
            
            # Connect using the fixed protocol
            connected = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.connect
            )
            
            if connected:
                self.motion_status = MotionStatus.IDLE
                self.stats['connection_time'] = time.time()
                
                # Get initial position
                await self._update_current_position()
                
                # Emit connection event
                self._emit_event("motion_connected", {"port": self.port})
                
                logger.info("✅ FluidNC connected and position updated")
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
            
            # Use fixed protocol disconnection
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
        """Get current position (from machine feedback)"""
        # Update position from latest status
        await self._update_current_position()
        return self.current_position.copy()
    
    async def get_current_position(self) -> Position4D:
        """Get current position (alias)"""
        return await self.get_position()
    
    async def get_status(self) -> MotionStatus:
        """Get current motion status"""
        return self.motion_status
    
    async def get_capabilities(self) -> MotionCapabilities:
        """Get motion controller capabilities"""
        if self.capabilities is None:
            raise MotionError("Capabilities not initialized")
        return self.capabilities
    
    # Motion Commands
    async def move_to_position(self, position: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move to absolute position with safety validation"""
        try:
            # Validate position
            if not self._validate_position_limits(position):
                raise MotionSafetyError(f"Position {position} exceeds limits")
            
            # Set feedrate if specified
            if feedrate:
                await self._send_command(f"F{feedrate}")
            
            # Send absolute movement (G90 is default, but ensure it)
            await self._send_command("G90")
            
            # Send move command
            gcode = f"G1 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} A{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.target_position = position.copy()
                self.stats['movements_completed'] += 1
                
                # Update current position after move completes
                await self._update_current_position()
                
                # Emit movement event
                self._emit_event("motion_completed", {
                    "target_position": position.to_dict(),
                    "actual_position": self.current_position.to_dict(),
                    "feedrate": feedrate
                })
                
                logger.info(f"✅ Absolute move to: {position}")
                return True
            else:
                logger.error(f"❌ Absolute move failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Absolute move failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move relative to current position with improved handling"""
        try:
            # Get current position from machine
            current = await self.get_position()
            
            # Calculate target position
            target = Position4D(
                current.x + delta.x,
                current.y + delta.y,
                current.z + delta.z,
                current.c + delta.c
            )
            
            # Validate target position against limits
            if not self._validate_position_limits(target):
                raise MotionSafetyError(f"Relative move {delta} would exceed limits")
            
            # Set feedrate if specified  
            if feedrate:
                await self._send_command(f"F{feedrate}")
            
            # Use absolute positioning to avoid coordinate drift
            # This is more reliable than relative mode
            success, response = await self._send_command("G90")
            if not success:
                return False
            
            # Send absolute move to calculated target
            gcode = f"G1 X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f} A{target.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.target_position = target.copy()
                self.stats['movements_completed'] += 1
                
                # Update position after move completes
                await self._update_current_position()
                
                # Emit movement event
                self._emit_event("motion_completed", {
                    "delta": delta.to_dict(),
                    "target_position": target.to_dict(),
                    "actual_position": self.current_position.to_dict(),
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
            
            # Ensure absolute mode
            await self._send_command("G90")
            
            gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} A{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.target_position = position.copy()
                self.stats['movements_completed'] += 1
                
                # Update position after rapid move
                await self._update_current_position()
                
                logger.info(f"✅ Rapid move to: {position}")
                return True
            else:
                logger.error(f"❌ Rapid move failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Rapid move failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    async def home_axes(self, axes: Optional[list] = None) -> bool:
        """Home specified axes or all axes"""
        try:
            logger.info("🏠 Starting homing sequence")
            
            if axes is None:
                # Home all axes
                success, response = await self._send_command("$H")
            else:
                # Home specific axes (FluidNC supports axis-specific homing)
                axis_string = ''.join(axes).upper()
                success, response = await self._send_command(f"$H{axis_string}")
            
            if success:
                # Update position after homing
                await self._update_current_position()
                
                self._emit_event("homing_completed", {
                    "axes": axes or ['x', 'y', 'z', 'c'],
                    "final_position": self.current_position.to_dict()
                })
                
                logger.info(f"✅ Homing completed: {axes or 'all axes'}")
                return True
            else:
                logger.error(f"❌ Homing failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Homing failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    async def emergency_stop(self) -> bool:
        """Emergency stop - immediate halt"""
        try:
            logger.warning("🛑 Emergency stop triggered")
            
            # Send immediate stop command
            stopped = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '!'
            )
            
            if stopped:
                self.motion_status = MotionStatus.ALARM
                
                # Update position after stop
                await self._update_current_position()
                
                self._emit_event("emergency_stop", {
                    "position": self.current_position.to_dict()
                })
                
                logger.warning("✅ Emergency stop completed")
                return True
            else:
                logger.error("❌ Emergency stop failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Emergency stop error: {e}")
            return False
    
    async def reset_controller(self) -> bool:
        """Reset FluidNC controller"""
        try:
            logger.info("🔄 Resetting FluidNC controller")
            
            # Send reset command
            reset = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, 'reset'
            )
            
            if reset:
                # Wait for controller to restart
                await asyncio.sleep(2.0)
                
                # Update status and position
                self.motion_status = MotionStatus.IDLE
                await self._update_current_position()
                
                self._emit_event("controller_reset", {})
                
                logger.info("✅ Controller reset completed")
                return True
            else:
                logger.error("❌ Controller reset failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Controller reset error: {e}")
            return False
    
    # Additional required abstract methods
    async def home_all_axes(self) -> bool:
        """Home all axes using $H command"""
        return await self.home_axes()
    
    async def home_axis(self, axis: str) -> bool:
        """Home specific axis"""
        return await self.home_axes([axis])
    
    async def set_position(self, position: Position4D) -> bool:
        """Set current position (G92 command)"""
        try:
            gcode = f"G92 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} A{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.current_position = position.copy()
                logger.info(f"✅ Position set to: {position}")
                return True
            else:
                logger.error(f"❌ Set position failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Set position error: {e}")
            return False
    
    async def pause_motion(self) -> bool:
        """Pause current motion (feed hold)"""
        try:
            paused = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '!'
            )
            
            if paused:
                logger.info("⏸️ Motion paused")
                return True
            else:
                logger.error("❌ Motion pause failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Motion pause error: {e}")
            return False
    
    async def resume_motion(self) -> bool:
        """Resume paused motion (cycle start)"""
        try:
            resumed = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '~'
            )
            
            if resumed:
                logger.info("▶️ Motion resumed")
                return True
            else:
                logger.error("❌ Motion resume failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Motion resume error: {e}")
            return False
    
    async def cancel_motion(self) -> bool:
        """Cancel current motion"""
        # Same as emergency stop for FluidNC
        return await self.emergency_stop()
    
    async def set_motion_limits(self, axis: str, limits: MotionLimits) -> bool:
        """Set motion limits for an axis"""
        try:
            self.limits[axis] = limits
            logger.info(f"✅ Motion limits set for {axis}: {limits}")
            return True
        except Exception as e:
            logger.error(f"❌ Set motion limits error: {e}")
            return False
    
    async def get_motion_limits(self, axis: str) -> MotionLimits:
        """Get motion limits for an axis"""
        if axis in self.limits:
            return self.limits[axis]
        else:
            raise MotionError(f"No limits defined for axis {axis}")
    
    async def execute_gcode(self, gcode: str) -> bool:
        """Execute raw G-code command"""
        try:
            success, response = await self._send_command(gcode)
            
            if success:
                logger.info(f"✅ G-code executed: {gcode}")
                return True
            else:
                logger.error(f"❌ G-code failed: {gcode} - {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ G-code execution error: {e}")
            return False
    
    async def wait_for_motion_complete(self, timeout: Optional[float] = None) -> bool:
        """Wait for all motion to complete"""
        try:
            timeout = timeout or 30.0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                await self._update_current_position()
                
                if self.motion_status == MotionStatus.IDLE:
                    logger.info("✅ Motion completed")
                    return True
                elif self.motion_status in [MotionStatus.ALARM, MotionStatus.ERROR]:
                    logger.warning("⚠️ Motion stopped due to error")
                    return False
                
                await asyncio.sleep(0.1)
            
            logger.warning("⏰ Motion completion timeout")
            return False
            
        except Exception as e:
            logger.error(f"❌ Wait for motion error: {e}")
            return False
    
    # Helper Methods
    async def _send_command(self, command: str) -> tuple[bool, str]:
        """Send command using fixed protocol with motion completion"""
        try:
            self.stats['commands_sent'] += 1
            
            # Use the fixed protocol with motion completion waiting
            success, response = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_command_with_motion_wait, command
            )
            
            return success, response
            
        except Exception as e:
            logger.error(f"❌ Command send error: {command} - {e}")
            return False, str(e)
    
    async def _update_current_position(self):
        """Update current position from machine status"""
        try:
            # Get current status from protocol
            status = self.protocol.get_current_status()
            
            if status and status.position:
                # Update current position from machine feedback
                self.current_position = Position4D(
                    x=status.position.get('x', 0.0),
                    y=status.position.get('y', 0.0),
                    z=status.position.get('z', 0.0),
                    c=status.position.get('a', 0.0)  # FluidNC uses 'a' for 4th axis
                )
                
                # Update motion status from machine state
                if status.state:
                    state_lower = status.state.lower()
                    if state_lower == 'idle':
                        self.motion_status = MotionStatus.IDLE
                    elif state_lower in ['run', 'jog']:
                        self.motion_status = MotionStatus.MOVING
                    elif state_lower in ['alarm', 'error']:
                        self.motion_status = MotionStatus.ALARM
                    elif state_lower == 'home':
                        self.motion_status = MotionStatus.HOMING
            
        except Exception as e:
            logger.error(f"❌ Position update error: {e}")
    
    async def _request_status_update(self):
        """Request fresh status from controller"""
        try:
            # Send status request
            await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_immediate_command, '?'
            )
            
            # Give time for response
            await asyncio.sleep(0.1)
            
            # Update position from response
            await self._update_current_position()
            
        except Exception as e:
            logger.error(f"❌ Status request error: {e}")
    
    def _validate_position_limits(self, position: Position4D) -> bool:
        """Validate position against motion limits"""
        try:
            # Check X axis
            x_limits = self.limits['x']
            if position.x < x_limits.min_limit or position.x > x_limits.max_limit:
                logger.error(f"❌ X position {position.x} outside limits {x_limits}")
                return False
            
            # Check Y axis
            y_limits = self.limits['y']
            if position.y < y_limits.min_limit or position.y > y_limits.max_limit:
                logger.error(f"❌ Y position {position.y} outside limits {y_limits}")
                return False
            
            # Check Z axis (continuous rotation, but still has practical limits)
            z_limits = self.limits['z']
            if position.z < z_limits.min_limit or position.z > z_limits.max_limit:
                logger.error(f"❌ Z position {position.z} outside limits {z_limits}")
                return False
            
            # Check C axis
            c_limits = self.limits['c']
            if position.c < c_limits.min_limit or position.c > c_limits.max_limit:
                logger.error(f"❌ C position {position.c} outside limits {c_limits}")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Limit validation error: {e}")
            return False
    
    def _on_status_update(self, status: FluidNCStatus):
        """Handle status updates from protocol"""
        try:
            # Update current position from status
            if status.position:
                self.current_position = Position4D(
                    x=status.position.get('x', 0.0),
                    y=status.position.get('y', 0.0),
                    z=status.position.get('z', 0.0),
                    c=status.position.get('a', 0.0)  # FluidNC uses 'a' for 4th axis
                )
            
            # Update motion status
            if status.state:
                state_lower = status.state.lower()
                old_status = self.motion_status
                
                if state_lower == 'idle':
                    self.motion_status = MotionStatus.IDLE
                elif state_lower in ['run', 'jog']:
                    self.motion_status = MotionStatus.MOVING
                elif state_lower in ['alarm', 'error']:
                    self.motion_status = MotionStatus.ALARM
                elif state_lower == 'home':
                    self.motion_status = MotionStatus.HOMING
                
                # Emit status change event if changed
                if old_status != self.motion_status:
                    self._emit_event("motion_status_changed", {
                        "old_status": old_status.value,
                        "new_status": self.motion_status.value,
                        "position": self.current_position.to_dict()
                    })
            
        except Exception as e:
            logger.error(f"❌ Status update handler error: {e}")
    
    def _emit_event(self, event_name: str, data: Dict[str, Any]):
        """Emit event to event bus"""
        try:
            self.event_bus.publish(event_name, data, source_module="fluidnc_controller")
        except Exception as e:
            logger.error(f"❌ Event emission error: {event_name} - {e}")
    
    # Statistics and Info
    def get_stats(self) -> Dict[str, Any]:
        """Get controller statistics"""
        stats = self.stats.copy()
        
        # Add protocol stats
        protocol_stats = self.protocol.get_stats()
        stats.update(protocol_stats)
        
        # Add current state
        stats.update({
            'current_position': self.current_position.to_dict(),
            'target_position': self.target_position.to_dict(),
            'motion_status': self.motion_status.value,
            'connected': self.protocol.is_connected()
        })
        
        return stats