#!/usr/bin/env python3
"""
Simple Homing Test
Tests the simplified homing approach that just sends $H and monitors status
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_simple_homing():
    """Test the simplified homing system"""
    logger.info("🧪 Testing Simplified Homing System")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Import motion controller
        from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
        
        # Create motion controller configuration
        motion_config = {
            'port': '/dev/ttyUSB0',
            'baud_rate': 115200,
            'command_timeout': 10.0
        }
        
        controller = SimplifiedFluidNCControllerFixed(config=motion_config)
        
        logger.info("🔌 Connecting to FluidNC...")
        if not await controller.connect():
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected to FluidNC")
        
        # Get initial status
        initial_status = await controller.get_status()
        logger.info(f"📊 Initial status: {initial_status}")
        
        # Safety confirmation
        logger.info("\n⚠️  SAFETY WARNING:")
        logger.info("⚠️  Ensure all axes can move freely to limit switches!")
        logger.info("⚠️  Be ready to hit emergency stop if needed!")
        
        input("\nPress Enter when ready to test homing (or Ctrl+C to cancel): ")
        
        # Test homing
        logger.info("\n🚀 Starting simplified homing test...")
        
        homing_success = await controller.home()
        
        if homing_success:
            logger.info("✅ Homing completed successfully!")
            
            # Check final position
            final_position = await controller.get_position()
            logger.info(f"🎯 Final position: {final_position}")
            
            # Check final status
            final_status = await controller.get_status()
            logger.info(f"📊 Final status: {final_status}")
            
        else:
            logger.error("❌ Homing failed!")
        
        # Disconnect
        await controller.disconnect()
        logger.info("🔌 Disconnected from FluidNC")
        
        return homing_success
        
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_simple_homing())
        if success:
            logger.info("\n✅ Simple homing test passed!")
            logger.info("🎉 Homing system is working correctly")
        else:
            logger.error("\n❌ Simple homing test failed!")
            logger.error("🔧 Check FluidNC connection and hardware")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)