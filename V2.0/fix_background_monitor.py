#!/usr/bin/env python3
"""
Quick Fix Background Monitor - Restart if not working
"""
import asyncio
import logging
import sys
import os
import time

# Add project root to path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_manager import ConfigManager
from motion.motion_controller_adapter import MotionControllerAdapter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def fix_background_monitor():
    """Check and restart background monitor if needed"""
    motion_adapter = None
    try:
        logger.info("🔧 Checking background monitor status...")
        
        # Initialize motion controller
        config_manager = ConfigManager("config/scanner_config.yaml") 
        motion_adapter = MotionControllerAdapter(config_manager)
        
        # Initialize
        await motion_adapter.initialize()
        if not motion_adapter.is_connected():
            logger.error("❌ Motion controller not connected")
            return False
        
        # Get FluidNC controller
        controller = motion_adapter.controller
        if not controller:
            logger.error("❌ FluidNC controller not available")
            return False
        
        # Check monitor status
        is_running = controller.is_background_monitor_running()
        logger.info(f"📊 Background monitor running: {is_running}")
        
        # Check task status
        task_exists = controller.background_monitor_task is not None
        task_done = controller.background_monitor_task.done() if task_exists else True
        
        logger.info(f"📝 Task exists: {task_exists}, Task done: {task_done}")
        
        # Check position freshness  
        if hasattr(controller, 'last_position_update'):
            age = time.time() - controller.last_position_update if controller.last_position_update > 0 else -1
            logger.info(f"⏱️  Position data age: {age:.1f} seconds")
        
        # Restart if needed
        if not is_running or task_done or (hasattr(controller, 'last_position_update') and time.time() - controller.last_position_update > 10):
            logger.warning("🔄 Background monitor needs restart")
            
            if hasattr(controller, 'restart_background_monitor'):
                logger.info("🚀 Restarting background monitor...")
                await controller.restart_background_monitor()
                
                # Wait a bit and check again
                await asyncio.sleep(2)
                new_status = controller.is_background_monitor_running()
                logger.info(f"✅ Monitor status after restart: {new_status}")
                
                return new_status
            else:
                logger.error("❌ No restart method available")
                return False
        else:
            logger.info("✅ Background monitor appears to be working correctly")
            return True
            
    except Exception as e:
        logger.error(f"❌ Fix failed: {e}")
        return False
    finally:
        if motion_adapter:
            try:
                await motion_adapter.shutdown()
            except:
                pass

if __name__ == "__main__":
    result = asyncio.run(fix_background_monitor())
    if result:
        print("✅ Background monitor is working")
    else:
        print("❌ Background monitor fix failed")
        print("Try: 1) Restart web server, 2) Check FluidNC connection, 3) Reboot Pi")