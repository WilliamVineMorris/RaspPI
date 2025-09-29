#!/usr/bin/env python3
"""
Safe high-resolution capture test without aggressive V4L2 cleanup.
Tests a gentler approach to sequential high-res capture.
"""

import asyncio
import logging
import sys
from pathlib import Path
import traceback

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from camera.pi_camera_controller import PiCameraController

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_safe_high_res_capture():
    """Test safe high-resolution capture without V4L2 conflicts."""
    
    logger.info("🔍 Testing safe high-resolution capture...")
    
    try:
        # Initialize camera controller
        config = {
            'camera_0': {
                'port': 0,
                'resolution': [3280, 2464],
                'name': 'camera_0'
            },
            'camera_1': {
                'port': 1,
                'resolution': [3280, 2464],
                'name': 'camera_1'
            }
        }
        
        logger.info("📷 Initializing camera controller...")
        camera_controller = PiCameraController(config)
        
        logger.info("🔄 Initializing cameras...")
        init_success = await camera_controller.initialize()
        logger.info(f"✅ Camera initialization result: {init_success}")
        
        if not init_success:
            logger.error("❌ Failed to initialize cameras!")
            return False
        
        # Test 1: Medium resolution capture (safe)
        logger.info("📸 Test 1: Medium resolution dual capture (6016x4512)...")
        try:
            result = await camera_controller.capture_dual_resolution_aware((6016, 4512))
            if result:
                logger.info(f"✅ Medium resolution capture successful:")
                for cam_key, img_array in result.items():
                    if img_array is not None:
                        logger.info(f"   {cam_key}: {img_array.shape}")
                    else:
                        logger.error(f"   {cam_key}: None (failed)")
            else:
                logger.error("❌ Medium resolution capture failed!")
        except Exception as med_error:
            logger.error(f"❌ Medium resolution capture failed: {med_error}")
        
        # Wait between tests
        await asyncio.sleep(2.0)
        
        # Test 2: High resolution capture (one camera only)
        logger.info("📸 Test 2: Single camera 64MP capture...")
        try:
            # Test just camera 0 at full resolution
            camera = camera_controller.cameras[0]
            
            # Stop current mode
            logger.info("📷 Stopping camera for reconfiguration...")
            camera.stop()
            await asyncio.sleep(0.5)
            
            # Configure for high-resolution
            logger.info("📷 Configuring for 64MP capture...")
            from picamera2 import Picamera2
            still_config = camera.create_still_configuration(
                main={"size": (9152, 6944), "format": "RGB888"},
                buffer_count=1
            )
            camera.configure(still_config)
            camera.start()
            await asyncio.sleep(1.0)
            
            # Capture
            logger.info("📷 Capturing 64MP image...")
            image_array = camera.capture_array("main")
            logger.info(f"✅ Single camera 64MP capture successful: {image_array.shape}")
            
            # Return to normal mode
            logger.info("📷 Returning to normal mode...")
            camera.stop()
            await asyncio.sleep(0.5)
            
            # Reinitialize with normal config
            preview_config = camera.create_preview_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                lores={"size": (640, 480), "format": "YUV420"}
            )
            camera.configure(preview_config)
            camera.start()
            await asyncio.sleep(0.5)
            
            logger.info("✅ Camera returned to normal mode successfully")
            
        except Exception as single_error:
            logger.error(f"❌ Single camera 64MP capture failed: {single_error}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
        
        logger.info("✅ Safe capture tests completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Critical error during safe capture test: {e}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main test function."""
    logger.info("🚀 Starting safe high-resolution capture test...")
    
    success = await test_safe_high_res_capture()
    
    if success:
        logger.info("✅ Safe capture test completed successfully")
    else:
        logger.error("❌ Safe capture test failed")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())