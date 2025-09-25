"""
Protocol Integration Test - Enhanced FluidNC System with Web Interface

Tests the enhanced protocol bridge for seamless integration with existing
web interface without requiring code changes.

Author: Scanner System Development
Created: December 2024
"""

import asyncio
import logging
import time
from motion.protocol_bridge import ProtocolBridgeController
from motion.enhanced_fluidnc_controller import EnhancedFluidNCController
from motion.base import Position4D

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_web_interface_compatibility():
    """Test compatibility with existing web interface API"""
    logger.info("🌐 Testing Web Interface Compatibility")
    
    try:
        # Create controller with existing config format
        config = {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 2.0
        }
        
        controller = ProtocolBridgeController(config)
        
        # Test initialization (existing API)
        logger.info("🔧 Testing initialization...")
        success = await controller.initialize(auto_unlock=True)
        logger.info(f"📊 Initialize: {'✅ Success' if success else '❌ Failed'}")
        
        if not success:
            return False
        
        # Test connection status (existing API)
        connected = controller.is_connected()
        logger.info(f"🔗 Connection Status: {'✅ Connected' if connected else '❌ Disconnected'}")
        
        # Test position query (existing API)
        position = await controller.get_current_position()
        logger.info(f"📍 Current Position: {position}")
        
        # Test small movement (existing API)
        logger.info("🎯 Testing movement with existing API...")
        start_time = time.time()
        
        # Small relative movement
        delta = Position4D(x=0, y=0, z=1.0, c=0)
        success = await controller.move_relative(delta, feedrate=100)
        
        if success:
            movement_time = time.time() - start_time
            final_position = await controller.get_current_position()
            
            logger.info(f"✅ Movement completed in {movement_time:.3f}s")
            logger.info(f"📍 Final Position: {final_position}")
        else:
            logger.error("❌ Movement failed")
        
        # Test statistics
        stats = controller.get_protocol_stats()
        logger.info(f"📊 Protocol Stats: {stats}")
        
        # Test monitor status (existing API compatibility)
        monitor_status = controller.check_background_monitor_status()
        logger.info(f"📡 Monitor Status: {monitor_status}")
        
        # Shutdown (existing API)
        await controller.shutdown()
        logger.info("✅ Web interface compatibility test complete")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_jog_commands():
    """Test jog commands like web interface uses"""
    logger.info("🕹️  Testing Jog Commands (Web Interface Style)")
    
    try:
        config = {'port': '/dev/ttyUSB0', 'baudrate': 115200}
        controller = ProtocolBridgeController(config)
        
        await controller.initialize()
        
        # Test jog commands in different directions (like web UI buttons)
        jog_tests = [
            ("X+", Position4D(x=1.0, y=0, z=0, c=0)),
            ("Y+", Position4D(x=0, y=1.0, z=0, c=0)),
            ("Z+", Position4D(x=0, y=0, z=5.0, c=0)),
            ("C+", Position4D(x=0, y=0, z=0, c=1.0))
        ]
        
        logger.info("🎮 Testing jog movements...")
        
        for direction, delta in jog_tests:
            logger.info(f"🎯 Jog {direction}: {delta}")
            
            start_time = time.time()
            success = await controller.move_relative(delta, feedrate=50)  # Slow jog speed
            jog_time = time.time() - start_time
            
            if success:
                position = await controller.get_current_position()
                logger.info(f"✅ {direction} jog: {jog_time:.3f}s, Position: {position}")
            else:
                logger.error(f"❌ {direction} jog failed")
            
            await asyncio.sleep(0.5)  # Pause between jogs
        
        await controller.shutdown()
        logger.info("✅ Jog command test complete")
        
    except Exception as e:
        logger.error(f"❌ Jog test failed: {e}")


async def test_web_api_simulation():
    """Simulate web API calls"""
    logger.info("🌐 Testing Web API Call Simulation")
    
    try:
        config = {'port': '/dev/ttyUSB0', 'baudrate': 115200}
        controller = ProtocolBridgeController(config)
        
        await controller.initialize()
        
        # Simulate rapid API status calls (like web UI polling)
        logger.info("📊 Simulating rapid status queries...")
        
        status_times = []
        for i in range(10):
            start_time = time.time()
            
            # Get status (like /api/status endpoint)
            position = await controller.get_current_position()
            connected = controller.is_connected()
            status = controller.status
            
            query_time = time.time() - start_time
            status_times.append(query_time)
            
            logger.info(f"📊 Status Query {i+1}: {query_time:.3f}s - {status.name} @ {position}")
            
            await asyncio.sleep(0.1)  # 100ms between queries
        
        avg_status_time = sum(status_times) / len(status_times)
        logger.info(f"📈 Average status query time: {avg_status_time:.3f}s")
        
        # Simulate movement command (like /api/jog endpoint)
        logger.info("🎯 Simulating jog API call...")
        
        jog_start = time.time()
        delta = Position4D(x=0, y=0, z=2.0, c=0)
        success = await controller.move_relative(delta, feedrate=100)
        jog_total_time = time.time() - jog_start
        
        logger.info(f"🎮 Jog API call: {jog_total_time:.3f}s total")
        
        await controller.shutdown()
        logger.info("✅ Web API simulation complete")
        
    except Exception as e:
        logger.error(f"❌ Web API simulation failed: {e}")


async def main():
    """Run integration tests"""
    logger.info("🚀 Enhanced Protocol Integration Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Web Interface Compatibility", test_web_interface_compatibility),
        ("Jog Commands", test_jog_commands),
        ("Web API Simulation", test_web_api_simulation)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"\n🧪 Running: {test_name}")
        logger.info("-" * 40)
        
        try:
            result = await test_func()
            results.append((test_name, result))
            logger.info(f"{'✅ PASSED' if result else '❌ FAILED'}: {test_name}")
        except Exception as e:
            logger.error(f"❌ FAILED: {test_name} - {e}")
            results.append((test_name, False))
        
        logger.info("-" * 40)
        await asyncio.sleep(1.0)
    
    # Summary
    logger.info(f"\n📋 Integration Test Results:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"  {status}: {test_name}")
    
    logger.info(f"\n🏁 Integration Tests: {passed}/{total} passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Ready for production integration.")
        logger.info("📝 Next steps:")
        logger.info("  1. Update main.py to use ProtocolBridgeController")
        logger.info("  2. Test with existing web interface")
        logger.info("  3. Monitor performance improvements")
    else:
        logger.warning("⚠️  Some tests failed - check configuration and hardware")


if __name__ == "__main__":
    asyncio.run(main())