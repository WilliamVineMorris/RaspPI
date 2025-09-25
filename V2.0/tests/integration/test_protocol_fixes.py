#!/usr/bin/env python3
"""
Quick Test for Protocol Fixes

Tests the various FluidNC controllers to see which one handles 
timeouts best for your web interface.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


async def test_enhanced_protocol():
    """Test the enhanced protocol with timeout fixes"""
    logger.info("🧪 Testing Enhanced Protocol with Timeout Fixes...")
    
    try:
        from motion.protocol_bridge import ProtocolBridgeController
        from motion.base import Position4D
        
        # Create minimal config for testing
        config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 2.0
        }
        controller = ProtocolBridgeController(config)
        
        # Test connection
        logger.info("📡 Testing connection...")
        connected = await controller.connect()
        
        if connected:
            logger.info("✅ Enhanced protocol connected")
            
            # Test simple move
            logger.info("🔄 Testing relative move...")
            delta = Position4D(0, 0, -1, 0)  # Same as jog command that failed
            success = await controller.move_relative(delta, feedrate=10.0)
            
            if success:
                logger.info("✅ Enhanced protocol move successful")
            else:
                logger.warning("⚠️  Enhanced protocol move failed")
            
            await controller.disconnect()
            return success
        else:
            logger.error("❌ Enhanced protocol connection failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Enhanced protocol test failed: {e}")
        return False


async def test_fallback_controller():
    """Test the fallback controller"""
    logger.info("🧪 Testing Fallback Controller...")
    
    try:
        from motion.fallback_fluidnc_controller import FallbackFluidNCController
        from motion.base import Position4D
        
        # Create minimal config for testing
        config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 2.0
        }
        controller = FallbackFluidNCController(config)
        
        # Test connection
        logger.info("📡 Testing connection...")
        connected = await controller.connect()
        
        if connected:
            logger.info("✅ Fallback controller connected")
            
            # Test simple move
            logger.info("🔄 Testing relative move...")
            delta = Position4D(0, 0, -1, 0)  # Same as jog command that failed
            success = await controller.move_relative(delta, feedrate=10.0)
            
            if success:
                logger.info("✅ Fallback controller move successful")
            else:
                logger.warning("⚠️  Fallback controller move failed")
            
            await controller.disconnect()
            return success
        else:
            logger.error("❌ Fallback controller connection failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Fallback controller test failed: {e}")
        return False


async def main():
    """Test protocol fixes"""
    logger.info("🚀 Quick Protocol Fix Test")
    logger.info("=" * 50)
    
    # Test enhanced protocol
    enhanced_success = await test_enhanced_protocol()
    
    logger.info("-" * 30)
    
    # Test fallback controller
    fallback_success = await test_fallback_controller()
    
    logger.info("=" * 50)
    logger.info("📊 Test Results:")
    logger.info(f"  Enhanced Protocol: {'✅ PASS' if enhanced_success else '❌ FAIL'}")
    logger.info(f"  Fallback Controller: {'✅ PASS' if fallback_success else '❌ FAIL'}")
    
    if enhanced_success:
        logger.info("\n🎉 Enhanced protocol should work better now!")
        logger.info("💡 The timeout fixes should resolve the jog command issues")
        logger.info("📝 Try restarting your web interface")
    elif fallback_success:
        logger.info("\n🔄 Enhanced protocol still has issues, but fallback works")
        logger.info("💡 You can switch to the fallback controller temporarily")
        logger.info("📝 Update scan_orchestrator.py to use FallbackFluidNCController")
    else:
        logger.info("\n❌ Both controllers have issues")
        logger.info("🔍 This suggests a hardware or connection problem")
        logger.info("📝 Check FluidNC is connected and responding")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())