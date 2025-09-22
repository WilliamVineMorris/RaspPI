"""
Abstract Scan Path Planning Interface

Defines the standard interface for scan path planning and generation.
This enables support for different scanning strategies while maintaining
consistent API for 4DOF path generation and optimization.

Author: Scanner System Development
Created: September 2025
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable, Union
from enum import Enum
import asyncio
from pathlib import Path

from core.exceptions import PathPlanningError
from core.events import ScannerEvent
from motion.base import Position4D


class ScanStrategy(Enum):
    """Scanning strategy types"""
    SPIRAL = "spiral"           # Spiral scanning pattern
    GRID = "grid"               # Grid-based scanning
    ADAPTIVE = "adaptive"       # Adaptive based on object geometry
    MANUAL = "manual"           # Manual point selection
    PHOTOGRAMMETRY = "photogrammetry"  # Photogrammetry optimized
    FEATURE_BASED = "feature_based"    # Feature-driven scanning


class PathOptimization(Enum):
    """Path optimization strategies"""
    NONE = "none"               # No optimization
    SHORTEST = "shortest"       # Minimize total path length
    TIME = "time"               # Minimize scan time
    QUALITY = "quality"         # Optimize for scan quality
    ENERGY = "energy"           # Minimize energy consumption


class CollisionMode(Enum):
    """Collision detection modes"""
    DISABLED = "disabled"       # No collision detection
    BASIC = "basic"             # Basic geometric collision detection
    ADVANCED = "advanced"       # Advanced physics-based detection


@dataclass
class ScanBounds:
    """3D scanning bounds definition"""
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float  # Minimum rotation angle
    z_max: float  # Maximum rotation angle
    c_min: float  # Minimum tilt angle
    c_max: float  # Maximum tilt angle
    
    def contains_position(self, position: Position4D) -> bool:
        """Check if position is within bounds"""
        return (self.x_min <= position.x <= self.x_max and
                self.y_min <= position.y <= self.y_max and
                self.z_min <= position.z <= self.z_max and
                self.c_min <= position.c <= self.c_max)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for serialization"""
        return {
            'x_min': self.x_min, 'x_max': self.x_max,
            'y_min': self.y_min, 'y_max': self.y_max,
            'z_min': self.z_min, 'z_max': self.z_max,
            'c_min': self.c_min, 'c_max': self.c_max
        }


@dataclass
class ScanParameters:
    """Scan configuration parameters"""
    strategy: ScanStrategy
    bounds: ScanBounds
    resolution: float  # Spatial resolution in mm
    angular_resolution: float  # Angular resolution in degrees
    overlap_percentage: float = 20.0  # Image overlap percentage
    optimization: PathOptimization = PathOptimization.TIME
    collision_mode: CollisionMode = CollisionMode.BASIC
    speed_factor: float = 1.0  # Speed scaling factor (0.1-2.0)
    
    def __post_init__(self):
        # Validation
        if not 0.1 <= self.speed_factor <= 2.0:
            raise ValueError("Speed factor must be between 0.1 and 2.0")
        if not 0.0 <= self.overlap_percentage <= 95.0:
            raise ValueError("Overlap percentage must be between 0 and 95")
        if self.resolution <= 0:
            raise ValueError("Resolution must be positive")
        if self.angular_resolution <= 0:
            raise ValueError("Angular resolution must be positive")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'strategy': self.strategy.value,
            'bounds': self.bounds.to_dict(),
            'resolution': self.resolution,
            'angular_resolution': self.angular_resolution,
            'overlap_percentage': self.overlap_percentage,
            'optimization': self.optimization.value,
            'collision_mode': self.collision_mode.value,
            'speed_factor': self.speed_factor
        }


