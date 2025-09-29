"""
Servo Tilt Calculation Utilities

Provides geometric calculation methods for automatic servo tilt angles
based on camera positioning and focus target points.

Author: Scanner System Development
Created: March 2025
"""

import math
from dataclasses import dataclass
from typing import Optional, Dict, Any
from core.exceptions import MotionControlError


@dataclass
class ServoTiltConfig:
    """Configuration for servo tilt calculations"""
    # Camera and turntable offset configuration
    camera_offset_x: float  # mm - Horizontal offset of camera from FluidNC X position
    camera_offset_y: float  # mm - Vertical offset of camera from FluidNC Y position
    turntable_offset_x: float  # mm - Horizontal offset of turntable center from origin
    turntable_offset_y: float  # mm - Vertical offset of turntable surface from origin
    
    # Servo angle limits
    min_angle: float = -45.0  # degrees - Maximum downward tilt
    max_angle: float = 45.0   # degrees - Maximum upward tilt
    center_angle: float = 0.0  # degrees - Horizontal position
    
    # Calculation parameters
    min_calculation_distance: float = 10.0  # mm - Minimum distance for stable calculation
    enable_negative_angles: bool = True  # Allow negative angles for points below FluidNC height


class ServoTiltCalculator:
    """
    Calculates servo tilt angles for optimal camera positioning.
    
    Two modes:
    1. Manual: Uses a fixed angle for all positions
    2. Automatic: Calculates angle based on geometric triangle
    
    Geometric calculation uses triangle where:
    - Base = fluidnc_x + x_turntable_offset + x_camera_offset
    - Height = fluidnc_y + y_camera_offset + y_turntable_offset + user_y_focus
    - Angle = atan2(height, base) converted to degrees
    """
    
    def __init__(self, config: ServoTiltConfig):
        """Initialize with servo tilt configuration"""
        self.config = config
        
    def calculate_manual_angle(self, manual_angle: float) -> float:
        """
        Manual mode: Return fixed angle within servo limits
        
        Args:
            manual_angle: Desired fixed angle in degrees
            
        Returns:
            Clamped angle within servo limits
            
        Raises:
            MotionControlError: If angle is outside valid range
        """
        # Clamp angle to servo limits
        clamped_angle = max(self.config.min_angle, 
                           min(self.config.max_angle, manual_angle))
        
        if abs(clamped_angle - manual_angle) > 0.01:  # Check if clamping occurred
            print(f"Warning: Manual angle {manual_angle}° clamped to {clamped_angle}°")
            
        return clamped_angle
    
    def calculate_automatic_angle(self, 
                                fluidnc_x: float, 
                                fluidnc_y: float, 
                                user_y_focus: float) -> float:
        """
        Automatic mode: Calculate servo angle based on geometric triangle
        
        Triangle geometry:
        - Base = fluidnc_x + x_turntable_offset + x_camera_offset
        - Height = fluidnc_y + y_camera_offset + y_turntable_offset + user_y_focus
        - Angle = atan2(height, base) converted to degrees
        
        Args:
            fluidnc_x: FluidNC X position in mm
            fluidnc_y: FluidNC Y position in mm  
            user_y_focus: Target Y height for camera focus in mm
            
        Returns:
            Calculated servo angle in degrees, clamped to servo limits
            
        Raises:
            MotionControlError: If calculation fails or distance too small
        """
        try:
            # Calculate triangle components using addition instead of subtraction
            base = fluidnc_x + self.config.turntable_offset_x + self.config.camera_offset_x
            height = fluidnc_y + self.config.camera_offset_y + self.config.turntable_offset_y + user_y_focus
            
            # Check minimum distance for stable calculation
            distance = math.sqrt(base * base + height * height)
            if distance < self.config.min_calculation_distance:
                raise MotionControlError(
                    f"Calculation distance {distance:.1f}mm too small "
                    f"(minimum: {self.config.min_calculation_distance}mm)"
                )
            
            # Calculate angle using atan2 for proper quadrant handling
            # Note: atan2(height, base) gives angle from horizontal
            # Servo: 0° = horizontal, +90° = up, -90° = down
            angle_radians = math.atan2(height, base)
            angle_degrees = math.degrees(angle_radians)
            
            # For servo orientation: if height is positive (camera above focus), angle should be negative (look down)
            # If height is negative (camera below focus), angle should be positive (look up)
            servo_angle = -angle_degrees  # Invert the angle for servo orientation
            
            # Handle negative angles based on configuration
            if not self.config.enable_negative_angles and servo_angle < 0:
                servo_angle = 0.0
                print(f"Warning: Negative angle disabled, using 0° instead of {servo_angle:.1f}°")
            
            # Clamp to servo limits
            clamped_angle = max(self.config.min_angle, 
                               min(self.config.max_angle, servo_angle))
            
            # Debug information
            print(f"Servo Angle Calculation:")
            print(f"  FluidNC Position: X={fluidnc_x:.1f}, Y={fluidnc_y:.1f}")
            print(f"  User Y Focus: {user_y_focus:.1f}mm")
            print(f"  Camera/Turntable Offsets: Cam({self.config.camera_offset_x}, {self.config.camera_offset_y}) Turntable({self.config.turntable_offset_x}, {self.config.turntable_offset_y})")
            print(f"  Triangle - Base: {base:.1f}mm, Height: {height:.1f}mm (using addition)")
            print(f"  Raw Angle: {angle_degrees:.1f}° -> Servo Angle: {servo_angle:.1f}° -> Clamped: {clamped_angle:.1f}°")
            print(f"  Servo Interpretation: {clamped_angle:.1f}° ({'UP' if clamped_angle > 0 else 'DOWN' if clamped_angle < 0 else 'HORIZONTAL'})")
            
            return clamped_angle
            
        except Exception as e:
            raise MotionControlError(f"Servo angle calculation failed: {e}")
    
    def calculate_servo_angle(self, 
                            mode: str,
                            fluidnc_x: float = 0.0,
                            fluidnc_y: float = 0.0, 
                            user_y_focus: float = 0.0,
                            manual_angle: float = 0.0) -> float:
        """
        Calculate servo angle based on mode and parameters
        
        Args:
            mode: "manual" or "automatic"
            fluidnc_x: FluidNC X position (for automatic mode)
            fluidnc_y: FluidNC Y position (for automatic mode)
            user_y_focus: Target Y focus height (for automatic mode)
            manual_angle: Fixed angle (for manual mode)
            
        Returns:
            Calculated servo angle in degrees
            
        Raises:
            MotionControlError: If mode invalid or calculation fails
        """
        if mode == "manual":
            return self.calculate_manual_angle(manual_angle)
        elif mode == "automatic":
            return self.calculate_automatic_angle(fluidnc_x, fluidnc_y, user_y_focus)
        else:
            raise MotionControlError(f"Invalid servo tilt mode: {mode}. Use 'manual' or 'automatic'")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """
        Validate servo tilt configuration
        
        Returns:
            Dictionary with validation results and warnings
        """
        validation = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check angle limits
        if self.config.min_angle >= self.config.max_angle:
            validation["errors"].append("min_angle must be less than max_angle")
            validation["valid"] = False
            
        if not (-90 <= self.config.min_angle <= 90):
            validation["warnings"].append(f"min_angle {self.config.min_angle}° outside typical servo range")
            
        if not (-90 <= self.config.max_angle <= 90):
            validation["warnings"].append(f"max_angle {self.config.max_angle}° outside typical servo range")
        
        # Check calculation parameters
        if self.config.min_calculation_distance <= 0:
            validation["errors"].append("min_calculation_distance must be positive")
            validation["valid"] = False
            
        # Check offsets are reasonable
        if abs(self.config.camera_offset_x) > 500:
            validation["warnings"].append(f"camera_offset_x {self.config.camera_offset_x}mm seems large")
            
        if abs(self.config.camera_offset_y) > 500:
            validation["warnings"].append(f"camera_offset_y {self.config.camera_offset_y}mm seems large")
        
        return validation


