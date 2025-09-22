#!/usr/bin/env python3
"""
Test FluidNC work coordinate offset reset functionality.

This script tests the proper work coordinate reset commands
to ensure Z-axis positioning works correctly without accumulation.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add the project directory to the path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from core.config_manager import ConfigManager
from motion.base import Position4D
from motion.fluidnc_controller import create_fluidnc_controller
from core.logging_setup import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_coordinate_reset():
    """Test work coordinate offset reset functionality"""
    
    # Load configuration
    config_path = project_dir / "config" / "system_config.yaml"
    config_manager = ConfigManager(config_path)
    
    # Create controller
    controller = create_fluidnc_controller(config_manager)
    
    try:
        # Connect to FluidNC
        logger.info("Connecting to FluidNC...")
        await controller.connect()
        logger.info("Connected successfully!")
        
        # Test 1: Check current work coordinate state
        logger.info("\n=== Test 1: Current Work Coordinate State ===")
        await controller._send_command('$#')  # Show all work coordinate offsets
        await asyncio.sleep(1.0)
        await controller._send_command('$G')  # Show current coordinate system
        await asyncio.sleep(1.0)
        
        # Test 2: Get current position
        logger.info("\n=== Test 2: Current Position ===")
        position = await controller.get_current_position()
        if position:
            logger.info(f"Current position: {position}")
        else:
            logger.warning("Could not get current position")
            return
        
        # Test 3: Reset work coordinate offsets
        logger.info("\n=== Test 3: Reset Work Coordinate Offsets ===")
        success = await controller.reset_work_coordinate_offsets()
        if success:
            logger.info("Work coordinate reset completed successfully")
        else:
            logger.error("Work coordinate reset failed")
        
        # Test 4: Check position after reset
        logger.info("\n=== Test 4: Position After Reset ===")
        position_after = await controller.get_current_position()
        if position_after:
            logger.info(f"Position after reset: {position_after}")
        else:
            logger.warning("Could not get position after reset")
            return
        
        # Test 5: Test Z-axis movement to verify no accumulation
        logger.info("\n=== Test 5: Test Z-Axis Movement ===")
        
        # Move Z to 30 degrees
        logger.info("Moving Z to 30°...")
        target1 = Position4D(x=position_after.x, y=position_after.y, z=30.0, c=position_after.c)
        await controller.move_to_position(target1)
        await asyncio.sleep(2.0)
        
        pos1 = await controller.get_current_position()
        if pos1:
            logger.info(f"Position after Z=30°: {pos1}")
        
        # Move Z to 60 degrees  
        logger.info("Moving Z to 60°...")
        target2 = Position4D(x=pos1.x, y=pos1.y, z=60.0, c=pos1.c)
        await controller.move_to_position(target2)
        await asyncio.sleep(2.0)
        
        pos2 = await controller.get_current_position()
        if pos2:
            logger.info(f"Position after Z=60°: {pos2}")
        
        # Move Z back to 0 degrees
        logger.info("Moving Z back to 0°...")
        target3 = Position4D(x=pos2.x, y=pos2.y, z=0.0, c=pos2.c)
        await controller.move_to_position(target3)
        await asyncio.sleep(2.0)
        
        pos3 = await controller.get_current_position()
        if pos3:
            logger.info(f"Position after Z=0°: {pos3}")
        
        # Analyze results
        logger.info("\n=== Analysis ===")
        if pos1 and pos2 and pos3:
            z_values = [pos1.z, pos2.z, pos3.z]
            expected = [30.0, 60.0, 0.0]
            
            logger.info(f"Z positions: {z_values}")
            logger.info(f"Expected:    {expected}")
            
            # Check for accumulation (old problem was ~54° accumulation)
            if abs(pos1.z - 30.0) < 1.0 and abs(pos2.z - 60.0) < 1.0 and abs(pos3.z - 0.0) < 1.0:
                logger.info("✅ SUCCESS: Z-axis positioning is accurate, no accumulation detected!")
            else:
                logger.warning("⚠️  WARNING: Z-axis positioning may still have issues")
                
                # Check if we have the old accumulation pattern
                if abs(pos2.z - pos1.z - 54.0) < 5.0:  # ~54° accumulation
                    logger.error("❌ FAILED: Still seeing ~54° accumulation pattern")
                else:
                    logger.info("At least the old accumulation pattern is gone")
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        
    finally:
        # Disconnect
        try:
            await controller.disconnect()
            logger.info("Disconnected from FluidNC")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_coordinate_reset())