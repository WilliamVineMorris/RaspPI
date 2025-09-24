#!/usr/bin/env python3
"""
Quick Fix Background Monitor - Restart if not working
This script directly fixes the background monitor without web server dependencies
"""
import asyncio
import logging
import sys
import os
import time
import signal

# Add project root to path  
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_manager import ConfigManager
from motion.motion_controller_adapter import MotionControllerAdapter

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Global variable for cleanup
motion_adapter = None

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global motion_adapter
    logger.info("🛑 Interrupt received, shutting down...")
    if motion_adapter:
        try:
            asyncio.create_task(motion_adapter.shutdown())
        except:
            pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

async def fix_background_monitor():
    """Check and restart background monitor if needed"""
    global motion_adapter
    try:
        logger.info("🔧 Checking background monitor status...")
        
        # Initialize motion controller
        config_manager = ConfigManager("config/scanner_config.yaml") 
        motion_adapter = MotionControllerAdapter(config_manager)
        
        # Initialize
        logger.info("🔌 Connecting to FluidNC...")
        await motion_adapter.initialize()
        if not motion_adapter.is_connected():
            logger.error("❌ Motion controller not connected")
            return False
        
        # Get FluidNC controller
        controller = motion_adapter.controller
        if not controller:
            logger.error("❌ FluidNC controller not available")
            return False
        
        logger.info("✅ Connected to FluidNC controller")
        
        # Check monitor status
        is_running = controller.is_background_monitor_running()
        logger.info(f"📊 Background monitor running: {is_running}")
        
        # Check task status
        task_exists = controller.background_monitor_task is not None
        task_done = controller.background_monitor_task.done() if task_exists else True
        task_cancelled = controller.background_monitor_task.cancelled() if task_exists else False
        
        logger.info(f"📝 Task exists: {task_exists}, Task done: {task_done}, Task cancelled: {task_cancelled}")
        
        # Check position freshness  
        if hasattr(controller, 'last_position_update'):
            age = time.time() - controller.last_position_update if controller.last_position_update > 0 else -1
            logger.info(f"⏱️  Position data age: {age:.1f} seconds")
        else:
            age = -1
            logger.warning("⚠️  No position update timestamp found")
        
        # Get current position
        current_pos = controller.current_position
        logger.info(f"📍 Current cached position: {current_pos}")
        
        # Check if background monitor needs restart
        needs_restart = (
            not is_running or 
            task_done or 
            task_cancelled or
            (age > 10 and age != -1)
        )
        
        if needs_restart:
            logger.warning("🔄 Background monitor needs restart")
            
            if hasattr(controller, 'restart_background_monitor'):
                logger.info("🚀 Restarting background monitor...")
                
                # Force stop existing monitor first
                if hasattr(controller, 'monitor_running'):
                    controller.monitor_running = False
                    logger.info("🛑 Stopped existing monitor")
                
                # Wait a moment
                await asyncio.sleep(1.0)
                
                # Restart the monitor
                await controller.restart_background_monitor()
                logger.info("✅ Background monitor restart command sent")
                
                # Wait for restart and verify
                await asyncio.sleep(2.0)
                new_status = controller.is_background_monitor_running()
                logger.info(f"📊 Monitor status after restart: {new_status}")
                
                # Monitor for position updates for 10 seconds to verify it's working
                logger.info("👀 Monitoring position updates for 10 seconds...")
                start_time = time.time()
                last_pos = controller.current_position
                updates_seen = 0
                
                while time.time() - start_time < 10:
                    current_pos = controller.current_position
                    
                    if current_pos != last_pos:
                        updates_seen += 1
                        logger.info(f"🔄 Position update #{updates_seen}: {last_pos} → {current_pos}")
                        last_pos = current_pos
                    
                    # Check position age
                    if hasattr(controller, 'last_position_update'):
                        current_age = time.time() - controller.last_position_update if controller.last_position_update > 0 else -1
                        if current_age > 5.0 and current_age != -1:
                            logger.warning(f"⚠️  Position still stale ({current_age:.1f}s old)")
                    
                    await asyncio.sleep(0.5)
                
                logger.info(f"📊 Monitoring complete - saw {updates_seen} position updates")
                
                if updates_seen > 0 or controller.is_background_monitor_running():
                    logger.info("✅ Background monitor appears to be working after restart")
                    return True
                else:
                    logger.warning("⚠️  Background monitor may still have issues")
                    return False
                
            else:
                logger.error("❌ No restart method available")
                return False
        else:
            logger.info("✅ Background monitor appears to be working correctly")
            
            # Still monitor for a few seconds to verify
            logger.info("👀 Quick verification - monitoring for 5 seconds...")
            start_time = time.time()
            last_pos = controller.current_position
            updates_seen = 0
            
            while time.time() - start_time < 5:
                current_pos = controller.current_position
                if current_pos != last_pos:
                    updates_seen += 1
                    logger.info(f"🔄 Position update: {last_pos} → {current_pos}")
                    last_pos = current_pos
                
                await asyncio.sleep(0.5)
            
            logger.info(f"📊 Verification complete - saw {updates_seen} position updates")
            return True
            
    except Exception as e:
        logger.error(f"❌ Background monitor fix failed: {e}")
        logger.exception("Exception details:")
        return False
    
    finally:
        # Cleanup
        if motion_adapter:
            try:
                logger.info("🧹 Shutting down motion adapter...")
                await motion_adapter.shutdown()
                logger.info("✅ Shutdown complete")
            except Exception as e:
                logger.warning(f"⚠️  Shutdown warning: {e}")

if __name__ == "__main__":
    print("🔧 FluidNC Background Monitor Fix Tool")
    print("=====================================")
    
    try:
        result = asyncio.run(fix_background_monitor())
        
        print("\n" + "="*50)
        if result:
            print("✅ SUCCESS: Background monitor is working")
            print("📝 The position updates should now appear in the web interface")
            print("🌐 Try jogging axes in the web UI to test")
        else:
            print("❌ FAILED: Background monitor fix unsuccessful")
            print("🔄 Recommendations:")
            print("   1. Restart the web server")
            print("   2. Check FluidNC USB connection")
            print("   3. Power cycle FluidNC controller")
            print("   4. Reboot Raspberry Pi if issues persist")
        print("="*50)
    
    except KeyboardInterrupt:
        print("\n🛑 Interrupted by user")
    except Exception as e:
        print(f"\n❌ Script error: {e}")
        sys.exit(1)