#!/usr/bin/env python3
"""
Standalone Movement Timing Test Script
Tests FluidNC movement timing without web interface to isolate the issue
"""

import asyncio
import sys
import time
from pathlib import Path

# Add current directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from motion.fluidnc_controller import FluidNCController
from motion.base import Position4D
from core.config_manager import ConfigManager
from core.events import EventBus
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_movement_timing():
    """Test movement timing with detailed logging"""
    
    logger.info("🚀 Starting FluidNC Movement Timing Test")
    
    # Initialize FluidNC controller with basic config
    fluidnc_config = {
        'port': '/dev/ttyUSB0',  # Default FluidNC port
        'baudrate': 115200,
        'axes': {
            'x': {'min': 0, 'max': 200},
            'y': {'min': 0, 'max': 200}, 
            'z': {'min': -360, 'max': 360},
            'c': {'min': -90, 'max': 90}
        }
    }
    
    # Initialize FluidNC controller
    controller = FluidNCController(fluidnc_config)
    
    try:
        # Connect to FluidNC
        logger.info("📡 Connecting to FluidNC...")
        await controller.connect()
        
        if not controller.is_connected():
            logger.error("❌ Failed to connect to FluidNC")
            return
            
        logger.info("✅ Connected to FluidNC")
        
        # Get initial position
        initial_pos = await controller.get_current_position()
        logger.info(f"📍 Initial position: {initial_pos}")
        
        # Test 1: Small Z movement
        logger.info("\n" + "="*60)
        logger.info("🔧 TEST 1: Small Z-axis movement (+1mm)")
        logger.info("="*60)
        
        start_time = time.time()
        
        # Send movement command with detailed timing
        delta = Position4D(x=0.0, y=0.0, z=1.0, c=0.0)
        logger.info(f"⏰ Sending relative move command at {time.time():.3f}")
        
        result = await controller.move_relative(delta, feedrate=10.0)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        logger.info(f"⏰ Movement function completed at {end_time:.3f}")
        logger.info(f"⏱️  Total time: {total_time:.3f} seconds")
        
        # Get final position
        final_pos = await controller.get_current_position()
        logger.info(f"📍 Final position: {final_pos}")
        
        # Calculate actual movement
        actual_delta = Position4D(
            x=final_pos.x - initial_pos.x,
            y=final_pos.y - initial_pos.y,
            z=final_pos.z - initial_pos.z,
            c=final_pos.c - initial_pos.c
        )
        logger.info(f"📏 Actual movement: {actual_delta}")
        logger.info(f"📊 Expected vs Actual Z: {delta.z:.3f} vs {actual_delta.z:.3f}")
        
        # Test 2: Wait and observe background status for 10 seconds
        logger.info("\n" + "="*60)
        logger.info("🔧 TEST 2: Monitoring FluidNC status for 10 seconds")
        logger.info("="*60)
        
        for i in range(10):
            await asyncio.sleep(1)
            current_pos = controller.current_position
            status = controller.status
            logger.info(f"⏰ T+{i+1}s: Status={status}, Position={current_pos}")
        
        # Test 3: Rapid sequence of small movements
        logger.info("\n" + "="*60)
        logger.info("🔧 TEST 3: Rapid sequence of small movements")
        logger.info("="*60)
        
        for i in range(3):
            logger.info(f"\n--- Movement {i+1}/3 ---")
            start_time = time.time()
            
            delta = Position4D(x=0.0, y=0.0, z=0.5, c=0.0)
            result = await controller.move_relative(delta, feedrate=10.0)
            
            end_time = time.time()
            logger.info(f"Movement {i+1} completed in {end_time - start_time:.3f}s")
            
            # Brief pause between movements
            await asyncio.sleep(0.5)
        
        logger.info("\n🎯 Test completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Cleanup
        try:
            await controller.disconnect()
            logger.info("📡 Disconnected from FluidNC")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

if __name__ == "__main__":
    logger.info("🔬 FluidNC Movement Timing Analysis")
    logger.info("This script tests movement timing without web interface")
    logger.info("Press Ctrl+C to exit\n")
    
    try:
        asyncio.run(test_movement_timing())
    except KeyboardInterrupt:
        logger.info("\n🛑 Test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Test script failed: {e}")
        import traceback
        traceback.print_exc()