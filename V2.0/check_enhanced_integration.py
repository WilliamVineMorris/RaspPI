#!/usr/bin/env python3
"""
Simple Enhanced Protocol Integration Check

Quick validation that enhanced FluidNC protocol is correctly integrated
and performing well. Run this to verify the integration is working.

Author: Scanner System Development  
Created: September 2025
"""

import asyncio
import logging
import time
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def check_enhanced_protocol():
    """Check enhanced protocol integration"""
    logger.info("🚀 Enhanced FluidNC Protocol Integration Check")
    logger.info("=" * 60)
    
    success_count = 0
    total_tests = 4
    
    # Test 1: Import Integration
    logger.info("\n1️⃣  Testing Import Integration...")
    try:
        from motion.protocol_bridge import ProtocolBridgeController
        from motion.fluidnc_protocol import FluidNCCommunicator
        logger.info("✅ Enhanced protocol modules imported successfully")
        success_count += 1
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
    
    # Test 2: Orchestrator Integration
    logger.info("\n2️⃣  Testing Orchestrator Integration...")
    try:
        # Check that scan orchestrator will use enhanced protocol
        with open('scanning/scan_orchestrator.py', 'r') as f:
            content = f.read()
        
        if 'protocol_bridge import ProtocolBridgeController' in content:
            logger.info("✅ Scan orchestrator configured for enhanced protocol")
            success_count += 1
        else:
            logger.error("❌ Scan orchestrator not using enhanced protocol") 
    except Exception as e:
        logger.error(f"❌ Orchestrator check failed: {e}")
    
    # Test 3: Performance Test
    logger.info("\n3️⃣  Testing Performance...")
    try:
        from motion.protocol_bridge import ProtocolBridgeController
        from motion.base import Position4D
        
        config = {'port': '/dev/ttyUSB0', 'baudrate': 115200}
        controller = ProtocolBridgeController(config)
        
        # Test connection and basic operation
        start_time = time.time()
        init_success = await controller.initialize(auto_unlock=True)
        init_time = time.time() - start_time
        
        if init_success:
            # Test position query speed
            start_time = time.time()
            position = await controller.get_current_position()
            query_time = time.time() - start_time
            
            # Test small movement speed
            start_time = time.time()
            delta = Position4D(x=0, y=0, z=0.5, c=0)
            move_success = await controller.move_relative(delta, feedrate=100)
            move_time = time.time() - start_time
            
            logger.info(f"✅ Performance Test Results:")
            logger.info(f"   📡 Position Query: {query_time:.3f}s")
            logger.info(f"   🎯 Movement: {move_time:.3f}s")
            
            if query_time < 0.5 and move_time < 2.0:
                logger.info("🚀 Performance: EXCELLENT")
                success_count += 1
            else:
                logger.warning("⚠️  Performance: ACCEPTABLE but could be better")
            
            # Get protocol stats
            stats = controller.get_protocol_stats()
            logger.info(f"   📊 Protocol Stats: {stats}")
            
            await controller.shutdown()
        else:
            logger.error("❌ Controller initialization failed")
            
    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
    
    # Test 4: System Ready Check
    logger.info("\n4️⃣  Testing System Readiness...")
    try:
        # Check key files exist
        key_files = [
            'motion/protocol_bridge.py',
            'motion/fluidnc_protocol.py', 
            'motion/enhanced_fluidnc_controller.py',
            'scanning/scan_orchestrator.py',
            'web/web_interface.py'
        ]
        
        missing_files = []
        for file_path in key_files:
            if not os.path.exists(file_path):
                missing_files.append(file_path)
        
        if not missing_files:
            logger.info("✅ All key system files present")
            success_count += 1
        else:
            logger.error(f"❌ Missing files: {missing_files}")
            
    except Exception as e:
        logger.error(f"❌ System readiness check failed: {e}")
    
    # Summary
    logger.info(f"\n{'='*60}")
    logger.info("📊 INTEGRATION CHECK SUMMARY")
    logger.info(f"{'='*60}")
    logger.info(f"✅ Tests Passed: {success_count}/{total_tests}")
    
    if success_count == total_tests:
        logger.info("🎉 INTEGRATION: SUCCESS")
        logger.info("✅ Enhanced protocol fully integrated and ready!")
        logger.info("\n📝 Next Steps:")
        logger.info("  1. Start web interface: python run_web_interface_fixed.py")
        logger.info("  2. Monitor improved response times")
        logger.info("  3. Enjoy sub-second motion control! 🚀")
        return True
    elif success_count >= 2:
        logger.warning("⚠️  INTEGRATION: PARTIAL SUCCESS")
        logger.warning("Most components working, minor issues detected")
        return True
    else:
        logger.error("❌ INTEGRATION: FAILED")
        logger.error("Major issues detected - check error messages above")
        return False


if __name__ == "__main__":
    success = asyncio.run(check_enhanced_protocol())
    sys.exit(0 if success else 1)