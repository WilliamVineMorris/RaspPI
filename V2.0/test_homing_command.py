#!/usr/bin/env python3
"""
Quick Test: Verify $H Command is Sent
Tests that homing actually sends the $H command to FluidNC
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed

# Setup detailed logging to see commands
logging.basicConfig(
    level=logging.DEBUG,  # DEBUG level to see all commands
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_homing_command():
    """Test that $H command is actually sent"""
    
    print("🧪 Testing $H Command Transmission")
    print("=" * 40)
    
    try:
        # Load configuration
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Create motion controller
        motion_config = config_manager.get('motion', {})
        controller_config = {
            'port': motion_config.get('controller', {}).get('port', '/dev/ttyUSB0'),
            'baud_rate': motion_config.get('controller', {}).get('baudrate', 115200),
            'command_timeout': motion_config.get('controller', {}).get('timeout', 30.0),
        }
        
        print(f"🔌 Connecting to FluidNC at {controller_config['port']}...")
        motion_controller = SimplifiedFluidNCControllerFixed(controller_config)
        
        # Connect
        if not await motion_controller.initialize():
            print("❌ Could not connect to FluidNC")
            return False
        
        print("✅ Connected to FluidNC")
        
        # Check initial status
        status = await motion_controller.get_status()
        print(f"📊 Initial status: {status}")
        
        # Show what we're about to do
        print("\n🎯 About to send homing command...")
        print("📺 Watch the logs below for the actual $H command being sent:")
        print("-" * 50)
        
        # Test homing with detailed callback
        def detailed_callback(phase, message):
            print(f"🔄 HOMING: {phase} - {message}")
        
        # Attempt homing
        success = await motion_controller.home_with_status_callback(detailed_callback)
        
        print("-" * 50)
        if success:
            print("✅ Homing command sequence completed successfully")
        else:
            print("❌ Homing command sequence failed")
        
        # Check final status
        final_status = await motion_controller.get_status()
        print(f"📊 Final status: {final_status}")
        
        return success
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup
        try:
            if 'motion_controller' in locals():
                await motion_controller.disconnect()
        except:
            pass

def main():
    """Main test"""
    print("🧪 $H Command Verification Test")
    print("=" * 50)
    print()
    print("This test will:")
    print("1. Connect to FluidNC")
    print("2. Show initial status (likely ALARM)")
    print("3. Attempt homing with detailed logging")
    print("4. Verify $H command is sent (look for it in logs)")
    print("5. Monitor homing progress")
    print()
    print("🔍 Look for these log messages:")
    print("   • 'Sending homing command ($H)'")
    print("   • '$H' in the protocol send logs")
    print("   • Status changes during homing")
    print()
    
    try:
        success = asyncio.run(test_homing_command())
        
        if success:
            print("\n🎉 Test completed - check logs above for $H command")
        else:
            print("\n⚠️ Test had issues - but check if $H was sent")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test error: {e}")

if __name__ == "__main__":
    main()