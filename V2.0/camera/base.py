"""
Abstract Camera Control Interface

Defines the standard interface for all camera control implementations.
This enables support for different camera types (Pi cameras, DSLRs, USB cameras)
while maintaining consistent API for dual-camera synchronized operation.

Author: Scanner System Development
Created: September 2025
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable, Union
from enum import Enum
import asyncio
from pathlib import Path

from core.exceptions import CameraError
from core.events import ScannerEvent


class CameraStatus(Enum):
    """Camera status states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    READY = "ready"
    CAPTURING = "capturing"
    STREAMING = "streaming"
    ERROR = "error"
    CALIBRATING = "calibrating"


class CaptureMode(Enum):
    """Camera capture modes"""
    SINGLE = "single"           # Single photo capture
    BURST = "burst"             # Burst mode capture
    CONTINUOUS = "continuous"   # Continuous capture
    TIMELAPSE = "timelapse"     # Time-lapse capture
    VIDEO = "video"             # Video recording


class ImageFormat(Enum):
    """Supported image formats"""
    JPEG = "jpeg"
    PNG = "png"
    RAW = "raw"
    TIFF = "tiff"


@dataclass
class CameraSettings:
    """Camera configuration settings"""
    resolution: Tuple[int, int]
    format: ImageFormat = ImageFormat.JPEG
    quality: int = 95  # JPEG quality 1-100
    iso: Optional[int] = None
    exposure_time: Optional[float] = None  # seconds
    gain: Optional[float] = None
    white_balance: Optional[str] = None
    auto_focus: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'resolution': self.resolution,
            'format': self.format.value,
            'quality': self.quality,
            'iso': self.iso,
            'exposure_time': self.exposure_time,
            'gain': self.gain,
            'white_balance': self.white_balance,
            'auto_focus': self.auto_focus
        }


@dataclass
class CaptureResult:
    """Result of a camera capture operation"""
    success: bool
    image_data: Optional[bytes] = None
    image_path: Optional[Path] = None
    metadata: Optional[Dict[str, Any]] = None
    timestamp: Optional[float] = None
    camera_id: Optional[str] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        if self.timestamp is None:
            import time
            self.timestamp = time.time()


@dataclass
class SyncCaptureResult:
    """Result of synchronized dual camera capture"""
    success: bool
    camera1_result: Optional[CaptureResult] = None
    camera2_result: Optional[CaptureResult] = None
    sync_error_ms: Optional[float] = None  # Synchronization error in milliseconds
    
    @property
    def both_successful(self) -> bool:
        """Check if both cameras captured successfully"""
        return (self.success and 
                self.camera1_result is not None and self.camera1_result.success and
                self.camera2_result is not None and self.camera2_result.success)


@dataclass
class CameraCapabilities:
    """Camera capabilities and limits"""
    supported_resolutions: List[Tuple[int, int]]
    supported_formats: List[ImageFormat]
    min_exposure_time: float  # seconds
    max_exposure_time: float  # seconds
    min_iso: int
    max_iso: int
    supports_video: bool = False
    supports_burst: bool = False
    max_burst_rate: float = 1.0  # fps
    max_video_resolution: Optional[Tuple[int, int]] = None
    supports_auto_focus: bool = False


