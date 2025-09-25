#!/usr/bin/env python3
"""
Test script to verify asyncio Lock event loop fix
"""

import asyncio
import sys
import os
import logging
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_motion_controller():
    """Test motion controller lock functionality"""
    try:
        from motion.fluidnc_controller import FluidNCController
        
        # Create motion controller with minimal config
        motion_config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 10.0
        }
        controller = FluidNCController(motion_config)
        
        logger.info("✅ FluidNC controller created successfully")
        
        # Test lock creation (this should work without event loop errors)
        lock = await controller._get_connection_lock()
        logger.info(f"✅ Connection lock created: {type(lock)}")
        
        # Test lock usage in context manager
        async with controller._LockContextManager(lock):
            logger.info("✅ Lock context manager works")
        
        # Test lock recreation
        controller.reset_connection_lock()
        new_lock = await controller._get_connection_lock()
        logger.info(f"✅ Lock recreation works: {type(new_lock)}")
        
        logger.info("🎉 All lock tests passed!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Lock test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    logger.info("🧪 Testing asyncio Lock event loop fix...")
    
    success = await test_motion_controller()
    
    if success:
        logger.info("✅ All tests passed - lock fix is working!")
        return 0
    else:
        logger.error("❌ Tests failed - lock issue still exists")
        return 1

if __name__ == "__main__":
    """Run the test"""
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        sys.exit(1)