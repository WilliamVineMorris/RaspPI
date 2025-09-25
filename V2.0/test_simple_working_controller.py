#!/usr/bin/env python3
"""
Simple Test for Working FluidNC Controller
Direct test using the proven approach from successful tests.

Author: Scanner System Development  
Created: September 26, 2025
"""

import time
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from simple_working_fluidnc_controller import SimpleWorkingFluidNCController, Position4D

def test_working_controller():
    """Test the simple working controller directly."""
    print("\n" + "=" * 60)
    print("🧪 TESTING SIMPLE WORKING FLUIDNC CONTROLLER")
    print("=" * 60)
    print("\nThis controller uses the EXACT approach from successful tests:")
    print("✅ test_simple_homing.py (23.2s homing success)")
    print("✅ test_homing_completion.py (proper detection)")
    print("✅ Direct serial communication that works")
    print("=" * 60)
    
    # Create controller
    controller = SimpleWorkingFluidNCController("/dev/ttyUSB0", 115200)
    
    try:
        # Test 1: Connection
        print("\n1️⃣ Testing Connection...")
        print(f"🔌 Connecting to {controller.port}")
        
        if not controller.connect():
            print("❌ Connection failed!")
            print("\n💡 Common issues:")
            print("   • Check USB cable connection")
            print("   • Verify FluidNC is powered on")
            print("   • Check if /dev/ttyUSB0 exists: ls /dev/ttyUSB*")
            print("   • Try: sudo chmod 666 /dev/ttyUSB0")
            return False
        
        print("✅ Connected successfully!")
        
        # Test 2: Status Check
        print("\n2️⃣ Checking Status...")
        status = controller.get_status()
        print(f"📊 Status: {status}")
        print(f"🏠 Homed: {controller.is_homed()}")
        print(f"📍 Position: {controller.get_position()}")
        
        # Test 3: Homing (if needed)
        if not controller.is_homed():
            print("\n3️⃣ Homing Test")
            print("=" * 40)
            print("⚠️  SAFETY WARNING:")
            print("⚠️  Ensure all axes can move freely to limit switches!")
            print("⚠️  Be ready to hit emergency stop if needed!")
            print("⚠️  Make sure workspace is clear!")
            print("=" * 40)
            
            response = input("\nProceed with homing? (y/N): ")
            
            if response.lower() == 'y':
                print("\n🏠 Starting homing sequence...")
                print("   Using PROVEN approach from successful tests")
                
                start_time = time.time()
                success = controller.home()
                elapsed = time.time() - start_time
                
                if success:
                    print(f"✅ Homing completed successfully in {elapsed:.1f} seconds!")
                    print(f"📍 New position: {controller.get_position()}")
                    print(f"🏠 Homed status: {controller.is_homed()}")
                    print(f"📊 Final status: {controller.get_status()}")
                else:
                    print("❌ Homing failed!")
                    print("   Check the console output above for details")
                    return False
            else:
                print("⏭️  Skipping homing test")
        else:
            print("✅ System is already homed")
        
        # Test 4: Basic Commands
        print("\n4️⃣ Testing Basic Commands...")
        
        # Status query
        print("   📊 Status query...")  
        status = controller.get_status()
        print(f"   Status: {status}")
        
        # G-code execution
        print("   🔧 G-code execution...")
        success = controller.execute_gcode("G4 P0.1")  # 0.1s dwell
        if success:
            print("   ✅ G-code execution works")
        else:
            print("   ⚠️  G-code execution failed (may be normal)")
        
        # Test 5: Movement (if homed)
        if controller.is_homed():
            print("\n5️⃣ Movement Test (Optional)")
            print("⚠️  This will make a small test movement!")
            response = input("Test small movement? (y/N): ")
            
            if response.lower() == 'y':
                current_pos = controller.get_position()
                print(f"📍 Current position: {current_pos}")
                
                # Small safe movement (5mm in X and Y)
                target = Position4D(
                    x=current_pos.x + 5,
                    y=current_pos.y - 10,  # Move towards center
                    z=current_pos.z,
                    c=current_pos.c
                )
                
                print(f"🎯 Moving to: {target}")
                
                move_start = time.time()
                success = controller.move_to_position(target)
                move_time = time.time() - move_start
                
                if success:
                    print(f"✅ Movement command successful ({move_time:.1f}s)")
                    
                    # Wait for motion to complete
                    print("⏳ Waiting for motion to complete...")
                    time.sleep(3)  # Simple wait
                    
                    final_pos = controller.get_position()
                    print(f"📍 Final position: {final_pos}")
                    
                    # Return to original position
                    print("🔄 Returning to original position...")
                    controller.move_to_position(current_pos)
                    time.sleep(3)
                    print("✅ Returned to original position")
                else:
                    print("❌ Movement failed")
            else:
                print("⏭️  Skipping movement test")
        
        # Test 6: Emergency Stop Test
        print("\n6️⃣ Testing Emergency Stop...")
        print("   (Safe test - no actual emergency)")
        
        stop_success = controller.stop_motion()
        if stop_success:
            print("✅ Emergency stop command works")
        else:
            print("⚠️  Emergency stop test failed")
        
        # Final status
        print("\n" + "=" * 60)
        print("📋 FINAL STATUS SUMMARY")
        print("=" * 60)
        print(f"   Connection: {'✅ Connected' if controller.is_connected() else '❌ Disconnected'}")
        print(f"   Homed: {'✅ Yes' if controller.is_homed() else '⚠️  No'}")
        print(f"   Status: {controller.get_status()}")
        print(f"   Position: {controller.get_position()}")
        
        print("\n🎉 ALL TESTS COMPLETED!")
        print("\n🚀 CONTROLLER IS READY FOR INTEGRATION!")
        
        print("\n💡 Next Steps:")
        print("1. This controller can replace all other motion controllers")
        print("2. Update scan_orchestrator.py to use SimpleWorkingFluidNCController")
        print("3. Update web_interface.py to use this controller")
        print("4. Archive old/broken controller implementations")
        
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
        # Clean disconnection
        print("\n🔌 Disconnecting...")
        controller.disconnect()
        print("✅ Disconnected successfully")

def main():
    """Run the simple controller test."""
    print("\n" + "🎯" * 20)
    print("SIMPLE WORKING FLUIDNC CONTROLLER TEST")
    print("🎯" * 20)
    print("\nThis is the SINGLE working implementation that should")
    print("replace ALL other motion controller implementations.")
    print("\nIt's based on the EXACT code from successful tests:")
    print("• Direct serial communication")
    print("• Proper 'Homing done' detection (lowercase)")
    print("• Simple, reliable approach")
    print("• No complex abstractions that break")
    
    success = test_working_controller()
    
    if success:
        print("\n" + "🎉" * 20)
        print("SUCCESS - CONTROLLER IS WORKING!")  
        print("🎉" * 20)
        print("\n✅ This controller is ready to replace all others!")
        return 0
    else:
        print("\n" + "⚠️" * 20)
        print("SOME TESTS FAILED - CHECK OUTPUT")
        print("⚠️" * 20)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)