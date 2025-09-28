#!/usr/bin/env python3
"""
Detailed capture debugging tool to diagnose camera capture failures.
Provides step-by-step analysis of the capture process.
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
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_capture_step_by_step():
    """Test capture process step by step with detailed diagnostics."""
    
    logger.info("🔍 Starting detailed capture diagnostics...")
    
    try:
        # Step 1: Load configuration
        logger.info("📋 Step 1: Loading configuration...")
        # Use simplified config structure for testing
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
        logger.info(f"✅ Configuration loaded successfully")
        
        # Step 2: Initialize camera controller
        logger.info("📷 Step 2: Initializing camera controller...")
        camera_controller = PiCameraController(config)
        logger.info(f"✅ Camera controller created")
        
        # Step 3: Initialize cameras (CRITICAL - this actually sets up self.cameras)
        logger.info("🔄 Step 3: Initializing cameras...")
        init_success = await camera_controller.initialize()
        logger.info(f"✅ Camera initialization result: {init_success}")
        
        # Step 4: Check camera availability
        logger.info("🔍 Step 4: Checking camera availability...")
        available_cameras = list(camera_controller.cameras.keys())
        logger.info(f"✅ Available cameras: {available_cameras}")
        
        if not available_cameras:
            logger.error("❌ No cameras available for testing!")
            return False
        
        # Step 5: Test individual camera capture
        for camera_id in available_cameras:
            logger.info(f"📸 Step 5.{camera_id}: Testing camera {camera_id} individual capture...")
            
            try:
                # Check if camera is initialized
                camera = camera_controller.cameras.get(camera_id)
                if not camera:
                    logger.error(f"❌ Camera {camera_id} not initialized!")
                    continue
                
                logger.info(f"📷 Camera {camera_id} object: {type(camera)}")
                logger.info(f"📷 Camera {camera_id} started: {camera.started if hasattr(camera, 'started') else 'Unknown'}")
                
                # Test basic capture
                logger.info(f"🔬 Testing basic capture_array for camera {camera_id}...")
                
                # Ensure camera is started
                if hasattr(camera, 'started') and not camera.started:
                    logger.info(f"📷 Starting camera {camera_id}...")
                    camera.start()
                    await asyncio.sleep(0.5)
                
                # Try basic capture
                try:
                    image_array = camera.capture_array("main")
                    if image_array is not None:
                        logger.info(f"✅ Camera {camera_id} basic capture successful: {image_array.shape}")
                    else:
                        logger.error(f"❌ Camera {camera_id} basic capture returned None!")
                except Exception as basic_error:
                    logger.error(f"❌ Camera {camera_id} basic capture failed: {basic_error}")
                    logger.error(f"   Error type: {type(basic_error)}")
                    logger.error(f"   Traceback: {traceback.format_exc()}")
                
                # Test ISP-managed capture
                logger.info(f"🔬 Testing ISP-managed capture for camera {camera_id}...")
                try:
                    result = await camera_controller.capture_with_isp_management(camera_id, "main")
                    if result is not None:
                        logger.info(f"✅ Camera {camera_id} ISP-managed capture successful: {result.shape}")
                    else:
                        logger.error(f"❌ Camera {camera_id} ISP-managed capture returned None!")
                except Exception as isp_error:
                    logger.error(f"❌ Camera {camera_id} ISP-managed capture failed: {isp_error}")
                    logger.error(f"   Error type: {type(isp_error)}")
                    logger.error(f"   Traceback: {traceback.format_exc()}")
                
            except Exception as camera_error:
                logger.error(f"❌ Camera {camera_id} testing failed: {camera_error}")
                logger.error(f"   Traceback: {traceback.format_exc()}")
        
        # Step 6: Test sequential dual capture
        logger.info("🔄 Step 6: Testing sequential dual capture...")
        try:
            result = await camera_controller.capture_dual_sequential_isp()
            if result:
                logger.info(f"✅ Sequential dual capture successful:")
                for cam_key, img_array in result.items():
                    if img_array is not None:
                        logger.info(f"   {cam_key}: {img_array.shape}")
                    else:
                        logger.error(f"   {cam_key}: None (failed)")
            else:
                logger.error("❌ Sequential dual capture returned empty result!")
        except Exception as dual_error:
            logger.error(f"❌ Sequential dual capture failed: {dual_error}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
        
        # Step 7: Test high-resolution capture
        logger.info("📸 Step 7: Testing high-resolution capture...")
        try:
            result = await camera_controller.capture_dual_resolution_aware((9152, 6944))
            if result:
                logger.info(f"✅ High-resolution dual capture successful:")
                for cam_key, img_array in result.items():
                    if img_array is not None:
                        logger.info(f"   {cam_key}: {img_array.shape}")
                    else:
                        logger.error(f"   {cam_key}: None (failed)")
            else:
                logger.error("❌ High-resolution dual capture returned empty result!")
        except Exception as hires_error:
            logger.error(f"❌ High-resolution dual capture failed: {hires_error}")
            logger.error(f"   Traceback: {traceback.format_exc()}")
        
        logger.info("🔍 Detailed capture diagnostics completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Critical error during diagnostics: {e}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        return False

async def main():
    """Main diagnostic function."""
    logger.info("🚀 Starting camera capture diagnostics...")
    
    success = await test_capture_step_by_step()
    
    if success:
        logger.info("✅ Diagnostics completed - check results above")
    else:
        logger.error("❌ Diagnostics failed - check error messages above")
    
    return success

if __name__ == "__main__":
    asyncio.run(main())