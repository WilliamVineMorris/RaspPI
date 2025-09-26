#!/usr/bin/env python3
"""
FluidNC Configuration Query Script

This script queries FluidNC settings to understand the actual coordinate limits
and configuration that's causing the error:22 soft limit violations.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def query_fluidnc_config():
    """Query FluidNC configuration to understand coordinate system"""
    
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
        
        logger.info("✅ Connected to FluidNC")
        
        # Get current position
        current_pos = await controller.get_position()
        logger.info(f"📍 Current position: {current_pos}")
        
        # Query key FluidNC settings
        logger.info("🔍 Querying FluidNC configuration...")
        
        # GRBL settings to check
        settings_queries = [
            ("$20", "Soft limits enable (0=off, 1=on)"),
            ("$21", "Hard limits enable"), 
            ("$22", "Homing cycle enable"),
            ("$23", "Homing direction invert"),
            ("$130", "X-axis max travel (mm)"),
            ("$131", "Y-axis max travel (mm)"), 
            ("$132", "Z-axis max travel (mm)"),
            ("$133", "A-axis max travel (mm)"),
            ("$$", "Show all settings"),
        ]
        
        for setting, description in settings_queries:
            logger.info(f"📋 Querying {setting}: {description}")
            try:
                success, response = controller.protocol.send_command_with_motion_wait(setting)
                if success and response:
                    logger.info(f"📋 {setting} = {response}")
                else:
                    logger.warning(f"📋 {setting} query failed: {response}")
            except Exception as e:
                logger.error(f"📋 {setting} query error: {e}")
            
            # Small delay between queries
            await asyncio.sleep(0.5)
        
        # Test if soft limits are the issue by trying to disable them
        logger.info("🔧 Testing if soft limits are the issue...")
        
        # Try to disable soft limits temporarily
        logger.info("🔧 Attempting to disable soft limits ($20=0)...")
        success, response = controller.protocol.send_command_with_motion_wait("$20=0")
        if success:
            logger.info(f"📋 Soft limits disable result: {response}")
            
            # Wait a moment for setting to take effect
            await asyncio.sleep(1.0)
            
            # Now try a small movement
            logger.info("🎯 Testing movement with soft limits disabled...")
            try:
                # Try the same movement that failed before
                from motion.base import Position4D
                test_pos = Position4D(x=10.0, y=190.0, z=0.0, c=0.0)
                success = await controller.move_to_position(test_pos)
                
                if success:
                    logger.info("✅ Movement successful with soft limits disabled!")
                    final_pos = await controller.get_position()
                    logger.info(f"📍 Final position: {final_pos}")
                else:
                    logger.error("❌ Movement still failed even with soft limits disabled")
                    
            except Exception as e:
                logger.error(f"❌ Movement test error: {e}")
            
            # Re-enable soft limits
            logger.info("🔧 Re-enabling soft limits ($20=1)...")
            success, response = controller.protocol.send_command_with_motion_wait("$20=1")
            logger.info(f"📋 Soft limits re-enable result: {response}")
            
        else:
            logger.error(f"❌ Failed to disable soft limits: {response}")
        
        # Check work coordinate systems
        logger.info("📐 Checking work coordinate systems...")
        wco_queries = [
            ("G54", "Work coordinate system 1"),
            ("G92.1", "Clear coordinate system offsets"),
            ("$#", "View coordinate parameters"),
        ]
        
        for cmd, desc in wco_queries:
            logger.info(f"📐 {desc} ({cmd})...")
            try:
                success, response = controller.protocol.send_command_with_motion_wait(cmd)
                logger.info(f"📐 {cmd} = {response}")
            except Exception as e:
                logger.error(f"📐 {cmd} error: {e}")
            await asyncio.sleep(0.5)
        
        logger.info("✅ FluidNC configuration query completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Configuration query failed: {e}")
        return False
        
    finally:
        # Cleanup
        await controller.disconnect()

if __name__ == "__main__":
    print("🔍 FluidNC Configuration Query")
    print("This script queries FluidNC settings to understand coordinate limits")
    print()
    
    # Run the query
    success = asyncio.run(query_fluidnc_config())
    
    if success:
        print("\n✅ FluidNC configuration query completed!")
        print("Check the logs above for the actual FluidNC settings.")
    else:
        print("\n❌ FluidNC configuration query failed!")
        sys.exit(1)