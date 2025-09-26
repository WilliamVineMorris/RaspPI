#!/usr/bin/env python3
"""
Test Motion Completion with Slow Movements

This test uses very slow feedrates to verify that motion completion
waiting is working properly with real mechanical movement times.

Usage:
    python test_slow_motion_completion.py
"""

import asyncio
import logging
import time
from pathlib import Path

# Import real system components
from core.config_manager import ConfigManager
from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed

# Test logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_slow_motion_completion():
    """Test motion completion with deliberately slow movements"""
    logger.info("🐌 Testing SLOW Motion Completion")
    
    try:
        # Initialize FluidNC controller
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_file)
        
        config_dict = {
            'motion': config_manager.get('motion', {}),
            'system': config_manager.get('system', {}),
            'fluidnc': config_manager.get('fluidnc', {})
        }
        motion_controller = SimplifiedFluidNCControllerFixed(config_dict)
        
        # Connect to FluidNC
        logger.info("🔌 Connecting to FluidNC...")
        connected = await motion_controller.connect()
        
        if not connected:
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected to FluidNC")
        
        # Set to scanning mode for feedrate control
        motion_controller.set_operating_mode("scanning_mode")
        logger.info("🔧 Set to scanning mode for controlled feedrates")
        
        # Get current position
        start_position = await motion_controller.get_position()
        logger.info(f"📍 Starting position: {start_position}")
        
        # Test with very slow feedrates to see motion completion timing
        logger.info("\n" + "="*60)
        logger.info("🐌 TESTING SLOW MOTION WITH CONTROLLED FEEDRATES")
        logger.info("="*60)
        
        # Test movements with specific slow feedrates
        test_moves = [
            {
                "name": "Very slow X move (F50)",
                "position": (start_position.x + 5.0, start_position.y, start_position.z, start_position.c),
                "feedrate": 50,  # Very slow: 50 mm/min
                "expected_time": 6000  # 5mm at 50mm/min = 6 seconds
            },
            {
                "name": "Slow Y move (F100)",
                "position": (start_position.x + 5.0, start_position.y + 5.0, start_position.z, start_position.c),
                "feedrate": 100,  # Slow: 100 mm/min
                "expected_time": 3000  # 5mm at 100mm/min = 3 seconds
            },
            {
                "name": "Return to start (F200)",
                "position": (start_position.x, start_position.y, start_position.z, start_position.c),
                "feedrate": 200,  # Medium: 200 mm/min
                "expected_time": 2000  # ~7mm diagonal at 200mm/min = ~2 seconds
            }
        ]
        
        for i, move in enumerate(test_moves, 1):
            logger.info(f"\n🎯 TEST {i}: {move['name']}")
            logger.info(f"   Target: X={move['position'][0]:.1f}, Y={move['position'][1]:.1f}")
            logger.info(f"   Feedrate: {move['feedrate']} mm/min")
            logger.info(f"   Expected time: ~{move['expected_time']/1000:.1f} seconds")
            
            # Create Position4D object
            from motion.base import Position4D
            target_position = Position4D(
                x=move['position'][0],
                y=move['position'][1], 
                z=move['position'][2],
                c=move['position'][3]
            )
            
            # Time the movement
            move_start = time.time()
            logger.info(f"   🏁 Starting movement at {move_start:.3f}...")
            
            # Execute the movement with specific feedrate
            success = await motion_controller.move_to_position(target_position, move['feedrate'])
            
            move_end = time.time()
            actual_duration = (move_end - move_start) * 1000
            
            if success:
                logger.info(f"   ✅ Move completed in {actual_duration:.0f}ms ({actual_duration/1000:.1f}s)")
                
                # Verify final position
                final_position = await motion_controller.get_position()
                logger.info(f"   📍 Final position: {final_position}")
                
                # Analyze timing
                expected_min = move['expected_time']
                timing_ratio = actual_duration / expected_min
                
                if actual_duration < expected_min * 0.1:  # Less than 10% of expected
                    logger.error(f"   ❌ MOTION COMPLETION ISSUE!")
                    logger.error(f"      Actual: {actual_duration:.0f}ms, Expected: >{expected_min:.0f}ms")
                    logger.error(f"      System is NOT waiting for real motion completion!")
                elif actual_duration < expected_min * 0.5:  # Less than 50% of expected
                    logger.warning(f"   ⚠️ Motion faster than expected:")
                    logger.warning(f"      Actual: {actual_duration:.0f}ms, Expected: ~{expected_min:.0f}ms")
                    logger.warning(f"      May not be waiting for full motion completion")
                else:
                    logger.info(f"   ✅ Motion timing looks realistic!")
                    logger.info(f"      Actual: {actual_duration:.0f}ms, Expected: ~{expected_min:.0f}ms")
                    logger.info(f"      System IS waiting for real motion completion!")
                
            else:
                logger.error(f"   ❌ Move failed")
            
            # Small delay between moves
            await asyncio.sleep(1.0)
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 SLOW MOTION TEST SUMMARY")
        logger.info("="*60)
        logger.info("This test verifies motion completion by using slow feedrates")
        logger.info("If timing matches expectations, motion completion is working!")
        
        # Disconnect
        await motion_controller.disconnect()
        logger.info("🔌 Disconnected from FluidNC")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    print("🐌 SLOW MOTION COMPLETION TEST")
    print("="*50)
    print("This test uses very slow feedrates to verify that")
    print("the system actually waits for mechanical motion completion.")
    print("")
    print("If motion completion is working properly:")
    print("• F50 (50mm/min) moves should take several seconds")
    print("• System should wait for real motion to finish")
    print("• Timing should match expected mechanical movement")
    print("")
    
    success = asyncio.run(test_slow_motion_completion())
    
    if success:
        print("\n🎯 MOTION COMPLETION ANALYSIS:")
        print("Check the timing results above:")
        print("✅ If moves took expected time → Motion completion is working")
        print("❌ If moves were too fast → Motion completion needs fixing")
    else:
        print("\n❌ Test failed - check FluidNC hardware connection")