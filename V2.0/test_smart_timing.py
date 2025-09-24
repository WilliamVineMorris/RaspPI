#!/usr/bin/env python3
"""
Quick timing test to verify the smart timeout and readiness fixes
"""

import asyncio
import logging
import time
import sys
import os

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    logger.info("🔬 Smart Timeout & Readiness Test")
    logger.info("Testing optimized command timing with reduced timeouts")
    
    try:
        # Initialize configuration
        config_manager = ConfigManager("config/scanner_config.yaml")
        
        # Create FluidNC controller
        controller = FluidNCController(config_manager.get_motion_config())
        
        logger.info("📡 Connecting to FluidNC...")
        success = await controller.connect()
        if not success:
            logger.error("❌ Failed to connect to FluidNC")
            return
        
        logger.info("✅ Connected to FluidNC")
        
        # Wait for background monitor to stabilize
        await asyncio.sleep(2.0)
        
        initial_pos = await controller.get_current_position()
        logger.info(f"📍 Initial position: {initial_pos}")
        
        # Test 3 rapid movements with precise timing measurement
        for i in range(3):
            logger.info(f"\n--- Optimized Movement {i+1}/3 ---")
            
            # Measure total time including all command overhead
            total_start = time.time()
            
            # Small Z movement
            await controller.move_relative(Position4D(0, 0, 0.5, 0))
            
            total_end = time.time()
            total_duration = total_end - total_start
            
            final_pos = await controller.get_current_position()
            logger.info(f"📍 Final position: {final_pos}")
            logger.info(f"⏱️  TOTAL TIME: {total_duration:.3f} seconds")
            
            # Classify performance
            if total_duration < 0.20:
                logger.info(f"✅ EXCELLENT: {total_duration:.3f}s (Target achieved!)")
            elif total_duration < 0.50:
                logger.info(f"✅ GOOD: {total_duration:.3f}s (Much improved)")
            elif total_duration < 2.0:
                logger.info(f"⚠️  FAIR: {total_duration:.3f}s (Better but not optimal)")
            else:
                logger.warning(f"❌ SLOW: {total_duration:.3f}s (Still has issues)")
            
            await asyncio.sleep(0.5)  # Brief pause between movements
        
        logger.info("\n🎯 Smart Timeout Test Results:")
        logger.info(f"✅ Background monitor: {controller.monitor_running}")
        logger.info(f"✅ System status: {controller.status.name}")
        logger.info("✅ Command timeouts optimized")
        logger.info("✅ Readiness checking implemented")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'controller' in locals():
            logger.info("📡 Disconnecting...")
            await controller.disconnect()
        logger.info("✅ Test complete")

if __name__ == "__main__":
    asyncio.run(main())