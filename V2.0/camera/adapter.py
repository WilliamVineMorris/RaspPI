"""
Phase 2: Standardized Camera Controller Adapter

This adapter provides a standardized interface for all camera controllers
with explicit support for rotational Z-axis motion synchronization.

Key Features:
- Standardized adapter pattern for camera controllers
- Motion-aware capture timing (especially Z-axis rotation)
- Dual camera synchronization with rotation compensation
- LED flash coordination with rotational positioning
- Position-based capture metadata
- Event-driven communication with motion system

Author: Scanner System Development - Phase 2
Created: September 2025
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple, Union
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from camera.base import (
    CameraController, CameraSettings, ImageFormat, CaptureResult, 
    SyncCaptureResult, CameraStatus
)
from motion.base import Position4D, AxisType
from core.exceptions import CameraError, CameraSyncError
from core.events import ScannerEvent, EventPriority


class CaptureMode(Enum):
    """Camera capture modes"""
    SINGLE = "single"
    DUAL_SYNC = "dual_sync"
    BURST = "burst"
    MOTION_TRIGGERED = "motion_triggered"


class RotationTiming(Enum):
    """Timing modes for rotational captures"""
    CONTINUOUS = "continuous"          # Capture during rotation
    STOP_AND_CAPTURE = "stop_capture"  # Stop rotation, capture, continue
    PREDICTIVE = "predictive"          # Predict position and capture


@dataclass
class CaptureCommand:
    """Standardized capture command"""
    mode: CaptureMode
    settings: CameraSettings
    position: Optional[Position4D] = None
    flash_enabled: bool = True
    rotation_timing: RotationTiming = RotationTiming.STOP_AND_CAPTURE
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class MotionAwareCaptureResult:
    """Capture result with motion context"""
    capture_result: Union[CaptureResult, SyncCaptureResult]
    actual_position: Position4D
    motion_velocity: Optional[float] = None  # For Z-axis: degrees/second
    timing_accuracy: Optional[float] = None  # Timing accuracy in ms
    rotation_during_exposure: Optional[float] = None  # Degrees rotated during exposure


class StandardCameraAdapter(ABC):
    """
    Standardized adapter interface for camera controllers
    
    This adapter provides a consistent interface for camera operations
    with explicit support for rotational Z-axis motion coordination.
    """
    
    def __init__(self, controller: CameraController, config: Dict[str, Any]):
        self.controller = controller
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Motion coordination
        self.motion_adapter = None  # Will be set by system orchestrator
        self._position_tolerance = config.get('position_tolerance', 0.1)  # degrees
        self._capture_timeout = config.get('capture_timeout', 5.0)  # seconds
        
        # Timing configuration
        self.timing_config = self._load_timing_config()
        
        # Statistics
        self._capture_count = 0
        self._timing_stats = {
            'successful_captures': 0,
            'failed_captures': 0,
            'sync_errors': 0,
            'timing_violations': 0
        }
    
    def _load_timing_config(self) -> Dict[str, Any]:
        """Load timing configuration for motion-aware captures"""
        camera_config = self.config.get('camera', {})
        
        return {
            'max_sync_tolerance': camera_config.get('max_sync_tolerance', 10.0),  # ms
            'exposure_time': camera_config.get('default_exposure', 0.033),  # seconds (30fps)
            'flash_duration': camera_config.get('flash_duration', 0.002),  # seconds
            'z_rotation_threshold': camera_config.get('z_rotation_threshold', 1.0),  # degrees/sec
            'motion_stabilization_time': camera_config.get('stabilization_time', 0.1),  # seconds
        }
    
    def set_motion_adapter(self, motion_adapter):
        """Set motion adapter for coordinate capture operations"""
        self.motion_adapter = motion_adapter
        self.logger.info("Motion adapter connected to camera adapter")
    
    # Abstract methods for implementation
    @abstractmethod
    async def initialize_controller(self) -> bool:
        """Initialize the underlying camera controller"""
        pass
    
    @abstractmethod
    async def shutdown_controller(self) -> bool:
        """Shutdown the underlying camera controller"""
        pass
    
    # Position-Aware Capture Methods
    async def capture_at_position(self, position: Position4D, settings: CameraSettings, 
                                flash_enabled: bool = True) -> MotionAwareCaptureResult:
        """
        Capture images at specific position with motion coordination
        
        Args:
            position: Target position for capture
            settings: Camera settings
            flash_enabled: Whether to use LED flash
            
        Returns:
            Motion-aware capture result
        """
        try:
            self.logger.info(f"Starting position-aware capture at {position}")
            
            # Move to target position if motion adapter available
            if self.motion_adapter:
                move_success = await self.motion_adapter.move_to_position(position)
                if not move_success:
                    raise CameraError(f"Failed to move to capture position: {position}")
                
                # Wait for motion to stabilize
                stabilization_time = self.timing_config['motion_stabilization_time']
                await asyncio.sleep(stabilization_time)
                
                # Verify position accuracy
                actual_position = await self.motion_adapter.get_current_position()
                position_error = self._calculate_position_error(position, actual_position)
                
                if position_error > self._position_tolerance:
                    self.logger.warning(
                        f"Position error {position_error:.3f}° exceeds tolerance "
                        f"{self._position_tolerance:.3f}°"
                    )
            else:
                actual_position = position  # Assume position is correct if no motion adapter
            
            # Execute capture with timing measurement
            capture_start = time.time()
            
            # Check for dual camera support
            cameras = await self.controller.list_cameras()
            if len(cameras) > 1:
                # Dual camera synchronized capture
                capture_result = await self.controller.capture_synchronized(
                    settings={'camera1': settings, 'camera2': settings}
                )
            else:
                # Single camera capture
                camera_id = cameras[0] if cameras else 'camera1'
                single_result = await self.controller.capture_photo(camera_id, settings)
                # Wrap single result in sync format for consistency
                capture_result = SyncCaptureResult(
                    success=single_result.success,
                    camera1_result=single_result,
                    camera2_result=None
                )
            
            capture_end = time.time()
            capture_duration = (capture_end - capture_start) * 1000  # ms
            
            # Calculate motion during capture (for Z-axis)
            rotation_during_exposure = None
            if self.motion_adapter and settings.exposure_time:
                # Estimate rotation during exposure based on typical Z-axis speeds
                estimated_z_speed = 0.0  # degrees/second (assume stationary)
                rotation_during_exposure = estimated_z_speed * settings.exposure_time
            
            # Create motion-aware result
            result = MotionAwareCaptureResult(
                capture_result=capture_result,
                actual_position=actual_position,
                timing_accuracy=capture_duration,
                rotation_during_exposure=rotation_during_exposure
            )
            
            # Update statistics
            self._capture_count += 1
            self._timing_stats['successful_captures'] += 1
            
            self.logger.info(
                f"Capture completed at {actual_position} "
                f"(timing: {capture_duration:.1f}ms)"
            )
            
            # Notify capture event
            self._notify_capture_event("position_capture_completed", {
                "position": actual_position.to_dict(),
                "timing_ms": capture_duration,
                "capture_id": f"pos_{self._capture_count:06d}"
            })
            
            return result
            
        except Exception as e:
            self._timing_stats['failed_captures'] += 1
            self.logger.error(f"Position-aware capture failed: {e}")
            self._notify_capture_event("capture_failed", {"error": str(e)})
            raise CameraError(f"Position-aware capture failed: {e}")
    
    async def capture_rotation_sequence(self, start_angle: float, end_angle: float, 
                                      step_degrees: float, settings: CameraSettings) -> List[MotionAwareCaptureResult]:
        """
        Capture sequence during Z-axis rotation
        
        Args:
            start_angle: Starting Z rotation (degrees)
            end_angle: Ending Z rotation (degrees)
            step_degrees: Angular step between captures
            settings: Camera settings
            
        Returns:
            List of motion-aware capture results
        """
        try:
            if not self.motion_adapter:
                raise CameraError("Motion adapter required for rotation sequences")
            
            self.logger.info(
                f"Starting rotation sequence: {start_angle}° to {end_angle}° "
                f"(step: {step_degrees}°)"
            )
            
            results = []
            current_angle = start_angle
            
            while current_angle <= end_angle:
                # Get current XY position to maintain
                current_pos = await self.motion_adapter.get_current_position()
                target_pos = Position4D(
                    x=current_pos.x,
                    y=current_pos.y,
                    z=current_angle,
                    c=current_pos.c
                )
                
                # Capture at this rotation angle
                result = await self.capture_at_position(target_pos, settings)
                results.append(result)
                
                current_angle += step_degrees
            
            self.logger.info(f"Rotation sequence completed: {len(results)} captures")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Rotation sequence failed: {e}")
            raise CameraError(f"Rotation sequence failed: {e}")
    
    async def capture_with_continuous_rotation(self, settings: CameraSettings, 
                                             rotation_speed: float) -> MotionAwareCaptureResult:
        """
        Capture during continuous Z-axis rotation
        
        Args:
            settings: Camera settings
            rotation_speed: Z rotation speed (degrees/second)
            
        Returns:
            Motion-aware capture result
        """
        try:
            if not self.motion_adapter:
                raise CameraError("Motion adapter required for continuous rotation capture")
            
            # Check if rotation speed is within acceptable limits
            max_rotation_speed = self.timing_config['z_rotation_threshold']
            if rotation_speed > max_rotation_speed:
                self.logger.warning(
                    f"Rotation speed {rotation_speed}°/s exceeds threshold "
                    f"{max_rotation_speed}°/s - image quality may be affected"
                )
            
            # Get position at capture start
            start_position = await self.motion_adapter.get_current_position()
            
            # Execute capture with motion velocity tracking
            capture_start = time.time()
            
            # Check for dual camera support
            cameras = await self.controller.list_cameras()
            if len(cameras) > 1:
                # Dual camera synchronized capture
                capture_result = await self.controller.capture_synchronized(
                    settings={'camera1': settings, 'camera2': settings}
                )
            else:
                # Single camera capture
                camera_id = cameras[0] if cameras else 'camera1'
                single_result = await self.controller.capture_photo(camera_id, settings)
                # Wrap single result in sync format for consistency
                capture_result = SyncCaptureResult(
                    success=single_result.success,
                    camera1_result=single_result,
                    camera2_result=None
                )
            
            capture_end = time.time()
            capture_duration = (capture_end - capture_start) * 1000  # ms
            
            # Calculate rotation during capture
            exposure_time = settings.exposure_time or self.timing_config['exposure_time']
            rotation_during_exposure = rotation_speed * exposure_time
            
            # Estimate actual position during capture (middle of exposure)
            mid_capture_z = start_position.z + (rotation_during_exposure / 2)
            actual_position = Position4D(
                x=start_position.x,
                y=start_position.y,
                z=mid_capture_z,
                c=start_position.c
            )
            
            result = MotionAwareCaptureResult(
                capture_result=capture_result,
                actual_position=actual_position,
                motion_velocity=rotation_speed,
                timing_accuracy=capture_duration,
                rotation_during_exposure=rotation_during_exposure
            )
            
            self.logger.info(
                f"Continuous rotation capture completed: "
                f"rotation {rotation_during_exposure:.2f}° during {exposure_time*1000:.1f}ms exposure"
            )
            
            return result
            
        except Exception as e:
            self.logger.error(f"Continuous rotation capture failed: {e}")
            raise CameraError(f"Continuous rotation capture failed: {e}")
    
    # Utility Methods
    def _calculate_position_error(self, target: Position4D, actual: Position4D) -> float:
        """
        Calculate position error with emphasis on Z-axis (rotational)
        
        Args:
            target: Target position
            actual: Actual position
            
        Returns:
            Position error in degrees (for rotational axes)
        """
        # For Z-axis (rotational), calculate angular difference
        z_error = abs(target.z - actual.z)
        
        # Handle wrap-around for continuous rotation
        if z_error > 180.0:
            z_error = 360.0 - z_error
        
        # For C-axis (camera tilt), direct angular difference
        c_error = abs(target.c - actual.c)
        
        # For linear axes, use Euclidean distance
        linear_error = ((target.x - actual.x) ** 2 + (target.y - actual.y) ** 2) ** 0.5
        
        # Return maximum error (worst axis)
        return max(z_error, c_error, linear_error)
    
    # Status and Information
    async def get_camera_status(self) -> Dict[str, Any]:
        """Get camera status with motion coordination info"""
        try:
            base_status = await self.controller.get_status()
            
            # Handle both single status and dict of statuses
            if isinstance(base_status, dict):
                status_str = str(base_status)
            else:
                status_str = base_status.value if hasattr(base_status, 'value') else str(base_status)
            
            enhanced_status = {
                "camera_status": status_str,
                "motion_coordination": self.motion_adapter is not None,
                "capture_count": self._capture_count,
                "timing_config": self.timing_config,
                "statistics": self._timing_stats.copy()
            }
            
            if self.motion_adapter:
                current_pos = await self.motion_adapter.get_current_position()
                enhanced_status["current_position"] = current_pos.to_dict()
            
            return enhanced_status
            
        except Exception as e:
            self.logger.error(f"Failed to get camera status: {e}")
            return {"error": str(e)}
    
    def get_timing_statistics(self) -> Dict[str, Any]:
        """Get capture timing statistics"""
        return {
            "total_captures": self._capture_count,
            "statistics": self._timing_stats.copy(),
            "success_rate": (
                self._timing_stats['successful_captures'] / max(self._capture_count, 1) * 100
            )
        }
    
    # Event Management
    def _notify_capture_event(self, event_type: str, data: Dict[str, Any]):
        """Notify capture event to system"""
        try:
            event = ScannerEvent(
                event_type=f"camera.{event_type}",
                data=data,
                source_module="camera_adapter",
                priority=EventPriority.HIGH if "error" in event_type else EventPriority.NORMAL
            )
            
            # Notify through controller if it has event callbacks
            if hasattr(self.controller, '_notify_event'):
                self.controller._notify_event(event_type, data)
                
        except Exception as e:
            self.logger.error(f"Failed to notify capture event: {e}")


class PiCameraAdapter(StandardCameraAdapter):
    """
    Raspberry Pi camera-specific implementation of the standardized camera adapter
    """
    
    def __init__(self, pi_camera_controller, config: Dict[str, Any]):
        super().__init__(pi_camera_controller, config)
        self.pi_camera = pi_camera_controller  # Type hint for Pi-specific features
        
    async def initialize_controller(self) -> bool:
        """Initialize Pi camera controller"""
        try:
            result = await self.pi_camera.initialize()
            if result:
                self.logger.info("Pi camera controller initialized successfully")
                self._notify_capture_event("controller_initialized", {
                    "controller_type": "PiCamera",
                    "dual_camera": hasattr(self.pi_camera, 'capture_dual_sync')
                })
            return result
        except Exception as e:
            self.logger.error(f"Pi camera controller initialization failed: {e}")
            return False
    
    async def shutdown_controller(self) -> bool:
        """Shutdown Pi camera controller"""
        try:
            result = await self.pi_camera.shutdown()
            if result:
                self.logger.info("Pi camera controller shutdown successfully")
                self._notify_capture_event("controller_shutdown", {})
            return result
        except Exception as e:
            self.logger.error(f"Pi camera controller shutdown failed: {e}")
            return False
    
    async def optimize_for_rotation(self, rotation_speed: float) -> CameraSettings:
        """
        Optimize camera settings for rotational motion
        
        Args:
            rotation_speed: Z-axis rotation speed (degrees/second)
            
        Returns:
            Optimized camera settings
        """
        try:
            # Base settings
            base_settings = CameraSettings(
                resolution=(1920, 1080),
                format=ImageFormat.JPEG
            )
            
            # Adjust exposure for motion blur
            if rotation_speed > 0:
                # Calculate maximum exposure to limit motion blur
                max_blur_degrees = 0.5  # Acceptable blur
                max_exposure = max_blur_degrees / rotation_speed
                
                # Limit exposure time
                optimized_exposure = min(max_exposure, 0.033)  # Max 30fps equivalent
                
                base_settings.exposure_time = optimized_exposure
                base_settings.iso = min(800, int(1.0 / optimized_exposure * 100))  # Compensate with ISO
                
                self.logger.info(
                    f"Optimized for {rotation_speed}°/s rotation: "
                    f"exposure={optimized_exposure*1000:.1f}ms, ISO={base_settings.iso}"
                )
            
            return base_settings
            
        except Exception as e:
            self.logger.error(f"Failed to optimize camera settings: {e}")
            # Return default settings on error
            return CameraSettings(resolution=(1920, 1080), format=ImageFormat.JPEG)

    # ISP Buffer Management Methods (delegated to PiCameraController)
    
    async def capture_with_isp_management(self, camera_id: int, stream_name: str = "main") -> Optional[Any]:
        """
        Delegate ISP-managed capture to underlying Pi camera controller.
        
        Args:
            camera_id: Camera ID (0 or 1)
            stream_name: Stream to capture from
            
        Returns:
            Captured image array or None if failed
        """
        if hasattr(self.pi_camera, 'capture_with_isp_management'):
            return await self.pi_camera.capture_with_isp_management(camera_id, stream_name)
        else:
            self.logger.warning("ISP management method not available in Pi camera controller")
            return None
    
    async def capture_dual_sequential_isp(self, stream_name: str = "main", delay_ms: int = 200) -> Dict[str, Any]:
        """
        Delegate dual sequential ISP capture to underlying Pi camera controller.
        
        Args:
            stream_name: Stream to capture from both cameras
            delay_ms: Delay between captures in milliseconds
            
        Returns:
            Dict with results: {'camera_0': image_array, 'camera_1': image_array}
        """
        if hasattr(self.pi_camera, 'capture_dual_sequential_isp'):
            return await self.pi_camera.capture_dual_sequential_isp(stream_name, delay_ms)
        else:
            self.logger.warning("Dual sequential ISP method not available in Pi camera controller")
            return {}
    
    async def prepare_cameras_for_capture(self) -> bool:
        """
        Delegate camera preparation to underlying Pi camera controller.
        
        Returns:
            True if preparation successful, False otherwise
        """
        if hasattr(self.pi_camera, 'prepare_cameras_for_capture'):
            return await self.pi_camera.prepare_cameras_for_capture()
        else:
            self.logger.warning("Camera preparation method not available in Pi camera controller")
            return False
    
    async def capture_dual_high_res_sequential(self, delay_ms: int = 500) -> Dict[str, Any]:
        """
        Delegate high-resolution sequential capture to underlying Pi camera controller.
        
        Args:
            delay_ms: Extended delay between captures for high-res operations
            
        Returns:
            Dict with results: {'camera_0': image_array, 'camera_1': image_array}
        """
        if hasattr(self.pi_camera, 'capture_dual_high_res_sequential'):
            return await self.pi_camera.capture_dual_high_res_sequential(delay_ms)
        else:
            self.logger.warning("High-res sequential method not available in Pi camera controller")
            return {}


# Factory function for creating camera adapters
def create_camera_adapter(controller: CameraController, config: Dict[str, Any]) -> StandardCameraAdapter:
    """
    Factory function to create appropriate camera adapter
    
    Args:
        controller: Camera controller instance
        config: System configuration
        
    Returns:
        Appropriate camera adapter instance
    """
    camera_type = config.get('camera', {}).get('type', 'unknown')
    
    if camera_type.lower() in ['pi_camera', 'raspberry_pi']:
        return PiCameraAdapter(controller, config)
    else:
        # Generic adapter for other camera types
        class GenericCameraAdapter(StandardCameraAdapter):
            async def initialize_controller(self) -> bool:
                return await self.controller.initialize()
            
            async def shutdown_controller(self) -> bool:
                return await self.controller.shutdown()
        
        return GenericCameraAdapter(controller, config)