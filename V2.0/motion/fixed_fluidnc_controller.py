#!/usr/bin/env python3
"""
Fixed FluidNC Motion Controller

This controller implements the working homing completion detection from the tests.
It uses the FixedFluidNCProtocol for proper "MSG:DBG: Homing done" detection.

Author: Scanner System Development
Created: September 26, 2025
"""

import asyncio
import logging
import time
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass

from .base import MotionController, MotionStatus, Position4D, MotionCapabilities, MotionLimits
from .fixed_fluidnc_protocol import FixedFluidNCProtocol, FluidNCStatus

logger = logging.getLogger(__name__)

class FixedFluidNCController(MotionController):
    """
    Fixed FluidNC motion controller with proper homing completion detection.
    
    This implementation:
    - Uses the working homing detection from successful tests
    - Waits for "MSG:DBG: Homing done" message
    - Verifies final status is "Idle"
    - Implements all abstract methods from MotionController base class
    """
    
    def __init__(self, port: str = "/dev/ttyUSB0", baud_rate: int = 115200):
        # Initialize with empty config for now
        super().__init__({})
        self.port = port
        self.baud_rate = baud_rate
        self.protocol = FixedFluidNCProtocol(port, baud_rate)
        self._status = MotionStatus.DISCONNECTED
        self._current_position = Position4D(0, 0, 0, 0)
        self._is_homed = False
        
        logger.info(f"🔧 FixedFluidNCController initialized for {port}")
    
    # Connection Management Methods
    async def connect(self) -> bool:
        """Connect to FluidNC controller"""
        try:
            logger.info("🚀 Connecting to FixedFluidNC controller...")
            
            if self.protocol.connect():
                self._status = MotionStatus.IDLE
                logger.info("✅ FixedFluidNC controller connected successfully")
                return True
            else:
                self._status = MotionStatus.ERROR
                logger.error("❌ Failed to connect to FluidNC")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection error: {e}")
            self._status = MotionStatus.ERROR
            return False
            
    async def disconnect(self) -> bool:
        """Disconnect from FluidNC controller"""
        try:
            logger.info("🔽 Disconnecting from FixedFluidNC controller...")
            
            # Stop any ongoing motion
            if self._status == MotionStatus.MOVING:
                await self.emergency_stop()
            
            # Disconnect
            if self.protocol.disconnect():
                self._status = MotionStatus.DISCONNECTED
                logger.info("✅ FixedFluidNC controller disconnected successfully")
                return True
            else:
                logger.error("❌ Error during disconnect")
                return False
                
        except Exception as e:
            logger.error(f"❌ Disconnect error: {e}")
            return False
    
    def is_connected(self) -> bool:
        """Check if connected to controller"""
        return self.protocol.is_connected()

    async def initialize(self) -> bool:
        """Initialize the motion controller (legacy method)"""
        return await self.connect()
    
    async def shutdown(self) -> bool:
        """Shutdown the motion controller (legacy method)"""
        return await self.disconnect()
    
    # Status and Information Methods
    async def get_status(self) -> MotionStatus:
        """Get current motion controller status"""
        return self._status
    
    async def get_capabilities(self) -> MotionCapabilities:
        """Get motion controller capabilities"""
        return MotionCapabilities(
            axes_count=4,
            supports_homing=True,
            supports_soft_limits=True,
            supports_probe=False,
            max_feedrate=1000.0,
            position_resolution=0.001
        )
    
    # Motion Commands
    async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
        """Move relative to current position"""
        current = await self.get_position()
        target = Position4D(
            x=current.x + delta.x,
            y=current.y + delta.y,
            z=current.z + delta.z,
            c=current.c + delta.c
        )
        return await self.move_to_position(target)
    
    async def rapid_move(self, position: Position4D) -> bool:
        """Rapid movement to position"""
        return await self.move_to_position(position)
    
    # Homing Methods  
    async def home_all_axes(self) -> bool:
        """Home all axes"""
        return await self.home_axes()
        
    async def home_axis(self, axis: str) -> bool:
        """Home specific axis (FluidNC homes all axes together)"""
        logger.warning("FluidNC homes all axes together, ignoring specific axis request")
        return await self.home_axes()
        
    async def set_position(self, position: Position4D) -> bool:
        """Set current position coordinate system"""
        try:
            # Use G92 to set coordinate system
            gcode = f"G92 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
            success, response = self.protocol.send_command(gcode)
            
            if success:
                self._current_position = position
                logger.info(f"✅ Position set to: {position}")
                return True
            else:
                logger.error(f"❌ Failed to set position: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Set position error: {e}")
            return False
    
    # Safety and Control Methods
    async def emergency_stop(self) -> bool:
        """Emergency stop all motion"""
        try:
            logger.warning("🚨 Emergency stop activated!")
            success, response = self.protocol.send_command("!")  # Feed hold
            
            if success:
                self._status = MotionStatus.EMERGENCY_STOP
                logger.info("✅ Emergency stop activated")
                return True
            else:
                logger.error(f"❌ Emergency stop failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Emergency stop error: {e}")
            return False
    
    async def pause_motion(self) -> bool:
        """Pause current motion"""
        try:
            success, response = self.protocol.send_command("!")  # Feed hold
            if success:
                logger.info("⏸️ Motion paused")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Pause error: {e}")
            return False
    
    async def resume_motion(self) -> bool:
        """Resume paused motion"""
        try:
            success, response = self.protocol.send_command("~")  # Cycle start
            if success:
                logger.info("▶️ Motion resumed")
                return True
            return False
        except Exception as e:
            logger.error(f"❌ Resume error: {e}")
            return False
    
    async def cancel_motion(self) -> bool:
        """Cancel current motion"""
        return await self.emergency_stop()
    
    # Configuration Methods (simplified implementations)
    async def set_motion_limits(self, axis: str, limits: MotionLimits) -> bool:
        """Set motion limits for axis"""
        logger.info(f"Motion limits setting not implemented for FluidNC")
        return True
    
    async def get_motion_limits(self, axis: str) -> Optional[MotionLimits]:
        """Get motion limits for axis"""
        return None
    
    async def set_feedrate(self, feedrate: float) -> bool:
        """Set feedrate"""
        try:
            success, response = self.protocol.send_command(f"F{feedrate:.1f}")
            return success
        except Exception as e:
            logger.error(f"❌ Set feedrate error: {e}")
            return False
    
    async def get_feedrate(self) -> float:
        """Get current feedrate"""
        return 100.0  # Default feedrate
    
    # Homing Implementation (the main method)
    async def home_axes(self) -> bool:
        """
        Home all axes using the working homing completion detection.
        
        This method uses the FixedFluidNCProtocol which properly waits for
        the "MSG:DBG: Homing done" message like the successful tests.
        """
        try:
            logger.info("🏠 Starting homing sequence...")
            self._status = MotionStatus.HOMING
            
            # Use the working homing implementation from protocol
            success, result = self.protocol.send_homing_command()
            
            if success:
                self._is_homed = True
                self._status = MotionStatus.IDLE
                # Update position after homing (FluidNC sets to 0,200,0,0)
                self._current_position = Position4D(0, 200, 0, 0)
                logger.info("✅ Homing completed successfully")
                return True
            else:
                self._is_homed = False
                self._status = MotionStatus.ERROR
                logger.error(f"❌ Homing failed: {result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Homing error: {e}")
            self._is_homed = False
            self._status = MotionStatus.ERROR
            return False
    
    async def move_to_position(self, position: Position4D) -> bool:
        """Move to specified position"""
        try:
            # Validate position
            if not self.validate_position(position):
                logger.error("❌ Invalid position for move")
                return False
            
            if not self._is_homed:
                logger.error("❌ System must be homed before moving")
                return False
            
            logger.info(f"🎯 Moving to position: {position}")
            self._status = MotionStatus.MOVING
            
            # Send G-code move command
            gcode = f"G0 X{position.x:.3f} Y{position.y:.3f} Z{position.z:.3f} C{position.c:.3f}"
            success, response = self.protocol.send_command(gcode)
            
            if success:
                # Wait for motion to complete
                await self._wait_for_idle()
                self._current_position = position
                logger.info("✅ Move completed successfully")
                return True
            else:
                logger.error(f"❌ Move command failed: {response}")
                self._status = MotionStatus.ERROR
                return False
                
        except Exception as e:
            logger.error(f"❌ Move error: {e}")
            self._status = MotionStatus.ERROR
            return False
    
    async def stop_motion(self) -> bool:
        """Stop current motion"""
        try:
            logger.info("🛑 Stopping motion...")
            success, response = self.protocol.send_command("!")  # Feed hold
            
            if success:
                await asyncio.sleep(0.5)
                # Send cycle stop
                success2, response2 = self.protocol.send_command("~")
                
                if success2:
                    self._status = MotionStatus.IDLE
                    logger.info("✅ Motion stopped successfully")
                    return True
            
            logger.error("❌ Failed to stop motion")
            return False
            
        except Exception as e:
            logger.error(f"❌ Stop motion error: {e}")
            return False
    
    async def get_position(self) -> Position4D:
        """Get current position"""
        try:
            # Update position from FluidNC
            success, response = self.protocol.send_command("?")
            if success:
                status = self.protocol.get_status()
                if status.position:
                    self._current_position = Position4D(
                        x=status.position.get('x', 0),
                        y=status.position.get('y', 0),
                        z=status.position.get('z', 0),
                        c=status.position.get('c', 0)
                    )
            
            return self._current_position
            
        except Exception as e:
            logger.error(f"❌ Get position error: {e}")
            return self._current_position
    
    def is_homed(self) -> bool:
        """Check if system is homed"""
        return self._is_homed
    
    async def _wait_for_idle(self, timeout: float = 30.0) -> bool:
        """Wait for motion to complete (status becomes Idle)"""
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            try:
                success, response = self.protocol.send_command("?")
                if success:
                    status = self.protocol.get_status()
                    if status.state == "Idle":
                        self._status = MotionStatus.IDLE
                        return True
                    elif "Alarm" in status.state:
                        self._status = MotionStatus.ERROR
                        logger.error(f"❌ Motion alarm: {status.state}")
                        return False
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Wait for idle error: {e}")
                return False
        
        logger.error("❌ Timeout waiting for motion to complete")
        self._status = MotionStatus.ERROR
        return False
    
    def get_controller_info(self) -> Dict[str, Any]:
        """Get controller information"""
        return {
            'type': 'FixedFluidNC',
            'port': self.port,
            'baud_rate': self.baud_rate,
            'connected': self.is_connected(),
            'homed': self.is_homed(),
            'status': self._status.value,
            'position': {
                'x': self._current_position.x,
                'y': self._current_position.y, 
                'z': self._current_position.z,
                'c': self._current_position.c
            },
            'protocol_stats': self.protocol.get_stats()
        }