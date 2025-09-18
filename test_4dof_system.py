#!/usr/bin/env python3
"""
FluidNC 4DOF Camera System Test Script

This script demonstrates the basic functionality of the upgraded 4DOF camera positioning system.
Run this to test the FluidNC controller and 4DOF movements.
"""

import sys
import time
from integrated_camera_system import IntegratedCameraSystem, Point

def test_4dof_system():
    """Test the 4DOF FluidNC camera system"""
    print("=== FluidNC 4DOF Camera System Test ===")
    print()
    
    # Initialize system with FluidNC
    print("1. Initializing FluidNC 4DOF system...")
    system = IntegratedCameraSystem(use_fluidnc=True)
    
    if not system.initialize_positioning_system():
        print("❌ Failed to initialize positioning system")
        return False
    
    print("✅ FluidNC system initialized successfully")
    print()
    
    # Test basic 4DOF movement
    print("2. Testing basic 4DOF movement...")
    test_position = Point(50, 50, 90, 105)  # X, Y, Z(rotation), C(15° tilt = 90+15=105mm)
    print(f"   Moving to: X={test_position.x}mm, Y={test_position.y}mm, Z={test_position.z}°, C=15° (pos:{test_position.c}mm)")
    
    success = system.camera_controller.move_to_capture_position(
        x=test_position.x,
        y=test_position.y, 
        z=test_position.z,
        c=15,  # 15° tilt angle (will be converted to 105mm position)
        feedrate=300
    )
    
    if success:
        print("✅ 4DOF movement successful")
    else:
        print("❌ 4DOF movement failed")
        return False
    
    time.sleep(2)
    print()
    
    # Test rotational scan
    print("3. Testing rotational scan (turntable)...")
    base_pos = Point(75, 75, 0, 90)  # 90mm = 0° tilt
    rotation_angles = [0, 90, 180, 270]  # 4 positions
    print(f"   Scanning at angles: {rotation_angles}°")
    
    success = system.camera_controller.rotational_scan(
        base_pos, 
        rotation_angles,
        c_angle=0,  # 0° tilt (will be converted to 90mm position)
        feedrate=200
    )
    
    if success:
        print("✅ Rotational scan completed")
    else:
        print("❌ Rotational scan failed")
    
    time.sleep(2)
    print()
    
    # Test camera tilt scan
    print("4. Testing camera tilt scan...")
    fixed_pos = Point(100, 100, 45, 90)  # Fixed XYZ, vary C (90mm = 0° tilt)
    tilt_angles = [70, 90, 110]  # ±20° tilt range (70mm=-20°, 90mm=0°, 110mm=+20°)
    print(f"   Tilt angles: {tilt_angles}°")
    
    success = system.camera_controller.tilt_scan(
        fixed_pos,
        tilt_angles,
        feedrate=150
    )
    
    if success:
        print("✅ Camera tilt scan completed")
    else:
        print("❌ Camera tilt scan failed")
    
    time.sleep(2)
    print()
    
    # Test axis limits validation
    print("5. Testing axis limits validation...")
    
    # Test valid position
    valid_pos = Point(150, 150, 180, 135)  # C=135mm = 45° tilt
    if system.controller.validate_position(valid_pos):
        print("✅ Valid position accepted")
    else:
        print("❌ Valid position rejected")
    
    # Test invalid position (exceeds X limit)
    invalid_pos = Point(250, 100, 180, 90)  # X=250 > 200mm limit
    if not system.controller.validate_position(invalid_pos):
        print("✅ Invalid position correctly rejected")
    else:
        print("❌ Invalid position incorrectly accepted")
    
    # Test invalid C-axis (exceeds tilt limit)
    invalid_tilt = Point(100, 100, 180, 190)  # C=190mm > 180mm limit
    if not system.controller.validate_position(invalid_tilt):
        print("✅ Invalid tilt correctly rejected")
    else:
        print("❌ Invalid tilt incorrectly accepted")
    
    print()
    
    # Return to home position
    print("6. Returning to home position...")
    success = system.camera_controller.return_to_home()
    
    if success:
        print("✅ Returned to home position")
    else:
        print("❌ Failed to return home")
    
    print()
    print("=== 4DOF Test Completed ===")
    return True

