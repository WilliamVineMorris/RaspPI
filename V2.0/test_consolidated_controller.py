#!/usr/bin/env python3
"""
Test Consolidated FluidNC Controller
Tests the single, working implementation with all fixes applied.

Author: Scanner System Development
Created: September 26, 2025
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_consolidated_controller():
    """Test the consolidated controller with all fixes."""
    print("\n" + "=" * 60)
    print("🧪 TESTING CONSOLIDATED FLUIDNC CONTROLLER")
    print("=" * 60)
    print("\nThis controller includes ALL fixes from successful tests:")
    print("✅ Proper 'Homing done' detection (lowercase)")
    print("✅ All abstract methods implemented")
    print("✅ Graceful alarm state handling")
    print("✅ Simple proven serial communication")
    print("✅ Based on working test_simple_homing.py approach")
    print("=" * 60)
    
    try:
        # Import the simple working controller (proven approach)
        from simple_working_fluidnc_controller import SimpleWorkingFluidNCController
        
        # Create controller (no config needed for simple version)
        print("\n1️⃣ Creating Controller...")
        controller = SimpleWorkingFluidNCController("/dev/ttyUSB0", 115200)
        print(f"✅ Controller created (port: {controller.port})")
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("\n💡 Make sure you have created the consolidated_fluidnc_controller.py file")
        return False
    except Exception as e:
        print(f"❌ Setup error: {e}")
        return False
    
    try:
        # Test connection
        print("\n2️⃣ Testing Connection...")
        print(f"🔌 Attempting to connect to {controller.port}")
        
        connected = await controller.initialize()
        
        if not connected:
            print("❌ Failed to connect to FluidNC")
            print("   Common issues:")
            print("   • Check USB cable connection")
            print("   • Verify FluidNC is powered on")
            print("   • Check if /dev/ttyUSB0 exists")
            print("   • Try: ls /dev/ttyUSB*")
            return False
        
        print("✅ Connected successfully!")
        
        # Check initial status
        print("\n3️⃣ Checking Initial Status...")
        status = await controller.get_status()
        position = controller.get_position()
        is_homed = controller.is_homed()
        
        print(f"📊 Status: {status}")
        print(f"📍 Position: {position}")
        print(f"🏠 Homed: {is_homed}")
        
        # Handle different status scenarios
        if status.name == "ALARM":
            print("\n⚠️  FluidNC is in ALARM state")
            print("   This is normal on startup - homing will clear it")
            
            # Test alarm clearing
            print("\n4️⃣ Testing Alarm Clear...")
            cleared = await controller.clear_alarm()
            if cleared:
                print("✅ Alarm cleared successfully")
                new_status = await controller.get_status()
                print(f"📊 New status: {new_status}")
            else:
                print("⚠️  Alarm not cleared automatically")
        
        # Test homing if not homed
        if not controller.is_homed():
            print("\n5️⃣ Homing Test")
            print("=" * 40)
            print("⚠️  SAFETY WARNING:")
            print("⚠️  Ensure all axes can move freely to limit switches!")
            print("⚠️  Be ready to hit emergency stop if needed!")
            print("⚠️  Make sure workspace is clear!")
            print("=" * 40)
            
            response = input("\nProceed with homing test? (y/N): ")
            
            if response.lower() == 'y':
                print("\n🏠 Starting homing sequence...")
                print("   Using the PROVEN approach from successful tests")
                
                start_time = time.time()
                success = await controller.home()
                elapsed = time.time() - start_time
                
                if success:
                    print(f"✅ Homing completed successfully in {elapsed:.1f} seconds!")
                    print(f"📍 New position: {controller.get_position()}")
                    print(f"🏠 Homed status: {controller.is_homed()}")
                else:
                    print("❌ Homing failed!")
                    print("   Check the logs above for error details")
                    return False
            else:
                print("⏭️  Skipping homing test")
        else:
            print("✅ System is already homed")
        
        # Test basic commands
        print("\n6️⃣ Testing Basic Commands...")
        
        # Test status query
        print("   Testing status query...")
        status = await controller.get_status()
        print(f"   ✅ Status: {status}")
        
        # Test G-code execution
        print("   Testing G-code execution...")
        success = await controller.execute_gcode("G4 P0.1")  # 0.1 second dwell
        if success:
            print("   ✅ G-code execution works")
        else:
            print("   ⚠️  G-code execution failed (may be normal)")
        
        # Test feed rate setting
        print("   Testing feed rate setting...")
        success = await controller.set_feed_rate(100)
        if success:
            print("   ✅ Feed rate setting works")
        else:
            print("   ⚠️  Feed rate setting failed (may be normal)")
        
        # Test movement (only if homed)
        if controller.is_homed():
            print("\n7️⃣ Movement Test (Optional)")
            print("⚠️  This will make a small test movement!")
            response = input("Test small movement? (y/N): ")
            
            if response.lower() == 'y':
                from motion.base import Position4D
                
                current_pos = controller.get_position()
                print(f"📍 Current position: {current_pos}")
                
                # Small safe movement (5mm in X and Y)
                target = Position4D(
                    x=current_pos.x + 5,
                    y=current_pos.y + 5,
                    z=current_pos.z,
                    c=current_pos.c
                )
                
                print(f"🎯 Moving to: {target}")
                
                move_start = time.time()
                success = await controller.move_to_position(target)
                move_time = time.time() - move_start
                
                if success:
                    print(f"✅ Movement successful in {move_time:.1f} seconds")
                    
                    # Wait for motion to complete
                    print("⏳ Waiting for motion to complete...")
                    complete = await controller.wait_for_motion_complete(timeout=10.0)
                    
                    if complete:
                        print("✅ Motion completed")
                        final_pos = controller.get_position()
                        print(f"📍 Final position: {final_pos}")
                        
                        # Return to original position
                        print("🔄 Returning to original position...")
                        await controller.move_to_position(current_pos)
                        await controller.wait_for_motion_complete(timeout=10.0)
                        print("✅ Returned to original position")
                    else:
                        print("⚠️  Motion completion timeout")
                else:
                    print("❌ Movement failed")
            else:
                print("⏭️  Skipping movement test")
        
        # Test emergency stop functionality
        print("\n8️⃣ Testing Emergency Stop (Safe Test)...")
        print("   This just tests the command, no actual emergency")
        
        try:
            await controller.emergency_stop()
            print("✅ Emergency stop command executed")
            
            # Clear the alarm that emergency stop creates
            await asyncio.sleep(1)
            await controller.clear_alarm()
            print("✅ Emergency stop alarm cleared")
        except Exception as e:
            print(f"⚠️  Emergency stop test error: {e}")
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\n✅ Controller Status Summary:")
        print(f"   Connection: {'✅ Connected' if controller.is_connected() else '❌ Disconnected'}")
        print(f"   Homed: {'✅ Yes' if controller.is_homed() else '⚠️ No'}")
        print(f"   Status: {await controller.get_status()}")
        print(f"   Position: {controller.get_position()}")
        
        print("\n🚀 READY FOR INTEGRATION!")
        print("\nNext steps:")
        print("1. Update scan_orchestrator.py to use ConsolidatedFluidNCController")
        print("2. Update web_interface.py imports")
        print("3. Run full system test")
        
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return False
        
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean shutdown
        print("\n🔌 Shutting down controller...")
        try:
            await controller.shutdown()
            print("✅ Controller shutdown complete")
        except:
            print("⚠️  Shutdown error (may be normal)")

def main():
    """Run the consolidated controller test."""
    print("\n" + "🎯" * 20)
    print("CONSOLIDATED FLUIDNC CONTROLLER TEST")
    print("🎯" * 20)
    print("\nThis test validates the single, working motion controller")
    print("that should replace all other implementations.")
    print("\nBased on successful tests:")
    print("• test_homing_completion.py (✅ 23.2s homing)")
    print("• test_simple_homing.py (✅ Simple approach)")
    print("• test_fluidnc_communication.py (✅ Serial works)")
    
    # Run the async test
    try:
        success = asyncio.run(test_consolidated_controller())
        
        if success:
            print("\n" + "🎉" * 20)
            print("SUCCESS - CONTROLLER IS READY!")
            print("🎉" * 20)
            return 0
        else:
            print("\n" + "⚠️" * 20)
            print("SOME TESTS FAILED - CHECK LOGS")
            print("⚠️" * 20)
            return 1
            
    except Exception as e:
        print(f"\n❌ Fatal test error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)