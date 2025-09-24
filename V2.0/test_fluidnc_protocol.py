"""
FluidNC Protocol Test Script

Demonstrates the new protocol-compliant FluidNC communication system
that properly separates immediate commands from line-based commands
and eliminates message confusion.

Usage: python test_fluidnc_protocol.py

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import serial
import time
from motion.fluidnc_protocol import FluidNCProtocol, FluidNCCommunicator, MessageType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_protocol_basic():
    """Test basic protocol functionality"""
    logger.info("🔧 Testing FluidNC Protocol - Basic Functionality")
    
    try:
        # Connect to FluidNC (adjust port as needed)
        port = '/dev/ttyUSB0'  # Change to COM3, etc. on Windows
        ser = serial.Serial(port, 115200, timeout=0.1)
        
        # Create protocol handler
        protocol = FluidNCProtocol(ser)
        
        # Start protocol
        await protocol.start()
        
        logger.info("✅ Protocol started")
        
        # Test immediate status request
        logger.info("📡 Testing immediate status request...")
        await protocol.send_immediate_command('?')
        
        # Wait for auto-report
        await asyncio.sleep(1.0)
        
        # Test line-based command
        logger.info("📤 Testing line-based command...")
        response = await protocol.send_line_command('G21', timeout=2.0)
        logger.info(f"📥 Response: {response}")
        
        # Get statistics
        stats = protocol.get_stats()
        logger.info(f"📊 Protocol Stats: {stats}")
        
        # Stop protocol
        await protocol.stop()
        logger.info("✅ Protocol test complete")
        
    except Exception as e:
        logger.error(f"❌ Protocol test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_communicator():
    """Test high-level communicator"""
    logger.info("🚀 Testing FluidNC Communicator - High Level Interface")
    
    try:
        # Connect to FluidNC
        port = '/dev/ttyUSB0'  # Adjust port
        ser = serial.Serial(port, 115200, timeout=0.1)
        
        # Create communicator
        comm = FluidNCCommunicator(ser)
        
        # Start communicator
        await comm.start()
        logger.info("✅ Communicator started")
        
        # Test status
        status = await comm.get_status()
        logger.info(f"📊 Status: {status}")
        
        # Test G-code command
        success = await comm.send_gcode('G21')  # Metric units
        logger.info(f"📤 G21 command: {'✅ Success' if success else '❌ Failed'}")
        
        # Test position query
        await asyncio.sleep(0.5)  # Wait for auto-reports
        logger.info(f"📍 Position: {comm.current_position}")
        logger.info(f"🔄 Status: {comm.current_status}")
        
        # Get stats
        stats = comm.get_stats()
        logger.info(f"📊 Communication Stats: {stats}")
        
        # Stop communicator  
        await comm.stop()
        logger.info("✅ Communicator test complete")
        
    except Exception as e:
        logger.error(f"❌ Communicator test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_movement_timing():
    """Test movement timing with new protocol"""
    logger.info("⏱️  Testing Movement Timing with Enhanced Protocol")
    
    try:
        # Connect to FluidNC
        port = '/dev/ttyUSB0'  # Adjust port
        ser = serial.Serial(port, 115200, timeout=0.1)
        
        # Create communicator
        comm = FluidNCCommunicator(ser)
        await comm.start()
        
        # Get initial position
        initial_status = await comm.get_status()
        logger.info(f"📍 Initial: {comm.current_position}")
        
        # Test small relative movement with timing
        logger.info("🎯 Testing relative movement timing...")
        
        start_time = time.time()
        
        # Send relative movement
        await comm.send_gcode('G91')  # Relative mode
        success = await comm.send_gcode('G1 Z1.0 F100')  # Small rotation
        await comm.send_gcode('G90')  # Absolute mode
        
        if success:
            # Wait for completion (monitor status changes)
            while comm.current_status.name in ['MOVING', 'RUN']:
                await asyncio.sleep(0.05)  # 50ms polling
            
            completion_time = time.time() - start_time
            logger.info(f"✅ Movement completed in {completion_time:.3f}s")
            
            # Get final position
            await asyncio.sleep(0.2)  # Wait for position update
            logger.info(f"📍 Final: {comm.current_position}")
        
        await comm.stop()
        
    except Exception as e:
        logger.error(f"❌ Movement timing test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all protocol tests"""
    logger.info("🚀 FluidNC Protocol Test Suite")
    logger.info("=" * 50)
    
    tests = [
        ("Basic Protocol", test_protocol_basic),
        ("High-Level Communicator", test_communicator), 
        ("Movement Timing", test_movement_timing)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n🔬 Running: {test_name}")
        logger.info("-" * 30)
        
        try:
            await test_func()
            logger.info(f"✅ {test_name}: PASSED")
        except Exception as e:
            logger.error(f"❌ {test_name}: FAILED - {e}")
        
        logger.info("-" * 30)
        await asyncio.sleep(1.0)  # Pause between tests
    
    logger.info("\n🏁 Protocol test suite complete")


if __name__ == "__main__":
    # Run the test suite
    asyncio.run(main())