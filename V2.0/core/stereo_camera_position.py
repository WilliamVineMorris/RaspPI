"""
Stereo Camera Position Calculator for Photogrammetry

This module calculates the 3D positions and orientations of stereo cameras
in a dual-camera scanning system for photogrammetry software compatibility
(RealityCapture, Meshroom, etc.).

Stereo Camera Geometry:
=======================
- Two cameras horizontally spaced by baseline distance
- Both aligned with tilt axis (position independent of tilt angle)
- Each camera rotated inward by convergence angle (toe-in)
- Cameras face toward turntable origin

Coordinate System:
==================
- Cartesian 3D coordinates (X, Y, Z in mm)
- Camera orientations as Euler angles (omega, phi, kappa in degrees)
- Origin at turntable center, Z-up convention

Author: Scanner System Development
Created: October 2025
"""

import math
from dataclasses import dataclass
from typing import Tuple, Dict
from core.types import Position4D
from core.coordinate_transform import CoordinateTransformer, CartesianPosition
from core.config_manager import ConfigManager


@dataclass
class CameraPosition3D:
    """3D position and orientation of a camera for photogrammetry"""
    x: float           # mm - X position in world space
    y: float           # mm - Y position in world space
    z: float           # mm - Z position (height) in world space
    omega: float       # degrees - Rotation around X axis (roll)
    phi: float         # degrees - Rotation around Y axis (pitch/tilt)
    kappa: float       # degrees - Rotation around Z axis (yaw/heading)
    camera_id: int     # Camera identifier (0 or 1)
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for export"""
        return {
            'x': self.x,
            'y': self.y,
            'z': self.z,
            'omega': self.omega,
            'phi': self.phi,
            'kappa': self.kappa,
            'camera_id': self.camera_id
        }
    
    def to_realitycapture_line(self, image_name: str) -> str:
        """Format as RealityCapture camera import line"""
        # RealityCapture format: filename X Y Z omega phi kappa
        return f"{image_name} {self.x:.6f} {self.y:.6f} {self.z:.6f} {self.omega:.6f} {self.phi:.6f} {self.kappa:.6f}"
    
    def to_meshroom_line(self, image_name: str) -> str:
        """Format as Meshroom geolocation line"""
        # Meshroom format: filename X Y Z (simpler, no orientation)
        return f"{image_name} {self.x:.6f} {self.y:.6f} {self.z:.6f}"


class StereoCameraPositionCalculator:
    """
    Calculates 3D positions and orientations for stereo camera array.
    
    Handles stereo baseline offset and convergence angles to generate
    accurate camera positions for photogrammetry software.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize calculator with stereo configuration.
        
        Args:
            config_manager: Configuration manager with stereo camera settings
        """
        self.config = config_manager
        self.transformer = CoordinateTransformer(config_manager)
        
        # Load stereo configuration
        self.stereo_enabled = config_manager.get('cameras.stereo.enabled', False)
        self.baseline_mm = float(config_manager.get('cameras.stereo.baseline_mm', 60.0))
        self.convergence_angle_deg = float(config_manager.get('cameras.stereo.convergence_angle_deg', 5.0))
        
    def calculate_stereo_camera_positions(
        self, 
        fluidnc_pos: Position4D,
        camera_id: int | None = None
    ) -> Dict[int, CameraPosition3D]:
        """
        Calculate 3D positions for both stereo cameras at a scan point.
        
        Args:
            fluidnc_pos: FluidNC machine position (X, Y, Z_rotation, C_tilt)
            camera_id: If specified, only calculate for this camera (0 or 1)
            
        Returns:
            Dictionary mapping camera_id to CameraPosition3D
            If camera_id specified, returns dict with single entry
        """
        # Convert FluidNC position to Cartesian center point
        center_cart = self.transformer.fluidnc_to_cartesian(fluidnc_pos)
        
        # Get turntable rotation angle (Z axis in FluidNC)
        turntable_rotation_deg = fluidnc_pos.z
        turntable_rotation_rad = math.radians(turntable_rotation_deg)
        
        # Get camera tilt angle (C axis in FluidNC)
        camera_tilt_deg = fluidnc_pos.c
        
        # Calculate positions for both cameras
        positions = {}
        
        # Determine which cameras to calculate
        cameras_to_calc = [camera_id] if camera_id is not None else [0, 1]
        
        for cam_id in cameras_to_calc:
            if cam_id == 0:
                # Left camera (Camera 0)
                # Offset left (negative) perpendicular to radius
                offset_direction = -1.0
                # Yaw: turntable rotation + convergence (pointing right/inward)
                yaw_offset = self.convergence_angle_deg
            else:
                # Right camera (Camera 1)
                # Offset right (positive) perpendicular to radius
                offset_direction = 1.0
                # Yaw: turntable rotation - convergence (pointing left/inward)
                yaw_offset = -self.convergence_angle_deg
            
            # Calculate camera position offset perpendicular to radial direction
            # Cameras are spaced horizontally along arc perpendicular to radius
            half_baseline = self.baseline_mm / 2.0
            
            # Offset perpendicular to radius (tangent to circle)
            # Perpendicular direction is 90° from radial direction
            perp_angle_rad = turntable_rotation_rad + math.radians(90.0) * offset_direction
            
            cam_x = center_cart.x + half_baseline * math.cos(perp_angle_rad)
            cam_y = center_cart.y + half_baseline * math.sin(perp_angle_rad)
            cam_z = center_cart.z  # Same height (aligned with tilt axis)
            
            # Calculate camera orientation (Euler angles)
            # Omega (roll around X): 0 (cameras are level)
            omega = 0.0
            
            # Phi (pitch/tilt around Y): Same as tilt servo angle
            phi = camera_tilt_deg
            
            # Kappa (yaw/heading around Z): Turntable rotation + convergence offset
            kappa = turntable_rotation_deg + yaw_offset
            
            positions[cam_id] = CameraPosition3D(
                x=cam_x,
                y=cam_y,
                z=cam_z,
                omega=omega,
                phi=phi,
                kappa=kappa,
                camera_id=cam_id
            )
        
        return positions
    
    def calculate_single_camera_position(
        self,
        fluidnc_pos: Position4D,
        camera_id: int
    ) -> CameraPosition3D:
        """
        Calculate 3D position for a single camera.
        
        Args:
            fluidnc_pos: FluidNC machine position
            camera_id: Camera identifier (0 or 1)
            
        Returns:
            CameraPosition3D for the specified camera
        """
        positions = self.calculate_stereo_camera_positions(fluidnc_pos, camera_id)
        return positions[camera_id]
    
    def format_for_gps_exif(self, position: CameraPosition3D) -> Tuple[tuple, tuple, tuple]:
        """
        Format camera position for GPS EXIF tags.
        
        Converts mm to a GPS-compatible rational format. Note: This is a creative
        use of GPS tags for photogrammetry, not actual geographic coordinates.
        
        Args:
            position: CameraPosition3D to convert
            
        Returns:
            Tuple of (latitude_rational, longitude_rational, altitude_rational)
        """
        return (
            self._float_to_gps_rational(position.x),
            self._float_to_gps_rational(position.y),
            self._float_to_gps_rational(position.z)
        )
    
    def _float_to_gps_rational(self, value: float) -> tuple:
        """
        Convert float coordinate to GPS rational format.
        
        GPS EXIF expects (degrees, minutes, seconds) as rational tuples.
        We repurpose this to store millimeter coordinates.
        
        Args:
            value: Coordinate value in mm
            
        Returns:
            Tuple in GPS format: ((degrees, 1), (minutes, 1), (seconds, 100))
        """
        # Handle negative values
        abs_value = abs(value)
        
        # Split into whole and fractional parts
        degrees = int(abs_value)
        fractional = abs_value - degrees
        
        # Convert fractional to "minutes" (0-60)
        minutes = int(fractional * 60)
        
        # Remaining fraction to "seconds" (0-60)
        seconds_fractional = (fractional * 60 - minutes) * 60
        seconds = int(seconds_fractional * 100)  # Store to 0.01 precision
        
        return ((degrees, 1), (minutes, 1), (seconds, 100))
    
    def export_camera_positions_txt(
        self,
        positions_dict: Dict[str, Dict[int, CameraPosition3D]],
        output_path: str,
        format_type: str = "realitycapture"
    ) -> bool:
        """
        Export camera positions to text file for photogrammetry import.
        
        Args:
            positions_dict: Dict mapping image_name to {camera_id: CameraPosition3D}
            output_path: Path to output text file
            format_type: "realitycapture" (full orientation) or "meshroom" (position only)
            
        Returns:
            True if export successful
        """
        try:
            with open(output_path, 'w') as f:
                # Write header
                if format_type == "realitycapture":
                    f.write("# RealityCapture Camera Import Format\n")
                    f.write("# filename X Y Z omega phi kappa\n")
                    f.write("# Coordinates in mm, angles in degrees\n")
                else:
                    f.write("# Meshroom Geolocation Format\n")
                    f.write("# filename X Y Z\n")
                    f.write("# Coordinates in mm\n")
                f.write("#\n")
                
                # Write camera positions
                for image_name, cameras in sorted(positions_dict.items()):
                    for cam_id in sorted(cameras.keys()):
                        pos = cameras[cam_id]
                        if format_type == "realitycapture":
                            f.write(pos.to_realitycapture_line(image_name) + "\n")
                        else:
                            f.write(pos.to_meshroom_line(image_name) + "\n")
                
            return True
            
        except Exception as e:
            print(f"Failed to export camera positions: {e}")
            return False


def create_stereo_position_calculator(config_manager: ConfigManager) -> StereoCameraPositionCalculator:
    """
    Factory function to create stereo camera position calculator.
    
    Args:
        config_manager: Configuration manager instance
        
    Returns:
        Configured StereoCameraPositionCalculator
    """
    return StereoCameraPositionCalculator(config_manager)
