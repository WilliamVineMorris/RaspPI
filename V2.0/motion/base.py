"""
Abstract Motion Control Interface

Defines the standard interface for all motion control implementations.
This ensures modularity and allows different motion controllers 
(FluidNC, GRBL, simulators) to be used interchangeably.

Author: Scanner System Development
Created: September 2025
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Callable
from enum import Enum
import asyncio

from core.exceptions import MotionControlError
from core.events import ScannerEvent


class MotionStatus(Enum):
    """Motion controller status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    IDLE = "idle"
    MOVING = "moving"
    HOMING = "homing"
    ALARM = "alarm"
    ERROR = "error"
    EMERGENCY_STOP = "emergency_stop"


class AxisType(Enum):
    """Types of motion axes"""
    LINEAR = "linear"
    ROTATIONAL = "rotational"


@dataclass
class Position4D:
    """4-degree-of-freedom position representation"""
    x: float = 0.0  # X-axis position (mm)
    y: float = 0.0  # Y-axis position (mm)
    z: float = 0.0  # Z-axis position (degrees, rotational)
    c: float = 0.0  # C-axis position (degrees, camera tilt)
    
    def __str__(self):
        return f"Position(X:{self.x:.3f}, Y:{self.y:.3f}, Z:{self.z:.3f}, C:{self.c:.3f})"
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization"""
        return {"x": self.x, "y": self.y, "z": self.z, "c": self.c}
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'Position4D':
        """Create from dictionary"""
        return cls(
            x=data.get('x', 0.0),
            y=data.get('y', 0.0),
            z=data.get('z', 0.0),
            c=data.get('c', 0.0)
        )
    
    def distance_to(self, other: 'Position4D') -> float:
        """Calculate 3D distance to another position (excluding rotation)"""
        import math
        return math.sqrt(
            (self.x - other.x) ** 2 + 
            (self.y - other.y) ** 2
            # Note: Z and C are rotational, distance calculation may need adjustment
        )


@dataclass
class MotionLimits:
    """Motion limits for an axis"""
    min_limit: float
    max_limit: float
    max_feedrate: float  # mm/min or degrees/min
    acceleration: Optional[float] = None  # mm/min² or degrees/min²
    
    def is_within_limits(self, position: float) -> bool:
        """Check if position is within limits"""
        return self.min_limit <= position <= self.max_limit


@dataclass
class MotionCapabilities:
    """Motion controller capabilities"""
    axes_count: int
    supports_homing: bool
    supports_soft_limits: bool
    supports_probe: bool
    max_feedrate: float
    position_resolution: float  # Minimum position increment


class MotionController(ABC):
    """
    Abstract base class for motion control systems
    
    This interface defines the contract that all motion controllers must implement.
    Supports 4DOF systems (X, Y, Z-rotational, C-camera tilt) but can be adapted
    for different configurations.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = MotionStatus.DISCONNECTED
        self.current_position = Position4D()
        self.target_position = Position4D()
        self.motion_limits: Dict[str, MotionLimits] = {}
        self.capabilities: Optional[MotionCapabilities] = None
        self.is_homed = False
        self.event_callbacks: List[Callable] = []
    
    # Connection Management
    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to motion controller
        
        Returns:
            True if connection successful
            
        Raises:
            MotionControlError: If connection fails
        """
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """
        Disconnect from motion controller
        
        Returns:
            True if disconnection successful
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if controller is connected"""
        pass
    
    # Status and Information
    @abstractmethod
    async def get_status(self) -> MotionStatus:
        """Get current motion controller status"""
        pass
    
    @abstractmethod
    async def get_position(self) -> Position4D:
        """Get current position from controller"""
        pass
    
    @abstractmethod
    async def get_capabilities(self) -> MotionCapabilities:
        """Get motion controller capabilities"""
        pass
    
    # Motion Commands
    @abstractmethod
    async def move_to_position(self, position: Position4D, feedrate: Optional[float] = None) -> bool:
        """
        Move to absolute position
        
        Args:
            position: Target position
            feedrate: Movement speed (mm/min or degrees/min)
            
        Returns:
            True if movement initiated successfully
            
        Raises:
            MotionControlError: If movement fails or is invalid
        """
        pass
    
    @abstractmethod
    async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
        """
        Move relative to current position
        
        Args:
            delta: Relative movement
            feedrate: Movement speed
            
        Returns:
            True if movement initiated successfully
        """
        pass
    
    @abstractmethod
    async def rapid_move(self, position: Position4D) -> bool:
        """
        Rapid (non-linear) movement to position
        
        Args:
            position: Target position
            
        Returns:
            True if movement initiated successfully
        """
        pass
    
    # Homing and Calibration
    @abstractmethod
    async def home_all_axes(self) -> bool:
        """
        Home all axes
        
        Returns:
            True if homing successful
            
        Raises:
            MotionControlError: If homing fails
        """
        pass
    
    @abstractmethod
    async def home_axis(self, axis: str) -> bool:
        """
        Home specific axis
        
        Args:
            axis: Axis name ('x', 'y', 'z', 'c')
            
        Returns:
            True if homing successful
        """
        pass
    
    @abstractmethod
    async def set_position(self, position: Position4D) -> bool:
        """
        Set current position (coordinate system origin)
        
        Args:
            position: Position to set as current
            
        Returns:
            True if position set successfully
        """
        pass
    
    # Safety and Control
    @abstractmethod
    async def emergency_stop(self) -> bool:
        """
        Immediately stop all motion
        
        Returns:
            True if emergency stop executed
        """
        pass
    
    @abstractmethod
    async def pause_motion(self) -> bool:
        """
        Pause current motion (can be resumed)
        
        Returns:
            True if motion paused
        """
        pass
    
    @abstractmethod
    async def resume_motion(self) -> bool:
        """
        Resume paused motion
        
        Returns:
            True if motion resumed
        """
        pass
    
    @abstractmethod
    async def cancel_motion(self) -> bool:
        """
        Cancel current motion
        
        Returns:
            True if motion cancelled
        """
        pass
    
    # Configuration and Limits
    @abstractmethod
    async def set_motion_limits(self, axis: str, limits: MotionLimits) -> bool:
        """
        Set motion limits for an axis
        
        Args:
            axis: Axis name
            limits: Motion limits
            
        Returns:
            True if limits set successfully
        """
        pass
    
    @abstractmethod
    async def get_motion_limits(self, axis: str) -> MotionLimits:
        """Get motion limits for an axis"""
        pass
    
    # Advanced Features
    @abstractmethod
    async def execute_gcode(self, gcode: str) -> bool:
        """
        Execute raw G-code command
        
        Args:
            gcode: G-code command string
            
        Returns:
            True if command executed successfully
        """
        pass
    
    @abstractmethod
    async def wait_for_motion_complete(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for all motion to complete
        
        Args:
            timeout: Maximum wait time in seconds
            
        Returns:
            True if motion completed within timeout
        """
        pass
    
    # Event Handling
    def add_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Add callback for motion events"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Remove event callback"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def _notify_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Notify all event callbacks"""
        from core.events import ScannerEvent, EventPriority
        
        event = ScannerEvent(
            event_type=event_type,
            data=data or {},
            source_module="motion",
            priority=EventPriority.NORMAL
        )
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                # Log error but don't stop other callbacks
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in motion event callback: {e}")
    
    # Utility Methods
    def validate_position(self, position: Position4D) -> bool:
        """
        Validate position against motion limits
        
        Args:
            position: Position to validate
            
        Returns:
            True if position is valid
            
        Raises:
            MotionControlError: If position is invalid
        """
        for axis, value in position.to_dict().items():
            if axis in self.motion_limits:
                limits = self.motion_limits[axis]
                if not limits.is_within_limits(value):
                    raise MotionControlError(
                        f"Position {value} exceeds limits for {axis} axis "
                        f"(min: {limits.min_limit}, max: {limits.max_limit})"
                    )
        return True
    
    def get_axis_type(self, axis: str) -> AxisType:
        """Get the type of an axis (linear or rotational)"""
        rotational_axes = ['z', 'c']  # Z is turntable, C is camera tilt
        return AxisType.ROTATIONAL if axis.lower() in rotational_axes else AxisType.LINEAR
    
    def calculate_move_time(self, start: Position4D, end: Position4D, feedrate: float) -> float:
        """
        Estimate time for movement between positions
        
        Args:
            start: Starting position
            end: Ending position
            feedrate: Movement feedrate
            
        Returns:
            Estimated move time in seconds
        """
        distance = start.distance_to(end)
        if distance == 0:
            return 0.0
        
        # Convert feedrate from per-minute to per-second
        feedrate_per_second = feedrate / 60.0
        return distance / feedrate_per_second if feedrate_per_second > 0 else 0.0


# Utility functions for working with motion controllers
def create_safe_position(x: float = 0.0, y: float = 0.0, z: float = 0.0, c: float = 0.0) -> Position4D:
    """Create a position with default safe values"""
    return Position4D(x=x, y=y, z=z, c=c)


def interpolate_positions(start: Position4D, end: Position4D, steps: int) -> List[Position4D]:
    """
    Create interpolated positions between start and end
    
    Args:
        start: Starting position
        end: Ending position
        steps: Number of intermediate steps
        
    Returns:
        List of interpolated positions
    """
    if steps <= 0:
        return [end]
    
    positions = []
    for i in range(steps + 1):
        t = i / steps
        
        pos = Position4D(
            x=start.x + (end.x - start.x) * t,
            y=start.y + (end.y - start.y) * t,
            z=start.z + (end.z - start.z) * t,
            c=start.c + (end.c - start.c) * t
        )
        positions.append(pos)
    
    return positions