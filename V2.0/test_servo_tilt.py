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
    
    # Create test configuration
    config = ServoTiltConfig(
        camera_offset_x=50.0,
        camera_offset_y=30.0,
        turntable_offset_x=100.0,
        turntable_offset_y=25.0,
        min_angle=-45.0,
        max_angle=45.0,
        min_calculation_distance=10.0
    )
    
    calculator = ServoTiltCalculator(config)
    
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
    test_positions = [
        (150.0, 100.0, 50.0),  # Standard position
        (200.0, 150.0, 75.0),  # Higher position  
        (100.0, 50.0, 25.0),   # Lower position
        (175.0, 80.0, 40.0),   # Mixed position
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
        ("automatic", 150.0, 100.0, 50.0, 0.0),
    ]
    
    for mode, x, y, focus, manual in test_cases:
        angle = calculator.calculate_servo_angle(mode, x, y, focus, manual)
        print(f"   Mode: {mode:9s} → Angle: {angle:6.1f}°")


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
    
    # Create calculator with known configuration
    config = ServoTiltConfig(
        camera_offset_x=50.0,
        camera_offset_y=30.0,
        turntable_offset_x=100.0,
        turntable_offset_y=25.0,
        min_angle=-45.0,
        max_angle=45.0
    )
    
    calculator = ServoTiltCalculator(config)
    
    # Test specific geometric case
    fluidnc_x = 150.0
    fluidnc_y = 100.0  
    user_y_focus = 50.0
    
    print(f"Test Case:")
    print(f"  FluidNC Position: X={fluidnc_x}, Y={fluidnc_y}")
    print(f"  User Y Focus: {user_y_focus}")
    print(f"  Camera Offset: X={config.camera_offset_x}, Y={config.camera_offset_y}")
    print(f"  Turntable Offset: X={config.turntable_offset_x}, Y={config.turntable_offset_y}")
    
    # Manual calculation for verification
    base = fluidnc_x - config.turntable_offset_x - config.camera_offset_x
    height = fluidnc_y - config.camera_offset_y - config.turntable_offset_y - user_y_focus
    angle_radians = math.atan2(height, base)
    angle_degrees = math.degrees(angle_radians)
    
    print(f"\nManual Calculation:")
    print(f"  Base = {fluidnc_x} - {config.turntable_offset_x} - {config.camera_offset_x} = {base}")
    print(f"  Height = {fluidnc_y} - {config.camera_offset_y} - {config.turntable_offset_y} - {user_y_focus} = {height}")
    print(f"  Angle = atan2({height}, {base}) = {angle_degrees:.3f}°")
    
    # Calculator result
    calc_angle = calculator.calculate_automatic_angle(fluidnc_x, fluidnc_y, user_y_focus)
    print(f"\nCalculator Result: {calc_angle:.3f}°")
    print(f"Match: {abs(calc_angle - angle_degrees) < 0.001}")


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
        
        # Create motion controller in simulation mode
        motion_config = config_manager.get('motion', {})
        motion_config['simulation_mode'] = True  # Force simulation mode
        
        print("1. Creating motion controller...")
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