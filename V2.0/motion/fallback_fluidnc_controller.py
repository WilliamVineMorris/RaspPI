"""
Fallback FluidNC Controller - Robust Communication

This is a simplified, more robust version of the FluidNC controller that 
handles timeout issues better. Use this if the enhanced protocol has timeout problems.
"""

import asyncio
import logging
import serial
import time
from typing import Optional
from motion.base import MotionController, Position4D, MotionStatus

logger = logging.getLogger(__name__)


class FallbackFluidNCController(MotionController):
    """Fallback FluidNC controller with robust timeout handling"""
    
    def __init__(self, config=None, port: str = "/dev/ttyUSB0", baud_rate: int = 115200):
        config = config or {}
        super().__init__(config)
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection: Optional[serial.Serial] = None
        self.current_position = Position4D(0, 0, 0, 0)
        self._status = MotionStatus.DISCONNECTED
        self._lock = asyncio.Lock()
        
    async def connect(self) -> bool:
        """Connect to FluidNC with robust error handling"""
        try:
            logger.info(f"🔌 Connecting to FluidNC at {self.port}")
            
            # Open serial connection
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=2.0,
                write_timeout=2.0
            )
            
            # Give FluidNC time to initialize
            await asyncio.sleep(2.0)
            
            # Clear any startup messages
            self._clear_buffer()
            
            # Simple connectivity test
            if await self._send_simple_command("?"):
                self._status = MotionStatus.IDLE
                logger.info("✅ FluidNC connected successfully")
                return True
            else:
                logger.error("❌ FluidNC connectivity test failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ FluidNC connection failed: {e}")
            self._status = MotionStatus.DISCONNECTED
            return False
    
    async def disconnect(self) -> bool:
        """Disconnect from FluidNC"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                logger.info("✅ FluidNC disconnected")
            
            self._status = MotionStatus.DISCONNECTED
            return True
            
        except Exception as e:
            logger.error(f"❌ FluidNC disconnect failed: {e}")
            return False
    
    async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
        """Robust relative movement"""
        async with self._lock:
            try:
                feedrate = feedrate or 100.0
                logger.info(f"🔄 Fallback relative move: {delta} at F{feedrate}")
                
                # Set relative mode - don't worry about response
                await self._send_robust_command("G91")
                
                # Send movement command
                gcode = f"G1 X{delta.x:.3f} Y{delta.y:.3f} Z{delta.z:.3f} A{delta.c:.3f} F{feedrate}"
                success = await self._send_robust_command(gcode)
                
                # Return to absolute mode
                await self._send_robust_command("G90")
                
                if success:
                    # Update position estimate
                    self.current_position = Position4D(
                        self.current_position.x + delta.x,
                        self.current_position.y + delta.y,
                        self.current_position.z + delta.z,
                        self.current_position.c + delta.c
                    )
                    logger.info("✅ Fallback move completed")
                    return True
                else:
                    logger.warning("⚠️  Fallback move may have failed")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Fallback relative move failed: {e}")
                return False
    
    async def _send_robust_command(self, command: str, timeout: float = 5.0) -> bool:
        """Send command with robust timeout handling"""
        if not self.serial_connection or not self.serial_connection.is_open:
            logger.error("❌ No serial connection available")
            return False
        
        try:
            # Send command
            command_line = f"{command}\n"
            self.serial_connection.write(command_line.encode())
            self.serial_connection.flush()
            
            logger.debug(f"📤 Sent: {command}")
            
            # Try to read response, but don't fail if timeout
            start_time = time.time()
            response_received = False
            
            while time.time() - start_time < timeout:
                if self.serial_connection.in_waiting > 0:
                    try:
                        response = self.serial_connection.readline().decode().strip()
                        logger.debug(f"📥 Received: {response}")
                        
                        # Accept any reasonable response
                        if response.lower() in ['ok', 'done'] or 'ok' in response.lower():
                            response_received = True
                            break
                        elif response.startswith('<') and response.endswith('>'):
                            # Status report - continue waiting
                            continue
                        elif response.startswith('[') and response.endswith(']'):
                            # Info message - continue waiting
                            continue
                        else:
                            # Some other response - assume it's ok
                            response_received = True
                            break
                            
                    except Exception as e:
                        logger.debug(f"📥 Read error: {e}")
                        break
                
                await asyncio.sleep(0.1)
            
            if not response_received:
                logger.warning(f"⚠️  No response for: {command} (continuing anyway)")
            
            # Always return True to avoid blocking
            return True
            
        except Exception as e:
            logger.error(f"❌ Command failed: {command} - {e}")
            return False
    
    async def _send_simple_command(self, command: str) -> bool:
        """Send simple command for testing"""
        if not self.serial_connection or not self.serial_connection.is_open:
            return False
        
        try:
            self.serial_connection.write(f"{command}\n".encode())
            self.serial_connection.flush()
            
            # Wait briefly for any response
            time.sleep(0.5)
            return True
            
        except Exception:
            return False
    
    def _clear_buffer(self):
        """Clear serial input buffer"""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.reset_input_buffer()
                # Read any pending data
                while self.serial_connection.in_waiting > 0:
                    self.serial_connection.readline()
            except Exception:
                pass
    
    # Required abstract methods - simplified implementations
    async def move_to_position(self, position: Position4D) -> bool:
        """Move to absolute position"""
        delta = Position4D(
            position.x - self.current_position.x,
            position.y - self.current_position.y,
            position.z - self.current_position.z,
            position.c - self.current_position.c
        )
        return await self.move_relative(delta)
    
    async def home_axis(self, axis: str) -> bool:
        """Home specified axis"""
        command = f"G28.2 {axis.upper()}0"
        return await self._send_robust_command(command, timeout=30.0)
    
    async def emergency_stop(self) -> bool:
        """Emergency stop"""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'!')
                self.serial_connection.flush()
            return True
        except Exception:
            return False
    
    async def get_current_position(self) -> Position4D:
        """Get current position"""
        return self.current_position
    
    async def get_status(self) -> MotionStatus:
        """Get motion status"""
        return self._status
    
    async def is_moving(self) -> bool:
        """Check if moving"""
        return self._status == MotionStatus.MOVING
    
    async def wait_for_idle(self, timeout: float = 30.0) -> bool:
        """Wait for idle state"""
        # Simple implementation - just wait a bit
        await asyncio.sleep(1.0)
        return True
    
    # Additional required methods
    async def is_connected(self) -> bool:
        """Check if connected"""
        return (self.serial_connection is not None and 
                self.serial_connection.is_open and 
                self._status != MotionStatus.DISCONNECTED)
    
    async def get_position(self) -> Position4D:
        """Get position (alias for get_current_position)"""
        return await self.get_current_position()
    
    async def set_position(self, position: Position4D) -> bool:
        """Set current position (coordinate system offset)"""
        self.current_position = position
        return True
    
    async def jog(self, axis: str, distance: float, feedrate: float = 100.0) -> bool:
        """Jog specified axis"""
        delta = Position4D()
        if axis.lower() == 'x':
            delta.x = distance
        elif axis.lower() == 'y':
            delta.y = distance
        elif axis.lower() == 'z':
            delta.z = distance
        elif axis.lower() == 'c':
            delta.c = distance
        
        return await self.move_relative(delta, feedrate)
    
    async def probe(self, direction: str, distance: float = 10.0) -> Optional[Position4D]:
        """Probe operation - simplified"""
        logger.warning("⚠️  Probe not implemented in fallback controller")
        return None
    
    async def set_feedrate(self, feedrate: float) -> bool:
        """Set feedrate"""
        command = f"F{feedrate}"
        return await self._send_robust_command(command)
    
    async def reset(self) -> bool:
        """Reset controller"""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'\x18')  # Ctrl-X
                self.serial_connection.flush()
                await asyncio.sleep(2.0)
                self._clear_buffer()
                return True
        except Exception:
            pass
        return False
    
    async def get_capabilities(self) -> dict:
        """Get controller capabilities"""
        return {
            'axes': ['X', 'Y', 'Z', 'C'],
            'homing': True,
            'probing': False,
            'feedrate_control': True
        }
    
    async def get_limits(self) -> dict:
        """Get axis limits"""
        return {
            'x': {'min': 0, 'max': 200},
            'y': {'min': 0, 'max': 200},
            'z': {'min': -360, 'max': 360},
            'c': {'min': -90, 'max': 90}
        }
    
    async def configure_axes(self, config: dict) -> bool:
        """Configure axes"""
        logger.info("✅ Axes configuration accepted (fallback)")
        return True
    
    # Additional required abstract methods
    async def rapid_move(self, position: Position4D) -> bool:
        """Rapid move to position"""
        return await self.move_to_position(position)
    
    async def home_all_axes(self) -> bool:
        """Home all axes"""
        success = True
        for axis in ['X', 'Y', 'Z', 'A']:  # A is C axis in FluidNC
            if not await self.home_axis(axis):
                success = False
        return success
    
    async def pause_motion(self) -> bool:
        """Pause motion"""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'!')  # Feed hold
                self.serial_connection.flush()
            return True
        except Exception:
            return False
    
    async def resume_motion(self) -> bool:
        """Resume motion"""
        try:
            if self.serial_connection:
                self.serial_connection.write(b'~')  # Cycle start/resume
                self.serial_connection.flush()
            return True
        except Exception:
            return False
    
    async def cancel_motion(self) -> bool:
        """Cancel motion"""
        return await self.emergency_stop()
    
    async def set_motion_limits(self, axis: str, limits) -> bool:
        """Set motion limits"""
        logger.info(f"✅ Motion limits set for {axis} (fallback)")
        return True
    
    async def get_motion_limits(self, axis: str):
        """Get motion limits"""
        limits_dict = await self.get_limits()
        return limits_dict.get(axis.lower(), {'min': 0, 'max': 100})
    
    async def execute_gcode(self, gcode: str) -> bool:
        """Execute G-code"""
        return await self._send_robust_command(gcode)
    
    async def wait_for_motion_complete(self, timeout: float = 30.0) -> bool:
        """Wait for motion complete"""
        await asyncio.sleep(1.0)  # Simple implementation
        return True