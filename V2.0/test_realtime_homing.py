#!/usr/bin/env python3
"""
Test Real-time Homing System
Tests the new status-based homing system that monitors FluidNC status changes
instead of using fixed timeouts.
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_realtime_homing():
    """Test the new real-time status-based homing system"""
    logger.info("🧪 Testing Real-time Homing System")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Import motion controller here to avoid import issues
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
        
        # Test real-time homing
        logger.info("\n🏠 Testing Real-time Homing System")
        logger.info("⚠️  SAFETY: Ensure all axes can move freely to limit switches!")
        logger.info("⚠️  SAFETY: Be ready to hit emergency stop if needed!")
        
        # Wait for user confirmation
        input("\nPress Enter when ready to test homing (or Ctrl+C to cancel): ")
        
        logger.info("\n🚀 Starting real-time homing test...")
        
        # Test basic homing
        homing_success = await controller.home()
        
        if homing_success:
            logger.info("✅ Real-time homing completed successfully!")
            
            # Check final position
            final_position = await controller.get_position()
            logger.info(f"🎯 Final position: {final_position}")
            
            # Verify we're at home (0,0,0,0)
            if (abs(final_position.x) < 0.1 and abs(final_position.y) < 0.1 and 
                abs(final_position.z) < 0.1 and abs(final_position.c) < 0.1):
                logger.info("✅ Position verification: Correctly at home position")
            else:
                logger.warning(f"⚠️ Position verification: Not exactly at home - {final_position}")
        else:
            logger.error("❌ Real-time homing failed!")
        
        # Test homing with status callback (web interface compatibility)
        logger.info("\n🌐 Testing homing with status callback...")
        
        # Create status callback
        status_messages = []
        def status_callback(status_type, message):
            status_messages.append(f"[{status_type}] {message}")
            logger.info(f"📱 Status callback: [{status_type}] {message}")
        
        # Test callback homing
        callback_success = await controller.home_with_status_callback(status_callback)
        
        if callback_success:
            logger.info("✅ Callback homing completed successfully!")
            logger.info(f"📋 Status messages received: {len(status_messages)}")
            for msg in status_messages:
                logger.info(f"   {msg}")
        else:
            logger.error("❌ Callback homing failed!")
        
        # Disconnect
        await controller.disconnect()
        logger.info("🔌 Disconnected from FluidNC")
        
        return homing_success and callback_success
        
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_protocol_directly():
    """Test the protocol layer directly for detailed debugging"""
    logger.info("\n🔬 Testing Protocol Layer Directly")
    logger.info("=" * 40)
    
    try:
        from motion.simplified_fluidnc_protocol_fixed import SimplifiedFluidNCProtocolFixed
        
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Create protocol instance
        protocol = SimplifiedFluidNCProtocolFixed(
            port='/dev/ttyUSB0',
            baud_rate=115200
        )
        
        logger.info("🔌 Connecting protocol...")
        if not protocol.connect():
            logger.error("❌ Protocol connection failed")
            return False
        
        logger.info("✅ Protocol connected")
        
        # Test direct homing command
        logger.info("🏠 Testing direct homing command...")
        
        # Wait for user confirmation
        input("\nPress Enter to send $H command directly (or Ctrl+C to cancel): ")
        
        success, response = protocol.send_homing_command()
        
        logger.info(f"📤 Homing command result: success={success}, response='{response}'")
        
        # Disconnect
        protocol.disconnect()
        logger.info("🔌 Protocol disconnected")
        
        return success
        
    except KeyboardInterrupt:
        logger.info("\n⏸️  Protocol test interrupted by user")
        return False
    except Exception as e:
        logger.error(f"❌ Protocol test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    logger.info("🧪 Real-time Homing Test Suite")
    logger.info("=" * 50)
    
    # Check if we should test protocol directly
    test_protocol = "--protocol" in sys.argv
    
    if test_protocol:
        success = await test_protocol_directly()
    else:
        success = await test_realtime_homing()
    
    if success:
        logger.info("\n✅ All tests passed!")
        logger.info("🎉 Real-time homing system is working correctly")
    else:
        logger.error("\n❌ Some tests failed!")
        logger.error("🔧 Check FluidNC connection and configuration")
    
    return success

if __name__ == "__main__":
    # Run the test
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⏸️  Test suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test suite failed: {e}")
        sys.exit(1)