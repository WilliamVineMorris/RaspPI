#!/usr/bin/env python3
"""
Minimal Movement Test

This test uses the smallest possible movements from the home position
to verify motion completion works, avoiding soft limit issues.
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

async def test_minimal_movement():
    """Test minimal movements to verify motion completion works"""
    
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
        
        # Get current position (don't home, use current position as-is)
        current_pos = await controller.get_position()
        logger.info(f"📍 Starting position: {current_pos}")
        
        # Try to disable soft limits first
        logger.info("🔧 Attempting to disable soft limits for testing...")
        try:
            success, response = controller.protocol.send_command_with_motion_wait("$20=0")
            logger.info(f"📋 Soft limits disable: {response}")
            await asyncio.sleep(1.0)  # Let setting take effect
        except:
            logger.warning("⚠️ Could not disable soft limits, proceeding anyway...")
        
        # Test very small movements from current position
        logger.info("🔄 Testing minimal movements from current position...")
        
        # Start with 1mm movements in positive directions only
        small_movements = [
            # Tiny X movements
            Position4D(x=current_pos.x + 1.0, y=current_pos.y, z=current_pos.z, c=current_pos.c),
            Position4D(x=current_pos.x + 2.0, y=current_pos.y, z=current_pos.z, c=current_pos.c),
            Position4D(x=current_pos.x + 1.0, y=current_pos.y, z=current_pos.z, c=current_pos.c),  # Back
            Position4D(x=current_pos.x, y=current_pos.y, z=current_pos.z, c=current_pos.c),        # Back to start
        ]
        
        for i, position in enumerate(small_movements):
            start_time = time.time()
            logger.info(f"🎯 Micro-movement {i+1}: {position}")
            
            try:
                success = await controller.move_to_position(position)
                duration = time.time() - start_time
                
                if success:
                    logger.info(f"✅ Micro-movement {i+1} completed in {duration:.2f}s")
                    actual_pos = await controller.get_position()
                    logger.info(f"📍 Actual position: {actual_pos}")
                    
                    # Check if motion completion actually waited
                    if duration > 0.5:  # Should take some time for real motion
                        logger.info(f"⏱️ Motion completion waiting worked - took {duration:.2f}s")
                    else:
                        logger.warning(f"⚠️ Motion completed very quickly ({duration:.2f}s) - may not be waiting")
                else:
                    logger.error(f"❌ Micro-movement {i+1} failed")
                    # Continue with next movement
                    
            except Exception as e:
                logger.error(f"❌ Micro-movement {i+1} exception: {e}")
            
            await asyncio.sleep(0.5)
        
        # Test relative movements instead of absolute
        logger.info("🔄 Testing relative movements...")
        
        relative_movements = [
            Position4D(x=0.5, y=0.0, z=0.0, c=0.0),    # 0.5mm right
            Position4D(x=0.0, y=-0.5, z=0.0, c=0.0),   # 0.5mm forward (Y negative from home pos)
            Position4D(x=-0.5, y=0.0, z=0.0, c=0.0),   # Back left
            Position4D(x=0.0, y=0.5, z=0.0, c=0.0),    # Back to start
        ]
        
        for i, delta in enumerate(relative_movements):
            start_time = time.time()
            logger.info(f"🎯 Relative move {i+1}: {delta}")
            
            try:
                success = await controller.move_relative(delta)
                duration = time.time() - start_time
                
                if success:
                    logger.info(f"✅ Relative move {i+1} completed in {duration:.2f}s")
                    actual_pos = await controller.get_position()
                    logger.info(f"📍 Position after relative move: {actual_pos}")
                else:
                    logger.error(f"❌ Relative move {i+1} failed")
                    
            except Exception as e:
                logger.error(f"❌ Relative move {i+1} exception: {e}")
            
            await asyncio.sleep(0.5)
        
        # Re-enable soft limits
        logger.info("🔧 Re-enabling soft limits...")
        try:
            success, response = controller.protocol.send_command_with_motion_wait("$20=1")
            logger.info(f"📋 Soft limits re-enable: {response}")
        except:
            logger.warning("⚠️ Could not re-enable soft limits")
        
        logger.info("✅ Minimal movement test completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        # Cleanup
        await controller.disconnect()

if __name__ == "__main__":
    print("🔬 Minimal Movement Test")
    print("Testing motion completion with the smallest possible movements")
    print()
    
    # Run the test
    success = asyncio.run(test_minimal_movement())
    
    if success:
        print("\n✅ Minimal movement test completed!")
        print("Check logs to see if motion completion timing worked properly.")
    else:
        print("\n❌ Minimal movement test failed!")
        sys.exit(1)