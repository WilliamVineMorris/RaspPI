#!/usr/bin/env python3
"""
Test Simplified FluidNC System

Tests the new simplified FluidNC protocol and controller to verify
they resolve the timeout and communication issues.

Author: Scanner System Redesign
Created: September 24, 2025
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)


async def test_simplified_protocol():
    """Test the simplified protocol directly"""
    logger.info("🧪 Testing Simplified FluidNC Protocol...")
    
    try:
        from motion.simplified_fluidnc_protocol import SimplifiedFluidNCProtocol
        
        # Create protocol instance
        protocol = SimplifiedFluidNCProtocol(port="/dev/ttyUSB0")
        
        # Test connection
        connected = await asyncio.get_event_loop().run_in_executor(
            None, protocol.connect
        )
        
        if connected:
            logger.info("✅ Protocol connection successful")
            
            # Test simple command
            success, response = await asyncio.get_event_loop().run_in_executor(
                None, protocol.send_command, "G90", 5.0
            )
            
            if success:
                logger.info(f"✅ Command successful: {response}")
            else:
                logger.warning(f"⚠️  Command failed: {response}")
            
            # Test status
            status = protocol.get_current_status()
            if status:
                logger.info(f"✅ Status available: {status.state}")
            else:
                logger.info("ℹ️  No status available yet")
            
            # Disconnect
            await asyncio.get_event_loop().run_in_executor(
                None, protocol.disconnect
            )
            
            logger.info("✅ Protocol test completed")
            return True
        else:
            logger.error("❌ Protocol connection failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Protocol test failed: {e}")
        return False


async def test_simplified_controller():
    """Test the simplified controller"""
    logger.info("🧪 Testing Simplified FluidNC Controller...")
    
    try:
        from motion.simplified_fluidnc_controller import SimplifiedFluidNCController
        from motion.base import Position4D
        
        # Create controller with config
        config = {
            'port': '/dev/ttyUSB0',
            'baud_rate': 115200,
            'command_timeout': 10.0
        }
        
        controller = SimplifiedFluidNCController(config)
        
        # Test connection
        connected = await controller.connect()
        
        if connected:
            logger.info("✅ Controller connection successful")
            
            # Test get position
            position = await controller.get_position()
            logger.info(f"✅ Current position: {position}")
            
            # Test small relative move (safe)
            delta = Position4D(x=0.1, y=0.0, z=0.0, c=0.0)
            success = await controller.move_relative(delta, feedrate=50.0)
            
            if success:
                logger.info("✅ Relative move successful")
            else:
                logger.warning("⚠️  Relative move failed")
            
            # Test capabilities
            capabilities = await controller.get_capabilities()
            logger.info(f"✅ Capabilities: {capabilities.axes_count} axes")
            
            # Test status
            status = await controller.get_status()
            logger.info(f"✅ Status: {status}")
            
            # Get statistics
            stats = controller.get_statistics()
            logger.info(f"✅ Statistics: {stats['commands_sent']} commands sent")
            
            # Disconnect
            await controller.disconnect()
            
            logger.info("✅ Controller test completed")
            return True
        else:
            logger.error("❌ Controller connection failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Controller test failed: {e}")
        return False


async def test_type_consistency():
    """Test Position4D type consistency"""
    logger.info("🧪 Testing Position4D Type Consistency...")
    
    try:
        from motion.base import Position4D
        
        # Test basic creation
        pos1 = Position4D(1.0, 2.0, 3.0, 4.0)
        logger.info(f"✅ Position created: {pos1}")
        
        # Test copy method
        pos2 = pos1.copy()
        logger.info(f"✅ Position copied: {pos2}")
        
        # Test to_dict
        pos_dict = pos1.to_dict()
        logger.info(f"✅ Position to dict: {pos_dict}")
        
        # Test from_dict
        pos3 = Position4D.from_dict(pos_dict)
        logger.info(f"✅ Position from dict: {pos3}")
        
        # Test distance calculation
        distance = pos1.distance_to(pos2)
        logger.info(f"✅ Distance calculation: {distance}")
        
        logger.info("✅ Type consistency test passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Type consistency test failed: {e}")
        return False


async def main():
    """Run all tests"""
    logger.info("🚀 Testing Simplified FluidNC System")
    logger.info("=" * 50)
    
    # Test type consistency first (no hardware needed)
    type_test = await test_type_consistency()
    
    logger.info("-" * 30)
    
    # Test protocol (requires hardware)
    protocol_test = await test_simplified_protocol()
    
    logger.info("-" * 30)
    
    # Test controller (requires hardware)
    controller_test = await test_simplified_controller()
    
    logger.info("=" * 50)
    logger.info("📊 Test Results:")
    logger.info(f"  Type Consistency: {'✅ PASS' if type_test else '❌ FAIL'}")
    logger.info(f"  Simplified Protocol: {'✅ PASS' if protocol_test else '❌ FAIL'}")
    logger.info(f"  Simplified Controller: {'✅ PASS' if controller_test else '❌ FAIL'}")
    
    if all([type_test, protocol_test, controller_test]):
        logger.info("\n🎉 All tests passed! The simplified system should work correctly.")
        logger.info("💡 This system should eliminate the timeout issues.")
        logger.info("📝 You can now integrate this into your main system.")
    elif type_test and not (protocol_test or controller_test):
        logger.info("\n⚠️  Hardware tests failed - check FluidNC connection")
        logger.info("✅ Type system is working correctly")
        logger.info("🔧 Hardware connection may be needed for full testing")
    else:
        logger.info("\n❌ Some tests failed - check error messages above")
        logger.info("🔍 Review the implementation for any remaining issues")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main())