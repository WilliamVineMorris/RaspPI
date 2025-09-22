"""
Scan Pattern Definitions

This module defines abstract and concrete scan patterns for 3D scanning.
Each pattern generates a sequence of positions and capture parameters
for systematic object coverage.
"""

import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Iterator, List, Optional, Tuple, Dict, Any

from core.types import Position4D, CameraSettings
from core.events import EventBus, ScannerEvent

logger = logging.getLogger(__name__)

class PatternType(Enum):
    """Types of scan patterns"""
    GRID = "grid"
    SPIRAL = "spiral"  
    ADAPTIVE = "adaptive"
    CUSTOM = "custom"

@dataclass
class ScanPoint:
    """Single point in a scan pattern"""
    position: Position4D
    camera_settings: Optional[CameraSettings] = None
    lighting_settings: Optional[Dict[str, Any]] = None
    capture_count: int = 1  # Number of images at this position
    dwell_time: float = 0.5  # Time to wait before capture (seconds)
    
    def __post_init__(self):
        """Validate scan point parameters"""
        if self.capture_count < 1:
            raise ValueError("Capture count must be at least 1")
        if self.dwell_time < 0:
            raise ValueError("Dwell time cannot be negative")

@dataclass  
class PatternParameters:
    """Base parameters for scan patterns"""
    # Coverage area (in object coordinate system)
    min_x: float = -100.0
    max_x: float = 100.0
    min_y: float = -100.0  
    max_y: float = 100.0
    min_z: float = -50.0
    max_z: float = 50.0
    min_c: float = -30.0  # Rotation angle range
    max_c: float = 30.0
    
    # Quality settings
    overlap_percentage: float = 30.0  # Image overlap for reconstruction
    max_distance: float = 150.0  # Maximum distance from object
    
    # Safety and limits
    max_feedrate: float = 1000.0  # mm/min
    safety_margin: float = 5.0  # Safety margin from limits
    
    def __post_init__(self):
        """Validate parameters"""
        if self.min_x >= self.max_x:
            raise ValueError("min_x must be less than max_x")
        if self.min_y >= self.max_y:
            raise ValueError("min_y must be less than max_y")
        if self.min_z >= self.max_z:
            raise ValueError("min_z must be less than max_z")
        if self.min_c >= self.max_c:
            raise ValueError("min_c must be less than max_c")
        if self.overlap_percentage < 0 or self.overlap_percentage > 90:
            raise ValueError("Overlap percentage must be between 0-90%")

