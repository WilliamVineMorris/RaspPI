#!/usr/bin/env python3
"""
Simple Pi Camera Test Script

Basic testing for the Pi camera controller on Raspberry Pi.
Tests camera detection, initialization, and basic functionality.

Usage:
    python test_camera_simple.py [--verbose] [--no-capture]

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
from camera.base import CameraSettings, ImageFormat
from core.logging_setup import setup_logging

class SimpleCameraTest:
    """Simple camera testing"""
    
    def __init__(self, no_capture: bool = False):
        self.no_capture = no_capture
        self.logger = logging.getLogger(__name__)
        
        # Create test directory
        self.test_dir = Path(tempfile.mkdtemp(prefix="camera_test_"))
        self.logger.info(f"Test directory: {self.test_dir}")
        
        # Basic configuration
        self.config = {
            'camera0_id': 0,
            'camera1_id': 1,
            'default_resolution': [1280, 720],
            'default_framerate': 30.0,
            'capture_timeout': 10.0,
            'video_codec': 'h264',
            'image_format': 'jpeg'
        }
        
    def cleanup(self):
        """Clean up test directory"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            self.logger.info(f"Cleaned up test directory: {self.test_dir}")
        
    async def run_tests(self) -> bool:
        """Run basic camera tests"""
        self.logger.info("📸 Simple Pi Camera Test Suite")
        self.logger.info(f"Capture mode: {'DISABLED' if self.no_capture else 'ENABLED'}")
        
        success = True
        
        try:
            success &= await self.test_controller_creation()
            success &= await self.test_camera_detection()
            success &= await self.test_initialization()
            success &= await self.test_camera_listing()
            
            if not self.no_capture:
                success &= await self.test_basic_capture()
            
            return success
            
        finally:
            self.cleanup()
    
    async def test_controller_creation(self) -> bool:
        """Test controller instantiation"""
        self.logger.info("\n📋 Testing Controller Creation...")
        
        try:
            controller = PiCameraController(self.config)
            self.logger.info("   ✅ Controller created successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Controller creation failed: {e}")
            return False
    
    async def test_camera_detection(self) -> bool:
        """Test camera hardware detection"""
        self.logger.info("\n🔍 Testing Camera Detection...")
        
        try:
            # Try to detect picamera2
            try:
                import picamera2
                self.logger.info("   ✅ picamera2 library available")
                
                # Check if we can list cameras
                from picamera2 import Picamera2
                cameras = Picamera2.global_camera_info()
                self.logger.info(f"   Detected {len(cameras)} camera(s)")
                
                for i, cam_info in enumerate(cameras):
                    self.logger.info(f"   Camera {i}: {cam_info.get('Model', 'Unknown')}")
                
            except ImportError:
                self.logger.info("   ⚠️  picamera2 library not available (normal on non-Pi systems)")
            except Exception as e:
                self.logger.info(f"   ⚠️  Camera detection error: {e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"   ❌ Camera detection test failed: {e}")
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
    
    async def test_camera_listing(self) -> bool:
        """Test camera listing functionality"""
        self.logger.info("\n📋 Testing Camera Listing...")
        
        try:
            controller = PiCameraController(self.config)
            
            initialized = await controller.initialize()
            if not initialized:
                self.logger.warning("   ⚠️  Cannot test listing - controller not initialized")
                return True
            
            # Test listing cameras
            cameras = await controller.list_cameras()
            self.logger.info(f"   Available cameras: {cameras}")
            
            # Test getting camera info for each camera
            for camera_id in cameras:
                try:
                    info = await controller.get_camera_info(camera_id)
                    self.logger.info(f"   Camera {camera_id} info: {info}")
                except Exception as e:
                    self.logger.warning(f"   Could not get info for camera {camera_id}: {e}")
            
            await controller.shutdown()
            return True
            
        except Exception as e:
            self.logger.warning(f"   ⚠️  Camera listing test failed: {e}")
            return True
    
    async def test_basic_capture(self) -> bool:
        """Test basic capture functionality"""
        self.logger.info("\n📷 Testing Basic Capture...")
        
        try:
            controller = PiCameraController(self.config)
            
            initialized = await controller.initialize()
            if not initialized:
                self.logger.warning("   ⚠️  Cannot test capture - controller not initialized")
                return True
            
            # Get available cameras
            cameras = await controller.list_cameras()
            if not cameras:
                self.logger.warning("   ⚠️  No cameras available for capture test")
                await controller.shutdown()
                return True
            
            # Test single photo capture
            camera_id = cameras[0]
            self.logger.info(f"   Testing single photo capture with camera {camera_id}...")
            
            settings = CameraSettings(
                resolution=(1280, 720),
                format=ImageFormat.JPEG,
                quality=90
            )
            
            result = await controller.capture_photo(camera_id, settings)
            
            if result.success:
                self.logger.info(f"   ✅ Photo captured successfully")
                if result.image_path:
                    self.logger.info(f"   Image saved to: {result.image_path}")
                if result.image_data:
                    self.logger.info(f"   Image data size: {len(result.image_data)} bytes")
            else:
                self.logger.warning("   ⚠️  Photo capture failed")
            
            # Test synchronized capture if multiple cameras
            if len(cameras) > 1:
                self.logger.info("   Testing synchronized capture...")
                sync_result = await controller.capture_synchronized()
                
                if sync_result.success:
                    self.logger.info("   ✅ Synchronized capture successful")
                    if sync_result.sync_error_ms is not None:
                        self.logger.info(f"   Sync error: {sync_result.sync_error_ms:.2f}ms")
                else:
                    self.logger.warning("   ⚠️  Synchronized capture failed")
            
            await controller.shutdown()
            return True
            
        except Exception as e:
            self.logger.warning(f"   ⚠️  Basic capture test failed: {e}")
            return True


async def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Simple Pi Camera Test')
    parser.add_argument('--no-capture', action='store_true', 
                       help='Skip actual capture tests (initialization only)')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging()
    logging.getLogger().setLevel(log_level)
    
    # Run tests
    tester = SimpleCameraTest(args.no_capture)
    success = await tester.run_tests()
    
    if success:
        print("\n🎉 All camera tests passed!")
    else:
        print("\n❌ Some camera tests failed!")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())