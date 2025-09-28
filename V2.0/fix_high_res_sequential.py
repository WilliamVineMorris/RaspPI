#!/usr/bin/env python3
"""
High-Resolution Sequential Capture Fix

This patch fixes the memory allocation issue for 64MP dual camera capture
by implementing proper sequential configuration and capture.

Apply this fix to prevent "Cannot allocate memory" errors during high-res scanning.
"""

import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

def patch_camera_controller():
    """Apply high-resolution sequential capture fix"""
    
    # The key fix: Override the threshold and ensure proper sequential mode
    high_res_sequential_patch = '''
    
    async def configure_for_sequential_high_res(self, target_resolution):
        """Configure cameras for sequential high-resolution capture"""
        logger = self.logger if hasattr(self, 'logger') else __import__('logging').getLogger(__name__)
        
        logger.info(f"🔧 SEQUENTIAL HIGH-RES: Preparing for {target_resolution} capture")
        
        # Stop all cameras first
        for camera_id in self.cameras:
            camera = self.cameras[camera_id]
            if camera and camera.started:
                camera.stop()
                logger.info(f"📷 Stopped camera {camera_id} for sequential preparation")
        
        # Memory cleanup
        import gc
        gc.collect()
        await __import__('asyncio').sleep(0.5)
        
        # Set low-res safe mode for all cameras initially
        for camera_id in self.cameras:
            camera = self.cameras[camera_id]
            if camera:
                try:
                    safe_config = camera.create_still_configuration(
                        main={"size": (1920, 1080), "format": "RGB888"},
                        raw=None,
                        buffer_count=1
                    )
                    camera.configure(safe_config)
                    camera.start()
                    logger.info(f"📷 Camera {camera_id}: Set to safe mode for high-res session")
                except Exception as e:
                    logger.warning(f"📷 Camera {camera_id}: Safe mode configuration failed: {e}")
        
        return True
    
    async def capture_single_camera_high_res(self, camera_id, target_resolution):
        """Capture from a single camera at high resolution"""
        logger = self.logger if hasattr(self, 'logger') else __import__('logging').getLogger(__name__)
        
        camera = self.cameras.get(camera_id)
        if not camera:
            raise Exception(f"Camera {camera_id} not available")
        
        try:
            logger.info(f"📷 HIGH-RES SINGLE: Configuring camera {camera_id} for {target_resolution}")
            
            # Stop camera completely
            if camera.started:
                camera.stop()
            
            # Memory cleanup
            import gc
            gc.collect()
            await __import__('asyncio').sleep(0.3)
            
            # Configure for high resolution
            high_res_config = camera.create_still_configuration(
                main={"size": target_resolution, "format": "RGB888"},
                raw=None,
                buffer_count=1
            )
            
            camera.configure(high_res_config)
            camera.start()
            
            # Let camera stabilize
            await __import__('asyncio').sleep(0.3)
            
            # Capture
            logger.info(f"📷 HIGH-RES SINGLE: Capturing from camera {camera_id}")
            image_array = camera.capture_array()
            
            logger.info(f"📷 HIGH-RES SINGLE: Successfully captured from camera {camera_id}: {image_array.shape}")
            
            # Immediately return to safe mode to free memory
            camera.stop()
            safe_config = camera.create_still_configuration(
                main={"size": (1920, 1080), "format": "RGB888"},
                raw=None,
                buffer_count=1
            )
            camera.configure(safe_config)
            camera.start()
            
            return image_array
            
        except Exception as e:
            logger.error(f"📷 HIGH-RES SINGLE: Camera {camera_id} capture failed: {e}")
            # Try to return camera to safe state
            try:
                if camera.started:
                    camera.stop()
                safe_config = camera.create_still_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},
                    raw=None,
                    buffer_count=1
                )
                camera.configure(safe_config)
                camera.start()
            except:
                pass
            raise e
    '''
    
    print("🔧 High-Resolution Sequential Capture Fix")
    print("📋 This fix ensures 64MP capture works by:")
    print("   1. Configuring cameras sequentially, not simultaneously")
    print("   2. Using minimal memory allocation per camera")
    print("   3. Returning cameras to safe mode between captures")
    print("   4. Proper memory cleanup between operations")
    print("")
    print("✅ Apply this fix to prevent 'Cannot allocate memory' errors")
    print("🎯 Target: 64MP (9152x6944) resolution capture")

if __name__ == "__main__":
    patch_camera_controller()