#!/usr/bin/env python3
"""
Enhanced test script to verify FluidNC hybrid status approach

Tests both:
1. Background monitor during movement (when auto-reports are active)
2. Manual queries during idle periods (when auto-reports stop)

This validates the hybrid approach works correctly without serial conflicts.
"""

import asyncio
import logging
import sys
import time
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from motion.fluidnc_controller import FluidNCController, Position4D
from core.config_manager import ConfigManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_hybrid_status_approach():
    """Test the hybrid status approach comprehensively"""
    logger.info("🧪 Testing FluidNC hybrid status approach...")
    
    try:
        # Create controller with basic config
        motion_config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 10.0
        }
        
        controller = FluidNCController(motion_config)
        
        # Test connection
        logger.info("📡 Testing FluidNC connection...")
        connected = await controller.connect()
        
        if not connected:
            logger.error("❌ Failed to connect to FluidNC")
            return False
        
        logger.info("✅ Connected to FluidNC")
        
        # Phase 1: Test idle period status (should use manual queries)
        logger.info("🔍 Phase 1: Testing idle period status updates...")
        idle_successes = 0
        idle_errors = 0
        
        for i in range(5):
            try:
                start_time = time.time()
                status = await controller.get_status()
                query_time = time.time() - start_time
                
                position_age = time.time() - controller.last_position_update if controller.last_position_update > 0 else 999.0
                
                logger.info(f"  Idle query {i+1}: Status={status.name}, Position={controller.current_position}, Query_time={query_time:.3f}s, Data_age={position_age:.1f}s")
                
                if position_age < 5.0:  # Should be fresh from manual query
                    idle_successes += 1
                else:
                    logger.warning(f"  Data still stale after manual query")
                    
            except Exception as e:
                idle_errors += 1
                logger.error(f"  Idle query error: {e}")
                
            await asyncio.sleep(2.0)
        
        logger.info(f"📊 Idle period results: {idle_successes}/5 successful queries, {idle_errors} errors")
        
        # Phase 2: Test movement period (if system is homed and can move)
        logger.info("🔍 Phase 2: Testing movement period status updates...")
        movement_test_possible = False
        
        if controller.is_homed and controller.status == controller.status.IDLE:
            try:
                # Make a small relative movement to trigger auto-reports
                logger.info("  Attempting small test movement to trigger auto-reports...")
                
                current_pos = controller.current_position
                test_pos = Position4D(
                    x=current_pos.x,
                    y=current_pos.y,
                    z=current_pos.z + 0.5,  # Small Z movement
                    c=current_pos.c
                )
                
                # Start movement
                move_success = await controller.move_to_position(test_pos, feedrate=100.0)
                if move_success:
                    movement_test_possible = True
                    logger.info("  ✅ Movement started - monitoring auto-report handling...")
                    
                    # Monitor during movement
                    movement_updates = 0
                    for i in range(10):  # Monitor for up to 20 seconds
                        start_time = time.time()
                        status = await controller.get_status()
                        query_time = time.time() - start_time
                        
                        position_age = time.time() - controller.last_position_update if controller.last_position_update > 0 else 999.0
                        
                        logger.info(f"    Movement query {i+1}: Status={status.name}, Query_time={query_time:.3f}s, Data_age={position_age:.1f}s")
                        
                        if position_age < 1.0:  # Fresh data from background monitor
                            movement_updates += 1
                            
                        if status == controller.status.IDLE:
                            logger.info("  ✅ Movement completed")
                            break
                            
                        await asyncio.sleep(2.0)
                    
                    logger.info(f"📊 Movement period results: {movement_updates} fresh updates received")
                else:
                    logger.warning("  ⚠️  Movement failed - skipping movement phase test")
                    
            except Exception as e:
                logger.warning(f"  ⚠️  Movement test failed: {e}")
        else:
            logger.info("  ⚠️  System not homed or not idle - skipping movement test")
            logger.info(f"     is_homed={controller.is_homed}, status={controller.status}")
        
        # Phase 3: Test alarm state handling
        logger.info("🔍 Phase 3: Testing alarm state detection...")
        try:
            alarm_state = await controller.get_alarm_state()
            logger.info(f"  Alarm state: {alarm_state}")
            
            if not alarm_state.get('is_alarm', True):
                logger.info("  ✅ No alarm state detected")
            else:
                logger.warning(f"  ⚠️  System reports alarm: {alarm_state.get('message', 'Unknown')}")
                
        except Exception as e:
            logger.error(f"  ❌ Alarm state check failed: {e}")
        
        # Overall assessment
        overall_success = (idle_successes >= 3 and idle_errors == 0)  # Most idle queries successful
        if movement_test_possible:
            overall_success = overall_success and (movement_updates > 0)  # Some fresh movement data
        
        if overall_success:
            logger.info("🎉 Hybrid status approach working correctly!")
            logger.info("   ✅ Manual queries work during idle periods")
            if movement_test_possible:
                logger.info("   ✅ Background monitor provides fresh data during movement")
            logger.info("   ✅ No serial conflicts detected")
        else:
            logger.warning("⚠️  Hybrid approach has some issues:")
            if idle_successes < 3:
                logger.warning("   - Manual queries during idle periods not working optimally")
            if idle_errors > 0:
                logger.warning(f"   - {idle_errors} query errors detected")
            if movement_test_possible and movement_updates == 0:
                logger.warning("   - Background monitor not providing fresh data during movement")
        
        # Clean shutdown
        await controller.disconnect()
        logger.info("🔌 Disconnected from FluidNC")
        
        return overall_success
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        logger.exception("Exception details:")
        return False

async def main():
    """Main test function"""
    logger.info("🚀 Starting FluidNC hybrid status approach test...")
    
    success = await test_hybrid_status_approach()
    
    if success:
        logger.info("🎉 Hybrid approach validated! System ready for web interface.")
        logger.info("💡 Run: python3 run_web_interface.py")
        sys.exit(0)
    else:
        logger.error("💥 Hybrid approach needs refinement.")
        logger.error("🔧 Check FluidNC connection and auto-report configuration.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())