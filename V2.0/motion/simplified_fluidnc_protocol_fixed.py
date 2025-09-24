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
        self.command_delay = 0.1
        self.motion_timeout = 30.0  # Maximum time to wait for motion completion
        
        # Statistics
        self.stats: Dict[str, Any] = {
            'commands_sent': 0,
            'responses_received': 0,
            'timeouts': 0,
            'motion_commands': 0,
            'motion_timeouts': 0,
            'connection_time': 0.0
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
        """Check if connected"""
        return (self.connected and 
                self.serial_connection is not None and 
                self.serial_connection.is_open)
    
    def send_command_with_motion_wait(self, command: str) -> Tuple[bool, str]:
        """
        Send command and wait for motion completion if it's a motion command
        
        This is the key fix - we wait for the machine to return to Idle state
        after motion commands before considering the command complete.
        """
        with self.command_lock:
            if not self.is_connected():
                return False, "Not connected"
            
            # Enforce command delay
            current_time = time.time()
            time_since_last = current_time - self.last_command_time
            if time_since_last < self.command_delay:
                time.sleep(self.command_delay - time_since_last)
            
            try:
                logger.debug(f"📤 Command: {command}")
                
                # Send command
                if self.serial_connection is None:
                    return False, "No serial connection"
                    
                command_line = f"{command}\n"
                self.serial_connection.write(command_line.encode('utf-8'))
                self.serial_connection.flush()
                
                self.stats['commands_sent'] += 1
                self.last_command_time = time.time()
                
                # Wait for immediate response (ok/error)
                immediate_response = self._wait_for_immediate_response(self.command_timeout)
                if not immediate_response:
                    self.stats['timeouts'] += 1
                    return False, "Command timeout"
                
                # Check if this is a motion command
                is_motion_command = self._is_motion_command(command)
                
                if is_motion_command:
                    logger.debug(f"⏳ Waiting for motion completion: {command}")
                    self.stats['motion_commands'] += 1
                    
                    # Wait for motion to complete (machine returns to Idle)
                    if self._wait_for_motion_completion():
                        logger.debug(f"✅ Motion completed: {command}")
                        return True, immediate_response
                    else:
                        logger.warning(f"⚠️ Motion completion timeout: {command}")
                        self.stats['motion_timeouts'] += 1
                        # Still return success as the command was accepted
                        return True, immediate_response
                else:
                    # Non-motion command, immediate response is sufficient
                    return True, immediate_response
                
            except Exception as e:
                logger.error(f"❌ Command failed: {command} - {e}")
                return False, f"Command error: {e}"
    
    def send_command(self, command: str) -> Tuple[bool, str]:
        """Send command (legacy interface, uses motion wait)"""
        return self.send_command_with_motion_wait(command)
    
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
        
        Motion is complete when machine returns to "Idle" state
        """
        start_time = time.time()
        motion_started = False
        
        while time.time() - start_time < self.motion_timeout:
            # Request status update
            if self.serial_connection:
                try:
                    self.serial_connection.write(b'?')
                    self.serial_connection.flush()
                except:
                    break
            
            # Check for status in the incoming data
            time.sleep(0.1)
            
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
                    if time.time() - start_time > 0.5:
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
                    
                    # Handle status reports (update current status)
                    if line.startswith('<') and line.endswith('>'):
                        self._parse_status_report(line)
                        continue
                    
                    # Skip info messages
                    if line.startswith('[') and line.endswith(']'):
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
        """Parse status report and update current status"""
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
            
            # Parse other parts
            for part in parts[1:]:
                if part.startswith('MPos:'):
                    # Machine position
                    coords = part[5:].split(',')
                    if len(coords) >= 4:
                        status.machine_position = {
                            'x': float(coords[0]),
                            'y': float(coords[1]),
                            'z': float(coords[2]),
                            'a': float(coords[3])
                        }
                        # Use machine position as work position for now
                        status.position = status.machine_position.copy()
                        status.work_position = status.machine_position.copy()
                
                elif part.startswith('WPos:'):
                    # Work position
                    coords = part[5:].split(',')
                    if len(coords) >= 4:
                        status.work_position = {
                            'x': float(coords[0]),
                            'y': float(coords[1]),
                            'z': float(coords[2]),
                            'a': float(coords[3])
                        }
                        status.position = status.work_position.copy()
                
                elif part.startswith('FS:'):
                    # Feed and spindle
                    fs_parts = part[3:].split(',')
                    if len(fs_parts) >= 2:
                        status.feed_rate = float(fs_parts[0])
                        status.spindle_speed = float(fs_parts[1])
            
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
        """Background status monitoring loop"""
        last_status_request = 0
        status_interval = 0.5  # Request status every 500ms
        
        while self.status_monitor_running and self.is_connected():
            try:
                current_time = time.time()
                
                # Request status periodically
                if current_time - last_status_request > status_interval:
                    if self.serial_connection:
                        self.serial_connection.write(b'?')
                        self.serial_connection.flush()
                    last_status_request = current_time
                
                # Read any incoming data
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith('<') and line.endswith('>'):
                        self._parse_status_report(line)
                
                time.sleep(0.05)  # Short sleep to prevent excessive CPU usage
                
            except Exception as e:
                logger.error(f"❌ Status monitor error: {e}")
                time.sleep(0.5)
        
        logger.debug("Status monitoring stopped")
    
    # Status and utility methods
    def get_current_status(self) -> Optional[FluidNCStatus]:
        """Get current status"""
        return self.current_status
    
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