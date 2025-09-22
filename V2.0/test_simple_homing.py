#!/usr/bin/env python3
"""
Simple hardware homing test
Run this on the Raspberry Pi with FluidNC connected
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

async def simple_homing_test():
    """Simple homing test on real hardware"""
    print("=== Simple Hardware Homing Test ===\n")
    
    try:
        # Setup logging
        setup_logging()
        
        # Load configuration directly
        config_path = project_root / "config" / "scanner_config.yaml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        motion_config = config['motion']['controller']
        
        print(f"Connecting to FluidNC on {motion_config.get('port', '/dev/ttyUSB0')}")
        
        # Create controller
        controller = FluidNCController(motion_config)
        
        # Connect (without auto-unlock - let user choose homing vs unlock)
        if await controller.connect(auto_unlock=False):
            print("✅ Connected to FluidNC")
        else:
            print("❌ Failed to connect to FluidNC")
            return False
        
        # Get initial status
        status = await controller.get_status()
        print(f"FluidNC Status: {status}")
        
        # Check if system is in alarm state
        if status == MotionStatus.ALARM:
            print("⚠️  System is in alarm state")
            print("   This is normal - homing will clear the alarm")
            print("   Alternative: call controller.unlock() to clear with $X")
        else:
            print("✅ System is ready")
        
        initial_position = await controller.get_current_position()
        if initial_position:
            print(f"Initial Position: {initial_position}")
        
        print(f"Is Homed: {controller.is_homed}")
        
        # Ask before homing
        print("\n--- Homing Test ---")
        print("This will execute: $H (FluidNC standard homing)")
        print("Expected behavior:")
        print("  X-axis: home to 0.0mm (minimum)")
        print("  Y-axis: home to 200.0mm (maximum)")
        print("  Z-axis: no homing (continuous rotation)")
        print("  C-axis: no homing (servo)")
        print("\nImproved homing completion detection:")
        print("  - Waits for actual homing sequence to start")
        print("  - Requires 5 seconds of stable 'Idle' state")
        print("  - Verifies final positions are within ±5mm of expected")
        print("  - Provides detailed progress logging")
        
        proceed = input("\nProceed with homing? (y/N): ")
        if proceed.lower() != 'y':
            print("Test cancelled")
            await controller.disconnect()
            return True
        
        # Execute homing
        print("\n🏠 Starting homing...")
        home_success = await controller.home_all_axes()
        
        if home_success:
            print("✅ Homing completed!")
            
            # Check final position
            final_position = await controller.get_current_position()
            if final_position:
                print(f"Final Position: {final_position}")
                
                # Detailed verification with tolerance
                print("\n--- Position Verification ---")
                expected_x, expected_y = 0.0, 200.0
                tolerance = 5.0  # 5mm tolerance
                
                x_diff = abs(final_position.x - expected_x)
                y_diff = abs(final_position.y - expected_y)
                x_ok = x_diff <= tolerance
                y_ok = y_diff <= tolerance
                
                print(f"X-axis: {final_position.x:.3f}mm (expected {expected_x}±{tolerance}mm)")
                print(f"  Difference: {x_diff:.3f}mm {'✅ PASS' if x_ok else '❌ FAIL'}")
                print(f"Y-axis: {final_position.y:.3f}mm (expected {expected_y}±{tolerance}mm)")
                print(f"  Difference: {y_diff:.3f}mm {'✅ PASS' if y_ok else '❌ FAIL'}")
                print(f"Z-axis: {final_position.z:.3f}° (no verification needed)")
                print(f"C-axis: {final_position.c:.3f}° (no verification needed)")
                
                if x_ok and y_ok:
                    print("\n✅ Position verification PASSED!")
                else:
                    print("\n❌ Position verification FAILED!")
                    print("   This may indicate:")
                    print("   - Homing completed too early")
                    print("   - Endstop positioning issues")
                    print("   - Motor configuration problems")
            
            print(f"Controller is_homed: {controller.is_homed}")
        else:
            print("❌ Homing FAILED")
        
        # Disconnect
        await controller.disconnect()
        print("✅ Test completed")
        return home_success
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(simple_homing_test())
    print(f"\n{'🎉 Test PASSED' if success else '💥 Test FAILED'}")
    sys.exit(0 if success else 1)