class CameraController(ABC):
    """
    Abstract base class for camera control systems
    
    This interface supports single or dual camera operations with
    synchronized capture capabilities for 3D scanning applications.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = CameraStatus.DISCONNECTED
        self.camera_settings: Dict[str, CameraSettings] = {}
        self.streaming_active = False
        self.event_callbacks: List[Callable] = []
        self.last_capture_time: Optional[float] = None
    
    # Connection Management
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize camera system
        
        Returns:
            True if initialization successful
            
        Raises:
            CameraError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """
        Shutdown camera system and release resources
        
        Returns:
            True if shutdown successful
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if camera(s) are available and ready"""
        pass
    
    # Camera Configuration
    @abstractmethod
    async def configure_camera(self, camera_id: str, settings: CameraSettings) -> bool:
        """
        Configure camera settings
        
        Args:
            camera_id: Camera identifier ('camera1', 'camera2', etc.)
            settings: Camera configuration settings
            
        Returns:
            True if configuration successful
            
        Raises:
            CameraError: If configuration fails
        """
        pass
    
    @abstractmethod
    async def get_camera_info(self, camera_id: str) -> Dict[str, Any]:
        """
        Get camera information and capabilities
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Dictionary with camera information
        """
        pass
    
    @abstractmethod
    async def list_cameras(self) -> List[str]:
        """
        List available cameras
        
        Returns:
            List of camera identifiers
        """
        pass
    
    # Single Camera Operations
    @abstractmethod
    async def capture_photo(self, camera_id: str, settings: Optional[CameraSettings] = None) -> CaptureResult:
        """
        Capture single photo from specified camera
        
        Args:
            camera_id: Camera identifier
            settings: Optional camera settings override
            
        Returns:
            Capture result with image data or file path
            
        Raises:
            CameraError: If capture fails
        """
        pass
    
    @abstractmethod
    async def capture_burst(self, camera_id: str, count: int, 
                          interval: float = 0.1, settings: Optional[CameraSettings] = None) -> List[CaptureResult]:
        """
        Capture burst of photos from specified camera
        
        Args:
            camera_id: Camera identifier
            count: Number of photos to capture
            interval: Time between captures in seconds
            settings: Optional camera settings override
            
        Returns:
            List of capture results
        """
        pass
    
    # Dual Camera Operations
    @abstractmethod
    async def capture_synchronized(self, settings: Optional[Dict[str, CameraSettings]] = None) -> SyncCaptureResult:
        """
        Capture synchronized photos from all available cameras
        
        Args:
            settings: Optional camera settings per camera
            
        Returns:
            Synchronized capture result
            
        Raises:
            CameraError: If synchronized capture fails
        """
        pass
    
    @abstractmethod
    async def calibrate_synchronization(self, test_captures: int = 10) -> float:
        """
        Calibrate camera synchronization timing
        
        Args:
            test_captures: Number of test captures for calibration
            
        Returns:
            Average synchronization error in milliseconds
            
        Raises:
            CameraError: If calibration fails
        """
        pass
    
    # Video Streaming
    @abstractmethod
    async def start_streaming(self, camera_id: str, settings: Optional[CameraSettings] = None) -> bool:
        """
        Start video streaming from camera
        
        Args:
            camera_id: Camera identifier
            settings: Optional streaming settings
            
        Returns:
            True if streaming started successfully
        """
        pass
    
    @abstractmethod
    async def stop_streaming(self, camera_id: str) -> bool:
        """
        Stop video streaming from camera
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if streaming stopped successfully
        """
        pass
    
    @abstractmethod
    async def get_stream_frame(self, camera_id: str) -> Optional[bytes]:
        """
        Get current frame from video stream
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Frame data as bytes (JPEG format) or None if not available
        """
        pass
    
    @abstractmethod
    def is_streaming(self, camera_id: str) -> bool:
        """
        Check if camera is currently streaming
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if camera is streaming
        """
        pass
    
    # Advanced Features
    @abstractmethod
    async def auto_focus(self, camera_id: str) -> bool:
        """
        Trigger auto-focus on camera
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if auto-focus completed successfully
        """
        pass
    
    @abstractmethod
    async def get_focus_value(self, camera_id: str) -> Optional[float]:
        """
        Get current focus value for camera
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Current focus value (0.0-1.0) or None if not supported
        """
        pass
    
    @abstractmethod
    async def set_focus_value(self, camera_id: str, focus_value: float) -> bool:
        """
        Set manual focus value for camera
        
        Args:
            camera_id: Camera identifier
            focus_value: Focus value (0.0 = near, 1.0 = infinity)
            
        Returns:
            True if focus was set successfully
        """
        pass
    
    @abstractmethod
    async def auto_focus_and_get_value(self, camera_id: str) -> Optional[float]:
        """
        Perform autofocus and return the optimal focus value
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Optimal focus value (0.0-1.0) or None if autofocus failed
        """
        pass
    
    @abstractmethod
    async def auto_exposure(self, camera_id: str) -> bool:
        """
        Trigger auto-exposure on camera
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if auto-exposure completed successfully
        """
        pass
    
    @abstractmethod
    async def capture_with_flash_sync(self, flash_controller, settings: Optional[Dict[str, CameraSettings]] = None) -> SyncCaptureResult:
        """
        Capture synchronized photos with LED flash
        
        Args:
            flash_controller: LED controller for flash synchronization
            settings: Optional camera settings per camera
            
        Returns:
            Synchronized capture result with flash
        """
        pass
    
    # Status and Monitoring
    @abstractmethod
    async def get_status(self, camera_id: Optional[str] = None) -> Union[CameraStatus, Dict[str, CameraStatus]]:
        """
        Get camera status
        
        Args:
            camera_id: Specific camera ID or None for all cameras
            
        Returns:
            Camera status or dictionary of statuses
        """
        pass
    
    @abstractmethod
    async def get_last_error(self, camera_id: str) -> Optional[str]:
        """
        Get last error message for camera
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Last error message or None
        """
        pass
    
    # File Management
    @abstractmethod
    async def save_capture_to_file(self, capture_result: CaptureResult, file_path: Path) -> bool:
        """
        Save capture result to file
        
        Args:
            capture_result: Capture result to save
            file_path: Destination file path
            
        Returns:
            True if file saved successfully
        """
        pass
    
    @abstractmethod
    async def cleanup_temp_files(self) -> bool:
        """
        Clean up temporary files and buffers
        
        Returns:
            True if cleanup successful
        """
        pass
    
    # Event Handling
    def add_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Add callback for camera events"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Remove event callback"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def _notify_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Notify all event callbacks"""
        from core.events import ScannerEvent, EventPriority
        
        event = ScannerEvent(
            event_type=event_type,
            data=data or {},
            source_module="camera",
            priority=EventPriority.NORMAL
        )
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in camera event callback: {e}")
    
    # Utility Methods
    def create_default_settings(self, camera_type: str = "pi_camera") -> CameraSettings:
        """Create default camera settings based on camera type"""
        if camera_type == "pi_camera":
            return CameraSettings(
                resolution=(3280, 2464),
                format=ImageFormat.JPEG,
                quality=95,
                auto_focus=True
            )
        elif camera_type == "dslr":
            return CameraSettings(
                resolution=(6000, 4000),
                format=ImageFormat.RAW,
                quality=100,
                auto_focus=True
            )
        else:
            return CameraSettings(
                resolution=(1920, 1080),
                format=ImageFormat.JPEG,
                quality=90,
                auto_focus=True
            )
    
    def calculate_sync_tolerance(self) -> float:
        """Calculate acceptable synchronization tolerance in milliseconds"""
        # For 3D scanning, typically want <10ms synchronization
        return 10.0
    
    def estimate_capture_time(self, settings: CameraSettings) -> float:
        """
        Estimate capture time based on settings
        
        Args:
            settings: Camera settings
            
        Returns:
            Estimated capture time in seconds
        """
        base_time = 0.1  # Base capture time
        
        # Higher resolution takes longer
        pixel_count = settings.resolution[0] * settings.resolution[1]
        resolution_factor = pixel_count / (1920 * 1080)  # Normalize to 1080p
        
        # RAW format takes longer
        format_factor = 2.0 if settings.format == ImageFormat.RAW else 1.0
        
        return base_time * resolution_factor * format_factor


# Utility functions for camera operations
def create_high_res_settings() -> CameraSettings:
    """Create settings for high-resolution capture"""
    return CameraSettings(
        resolution=(3280, 2464),
        format=ImageFormat.JPEG,
        quality=95,
        auto_focus=True
    )


def create_streaming_settings() -> CameraSettings:
    """Create settings optimized for streaming"""
    return CameraSettings(
        resolution=(1280, 720),
        format=ImageFormat.JPEG,
        quality=75,
        auto_focus=False  # Disable AF for smoother streaming
    )


def validate_sync_result(result: SyncCaptureResult, tolerance_ms: float = 10.0) -> bool:
    """
    Validate synchronization result
    
    Args:
        result: Synchronization result to validate
        tolerance_ms: Maximum acceptable sync error in milliseconds
        
    Returns:
        True if synchronization is within tolerance
    """
    if not result.both_successful:
        return False
    
    if result.sync_error_ms is None:
        return True  # No sync error reported
    
    return abs(result.sync_error_ms) <= tolerance_ms