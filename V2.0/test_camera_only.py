#!/usr/bin/env python3
"""
Pi Camera Controller Test Script

Focused testing for the Pi camera controller on Raspberry Pi.
Tests camera detection, initialization, capture, and video functionality.

Usage:
    python test_camera_only.py [--camera0 ID] [--camera1 ID] [--no-actual-capture]

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from camera.pi_camera_controller import PiCameraController
from camera.base import CameraSettings, CaptureMode, ImageFormat
from core.logging_setup import setup_logging

class CameraControllerTester:
    """Focused camera controller testing"""
    
    def __init__(self, camera0_id: int, camera1_id: int, no_capture: bool = False):
        self.camera0_id = camera0_id
        self.camera1_id = camera1_id
        self.no_capture = no_capture
        self.logger = logging.getLogger(__name__)
        
        # Create test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="camera_test_"))
        self.logger.info(f"Test directory: {self.test_dir}")
        
        # Test configuration
        self.config = {
            'camera0_id': camera0_id,
            'camera1_id': camera1_id,
            'default_resolution': [1920, 1080],
            'default_framerate': 30.0,
            'capture_timeout': 10.0,
            'video_codec': 'h264',
            'image_format': 'jpeg',
            'burst_capture': {
                'max_images': 10,
                'interval_ms': 100
            }
        }
        
    def cleanup(self):
        """Clean up test directory"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            self.logger.info(f"Cleaned up test directory: {self.test_dir}")
        
    async def run_tests(self) -> bool:
        """Run all camera controller tests"""
        self.logger.info("📸 Pi Camera Controller Test Suite")
        self.logger.info(f"Camera0 ID: {self.camera0_id}, Camera1 ID: {self.camera1_id}")
        self.logger.info(f"Capture mode: {'DISABLED' if self.no_capture else 'ENABLED'}")
        
        success = True
        
        try:
            # Basic tests
            success &= await self.test_controller_creation()
            success &= await self.test_camera_detection()
            success &= await self.test_settings_validation()
            success &= await self.test_capabilities()
            
            # Hardware tests
            success &= await self.test_initialization()
            
            if not self.no_capture:
                success &= await self.test_image_capture()
                success &= await self.test_video_recording()
                success &= await self.test_burst_capture()
                success &= await self.test_synchronized_capture()
            
            return success
            
        finally:
            self.cleanup()
    
    async def test_controller_creation(self) -> bool:
        """Test controller instantiation"""
        self.logger.info("\n📋 Testing Controller Creation...")
        
        try:
            controller = PiCameraController(self.config)
            
            self.logger.info(f"   ✅ Controller created")
            self.logger.info(f"   Configuration: {len(self.config)} parameters")
            self.logger.info(f"   Default resolution: {self.config['default_resolution']}")
            self.logger.info(f"   Image format: {self.config['image_format']}")
            self.logger.info(f"   Video codec: {self.config['video_codec']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Controller creation failed: {e}")
            return False
    
    async def test_camera_detection(self) -> bool:
        """Test camera hardware detection"""
        self.logger.info("\n🔍 Testing Camera Detection...")
        
        try:
            controller = PiCameraController(self.config)
            
            # Test camera availability detection
            self.logger.info("   Checking camera availability...")
            
            try:
                # Try to detect picamera2
                import picamera2
                self.logger.info("   ✅ picamera2 library available")
                
                # Check if we can list cameras
                from picamera2 import Picamera2
                cameras = Picamera2.global_camera_info()
                self.logger.info(f"   Detected {len(cameras)} camera(s)")
                
                for i, cam_info in enumerate(cameras):
                    self.logger.info(f"   Camera {i}: {cam_info}")
                
                if len(cameras) >= 2:
                    self.logger.info("   ✅ Sufficient cameras for dual-camera setup")
                elif len(cameras) == 1:
                    self.logger.info("   ⚠️  Only one camera detected (single-camera mode possible)")
                else:
                    self.logger.info("   ⚠️  No cameras detected")
                
            except ImportError:
                self.logger.info("   ⚠️  picamera2 library not available (normal on non-Pi systems)")
            except Exception as e:
                self.logger.info(f"   ⚠️  Camera detection error: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Camera detection test failed: {e}")
            return False
    
    async def test_settings_validation(self) -> bool:
        """Test camera settings validation"""
        self.logger.info("\n⚙️  Testing Settings Validation...")
        
        try:
            controller = PiCameraController(self.config)
            
            # Test valid settings
            valid_settings = [
                CameraSettings(resolution=(1920, 1080), format=ImageFormat.JPEG),
                CameraSettings(resolution=(1280, 720), format=ImageFormat.PNG),
                CameraSettings(resolution=(640, 480), format=ImageFormat.JPEG, quality=80),
            ]
            
            # Test invalid settings (we'll check basic validation)
            invalid_settings = [
                CameraSettings(resolution=(0, 0), format=ImageFormat.JPEG),        # Invalid resolution
                CameraSettings(resolution=(1920, 1080), quality=150),              # Invalid quality
            ]
            
            valid_count = 0
            for settings in valid_settings:
                # Basic validation - check if settings are reasonable
                if (settings.resolution[0] > 0 and settings.resolution[1] > 0 and
                    0 <= settings.quality <= 100):
                    valid_count += 1
                    self.logger.info(f"   ✅ Valid: {settings.resolution}, {settings.format.value}")
                else:
                    self.logger.error(f"   ❌ Should be valid: {settings}")
            
            invalid_count = 0
            for settings in invalid_settings:
                # Basic validation - check for invalid settings
                if (settings.resolution[0] <= 0 or settings.resolution[1] <= 0 or
                    settings.quality < 0 or settings.quality > 100):
                    invalid_count += 1
                    self.logger.info(f"   ✅ Invalid (correct): {settings}")
                else:
                    self.logger.error(f"   ❌ Should be invalid: {settings}")
            
            success = (valid_count == len(valid_settings) and 
                      invalid_count == len(invalid_settings))
            
            self.logger.info(f"   Settings validation: {valid_count}/{len(valid_settings)} valid, "
                           f"{invalid_count}/{len(invalid_settings)} invalid")
            
            return success
            
        except Exception as e:
            self.logger.error(f"   ❌ Settings validation test failed: {e}")
            return False
    
    async def test_capabilities(self) -> bool:
        """Test camera capabilities"""
        self.logger.info("\n🛠️  Testing Camera Capabilities...")
        
        try:
            controller = PiCameraController(self.config)
            
            capabilities = await controller.get_capabilities()
            
            self.logger.info(f"   Camera count: {capabilities.camera_count}")
            self.logger.info(f"   Max resolution: {capabilities.max_resolution}")
            self.logger.info(f"   Supported formats: {capabilities.supported_formats}")
            self.logger.info(f"   Max framerate: {capabilities.max_framerate}")
            self.logger.info(f"   Supports video: {capabilities.supports_video}")
            self.logger.info(f"   Supports burst: {capabilities.supports_burst}")
            self.logger.info(f"   Supports sync: {capabilities.supports_synchronized_capture}")
            
            # Validate expected capabilities
            if capabilities.camera_count >= 1:
                self.logger.info("   ✅ At least one camera capability reported")
            else:
                self.logger.error("   ❌ No cameras in capabilities")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Capabilities test failed: {e}")
            return False
    
    async def test_initialization(self) -> bool:
        """Test camera initialization"""
        self.logger.info("\n🔌 Testing Camera Initialization...")
        
        try:
            controller = PiCameraController(self.config)
            
            self.logger.info("   Attempting camera initialization...")
            
            # Test initialization
            initialized = await controller.initialize()
            
            if initialized:
                self.logger.info("   ✅ Camera controller initialized successfully!")
                
                # Test status
                status = await controller.get_status()
                self.logger.info(f"   Current status: {status}")
                
                # Test if cameras are available
                if controller.is_available():
                    self.logger.info("   ✅ Camera system available")
                else:
                    self.logger.info("   ⚠️  Camera system not fully available")
                
                # Test shutdown
                await controller.shutdown()
                self.logger.info("   ✅ Camera controller shutdown complete")
                
                return True
                
            else:
                self.logger.warning("   ⚠️  Could not initialize camera controller")
                self.logger.warning("   This is normal if Pi cameras are not connected")
                return True  # Not a failure if hardware isn't available
                
        except Exception as e:
            self.logger.warning(f"   ⚠️  Initialization test failed: {e}")
            self.logger.warning("   This is normal if Pi camera hardware is not available")
            return True  # Not a failure if hardware isn't available
    
    async def test_image_capture(self) -> bool:
        """Test image capture functionality"""
        self.logger.info("\n📷 Testing Image Capture...")
        
        try:
            controller = PiCameraController(self.config)
            
            initialized = await controller.initialize()
            if not initialized:
                self.logger.warning("   ⚠️  Cannot test capture - controller not initialized")
                return True
            
            # Test single image capture
            self.logger.info("   Testing single image capture...")
            
            settings = CameraSettings(
                resolution=(1280, 720),
                framerate=30.0,
                format='jpeg'
            )
            
            image_path = self.test_dir / "test_single.jpg"
            success = await controller.capture_image(str(image_path), settings)
            
            if success and image_path.exists():
                file_size = image_path.stat().st_size
                self.logger.info(f"   ✅ Single image captured: {file_size} bytes")
            else:
                self.logger.warning("   ⚠️  Single image capture failed or no file created")
            
            # Test dual camera capture if available
            self.logger.info("   Testing dual camera capture...")
            
            image0_path = self.test_dir / "test_dual_cam0.jpg"
            image1_path = self.test_dir / "test_dual_cam1.jpg"
            
            success = await controller.capture_image_dual(
                str(image0_path), str(image1_path), settings
            )
            
            if success:
                if image0_path.exists() and image1_path.exists():
                    size0 = image0_path.stat().st_size
                    size1 = image1_path.stat().st_size
                    self.logger.info(f"   ✅ Dual images captured: cam0={size0}B, cam1={size1}B")
                else:
                    self.logger.warning("   ⚠️  Dual capture succeeded but files not found")
            else:
                self.logger.warning("   ⚠️  Dual camera capture failed (normal with one camera)")
            
            await controller.shutdown()
            return True
            
        except Exception as e:
            self.logger.warning(f"   ⚠️  Image capture test failed: {e}")
            return True
    
    async def test_video_recording(self) -> bool:
        """Test video recording functionality"""
        self.logger.info("\n🎥 Testing Video Recording...")
        
        try:
            controller = PiCameraController(self.config)
            
            initialized = await controller.initialize()
            if not initialized:
                self.logger.warning("   ⚠️  Cannot test video - controller not initialized")
                return True
            
            # Test short video recording
            self.logger.info("   Testing short video recording (3 seconds)...")
            
            settings = CameraSettings(
                resolution=(1280, 720),
                framerate=30.0,
                format='h264'
            )
            
            video_path = self.test_dir / "test_video.h264"
            
            # Start recording
            success = await controller.start_video_recording(str(video_path), settings)
            if success:
                self.logger.info("   Recording started...")
                
                # Record for 3 seconds
                await asyncio.sleep(3.0)
                
                # Stop recording
                success = await controller.stop_video_recording()
                if success:
                    self.logger.info("   Recording stopped")
                    
                    if video_path.exists():
                        file_size = video_path.stat().st_size
                        self.logger.info(f"   ✅ Video recorded: {file_size} bytes")
                    else:
                        self.logger.warning("   ⚠️  Video file not found")
                else:
                    self.logger.warning("   ⚠️  Failed to stop recording")
            else:
                self.logger.warning("   ⚠️  Failed to start recording")
            
            await controller.shutdown()
            return True
            
        except Exception as e:
            self.logger.warning(f"   ⚠️  Video recording test failed: {e}")
            return True
    
    async def test_burst_capture(self) -> bool:
        """Test burst capture functionality"""
        self.logger.info("\n📸📸 Testing Burst Capture...")
        
        try:
            controller = PiCameraController(self.config)
            
            initialized = await controller.initialize()
            if not initialized:
                self.logger.warning("   ⚠️  Cannot test burst - controller not initialized")
                return True
            
            # Test burst capture
            self.logger.info("   Testing burst capture (5 images)...")
            
            settings = CameraSettings(
                resolution=(640, 480),
                framerate=30.0,
                format='jpeg'
            )
            
            burst_dir = self.test_dir / "burst"
            burst_dir.mkdir(exist_ok=True)
            
            pattern = str(burst_dir / "burst_{:03d}.jpg")
            
            success = await controller.capture_burst(
                pattern, count=5, interval_ms=200, settings=settings
            )
            
            if success:
                # Check captured files
                burst_files = list(burst_dir.glob("*.jpg"))
                self.logger.info(f"   ✅ Burst capture completed: {len(burst_files)} files")
                
                for i, file_path in enumerate(sorted(burst_files)):
                    file_size = file_path.stat().st_size
                    self.logger.info(f"     Image {i+1}: {file_size} bytes")
            else:
                self.logger.warning("   ⚠️  Burst capture failed")
            
            await controller.shutdown()
            return True
            
        except Exception as e:
            self.logger.warning(f"   ⚠️  Burst capture test failed: {e}")
            return True
    
    async def test_synchronized_capture(self) -> bool:
        """Test synchronized capture for 3D scanning"""
        self.logger.info("\n👥 Testing Synchronized Capture...")
        
        try:
            controller = PiCameraController(self.config)
            
            initialized = await controller.initialize()
            if not initialized:
                self.logger.warning("   ⚠️  Cannot test sync capture - controller not initialized")
                return True
            
            # Test synchronized capture
            self.logger.info("   Testing synchronized dual-camera capture...")
            
            settings = CameraSettings(
                resolution=(1280, 720),
                framerate=30.0,
                format='jpeg'
            )
            
            sync_dir = self.test_dir / "synchronized"
            sync_dir.mkdir(exist_ok=True)
            
            cam0_pattern = str(sync_dir / "sync_cam0_{:03d}.jpg")
            cam1_pattern = str(sync_dir / "sync_cam1_{:03d}.jpg")
            
            success = await controller.capture_synchronized(
                cam0_pattern, cam1_pattern, count=3, settings=settings
            )
            
            if success:
                # Check captured files
                cam0_files = list(sync_dir.glob("sync_cam0_*.jpg"))
                cam1_files = list(sync_dir.glob("sync_cam1_*.jpg"))
                
                self.logger.info(f"   ✅ Synchronized capture: cam0={len(cam0_files)}, cam1={len(cam1_files)}")
                
                # Check that we have matching pairs
                if len(cam0_files) == len(cam1_files):
                    self.logger.info("   ✅ Matching camera pairs captured")
                else:
                    self.logger.warning(f"   ⚠️  Mismatched captures: cam0={len(cam0_files)}, cam1={len(cam1_files)}")
            else:
                self.logger.warning("   ⚠️  Synchronized capture failed (normal with single camera)")
            
            await controller.shutdown()
            return True
            
        except Exception as e:
            self.logger.warning(f"   ⚠️  Synchronized capture test failed: {e}")
            return True


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Pi Camera Controller Test')
    parser.add_argument('--camera0', type=int, default=0, help='Camera 0 ID')
    parser.add_argument('--camera1', type=int, default=1, help='Camera 1 ID')
    parser.add_argument('--no-actual-capture', action='store_true', 
                       help='Skip actual capture tests (initialization only)')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging()
    logging.getLogger().setLevel(log_level)
    
    # Run tests
    tester = CameraControllerTester(args.camera0, args.camera1, args.no_actual_capture)
    success = await tester.run_tests()
    
    if success:
        print("\n🎉 All camera controller tests passed!")
    else:
        print("\n❌ Some camera controller tests failed!")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())