#!/usr/bin/env python3
"""
Test Fixed Homing Integration

This script tests the integration of:
- FixedFluidNCProtocol (with proper "Homing done" detection)
- FixedFluidNCController (implementing MotionController interface)
- Complete homing system with status management

Based on the successful test_homing_completion.py and test_simple_homing.py results.

Author: Scanner System Development
Created: September 26, 2025
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the motion module to path
sys.path.append(str(Path(__file__).parent))

from motion.fixed_fluidnc_controller import FixedFluidNCController
from motion.base import MotionStatus, Position4D

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_fixed_homing_integration():
    """Test the complete fixed homing system"""
    
    print("🧪 Testing Fixed Homing Integration")
    print("=" * 50)
    
    # Create controller
    controller = FixedFluidNCController("/dev/ttyUSB0")
    
    try:
        # Initialize controller
        print("🚀 Initializing controller...")
        if not await controller.initialize():
            print("❌ Failed to initialize controller")
            return False
        
        print("✅ Controller initialized successfully")
        
        # Check initial status
        status = controller.get_status()
        print(f"📊 Initial status: {status}")
        
        # Get position
        position = await controller.get_position()
        print(f"📍 Current position: {position}")
        
        # Check if already homed
        if controller.is_homed():
            print("✅ System is already homed")
        else:
            print("⚠️  System needs homing")
            
            # Safety confirmation
            print("\n" + "=" * 60)
            print("⚠️  SAFETY WARNING:")
            print("⚠️  About to start homing sequence!")
            print("⚠️  Ensure all axes can move freely to limit switches!")
            print("⚠️  Be ready to hit emergency stop if needed!")
            print("=" * 60)
            
            confirm = input("\nPress Enter when ready to start homing (or Ctrl+C to cancel): ")
            
            print("\n🏠 Starting homing sequence...")
            start_time = time.time()
            
            # Home the axes using the fixed implementation
            success = await controller.home_axes()
            
            if success:
                elapsed = time.time() - start_time
                print(f"✅ Homing completed successfully in {elapsed:.1f} seconds!")
                
                # Verify homing status
                if controller.is_homed():
                    print("✅ System reports as homed")
                else:
                    print("⚠️  System does not report as homed")
                
                # Get final position
                final_position = await controller.get_position()
                print(f"📍 Final position: {final_position}")
                
                # Get final status
                final_status = controller.get_status()
                print(f"📊 Final status: {final_status}")
                
            else:
                print("❌ Homing failed!")
                return False
        
        # Test a small move if homed
        if controller.is_homed():
            print("\n🎯 Testing small move...")
            test_position = Position4D(10, 190, 0, 0)  # Small move
            
            if controller.validate_position(test_position):
                print(f"📤 Moving to: {test_position}")
                move_success = await controller.move_to_position(test_position)
                
                if move_success:
                    print("✅ Move completed successfully")
                    final_pos = await controller.get_position()
                    print(f"📍 Moved to: {final_pos}")
                else:
                    print("❌ Move failed")
            else:
                print("❌ Test position is invalid")
        
        # Get controller info
        info = controller.get_controller_info()
        print(f"\n📋 Controller Info:")
        for key, value in info.items():
            print(f"   {key}: {value}")
        
        print("\n✅ Fixed homing integration test completed!")
        return True
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
        return False
        
    except Exception as e:
        logger.error(f"❌ Test error: {e}")
        return False
        
    finally:
        # Shutdown controller
        print("🔽 Shutting down controller...")
        await controller.shutdown()
        print("✅ Controller shutdown complete")

async def main():
    """Main test function"""
    
    print("🧪 Fixed Homing Integration Test")
    print("=================================")
    print()
    print("This test validates the complete fixed homing system:")
    print("• FixedFluidNCProtocol with proper 'Homing done' detection")
    print("• FixedFluidNCController implementing MotionController interface")
    print("• Complete integration with status management")
    print()
    
    try:
        success = await test_fixed_homing_integration()
        
        if success:
            print("\n🎉 All tests passed!")
            print("✅ Fixed homing integration is working correctly")
            return 0
        else:
            print("\n❌ Test failed!")
            return 1
            
    except Exception as e:
        logger.error(f"❌ Test suite error: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())