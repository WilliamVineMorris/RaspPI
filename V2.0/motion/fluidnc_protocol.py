"""
FluidNC Protocol-Compliant Communication System

This module implements a robust communication system that properly handles
FluidNC's real-time reporting protocol, separating immediate commands from
line-based commands and managing auto-reports correctly.

Key Protocol Features:
- Immediate characters (?, !, ~, Ctrl-X) processed instantly
- Line-based commands wait for "ok" responses  
- Auto-reporting provides real-time status without polling
- Proper message type separation and handling

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import time
import re
import enum
from typing import Optional, Dict, Any, List, Callable, Union
from dataclasses import dataclass
import serial

from motion.base import Position4D, MotionStatus
from core.exceptions import FluidNCError, FluidNCConnectionError, FluidNCCommandError


logger = logging.getLogger(__name__)


class MessageType(enum.Enum):
    """FluidNC message types"""
    STATUS_REPORT = "status"          # <Idle|MPos:...>
    COMMAND_RESPONSE = "response"     # ok, error:N
    ALARM = "alarm"                   # ALARM:N
    INFO = "info"                     # [MSG:INFO:...]
    JSON = "json"                     # [JSON:{...}]
    UNKNOWN = "unknown"


@dataclass
class FluidNCMessage:
    """Structured FluidNC message"""
    type: MessageType
    raw: str
    timestamp: float
    data: Optional[Dict[str, Any]] = None


class FluidNCProtocol:
    """
    FluidNC Protocol Handler
    
    Implements proper FluidNC communication protocol with:
    - Immediate character handling (?, !, ~, Ctrl-X)
    - Line-based command processing with ok/error responses
    - Auto-report processing and status parsing
    - Message type separation and routing
    """
    
    def __init__(self, serial_connection: serial.Serial):
        self.serial = serial_connection
        self.running = False
        
        # Message processing
        self.message_handlers: Dict[MessageType, List[Callable]] = {
            MessageType.STATUS_REPORT: [],
            MessageType.COMMAND_RESPONSE: [],
            MessageType.ALARM: [],
            MessageType.INFO: [],
            MessageType.JSON: [],
            MessageType.UNKNOWN: []
        }
        
        # Command tracking
        self.pending_commands: Dict[str, asyncio.Future] = {}
        self.command_sequence = 0
        
        # Protocol state
        self.last_status = None
        self.auto_reporting_enabled = True
        
        # Statistics
        self.stats = {
            'messages_processed': 0,
            'commands_sent': 0,
            'status_reports': 0,
            'errors': 0,
            'start_time': time.time()
        }
    
    async def start(self):
        """Start the protocol handler"""
        if self.running:
            return
            
        self.running = True
        self.reader_task = asyncio.create_task(self._message_reader())
        logger.info("🚀 FluidNC Protocol handler started")
    
    async def stop(self):
        """Stop the protocol handler"""
        if not self.running:
            return
            
        self.running = False
        
        # Cancel pending commands
        for future in self.pending_commands.values():
            if not future.done():
                future.cancel()
        
        # Stop reader
        if hasattr(self, 'reader_task'):
            self.reader_task.cancel()
            try:
                await self.reader_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 FluidNC Protocol handler stopped")
    
    def add_message_handler(self, message_type: MessageType, handler: Callable):
        """Add a handler for specific message types"""
        self.message_handlers[message_type].append(handler)
    
    def remove_message_handler(self, message_type: MessageType, handler: Callable):
        """Remove a message handler"""
        if handler in self.message_handlers[message_type]:
            self.message_handlers[message_type].remove(handler)
    
    async def send_immediate_command(self, command: str) -> None:
        """
        Send immediate command (single character like ?, !, ~, Ctrl-X)
        These don't wait for responses and are processed immediately
        """
        if not self.serial or not self.serial.is_open:
            raise FluidNCConnectionError("Serial connection not available")
        
        # Immediate commands are single characters
        if len(command) != 1:
            raise FluidNCCommandError(f"Immediate commands must be single characters, got: {command}")
        
        try:
            self.serial.write(command.encode('utf-8'))
            self.serial.flush()
            logger.debug(f"📤 Immediate: {repr(command)}")
            self.stats['commands_sent'] += 1
        except Exception as e:
            logger.error(f"Failed to send immediate command '{command}': {e}")
            raise FluidNCConnectionError(f"Immediate command failed: {e}")
    
    async def send_line_command(self, command: str, timeout: float = 10.0) -> str:
        """
        Send line-based command and wait for ok/error response
        These are queued and processed sequentially by FluidNC
        """
        if not self.serial or not self.serial.is_open:
            raise FluidNCConnectionError("Serial connection not available")
        
        # Generate unique command ID for tracking
        self.command_sequence += 1
        cmd_id = f"cmd_{self.command_sequence}"
        
        # Create future for response
        response_future = asyncio.Future()
        self.pending_commands[cmd_id] = response_future
        
        try:
            # Send command with proper line termination
            command_line = command.strip() + '\n'
            self.serial.write(command_line.encode('utf-8'))
            self.serial.flush()
            
            logger.debug(f"📤 Command[{cmd_id}]: {command.strip()}")
            self.stats['commands_sent'] += 1
            
            # Wait for response with longer timeout
            try:
                response = await asyncio.wait_for(response_future, timeout)
                logger.debug(f"📥 Response[{cmd_id}]: {response}")
                return response
            except asyncio.TimeoutError:
                logger.error(f"⏰ Command timeout[{cmd_id}]: {command}")
                # Don't raise immediately - maybe FluidNC is busy
                # Try waiting a bit more for delayed response
                try:
                    response = await asyncio.wait_for(response_future, 2.0)
                    logger.warning(f"📥 Delayed response[{cmd_id}]: {response}")
                    return response
                except asyncio.TimeoutError:
                    logger.error(f"❌ Final timeout[{cmd_id}]: {command}")
                    raise FluidNCCommandError(f"Command timeout: {command}")
        
        except Exception as e:
            if not isinstance(e, FluidNCCommandError):
                logger.error(f"Failed to send line command '{command}': {e}")
            raise
        finally:
            # Clean up command tracking
            self.pending_commands.pop(cmd_id, None)
    
    async def get_status(self) -> Optional[Dict[str, Any]]:
        """Get current status using immediate ? command"""
        # Send immediate status request
        await self.send_immediate_command('?')
        
        # The status report will be handled by message reader and stored
        # Return the most recent status
        return self.last_status
    
    async def _message_reader(self):
        """
        Core message reader - processes all incoming FluidNC messages
        Separates immediate responses from line-based responses
        """
        logger.info("📡 FluidNC message reader started")
        
        message_buffer = ""
        
        try:
            while self.running:
                try:
                    # Read available data with timeout
                    if self.serial.in_waiting > 0:
                        # Read all available data
                        data = self.serial.read(self.serial.in_waiting)
                        if data:
                            message_buffer += data.decode('utf-8', errors='replace')
                    
                    # Process complete messages
                    while '\n' in message_buffer or '\r' in message_buffer:
                        # Find line ending
                        line_end = min([i for i in [message_buffer.find('\n'), message_buffer.find('\r')] if i >= 0])
                        
                        # Extract message
                        raw_message = message_buffer[:line_end].strip()
                        message_buffer = message_buffer[line_end + 1:]
                        
                        if raw_message:
                            logger.debug(f"📨 Raw message: {repr(raw_message)}")
                            await self._process_message(raw_message)
                    
                    # Small delay to prevent busy waiting
                    await asyncio.sleep(0.01)  # 10ms for good responsiveness
                
                except Exception as e:
                    logger.error(f"Message reader error: {e}")
                    await asyncio.sleep(0.1)  # Back off on errors
        
        except asyncio.CancelledError:
            logger.info("Message reader cancelled")
            raise
        except Exception as e:
            logger.error(f"Message reader fatal error: {e}")
        finally:
            logger.info("📡 FluidNC message reader stopped")
    
    async def _process_message(self, raw_message: str):
        """Process a complete message from FluidNC"""
        message = self._parse_message(raw_message)
        
        if message:
            self.stats['messages_processed'] += 1
            
            # Handle different message types
            if message.type == MessageType.STATUS_REPORT:
                await self._handle_status_report(message)
            elif message.type == MessageType.COMMAND_RESPONSE:
                await self._handle_command_response(message)
            elif message.type == MessageType.ALARM:
                await self._handle_alarm(message)
            
            # Call registered handlers
            for handler in self.message_handlers[message.type]:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Message handler error: {e}")
    
    def _parse_message(self, raw_message: str) -> Optional[FluidNCMessage]:
        """Parse raw message into structured FluidNCMessage"""
        raw = raw_message.strip()
        if not raw:
            return None
        
        message = FluidNCMessage(
            type=MessageType.UNKNOWN,
            raw=raw,
            timestamp=time.time()
        )
        
        # Status reports: <State|Data|...>
        if raw.startswith('<') and raw.endswith('>'):
            message.type = MessageType.STATUS_REPORT
            message.data = self._parse_status_report(raw)
        
        # Command responses: ok, error:N
        elif raw in ['ok', 'OK']:
            message.type = MessageType.COMMAND_RESPONSE
            message.data = {'status': 'ok'}
            logger.debug(f"📋 Parsed OK response: {raw}")
        elif raw.startswith('error:') or raw == 'error':
            message.type = MessageType.COMMAND_RESPONSE
            error_match = re.match(r'error:(\d+)', raw)
            error_code = int(error_match.group(1)) if error_match else 0
            message.data = {'status': 'error', 'code': error_code}
            logger.debug(f"📋 Parsed ERROR response: {raw} -> code: {error_code}")
        
        # Alarm messages: ALARM:N
        elif raw.startswith('ALARM:'):
            message.type = MessageType.ALARM
            alarm_match = re.match(r'ALARM:(\d+)', raw)
            alarm_code = int(alarm_match.group(1)) if alarm_match else 0
            message.data = {'code': alarm_code}
        
        # Info messages: [MSG:INFO:...]
        elif raw.startswith('[MSG:'):
            message.type = MessageType.INFO
            message.data = {'content': raw}
        
        # JSON messages: [JSON:{...}]
        elif raw.startswith('[JSON:'):
            message.type = MessageType.JSON
            # Extract JSON content
            json_match = re.match(r'\[JSON:(.+)\]', raw)
            if json_match:
                import json
                try:
                    message.data = json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    message.data = {'raw_json': json_match.group(1)}
        
        return message
    
    def _parse_status_report(self, status_line: str) -> Dict[str, Any]:
        """Parse FluidNC status report into structured data"""
        # Remove angle brackets
        content = status_line[1:-1]
        sections = content.split('|')
        
        parsed = {}
        
        for section in sections:
            if ':' in section:
                key, value = section.split(':', 1)
                
                if key == 'MPos' or key == 'WPos':
                    # Parse position
                    coords = [float(x) for x in value.split(',')]
                    parsed[key.lower()] = {
                        'x': coords[0] if len(coords) > 0 else 0,
                        'y': coords[1] if len(coords) > 1 else 0,
                        'z': coords[2] if len(coords) > 2 else 0,
                        'c': coords[3] if len(coords) > 3 else 0
                    }
                elif key == 'FS':
                    # Feed and spindle
                    values = value.split(',')
                    parsed['feed'] = int(values[0]) if len(values) > 0 else 0
                    parsed['spindle'] = int(values[1]) if len(values) > 1 else 0
                elif key == 'Bf':
                    # Buffer status
                    values = value.split(',')
                    parsed['buffer'] = {
                        'planner': int(values[0]) if len(values) > 0 else 0,
                        'serial': int(values[1]) if len(values) > 1 else 0
                    }
                elif key == 'WCO':
                    # Work coordinate offset
                    coords = [float(x) for x in value.split(',')]
                    parsed['wco'] = {
                        'x': coords[0] if len(coords) > 0 else 0,
                        'y': coords[1] if len(coords) > 1 else 0,
                        'z': coords[2] if len(coords) > 2 else 0,
                        'c': coords[3] if len(coords) > 3 else 0
                    }
                else:
                    parsed[key.lower()] = value
            else:
                # State information (first section usually)
                parsed['state'] = section.lower()
        
        return parsed
    
    async def _handle_status_report(self, message: FluidNCMessage):
        """Handle status report messages"""
        self.stats['status_reports'] += 1
        self.last_status = message.data
        if message.data:
            logger.debug(f"📊 Status: {message.data.get('state', 'unknown')}")
    
    async def _handle_command_response(self, message: FluidNCMessage):
        """Handle command response (ok/error)"""
        # Find oldest pending command and resolve it
        if not self.pending_commands or not message.data:
            logger.debug("📥 Response received but no pending commands")
            return
        
        # Get oldest command (FIFO)
        cmd_id = next(iter(self.pending_commands))
        future = self.pending_commands.get(cmd_id)
        
        if future and not future.done():
            try:
                if message.data.get('status') == 'ok':
                    future.set_result('ok')
                    logger.debug(f"✅ Command completed[{cmd_id}]: ok")
                else:
                    error_msg = f"error:{message.data.get('code', 'unknown')}"
                    future.set_result(error_msg)
                    logger.debug(f"❌ Command failed[{cmd_id}]: {error_msg}")
                
                # Remove from pending only after successfully setting result
                self.pending_commands.pop(cmd_id, None)
                
            except Exception as e:
                logger.error(f"Error handling command response: {e}")
                # Ensure command is removed even if there's an error
                self.pending_commands.pop(cmd_id, None)
        else:
            logger.debug(f"📥 Response for completed/missing command[{cmd_id}]")
    
    async def _handle_alarm(self, message: FluidNCMessage):
        """Handle alarm messages"""
        if message.data:
            logger.warning(f"🚨 ALARM: {message.data.get('code', 'unknown')}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get protocol statistics"""
        runtime = time.time() - self.stats['start_time']
        return {
            **self.stats,
            'runtime_seconds': runtime,
            'messages_per_second': self.stats['messages_processed'] / max(runtime, 1),
            'pending_commands': len(self.pending_commands)
        }


