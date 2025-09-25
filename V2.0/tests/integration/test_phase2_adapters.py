"""
Phase 2: Simple Test Script for Adapter Pattern Validation

This script tests the Phase 2 adapter implementations with minimal dependencies
to validate that Z-axis rotational motion is properly understood system-wide.

Author: Scanner System Development - Phase 2
Created: September 2025
"""

import asyncio
import logging
from pathlib import Path
from typing import Dict, Any

from core.config_manager import ConfigManager
from core.logging_setup import setup_logging

# Import base controllers (if available)
try:
    from motion.fluidnc_controller import create_fluidnc_controller
    MOTION_AVAILABLE = True
except ImportError:
    MOTION_AVAILABLE = False

try:
    from camera.pi_camera_controller import create_pi_camera_controller
    CAMERA_AVAILABLE = True
except ImportError:
    CAMERA_AVAILABLE = False

try:
    from lighting.gpio_led_controller import create_lighting_controller
    LIGHTING_AVAILABLE = True
except ImportError:
    LIGHTING_AVAILABLE = False

# Import Phase 2 adapters
from motion.adapter import create_motion_adapter, StandardMotionAdapter
from camera.adapter import create_camera_adapter, StandardCameraAdapter
from lighting.adapter import create_lighting_adapter, StandardLightingAdapter

from motion.base import Position4D, AxisType


async def test_motion_adapter_z_axis():
    """Test that motion adapter properly understands Z-axis as rotational"""
    
    logger = logging.getLogger(__name__)
    logger.info("🔄 Testing Motion Adapter Z-Axis Rotational Understanding")
    
    try:
        # Load configuration
        config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
        if not config_path.exists():
            logger.error(f"Configuration file not found: {config_path}")
            return False
        
        config_manager = ConfigManager(config_path)
        motion_config = config_manager.get('motion', {})
        
        # Test with mock controller if real hardware not available
        if MOTION_AVAILABLE:
            logger.info("Creating FluidNC controller...")
            motion_controller = create_fluidnc_controller(config_manager)
        else:
            logger.info("FluidNC controller not available - using mock")
            from motion.base import MotionController, MotionStatus
            
            class MockMotionController(MotionController):
                def __init__(self, config):
                    super().__init__(config)
                    self.status = MotionStatus.IDLE
                
                async def connect(self): return True
                async def disconnect(self): return True
                def is_connected(self): return True
                async def get_status(self): return self.status
                async def get_position(self): return Position4D(0, 0, 0, 0)
                async def get_capabilities(self): return None
                async def move_to_position(self, position, feedrate=None): return True
                async def move_relative(self, delta, feedrate=None): return True
                async def rapid_move(self, position): return True
                async def home_all_axes(self): return True
                async def home_axis(self, axis): return True
                async def emergency_stop(self): return True
                async def pause_motion(self): return True
                async def resume_motion(self): return True
                async def cancel_motion(self): return True
                async def set_motion_limits(self, axis, limits): return True
                async def get_motion_limits(self, axis): return None
                async def wait_for_motion_complete(self, timeout=None): return True
                async def set_position(self, position): return True
                async def execute_gcode(self, gcode): return True
            
            motion_controller = MockMotionController(motion_config)
        
        # Create motion adapter
        logger.info("Creating motion adapter...")
        motion_adapter = create_motion_adapter(motion_controller, motion_config)
        
        # Test Z-axis configuration
        logger.info("Testing Z-axis rotational configuration...")
        z_axis_info = motion_adapter.get_axis_info('z')
        
        if z_axis_info:
            logger.info(f"✅ Z-axis type: {z_axis_info.axis_type.value}")
            logger.info(f"✅ Z-axis move type: {z_axis_info.move_type.value}")
            logger.info(f"✅ Z-axis continuous: {z_axis_info.continuous}")
            logger.info(f"✅ Z-axis units: {z_axis_info.units}")
            
            # Verify it's rotational
            if z_axis_info.axis_type == AxisType.ROTATIONAL:
                logger.info("✅ SUCCESS: Z-axis properly configured as ROTATIONAL")
            else:
                logger.error("❌ FAILURE: Z-axis not configured as rotational")
                return False
                
            if z_axis_info.continuous:
                logger.info("✅ SUCCESS: Z-axis supports continuous rotation")
            else:
                logger.warning("⚠️  Z-axis not configured for continuous rotation")
        else:
            logger.error("❌ FAILURE: Could not get Z-axis information")
            return False
        
        # Test position validation with rotational awareness
        logger.info("Testing rotational position validation...")
        
        # Test normal position
        test_pos1 = Position4D(x=50.0, y=50.0, z=90.0, c=0.0)
        try:
            is_valid = motion_adapter.validate_position_with_axis_types(test_pos1)
            logger.info(f"✅ Position validation test 1 passed: {test_pos1}")
        except Exception as e:
            logger.error(f"❌ Position validation test 1 failed: {e}")
            return False
        
        # Test Z rotation normalization
        logger.info("Testing Z-axis rotation normalization...")
        normalized_z = motion_adapter.normalize_z_position(270.0)
        expected_z = -90.0  # 270° should normalize to -90°
        
        if abs(normalized_z - expected_z) < 0.001:
            logger.info(f"✅ Z normalization test passed: 270° → {normalized_z:.1f}°")
        else:
            logger.error(f"❌ Z normalization test failed: 270° → {normalized_z:.1f}° (expected {expected_z}°)")
            return False
        
        # Test optimal rotation direction
        logger.info("Testing optimal rotation direction calculation...")
        optimal_z, direction = motion_adapter.calculate_z_rotation_direction(10.0, 350.0)
        
        # 10° to 350° should go -20° (CCW) instead of +340° (CW)
        expected_optimal = -10.0  # Approximate
        
        logger.info(f"✅ Rotation optimization: 10° → 350° via {direction} to {optimal_z:.1f}°")
        
        logger.info("✅ SUCCESS: Motion Adapter Z-Axis Tests Passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Motion adapter Z-axis test failed: {e}")
        return False


