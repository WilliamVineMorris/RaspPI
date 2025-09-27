#!/usr/bin/env python3
"""
Test script to verify scan template synchronization fixes
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the V2.0 directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.types import Position4D, CameraSettings
from scanning.scan_patterns import CylindricalScanPattern, CylindricalScanParameters
from scanning.scan_orchestrator import ScanOrchestrator
from camera.pi_camera_controller import PiCameraController
from motion.mock_motion_controller import MockMotionController
from storage.mock_storage_manager import MockStorageManager
from core.config_manager import ConfigManager

async def test_scan_template_synchronization():
    """Test that scan positions file contains actual calibrated values"""
    print("🧪 Testing Scan Template Synchronization Fix...")
    
    try:
        # Initialize components
        config_manager = ConfigManager()
        camera_controller = PiCameraController(config_manager)
        motion_controller = MockMotionController(config_manager)
        storage_manager = MockStorageManager(config_manager)
        
        # Create scan orchestrator
        orchestrator = ScanOrchestrator(
            camera_manager=camera_controller,
            motion_controller=motion_controller,
            storage_manager=storage_manager,
            config_manager=config_manager
        )
        
        # Create a simple cylindrical scan pattern
        params = CylindricalScanParameters(
            x_start=30.0, x_end=30.0, x_step=1.0,
            y_start=100, y_end=120, y_step=1.0,
            z_rotations=[0.0, 90.0],
            c_angles=[0.0]
        )
        
        pattern = CylindricalScanPattern(params)
        
        # Simulate calibrated camera settings (like what would be set during calibration)
        if hasattr(camera_controller, '_calibrated_settings'):
            camera_controller._calibrated_settings = {}
        else:
            camera_controller._calibrated_settings = {}
            
        camera_controller._calibrated_settings[0] = {
            'exposure_time': 32746,  # 1/30s in microseconds
            'analogue_gain': 8.0,    # ISO 800 equivalent
            'focus_value': 6.5,
            'brightness_score': 0.7
        }
        
        # Test the _get_actual_camera_settings method
        print("📸 Testing camera settings retrieval...")
        
        # Create a simple camera manager adapter for testing
        class TestCameraManager:
            def __init__(self, controller):
                self.controller = controller
        
        orchestrator.camera_manager = TestCameraManager(camera_controller)
        
        # Get actual camera settings
        actual_settings = await orchestrator._get_actual_camera_settings()
        
        print(f"✅ Actual camera settings retrieved:")
        print(f"   Exposure: {actual_settings['exposure_time']}")
        print(f"   ISO: {actual_settings['iso']}")
        print(f"   Resolution: {actual_settings['resolution']}")
        print(f"   Source: {actual_settings['calibration_source']}")
        
        # Verify the settings are correct
        assert actual_settings['exposure_time'] == '1/30s', f"Expected '1/30s', got {actual_settings['exposure_time']}"
        assert actual_settings['iso'] == 800, f"Expected 800, got {actual_settings['iso']}"
        assert actual_settings['resolution'] == [4608, 2592], f"Expected [4608, 2592], got {actual_settings['resolution']}"
        assert actual_settings['calibration_source'] == 'camera_calibrated', f"Expected 'camera_calibrated', got {actual_settings['calibration_source']}"
        
        # Test scan positions file generation
        print("📋 Testing scan positions file generation...")
        temp_dir = Path("/tmp/test_scan_positions")
        temp_dir.mkdir(exist_ok=True)
        
        positions_metadata = await orchestrator._generate_scan_positions_file(
            pattern, temp_dir, "test_scan_20250927"
        )
        
        # Verify scan positions metadata
        assert 'scan_info' in positions_metadata
        assert 'camera_settings_info' in positions_metadata['scan_info']
        assert positions_metadata['scan_info']['camera_settings_info']['settings_source'] == 'camera_calibrated'
        
        # Check first scan position
        first_position = positions_metadata['scan_positions'][0]
        camera_settings = first_position['camera_settings']
        
        assert camera_settings['exposure_time'] == '1/30s', f"Position file exposure incorrect: {camera_settings['exposure_time']}"
        assert camera_settings['iso'] == 800, f"Position file ISO incorrect: {camera_settings['iso']}"
        assert camera_settings['resolution'] == [4608, 2592], f"Position file resolution incorrect: {camera_settings['resolution']}"
        
        print("✅ Scan positions file generated correctly:")
        print(f"   Exposure: {camera_settings['exposure_time']}")
        print(f"   ISO: {camera_settings['iso']}")
        print(f"   Resolution: {camera_settings['resolution']}")
        print(f"   Source: {camera_settings['calibration_source']}")
        
        # Test with no calibration available
        print("🔄 Testing fallback when no calibration available...")
        del camera_controller._calibrated_settings
        
        fallback_settings = await orchestrator._get_actual_camera_settings()
        assert fallback_settings['calibration_source'] == 'no_calibration_available'
        assert fallback_settings['exposure_time'] == '1/30s'  # Sensible default
        assert fallback_settings['iso'] == 800  # Sensible default
        
        print("✅ Fallback settings work correctly:")
        print(f"   Source: {fallback_settings['calibration_source']}")
        
        # Check that positions file was actually written
        positions_file = temp_dir / "test_scan_20250927_scan_positions.json"
        assert positions_file.exists(), "Scan positions file was not created"
        
        print(f"📄 Scan positions file created: {positions_file}")
        
        # Clean up
        if positions_file.exists():
            positions_file.unlink()
        if temp_dir.exists():
            temp_dir.rmdir()
        
        print("\n🎉 All tests passed! Scan template synchronization fix is working correctly.")
        print("\n📋 Summary of improvements:")
        print("   ✅ Scan positions file now uses actual calibrated camera settings")
        print("   ✅ Resolution corrected to actual ArduCam 64MP values (4608x2592)")
        print("   ✅ Exposure and ISO values reflect real calibration results") 
        print("   ✅ Fallback to sensible defaults when calibration unavailable")
        print("   ✅ Metadata includes source information for traceability")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    success = await test_scan_template_synchronization()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())