@dataclass
class ScanPoint:
    """Individual scan point with metadata"""
    position: Position4D
    sequence_number: int
    lighting_zones: List[str]  # LED zones to activate
    camera_settings: Optional[Dict[str, Any]] = None
    lighting_settings: Optional[Dict[str, Any]] = None
    estimated_duration: Optional[float] = None  # seconds
    priority: int = 0  # Higher priority scanned first
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'position': self.position.to_dict(),
            'sequence_number': self.sequence_number,
            'lighting_zones': self.lighting_zones,
            'camera_settings': self.camera_settings,
            'lighting_settings': self.lighting_settings,
            'estimated_duration': self.estimated_duration,
            'priority': self.priority
        }


@dataclass
class ScanPath:
    """Complete scan path with metadata"""
    points: List[ScanPoint]
    parameters: ScanParameters
    total_estimated_time: float  # seconds
    total_distance: float  # mm
    path_id: str
    created_timestamp: float
    
    @property
    def point_count(self) -> int:
        """Number of scan points"""
        return len(self.points)
    
    @property
    def estimated_hours(self) -> float:
        """Estimated scan time in hours"""
        return self.total_estimated_time / 3600.0
    
    def get_point_by_sequence(self, sequence: int) -> Optional[ScanPoint]:
        """Get scan point by sequence number"""
        for point in self.points:
            if point.sequence_number == sequence:
                return point
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'points': [point.to_dict() for point in self.points],
            'parameters': self.parameters.to_dict(),
            'total_estimated_time': self.total_estimated_time,
            'total_distance': self.total_distance,
            'path_id': self.path_id,
            'created_timestamp': self.created_timestamp
        }


@dataclass
class PathValidationResult:
    """Result of path validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    collision_points: List[int]  # Sequence numbers of collision points
    
    @property
    def has_errors(self) -> bool:
        """Check if validation found errors"""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if validation found warnings"""
        return len(self.warnings) > 0


