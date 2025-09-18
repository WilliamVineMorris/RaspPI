#!/usr/bin/env python3
"""
Test script to verify FluidNC timeout and communication fixes
"""

import time
import logging
from camera_positioning_gcode import FluidNCController, Point

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_fluidnc_communication():
    """Test FluidNC communication with improved timeout handling"""
    print("🔧 Testing FluidNC Communication Fixes")
    print("=" * 50)
    
    # Get port from user
    port = input("Enter FluidNC port (e.g., COM3, /dev/ttyUSB0): ").strip()
    if not port:
        print("No port specified, exiting test")
        return False
    
    # Initialize controller with longer timeout
    controller = FluidNCController(port=port, timeout=10.0)
    
    try:
        print("\n1. Testing connection...")
        if not controller.connect():
            print("❌ Failed to connect to FluidNC")
            return False
        
        print("✅ Connected successfully")
        
        print("\n2. Testing status query...")
        status = controller.get_status()
        print(f"Status: {status}")
        
        print("\n3. Testing homing status check before homing...")
        initial_homed = controller.check_homing_status()
        print(f"Initially homed: {'✅ Yes' if initial_homed else '❌ No'}")
        
        print("\n4. Testing unlock command...")
        unlock_success = controller.unlock_controller()
        print(f"Unlock result: {'✅ Success' if unlock_success else '❌ Failed'}")
        
        print("\n5. Testing homing with verification (this may take up to 60 seconds)...")
        print("⏳ Homing in progress - watch for progress updates...")
        start_time = time.time()
        
        home_success = controller.home_axes()
        elapsed = time.time() - start_time
        
        print(f"Homing result: {'✅ Success' if home_success else '❌ Failed'}")
        print(f"Homing took: {elapsed:.1f} seconds")
        
        print("\n6. Verifying homing status after completion...")
        final_homed = controller.check_homing_status()
        is_homed_check = controller.is_homed()
        print(f"Homing verification: {'✅ Verified' if final_homed else '❌ Not verified'}")
        print(f"Is homed (legacy): {'✅ Yes' if is_homed_check else '❌ No'}")
        
        print("\n7. Testing position reporting after homing...")
        machine_pos = controller.get_machine_position()
        work_pos = controller.get_work_position()
        
        print(f"Machine Position: X:{machine_pos.x:.1f} Y:{machine_pos.y:.1f} Z:{machine_pos.z:.1f} C:{machine_pos.c:.1f}")
        print(f"Work Position: X:{work_pos.x:.1f} Y:{work_pos.y:.1f} Z:{work_pos.z:.1f} C:{work_pos.c:.1f}")
        
        # Check if Y-axis is at expected home position (200mm for our config)
        if abs(machine_pos.y - 200.0) < 10.0:
            print("✅ Y-axis at expected home position (~200mm)")
        else:
            print(f"⚠️ Y-axis position unexpected: {machine_pos.y:.1f}mm (expected ~200mm)")
        
        print("\n8. Testing final status...")
        final_status = controller.get_status()
        print(f"Final status: {final_status}")
        
        print("\n9. Testing small movement...")
        test_point = Point(5, 195, 0, 90)  # Small movement from home
        move_success = controller.move_to_point(test_point, feedrate=100)
        print(f"Movement result: {'✅ Success' if move_success else '❌ Failed'}")
        
        if move_success:
            # Check position after movement
            new_pos = controller.get_machine_position()
            print(f"Position after move: X:{new_pos.x:.1f} Y:{new_pos.y:.1f} Z:{new_pos.z:.1f} C:{new_pos.c:.1f}")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False
        
    finally:
        print("\n10. Disconnecting...")
        controller.disconnect()
        print("✅ Disconnected")

