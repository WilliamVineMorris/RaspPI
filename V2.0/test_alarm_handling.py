#!/usr/bin/env python3
"""
Test FluidNC Alarm State Handling
Demonstrates graceful handling of alarm states and guided homing
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
from homing_status_manager import HomingStatusManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_alarm_state_handling():
    """Test alarm state detection and handling"""
    
    print("🚨 FluidNC Alarm State Handling Test")
    print("=" * 50)
    
    try:
        # Initialize configuration
        print("📋 Loading configuration...")
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        # Create motion controller with enhanced alarm handling
        motion_config = config_manager.get('motion', {})
        controller_config = {
            'port': motion_config.get('controller', {}).get('port', '/dev/ttyUSB0'),
            'baud_rate': motion_config.get('controller', {}).get('baudrate', 115200),
            'command_timeout': motion_config.get('controller', {}).get('timeout', 30.0),
            'motion_limits': {
                'x': {
                    'min': motion_config.get('axes', {}).get('x_axis', {}).get('min_limit', 0.0),
                    'max': motion_config.get('axes', {}).get('x_axis', {}).get('max_limit', 200.0),
                    'max_feedrate': motion_config.get('axes', {}).get('x_axis', {}).get('max_feedrate', 1000.0)
                },
                'y': {
                    'min': motion_config.get('axes', {}).get('y_axis', {}).get('min_limit', 0.0),
                    'max': motion_config.get('axes', {}).get('y_axis', {}).get('max_limit', 200.0),
                    'max_feedrate': motion_config.get('axes', {}).get('y_axis', {}).get('max_feedrate', 1000.0)
                },
                'z': {
                    'min': motion_config.get('axes', {}).get('z_axis', {}).get('min_limit', -180.0),
                    'max': motion_config.get('axes', {}).get('z_axis', {}).get('max_limit', 180.0),
                    'max_feedrate': motion_config.get('axes', {}).get('z_axis', {}).get('max_feedrate', 800.0)
                },
                'c': {
                    'min': motion_config.get('axes', {}).get('c_axis', {}).get('min_limit', -90.0),
                    'max': motion_config.get('axes', {}).get('c_axis', {}).get('max_limit', 90.0),
                    'max_feedrate': motion_config.get('axes', {}).get('c_axis', {}).get('max_feedrate', 5000.0)
                }
            },
            'feedrates': motion_config.get('feedrates', {})
        }
        
        print("🔧 Creating motion controller...")
        motion_controller = SimplifiedFluidNCControllerFixed(controller_config)
        
        # Create homing status manager
        print("🏠 Creating homing status manager...")
        homing_manager = HomingStatusManager(motion_controller)
        
        # Test 1: Connection with alarm state handling
        print("\n🔌 Test 1: Connection with Alarm State Handling")
        print("-" * 45)
        
        print("   • Attempting to connect to FluidNC...")
        connected = await motion_controller.initialize()
        
        if connected:
            print("   ✅ Motion controller connected!")
            
            # Check initial status
            status = await motion_controller.get_status()
            print(f"   📊 Initial status: {status}")
            
            if status.name == "ALARM":
                print("   ⚠️  Controller in ALARM state (expected after boot)")
                print("   💡 This is normal - FluidNC requires homing after power-on")
            else:
                print(f"   📊 Controller in {status.name} state")
        else:
            print("   ❌ Motion controller failed to connect")
            print("   💡 Check:")
            print("      - FluidNC USB connection")
            print("      - Port availability (/dev/ttyUSB0)")
            print("      - Device permissions")
            return False
        
        # Test 2: Homing status check
        print("\n🔍 Test 2: Homing Status Check")
        print("-" * 35)
        
        homing_state = await homing_manager.check_homing_status()
        print(f"   📊 Homing Status: {homing_state.status.value}")
        print(f"   💬 Message: {homing_state.message}")
        print(f"   🏠 Can Home: {homing_state.can_home}")
        print(f"   👤 Requires User Action: {homing_state.requires_user_action}")
        
        if homing_state.recommendations:
            print("   💡 Recommendations:")
            for rec in homing_state.recommendations:
                print(f"      • {rec}")
        
        # Test 3: Offer to perform homing or manual unlock
        if homing_state.can_home and homing_state.requires_user_action:
            print("\n🏠 Test 3: Homing & Manual Unlock Options")
            print("-" * 45)
            
            if homing_state.status.value == "required":
                print("   ⚠️  FluidNC is in ALARM state - two options available:")
                print("   1. 🏠 Full Homing (recommended) - moves to home position")
                print("   2. 🔓 Manual Unlock - clears alarm without moving")
                print()
                print("   ⚠️  SAFETY WARNING for Homing:")
                print("      • Ensure all axes can move freely")
                print("      • Check that limit switches are connected")
                print("      • Be ready to power off if something goes wrong")
                print()
                print("   ⚠️  WARNING for Manual Unlock:")
                print("      • Position will be unknown after unlock")
                print("      • Only use if homing is impossible")
                print("      • Manual positioning will be required")
                
                print("\n   Options:")
                print("   h) Full homing sequence (recommended)")
                print("   u) Manual unlock only (position unknown)")
                print("   s) Skip testing")
                
                response = input("\n   🤔 Choose option (h/u/s): ").strip().lower()
                
                # Track progress
                def status_callback(state):
                    print(f"   📊 {state.message}")
                
                homing_manager.add_status_callback(status_callback)
                
                if response == 'h':
                    print("\n   🏠 Starting full homing sequence...")
                    success = await homing_manager.start_homing()
                    
                    if success:
                        print("   ✅ Homing completed successfully!")
                        
                        # Verify final status
                        final_status = await motion_controller.get_status()
                        print(f"   📊 Final status: {final_status}")
                        
                        if final_status.name == "IDLE":
                            print("   🎯 System ready for operation!")
                            print("   💡 Position is now accurately known")
                        
                    else:
                        print("   ❌ Homing failed!")
                        
                        # Get failure details
                        final_state = await homing_manager.check_homing_status()
                        print(f"   � Error details: {final_state.message}")
                        
                        # Offer manual unlock as fallback
                        print("\n   🔓 Would you like to try manual unlock instead?")
                        unlock_response = input("   🤔 Try manual unlock? (y/N): ").strip().lower()
                        
                        if unlock_response == 'y':
                            print("   🔓 Attempting manual unlock...")
                            unlock_success = await homing_manager.manual_unlock()
                            
                            if unlock_success:
                                print("   ✅ Manual unlock successful!")
                                print("   ⚠️  Position is unknown - be careful with movements")
                            else:
                                print("   ❌ Manual unlock also failed")
                                
                elif response == 'u':
                    print("\n   🔓 Starting manual unlock...")
                    success = await homing_manager.manual_unlock()
                    
                    if success:
                        print("   ✅ Manual unlock successful!")
                        print("   ⚠️  Position is unknown - home when safe")
                        
                        # Verify final status
                        final_status = await motion_controller.get_status()
                        print(f"   📊 Final status: {final_status}")
                        
                    else:
                        print("   ❌ Manual unlock failed!")
                        
                        # Get failure details
                        final_state = await homing_manager.check_homing_status()
                        print(f"   💬 Error details: {final_state.message}")
                        
                        if final_state.recommendations:
                            print("   💡 Try these solutions:")
                            for rec in final_state.recommendations:
                                print(f"      • {rec}")
                                
                else:
                    print("   ⏭️  Skipping homing/unlock testing")
                    print("   💡 You can test manually using:")
                    print("      • Web interface 'Home' or 'Unlock' buttons")
                    print("      • Manual FluidNC commands ($X then $H)")
            else:
                print("   📊 System not in alarm state - homing not required")
                print("   💡 But homing can still be performed for testing")
        
        # Test 4: Web interface integration readiness
        print("\n🌐 Test 4: Web Interface Integration")
        print("-" * 40)
        
        web_status = homing_manager.get_status_for_web()
        print("   📊 Web status data:")
        for key, value in web_status.items():
            print(f"      {key}: {value}")
        
        print("\n   💡 Web interface will show:")
        if web_status['homing_required']:
            print("      🔴 'Homing Required' warning")
            print("      🏠 'Home All Axes' button enabled")
        elif web_status['homing_in_progress']:
            print("      🟡 'Homing in Progress' status")
            print("      ⏳ Progress indicator")
        else:
            print("      🟢 'System Ready' status")
            print("      🎯 Manual controls enabled")
        
        print("\n✅ Test completed successfully!")
        print("🎯 Next step: Run 'python run_web_interface.py' to test web interface")
        
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
    """Main test function"""
    print("🚨 FluidNC Alarm State Handling & Guided Homing Test")
    print("=" * 60)
    print()
    print("This test will:")
    print("1. Connect to FluidNC (handling alarm states gracefully)")
    print("2. Check homing requirements and provide guidance")
    print("3. Offer guided homing with safety checks")
    print("4. Verify web interface integration readiness")
    print()
    
    try:
        # Run the async test
        success = asyncio.run(test_alarm_state_handling())
        
        if success:
            print("\n🎉 All tests passed!")
            print("💡 The system now handles FluidNC alarm states gracefully")
        else:
            print("\n❌ Some tests failed")
            print("💡 Check connections and try again")
            
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")

if __name__ == "__main__":
    main()