class PathPlanner(ABC):
    """
    Abstract base class for scan path planning systems
    
    This interface supports generation and optimization of 4DOF scan paths
    for various scanning strategies and object types.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.current_path: Optional[ScanPath] = None
        self.saved_paths: Dict[str, ScanPath] = {}
        self.event_callbacks: List[Callable] = []
        self.planning_active = False
    
    # Path Generation
    @abstractmethod
    async def generate_path(self, parameters: ScanParameters) -> ScanPath:
        """
        Generate scan path based on parameters
        
        Args:
            parameters: Scan configuration parameters
            
        Returns:
            Generated scan path
            
        Raises:
            PathPlanningError: If path generation fails
        """
        pass
    
    @abstractmethod
    async def generate_spiral_path(self, bounds: ScanBounds, resolution: float, 
                                  angular_step: float) -> ScanPath:
        """
        Generate spiral scanning pattern
        
        Args:
            bounds: Scanning bounds
            resolution: Spatial resolution in mm
            angular_step: Angular step size in degrees
            
        Returns:
            Spiral scan path
        """
        pass
    
    @abstractmethod
    async def generate_grid_path(self, bounds: ScanBounds, x_points: int, 
                                y_points: int, z_angles: int, c_angles: int) -> ScanPath:
        """
        Generate grid-based scanning pattern
        
        Args:
            bounds: Scanning bounds
            x_points: Number of X-axis points
            y_points: Number of Y-axis points
            z_angles: Number of Z-axis angles
            c_angles: Number of C-axis angles
            
        Returns:
            Grid scan path
        """
        pass
    
    @abstractmethod
    async def generate_adaptive_path(self, object_geometry: Dict[str, Any], 
                                   target_quality: float) -> ScanPath:
        """
        Generate adaptive path based on object geometry
        
        Args:
            object_geometry: Object geometry information
            target_quality: Target scan quality (0.0-1.0)
            
        Returns:
            Adaptive scan path
        """
        pass
    
    # Path Optimization
    @abstractmethod
    async def optimize_path(self, path: ScanPath, optimization: PathOptimization) -> ScanPath:
        """
        Optimize scan path using specified strategy
        
        Args:
            path: Original scan path
            optimization: Optimization strategy
            
        Returns:
            Optimized scan path
        """
        pass
    
    @abstractmethod
    async def minimize_travel_time(self, path: ScanPath) -> ScanPath:
        """
        Optimize path to minimize travel time
        
        Args:
            path: Original scan path
            
        Returns:
            Time-optimized scan path
        """
        pass
    
    @abstractmethod
    async def add_scan_point(self, path: ScanPath, position: Position4D, 
                           sequence: Optional[int] = None) -> ScanPath:
        """
        Add scan point to existing path
        
        Args:
            path: Existing scan path
            position: New scan position
            sequence: Optional sequence number (auto-assigned if None)
            
        Returns:
            Updated scan path
        """
        pass
    
    @abstractmethod
    async def remove_scan_point(self, path: ScanPath, sequence: int) -> ScanPath:
        """
        Remove scan point from path
        
        Args:
            path: Existing scan path
            sequence: Sequence number to remove
            
        Returns:
            Updated scan path
        """
        pass
    
    # Path Validation
    @abstractmethod
    async def validate_path(self, path: ScanPath) -> PathValidationResult:
        """
        Validate scan path for safety and feasibility
        
        Args:
            path: Scan path to validate
            
        Returns:
            Validation result
        """
        pass
    
    @abstractmethod
    async def check_collisions(self, path: ScanPath) -> List[int]:
        """
        Check for potential collisions in path
        
        Args:
            path: Scan path to check
            
        Returns:
            List of sequence numbers with potential collisions
        """
        pass
    
    @abstractmethod
    async def validate_motion_limits(self, path: ScanPath) -> bool:
        """
        Validate that all path points are within motion limits
        
        Args:
            path: Scan path to validate
            
        Returns:
            True if all points are within limits
        """
        pass
    
    # Path Analysis
    @abstractmethod
    async def estimate_scan_time(self, path: ScanPath) -> float:
        """
        Estimate total scan time for path
        
        Args:
            path: Scan path to analyze
            
        Returns:
            Estimated scan time in seconds
        """
        pass
    
    @abstractmethod
    async def calculate_path_statistics(self, path: ScanPath) -> Dict[str, Any]:
        """
        Calculate detailed path statistics
        
        Args:
            path: Scan path to analyze
            
        Returns:
            Dictionary with path statistics
        """
        pass
    
    @abstractmethod
    async def analyze_coverage(self, path: ScanPath, object_bounds: ScanBounds) -> float:
        """
        Analyze scan coverage percentage
        
        Args:
            path: Scan path to analyze
            object_bounds: Object bounds for coverage calculation
            
        Returns:
            Coverage percentage (0.0-100.0)
        """
        pass
    
    # Path Management
    @abstractmethod
    async def save_path(self, path: ScanPath, file_path: Path) -> bool:
        """
        Save scan path to file
        
        Args:
            path: Scan path to save
            file_path: Destination file path
            
        Returns:
            True if save successful
        """
        pass
    
    @abstractmethod
    async def load_path(self, file_path: Path) -> ScanPath:
        """
        Load scan path from file
        
        Args:
            file_path: Path file to load
            
        Returns:
            Loaded scan path
            
        Raises:
            PathPlanningError: If load fails
        """
        pass
    
    @abstractmethod
    async def list_saved_paths(self, directory: Path) -> List[str]:
        """
        List saved path files in directory
        
        Args:
            directory: Directory to search
            
        Returns:
            List of path file names
        """
        pass
    
    # Interactive Planning
    @abstractmethod
    async def start_interactive_planning(self, initial_bounds: ScanBounds) -> bool:
        """
        Start interactive path planning session
        
        Args:
            initial_bounds: Initial scanning bounds
            
        Returns:
            True if interactive session started
        """
        pass
    
    @abstractmethod
    async def preview_point(self, position: Position4D) -> Dict[str, Any]:
        """
        Preview scan point before adding to path
        
        Args:
            position: Position to preview
            
        Returns:
            Preview information (visibility, lighting, etc.)
        """
        pass
    
    @abstractmethod
    async def get_suggested_points(self, current_path: ScanPath, count: int = 5) -> List[Position4D]:
        """
        Get suggested next scan points
        
        Args:
            current_path: Current scan path
            count: Number of suggestions to return
            
        Returns:
            List of suggested positions
        """
        pass
    
    # Event Handling
    def add_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Add callback for planning events"""
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
            source_module="planning",
            priority=EventPriority.NORMAL
        )
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in planning event callback: {e}")
    
    # Utility Methods
    def create_default_bounds(self) -> ScanBounds:
        """Create default scanning bounds"""
        return ScanBounds(
            x_min=0.0, x_max=200.0,
            y_min=0.0, y_max=200.0,
            z_min=0.0, z_max=360.0,
            c_min=-90.0, c_max=90.0
        )
    
    def estimate_point_duration(self, point: ScanPoint) -> float:
        """
        Estimate duration for single scan point
        
        Args:
            point: Scan point to estimate
            
        Returns:
            Estimated duration in seconds
        """
        base_time = 2.0  # Base capture time
        
        # Add time for lighting zones
        lighting_time = len(point.lighting_zones) * 0.1
        
        # Add time for camera settings
        settings_time = 0.5 if point.camera_settings else 0.0
        
        return base_time + lighting_time + settings_time
    
    def calculate_movement_time(self, from_pos: Position4D, to_pos: Position4D, speed_factor: float = 1.0) -> float:
        """
        Calculate movement time between positions
        
        Args:
            from_pos: Starting position
            to_pos: Target position
            speed_factor: Speed scaling factor
            
        Returns:
            Movement time in seconds
        """
        # Base movement speeds (units/second)
        linear_speed = 50.0  # mm/s
        angular_speed = 90.0  # degrees/s
        
        # Calculate movement distances
        linear_dist = ((to_pos.x - from_pos.x)**2 + (to_pos.y - from_pos.y)**2)**0.5
        z_dist = abs(to_pos.z - from_pos.z)
        c_dist = abs(to_pos.c - from_pos.c)
        
        # Calculate movement times
        linear_time = linear_dist / (linear_speed * speed_factor)
        z_time = z_dist / (angular_speed * speed_factor)
        c_time = c_dist / (angular_speed * speed_factor)
        
        # Return maximum time (limiting axis)
        return max(linear_time, z_time, c_time)


