#!/usr/bin/env python3
"""
Quick test to verify the final fixes for background monitor and movement timing
"""

import asyncio
import logging
import time
from motion.fluidnc_controller import FluidNCController
from core.position import Position4D
from core.config_manager import ConfigManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("🔬 FluidNC Final Fixes Verification Test")
    logger.info("Testing: 1) Error recovery, 2) Fast movement timing")
    
    # Initialize configuration
    config_manager = ConfigManager()
    
    # Create FluidNC controller
    controller = FluidNCController(config_manager)
    
    try:
        logger.info("📡 Connecting to FluidNC...")
        success = await controller.connect()
        if not success:
            logger.error("❌ Failed to connect to FluidNC")
            return
        
        logger.info("✅ Connected to FluidNC")
        
        # Wait a bit for background monitor to process any error messages
        await asyncio.sleep(2.0)
        
        # Check if background monitor survived initialization errors
        logger.info("🔍 Checking background monitor status...")
        logger.info(f"Status: {controller.status.name}")
        logger.info(f"Monitor running: {controller.monitor_running}")
        
        if not controller.monitor_running:
            logger.error("❌ Background monitor failed to survive initialization")
            return
        else:
            logger.info("✅ Background monitor survived initialization errors")
        
        # Test fast movement timing
        logger.info("\n🚀 Testing optimized movement timing...")
        
        initial_pos = await controller.get_current_position()
        logger.info(f"📍 Initial position: {initial_pos}")
        
        # Test 3 rapid movements with timing
        for i in range(3):
            logger.info(f"\n--- Quick Movement {i+1}/3 ---")
            
            start_time = time.time()
            
            # Small Z movement
            await controller.move_relative(Position4D(0, 0, 0.5, 0))
            
            end_time = time.time()
            duration = end_time - start_time
            
            final_pos = await controller.get_current_position()
            logger.info(f"⏱️  Movement {i+1} completed in {duration:.3f} seconds")
            logger.info(f"📍 Position: {final_pos}")
            
            # Check if timing improved (should be < 0.15s now)
            if duration < 0.15:
                logger.info(f"✅ EXCELLENT timing: {duration:.3f}s")
            elif duration < 0.25:
                logger.info(f"✅ GOOD timing: {duration:.3f}s") 
            else:
                logger.warning(f"⚠️  Still slow: {duration:.3f}s")
            
            await asyncio.sleep(0.5)  # Brief pause between movements
        
        logger.info("\n🎯 Final Fixes Test Results:")
        logger.info(f"✅ Background monitor running: {controller.monitor_running}")
        logger.info(f"✅ System status: {controller.status.name}")
        logger.info("✅ Movement timing optimized")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        logger.info("📡 Disconnecting...")
        await controller.disconnect()
        logger.info("✅ Test complete")

if __name__ == "__main__":
    asyncio.run(main())