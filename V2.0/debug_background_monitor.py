#!/usr/bin/env python3
"""
Debug Background Monitor - Check if background status monitoring is working
"""
import asyncio
import time
import logging
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_manager import ConfigManager
from motion.motion_controller_adapter import MotionControllerAdapter
from core.position import Position4D

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def debug_background_monitor():
    """Debug the background monitor task"""
    try:
        logger.info("🚀 Starting Background Monitor Debug")
        
        # Initialize motion controller
        config_manager = ConfigManager("config/scanner_config.yaml")
        motion_adapter = MotionControllerAdapter(config_manager)
        
        # Initialize the motion controller
        logger.info("Initializing motion controller...")
        await motion_adapter.initialize()
        
        if not motion_adapter.is_connected():
            logger.error("❌ Motion controller not connected - cannot debug monitor")
            return
        
        # Check if we have access to the FluidNC controller
        fluidnc_controller = motion_adapter.controller
        if not fluidnc_controller:
            logger.error("❌ FluidNC controller not accessible")
            return
        
        logger.info(f"✅ Motion controller connected: {fluidnc_controller}")
        
        # Check background monitor status
        is_monitor_running = fluidnc_controller.is_background_monitor_running()
        logger.info(f"🔍 Background monitor running: {is_monitor_running}")
        
        if hasattr(fluidnc_controller, 'background_monitor_task'):
            task = fluidnc_controller.background_monitor_task
            if task:
                logger.info(f"📝 Monitor task exists: done={task.done()}, cancelled={task.cancelled()}")
                if task.done():
                    try:
                        exception = task.exception()
                        if exception:
                            logger.error(f"💥 Monitor task failed with: {exception}")
                    except:
                        logger.info("✅ Monitor task completed successfully")
            else:
                logger.warning("⚠️  No background monitor task found")
        
        # Check current position cache
        current_pos = fluidnc_controller.current_position
        logger.info(f"📍 Current cached position: {current_pos}")
        
        # Check position update timestamp
        if hasattr(fluidnc_controller, 'last_position_update'):
            last_update = fluidnc_controller.last_position_update
            age = time.time() - last_update if last_update > 0 else -1
            logger.info(f"⏱️  Last position update: {age:.1f} seconds ago")
        else:
            logger.warning("⚠️  No position update timestamp available")
        
        # Monitor position changes for 30 seconds
        logger.info("👀 Monitoring position changes for 30 seconds...")
        start_time = time.time()
        last_logged_position = current_pos
        changes_detected = 0
        
        while time.time() - start_time < 30:
            current_pos = fluidnc_controller.current_position
            
            # Check if position changed
            if current_pos != last_logged_position:
                changes_detected += 1
                logger.info(f"🔄 Position change #{changes_detected}: {last_logged_position} → {current_pos}")
                last_logged_position = current_pos
            
            # Check position age
            if hasattr(fluidnc_controller, 'last_position_update'):
                age = time.time() - fluidnc_controller.last_position_update if fluidnc_controller.last_position_update > 0 else -1
                if age > 5.0:
                    logger.warning(f"⚠️  Position data is stale ({age:.1f}s old)")
            
            await asyncio.sleep(0.5)  # Check every 500ms
        
        logger.info(f"📊 Position monitoring complete - detected {changes_detected} changes")
        
        # Try restarting background monitor if it seems stuck
        if changes_detected == 0 and is_monitor_running:
            logger.warning("🔄 No position changes detected - trying to restart background monitor")
            try:
                if hasattr(fluidnc_controller, 'restart_background_monitor'):
                    await fluidnc_controller.restart_background_monitor()
                    logger.info("✅ Background monitor restart attempted")
                else:
                    logger.warning("⚠️  No restart method available")
            except Exception as e:
                logger.error(f"❌ Failed to restart background monitor: {e}")
        
        # Final status check
        final_monitor_status = fluidnc_controller.is_background_monitor_running()
        final_position = fluidnc_controller.current_position
        logger.info(f"🏁 Final status - Monitor running: {final_monitor_status}, Position: {final_position}")
        
    except Exception as e:
        logger.error(f"❌ Background monitor debug failed: {e}")
        logger.exception("Debug exception details:")
    
    finally:
        # Cleanup
        if 'motion_adapter' in locals():
            try:
                await motion_adapter.shutdown()
                logger.info("✅ Motion adapter shutdown complete")
            except:
                pass

if __name__ == "__main__":
    asyncio.run(debug_background_monitor())