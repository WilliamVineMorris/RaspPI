"""
Coordinate System Transformations for 4DOF Scanner

This module handles conversions between three coordinate systems:

1. CAMERA-RELATIVE (Cylindrical): User-facing coordinates
   - radius: Distance from turntable center to camera (mm)
   - height: Height above turntable surface (mm)
   - rotation: Turntable rotation angle (degrees)
   - tilt: Camera servo tilt angle (degrees)

2. FLUIDNC (Machine): Hardware control coordinates  
   - x: Linear X-axis position (0-200mm)
   - y: Linear Y-axis position (0-200mm)
   - z: Rotational Z-axis angle (degrees)
   - c: Rotational C-axis angle (degrees)

3. CARTESIAN (World): 3D space coordinates
   - x: X position in 3D space (mm)
   - y: Y position in 3D space (mm) 
   - z: Z position in 3D space (mm)
   - c: Camera tilt angle (degrees)

Coordinate Transformations:
=========================

CAMERA → FLUIDNC:
-----------------
Given camera-relative coordinates (radius, height, rotation, tilt):

1. Camera position in cylindrical coords relative to turntable center:
   camera_x_cyl = radius * cos(rotation)
   camera_y_cyl = radius * sin(rotation)
   camera_z = height

2. Apply turntable offset to get world coordinates:
   world_x = camera_x_cyl + turntable_offset_x
   world_y = camera_y_cyl + turntable_offset_y
   world_z = camera_z + turntable_offset_y

3. Apply camera offset to get FluidNC coordinates:
   fluidnc_x = world_x - camera_offset_x
   fluidnc_y = world_z - camera_offset_y
   fluidnc_z = rotation
   fluidnc_c = tilt

FLUIDNC → CAMERA:
-----------------
Given FluidNC coordinates (x, y, z, c):

1. Apply camera offset to get world coordinates:
   world_x = fluidnc_x + camera_offset_x
   world_z = fluidnc_y + camera_offset_y

2. Subtract turntable offset:
   camera_x_cyl = world_x - turntable_offset_x
   camera_z = world_z - turntable_offset_y

3. Convert to cylindrical:
   radius = sqrt(camera_x_cyl² + camera_y_cyl²)  [where camera_y_cyl from rotation]
   height = camera_z
   rotation = fluidnc_z
   tilt = fluidnc_c

CAMERA → CARTESIAN:
------------------
Given camera-relative coordinates (radius, height, rotation, tilt):

Simply apply turntable offset:
   cart_x = radius * cos(rotation) + turntable_offset_x
   cart_y = radius * sin(rotation) + turntable_offset_y  
   cart_z = height + turntable_offset_y
   cart_c = tilt

"""

from dataclasses import dataclass
from typing import Tuple
import math
from core.types import Position4D
from core.config_manager import ConfigManager


@dataclass
class CameraRelativePosition:
    """Camera-relative cylindrical coordinates"""
    radius: float      # mm - distance from turntable center
    height: float      # mm - height above turntable surface
    rotation: float    # degrees - turntable rotation
    tilt: float        # degrees - camera servo tilt


@dataclass
class CartesianPosition:
    """Cartesian world coordinates"""
    x: float           # mm - X position in world space
    y: float           # mm - Y position in world space
    z: float           # mm - Z position (height) in world space
    c: float           # degrees - camera tilt angle


