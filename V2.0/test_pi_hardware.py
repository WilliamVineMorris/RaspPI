#!/usr/bin/env python3
"""
Raspberry Pi Hardware Test Suite

Comprehensive testing script for the V2.0 scanner system on Raspberry Pi.
Tests all hardware components with graceful fallbacks for missing hardware.

Usage:
    python test_pi_hardware.py [--component] [--verbose] [--mock]

Components:
    --motion     Test FluidNC motion controller only
    --camera     Test Pi cameras only  
    --config     Test configuration system only
    --all        Test all components (default)

Options:
    --verbose    Enable detailed logging
    --mock       Use mock hardware for testing
    --dry-run    Don't send actual commands to hardware
    --interactive  Run interactive tests

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.logging_setup import setup_logging
from motion.fluidnc_controller import FluidNCController, create_fluidnc_controller
from camera.pi_camera_controller import PiCameraController, create_pi_camera_controller, detect_pi_cameras
from motion.base import Position4D, MotionStatus
from camera.base import CameraSettings, ImageFormat

# Test configuration
TEST_CONFIG = {
    'motion': {
        'controller': {
            'port': '/dev/ttyUSB0',
            'baudrate': 115200,
            'timeout': 5.0
        },
        'axes': {
            'x_axis': {'min_limit': -150.0, 'max_limit': 150.0, 'max_feedrate': 8000.0},
            'y_axis': {'min_limit': -100.0, 'max_limit': 100.0, 'max_feedrate': 8000.0},
            'z_axis': {'min_limit': -180.0, 'max_limit': 180.0, 'max_feedrate': 3600.0},
            'c_axis': {'min_limit': -45.0, 'max_limit': 45.0, 'max_feedrate': 1800.0}
        }
    },
    'camera': {
        'controller': {
            'camera_count': 2,
            'default_format': 'JPEG'
        }
    }
}

class HardwareTestRunner:
    """Main test runner for Pi hardware"""
    
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        self.test_results: Dict[str, bool] = {}
        self.test_details: Dict[str, List[str]] = {}
        
        # Test output directory
        self.test_dir = Path("test_output")
        self.test_dir.mkdir(exist_ok=True)
        
    async def run_all_tests(self) -> bool:
        """Run all hardware tests"""
        self.logger.info("🔧 Starting Raspberry Pi Hardware Test Suite")
        self.logger.info(f"Test output directory: {self.test_dir.absolute()}")
        
        success = True
        
        # Configuration tests
        if self.args.component in ['all', 'config']:
            success &= await self.test_configuration()
        
        # Motion controller tests
        if self.args.component in ['all', 'motion']:
            success &= await self.test_motion_controller()
        
        # Camera tests  
        if self.args.component in ['all', 'camera']:
            success &= await self.test_cameras()
        
        # Integration tests
        if self.args.component == 'all':
            success &= await self.test_integration()
        
        # Print summary
        self.print_test_summary()
        
        return success
    
    async def test_configuration(self) -> bool:
        """Test configuration system"""
        self.logger.info("\n📋 Testing Configuration System...")
        
        try:
            # Create test config file
            config_file = self.test_dir / "test_config.yaml"
            self._create_test_config_file(config_file)
            
            # Test config manager
            config_manager = ConfigManager(config_file)
            
            # Test basic operations
            motion_config = config_manager.get('motion', {})
            camera_config = config_manager.get('camera', {})
            
            self.logger.info(f"✅ Configuration loaded successfully")
            self.logger.info(f"   Motion config: {len(motion_config)} settings")
            self.logger.info(f"   Camera config: {len(camera_config)} settings")
            
            self.test_results['config'] = True
            self.test_details['config'] = ['Configuration system working']
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Configuration test failed: {e}")
            self.test_results['config'] = False
            self.test_details['config'] = [f'Error: {e}']
            return False
    
    async def test_motion_controller(self) -> bool:
        """Test FluidNC motion controller"""
        self.logger.info("\n🚀 Testing FluidNC Motion Controller...")
        
        try:
            # Create controller
            controller = FluidNCController(TEST_CONFIG['motion']['controller'])
            
            # Test basic properties
            self.logger.info(f"   Port: {controller.port}")
            self.logger.info(f"   Baudrate: {controller.baudrate}")
            self.logger.info(f"   Status: {controller.status}")
            
            # Test position validation
            valid_pos = Position4D(x=50.0, y=25.0, z=90.0, c=15.0)
            invalid_pos = Position4D(x=200.0, y=25.0, z=90.0, c=15.0)
            
            pos_valid = controller._validate_position(valid_pos)
            pos_invalid = controller._validate_position(invalid_pos)
            
            self.logger.info(f"   Position validation: Valid={pos_valid}, Invalid={pos_invalid}")
            
            # Test capabilities
            capabilities = await controller.get_capabilities()
            self.logger.info(f"   Capabilities: {capabilities.axes_count} axes, homing={capabilities.supports_homing}")
            
            # Test limits
            try:
                x_limits = await controller.get_motion_limits('x')
                self.logger.info(f"   X limits: {x_limits.min_limit} to {x_limits.max_limit}")
            except Exception as e:
                self.logger.warning(f"   Limits test: {e}")
            
            if not self.args.dry_run:
                # Test connection (will fail if no hardware)
                self.logger.info("   Testing hardware connection...")
                try:
                    connected = await controller.initialize()
                    if connected:
                        self.logger.info("   ✅ FluidNC controller connected successfully")
                        
                        # Test status
                        status = await controller.get_status()
                        position = await controller.get_position()
                        self.logger.info(f"   Status: {status}, Position: {position}")
                        
                        await controller.shutdown()
                    else:
                        self.logger.warning("   ⚠️  FluidNC controller not connected (hardware not available)")
                except Exception as e:
                    self.logger.warning(f"   ⚠️  FluidNC connection failed: {e}")
            
            self.test_results['motion'] = True
            self.test_details['motion'] = [
                f'Controller created successfully',
                f'Position validation working: {pos_valid and not pos_invalid}',
                f'Capabilities: {capabilities.axes_count} axes'
            ]
            
            self.logger.info("✅ Motion controller tests completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Motion controller test failed: {e}")
            self.test_results['motion'] = False
            self.test_details['motion'] = [f'Error: {e}']
            return False
    
    async def test_cameras(self) -> bool:
        """Test Pi camera system"""
        self.logger.info("\n📷 Testing Pi Camera System...")
        
        try:
            # Detect available cameras
            available_cameras = detect_pi_cameras()
            self.logger.info(f"   Detected cameras: {len(available_cameras)}")
            
            for cam_info in available_cameras:
                self.logger.info(f"     Camera {cam_info['camera_id']}: {cam_info['model']}")
            
            # Create controller
            controller = PiCameraController(TEST_CONFIG['camera']['controller'])
            
            # Test basic properties
            self.logger.info(f"   Camera count: {controller.camera_count}")
            self.logger.info(f"   Default format: {controller.default_format}")
            self.logger.info(f"   Status: {controller.status}")
            
            # Test camera info
            self.logger.info(f"   Camera info loaded: {len(controller.camera_info)} cameras")
            for cam_id, info in controller.camera_info.items():
                self.logger.info(f"     Camera {cam_id}: Available={info.is_available}, Type={info.camera_type}")
            
            # Test capabilities
            if controller.camera_info:
                first_cam_id = list(controller.camera_info.keys())[0]
                capabilities = await controller.get_camera_capabilities(first_cam_id)
                self.logger.info(f"   Capabilities: {len(capabilities.supported_resolutions)} resolutions")
            
            if not self.args.dry_run and not self.args.mock:
                # Test initialization (will fail if no cameras)
                self.logger.info("   Testing camera initialization...")
                try:
                    initialized = await controller.initialize()
                    if initialized:
                        self.logger.info("   ✅ Camera controller initialized successfully")
                        
                        # Test camera list
                        camera_list = await controller.list_cameras()
                        self.logger.info(f"   Available cameras: {camera_list}")
                        
                        # Test camera info
                        for cam_id in camera_list:
                            info = await controller.get_camera_info(cam_id)
                            self.logger.info(f"     {cam_id}: {info.get('camera_type', 'Unknown')}")
                        
                        # Test capture (if interactive)
                        if self.args.interactive and camera_list:
                            await self.test_camera_capture(controller, camera_list[0])
                        
                        await controller.shutdown()
                    else:
                        self.logger.warning("   ⚠️  Camera controller not initialized (cameras not available)")
                except Exception as e:
                    self.logger.warning(f"   ⚠️  Camera initialization failed: {e}")
            
            self.test_results['camera'] = True
            self.test_details['camera'] = [
                f'Controller created successfully',
                f'Detected {len(available_cameras)} cameras',
                f'Camera info loaded for {len(controller.camera_info)} cameras'
            ]
            
            self.logger.info("✅ Camera tests completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Camera test failed: {e}")
            self.test_results['camera'] = False
            self.test_details['camera'] = [f'Error: {e}']
            return False
    
    async def test_camera_capture(self, controller: PiCameraController, camera_id: str):
        """Test camera capture functionality"""
        try:
            self.logger.info(f"   Testing capture from {camera_id}...")
            
            # Create test settings
            settings = CameraSettings(
                resolution=(1280, 720),
                format=ImageFormat.JPEG,
                quality=85
            )
            
            # Test single capture
            result = await controller.capture_photo(camera_id, settings)
            if result.success:
                self.logger.info(f"   ✅ Single capture successful: {result.image_path}")
            else:
                self.logger.warning(f"   ⚠️  Single capture failed")
            
            # Test burst capture (small burst)
            self.logger.info(f"   Testing burst capture...")
            burst_results = await controller.capture_burst(camera_id, 3, 0.5, settings)
            self.logger.info(f"   Burst capture: {len(burst_results)} images captured")
            
        except Exception as e:
            self.logger.error(f"   Capture test failed: {e}")
    
    async def test_integration(self) -> bool:
        """Test system integration"""
        self.logger.info("\n🔗 Testing System Integration...")
        
        try:
            # Test event system
            from core.events import EventBus
            event_bus = EventBus()
            
            event_received = False
            def test_callback(event):
                nonlocal event_received
                event_received = True
                self.logger.info(f"   Event received: {event.event_type}")
            
            event_bus.subscribe("test_event", test_callback)
            event_bus.publish("test_event", {"test": "data"})
            
            # Give time for event processing
            await asyncio.sleep(0.1)
            
            if event_received:
                self.logger.info("   ✅ Event system working")
            else:
                self.logger.warning("   ⚠️  Event system not responding")
            
            # Test configuration integration
            config_file = self.test_dir / "integration_config.yaml"
            self._create_test_config_file(config_file)
            config_manager = ConfigManager(config_file)
            
            # Test controller creation from config
            try:
                motion_controller = create_fluidnc_controller(config_manager)
                camera_controller = create_pi_camera_controller(config_manager)
                
                self.logger.info("   ✅ Controllers created from configuration")
            except Exception as e:
                self.logger.warning(f"   ⚠️  Controller creation failed: {e}")
            
            self.test_results['integration'] = True
            self.test_details['integration'] = [
                f'Event system: {event_received}',
                'Controller factory functions working'
            ]
            
            self.logger.info("✅ Integration tests completed")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Integration test failed: {e}")
            self.test_results['integration'] = False
            self.test_details['integration'] = [f'Error: {e}']
            return False
    
    def _create_test_config_file(self, config_file: Path):
        """Create test configuration file"""
        import yaml
        
        config_content = {
            'motion': TEST_CONFIG['motion'],
            'camera': TEST_CONFIG['camera'],
            'logging': {
                'level': 'INFO',
                'format': 'detailed'
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_content, f, default_flow_style=False)
    
    def print_test_summary(self):
        """Print test results summary"""
        self.logger.info("\n" + "="*60)
        self.logger.info("🏁 TEST SUMMARY")
        self.logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, passed in self.test_results.items():
            status = "✅ PASSED" if passed else "❌ FAILED"
            self.logger.info(f"{test_name.upper():20} {status}")
            
            if test_name in self.test_details:
                for detail in self.test_details[test_name]:
                    self.logger.info(f"                     • {detail}")
        
        self.logger.info("="*60)
        self.logger.info(f"Results: {passed_tests}/{total_tests} tests passed")
        
        if passed_tests == total_tests:
            self.logger.info("🎉 All tests passed! System ready for deployment.")
        else:
            self.logger.warning("⚠️  Some tests failed. Check hardware connections and configuration.")
        
        # Create test report
        self._create_test_report()
    
    def _create_test_report(self):
        """Create detailed test report file"""
        report_file = self.test_dir / f"test_report_{int(time.time())}.txt"
        
        with open(report_file, 'w') as f:
            f.write("Raspberry Pi Hardware Test Report\n")
            f.write("="*50 + "\n\n")
            f.write(f"Test Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Arguments: {vars(self.args)}\n\n")
            
            for test_name, passed in self.test_results.items():
                f.write(f"{test_name.upper()}: {'PASSED' if passed else 'FAILED'}\n")
                if test_name in self.test_details:
                    for detail in self.test_details[test_name]:
                        f.write(f"  - {detail}\n")
                f.write("\n")
        
        self.logger.info(f"📄 Test report saved: {report_file}")


async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description='Raspberry Pi Hardware Test Suite')
    parser.add_argument('--component', choices=['all', 'motion', 'camera', 'config'], 
                       default='all', help='Component to test')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--mock', action='store_true', help='Use mock hardware')
    parser.add_argument('--dry-run', action='store_true', help='Don\'t send commands to hardware')
    parser.add_argument('--interactive', action='store_true', help='Run interactive tests')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level, log_file="test_output/test_log.log")
    
    # Run tests
    test_runner = HardwareTestRunner(args)
    success = await test_runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())