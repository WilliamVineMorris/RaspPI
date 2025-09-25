#!/usr/bin/env python3
"""
Fixed FluidNC Protocol with Proper Homing Completion Detection

This is a clean implementation based on the successful test results.
It properly waits for the "MSG:DBG: Homing done" message before declaring success.

Author: Scanner System Development
Created: September 26, 2025
"""

import serial
import time
import threading
import logging
from typing import Tuple, Optional, Dict, Any
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
    timestamp: float = 0.0

class FixedFluidNCProtocol:
    """
    Fixed FluidNC protocol with proper homing completion detection.
    
    Key improvements:
    - Waits for "MSG:DBG: Homing done" message  
    - Verifies final status is "Idle"
    - Uses direct serial communication like successful tests
    - Proper timeout handling
    """
    
    def __init__(self, port: str, baud_rate: int = 115200, command_timeout: float = 10.0):
        self.port = port
        self.baud_rate = baud_rate
        self.command_timeout = command_timeout
        self.serial_connection: Optional[serial.Serial] = None
        self.connected = False
        self.current_status = FluidNCStatus()
        
        # Statistics
        self.stats = {
            'commands_sent': 0,
            'responses_received': 0,
            'connection_time': 0.0
        }
    
    def connect(self) -> bool:
        """Connect to FluidNC controller"""
        try:
            logger.info(f"🔌 Connecting to FluidNC at {self.port}")
            
            # Close existing connection
            if self.serial_connection:
                self.serial_connection.close()
            
            # Open new connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=2.0,
                write_timeout=1.0
            )
            
            # Allow connection to stabilize
            time.sleep(1.0)
            
            # Clear buffers
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # Test connection
            success, response = self._test_connection()
            if success:
                self.connected = True
                self.stats['connection_time'] = time.time()
                logger.info("✅ FluidNC connected successfully")
                return True
            else:
                logger.error(f"❌ Connection test failed: {response}")
                if self.serial_connection:
                    self.serial_connection.close()
                    self.serial_connection = None
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
            return False
    
    def disconnect(self) -> bool:
        """Disconnect from FluidNC"""
        try:
            if self.serial_connection:
                self.serial_connection.close()
                self.serial_connection = None
            self.connected = False
            logger.info("✅ FluidNC disconnected")
            return True
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to FluidNC"""
        return self.connected and self.serial_connection is not None
    
    def _test_connection(self) -> Tuple[bool, str]:
        """Test connection with status request"""
        try:
            return self.send_command("?")
        except Exception as e:
            return False, str(e)
    
    def send_command(self, command: str) -> Tuple[bool, str]:
        """Send command and get response"""
        if not self.is_connected() or self.serial_connection is None:
            return False, "Not connected"
        
        try:
            # Send command
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()
            self.stats['commands_sent'] += 1
            
            # Wait for response
            time.sleep(0.5)
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting).decode('utf-8', errors='ignore')
                self.stats['responses_received'] += 1
                
                # Parse status if it's a status response
                if command == "?" and response.strip():
                    self._parse_status_response(response)
                
                return True, response.strip()
            else:
                return True, "No response"
                
        except Exception as e:
            logger.error(f"❌ Command error: {e}")
            return False, str(e)
    
    def send_homing_command(self) -> Tuple[bool, str]:
        """
        Send homing command and wait for proper completion.
        
        Based on successful test results, this method:
        1. Sends $H command
        2. Monitors for debug messages  
        3. Waits for "MSG:DBG: Homing done"
        4. Verifies final status is "Idle"
        """
        if not self.is_connected() or self.serial_connection is None:
            return False, "Not connected"
        
        try:
            logger.info("🏠 Starting homing sequence...")
            
            # Clear alarm first
            logger.info("📤 Clearing alarm ($X)")
            success, response = self.send_command("$X")
            if success:
                logger.debug(f"🔓 Unlock response: {response}")
            
            # Send homing command
            logger.info("📤 Sending homing command ($H)")
            self.serial_connection.write(b"$H\n")
            self.serial_connection.flush()
            self.stats['commands_sent'] += 1
            
            # Monitor for completion
            start_time = time.time()
            homing_started = False
            homing_done = False
            timeout = 120.0  # 2 minutes
            
            logger.info("📊 Monitoring for homing completion...")
            
            while (time.time() - start_time) < timeout:
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.read(self.serial_connection.in_waiting).decode('utf-8', errors='ignore')
                    if data.strip():
                        elapsed = time.time() - start_time
                        
                        # Check each line for homing messages
                        for line in data.strip().split('\n'):
                            line = line.strip()
                            if not line:
                                continue
                            
                            # Check for homing start
                            if '[MSG:DBG: Homing' in line and 'Cycle' in line:
                                if not homing_started:
                                    logger.info(f"🏠 Homing sequence started: {line}")
                                    homing_started = True
                            
                            # Check for homing completion (case insensitive)
                            elif '[MSG:DBG: Homing' in line and 'done' in line.lower():
                                logger.info(f"✅ Homing completion detected: {line}")
                                homing_done = True
                                break
                            
                            # Log homed axis messages
                            elif 'MSG:Homed:' in line:
                                logger.info(f"✅ Axis homed: {line}")
                            
                            # Check for errors
                            elif 'ALARM' in line.upper():
                                logger.error(f"❌ Alarm during homing: {line}")
                                return False, f"Alarm during homing: {line}"
                            elif line.startswith('error:'):
                                logger.error(f"❌ Error during homing: {line}")
                                return False, f"Error during homing: {line}"
                        
                        # If homing is done, break the loop
                        if homing_done:
                            break
                
                time.sleep(0.1)  # Check every 100ms
            
            # Verify completion
            if homing_done:
                logger.info("⏳ Homing done detected, verifying final status...")
                time.sleep(1.0)  # Allow time for final status update
                
                # Check final status
                success, status_response = self.send_command("?")
                if success:
                    logger.info(f"📊 Final status: {status_response}")
                    
                    if 'Idle' in status_response:
                        logger.info("✅ Homing completed successfully - status is Idle!")
                        return True, "Homing completed successfully"
                    elif 'Alarm' in status_response:
                        logger.error("❌ Homing failed - final status is Alarm!")
                        return False, "Final status is Alarm"
                    else:
                        logger.warning(f"⚠️ Unexpected final status: {status_response}")
                        return False, f"Unexpected final status: {status_response}"
                else:
                    logger.error("❌ Could not verify final status")
                    return False, "Could not verify final status"
            else:
                # Timeout or never started
                if homing_started:
                    logger.error("❌ Homing started but never completed (timeout)")
                    return False, "Homing timeout after starting"
                else:  
                    logger.error("❌ Homing never started (no debug messages received)")
                    return False, "Homing never started"
                    
        except Exception as e:
            logger.error(f"❌ Homing error: {e}")
            return False, str(e)
    
    def _parse_status_response(self, response: str):
        """Parse FluidNC status response"""
        try:
            # Look for status report format: <State|MPos:x,y,z|...>
            for line in response.split('\n'):
                line = line.strip()
                if line.startswith('<') and line.endswith('>'):
                    # Parse status report
                    content = line[1:-1]  # Remove < >
                    parts = content.split('|')
                    
                    if parts:
                        # First part is state
                        self.current_status.state = parts[0]
                        self.current_status.timestamp = time.time()
                        
                        # Parse position if available
                        for part in parts:
                            if part.startswith('MPos:'):
                                pos_str = part[5:]  # Remove 'MPos:'
                                pos_values = pos_str.split(',')
                                if len(pos_values) >= 3:
                                    self.current_status.position = {
                                        'x': float(pos_values[0]),
                                        'y': float(pos_values[1]),
                                        'z': float(pos_values[2]),
                                        'c': float(pos_values[3]) if len(pos_values) > 3 else 0.0
                                    }
                        
                        logger.debug(f"📊 Status: {self.current_status.state}")
                        break
                        
        except Exception as e:
            logger.debug(f"Status parse error: {e}")
    
    def get_status(self) -> FluidNCStatus:
        """Get current status"""
        return self.current_status
    
    def get_stats(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        return self.stats.copy()