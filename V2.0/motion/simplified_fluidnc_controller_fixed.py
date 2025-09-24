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
import time
from typing import Optional, Dict, Any

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
        
        # Operating mode for feedrate selection
        self.operating_mode = "manual_mode"  # Default to manual/jog mode
        
        # Feedrate configuration per mode and axis
        self.feedrate_config = config.get('feedrates', {})
        
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
    
    def refresh_connection_status(self) -> bool:
        """Force refresh connection status (synchronous)"""
        try:
            return self.protocol.is_connected()
        except Exception as e:
            logger.debug(f"Connection status refresh failed: {e}")
            return False
    
    @property
    def _connected(self) -> bool:
        """Synchronous connection status for web interface"""
        try:
            # Force refresh connection status to avoid stale cached values
            return self.protocol.is_connected()
        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            return False
    
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
        """Move to absolute position with safety validation and intelligent feedrate"""
        try:
            # Validate position
            if not self._validate_position_limits(position):
                raise MotionSafetyError(f"Position {position} exceeds limits")
            
            # Calculate movement delta for feedrate selection
            current = await self.get_position()
            delta = Position4D(
                position.x - current.x,
                position.y - current.y,
                position.z - current.z,
                position.c - current.c
            )
            
            # Use provided feedrate or get optimal feedrate based on current mode
            if feedrate is None:
                feedrate = self.get_optimal_feedrate(delta)
                logger.debug(f"🎯 Auto-selected feedrate: {feedrate} ({self.operating_mode})")
            
            # Set feedrate
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
                    "feedrate": feedrate,
                    "operating_mode": self.operating_mode
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
        """Move relative to current position with intelligent feedrate selection"""
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
            
            # Use provided feedrate or get optimal feedrate based on current mode
            if feedrate is None:
                feedrate = self.get_optimal_feedrate(delta)
                logger.debug(f"🎯 Auto-selected feedrate: {feedrate} ({self.operating_mode})")
            
            # Set feedrate
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
                    "feedrate": feedrate,
                    "operating_mode": self.operating_mode
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
        """Home specified axes or all axes with enhanced detection"""
        try:
            logger.info("🏠 Starting enhanced homing sequence")
            
            # Determine homing command
            if axes is None or (isinstance(axes, list) and set([ax.upper() for ax in axes]) == {'X', 'Y', 'Z', 'C'}):
                # Home all axes using standard $H command
                homing_command = "$H"
                logger.info("🏠 Executing full homing sequence with $H command")
            else:
                # Home specific axes (FluidNC supports axis-specific homing)
                axis_string = ''.join(axes).upper()
                homing_command = f"$H{axis_string}"
                logger.info(f"🏠 Executing selective homing for axes: {axis_string}")
            
            # Enhanced homing detection with message monitoring
            return await self._execute_homing_with_message_detection(homing_command, axes)
                
        except Exception as e:
            logger.error(f"❌ Homing failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    async def _execute_homing_with_message_detection(self, homing_command: str, axes: Optional[list] = None) -> bool:
        """Execute homing with enhanced message detection"""
        try:
            logger.info(f"🏠 Sending homing command: {homing_command}")
            
            # Start message monitoring for homing completion detection
            homing_messages = []
            homing_complete = False
            homing_failed = False
            axes_homed = set()
            
            def message_callback(message_type: str, content: str):
                nonlocal homing_complete, homing_failed, axes_homed
                homing_messages.append(f"{message_type}: {content}")
                
                if message_type == "debug":
                    if "Homing done" in content:
                        logger.info("🎯 DETECTED: Homing completion signal!")
                        homing_complete = True
                    elif "Homing Cycle" in content:
                        axis = content.split("Homing Cycle ")[-1].strip()
                        logger.info(f"🏠 DETECTED: Starting homing cycle for axis {axis}")
                    elif content.startswith("Homed:"):
                        axis = content.split("Homed:")[-1].strip()
                        axes_homed.add(axis)
                        logger.info(f"✅ DETECTED: Axis {axis} homed successfully")
                elif message_type == "error" or "alarm" in content.lower():
                    logger.error(f"❌ DETECTED: Homing error - {content}")
                    homing_failed = True
            
        # Enhanced monitoring will use direct protocol inspection
        # (Protocol enhancement needed for full message callback support)            try:
                # Send homing command
                success, response = await self._send_command(homing_command)
                
                if not success:
                    logger.error(f"❌ Homing command failed: {response}")
                    return False
                
                logger.info(f"🏠 Homing command sent, initial response: {response}")
                
                # Enhanced monitoring with both status and message detection
                homing_timeout = 45.0  # Increased timeout based on your 22-second actual time
                homing_start_time = time.time()
                last_status_check = 0
                
                logger.info("🏠 Monitoring for homing completion signals...")
                
                while time.time() - homing_start_time < homing_timeout:
                    elapsed = time.time() - homing_start_time
                    
                    # Check for completion via debug message (primary detection)
                    if homing_complete:
                        logger.info(f"✅ Homing completed via debug message detection after {elapsed:.1f}s")
                        break
                    
                    # Check for failure
                    if homing_failed:
                        logger.error(f"❌ Homing failed via message detection after {elapsed:.1f}s")
                        return False
                    
                    # Periodically check status as backup (every 2 seconds)
                    if elapsed - last_status_check >= 2.0:
                        status = self.protocol.get_current_status()
                        last_status_check = elapsed
                        
                        if status and status.state:
                            state_lower = status.state.lower()
                            logger.debug(f"🏠 Status check at {elapsed:.1f}s: {status.state}")
                            
                            # Backup detection: if we see Idle and have homed axes, assume completion
                            if state_lower in ['idle', 'run'] and axes_homed:
                                logger.info(f"✅ Backup detection: State={status.state}, Axes homed: {axes_homed}")
                                homing_complete = True
                                break
                            elif state_lower in ['alarm', 'error']:
                                logger.error(f"❌ Status-based failure detection: {status.state}")
                                return False
                    
                    # Brief pause
                    await asyncio.sleep(0.1)
                
                if not homing_complete:
                    if time.time() - homing_start_time >= homing_timeout:
                        logger.warning(f"⚠️ Homing timeout after {homing_timeout}s")
                        logger.info(f"📝 Debug messages captured: {len(homing_messages)}")
                        for msg in homing_messages[-5:]:  # Show last 5 messages
                            logger.info(f"   {msg}")
                        return False
                
                # Final verification
                await asyncio.sleep(1.0)  # Allow system to settle
                final_status = self.protocol.get_current_status()
                
                if final_status and final_status.state.lower() in ['idle', 'run']:
                    logger.info(f"✅ Final verification: FluidNC in {final_status.state} state")
                else:
                    logger.warning(f"⚠️ Final verification: Unexpected state: {final_status.state if final_status else 'None'}")
                
            finally:
                # Restore original callback (if protocol supports it)
                if hasattr(self.protocol, 'message_callback'):
                    self.protocol.message_callback = old_callback
                
            # Update position after homing
            await self._update_current_position()
            
            self._emit_event("homing_completed", {
                "axes": axes or ['x', 'y', 'z', 'c'],
                "final_position": self.current_position.to_dict(),
                "homing_messages": homing_messages[-10:],  # Include recent messages
                "axes_homed": list(axes_homed)
            })
            
            logger.info(f"✅ Enhanced homing completed: {axes or 'all axes'}")
            logger.info(f"🎯 Axes homed: {axes_homed}, Messages captured: {len(homing_messages)}")
            logger.info(f"📍 New position: {self.current_position}")
            return True
                
        except Exception as e:
            logger.error(f"❌ Enhanced homing failed: {e}")
            self.stats['errors_encountered'] += 1
            return False
    
    def home_axes_sync(self, axes: Optional[list] = None) -> bool:
        """Synchronous version of home_axes for web interface"""
        import asyncio
        try:
            # Create new event loop for synchronous execution
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(self.home_axes(axes))
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"❌ Synchronous homing failed: {e}")
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
    
    # Feedrate Management
    def set_operating_mode(self, mode: str) -> bool:
        """
        Set operating mode for feedrate selection
        
        Args:
            mode: "manual_mode" for jog/web interface, "scanning_mode" for automated scanning
            
        Returns:
            bool: True if mode was set successfully
        """
        valid_modes = ["manual_mode", "scanning_mode"]
        
        if mode not in valid_modes:
            logger.error(f"❌ Invalid operating mode: {mode}. Valid modes: {valid_modes}")
            return False
            
        old_mode = self.operating_mode
        self.operating_mode = mode
        
        logger.info(f"🔧 Operating mode changed: {old_mode} → {mode}")
        
        # Emit mode change event
        self._emit_event("operating_mode_changed", {
            "old_mode": old_mode,
            "new_mode": mode,
            "feedrates": self.get_current_feedrates()
        })
        
        return True
    
    def get_operating_mode(self) -> str:
        """Get current operating mode"""
        return self.operating_mode
    
    def get_current_feedrates(self) -> Dict[str, float]:
        """Get feedrates for current operating mode"""
        mode_config = self.feedrate_config.get(self.operating_mode, {})
        
        return {
            'x_axis': mode_config.get('x_axis', 100.0),
            'y_axis': mode_config.get('y_axis', 100.0),
            'z_axis': mode_config.get('z_axis', 100.0),
            'c_axis': mode_config.get('c_axis', 100.0)
        }
    
    def get_feedrate_for_axis(self, axis: str) -> float:
        """
        Get feedrate for specific axis in current operating mode
        
        Args:
            axis: 'x', 'y', 'z', or 'c'
            
        Returns:
            float: Feedrate for the axis
        """
        axis_key = f"{axis.lower()}_axis"
        current_feedrates = self.get_current_feedrates()
        
        return current_feedrates.get(axis_key, 100.0)
    
    def get_optimal_feedrate(self, position_delta: Position4D) -> float:
        """
        Get optimal feedrate based on the movement and current mode
        
        Chooses the limiting feedrate based on which axes are moving
        
        Args:
            position_delta: Movement delta to analyze
            
        Returns:
            float: Optimal feedrate for the movement
        """
        feedrates = []
        
        # Check which axes are moving and get their feedrates
        if abs(position_delta.x) > 0.001:
            feedrates.append(self.get_feedrate_for_axis('x'))
        if abs(position_delta.y) > 0.001:
            feedrates.append(self.get_feedrate_for_axis('y'))
        if abs(position_delta.z) > 0.001:
            feedrates.append(self.get_feedrate_for_axis('z'))
        if abs(position_delta.c) > 0.001:
            feedrates.append(self.get_feedrate_for_axis('c'))
        
        # Use the minimum feedrate (most conservative)
        if feedrates:
            return min(feedrates)
        else:
            return self.get_feedrate_for_axis('x')  # Default
    
    def get_all_feedrate_configurations(self) -> Dict[str, Any]:
        """Get complete feedrate configuration for all modes"""
        return self.feedrate_config.copy()
    
    def update_feedrate_config(self, mode: str, axis: str, feedrate: float) -> bool:
        """
        Update feedrate for specific mode and axis
        
        Args:
            mode: "manual_mode" or "scanning_mode"
            axis: "x_axis", "y_axis", "z_axis", or "c_axis"
            feedrate: New feedrate value
            
        Returns:
            bool: True if updated successfully
        """
        if mode not in ["manual_mode", "scanning_mode"]:
            logger.error(f"❌ Invalid mode: {mode}")
            return False
            
        if axis not in ["x_axis", "y_axis", "z_axis", "c_axis"]:
            logger.error(f"❌ Invalid axis: {axis}")
            return False
            
        # Validate against max feedrate limits
        axis_letter = axis.split('_')[0]
        axis_limits = self.limits.get(axis_letter)
        max_feedrate = axis_limits.max_feedrate if axis_limits else 1000.0
        
        if feedrate > max_feedrate:
            logger.warning(f"⚠️ Feedrate {feedrate} exceeds max {max_feedrate} for {axis}")
            feedrate = max_feedrate
        
        if feedrate <= 0:
            logger.error(f"❌ Invalid feedrate: {feedrate}")
            return False
        
        # Update configuration
        if mode not in self.feedrate_config:
            self.feedrate_config[mode] = {}
            
        old_feedrate = self.feedrate_config[mode].get(axis, 0.0)
        self.feedrate_config[mode][axis] = feedrate
        
        logger.info(f"🔧 Feedrate updated: {mode}.{axis} {old_feedrate} → {feedrate}")
        
        # Emit configuration change event
        self._emit_event("feedrate_config_changed", {
            "mode": mode,
            "axis": axis,
            "old_feedrate": old_feedrate,
            "new_feedrate": feedrate
        })
        
        return True
    
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
    
    # Additional Methods for Scan Orchestrator Compatibility
    async def initialize(self) -> bool:
        """Initialize the motion controller (alias for connect)"""
        return await self.connect()
    
    async def shutdown(self) -> bool:
        """Shutdown the motion controller (alias for disconnect)"""
        return await self.disconnect()
    
    async def home(self) -> bool:
        """Home all axes - placeholder implementation"""
        try:
            # Send homing command
            success, response = await self._send_command("$H")
            if success:
                self.motion_status = MotionStatus.HOMING
                self.stats['homing_completed'] += 1
                
                # Wait for homing to complete by monitoring status
                # This is a simplified implementation
                timeout = 60.0  # 60 second homing timeout
                start_time = time.time()
                
                while (time.time() - start_time) < timeout:
                    await asyncio.sleep(0.5)
                    status = await self.get_status()
                    
                    if status == MotionStatus.IDLE:
                        logger.info("✅ Homing completed successfully")
                        return True
                    elif status == MotionStatus.ALARM:
                        logger.error("❌ Homing failed - alarm state")
                        return False
                
                logger.error("❌ Homing timeout")
                return False
            else:
                logger.error(f"❌ Homing command failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Homing failed: {e}")
            return False
    
    async def move_to(self, x: float, y: float) -> bool:
        """Move to X,Y position (compatibility method)"""
        current = await self.get_position()
        target = Position4D(x=x, y=y, z=current.z, c=current.c)
        return await self.move_to_position(target)
    
    async def move_z_to(self, z: float) -> bool:
        """Move Z axis to position (compatibility method)"""
        current = await self.get_position()
        target = Position4D(x=current.x, y=current.y, z=z, c=current.c)
        return await self.move_to_position(target)
    
    async def rotate_to(self, c: float) -> bool:
        """Rotate C axis to position (compatibility method)"""
        current = await self.get_position()
        target = Position4D(x=current.x, y=current.y, z=current.z, c=c)
        return await self.move_to_position(target)
    
    def get_current_settings(self) -> Dict[str, Any]:
        """Get current motion settings (compatibility method)"""
        return {
            'operating_mode': self.get_operating_mode(),
            'current_feedrates': self.get_current_feedrates(),
            'motion_limits': {
                axis: {
                    'min': limits.min_limit,
                    'max': limits.max_limit,
                    'max_feedrate': limits.max_feedrate
                } for axis, limits in self.limits.items()
            },
            'controller_config': {
                'port': self.port,
                'baud_rate': self.baud_rate,
                'timeout': self.protocol.command_timeout if hasattr(self.protocol, 'command_timeout') else 10.0
            },
            'capabilities': {
                'axes_count': self.capabilities.axes_count if self.capabilities else 4,
                'supports_homing': True,
                'supports_feedrate_config': True,
                'supports_operating_modes': True
            }
        }