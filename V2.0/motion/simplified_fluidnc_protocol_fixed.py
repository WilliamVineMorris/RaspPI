#!/usr/bin/env python3
"""
Fixed FluidNC Protocol with Motion Completion Waiting

This version addresses the key issues found in testing:
1. Waits for motion completion before returning
2. Properly tracks current position
3. Handles motion state correctly

Author: Scanner System Redesign  
Created: September 24, 2025
"""

import logging
import threading
import time
import serial
from typing import Optional, Dict, Any, Callable, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FluidNCStatus:
    """FluidNC status information"""
    state: str = "Unknown"
    position: Optional[Dict[str, float]] = None
    work_position: Optional[Dict[str, float]] = None
    feed_rate: float = 0.0
    spindle_speed: float = 0.0
    machine_position: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        if self.position is None:
            self.position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0}
        if self.work_position is None:
            self.work_position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0}
        if self.machine_position is None:
            self.machine_position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0}


class SimplifiedFluidNCProtocolFixed:
    """
    Simplified FluidNC protocol with proper motion completion waiting
    
    Key improvements:
    - Waits for motion to complete before returning
    - Properly tracks current position
    - Handles "Idle" state transitions correctly
    """
    
    def __init__(self, port: str = '/dev/ttyUSB0', baud_rate: int = 115200, 
                 command_timeout: float = 10.0):
        self.port = port
        self.baud_rate = baud_rate
        self.command_timeout = command_timeout
        
        # Connection
        self.serial_connection: Optional[serial.Serial] = None
        self.connection_lock = threading.RLock()
        self.connected = False
        
        # Status monitoring
        self.current_status: Optional[FluidNCStatus] = None
        self.status_callbacks: list[Callable[[FluidNCStatus], None]] = []
        self.status_monitor_running = False
        self.status_thread: Optional[threading.Thread] = None
        
        # Command execution with motion completion
        self.command_lock = threading.RLock()
        self.last_command_time = 0
        self.command_delay = 0.02  # Reduced from 0.1s to 20ms for responsiveness
        self.manual_command_delay = 0.005  # Ultra-fast for manual operations - 5ms
        self.motion_timeout = 30.0  # Maximum time to wait for motion completion
        
        # Command queue management  
        self.pending_commands = 0
        self.max_pending_commands = 5  # Increased limit to prevent dropping important commands
        
        # Message capture for enhanced homing detection
        self.recent_raw_messages: list[str] = []
        self.max_message_history = 100
        self.message_lock = threading.RLock()
        
        # Statistics
        self.stats: Dict[str, Any] = {
            'commands_sent': 0,
            'responses_received': 0,
            'timeouts': 0,
            'motion_commands': 0,
            'motion_timeouts': 0,
            'connection_time': 0.0,
            'debug_messages_captured': 0
        }
    
    def connect(self) -> bool:
        """Connect to FluidNC controller"""
        with self.connection_lock:
            try:
                logger.info(f"🔌 Connecting to FluidNC at {self.port}")
                
                # Close existing connection
                self._close_connection()
                
                # Open new connection
                self.serial_connection = serial.Serial(
                    port=self.port,
                    baudrate=self.baud_rate,
                    timeout=1.0,
                    write_timeout=1.0
                )
                
                # Clear any pending data
                time.sleep(0.5)
                self.serial_connection.reset_input_buffer()
                self.serial_connection.reset_output_buffer()
                
                # Test connection with status request
                if self._test_connection():
                    self.connected = True
                    self.stats['connection_time'] = time.time()
                    
                    # Start status monitoring
                    self._start_status_monitoring()
                    
                    logger.info("✅ FluidNC connected successfully")
                    return True
                else:
                    self._close_connection()
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Connection failed: {e}")
                self._close_connection()
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from FluidNC"""
        with self.connection_lock:
            try:
                logger.info("🔌 Disconnecting from FluidNC")
                
                # Stop status monitoring
                self._stop_status_monitoring()
                
                # Close connection
                self._close_connection()
                
                logger.info("✅ FluidNC disconnected")
                return True
                
            except Exception as e:
                logger.error(f"❌ Disconnect error: {e}")
                return False
    
    def is_connected(self) -> bool:
        """Check if connected with enhanced stability checking"""
        try:
            is_conn = (self.connected and 
                      self.serial_connection is not None and 
                      self.serial_connection.is_open)
            
            # If connection appears good, verify it's actually responsive
            if is_conn and time.time() - self.last_command_time > 5.0:
                # Haven't sent commands recently, connection might be stale
                # Quick validation without blocking
                try:
                    if self.serial_connection and self.serial_connection.in_waiting is not None:
                        return True
                    else:
                        logger.debug("Connection validation failed - serial not responsive")
                        return False
                except:
                    logger.debug("Connection validation failed - exception during check")
                    return False
            
            return is_conn
        except Exception as e:
            logger.debug(f"Connection check failed: {e}")
            return False
    
    def send_command_with_motion_wait(self, command: str, priority: str = "normal") -> Tuple[bool, str]:
        """
        Send command and wait for motion completion if it's a motion command
        
        This is the key fix - we wait for the machine to return to Idle state
        after motion commands before considering the command complete.
        
        Args:
            command: G-code command to send
            priority: Command priority ("high" for manual operations, "normal" for scans)
        """
        start_time = time.time()
        logger.debug(f"🕐 [TIMING] Starting {priority} priority command: {command}")
        
        # Check for command queue buildup (only for motion commands to prevent system overload)
        is_motion_cmd = self._is_motion_command(command)
        if priority == "high" and is_motion_cmd and self.pending_commands > self.max_pending_commands:
            logger.debug(f"⚠️ Dropping high-priority motion command due to queue buildup: {self.pending_commands}")
            return False, "Motion command queue full"
        
        with self.command_lock:
            if not self.is_connected():
                return False, "Not connected"
            
            # Track pending commands
            self.pending_commands += 1
            
            try:
                # Enforce command delay (priority-aware)
                current_time = time.time()
                time_since_last = current_time - self.last_command_time
                
                # Use faster delay for high priority (manual) operations
                if priority == "high":
                    active_delay = self.manual_command_delay
                    delay_type = "High-priority"
                else:
                    active_delay = self.command_delay
                    delay_type = "Standard"
                
                if time_since_last < active_delay:
                    delay_needed = active_delay - time_since_last
                    logger.debug(f"⏳ [TIMING] {delay_type} command delay: {delay_needed*1000:.1f}ms")
                    time.sleep(delay_needed)
                
                # Continue with command execution
                command_ready_time = time.time()
                logger.debug(f"🕐 [TIMING] Command ready after: {(command_ready_time-start_time)*1000:.1f}ms")
                logger.debug(f"📤 Command: {command}")
                
                # Send command
                if self.serial_connection is None:
                    return False, "No serial connection"
                    
                command_line = f"{command}\n"
                self.serial_connection.write(command_line.encode('utf-8'))
                self.serial_connection.flush()
                
                self.stats['commands_sent'] += 1
                self.last_command_time = time.time()
                
                command_sent_time = time.time()
                logger.debug(f"📤 [TIMING] Command sent after: {(command_sent_time-start_time)*1000:.1f}ms")
                
                # Wait for immediate response (ok/error) - shorter timeout for manual commands
                response_timeout = 2.0 if priority == "high" else self.command_timeout
                immediate_response = self._wait_for_immediate_response(response_timeout)
                response_received_time = time.time() 
                logger.debug(f"📥 [TIMING] Response received after: {(response_received_time-start_time)*1000:.1f}ms")
                
                if not immediate_response:
                    self.stats['timeouts'] += 1
                    return False, "Command timeout"
                
                # Check if this is a motion command
                is_motion_command = self._is_motion_command(command)
                
                if is_motion_command:
                    logger.debug(f"⏳ [TIMING] Starting motion wait: {command}")
                    motion_wait_start = time.time()
                    self.stats['motion_commands'] += 1
                    
                    # Wait for motion to complete (machine returns to Idle)
                    if self._wait_for_motion_completion():
                        motion_complete_time = time.time()
                        logger.debug(f"✅ [TIMING] Motion completed: {command} - Motion wait: {(motion_complete_time-motion_wait_start)*1000:.1f}ms")
                        logger.debug(f"🏁 [TIMING] Total command time: {(motion_complete_time-start_time)*1000:.1f}ms")
                        return True, immediate_response
                    else:
                        motion_timeout_time = time.time()
                        logger.warning(f"⚠️ [TIMING] Motion completion timeout: {command} - Timeout after: {(motion_timeout_time-motion_wait_start)*1000:.1f}ms")
                        self.stats['motion_timeouts'] += 1
                        # Still return success as the command was accepted
                        return True, immediate_response
                else:
                    # Non-motion command, immediate response is sufficient
                    non_motion_complete_time = time.time()
                    logger.debug(f"🏁 [TIMING] Non-motion command completed: {(non_motion_complete_time-start_time)*1000:.1f}ms")
                    return True, immediate_response
                
            except Exception as e:
                logger.error(f"❌ Command failed: {command} - {e}")
                return False, f"Command error: {e}"
            finally:
                # Always decrement pending commands
                self.pending_commands = max(0, self.pending_commands - 1)
    
    def send_command(self, command: str) -> Tuple[bool, str]:
        """Send command (legacy interface, uses motion wait)"""
        return self.send_command_with_motion_wait(command)
    
    def send_homing_command(self, command: str = "$H") -> Tuple[bool, str]:
        """
        Send homing command with status-based monitoring.
        
        FluidNC doesn't always send immediate 'ok' for $H commands.
        Instead, it starts homing and reports status changes.
        This method monitors status changes rather than waiting for 'ok'.
        """
        logger.info(f"🏠 Sending homing command with status monitoring: {command}")
        
        with self.command_lock:
            if not self.is_connected():
                return False, "Not connected"
            
            # Track pending commands
            self.pending_commands += 1
            
            try:
                start_time = time.time()
                
                # Store initial status
                initial_status = self.current_status.state if self.current_status else None
                logger.debug(f"📊 Status before homing: {initial_status}")
                
                # Send command
                logger.debug(f"📤 Homing Command: {command}")
                
                if self.serial_connection is None:
                    return False, "No serial connection"
                    
                # Clear input buffer to ensure fresh status updates
                self.serial_connection.reset_input_buffer()
                
                command_line = f"{command}\n"
                self.serial_connection.write(command_line.encode('utf-8'))
                self.serial_connection.flush()
                
                self.stats['commands_sent'] += 1
                self.last_command_time = time.time()
                
                command_sent_time = time.time()
                logger.debug(f"📤 [TIMING] Homing command sent after: {(command_sent_time-start_time)*1000:.1f}ms")
                
                # Monitor for status change instead of waiting for 'ok'
                return self._monitor_homing_status_change(initial_status, start_time)
                    
            except Exception as e:
                logger.error(f"❌ Homing command error: {e}")
                return False, f"Command error: {e}"
            finally:
                self.pending_commands = max(0, self.pending_commands - 1)

    def _monitor_homing_status_change(self, initial_status: str | None, start_time: float) -> Tuple[bool, str]:
        """Monitor for status changes that indicate homing has started."""
        timeout = 8.0  # 8 seconds to see status change
        last_activity = start_time
        
        while (time.time() - start_time) < timeout:
            time.sleep(0.1)  # Check every 100ms
            
            # Check for incoming data
            if self.serial_connection and self.serial_connection.in_waiting > 0:
                try:
                    data = self.serial_connection.read(self.serial_connection.in_waiting)
                    if data:
                        decoded = data.decode('utf-8', errors='ignore')
                        self._process_incoming_data(decoded)
                        last_activity = time.time()
                        
                        # Check for immediate 'ok' response (some FluidNC versions send this)
                        if 'ok' in decoded.lower():
                            logger.info("✅ Received 'ok' - homing command accepted")
                            return True, "Homing started"
                            
                except Exception as e:
                    logger.debug(f"Error reading serial data: {e}")
            
            # Check if status changed
            current_status = self.current_status.state if self.current_status else None
            
            if current_status and current_status != initial_status:
                if current_status == "Homing":
                    logger.info(f"✅ Homing started (status: {initial_status} → {current_status})")
                    return True, f"Status changed to {current_status}"
                elif current_status == "Idle" and initial_status == "Alarm":
                    # Quick homing completion (ALARM → IDLE directly)
                    logger.info(f"✅ Homing completed quickly (status: {initial_status} → {current_status})")
                    return True, "Homing completed"
                elif current_status == "Alarm" and initial_status != "Alarm":
                    # Something went wrong
                    logger.error(f"❌ Homing triggered alarm (status: {initial_status} → {current_status})")
                    return False, "Homing caused alarm"
                else:
                    logger.debug(f"📊 Status change detected: {initial_status} → {current_status}")
            
            # Check for prolonged inactivity
            if (time.time() - last_activity) > 3.0:
                logger.warning("⚠️ No response from FluidNC - may be unresponsive")
                # Continue waiting but log concern
        
        # Check final activity level
        if (time.time() - last_activity) < 2.0:
            logger.warning("⚠️ FluidNC responsive but no clear homing confirmation")
            logger.info("💡 Assuming homing started - will monitor via status updates")
            return True, "Assumed started"
        else:
            logger.error("❌ No response from FluidNC after homing command")
            return False, "No response"

    def _process_incoming_data(self, data: str):
        """Process incoming data from FluidNC."""
        if not data.strip():
            return
            
        # Process each line
        for line in data.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # Status reports (e.g., <Idle|MPos:0.000,0.000,0.000|...>)
            if line.startswith('<') and line.endswith('>'):
                self._parse_status_report(line)
                logger.debug(f"📡 Status update: {line}")
            
            # Error responses
            elif line.startswith('error:'):
                logger.error(f"🔴 FluidNC error: {line}")
            
            # Alarm messages
            elif 'ALARM' in line.upper():
                logger.warning(f"⚠️ Alarm message: {line}")
            
            # OK responses
            elif line.strip().lower() == 'ok':
                logger.debug("✅ Received 'ok' response")
            
            # Grbl messages
            elif line.startswith('[') and line.endswith(']'):
                logger.info(f"📢 FluidNC message: {line}")
            
            # Other responses
            else:
                logger.debug(f"📥 FluidNC: {line}")

    def monitor_homing_progress(self, callback=None) -> bool:
        """
        Monitor homing progress using real-time status updates.
        Returns True when homing completes, False if it fails or times out.
        """
        logger.info("📊 Monitoring homing progress via real-time status updates...")
        
        start_time = time.time()
        last_status_time = start_time
        last_position = None
        position_unchanged_count = 0
        max_homing_time = 120.0  # 2 minutes max for homing
        inactivity_timeout = 15.0  # 15 seconds without status updates
        
        while (time.time() - start_time) < max_homing_time:
            time.sleep(0.5)  # Check every 500ms
            
            current_time = time.time()
            elapsed_time = current_time - start_time
            
            # Check for status updates
            if self.current_status:
                current_status = self.current_status.state
                current_position = getattr(self.current_status, 'position', None)
                
                # Update callback with progress
                if callback:
                    try:
                        callback(f"homing", f"Homing in progress (status: {current_status})", elapsed_time)
                    except Exception as e:
                        logger.debug(f"Callback error: {e}")
                
                # Check if we have recent status updates
                status_age = current_time - (getattr(self.current_status, 'timestamp', 0) or last_status_time)
                if status_age < 2.0:  # Status is recent
                    last_status_time = current_time
                    
                    # Check for position changes (axes moving)
                    if current_position and last_position:
                        if current_position != last_position:
                            position_unchanged_count = 0
                            logger.debug(f"🔄 Axes moving: {last_position} → {current_position}")
                        else:
                            position_unchanged_count += 1
                    
                    last_position = current_position
                
                # Check for completion
                if current_status == "Idle":
                    # Confirm completion with brief delay
                    time.sleep(1.0)
                    if self.current_status and self.current_status.state == "Idle":
                        logger.info("✅ Homing completed successfully")
                        if callback:
                            callback("complete", "Homing completed successfully!", elapsed_time)
                        return True
                
                # Check for errors
                elif current_status == "Alarm":
                    logger.error("❌ Homing failed - ALARM state")
                    if callback:
                        callback("error", "Homing failed - ALARM triggered", elapsed_time)
                    return False
                
                # Check for stuck condition (no movement for too long)
                if position_unchanged_count > 20 and current_status == "Homing":  # 10+ seconds no movement
                    logger.warning(f"⚠️ No axis movement detected for {position_unchanged_count/2}s during homing")
                    # Don't fail immediately - axes might move slowly
            
            # Check for system inactivity
            if (current_time - last_status_time) > inactivity_timeout:
                logger.error(f"❌ No status updates for {inactivity_timeout}s - system unresponsive")
                if callback:
                    callback("error", "System unresponsive - no status updates", elapsed_time)
                return False
        
        logger.error(f"❌ Homing timeout after {max_homing_time}s")
        if callback:
            callback("error", f"Homing timeout after {max_homing_time}s", elapsed_time)
        return False
    
    def _is_motion_command(self, command: str) -> bool:
        """Check if command causes motion"""
        command_upper = command.upper().strip()
        
        # G-code motion commands
        motion_gcodes = ['G0', 'G1', 'G2', 'G3', 'G38']
        
        for gcode in motion_gcodes:
            if command_upper.startswith(gcode):
                return True
        
        # Homing commands
        if command_upper.startswith('$H') or command_upper == '$H':
            return True
            
        return False
    
    def _wait_for_motion_completion(self) -> bool:
        """
        Wait for motion to complete by monitoring machine state
        Optimized to reduce interference with command execution
        """
        start_time = time.time()
        motion_started = False
        last_status_request = 0
        status_request_interval = 0.2  # Reduced frequency: every 200ms
        
        while time.time() - start_time < self.motion_timeout:
            current_time = time.time()
            
            # Send status requests less frequently and only when needed
            if current_time - last_status_request > status_request_interval:
                if self.serial_connection:
                    try:
                        self.serial_connection.write(b'?')
                        self.serial_connection.flush()
                        last_status_request = current_time
                    except:
                        break
            
            # Shorter sleep for more responsive checking
            time.sleep(0.05)
            
            if self.current_status:
                state = self.current_status.state.lower()
                
                if state in ['run', 'jog']:
                    motion_started = True
                    logger.debug(f"🔄 Motion in progress: {state}")
                elif state == 'idle' and motion_started:
                    logger.debug("✅ Motion completed - machine idle")
                    return True
                elif state == 'idle' and not motion_started:
                    # Machine was already idle, give it a moment to start motion
                    if time.time() - start_time > 0.3:  # Reduced from 0.5s
                        logger.debug("✅ Motion completed - machine remained idle")
                        return True
                elif state in ['alarm', 'error']:
                    logger.warning(f"⚠️ Motion stopped due to: {state}")
                    return False
        
        logger.warning(f"⏰ Motion completion timeout after {self.motion_timeout}s")
        return False
    
    def _wait_for_immediate_response(self, timeout: float) -> Optional[str]:
        """Wait for immediate command response (ok/error)"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    if not line:
                        continue
                    
                    # Capture all raw messages for homing detection
                    self._capture_raw_message(line)
                    
                    # Handle status reports (update current status) - with error protection
                    if line.startswith('<') and line.endswith('>'):
                        try:
                            self._parse_status_report(line)
                        except Exception as parse_error:
                            logger.warning(f"🔧 Status parsing recovered from error: {parse_error}")
                            # Continue processing other messages even if this one fails
                        continue
                    
                    # Handle debug/info messages (but we already captured them)
                    if line.startswith('[') and line.endswith(']'):
                        # Track debug messages for statistics
                        if "[MSG:DBG:" in line or "[MSG:Homed:" in line:
                            self.stats['debug_messages_captured'] += 1
                        continue
                    
                    # Command response
                    if line.lower() in ['ok', 'error'] or line.startswith('error:'):
                        self.stats['responses_received'] += 1
                        return line
                
                time.sleep(0.01)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Response wait error: {e}")
            return None
    
    def _parse_status_report(self, status_line: str):
        """Parse status report and update current status - Enhanced with error handling"""
        try:
            # Example: <Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0>
            if not (status_line.startswith('<') and status_line.endswith('>')):
                return
            
            content = status_line[1:-1]  # Remove < >
            parts = content.split('|')
            
            if not parts:
                return
            
            # Parse state
            state = parts[0]
            
            # Initialize status
            status = FluidNCStatus(state=state)
            
            # Parse other parts with enhanced error handling
            for part in parts[1:]:
                try:
                    if part.startswith('MPos:'):
                        # Machine position with safe float parsing
                        coords = part[5:].split(',')
                        if len(coords) >= 4:
                            # Validate each coordinate before parsing
                            parsed_coords = []
                            for coord in coords[:4]:  # Only take first 4
                                # Clean up potential corruption (multiple decimals, etc.)
                                clean_coord = coord.strip()
                                if clean_coord.count('.') > 1:
                                    # Handle corrupted coordinates like '0.0000.673'
                                    logger.warning(f"🔧 Fixing corrupted coordinate: '{clean_coord}'")
                                    # Take the first valid float part
                                    parts_split = clean_coord.split('.')
                                    if len(parts_split) >= 2:
                                        clean_coord = f"{parts_split[0]}.{parts_split[1]}"
                                
                                parsed_coords.append(float(clean_coord))
                            
                            if len(parsed_coords) >= 4:
                                status.machine_position = {
                                    'x': parsed_coords[0],
                                    'y': parsed_coords[1], 
                                    'z': parsed_coords[2],
                                    'a': parsed_coords[3]
                                }
                                # Use machine position as work position for now
                                status.position = status.machine_position.copy()
                                status.work_position = status.machine_position.copy()
                    
                    elif part.startswith('WPos:'):
                        # Work position with safe parsing
                        coords = part[5:].split(',')
                        if len(coords) >= 4:
                            parsed_coords = []
                            for coord in coords[:4]:
                                clean_coord = coord.strip()
                                if clean_coord.count('.') > 1:
                                    logger.warning(f"🔧 Fixing corrupted work coordinate: '{clean_coord}'")
                                    parts_split = clean_coord.split('.')
                                    if len(parts_split) >= 2:
                                        clean_coord = f"{parts_split[0]}.{parts_split[1]}"
                                parsed_coords.append(float(clean_coord))
                            
                            if len(parsed_coords) >= 4:
                                status.work_position = {
                                    'x': parsed_coords[0],
                                    'y': parsed_coords[1],
                                    'z': parsed_coords[2],
                                    'a': parsed_coords[3]
                                }
                                status.position = status.work_position.copy()
                    
                    elif part.startswith('FS:'):
                        # Feed and spindle with safe parsing
                        fs_parts = part[3:].split(',')
                        if len(fs_parts) >= 2:
                            try:
                                status.feed_rate = float(fs_parts[0].strip())
                                status.spindle_speed = float(fs_parts[1].strip())
                            except ValueError:
                                # Skip corrupted feed/spindle data
                                pass
                                
                except ValueError as ve:
                    # Skip corrupted parts but continue parsing other parts
                    logger.debug(f"🔧 Skipping corrupted status part: '{part}' - {ve}")
                    continue
            
            # Update current status
            self.current_status = status
            
            # Notify callbacks
            for callback in self.status_callbacks:
                try:
                    callback(status)
                except Exception as e:
                    logger.error(f"❌ Status callback error: {e}")
            
        except Exception as e:
            logger.error(f"❌ Status parsing error: {e}")
    
    def _test_connection(self) -> bool:
        """Test connection with status request"""
        try:
            if self.serial_connection is None:
                return False
                
            # Send status request
            self.serial_connection.write(b'?\n')
            self.serial_connection.flush()
            
            # Wait for status response
            start_time = time.time()
            while time.time() - start_time < 3.0:
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    # Capture all messages
                    self._capture_raw_message(response)
                    if response.startswith('<') and response.endswith('>'):
                        self._parse_status_report(response)
                        return True
                time.sleep(0.1)
            
            return False
            
        except Exception:
            return False
    
    def _close_connection(self):
        """Close serial connection"""
        try:
            self.connected = False
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
        except Exception as e:
            logger.error(f"❌ Close connection error: {e}")
    
    def _start_status_monitoring(self):
        """Start background status monitoring"""
        if self.status_monitor_running:
            return
        
        self.status_monitor_running = True
        self.status_thread = threading.Thread(target=self._status_monitor_loop, daemon=True)
        self.status_thread.start()
        logger.info("✅ FluidNC connected with auto-reporting enabled")
    
    def _stop_status_monitoring(self):
        """Stop background status monitoring"""
        self.status_monitor_running = False
        if self.status_thread:
            self.status_thread.join(timeout=1.0)
            self.status_thread = None
    
    def _status_monitor_loop(self):
        """Background status monitoring loop with adaptive polling"""
        last_status_request = 0
        base_status_interval = 0.5  # Request status every 500ms normally
        
        while self.status_monitor_running and self.is_connected():
            try:
                current_time = time.time()
                
                # Adaptive status polling: reduce frequency during command execution
                recent_command_activity = (current_time - self.last_command_time) < 2.0
                status_interval = 1.0 if recent_command_activity else base_status_interval
                
                # Request status periodically (but less during active commands)
                if current_time - last_status_request > status_interval:
                    # Check if command lock is free before sending status request
                    if self.command_lock.acquire(blocking=False):
                        try:
                            if self.serial_connection:
                                self.serial_connection.write(b'?')
                                self.serial_connection.flush()
                            last_status_request = current_time
                        finally:
                            self.command_lock.release()
                    else:
                        # Command in progress, skip this status request
                        last_status_request = current_time
                
                # Read any incoming data (process multiple lines to prevent buffer buildup)
                lines_processed = 0
                max_lines_per_cycle = 5  # Prevent overwhelming the parser
                
                while (self.serial_connection and 
                       self.serial_connection.in_waiting > 0 and 
                       lines_processed < max_lines_per_cycle):
                    
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        # Capture all messages for homing detection
                        self._capture_raw_message(line)
                        
                        if line.startswith('<') and line.endswith('>'):
                            self._parse_status_report(line)
                    
                    lines_processed += 1
                
                time.sleep(0.05 if lines_processed == 0 else 0.02)  # Shorter sleep if processing data
                
            except Exception as e:
                logger.error(f"❌ Status monitor error: {e}")
                time.sleep(0.5)
        
        logger.debug("Status monitoring stopped")
    
    # Status and utility methods
    def get_current_status(self) -> Optional[FluidNCStatus]:
        """Get current status"""
        return self.current_status
    
    def get_recent_raw_messages(self, count: int = 20) -> list[str]:
        """Get recent raw messages for debug message detection"""
        with self.message_lock:
            return self.recent_raw_messages[-count:] if self.recent_raw_messages else []
    
    def _capture_raw_message(self, message: str):
        """Capture raw message for homing detection"""
        with self.message_lock:
            self.recent_raw_messages.append(f"{time.time():.3f}: {message}")
            
            # Limit history size
            if len(self.recent_raw_messages) > self.max_message_history:
                self.recent_raw_messages = self.recent_raw_messages[-self.max_message_history:]
            
            # Count debug messages
            if "[MSG:DBG:" in message or "[MSG:Homed:" in message:
                self.stats['debug_messages_captured'] += 1
    
    def add_status_callback(self, callback: Callable[[FluidNCStatus], None]):
        """Add status callback"""
        self.status_callbacks.append(callback)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics"""
        return self.stats.copy()
    
    def send_immediate_command(self, command: str) -> bool:
        """Send immediate command (?, !, ~, reset)"""
        with self.connection_lock:
            if not self.is_connected():
                return False
            
            try:
                if self.serial_connection is None:
                    return False
                    
                logger.debug(f"📤 Immediate: {command}")
                
                if command in ['?', '!', '~']:
                    self.serial_connection.write(command.encode('utf-8'))
                elif command == 'reset':
                    self.serial_connection.write(b'\x18')  # Ctrl-X
                else:
                    return False
                
                self.serial_connection.flush()
                return True
                
            except Exception as e:
                logger.error(f"❌ Immediate command failed: {command} - {e}")
                return False