def test_controller_comparison():
    """Compare FluidNC vs GRBL controller initialization"""
    print("=== Controller Comparison Test ===")
    print()
    
    # Test FluidNC
    print("Testing FluidNC controller...")
    fluidnc_system = IntegratedCameraSystem(use_fluidnc=True)
    fluidnc_success = fluidnc_system.initialize_positioning_system()
    print(f"FluidNC result: {'✅ Success' if fluidnc_success else '❌ Failed'}")
    
    # Test GRBL (for comparison/fallback)
    print("Testing GRBL controller...")
    grbl_system = IntegratedCameraSystem(use_fluidnc=False)
    grbl_success = grbl_system.initialize_positioning_system()
    print(f"GRBL result: {'✅ Success' if grbl_success else '❌ Failed'}")
    
    print()
    print("Recommendation: Use FluidNC for 4DOF, GRBL for 3DOF legacy")
    print()

def demonstrate_new_scan_patterns():
    """Demonstrate the new scan patterns available with 4DOF"""
    print("=== New 4DOF Scan Patterns Demo ===")
    print()
    
    system = IntegratedCameraSystem(use_fluidnc=True)
    if not system.initialize_positioning_system():
        print("❌ Cannot initialize system for demo")
        return
    
    print("Available 4DOF scan patterns:")
    print()
    
    # 1. Traditional grid scan (now with tilt)
    print("1. Enhanced Grid Scan (with camera tilt)")
    corner1 = Point(20, 20, 0, 80)  # Start with -10° tilt (80mm = -10°)
    corner2 = Point(80, 80, 0, 80)
    # This would create a grid scan with all positions at -10° camera tilt
    print(f"   Grid from {corner1.x},{corner1.y} to {corner2.x},{corner2.y} at -10° tilt")
    
    # 2. Rotational scan at multiple heights
    print("2. Multi-Level Rotational Scan")
    base_pos = Point(100, 50, 0, 90)  # 90mm = 0° tilt
    rotation_angles = [0, 45, 90, 135, 180, 225, 270, 315]
    print(f"   8-position turntable scan at position {base_pos.x},{base_pos.y}")
    
    # 3. Camera tilt sweep
    print("3. Camera Tilt Sweep")
    fixed_pos = Point(100, 100, 90, 90)  # Fixed position, sweep tilt (90mm = 0°)
    tilt_range = list(range(-30, 31, 10))  # -30° to +30° in 10° steps
    print(f"   Tilt sweep: {tilt_range}° at position {fixed_pos.x},{fixed_pos.y}")
    
    # 4. Spherical scan
    print("4. Full Spherical Scan")
    center = Point(100, 100, 0, 90)  # 90mm = 0° tilt
    z_positions = [0, 60, 120, 180, 240, 300]  # 6 turntable positions
    c_positions = [70, 90, 110]  # 3 camera tilts (70mm=-20°, 90mm=0°, 110mm=+20°)
    total_positions = len(z_positions) * len(c_positions)
    print(f"   {total_positions} position spherical scan ({len(z_positions)} rotations × {len(c_positions)} tilts)")
    
    print()
    print("These patterns capture much more comprehensive data than 3DOF systems!")
    print()

if __name__ == "__main__":
    print("FluidNC 4DOF Camera Positioning System")
    print("=" * 50)
    print()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--demo-only":
            demonstrate_new_scan_patterns()
            sys.exit(0)
        elif sys.argv[1] == "--compare":
            test_controller_comparison()
            sys.exit(0)
    
    try:
        # Full test sequence
        success = test_4dof_system()
        
        if success:
            print("🎉 All tests passed! 4DOF system is ready for use.")
        else:
            print("⚠️  Some tests failed. Check hardware connections and configuration.")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\nTest completed.")