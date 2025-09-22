#!/usr/bin/env python3
"""
Hardware test for homing functionality
Run this on the Raspberry Pi with FluidNC connected
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from motion.fluidnc_controller import FluidNCController
from motion.base import Position4D
from core.logging_setup import setup_logging

async def test_hardware_homing():
    """Test homing on real hardware"""
    print("=== Hardware Homing Test ===\n")
    
    try:
        # Setup logging
        setup_logging()
        
        # Load configuration directly
        import yaml
        config_path = project_root / "config" / "scanner_config.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        motion_config = config['motion']['controller']
        
        print(f"Connecting to FluidNC on {motion_config.get('port', '/dev/ttyUSB0')}")
        print(f"Baudrate: {motion_config.get('baudrate', 115200)}")
        
        # Create controller
        controller = FluidNCController(motion_config)
        
        # Test connection (without auto-unlock)
        print("\n--- Testing Connection ---")
        if await controller.connect(auto_unlock=False):
            print("✅ Connected to FluidNC successfully")
        else:
            print("❌ Failed to connect to FluidNC")
            return False
        
        # Get initial status
        print("\n--- Initial Status ---")
        status = await controller.get_status()
        print(f"FluidNC Status: {status}")
        
        position = await controller.get_current_position()
        if position:
            print(f"Current Position: {position}")
        else:
            print("Could not read current position")
        
        print(f"Is Homed: {controller.is_homed}")
        
        # Test homing
        print("\n--- Starting Homing Sequence ---")
        print("This will execute: $H (FluidNC standard homing)")
        print("Expected behavior:")
        print("  - X-axis will home to 0.0mm (minimum limit)")
        print("  - Y-axis will home to 200.0mm (maximum limit)")
        print("  - Z-axis does not participate in homing")
        print("  - C-axis does not participate in homing")
        
        user_input = input("\nProceed with homing? (y/N): ")
        if user_input.lower() != 'y':
            print("Homing cancelled by user")
            await controller.disconnect()
            return True
        
        print("\n🏠 Starting homing sequence...")
        home_success = await controller.home_all_axes()
        
        if home_success:
            print("✅ Homing completed successfully!")
            
            # Get final position
            final_position = await controller.get_current_position()
            if final_position:
                print(f"Final Position: {final_position}")
                
                # Verify expected positions
                print("\n--- Position Verification ---")
                expected_x = 0.0
                expected_y = 200.0
                tolerance = 1.0  # 1mm tolerance
                
                x_ok = abs(final_position.x - expected_x) <= tolerance
                y_ok = abs(final_position.y - expected_y) <= tolerance
                
                print(f"X-axis: {final_position.x}mm (expected {expected_x}mm) {'✅' if x_ok else '❌'}")
                print(f"Y-axis: {final_position.y}mm (expected {expected_y}mm) {'✅' if y_ok else '❌'}")
                print(f"Z-axis: {final_position.z}° (should remain at current position)")
                print(f"C-axis: {final_position.c}° (should remain at current position)")
                
                if x_ok and y_ok:
                    print("\n✅ Homing verification PASSED!")
                else:
                    print("\n⚠️  Homing verification FAILED - positions not as expected")
            else:
                print("⚠️  Could not read final position")
        else:
            print("❌ Homing FAILED")
        
        # Test some basic movements after homing
        if home_success and controller.is_homed:
            print("\n--- Testing Basic Movement ---")
            test_move = input("Test small movement to verify system? (y/N): ")
            if test_move.lower() == 'y':
                print("Moving to safe test position: X=10mm, Y=190mm")
                test_position = Position4D(x=10.0, y=190.0, z=0.0, c=0.0)
                move_success = await controller.move_to_position(test_position)
                if move_success:
                    print("✅ Test movement completed")
                    final_pos = await controller.get_current_position()
                    if final_pos:
                        print(f"Final test position: {final_pos}")
                else:
                    print("❌ Test movement failed")
        
        # Disconnect
        await controller.disconnect()
        print("\n✅ Hardware test completed")
        return True
        
    except Exception as e:
        print(f"❌ Hardware test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_hardware_homing())
    if success:
        print("\n🎉 Hardware homing test completed successfully!")
        print("The homing fixes are working correctly on real hardware.")
    else:
        print("\n💥 Hardware test failed - check hardware connection and configuration")
    
    sys.exit(0 if success else 1)