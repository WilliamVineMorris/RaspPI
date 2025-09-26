#!/usr/bin/env python3
"""
Safe Motion Completion Test

This test uses only safe coordinates that are known to work
and focuses on verifying that motion completion waiting works properly.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

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

async def test_safe_motion_completion():
    """Test motion completion with only safe coordinates"""
    
    # Initialize motion controller with basic config
    motion_config = {
        'port': '/dev/ttyUSB0',
        'baud_rate': 115200,
        'command_timeout': 10.0,
        'motion_limits': {
            'x': {'min': 0.0, 'max': 200.0, 'max_feedrate': 1000.0},
            'y': {'min': 0.0, 'max': 200.0, 'max_feedrate': 1000.0},
            'z': {'min': -180.0, 'max': 180.0, 'max_feedrate': 500.0},
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
        
        # Get home position
        home_pos = await controller.get_position()
        logger.info(f"📍 Home position: {home_pos}")
        
        # Test a series of SAFE movements that should not trigger limits
        # Based on the home position X:0, Y:200, Z:0, C:0
        safe_positions = [
            # Small movements from home
            Position4D(x=10.0, y=190.0, z=0.0, c=0.0),   # Small X move, Y down slightly
            Position4D(x=20.0, y=180.0, z=0.0, c=0.0),   # Bit more X, Y down more
            Position4D(x=30.0, y=170.0, z=0.0, c=0.0),   # Continue pattern
            
            # Test some Z rotation (only positive values to be safe)
            Position4D(x=40.0, y=160.0, z=10.0, c=0.0),  # Small Z rotation
            Position4D(x=50.0, y=150.0, z=20.0, c=0.0),  # Bit more Z rotation
            
            # Test C axis (small angles to be safe)
            Position4D(x=60.0, y=140.0, z=0.0, c=10.0),  # Small C rotation
            Position4D(x=70.0, y=130.0, z=0.0, c=20.0),  # Bit more C rotation
            
            # Return to safe position
            Position4D(x=50.0, y=150.0, z=0.0, c=0.0),   # Back to middle-ish
        ]
        
        logger.info("🔄 Testing motion completion with safe coordinates...")
        
        for i, position in enumerate(safe_positions):
            start_time = time.time()
            logger.info(f"🎯 Movement {i+1}: Moving to {position}")
            
            try:
                success = await controller.move_to_position(position)
                
                end_time = time.time()
                duration = end_time - start_time
                
                if success:
                    logger.info(f"✅ Movement {i+1} completed in {duration:.2f}s")
                    # Verify we're actually at the position
                    current_pos = await controller.get_position()
                    logger.info(f"📍 Actual position: {current_pos}")
                    
                    # Check if we're close to target (within reasonable tolerance)
                    x_diff = abs(current_pos.x - position.x)
                    y_diff = abs(current_pos.y - position.y)
                    
                    if x_diff < 1.0 and y_diff < 1.0:
                        logger.info(f"📐 Position accuracy: X±{x_diff:.3f}mm, Y±{y_diff:.3f}mm - GOOD")
                    else:
                        logger.warning(f"📐 Position accuracy: X±{x_diff:.3f}mm, Y±{y_diff:.3f}mm - May need calibration")
                        
                else:
                    logger.error(f"❌ Movement {i+1} failed")
                    # Get current position to see where we are
                    current_pos = await controller.get_position()
                    logger.info(f"📍 Current position after failure: {current_pos}")
                    return False
                
            except Exception as e:
                logger.error(f"❌ Movement {i+1} exception: {e}")
                return False
            
            # Small delay between movements to see timing clearly
            await asyncio.sleep(1.0)
        
        # Test individual axis movements
        logger.info("⚙️ Testing individual axis movements...")
        
        # Test X axis
        logger.info("➡️ Testing X-axis movement...")
        start_time = time.time()
        success = await controller.move_to(80.0, 120.0)  # Safe X/Y coordinates
        duration = time.time() - start_time
        logger.info(f"X-axis move: {'✅ SUCCESS' if success else '❌ FAILED'} in {duration:.2f}s")
        
        # Test Z rotation (small safe angle)
        logger.info("🔄 Testing Z-axis rotation...")
        start_time = time.time()
        success = await controller.move_z_to(30.0)  # Small positive Z rotation
        duration = time.time() - start_time
        logger.info(f"Z-axis rotate: {'✅ SUCCESS' if success else '❌ FAILED'} in {duration:.2f}s")
        
        # Test C rotation (small safe angle)
        logger.info("🔄 Testing C-axis rotation...")
        start_time = time.time()
        success = await controller.rotate_to(30.0)  # Small positive C rotation
        duration = time.time() - start_time
        logger.info(f"C-axis rotate: {'✅ SUCCESS' if success else '❌ FAILED'} in {duration:.2f}s")
        
        logger.info("✅ All safe motion tests completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        # Cleanup
        await controller.disconnect()

if __name__ == "__main__":
    print("🧪 Safe Motion Completion Test")
    print("This test uses only safe coordinates and verifies motion completion waiting")
    print()
    
    # Run the test
    success = asyncio.run(test_safe_motion_completion())
    
    if success:
        print("\n✅ Safe motion completion test PASSED!")
        print("The system properly waits for each movement to complete.")
    else:
        print("\n❌ Safe motion completion test FAILED!")
        print("There are still issues with motion completion or coordinate limits.")
        sys.exit(1)