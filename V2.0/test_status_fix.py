#!/usr/bin/env python3
"""
Quick test for improved FluidNC status handling
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

async def test_status_handling():
    """Test the improved status response handling"""
    print("=== Testing FluidNC Status Response Handling ===\n")
    
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
        
        # Connect
        if await controller.connect(auto_unlock=False):
            print("✅ Connected to FluidNC")
        else:
            print("❌ Failed to connect to FluidNC")
            return False
        
        # Test status responses
        print("\n--- Testing Status Response Handling ---")
        for i in range(5):
            print(f"\nTest {i+1}/5:")
            status_response = await controller._get_status_response()
            print(f"Raw status response: {status_response}")
            
            # Parse position
            if status_response:
                position = controller._parse_position_from_status(status_response)
                if position:
                    print(f"Parsed position: {position}")
                else:
                    print("Could not parse position")
            else:
                print("No status response received")
            
            await asyncio.sleep(1)
        
        print("\n--- Quick Homing Test ---")
        proceed = input("Test homing with improved detection? (y/N): ")
        if proceed.lower() == 'y':
            print("Starting homing with improved completion detection...")
            home_success = await controller.home_all_axes()
            
            if home_success:
                print("✅ Homing completed successfully!")
                final_position = await controller.get_current_position()
                if final_position:
                    print(f"Final position: {final_position}")
            else:
                print("❌ Homing failed")
        
        await controller.disconnect()
        print("\n✅ Test completed")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_status_handling())
    print(f"\n{'🎉 Test PASSED' if success else '💥 Test FAILED'}")
    sys.exit(0 if success else 1)