class FluidNCCommunicator:
    """
    High-level FluidNC communication interface
    
    Provides motion control methods using the protocol handler
    """
    
    def __init__(self, serial_connection: serial.Serial):
        self.protocol = FluidNCProtocol(serial_connection)
        self.current_position = Position4D()
        self.current_status = MotionStatus.DISCONNECTED
        
        # Register for status updates
        self.protocol.add_message_handler(MessageType.STATUS_REPORT, self._on_status_update)
        self.protocol.add_message_handler(MessageType.ALARM, self._on_alarm)
    
    async def start(self):
        """Start the communicator"""
        await self.protocol.start()
        
        # Enable auto-reporting for real-time updates
        try:
            await self.protocol.send_line_command('$10=3')  # Machine pos, work pos, buffer status
            logger.info("✅ FluidNC auto-reporting enabled")
        except Exception as e:
            logger.warning(f"Could not enable auto-reporting: {e}")
    
    async def stop(self):
        """Stop the communicator"""
        await self.protocol.stop()
    
    async def _on_status_update(self, message: FluidNCMessage):
        """Handle status updates"""
        data = message.data
        if not data:
            return
        
        # Update position
        if 'mpos' in data:
            pos_data = data['mpos']
            self.current_position = Position4D(
                x=pos_data.get('x', 0),
                y=pos_data.get('y', 0),
                z=pos_data.get('z', 0),
                c=pos_data.get('c', 0)
            )
        
        # Update status
        state = data.get('state', '').lower()
        if state == 'idle':
            self.current_status = MotionStatus.IDLE
        elif state in ['run', 'jog']:
            self.current_status = MotionStatus.MOVING
        elif state == 'alarm':
            self.current_status = MotionStatus.ALARM
        elif state == 'home':
            self.current_status = MotionStatus.HOMING
    
    async def _on_alarm(self, message: FluidNCMessage):
        """Handle alarm messages"""
        self.current_status = MotionStatus.ALARM
        if message.data:
            logger.error(f"FluidNC ALARM: {message.data.get('code', 'unknown')}")
    
    async def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        # Trigger status update
        await self.protocol.get_status()
        
        return {
            'status': self.current_status,
            'position': self.current_position,
            'connected': self.protocol.running
        }
    
    async def send_gcode(self, gcode: str) -> bool:
        """Send G-code command"""
        try:
            response = await self.protocol.send_line_command(gcode)
            return response == 'ok'
        except Exception as e:
            logger.error(f"G-code command failed: {e}")
            return False
    
    async def emergency_stop(self):
        """Send emergency stop (immediate)"""
        await self.protocol.send_immediate_command('!')  # Feed hold
        await asyncio.sleep(0.1)
        await self.protocol.send_immediate_command('\x18')  # Reset
    
    async def resume(self):
        """Resume from hold (immediate)"""
        await self.protocol.send_immediate_command('~')
    
    async def home_all(self) -> bool:
        """Home all axes"""
        try:
            response = await self.protocol.send_line_command('$H', timeout=30.0)
            return response == 'ok'
        except Exception as e:
            logger.error(f"Homing failed: {e}")
            return False
    
    async def move_to_position(self, position: Position4D, feedrate: float = 100.0) -> bool:
        """Move to absolute position"""
        gcode = f"G1 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f} F{feedrate}"
        return await self.send_gcode(gcode)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get communication statistics"""
        return self.protocol.get_stats()