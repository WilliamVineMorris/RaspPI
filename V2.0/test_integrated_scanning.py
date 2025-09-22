#!/usr/bin/env python3
"""
Integrated Scanning System Test Suite

Comprehensive test for the hardware-integrated scanning system.
Tests the full scan orchestrator with real FluidNC motion controller
and Pi camera controllers to validate end-to-end functionality.

Usage:
    python test_integrated_scanning.py [options]

Options:
    --motion-port PORT     Serial port for FluidNC (default: /dev/ttyUSB0)
    --simulation           Run in simulation mode (use mock hardware)
    --quick               Run quick test with minimal points
    --verbose             Enable verbose logging
    --output-dir DIR      Output directory for scan results

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import argparse
import logging
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.logging_setup import setup_logging
from scanning import ScanOrchestrator


class IntegratedScanningTestRunner:
    """Test runner for integrated scanning system"""
    
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        self.test_results = {}
        
    async def run_all_tests(self) -> bool:
        """Run all integrated scanning tests"""
        self.logger.info("🚀 Starting Integrated Scanning System Tests")
        self.logger.info(f"Test configuration:")
        self.logger.info(f"  Simulation mode: {self.args.simulation}")
        self.logger.info(f"  Motion port: {self.args.motion_port}")
        self.logger.info(f"  Quick mode: {self.args.quick}")
        self.logger.info(f"  Output dir: {self.args.output_dir}")
        
        success = True
        
        # Test 1: System Initialization
        success &= await self.test_system_initialization()
        
        # Test 2: Hardware Connectivity
        if not self.args.simulation:
            success &= await self.test_hardware_connectivity()
        
        # Test 3: Scan Pattern Generation
        success &= await self.test_scan_pattern_generation()
        
        # Test 4: Mock Scan Execution (always safe)
        success &= await self.test_mock_scan_execution()
        
        # Test 5: Hardware Scan Execution (if not simulation)
        if not self.args.simulation:
            success &= await self.test_hardware_scan_execution()
        
        # Test 6: Error Recovery
        success &= await self.test_error_recovery()
        
        self._print_final_results(success)
        return success
    
    async def test_system_initialization(self) -> bool:
        """Test system initialization with hardware integration"""
        self.logger.info("🔧 Testing System Initialization...")
        
        try:
            # Create test configuration
            config_file = self._create_test_config()
            
            # Initialize system
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            # Test initialization
            init_success = await orchestrator.initialize()
            
            if init_success:
                self.logger.info("✅ System initialization successful")
                self.test_results['initialization'] = True
                
                # Check component status
                motion_connected = orchestrator.motion_controller.is_connected()
                camera_ready = await orchestrator.camera_manager.check_camera_health()
                
                self.logger.info(f"   Motion controller connected: {motion_connected}")
                self.logger.info(f"   Camera system ready: {camera_ready}")
                
                # Cleanup
                await orchestrator.shutdown()
                return True
            else:
                self.logger.error("❌ System initialization failed")
                self.test_results['initialization'] = False
                return False
                
        except Exception as e:
            self.logger.error(f"❌ System initialization error: {e}")
            self.test_results['initialization'] = False
            return False
        finally:
            # Cleanup config file
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def test_hardware_connectivity(self) -> bool:
        """Test hardware connectivity (motion + cameras)"""
        self.logger.info("🔌 Testing Hardware Connectivity...")
        
        try:
            config_file = self._create_test_config(simulation=False)
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            # Initialize with real hardware
            init_success = await orchestrator.initialize()
            
            if not init_success:
                self.logger.warning("⚠️  Hardware initialization failed - may be expected if hardware not connected")
                self.test_results['hardware_connectivity'] = False
                return False
            
            # Test motion controller
            motion_connected = orchestrator.motion_controller.is_connected()
            self.logger.info(f"   Motion controller: {'✅ Connected' if motion_connected else '❌ Not connected'}")
            
            # Test camera system
            camera_health = await orchestrator.camera_manager.check_camera_health()
            self.logger.info(f"   Camera system: {'✅ Ready' if camera_health else '❌ Not ready'}")
            
            # Cleanup
            await orchestrator.shutdown()
            
            success = motion_connected and camera_health
            self.test_results['hardware_connectivity'] = success
            
            if success:
                self.logger.info("✅ Hardware connectivity test passed")
            else:
                self.logger.warning("⚠️  Hardware connectivity test failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Hardware connectivity test error: {e}")
            self.test_results['hardware_connectivity'] = False
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def test_scan_pattern_generation(self) -> bool:
        """Test scan pattern generation"""
        self.logger.info("📐 Testing Scan Pattern Generation...")
        
        try:
            config_file = self._create_test_config()
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            await orchestrator.initialize()
            
            # Test cylindrical pattern
            cylindrical_pattern = orchestrator.create_cylindrical_pattern(
                x_range=(-10.0, 10.0),
                y_range=(20.0, 40.0),
                z_rotations=[0.0, 90.0],
                c_angles=[-10.0, 0.0, 10.0]
            )
            
            points = cylindrical_pattern.generate_points()
            self.logger.info(f"   Cylindrical pattern: {len(points)} points generated")
            
            # Test grid pattern
            grid_pattern = orchestrator.create_grid_pattern(
                x_range=(-20.0, 20.0),
                y_range=(-15.0, 15.0),
                spacing=10.0,
                z_height=25.0,
                rotations=[0.0, 45.0]
            )
            
            grid_points = grid_pattern.generate_points()
            self.logger.info(f"   Grid pattern: {len(grid_points)} points generated")
            
            await orchestrator.shutdown()
            
            if len(points) > 0 and len(grid_points) > 0:
                self.logger.info("✅ Scan pattern generation successful")
                self.test_results['pattern_generation'] = True
                return True
            else:
                self.logger.error("❌ Scan pattern generation failed")
                self.test_results['pattern_generation'] = False
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Scan pattern generation error: {e}")
            self.test_results['pattern_generation'] = False
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def test_mock_scan_execution(self) -> bool:
        """Test scan execution with mock hardware (safe test)"""
        self.logger.info("🔄 Testing Mock Scan Execution...")
        
        try:
            # Create output directory
            if self.args.output_dir:
                output_dir = Path(self.args.output_dir) / f"mock_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            else:
                output_dir = Path(tempfile.gettempdir()) / f"mock_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Use simulation mode for safe testing
            config_file = self._create_test_config(simulation=True)
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            await orchestrator.initialize()
            
            # Create small test pattern
            if self.args.quick:
                pattern = orchestrator.create_cylindrical_pattern(
                    x_range=(0.0, 10.0),
                    y_range=(20.0, 30.0),
                    z_rotations=[0.0],
                    c_angles=[0.0]
                )
            else:
                pattern = orchestrator.create_cylindrical_pattern(
                    x_range=(-5.0, 5.0),
                    y_range=(20.0, 30.0),
                    z_rotations=[0.0, 90.0],
                    c_angles=[-5.0, 0.0, 5.0]
                )
            
            points = pattern.generate_points()
            self.logger.info(f"   Executing scan with {len(points)} points...")
            
            # Start scan
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=output_dir,
                scan_id=f"mock_test_{datetime.now().strftime('%H%M%S')}"
            )
            
            self.logger.info(f"   Scan started: {scan_state.scan_id}")
            
            # Wait for completion
            completed = await orchestrator.wait_for_scan_completion(timeout=30.0)
            
            await orchestrator.shutdown()
            
            # Check results
            output_files = list(output_dir.glob("*"))
            self.logger.info(f"   Generated {len(output_files)} output files")
            
            if completed and len(output_files) > 0:
                self.logger.info("✅ Mock scan execution successful")
                self.test_results['mock_scan'] = True
                return True
            else:
                self.logger.error("❌ Mock scan execution failed")
                self.test_results['mock_scan'] = False
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Mock scan execution error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.test_results['mock_scan'] = False
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def test_hardware_scan_execution(self) -> bool:
        """Test scan execution with real hardware"""
        self.logger.info("🏭 Testing Hardware Scan Execution...")
        
        try:
            # Create output directory
            if self.args.output_dir:
                output_dir = Path(self.args.output_dir) / f"hardware_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            else:
                output_dir = Path(tempfile.gettempdir()) / f"hardware_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Use real hardware
            config_file = self._create_test_config(simulation=False)
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            init_success = await orchestrator.initialize()
            if not init_success:
                self.logger.warning("⚠️  Hardware initialization failed - skipping hardware scan test")
                self.test_results['hardware_scan'] = False
                return False
            
            # Create minimal test pattern for safety
            pattern = orchestrator.create_cylindrical_pattern(
                x_range=(0.0, 5.0),      # Small movement range
                y_range=(25.0, 30.0),    # Small height range
                z_rotations=[0.0],       # Single rotation
                c_angles=[0.0]           # Single camera angle
            )
            
            points = pattern.generate_points()
            self.logger.info(f"   Executing hardware scan with {len(points)} points...")
            self.logger.warning("⚠️  CAUTION: Moving real hardware!")
            
            # Start scan
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=output_dir,
                scan_id=f"hardware_test_{datetime.now().strftime('%H%M%S')}"
            )
            
            self.logger.info(f"   Scan started: {scan_state.scan_id}")
            
            # Wait for completion
            completed = await orchestrator.wait_for_scan_completion(timeout=60.0)
            
            await orchestrator.shutdown()
            
            # Check results
            output_files = list(output_dir.glob("*"))
            self.logger.info(f"   Generated {len(output_files)} output files")
            
            if completed and len(output_files) > 0:
                self.logger.info("✅ Hardware scan execution successful")
                self.test_results['hardware_scan'] = True
                return True
            else:
                self.logger.error("❌ Hardware scan execution failed")
                self.test_results['hardware_scan'] = False
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Hardware scan execution error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self.test_results['hardware_scan'] = False
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def test_error_recovery(self) -> bool:
        """Test error recovery mechanisms"""
        self.logger.info("🛡️  Testing Error Recovery...")
        
        try:
            config_file = self._create_test_config(simulation=True)
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            await orchestrator.initialize()
            
            # Test pause/resume functionality
            pattern = orchestrator.create_cylindrical_pattern(
                x_range=(0.0, 10.0),
                y_range=(20.0, 30.0),
                z_rotations=[0.0, 90.0],
                c_angles=[0.0]
            )
            
            # Start scan
            output_dir = Path(tempfile.gettempdir()) / f"error_test_{datetime.now().strftime('%H%M%S')}"
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=output_dir,
                scan_id="error_test"
            )
            
            # Let it run briefly
            await asyncio.sleep(2.0)
            
            # Test pause
            await orchestrator.pause_scan()
            self.logger.info("   Scan paused successfully")
            
            # Wait a bit
            await asyncio.sleep(1.0)
            
            # Test resume
            await orchestrator.resume_scan()
            self.logger.info("   Scan resumed successfully")
            
            # Let it complete or timeout
            completed = await orchestrator.wait_for_scan_completion(timeout=20.0)
            
            await orchestrator.shutdown()
            
            self.logger.info("✅ Error recovery test successful")
            self.test_results['error_recovery'] = True
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error recovery test error: {e}")
            self.test_results['error_recovery'] = False
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    def _create_test_config(self, simulation: Optional[bool] = None) -> str:
        """Create test configuration file"""
        if simulation is None:
            simulation = self.args.simulation
            
        config_content = {
            'system': {
                'name': 'Test Scanner',
                'simulation_mode': simulation,
                'log_level': 'INFO'
            },
            'motion': {
                'controller': {
                    'port': self.args.motion_port,
                    'baudrate': 115200,
                    'timeout': 5.0
                },
                'axes': {
                    'x_axis': {'min_limit': -50.0, 'max_limit': 50.0, 'max_feedrate': 1000.0},
                    'y_axis': {'min_limit': 0.0, 'max_limit': 100.0, 'max_feedrate': 1000.0},
                    'z_axis': {'min_limit': -180.0, 'max_limit': 180.0, 'max_feedrate': 360.0},
                    'c_axis': {'min_limit': -45.0, 'max_limit': 45.0, 'max_feedrate': 180.0}
                }
            },
            'cameras': {
                'camera_1': {'port': 0, 'resolution': [1920, 1080]},
                'camera_2': {'port': 1, 'resolution': [1920, 1080]}
            }
        }
        
        import tempfile
        try:
            import yaml
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config_content, f, default_flow_style=False)
                return f.name
        except ImportError:
            # Fallback to json for configuration
            import json
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config_content, f, indent=2)
                return f.name
    
    def _print_final_results(self, overall_success: bool):
        """Print final test results"""
        self.logger.info("=" * 60)
        self.logger.info("🧪 INTEGRATED SCANNING SYSTEM TEST RESULTS")
        self.logger.info("=" * 60)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            self.logger.info(f"  {test_name:.<30} {status}")
        
        self.logger.info("=" * 60)
        
        if overall_success:
            self.logger.info("🎉 ALL TESTS PASSED - Integrated scanning system ready!")
        else:
            self.logger.warning("⚠️  SOME TESTS FAILED - Check logs for details")
            
        self.logger.info("=" * 60)


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Integrated Scanning System Test Suite')
    
    # Hardware options
    parser.add_argument('--motion-port', default='/dev/ttyUSB0', 
                       help='Serial port for FluidNC (default: /dev/ttyUSB0)')
    parser.add_argument('--simulation', action='store_true', 
                       help='Run in simulation mode (use mock hardware)')
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick test with minimal scan points')
    
    # Output options
    parser.add_argument('--output-dir', 
                       help='Output directory for scan results (default: temp)')
    parser.add_argument('--verbose', action='store_true', 
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level_str = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level=log_level_str, log_dir=Path("test_output"))
    
    # Create output directory if needed
    if args.output_dir:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Run tests
    test_runner = IntegratedScanningTestRunner(args)
    success = await test_runner.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())