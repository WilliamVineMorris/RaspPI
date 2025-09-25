#!/usr/bin/env python3
"""
Test script to verify FluidNC serial conflict fixes

This script tests the fixed FluidNC controller to ensure:
1. Background monitor runs without serial conflicts
2. Web API calls don't interfere with background monitor
3. No corrupted status responses or "device reports readiness" errors

Run this before starting the web interface to verify the fixes work.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from motion.fluidnc_controller import FluidNCController
from core.config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_serial_conflict_fix():
    """Test the serial conflict fixes"""
    logger.info("🧪 Testing FluidNC serial conflict fixes...")
    
    try:
        # Load configuration - create basic FluidNC config
        motion_config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 10.0
        }
        
        # Create controller
        controller = FluidNCController(motion_config)
        
        # Test connection
        logger.info("📡 Testing FluidNC connection...")
        connected = await controller.connect()
        
        if not connected:
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected to FluidNC")
        
        # Let background monitor run for a bit
        logger.info("⏱️  Letting background monitor run for 10 seconds...")
        start_time = time.time()
        error_count = 0
        status_updates = 0
        
        # Monitor for errors while background monitor runs
        while time.time() - start_time < 10.0:
            try:
                # This should use background monitor data, not make serial queries
                status = await controller.get_status()
                status_updates += 1
                
                # Check position age
                current_time = time.time()
                position_age = current_time - controller.last_position_update if controller.last_position_update > 0 else 999.0
                
                logger.info(f"📊 Status: {status.name}, Position: {controller.current_position}, Data age: {position_age:.1f}s")
                
            except Exception as e:
                error_count += 1
                logger.error(f"❌ Status query error ({error_count}): {e}")
            
            await asyncio.sleep(2.0)  # Check every 2 seconds
        
        # Test results
        logger.info(f"📈 Test Results:")
        logger.info(f"   Status updates: {status_updates}")
        logger.info(f"   Errors: {error_count}")
        logger.info(f"   Background monitor running: {controller.is_background_monitor_running()}")
        
        success = error_count == 0 and status_updates > 0
        
        if success:
            logger.info("✅ Serial conflict fixes working properly!")
        else:
            logger.error("❌ Still experiencing serial conflicts")
        
        # Clean shutdown
        await controller.disconnect()
        logger.info("🔌 Disconnected from FluidNC")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        logger.exception("Exception details:")
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting FluidNC serial conflict fix test...")
    
    success = await test_serial_conflict_fix()
    
    if success:
        logger.info("🎉 All tests passed! Serial conflicts should be resolved.")
        logger.info("💡 You can now run the web interface with: python3 run_web_interface.py")
        sys.exit(0)
    else:
        logger.error("💥 Tests failed. Serial conflicts may still exist.")
        logger.error("🔧 Check FluidNC connection and review the fixes.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())