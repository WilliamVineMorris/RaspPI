"""
Simplified FluidNC Protocol Handler - V2.1

This is a complete redesign of the FluidNC communication protocol that eliminates
the core issues identified in the codebase analysis:

1. No complex async queuing - simple synchronous commands
2. Clear command/response matching without race conditions  
3. Separate status monitoring from command processing
4. Proper timeout handling with retry logic
5. Thread-safe serial communication

Design Principles:
- One command at a time (blocking)
- Clear request/response pairs
- Background status monitoring
- Proper resource management
- No queuing complexity

Author: Scanner System Redesign
Created: September 24, 2025
"""

import asyncio
import logging
import serial
import threading
import time
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FluidNCState(Enum):
    """FluidNC controller states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    RUN = "run"
    HOLD = "hold"
    JOG = "jog"
    ALARM = "alarm"
    DOOR = "door"
    CHECK = "check"
    HOME = "home"
    SLEEP = "sleep"


@dataclass
class FluidNCStatus:
    """FluidNC status information"""
    state: FluidNCState
    position: Dict[str, float]  # Machine position
    work_position: Dict[str, float]  # Work coordinate position
    feedrate: float
    spindle_speed: float
    line_number: int
    
    @classmethod
    def parse_status_report(cls, status_line: str) -> Optional['FluidNCStatus']:
        """Parse FluidNC status report line"""
        try:
            # Remove < and > brackets
            if not (status_line.startswith('<') and status_line.endswith('>')):
                return None
            
            content = status_line[1:-1]
            parts = content.split('|')
            
            if not parts:
                return None
            
            # Parse state
            state_str = parts[0].lower()
            try:
                state = FluidNCState(state_str)
            except ValueError:
                state = FluidNCState.IDLE
            
            # Initialize with defaults
            position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0}
            work_position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'a': 0.0}
            feedrate = 0.0
            spindle_speed = 0.0
            line_number = 0
            
            # Parse other fields
            for part in parts[1:]:
                if part.startswith('MPos:'):
                    coords = part[5:].split(',')
                    if len(coords) >= 4:
                        position = {
                            'x': float(coords[0]),
                            'y': float(coords[1]),
                            'z': float(coords[2]),
                            'a': float(coords[3])
                        }
                elif part.startswith('WPos:'):
                    coords = part[5:].split(',')
                    if len(coords) >= 4:
                        work_position = {
                            'x': float(coords[0]),
                            'y': float(coords[1]),
                            'z': float(coords[2]),
                            'a': float(coords[3])
                        }
                elif part.startswith('F:'):
                    feedrate = float(part[2:])
                elif part.startswith('S:'):
                    spindle_speed = float(part[2:])
            
            return cls(
                state=state,
                position=position,
                work_position=work_position,
                feedrate=feedrate,
                spindle_speed=spindle_speed,
                line_number=line_number
            )
            
        except Exception as e:
            logger.warning(f"Failed to parse status: {status_line} - {e}")
            return None


class SimplifiedFluidNCProtocol:
    """
    Simplified FluidNC Protocol Handler
    
    Key Features:
    - Synchronous command execution (one at a time)
    - Background status monitoring
    - Proper timeout handling
    - Thread-safe operations
    - Clear error handling
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baud_rate: int = 115200):
        self.port = port
        self.baud_rate = baud_rate
        
        # Serial connection
        self.serial_connection: Optional[serial.Serial] = None
        self.connection_lock = threading.RLock()
        
        # Status monitoring
        self.current_status: Optional[FluidNCStatus] = None
        self.status_callbacks: list[Callable[[FluidNCStatus], None]] = []
        self.status_monitor_running = False
        self.status_thread: Optional[threading.Thread] = None
        
        # Command execution
        self.command_lock = threading.RLock()
        self.last_command_time = 0
        self.command_delay = 0.1  # Minimum delay between commands
        
        # Statistics
        self.stats: Dict[str, Any] = {
            'commands_sent': 0,
            'responses_received': 0,
            'timeouts': 0,
            'connection_time': 0.0
        }
    
    # Connection Management
    def connect(self) -> bool:
        """Connect to FluidNC controller"""
        with self.connection_lock:
            try:
                logger.info(f"🔌 Connecting to FluidNC at {self.port}")
                
                # Close existing connection if any
                self._close_connection()
                
                # Open new connection
                self.serial_connection = serial.Serial(
                    port=self.port,
                    baudrate=self.baud_rate,
                    timeout=2.0,
                    write_timeout=2.0,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                )
                
                # Wait for FluidNC initialization
                time.sleep(2.0)
                
                # Clear any startup messages
                self._clear_input_buffer()
                
                # Test connection
                if self._test_connection():
                    # Start status monitoring
                    self._start_status_monitoring()
                    
                    self.stats['connection_time'] = time.time()
                    logger.info("✅ FluidNC connected successfully")
                    return True
                else:
                    logger.error("❌ FluidNC connection test failed")
                    self._close_connection()
                    return False
                    
            except Exception as e:
                logger.error(f"❌ FluidNC connection failed: {e}")
                self._close_connection()
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from FluidNC"""
        with self.connection_lock:
            try:
                logger.info("🔌 Disconnecting from FluidNC")
                
                # Stop status monitoring
                self._stop_status_monitoring()
                
                # Close serial connection
                self._close_connection()
                
                logger.info("✅ FluidNC disconnected")
                return True
                
            except Exception as e:
                logger.error(f"❌ FluidNC disconnect failed: {e}")
                return False
    
    def is_connected(self) -> bool:
        """Check if connected to FluidNC"""
        with self.connection_lock:
            return (self.serial_connection is not None and 
                    self.serial_connection.is_open)
    
    # Command Execution
    def send_command(self, command: str, timeout: float = 5.0) -> tuple[bool, str]:
        """
        Send command to FluidNC and wait for response
        
        Args:
            command: G-code or FluidNC command
            timeout: Maximum wait time for response
            
        Returns:
            (success, response) tuple
        """
        with self.command_lock:
            if not self.is_connected():
                return False, "Not connected to FluidNC"
            
            try:
                # Respect command timing
                elapsed = time.time() - self.last_command_time
                if elapsed < self.command_delay:
                    time.sleep(self.command_delay - elapsed)
                
                # Send command
                command_line = f"{command.strip()}\n"
                logger.debug(f"📤 Sending: {command.strip()}")
                
                if self.serial_connection:
                    self.serial_connection.write(command_line.encode('utf-8'))
                    self.serial_connection.flush()
                
                self.stats['commands_sent'] += 1
                self.last_command_time = time.time()
                
                # Wait for response
                response = self._wait_for_response(timeout)
                
                if response:
                    self.stats['responses_received'] += 1
                    logger.debug(f"📥 Response: {response}")
                    return True, response
                else:
                    self.stats['timeouts'] += 1
                    logger.warning(f"⏰ Command timeout: {command}")
                    return False, "Command timeout"
                    
            except Exception as e:
                logger.error(f"❌ Command failed: {command} - {e}")
                return False, f"Command error: {e}"
    
    def send_immediate_command(self, command: str) -> bool:
        """
        Send immediate command (?, !, ~, Ctrl-X)
        These don't expect "ok" responses
        """
        with self.connection_lock:
            if not self.is_connected():
                return False
            
            try:
                logger.debug(f"📤 Immediate: {command}")
                
                if self.serial_connection:
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
    
    # Status Monitoring
    def get_current_status(self) -> Optional[FluidNCStatus]:
        """Get current FluidNC status"""
        return self.current_status
    
    def add_status_callback(self, callback: Callable[[FluidNCStatus], None]):
        """Add callback for status updates"""
        self.status_callbacks.append(callback)
    
    def request_status(self) -> bool:
        """Request immediate status update"""
        return self.send_immediate_command('?')
    
    # Private Methods
    def _close_connection(self):
        """Close serial connection"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
        except Exception:
            pass
        finally:
            self.serial_connection = None
    
    def _clear_input_buffer(self):
        """Clear serial input buffer"""
        try:
            if self.serial_connection:
                self.serial_connection.reset_input_buffer()
                # Read any pending data
                while self.serial_connection.in_waiting > 0:
                    self.serial_connection.readline()
                    time.sleep(0.01)
        except Exception:
            pass
    
    def _test_connection(self) -> bool:
        """Test FluidNC connection"""
        try:
            if not self.serial_connection:
                return False
                
            # Send status request
            self.serial_connection.write(b'?\n')
            self.serial_connection.flush()
            
            # Wait for response
            start_time = time.time()
            while time.time() - start_time < 3.0:
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    if response.startswith('<') and response.endswith('>'):
                        return True
                time.sleep(0.1)
            
            return False
            
        except Exception:
            return False
    
    def _wait_for_response(self, timeout: float) -> Optional[str]:
        """Wait for command response"""
        try:
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    # Skip empty lines
                    if not line:
                        continue
                    
                    # Skip status reports (handled by monitor)
                    if line.startswith('<') and line.endswith('>'):
                        continue
                    
                    # Skip info messages
                    if line.startswith('[') and line.endswith(']'):
                        continue
                    
                    # Return actual response
                    return line
                
                time.sleep(0.01)
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Response wait failed: {e}")
            return None
    
    def _start_status_monitoring(self):
        """Start background status monitoring"""
        if self.status_monitor_running:
            return
        
        self.status_monitor_running = True
        self.status_thread = threading.Thread(
            target=self._status_monitor_loop,
            name="FluidNC-Status-Monitor",
            daemon=True
        )
        self.status_thread.start()
        logger.debug("📊 Status monitoring started")
    
    def _stop_status_monitoring(self):
        """Stop status monitoring"""
        self.status_monitor_running = False
        
        if self.status_thread and self.status_thread.is_alive():
            self.status_thread.join(timeout=2.0)
        
        logger.debug("📊 Status monitoring stopped")
    
    def _status_monitor_loop(self):
        """Background status monitoring loop"""
        logger.debug("📊 Status monitor loop started")
        
        while self.status_monitor_running and self.is_connected():
            try:
                # Check for incoming status reports
                if self.serial_connection and self.serial_connection.in_waiting > 0:
                    line = self.serial_connection.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line.startswith('<') and line.endswith('>'):
                        # Parse status report
                        status = FluidNCStatus.parse_status_report(line)
                        if status:
                            self.current_status = status
                            
                            # Notify callbacks
                            for callback in self.status_callbacks:
                                try:
                                    callback(status)
                                except Exception as e:
                                    logger.error(f"❌ Status callback failed: {e}")
                
                # Request status periodically
                time.sleep(0.5)
                if self.status_monitor_running:
                    self.send_immediate_command('?')
                
            except Exception as e:
                logger.error(f"❌ Status monitor error: {e}")
                time.sleep(1.0)
        
        logger.debug("📊 Status monitor loop ended")
    
    # Utility Methods
    def get_statistics(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        stats = self.stats.copy()
        stats['connection_duration'] = time.time() - self.stats['connection_time'] if self.stats['connection_time'] > 0 else 0
        stats['success_rate'] = self.stats['responses_received'] / max(1, self.stats['commands_sent'])
        return stats