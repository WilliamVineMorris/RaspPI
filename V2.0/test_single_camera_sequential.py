#!/usr/bin/env python3
"""
Single camera sequential test to avoid V4L2 device conflicts.
Tests one camera at a time to prevent "No such device" errors.
"""

import asyncio
import logging
import sys
from pathlib import Path
import traceback

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

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

async def test_single_camera_sequential():
    """Test one camera at a time to avoid V4L2 conflicts."""
    
    logger.info("🔍 Testing single camera sequential approach...")
    
    results = {}
    
    for camera_port in [0, 1]:
        logger.info(f"📷 Testing camera {camera_port} individually...")
        
        try:
            # Create config for single camera
            config = {
                f'camera_{camera_port}': {
                    'port': camera_port,
                    'resolution': [3280, 2464],
                    'name': f'camera_{camera_port}'
                }
            }
            
            # Initialize controller with single camera
            logger.info(f"🔄 Initializing camera {camera_port} controller...")
            camera_controller = PiCameraController(config)
            init_success = await camera_controller.initialize()
            
            if not init_success:
                logger.error(f"❌ Failed to initialize camera {camera_port}")
                results[f'camera_{camera_port}'] = None
                continue
            
            # Test basic capture
            logger.info(f"📸 Testing basic capture for camera {camera_port}...")
            camera = camera_controller.cameras[camera_port]
            basic_result = camera.capture_array("main")
            logger.info(f"✅ Camera {camera_port} basic capture: {basic_result.shape}")
            
            # Test ISP-managed capture
            logger.info(f"🔬 Testing ISP-managed capture for camera {camera_port}...")
            isp_result = await camera_controller.capture_with_isp_management(camera_port, "main")
            if isp_result is not None:
                logger.info(f"✅ Camera {camera_port} ISP capture: {isp_result.shape}")
            else:
                logger.error(f"❌ Camera {camera_port} ISP capture failed")
            
            # Test high-resolution capture
            logger.info(f"📸 Testing 64MP capture for camera {camera_port}...")
            
            # Stop current mode
            camera.stop()
            await asyncio.sleep(0.5)
            
            # Configure for high-resolution
            still_config = camera.create_still_configuration(
                main={"size": (9152, 6944), "format": "RGB888"},
                buffer_count=1
            )
            camera.configure(still_config)
            camera.start()
            await asyncio.sleep(1.0)
            
            # Capture high-resolution
            hires_result = camera.capture_array("main")
            logger.info(f"✅ Camera {camera_port} 64MP capture: {hires_result.shape}")
            
            results[f'camera_{camera_port}'] = hires_result.shape
            
            # Clean shutdown for this camera
            logger.info(f"🧹 Cleaning up camera {camera_port}...")
            camera.stop()
            await asyncio.sleep(0.2)
            camera.close()
            await asyncio.sleep(0.5)
            
            logger.info(f"✅ Camera {camera_port} test completed successfully")
            
        except Exception as camera_error:
            logger.error(f"❌ Camera {camera_port} test failed: {camera_error}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
            results[f'camera_{camera_port}'] = None
        
        # Delay between cameras
        if camera_port == 0:
            logger.info("⏱️ Waiting before next camera...")
            await asyncio.sleep(2.0)
    
    # Summary
    logger.info("📊 Single camera sequential test results:")
    for cam_key, result in results.items():
        if result:
            logger.info(f"   {cam_key}: ✅ {result}")
        else:
            logger.error(f"   {cam_key}: ❌ Failed")
    
    return results

async def main():
    """Main test function."""
    logger.info("🚀 Starting single camera sequential test...")
    
    results = await test_single_camera_sequential()
    
    success = all(result is not None for result in results.values())
    
    if success:
        logger.info("✅ All single camera tests passed")
    else:
        logger.error("❌ Some single camera tests failed")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())