#!/usr/bin/env python3
"""
Test Enhanced Homing Detection
Tests the new debug-message-based homing detection
"""

import asyncio
import logging
import sys
import os

# Add the V2.0 directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_enhanced_homing():
    """Test the enhanced homing detection"""
    try:
        logger.info("🧪 Testing Enhanced Homing Detection")
        logger.info("=" * 60)
        
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # Create controller
        controller = SimplifiedFluidNCControllerFixed(config)
        
        logger.info("🔌 Connecting to FluidNC...")
        connected = await controller.connect()
        
        if not connected:
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected successfully")
        
        # Check if protocol has message capture capability
        if hasattr(controller.protocol, 'get_recent_raw_messages'):
            logger.info("✅ Protocol has message capture capability")
            
            # Show recent messages
            recent = controller.protocol.get_recent_raw_messages(5)
            logger.info(f"📝 Recent messages: {len(recent)}")
            for msg in recent:
                logger.info(f"   {msg}")
        else:
            logger.warning("⚠️ Protocol missing message capture - adding it...")
            
        # Show current status
        status = await controller.get_status()
        logger.info(f"📊 Current status: {status}")
        
        position = await controller.get_position()
        logger.info(f"📍 Current position: {position}")
        
        # Ask user to proceed with actual homing
        print("\n" + "="*60)
        print("🏠 ENHANCED HOMING TEST")
        print("="*60)
        print("This will test the new homing detection that looks for:")
        print("   [MSG:DBG: Homing done]")
        print("   [MSG:Homed:X/Y]")
        print("\nMake sure your machine is ready for homing!")
        print("⚠️  Ensure axes can move to home positions safely")
        
        response = input("\n🔶 Proceed with homing test? (y/N): ").strip().lower()
        
        if response != 'y':
            logger.info("Test cancelled by user")
            await controller.disconnect()
            return True
        
        logger.info("🏠 Starting enhanced homing test...")
        
        # Perform enhanced homing
        homing_success = await controller.home_axes()
        
        if homing_success:
            logger.info("✅ Enhanced homing completed successfully!")
            
            # Show final position
            final_position = await controller.get_position()
            logger.info(f"📍 Final position: {final_position}")
            
            # Show protocol statistics
            if hasattr(controller.protocol, 'stats'):
                stats = controller.protocol.stats
                logger.info(f"📊 Debug messages captured: {stats.get('debug_messages_captured', 0)}")
            
        else:
            logger.error("❌ Enhanced homing failed")
        
        # Disconnect
        await controller.disconnect()
        logger.info("🔌 Disconnected")
        
        return homing_success
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

async def test_message_capture():
    """Test just the message capture functionality"""
    try:
        logger.info("🧪 Testing Message Capture Only")
        
        config_manager = ConfigManager()
        config = config_manager.get_config()
        controller = SimplifiedFluidNCControllerFixed(config)
        
        connected = await controller.connect()
        if not connected:
            logger.error("❌ Connection failed")
            return False
        
        logger.info("✅ Connected - testing message capture...")
        
        # Send a simple command and check message capture
        await controller._send_command("?")
        await asyncio.sleep(1.0)
        
        if hasattr(controller.protocol, 'get_recent_raw_messages'):
            messages = controller.protocol.get_recent_raw_messages(10)
            logger.info(f"📝 Captured {len(messages)} messages:")
            for msg in messages:
                logger.info(f"   {msg}")
        else:
            logger.error("❌ Message capture not available")
        
        await controller.disconnect()
        return True
        
    except Exception as e:
        logger.error(f"❌ Message capture test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Enhanced Homing Detection Test Suite")
    print("="*50)
    print("1. Test message capture only")
    print("2. Test full enhanced homing")
    
    choice = input("\nSelect test (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(test_message_capture())
    elif choice == "2":
        asyncio.run(test_enhanced_homing())
    else:
        print("Invalid choice")
        sys.exit(1)