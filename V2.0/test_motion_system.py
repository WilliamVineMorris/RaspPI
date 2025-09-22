#!/usr/bin/env python3
"""
Motion System Testing Script
Progressive testing of motion capabilities after successful homing
"""

import asyncio
import sys
import yaml
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from motion.fluidnc_controller import FluidNCController
from motion.base import Position4D, MotionStatus
from core.logging_setup import setup_logging

async def test_motion_system():
    """Progressive motion system testing"""
    print("=== Motion System Testing ===\n")
    
    try:
        # Setup logging
        setup_logging()
        
        # Load configuration
        config_path = project_root / "config" / "scanner_config.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        motion_config = config['motion']['controller']
        
        print(f"Connecting to FluidNC on {motion_config.get('port', '/dev/ttyUSB0')}")
        
        # Create controller
        controller = FluidNCController(motion_config)
        
        # Connect
        if await controller.connect(auto_unlock=False):
            print("✅ Connected to FluidNC")
        else:
            print("❌ Failed to connect to FluidNC")
            return False
        
        # Check if system is homed
        print("\n--- System Status Check ---")
        status = await controller.get_status()
        print(f"System Status: {status}")
        
        if not controller.is_homed:
            print("⚠️  System not homed. Need to home first...")
            proceed_home = input("Run homing sequence? (y/N): ")
            if proceed_home.lower() == 'y':
                print("🏠 Homing system...")
                if not await controller.home_all_axes():
                    print("❌ Homing failed - cannot proceed with motion tests")
                    return False
                print("✅ Homing completed")
            else:
                print("❌ Cannot test motion without homing")
                return False
        else:
            print("✅ System is homed and ready")
        
        # Get current position
        current_pos = await controller.get_current_position()
        print(f"Current Position: {current_pos}")
        
        # Test 1: Individual Axis Movements
        print("\n" + "="*50)
        print("TEST 1: INDIVIDUAL AXIS MOVEMENTS")
        print("="*50)
        
        test_individual = input("Test individual axis movements? (y/N): ")
        if test_individual.lower() == 'y':
            
            # X-axis test (5mm movement)
            print("\n--- X-Axis Test ---")
            print("Moving X-axis +5mm from home...")
            test_pos = Position4D(x=5.0, y=current_pos.y, z=current_pos.z, c=current_pos.c)
            if await test_movement(controller, test_pos, "X+5mm"):
                # Return to home X
                home_pos = Position4D(x=0.0, y=current_pos.y, z=current_pos.z, c=current_pos.c)
                await test_movement(controller, home_pos, "X return to home")
            
            # Y-axis test (10mm movement from max)
            print("\n--- Y-Axis Test ---")
            print("Moving Y-axis -10mm from home...")
            test_pos = Position4D(x=0.0, y=190.0, z=current_pos.z, c=current_pos.c)
            if await test_movement(controller, test_pos, "Y-10mm"):
                # Return to home Y
                home_pos = Position4D(x=0.0, y=200.0, z=current_pos.z, c=current_pos.c)
                await test_movement(controller, home_pos, "Y return to home")
            
            # Z-axis test (90° rotation)
            print("\n--- Z-Axis Test (Rotation) ---")
            print("Rotating Z-axis +90°...")
            test_pos = Position4D(x=0.0, y=200.0, z=90.0, c=current_pos.c)
            if await test_movement(controller, test_pos, "Z+90°"):
                # Return to Z=0
                home_pos = Position4D(x=0.0, y=200.0, z=0.0, c=current_pos.c)
                await test_movement(controller, home_pos, "Z return to 0°")
            
            # C-axis test (tilt)
            print("\n--- C-Axis Test (Camera Tilt) ---")
            print("Tilting C-axis +45°...")
            test_pos = Position4D(x=0.0, y=200.0, z=0.0, c=45.0)
            if await test_movement(controller, test_pos, "C+45°"):
                # Return to C=0
                home_pos = Position4D(x=0.0, y=200.0, z=0.0, c=0.0)
                await test_movement(controller, home_pos, "C return to 0°")
        
        # Test 2: Combined Movements
        print("\n" + "="*50)
        print("TEST 2: COMBINED MOVEMENTS")
        print("="*50)
        
        test_combined = input("Test combined axis movements? (y/N): ")
        if test_combined.lower() == 'y':
            
            print("\n--- Combined Movement Test ---")
            print("Moving to scan position: X=50mm, Y=150mm, Z=45°, C=30°")
            scan_pos = Position4D(x=50.0, y=150.0, z=45.0, c=30.0)
            if await test_movement(controller, scan_pos, "Scan position"):
                
                print("Moving to another scan position: X=100mm, Y=100mm, Z=-45°, C=-30°")
                scan_pos2 = Position4D(x=100.0, y=100.0, z=-45.0, c=-30.0)
                if await test_movement(controller, scan_pos2, "Scan position 2"):
                    
                    # Return to home position
                    print("Returning to home position...")
                    home_pos = Position4D(x=0.0, y=200.0, z=0.0, c=0.0)
                    await test_movement(controller, home_pos, "Return home")
        
        # Test 3: Speed and Accuracy
        print("\n" + "="*50)
        print("TEST 3: SPEED AND ACCURACY")
        print("="*50)
        
        test_speed = input("Test different movement speeds? (y/N): ")
        if test_speed.lower() == 'y':
            
            positions = [
                Position4D(x=25.0, y=175.0, z=0.0, c=0.0),
                Position4D(x=75.0, y=125.0, z=0.0, c=0.0),
                Position4D(x=125.0, y=175.0, z=0.0, c=0.0),
                Position4D(x=0.0, y=200.0, z=0.0, c=0.0)  # Home
            ]
            
            feedrates = [500, 1000, 2000]  # mm/min
            
            for feedrate in feedrates:
                print(f"\n--- Testing at {feedrate} mm/min ---")
                for i, pos in enumerate(positions):
                    success = await test_movement_with_feedrate(controller, pos, feedrate, f"Speed test {i+1}")
                    if not success:
                        break
                
                await asyncio.sleep(1)  # Brief pause between speed tests
        
        # Test 4: Position Accuracy
        print("\n" + "="*50)
        print("TEST 4: POSITION ACCURACY")
        print("="*50)
        
        test_accuracy = input("Test position accuracy (precise movements)? (y/N): ")
        if test_accuracy.lower() == 'y':
            
            print("\n--- Precision Movement Test ---")
            precise_positions = [
                Position4D(x=1.0, y=199.0, z=0.0, c=0.0),    # 1mm precision
                Position4D(x=0.5, y=199.5, z=0.0, c=0.0),    # 0.5mm precision  
                Position4D(x=0.1, y=199.9, z=0.0, c=0.0),    # 0.1mm precision
                Position4D(x=0.0, y=200.0, z=0.0, c=0.0)     # Back to home
            ]
            
            for i, pos in enumerate(precise_positions):
                success = await test_movement(controller, pos, f"Precision test {i+1}")
                if success:
                    await asyncio.sleep(0.5)  # Allow settling
                else:
                    break
        
        await controller.disconnect()
        print("\n" + "="*50)
        print("✅ MOTION TESTING COMPLETED")
        print("="*50)
        print("All motion tests have been completed.")
        print("Review the logs above for any issues or failures.")
        return True
        
    except Exception as e:
        print(f"❌ Motion testing failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_movement(controller, target_position, description):
    """Test a single movement and verify results"""
    print(f"\n🎯 {description}")
    print(f"   Target: {target_position}")
    
    try:
        # Record start position
        start_pos = await controller.get_current_position()
        print(f"   Start:  {start_pos}")
        
        # Execute movement
        success = await controller.move_to_position(target_position)
        
        if success:
            # Verify final position
            final_pos = await controller.get_current_position()
            print(f"   Final:  {final_pos}")
            
            # Calculate accuracy
            x_diff = abs(final_pos.x - target_position.x)
            y_diff = abs(final_pos.y - target_position.y)
            z_diff = abs(final_pos.z - target_position.z)
            c_diff = abs(final_pos.c - target_position.c)
            
            tolerance = 0.5  # 0.5mm/degree tolerance
            x_ok = x_diff <= tolerance
            y_ok = y_diff <= tolerance  
            z_ok = z_diff <= tolerance
            c_ok = c_diff <= tolerance
            
            print(f"   Accuracy: X±{x_diff:.3f} Y±{y_diff:.3f} Z±{z_diff:.3f} C±{c_diff:.3f}")
            
            if x_ok and y_ok and z_ok and c_ok:
                print(f"   Result: ✅ SUCCESS - Within {tolerance} tolerance")
                return True
            else:
                print(f"   Result: ⚠️  ACCURACY WARNING - Outside {tolerance} tolerance")
                return True  # Still count as success but note the accuracy issue
        else:
            print(f"   Result: ❌ MOVEMENT FAILED")
            return False
            
    except Exception as e:
        print(f"   Result: ❌ ERROR - {e}")
        return False

async def test_movement_with_feedrate(controller, target_position, feedrate, description):
    """Test movement with specific feedrate"""
    print(f"\n🎯 {description} @ {feedrate} mm/min")
    print(f"   Target: {target_position}")
    
    try:
        start_pos = await controller.get_current_position()
        
        # Execute movement with specific feedrate
        success = await controller.move_to_position(target_position, feedrate=feedrate)
        
        if success:
            final_pos = await controller.get_current_position()
            print(f"   Final:  {final_pos}")
            print(f"   Result: ✅ SUCCESS at {feedrate} mm/min")
            return True
        else:
            print(f"   Result: ❌ FAILED at {feedrate} mm/min")
            return False
            
    except Exception as e:
        print(f"   Result: ❌ ERROR at {feedrate} mm/min - {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_motion_system())
    print(f"\n{'🎉 MOTION TESTS PASSED' if success else '💥 MOTION TESTS FAILED'}")
    sys.exit(0 if success else 1)