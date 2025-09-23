"""
Scan Orchestrator - Main Coordination Engine

This module provides the ScanOrchestrator class that coordinates all scanner
components to perform complete 3D scanning operations. It integrates motion
control, camera capture, pattern execution, and state management.

Note: This is the orchestration framework. Hardware interfaces will be
implemented when the motion and camera modules are complete.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

from core.config_manager import ConfigManager
from core.events import EventBus, EventPriority
from core.exceptions import ScannerSystemError, HardwareError, ConfigurationError

from .scan_patterns import ScanPattern, ScanPoint, GridScanPattern
from .scan_state import ScanState, ScanStatus, ScanPhase

logger = logging.getLogger(__name__)

# Protocol definitions for hardware interfaces (to be implemented)
class MotionControllerProtocol(Protocol):
    """Protocol for motion controller interface"""
    async def initialize(self) -> bool: ...
    async def home(self) -> bool: ...
    async def move_to(self, x: float, y: float) -> bool: ...
    async def move_z_to(self, z: float) -> bool: ...
    async def rotate_to(self, rotation: float) -> bool: ...
    async def emergency_stop(self) -> bool: ...
    async def shutdown(self) -> None: ...
    def is_connected(self) -> bool: ...
    def get_current_settings(self) -> Dict[str, Any]: ...

class CameraManagerProtocol(Protocol):
    """Protocol for camera manager interface"""
    async def initialize(self) -> bool: ...
    async def capture_all(self, output_dir: Path, filename_base: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]: ...
    async def check_camera_health(self) -> bool: ...
    async def stop_all(self) -> None: ...
    async def shutdown(self) -> None: ...
    def get_current_settings(self) -> Dict[str, Any]: ...

class LightingControllerProtocol(Protocol):
    """Protocol for lighting controller interface"""
    async def initialize(self) -> bool: ...
    async def shutdown(self) -> bool: ...
    def is_available(self) -> bool: ...
    async def flash(self, zone_ids: List[str], settings: Any) -> Any: ...
    async def turn_off_all(self) -> bool: ...
    async def get_status(self, zone_id: Optional[str] = None) -> Any: ...

# Hardware Adapter Classes

# Mock implementations for testing/development
class MockMotionController:
    """Mock motion controller for testing"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._connected = False
        self._position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rotation': 0.0}
        
    async def initialize(self) -> bool:
        await asyncio.sleep(0.1)  # Simulate initialization
        self._connected = True
        return True
        
    async def home(self) -> bool:
        await asyncio.sleep(0.2)  # Reduce homing time for tests
        self._position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'rotation': 0.0}
        return True
        
    async def move_to(self, x: float, y: float) -> bool:
        await asyncio.sleep(0.2)  # Slightly increase to allow pause testing
        self._position.update({'x': x, 'y': y})
        return True
        
    async def move_z_to(self, z: float) -> bool:
        await asyncio.sleep(0.15)  # Slightly increase to allow pause testing
        self._position['z'] = z
        return True
        
    async def rotate_to(self, rotation: float) -> bool:
        await asyncio.sleep(0.15)  # Slightly increase to allow pause testing
        self._position['rotation'] = rotation
        return True
        
    async def emergency_stop(self) -> bool:
        return True
        
    async def shutdown(self) -> None:
        self._connected = False
        
    def is_connected(self) -> bool:
        return self._connected
        
    def get_current_settings(self) -> Dict[str, Any]:
        return {'position': self._position.copy()}

class MockCameraManager:
    """Mock camera manager for testing"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._initialized = False
        
    async def initialize(self) -> bool:
        await asyncio.sleep(0.2)
        self._initialized = True
        return True
        
    async def capture_all(self, output_dir: Path, filename_base: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        await asyncio.sleep(0.3)  # Slightly increase to allow pause testing
        
        # Create mock image files
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = []
        for camera_id in ['camera_0', 'camera_1']:
            filename = f"{filename_base}_{camera_id}.jpg"
            filepath = output_dir / filename
            
            # Create dummy JPEG files with proper headers
            try:
                # Create a minimal valid JPEG file
                jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
                jpeg_data = b'\xff\xc0\x00\x11\x08\x00\x10\x00\x10\x01\x01\x11\x00\x02\x11\x01\x03\x11\x01'
                jpeg_end = b'\xff\xd9'
                
                # Write minimal but valid JPEG file
                with open(filepath, 'wb') as f:
                    f.write(jpeg_header)
                    f.write(jpeg_data)
                    # Add some dummy image data
                    f.write(b'\x00' * 64)  # Minimal image data
                    f.write(jpeg_end)
                
                results.append({
                    'camera_id': camera_id,
                    'success': True,
                    'filepath': str(filepath),
                    'metadata': metadata
                })
            except Exception as e:
                results.append({
                    'camera_id': camera_id,
                    'success': False,
                    'error': str(e)
                })
                
        return results
        
    async def check_camera_health(self) -> bool:
        return self._initialized
        
    async def stop_all(self) -> None:
        pass
        
    async def shutdown(self) -> None:
        self._initialized = False
        
    def get_current_settings(self) -> Dict[str, Any]:
        return {'initialized': self._initialized}
    
    def get_preview_frame(self, camera_id: int) -> Optional[Any]:
        """Mock preview frame for testing"""
        import numpy as np
        # Return a simple test pattern
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        frame[:] = (64, 128, 192)  # Blue-ish mock color
        return frame
    
    def set_scanning_mode(self, is_scanning: bool):
        """Mock scanning mode setting"""
        self._scanning_mode = is_scanning
    
    def get_status(self) -> Dict[str, Any]:
        """Mock status for testing"""
        return {
            'cameras': ['camera_1', 'camera_2'],
            'active_cameras': ['camera_1', 'camera_2'] if self._initialized else [],
            'initialized': self._initialized
        }

class MockLightingController:
    """Mock lighting controller for testing"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._initialized = False
        self._zones = ['top_ring', 'side_ring', 'flash_zone']  # Mock zones
        
    async def initialize(self) -> bool:
        await asyncio.sleep(0.1)
        self._initialized = True
        return True
        
    async def shutdown(self) -> bool:
        self._initialized = False
        return True
        
    def is_available(self) -> bool:
        return self._initialized
        
    async def flash(self, zone_ids: List[str], settings: Any) -> Any:
        await asyncio.sleep(0.05)  # Simulate flash duration
        # Mock flash result
        return {
            'success': True,
            'zones_activated': zone_ids,
            'actual_brightness': {zone_id: 0.8 for zone_id in zone_ids},
            'duration_ms': 100
        }
        
    async def turn_off_all(self) -> bool:
        return True
        
    async def get_status(self, zone_id: Optional[str] = None) -> Any:
        if zone_id:
            return "ready" if self._initialized else "disconnected"
        else:
            return {zone_id: "ready" if self._initialized else "disconnected" 
                   for zone_id in self._zones}