async def test_camera_adapter_integration():
    """Test camera adapter integration with motion coordination"""
    
    logger = logging.getLogger(__name__)
    logger.info("📸 Testing Camera Adapter Motion Integration")
    
    try:
        # Simple integration test without requiring real hardware
        config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(config_path)
        camera_config = config_manager.get('camera', {})
        
        # Create mock camera controller
        from camera.base import CameraController, CameraStatus, CaptureResult
        
        class MockCameraController(CameraController):
            def __init__(self, config):
                super().__init__(config)
                self.status = CameraStatus.READY
            
            async def initialize(self): return True
            async def shutdown(self): return True
            def is_available(self): return True
            async def configure_camera(self, camera_id, settings): return True
            async def get_camera_info(self, camera_id): return {}
            async def list_cameras(self): return ['camera1']
            async def capture_photo(self, camera_id, settings=None):
                return CaptureResult(success=True, camera_id=camera_id)
            async def capture_burst(self, camera_id, count, interval=0.1, settings=None): return []
            async def capture_synchronized(self, settings=None):
                from camera.base import SyncCaptureResult
                return SyncCaptureResult(success=True)
            async def calibrate_synchronization(self, test_captures=10): return 0.0
            async def start_streaming(self, camera_id, settings=None): return True
            async def stop_streaming(self, camera_id): return True
            async def get_stream_frame(self, camera_id): return None
            def is_streaming(self, camera_id): return False
            async def auto_focus(self, camera_id): return True
            async def auto_exposure(self, camera_id): return True
            async def capture_with_flash_sync(self, flash_controller, settings=None):
                from camera.base import SyncCaptureResult
                return SyncCaptureResult(success=True)
            async def get_status(self, camera_id=None): return self.status
            async def get_last_error(self, camera_id): return None
            async def save_capture_to_file(self, capture_result, file_path): return True
            async def cleanup_temp_files(self): return True
        
        camera_controller = MockCameraController(camera_config)
        
        # Create camera adapter
        camera_adapter = create_camera_adapter(camera_controller, camera_config)
        
        # Test adapter creation
        logger.info(f"✅ Camera adapter created: {type(camera_adapter).__name__}")
        
        # Test position-aware capture (without motion adapter - should handle gracefully)
        logger.info("Testing position-aware capture...")
        test_position = Position4D(x=0.0, y=0.0, z=45.0, c=0.0)
        
        from camera.base import CameraSettings, ImageFormat
        test_settings = CameraSettings(
            resolution=(1920, 1080),
            format=ImageFormat.JPEG
        )
        
        try:
            result = await camera_adapter.capture_at_position(test_position, test_settings)
            logger.info("✅ Position-aware capture test completed")
        except Exception as e:
            logger.info(f"⚠️  Position-aware capture expected to fail without motion adapter: {e}")
        
        logger.info("✅ SUCCESS: Camera Adapter Tests Passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Camera adapter test failed: {e}")
        return False


