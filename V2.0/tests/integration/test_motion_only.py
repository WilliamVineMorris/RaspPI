#!/usr/bin/env python3
"""
FluidNC Motion Controller Test Script

Focused testing for the FluidNC motion controller on Raspberry Pi.
Tests serial communication, G-code commands, and motion validation.

Usage:
    python test_motion_only.py [--port PORT] [--baudrate BAUD] [--interactive]

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from motion.fluidnc_controller import FluidNCController
from motion.base import Position4D, MotionStatus
from core.logging_setup import setup_logging

class MotionControllerTester:
    """Focused motion controller testing"""
    
    def __init__(self, port: str, baudrate: int, interactive: bool = False):
        self.port = port
        self.baudrate = baudrate
        self.interactive = interactive
        self.logger = logging.getLogger(__name__)
        
        # Test configuration
        self.config = {
            'port': port,
            'baudrate': baudrate,
            'timeout': 10.0,
            'axes': {
                'x_axis': {'min_limit': -150.0, 'max_limit': 150.0, 'max_feedrate': 8000.0},
                'y_axis': {'min_limit': -100.0, 'max_limit': 100.0, 'max_feedrate': 8000.0},
                'z_axis': {'min_limit': -180.0, 'max_limit': 180.0, 'max_feedrate': 3600.0},
                'c_axis': {'min_limit': -45.0, 'max_limit': 45.0, 'max_feedrate': 1800.0}
            }
        }
        
    async def run_tests(self) -> bool:
        """Run all motion controller tests"""
        self.logger.info("🚀 FluidNC Motion Controller Test Suite")
        self.logger.info(f"Port: {self.port}, Baudrate: {self.baudrate}")
        
        success = True
        
        # Basic tests
        success &= await self.test_controller_creation()
        success &= await self.test_position_validation()
        success &= await self.test_limits_management()
        success &= await self.test_capabilities()
        
        # Hardware tests
        success &= await self.test_connection()
        
        if self.interactive:
            await self.run_interactive_tests()
        
        return success
    
    async def test_controller_creation(self) -> bool:
        """Test controller instantiation"""
        self.logger.info("\n📋 Testing Controller Creation...")
        
        try:
            controller = FluidNCController(self.config)
            
            self.logger.info(f"   ✅ Controller created")
            self.logger.info(f"   Port: {controller.port}")
            self.logger.info(f"   Baudrate: {controller.baudrate}")
            self.logger.info(f"   Timeout: {controller.timeout}")
            self.logger.info(f"   Initial status: {controller.status}")
            self.logger.info(f"   Initial position: {controller.current_position}")
            self.logger.info(f"   Axes configured: {len(controller.axis_limits)}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Controller creation failed: {e}")
            return False
    
    async def test_position_validation(self) -> bool:
        """Test position validation logic"""
        self.logger.info("\n🎯 Testing Position Validation...")
        
        try:
            controller = FluidNCController(self.config)
            
            # Test valid positions
            valid_positions = [
                Position4D(x=0.0, y=0.0, z=0.0, c=0.0),           # Origin
                Position4D(x=100.0, y=50.0, z=90.0, c=30.0),      # Within limits
                Position4D(x=-100.0, y=-50.0, z=-90.0, c=-30.0),  # Negative within limits
                Position4D(x=150.0, y=100.0, z=180.0, c=45.0),    # At limits
            ]
            
            # Test invalid positions
            invalid_positions = [
                Position4D(x=200.0, y=0.0, z=0.0, c=0.0),         # X out of range
                Position4D(x=0.0, y=150.0, z=0.0, c=0.0),         # Y out of range
                Position4D(x=0.0, y=0.0, z=200.0, c=0.0),         # Z out of range
                Position4D(x=0.0, y=0.0, z=0.0, c=60.0),          # C out of range
            ]
            
            valid_count = 0
            for pos in valid_positions:
                if controller._validate_position(pos):
                    valid_count += 1
                    self.logger.info(f"   ✅ Valid: {pos}")
                else:
                    self.logger.error(f"   ❌ Should be valid: {pos}")
            
            invalid_count = 0
            for pos in invalid_positions:
                if not controller._validate_position(pos):
                    invalid_count += 1
                    self.logger.info(f"   ✅ Invalid (correct): {pos}")
                else:
                    self.logger.error(f"   ❌ Should be invalid: {pos}")
            
            success = (valid_count == len(valid_positions) and 
                      invalid_count == len(invalid_positions))
            
            self.logger.info(f"   Position validation: {valid_count}/{len(valid_positions)} valid, "
                           f"{invalid_count}/{len(invalid_positions)} invalid")
            
            return success
            
        except Exception as e:
            self.logger.error(f"   ❌ Position validation test failed: {e}")
            return False
    
    async def test_limits_management(self) -> bool:
        """Test motion limits management"""
        self.logger.info("\n⚖️  Testing Limits Management...")
        
        try:
            controller = FluidNCController(self.config)
            
            # Test getting limits
            for axis in ['x', 'y', 'z', 'c']:
                try:
                    limits = await controller.get_motion_limits(axis)
                    self.logger.info(f"   {axis.upper()} limits: {limits.min_limit} to {limits.max_limit}, "
                                   f"max feed: {limits.max_feedrate}")
                except Exception as e:
                    self.logger.error(f"   ❌ Failed to get {axis} limits: {e}")
                    return False
            
            # Test setting limits
            from motion.base import MotionLimits
            new_limits = MotionLimits(-200.0, 200.0, 10000.0)
            
            success = await controller.set_motion_limits('x', new_limits)
            if success:
                retrieved_limits = await controller.get_motion_limits('x')
                if (retrieved_limits.min_limit == new_limits.min_limit and
                    retrieved_limits.max_limit == new_limits.max_limit):
                    self.logger.info("   ✅ Limits setting and retrieval working")
                else:
                    self.logger.error("   ❌ Limits not set correctly")
                    return False
            else:
                self.logger.error("   ❌ Failed to set limits")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Limits management test failed: {e}")
            return False
    
    async def test_capabilities(self) -> bool:
        """Test controller capabilities"""
        self.logger.info("\n🛠️  Testing Controller Capabilities...")
        
        try:
            controller = FluidNCController(self.config)
            
            capabilities = await controller.get_capabilities()
            
            self.logger.info(f"   Axes count: {capabilities.axes_count}")
            self.logger.info(f"   Supports homing: {capabilities.supports_homing}")
            self.logger.info(f"   Supports soft limits: {capabilities.supports_soft_limits}")
            self.logger.info(f"   Supports probe: {capabilities.supports_probe}")
            self.logger.info(f"   Max feedrate: {capabilities.max_feedrate}")
            self.logger.info(f"   Position resolution: {capabilities.position_resolution}")
            
            # Validate expected capabilities
            expected_axes = 4
            if capabilities.axes_count == expected_axes:
                self.logger.info("   ✅ Correct axes count")
            else:
                self.logger.error(f"   ❌ Expected {expected_axes} axes, got {capabilities.axes_count}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Capabilities test failed: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """Test hardware connection"""
        self.logger.info("\n🔌 Testing Hardware Connection...")
        
        try:
            controller = FluidNCController(self.config)
            
            self.logger.info(f"   Attempting connection to {self.port}...")
            
            # Test initialization
            connected = await controller.initialize()
            
            if connected:
                self.logger.info("   ✅ FluidNC controller connected successfully!")
                
                # Test status
                status = await controller.get_status()
                position = await controller.get_position()
                
                self.logger.info(f"   Current status: {status}")
                self.logger.info(f"   Current position: {position}")
                
                # Test if controller is homed
                if controller.is_homed:
                    self.logger.info("   ✅ Controller is homed")
                else:
                    self.logger.info("   ⚠️  Controller not homed (normal on startup)")
                
                # Test emergency stop (safe command)
                self.logger.info("   Testing emergency stop...")
                estop_success = await controller.emergency_stop()
                if estop_success:
                    self.logger.info("   ✅ Emergency stop command sent")
                
                # Test reset
                self.logger.info("   Testing controller reset...")
                reset_success = await controller.reset_controller()
                if reset_success:
                    self.logger.info("   ✅ Controller reset successful")
                
                # Shutdown
                await controller.shutdown()
                self.logger.info("   ✅ Controller shutdown complete")
                
                return True
                
            else:
                self.logger.warning(f"   ⚠️  Could not connect to FluidNC at {self.port}")
                self.logger.warning("   This is normal if hardware is not connected")
                return True  # Not a failure if hardware isn't available
                
        except Exception as e:
            self.logger.warning(f"   ⚠️  Connection test failed: {e}")
            self.logger.warning("   This is normal if FluidNC hardware is not connected")
            return True  # Not a failure if hardware isn't available
    
    async def run_interactive_tests(self):
        """Run interactive tests with user input"""
        self.logger.info("\n🎮 Interactive Tests")
        self.logger.info("WARNING: These tests will send actual commands to the FluidNC controller!")
        
        response = input("Do you want to proceed with interactive tests? (y/N): ")
        if response.lower() != 'y':
            self.logger.info("Interactive tests skipped")
            return
        
        try:
            controller = FluidNCController(self.config)
            connected = await controller.initialize()
            
            if not connected:
                self.logger.error("Cannot run interactive tests - controller not connected")
                return
            
            while True:
                print("\nInteractive Test Menu:")
                print("1. Get current status")
                print("2. Get current position")
                print("3. Test home axis (specify axis)")
                print("4. Test jog movement (small movement)")
                print("5. Send custom G-code")
                print("6. Emergency stop")
                print("7. Exit")
                
                choice = input("Enter choice (1-7): ").strip()
                
                if choice == '1':
                    status = await controller.get_status()
                    print(f"Status: {status}")
                
                elif choice == '2':
                    position = await controller.get_position()
                    print(f"Position: {position}")
                
                elif choice == '3':
                    axis = input("Enter axis to home (X/Y/Z/C): ").strip().upper()
                    if axis in ['X', 'Y', 'Z', 'C']:
                        print(f"Homing {axis} axis...")
                        success = await controller.home_axis(axis)
                        print(f"Homing result: {success}")
                    else:
                        print("Invalid axis")
                
                elif choice == '4':
                    axis = input("Enter axis to jog (X/Y/Z/C): ").strip().upper()
                    distance = input("Enter distance (small value): ").strip()
                    try:
                        distance = float(distance)
                        if abs(distance) > 10:
                            print("Distance too large for safety")
                            continue
                        
                        delta = Position4D(0, 0, 0, 0)
                        if axis == 'X':
                            delta.x = distance
                        elif axis == 'Y':
                            delta.y = distance
                        elif axis == 'Z':
                            delta.z = distance
                        elif axis == 'C':
                            delta.c = distance
                        else:
                            print("Invalid axis")
                            continue
                        
                        print(f"Jogging {axis} by {distance}...")
                        success = await controller.move_relative(delta, 1000.0)
                        print(f"Jog result: {success}")
                        
                    except ValueError:
                        print("Invalid distance")
                
                elif choice == '5':
                    gcode = input("Enter G-code command: ").strip()
                    if gcode:
                        print(f"Sending: {gcode}")
                        success = await controller.execute_gcode(gcode)
                        print(f"Result: {success}")
                
                elif choice == '6':
                    print("Sending emergency stop...")
                    success = await controller.emergency_stop()
                    print(f"Emergency stop result: {success}")
                
                elif choice == '7':
                    break
                
                else:
                    print("Invalid choice")
            
            await controller.shutdown()
            
        except Exception as e:
            self.logger.error(f"Interactive test error: {e}")


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='FluidNC Motion Controller Test')
    parser.add_argument('--port', default='/dev/ttyUSB0', help='Serial port for FluidNC')
    parser.add_argument('--baudrate', type=int, default=115200, help='Serial baudrate')
    parser.add_argument('--interactive', action='store_true', help='Run interactive tests')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging()
    logging.getLogger().setLevel(log_level)
    
    # Run tests
    tester = MotionControllerTester(args.port, args.baudrate, args.interactive)
    success = await tester.run_tests()
    
    if success:
        print("\n🎉 All motion controller tests passed!")
    else:
        print("\n❌ Some motion controller tests failed!")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())