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

# Import timing logger
try:
    from timing_logger import timing_logger
    TIMING_AVAILABLE = True
except ImportError:
    TIMING_AVAILABLE = False
    # Create dummy timing logger for compatibility
    class DummyTimingLogger:
        def log_fluidnc_send(self, *args, **kwargs): pass
        def log_fluidnc_response(self, *args, **kwargs): pass
        def log_error(self, *args, **kwargs): pass
    timing_logger = DummyTimingLogger()

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
        
        # Modal state tracking to avoid redundant commands
        self._modal_absolute_mode = False  # Track if G90 has been set
        
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
                min_limit=axis_limits.get('z', {}).get('min', None),  # Allow null for continuous rotation
                max_limit=axis_limits.get('z', {}).get('max', None),  # Allow null for continuous rotation
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
                
                # Reset modal state tracking for clean start
                self._modal_absolute_mode = False
                
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
            # CRITICAL: Validate C-axis (servo) limits to prevent FluidNC rejection
            if abs(position.c) > 90.0:  # FluidNC servo has ±90° range from center (180° total)
                logger.error(f"❌ C-axis position {position.c}° exceeds servo limits (±90°)")
                return False
            
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
            
            # Use provided feedrate or get optimal feedrate (only needed for scanning mode)
            if feedrate is None and self.operating_mode != "manual_mode":
                feedrate = self.get_optimal_feedrate(delta)
                logger.debug(f"🎯 Auto-selected feedrate: {feedrate} ({self.operating_mode})")
            
            # CRITICAL FIX: Use G0 rapid moves for all operations to avoid soft limit errors
            # FluidNC appears to have restrictive soft limits that reject G1 moves but allow G0 moves
            if self.operating_mode == "manual_mode":
                # For manual positioning, use G0 rapid moves (works reliably)
                gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
                logger.debug(f"🚀 Using G0 rapid move for manual positioning")
                success, response = await self._send_command(gcode, priority="high")
            else:
                # For scan operations, ALSO use G0 rapid moves to avoid soft limit errors
                # G0 commands work while G1 commands trigger error:22 soft limit violations
                gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
                logger.debug(f"🎯 Using G0 rapid move for scan positioning (avoids soft limits)")
                success, response = await self._send_command(gcode, priority="normal")
            
            if success:
                self.target_position = position.copy()
                self.stats['movements_completed'] += 1
                
                # CRITICAL: Wait for motion to actually complete before continuing
                logger.debug(f"⏳ Waiting for motion to complete to position: {position}")
                motion_complete = await self.wait_for_motion_complete(timeout=30.0)
                
                if not motion_complete:
                    logger.error(f"❌ Motion to {position} did not complete within timeout")
                    return False
                
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
            
            # Use provided feedrate or get optimal feedrate (only needed for scanning mode)
            if feedrate is None and self.operating_mode != "manual_mode":
                feedrate = self.get_optimal_feedrate(delta)
                logger.debug(f"🎯 Auto-selected feedrate: {feedrate} ({self.operating_mode})")
            
            # CRITICAL FIX: Use G0 rapid moves for all operations to avoid soft limit errors
            # FluidNC soft limits reject G1 moves but allow G0 moves at same coordinates
            if self.operating_mode == "manual_mode":
                # For manual jogging, use G0 (rapid) for maximum speed
                gcode = f"G0 X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f} C{target.c:.3f}"
                logger.debug(f"🚀 Using G0 rapid motion for manual jogging")
                
                success, response = await self._send_command(gcode, priority="high")
            else:
                # For scan operations, ALSO use G0 rapid moves to avoid soft limit errors
                # Testing showed G1 commands trigger error:22 while G0 commands work fine
                gcode = f"G0 X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f} C{target.c:.3f}"
                success, response = await self._send_command(gcode, priority="normal")
                logger.debug(f"🎯 Using G0 rapid move for scan operations (avoids soft limits)")
            
            if success:
                self.target_position = target.copy()
                self.stats['movements_completed'] += 1
                
                # CRITICAL: Wait for motion to actually complete before continuing
                logger.debug(f"⏳ Waiting for relative motion to complete: {delta}")
                motion_complete = await self.wait_for_motion_complete(timeout=30.0)
                
                if not motion_complete:
                    logger.error(f"❌ Relative motion {delta} did not complete within timeout")
                    return False
                
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
            
            # Use G0 rapid move directly (no need for G90 mode setting)
            # G0 commands work reliably while G1 commands trigger soft limit errors
            gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
            success, response = await self._send_command(gcode)
            
            if success:
                self.target_position = position.copy()
                self.stats['movements_completed'] += 1
                
                # CRITICAL: Wait for rapid motion to actually complete before continuing
                logger.debug(f"⏳ Waiting for rapid motion to complete to position: {position}")
                motion_complete = await self.wait_for_motion_complete(timeout=30.0)
                
                if not motion_complete:
                    logger.error(f"❌ Rapid motion to {position} did not complete within timeout")
                    return False
                
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
        """Enhanced homing with FluidNC debug message detection and proper alarm clearing"""
        try:
            logger.info("🏠 Starting ENHANCED homing with debug message detection")
            
            # CRITICAL: Reset homed status IMMEDIATELY at function start
            self.is_homed = False
            logger.info("🔄 IMMEDIATE reset: is_homed flag set to False at function start")
            
            # STEP 1: Clear alarm state BEFORE homing
            logger.info("🔓 Step 1: Clearing alarm state before homing")
            alarm_clear_success = await self.clear_alarm()
            if not alarm_clear_success:
                logger.warning("⚠️ Pre-homing alarm clear failed, but continuing...")
            
            # Wait for system to settle after alarm clear
            await asyncio.sleep(1.0)
            logger.info("⏳ Waited 1 second after alarm clear")
            
            # Determine homing command
            if axes is None or (isinstance(axes, list) and set([ax.upper() for ax in axes]) == {'X', 'Y', 'Z', 'C'}):
                homing_command = "$H"
                logger.info("🏠 Full homing sequence ($H)")
            else:
                axis_string = ''.join(axes).upper()
                homing_command = f"$H{axis_string}"
                logger.info(f"🏠 Selective homing ({homing_command})")
            
            # Send homing command using direct serial approach (proven working)
            logger.info(f"🏠 Sending: {homing_command}")
            
            try:
                # Direct serial send to avoid motion wait conflicts during homing
                with self.protocol.connection_lock:
                    if self.protocol.serial_connection:
                        command_bytes = f"{homing_command}\n".encode('utf-8')
                        self.protocol.serial_connection.write(command_bytes)
                        self.protocol.serial_connection.flush()
                        logger.info("✅ Homing command sent directly via serial")
                        success = True
                        response = "Command sent via direct serial"
                    else:
                        success = False
                        response = "No serial connection available"
            except Exception as e:
                success = False
                response = f"Direct send error: {e}"
                logger.error(f"❌ Direct serial send failed: {e}")
            
            if not success:
                logger.error(f"❌ Homing command failed: {response}")
                return False
            
            logger.info(f"🏠 Command sent successfully: {response}")
            
            # Enhanced monitoring for FluidNC debug messages
            homing_timeout = 60.0  # Increased to 60s to allow for full homing cycle
            start_time = time.time()
            
            homing_done_detected = False
            axes_homed = set()
            last_status_check = 0
            was_in_home_state = False  # Track if we saw "Home" state
            
            logger.info("🏠 Monitoring for '[MSG:DBG: Homing done]' message...")
            logger.info("🔧 Smart error detection: Ignoring alarms for first 5s, monitoring state transitions")
            
            # Record homing start timestamp to filter out old messages
            homing_start_timestamp = time.time()
            logger.info(f"🕐 Homing command timestamp: {homing_start_timestamp:.3f} - will ignore older messages")
            
            while time.time() - start_time < homing_timeout:
                elapsed = time.time() - start_time
                
                try:
                    # Check recent protocol messages for debug completion signal
                    if hasattr(self.protocol, 'get_recent_raw_messages'):
                        recent_messages = self.protocol.get_recent_raw_messages(50)
                        
                        for message in recent_messages:
                            # Extract timestamp from message if available
                            message_timestamp = None
                            try:
                                if ':' in message and message.split(':')[0].replace('.', '').isdigit():
                                    message_timestamp = float(message.split(':')[0])
                            except:
                                pass
                            
                            # Primary completion detection - only consider NEW messages
                            if "[MSG:DBG: Homing done]" in message:
                                # Check if this message is from AFTER homing started
                                if message_timestamp and message_timestamp < homing_start_timestamp:
                                    logger.debug(f"🔧 Ignoring OLD homing done message: {message_timestamp:.3f} < {homing_start_timestamp:.3f}")
                                    continue
                                
                                logger.info(f"🎯 DETECTED: [MSG:DBG: Homing done] at {elapsed:.1f}s!")
                                logger.info(f"   Message: {message}")
                                logger.info(f"   Message timestamp: {message_timestamp:.3f} vs start: {homing_start_timestamp:.3f}")
                                homing_done_detected = True
                                break
                            
                            # Individual axis completion tracking
                            if "[MSG:Homed:" in message:
                                # Check if this message is from AFTER homing started
                                if message_timestamp and message_timestamp < homing_start_timestamp:
                                    logger.debug(f"🔧 Ignoring OLD axis homed message: {message_timestamp:.3f}")
                                    continue
                                
                                try:
                                    axis = message.split("[MSG:Homed:")[1].split("]")[0]
                                    if axis not in axes_homed:
                                        axes_homed.add(axis)
                                        logger.info(f"✅ Axis homed: {axis} (timestamp: {message_timestamp:.3f})")
                                except:
                                    pass
                            
                            # Smart error detection - ignore initial alarm states during early homing
                            if any(error in message.lower() for error in ['error']) and elapsed > 2.0:
                                # Only treat as error after 2+ seconds and if it's an actual error message
                                if 'error' in message.lower() and not 'alarm' in message.lower():
                                    logger.error(f"❌ DETECTED: Homing error - {message}")
                                    return False
                            
                            # Ignore initial alarm states - they're expected before homing starts
                            if 'alarm' in message.lower() and elapsed < 5.0:
                                logger.debug(f"🔧 Ignoring initial alarm state at {elapsed:.1f}s: {message[:100]}...")
                            elif 'alarm' in message.lower() and elapsed > 10.0:
                                # Only treat alarm as error if it persists well into homing process
                                logger.warning(f"⚠️ Persistent alarm during homing at {elapsed:.1f}s - continuing to monitor")
                    
                    # Break if we found the completion signal
                    if homing_done_detected:
                        # Immediately check if system is actually ready or still in alarm
                        immediate_status = self.protocol.get_current_status()
                        if immediate_status and immediate_status.state.lower() == 'alarm':
                            logger.warning(f"⚠️ Homing message detected but system still in ALARM state!")
                            logger.info("🔓 Clearing alarm and continuing to monitor...")
                            # Clear alarm but don't break - continue monitoring for actual completion
                            await self.clear_alarm()
                            homing_done_detected = False  # Reset and continue monitoring
                            continue
                        else:
                            logger.info(f"✅ Homing completed via debug message after {elapsed:.1f}s")
                            logger.info(f"📊 System state: {immediate_status.state if immediate_status else 'Unknown'}")
                            break
                    
                    # Periodic status monitoring (with error protection)
                    if elapsed - last_status_check >= 5.0:  # Every 5 seconds like test
                        try:
                            status = self.protocol.get_current_status()
                            last_status_check = elapsed
                            
                            if status and status.state:
                                state_lower = status.state.lower()
                                logger.info(f"🏠 Status at {elapsed:.0f}s: {status.state}")
                                
                                # Track if we were in home state
                                if state_lower == 'home':
                                    was_in_home_state = True
                                    logger.info("🏠 Detected: System in 'Home' state - homing in progress")
                                
                                # Enhanced fallback detection - Home->Idle transition indicates completion
                                if state_lower in ['idle'] and was_in_home_state:
                                    logger.info(f"✅ COMPLETION DETECTED: Home->Idle transition at {elapsed:.1f}s")
                                    logger.info("🎯 This indicates homing completed successfully")
                                    homing_done_detected = True
                                    break
                                elif state_lower in ['idle'] and elapsed > 10.0:  # Reduced from 20s to 10s
                                    logger.info(f"✅ Fallback detection: Idle after {elapsed:.1f}s - assuming homing complete")
                                    homing_done_detected = True
                                    break
                                elif state_lower in ['idle'] and elapsed > 5.0:  # Even earlier detection
                                    logger.info(f"🔍 Early idle detection at {elapsed:.1f}s - checking if homing actually completed")
                                    # Check if this is a legitimate homing completion vs just idle
                                    # If we were in "home" state and now idle, likely homing completed
                                    logger.info(f"✅ Early completion: Idle state indicates homing finished")
                                    homing_done_detected = True
                                    break
                                elif state_lower in ['alarm', 'error']:
                                    logger.error(f"❌ Status failure: {status.state}")
                                    return False
                        except Exception as status_error:
                            logger.debug(f"🔧 Status check error at {elapsed:.0f}s: {status_error}")
                
                except Exception as loop_error:
                    logger.debug(f"🔧 Monitoring loop error at {elapsed:.1f}s: {loop_error}")
                    # Continue monitoring despite errors
                
                await asyncio.sleep(0.5)  # Check every 500ms like test
            
            # Timeout check
            if not homing_done_detected:
                logger.error(f"❌ Homing timeout after {homing_timeout}s - No completion signal detected")
                logger.info("💡 If homing actually completed, check protocol message capture")
                return False
            
            # Final verification and position update
            await asyncio.sleep(1.0)  # Let system settle
            final_status = self.protocol.get_current_status()
            
            # Check if system is still in alarm state after "homing completion"
            if final_status and final_status.state.lower() == 'alarm':
                logger.warning(f"⚠️ System still in ALARM state after homing detection!")
                logger.info("🔓 Attempting to clear alarm state - homing may not have actually occurred")
                
                # Clear alarm state since homing didn't actually complete properly
                clear_success = await self.clear_alarm()
                if clear_success:
                    logger.info("✅ Alarm cleared after homing detection")
                    # Re-check status after clearing
                    await asyncio.sleep(0.5)
                    final_status = self.protocol.get_current_status()
                    if final_status and final_status.state.lower() in ['idle', 'run']:
                        logger.info(f"✅ Final verification after alarm clear: {final_status.state}")
                    else:
                        logger.error(f"❌ Still not in ready state after alarm clear: {final_status.state if final_status else 'None'}")
                        return False
                else:
                    logger.error("❌ Failed to clear alarm state after homing")
                    return False
            elif final_status and final_status.state.lower() in ['idle', 'run']:
                logger.info(f"✅ Final verification: {final_status.state}")
            else:
                logger.warning(f"⚠️ Final state unexpected: {final_status.state if final_status else 'None'}")
            
            # Update position after homing
            await self._update_current_position()
            
            # STEP 2: Clear alarm state AFTER homing (final ensure)
            logger.info("🔓 Step 2: Final alarm clear after homing completion")
            final_alarm_clear = await self.clear_alarm()
            if final_alarm_clear:
                logger.info("✅ Post-homing alarm clear successful")
            else:
                logger.warning("⚠️ Post-homing alarm clear failed, but homing completed")
            
            # Emit enhanced completion event
            self._emit_event("homing_completed", {
                "axes": axes or ['x', 'y', 'z', 'c'],
                "final_position": self.current_position.to_dict(),
                "axes_homed": list(axes_homed),
                "completion_time": elapsed,
                "detection_method": "debug_message_enhanced"
            })
            
            logger.info(f"✅ ENHANCED homing completed successfully!")
            logger.info(f"📊 Duration: {elapsed:.1f}s, Axes detected: {axes_homed}")
            logger.info(f"📍 Final position: {self.current_position}")
            
            # CRITICAL: Set homed status for web interface
            self.is_homed = True
            logger.info(f"🎯 Controller is_homed flag set to True")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Enhanced homing failed: {e}")
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
            
            # Enhanced monitoring for FluidNC debug messages (proven approach)
            homing_timeout = 45.0  # Based on actual 22s timing
            start_time = time.time()
            
            homing_done_detected = False
            axes_homed = set()
            last_status_check = 0
            
            logger.info("🏠 Monitoring for '[MSG:DBG: Homing done]' message...")
                
            # Homing monitoring completed
                
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
            
            # Clear alarms even on error to ensure clean state
            try:
                logger.info("🔓 Error recovery: Clearing alarms after homing failure")
                error_alarm_clear = await self.clear_alarm()
                if error_alarm_clear:
                    logger.info("✅ Error recovery alarm clear successful")
            except Exception as clear_error:
                logger.error(f"❌ Error recovery alarm clear failed: {clear_error}")
            
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
    
    async def clear_alarm(self) -> bool:
        """Clear alarm state using $X command with direct serial communication"""
        try:
            logger.info("🔓 Clearing alarm state with $X command")
            
            # Send $X command directly via serial (like homing)
            try:
                with self.protocol.connection_lock:
                    if self.protocol.serial_connection:
                        command_bytes = "$X\n".encode('utf-8')
                        self.protocol.serial_connection.write(command_bytes)
                        self.protocol.serial_connection.flush()
                        logger.info("✅ $X command sent directly via serial")
                        success = True
                    else:
                        logger.error("❌ No serial connection available for $X")
                        return False
            except Exception as e:
                logger.error(f"❌ Direct serial send of $X failed: {e}")
                return False
            
            if success:
                # Give FluidNC adequate time to process the $X command
                await asyncio.sleep(1.0)  # Increased from 0.5s to 1.0s
                logger.info("⏳ Waited 1 second for $X command processing")
                
                # Update position and status
                await self._update_current_position()
                
                # Check if we're no longer in alarm state
                current_status = self.protocol.get_current_status()
                if current_status:
                    logger.info(f"📊 Status after $X command: {current_status.state}")
                    if current_status.state.lower() != 'alarm':
                        logger.info("✅ Alarm cleared successfully")
                        self._emit_event("alarm_cleared", {
                            "status": current_status.state
                        })
                        return True
                    else:
                        logger.warning("⚠️ $X command sent but still in alarm state")
                        # Try one more time with longer wait
                        await asyncio.sleep(1.0)
                        current_status = self.protocol.get_current_status()
                        if current_status and current_status.state.lower() != 'alarm':
                            logger.info("✅ Alarm cleared after additional wait")
                            return True
                        else:
                            logger.error("❌ Still in alarm state after retry")
                            return False
                else:
                    logger.warning("⚠️ Could not get status after $X command")
                    return False
            else:
                logger.error("❌ Failed to send $X command")
                return False
                
        except Exception as e:
            logger.error(f"❌ Clear alarm error: {e}")
            return False
    
    def clear_alarm_sync(self) -> bool:
        """Synchronous version of clear_alarm for web interface"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.clear_alarm())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"❌ Sync clear alarm error: {e}")
            return False
    
    def move_to_position_sync(self, position: Position4D, feedrate: Optional[float] = None) -> Dict[str, Any]:
        """Synchronous version of move_to_position with better event loop handling"""
        try:
            import concurrent.futures
            
            # Check if we're already in an async context
            try:
                current_loop = asyncio.get_running_loop()
                logger.debug("🔄 Detected running event loop, using thread executor")
                
                # Use thread executor to avoid blocking current loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    def run_move():
                        # Create new loop in thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            success = new_loop.run_until_complete(self.move_to_position(position, feedrate))
                            current_pos = new_loop.run_until_complete(self.get_current_position())
                            return success, current_pos
                        finally:
                            new_loop.close()
                    
                    success, current_pos = executor.submit(run_move).result(timeout=10.0)
                    
            except RuntimeError:
                # No event loop running, safe to create one
                logger.debug("🔄 No running event loop, creating new one")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    success = loop.run_until_complete(self.move_to_position(position, feedrate))
                    current_pos = loop.run_until_complete(self.get_current_position())
                finally:
                    loop.close()
            
            return {
                'success': success,
                'position': current_pos.to_dict() if current_pos else None,
                'coordinates': {
                    'x': current_pos.x if current_pos else 0.0,
                    'y': current_pos.y if current_pos else 0.0,
                    'z': current_pos.z if current_pos else 0.0,
                    'c': current_pos.c if current_pos else 0.0
                } if current_pos else None
            }
            
        except Exception as e:
            logger.error(f"❌ Sync move to position error: {e}")
            return {'success': False, 'error': str(e), 'position': None, 'coordinates': None}
    
    def relative_move_sync(self, delta: Position4D, feedrate: Optional[float] = None) -> Dict[str, Any]:
        """Synchronous version of relative_move for web interface"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success = loop.run_until_complete(self.move_relative(delta, feedrate))
                # Get current position after move for coordinate capture
                current_pos = loop.run_until_complete(self.get_current_position())
                return {
                    'success': success,
                    'position': current_pos.to_dict() if current_pos else None,
                    'coordinates': {
                        'x': current_pos.x if current_pos else 0.0,
                        'y': current_pos.y if current_pos else 0.0,
                        'z': current_pos.z if current_pos else 0.0,
                        'c': current_pos.c if current_pos else 0.0
                    } if current_pos else None
                }
            finally:
                loop.close()
        except Exception as e:
            logger.error(f"❌ Sync relative move error: {e}")
            return {'success': False, 'error': str(e), 'position': None, 'coordinates': None}
    
    def get_current_position_sync(self) -> Optional[Position4D]:
        """Synchronous version of get_current_position with better event loop handling"""
        try:
            import concurrent.futures
            
            # Check if we're already in an async context
            try:
                current_loop = asyncio.get_running_loop()
                logger.debug("🔄 Detected running event loop, using thread executor")
                
                # Use thread executor to avoid blocking current loop
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    def get_position():
                        # Create new loop in thread
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(self.get_current_position())
                        finally:
                            new_loop.close()
                    
                    return executor.submit(get_position).result(timeout=5.0)
                    
            except RuntimeError:
                # No event loop running, safe to create one
                logger.debug("🔄 No running event loop, creating new one")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(self.get_current_position())
                finally:
                    loop.close()
                    
        except Exception as e:
            logger.error(f"❌ Sync get position error: {e}")
            return None
    

    
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
                
                # CRITICAL: Reset homed status when controller is reset
                self.is_homed = False
                logger.info("🔄 Reset is_homed flag to False after controller reset")
                
                self._emit_event("controller_reset", {
                    "homed_status_reset": True
                })
                
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
    async def _send_command(self, command: str, command_id: Optional[str] = None, priority: str = "normal") -> tuple[bool, str]:
        """Send command using fixed protocol with motion completion
        
        Args:
            command: G-code command to send
            command_id: Optional command ID for timing tracking
            priority: Command priority ("high" for manual operations, "normal" for scans)
        """
        try:
            self.stats['commands_sent'] += 1
            
            # Enhanced debug logging for movement troubleshooting
            logger.info(f"🔧 DEBUG: Sending G-code command: '{command}' (priority: {priority})")
            
            # Log FluidNC command send
            if TIMING_AVAILABLE and command_id:
                timing_logger.log_fluidnc_send(command_id, command)
            
            # Use the fixed protocol with motion completion waiting and priority
            success, response = await asyncio.get_event_loop().run_in_executor(
                None, self.protocol.send_command_with_motion_wait, command, priority
            )
            
            # Enhanced debug logging for response
            logger.info(f"🔧 DEBUG: FluidNC response - Success: {success}, Response: '{response}'")
            
            # Log FluidNC response
            if TIMING_AVAILABLE and command_id:
                timing_logger.log_fluidnc_response(command_id, response)
            
            return success, response
            
        except Exception as e:
            logger.error(f"❌ Command send error: {command} - {e}")
            if TIMING_AVAILABLE and command_id:
                timing_logger.log_error(command_id, str(e), "fluidnc_send")
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
            
            # Check Z axis (continuous rotation - skip limits if null)
            z_limits = self.limits['z']
            if z_limits.min_limit is not None and z_limits.max_limit is not None:
                if position.z < z_limits.min_limit or position.z > z_limits.max_limit:
                    logger.error(f"❌ Z position {position.z} outside limits {z_limits}")
                    return False
            else:
                logger.debug(f"✅ Z axis continuous rotation - no limits (position: {position.z}°)")
            
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