def test_timeout_values():
    """Test that different commands get appropriate timeouts"""
    print("\n🔧 Testing Timeout Values")
    print("=" * 30)
    
    controller = FluidNCController()
    
    test_commands = [
        ("$H", "Homing command"),
        ("G1 X10 Y10 F500", "Movement command"),
        ("?", "Status query"),
        ("$X", "Unlock command"),
        ("G21", "Settings command")
    ]
    
    for gcode, description in test_commands:
        timeout = controller._get_command_timeout(gcode)
        print(f"{description:<20}: {gcode:<15} -> {timeout:>5.1f}s timeout")

def test_homing_verification():
    """Test the homing verification logic"""
    print("\n🔧 Testing Homing Verification Logic")
    print("=" * 40)
    
    controller = FluidNCController()
    
    # Test different status scenarios
    test_cases = [
        # (status, expected_homed, description)
        ("<Idle|MPos:0.000,200.000,0.000,90.000|FS:0,0|WCO:0.000,0.000,0.000,0.000>", True, "Properly homed at Y=200"),
        ("<Idle|MPos:5.000,195.000,45.000,95.000|FS:0,0|WCO:0.000,0.000,0.000,0.000>", True, "Homed and moved slightly"),
        ("<Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0|WCO:0.000,0.000,0.000,0.000>", False, "At origin, not homed position"),
        ("<Alarm|MPos:0.000,200.000,0.000,90.000>", False, "Alarm state, not homed"),
        ("<Idle|MPos:0.000,100.000,0.000,90.000|FS:0,0>", False, "No WCO, questionable homing"),
        ("<Idle|MPos:0.000,200.000,0.000,90.000|FS:0,0>", False, "No WCO present"),
    ]
    
    for status, expected, description in test_cases:
        # Temporarily replace get_status method
        original_get_status = controller.get_status
        controller.get_status = lambda: status
        
        # Test homing check
        result = controller.check_homing_status()
        status_icon = "✅" if result == expected else "❌"
        
        print(f"{status_icon} {description}: {result} (expected {expected})")
        
        # Restore original method
        controller.get_status = original_get_status

def test_message_parsing():
    """Test FluidNC message parsing capabilities"""
    print("\n🔧 Testing Message Parsing")
    print("=" * 30)
    
    # Test status parsing
    test_statuses = [
        "<Idle|MPos:0.000,200.000,0.000,90.000|FS:0,0|WCO:0.000,0.000,0.000,0.000>",
        "<Home|MPos:0.000,200.000,0.000,90.000|FS:0,0>",
        "<Run|MPos:10.500,195.300,45.000,95.000|FS:500,0|WCO:0.000,0.000,0.000,0.000>",
        "<Alarm|MPos:0.000,0.000,0.000,0.000>"
    ]
    
    controller = FluidNCController()
    
    for status in test_statuses:
        print(f"\nTesting status: {status}")
        
        # Temporarily set status for testing
        original_get_status = controller.get_status
        controller.get_status = lambda: status
        
        # Test parsing
        is_homed = controller.is_homed()
        machine_pos = controller.get_machine_position()
        work_pos = controller.get_work_position()
        
        print(f"  Is homed: {is_homed}")
        print(f"  Machine pos: X:{machine_pos.x} Y:{machine_pos.y} Z:{machine_pos.z} C:{machine_pos.c}")
        print(f"  Work pos: X:{work_pos.x} Y:{work_pos.y} Z:{work_pos.z} C:{work_pos.c}")
        
        # Restore original method
        controller.get_status = original_get_status

if __name__ == "__main__":
    print("FluidNC Communication Test Suite")
    print("=" * 50)
    
    # Test timeout calculation
    test_timeout_values()
    
    # Test homing verification logic
    test_homing_verification()
    
    # Test message parsing
    test_message_parsing()
    
    # Ask user if they want to test with actual hardware
    response = input("\n🤖 Do you want to test with actual FluidNC hardware? (y/N): ").strip().lower()
    
    if response == 'y':
        test_fluidnc_communication()
    else:
        print("Skipping hardware test")
    
    print("\n✅ Test suite completed")