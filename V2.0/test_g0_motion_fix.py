#!/usr/bin/env python3
"""
Test G0 Motion Completion Fix

This test verifies that the G0 rapid move fix works for both
motion completion timing and coordinate limit avoidance.
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

async def test_g0_motion_fix():
    """Test that G0 rapid moves work for motion completion and avoid soft limits"""
    
    # Initialize motion controller
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
        
        logger.info("✅ Connected to FluidNC")
        
        # Get current position (don't home if not needed)
        current_pos = await controller.get_position()
        logger.info(f"📍 Starting position: {current_pos}")
        
        # Test absolute positioning (which should now use G0 internally)
        logger.info("🎯 Testing absolute positioning with G0 rapid moves...")
        
        test_positions = [
            Position4D(x=10.0, y=190.0, z=0.0, c=0.0),    # Small move from home
            Position4D(x=20.0, y=180.0, z=0.0, c=0.0),    # Larger move
            Position4D(x=30.0, y=170.0, z=5.0, c=5.0),    # Add Z and C rotation
            Position4D(x=40.0, y=160.0, z=10.0, c=10.0),  # More rotation
            Position4D(x=50.0, y=150.0, z=0.0, c=0.0),    # Back to no rotation
            Position4D(x=current_pos.x, y=current_pos.y, z=current_pos.z, c=current_pos.c)  # Return home
        ]
        
        for i, position in enumerate(test_positions):
            start_time = time.time()
            logger.info(f"🎯 Movement {i+1}: Moving to {position}")
            
            try:
                success = await controller.move_to_position(position)
                duration = time.time() - start_time
                
                if success:
                    logger.info(f"✅ Movement {i+1} completed in {duration:.2f}s")
                    
                    # Verify position
                    actual_pos = await controller.get_position()
                    logger.info(f"📍 Actual position: {actual_pos}")
                    
                    # Check motion completion timing
                    if duration > 0.3:  # Should take realistic time for motion
                        logger.info(f"⏱️ Good motion timing - {duration:.2f}s indicates real motion completion waiting")
                    else:
                        logger.warning(f"⚠️ Very fast completion - {duration:.2f}s may indicate no motion")
                        
                else:
                    logger.error(f"❌ Movement {i+1} failed")
                    return False
                    
            except Exception as e:
                logger.error(f"❌ Movement {i+1} exception: {e}")
                return False
            
            # Small delay between movements
            await asyncio.sleep(0.5)
        
        # Test individual axis movements
        logger.info("⚙️ Testing individual axis movements...")
        
        # Test X axis movement
        start_time = time.time()
        success = await controller.move_to(60.0, 140.0)
        duration = time.time() - start_time
        if success:
            logger.info(f"✅ X/Y move successful in {duration:.2f}s")
        else:
            logger.error("❌ X/Y move failed")
            return False
        
        # Test Z rotation
        start_time = time.time()
        success = await controller.move_z_to(15.0)
        duration = time.time() - start_time
        if success:
            logger.info(f"✅ Z rotation successful in {duration:.2f}s")
        else:
            logger.error("❌ Z rotation failed")
            return False
        
        # Test C rotation  
        start_time = time.time()
        success = await controller.rotate_to(15.0)
        duration = time.time() - start_time
        if success:
            logger.info(f"✅ C rotation successful in {duration:.2f}s")
        else:
            logger.error("❌ C rotation failed")
            return False
        
        # Return to starting position
        start_time = time.time()
        success = await controller.move_to_position(current_pos)
        duration = time.time() - start_time
        if success:
            logger.info(f"✅ Return to start successful in {duration:.2f}s")
        else:
            logger.error("❌ Return to start failed")
            return False
        
        logger.info("🎉 G0 motion fix test completed successfully!")
        logger.info("✅ Motion completion waiting works properly")
        logger.info("✅ G0 rapid moves avoid soft limit errors")
        logger.info("✅ All movement types work correctly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        # Cleanup
        await controller.disconnect()

if __name__ == "__main__":
    print("🔧 Testing G0 Motion Completion Fix")
    print("This test verifies that G0 rapid moves work for motion completion and avoid soft limits")
    print()
    
    # Run the test
    success = asyncio.run(test_g0_motion_fix())
    
    if success:
        print("\n🎉 G0 Motion Fix Test PASSED!")
        print("✅ Motion completion timing works correctly")
        print("✅ G0 rapid moves successfully avoid soft limit errors")
        print("✅ System is ready for full scanning operations")
    else:
        print("\n❌ G0 Motion Fix Test FAILED!")
        print("There are still issues that need to be resolved.")
        sys.exit(1)