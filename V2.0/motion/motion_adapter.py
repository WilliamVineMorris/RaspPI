#!/usr/bin/env python3
"""
Motion Controller Adapter
Bridges SimpleWorkingFluidNCController with the abstract MotionController interface.
This allows the working controller to be used with the existing system.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

from motion.base import MotionController, MotionStatus, Position4D
from simple_working_fluidnc_controller import SimpleWorkingFluidNCController, Position
from core.config_manager import ConfigManager
from core.events import EventBus, Event, EventPriority

class MotionControllerAdapter(MotionController):
    """
    Adapter that wraps SimpleWorkingFluidNCController to implement MotionController interface.
    This allows us to use the working controller without modifying it.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """Initialize the adapter with config manager."""
        super().__init__(config_manager)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Extract port and baudrate from config
        motion_config = config_manager.get_hardware_config().get('motion', {})
        port = motion_config.get('port', '/dev/ttyUSB0')
        baudrate = motion_config.get('baudrate', 115200)
        
        # Create the working controller
        self.controller = SimpleWorkingFluidNCController(port=port, baudrate=baudrate)
        
        # Event bus for compatibility
        self.event_bus = EventBus()
        
        self.logger.info("Motion adapter initialized with SimpleWorkingFluidNCController")
    
    async def initialize(self) -> bool:
        """Initialize the motion controller."""
        try:
            # Use the working controller's connect method
            success = self.controller.connect()
            
            if success:
                self.logger.info("✅ Motion controller initialized successfully")
                
                # Publish connection event
                await self.event_bus.publish(Event(
                    type="motion_connected",
                    source="motion_adapter"
                ))
                
                # Check if in alarm state
                status = self.controller.get_status()
                if status == "Alarm":
                    self.logger.warning("⚠️ Controller in ALARM state - homing required")
                    self.logger.info("💡 Use home() method to clear alarm and establish position")
            else:
                self.logger.error("❌ Failed to initialize motion controller")
                
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Initialization error: {e}")
            return False
    
    async def shutdown(self) -> None:
        """Shutdown the motion controller."""
        try:
            self.controller.disconnect()
            
            # Publish disconnection event
            await self.event_bus.publish(Event(
                type="motion_disconnected",
                source="motion_adapter"
            ))
            
            self.logger.info("✅ Motion controller shutdown")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    def is_connected(self) -> bool:
        """Check if controller is connected."""
        return self.controller.is_connected()
    
    async def get_status(self) -> MotionStatus:
        """Get current motion status."""
        status_str = self.controller.get_status()
        
        # Map string status to MotionStatus enum
        status_map = {
            "Idle": MotionStatus.IDLE,
            "Alarm": MotionStatus.ALARM,
            "Run": MotionStatus.MOVING,
            "Jog": MotionStatus.MOVING,
            "Home": MotionStatus.HOMING,
            "Homing": MotionStatus.HOMING,
            "Hold": MotionStatus.IDLE,
        }
        
        return status_map.get(status_str, MotionStatus.UNKNOWN)
    
    def get_position(self) -> Position4D:
        """Get current position."""
        pos = self.controller.get_position()
        return Position4D(x=pos.x, y=pos.y, z=pos.z, c=pos.c)
    
    async def home(self) -> bool:
        """Home all axes."""
        try:
            # Use the working controller's home method
            success = self.controller.home()
            
            if success:
                self.logger.info("✅ Homing completed successfully")
                
                # Publish homing complete event
                await self.event_bus.publish(Event(
                    type="homing_complete",
                    source="motion_adapter"
                ))
            else:
                self.logger.error("❌ Homing failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Homing error: {e}")
            return False
    
    async def move_to_position(self, position: Position4D) -> bool:
        """Move to specified position."""
        try:
            # Validate position
            if not self.validate_position(position):
                self.logger.error(f"Invalid position: {position}")
                return False
            
            # Convert Position4D to simple Position
            simple_pos = Position(x=position.x, y=position.y, z=position.z, c=position.c)
            
            # Use the working controller's move method
            success = self.controller.move_to_position(simple_pos)
            
            if success:
                self.logger.debug(f"Moved to {position}")
            else:
                self.logger.error(f"Failed to move to {position}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Movement error: {e}")
            return False
    
    async def stop_motion(self) -> bool:
        """Stop all motion immediately."""
        try:
            self.controller.stop_motion()
            
            # Publish motion stopped event
            await self.event_bus.publish(Event(
                type="motion_stopped",
                source="motion_adapter",
                priority=EventPriority.HIGH
            ))
            
            return True
            
        except Exception as e:
            self.logger.error(f"Stop motion error: {e}")
            return False
    
    async def set_feed_rate(self, rate: float) -> bool:
        """Set feed rate override percentage."""
        try:
            # The simple controller doesn't have feed rate override
            # We can implement this by adjusting the G-code F parameter
            # For now, just log it
            self.logger.info(f"Feed rate set to {rate}% (not implemented in simple controller)")
            return True
            
        except Exception as e:
            self.logger.error(f"Feed rate error: {e}")
            return False
    
    def is_homed(self) -> bool:
        """Check if system is homed."""
        return self.controller.is_homed()
    
    async def emergency_stop(self) -> None:
        """Trigger emergency stop."""
        try:
            self.controller.stop_motion()
            
            # Publish emergency stop event
            await self.event_bus.publish(Event(
                type="emergency_stop",
                source="motion_adapter",
                priority=EventPriority.CRITICAL
            ))
            
            self.logger.warning("🚨 EMERGENCY STOP TRIGGERED")
            
        except Exception as e:
            self.logger.error(f"Emergency stop error: {e}")
    
    async def clear_alarm(self) -> bool:
        """Clear alarm state."""
        try:
            # Send unlock command through the simple controller
            response = self.controller.send_command("$X")
            success = response is not None and "ok" in response.lower()
            
            if success:
                self.logger.info("✅ Alarm cleared")
            else:
                self.logger.error("❌ Failed to clear alarm")
                
            return success
            
        except Exception as e:
            self.logger.error(f"Clear alarm error: {e}")
            return False
    
    async def execute_gcode(self, gcode: str) -> bool:
        """Execute arbitrary G-code command."""
        try:
            response = self.controller.send_command(gcode)
            return response is not None and "error" not in response.lower()
            
        except Exception as e:
            self.logger.error(f"G-code execution error: {e}")
            return False
    
    async def wait_for_motion_complete(self, timeout: float = 30.0) -> bool:
        """Wait for current motion to complete."""
        try:
            # Simple polling approach
            start_time = asyncio.get_event_loop().time()
            
            while (asyncio.get_event_loop().time() - start_time) < timeout:
                status = await self.get_status()
                
                if status == MotionStatus.IDLE:
                    return True
                elif status == MotionStatus.ALARM:
                    self.logger.error("Motion stopped due to alarm")
                    return False
                
                await asyncio.sleep(0.1)  # Check every 100ms
            
            self.logger.warning(f"Motion timeout after {timeout}s")
            return False
            
        except Exception as e:
            self.logger.error(f"Wait for motion error: {e}")
            return False