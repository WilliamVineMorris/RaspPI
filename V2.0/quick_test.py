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
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from scanning.scan_orchestrator import ScanOrchestrator, MockCameraManager


def create_test_config():
    """Create test configuration matching real FluidNC hardware"""
    # Create temporary file with manual YAML matching actual FluidNC config
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write("system:\n")
        f.write("  name: Quick Test Scanner\n")
        f.write("  debug_mode: false\n")
        f.write("  simulation_mode: false\n")
        f.write("  log_level: INFO\n")
        f.write("platform:\n")
        f.write("  type: raspberry_pi_5\n")
        f.write("motion:\n")
        f.write("  controller:\n")
        f.write("    type: fluidnc\n")
        f.write("    port: /dev/ttyUSB0\n")
        f.write("    baudrate: 115200\n")
        f.write("  axes:\n")
        f.write("    x_axis:\n")
        f.write("      type: linear\n")
        f.write("      units: mm\n")
        f.write("      min_limit: 0.0\n")
        f.write("      max_limit: 200.0\n")  # From max_travel_mm in FluidNC config
        f.write("      max_feedrate: 1000.0\n")  # From max_rate_mm_per_min
        f.write("      steps_per_mm: 800\n")  # From FluidNC config
        f.write("      has_limits: true\n")  # Has limit switches
        f.write("    y_axis:\n")
        f.write("      type: linear\n")
        f.write("      units: mm\n")
        f.write("      min_limit: 0.0\n")
        f.write("      max_limit: 200.0\n")  # From max_travel_mm
        f.write("      max_feedrate: 1000.0\n")  # From max_rate_mm_per_min
        f.write("      steps_per_mm: 800\n")  # From FluidNC config
        f.write("      has_limits: true\n")  # Has limit switches
        f.write("    z_axis:\n")
        f.write("      type: rotational\n")
        f.write("      units: degrees\n")
        f.write("      min_limit: -180.0\n")  # Continuous rotation
        f.write("      max_limit: 180.0\n")   # 360mm travel = 360 degrees
        f.write("      max_feedrate: 800.0\n")  # From max_rate_mm_per_min
        f.write("      steps_per_mm: 1422\n")  # From FluidNC config (steps per degree)
        f.write("      continuous: true\n")  # Continuous rotation
        f.write("      has_limits: false\n")  # No limit switches
        f.write("    c_axis:\n")
        f.write("      type: rotational\n")
        f.write("      units: degrees\n")
        f.write("      min_limit: -90.0\n")  # Servo range
        f.write("      max_limit: 90.0\n")   # 180mm travel = 180 degrees
        f.write("      max_feedrate: 5000.0\n")  # From max_rate_mm_per_min (servo is fast)
        f.write("      steps_per_mm: 300\n")  # From FluidNC config
        f.write("      servo_controlled: true\n")  # RC servo
        f.write("      has_limits: false\n")  # Soft limits only
        f.write("cameras:\n")
        f.write("  camera_1:\n")
        f.write("    port: 0\n")
        f.write("    resolution: [1920, 1080]\n")
        f.write("    name: main\n")
        f.write("lighting:\n")
        f.write("  zones:\n")
        f.write("    zone_1:\n")
        f.write("      type: led_array\n")
        f.write("      pin: 18\n")
        f.write("      count: 60\n")
        
        return f.name


