#!/usr/bin/env python3
"""
Quick Integration Test

Test the fixes for FluidNC connection and JPEG generation
without running the full test suite.

Usage:
    python quick_test.py

Author: Scanner System Development  
Created: September 2025
"""

import sys
import asyncio
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from scanning.scan_orchestrator import ScanOrchestrator, MockCameraManager


def create_test_config():
    """Create minimal test configuration"""
    config = {
        'system': {
            'name': 'Quick Test Scanner',
            'debug_mode': False,
            'simulation_mode': False,  # Test with real hardware
            'log_level': 'INFO'
        },
        'platform': {
            'type': 'raspberry_pi_5',
            'gpio_library': 'pigpio',
            'camera_interface': 'libcamera'
        },
        'motion': {
            'controller': {
                'type': 'fluidnc',
                'connection': 'usb',
                'port': '/dev/ttyUSB0',
                'baudrate': 115200,
                'timeout': 5.0  # Shorter timeout for testing
            },
            'axes': {
                'x_axis': {
                    'type': 'linear',
                    'units': 'mm',
                    'min_limit': 0.0,
                    'max_limit': 200.0,
                    'max_feedrate': 1000.0,
                    'home_position': 0.0,
                    'home_direction': 'negative'
                },
                'y_axis': {
                    'type': 'linear', 
                    'units': 'mm',
                    'min_limit': 0.0,
                    'max_limit': 200.0,
                    'max_feedrate': 1000.0,
                    'home_position': 0.0,
                    'home_direction': 'negative'
                },
                'z_axis': {
                    'type': 'rotational',
                    'units': 'degrees',
                    'min_limit': -999999.0,
                    'max_limit': 999999.0,
                    'max_feedrate': 360.0,
                    'home_position': 0.0,
                    'continuous': True
                },
                'c_axis': {
                    'type': 'rotational',
                    'units': 'degrees',
                    'min_limit': -90.0,
                    'max_limit': 90.0,
                    'max_feedrate': 180.0,
                    'home_position': 0.0
                }
            }
        },
        'cameras': {
            'camera_1': {
                'port': 0,
                'resolution': [1920, 1080],
                'name': 'main',
                'framerate': 30
            },
            'camera_2': {
                'port': 1,
                'resolution': [1920, 1080],
                'name': 'secondary',
                'framerate': 30
            }
        }
    }
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        # Write YAML manually
        def write_dict(d, indent=0):
            for key, value in d.items():
                f.write('  ' * indent + f"{key}:")
                if isinstance(value, dict):
                    f.write('\n')
                    write_dict(value, indent + 1)
                elif isinstance(value, list):
                    f.write(f" {value}\n")
                else:
                    f.write(f" {value}\n")
        
        write_dict(config)
        return f.name


async def test_fluidnc_connection():
    """Test FluidNC connection with improved initialization"""
    print("🔧 Testing FluidNC Connection...")
    
    config_file = create_test_config()
    
    try:
        config_manager = ConfigManager(config_file)
        orchestrator = ScanOrchestrator(config_manager)
        
        print("   🔌 Initializing orchestrator...")
        success = await orchestrator.initialize()
        
        if success:
            print("   ✅ FluidNC initialization successful!")
            
            # Test homing  
            print("   🏠 Testing homing sequence...")
            motion_controller = orchestrator.motion_controller
            
            # Check if it's the real controller (adapter with FluidNC)
            try:
                if hasattr(motion_controller, 'controller'):
                    # This is the adapter, get the real controller
                    real_controller = getattr(motion_controller, 'controller')
                    if hasattr(real_controller, 'home_all_axes'):
                        homed = await real_controller.home_all_axes()
                        if homed:
                            print("   ✅ Homing completed successfully!")
                        else:
                            print("   ⚠️  Homing failed")
                    else:
                        print("   ℹ️  Controller doesn't support homing test")
                else:
                    print("   ℹ️  Mock controller - skipping homing test")
            except Exception as e:
                print(f"   ⚠️  Homing error: {e}")
        else:
            print("   ❌ FluidNC initialization failed")
        
        await orchestrator.shutdown()
        return success
        
    except Exception as e:
        print(f"   ❌ FluidNC test error: {e}")
        return False
    finally:
        Path(config_file).unlink()