class CoordinateTransformer:
    """
    Transforms between camera-relative, FluidNC machine, and Cartesian coordinates.
    
    Uses offsets from scanner configuration to handle the physical positioning
    differences between the camera, turntable, and FluidNC coordinate frame.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize transformer with configuration offsets.
        
        Args:
            config_manager: Configuration manager with camera and turntable offsets
        """
        self.config = config_manager
        
        # Load offsets from configuration using dot notation
        self.camera_offset_x = float(self.config.get('cameras.positioning.camera_offset.x', 0.0))
        self.camera_offset_y = float(self.config.get('cameras.positioning.camera_offset.y', 0.0))
        
        self.turntable_offset_x = float(self.config.get('cameras.positioning.turntable_offset.x', 0.0))
        self.turntable_offset_y = float(self.config.get('cameras.positioning.turntable_offset.y', 0.0))
    
    def camera_to_fluidnc(self, camera_pos: CameraRelativePosition) -> Position4D:
        """
        Convert camera-relative cylindrical coordinates to FluidNC machine coordinates.
        
        IMPORTANT: FluidNC uses cylindrical-like coordinates!
        - FluidNC X = radial camera position (distance from turntable center)
        - FluidNC Y = vertical camera height
        - FluidNC Z = turntable rotation angle
        - FluidNC C = camera tilt angle
        
        Args:
            camera_pos: Camera-relative position (radius, height, rotation, tilt)
            
        Returns:
            Position4D: FluidNC machine coordinates (x, y, z, c)
        """
        # FluidNC X is the radial position (with offsets applied)
        # Camera radius is relative to turntable center
        # Add turntable offset (where turntable is), then add camera offset
        fluidnc_x = camera_pos.radius + self.turntable_offset_x + self.camera_offset_x
        
        # FluidNC Y is the vertical height (with offsets applied)
        # Camera height is relative to turntable surface
        # Add turntable offset, then add camera offset
        world_height = camera_pos.height + self.turntable_offset_y
        fluidnc_y = world_height + self.camera_offset_y
        
        return Position4D(
            x=fluidnc_x,
            y=fluidnc_y,
            z=camera_pos.rotation,
            c=camera_pos.tilt
        )
    
    def fluidnc_to_camera(self, fluidnc_pos: Position4D) -> CameraRelativePosition:
        """
        Convert FluidNC machine coordinates to camera-relative cylindrical coordinates.
        
        IMPORTANT: FluidNC uses cylindrical-like coordinates!
        - FluidNC X = radial camera position (already a radius!)
        - FluidNC Y = vertical camera height
        - FluidNC Z = turntable rotation angle
        - FluidNC C = camera tilt angle
        
        Args:
            fluidnc_pos: FluidNC machine position (x, y, z, c)
            
        Returns:
            CameraRelativePosition: Camera-relative cylindrical coordinates
        """
        # FluidNC X is already the radial position, remove offsets
        # Remove camera offset first, then turntable offset
        radius = fluidnc_pos.x - self.camera_offset_x - self.turntable_offset_x
        
        # FluidNC Y is the height with offsets, remove them
        world_height = fluidnc_pos.y - self.camera_offset_y
        height = world_height - self.turntable_offset_y
        
        return CameraRelativePosition(
            radius=radius,
            height=height,
            rotation=fluidnc_pos.z,
            tilt=fluidnc_pos.c
        )
    
    def camera_to_cartesian(self, camera_pos: CameraRelativePosition) -> CartesianPosition:
        """
        Convert camera-relative coordinates to Cartesian world coordinates.
        
        Args:
            camera_pos: Camera-relative position
            
        Returns:
            CartesianPosition: Cartesian world coordinates
        """
        rotation_rad = math.radians(camera_pos.rotation)
        
        # Convert cylindrical to cartesian and apply turntable offset
        cart_x = camera_pos.radius * math.cos(rotation_rad) + self.turntable_offset_x
        cart_y = camera_pos.radius * math.sin(rotation_rad) + self.turntable_offset_y
        cart_z = camera_pos.height + self.turntable_offset_y
        
        return CartesianPosition(
            x=cart_x,
            y=cart_y,
            z=cart_z,
            c=camera_pos.tilt
        )
    
    def fluidnc_to_cartesian(self, fluidnc_pos: Position4D) -> CartesianPosition:
        """
        Convert FluidNC coordinates to Cartesian world coordinates.
        
        Args:
            fluidnc_pos: FluidNC machine position
            
        Returns:
            CartesianPosition: Cartesian world coordinates
        """
        # First convert to camera-relative, then to cartesian
        camera_pos = self.fluidnc_to_camera(fluidnc_pos)
        return self.camera_to_cartesian(camera_pos)
    
    def cartesian_to_camera(self, cart_pos: CartesianPosition) -> CameraRelativePosition:
        """
        Convert Cartesian world coordinates to camera-relative coordinates.
        
        Args:
            cart_pos: Cartesian world position
            
        Returns:
            CameraRelativePosition: Camera-relative cylindrical coordinates
        """
        # Subtract turntable offset
        x_rel = cart_pos.x - self.turntable_offset_x
        y_rel = cart_pos.y - self.turntable_offset_y
        z_rel = cart_pos.z - self.turntable_offset_y
        
        # Convert to cylindrical
        radius = math.sqrt(x_rel**2 + y_rel**2)
        rotation = math.degrees(math.atan2(y_rel, x_rel))
        
        return CameraRelativePosition(
            radius=radius,
            height=z_rel,
            rotation=rotation,
            tilt=cart_pos.c
        )
    
    def cartesian_to_fluidnc(self, cart_pos: CartesianPosition) -> Position4D:
        """
        Convert Cartesian world coordinates to FluidNC machine coordinates.
        
        Args:
            cart_pos: Cartesian world position
            
        Returns:
            Position4D: FluidNC machine coordinates
        """
        # First convert to camera-relative, then to FluidNC
        camera_pos = self.cartesian_to_camera(cart_pos)
        return self.camera_to_fluidnc(camera_pos)


def calculate_servo_tilt_angle(
    camera_radius: float,
    camera_height: float,
    focus_height: float,
    turntable_offset_y: float,
    camera_offset_y: float
) -> float:
    """
    Calculate servo tilt angle for focus point targeting.
    
    Uses actual camera position relative to turntable, accounting for offsets.
    
    Args:
        camera_radius: Camera distance from turntable center (mm)
        camera_height: Camera height above turntable surface (mm)
        focus_height: Target focus height above turntable surface (mm)
        turntable_offset_y: Vertical offset of turntable from origin (mm)
        camera_offset_y: Vertical offset of camera from FluidNC Y (mm)
        
    Returns:
        float: Servo tilt angle in degrees (negative = down, positive = up)
    """
    # Calculate actual camera position in world space
    camera_world_z = camera_height + turntable_offset_y
    focus_world_z = focus_height + turntable_offset_y
    
    # Horizontal distance from camera to turntable center
    horizontal_dist = camera_radius
    
    # Vertical distance from camera to focus point
    vertical_dist = focus_world_z - camera_world_z
    
    # Calculate tilt angle using arctangent
    # Negative result = camera above focus (tilt down)
    # Positive result = camera below focus (tilt up)
    tilt_angle = math.degrees(math.atan2(vertical_dist, horizontal_dist))
    
    return tilt_angle