class MotionControllerAdapter:
    """Adapter to make FluidNCController compatible with orchestrator protocol"""
    
    def __init__(self, fluidnc_controller):
        self.controller = fluidnc_controller
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> bool:
        return await self.controller.initialize()
        
    async def home(self) -> bool:
        return await self.controller.home_all_axes()
        
    async def move_to(self, x: float, y: float) -> bool:
        from motion.base import Position4D
        current_pos = await self.controller.get_position()
        new_pos = Position4D(x=x, y=y, z=current_pos.z, c=current_pos.c)
        return await self.controller.move_to_position(new_pos)
        
    async def move_z_to(self, z: float) -> bool:
        from motion.base import Position4D
        current_pos = await self.controller.get_position()
        new_pos = Position4D(x=current_pos.x, y=current_pos.y, z=z, c=current_pos.c)
        return await self.controller.move_to_position(new_pos)
        
    async def rotate_to(self, rotation: float) -> bool:
        from motion.base import Position4D
        current_pos = await self.controller.get_position()
        new_pos = Position4D(x=current_pos.x, y=current_pos.y, z=current_pos.z, c=rotation)
        return await self.controller.move_to_position(new_pos)
        
    async def emergency_stop(self) -> bool:
        return await self.controller.emergency_stop()
        
    def emergency_stop_sync(self) -> bool:
        """Synchronous wrapper for emergency stop"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.controller.emergency_stop())
            loop.close()
            return result
        except Exception:
            return False
        
    async def shutdown(self) -> None:
        await self.controller.shutdown()
        
    def is_connected(self) -> bool:
        return self.controller.is_connected()
        
    def get_status(self) -> Dict[str, Any]:
        """Get motion controller status"""
        try:
            is_connected = self.controller.is_connected()
            self.logger.info(f"Motion controller connection status: {is_connected}")
            return {
                'state': 'idle' if is_connected else 'disconnected',
                'connected': is_connected,
                'initialized': is_connected
            }
        except Exception as e:
            self.logger.error(f"Error getting motion controller status: {e}")
            return {
                'state': 'error',
                'connected': False,
                'initialized': False
            }
            
    def get_position(self) -> Dict[str, float]:
        """Get current position in a dict format"""
        try:
            if hasattr(self.controller, 'get_position_sync'):
                # Use synchronous method if available
                pos = self.controller.get_position_sync()
            else:
                # Fallback to basic position if no sync method
                return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
                
            return {
                'x': pos.x if hasattr(pos, 'x') else 0.0,
                'y': pos.y if hasattr(pos, 'y') else 0.0, 
                'z': pos.z if hasattr(pos, 'z') else 0.0,
                'c': pos.c if hasattr(pos, 'c') else 0.0
            }
        except Exception:
            return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
        
    def get_current_settings(self) -> Dict[str, Any]:
        return {'controller_type': 'FluidNC', 'connected': self.controller.is_connected()}


class CameraManagerAdapter:
    """Adapter to make PiCameraController compatible with orchestrator protocol"""
    
    def __init__(self, pi_camera_controller, config_manager):
        self.controller = pi_camera_controller
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
    async def initialize(self) -> bool:
        return await self.controller.initialize()
        
    async def capture_all(self, output_dir: Path, filename_base: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Capture from all available cameras"""
        results = []
        
        # Get list of available cameras
        cameras = await self.controller.list_cameras()
        
        for camera_id in cameras:
            try:
                # Use synchronized capture for all cameras
                sync_result = await self.controller.capture_synchronized()
                
                # Process results for each camera
                if sync_result.success:
                    for cam_result in sync_result.results:
                        if cam_result.success and cam_result.filepath:
                            # Move file to desired location
                            import shutil
                            src_path = Path(cam_result.filepath)
                            dst_path = output_dir / f"{filename_base}_{cam_result.camera_id}.jpg"
                            shutil.move(str(src_path), str(dst_path))
                            
                            results.append({
                                'camera_id': cam_result.camera_id,
                                'success': True,
                                'filepath': str(dst_path),
                                'metadata': metadata
                            })
                        else:
                            results.append({
                                'camera_id': cam_result.camera_id,
                                'success': False,
                                'error': cam_result.error_message or 'Unknown error'
                            })
                else:
                    # Fallback to individual captures
                    for camera_id in cameras:
                        try:
                            result = await self.controller.capture_photo(camera_id)
                            if result.success and result.filepath:
                                import shutil
                                src_path = Path(result.filepath)
                                dst_path = output_dir / f"{filename_base}_{result.camera_id}.jpg"
                                shutil.move(str(src_path), str(dst_path))
                                
                                results.append({
                                    'camera_id': result.camera_id,
                                    'success': True,
                                    'filepath': str(dst_path),
                                    'metadata': metadata
                                })
                            else:
                                results.append({
                                    'camera_id': camera_id,
                                    'success': False,
                                    'error': result.error_message or 'Capture failed'
                                })
                        except Exception as e:
                            results.append({
                                'camera_id': camera_id,
                                'success': False,
                                'error': str(e)
                            })
                            
            except Exception as e:
                # Handle complete failure
                for camera_id in cameras:
                    results.append({
                        'camera_id': camera_id,
                        'success': False,
                        'error': str(e)
                    })
                break
                
        return results
        
    async def check_camera_health(self) -> bool:
        status = await self.controller.get_status()
        from camera.base import CameraStatus
        return status in [CameraStatus.READY, CameraStatus.CAPTURING]
        
    async def stop_all(self) -> None:
        # Pi camera controller doesn't have explicit stop_all, but we can shutdown and restart
        pass
        
    async def shutdown(self) -> None:
        await self.controller.shutdown()
        
    def get_current_settings(self) -> Dict[str, Any]:
        return {'controller_type': 'PiCamera', 'is_connected': self.controller.is_connected()}
    
    def get_preview_frame(self, camera_id) -> Optional[Any]:
        """Get a preview frame using optimized Picamera2 methods with comprehensive debugging"""
        try:
            import cv2
            import numpy as np
            import time
            import io
            from PIL import Image
            import threading
            from typing import List, Union
            
            self.logger.info(f"get_preview_frame called for camera {camera_id} (type: {type(camera_id)})")
            
            # Check if we have access to the real camera controller
            if not hasattr(self.controller, 'cameras'):
                self.logger.warning(f"Controller has no cameras attribute. Controller type: {type(self.controller)}")
                return None
                
            cameras = self.controller.cameras
            self.logger.info(f"Available cameras: {list(cameras.keys()) if cameras else 'None'}")
            
            # Handle camera ID mapping - convert string IDs if necessary
            actual_camera_id = camera_id
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                # Extract numeric part from 'camera_1' -> 0, 'camera_2' -> 1, etc.
                try:
                    numeric_id = int(camera_id.split('_')[1]) - 1
                    if numeric_id in cameras:
                        actual_camera_id = numeric_id
                        self.logger.info(f"Mapped string ID {camera_id} to numeric ID {actual_camera_id}")
                except (ValueError, IndexError):
                    self.logger.warning(f"Could not parse camera ID: {camera_id}")
            
            if actual_camera_id not in cameras:
                self.logger.warning(f"Camera {actual_camera_id} not in available cameras: {list(cameras.keys())}")
                return None
            
            camera = cameras.get(actual_camera_id)
            if not camera:
                self.logger.warning(f"Camera {actual_camera_id} is None")
                return None
            
            self.logger.info(f"Starting capture from camera {actual_camera_id}")
            
            # Use threading for timeout
            result: List[Union[np.ndarray, None]] = [None]  # Use list to allow modification in nested function
            exception: List[Union[Exception, None]] = [None]
            
            def capture_frame():
                try:
                    # Check camera state first
                    if not hasattr(camera, 'started') or not camera.started:
                        self.logger.info(f"Camera {actual_camera_id} not started, starting now...")
                        camera.start()
                        time.sleep(0.5)  # Give camera time to start
                    
                    self.logger.info(f"Camera {actual_camera_id} is started, attempting capture...")
                    
                    # Try array capture first (fastest method)
                    try:
                        array = camera.capture_array("main")
                        self.logger.info(f"Array capture successful for camera {actual_camera_id}: {array.shape}")
                        
                        if array is not None and array.size > 0:
                            # Handle different array formats
                            if len(array.shape) == 3 and array.shape[2] == 3:
                                # Assume RGB from camera, convert to BGR
                                frame_bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                                self.logger.info(f"Converted array to BGR for camera {actual_camera_id}: {frame_bgr.shape}")
                                result[0] = frame_bgr
                                return
                            else:
                                self.logger.warning(f"Unexpected array shape from camera {actual_camera_id}: {array.shape}")
                        else:
                            self.logger.warning(f"Empty or invalid array from camera {actual_camera_id}")
                    
                    except Exception as array_error:
                        self.logger.warning(f"Array capture failed for camera {actual_camera_id}: {array_error}")
                        
                        # Fallback to file capture
                        try:
                            self.logger.info(f"Trying file capture for camera {actual_camera_id}")
                            stream = io.BytesIO()
                            camera.capture_file(stream, format='jpeg')
                            stream.seek(0)
                            
                            # Convert JPEG to opencv array
                            image = Image.open(stream)
                            frame_rgb = np.array(image)
                            
                            if len(frame_rgb.shape) == 3 and frame_rgb.shape[2] == 3:
                                # Convert RGB to BGR for OpenCV
                                frame_bgr = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2BGR)
                                self.logger.info(f"File capture successful for camera {actual_camera_id}: {frame_bgr.shape}")
                                result[0] = frame_bgr
                                return
                            else:
                                self.logger.warning(f"Invalid frame shape from file capture {actual_camera_id}: {frame_rgb.shape}")
                        
                        except Exception as file_error:
                            self.logger.error(f"File capture also failed for camera {actual_camera_id}: {file_error}")
                
                except Exception as e:
                    self.logger.error(f"Exception in capture thread for camera {actual_camera_id}: {e}")
                    exception[0] = e
            
            # Start capture in separate thread with timeout
            capture_thread = threading.Thread(target=capture_frame)
            capture_thread.daemon = True
            capture_thread.start()
            
            # Wait for thread to complete with timeout
            capture_thread.join(timeout=3.0)  # 3 second timeout
            
            if capture_thread.is_alive():
                self.logger.error(f"Camera capture timed out for camera {actual_camera_id}")
                return None
            
            if exception[0]:
                self.logger.error(f"Camera capture failed with exception: {exception[0]}")
                return None
            
            if result[0] is not None:
                self.logger.info(f"Successfully captured frame for camera {actual_camera_id}")
                return result[0]
            else:
                self.logger.warning(f"No frame captured for camera {actual_camera_id}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error in get_preview_frame for camera {camera_id}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def set_scanning_mode(self, is_scanning: bool):
        """Set scanning mode to optimize camera usage"""
        self._is_scanning = is_scanning
        self.logger.info(f"Camera mode set to: {'scanning' if is_scanning else 'live preview'}")
        
        # Reset camera configurations to force reconfiguration
        try:
            for camera_id, camera in self.controller.cameras.items():
                if camera and hasattr(camera, '_current_config_type'):
                    delattr(camera, '_current_config_type')
        except Exception as e:
            self.logger.warning(f"Error resetting camera configs: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get camera manager status"""
        try:
            # Check if cameras are initialized and connected
            is_connected = self.controller.is_connected() if hasattr(self.controller, 'is_connected') else True
            self.logger.debug(f"Camera manager connection status: {is_connected}")
            
            if is_connected:
                # If connected, report cameras as active
                status = {
                    'cameras': ['camera_1', 'camera_2'],  # Based on configuration
                    'active_cameras': ['camera_1', 'camera_2'],  # Both cameras active when connected
                    'initialized': True
                }
                self.logger.info(f"Camera status: {status}")
                return status
            else:
                status = {
                    'cameras': ['camera_1', 'camera_2'],  # Still available but not active
                    'active_cameras': [],
                    'initialized': False
                }
                self.logger.info(f"Camera status (disconnected): {status}")
                return status
        except Exception as e:
            self.logger.error(f"Error getting camera status: {e}")
            return {
                'cameras': [],
                'active_cameras': [],
                'initialized': False
            }

class LightingControllerAdapter:
    """Adapter to make GPIOLEDController compatible with orchestrator protocol"""
    
    def __init__(self, lighting_controller):
        self.controller = lighting_controller
        
    async def initialize(self) -> bool:
        return await self.controller.initialize()
        
    async def shutdown(self) -> bool:
        return await self.controller.shutdown()
        
    def is_available(self) -> bool:
        return self.controller.is_available()
        
    async def flash(self, zone_ids: List[str], settings: Any) -> Any:
        return await self.controller.flash(zone_ids, settings)
        
    async def turn_off_all(self) -> bool:
        return await self.controller.turn_off_all()
        
    async def get_status(self, zone_id: Optional[str] = None) -> Any:
        return await self.controller.get_status(zone_id)
    
    def get_sync_status(self, zone_id: Optional[str] = None) -> Any:
        """Synchronous wrapper for status - safe for web interface"""
        try:
            # Return basic status without async calls
            return {
                'zones': {},
                'initialized': self.controller.is_available() if hasattr(self.controller, 'is_available') else False,
                'status': 'available' if hasattr(self.controller, 'is_available') and self.controller.is_available() else 'unavailable'
            }
        except Exception:
            return {
                'zones': {},
                'initialized': False,
                'status': 'error'
            }
    
    def turn_off_all_sync(self) -> bool:
        """Synchronous wrapper for turn_off_all - safe for emergency stops"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.controller.turn_off_all())
            loop.close()
            return result
        except Exception as e:
            return False
            
    def flash_sync(self, zone_ids: List[str], settings: Any) -> Any:
        """Synchronous wrapper for flash - safe for web interface"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.controller.flash(zone_ids, settings))
            loop.close()
            return result
        except Exception as e:
            return False

class ScanOrchestrator:
    """
    Main orchestration engine for 3D scanning operations
    
    Coordinates motion controller, cameras, scan patterns, and state management
    to perform complete scanning workflows with error recovery and progress tracking.
    """
    
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the scan orchestrator
        
        Args:
            config_manager: System configuration manager
        """
        self.config_manager = config_manager
        self.config = config_manager  # ConfigManager itself has the config data
        
        # Initialize logger first
        self.logger = logging.getLogger(__name__)
        
        # Initialize components - UPDATED: Using real hardware controllers
        # Check if simulation mode is enabled
        if config_manager.get('system.simulation_mode', False):
            # Use mock controllers for simulation/testing
            self.motion_controller = MockMotionController(config_manager)
            self.camera_manager = MockCameraManager(config_manager)
            self.lighting_controller = MockLightingController(config_manager)
            self.logger.info("Initialized with mock hardware (simulation mode)")
        else:
            # Import and use real hardware controllers with adapters
            try:
                from motion.fluidnc_controller import FluidNCController
                from camera.pi_camera_controller import PiCameraController
                from lighting.gpio_led_controller import GPIOLEDController
                
                motion_config = config_manager.get('motion', {})
                camera_config = config_manager.get('cameras', {})
                lighting_config = config_manager.get('lighting', {})
                
                # Create hardware controllers
                fluidnc_controller = FluidNCController(motion_config)
                pi_camera_controller = PiCameraController(camera_config)
                gpio_lighting_controller = GPIOLEDController(lighting_config)
                
                # Wrap with adapters to match protocol interface
                self.motion_controller = MotionControllerAdapter(fluidnc_controller)
                self.camera_manager = CameraManagerAdapter(pi_camera_controller, config_manager)
                self.lighting_controller = LightingControllerAdapter(gpio_lighting_controller)
                self.logger.info("Initialized with real hardware controllers")
            except ImportError as e:
                self.logger.warning(f"Hardware modules not available, falling back to mocks: {e}")
                self.motion_controller = MockMotionController(config_manager)
                self.camera_manager = MockCameraManager(config_manager)
                self.lighting_controller = MockLightingController(config_manager)
        self.event_bus = EventBus()
        
        # Active scan state
        self.current_scan: Optional[ScanState] = None
        self.current_pattern: Optional[ScanPattern] = None
        self.scan_task: Optional[asyncio.Task] = None  # Store task reference
        
        # Runtime flags
        self._stop_requested = False
        self._pause_requested = False
        self._emergency_stop = False
        
        # Performance tracking
        self._timing_stats = {
            'movement_time': 0.0,
            'capture_time': 0.0,
            'processing_time': 0.0
        }
        
        # Subscribe to events
        self._setup_event_handlers()
    
    def _setup_event_handlers(self):
        """Setup event handlers for system events"""
        
        def emergency_handler(event):
            """Handle emergency stop events"""
            self.logger.critical("Emergency stop received")
            self._emergency_stop = True
            if self.current_scan:
                self.current_scan.add_error(
                    "emergency_stop", 
                    "Emergency stop activated",
                    recoverable=False
                )
        
        def motion_error_handler(event):
            """Handle motion controller errors"""
            if self.current_scan:
                self.current_scan.add_error(
                    "motion_error",
                    event.data.get('error', 'Motion controller error'),
                    event.data,
                    recoverable=event.data.get('recoverable', True)
                )
        
        def camera_error_handler(event):
            """Handle camera errors"""
            if self.current_scan:
                self.current_scan.add_error(
                    "camera_error",
                    event.data.get('error', 'Camera error'),
                    event.data,
                    recoverable=event.data.get('recoverable', True)
                )
        
        # Subscribe to events
        self.event_bus.subscribe("emergency_stop", emergency_handler)
        self.event_bus.subscribe("motion_error", motion_error_handler)
        self.event_bus.subscribe("camera_error", camera_error_handler)
    
    async def initialize(self) -> bool:
        """
        Initialize all scanner components
        
        Returns:
            True if initialization successful
        """
        try:
            self.logger.info("Initializing scan orchestrator")
            
            # Initialize motion controller
            if not await self.motion_controller.initialize():
                raise HardwareError("Failed to initialize motion controller")
            
            # Initialize camera manager
            if not await self.camera_manager.initialize():
                raise HardwareError("Failed to initialize camera manager")
            
            # Initialize lighting controller
            if not await self.lighting_controller.initialize():
                self.logger.warning("Failed to initialize lighting controller - continuing without lighting")
                # Don't fail initialization if lighting fails - scans can work without lighting
            
            # Perform system health check
            if not await self._health_check():
                raise ScannerSystemError("System health check failed")
            
            self.logger.info("Scan orchestrator initialized successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to initialize scan orchestrator: {e}")
            return False
    
    async def _health_check(self) -> bool:
        """Perform system health check"""
        try:
            # Check motion controller
            if not self.motion_controller.is_connected():
                self.logger.error("Motion controller not connected")
                return False
            
            # Check cameras
            if not await self.camera_manager.check_camera_health():
                self.logger.error("Camera health check failed")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
    
    async def start_scan(self, 
                        pattern: ScanPattern,
                        output_directory: Union[str, Path],
                        scan_id: Optional[str] = None,
                        scan_parameters: Optional[Dict[str, Any]] = None) -> ScanState:
        """
        Start a new scanning operation
        
        Args:
            pattern: Scan pattern to execute
            output_directory: Directory to save scan results
            scan_id: Optional scan identifier (auto-generated if None)
            scan_parameters: Additional scan parameters
            
        Returns:
            ScanState object for tracking progress
        """
        if self.current_scan and self.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED]:
            raise ScannerSystemError("Cannot start scan: another scan is active")
        
        # Generate scan ID if not provided
        if scan_id is None:
            scan_id = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create scan state
        self.current_scan = ScanState(
            scan_id=scan_id,
            pattern_id=pattern.pattern_id,
            output_directory=Path(output_directory)
        )
        self.current_pattern = pattern
        
        # Initialize scan parameters
        scan_parameters = scan_parameters or {}
        scan_parameters.update({
            'pattern_type': pattern.pattern_type.value,
            'pattern_parameters': pattern.parameters.__dict__,
            'total_points': len(pattern.generate_points()),
            'camera_settings': self.camera_manager.get_current_settings(),
            'motion_settings': self.motion_controller.get_current_settings()
        })
        
        # Initialize scan state
        self.current_scan.initialize(
            total_points=len(pattern.generate_points()),
            scan_parameters=scan_parameters
        )
        
        # Reset flags
        self._stop_requested = False
        self._pause_requested = False
        self._emergency_stop = False
        
        self.logger.info(f"Starting scan {scan_id} with {len(pattern.generate_points())} points")
        
        # Start scanning in background task and store reference
        self.scan_task = asyncio.create_task(self._execute_scan())
        
        # Add error callback to log any uncaught exceptions
        def task_done_callback(task: asyncio.Task):
            try:
                if task.cancelled():
                    self.logger.warning("Scan task was cancelled")
                elif task.exception():
                    exc = task.exception()
                    self.logger.error(f"Scan task failed with exception: {exc}")
                    import traceback
                    self.logger.error(f"Task exception traceback: {traceback.format_exc()}")
                else:
                    self.logger.info("Scan task completed successfully")
            except Exception as e:
                self.logger.error(f"Error in task callback: {e}")
        
        self.scan_task.add_done_callback(task_done_callback)
        
        return self.current_scan
    
    async def _execute_scan(self):
        """Main scan execution loop"""
        if not self.current_scan or not self.current_pattern:
            self.logger.error("Cannot execute scan: missing scan state or pattern")
            return
        
        try:
            # Switch camera to scanning mode for optimal scan performance
            if hasattr(self.camera_manager, 'set_scanning_mode'):
                self.camera_manager.set_scanning_mode(True)
                self.logger.info("Camera switched to scanning mode")
            
            # Start the scan
            self.current_scan.start()
            self.logger.info(f"Scan {self.current_scan.scan_id} started")
            
            # Home the system
            self.logger.info("Starting homing sequence")
            await self._home_system()
            self.logger.info("Homing completed")
            
            # Execute scan points
            self.logger.info("Starting scan points execution")
            await self._execute_scan_points()
            self.logger.info("Scan points execution completed")
            
            # Complete the scan
            if not self._stop_requested and not self._emergency_stop:
                self.current_scan.complete()
                self.logger.info(f"Scan {self.current_scan.scan_id} completed successfully")
            else:
                self.current_scan.cancel()
                self.logger.info(f"Scan {self.current_scan.scan_id} cancelled")
                
        except Exception as e:
            self.logger.error(f"Scan execution failed: {e}")
            import traceback
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
            if self.current_scan:
                self.current_scan.fail(str(e), {'exception_type': type(e).__name__})
        
        finally:
            # Always switch camera back to live streaming mode
            if hasattr(self.camera_manager, 'set_scanning_mode'):
                self.camera_manager.set_scanning_mode(False)
                self.logger.info("Camera switched back to live streaming mode")
            await self._cleanup_scan()
    
    async def _home_system(self):
        """Home the motion system"""
        if self._check_stop_conditions():
            return
        
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.HOMING)
        self.logger.info("Homing motion system")
        
        if not await self.motion_controller.home():
            raise HardwareError("Failed to home motion system")
    
    async def _execute_scan_points(self):
        """Execute all scan points"""
        if not self.current_pattern or not self.current_scan:
            return
        
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.POSITIONING)
        
        # Generate points from pattern
        scan_points = self.current_pattern.generate_points()
        self.logger.info(f"Starting scan of {len(scan_points)} points")
        
        for i, point in enumerate(scan_points):
            if self._check_stop_conditions():
                self.logger.info(f"Scan stopped at point {i}")
                break
            
            # Handle pause requests
            await self._handle_pause()
            
            try:
                self.logger.debug(f"Processing point {i+1}/{len(scan_points)}: {point.position}")
                
                # Move to position
                await self._move_to_point(point)
                
                # Capture images
                images_captured = await self._capture_at_point(point, i)
                
                # Update progress
                self.current_scan.update_progress(i + 1, images_captured)
                
                self.logger.debug(f"Completed point {i+1}/{len(scan_points)}")
                
            except Exception as e:
                self.logger.error(f"Failed to process point {i}: {e}")
                self.current_scan.add_error(
                    "point_processing_error",
                    f"Failed to process scan point {i}: {e}",
                    {'point_index': i, 'point_data': point.__dict__},
                    recoverable=True
                )
                
                # Continue with next point unless it's a critical error
                if not isinstance(e, HardwareError):
                    continue
                else:
                    raise
        
        self.logger.info(f"Scan execution completed")
    
    async def _move_to_point(self, point: ScanPoint):
        """Move to a scan point"""
        move_start = time.time()
        
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.POSITIONING)
        
        # Move to XY position
        if not await self.motion_controller.move_to(point.position.x, point.position.y):
            raise HardwareError(f"Failed to move to position ({point.position.x}, {point.position.y})")
        
        # Set Z rotation angle if specified
        if point.position.z is not None:
            if not await self.motion_controller.move_z_to(point.position.z):
                raise HardwareError(f"Failed to rotate Z-axis to {point.position.z} degrees")
        
        # Set rotation if specified
        if point.position.c is not None:
            if not await self.motion_controller.rotate_to(point.position.c):
                raise HardwareError(f"Failed to rotate to {point.position.c} degrees")
        
        # Wait for stabilization
        stabilization_delay = self.config.get('motion', {}).get('stabilization_delay', 0.5)
        await asyncio.sleep(stabilization_delay)
        
        self._timing_stats['movement_time'] += time.time() - move_start
    
    async def _capture_at_point(self, point: ScanPoint, point_index: int) -> int:
        """Capture images at a scan point"""
        capture_start = time.time()
        images_captured = 0
        
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.CAPTURING)
        
        try:
            # Generate filename for this point
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename_base = f"scan_{self.current_scan.scan_id if self.current_scan else 'unknown'}_point_{point_index:04d}_{timestamp}"
            
            # Apply lighting if configured and available
            lighting_applied = False
            if hasattr(point, 'lighting_settings') and point.lighting_settings and self.lighting_controller.is_available():
                try:
                    from lighting.base import LightingSettings
                    
                    # Convert lighting settings to proper format
                    settings = LightingSettings(
                        brightness=point.lighting_settings.get('brightness', 0.8),
                        duration_ms=point.lighting_settings.get('duration_ms', 100),
                        fade_time_ms=point.lighting_settings.get('fade_time_ms', 50)
                    )
                    
                    # Get zones to activate
                    zones = point.lighting_settings.get('zones', ['top_ring', 'side_ring'])
                    
                    # Flash lighting for capture
                    flash_result = await self.lighting_controller.flash(zones, settings)
                    lighting_applied = flash_result.get('success', False)
                    
                    if not lighting_applied:
                        self.logger.warning(f"Lighting flash failed at point {point_index}")
                    
                except Exception as e:
                    self.logger.warning(f"Failed to apply lighting at point {point_index}: {e}")
            
            # Small delay to allow lighting to stabilize before capture
            if lighting_applied:
                await asyncio.sleep(0.02)  # 20ms stabilization delay
            
            # Capture from all cameras
            capture_results = await self.camera_manager.capture_all(
                output_dir=self.current_scan.output_directory if self.current_scan else Path('.'),
                filename_base=filename_base,
                metadata={
                    'scan_id': self.current_scan.scan_id if self.current_scan else 'unknown',
                    'point_index': point_index,
                    'position': {
                        'x': point.position.x, 
                        'y': point.position.y, 
                        'z': point.position.z
                    },
                    'rotation': point.position.c,
                    'timestamp': timestamp,
                    'lighting_applied': lighting_applied
                }
            )
            
            images_captured = len([r for r in capture_results if r['success']])
            
            # Log any capture failures
            for result in capture_results:
                if not result['success'] and self.current_scan:
                    self.current_scan.add_error(
                        "capture_error",
                        f"Failed to capture from camera {result['camera_id']}: {result.get('error', 'Unknown error')}",
                        result,
                        recoverable=True
                    )
            
            self._timing_stats['capture_time'] += time.time() - capture_start
            return images_captured
            
        except Exception as e:
            self._timing_stats['capture_time'] += time.time() - capture_start
            raise HardwareError(f"Failed to capture images at point {point_index}: {e}")
    
    async def _handle_pause(self):
        """Handle pause requests"""
        if self._pause_requested and self.current_scan:
            self.logger.info("Handling pause request")
            self.current_scan.pause()
            self._pause_requested = False
            
            # Wait until resume is requested (with timeout to prevent infinite loops)
            pause_timeout = 30.0  # 30 second timeout
            pause_start = time.time()
            
            self.logger.info("Waiting for resume or stop")
            while self.current_scan.status == ScanStatus.PAUSED:
                if self._stop_requested or self._emergency_stop:
                    self.logger.info("Stop requested during pause")
                    break
                if time.time() - pause_start > pause_timeout:
                    self.logger.warning("Pause timeout reached, auto-resuming scan")
                    self.current_scan.resume()
                    break
                await asyncio.sleep(0.1)
            self.logger.info("Pause handling completed")
    
    def _check_stop_conditions(self) -> bool:
        """Check if scan should stop"""
        return self._stop_requested or self._emergency_stop
    
    async def _cleanup_scan(self):
        """Cleanup after scan completion"""
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.CLEANUP)
        
        try:
            # Return to home position
            await self.motion_controller.home()
            
            # Generate final report
            await self._generate_scan_report()
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
        
        finally:
            self.current_pattern = None
            # Keep current_scan for status queries
    
    async def _generate_scan_report(self):
        """Generate final scan report"""
        if not self.current_scan:
            return
        
        report_file = self.current_scan.output_directory / f"{self.current_scan.scan_id}_report.json"
        
        report_data = {
            'scan_id': self.current_scan.scan_id,
            'status': self.current_scan.status.value,
            'start_time': self.current_scan.timing.start_time.isoformat() if self.current_scan.timing.start_time else None,
            'end_time': self.current_scan.timing.end_time.isoformat() if self.current_scan.timing.end_time else None,
            'elapsed_time': self.current_scan.timing.elapsed_time,
            'points_processed': self.current_scan.progress.current_point,
            'total_points': self.current_scan.progress.total_points,
            'images_captured': self.current_scan.progress.images_captured,
            'completion_percentage': self.current_scan.progress.completion_percentage,
            'errors': len(self.current_scan.errors),
            'timing_stats': self._timing_stats,
            'scan_parameters': self.current_scan.scan_parameters
        }
        
        try:
            import json
            # Ensure output directory exists
            report_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)
            
            self.logger.info(f"Scan report saved to {report_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save scan report: {e}")
    
    async def wait_for_scan_completion(self, timeout: Optional[float] = None) -> bool:
        """
        Wait for the current scan to complete
        
        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)
            
        Returns:
            True if scan completed, False if timeout or no scan active
        """
        if not self.scan_task:
            return False
        
        try:
            if timeout:
                await asyncio.wait_for(self.scan_task, timeout=timeout)
            else:
                await self.scan_task
            return True
        except asyncio.TimeoutError:
            self.logger.warning(f"Scan did not complete within {timeout} seconds")
            return False
        except Exception as e:
            self.logger.error(f"Error waiting for scan completion: {e}")
            return False

    # Control methods
    
    async def pause_scan(self) -> bool:
        """Request scan pause"""
        if not self.current_scan or self.current_scan.status != ScanStatus.RUNNING:
            return False
        
        self._pause_requested = True
        self.logger.info("Scan pause requested")
        return True
    
    async def resume_scan(self) -> bool:
        """Resume paused scan"""
        if not self.current_scan or self.current_scan.status != ScanStatus.PAUSED:
            return False
        
        self.current_scan.resume()
        self.logger.info("Scan resumed")
        return True
    
    async def stop_scan(self) -> bool:
        """Request scan stop"""
        if not self.current_scan or self.current_scan.status not in [ScanStatus.RUNNING, ScanStatus.PAUSED]:
            return False
        
        self._stop_requested = True
        self.logger.info("Scan stop requested")
        return True
    
    async def emergency_stop(self):
        """Emergency stop all operations"""
        self._emergency_stop = True
        
        # Stop motion immediately
        await self.motion_controller.emergency_stop()
        
        # Stop cameras
        await self.camera_manager.stop_all()
        
        self.logger.critical("Emergency stop executed")
        
        # Publish emergency event
        self.event_bus.publish(
            "emergency_stop",
            {'timestamp': datetime.now().isoformat()},
            source_module="scan_orchestrator",
            priority=EventPriority.CRITICAL
        )
    
    # Status and information methods
    
    def get_scan_status(self) -> Optional[Dict[str, Any]]:
        """Get current scan status"""
        if not self.current_scan:
            return None
        
        return {
            'scan_id': self.current_scan.scan_id,
            'status': self.current_scan.status.value,
            'phase': self.current_scan.phase.value,
            'progress': {
                'current_point': self.current_scan.progress.current_point,
                'total_points': self.current_scan.progress.total_points,
                'completion_percentage': self.current_scan.progress.completion_percentage,
                'estimated_remaining': self.current_scan.progress.estimated_remaining
            },
            'timing': {
                'elapsed_time': self.current_scan.timing.elapsed_time,
                'start_time': self.current_scan.timing.start_time.isoformat() if self.current_scan.timing.start_time else None
            },
            'errors': len(self.current_scan.errors),
            'last_error': self.current_scan.errors[-1].message if self.current_scan.errors else None
        }
    
    def get_camera_status(self) -> Dict[str, Any]:
        """Get camera system status"""
        try:
            return self.camera_manager.get_status()
        except Exception as e:
            self.logger.error(f"Error getting camera status: {e}")
            return {
                'cameras': [],
                'active_cameras': [],
                'initialized': False,
                'error': str(e)
            }
    
    def get_preview_frame(self, camera_id) -> Optional[Any]:
        """Get a preview frame from a specific camera"""
        try:
            return self.camera_manager.get_preview_frame(camera_id)
        except Exception as e:
            self.logger.error(f"Error getting preview frame for camera {camera_id}: {e}")
            return None
    
    def create_grid_pattern(self, 
                           x_range: tuple[float, float],
                           y_range: tuple[float, float],
                           spacing: float,
                           z_rotation: Optional[float] = None,
                           rotations: Optional[List[float]] = None) -> GridScanPattern:
        """Create a grid scan pattern
        
        Args:
            x_range: Range of X-axis movement in mm
            y_range: Range of Y-axis movement in mm  
            spacing: Grid spacing in mm
            z_rotation: Fixed Z-axis rotation angle in degrees (if single angle)
            rotations: List of Z-axis rotation angles in degrees
        """
        from .scan_patterns import GridPatternParameters
        
        # Handle Z rotation - if single rotation provided, use small range around it
        if z_rotation is not None:
            min_z = z_rotation
            max_z = z_rotation + 0.1  # Small increment to satisfy validation
        else:
            min_z = 0.0
            max_z = 0.1
        
        # Create pattern parameters
        parameters = GridPatternParameters(
            min_x=x_range[0],
            max_x=x_range[1],
            min_y=y_range[0],
            max_y=y_range[1],
            min_z=min_z,
            max_z=max_z,
            x_spacing=spacing,
            y_spacing=spacing,
            c_steps=len(rotations) if rotations else 1,
            safety_margin=0.5  # Use smaller safety margin for wider coordinate ranges
        )
        
        # Generate pattern ID
        pattern_id = f"grid_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return GridScanPattern(pattern_id=pattern_id, parameters=parameters)
    
    def create_cylindrical_pattern(self,
                                 x_range: tuple[float, float],
                                 y_range: tuple[float, float], 
                                 x_step: float = 10.0,
                                 y_step: float = 15.0,
                                 z_rotations: Optional[List[float]] = None,
                                 c_angles: Optional[List[float]] = None):
        """
        Create a cylindrical scan pattern for turntable scanner
        
        Args:
            x_range: Horizontal camera movement range (start, end) in mm
            y_range: Vertical camera movement range (start, end) in mm  
            x_step: Horizontal step size in mm
            y_step: Vertical step size in mm
            z_rotations: Turntable rotation angles in degrees (None for default)
            c_angles: Camera pivot angles in degrees (None for default)
        """
        from .scan_patterns import CylindricalPatternParameters, CylindricalScanPattern
        
        # Create pattern parameters
        parameters = CylindricalPatternParameters(
            x_start=x_range[0],
            x_end=x_range[1],
            y_start=y_range[0],
            y_end=y_range[1],
            x_step=x_step,
            y_step=y_step,
            z_rotations=z_rotations,
            c_angles=c_angles,
            safety_margin=0.5  # Use smaller safety margin
        )
        
        # Generate pattern ID
        pattern_id = f"cylindrical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return CylindricalScanPattern(pattern_id=pattern_id, parameters=parameters)
    
    async def shutdown(self):
        """Shutdown the orchestrator"""
        self.logger.info("Shutting down scan orchestrator")
        
        # Stop any active scan
        if self.current_scan and self.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED]:
            await self.stop_scan()
            
            # Wait for scan to stop
            timeout = 10.0
            start_time = time.time()
            while (self.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED] 
                   and time.time() - start_time < timeout):
                await asyncio.sleep(0.1)
        
        # Shutdown components
        await self.motion_controller.shutdown()
        await self.camera_manager.shutdown()
        
        self.logger.info("Scan orchestrator shutdown complete")