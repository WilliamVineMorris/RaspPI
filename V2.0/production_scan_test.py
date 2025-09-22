#!/usr/bin/env python3
"""
Production Scan Testing Suite

Complete end-to-end production scanning test that demonstrates the full
capabilities of the integrated hardware scanning system with real FluidNC
motion control and Pi cameras.

This script performs comprehensive scans using cylindrical patterns optimized
for the 4DOF scanner geometry, validates output quality, and demonstrates
production-ready scanning workflows.

Usage:
    python production_scan_test.py [options]

Options:
    --output-dir DIR       Output directory for production scans
    --scan-pattern TYPE    Scan pattern type: cylindrical, grid, or both (default: cylindrical)
    --density LEVEL        Scan density: low, medium, high (default: medium)
    --validate-output      Perform output validation and quality checks
    --motion-port PORT     Serial port for FluidNC (default: /dev/ttyUSB0)
    --dry-run             Validate setup without moving hardware
    --interactive         Interactive scan with manual controls

Safety Features:
    - Hardware validation before starting
    - Motion limit checks
    - Emergency stop capabilities
    - Progressive scan patterns starting with minimal movement

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import argparse
import logging
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.logging_setup import setup_logging
from scanning import ScanOrchestrator


class ProductionScanTestSuite:
    """Production scan testing and validation suite"""
    
    def __init__(self, args):
        self.args = args
        self.logger = logging.getLogger(__name__)
        self.scan_results = []
        self.output_base_dir = Path(args.output_dir) if args.output_dir else Path("production_scans")
        
        # Scan pattern configurations
        self.scan_configs = {
            'low': {
                'cylindrical': {
                    'x_range': (-10.0, 10.0),
                    'y_range': (20.0, 40.0),
                    'x_step': 10.0,
                    'y_step': 20.0,
                    'z_rotations': [0.0, 90.0],
                    'c_angles': [0.0]
                },
                'grid': {
                    'x_range': (-15.0, 15.0),
                    'y_range': (-10.0, 10.0),
                    'spacing': 15.0,
                    'z_height': 25.0,
                    'rotations': [0.0, 90.0]
                }
            },
            'medium': {
                'cylindrical': {
                    'x_range': (-20.0, 20.0),
                    'y_range': (15.0, 60.0),
                    'x_step': 8.0,
                    'y_step': 15.0,
                    'z_rotations': [0.0, 45.0, 90.0, 135.0],
                    'c_angles': [-10.0, 0.0, 10.0]
                },
                'grid': {
                    'x_range': (-25.0, 25.0),
                    'y_range': (-20.0, 20.0),
                    'spacing': 10.0,
                    'z_height': 30.0,
                    'rotations': [0.0, 45.0, 90.0, 135.0]
                }
            },
            'high': {
                'cylindrical': {
                    'x_range': (-30.0, 30.0),
                    'y_range': (10.0, 80.0),
                    'x_step': 6.0,
                    'y_step': 12.0,
                    'z_rotations': [0.0, 30.0, 60.0, 90.0, 120.0, 150.0],
                    'c_angles': [-15.0, -5.0, 0.0, 5.0, 15.0]
                },
                'grid': {
                    'x_range': (-40.0, 40.0),
                    'y_range': (-30.0, 30.0),
                    'spacing': 8.0,
                    'z_height': 35.0,
                    'rotations': [0.0, 30.0, 60.0, 90.0, 120.0, 150.0]
                }
            }
        }
    
    async def run_production_tests(self) -> bool:
        """Run complete production scan test suite"""
        self.logger.info("🏭 Starting Production Scan Test Suite")
        self.logger.info("=" * 70)
        self.logger.info(f"Configuration:")
        self.logger.info(f"  Output directory: {self.output_base_dir}")
        self.logger.info(f"  Scan pattern: {self.args.scan_pattern}")
        self.logger.info(f"  Scan density: {self.args.density}")
        self.logger.info(f"  Validate output: {self.args.validate_output}")
        self.logger.info(f"  Dry run: {self.args.dry_run}")
        self.logger.info(f"  Motion port: {self.args.motion_port}")
        self.logger.info("=" * 70)
        
        success = True
        
        # Step 1: Hardware validation
        success &= await self.validate_hardware_setup()
        
        if not success and not self.args.dry_run:
            self.logger.error("❌ Hardware validation failed. Cannot proceed with production scans.")
            return False
        
        # Step 2: Execute production scans
        if self.args.scan_pattern in ['cylindrical', 'both']:
            success &= await self.run_cylindrical_scan()
        
        if self.args.scan_pattern in ['grid', 'both']:
            success &= await self.run_grid_scan()
        
        # Step 3: Output validation
        if self.args.validate_output:
            success &= await self.validate_scan_outputs()
        
        # Step 4: Interactive mode
        if self.args.interactive:
            await self.run_interactive_scan()
        
        # Step 5: Generate final report
        self.generate_production_report()
        
        return success
    
    async def validate_hardware_setup(self) -> bool:
        """Validate hardware setup and connectivity"""
        self.logger.info("🔧 Validating Hardware Setup...")
        
        try:
            # Create configuration
            config_file = self._create_production_config()
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            # Test initialization
            if self.args.dry_run:
                self.logger.info("   Dry run mode: Skipping actual hardware initialization")
                return True
                
            init_success = await orchestrator.initialize()
            
            if not init_success:
                self.logger.error("   ❌ Hardware initialization failed")
                return False
            
            # Validate motion controller
            motion_connected = orchestrator.motion_controller.is_connected()
            self.logger.info(f"   Motion controller: {'✅ Connected' if motion_connected else '❌ Disconnected'}")
            
            # Validate camera system
            camera_health = await orchestrator.camera_manager.check_camera_health()
            self.logger.info(f"   Camera system: {'✅ Ready' if camera_health else '❌ Not ready'}")
            
            # Test basic movement (minimal, safe)
            if motion_connected:
                self.logger.info("   Testing basic motion...")
                home_success = await orchestrator.motion_controller.home()
                self.logger.info(f"   Homing: {'✅ Success' if home_success else '❌ Failed'}")
                
                # Small test movement
                move_success = await orchestrator.motion_controller.move_to(5.0, 25.0)
                self.logger.info(f"   Test movement: {'✅ Success' if move_success else '❌ Failed'}")
                
                # Return home
                await orchestrator.motion_controller.home()
            
            await orchestrator.shutdown()
            
            validation_success = motion_connected and camera_health
            
            if validation_success:
                self.logger.info("✅ Hardware validation successful")
            else:
                self.logger.error("❌ Hardware validation failed")
                
            return validation_success
            
        except Exception as e:
            self.logger.error(f"❌ Hardware validation error: {e}")
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def run_cylindrical_scan(self) -> bool:
        """Execute cylindrical scan pattern optimized for turntable scanner"""
        self.logger.info("🔄 Executing Cylindrical Scan Pattern...")
        
        try:
            # Create scan session directory
            session_dir = self.output_base_dir / f"cylindrical_{self.args.density}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Setup orchestrator
            config_file = self._create_production_config()
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            if not self.args.dry_run:
                await orchestrator.initialize()
            
            # Get scan configuration
            scan_config = self.scan_configs[self.args.density]['cylindrical']
            
            # Create pattern
            pattern = orchestrator.create_cylindrical_pattern(**scan_config)
            points = pattern.generate_points()
            
            self.logger.info(f"   Pattern configuration:")
            self.logger.info(f"     X range: {scan_config['x_range']} mm")
            self.logger.info(f"     Y range: {scan_config['y_range']} mm")
            self.logger.info(f"     Z rotations: {len(scan_config['z_rotations'])} angles")
            self.logger.info(f"     C angles: {len(scan_config['c_angles'])} angles")
            self.logger.info(f"   Total scan points: {len(points)}")
            
            if self.args.dry_run:
                self.logger.info("   Dry run mode: Pattern validation successful")
                estimated_time = len(points) * 3.0  # 3 seconds per point estimate
                self.logger.info(f"   Estimated scan time: {estimated_time/60:.1f} minutes")
                return True
            
            # Execute scan
            self.logger.info("   🚀 Starting cylindrical scan...")
            self.logger.warning("   ⚠️  CAUTION: Hardware will move through scan pattern!")
            
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=session_dir,
                scan_id=f"cylindrical_{self.args.density}_{datetime.now().strftime('%H%M%S')}"
            )
            
            self.logger.info(f"   Scan ID: {scan_state.scan_id}")
            
            # Monitor progress
            start_time = datetime.now()
            completed = await orchestrator.wait_for_scan_completion(timeout=len(points) * 5.0)  # 5 sec per point max
            end_time = datetime.now()
            
            scan_duration = (end_time - start_time).total_seconds()
            
            await orchestrator.shutdown()
            
            # Analyze results
            output_files = list(session_dir.glob("*"))
            
            scan_result = {
                'pattern_type': 'cylindrical',
                'density': self.args.density,
                'scan_points': len(points),
                'duration_seconds': scan_duration,
                'completed': completed,
                'output_files': len(output_files),
                'session_dir': str(session_dir),
                'config': scan_config
            }
            
            self.scan_results.append(scan_result)
            
            if completed:
                self.logger.info(f"   ✅ Cylindrical scan completed successfully")
                self.logger.info(f"   Duration: {scan_duration:.1f} seconds ({scan_duration/60:.1f} minutes)")
                self.logger.info(f"   Output files: {len(output_files)}")
                self.logger.info(f"   Average time per point: {scan_duration/len(points):.2f} seconds")
                return True
            else:
                self.logger.error(f"   ❌ Cylindrical scan failed or timed out")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Cylindrical scan error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def run_grid_scan(self) -> bool:
        """Execute grid scan pattern for comparison"""
        self.logger.info("📐 Executing Grid Scan Pattern...")
        
        try:
            # Create scan session directory
            session_dir = self.output_base_dir / f"grid_{self.args.density}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session_dir.mkdir(parents=True, exist_ok=True)
            
            # Setup orchestrator
            config_file = self._create_production_config()
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            if not self.args.dry_run:
                await orchestrator.initialize()
            
            # Get scan configuration
            scan_config = self.scan_configs[self.args.density]['grid']
            
            # Create pattern
            pattern = orchestrator.create_grid_pattern(**scan_config)
            points = pattern.generate_points()
            
            self.logger.info(f"   Pattern configuration:")
            self.logger.info(f"     X range: {scan_config['x_range']} mm")
            self.logger.info(f"     Y range: {scan_config['y_range']} mm")
            self.logger.info(f"     Grid spacing: {scan_config['spacing']} mm")
            self.logger.info(f"     Z height: {scan_config['z_height']} mm")
            self.logger.info(f"     Rotations: {len(scan_config['rotations'])} angles")
            self.logger.info(f"   Total scan points: {len(points)}")
            
            if self.args.dry_run:
                self.logger.info("   Dry run mode: Pattern validation successful")
                estimated_time = len(points) * 3.0
                self.logger.info(f"   Estimated scan time: {estimated_time/60:.1f} minutes")
                return True
            
            # Execute scan
            self.logger.info("   🚀 Starting grid scan...")
            
            scan_state = await orchestrator.start_scan(
                pattern=pattern,
                output_directory=session_dir,
                scan_id=f"grid_{self.args.density}_{datetime.now().strftime('%H%M%S')}"
            )
            
            # Monitor progress
            start_time = datetime.now()
            completed = await orchestrator.wait_for_scan_completion(timeout=len(points) * 5.0)
            end_time = datetime.now()
            
            scan_duration = (end_time - start_time).total_seconds()
            
            await orchestrator.shutdown()
            
            # Analyze results
            output_files = list(session_dir.glob("*"))
            
            scan_result = {
                'pattern_type': 'grid',
                'density': self.args.density,
                'scan_points': len(points),
                'duration_seconds': scan_duration,
                'completed': completed,
                'output_files': len(output_files),
                'session_dir': str(session_dir),
                'config': scan_config
            }
            
            self.scan_results.append(scan_result)
            
            if completed:
                self.logger.info(f"   ✅ Grid scan completed successfully")
                self.logger.info(f"   Duration: {scan_duration:.1f} seconds ({scan_duration/60:.1f} minutes)")
                self.logger.info(f"   Output files: {len(output_files)}")
                return True
            else:
                self.logger.error(f"   ❌ Grid scan failed or timed out")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Grid scan error: {e}")
            return False
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    async def validate_scan_outputs(self) -> bool:
        """Validate scan output quality and completeness"""
        self.logger.info("🔍 Validating Scan Outputs...")
        
        validation_success = True
        
        for result in self.scan_results:
            self.logger.info(f"   Validating {result['pattern_type']} scan...")
            
            session_dir = Path(result['session_dir'])
            
            # Check for image files
            image_files = list(session_dir.glob("*.jpg")) + list(session_dir.glob("*.png"))
            self.logger.info(f"     Image files: {len(image_files)}")
            
            # Check for metadata files
            json_files = list(session_dir.glob("*.json"))
            self.logger.info(f"     Metadata files: {len(json_files)}")
            
            # Expected files per scan point (2 cameras)
            expected_images = result['scan_points'] * 2
            image_ratio = len(image_files) / expected_images if expected_images > 0 else 0
            
            self.logger.info(f"     Image completion: {image_ratio:.1%} ({len(image_files)}/{expected_images})")
            
            # Validate image file sizes
            total_size = sum(f.stat().st_size for f in image_files)
            avg_size = total_size / len(image_files) if image_files else 0
            
            self.logger.info(f"     Total data size: {total_size/1024/1024:.1f} MB")
            self.logger.info(f"     Average image size: {avg_size/1024:.1f} KB")
            
            # Quality checks
            if image_ratio < 0.9:
                self.logger.warning(f"     ⚠️  Low image completion ratio: {image_ratio:.1%}")
                validation_success = False
            
            if avg_size < 10*1024:  # Less than 10KB suggests empty files
                self.logger.warning(f"     ⚠️  Small average image size: {avg_size/1024:.1f} KB")
                validation_success = False
            
            # Update result with validation info
            result['validation'] = {
                'image_files': len(image_files),
                'expected_images': expected_images,
                'completion_ratio': image_ratio,
                'total_size_mb': total_size/1024/1024,
                'avg_size_kb': avg_size/1024
            }
        
        if validation_success:
            self.logger.info("✅ Scan output validation successful")
        else:
            self.logger.warning("⚠️  Scan output validation found issues")
            
        return validation_success
    
    async def run_interactive_scan(self):
        """Run interactive scan with manual controls"""
        self.logger.info("🎮 Starting Interactive Scan Mode...")
        
        if self.args.dry_run:
            self.logger.info("   Interactive mode not available in dry run")
            return
        
        try:
            config_file = self._create_production_config()
            config_manager = ConfigManager(config_file)
            orchestrator = ScanOrchestrator(config_manager)
            
            await orchestrator.initialize()
            
            # Create interactive session directory
            session_dir = self.output_base_dir / f"interactive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            session_dir.mkdir(parents=True, exist_ok=True)
            
            self.logger.info("   Interactive scan ready. Use commands:")
            self.logger.info("     'start' - Start a small test scan")
            self.logger.info("     'pause' - Pause current scan")
            self.logger.info("     'resume' - Resume paused scan")
            self.logger.info("     'stop' - Stop current scan")
            self.logger.info("     'status' - Show scan status")
            self.logger.info("     'quit' - Exit interactive mode")
            
            current_scan = None
            
            while True:
                try:
                    command = input("Scanner> ").strip().lower()
                    
                    if command == 'start':
                        if current_scan:
                            print("Scan already running. Use 'stop' first.")
                            continue
                            
                        # Create small test pattern
                        pattern = orchestrator.create_cylindrical_pattern(
                            x_range=(0.0, 10.0),
                            y_range=(25.0, 35.0),
                            z_rotations=[0.0, 45.0],
                            c_angles=[0.0]
                        )
                        
                        current_scan = await orchestrator.start_scan(
                            pattern=pattern,
                            output_directory=session_dir,
                            scan_id=f"interactive_{datetime.now().strftime('%H%M%S')}"
                        )
                        
                        print(f"Started scan: {current_scan.scan_id}")
                        
                    elif command == 'pause':
                        if current_scan:
                            await orchestrator.pause_scan()
                            print("Scan paused")
                        else:
                            print("No active scan")
                            
                    elif command == 'resume':
                        if current_scan:
                            await orchestrator.resume_scan()
                            print("Scan resumed")
                        else:
                            print("No active scan")
                            
                    elif command == 'stop':
                        if current_scan:
                            await orchestrator.stop_scan()
                            print("Scan stopped")
                            current_scan = None
                        else:
                            print("No active scan")
                            
                    elif command == 'status':
                        if current_scan:
                            try:
                                status = orchestrator.get_scan_status()
                                if status:
                                    print(f"Scan: {status.get('scan_id', 'Unknown')}")
                                    print(f"Status: {status.get('status', 'Unknown')}")
                                    if 'progress' in status:
                                        progress = status['progress']
                                        print(f"Progress: {progress.get('completion_percentage', 0):.1f}%")
                                        print(f"Points: {progress.get('current_point', 0)}/{progress.get('total_points', 0)}")
                                    else:
                                        print("Progress: Not available")
                                else:
                                    print("Status: Unable to retrieve scan status")
                            except Exception as e:
                                print(f"Error getting status: {e}")
                        else:
                            print("No active scan")
                            
                    elif command == 'quit':
                        if current_scan:
                            await orchestrator.stop_scan()
                        break
                        
                    else:
                        print("Unknown command. Type 'quit' to exit.")
                        
                except KeyboardInterrupt:
                    print("\\nExiting interactive mode...")
                    if current_scan:
                        await orchestrator.stop_scan()
                    break
                except Exception as e:
                    print(f"Error: {e}")
            
            await orchestrator.shutdown()
            
        except Exception as e:
            self.logger.error(f"Interactive scan error: {e}")
        finally:
            try:
                Path(config_file).unlink()
            except:
                pass
    
    def generate_production_report(self):
        """Generate comprehensive production test report"""
        self.logger.info("📊 Generating Production Test Report...")
        
        report_file = self.output_base_dir / f"production_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        report = {
            'test_session': {
                'timestamp': datetime.now().isoformat(),
                'configuration': {
                    'scan_pattern': self.args.scan_pattern,
                    'density': self.args.density,
                    'dry_run': self.args.dry_run,
                    'motion_port': self.args.motion_port
                }
            },
            'scan_results': self.scan_results,
            'summary': self._generate_summary()
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        self.logger.info(f"   Report saved: {report_file}")
        
        # Print summary to console
        summary = report['summary']
        self.logger.info("=" * 70)
        self.logger.info("📋 PRODUCTION TEST SUMMARY")
        self.logger.info("=" * 70)
        self.logger.info(f"Total scans executed: {summary['total_scans']}")
        self.logger.info(f"Successful scans: {summary['successful_scans']}")
        self.logger.info(f"Total scan points: {summary['total_points']}")
        self.logger.info(f"Total output files: {summary['total_files']}")
        self.logger.info(f"Total scan time: {summary['total_duration']:.1f} seconds")
        
        if summary['total_points'] > 0:
            self.logger.info(f"Average time per point: {summary['avg_time_per_point']:.2f} seconds")
        
        self.logger.info("=" * 70)
        
        if summary['successful_scans'] == summary['total_scans']:
            self.logger.info("🎉 ALL PRODUCTION TESTS PASSED!")
        else:
            self.logger.warning("⚠️  SOME PRODUCTION TESTS FAILED")
            
        self.logger.info("=" * 70)
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate test summary statistics"""
        total_scans = len(self.scan_results)
        successful_scans = sum(1 for r in self.scan_results if r['completed'])
        total_points = sum(r['scan_points'] for r in self.scan_results)
        total_files = sum(r['output_files'] for r in self.scan_results)
        total_duration = sum(r['duration_seconds'] for r in self.scan_results)
        
        return {
            'total_scans': total_scans,
            'successful_scans': successful_scans,
            'total_points': total_points,
            'total_files': total_files,
            'total_duration': total_duration,
            'avg_time_per_point': total_duration / total_points if total_points > 0 else 0,
            'success_rate': successful_scans / total_scans if total_scans > 0 else 0
        }
    
    def _create_production_config(self) -> str:
        """Create production configuration file"""
        config_content = {
            'system': {
                'name': 'Production Scanner',
                'simulation_mode': self.args.dry_run,
                'log_level': 'INFO'
            },
            'motion': {
                'controller': {
                    'type': 'fluidnc',
                    'connection': 'usb',
                    'port': self.args.motion_port,
                    'baudrate': 115200,
                    'timeout': 10.0
                },
                'axes': {
                    'x_axis': {
                        'type': 'linear',
                        'units': 'mm',
                        'min_limit': -50.0, 
                        'max_limit': 50.0, 
                        'max_feedrate': 1500.0,
                        'home_position': 0.0
                    },
                    'y_axis': {
                        'type': 'linear',
                        'units': 'mm',
                        'min_limit': 0.0, 
                        'max_limit': 100.0, 
                        'max_feedrate': 1500.0,
                        'home_position': 0.0
                    },
                    'z_axis': {
                        'type': 'rotational',
                        'units': 'degrees',
                        'min_limit': -360.0, 
                        'max_limit': 360.0, 
                        'max_feedrate': 720.0,
                        'home_position': 0.0,
                        'continuous': True
                    },
                    'c_axis': {
                        'type': 'rotational',
                        'units': 'degrees',
                        'min_limit': -45.0, 
                        'max_limit': 45.0, 
                        'max_feedrate': 360.0,
                        'home_position': 0.0
                    }
                }
            },
            'cameras': {
                'camera_1': {
                    'port': 0, 
                    'resolution': [1920, 1080],
                    'name': 'main'
                },
                'camera_2': {
                    'port': 1, 
                    'resolution': [1920, 1080],
                    'name': 'secondary'
                }
            },
            'lighting': {
                'led_zones': {
                    'zone_1': {
                        'gpio_pin': 18, 
                        'name': 'main_light',
                        'max_intensity': 85.0
                    },
                    'zone_2': {
                        'gpio_pin': 19, 
                        'name': 'secondary_light',
                        'max_intensity': 85.0
                    }
                }
            }
        }
        
        import tempfile
        try:
            import yaml
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(config_content, f, default_flow_style=False)
                return f.name
        except ImportError:
            import json
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                json.dump(config_content, f, indent=2)
                return f.name


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Production Scan Testing Suite')
    
    # Scan configuration
    parser.add_argument('--output-dir', default='production_scans',
                       help='Output directory for production scans')
    parser.add_argument('--scan-pattern', choices=['cylindrical', 'grid', 'both'], 
                       default='cylindrical', help='Scan pattern type')
    parser.add_argument('--density', choices=['low', 'medium', 'high'], 
                       default='medium', help='Scan density level')
    
    # Hardware options
    parser.add_argument('--motion-port', default='/dev/ttyUSB0',
                       help='Serial port for FluidNC')
    parser.add_argument('--dry-run', action='store_true',
                       help='Validate setup without moving hardware')
    
    # Test options
    parser.add_argument('--validate-output', action='store_true',
                       help='Perform output validation and quality checks')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive scan with manual controls')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(log_level=log_level, log_dir=Path("test_output"))
    
    # Create output directory
    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    
    # Run production tests
    test_suite = ProductionScanTestSuite(args)
    success = await test_suite.run_production_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())