async def test_mock_camera_jpeg():
    """Test mock camera JPEG generation"""
    print("\n📷 Testing Mock Camera JPEG Generation...")
    
    # Create simulation config
    config = {
        'system': {
            'name': 'Mock Test Scanner',
            'debug_mode': False,
            'simulation_mode': True,  # Force simulation for this test
            'log_level': 'INFO'
        },
        'platform': {
            'type': 'test'
        },
        'cameras': {
            'camera_1': {
                'port': 0,
                'resolution': [640, 480],
                'name': 'test_camera'
            }
        }
    }
    
    # Write to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        def write_dict(d, indent=0):
            for key, value in d.items():
                f.write('  ' * indent + f"{key}:")
                if isinstance(value, dict):
                    f.write('\n')
                    write_dict(value, indent + 1)
                elif isinstance(value, list):
                    f.write(f" {value}\n")
                else:
                    f.write(f" {value}\n")
        
        write_dict(config)
        config_file = f.name
    
    try:
        config_manager = ConfigManager(config_file)
        
        mock_camera = MockCameraManager(config_manager)
        
        # Test capture
        test_output_dir = Path("/tmp/quick_test_jpeg")
        test_output_dir.mkdir(exist_ok=True)
        
        print("   📸 Generating mock JPEG files...")
        results = await mock_camera.capture_all(
            test_output_dir,
            "test_image",
            {"test": "quick_test"}
        )
        
        print(f"   📤 Generated {len(results)} files")
        
        # Analyze each file
        valid_jpegs = 0
        for result in results:
            if result['success']:
                file_path = Path(result['filepath'])
                print(f"   📁 Checking: {file_path.name}")
                
                # Check JPEG validity
                try:
                    with open(file_path, 'rb') as f:
                        header = f.read(4)
                    
                    if header.startswith(b'\xff\xd8'):
                        print(f"      ✅ Valid JPEG header")
                        valid_jpegs += 1
                    else:
                        print(f"      ❌ Invalid JPEG header: {header.hex()}")
                
                except Exception as e:
                    print(f"      ❌ Error reading file: {e}")
        
        # Cleanup
        for result in results:
            if result['success']:
                Path(result['filepath']).unlink()
        test_output_dir.rmdir()
        
        success = valid_jpegs == len(results)
        if success:
            print(f"   ✅ All {valid_jpegs} JPEG files are valid!")
        else:
            print(f"   ⚠️  Only {valid_jpegs}/{len(results)} JPEG files are valid")
        
        return success
        
    except Exception as e:
        print(f"   ❌ JPEG test error: {e}")
        return False
    finally:
        Path(config_file).unlink()


async def main():
    """Main test function"""
    print("🧪 Quick Integration Test - Testing Fixes")
    print("=" * 50)
    
    # Test FluidNC connection improvements
    fluidnc_success = await test_fluidnc_connection()
    
    # Test JPEG generation fixes
    jpeg_success = await test_mock_camera_jpeg()
    
    # Summary
    print("\n📊 Test Results Summary")
    print("=" * 30)
    print(f"   FluidNC Connection: {'✅ PASS' if fluidnc_success else '❌ FAIL'}")
    print(f"   JPEG Generation:    {'✅ PASS' if jpeg_success else '❌ FAIL'}")
    
    if fluidnc_success and jpeg_success:
        print("\n🎉 ALL FIXES WORKING! Ready for full integration test")
    else:
        print("\n⚠️  Some issues remain - check logs for details")
    
    return fluidnc_success and jpeg_success


if __name__ == "__main__":
    asyncio.run(main())