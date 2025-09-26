#!/usr/bin/env python3
"""
FluidNC Limits Diagnostic Script

This script checks the actual soft limits configured in FluidNC
and helps diagnose coordinate limit issues.
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

async def check_fluidnc_limits():
    """Check FluidNC limits and configuration"""
    
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
        
        # Get FluidNC settings
        logger.info("🔍 Checking FluidNC configuration...")
        
        # Query soft limits
        settings_to_check = [
            "$20",  # Soft limits enable
            "$130", # X max travel
            "$131", # Y max travel  
            "$132", # Z max travel
            "$133", # A/C max travel
        ]
        
        for setting in settings_to_check:
            success, response = controller.protocol.send_command_with_motion_wait(setting)
            logger.info(f"📋 {setting}: {response}")
            await asyncio.sleep(0.5)
        
        # Get current position
        current_pos = await controller.get_position()
        logger.info(f"📍 Current position: {current_pos}")
        
        # Test small safe movements to understand coordinate system
        logger.info("🧪 Testing safe coordinate movements...")
        
        safe_test_positions = [
            Position4D(x=10.0, y=10.0, z=0.0, c=0.0),   # Small positive movement
            Position4D(x=50.0, y=50.0, z=10.0, c=10.0), # Medium positive movement
            Position4D(x=100.0, y=100.0, z=0.0, c=0.0), # Larger positive movement
        ]
        
        for i, pos in enumerate(safe_test_positions):
            logger.info(f"🎯 Testing movement {i+1}: {pos}")
            
            try:
                # Test X/Y movement first
                success = await controller.move_to(pos.x, pos.y)
                if success:
                    logger.info(f"✅ X/Y movement successful")
                    
                    # Test Z movement
                    success = await controller.move_z_to(pos.z)
                    if success:
                        logger.info(f"✅ Z movement successful")
                    else:
                        logger.warning(f"❌ Z movement failed to {pos.z}°")
                        
                    # Test C movement  
                    success = await controller.rotate_to(pos.c)
                    if success:
                        logger.info(f"✅ C movement successful")
                    else:
                        logger.warning(f"❌ C movement failed to {pos.c}°")
                        
                else:
                    logger.warning(f"❌ X/Y movement failed to ({pos.x}, {pos.y})")
                    
            except Exception as e:
                logger.error(f"❌ Movement test {i+1} failed: {e}")
                
            # Small delay between tests
            await asyncio.sleep(1.0)
        
        # Test Z-axis range specifically
        logger.info("🔄 Testing Z-axis rotation range...")
        z_test_angles = [0.0, 10.0, -10.0, 30.0, -30.0]
        
        for angle in z_test_angles:
            logger.info(f"🔄 Testing Z rotation to {angle}°...")
            try:
                success = await controller.move_z_to(angle)
                if success:
                    logger.info(f"✅ Z rotation to {angle}° successful")
                else:
                    logger.warning(f"❌ Z rotation to {angle}° failed")
            except Exception as e:
                logger.error(f"❌ Z rotation to {angle}° error: {e}")
            
            await asyncio.sleep(0.5)
        
        logger.info("✅ FluidNC limits diagnostic completed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Diagnostic failed with error: {e}")
        return False
        
    finally:
        # Cleanup
        await controller.disconnect()

if __name__ == "__main__":
    print("🔍 FluidNC Limits Diagnostic")
    print("This script checks FluidNC configuration and tests safe movements")
    print()
    
    # Run the diagnostic
    success = asyncio.run(check_fluidnc_limits())
    
    if success:
        print("\n✅ FluidNC diagnostic completed!")
        print("Check the logs above for limit information and movement test results.")
    else:
        print("\n❌ FluidNC diagnostic failed!")
        print("Check FluidNC connection and configuration.")
        sys.exit(1)