class ScanPattern(ABC):
    """
    Abstract base class for all scan patterns
    
    Defines the interface for generating systematic scan positions
    for 3D object reconstruction.
    """
    
    def __init__(self, pattern_id: str, parameters: PatternParameters):
        self.pattern_id = pattern_id
        self.parameters = parameters
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._points_cache: Optional[List[ScanPoint]] = None
        self._current_index = 0
        
    @property
    @abstractmethod
    def pattern_type(self) -> PatternType:
        """Return the pattern type"""
        pass
    
    @property
    @abstractmethod
    def estimated_duration(self) -> float:
        """Estimate total scan duration in minutes"""
        pass
    
    @abstractmethod
    def generate_points(self) -> List[ScanPoint]:
        """
        Generate all scan points for this pattern
        
        Returns:
            List of ScanPoint objects defining the scan sequence
        """
        pass
    
    def get_points(self, use_cache: bool = True) -> List[ScanPoint]:
        """
        Get scan points, optionally using cache
        
        Args:
            use_cache: Whether to use cached points if available
            
        Returns:
            List of scan points
        """
        if not use_cache or self._points_cache is None:
            self.logger.info(f"Generating scan points for pattern {self.pattern_id}")
            self._points_cache = self.generate_points()
            self.logger.info(f"Generated {len(self._points_cache)} scan points")
            
        return self._points_cache
    
    def __iter__(self) -> Iterator[ScanPoint]:
        """Make pattern iterable"""
        self._current_index = 0
        return self
    
    def __next__(self) -> ScanPoint:
        """Iterator protocol"""
        points = self.get_points()
        if self._current_index >= len(points):
            raise StopIteration
        
        point = points[self._current_index]
        self._current_index += 1
        return point
    
    def __len__(self) -> int:
        """Return number of scan points"""
        return len(self.get_points())
    
    def validate_point(self, point: ScanPoint) -> bool:
        """
        Validate that a scan point is within safe limits
        
        Args:
            point: Scan point to validate
            
        Returns:
            True if point is valid and safe
        """
        pos = point.position
        params = self.parameters
        
        # Check coordinate limits with safety margin
        margin = params.safety_margin
        
        if not (params.min_x + margin <= pos.x <= params.max_x - margin):
            self.logger.warning(f"Point X {pos.x} outside safe limits")
            return False
            
        if not (params.min_y + margin <= pos.y <= params.max_y - margin):
            self.logger.warning(f"Point Y {pos.y} outside safe limits") 
            return False
            
        if not (params.min_z + margin <= pos.z <= params.max_z - margin):
            self.logger.warning(f"Point Z {pos.z} outside safe limits")
            return False
            
        if not (params.min_c + margin <= pos.c <= params.max_c - margin):
            self.logger.warning(f"Point C {pos.c} outside safe limits")
            return False
            
        return True
    
    def get_progress_info(self) -> Dict[str, Any]:
        """
        Get pattern progress information
        
        Returns:
            Dictionary with progress details
        """
        points = self.get_points()
        total_points = len(points)
        
        return {
            'pattern_id': self.pattern_id,
            'pattern_type': self.pattern_type.value,
            'total_points': total_points,
            'current_index': self._current_index,
            'progress_percentage': (self._current_index / total_points * 100) if total_points > 0 else 0,
            'estimated_duration': self.estimated_duration,
            'parameters': self.parameters
        }
    
    def reset(self):
        """Reset pattern iterator to beginning"""
        self._current_index = 0
    
    def calculate_field_of_view(self, distance: float, camera_angle: float = 60.0) -> Tuple[float, float]:
        """
        Calculate field of view dimensions at given distance
        
        Args:
            distance: Distance from camera to object
            camera_angle: Camera field of view angle in degrees
            
        Returns:
            Tuple of (width, height) of field of view
        """
        # Convert angle to radians
        angle_rad = math.radians(camera_angle)
        
        # Calculate field of view width/height 
        fov_width = 2 * distance * math.tan(angle_rad / 2)
        
        # Assume 4:3 aspect ratio
        fov_height = fov_width * 0.75
        
        return fov_width, fov_height
    
    def calculate_overlap_spacing(self, fov_width: float, fov_height: float) -> Tuple[float, float]:
        """
        Calculate spacing between points for desired overlap
        
        Args:
            fov_width: Field of view width
            fov_height: Field of view height
            
        Returns:
            Tuple of (x_spacing, y_spacing)
        """
        overlap_factor = (100 - self.parameters.overlap_percentage) / 100
        
        x_spacing = fov_width * overlap_factor
        y_spacing = fov_height * overlap_factor
        
        return x_spacing, y_spacing


@dataclass
class GridPatternParameters(PatternParameters):
    """Parameters specific to grid scan pattern"""
    # Grid spacing (if 0, calculated from overlap)
    x_spacing: float = 0.0  
    y_spacing: float = 0.0
    z_spacing: float = 20.0  # Depth layers
    c_steps: int = 5  # Number of rotation positions
    
    # Scanning strategy
    zigzag: bool = True  # Use zigzag pattern for efficiency
    spiral_outward: bool = False  # Spiral from center outward
    
    # Multi-exposure options
    bracket_exposures: bool = False  # Take multiple exposures per point
    exposure_steps: int = 3  # Number of exposure brackets


