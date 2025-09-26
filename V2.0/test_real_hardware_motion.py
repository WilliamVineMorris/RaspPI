#!/usr/bin/env python3
"""
Real Hardware Motion Optimization Test

Test actual FluidNC hardware movement with motion optimization.
This will verify the motion controller actually moves the hardware.
"""

import sys
import asyncio
import logging
from pathlib import Path

v2_path = Path(__file__).parent
sys.path.insert(0, str(v2_path))

from core.config_manager import ConfigManager
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
from core.types import Position4D

logger = logging.getLogger(__name__)

class HardwareMotionTracker:
    """Track actual FluidNC commands sent to hardware"""
    def __init__(self, controller):
        self.controller = controller
        self.commands_sent = []
        
        # Get the protocol to track actual G-code commands
        self.protocol = controller.protocol
        self.original_send_command = self.protocol._send_command
        
        # Replace with tracking version
        self.protocol._send_command = self.track_command
        
    async def track_command(self, command, timeout=None):
        """Track G-code commands sent to FluidNC"""
        self.commands_sent.append(command)
        print(f"📡 HARDWARE COMMAND: {command}")
        return await self.original_send_command(command, timeout)

async def test_real_hardware_motion():
    """Test actual hardware motion with optimization"""
    print("Testing REAL HARDWARE motion with optimization...")
    print("⚠️  WARNING: This will move actual hardware!")
    
    # Load real configuration (not simulation)
    config_file = v2_path / "config" / "scanner_config.yaml"
    config_manager = ConfigManager(config_file)
    
    # Initialize real FluidNC controller with FluidNC-specific config
    fluidnc_config = {
        'port': config_manager.get('fluidnc.port', '/dev/ttyUSB0'),
        'baud_rate': config_manager.get('fluidnc.baud_rate', 115200),
        'command_timeout': config_manager.get('fluidnc.command_timeout', 10.0)
    }
    
    controller = SimplifiedFluidNCControllerFixed(fluidnc_config)
    
    # Setup command tracking
    tracker = HardwareMotionTracker(controller)
    
    try:
        # Initialize and connect to FluidNC
        print("🔗 Connecting to FluidNC...")
        success = await controller.initialize()
        if not success:
            print("❌ Failed to connect to FluidNC hardware")
            return False
            
        print("✅ Connected to FluidNC successfully")
        
        # Home the system first
        print("🏠 Homing system...")
        await controller.home()
        print("✅ Homing completed")
        
        # Clear command log
        tracker.commands_sent.clear()
        
        # Test optimized motion - single move_to_position call
        print("\n🎯 Testing optimized single 4D positioning...")
        test_position = Position4D(x=20.0, y=30.0, z=45.0, c=15.0)
        
        print(f"Moving to: {test_position}")
        start_time = asyncio.get_event_loop().time()
        
        # Convert to motion Position4D type
        from motion.base import Position4D as MotionPosition4D
        motion_pos = MotionPosition4D(
            x=test_position.x, y=test_position.y, 
            z=test_position.z, c=test_position.c
        )
        
        # This should send ONE G0 command instead of three
        success = await controller.move_to_position(motion_pos)
        
        end_time = asyncio.get_event_loop().time()
        move_time = end_time - start_time
        
        if success:
            print(f"✅ Hardware movement completed in {move_time:.1f}s")
        else:
            print(f"❌ Hardware movement failed")
            return False
        
        # Analyze actual commands sent to hardware
        print(f"\n📡 HARDWARE COMMAND ANALYSIS:")
        print(f"Total commands sent to FluidNC: {len(tracker.commands_sent)}")
        
        g0_commands = [cmd for cmd in tracker.commands_sent if cmd.startswith('G0 ')]
        motion_commands = [cmd for cmd in tracker.commands_sent if cmd.startswith(('G0 ', 'G1 '))]
        
        print(f"- G0 rapid move commands: {len(g0_commands)}")
        print(f"- Total motion commands: {len(motion_commands)}")
        
        print(f"\n📋 ACTUAL HARDWARE COMMANDS:")
        for i, cmd in enumerate(tracker.commands_sent, 1):
            print(f"{i:2d}. {cmd}")
        
        # Verify optimization worked
        if len(motion_commands) == 1 and len(g0_commands) == 1:
            print(f"\n✅ HARDWARE OPTIMIZATION VERIFIED!")
            print(f"   ✓ Single G0 command sent to FluidNC")
            print(f"   ✓ No redundant motion commands")
            print(f"   ✓ Hardware actually moved to position")
            return True
        else:
            print(f"\n⚠️  HARDWARE OPTIMIZATION ISSUE:")
            print(f"   Expected 1 motion command, got {len(motion_commands)}")
            print(f"   May still have redundant commands")
            return False
            
    except Exception as e:
        print(f"\n❌ HARDWARE TEST ERROR: {e}")
        print(f"Commands sent before error:")
        for cmd in tracker.commands_sent:
            print(f"  {cmd}")
        return False
        
    finally:
        # Cleanup - return to home
        try:
            print(f"\n🏠 Returning to home position...")
            await controller.home()
            print("✅ Returned to home")
        except:
            pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    try:
        result = asyncio.run(test_real_hardware_motion())
        if result:
            print(f"\n🎉 REAL HARDWARE MOTION OPTIMIZATION VERIFIED!")
            print(f"   The FluidNC controller is sending optimized commands")
            print(f"   Hardware motion is working correctly")
        else:
            print(f"\n💥 Hardware motion optimization needs work")
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Test interrupted - hardware may need manual homing")
    except Exception as e:
        print(f"\n💥 Hardware test failed: {e}")
        import traceback
        traceback.print_exc()