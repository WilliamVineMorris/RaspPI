#!/usr/bin/env python3
"""
Movement Timing Test - Test improved movement detection
"""

import asyncio
import time
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from motion.fluidnc_controller import FluidNCController
from core.position import Position4D

async def test_movement_timing():
    """Test movement timing with the new optimizations"""
    print("🚀 Testing Movement Timing Optimizations")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # Initialize motion controller
        motion_controller = FluidNCController(config)
        
        print("📊 Testing small Z movements (similar to web interface)...")
        
        # Get current position
        current_pos = await motion_controller.get_current_position()
        print(f"🎯 Starting position: {current_pos}")
        
        # Test small movements with timing
        test_movements = [
            Position4D(x=0.0, y=0.0, z=1.0, c=0.0),    # +1mm Z
            Position4D(x=0.0, y=0.0, z=-1.0, c=0.0),   # -1mm Z  
            Position4D(x=0.0, y=0.0, z=0.5, c=0.0),    # +0.5mm Z
            Position4D(x=0.0, y=0.0, z=-0.5, c=0.0),   # -0.5mm Z
        ]
        
        for i, delta in enumerate(test_movements, 1):
            print(f"\n🎯 Test Movement {i}: {delta}")
            
            # Time the jog movement
            start_time = time.time()
            
            success = await motion_controller.jog(delta, speed=10.0)
            
            end_time = time.time()
            duration = (end_time - start_time) * 1000
            
            # Get final position
            final_pos = await motion_controller.get_current_position()
            
            print(f"  ✅ Movement {i}: {duration:.1f}ms (success: {success})")
            print(f"  📍 Final position: {final_pos}")
            
            # Quick analysis
            if duration < 500:
                print(f"  🚀 EXCELLENT timing (<500ms)")
            elif duration < 1000:
                print(f"  ✅ GOOD timing (<1s)")
            elif duration < 2000:
                print(f"  ⚠️  FAIR timing (<2s)")
            else:
                print(f"  ❌ SLOW timing (>{duration:.0f}ms)")
            
            # Wait between movements
            await asyncio.sleep(0.5)
        
        await motion_controller.cleanup()
        
        print(f"\n🎯 Movement Timing Test Complete!")
        print(f"💡 Expected improvements:")
        print(f"   - Fast completion detection for quick movements")
        print(f"   - Reduced extended timeout (1.5s instead of 3s)")
        print(f"   - Better IDLE status detection")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("🔬 Movement Timing Optimization Test")
    print("Testing the new fast movement detection...")
    
    await test_movement_timing()

if __name__ == "__main__":
    asyncio.run(main())