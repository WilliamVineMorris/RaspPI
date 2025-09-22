"""
Core Data Types for Scanner System

Defines common data types used throughout the scanner system for
position tracking, camera settings, and system state management.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any

@dataclass
class Position4D:
    """4-axis position in scanner coordinate system"""
    x: float  # X-axis position (mm)
    y: float  # Y-axis position (mm) 
    z: float  # Z-axis position (mm)
    c: float  # C-axis rotation (degrees)
    
    def __post_init__(self):
        """Validate position values"""
        # Basic validation - could be expanded with actual limits
        if not (-1000 <= self.x <= 1000):
            raise ValueError(f"X position {self.x} out of range [-1000, 1000]")
        if not (-1000 <= self.y <= 1000):
            raise ValueError(f"Y position {self.y} out of range [-1000, 1000]")
        if not (-500 <= self.z <= 500):
            raise ValueError(f"Z position {self.z} out of range [-500, 500]")
        if not (-360 <= self.c <= 360):
            raise ValueError(f"C rotation {self.c} out of range [-360, 360]")
    
    def distance_to(self, other: 'Position4D') -> float:
        """Calculate 3D distance to another position (ignoring rotation)"""
        return ((self.x - other.x)**2 + (self.y - other.y)**2 + (self.z - other.z)**2)**0.5
    
    def __str__(self) -> str:
        return f"Position4D(x={self.x:.2f}, y={self.y:.2f}, z={self.z:.2f}, c={self.c:.2f})"

@dataclass
class CameraSettings:
    """Camera capture settings"""
    exposure_time: Optional[float] = None  # Exposure time in seconds
    iso: Optional[int] = None              # ISO setting
    white_balance: Optional[str] = None    # White balance mode
    focus_distance: Optional[float] = None # Focus distance in mm
    capture_format: str = "JPEG"           # Image format
    resolution: tuple[int, int] = (4624, 3472)  # Image resolution (width, height)
    
    def __post_init__(self):
        """Validate camera settings"""
        if self.exposure_time is not None and self.exposure_time <= 0:
            raise ValueError("Exposure time must be positive")
        if self.iso is not None and not (100 <= self.iso <= 6400):
            raise ValueError("ISO must be between 100 and 6400")
        if self.focus_distance is not None and self.focus_distance < 0:
            raise ValueError("Focus distance cannot be negative")

@dataclass
class SystemStatus:
    """Overall system status"""
    motion_connected: bool = False
    cameras_ready: bool = False
    lighting_ready: bool = False
    emergency_stop: bool = False
    current_position: Optional[Position4D] = None
    active_scan_id: Optional[str] = None
    
    @property
    def system_ready(self) -> bool:
        """True if all critical systems are ready"""
        return (self.motion_connected and 
                self.cameras_ready and 
                not self.emergency_stop)

@dataclass
class CalibrationData:
    """Camera and system calibration data"""
    camera_matrix: Optional[list] = None      # Camera intrinsic matrix
    distortion_coeffs: Optional[list] = None # Distortion coefficients  
    stereo_baseline: Optional[float] = None   # Distance between cameras (mm)
    coordinate_transform: Optional[Dict[str, Any]] = None  # World to camera transform
    
    def is_calibrated(self) -> bool:
        """Check if essential calibration data is available"""
        return (self.camera_matrix is not None and 
                self.distortion_coeffs is not None)