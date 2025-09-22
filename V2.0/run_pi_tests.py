#!/usr/bin/env python3
"""
Pi Hardware Test Runner

Master test script to run all hardware validation tests on Raspberry Pi.
This script runs all component tests and provides a comprehensive report.

Usage:
    python run_pi_tests.py [options]

Options:
    --motion-port PORT     Serial port for FluidNC (default: /dev/ttyUSB0)
    --motion-baud BAUD     Serial baudrate (default: 115200)
    --skip-motion          Skip motion controller tests
    --skip-camera          Skip camera tests
    --no-capture           Skip actual camera capture tests
    --interactive          Run interactive motion tests
    --verbose              Verbose logging
    --quick                Run only basic tests (no hardware interaction)

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.logging_setup import setup_logging

class PiTestRunner:
    """Comprehensive Pi hardware test runner"""
    
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        self.test_results: Dict[str, bool] = {}
        self.test_times: Dict[str, float] = {}
        self.start_time = time.time()
        
    def log_test_start(self, test_name: str):
        """Log test start and record time"""
        self.logger.info(f"\n{'='*60}")
        self.logger.info(f"🧪 Starting {test_name}")
        self.logger.info(f"{'='*60}")
        self.test_times[test_name] = time.time()
    
    def log_test_end(self, test_name: str, success: bool):
        """Log test end and record result"""
        elapsed = time.time() - self.test_times[test_name]
        status = "✅ PASSED" if success else "❌ FAILED"
        self.logger.info(f"\n{'-'*60}")
        self.logger.info(f"{status} {test_name} ({elapsed:.2f}s)")
        self.logger.info(f"{'-'*60}")
        self.test_results[test_name] = success
    
    async def run_motion_tests(self) -> bool:
        """Run motion controller tests"""
        if self.args.skip_motion:
            self.logger.info("⏭️  Skipping motion controller tests")
            return True
        
        self.log_test_start("Motion Controller Tests")
        
        try:
            # Import here to avoid issues if motion module has problems
            from test_motion_only import MotionControllerTester
            
            tester = MotionControllerTester(
                self.args.motion_port, 
                self.args.motion_baud, 
                self.args.interactive
            )
            
            success = await tester.run_tests()
            self.log_test_end("Motion Controller Tests", success)
            return success
            
        except Exception as e:
            self.logger.error(f"Motion controller test crashed: {e}")
            self.log_test_end("Motion Controller Tests", False)
            return False
    
    async def run_camera_tests(self) -> bool:
        """Run camera tests"""
        if self.args.skip_camera:
            self.logger.info("⏭️  Skipping camera tests")
            return True
        
        self.log_test_start("Camera Tests")
        
        try:
            # Import here to avoid issues if camera module has problems
            from test_camera_simple import SimpleCameraTest
            
            tester = SimpleCameraTest(self.args.no_capture)
            success = await tester.run_tests()
            self.log_test_end("Camera Tests", success)
            return success
            
        except Exception as e:
            self.logger.error(f"Camera test crashed: {e}")
            self.log_test_end("Camera Tests", False)
            return False
    
    async def run_core_tests(self) -> bool:
        """Run core system tests"""
        self.log_test_start("Core System Tests")
        
        try:
            success = True
            
            # Test core imports
            self.logger.info("📋 Testing core module imports...")
            try:
                from core.exceptions import ScannerError, MotionError, CameraError
                from core.events import EventBus
                from core.config_manager import ConfigManager
                from core.logging_setup import setup_logging
                self.logger.info("   ✅ Core modules imported successfully")
            except Exception as e:
                self.logger.error(f"   ❌ Core module import failed: {e}")
                success = False
            
            # Test motion imports
            self.logger.info("📋 Testing motion module imports...")
            try:
                from motion.base import MotionController, Position4D, MotionLimits
                from motion.fluidnc_controller import FluidNCController
                self.logger.info("   ✅ Motion modules imported successfully")
            except Exception as e:
                self.logger.error(f"   ❌ Motion module import failed: {e}")
                success = False
            
            # Test camera imports
            self.logger.info("📋 Testing camera module imports...")
            try:
                from camera.base import CameraController, CameraSettings
                from camera.pi_camera_controller import PiCameraController
                self.logger.info("   ✅ Camera modules imported successfully")
            except Exception as e:
                self.logger.error(f"   ❌ Camera module import failed: {e}")
                success = False
            
            # Test configuration loading
            self.logger.info("📋 Testing configuration system...")
            try:
                from core.config_manager import ConfigManager
                import tempfile
                import yaml
                
                # Create temporary config file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                    yaml.dump({'test': True, 'system': {'name': 'test'}}, f)
                    temp_config = f.name
                
                config_manager = ConfigManager(temp_config)
                test_value = config_manager.get('test', False)
                
                # Clean up
                import os
                os.unlink(temp_config)
                
                self.logger.info("   ✅ Configuration system working")
            except Exception as e:
                self.logger.error(f"   ❌ Configuration system failed: {e}")
                success = False
            
            # Test event system
            self.logger.info("📋 Testing event system...")
            try:
                from core.events import EventBus, ScannerEvent
                event_bus = EventBus()
                test_event = ScannerEvent("test", {"data": "test"})
                # Don't actually send event, just test creation
                self.logger.info("   ✅ Event system working")
            except Exception as e:
                self.logger.error(f"   ❌ Event system failed: {e}")
                success = False
            
            self.log_test_end("Core System Tests", success)
            return success
            
        except Exception as e:
            self.logger.error(f"Core system test crashed: {e}")
            self.log_test_end("Core System Tests", False)
            return False
    
    def generate_report(self):
        """Generate comprehensive test report"""
        total_time = time.time() - self.start_time
        
        print("\n" + "="*80)
        print("🔍 PI HARDWARE TEST REPORT")
        print("="*80)
        
        # Summary
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        failed_tests = total_tests - passed_tests
        
        print(f"\n📊 SUMMARY:")
        print(f"   Total Tests: {total_tests}")
        print(f"   Passed: {passed_tests} ✅")
        print(f"   Failed: {failed_tests} ❌")
        print(f"   Success Rate: {(passed_tests/total_tests*100):.1f}%")
        print(f"   Total Time: {total_time:.2f}s")
        
        # Detailed results
        print(f"\n📋 DETAILED RESULTS:")
        for test_name, result in self.test_results.items():
            status = "PASSED ✅" if result else "FAILED ❌"
            time_taken = self.test_times.get(test_name, 0)
            elapsed = time.time() - time_taken if time_taken > 0 else 0
            print(f"   {test_name}: {status} ({elapsed:.2f}s)")
        
        # Recommendations
        print(f"\n💡 RECOMMENDATIONS:")
        
        if failed_tests == 0:
            print("   🎉 All tests passed! Your Pi hardware setup is working correctly.")
            print("   Ready to proceed with next development phase.")
        else:
            print("   ⚠️  Some tests failed. Review the issues above:")
            
            for test_name, result in self.test_results.items():
                if not result:
                    if "Motion" in test_name:
                        print("     • Motion Controller: Check FluidNC connection and USB cable")
                        print("     • Verify FluidNC is powered and configured correctly")
                        print(f"     • Check if {self.args.motion_port} is the correct serial port")
                    elif "Camera" in test_name:
                        print("     • Camera: Check Pi camera connections (ribbon cables)")
                        print("     • Verify camera modules are enabled: 'sudo raspi-config'")
                        print("     • Check picamera2 installation: 'pip install picamera2'")
                    elif "Core" in test_name:
                        print("     • Core System: Check Python dependencies and imports")
                        print("     • Verify all modules are in correct locations")
        
        print("\n" + "="*80)
        
        return failed_tests == 0
    
    async def run_all_tests(self) -> bool:
        """Run all tests"""
        self.logger.info("🚀 Starting Pi Hardware Test Suite")
        self.logger.info(f"Test configuration:")
        self.logger.info(f"  Motion port: {self.args.motion_port}")
        self.logger.info(f"  Motion baud: {self.args.motion_baud}")
        self.logger.info(f"  Skip motion: {self.args.skip_motion}")
        self.logger.info(f"  Skip camera: {self.args.skip_camera}")
        self.logger.info(f"  No capture: {self.args.no_capture}")
        self.logger.info(f"  Interactive: {self.args.interactive}")
        self.logger.info(f"  Quick mode: {self.args.quick}")
        
        # Run tests in order
        success = True
        
        # Always run core tests first
        success &= await self.run_core_tests()
        
        if not self.args.quick:
            # Run hardware tests if not in quick mode
            success &= await self.run_motion_tests()
            success &= await self.run_camera_tests()
        
        # Generate report
        overall_success = self.generate_report()
        
        return overall_success


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Pi Hardware Test Runner')
    
    # Motion controller options
    parser.add_argument('--motion-port', default='/dev/ttyUSB0', 
                       help='Serial port for FluidNC (default: /dev/ttyUSB0)')
    parser.add_argument('--motion-baud', type=int, default=115200, 
                       help='Serial baudrate (default: 115200)')
    parser.add_argument('--skip-motion', action='store_true', 
                       help='Skip motion controller tests')
    parser.add_argument('--interactive', action='store_true', 
                       help='Run interactive motion tests')
    
    # Camera options
    parser.add_argument('--skip-camera', action='store_true', 
                       help='Skip camera tests')
    parser.add_argument('--no-capture', action='store_true', 
                       help='Skip actual camera capture tests')
    
    # General options
    parser.add_argument('--quick', action='store_true', 
                       help='Run only basic tests (no hardware interaction)')
    parser.add_argument('--verbose', action='store_true', 
                       help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging()
    logging.getLogger().setLevel(log_level)
    
    # Run tests
    runner = PiTestRunner(args)
    success = await runner.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())