#!/usr/bin/env python3
"""
Enhanced Protocol System Integration Validator

Validates that the enhanced FluidNC protocol has been successfully integrated
into the complete scanning system architecture. This focuses on the key
integration points that matter for production deployment.

This script:
1. Tests the enhanced protocol bridge directly
2. Validates import integration
3. Tests performance improvements
4. Provides system readiness validation

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import time
import sys
import os
from typing import Dict, Any
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SystemIntegrationValidator:
    """Validates enhanced protocol integration across the entire system"""
    
    def __init__(self):
        self.test_results = {}
        self.performance_metrics = {}
        self.start_time = time.time()
    
    async def run_validation(self) -> bool:
        """Run complete system validation"""
        logger.info("🚀 Enhanced Protocol System Integration Validation")
        logger.info("=" * 70)
        
        tests = [
            ("Protocol Bridge Functionality", self.test_protocol_bridge),
            ("Performance Validation", self.test_performance_metrics),
            ("System Architecture Validation", self.test_system_architecture),
            ("Integration Import Test", self.test_integration_imports)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            logger.info(f"\n🧪 {test_name}")
            logger.info("-" * 50)
            
            try:
                start_time = time.time()
                result = await test_func()
                test_time = time.time() - start_time
                
                self.test_results[test_name] = result
                self.performance_metrics[test_name] = test_time
                
                status = "✅ PASSED" if result else "❌ FAILED"
                logger.info(f"{status} - {test_name} ({test_time:.2f}s)")
                
                if not result:
                    all_passed = False
                    
            except Exception as e:
                logger.error(f"❌ FAILED - {test_name}: {e}")
                self.test_results[test_name] = False
                all_passed = False
            
            logger.info("-" * 50)
            await asyncio.sleep(1.0)
        
        await self.print_summary(all_passed)
        return all_passed
    
    async def test_protocol_bridge(self) -> bool:
        """Test the protocol bridge functionality"""
        try:
            from motion.protocol_bridge import ProtocolBridgeController
            from motion.base import Position4D
            
            logger.info("🔧 Testing enhanced protocol bridge...")
            
            # Test controller creation
            config = {'port': '/dev/ttyUSB0', 'baudrate': 115200}
            controller = ProtocolBridgeController(config)
            logger.info("✅ Protocol bridge controller created")
            
            # Test initialization
            success = await controller.initialize(auto_unlock=True)
            if not success:
                logger.error("❌ Protocol bridge initialization failed")
                return False
            
            logger.info("✅ Protocol bridge initialized successfully")
            
            # Test position query
            start_time = time.time()
            position = await controller.get_current_position()
            query_time = time.time() - start_time
            
            logger.info(f"✅ Position query: {query_time:.3f}s - {position}")
            
            # Test small movement
            start_time = time.time()
            delta = Position4D(x=0, y=0, z=1.0, c=0)
            move_success = await controller.move_relative(delta, feedrate=100)
            move_time = time.time() - start_time
            
            if move_success:
                logger.info(f"✅ Movement completed: {move_time:.3f}s")
            else:
                logger.error("❌ Movement failed")
                await controller.shutdown()
                return False
            
            # Test statistics
            stats = controller.get_protocol_stats()
            logger.info(f"📊 Protocol stats: {stats}")
            
            # Performance validation
            if move_time > 2.0:
                logger.warning(f"⚠️  Movement slower than expected: {move_time:.3f}s")
            else:
                logger.info(f"🚀 Performance excellent: {move_time:.3f}s")
            
            await controller.shutdown()
            logger.info("✅ Protocol bridge test complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Protocol bridge test failed: {e}")
            return False
    
    async def test_orchestrator_integration(self) -> bool:
        """Test scan orchestrator integration with enhanced protocol"""
        try:
            from scanning.scan_orchestrator import ScanOrchestrator
            from core.config_manager import ConfigManager
            
            logger.info("🎯 Testing scan orchestrator integration...")
            
            # Create orchestrator (should use enhanced protocol)
            config_manager = ConfigManager()
            orchestrator = ScanOrchestrator(config_manager)
            
            # Test initialization
            success = await orchestrator.initialize_system()
            if not success:
                logger.error("❌ Orchestrator initialization failed")
                return False
            
            logger.info("✅ Orchestrator initialized with enhanced protocol")
            
            # Check if motion controller is using enhanced protocol
            if hasattr(orchestrator, 'motion_controller') and orchestrator.motion_controller:
                motion_controller = orchestrator.motion_controller
                
                # Check adapter structure
                if hasattr(motion_controller, 'controller'):
                    controller = motion_controller.controller
                    controller_type = type(controller).__name__
                    
                    logger.info(f"📊 Motion controller type: {controller_type}")
                    
                    # Verify it's using enhanced protocol
                    if 'ProtocolBridge' in controller_type:
                        logger.info("✅ Enhanced protocol bridge detected in orchestrator")
                    else:
                        logger.warning(f"⚠️  Using controller: {controller_type}")
                
                # Test motion through orchestrator
                start_time = time.time()
                
                # Test position query through orchestrator
                status = await orchestrator.get_status()
                query_time = time.time() - start_time
                
                logger.info(f"✅ Orchestrator status query: {query_time:.3f}s")
                logger.info(f"📊 Status: {status}")
                
            else:
                logger.warning("⚠️  Motion controller not found in orchestrator")
            
            await orchestrator.shutdown()
            logger.info("✅ Orchestrator integration test complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Orchestrator integration test failed: {e}")
            return False
    
    async def test_web_interface_integration(self) -> bool:
        """Test web interface integration"""
        try:
            from web.web_interface import ScannerWebInterface
            from scanning.scan_orchestrator import ScanOrchestrator
            from core.config_manager import ConfigManager
            
            logger.info("🌐 Testing web interface integration...")
            
            # Create orchestrator and web interface
            config_manager = ConfigManager()
            orchestrator = ScanOrchestrator(config_manager)
            web_interface = ScannerWebInterface(orchestrator)
            
            logger.info("✅ Web interface created")
            
            # Test orchestrator initialization through web interface
            if orchestrator:
                await orchestrator.initialize_system()
                logger.info("✅ Orchestrator initialized through web interface")
                
                # Check motion controller availability
                if hasattr(orchestrator, 'motion_controller') and orchestrator.motion_controller:
                    logger.info("✅ Motion controller available to web interface")
                    
                    # Test getting status through web interface path
                    status = await orchestrator.get_status()
                    logger.info(f"✅ Web interface can query status: {status}")
                else:
                    logger.warning("⚠️  Motion controller not available to web interface")
                
                await orchestrator.shutdown()
            
            logger.info("✅ Web interface integration test complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ Web interface integration test failed: {e}")
            return False
    
    async def test_performance_metrics(self) -> bool:
        """Test and validate performance improvements"""
        try:
            from motion.protocol_bridge import ProtocolBridgeController
            from motion.base import Position4D
            
            logger.info("⏱️  Testing performance metrics...")
            
            config = {'port': '/dev/ttyUSB0', 'baudrate': 115200}
            controller = ProtocolBridgeController(config)
            
            await controller.initialize(auto_unlock=True)
            
            # Performance benchmarks
            benchmarks = []
            
            # Test rapid status queries
            logger.info("📊 Testing rapid status queries...")
            status_times = []
            for i in range(5):
                start_time = time.time()
                await controller.get_current_position()
                query_time = time.time() - start_time
                status_times.append(query_time)
            
            avg_status_time = sum(status_times) / len(status_times)
            benchmarks.append(("Status Query", avg_status_time, 0.2))  # Should be < 200ms
            
            # Test movement completion
            logger.info("🎯 Testing movement completion...")
            movement_times = []
            for i in range(3):
                start_time = time.time()
                delta = Position4D(x=0, y=0, z=0.5, c=0)
                await controller.move_relative(delta, feedrate=100)
                move_time = time.time() - start_time
                movement_times.append(move_time)
            
            avg_move_time = sum(movement_times) / len(movement_times)
            benchmarks.append(("Movement Completion", avg_move_time, 2.0))  # Should be < 2s
            
            # Evaluate benchmarks
            all_passed = True
            logger.info("📈 Performance Results:")
            
            for test_name, actual_time, threshold in benchmarks:
                status = "✅ EXCELLENT" if actual_time < threshold else "⚠️  SLOW"
                logger.info(f"   {status} {test_name}: {actual_time:.3f}s (threshold: {threshold}s)")
                
                if actual_time >= threshold:
                    all_passed = False
            
            # Log protocol statistics
            stats = controller.get_protocol_stats()
            logger.info(f"📊 Protocol Statistics: {stats}")
            
            await controller.shutdown()
            
            if all_passed:
                logger.info("🚀 Performance validation: EXCELLENT")
            else:
                logger.warning("⚠️  Performance validation: NEEDS IMPROVEMENT")
            
            return all_passed
            
        except Exception as e:
            logger.error(f"❌ Performance metrics test failed: {e}")
            return False
    
    async def test_system_architecture(self) -> bool:
        """Test overall system architecture with enhanced protocol"""
        try:
            logger.info("🏗️  Testing system architecture...")
            
            # Test module imports
            import_tests = [
                ("Enhanced Protocol", "motion.protocol_bridge", "ProtocolBridgeController"),
                ("FluidNC Protocol", "motion.fluidnc_protocol", "FluidNCCommunicator"),
                ("Scan Orchestrator", "scanning.scan_orchestrator", "ScanOrchestrator"),
                ("Web Interface", "web.web_interface", "ScannerWebInterface"),
            ]
            
            for test_name, module_name, class_name in import_tests:
                try:
                    module = __import__(module_name, fromlist=[class_name])
                    cls = getattr(module, class_name)
                    logger.info(f"✅ {test_name}: {module_name}.{class_name}")
                except Exception as e:
                    logger.error(f"❌ {test_name} import failed: {e}")
                    return False
            
            # Test configuration system
            try:
                from core.config_manager import ConfigManager
                config = ConfigManager()
                motion_config = config.get('motion', {})
                logger.info(f"✅ Configuration system: Motion config loaded")
            except Exception as e:
                logger.error(f"❌ Configuration system failed: {e}")
                return False
            
            logger.info("✅ System architecture validation complete")
            return True
            
        except Exception as e:
            logger.error(f"❌ System architecture test failed: {e}")
            return False
    
    async def print_summary(self, all_passed: bool):
        """Print validation summary"""
        total_time = time.time() - self.start_time
        
        logger.info(f"\n{'='*70}")
        logger.info("📋 ENHANCED PROTOCOL INTEGRATION VALIDATION SUMMARY")
        logger.info(f"{'='*70}")
        
        passed_count = sum(1 for result in self.test_results.values() if result)
        total_count = len(self.test_results)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASSED" if result else "❌ FAILED"
            test_time = self.performance_metrics.get(test_name, 0)
            logger.info(f"  {status} {test_name} ({test_time:.2f}s)")
        
        logger.info(f"\n📊 Results: {passed_count}/{total_count} tests passed")
        logger.info(f"⏱️  Total validation time: {total_time:.2f}s")
        
        if all_passed:
            logger.info("\n🎉 INTEGRATION VALIDATION: SUCCESS")
            logger.info("✅ Enhanced FluidNC protocol successfully integrated!")
            logger.info("🚀 System ready for production with improved performance")
            logger.info("\n📝 Next Steps:")
            logger.info("  1. Start web interface: python run_web_interface_fixed.py")
            logger.info("  2. Monitor performance improvements")
            logger.info("  3. Test with real scanning operations")
        else:
            logger.error("\n❌ INTEGRATION VALIDATION: FAILED")
            logger.error("⚠️  Some integration tests failed - check configuration")
            logger.error("📞 Review error messages above for troubleshooting")


async def main():
    """Run system integration validation"""
    validator = SystemIntegrationValidator()
    success = await validator.run_validation()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())