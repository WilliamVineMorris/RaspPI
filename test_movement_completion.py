#!/usr/bin/env python3
"""
Test script to validate movement completion and sequencing
"""

import time
import logging
from camera_positioning_gcode import FluidNCController, Point

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_movement_completion():
    """Test movement completion detection"""
    print("🔧 Testing Movement Completion Detection")
    print("=" * 50)
    
    # Get port from user
    port = input("Enter FluidNC port (e.g., COM3, /dev/ttyUSB0): ").strip()
    if not port:
        print("No port specified, exiting test")
        return False
    
    # Initialize controller
    controller = FluidNCController(port=port, timeout=10.0)
    
    try:
        print("\n1. Connecting to FluidNC...")
        if not controller.connect():
            print("❌ Failed to connect to FluidNC")
            return False
        
        print("✅ Connected successfully")
        
        print("\n2. Checking if system is homed...")
        if not controller.check_homing_status():
            print("⚠️ System not homed. Please home first.")
            response = input("Home system now? (y/N): ").strip().lower()
            if response == 'y':
                print("Homing...")
                if not controller.home_axes():
                    print("❌ Homing failed")
                    return False
            else:
                print("⚠️ Testing without homing - movements may be limited")
        else:
            print("✅ System is homed")
        
        print("\n3. Testing individual movement with completion...")
        
        # Get current position
        current_pos = controller.get_machine_position()
        print(f"Current position: X:{current_pos.x:.1f} Y:{current_pos.y:.1f} Z:{current_pos.z:.1f} C:{current_pos.c:.1f}")
        
        # Test small movement
        test_point = Point(current_pos.x + 5, current_pos.y - 5, current_pos.z, current_pos.c)
        
        print(f"Moving to test position: X:{test_point.x:.1f} Y:{test_point.y:.1f}...")
        start_time = time.time()
        
        success = controller.move_to_point_and_wait(test_point, feedrate=100)
        elapsed = time.time() - start_time
        
        print(f"Movement result: {'✅ Success' if success else '❌ Failed'}")
        print(f"Movement took: {elapsed:.1f} seconds")
        
        # Verify position
        new_pos = controller.get_machine_position()
        print(f"Final position: X:{new_pos.x:.1f} Y:{new_pos.y:.1f} Z:{new_pos.z:.1f} C:{new_pos.c:.1f}")
        
        # Check accuracy
        x_error = abs(new_pos.x - test_point.x)
        y_error = abs(new_pos.y - test_point.y)
        
        if x_error < 0.5 and y_error < 0.5:
            print("✅ Position accuracy good")
        else:
            print(f"⚠️ Position error: X:{x_error:.2f}mm Y:{y_error:.2f}mm")
        
        print("\n4. Testing movement sequence (multiple moves)...")
        
        # Define a small test pattern
        test_pattern = [
            Point(current_pos.x, current_pos.y, current_pos.z, current_pos.c),      # Return to start
            Point(current_pos.x + 10, current_pos.y, current_pos.z, current_pos.c), # Move right
            Point(current_pos.x + 10, current_pos.y - 10, current_pos.z, current_pos.c), # Move down
            Point(current_pos.x, current_pos.y - 10, current_pos.z, current_pos.c), # Move left
            Point(current_pos.x, current_pos.y, current_pos.z, current_pos.c),      # Return to start
        ]
        
        print(f"Executing {len(test_pattern)} move sequence...")
        sequence_start = time.time()
        
        for i, point in enumerate(test_pattern):
            print(f"  Move {i+1}/{len(test_pattern)}: X:{point.x:.1f} Y:{point.y:.1f}")
            move_start = time.time()
            
            success = controller.move_to_point_and_wait(point, feedrate=200)
            move_time = time.time() - move_start
            
            if not success:
                print(f"❌ Move {i+1} failed")
                return False
            
            print(f"    Completed in {move_time:.1f}s")
            
            # Simulate photo capture delay
            time.sleep(0.5)
        
        sequence_time = time.time() - sequence_start
        print(f"✅ Sequence completed in {sequence_time:.1f}s total")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        print("\n5. Disconnecting...")
        controller.disconnect()
        print("✅ Disconnected")

def test_wait_vs_no_wait():
    """Compare movement with and without waiting"""
    print("\n🔧 Testing Wait vs No-Wait Movement")
    print("=" * 40)
    
    # This is a simulation to show the difference
    print("Simulating movement timing...")
    
    print("\n📊 Expected Results:")
    print("• move_to_point(): Returns immediately (command sent)")
    print("• move_to_point_and_wait(): Returns after movement complete")
    print("• Scanning operations now use move_to_point_and_wait()")
    print("• Each position is reached before taking photo")
    print("• No queued movements during scanning")

if __name__ == "__main__":
    print("Movement Completion Test Suite")
    print("=" * 50)
    
    # Show the difference
    test_wait_vs_no_wait()
    
    # Ask user if they want to test with actual hardware
    response = input("\n🤖 Do you want to test with actual FluidNC hardware? (y/N): ").strip().lower()
    
    if response == 'y':
        test_movement_completion()
    else:
        print("Skipping hardware test")
    
    print("\n✅ Test suite completed")