def create_servo_tilt_calculator(camera_config: Dict[str, Any]) -> ServoTiltCalculator:
    """
    Factory function to create ServoTiltCalculator from camera configuration
    
    Args:
        camera_config: Camera configuration dictionary from scanner_config.yaml
        
    Returns:
        Configured ServoTiltCalculator instance
        
    Raises:
        MotionControlError: If configuration is invalid
    """
    try:
        # Extract positioning configuration
        positioning = camera_config.get("positioning", {})
        camera_offset = positioning.get("camera_offset", {})
        turntable_offset = positioning.get("turntable_offset", {})
        
        # Extract servo tilt configuration  
        servo_tilt = camera_config.get("servo_tilt", {})
        auto_calc = servo_tilt.get("auto_calculation", {})
        
        # Create configuration
        config = ServoTiltConfig(
            camera_offset_x=camera_offset.get("x", 50.0),
            camera_offset_y=camera_offset.get("y", 30.0),
            turntable_offset_x=turntable_offset.get("x", 100.0),
            turntable_offset_y=turntable_offset.get("y", 25.0),
            min_angle=servo_tilt.get("min_angle", -45.0),
            max_angle=servo_tilt.get("max_angle", 45.0),
            center_angle=servo_tilt.get("center_angle", 0.0),
            min_calculation_distance=auto_calc.get("min_calculation_distance", 10.0),
            enable_negative_angles=auto_calc.get("enable_negative_angles", True)
        )
        
        # Create calculator
        calculator = ServoTiltCalculator(config)
        
        # Validate configuration
        validation = calculator.validate_configuration()
        if not validation["valid"]:
            raise MotionControlError(f"Invalid servo tilt configuration: {validation['errors']}")
            
        # Print warnings if any
        for warning in validation["warnings"]:
            print(f"Servo Tilt Warning: {warning}")
            
        return calculator
        
    except Exception as e:
        raise MotionControlError(f"Failed to create servo tilt calculator: {e}")