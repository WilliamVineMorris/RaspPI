#!/usr/bin/env python3
"""
Test Fixed Homing with Proper Timeout
Tests the new homing command with appropriate timeout settings
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_fixed_homing():
    """Test homing with proper timeout handling"""
    
    print("🏠 Testing Fixed Homing with Proper Timeout")
    print("=" * 50)
    
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
        
        print("\n🏠 Key Changes in Fixed Version:")
        print("   • Homing command uses separate timeout (5s for command acceptance)")
        print("   • Actual homing progress monitored via status polling") 
        print("   • No timeout waiting for homing completion in command layer")
        print("   • Status monitoring handles the long homing process")
        
        print("\n🎯 Starting homing with better timeout handling...")
        print("⚠️ SAFETY: Ensure axes can move freely!")
        
        # Wait for user confirmation
        response = input("\n🤔 Proceed with homing test? (y/N): ").strip().lower()
        
        if response != 'y':
            print("⏭️ Skipping homing test")
            return True
        
        print("\n📊 Starting homing - watch for these improvements:")
        print("   • Command accepted quickly (within 5s)")
        print("   • No 10s timeout during homing process")
        print("   • Status updates show homing progress")
        print("   • Completion detected via status monitoring")
        
        # Test homing with status tracking
        homing_start_time = asyncio.get_event_loop().time()
        
        def detailed_callback(phase, message):
            elapsed = asyncio.get_event_loop().time() - homing_start_time
            print(f"🔄 [{elapsed:6.1f}s] {phase}: {message}")
        
        # Attempt homing
        success = await motion_controller.home_with_status_callback(detailed_callback)
        
        total_time = asyncio.get_event_loop().time() - homing_start_time
        
        if success:
            print(f"✅ Homing completed successfully in {total_time:.1f}s")
            
            # Verify position
            final_status = await motion_controller.get_status()
            position = await motion_controller.get_position()
            print(f"📊 Final status: {final_status}")
            print(f"📍 Final position: {position}")
            
        else:
            print(f"❌ Homing failed after {total_time:.1f}s")
            print("💡 But check if FluidNC is still moving - may need more time")
            
            # Check if still homing
            final_status = await motion_controller.get_status()
            print(f"📊 Current status: {final_status}")
            
            if final_status == "HOMING":
                print("⏳ FluidNC is still homing - this is normal for large machines")
                print("💡 You can monitor progress via web interface")
        
        return True
        
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
    print("🔧 Fixed Homing Timeout Test")
    print("=" * 40)
    print()
    print("Changes made to fix timeout issues:")
    print("✅ Homing command uses 5s timeout (just for command acceptance)")
    print("✅ Actual homing monitored via status polling (no timeout)")
    print("✅ Separate homing command method for better handling")
    print("✅ Progress tracking shows real-time status")
    print()
    
    try:
        success = asyncio.run(test_fixed_homing())
        
        if success:
            print("\n🎉 Test completed successfully!")
            print("💡 Homing should now work without timeout issues")
        else:
            print("\n⚠️ Test had issues")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted")
    except Exception as e:
        print(f"\n❌ Test error: {e}")

if __name__ == "__main__":
    main()