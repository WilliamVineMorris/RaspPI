#!/usr/bin/env python3
"""
Working Homing System with Proper Completion Detection
Based on the successful test results showing 'MSG:DBG: Homing done'
"""

import asyncio
import logging
import time
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_working_homing():
    """Test the homing system that properly waits for completion"""
    logger.info("🧪 Testing Working Homing System")
    logger.info("=" * 50)
    
    try:
        # Load configuration
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Import and create a simple motion controller that just uses the basic protocol
        from motion.simplified_fluidnc_protocol_fixed import SimplifiedFluidNCProtocolFixed
        
        # Create protocol instance
        protocol = SimplifiedFluidNCProtocolFixed(
            port='/dev/ttyUSB0',
            baud_rate=115200
        )
        
        logger.info("🔌 Connecting to FluidNC...")
        if not protocol.connect():
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected to FluidNC")
        
        # Check initial status
        success, response = protocol.send_command("?")
        if success:
            logger.info(f"📊 Initial status: {response}")
        
        # Clear alarm if needed
        success, response = protocol.send_command("$X")
        if success:
            logger.info(f"🔓 Unlock response: {response}")
        
        # Safety confirmation
        logger.info("\n⚠️  SAFETY WARNING:")
        logger.info("⚠️  Ensure all axes can move freely to limit switches!")
        logger.info("⚠️  Be ready to hit emergency stop if needed!")
        
        input("\nPress Enter when ready to test homing (or Ctrl+C to cancel): ")
        
        # Test homing with the fixed method
        logger.info("\n🚀 Starting working homing test...")
        
        # Use the send_homing_command method
        homing_success, homing_response = await asyncio.get_event_loop().run_in_executor(
            None, protocol.send_homing_command
        )
        
        if homing_success:
            logger.info("✅ Homing completed successfully!")
            logger.info(f"📋 Response: {homing_response}")
            
            # Check final status
            success, status_response = protocol.send_command("?")
            if success:
                logger.info(f"📊 Final status: {status_response}")
                if 'Idle' in status_response:
                    logger.info("✅ Confirmed: FluidNC is in Idle state")
                else:
                    logger.warning(f"⚠️ Unexpected status: {status_response}")
        else:
            logger.error("❌ Homing failed!")
            logger.error(f"📋 Error: {homing_response}")
        
        # Disconnect
        protocol.disconnect()
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
        success = asyncio.run(test_working_homing())
        if success:
            logger.info("\n✅ Working homing test passed!")
            logger.info("🎉 Homing system properly detects completion")
        else:
            logger.error("\n❌ Working homing test failed!")
            logger.error("🔧 Check the homing detection logic")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        sys.exit(1)