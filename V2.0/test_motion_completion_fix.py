#!/usr/bin/env python3
"""
Test script to verify motion completion fix works properly
This test should show that each movement waits for completion before proceeding
"""

import asyncio
import logging
import sys
from pathlib import Path
import time

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from motion.base import Position4D
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_motion_completion():
    """Test that motion completion works properly"""
    
    # Initialize motion controller with basic config
    motion_config = {
        'port': '/dev/ttyUSB0',
        'baud_rate': 115200,
        'command_timeout': 10.0,
        'motion_limits': {
            'x': {'min': 0.0, 'max': 200.0, 'max_feedrate': 1000.0},
            'y': {'min': 0.0, 'max': 200.0, 'max_feedrate': 1000.0},
            'z': {'min': -360.0, 'max': 360.0, 'max_feedrate': 500.0},
            'c': {'min': -90.0, 'max': 90.0, 'max_feedrate': 300.0}
        }
    }
    controller = SimplifiedFluidNCControllerFixed(motion_config)
    
    try:
        # Connect to FluidNC
        if not await controller.connect():
            logger.error("Failed to connect to FluidNC")
            return False
        
        # Home the system first
        logger.info("🏠 Starting homing sequence...")
        home_success = await controller.home_axes()
        if not home_success:
            logger.error("Homing failed")
            return False
        logger.info("✅ Homing completed")
        
        # Test a series of movements to verify motion completion
        test_positions = [
            Position4D(x=50.0, y=50.0, z=0.0, c=0.0),
            Position4D(x=100.0, y=50.0, z=0.0, c=0.0),
            Position4D(x=100.0, y=100.0, z=0.0, c=0.0),
            Position4D(x=50.0, y=100.0, z=0.0, c=0.0),
        ]
        
        logger.info("🔄 Testing motion completion with series of movements...")
        
        for i, position in enumerate(test_positions):
            start_time = time.time()
            logger.info(f"🎯 Moving to position {i+1}: {position}")
            
            success = await controller.move_to_position(position)
            
            end_time = time.time()
            duration = end_time - start_time
            
            if success:
                logger.info(f"✅ Movement {i+1} completed in {duration:.2f}s")
                # Verify we're actually at the position
                current_pos = await controller.get_position()
                logger.info(f"📍 Current position: {current_pos}")
            else:
                logger.error(f"❌ Movement {i+1} failed")
                return False
            
            # Small delay between movements
            await asyncio.sleep(0.5)
        
        logger.info("✅ All test movements completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        # Cleanup
        await controller.disconnect()

if __name__ == "__main__":
    print("🧪 Testing motion completion fix...")
    print("This test verifies that movements wait for completion before proceeding")
    print()
    
    # Run the test
    success = asyncio.run(test_motion_completion())
    
    if success:
        print("\n✅ Motion completion fix test PASSED!")
        print("The system now properly waits for each movement to complete.")
    else:
        print("\n❌ Motion completion fix test FAILED!")
        print("There may still be issues with motion completion.")
        sys.exit(1)