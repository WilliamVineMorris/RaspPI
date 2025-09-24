#!/usr/bin/env python3
"""
Manual Background Monitor Restart Script
Use this to restart the background monitor if it's not running properly
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

async def restart_monitor():
    """Restart the background monitor"""
    try:
        from scanning.scan_orchestrator import ScanOrchestrator
        
        # Try to access the orchestrator that should already be running
        # This is a quick fix to restart the monitor
        logger.info("🔄 Attempting to restart background monitor...")
        
        # We need to access the existing orchestrator instance
        # Since we're running alongside the web interface, let's try a different approach
        
        # Import the FluidNC controller directly
        from motion.fluidnc_controller import FluidNCController
        
        # Create a temporary connection to restart monitor
        motion_config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 10.0
        }
        
        controller = FluidNCController(motion_config)
        
        # Try to connect and restart monitor
        if await controller.connect():
            logger.info("✅ Connected to FluidNC")
            
            # Force restart the background monitor
            await controller.restart_background_monitor()
            logger.info("✅ Background monitor restarted")
            
            # Keep alive for a moment to let it start
            await asyncio.sleep(2)
            
            logger.info("🎉 Monitor restart complete")
            return True
        else:
            logger.error("❌ Could not connect to FluidNC")
            return False
            
    except Exception as e:
        logger.error(f"❌ Failed to restart monitor: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main function"""
    logger.info("🛠️ Manual Background Monitor Restart")
    logger.info("This will attempt to restart the FluidNC background monitor")
    
    success = await restart_monitor()
    
    if success:
        logger.info("✅ Background monitor restart successful")
        logger.info("📊 Check the main application logs for 'Background status monitor started'")
        return 0
    else:
        logger.error("❌ Background monitor restart failed")
        return 1

if __name__ == "__main__":
    """Run the restart"""
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        logger.info("Restart interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Restart failed with exception: {e}")
        sys.exit(1)