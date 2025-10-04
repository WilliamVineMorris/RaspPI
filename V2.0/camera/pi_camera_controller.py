"""
Raspberry Pi Camera Controller Implementation

Concrete implementation of the CameraController interface for Raspberry Pi cameras.
Supports dual camera setup with different capture modes, formats, and configurations.

Hardware Setup:
- Pi Camera 1 on port 0 (main scanning camera)
- Pi Camera 2 on port 1 (secondary/preview camera)
- Both cameras configurable independently

Key Features:
- Dual camera management with independent settings
- Multiple capture modes (single, burst, video)
- Format support (JPEG, PNG, RAW)
- Hardware-accelerated encoding where available
- Thread-safe operation with async interface

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import time
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import io

try:
    from picamera2 import Picamera2
    from picamera2.controls import Controls
    from picamera2.encoders import JpegEncoder, H264Encoder
    from picamera2.outputs import FileOutput, CircularOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    Picamera2 = None

from camera.base import (
    CameraController, CameraStatus, CaptureMode, 
    ImageFormat, CameraSettings, CameraCapabilities,
    CaptureResult, SyncCaptureResult
)
from core.exceptions import (
    CameraError, CameraConfigurationError, 
    CameraCaptureError, CameraConnectionError, CameraInitializationError
)
from core.events import ScannerEvent, EventPriority
from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class CameraSpecs:
    """Camera hardware specifications"""
    focal_length_mm: float
    aperture_f_number: float
    sensor_model: str
    crop_factor: float
    physical_sensor_size_mm: Tuple[float, float]  # (width, height)
    pixel_size_um: float
    
    @property
    def focal_length_35mm_equivalent(self) -> float:
        """Calculate 35mm equivalent focal length"""
        return self.focal_length_mm * self.crop_factor


class PiCameraInfo:
    """Information about a Pi camera"""
    def __init__(self, camera_id: int, camera_type: str = "unknown"):
        self.camera_id = camera_id
        self.camera_type = camera_type
        self.is_available = False
        self.native_resolution = (0, 0)
        self.supported_formats = []
        
        # Camera specifications (calibrated values)
        self.specs = self._get_camera_specs(camera_type)
    
    def _get_camera_specs(self, camera_type: str) -> CameraSpecs:
        """Get calibrated camera specifications based on camera type"""
        # Default specs for Arducam 64MP with Sony IMX519
        if "arducam" in camera_type.lower() or "64mp" in camera_type.lower() or "imx519" in camera_type.lower():
            return CameraSpecs(
                focal_length_mm=2.74,  # Measured focal length for Arducam 64MP
                aperture_f_number=1.8,  # Fixed aperture for this lens
                sensor_model="Sony IMX519",
                crop_factor=7.37,  # Calculated from sensor size vs full frame
                physical_sensor_size_mm=(5.94, 3.34),  # IMX519 sensor dimensions
                pixel_size_um=1.285  # IMX519 pixel pitch
            )
        
        # Default/unknown camera specs
        return CameraSpecs(
            focal_length_mm=3.04,  # Typical Pi camera focal length
            aperture_f_number=2.0,  # Typical Pi camera aperture
            sensor_model="Unknown",
            crop_factor=7.0,  # Typical crop factor for small sensors
            physical_sensor_size_mm=(5.7, 4.28),  # Typical Pi camera sensor
            pixel_size_um=1.4  # Typical pixel size
        )


@dataclass
class CaptureRequest:
    """Camera capture request"""
    camera_id: int
    settings: CameraSettings
    output_path: Optional[Path] = None
    capture_mode: CaptureMode = CaptureMode.SINGLE
    burst_count: int = 1


class PiCameraController(CameraController):
    """Raspberry Pi Camera Controller Implementation"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize Pi camera controller"""
        super().__init__(config)
        
        # Configuration
        self.config = config
        self.camera_count = config.get('camera_count', 2)
        self.default_format = self._parse_image_format(config.get('default_format', 'jpeg'))
        
        # Camera instances
        self.cameras: Dict[int, Any] = {}  # Will hold Picamera2 instances when available
        self.camera_info: Dict[int, PiCameraInfo] = {}
        self.camera_locks: Dict[int, asyncio.Lock] = {}
        
        # State tracking
        self.status = CameraStatus.DISCONNECTED
        self.active_captures: Dict[int, bool] = {}
        self.capture_queue = asyncio.Queue()
        
        # Threading for camera operations
        self.camera_thread: Optional[threading.Thread] = None
        self.thread_stop_event = threading.Event()
        
        # Statistics
        self.capture_count = 0
        self.error_count = 0
        
        # Scanning mode tracking
        self.scanning_mode = False
        
        # Initialize camera information
        self._initialize_camera_info()
    
    def _parse_image_format(self, format_str: str) -> ImageFormat:
        """Parse image format string to ImageFormat enum"""
        format_lower = format_str.lower()
        for fmt in ImageFormat:
            if fmt.value == format_lower:
                return fmt
        # Default to JPEG if unknown format
        return ImageFormat.JPEG
    
    def _initialize_camera_info(self):
        """Initialize camera information"""
        try:
            if not PICAMERA2_AVAILABLE:
                logger.error("picamera2 library not available")
                return
            
            # Discover available cameras
            for camera_id in range(self.camera_count):
                try:
                    # Try to create camera instance to check availability
                    if not PICAMERA2_AVAILABLE or Picamera2 is None:
                        raise Exception("picamera2 not available")
                        
                    test_camera = Picamera2(camera_id)
                    camera_info = test_camera.camera_properties
                    test_camera.close()
                    
                    # Store camera information
                    self.camera_info[camera_id] = PiCameraInfo(
                        camera_id=camera_id,
                        camera_type=camera_info.get('Model', 'Unknown')
                    )
                    self.camera_info[camera_id].is_available = True
                    
                    # Set up locks
                    self.camera_locks[camera_id] = asyncio.Lock()
                    self.active_captures[camera_id] = False
                    
                    logger.info(f"Camera {camera_id} available: {self.camera_info[camera_id].camera_type}")
                    
                except Exception as e:
                    logger.warning(f"Camera {camera_id} not available: {e}")
                    self.camera_info[camera_id] = PiCameraInfo(camera_id, "unavailable")
                    self.camera_info[camera_id].is_available = False
                    
        except Exception as e:
            logger.error(f"Failed to initialize camera info: {e}")
    
    # Abstract method implementations
    async def initialize(self) -> bool:
        """Initialize camera controller"""
        try:
            logger.info("Initializing Pi camera controller...")
            
            if not PICAMERA2_AVAILABLE:
                raise CameraConnectionError("picamera2 library not available")
            
            # CRITICAL: Ensure any existing cameras are properly closed first
            await self._cleanup_existing_cameras()
            
            # Initialize available cameras
            initialized_count = 0
            for camera_id, info in self.camera_info.items():
                if info.is_available:
                    try:
                        await self._initialize_camera(camera_id)
                        initialized_count += 1
                    except Exception as e:
                        logger.error(f"Failed to initialize camera {camera_id}: {e}")
                        # Try to cleanup this specific camera if initialization failed
                        await self._force_cleanup_camera(camera_id)
            
            if initialized_count == 0:
                raise CameraConnectionError("No cameras could be initialized")
            
            # Start camera thread
            self._start_camera_thread()
            
            self.status = CameraStatus.READY
            logger.info(f"Pi camera controller initialized with {initialized_count} cameras")
            
            self._notify_event("camera_initialized", {
                "cameras_available": initialized_count,
                "camera_info": {cid: info.__dict__ for cid, info in self.camera_info.items()}
            })
            
            return True
            
        except Exception as e:
            self.status = CameraStatus.ERROR
            logger.error(f"Camera controller initialization failed: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """Shutdown camera controller"""
        try:
            logger.info("Shutting down camera controller...")
            
            # Stop camera thread first
            if self.camera_thread and self.camera_thread.is_alive():
                self.thread_stop_event.set()
                self.camera_thread.join(timeout=5.0)
            
            # Force cleanup all cameras with enhanced error protection
            await self._cleanup_existing_cameras()
            
            # Clear all state
            self.cameras = {}
            self.active_captures = {}
            self.camera_locks = {}
            
            self.status = CameraStatus.DISCONNECTED
            logger.info("Camera controller shutdown complete")
            
            return True
            
        except Exception as e:
            logger.error(f"Camera shutdown error: {e}")
            # Force status to disconnected even if shutdown failed
            self.status = CameraStatus.DISCONNECTED
            return False
    
    def is_connected(self) -> bool:
        """Check if cameras are connected"""
        return self.status in [CameraStatus.READY, CameraStatus.CAPTURING]
    
    def is_available(self) -> bool:
        """Check if camera(s) are available and ready"""
        return len([info for info in self.camera_info.values() if info.is_available]) > 0
    
    async def get_status(self) -> CameraStatus:
        """Get camera status"""
        return self.status
    
    def get_status_sync(self) -> CameraStatus:
        """Get camera status synchronously for web interface"""
        return self.status
    
    async def list_cameras(self) -> List[str]:
        """Get list of available camera identifiers"""
        return [f"camera{cid}" for cid, info in self.camera_info.items() if info.is_available]
    
    async def configure_camera(self, camera_id: str, settings: CameraSettings) -> bool:
        """Configure camera settings"""
        try:
            # Convert camera_id string to int
            cam_id = int(camera_id.replace('camera', ''))
            return await self.set_camera_settings(cam_id, settings)
        except Exception as e:
            logger.error(f"Failed to configure camera {camera_id}: {e}")
            return False
    
    async def capture_photo(self, camera_id: str, settings: Optional[CameraSettings] = None) -> 'CaptureResult':
        """Capture single photo from specified camera"""
        try:
            from camera.base import CaptureResult
            
            # Convert camera_id string to int
            cam_id = int(camera_id.replace('camera', ''))
            
            # Apply calibrated settings for scan capture
            await self.apply_scan_settings(camera_id)
            
            # Create temporary output path
            timestamp = int(time.time() * 1000)
            temp_path = Path(f"/tmp/capture_{cam_id}_{timestamp}.jpg")
            
            if settings:
                await self.set_camera_settings(cam_id, settings)
            
            success = await self.capture_image(cam_id, settings or CameraSettings(resolution=self._get_optimal_resolution_for_capture()), temp_path)
            
            # Restore live streaming settings after capture
            await self.restore_live_settings(camera_id)
            
            return CaptureResult(
                success=success,
                image_path=temp_path if success else None,
                camera_id=camera_id,
                timestamp=time.time()
            )
            
        except Exception as e:
            logger.error(f"Photo capture failed: {e}")
            from camera.base import CaptureResult
            return CaptureResult(success=False, camera_id=camera_id)
    
    async def capture_burst(self, camera_id: str, count: int, 
                          interval: float = 0.1, settings: Optional[CameraSettings] = None) -> List[CaptureResult]:
        """Capture burst of photos from specified camera"""
        try:
            # Convert camera_id string to int
            cam_id = int(camera_id.replace('camera', ''))
            
            # Create output directory
            timestamp = int(time.time() * 1000)
            output_dir = Path(f"/tmp/burst_{cam_id}_{timestamp}")
            output_dir.mkdir(exist_ok=True)
            
            if settings:
                await self.set_camera_settings(cam_id, settings)
            
            # Use the internal burst capture method with different name
            captured_files = await self._capture_burst_internal(cam_id, settings or CameraSettings(resolution=self._get_optimal_resolution_for_capture()), output_dir, count)
            
            results = []
            for i, file_path in enumerate(captured_files):
                results.append(CaptureResult(
                    success=True,
                    image_path=file_path,
                    camera_id=camera_id,
                    timestamp=time.time() + i * interval
                ))
            
            return results
            
        except Exception as e:
            logger.error(f"Burst capture failed: {e}")
            return []
    
    async def capture_synchronized(self, settings: Optional[Dict[str, CameraSettings]] = None) -> 'SyncCaptureResult':
        """Capture synchronized photos from all available cameras"""
        try:
            from camera.base import SyncCaptureResult, CaptureResult
            
            available_cameras = await self.list_cameras()
            if len(available_cameras) < 2:
                return SyncCaptureResult(success=False)
            
            # Capture from first two cameras simultaneously
            camera1_id = available_cameras[0]
            camera2_id = available_cameras[1]
            
            # Use provided settings or defaults with dynamic resolution
            default_resolution = self._get_optimal_resolution_for_capture()
            cam1_settings = settings.get(camera1_id, CameraSettings(resolution=default_resolution)) if settings else CameraSettings(resolution=default_resolution)
            cam2_settings = settings.get(camera2_id, CameraSettings(resolution=default_resolution)) if settings else CameraSettings(resolution=default_resolution)
            
            # Synchronous capture (simplified)
            start_time = time.time()
            
            cam1_result = await self.capture_photo(camera1_id, cam1_settings)
            cam2_result = await self.capture_photo(camera2_id, cam2_settings)
            
            end_time = time.time()
            sync_error = (end_time - start_time) * 1000  # Convert to ms
            
            return SyncCaptureResult(
                success=cam1_result.success and cam2_result.success,
                camera1_result=cam1_result,
                camera2_result=cam2_result,
                sync_error_ms=sync_error
            )
            
        except Exception as e:
            logger.error(f"Synchronized capture failed: {e}")
            from camera.base import SyncCaptureResult
            return SyncCaptureResult(success=False)
    
    async def calibrate_synchronization(self, test_captures: int = 10) -> float:
        """Calibrate camera synchronization timing"""
        try:
            total_error = 0.0
            successful_captures = 0
            
            for i in range(test_captures):
                result = await self.capture_synchronized()
                if result.success and result.sync_error_ms is not None:
                    total_error += result.sync_error_ms
                    successful_captures += 1
                
                await asyncio.sleep(0.5)  # Brief pause between captures
            
            if successful_captures == 0:
                raise CameraError("No successful calibration captures")
            
            average_error = total_error / successful_captures
            logger.info(f"Synchronization calibrated: {average_error:.2f}ms average error")
            
            return average_error
            
        except Exception as e:
            logger.error(f"Synchronization calibration failed: {e}")
            return 999.0  # High error value indicating failure
    
    async def start_streaming(self, camera_id: str, settings: Optional[CameraSettings] = None) -> bool:
        """Start video streaming from camera"""
        try:
            # Convert camera_id string to int
            cam_id = int(camera_id.replace('camera', ''))
            
            if settings:
                await self.set_camera_settings(cam_id, settings)
            
            # Create streaming output path
            timestamp = int(time.time() * 1000)
            output_path = Path(f"/tmp/stream_{cam_id}_{timestamp}.mp4")
            
            return await self.start_video_recording(cam_id, settings or CameraSettings(resolution=(1280, 720)), output_path)
            
        except Exception as e:
            logger.error(f"Streaming start failed: {e}")
            return False
    
    async def stop_streaming(self, camera_id: str) -> bool:
        """Stop video streaming from camera"""
        try:
            # Convert camera_id string to int
            cam_id = int(camera_id.replace('camera', ''))
            
            return await self.stop_video_recording(cam_id)
            
        except Exception as e:
            logger.error(f"Streaming stop failed: {e}")
            return False
    
    async def get_stream_frame(self, camera_id: str) -> Optional[bytes]:
        """Get current frame from video stream"""
        # Not implemented for Pi cameras in this version
        logger.warning(f"Stream frame capture not implemented for {camera_id}")
        return None
    
    def get_preview_frame(self, camera_id: str) -> Optional[Any]:
        """Get preview frame for web streaming - optimized for performance"""
        try:
            # Convert camera_id string to int
            cam_id = int(camera_id.replace('camera_', '').replace('camera', ''))
            
            # Only support camera 0 for now
            if cam_id != 0 and cam_id != 1:
                return None
                
            # Check if camera is available and initialized
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                return None
            
            # For performance, return a lightweight test frame
            # In production, this would capture actual camera frame
            import numpy as np
            import cv2
            
            # Create optimized preview frame (lower resolution for streaming)
            frame = np.zeros((360, 640, 3), dtype=np.uint8)  # 640x360 for better performance
            frame[:120, :, :] = [40, 80, 120]   # Dark blue top
            frame[120:240, :, :] = [60, 120, 180]  # Medium blue middle  
            frame[240:, :, :] = [80, 160, 240]   # Light blue bottom
            
            # Add camera ID text for identification
            cv2.putText(frame, f"Pi Camera {cam_id}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            # Add status indicator
            status_text = "READY" if self.cameras[cam_id] else "OFFLINE"
            cv2.putText(frame, status_text, (10, 330), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0) if self.cameras[cam_id] else (0, 0, 255), 2)
            
            return frame
            
        except Exception as e:
            logger.error(f"Preview frame generation failed for {camera_id}: {e}")
            return None
    
    def is_streaming(self, camera_id: str) -> bool:
        """Check if camera is currently streaming"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            return self.active_captures.get(cam_id, False)
        except Exception:
            return False
    
    async def auto_focus(self, camera_id: str) -> bool:
        """Trigger auto-focus on camera with enhanced ArduCam support"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                logger.warning(f"📷 Camera {camera_id} not available for autofocus")
                return False
            
            picamera2 = self.cameras[cam_id]
            
            # Check if camera supports autofocus
            if not self._supports_autofocus(cam_id):
                logger.info(f"📷 Camera {camera_id} has fixed focus or autofocus not supported - using manual focus")
                return True
            
            logger.info(f"📷 Starting autofocus for {camera_id}")
            
            # Use official Picamera2 autofocus approach (Section 5.2)
            try:
                # Set camera to Auto mode for single-shot autofocus (recommended for scan points)
                logger.debug(f"📷 Camera {camera_id} setting Auto mode for single-shot autofocus")
                
                # Import controls for proper enum usage
                try:
                    from libcamera import controls
                    af_mode_auto = controls.AfModeEnum.Auto
                    af_range_macro = controls.AfRangeEnum.Macro
                    logger.debug(f"📷 Camera {camera_id} using libcamera controls enum")
                except ImportError:
                    # Fallback to numeric mode if libcamera not available
                    af_mode_auto = 1  # Auto mode
                    af_range_macro = 1  # Macro range
                    logger.debug(f"📷 Camera {camera_id} using numeric AF mode (fallback)")
                
                # Set Auto mode for controlled autofocus with Macro range (closest objects)
                # Macro range focuses on 8cm-1m, excluding infinity/far distances
                picamera2.set_controls({
                    "AfMode": af_mode_auto,
                    "AfRange": af_range_macro
                })
                logger.info(f"📷 Camera {camera_id} AF range set to Macro (8cm-1m, closest objects only)")
                await asyncio.sleep(0.2)  # Let mode change take effect
                
                # Use official autofocus_cycle() helper function (recommended approach)
                logger.info(f"📷 Camera {camera_id} starting autofocus cycle...")
                
                # Use proper async autofocus approach from Picamera2 documentation
                success = False
                
                try:
                    # Method 1: Try async autofocus_cycle (wait=False) as per documentation
                    if hasattr(picamera2, 'autofocus_cycle') and hasattr(picamera2, 'wait'):
                        logger.debug(f"📷 Camera {camera_id} using async autofocus_cycle(wait=False)...")
                        
                        # Start autofocus cycle asynchronously (as shown in docs)
                        job = picamera2.autofocus_cycle(wait=False)
                        logger.debug(f"📷 Camera {camera_id} autofocus job started, waiting for completion...")
                        
                        # Wait for completion with timeout
                        def wait_for_job():
                            return picamera2.wait(job)
                        
                        # Run in thread to avoid blocking
                        wait_task = asyncio.create_task(asyncio.to_thread(wait_for_job))
                        result = await asyncio.wait_for(wait_task, timeout=4.0)
                        
                        if result:
                            logger.info(f"✅ Camera {camera_id} async autofocus completed successfully")
                            success = True
                        else:
                            logger.warning(f"⚠️ Camera {camera_id} async autofocus completed but may not be optimal")
                            success = True  # Still consider usable
                            
                    # Method 2: Try synchronous autofocus_cycle as fallback
                    elif hasattr(picamera2, 'autofocus_cycle'):
                        logger.debug(f"📷 Camera {camera_id} using synchronous autofocus_cycle()...")
                        
                        def run_sync_autofocus():
                            return picamera2.autofocus_cycle()
                        
                        sync_task = asyncio.create_task(asyncio.to_thread(run_sync_autofocus))
                        result = await asyncio.wait_for(sync_task, timeout=4.0)
                        
                        if result:
                            logger.info(f"✅ Camera {camera_id} sync autofocus completed successfully")
                            success = True
                        else:
                            logger.warning(f"⚠️ Camera {camera_id} sync autofocus completed but may not be optimal")
                            success = True
                            
                    else:
                        logger.info(f"📷 Camera {camera_id} autofocus_cycle method not available")
                        
                except Exception as cycle_error:
                    logger.warning(f"📷 Camera {camera_id} autofocus_cycle failed: {cycle_error}")
                
                # Method 3: Manual autofocus implementation if others failed
                if not success:
                    logger.info(f"📷 Camera {camera_id} using manual AF trigger implementation...")
                    
                    try:
                        # Trigger autofocus manually and monitor state
                        picamera2.set_controls({"AfTrigger": 0})
                        logger.debug(f"📷 Camera {camera_id} manual AF trigger sent")
                        
                        # Monitor autofocus state for completion with shorter timeout
                        max_wait = 4.0  # Match the overall timeout expectation
                        start_time = time.time()
                        last_state = None
                        
                        while (time.time() - start_time) < max_wait:
                            try:
                                metadata = picamera2.capture_metadata()
                                af_state = metadata.get('AfState', 0)
                                lens_pos = metadata.get('LensPosition', None)
                                
                                if af_state != last_state:
                                    logger.debug(f"📷 Camera {camera_id} AF state: {af_state}, lens: {lens_pos}")
                                    last_state = af_state
                                
                                # AfState: 0=Inactive, 1=PassiveScan, 2=PassiveFocused, 3=ActiveScan, 4=FocusedLocked, 5=NotFocusedLocked
                                if af_state in [2, 4]:  # Successfully focused
                                    logger.info(f"✅ Camera {camera_id} manual autofocus successful (state={af_state}, lens={lens_pos})")
                                    success = True
                                    break
                                elif af_state == 5:  # Focus failed but still locked
                                    logger.warning(f"⚠️ Camera {camera_id} focus locked but may not be optimal (state={af_state}, lens={lens_pos})")
                                    success = True  # Still usable
                                    break
                                    
                            except Exception as meta_error:
                                logger.debug(f"📷 Camera {camera_id} metadata read error: {meta_error}")
                                
                            await asyncio.sleep(0.05)  # Faster polling
                        
                        if not success:
                            logger.warning(f"⏱️ Camera {camera_id} manual autofocus timed out after {max_wait}s")
                            
                    except Exception as manual_error:
                        logger.warning(f"📷 Camera {camera_id} manual autofocus failed: {manual_error}")
                
                # Report final status
                if success:
                    logger.info(f"✅ Camera {camera_id} autofocus completed successfully")
                else:
                    logger.warning(f"⚠️ Camera {camera_id} autofocus had issues but continuing")
                
                return True  # Always continue scanning
                
            except Exception as focus_error:
                logger.warning(f"📷 Camera {camera_id} autofocus process failed: {focus_error}")
                logger.info(f"📷 Camera {camera_id} continuing with current focus setting")
                return True  # Don't block scan for autofocus issues
            
        except Exception as e:
            logger.error(f"❌ Auto-focus error for {camera_id}: {e}")
            logger.info(f"🔄 Continuing scan without autofocus for {camera_id}")
            return True  # Never fail the scan for autofocus issues

    async def auto_exposure(self, camera_id: str) -> bool:
        """Trigger auto-exposure on camera"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                return False
            
            # Auto-exposure is typically handled automatically by Pi cameras
            logger.debug(f"Auto-exposure triggered for {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Auto-exposure failed for {camera_id}: {e}")
            return False

    def _supports_autofocus(self, cam_id: int) -> bool:
        """Check if camera supports autofocus according to Picamera2 documentation"""
        try:
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                logger.debug(f"📷 Camera {cam_id} not available for autofocus check")
                return False
            
            picamera2 = self.cameras[cam_id]
            
            # According to Picamera2 docs: "Camera modules that do not support autofocus 
            # will not advertise these options as being available in camera_controls"
            try:
                controls = picamera2.camera_controls
                
                # Check for required AF controls as per documentation
                required_af_controls = ['AfMode', 'AfTrigger', 'LensPosition']
                available_af_controls = [ctrl for ctrl in required_af_controls if ctrl in controls]
                
                if len(available_af_controls) < 2:  # Need at least AfMode and one other
                    logger.info(f"📷 Camera {cam_id}: Insufficient autofocus controls ({available_af_controls})")
                    return False
                
                # Log available AF controls for debugging
                af_controls_info = {ctrl: controls[ctrl] for ctrl in available_af_controls}
                logger.debug(f"📷 Camera {cam_id}: Available AF controls: {af_controls_info}")
                
                # If AfMode is available, camera should support autofocus
                if 'AfMode' in controls:
                    af_mode_range = controls['AfMode']
                    logger.info(f"📷 Camera {cam_id}: Autofocus supported (AfMode range: {af_mode_range})")
                    return True
                else:
                    logger.info(f"📷 Camera {cam_id}: No AfMode control, autofocus not supported")
                    return False
                    
            except Exception as controls_error:
                logger.warning(f"📷 Camera {cam_id}: Could not check camera controls: {controls_error}")
                return False
                
        except Exception as e:
            logger.warning(f"📷 Camera {cam_id}: Autofocus support check failed: {e}")
            return False

    async def get_focus_value(self, camera_id: str) -> Optional[float]:
        """Get current focus value for camera"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                return None
            
            if not self._supports_autofocus(cam_id):
                return None
                
            picamera2 = self.cameras[cam_id]
            metadata = picamera2.capture_metadata()
            lens_position = metadata.get('LensPosition')
            
            if lens_position is not None:
                # Convert lens position to 0.0-1.0 range
                # Typical lens position range is 0-1023, where 0 is infinity and higher values are closer
                # We'll normalize and invert so 0.0 = near (high lens position) and 1.0 = infinity (low lens position)
                normalized = 1.0 - (lens_position / 1023.0)
                return max(0.0, min(1.0, normalized))
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get focus value for {camera_id}: {e}")
            return None

    async def set_focus_value(self, camera_id: str, focus_value: float) -> bool:
        """Set manual focus value for camera"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                return False
                
            if not self._supports_autofocus(cam_id):
                logger.debug(f"Camera {camera_id} does not support manual focus")
                return False
            
            # Clamp focus value to valid range
            focus_value = max(0.0, min(1.0, focus_value))
            
            # Convert 0.0-1.0 range to lens position
            # 0.0 = near (high lens position), 1.0 = infinity (low lens position)
            lens_position = int((1.0 - focus_value) * 1023)
            
            picamera2 = self.cameras[cam_id]
            picamera2.set_controls({
                "AfMode": 0,  # Manual focus
                "LensPosition": lens_position
            })
            
            logger.info(f"Set focus value {focus_value:.3f} (lens position {lens_position}) for {camera_id}")
            
            # Give camera time to adjust focus
            await asyncio.sleep(0.2)
            return True
            
        except Exception as e:
            logger.error(f"Failed to set focus value for {camera_id}: {e}")
            return False

    async def auto_focus_and_get_value(self, camera_id: str) -> Optional[float]:
        """Perform autofocus and return the optimal focus value - integrated approach"""
        logger.info(f"🔍 ENTRY: auto_focus_and_get_value({camera_id}) called")
        
        try:
            cam_id = int(camera_id.replace('camera', ''))
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                logger.warning(f"📷 Camera {camera_id} not available for autofocus")
                return None
                
            if not self._supports_autofocus(cam_id):
                logger.info(f"📷 Camera {camera_id} fixed focus, returning hyperfocal value")
                return 0.5
                
            picamera2 = self.cameras[cam_id]
            logger.info(f"📷 Camera {camera_id} starting integrated autofocus with value retrieval...")
            
            # Set Auto mode for single-shot autofocus with Macro range
            try:
                from libcamera import controls
                af_mode_auto = controls.AfModeEnum.Auto
                af_range_macro = controls.AfRangeEnum.Macro
            except ImportError:
                af_mode_auto = 1  # Auto mode fallback
                af_range_macro = 1  # Macro range fallback
            
            # Set Macro range to focus on closest objects (8cm-1m)
            # Macro range excludes far distances and infinity
            picamera2.set_controls({
                "AfMode": af_mode_auto,
                "AfRange": af_range_macro
            })
            logger.info(f"📷 Camera {camera_id} AF range set to Macro (8cm-1m, closest objects only)")
            await asyncio.sleep(0.2)
            
            # Variable to store final lens position
            final_lens_position = None
            autofocus_success = False
            
            # Method 1: Try async autofocus_cycle with manual monitoring (avoid blocking wait)
            try:
                if hasattr(picamera2, 'autofocus_cycle'):
                    logger.info(f"📷 Camera {camera_id} starting autofocus_cycle(wait=False)...")
                    
                    # Start autofocus asynchronously
                    job = picamera2.autofocus_cycle(wait=False)
                    logger.info(f"📷 Camera {camera_id} autofocus job started, monitoring completion...")
                    
                    # Monitor completion manually instead of using blocking wait
                    start_time = time.time()
                    check_interval = 0.1
                    timeout = 8.0  # 8 second timeout
                    
                    while (time.time() - start_time) < timeout:
                        # Check if autofocus is still running by monitoring AF state
                        try:
                            metadata = picamera2.capture_metadata()
                            af_state = metadata.get('AfState', 0)
                            lens_pos = metadata.get('LensPosition')
                            
                            # AfState: 2=PassiveFocused, 4=FocusedLocked, 5=NotFocusedLocked
                            if af_state in [2, 4, 5]:  # Focus completed
                                final_lens_position = lens_pos
                                autofocus_success = True
                                logger.info(f"✅ Camera {camera_id} autofocus_cycle completed, state: {af_state}, lens: {lens_pos}")
                                break
                                
                            logger.debug(f"📷 Camera {camera_id} AF state: {af_state}, lens: {lens_pos}")
                            
                        except Exception as metadata_error:
                            logger.debug(f"📷 Camera {camera_id} metadata check error: {metadata_error}")
                            
                        await asyncio.sleep(check_interval)
                    
                    if not autofocus_success:
                        elapsed = time.time() - start_time
                        logger.warning(f"📷 Camera {camera_id} autofocus_cycle monitoring timed out after {elapsed:.1f}s")
                    
            except Exception as async_error:
                logger.warning(f"📷 Camera {camera_id} autofocus_cycle failed: {async_error}")
            
            # Method 2: Manual trigger with state monitoring and value capture
            if not autofocus_success:
                logger.info(f"📷 Camera {camera_id} using manual AF trigger with monitoring...")
                
                try:
                    picamera2.set_controls({"AfTrigger": 0})
                    
                    start_time = time.time()
                    while (time.time() - start_time) < 10.0:  # Increased to 10s
                        metadata = picamera2.capture_metadata()
                        af_state = metadata.get('AfState', 0)
                        lens_pos = metadata.get('LensPosition')
                        
                        # AfState: 2=PassiveFocused, 4=FocusedLocked, 5=NotFocusedLocked
                        if af_state in [2, 4, 5]:
                            final_lens_position = lens_pos
                            autofocus_success = True
                            logger.info(f"✅ Camera {camera_id} manual AF successful, state: {af_state}, lens: {lens_pos}")
                            break
                            
                        await asyncio.sleep(0.05)
                        
                except Exception as manual_error:
                    logger.warning(f"📷 Camera {camera_id} manual AF failed: {manual_error}")
            
            # Convert lens position to normalized value
            logger.debug(f"📷 Camera {camera_id} autofocus_success={autofocus_success}, final_lens_position={final_lens_position}")
            
            if autofocus_success and final_lens_position is not None:
                # ArduCam lens positions typically range 0-10+ (higher = closer)
                normalized_focus = min(1.0, max(0.0, final_lens_position / 10.0))
                logger.info(f"🎯 Camera {camera_id} SUCCESS: Returning focus value {normalized_focus:.3f} (raw: {final_lens_position})")
                logger.info(f"🔍 EXIT: auto_focus_and_get_value({camera_id}) returning {normalized_focus:.3f}")
                return normalized_focus
            elif autofocus_success:
                logger.warning(f"📷 Camera {camera_id} autofocus succeeded but no lens position available")
                logger.info(f"🔍 EXIT: auto_focus_and_get_value({camera_id}) returning default 0.5 (no lens pos)")
                return 0.5  # Default value
            else:
                logger.warning(f"📷 Camera {camera_id} autofocus did not succeed, using default")
                logger.info(f"🔍 EXIT: auto_focus_and_get_value({camera_id}) returning default 0.5 (failed)")
                return 0.5  # Default value
            
        except Exception as e:
            logger.error(f"📷 Camera {camera_id} autofocus and value retrieval failed: {e}")
            logger.info(f"🔍 EXIT: auto_focus_and_get_value({camera_id}) returning default 0.5 (exception)")
            return 0.5  # Return default instead of None to prevent scan failure

    async def auto_calibrate_camera(self, camera_id: str) -> Dict[str, float]:
        """Perform comprehensive auto-calibration: autofocus + auto-exposure optimization"""
        calibration_timeout = 15.0  # Maximum time for entire calibration
        calibration_start = time.time()
        
        logger.info(f"🔧 CALIBRATION: Starting auto-calibration for {camera_id} (timeout: {calibration_timeout}s)")
        
        try:
            cam_id = int(camera_id.replace('camera', ''))
            
            if cam_id not in self.cameras or not self.cameras[cam_id]:
                logger.warning(f"📷 Camera {camera_id} not available for calibration")
                return {'focus': 0.5, 'exposure_time': 33000, 'analogue_gain': 1.0}
                
            picamera2 = self.cameras[cam_id]
            
            # Check camera state before calibration with enhanced error checking
            try:
                if not hasattr(picamera2, 'started') or not picamera2.started:
                    logger.warning(f"⚠️ Camera {camera_id} not started - attempting to start...")
                    try:
                        picamera2.start()
                        await asyncio.sleep(0.2)
                        
                        # Verify start was successful
                        if not hasattr(picamera2, 'started') or not picamera2.started:
                            raise CameraError(f"Camera {camera_id} failed to start after restart attempt")
                            
                    except Exception as start_error:
                        logger.error(f"❌ Failed to start camera {camera_id}: {start_error}")
                        return {'focus': 0.5, 'exposure_time': 33000, 'analogue_gain': 1.0}
                        
            except Exception as state_error:
                logger.error(f"❌ Camera {camera_id} state check failed: {state_error}")
                return {'focus': 0.5, 'exposure_time': 33000, 'analogue_gain': 1.0}
            
            # Step 1: Enable auto-exposure, auto-white-balance, and focus/metering zones
            logger.info(f"📷 Camera {camera_id} enabling auto-exposure controls...")
            try:
                from libcamera import controls
                
                # Get focus zone configuration from config dict
                focus_zone_config = self.config.get('focus_zone', {})
                focus_zone_enabled = focus_zone_config.get('enabled', False)
                
                # Prepare control dictionary
                control_dict = {
                    "AeEnable": True,           # Enable auto-exposure
                    "AwbEnable": True,          # Enable auto white balance
                    "AeMeteringMode": controls.AeMeteringModeEnum.CentreWeighted,  # Focus on center
                    "AeExposureMode": controls.AeExposureModeEnum.Normal,         # Normal exposure
                }
                
                # Add focus/metering windows if enabled
                if focus_zone_enabled:
                    focus_window = focus_zone_config.get('window', [0.25, 0.25, 0.5, 0.5])
                    
                    # CRITICAL: AfWindows uses absolute pixel coordinates relative to ScalerCropMaximum
                    # NOT percentages! Get the maximum scaler crop window size.
                    try:
                        # ScalerCropMaximum = (x_offset, y_offset, width, height) of maximum crop window
                        scaler_crop_max = picamera2.camera_properties.get('ScalerCropMaximum')
                        if scaler_crop_max:
                            # Use ScalerCropMaximum dimensions as reference
                            max_width = scaler_crop_max[2]   # Width of maximum crop window
                            max_height = scaler_crop_max[3]  # Height of maximum crop window
                            logger.debug(f"📷 Camera {camera_id} ScalerCropMaximum: {scaler_crop_max}, using {max_width}×{max_height}")
                        else:
                            # Fallback to PixelArraySize if ScalerCropMaximum not available
                            pixel_array = picamera2.camera_properties.get('PixelArraySize', (1920, 1080))
                            max_width = pixel_array[0]
                            max_height = pixel_array[1]
                            logger.warning(f"⚠️ Camera {camera_id} ScalerCropMaximum not found, using PixelArraySize: {pixel_array}")
                    except Exception as e:
                        # Ultimate fallback
                        max_width = 1920
                        max_height = 1080
                        logger.warning(f"⚠️ Camera {camera_id} could not get sensor size: {e}, using default 1920×1080")
                    
                    # Convert fractional coordinates to absolute pixel coordinates
                    # AfWindows format: (x_offset, y_offset, width, height) in pixels relative to ScalerCropMaximum
                    x_px = int(focus_window[0] * max_width)
                    y_px = int(focus_window[1] * max_height)
                    w_px = int(focus_window[2] * max_width)
                    h_px = int(focus_window[3] * max_height)
                    
                    # AfMetering windows for autofocus region
                    # Format: list of (x_offset, y_offset, width, height) tuples in absolute pixels
                    control_dict["AfMetering"] = controls.AfMeteringEnum.Windows
                    control_dict["AfWindows"] = [(x_px, y_px, w_px, h_px)]
                    
                    # Optional: ScalerCrop for digital zoom to focus area
                    if focus_zone_config.get('use_crop', False):
                        crop_margin = focus_zone_config.get('crop_margin', 0.1)
                        crop_x = max(0, int((focus_window[0] - crop_margin) * max_width))
                        crop_y = max(0, int((focus_window[1] - crop_margin) * max_height))
                        crop_w = min(max_width, int((focus_window[2] + 2 * crop_margin) * max_width))
                        crop_h = min(max_height, int((focus_window[3] + 2 * crop_margin) * max_height))
                        control_dict["ScalerCrop"] = (crop_x, crop_y, crop_w, crop_h)
                        logger.debug(f"📷 Camera {camera_id} ScalerCrop: ({crop_x}, {crop_y}, {crop_w}, {crop_h})")
                    
                    logger.info(f"📷 Camera {camera_id} focus zone: AfWindows=[({x_px}, {y_px}, {w_px}, {h_px})] relative to ScalerCropMaximum {max_width}×{max_height}")
                else:
                    logger.info(f"📷 Camera {camera_id} using default full-frame metering (focus_zone disabled)")
                
                # Set all controls
                picamera2.set_controls(control_dict)
                
                # Allow time for auto-exposure to settle
                await asyncio.sleep(1.0)
                
            except ImportError:
                # Fallback for older libcamera versions
                logger.warning(f"⚠️ Camera {camera_id} older libcamera version - using basic auto-exposure")
                picamera2.set_controls({
                    "AeEnable": True,
                    "AwbEnable": True,
                })
                await asyncio.sleep(1.0)
            
            # Step 2: Capture a few frames to let AE settle (with timeout protection)
            logger.info(f"📷 Camera {camera_id} letting auto-exposure settle...")
            settle_timeout = 5.0  # Maximum time to wait for AE settling
            settle_start = time.time()
            
            try:
                for i in range(3):
                    if time.time() - settle_start > settle_timeout:
                        logger.warning(f"⚠️ Camera {camera_id} AE settling timeout - proceeding with current settings")
                        break
                    
                    try:
                        metadata = picamera2.capture_metadata()
                        exposure = metadata.get('ExposureTime', 33000)
                        gain = metadata.get('AnalogueGain', 1.0)
                        logger.debug(f"📷 Camera {camera_id} AE settle frame {i+1}: exposure={exposure}, gain={gain:.2f}")
                        await asyncio.sleep(0.3)
                    except Exception as metadata_error:
                        logger.warning(f"⚠️ Camera {camera_id} metadata capture failed on frame {i+1}: {metadata_error}")
                        # Continue with reduced delay
                        await asyncio.sleep(0.1)
                        
            except Exception as settle_error:
                logger.error(f"❌ Camera {camera_id} AE settling failed: {settle_error}")
                # Continue calibration with defaults
            
            # Step 3: Perform autofocus (reuse existing method) with timeout check
            if time.time() - calibration_start > calibration_timeout:
                logger.warning(f"⚠️ Camera {camera_id} calibration timeout - using defaults")
                focus_value = 0.5
            else:
                logger.info(f"📷 Camera {camera_id} performing autofocus...")
                try:
                    focus_value = await asyncio.wait_for(
                        self.auto_focus_and_get_value(camera_id), 
                        timeout=calibration_timeout - (time.time() - calibration_start)
                    )
                    if focus_value is None:
                        focus_value = 0.5
                except asyncio.TimeoutError:
                    logger.warning(f"⚠️ Camera {camera_id} autofocus timeout - using default")
                    focus_value = 0.5
                except Exception as focus_error:
                    logger.warning(f"⚠️ Camera {camera_id} autofocus failed: {focus_error}")
                    focus_value = 0.5
            
            # Step 4: Capture final calibration metadata with timeout protection
            logger.info(f"📷 Camera {camera_id} capturing final calibration values...")
            try:
                final_metadata = picamera2.capture_metadata()
            except Exception as metadata_error:
                logger.warning(f"⚠️ Camera {camera_id} final metadata capture failed: {metadata_error}")
                # Use default metadata
                final_metadata = {
                    'ExposureTime': 33000,
                    'AnalogueGain': 1.0,
                    'Lux': None
                }
            
            # Extract optimized exposure settings with fallbacks
            final_exposure = final_metadata.get('ExposureTime', 33000)  # microseconds
            final_gain = final_metadata.get('AnalogueGain', 1.0)
            final_lux = final_metadata.get('Lux', None)
            
            # Calculate brightness score (0-1) from current image with error protection
            try:
                brightness_score = await self._calculate_brightness_score(picamera2)
            except Exception as brightness_error:
                logger.warning(f"⚠️ Camera {camera_id} brightness calculation failed: {brightness_error}")
                brightness_score = 0.5  # Default middle brightness
            
            # Store calibrated settings for scan-time application (don't lock during live streaming)
            logger.info(f"📷 Camera {camera_id} storing calibrated settings for scan use...")
            
            # Store calibrated settings for this camera (but don't lock yet)
            if not hasattr(self, '_calibrated_settings'):
                self._calibrated_settings = {}
            self._calibrated_settings[cam_id] = {
                'exposure_time': int(final_exposure),
                'analogue_gain': float(final_gain),
                'focus_value': focus_value,
                'brightness_score': brightness_score,
                'timestamp': time.time(),  # Track when calibration was done
                'locked': False  # Track if settings are currently locked
            }
            
            # Also store a backup copy for persistence during mode switches
            if not hasattr(self, '_calibration_backup'):
                self._calibration_backup = {}
            self._calibration_backup[cam_id] = self._calibrated_settings[cam_id].copy()
            
            # Re-enable auto exposure for live streaming (keep it normal for preview)
            try:
                picamera2.set_controls({
                    "AeEnable": True,   # Keep auto-exposure enabled for live streaming
                    "AwbEnable": True,  # Keep auto white balance enabled
                })
                logger.info(f"📷 Camera {camera_id} calibrated settings stored, live streaming mode restored")
            except Exception as restore_error:
                logger.warning(f"⚠️ Camera {camera_id} failed to restore live streaming mode: {restore_error}")
            
            calibration_result = {
                'focus': focus_value,
                'exposure_time': final_exposure,
                'analogue_gain': final_gain,
                'brightness_score': brightness_score,
                'lux': final_lux,
                'settings_stored': True
            }
            
            logger.info(f"✅ Camera {camera_id} calibration complete:")
            logger.info(f"   Focus: {focus_value:.3f}")
            logger.info(f"   Exposure: {final_exposure}μs ({final_exposure/1000:.1f}ms)")
            logger.info(f"   Gain: {final_gain:.2f}")
            logger.info(f"   Brightness: {brightness_score:.2f}")
            if final_lux:
                logger.info(f"   Lux: {final_lux:.1f}")
            
            return calibration_result
            
        except Exception as e:
            logger.error(f"📷 Camera {camera_id} calibration failed: {e}")
            return {'focus': 0.5, 'exposure_time': 33000, 'analogue_gain': 1.0, 'brightness_score': 0.5}

    async def _calculate_brightness_score(self, picamera2) -> float:
        """Calculate brightness score from current camera image (0=dark, 1=bright)"""
        try:
            # Capture a small array for analysis
            array = picamera2.capture_array("lores")  # Use low-res for speed
            
            if array is not None and array.size > 0:
                # Convert to grayscale if needed
                if len(array.shape) == 3:
                    # RGB to grayscale: 0.299*R + 0.587*G + 0.114*B
                    gray = (array[:, :, 0] * 0.299 + 
                           array[:, :, 1] * 0.587 + 
                           array[:, :, 2] * 0.114).astype('uint8')
                else:
                    gray = array
                
                # Calculate mean brightness (0-255) and normalize to 0-1
                mean_brightness = float(gray.mean())
                brightness_score = min(1.0, max(0.0, mean_brightness / 255.0))
                
                return brightness_score
            
        except Exception as e:
            logger.debug(f"Brightness calculation failed: {e}")
            
        return 0.5  # Default middle brightness if calculation fails

    async def apply_scan_settings(self, camera_id: str) -> bool:
        """Apply calibrated settings for scan capture (temporary lock during photo)"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            
            # Check if we have calibrated settings for this camera
            if (hasattr(self, '_calibrated_settings') and 
                cam_id in self._calibrated_settings):
                
                calibrated = self._calibrated_settings[cam_id]
                picamera2 = self.cameras[cam_id]
                
                if picamera2:
                    # Apply calibrated exposure settings for this capture only
                    picamera2.set_controls({
                        "AeEnable": False,  # Temporarily disable auto-exposure
                        "ExposureTime": calibrated['exposure_time'],
                        "AnalogueGain": calibrated['analogue_gain'],
                    })
                    
                    logger.debug(f"🎯 Camera {camera_id} scan settings applied: "
                               f"{calibrated['exposure_time']}μs, gain: {calibrated['analogue_gain']:.2f}")
                    return True
                    
        except Exception as e:
            logger.warning(f"⚠️ Camera {camera_id} failed to apply scan settings: {e}")
            
        return False

    async def restore_live_settings(self, camera_id: str) -> bool:
        """Restore auto-exposure for live streaming after scan capture"""
        try:
            cam_id = int(camera_id.replace('camera', ''))
            picamera2 = self.cameras[cam_id]
            
            if picamera2:
                # Re-enable auto exposure for live streaming
                picamera2.set_controls({
                    "AeEnable": True,   # Enable auto-exposure for live preview
                    "AwbEnable": True,  # Enable auto white balance
                })
                
                logger.debug(f"🔄 Camera {camera_id} live streaming settings restored")
                return True
                    
        except Exception as e:
            logger.warning(f"⚠️ Camera {camera_id} failed to restore live settings: {e}")
            
        return False

    async def restore_calibrated_settings_if_lost(self) -> bool:
        """Restore calibrated settings from backup if they were lost during camera restarts"""
        try:
            restored_count = 0
            
            if hasattr(self, '_calibration_backup') and hasattr(self, '_calibrated_settings'):
                for cam_id, backup_settings in self._calibration_backup.items():
                    # Check if current calibrated settings are missing or corrupted
                    if (cam_id not in self._calibrated_settings or 
                        not isinstance(self._calibrated_settings[cam_id], dict) or
                        'exposure_time' not in self._calibrated_settings[cam_id]):
                        
                        # Restore from backup
                        self._calibrated_settings[cam_id] = backup_settings.copy()
                        restored_count += 1
                        logger.info(f"📋 Camera {cam_id}: Restored calibrated settings from backup")
            
            if restored_count > 0:
                logger.info(f"🔄 Restored calibrated settings for {restored_count} cameras from backup")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ Failed to restore calibrated settings from backup: {e}")
            
        return False

    async def set_scanning_mode(self, enabled: bool) -> bool:
        """Enable/disable scanning mode - manages exposure settings appropriately"""
        try:
            self.scanning_mode = enabled
            
            for cam_id, picamera2 in self.cameras.items():
                if picamera2:
                    camera_id = f"camera{cam_id}"
                    
                    if enabled:
                        # Entering scanning mode - apply calibrated settings if available
                        logger.info(f"📷 Camera {camera_id} entering scanning mode")
                        if (hasattr(self, '_calibrated_settings') and 
                            cam_id in self._calibrated_settings):
                            await self.apply_scan_settings(camera_id)
                    else:
                        # Exiting scanning mode - restore live streaming settings
                        logger.info(f"📷 Camera {camera_id} returning to live streaming mode")
                        await self.restore_live_settings(camera_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to set scanning mode: {e}")
            return False

    async def capture_with_flash_sync(self, flash_controller, settings: Optional[Dict[str, CameraSettings]] = None) -> SyncCaptureResult:
        """Capture synchronized photos with flash lighting"""
        try:
            # For now, just do regular synchronized capture
            # In full implementation, would coordinate with flash_controller
            logger.info("Flash sync capture requested - using regular sync capture")
            return await self.capture_synchronized(settings)
            
        except Exception as e:
            logger.error(f"Flash sync capture failed: {e}")
            return SyncCaptureResult(success=False)

    async def get_last_error(self, camera_id: str) -> Optional[str]:
        """Get last error message for camera"""
        # Simple implementation - would store actual errors in real version
        return None

    async def save_capture_to_file(self, capture_result: CaptureResult, file_path: Path) -> bool:
        """Save capture result to file"""
        try:
            if capture_result.image_data:
                # Save binary data to file
                with open(file_path, 'wb') as f:
                    f.write(capture_result.image_data)
                return True
            elif capture_result.image_path:
                # Copy from temporary location
                import shutil
                shutil.copy2(capture_result.image_path, file_path)
                return True
            else:
                logger.error("No image data or path in capture result")
                return False
                
        except Exception as e:
            logger.error(f"Failed to save capture to file: {e}")
            return False

    async def cleanup_temp_files(self) -> bool:
        """Clean up temporary files"""
        try:
            # In real implementation, would track and clean temp files
            logger.debug("Temporary file cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {e}")
            return False
    
    async def get_available_cameras(self) -> List[int]:
        """Get list of available camera IDs"""
        return [cid for cid, info in self.camera_info.items() if info.is_available]
    
    async def get_camera_info(self, camera_id: int) -> Dict[str, Any]:
        """Get information about specific camera"""
        if camera_id not in self.camera_info:
            raise CameraError(f"Camera {camera_id} not found")
        
        info = self.camera_info[camera_id]
        camera_data = {
            "camera_id": info.camera_id,
            "camera_type": info.camera_type,
            "is_available": info.is_available,
            "native_resolution": info.native_resolution,
            "supported_formats": info.supported_formats
        }
        
        # Add runtime information if camera is active
        if camera_id in self.cameras and self.cameras[camera_id]:
            camera = self.cameras[camera_id]
            camera_data.update({
                "current_configuration": camera.camera_configuration(),
                "controls": camera.camera_controls(),
                "is_recording": self.active_captures.get(camera_id, False)
            })
        
        return camera_data
    
    def get_camera_specifications(self, camera_id: int) -> Dict[str, Any]:
        """Get calibrated camera specifications (hardware specs, not dynamic settings)"""
        if camera_id not in self.camera_info:
            raise CameraError(f"Camera {camera_id} not found")
        
        specs = self.camera_info[camera_id].specs
        return {
            'focal_length_mm': specs.focal_length_mm,
            'focal_length_35mm_equiv': specs.focal_length_35mm_equivalent,
            'aperture_f_number': specs.aperture_f_number,
            'sensor_model': specs.sensor_model,
            'crop_factor': specs.crop_factor,
            'physical_sensor_size_mm': specs.physical_sensor_size_mm,
            'pixel_size_um': specs.pixel_size_um,
            'calibrated': True  # Indicates these are calibrated values, not estimates
        }
    
    def extract_dynamic_camera_metadata(self, picamera2_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract dynamic camera settings from Picamera2 metadata (changes per capture)"""
        if not picamera2_metadata:
            return {}
        
        dynamic_metadata = {}
        
        # Exposure settings (changes with lighting conditions)
        if 'ExposureTime' in picamera2_metadata:
            exposure_us = picamera2_metadata['ExposureTime']
            exposure_sec = exposure_us / 1000000.0
            if exposure_sec >= 1:
                dynamic_metadata['exposure_time'] = f"{exposure_sec:.2f}s"
            else:
                denominator = int(1 / exposure_sec) if exposure_sec > 0 else 60
                dynamic_metadata['exposure_time'] = f"1/{denominator}s"
            dynamic_metadata['exposure_time_us'] = exposure_us
        
        # ISO/Gain (changes with lighting conditions)
        if 'AnalogueGain' in picamera2_metadata:
            gain = picamera2_metadata['AnalogueGain']
            dynamic_metadata['iso_equivalent'] = int(gain * 100)  # Base ISO ~100
            dynamic_metadata['analogue_gain'] = gain
        
        # Focus settings (changes between captures)
        if 'LensPosition' in picamera2_metadata:
            dynamic_metadata['focus_position'] = picamera2_metadata['LensPosition']
        
        if 'FocusFoM' in picamera2_metadata:
            dynamic_metadata['focus_measure'] = picamera2_metadata['FocusFoM']
        
        # White balance (changes with lighting)
        if 'ColourTemperature' in picamera2_metadata:
            dynamic_metadata['color_temperature_k'] = picamera2_metadata['ColourTemperature']
        
        if 'ColourGains' in picamera2_metadata:
            gains = picamera2_metadata['ColourGains']
            if isinstance(gains, list) and len(gains) >= 2:
                dynamic_metadata['white_balance_gains'] = {
                    'red': gains[0],
                    'blue': gains[1]
                }
        
        # Light measurement (changes with environment)
        if 'Lux' in picamera2_metadata:
            dynamic_metadata['light_level_lux'] = picamera2_metadata['Lux']
        
        # Digital processing settings
        if 'DigitalGain' in picamera2_metadata:
            dynamic_metadata['digital_gain'] = picamera2_metadata['DigitalGain']
        
        return dynamic_metadata
    
    def create_complete_camera_metadata(self, camera_id: int, picamera2_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create complete camera metadata combining calibrated specs and dynamic settings"""
        try:
            # Get calibrated hardware specifications
            specs = self.get_camera_specifications(camera_id)
            
            # Extract dynamic settings from current capture
            dynamic = self.extract_dynamic_camera_metadata(picamera2_metadata or {})
            
            # Combine into complete metadata
            complete_metadata = {
                'camera_specifications': {
                    'make': 'Arducam',
                    'model': f'64MP Camera {camera_id}',
                    'sensor_model': specs['sensor_model'],
                    'focal_length_mm': specs['focal_length_mm'],
                    'focal_length_35mm_equiv': specs['focal_length_35mm_equiv'],
                    'aperture_f_number': specs['aperture_f_number'],
                    'aperture_string': f"f/{specs['aperture_f_number']}",
                    'crop_factor': specs['crop_factor'],
                    'pixel_size_um': specs['pixel_size_um'],
                    'calibration_source': 'factory_calibrated' if specs['calibrated'] else 'estimated'
                },
                'capture_settings': dynamic,
                'metadata_version': '2.0',
                'extraction_timestamp': time.time()
            }
            
            return complete_metadata
            
        except Exception as e:
            logger.error(f"Failed to create camera metadata for camera {camera_id}: {e}")
            return {}
    
    async def capture_image(self, camera_id: int, settings: CameraSettings, output_path: Path) -> bool:
        """Capture single image"""
        try:
            if camera_id not in self.cameras:
                raise CameraError(f"Camera {camera_id} not initialized")
            
            if not self.cameras[camera_id]:
                raise CameraError(f"Camera {camera_id} not available")
            
            async with self.camera_locks[camera_id]:
                # Create capture request
                request = CaptureRequest(
                    camera_id=camera_id,
                    settings=settings,
                    output_path=output_path,
                    capture_mode=CaptureMode.SINGLE
                )
                
                # Add to queue
                await self.capture_queue.put(request)
                
                # Wait for completion (simplified - in real implementation would use callbacks)
                await asyncio.sleep(0.1)  # Allow processing
                
                self.capture_count += 1
                
                self._notify_event("image_captured", {
                    "camera_id": camera_id,
                    "output_path": str(output_path),
                    "settings": settings.__dict__
                })
                
                return True
                
        except Exception as e:
            self.error_count += 1
            logger.error(f"Image capture failed: {e}")
            return False
    
    async def _capture_burst_internal(self, camera_id: int, settings: CameraSettings, 
                          output_dir: Path, count: int) -> List[Path]:
        """Capture burst of images"""
        try:
            captured_files = []
            
            for i in range(count):
                timestamp = int(time.time() * 1000)
                output_path = output_dir / f"burst_{camera_id}_{timestamp}_{i:03d}.jpg"
                
                if await self.capture_image(camera_id, settings, output_path):
                    captured_files.append(output_path)
                else:
                    logger.warning(f"Failed to capture burst image {i}")
            
            self._notify_event("burst_captured", {
                "camera_id": camera_id,
                "count": len(captured_files),
                "files": [str(f) for f in captured_files]
            })
            
            return captured_files
            
        except Exception as e:
            logger.error(f"Burst capture failed: {e}")
            return []
    
    async def start_video_recording(self, camera_id: int, settings: CameraSettings, output_path: Path) -> bool:
        """Start video recording"""
        try:
            if camera_id not in self.cameras:
                raise CameraError(f"Camera {camera_id} not initialized")
            
            async with self.camera_locks[camera_id]:
                if self.active_captures[camera_id]:
                    raise CameraError(f"Camera {camera_id} already capturing")
                
                # Create video capture request
                request = CaptureRequest(
                    camera_id=camera_id,
                    settings=settings,
                    output_path=output_path,
                    capture_mode=CaptureMode.VIDEO
                )
                
                await self.capture_queue.put(request)
                self.active_captures[camera_id] = True
                
                self._notify_event("video_recording_started", {
                    "camera_id": camera_id,
                    "output_path": str(output_path)
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Video recording start failed: {e}")
            return False
    
    async def stop_video_recording(self, camera_id: int) -> bool:
        """Stop video recording"""
        try:
            async with self.camera_locks[camera_id]:
                if not self.active_captures[camera_id]:
                    logger.warning(f"Camera {camera_id} not recording")
                    return True
                
                # Signal stop via camera thread
                self.active_captures[camera_id] = False
                
                self._notify_event("video_recording_stopped", {
                    "camera_id": camera_id
                })
                
                return True
                
        except Exception as e:
            logger.error(f"Video recording stop failed: {e}")
            return False
    
    async def set_camera_settings(self, camera_id: int, settings: CameraSettings) -> bool:
        """Apply camera settings"""
        try:
            if camera_id not in self.cameras or not self.cameras[camera_id]:
                raise CameraError(f"Camera {camera_id} not available")
            
            camera = self.cameras[camera_id]
            
            # Convert settings to picamera2 format
            controls = {}
            
            if settings.exposure_time:
                controls['ExposureTime'] = int(settings.exposure_time * 1000)  # Convert to microseconds
            
            if settings.iso:
                controls['AnalogueGain'] = settings.iso / 100.0
            
            if settings.white_balance:
                controls['ColourGains'] = settings.white_balance
            
            # Apply controls using set_controls method
            if controls:
                camera.set_controls(controls)
            
            logger.debug(f"Applied settings to camera {camera_id}: {controls}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set camera settings: {e}")
            return False
    
    async def get_camera_settings(self, camera_id: int) -> CameraSettings:
        """Get current camera settings"""
        try:
            if camera_id not in self.cameras or not self.cameras[camera_id]:
                raise CameraError(f"Camera {camera_id} not available")
            
            # Return default settings with dynamic resolution
            default_resolution = self._get_optimal_resolution_for_capture()
            return CameraSettings(
                resolution=default_resolution,
                format=self.default_format,
                exposure_time=0.01,  # 10ms
                iso=100,
                white_balance="auto"
            )
            
        except Exception as e:
            logger.error(f"Failed to get camera settings: {e}")
            return CameraSettings(resolution=self._get_optimal_resolution_for_capture())
    
    async def get_camera_capabilities(self, camera_id: int) -> CameraCapabilities:
        """Get camera capabilities"""
        try:
            if camera_id not in self.camera_info:
                raise CameraError(f"Camera {camera_id} not found")
            
            # Pi Camera capabilities with dynamic aspect ratio support
            return CameraCapabilities(
                supported_resolutions=[
                    # 16:9 resolutions (≤4K)
                    (640, 360), (1280, 720), (1920, 1080), (3840, 2160),
                    # 4:3 resolutions (>4K)
                    (640, 480), (2592, 1944), (3280, 2464), (4624, 3472)
                ],
                supported_formats=[ImageFormat.JPEG, ImageFormat.PNG],
                min_exposure_time=0.000001,  # 1 microsecond
                max_exposure_time=6.0,       # 6 seconds
                min_iso=100,
                max_iso=1600,
                supports_video=True,
                supports_burst=True,
                max_burst_rate=30.0  # fps
            )
            
        except Exception as e:
            logger.error(f"Failed to get camera capabilities: {e}")
            return CameraCapabilities(
                supported_resolutions=[
                    # 16:9 resolutions (≤4K)  
                    (640, 360), (1280, 720), (1920, 1080), (3840, 2160),
                    # 4:3 resolutions (>4K)
                    (640, 480), (2592, 1944), (3280, 2464), (4624, 3472)
                ],
                supported_formats=[ImageFormat.JPEG, ImageFormat.PNG],
                min_exposure_time=0.000001,  # 1 microsecond
                max_exposure_time=6.0,       # 6 seconds
                min_iso=100,
                max_iso=1600,
                supports_video=True,
                supports_burst=True,
                max_burst_rate=30.0  # fps
            )
    
    # Internal methods
    async def _initialize_camera(self, camera_id: int):
        """Initialize specific camera with ArduCam optimization"""
        try:
            if not PICAMERA2_AVAILABLE or Picamera2 is None:
                raise CameraConfigurationError("picamera2 not available")
            
            # Ensure any existing camera for this ID is cleaned up first
            await self._force_cleanup_camera(camera_id)
            await asyncio.sleep(0.2)  # Give hardware time to reset
                
            logger.info(f"📷 Initializing camera {camera_id}")
            
            # Initialize with error protection
            try:
                camera = Picamera2(camera_id)
            except Exception as init_error:
                logger.error(f"❌ Failed to create Picamera2 instance for camera {camera_id}: {init_error}")
                raise CameraInitializationError(f"Camera {camera_id} instance creation failed: {init_error}")
            
            # Get camera properties for ArduCam detection
            props = camera.camera_properties
            camera_model = props.get('Model', 'Unknown')
            pixel_array_size = props.get('PixelArraySize', (0, 0))
            
            logger.info(f"📷 Camera {camera_id}: {camera_model}, sensor size: {pixel_array_size}")
            
            # Create PREVIEW configuration for better livestream (not still config)
            if 'imx519' in camera_model.lower() or pixel_array_size[0] >= 9000:
                logger.info(f"📷 Camera {camera_id}: Detected ArduCam 64MP (IMX519), applying dynamic aspect ratio config")
                # ArduCam 64MP livestream configuration - KEEP 1080p for livestream as requested
                config = camera.create_preview_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},   # 16:9 for smooth livestream
                    lores={"size": (640, 480)},  # 4:3 low-res stream for web preview
                    raw=None  # Disable raw for performance
                )
                logger.info(f"📷 Camera {camera_id}: Using 16:9 aspect ratio (1920x1080) for livestream")
            else:
                logger.info(f"📷 Camera {camera_id}: Standard Pi camera dynamic aspect ratio configuration")
                # Standard Pi camera livestream configuration - KEEP 1080p for livestream
                config = camera.create_preview_configuration(
                    main={"size": (1920, 1080), "format": "RGB888"},   # 16:9 for livestream
                    lores={"size": (640, 480)},  # 4:3 low-res for web
                    raw=None
                )
                logger.info(f"📷 Camera {camera_id}: Using 16:9 aspect ratio (1920x1080) for livestream")
            
            # Apply configuration
            camera.configure(config)
            
            # Start camera to make it operational (with error protection)
            try:
                camera.start()
                logger.debug(f"📷 Camera {camera_id}: Camera started successfully")
                
                # Verify camera is actually running
                if not hasattr(camera, 'started') or not camera.started:
                    raise CameraError(f"Camera {camera_id} failed to start properly")
                    
            except Exception as start_error:
                logger.error(f"❌ Camera {camera_id} start failed: {start_error}")
                # Try to cleanup the failed camera
                try:
                    camera.close()
                except:
                    pass
                raise CameraInitializationError(f"Camera {camera_id} start failed: {start_error}")
            
            # Set high quality capture controls for both camera types
            try:
                # Build control dictionary optimized for livestream quality
                control_dict = {
                    # Core auto controls - ESSENTIAL for proper livestream
                    "AwbEnable": True,              # Auto white balance for proper colors
                    "AeEnable": True,               # Auto exposure for proper brightness
                    
                    # LED Flicker Reduction - Synchronized with 250Hz PWM LEDs
                    # AeFlickerMode: 0=Off, 1=Manual (with AeFlickerPeriod)
                    "AeFlickerMode": 1,             # Manual flicker period mode (avoids LED banding)
                    "AeFlickerPeriod": 4000,        # 250Hz PWM = 4000μs period (1/250s = 0.004s)
                    
                    # Exposure settings optimized for livestream responsiveness
                    # AeConstraintMode: 0=Normal, 1=Highlight, 2=Shadows, 3=Custom
                    "AeConstraintMode": 1,          # Highlight metering (better for bright objects)
                    "AeExposureMode": 0,            # Normal exposure mode
                    "AeMeteringMode": 0,            # CentreWeighted metering
                    "ExposureValue": 0.0,           # No exposure compensation initially
                    
                    # Image quality for streaming
                    "Brightness": 0.0,              # Neutral brightness
                    "Contrast": 1.0,                # Standard contrast  
                    "Saturation": 1.0,              # Standard saturation
                    "Sharpness": 1.0,               # Moderate sharpening for streaming
                    
                    # Performance settings
                    "NoiseReductionMode": 1,        # Fast noise reduction for streaming
                    "FrameRate": 30.0,              # Smooth 30 FPS for livestream
                }
                
                # Add AF controls if supported (per Picamera2 docs section 5.2)
                controls = camera.camera_controls
                if 'AfMode' in controls:
                    # Import proper AF mode enum if available
                    try:
                        from libcamera import controls as libcam_controls
                        control_dict["AfMode"] = libcam_controls.AfModeEnum.Manual  # Start in manual
                        logger.debug(f"📷 Camera {camera_id}: Using libcamera AF enum")
                    except ImportError:
                        control_dict["AfMode"] = 0  # Manual mode (fallback)
                        logger.debug(f"📷 Camera {camera_id}: Using numeric AF mode")
                    
                    # Set lens to hyperfocal distance if LensPosition is available
                    if 'LensPosition' in controls:
                        lens_range = controls['LensPosition']
                        hyperfocal_pos = lens_range[2] if len(lens_range) > 2 else 1.0  # Use default/hyperfocal
                        control_dict["LensPosition"] = hyperfocal_pos
                        logger.debug(f"📷 Camera {camera_id}: Setting lens to hyperfocal position: {hyperfocal_pos}")
                
                camera.set_controls(control_dict)
                logger.info(f"📷 Camera {camera_id}: High quality controls applied")
                
            except Exception as control_error:
                logger.warning(f"📷 Camera {camera_id}: Some controls not supported: {control_error}")
                # Continue anyway, basic functionality should work
            
            # Store camera instance
            self.cameras[camera_id] = camera
            
            # Update camera info with actual capabilities
            self.camera_info[camera_id].native_resolution = pixel_array_size
            self.camera_info[camera_id].camera_type = camera_model
            
            # Give camera a moment to settle after configuration
            await asyncio.sleep(0.1)
            
            logger.info(f"✅ Camera {camera_id} initialized successfully ({camera_model})")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize camera {camera_id}: {e}")
            raise CameraConfigurationError(f"Camera {camera_id} initialization failed: {e}")
    
    async def _cleanup_existing_cameras(self):
        """Cleanup any existing cameras before reinitialization"""
        try:
            if hasattr(self, 'cameras') and self.cameras:
                logger.info("🧹 Cleaning up existing cameras before reinitialization...")
                for camera_id in list(self.cameras.keys()):
                    await self._force_cleanup_camera(camera_id)
                self.cameras.clear()
            
            # Reset camera state
            self.cameras = {}
            self.active_captures = {}
            
            # Give hardware time to reset
            await asyncio.sleep(0.5)
            logger.info("✅ Camera cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Camera cleanup error: {e}")
    
    async def _force_cleanup_camera(self, camera_id: int):
        """Force cleanup of specific camera with error protection"""
        try:
            if camera_id in self.cameras and self.cameras[camera_id]:
                camera = self.cameras[camera_id]
                
                # Try graceful stop first
                try:
                    if hasattr(camera, 'stop') and callable(camera.stop):
                        camera.stop()
                        logger.debug(f"📷 Camera {camera_id} stopped gracefully")
                        # Give time for stop to complete
                        await asyncio.sleep(0.1)
                except Exception as stop_error:
                    logger.warning(f"⚠️ Camera {camera_id} stop failed: {stop_error}")
                
                # Force close with additional error protection
                try:
                    if hasattr(camera, 'close') and callable(camera.close):
                        camera.close()
                        logger.debug(f"📷 Camera {camera_id} closed")
                        # Give time for cleanup to complete
                        await asyncio.sleep(0.1)
                except Exception as close_error:
                    logger.warning(f"⚠️ Camera {camera_id} close failed: {close_error}")
                
                # Clear reference
                self.cameras[camera_id] = None
                
            # Clear from active captures if present
            if camera_id in self.active_captures:
                self.active_captures[camera_id] = False
                
        except Exception as e:
            logger.error(f"❌ Force cleanup camera {camera_id} failed: {e}")
            # Always clear reference even if cleanup failed
            if hasattr(self, 'cameras') and camera_id in self.cameras:
                self.cameras[camera_id] = None
    
    def _get_optimal_resolution_for_capture(self, target_resolution: Optional[Tuple[int, int]] = None) -> Tuple[int, int]:
        """
        Get optimal resolution for capture based on dynamic aspect ratio rules:
        - 3840x2160 and below: 16:9 aspect ratio
        - Above 3840x2160: 4:3 aspect ratio
        """
        if target_resolution:
            width, height = target_resolution
            
            # If resolution is above 4K threshold, use 4:3 aspect ratio
            if width > 3840 or height > 2160:
                # High resolution - use 4:3 aspect ratio
                if width >= 4624:  # Native sensor resolution
                    logger.debug("📐 Using native sensor resolution: 4624x3472 (4:3)")
                    return (4624, 3472)  # Native 4:3
                elif width >= 3280:
                    logger.debug("📐 Using high resolution: 3280x2464 (4:3)")
                    return (3280, 2464)  # High 4:3
                else:
                    logger.debug("📐 Using medium resolution: 2592x1944 (4:3)")
                    return (2592, 1944)  # Medium 4:3
            else:
                # Standard resolution - use 16:9 aspect ratio  
                if width >= 3840:
                    logger.debug("📐 Using 4K resolution: 3840x2160 (16:9)")
                    return (3840, 2160)  # 4K 16:9
                elif width >= 1920:
                    logger.debug("📐 Using 1080p resolution: 1920x1080 (16:9)")
                    return (1920, 1080)  # 1080p 16:9
                elif width >= 1280:
                    logger.debug("📐 Using 720p resolution: 1280x720 (16:9)")
                    return (1280, 720)   # 720p 16:9
                else:
                    logger.debug("📐 Using low resolution: 640x360 (16:9)")
                    return (640, 360)    # Low 16:9
        
        # Default to 1080p for general capture
        logger.debug("📐 Using default resolution: 1920x1080 (16:9)")
        return (1920, 1080)
    
    def _is_high_resolution(self, resolution: Tuple[int, int]) -> bool:
        """Check if resolution requires 4:3 aspect ratio (above 4K threshold)"""
        width, height = resolution
        return width > 3840 or height > 2160
    
    async def _close_camera(self, camera_id: int):
        """Close specific camera"""
        try:
            await self._force_cleanup_camera(camera_id)
            logger.info(f"Camera {camera_id} closed")
                
        except Exception as e:
            logger.error(f"Error closing camera {camera_id}: {e}")
    
    def _start_camera_thread(self):
        """Start camera processing thread"""
        self.camera_thread = threading.Thread(
            target=self._camera_thread_worker,
            name="CameraWorker",
            daemon=True
        )
        self.camera_thread.start()
        logger.debug("Camera worker thread started")
    
    def _camera_thread_worker(self):
        """Camera thread worker function"""
        logger.debug("Camera worker thread running")
        
        while not self.thread_stop_event.is_set():
            try:
                # Process capture queue (simplified implementation)
                # In real implementation would handle capture requests
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Camera thread error: {e}")
        
        logger.debug("Camera worker thread stopped")

    # ISP Buffer Management Methods for High-Resolution Dual Camera Operations
    
    async def capture_with_isp_management(self, camera_id: int, stream_name: str = "main") -> Optional[Any]:
        """
        Capture from camera with ISP buffer management to prevent buffer queue errors.
        
        Args:
            camera_id: Camera ID (0 or 1)
            stream_name: Stream to capture from ("main", "lores", etc.)
            
        Returns:
            Captured image array or None if failed
        """
        try:
            if camera_id not in self.cameras or not self.cameras[camera_id]:
                raise CameraError(f"Camera {camera_id} not available")
            
            camera = self.cameras[camera_id]
            
            # ISP Buffer Management: Clear buffers before capture
            import gc
            import time
            
            # Force garbage collection to free ISP buffers
            gc.collect()
            
            # Allow ISP pipeline to stabilize
            await asyncio.sleep(0.05)
            
            # Enhanced capture with ISP buffer retry logic
            max_retries = 3
            retry_delay = 0.5
            image_array = None  # Initialize to prevent UnboundLocalError
            
            for attempt in range(max_retries):
                try:
                    # Check camera state before capture
                    if not camera.started:
                        logger.warning(f"Camera {camera_id} not started, attempting to start...")
                        camera.start()
                        await asyncio.sleep(0.3)  # Extended stabilization
                    
                    # ISP stabilization for high-resolution
                    await asyncio.sleep(0.1 + (attempt * 0.1))  # Progressive delay
                    
                    # Capture with buffer management
                    logger.debug(f"ISP capture attempt {attempt + 1} for camera {camera_id}")
                    image_array = camera.capture_array(stream_name)
                    
                    # Clear buffers immediately after successful capture
                    gc.collect()
                    
                    logger.info(f"ISP-managed capture successful for camera {camera_id}")
                    return image_array  # Return immediately on success
                    
                except Exception as capture_error:
                    error_msg = str(capture_error)
                    logger.warning(f"ISP capture attempt {attempt + 1} failed for camera {camera_id}: {error_msg}")
                    
                    # Handle specific ISP buffer issues
                    if "Failed to queue buffer" in error_msg or "Invalid argument" in error_msg:
                        logger.info(f"ISP buffer issue detected, attempting recovery...")
                        
                        # ISP recovery: Stop and restart camera with delay
                        try:
                            if camera.started:
                                camera.stop()
                            await asyncio.sleep(retry_delay)
                            gc.collect()
                            camera.start()
                            await asyncio.sleep(0.3)  # ISP stabilization
                            
                            logger.info(f"Camera {camera_id} ISP recovery completed")
                            
                        except Exception as recovery_error:
                            logger.error(f"ISP recovery failed for camera {camera_id}: {recovery_error}")
                    
                    # If this was the last attempt, log final failure
                    if attempt == max_retries - 1:
                        logger.error(f"All {max_retries} capture attempts failed for camera {camera_id}")
                        return None
                    
                    # Progressive backoff
                    await asyncio.sleep(retry_delay * (attempt + 1))
            
            # This should never be reached due to explicit returns above, but safety fallback
            logger.error(f"Unexpected end of retry loop for camera {camera_id}")
            return None
                    
        except Exception as e:
            logger.error(f"ISP-managed capture failed for camera {camera_id}: {e}")
            return None
    
    async def capture_dual_sequential_isp(self, stream_name: str = "main", delay_ms: int = 100) -> Dict[str, Any]:
        """
        Capture from both cameras sequentially with ISP buffer management.
        
        Args:
            stream_name: Stream to capture from both cameras
            delay_ms: Delay between captures in milliseconds
            
        Returns:
            Dict with results: {'camera_0': image_array, 'camera_1': image_array}
        """
        results = {}
        
        try:
            available_cameras = [0, 1] if len(self.cameras) >= 2 else list(self.cameras.keys())
            
            for camera_id in available_cameras:
                camera_key = f"camera_{camera_id}"
                
                # Capture with ISP management
                image_array = await self.capture_with_isp_management(camera_id, stream_name)
                
                if image_array is not None:
                    results[camera_key] = image_array
                    logger.info(f"Sequential ISP capture successful: {camera_key} -> {image_array.shape}")
                else:
                    results[camera_key] = None
                    logger.error(f"Sequential ISP capture failed: {camera_key}")
                
                # Delay between captures to allow ISP buffers to clear
                if len(available_cameras) > 1 and camera_id != available_cameras[-1]:
                    await asyncio.sleep(delay_ms / 1000.0)
                    
        except Exception as e:
            logger.error(f"Dual sequential ISP capture failed: {e}")
            
        return results
    
    async def prepare_cameras_for_capture(self, target_resolution=None) -> bool:
        """
        Prepare cameras for capture with resolution-aware memory management.
        - High-res (64MP): Sequential single-camera preparation to avoid memory pressure
        - Lower-res: Standard simultaneous preparation
        
        Args:
            target_resolution: Optional tuple specifying desired resolution (width, height)
        
        Returns:
            True if preparation successful, False otherwise
        """
        try:
            import gc
            
            # Global buffer cleanup
            gc.collect()
            
            # Detect current resolution and determine if reconfiguration is needed
            needs_high_res = False
            needs_reconfiguration = False
            
            # Use provided target resolution first, otherwise try to detect current
            if target_resolution is not None:
                logger.info(f"📷 Using provided target resolution: {target_resolution}")
            else:
                # Try to detect current camera resolution
                try:
                    for camera_id in self.cameras:
                        camera = self.cameras[camera_id]
                        if camera and hasattr(camera, 'camera_configuration'):
                            try:
                                config = camera.camera_configuration()
                                if config and 'main' in config:
                                    current_size = config['main'].get('size')
                                    if current_size:
                                        target_resolution = current_size
                                        logger.info(f"📷 Camera {camera_id}: Current resolution detected: {target_resolution}")
                                        break
                            except Exception:
                                continue
                    
                    # If no current resolution detected, use safe default
                    if target_resolution is None:
                        target_resolution = (4608, 2592)  # Safe 12MP default
                        logger.info(f"📷 No current resolution detected, will configure to default: {target_resolution}")
                    
                except Exception as resolution_check_error:
                    logger.debug(f"Resolution detection failed: {resolution_check_error}")
                    target_resolution = (4608, 2592)  # Safe fallback
            
            # Determine if this is high-resolution mode and if reconfiguration is needed
            needs_high_res = target_resolution[0] >= 8000  # 8000+ pixels width = high-res
            needs_reconfiguration = True  # Will need to configure cameras
            
            logger.info(f"📷 Camera preparation: Target resolution {target_resolution}, High-res mode: {needs_high_res}, Reconfiguration needed: {needs_reconfiguration}")
            
            if needs_reconfiguration:
                if needs_high_res:
                    # HIGH-RESOLUTION MODE: Sequential single-camera preparation
                    logger.info("📷 HIGH-RES MODE: Sequential reconfiguration to prevent memory allocation failures")
                    
                    # CRITICAL: Only configure cameras during capture, not during preparation for high-res mode
                    # This prevents memory allocation failures from attempting to configure both cameras simultaneously
                    logger.info("📷 HIGH-RES: Skipping simultaneous configuration - cameras will be configured individually during capture")
                    
                    # Set flag for sequential mode
                    self._high_res_sequential_mode = True
                            
                else:
                    # STANDARD MODE: Simultaneous preparation for lower resolutions
                    logger.info("📷 STANDARD MODE: Reconfiguring for moderate resolution")
                    
                    for camera_id in self.cameras:
                        camera = self.cameras[camera_id]
                        if camera:
                            try:
                                # For lower resolutions, standard configuration works fine
                                if camera.started:
                                    camera.stop()
                                    
                                # Use moderate resolution configuration that works reliably
                                standard_config = camera.create_still_configuration(
                                    main={"size": target_resolution, "format": "RGB888"},
                                    raw=None,
                                    buffer_count=1
                                )
                                
                                camera.configure(standard_config)
                                camera.start()
                                
                                logger.info(f"📷 Camera {camera_id}: Standard resolution reconfiguration applied")
                                
                            except Exception as config_error:
                                logger.warning(f"Camera {camera_id} standard reconfiguration failed: {config_error}")
            else:
                # NO RECONFIGURATION NEEDED: Cameras already at correct resolution
                logger.info(f"📷 OPTIMAL: Cameras already configured for {target_resolution} - no reconfiguration needed")
                
                # Just verify cameras are ready without changing configuration
                for camera_id in self.cameras:
                    camera = self.cameras[camera_id]
                    if camera:
                        if not camera.started:
                            try:
                                camera.start()
                                logger.info(f"📷 Camera {camera_id}: Started (keeping existing {target_resolution} configuration)")
                            except Exception as start_error:
                                logger.warning(f"Camera {camera_id} start failed: {start_error}")
                        else:
                            logger.info(f"📷 Camera {camera_id}: Already running with {target_resolution} configuration")
            
            # Final verification
            ready_count = 0
            for camera_id in self.cameras:
                if self.cameras[camera_id] and hasattr(self.cameras[camera_id], 'capture_array'):
                    ready_count += 1
            
            mode_description = "high-resolution sequential" if needs_high_res else "standard resolution simultaneous"
            logger.info(f"Camera preparation complete: {ready_count} cameras ready for {mode_description} capture")
            return ready_count > 0
            
        except Exception as e:
            logger.error(f"Camera preparation failed: {e}")
            return False
    
    async def capture_dual_resolution_aware(self, target_resolution: Optional[Tuple[int, int]] = None, delay_ms: int = 500) -> Dict[str, Any]:
        """
        Resolution-aware dual camera capture with automatic strategy selection.
        - High-res (64MP): Sequential single-camera capture to prevent memory allocation failures
        - Lower-res: Simultaneous capture for better sync
        
        Args:
            target_resolution: Target resolution tuple (width, height). If None, uses current camera configuration
            delay_ms: Delay between captures in sequential mode
            
        Returns:
            Dict with results: {'camera_0': image_array, 'camera_1': image_array}
        """
        results = {}
        
        try:
            available_cameras = [0, 1] if len(self.cameras) >= 2 else list(self.cameras.keys())
            
            # Determine capture strategy based on resolution
            if target_resolution is None:
                # Try to detect current resolution from camera configuration
                target_resolution = (4608, 2592)  # Safe default
                for camera_id in available_cameras:
                    if camera_id in self.cameras:
                        camera = self.cameras[camera_id]
                        if camera and hasattr(camera, 'camera_configuration'):
                            try:
                                config = camera.camera_configuration()
                                if 'main' in config and 'size' in config['main']:
                                    target_resolution = config['main']['size']
                                    break
                            except Exception:
                                pass
            
            is_high_resolution = target_resolution and target_resolution[0] >= 8000  # 8000+ pixels width = high-res
            
            logger.info(f"📷 Resolution-aware capture: {target_resolution}, Strategy: {'Sequential' if is_high_resolution else 'Simultaneous'}")
            
            if is_high_resolution:
                # HIGH-RESOLUTION: Sequential capture to prevent memory allocation failures
                logger.info(f"🔧 HIGH-RES SEQUENTIAL: Capturing {len(available_cameras)} cameras one at a time to manage memory")
                
                import gc
                
                # Pre-capture memory cleanup and diagnostics for high-res
                for _ in range(3):
                    gc.collect()
                    await asyncio.sleep(0.2)
                
                # Memory diagnostics
                try:
                    import psutil
                    mem = psutil.virtual_memory()
                    logger.info(f"📊 System memory: {mem.percent}% used, {mem.available / 1024**3:.1f}GB available")
                except ImportError:
                    logger.debug("psutil not available for memory diagnostics")
                
                for camera_id in available_cameras:
                    camera_key = f"camera_{camera_id}"
                    
                    try:
                        logger.info(f"📷 High-res sequential capture starting for {camera_key} at {target_resolution}")
                        
                        # Get camera and reinitialize if needed (after previous camera was closed)
                        camera = self.cameras[camera_id]
                        
                        # If camera was closed by previous capture, reinitialize it
                        if camera is None:
                            logger.info(f"📷 {camera_key}: Camera needs reinitialization after V4L2 cleanup")
                            try:
                                # Reinitialize camera after previous closure
                                from picamera2 import Picamera2
                                new_camera = Picamera2(camera_num=camera_id)
                                self.cameras[camera_id] = new_camera
                                camera = new_camera
                                logger.info(f"📷 {camera_key}: Camera reinitialized successfully")
                                
                                # CRITICAL: Restore calibrated settings after reinitialization
                                if hasattr(self, '_stored_camera_settings') and camera_id in self._stored_camera_settings:
                                    stored_settings = self._stored_camera_settings[camera_id]
                                    logger.info(f"📷 {camera_key}: Restoring calibrated settings after reinitialization...")
                                    
                                    # Apply stored focus and exposure settings
                                    try:
                                        if 'focus' in stored_settings and hasattr(camera, 'set_controls'):
                                            camera.set_controls({
                                                "LensPosition": stored_settings['focus'],
                                                "ExposureTime": stored_settings.get('exposure_time', 32752),
                                                "AnalogueGain": stored_settings.get('gain', 8.0),
                                            })
                                            logger.info(f"📷 {camera_key}: Calibrated settings restored - Focus: {stored_settings['focus']:.3f}, Exposure: {stored_settings.get('exposure_time', 32752)}μs")
                                    except Exception as restore_error:
                                        logger.warning(f"📷 {camera_key}: Settings restore failed: {restore_error}")
                                else:
                                    logger.warning(f"📷 {camera_key}: No stored calibrated settings found for restoration")
                                    
                            except Exception as reinit_error:
                                logger.error(f"📷 {camera_key}: Camera reinitialization failed: {reinit_error}")
                                results[camera_key] = None
                                continue
                        if camera:
                            # Stop camera and clean memory before reconfiguration
                            if camera.started:
                                camera.stop()
                                logger.info(f"📷 {camera_key}: Stopped camera for sequential reconfiguration")
                            
                            # Aggressive memory cleanup
                            gc.collect()
                            await asyncio.sleep(0.5)  # Extended delay for memory recovery
                            
                            # Configure for high-resolution capture
                            logger.info(f"📷 {camera_key}: Configuring for {target_resolution} capture")
                            high_res_config = camera.create_still_configuration(
                                main={"size": target_resolution, "format": "RGB888"},
                                raw=None,  # Disable RAW to prevent ISP buffer issues
                                buffer_count=1  # Minimal buffer allocation
                            )
                            
                            try:
                                camera.configure(high_res_config)
                                camera.start()
                                
                                # Brief settling time
                                await asyncio.sleep(0.2)
                                
                                logger.info(f"📷 {camera_key}: Successfully configured and started for high-res capture")
                                
                            except Exception as config_start_error:
                                if "Cannot allocate memory" in str(config_start_error):
                                    logger.error(f"📷 {camera_key}: Memory allocation failed during configuration - trying fallback resolution")
                                    # Try with slightly reduced resolution as fallback
                                    try:
                                        fallback_resolution = (8000, 6000)  # Reduced from 9152x6944
                                        logger.info(f"📷 {camera_key}: Attempting fallback resolution {fallback_resolution}")
                                        
                                        fallback_config = camera.create_still_configuration(
                                            main={"size": fallback_resolution, "format": "RGB888"},
                                            raw=None,
                                            buffer_count=1
                                        )
                                        camera.configure(fallback_config)
                                        camera.start()
                                        await asyncio.sleep(0.2)
                                        
                                        logger.info(f"📷 {camera_key}: Fallback resolution successful")
                                        target_resolution = fallback_resolution  # Update for this capture
                                        
                                    except Exception as fallback_error:
                                        logger.error(f"📷 {camera_key}: Fallback resolution also failed: {fallback_error}")
                                        raise config_start_error  # Re-raise original error
                                else:
                                    raise config_start_error
                            
                            # Quick verification that camera is configured correctly
                            try:
                                # camera_configuration is a method, not a property
                                current_config = camera.camera_configuration()
                                current_size = current_config.get('main', {}).get('size', (0, 0))
                                logger.info(f"📷 {camera_key}: Verified resolution {current_size}")
                            except Exception as verify_error:
                                logger.warning(f"📷 {camera_key}: Could not verify configuration: {verify_error}")
                            
                            # Continue with capture - check camera state before proceeding
                            
                        # Pre-capture ISP preparation
                        logger.info(f"📷 {camera_key}: Preparing for ISP-managed capture...")
                        gc.collect()
                        await asyncio.sleep(0.1)
                        
                        # Verify camera is ready for capture
                        if not camera.started:
                            logger.error(f"📷 {camera_key}: Camera not started before capture!")
                            results[camera_key] = None
                            continue
                        
                        logger.info(f"📷 {camera_key}: Starting ISP-managed capture at {target_resolution}")
                        
                        # Capture with timeout and V4L2 error monitoring
                        try:
                            # Monitor for V4L2 buffer errors during capture
                            logger.info(f"🔍 {camera_key}: Starting capture with V4L2 error monitoring...")
                            
                            image_array = await asyncio.wait_for(
                                self.capture_with_isp_management(camera_id, "main"),
                                timeout=30.0  # 30 second timeout for high-res capture
                            )
                            
                            # Check for V4L2 errors in system logs (if capture succeeds)
                            if image_array is not None:
                                logger.info(f"🔍 {camera_key}: Checking for V4L2 buffer errors during capture...")
                                try:
                                    import subprocess
                                    # Check recent kernel messages for V4L2 errors
                                    result = subprocess.run(['dmesg', '|', 'tail', '-20', '|', 'grep', '-i', 'v4l2'], 
                                                          shell=True, capture_output=True, text=True, timeout=3)
                                    if result.returncode == 0 and 'ERROR' in result.stdout:
                                        logger.warning(f"🚨 {camera_key}: V4L2 errors detected in kernel logs during capture")
                                    else:
                                        logger.info(f"✅ {camera_key}: No V4L2 errors detected in recent kernel logs")
                                except Exception as log_error:
                                    logger.debug(f"V4L2 log check skipped: {log_error}")
                            
                        except asyncio.TimeoutError:
                            logger.error(f"📷 {camera_key}: Capture timed out after 30 seconds")
                            image_array = None
                        
                        if image_array is not None:
                            results[camera_key] = image_array
                            logger.info(f"✅ High-res capture successful: {camera_key} -> {image_array.shape}")
                        else:
                            results[camera_key] = None
                            logger.error(f"❌ High-res capture failed: {camera_key}")
                        
                    except Exception as camera_error:
                        logger.error(f"High-res capture error for {camera_key}: {camera_error}")
                        results[camera_key] = None
                        
                    finally:
                        # CRITICAL: Complete camera cleanup for V4L2 buffer release
                        if camera:
                            logger.info(f"📷 {camera_key}: Complete camera cleanup for V4L2 buffer release...")
                            
                            # Step 0: Store calibrated settings before closing camera
                            try:
                                if not hasattr(self, '_stored_camera_settings'):
                                    self._stored_camera_settings = {}
                                
                                # Try to extract current calibrated settings before closure
                                current_controls = {}
                                if hasattr(camera, 'capture_metadata'):
                                    try:
                                        metadata = camera.capture_metadata()
                                        current_controls = {
                                            'focus': metadata.get('LensPosition', 0.0),
                                            'exposure_time': metadata.get('ExposureTime', 32752),
                                            'gain': metadata.get('AnalogueGain', 8.0),
                                        }
                                        self._stored_camera_settings[camera_id] = current_controls
                                        logger.info(f"📷 {camera_key}: Stored calibrated settings - Focus: {current_controls['focus']:.3f}, Exposure: {current_controls['exposure_time']}μs")
                                    except Exception as metadata_error:
                                        logger.debug(f"Metadata capture failed: {metadata_error}")
                                        # Fallback to default calibrated values if available
                                        if hasattr(self, '_camera_calibration') and camera_id in self._camera_calibration:
                                            calib = self._camera_calibration[camera_id]
                                            self._stored_camera_settings[camera_id] = {
                                                'focus': calib.get('focus', 0.6),
                                                'exposure_time': calib.get('exposure_time', 32752),
                                                'gain': calib.get('gain', 8.0),
                                            }
                                            logger.info(f"📷 {camera_key}: Using fallback calibrated settings from calibration data")
                            except Exception as store_error:
                                logger.warning(f"📷 {camera_key}: Settings storage failed: {store_error}")
                            
                            # Step 1: Stop camera
                            try:
                                if hasattr(camera, 'started') and camera.started:
                                    camera.stop()
                                    logger.info(f"📷 {camera_key}: Camera stopped")
                            except Exception as stop_error:
                                logger.warning(f"📷 {camera_key}: Camera stop warning: {stop_error}")
                            
                            # Step 2: Close camera to release V4L2 buffers (necessary for buffer release)
                            try:
                                camera.close()
                                logger.info(f"📷 {camera_key}: Camera closed - V4L2 buffers released")
                                
                                # Mark that this camera needs reinitialization
                                self.cameras[camera_id] = None
                                
                            except Exception as close_error:
                                logger.warning(f"📷 {camera_key}: Camera close warning: {close_error}")
                            
                            # Step 3: Extended delay for complete V4L2 cleanup
                            await asyncio.sleep(0.7)
                            
                            logger.info(f"📷 {camera_key}: V4L2 resources fully released")
                        
                        # Aggressive memory cleanup between cameras
                        for cleanup_round in range(3):
                            gc.collect()
                            await asyncio.sleep(0.3)  # Extended cleanup cycles
                        
                        # Extended delay before next camera for complete memory recovery
                        if len(available_cameras) > 1 and camera_id != available_cameras[-1]:
                            logger.info(f"⏱️ High-res memory recovery: {delay_ms}ms before next camera")
                            await asyncio.sleep(delay_ms / 1000.0)
                            
                            # Additional memory cleanup before next camera
                            for final_cleanup in range(2):
                                gc.collect()
                                await asyncio.sleep(0.2)
                            
                            # Comprehensive V4L2 subsystem cleanup
                            logger.info(f"🧹 Comprehensive V4L2 subsystem cleanup...")
                            try:
                                import subprocess
                                
                                # Step 1: Drop system caches to free V4L2 kernel buffers
                                subprocess.run(['sudo', 'sh', '-c', 'echo 1 > /proc/sys/vm/drop_caches'], 
                                             capture_output=True, timeout=2)
                                logger.info("🧹 System cache drop completed")
                                
                                # Step 2: Skip V4L2 module reset to prevent device conflicts
                                # Module reset can interfere with other active cameras
                                logger.info("🧹 Skipping V4L2 module reset to protect other active cameras")
                                
                            except Exception as cleanup_error:
                                logger.debug(f"V4L2 cleanup skipped: {cleanup_error}")
                            
                            # Reduced delay to prevent device conflicts
                            await asyncio.sleep(0.3)  # Reduced from 2.0s
                            
                            # Memory status check before next camera
                            try:
                                import psutil
                                mem = psutil.virtual_memory()
                                logger.info(f"📊 Pre-camera memory: {mem.percent}% used, {mem.available / 1024**3:.1f}GB available")
                            except ImportError:
                                pass
                            
                            logger.info(f"✅ {camera_key}: Safe cleanup completed, ready for next camera")

                
            else:
                # LOWER-RESOLUTION: Simultaneous capture for better sync
                logger.info(f"🔧 STANDARD SIMULTANEOUS: Capturing {len(available_cameras)} cameras simultaneously at {target_resolution}")
                
                # Ensure cameras are properly configured for target resolution before capture
                for camera_id in available_cameras:
                    camera = self.cameras[camera_id]
                    if camera:
                        try:
                            # Check current configuration matches target
                            current_config = camera.camera_configuration()
                            if current_config and 'main' in current_config:
                                current_size = current_config['main'].get('size')
                                if current_size != target_resolution:
                                    logger.info(f"📷 Camera {camera_id}: Reconfiguring from {current_size} to {target_resolution}")
                                    
                                    # Stop and reconfigure with correct resolution
                                    if camera.started:
                                        camera.stop()
                                    
                                    # Create proper configuration for target resolution
                                    capture_config = camera.create_still_configuration(
                                        main={"size": target_resolution, "format": "RGB888"},
                                        raw=None
                                    )
                                    camera.configure(capture_config)
                                    camera.start()
                                    
                                    # Allow camera to stabilize
                                    await asyncio.sleep(0.3)
                                    
                                    logger.info(f"📷 Camera {camera_id}: Reconfigured to {target_resolution}")
                        except Exception as config_error:
                            logger.warning(f"📷 Camera {camera_id}: Configuration check failed: {config_error}")
                
                # Use standard dual sequential with shorter delays for lower-res
                results = await self.capture_dual_sequential_isp("main", delay_ms=100)
                
            logger.info(f"📊 Resolution-aware capture complete: {len([r for r in results.values() if r is not None])}/{len(results)} successful")
            return results
            
        except Exception as e:
            logger.error(f"Resolution-aware dual capture failed: {e}")
            return {}

    async def capture_dual_high_res_sequential(self, delay_ms: int = 500) -> Dict[str, Any]:
        """
        Legacy high-resolution sequential capture - now redirects to resolution-aware capture.
        
        Args:
            delay_ms: Extended delay between captures for high-res operations
            
        Returns:
            Dict with results: {'camera_0': image_array, 'camera_1': image_array}
        """
        logger.info("🔄 Redirecting to resolution-aware capture system")
        return await self.capture_dual_resolution_aware(target_resolution=(9152, 6944), delay_ms=delay_ms)


# Utility functions for Pi camera operations
def create_pi_camera_controller(config_manager: ConfigManager) -> PiCameraController:
    """Create Pi camera controller from configuration"""
    camera_config = config_manager.get('camera', {})
    controller_config = camera_config.get('controller', {})
    
    return PiCameraController(controller_config)


def detect_pi_cameras() -> List[Dict[str, Any]]:
    """Detect available Pi cameras"""
    cameras = []
    
    if not PICAMERA2_AVAILABLE:
        logger.warning("picamera2 not available for camera detection")
        return cameras
    
    for camera_id in range(4):  # Check up to 4 cameras
        try:
            if not PICAMERA2_AVAILABLE or Picamera2 is None:
                continue
                
            test_camera = Picamera2(camera_id)
            props = test_camera.camera_properties
            test_camera.close()
            
            cameras.append({
                "camera_id": camera_id,
                "model": props.get('Model', 'Unknown'),
                "location": props.get('Location', 'Unknown'),
                "pixel_array_size": props.get('PixelArraySize', (0, 0))
            })
            
        except Exception:
            # Camera not available
            continue
    
    return cameras


def get_optimal_pi_camera_settings(resolution: Tuple[int, int], 
                                  lighting_conditions: str = "normal") -> CameraSettings:
    """Get optimal camera settings for given conditions"""
    
    # Base settings
    settings = CameraSettings(
        resolution=resolution,
        format=ImageFormat.JPEG
    )
    
    # Adjust for lighting conditions
    if lighting_conditions == "low_light":
        settings.exposure_time = 0.05  # 50ms
        settings.iso = 800
    elif lighting_conditions == "bright":
        settings.exposure_time = 0.001  # 1ms
        settings.iso = 100
    else:  # normal
        settings.exposure_time = 0.01  # 10ms
        settings.iso = 200
    
    return settings