def create_mock_config():
    """Create configuration for mock camera testing"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        f.write("system:\n")
        f.write("  name: Mock Test Scanner\n")
        f.write("  debug_mode: true\n")
        f.write("  simulation_mode: true\n")
        f.write("  log_level: INFO\n")
        f.write("platform:\n")
        f.write("  type: test\n")
        f.write("motion:\n")
        f.write("  controller:\n")
        f.write("    type: mock\n")
        f.write("    port: /dev/null\n")
        f.write("  axes:\n")
        f.write("    x_axis:\n")
        f.write("      type: linear\n")
        f.write("      units: mm\n")
        f.write("      min_limit: 0.0\n")
        f.write("      max_limit: 200.0\n")
        f.write("      max_feedrate: 1000.0\n")
        f.write("    y_axis:\n")
        f.write("      type: linear\n")
        f.write("      units: mm\n")
        f.write("      min_limit: 0.0\n")
        f.write("      max_limit: 200.0\n")
        f.write("      max_feedrate: 1000.0\n")
        f.write("    z_axis:\n")
        f.write("      type: rotational\n")
        f.write("      units: degrees\n")
        f.write("      min_limit: -999999.0\n")
        f.write("      max_limit: 999999.0\n")
        f.write("      max_feedrate: 360.0\n")
        f.write("    c_axis:\n")
        f.write("      type: rotational\n")
        f.write("      units: degrees\n")
        f.write("      min_limit: -90.0\n")
        f.write("      max_limit: 90.0\n")
        f.write("      max_feedrate: 180.0\n")
        f.write("cameras:\n")
        f.write("  camera_1:\n")
        f.write("    port: 0\n")
        f.write("    resolution: [640, 480]\n")
        f.write("    name: test_camera\n")
        f.write("lighting:\n")
        f.write("  zones:\n")
        f.write("    zone_1:\n")
        f.write("      type: led_array\n")
        f.write("      pin: 18\n")
        f.write("      count: 60\n")
        
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
            
            # Check if motion controller is connected
            motion_controller = orchestrator.motion_controller
            if motion_controller and hasattr(motion_controller, 'is_connected'):
                connected = motion_controller.is_connected()
                if connected:
                    print("   ✅ FluidNC connection verified!")
                else:
                    print("   ❌ FluidNC not connected")
            else:
                print("   ⚠️  Motion controller status unknown")
        else:
            print("   ❌ FluidNC initialization failed")
            
        # Clean shutdown
        await orchestrator.shutdown()
        return success
        
    except Exception as e:
        print(f"   ❌ FluidNC test error: {e}")
        return False
    finally:
        if os.path.exists(config_file):
            os.unlink(config_file)


async def test_mock_camera_jpeg():
    """Test mock camera JPEG generation"""
    print("📷 Testing Mock Camera JPEG Generation...")
    
    config_file = create_mock_config()
    
    try:
        config_manager = ConfigManager(config_file)
        mock_camera = MockCameraManager(config_manager)
        
        # Test JPEG generation
        test_output_dir = Path("/tmp/test_mock_jpeg")
        test_output_dir.mkdir(exist_ok=True)
        
        print("   📸 Generating test JPEG...")
        
        try:
            results = await mock_camera.capture_all(
                test_output_dir, 
                "quick_test", 
                {"test": True}
            )
            
            if results and len(results) > 0:
                # Check first result
                result = results[0]
                if result['success']:
                    file_path = Path(result['filepath'])
                    if file_path.exists():
                        # Check JPEG header
                        with open(file_path, 'rb') as f:
                            header = f.read(4)
                        
                        if header.startswith(b'\xff\xd8'):
                            print("   ✅ Valid JPEG generated!")
                            return True
                        else:
                            print(f"   ❌ Invalid JPEG header: {header.hex()}")
                            return False
                    else:
                        print("   ❌ JPEG file not created")
                        return False
                else:
                    print(f"   ❌ Capture failed: {result.get('error', 'Unknown error')}")
                    return False
            else:
                print("   ❌ No capture results")
                return False
                
        except Exception as e:
            print(f"   ❌ JPEG generation error: {e}")
            return False
        
        finally:
            # Cleanup
            if test_output_dir.exists():
                for file in test_output_dir.glob("*"):
                    file.unlink()
                test_output_dir.rmdir()
        
    except Exception as e:
        print(f"   ❌ JPEG test error: {e}")
        return False
    finally:
        if os.path.exists(config_file):
            os.unlink(config_file)


async def main():
    """Run quick integration tests"""
    print("🧪 Quick Integration Test - Testing Fixes")
    print("=" * 50)
    
    # Test 1: FluidNC Connection
    fluidnc_success = await test_fluidnc_connection()
    
    # Test 2: Mock Camera JPEG Generation
    jpeg_success = await test_mock_camera_jpeg()
    
    # Results Summary
    print("\n📊 Test Results Summary")
    print("=" * 30)
    print(f"   FluidNC Connection: {'✅ PASS' if fluidnc_success else '❌ FAIL'}")
    print(f"   JPEG Generation:    {'✅ PASS' if jpeg_success else '❌ FAIL'}")
    
    if fluidnc_success and jpeg_success:
        print("\n🎉 All tests passed! Fixes are working correctly.")
    else:
        print("\n⚠️  Some issues remain - check logs for details")


if __name__ == "__main__":
    asyncio.run(main())