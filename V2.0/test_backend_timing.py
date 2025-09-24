#!/usr/bin/env python3
"""
Simple Web Interface Timing Test - Using existing modules
"""

import asyncio
import time
import statistics
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from motion.fluidnc_controller import FluidNCController
from core.position import Position4D

async def test_motion_timing():
    """Test motion controller timing directly"""
    print("🔬 Testing Motion Controller Timing")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # Initialize motion controller
        motion_controller = FluidNCController(config)
        
        # Test status queries
        print("\n📊 Testing status queries...")
        status_times = []
        
        for i in range(10):
            start_time = time.time()
            try:
                status = await motion_controller.get_status()
                response_time = (time.time() - start_time) * 1000
                status_times.append(response_time)
                print(f"  Status query {i+1}: {response_time:.1f}ms")
            except Exception as e:
                print(f"  Status query {i+1}: ERROR - {e}")
            
            await asyncio.sleep(0.1)
        
        # Analyze status timing
        if status_times:
            avg_time = statistics.mean(status_times)
            min_time = min(status_times)
            max_time = max(status_times)
            
            print(f"\n📈 Status Query Results:")
            print(f"  Average: {avg_time:.1f}ms")
            print(f"  Min:     {min_time:.1f}ms")
            print(f"  Max:     {max_time:.1f}ms")
            
            if avg_time < 50:
                print(f"  ✅ EXCELLENT status timing")
            elif avg_time < 100:
                print(f"  ✅ GOOD status timing")
            else:
                print(f"  ⚠️  SLOW status timing")
        
        # Test small movements
        print(f"\n🎯 Testing small movements...")
        movement_times = []
        
        home_position = Position4D(x=10.0, y=10.0, z=0.0, c=0.0)
        
        for i in range(3):
            # Small movement
            target_position = Position4D(
                x=home_position.x + (0.5 if i % 2 == 0 else -0.5),
                y=home_position.y,
                z=home_position.z + (0.1 * i),
                c=home_position.c
            )
            
            start_time = time.time()
            try:
                success = await motion_controller.move_to_position(target_position, speed=20.0)
                response_time = (time.time() - start_time) * 1000
                movement_times.append(response_time)
                print(f"  Movement {i+1}: {response_time:.1f}ms (success: {success})")
            except Exception as e:
                print(f"  Movement {i+1}: ERROR - {e}")
            
            await asyncio.sleep(0.5)
        
        # Analyze movement timing
        if movement_times:
            avg_time = statistics.mean(movement_times)
            min_time = min(movement_times)
            max_time = max(movement_times)
            
            print(f"\n🚀 Movement Results:")
            print(f"  Average: {avg_time:.1f}ms")
            print(f"  Min:     {min_time:.1f}ms")
            print(f"  Max:     {max_time:.1f}ms")
            
            if avg_time < 500:
                print(f"  ✅ EXCELLENT movement timing")
            elif avg_time < 1000:
                print(f"  ✅ GOOD movement timing")
            else:
                print(f"  ⚠️  SLOW movement timing")
        
        # Overall assessment
        if status_times and movement_times:
            print(f"\n🎯 Overall Performance Assessment:")
            avg_status = statistics.mean(status_times)
            avg_movement = statistics.mean(movement_times)
            
            print(f"  Status queries: {avg_status:.1f}ms average")
            print(f"  Small movements: {avg_movement:.1f}ms average")
            
            if avg_status < 50 and avg_movement < 500:
                print(f"  ✅ Backend performance is EXCELLENT for real-time web UI")
            elif avg_status < 100 and avg_movement < 1000:
                print(f"  ✅ Backend performance is GOOD for web interface")
            else:
                print(f"  ⚠️  Backend may cause web UI delays")
        
        await motion_controller.cleanup()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

async def main():
    print("🔬 Simple Motion Timing Test")
    print("Testing backend performance directly...")
    print("(This tests the same systems the web interface uses)")
    
    await test_motion_timing()
    
    print(f"\n💡 To test the full web interface:")
    print(f"   1. Start web interface: python run_web_interface.py")
    print(f"   2. Run web test: python test_web_performance.py")

if __name__ == "__main__":
    asyncio.run(main())