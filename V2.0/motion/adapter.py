"""
Phase 2: Standardized Motion Controller Adapter

This adapter provides a standardized interface for all motion controllers 
with explicit support for Z-axis as rotational and proper axis type handling.

Key Features:
- Standardized adapter pattern for motion controllers
- Explicit Z-axis rotational semantics
- Position validation with axis-aware limits
- Continuous rotation support for Z-axis
- Type-safe axis handling
- Improved error handling and logging

Author: Scanner System Development - Phase 2
Created: September 2025
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from motion.base import (
    MotionController, Position4D, MotionStatus, AxisType, 
    MotionLimits, MotionCapabilities
)
from core.exceptions import MotionControlError, MotionSafetyError
from core.events import ScannerEvent, EventPriority


class AxisMoveType(Enum):
    """Types of axis movement"""
    LINEAR = "linear"
    ROTATIONAL_LIMITED = "rotational_limited"
    ROTATIONAL_CONTINUOUS = "rotational_continuous"


@dataclass
class AxisDefinition:
    """Complete axis definition with type and constraints"""
    name: str
    axis_type: AxisType
    move_type: AxisMoveType
    units: str
    limits: MotionLimits
    continuous: bool = False
    wrap_around: bool = False  # For continuous rotational axes
    home_required: bool = True


@dataclass
class MotionCommand:
    """Standardized motion command"""
    target_position: Position4D
    feedrate: Optional[float] = None
    move_type: str = "linear"  # linear, rapid, arc
    wait_complete: bool = True


class StandardMotionAdapter(ABC):
    """
    Standardized adapter interface for motion controllers
    
    This adapter provides a consistent interface regardless of the underlying
    motion controller (FluidNC, GRBL, simulators, etc.) with explicit support
    for rotational Z-axis.
    """
    
    def __init__(self, controller: MotionController, config: Dict[str, Any]):
        self.controller = controller
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Define axis system with Z as rotational
        self.axes = self._define_axis_system()
        
        # Validation state
        self._last_validated_position: Optional[Position4D] = None
        self._position_cache: Optional[Position4D] = None
        self._cache_timestamp: float = 0
        
    def _define_axis_system(self) -> Dict[str, AxisDefinition]:
        """Define the 4DOF axis system with Z as rotational"""
        axes_config = self.config.get('axes', {})
        
        # X-Axis: Linear motion
        x_config = axes_config.get('x_axis', {})
        x_axis = AxisDefinition(
            name='X',
            axis_type=AxisType.LINEAR,
            move_type=AxisMoveType.LINEAR,
            units='mm',
            limits=MotionLimits(
                min_limit=x_config.get('min_limit', 0.0),
                max_limit=x_config.get('max_limit', 200.0),
                max_feedrate=x_config.get('max_feedrate', 1000.0)
            ),
            continuous=False,
            home_required=x_config.get('homing_required', True)
        )
        
        # Y-Axis: Linear motion  
        y_config = axes_config.get('y_axis', {})
        y_axis = AxisDefinition(
            name='Y',
            axis_type=AxisType.LINEAR,
            move_type=AxisMoveType.LINEAR,
            units='mm',
            limits=MotionLimits(
                min_limit=y_config.get('min_limit', 0.0),
                max_limit=y_config.get('max_limit', 200.0),
                max_feedrate=y_config.get('max_feedrate', 1000.0)
            ),
            continuous=False,
            home_required=y_config.get('homing_required', True)
        )
        
        # Z-Axis: ROTATIONAL CONTINUOUS motion (turntable)
        z_config = axes_config.get('z_axis', {})
        z_axis = AxisDefinition(
            name='Z',
            axis_type=AxisType.ROTATIONAL,
            move_type=AxisMoveType.ROTATIONAL_CONTINUOUS,
            units='degrees',
            limits=MotionLimits(
                min_limit=z_config.get('min_limit', -180.0),
                max_limit=z_config.get('max_limit', 180.0),
                max_feedrate=z_config.get('max_feedrate', 800.0)
            ),
            continuous=z_config.get('continuous', True),
            wrap_around=True,  # Z-axis wraps around at ±180°
            home_required=z_config.get('homing_required', False)
        )
        
        # C-Axis: Rotational limited motion (camera tilt)
        c_config = axes_config.get('c_axis', {})
        c_axis = AxisDefinition(
            name='C',
            axis_type=AxisType.ROTATIONAL,
            move_type=AxisMoveType.ROTATIONAL_LIMITED,
            units='degrees',
            limits=MotionLimits(
                min_limit=c_config.get('min_limit', -90.0),
                max_limit=c_config.get('max_limit', 90.0),
                max_feedrate=c_config.get('max_feedrate', 1800.0)
            ),
            continuous=False,
            home_required=c_config.get('homing_required', False)
        )
        
        return {
            'x': x_axis,
            'y': y_axis, 
            'z': z_axis,
            'c': c_axis
        }
    
    # Abstract methods for implementation
    @abstractmethod
    async def initialize_controller(self) -> bool:
        """Initialize the underlying motion controller"""
        pass
    
    @abstractmethod
    async def shutdown_controller(self) -> bool:
        """Shutdown the underlying motion controller"""
        pass
    
    # Position Management with Z-Axis Awareness
    def normalize_z_position(self, z_degrees: float) -> float:
        """
        Normalize Z-axis position for continuous rotation
        
        Args:
            z_degrees: Raw Z position in degrees
            
        Returns:
            Normalized Z position in range [-180, 180]
        """
        if not self.axes['z'].continuous:
            return z_degrees
            
        # Normalize to [-180, 180] range for continuous rotation
        while z_degrees > 180.0:
            z_degrees -= 360.0
        while z_degrees < -180.0:
            z_degrees += 360.0
            
        return z_degrees
    
    def calculate_z_rotation_direction(self, current_z: float, target_z: float) -> Tuple[float, str]:
        """
        Calculate optimal rotation direction for Z-axis
        
        Args:
            current_z: Current Z position
            target_z: Target Z position
            
        Returns:
            (optimal_target, direction) where direction is 'cw' or 'ccw'
        """
        if not self.axes['z'].continuous:
            return target_z, 'direct'
        
        # Normalize both positions
        current = self.normalize_z_position(current_z)
        target = self.normalize_z_position(target_z)
        
        # Calculate shortest rotation path
        direct_diff = target - current
        wrap_cw_diff = direct_diff - 360.0 if direct_diff > 180.0 else direct_diff + 360.0
        
        if abs(direct_diff) <= abs(wrap_cw_diff):
            return target, 'direct'
        else:
            # Use wrap-around path
            if wrap_cw_diff > 0:
                return current + wrap_cw_diff, 'ccw'
            else:
                return current + wrap_cw_diff, 'cw'
    
    def validate_position_with_axis_types(self, position: Position4D) -> bool:
        """
        Validate position with axis-type awareness
        
        Args:
            position: Position to validate
            
        Returns:
            True if position is valid
            
        Raises:
            MotionSafetyError: If position violates axis constraints
        """
        errors = []
        
        # Validate each axis according to its type
        pos_dict = position.to_dict()
        
        for axis_name, axis_def in self.axes.items():
            value = pos_dict[axis_name.lower()]
            
            if axis_def.axis_type == AxisType.ROTATIONAL and axis_def.continuous:
                # For continuous rotational axes, normalize before checking
                normalized_value = self.normalize_z_position(value)
                if not axis_def.limits.is_within_limits(normalized_value):
                    errors.append(
                        f"{axis_name}-axis position {value}° (normalized: {normalized_value}°) "
                        f"exceeds limits [{axis_def.limits.min_limit}°, {axis_def.limits.max_limit}°]"
                    )
            else:
                # Standard limit checking for linear and limited rotational axes
                if not axis_def.limits.is_within_limits(value):
                    errors.append(
                        f"{axis_name}-axis position {value}{axis_def.units} "
                        f"exceeds limits [{axis_def.limits.min_limit}, {axis_def.limits.max_limit}]{axis_def.units}"
                    )
        
        if errors:
            raise MotionSafetyError(f"Position validation failed: {'; '.join(errors)}")
        
        self._last_validated_position = position
        return True
    
    # High-Level Motion Commands
    async def move_to_position(self, position: Position4D, feedrate: Optional[float] = None) -> bool:
        """
        Move to absolute position with Z-axis rotation optimization
        
        Args:
            position: Target position
            feedrate: Movement speed
            
        Returns:
            True if movement successful
        """
        try:
            # Validate position with axis-type awareness
            self.validate_position_with_axis_types(position)
            
            # Get current position for Z-axis optimization
            current_pos = await self.get_current_position()
            
            # Optimize Z-axis rotation for continuous axes
            optimized_position = position
            if self.axes['z'].continuous:
                optimal_z, direction = self.calculate_z_rotation_direction(
                    current_pos.z, position.z
                )
                optimized_position = Position4D(
                    x=position.x,
                    y=position.y,
                    z=optimal_z,
                    c=position.c
                )
                
                self.logger.info(
                    f"Z-axis rotation optimized: {position.z}° → {optimal_z}° "
                    f"(direction: {direction})"
                )
            
            # Execute move with underlying controller
            result = await self.controller.move_to_position(optimized_position, feedrate)
            
            if result:
                self.logger.info(f"Move completed to {optimized_position}")
                self._notify_motion_event("position_reached", {
                    "target": optimized_position.to_dict(),
                    "original_target": position.to_dict()
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Move to position failed: {e}")
            self._notify_motion_event("motion_error", {"error": str(e)})
            return False
    
    async def move_z_to(self, z_degrees: float, feedrate: Optional[float] = None) -> bool:
        """
        Move Z-axis to specific rotation with optimization
        
        Args:
            z_degrees: Target Z rotation in degrees
            feedrate: Rotation speed in degrees/min
            
        Returns:
            True if rotation successful
        """
        try:
            current_pos = await self.get_current_position()
            target_pos = Position4D(
                x=current_pos.x,
                y=current_pos.y,
                z=z_degrees,
                c=current_pos.c
            )
            
            return await self.move_to_position(target_pos, feedrate)
            
        except Exception as e:
            self.logger.error(f"Z-axis rotation to {z_degrees}° failed: {e}")
            return False
    
    async def rotate_z_relative(self, delta_degrees: float, feedrate: Optional[float] = None) -> bool:
        """
        Rotate Z-axis by relative amount
        
        Args:
            delta_degrees: Relative rotation in degrees
            feedrate: Rotation speed in degrees/min
            
        Returns:
            True if rotation successful
        """
        try:
            current_pos = await self.get_current_position()
            new_z = current_pos.z + delta_degrees
            
            return await self.move_z_to(new_z, feedrate)
            
        except Exception as e:
            self.logger.error(f"Z-axis relative rotation by {delta_degrees}° failed: {e}")
            return False
    
    # Cached Position Management
    async def get_current_position(self, use_cache: bool = True) -> Position4D:
        """
        Get current position with optional caching
        
        Args:
            use_cache: Whether to use cached position if recent
            
        Returns:
            Current position
        """
        import time
        
        current_time = time.time()
        
        # Use cache if recent (within 100ms) and requested
        if (use_cache and self._position_cache is not None and 
            (current_time - self._cache_timestamp) < 0.1):
            return self._position_cache
        
        # Get fresh position from controller
        position = await self.controller.get_position()
        
        # Normalize Z-axis if continuous
        if position and self.axes['z'].continuous:
            position.z = self.normalize_z_position(position.z)
        
        # Update cache
        self._position_cache = position
        self._cache_timestamp = current_time
        
        return position
    
    def invalidate_position_cache(self):
        """Invalidate position cache to force fresh read"""
        self._position_cache = None
        self._cache_timestamp = 0
    
    # Status and Information
    async def get_motion_status(self) -> MotionStatus:
        """Get current motion status"""
        return await self.controller.get_status()
    
    def get_axis_info(self, axis: str) -> Optional[AxisDefinition]:
        """Get axis definition information"""
        return self.axes.get(axis.lower())
    
    def get_all_axis_info(self) -> Dict[str, AxisDefinition]:
        """Get all axis definitions"""
        return self.axes.copy()
    
    # Safety and Emergency
    async def emergency_stop(self) -> bool:
        """Emergency stop all motion"""
        try:
            result = await self.controller.emergency_stop()
            if result:
                self._notify_motion_event("emergency_stop", {"reason": "user_initiated"})
            return result
        except Exception as e:
            self.logger.error(f"Emergency stop failed: {e}")
            return False
    
    # Event Management
    def _notify_motion_event(self, event_type: str, data: Dict[str, Any]):
        """Notify motion event to system"""
        try:
            event = ScannerEvent(
                event_type=f"motion.{event_type}",
                data=data,
                source_module="motion_adapter",
                priority=EventPriority.HIGH if "error" in event_type else EventPriority.NORMAL
            )
            
            # Notify through controller if it has event callbacks
            if hasattr(self.controller, '_notify_event'):
                self.controller._notify_event(event_type, data)
                
        except Exception as e:
            self.logger.error(f"Failed to notify motion event: {e}")


class FluidNCMotionAdapter(StandardMotionAdapter):
    """
    FluidNC-specific implementation of the standardized motion adapter
    
    Provides FluidNC-specific optimizations and features while maintaining
    the standard adapter interface.
    """
    
    def __init__(self, fluidnc_controller, config: Dict[str, Any]):
        super().__init__(fluidnc_controller, config)
        self.fluidnc = fluidnc_controller  # Type hint for FluidNC-specific features
        
    async def initialize_controller(self) -> bool:
        """Initialize FluidNC controller"""
        try:
            result = await self.fluidnc.initialize()
            if result:
                self.logger.info("FluidNC controller initialized successfully")
                self._notify_motion_event("controller_initialized", {
                    "controller_type": "FluidNC",
                    "axes": list(self.axes.keys())
                })
            return result
        except Exception as e:
            self.logger.error(f"FluidNC controller initialization failed: {e}")
            return False
    
    async def shutdown_controller(self) -> bool:
        """Shutdown FluidNC controller"""
        try:
            result = await self.fluidnc.shutdown()
            if result:
                self.logger.info("FluidNC controller shutdown successfully")
                self._notify_motion_event("controller_shutdown", {})
            return result
        except Exception as e:
            self.logger.error(f"FluidNC controller shutdown failed: {e}")
            return False
    
    async def home_axes(self) -> bool:
        """Home all required axes"""
        try:
            self.logger.info("Starting homing sequence for FluidNC")
            
            # Get axes that require homing
            homing_axes = [
                axis_def.name for axis_def in self.axes.values() 
                if axis_def.home_required
            ]
            
            self.logger.info(f"Homing axes: {homing_axes}")
            
            result = await self.fluidnc.home_all_axes()
            
            if result:
                self.logger.info("FluidNC homing completed successfully")
                self._notify_motion_event("homing_completed", {
                    "homed_axes": homing_axes
                })
                # Invalidate position cache after homing
                self.invalidate_position_cache()
            
            return result
            
        except Exception as e:
            self.logger.error(f"FluidNC homing failed: {e}")
            self._notify_motion_event("homing_failed", {"error": str(e)})
            return False
    
    def get_fluidnc_status(self) -> Dict[str, Any]:
        """Get FluidNC-specific status information"""
        try:
            status = {
                "connection": self.fluidnc.is_connected(),
                "status": self.fluidnc.status.value if self.fluidnc.status else "unknown",
                "is_homed": getattr(self.fluidnc, 'is_homed', False),
                "axes_info": {}
            }
            
            # Add axis-specific information
            for axis_name, axis_def in self.axes.items():
                status["axes_info"][axis_name] = {
                    "type": axis_def.axis_type.value,
                    "move_type": axis_def.move_type.value,
                    "units": axis_def.units,
                    "continuous": axis_def.continuous,
                    "home_required": axis_def.home_required,
                    "limits": {
                        "min": axis_def.limits.min_limit,
                        "max": axis_def.limits.max_limit,
                        "max_feedrate": axis_def.limits.max_feedrate
                    }
                }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get FluidNC status: {e}")
            return {"error": str(e)}


# Factory function for creating motion adapters
def create_motion_adapter(controller: MotionController, config: Dict[str, Any]) -> StandardMotionAdapter:
    """
    Factory function to create appropriate motion adapter
    
    Args:
        controller: Motion controller instance
        config: System configuration
        
    Returns:
        Appropriate motion adapter instance
    """
    controller_type = config.get('controller', {}).get('type', 'unknown')
    
    if controller_type.lower() == 'fluidnc':
        return FluidNCMotionAdapter(controller, config)
    else:
        # Generic adapter for other controller types
        class GenericMotionAdapter(StandardMotionAdapter):
            async def initialize_controller(self) -> bool:
                return await self.controller.connect()
            
            async def shutdown_controller(self) -> bool:
                return await self.controller.disconnect()
        
        return GenericMotionAdapter(controller, config)