# Utility functions for path planning
def create_photogrammetry_parameters(bounds: ScanBounds, overlap: float = 60.0) -> ScanParameters:
    """Create parameters optimized for photogrammetry"""
    return ScanParameters(
        strategy=ScanStrategy.PHOTOGRAMMETRY,
        bounds=bounds,
        resolution=1.0,  # 1mm resolution
        angular_resolution=15.0,  # 15-degree steps
        overlap_percentage=overlap,
        optimization=PathOptimization.QUALITY
    )


def create_quick_scan_parameters(bounds: ScanBounds) -> ScanParameters:
    """Create parameters for quick preview scan"""
    return ScanParameters(
        strategy=ScanStrategy.GRID,
        bounds=bounds,
        resolution=5.0,  # 5mm resolution
        angular_resolution=45.0,  # 45-degree steps
        overlap_percentage=10.0,
        optimization=PathOptimization.TIME,
        speed_factor=1.5
    )


def validate_scan_bounds(bounds: ScanBounds, hardware_limits: Dict[str, Tuple[float, float]]) -> bool:
    """
    Validate scan bounds against hardware limits
    
    Args:
        bounds: Scan bounds to validate
        hardware_limits: Hardware limits dict with (min, max) tuples
        
    Returns:
        True if bounds are within hardware limits
    """
    limits = hardware_limits
    
    return (limits['x'][0] <= bounds.x_min <= bounds.x_max <= limits['x'][1] and
            limits['y'][0] <= bounds.y_min <= bounds.y_max <= limits['y'][1] and
            limits['z'][0] <= bounds.z_min <= bounds.z_max <= limits['z'][1] and
            limits['c'][0] <= bounds.c_min <= bounds.c_max <= limits['c'][1])