class GridScanPattern(ScanPattern):
    """
    Grid-based scan pattern for systematic coverage
    
    Creates a regular grid of positions with optional rotation angles
    for comprehensive object capture. Supports zigzag traversal for
    efficiency and various optimization strategies.
    """
    
    def __init__(self, pattern_id: str, parameters: GridPatternParameters):
        super().__init__(pattern_id, parameters)
        self.grid_params = parameters
        
    @property
    def pattern_type(self) -> PatternType:
        return PatternType.GRID
    
    @property
    def estimated_duration(self) -> float:
        """Estimate scan duration based on points and timing"""
        points = self.get_points()
        
        # Base time per point (movement + settling + capture)
        time_per_point = 15.0  # seconds
        
        # Add time for exposure bracketing
        if self.grid_params.bracket_exposures:
            time_per_point *= self.grid_params.exposure_steps
            
        # Add movement time estimation
        avg_movement_time = 5.0  # seconds per movement
        
        total_time = len(points) * (time_per_point + avg_movement_time)
        
        return total_time / 60.0  # Convert to minutes
    
    def generate_points(self) -> List[ScanPoint]:
        """Generate grid scan points"""
        points = []
        
        # Calculate grid spacing if not provided
        x_spacing, y_spacing = self._calculate_spacing()
        z_spacing = self.grid_params.z_spacing
        
        # Generate grid coordinates
        x_positions = self._generate_axis_positions(
            self.parameters.min_x, self.parameters.max_x, x_spacing
        )
        y_positions = self._generate_axis_positions(
            self.parameters.min_y, self.parameters.max_y, y_spacing
        )
        z_positions = self._generate_axis_positions(
            self.parameters.min_z, self.parameters.max_z, z_spacing
        )
        c_positions = self._generate_rotation_positions()
        
        self.logger.info(f"Grid dimensions: {len(x_positions)}x{len(y_positions)}x{len(z_positions)}x{len(c_positions)}")
        
        # Generate points in efficient order
        for z in z_positions:
            for c in c_positions:
                # Alternate Y direction for zigzag
                y_coords = y_positions if not self.grid_params.zigzag else y_positions
                
                for y_idx, y in enumerate(y_coords):
                    # Alternate X direction on alternate Y rows for zigzag
                    x_coords = x_positions
                    if self.grid_params.zigzag and y_idx % 2 == 1:
                        x_coords = list(reversed(x_positions))
                    
                    for x in x_coords:
                        position = Position4D(x=x, y=y, z=z, c=c)
                        
                        # Create scan point with appropriate settings
                        scan_point = ScanPoint(
                            position=position,
                            camera_settings=self._get_camera_settings(position),
                            lighting_settings=self._get_lighting_settings(position),
                            capture_count=self.grid_params.exposure_steps if self.grid_params.bracket_exposures else 1,
                            dwell_time=0.5
                        )
                        
                        # Validate point before adding
                        if self.validate_point(scan_point):
                            points.append(scan_point)
                        else:
                            self.logger.warning(f"Skipping invalid point: {position}")
        
        self.logger.info(f"Generated {len(points)} valid grid points")
        return points
    
    def _calculate_spacing(self) -> Tuple[float, float]:
        """Calculate grid spacing based on parameters"""
        # Use provided spacing if available
        if self.grid_params.x_spacing > 0 and self.grid_params.y_spacing > 0:
            return self.grid_params.x_spacing, self.grid_params.y_spacing
        
        # Calculate spacing based on overlap and field of view
        # Estimate distance as middle of Z range
        avg_distance = (self.parameters.min_z + self.parameters.max_z) / 2
        avg_distance = abs(avg_distance)  # Distance is positive
        
        # Calculate field of view at average distance
        fov_width, fov_height = self.calculate_field_of_view(avg_distance)
        
        # Calculate spacing for desired overlap
        x_spacing, y_spacing = self.calculate_overlap_spacing(fov_width, fov_height)
        
        self.logger.info(f"Calculated spacing: X={x_spacing:.1f}mm, Y={y_spacing:.1f}mm")
        return x_spacing, y_spacing
    
    def _generate_axis_positions(self, min_val: float, max_val: float, spacing: float) -> List[float]:
        """Generate positions along an axis"""
        if spacing <= 0:
            return [min_val]
            
        positions = []
        current = min_val
        
        while current <= max_val:
            positions.append(current)
            current += spacing
            
        # Ensure we include the max value if not already included
        if len(positions) > 0 and positions[-1] < max_val:
            positions.append(max_val)
            
        return positions
    
    def _generate_rotation_positions(self) -> List[float]:
        """Generate rotation positions"""
        c_steps = self.grid_params.c_steps
        
        if c_steps <= 1:
            return [0.0]  # No rotation
            
        # Generate evenly spaced rotation angles
        c_range = self.parameters.max_c - self.parameters.min_c
        step_size = c_range / (c_steps - 1) if c_steps > 1 else 0
        
        positions = []
        for i in range(c_steps):
            angle = self.parameters.min_c + (i * step_size)
            positions.append(angle)
            
        return positions
    
    def _get_camera_settings(self, position: Position4D) -> Optional[CameraSettings]:
        """Get camera settings for position (can be customized)"""
        # For now, return None to use default settings
        # This can be enhanced to adjust settings based on position
        return None
    
    def _get_lighting_settings(self, position: Position4D) -> Optional[Dict[str, Any]]:
        """Get lighting settings for position (can be customized)"""
        # For now, return None to use default settings
        # This can be enhanced to adjust lighting based on position/angle
        return None


# Additional pattern types can be added here (SpiralScanPattern, etc.)