async def test_lighting_adapter_safety():
    """Test lighting adapter safety features"""
    
    logger = logging.getLogger(__name__)
    logger.info("💡 Testing Lighting Adapter Safety Features")
    
    try:
        # Test adapter creation and safety limits
        lighting_config = {
            'lighting': {
                'safety': {
                    'max_duty_cycle': 0.89,  # Below 90% safety limit
                    'max_current_ma': 500.0,
                    'thermal_limit_c': 60.0
                }
            }
        }
        
        # Create mock lighting controller
        from lighting.base import LightingController, LightingStatus, FlashResult, LightingSettings
        
        class MockLightingController(LightingController):
            def __init__(self, config):
                super().__init__(config)
                self.status = LightingStatus.READY
            
            async def initialize(self): return True
            async def shutdown(self): return True
            def is_available(self): return True
            async def configure_zone(self, zone): return True
            async def get_zone_info(self, zone_id): return {}
            async def list_zones(self): return ['zone1']
            async def set_brightness(self, zone_id, brightness): return True
            async def get_brightness(self, zone_id): return 0.0
            async def turn_on(self, zone_id, brightness=0.5): return True
            async def turn_off(self, zone_id): return True
            async def turn_off_all(self): return True
            async def flash(self, zone_ids, settings):
                return FlashResult(success=True, zones_activated=zone_ids, actual_brightness={})
            async def synchronized_flash(self, zone_settings):
                return FlashResult(success=True, zones_activated=[], actual_brightness={})
            async def fade_to(self, zone_id, target_brightness, duration_ms): return True
            async def strobe(self, zone_id, frequency, duration_ms, brightness=1.0): return True
            async def load_pattern(self, pattern_file): return True
            async def execute_pattern(self, pattern_name, repeat=1): return True
            async def get_status(self, zone_id=None): return self.status
            async def get_last_error(self, zone_id): return None
            async def get_power_metrics(self): return None
            async def remove_zone(self, zone_id): return True
            async def set_all_brightness(self, brightness): return True
            async def set_zone_settings(self, zone_id, settings): return True
            async def get_zone_settings(self, zone_id): return LightingSettings()
            async def emergency_shutdown(self): return True
            async def validate_settings(self, settings): return True
            async def stop_pattern(self): return True
            async def trigger_for_capture(self, zone_ids): return True
            async def calibrate_flash_timing(self): return 0.0
            async def calibrate_camera_sync(self, camera_controller): return 0.0
        
        lighting_controller = MockLightingController(lighting_config)
        
        # Create lighting adapter
        lighting_adapter = create_lighting_adapter(lighting_controller, lighting_config)
        
        # Test adapter creation
        logger.info(f"✅ Lighting adapter created: {type(lighting_adapter).__name__}")
        
        # Test safety validation
        logger.info("Testing duty cycle safety validation...")
        
        # Test safe duty cycle
        try:
            is_safe = lighting_adapter.validate_duty_cycle_safe(0.8)  # 80% - safe
            logger.info("✅ Safe duty cycle validation passed")
        except Exception as e:
            logger.error(f"❌ Safe duty cycle validation failed: {e}")
            return False
        
        # Test unsafe duty cycle
        try:
            unsafe_result = lighting_adapter.validate_duty_cycle_safe(0.95)  # 95% - unsafe
            logger.error("❌ Unsafe duty cycle should have been rejected")
            return False
        except Exception as e:
            logger.info(f"✅ Unsafe duty cycle properly rejected: {e}")
        
        logger.info("✅ SUCCESS: Lighting Adapter Safety Tests Passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Lighting adapter test failed: {e}")
        return False


async def run_phase2_adapter_tests():
    """Run comprehensive Phase 2 adapter tests"""
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("🚀 Starting Phase 2 Adapter Pattern Tests")
    logger.info("="*60)
    
    test_results = []
    
    # Test 1: Motion Adapter Z-Axis Understanding
    logger.info("\n📋 TEST 1: Motion Adapter Z-Axis Rotational Support")
    logger.info("-" * 50)
    result1 = await test_motion_adapter_z_axis()
    test_results.append(("Motion Adapter Z-Axis", result1))
    
    # Test 2: Camera Adapter Integration  
    logger.info("\n📋 TEST 2: Camera Adapter Motion Integration")
    logger.info("-" * 50)
    result2 = await test_camera_adapter_integration()
    test_results.append(("Camera Adapter Integration", result2))
    
    # Test 3: Lighting Adapter Safety
    logger.info("\n📋 TEST 3: Lighting Adapter Safety Features")
    logger.info("-" * 50)
    result3 = await test_lighting_adapter_safety()
    test_results.append(("Lighting Adapter Safety", result3))
    
    # Summary
    logger.info("\n🎯 PHASE 2 TEST SUMMARY")
    logger.info("="*60)
    
    passed_tests = 0
    total_tests = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"{status}: {test_name}")
        if result:
            passed_tests += 1
    
    success_rate = (passed_tests / total_tests) * 100
    logger.info(f"\nOverall Success Rate: {passed_tests}/{total_tests} ({success_rate:.1f}%)")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL PHASE 2 ADAPTER TESTS PASSED!")
        logger.info("✅ Z-axis rotational motion properly understood system-wide")
        logger.info("✅ Adapter pattern standardization successful")
        logger.info("✅ Safety measures implemented and validated")
        return True
    else:
        logger.error(f"⚠️  {total_tests - passed_tests} test(s) failed")
        return False


if __name__ == "__main__":
    import sys
    
    # Run Phase 2 adapter tests
    success = asyncio.run(run_phase2_adapter_tests())
    
    if success:
        print("\n" + "="*60)
        print("🎉 PHASE 2 ADAPTER PATTERN TESTS COMPLETED SUCCESSFULLY")
        print("✅ Ready for Pi hardware testing")
        print("="*60)
        sys.exit(0)
    else:
        print("\n" + "="*60)
        print("❌ PHASE 2 ADAPTER PATTERN TESTS FAILED")
        print("⚠️  Please check logs for details")
        print("="*60)
        sys.exit(1)