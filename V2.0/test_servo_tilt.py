#!/usr/bin/env python3
"""
Test Servo Tilt Functionality

Tests the servo tilt calculation system with both manual and automatic modes.
Validates geometric calculations and configuration handling.

Author: Scanner System Development
Created: March 2025
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motion.servo_tilt import ServoTiltCalculator, ServoTiltConfig, create_servo_tilt_calculator
from motion.base import Position4D
from core.config_manager import ConfigManager
from core.exceptions import MotionControlError
import math


def test_servo_tilt_calculator():
    """Test basic servo tilt calculator functionality"""
    print("🧪 Testing Servo Tilt Calculator")
    print("=" * 50)
    
    # Create test configuration matching physical hardware
    config = ServoTiltConfig(
        camera_offset_x=-10.0,  # Negative as requested
        camera_offset_y=20.0,   # Positive
        turntable_offset_x=30.0, # Positive
        turntable_offset_y=-10.0, # Negative as requested
        min_angle=-75.0,        # Expanded range as requested
        max_angle=75.0,         # Expanded range as requested
        min_calculation_distance=10.0
    )
    
    calculator = ServoTiltCalculator(config)
    
    # Display configuration
    print(f"\nConfiguration:")
    print(f"   Camera Offset: X={config.camera_offset_x}, Y={config.camera_offset_y}")
    print(f"   Turntable Offset: X={config.turntable_offset_x}, Y={config.turntable_offset_y}")
    print(f"   Angle Limits: {config.min_angle}° to {config.max_angle}°")
    print(f"   Min Distance: {config.min_calculation_distance}mm")
    
    # Test configuration validation
    print("\n1. Configuration Validation:")
    validation = calculator.validate_configuration()
    print(f"   Valid: {validation['valid']}")
    print(f"   Warnings: {validation['warnings']}")
    print(f"   Errors: {validation['errors']}")
    
    # Test manual mode
    print("\n2. Manual Mode Tests:")
    manual_angles = [0.0, 15.0, -20.0, 50.0, -60.0]  # Include some out-of-range
    for angle in manual_angles:
        result = calculator.calculate_manual_angle(angle)
        print(f"   Input: {angle:6.1f}° → Output: {result:6.1f}°")
    
    # Test automatic mode with various positions
    print("\n3. Automatic Mode Tests:")
    
    # First test: Validation case for -45° with 100mm base and height
    print("\n   Validation Test (should give -45°):")
    print("   Target: base=100mm, height=100mm should give -45° servo angle")
    
    # Calculate FluidNC position to get base=100mm, height=100mm
    # base = fluidnc_x + turntable_offset_x + camera_offset_x = fluidnc_x + 30 + (-10) = fluidnc_x + 20
    # height = fluidnc_y + camera_offset_y + turntable_offset_y + user_y_focus = fluidnc_y + 20 + (-10) + user_y_focus = fluidnc_y + 10 + user_y_focus
    # For base=100: fluidnc_x + 20 = 100, so fluidnc_x = 80
    # For height=100: fluidnc_y + 10 + user_y_focus = 100, so if user_y_focus=0: fluidnc_y = 90
    
    validation_case = (80.0, 90.0, 0.0)  # Should give base=100, height=100
    fluidnc_x, fluidnc_y, user_y_focus = validation_case
    try:
        angle = calculator.calculate_automatic_angle(fluidnc_x, fluidnc_y, user_y_focus)
        expected_angle = -45.0  # atan2(100, 100) = 45°, servo = -45°
        print(f"   FluidNC({fluidnc_x}, {fluidnc_y}) Focus:{user_y_focus} → Angle: {angle:.1f}° (Expected: {expected_angle:.1f}°)")
        print(f"   ✅ Validation {'PASSED' if abs(angle - expected_angle) < 1.0 else 'FAILED'}")
    except MotionControlError as e:
        print(f"   FluidNC({fluidnc_x}, {fluidnc_y}) Focus:{user_y_focus} → ERROR: {e}")
    
    print("\n   Additional Test Cases:")
    test_positions = [
        (50.0, 40.0, 20.0),   # Different angles
        (30.0, 60.0, 30.0),   # Different configuration
        (70.0, 20.0, 10.0),   # Another test case
    ]
    
    for fluidnc_x, fluidnc_y, user_y_focus in test_positions:
        try:
            angle = calculator.calculate_automatic_angle(fluidnc_x, fluidnc_y, user_y_focus)
            print(f"   FluidNC({fluidnc_x}, {fluidnc_y}) Focus:{user_y_focus} → Angle: {angle:6.1f}°")
        except MotionControlError as e:
            print(f"   FluidNC({fluidnc_x}, {fluidnc_y}) Focus:{user_y_focus} → ERROR: {e}")
    
    # Test edge cases
    print("\n4. Edge Case Tests:")
    try:
        # Very close position (should fail)
        angle = calculator.calculate_automatic_angle(105.0, 30.0, 25.0)
        print(f"   Close position: {angle:.1f}°")
    except MotionControlError as e:
        print(f"   Close position: ERROR (expected) - {e}")
    
    # Test both modes via unified interface
    print("\n5. Unified Interface Tests:")
    test_cases = [
        ("manual", 0.0, 0.0, 0.0, 15.0),
        ("automatic", 200.0, 150.0, 75.0, 0.0),  # Use working position instead
    ]
    
    for mode, x, y, focus, manual in test_cases:
        try:
            angle = calculator.calculate_servo_angle(mode, x, y, focus, manual)
            print(f"   Mode: {mode:9s} → Angle: {angle:6.1f}°")
        except MotionControlError as e:
            print(f"   Mode: {mode:9s} → ERROR: {e}")


def test_config_integration():
    """Test integration with configuration system"""
    print("\n🧪 Testing Configuration Integration")
    print("=" * 50)
    
    try:
        # Load configuration 
        config_file = "config/scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        print("1. Loading camera configuration...")
        camera_config = config_manager.get('cameras', {})
        print(f"   Camera config found: {bool(camera_config)}")
        print(f"   Servo tilt enabled: {camera_config.get('servo_tilt', {}).get('enable', False)}")
        
        # Test factory function
        print("\n2. Creating servo tilt calculator from config...")
        try:
            calculator = create_servo_tilt_calculator(camera_config)
            print("   ✅ Calculator created successfully")
            
            # Test with configuration values
            servo_config = camera_config.get('servo_tilt', {})
            if servo_config.get('enable', False):
                mode = servo_config.get('calculation_mode', 'automatic')
                manual_angle = servo_config.get('manual_angle', 0.0)
                
                print(f"   Mode: {mode}")
                print(f"   Manual angle: {manual_angle}°")
                
                # Test calculation
                if mode == "automatic":
                    test_angle = calculator.calculate_servo_angle(
                        mode="automatic",
                        fluidnc_x=150.0,
                        fluidnc_y=100.0,
                        user_y_focus=50.0
                    )
                    print(f"   Test automatic angle: {test_angle:.1f}°")
                else:
                    test_angle = calculator.calculate_servo_angle(
                        mode="manual",
                        manual_angle=manual_angle
                    )
                    print(f"   Test manual angle: {test_angle:.1f}°")
            
        except Exception as e:
            print(f"   ❌ Calculator creation failed: {e}")
            
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")


def test_geometric_calculation():
    """Test geometric calculation details"""
    print("\n🧪 Testing Geometric Calculations")
    print("=" * 50)
    
    # Create calculator with correct configuration (matching the updated config)
    config = ServoTiltConfig(
        camera_offset_x=-10.0,  # Correct negative value
        camera_offset_y=20.0,   # Correct positive value
        turntable_offset_x=30.0, # Correct positive value
        turntable_offset_y=-10.0, # Correct negative value
        min_angle=-75.0,        # Updated range
        max_angle=75.0          # Updated range
    )
    
    calculator = ServoTiltCalculator(config)
    
    # Test specific geometric case - the validation case
    fluidnc_x = 80.0   # Should give base = 80 + 30 + (-10) = 100mm
    fluidnc_y = 90.0   # Should give height = 90 + 20 + (-10) + 0 = 100mm
    user_y_focus = 0.0
    
    print(f"Test Case (Validation - should give -45°):")
    print(f"  FluidNC Position: X={fluidnc_x}, Y={fluidnc_y}")
    print(f"  User Y Focus: {user_y_focus}")
    print(f"  Camera Offset: X={config.camera_offset_x}, Y={config.camera_offset_y}")
    print(f"  Turntable Offset: X={config.turntable_offset_x}, Y={config.turntable_offset_y}")
    
    # Manual calculation for verification using addition
    base = fluidnc_x + config.turntable_offset_x + config.camera_offset_x
    height = fluidnc_y + config.camera_offset_y + config.turntable_offset_y + user_y_focus
    angle_radians = math.atan2(height, base)
    angle_degrees = math.degrees(angle_radians)
    servo_angle = -angle_degrees  # Inverted for servo orientation
    
    print(f"\nManual Calculation (using addition):")
    print(f"  Base = {fluidnc_x} + {config.turntable_offset_x} + ({config.camera_offset_x}) = {base}")
    print(f"  Height = {fluidnc_y} + {config.camera_offset_y} + ({config.turntable_offset_y}) + {user_y_focus} = {height}")
    print(f"  Raw Angle = atan2({height}, {base}) = {angle_degrees:.3f}°")
    print(f"  Servo Angle = -{angle_degrees:.3f}° = {servo_angle:.3f}° ({'UP' if servo_angle > 0 else 'DOWN' if servo_angle < 0 else 'HORIZONTAL'})")
    
    # Calculator result
    calc_angle = calculator.calculate_automatic_angle(fluidnc_x, fluidnc_y, user_y_focus)
    print(f"\nCalculator Result: {calc_angle:.3f}°")
    print(f"Expected: -45.000°")
    print(f"Match: {abs(calc_angle - servo_angle) < 0.001}")
    print(f"Validation: {abs(calc_angle + 45.0) < 0.1}")


def test_motion_controller_integration():
    """Test integration with motion controller (simulation mode)"""
    print("\n🧪 Testing Motion Controller Integration")
    print("=" * 50)
    
    try:
        # Import motion controller
        from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
        from core.config_manager import ConfigManager
        
        # Load configuration
        config_file = "config/scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Get the full configuration and ensure cameras section is passed to motion controller
        motion_config = config_manager.get('motion', {})
        cameras_config = config_manager.get('cameras', {})
        
        # Motion controller needs cameras config at the top level, not nested
        motion_config['cameras'] = cameras_config
        motion_config['simulation_mode'] = True  # Force simulation mode
        
        print("1. Creating motion controller...")
        print(f"   Camera config available: {bool(cameras_config)}")
        print(f"   Servo tilt in config: {cameras_config.get('servo_tilt', {}).get('enable', False)}")
        
        controller = SimplifiedFluidNCControllerFixed(motion_config)
        print(f"   Servo tilt available: {controller.servo_tilt_calculator is not None}")
        
        if controller.servo_tilt_calculator:
            print("\n2. Testing servo tilt methods...")
            
            # Test servo angle calculation
            angle = controller.calculate_servo_angle(
                mode="automatic",
                fluidnc_x=150.0,
                fluidnc_y=100.0,
                user_y_focus=50.0
            )
            print(f"   Calculated angle: {angle}°")
            
            # Test servo tilt info
            info = controller.get_servo_tilt_info()
            print(f"   Servo enabled: {info['enabled']}")
            if info['enabled']:
                print(f"   Camera offset: {info['configuration']['camera_offset']}")
                print(f"   Angle limits: {info['configuration']['angle_limits']}")
        else:
            print("   ⚠️  Servo tilt not initialized")
            
    except Exception as e:
        print(f"❌ Motion controller test failed: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Run all servo tilt tests"""
    print("🚀 Servo Tilt System Test Suite")
    print("=" * 60)
    
    try:
        test_servo_tilt_calculator()
        test_config_integration() 
        test_geometric_calculation()
        test_motion_controller_integration()
        
        print("\n" + "=" * 60)
        print("✅ All servo tilt tests completed!")
        print("\nNext steps:")
        print("1. Test on Pi hardware with actual servo")
        print("2. Integrate with web interface for Y focus input")
        print("3. Test with scanning operations")
        
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)