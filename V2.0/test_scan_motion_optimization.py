#!/usr/bin/env python3
"""
Test Motion Optimization in _move_to_point

Direct test to verify the _move_to_point method uses optimized single 4D positioning
instead of 3 separate axis commands.
"""

import sys
import os
import asyncio
import logging
from pathlib import Path

# Add the V2.0 directory to Python path  
v2_path = Path(__file__).parent
sys.path.insert(0, str(v2_path))

from core.config_manager import ConfigManager
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import ScanPoint
from core.types import Position4D

logger = logging.getLogger(__name__)

class MotionCommandTracker:
    """Track motion commands to verify optimization"""
    def __init__(self, orchestrator):
        self.commands = []
        
        # Get the motion controller from orchestrator
        motion_controller = orchestrator.motion_controller
        
        # Store original methods
        self.original_move_to = motion_controller.move_to
        self.original_move_z_to = motion_controller.move_z_to  
        self.original_rotate_to = motion_controller.rotate_to
        self.original_move_to_position = motion_controller.move_to_position
        
        # Replace methods with tracking versions
        motion_controller.move_to = self.track_move_to
        motion_controller.move_z_to = self.track_move_z_to
        motion_controller.rotate_to = self.track_rotate_to
        motion_controller.move_to_position = self.track_move_to_position
        
    async def track_move_to(self, x, y):
        self.commands.append(f"move_to({x}, {y})")
        return await self.original_move_to(x, y)
        
    async def track_move_z_to(self, z):
        self.commands.append(f"move_z_to({z})")
        return await self.original_move_z_to(z)
        
    async def track_rotate_to(self, c):
        self.commands.append(f"rotate_to({c})")
        return await self.original_rotate_to(c)
        
    async def track_move_to_position(self, position, feedrate=None):
        self.commands.append(f"move_to_position({position.x}, {position.y}, {position.z}, {position.c})")
        return await self.original_move_to_position(position, feedrate)

async def test_move_to_point_optimization():
    """Test that _move_to_point uses optimized single 4D positioning"""
    print("Testing _move_to_point motion optimization...")
    
    # Setup with simulation mode enabled
    config_file = v2_path / "config" / "scanner_config.yaml"
    config = ConfigManager(config_file)
    
    # Force simulation mode for testing
    config._config_data = {
        'system': {'simulation_mode': True}
    }
    
    # Initialize orchestrator (uses simulation mode)
    orchestrator = ScanOrchestrator(config)
    await orchestrator.initialize()
    
    # Setup command tracking
    tracker = MotionCommandTracker(orchestrator)
    
    # Create test scan point
    test_position = Position4D(x=15.0, y=20.0, z=30.0, c=45.0)
    test_point = ScanPoint(position=test_position)
    
    print(f"Testing movement to: {test_position}")
    
    try:
        # Test the _move_to_point method directly
        print("Executing _move_to_point...")
        
        # Clear commands before test
        tracker.commands.clear()
        
        # Call the method directly
        await orchestrator._move_to_point(test_point)
        
        print(f"✅ Move completed successfully!")
        
        # Analyze commands
        print(f"\n📊 MOTION COMMAND ANALYSIS:")
        print(f"Total commands issued: {len(tracker.commands)}")
        
        move_to_position_count = len([c for c in tracker.commands if 'move_to_position' in c])
        move_to_count = len([c for c in tracker.commands if c.startswith('move_to(')])
        move_z_count = len([c for c in tracker.commands if 'move_z_to' in c])
        rotate_count = len([c for c in tracker.commands if 'rotate_to' in c])
        
        print(f"- move_to_position calls: {move_to_position_count}")
        print(f"- move_to calls: {move_to_count}")  
        print(f"- move_z_to calls: {move_z_count}")
        print(f"- rotate_to calls: {rotate_count}")
        
        print(f"\n📋 COMMAND LOG:")
        for i, cmd in enumerate(tracker.commands, 1):
            print(f"{i:2d}. {cmd}")
        
        # Verify optimization
        if move_to_position_count == 1 and (move_to_count + move_z_count + rotate_count) == 0:
            print(f"\n✅ OPTIMIZATION VERIFIED!")
            print(f"   ✓ Uses single move_to_position() call instead of 3 separate axis commands")
            print(f"   ✓ Eliminates redundant motion commands")
            return True
        elif move_to_position_count > 0:
            print(f"\n⚠️  PARTIAL OPTIMIZATION:")
            print(f"   ✓ Uses move_to_position() but also has separate axis commands")
            print(f"   → Should only use move_to_position for complete optimization")
            return False
        else:
            print(f"\n❌ NO OPTIMIZATION:")
            print(f"   ✗ Still using separate axis commands (move_to, move_z_to, rotate_to)")
            print(f"   ✗ Should use single move_to_position() call")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        print(f"Command log before error:")
        for i, cmd in enumerate(tracker.commands, 1):
            print(f"{i:2d}. {cmd}")
        return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)  # Reduce log noise
    
    try:
        result = asyncio.run(test_move_to_point_optimization())
        if result:
            print(f"\n🎉 Motion optimization test PASSED!")
            print(f"   Single 4D positioning is now working correctly")
            sys.exit(0)
        else:
            print(f"\n💥 Motion optimization test FAILED!")
            print(f"   Still using inefficient separate axis commands")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print(f"\n⚠️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)