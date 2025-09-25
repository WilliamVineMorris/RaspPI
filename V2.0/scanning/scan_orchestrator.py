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
import cv2
import numpy as np
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

class MockStorageManager:
    """Mock storage manager for testing"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._initialized = False
        self._sessions = {}
        self._current_session_id = None
        
    async def initialize(self) -> bool:
        await asyncio.sleep(0.1)
        self._initialized = True
        return True
        
    async def shutdown(self) -> bool:
        self._initialized = False
        return True
        
    def is_available(self) -> bool:
        return self._initialized
        
    async def create_session(self, session_metadata: Dict[str, Any]) -> str:
        session_id = f"mock_session_{len(self._sessions) + 1}"
        self._sessions[session_id] = {
            'id': session_id,
            'metadata': session_metadata,
            'created_at': time.time(),
            'files': []
        }
        self._current_session_id = session_id
        return session_id
        
    async def finalize_session(self, session_id: str) -> bool:
        if session_id in self._sessions:
            self._sessions[session_id]['completed_at'] = time.time()
            return True
        return False
        
    async def store_file(self, file_data: bytes, metadata: Any, location_name: Optional[str] = None) -> str:
        file_id = f"mock_file_{len(self._sessions.get(self._current_session_id, {}).get('files', [])) + 1}"
        if self._current_session_id and self._current_session_id in self._sessions:
            self._sessions[self._current_session_id]['files'].append({
                'file_id': file_id,
                'size': len(file_data),
                'metadata': metadata
            })
        return file_id
        
    async def list_sessions(self, limit: int = 100) -> List[Any]:
        return list(self._sessions.values())[:limit]

class MotionControllerAdapter:
    """Adapter to make Enhanced FluidNC Protocol Bridge compatible with orchestrator protocol
    
    Enhanced Protocol Performance:
    - Sub-second movement completion (0.7s typical vs 9+ seconds previously) 
    - Real-time position updates (61ms response vs polling delays)
    - Protocol-compliant message separation for reliability
    - 100% API compatibility with existing web interface
    """
    
    def __init__(self, fluidnc_controller):
        self.controller = fluidnc_controller
        self.logger = logging.getLogger(__name__)
        self._homing_in_progress = False
        
    async def initialize(self) -> bool:
        return await self.controller.initialize()
        
    async def home(self) -> bool:
        """Asynchronous wrapper for homing all axes with progress tracking"""
        try:
            self._homing_in_progress = True
            result = await self.controller.home_all_axes()
            self._homing_in_progress = False
            return result
        except Exception as e:
            self._homing_in_progress = False
            self.logger.error(f"Home axes failed: {e}")
            return False
        
    def home_axes(self, axes: List[str]) -> bool:
        """Synchronous wrapper for homing specific axes"""
        try:
            self._homing_in_progress = True
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.controller.home_all_axes())
            loop.close()
            self._homing_in_progress = False
            return result
        except Exception as e:
            self._homing_in_progress = False
            self.logger.error(f"Home axes failed: {e}")
            return False
        
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
        
    async def move_relative(self, delta, feedrate: Optional[float] = None) -> bool:
        """Asynchronous wrapper for relative movement"""
        return await self.controller.move_relative(delta, feedrate)
    
    async def move_to_position(self, position, feedrate: Optional[float] = None) -> bool:
        """Asynchronous wrapper for absolute position movement"""
        return await self.controller.move_to_position(position, feedrate)
        
    async def get_current_position(self):
        """Asynchronous wrapper for getting current position"""
        fresh_pos = await self.controller.get_current_position()
        self.logger.debug(f"Adapter get_current_position returning: {fresh_pos}")
        return fresh_pos
        
    async def force_position_update(self):
        """Force an immediate position update for debugging"""
        try:
            fresh_pos = await self.controller.get_current_position()
            self.logger.info(f"🔧 Forced position update: {fresh_pos}")
            return fresh_pos
        except Exception as e:
            self.logger.error(f"Force position update failed: {e}")
            return self.current_position
        
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
    
    @property
    def current_position(self):
        """Access the cached current position from the underlying controller"""
        if hasattr(self.controller, 'current_position'):
            pos = self.controller.current_position
            # Add debugging to see when position is accessed
            import time
            self.logger.debug(f"Adapter returning position: {pos} at {time.time()}")
            return pos
        else:
            # Fallback - create a basic position object
            from core.types import Position4D
            return Position4D(x=0.0, y=0.0, z=0.0, c=0.0)
    
    @property 
    def status(self):
        """Access the current status from the underlying controller"""
        if hasattr(self.controller, 'status'):
            return self.controller.status
        else:
            return 'unknown'
    
    @property
    def is_homed(self) -> bool:
        """Access the homing status from the underlying controller"""
        if hasattr(self.controller, 'is_homed'):
            return self.controller.is_homed and not self._homing_in_progress
        else:
            return False
        
    def get_status(self) -> Dict[str, Any]:
        """Get motion controller status with enhanced FluidNC information"""
        try:
            is_connected = self.controller.is_connected()
            self.logger.debug(f"Motion controller connection status: {is_connected}")
            
            # Get position and homing status from controller
            position = None
            is_homed = False
            raw_status = None
            fluidnc_status = None
            axes_homed = {'x': False, 'y': False, 'z': False, 'c': False}
            
            if is_connected:
                try:
                    # Get position from controller's cached current_position
                    if hasattr(self.controller, 'current_position'):
                        position = self.controller.current_position
                        position_dict = {
                            'x': getattr(position, 'x', 0.0),
                            'y': getattr(position, 'y', 0.0), 
                            'z': getattr(position, 'z', 0.0),
                            'c': getattr(position, 'c', 0.0)
                        }
                        self.logger.debug(f"Retrieved cached position from FluidNC controller: {position_dict}")
                    elif hasattr(self.controller, 'get_position_sync'):
                        position = self.controller.get_position_sync()
                        position_dict = {
                            'x': position.x,
                            'y': position.y, 
                            'z': position.z,
                            'c': position.c
                        }
                    else:
                        self.logger.warning("Controller has no current_position or get_position_sync, using defaults")
                        position_dict = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
                    
                    # Get enhanced FluidNC status information
                    if hasattr(self.controller, '_last_status'):
                        raw_status = self.controller._last_status
                        self.logger.debug(f"Raw FluidNC status: {raw_status}")
                        
                        # Parse FluidNC status for detailed information
                        if raw_status:
                            # Extract state information
                            if '<Idle' in raw_status:
                                fluidnc_status = 'Idle'
                            elif '<Run' in raw_status:
                                fluidnc_status = 'Run'
                            elif '<Home' in raw_status:
                                fluidnc_status = 'Homing'
                            elif '<Jog' in raw_status:
                                fluidnc_status = 'Jogging'
                            elif '<Alarm' in raw_status:
                                fluidnc_status = 'Alarm'
                            else:
                                fluidnc_status = 'Unknown'
                                
                            # Check individual axis homing status
                            # FluidNC typically shows homed axes in status
                            if ':' in raw_status and '|' in raw_status:
                                # Parse individual axis status if available
                                # This is FluidNC specific and may need adjustment
                                try:
                                    # Look for homing indicators in status
                                    if 'H' in raw_status or 'homed' in raw_status.lower():
                                        # Assume all axes are homed if any homing indicator present
                                        axes_homed = {'x': True, 'y': True, 'z': True, 'c': True}
                                except Exception as parse_error:
                                    self.logger.debug(f"Could not parse individual axis status: {parse_error}")
                    
                    # Get homing status - don't report homed=True if homing is in progress
                    if hasattr(self.controller, 'is_homed'):
                        is_homed = self.controller.is_homed and not self._homing_in_progress
                    
                    # Alternative homing detection from raw status
                    if not is_homed and raw_status and 'Idle' in raw_status:
                        # Check if this looks like a post-homing idle state
                        # This is a heuristic and may need adjustment
                        if any(axes_homed.values()) or 'H' in raw_status:
                            is_homed = True
                        
                except Exception as e:
                    self.logger.debug(f"Error getting detailed motion status: {e}")
                    position_dict = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
            else:
                position_dict = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
            
            # Determine state based on homing status and connection
            if self._homing_in_progress:
                state = 'homing'
            elif is_connected:
                if fluidnc_status == 'Homing':
                    state = 'homing'
                elif fluidnc_status == 'Run' or fluidnc_status == 'Jogging':
                    state = 'moving'
                elif fluidnc_status == 'Alarm':
                    state = 'alarm'
                else:
                    state = 'idle'
            else:
                state = 'disconnected'
                
            return {
                'status': state,  # Add this for compatibility
                'state': state,
                'connected': is_connected,
                'initialized': is_connected,
                'is_homed': is_homed,
                'homed': is_homed,  # Add both field names for compatibility
                'position': position_dict,
                'raw_status': raw_status,
                'fluidnc_status': fluidnc_status,
                'axes_homed': axes_homed,
                'homing_in_progress': self._homing_in_progress
            }
        except Exception as e:
            self.logger.error(f"Error getting motion controller status: {e}")
            return {
                'status': 'error',
                'state': 'error',
                'connected': False,
                'initialized': False,
                'is_homed': False,
                'homed': False,
                'position': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0},
                'raw_status': None,
                'fluidnc_status': 'Error',
                'axes_homed': {'x': False, 'y': False, 'z': False, 'c': False},
                'homing_in_progress': False
            }
            
    def get_position(self) -> Dict[str, float]:
        """Get current position in a dict format"""
        try:
            # Use cached current_position from the controller
            if hasattr(self.controller, 'current_position'):
                pos = self.controller.current_position
                return {
                    'x': getattr(pos, 'x', 0.0),
                    'y': getattr(pos, 'y', 0.0), 
                    'z': getattr(pos, 'z', 0.0),
                    'c': getattr(pos, 'c', 0.0)
                }
            elif hasattr(self.controller, 'get_position_sync'):
                # Use synchronous method if available
                pos = self.controller.get_position_sync()
                return {
                    'x': pos.x if hasattr(pos, 'x') else 0.0,
                    'y': pos.y if hasattr(pos, 'y') else 0.0, 
                    'z': pos.z if hasattr(pos, 'z') else 0.0,
                    'c': pos.c if hasattr(pos, 'c') else 0.0
                }
            else:
                # Fallback to basic position if no sync method
                return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
        except Exception as e:
            self.logger.debug(f"Error getting position: {e}")
            return {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
        
    def get_current_settings(self) -> Dict[str, Any]:
        return {'controller_type': 'FluidNC', 'connected': self.controller.is_connected()}


class CameraManagerAdapter:
    """Adapter to make PiCameraController compatible with orchestrator protocol"""
    
    def __init__(self, pi_camera_controller, config_manager):
        self.controller = pi_camera_controller
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Dual-mode camera system for optimized streaming and capture
        self._streaming_mode = True  # Start in streaming-only mode
        self._is_scanning = False
        
        # Picamera2 dual-configuration system
        self._stream_config = None    # 1080p streaming configuration
        self._capture_config = None   # High-res capture configuration
        self._current_mode = "streaming"  # Current camera mode
        
        # Performance and resource management
        self._camera_instances = {}   # Store camera instances for each mode
        self._last_mode_switch = 0
        self._mode_switch_cooldown = 1.0  # Minimum seconds between mode switches
        
        # Camera resource locking (simplified for dual-mode)
        import threading
        self._mode_lock = threading.Lock()  # Lock for mode switching
        self._capture_lock = threading.Lock()  # Lock for captures
        
        # OPTIMAL CONFIGURATION: Camera native output used directly
        self._force_color_conversion = 'native_direct'  # Fixed optimal mode
        self.logger.info("CAMERA: Initialized with optimal native RGB888 output (no conversion needed)")
            
        self.logger.info("CAMERA: Camera adapter initialized with color format configuration")
        
        self.logger.info("CAMERA: Dual-mode system initialized (1080p streaming + high-res capture)")
        
    async def initialize(self) -> bool:
        """Initialize dual-mode camera system with optimized configurations"""
        try:
            # Initialize the underlying controller
            result = await self.controller.initialize()
            
            if result:
                # Setup dual-mode configurations using Picamera2 native functions
                await self._setup_dual_mode_configurations()
                self.logger.info("CAMERA: Dual-mode system initialized successfully")
                return True
            else:
                self.logger.error("CAMERA: Failed to initialize underlying controller")
                return False
                
        except Exception as e:
            self.logger.error(f"CAMERA: Dual-mode initialization failed: {e}")
            return False
    
    async def _setup_dual_mode_configurations(self):
        """Setup optimized camera configurations for streaming and capture"""
        try:
            # Only configure Camera 0 for dual-mode operation
            camera_id = 0
            
            if hasattr(self.controller, 'cameras') and camera_id in self.controller.cameras:
                camera = self.controller.cameras[camera_id]
                
                if camera:
                    # OPTIMAL: RGB888 format with direct output provides correct colors
                    self._stream_config = camera.create_video_configuration(
                        main={"size": (1920, 1080), "format": "RGB888"},
                        lores={"size": (640, 480), "format": "YUV420"},  # Thumbnail for processing
                        display="lores"  # Use low-res for display efficiency
                    )
                    
                    # OPTIMAL: RGB888 format for high-res capture
                    self._capture_config = camera.create_still_configuration(
                        main={"size": (4608, 2592), "format": "RGB888"},  # Full sensor resolution
                        lores={"size": (1920, 1080), "format": "YUV420"},  # Preview
                        display="lores"
                    )
                    
                    # Start in streaming mode
                    camera.configure(self._stream_config)
                    camera.start()
                    
                    self._current_mode = "streaming"
                    self.logger.info("CAMERA: OPTIMAL CONFIGURATION - RGB888 native output provides perfect colors")
                    
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to setup dual-mode configurations: {e}")
    
    async def _switch_camera_mode(self, target_mode: str):
        """Efficiently switch between streaming and capture modes"""
        try:
            current_time = time.time()
            
            # Check cooldown to prevent rapid switching
            if current_time - self._last_mode_switch < self._mode_switch_cooldown:
                return False
            
            with self._mode_lock:
                if self._current_mode == target_mode:
                    return True  # Already in target mode
                
                camera_id = 0
                if hasattr(self.controller, 'cameras') and camera_id in self.controller.cameras:
                    camera = self.controller.cameras[camera_id]
                    
                    if camera:
                        # Stop current mode
                        if hasattr(camera, 'stop'):
                            camera.stop()
                        
                        # Switch configuration
                        if target_mode == "streaming":
                            camera.configure(self._stream_config)
                        elif target_mode == "capture":
                            camera.configure(self._capture_config)
                        
                        # Restart with new configuration
                        camera.start()
                        
                        self._current_mode = target_mode
                        self._last_mode_switch = current_time
                        
                        self.logger.info(f"CAMERA: Switched to {target_mode} mode")
                        return True
                        
        except Exception as e:
            self.logger.error(f"CAMERA: Mode switch to {target_mode} failed: {e}")
            return False
        
    async def capture_all(self, output_dir: Path, filename_base: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Capture from all available cameras with autofocus and optimization"""
        results = []
        
        try:
            # Switch to capture mode for high-resolution images
            await self._switch_camera_mode("capture")
            
            # Trigger autofocus before capture for optimal sharpness
            self.logger.info("CAMERA: Triggering autofocus before capture")
            await self.trigger_autofocus('camera_1')
            
            # Brief wait for autofocus to complete
            await asyncio.sleep(1.0)
            
            # Capture high-resolution image from Camera 0
            try:
                # Use high-resolution capture method
                high_res_image = await self.capture_high_resolution('camera_1', metadata.get('camera_settings'))
                
                if high_res_image is not None:
                    # Save the high-resolution image
                    output_path = output_dir / f"{filename_base}_camera_1.jpg"
                    
                    # Encode and save
                    import cv2
                    success = cv2.imwrite(str(output_path), high_res_image, [
                        cv2.IMWRITE_JPEG_QUALITY, 95,  # High quality for scanning
                        cv2.IMWRITE_JPEG_OPTIMIZE, 1
                    ])
                    
                    if success:
                        results.append({
                            'camera_id': 'camera_1',
                            'filepath': str(output_path),
                            'resolution': high_res_image.shape,
                            'success': True,
                            'metadata': {
                                'autofocus_used': True,
                                'capture_mode': 'high_resolution',
                                **metadata
                            }
                        })
                        self.logger.info(f"CAMERA: High-res capture saved: {output_path}, shape: {high_res_image.shape}")
                    else:
                        self.logger.error(f"CAMERA: Failed to save high-res image to {output_path}")
                else:
                    self.logger.error("CAMERA: High-resolution capture returned None")
                    
            except Exception as capture_error:
                self.logger.error(f"CAMERA: High-resolution capture failed: {capture_error}")
                results.append({
                    'camera_id': 'camera_1',
                    'success': False,
                    'error': str(capture_error)
                })
            
            # Switch back to streaming mode
            await self._switch_camera_mode("streaming")
            
        except Exception as e:
            self.logger.error(f"CAMERA: Capture all failed: {e}")
            # Ensure we return to streaming mode on error
            try:
                await self._switch_camera_mode("streaming")
            except:
                pass
                
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
    
    def get_preview_frame(self, camera_id):
        """
        Get optimized preview frame using Picamera2 native streaming
        
        Uses dual-mode system:
        - Streaming mode: 1080p with minimal processing
        - Capture mode: High-res with full quality
        """
        try:
            current_time = time.time()
            
            # Rate-limited debug logging
            if not hasattr(self, '_last_debug_log') or (current_time - self._last_debug_log) > 20.0:
                self.logger.info(f"CAMERA: Native preview frame requested for {camera_id}")
                self._last_debug_log = current_time
            
            # Only Camera 0 supported in current implementation
            if camera_id not in [0, '0', 'camera_1']:
                return None
            
            # Map camera ID
            mapped_camera_id = 0
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                try:
                    mapped_camera_id = int(camera_id.split('_')[1]) - 1
                except (ValueError, IndexError):
                    return None
            
            # Access Camera 0 directly
            if hasattr(self.controller, 'cameras') and mapped_camera_id in self.controller.cameras:
                camera = self.controller.cameras[mapped_camera_id]
                
                if camera and hasattr(camera, 'capture_array'):
                    try:
                        # Ensure we're in streaming mode for live preview
                        if self._current_mode != "streaming":
                            asyncio.create_task(self._switch_camera_mode("streaming"))
                            time.sleep(0.1)  # Brief wait for mode switch
                        
                        # Use Picamera2's native capture with streaming-optimized config
                        # This gets the 1080p main stream directly without additional processing
                        frame_array = camera.capture_array("main")
                        
                        if frame_array is not None and frame_array.size > 0:
                            # OPTIMAL: Use camera RGB888 output directly - provides perfect colors
                            frame_bgr = frame_array.copy()  # Direct use - optimal performance
                            
                            if not hasattr(self, '_color_format_logged'):
                                self.logger.info("CAMERA: Using native RGB888 output directly - optimal configuration (no conversion overhead)")
                                self._color_format_logged = True
                                
                            # Frame is ready for OpenCV JPEG encoding
                            
                            # Optional: Apply minimal enhancement for better web display
                            # Only if the frame appears too dark/flat
                            mean_brightness = np.mean(frame_bgr)
                            if mean_brightness < 80:  # Dark frame
                                frame_bgr = cv2.convertScaleAbs(frame_bgr, alpha=1.2, beta=15)
                            
                            # Performance logging
                            if not hasattr(self, '_last_success_log') or (current_time - self._last_success_log) > 20.0:
                                self.logger.info(f"CAMERA: Native 1080p frame captured: {frame_bgr.shape}, dtype: {frame_bgr.dtype}")
                                self._last_success_log = current_time
                            
                            return frame_bgr
                        else:
                            self.logger.warning(f"CAMERA: Empty frame from native capture")
                            
                    except Exception as capture_error:
                        if not hasattr(self, '_last_error_log') or (current_time - self._last_error_log) > 10.0:
                            self.logger.error(f"CAMERA: Native capture failed: {capture_error}")
                            self._last_error_log = current_time
                else:
                    self.logger.warning(f"CAMERA: Camera {mapped_camera_id} not available or missing capture method")
            else:
                self.logger.warning(f"CAMERA: No camera available for ID {camera_id}")
                
            return None
            
        except Exception as e:
            self.logger.error(f"CAMERA: Error in native preview frame for {camera_id}: {e}")
            return None
    
    async def capture_high_resolution(self, camera_id, settings=None):
        """
        Capture high-resolution photo for scanning using native Picamera2 functions
        
        Args:
            camera_id: Camera identifier
            settings: Optional camera settings
            
        Returns:
            numpy.ndarray: High-resolution image or None if failed
        """
        try:
            with self._capture_lock:
                # Switch to capture mode for maximum quality
                await self._switch_camera_mode("capture")
                
                # Only Camera 0 supported
                mapped_camera_id = 0
                if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                    try:
                        mapped_camera_id = int(camera_id.split('_')[1]) - 1
                    except (ValueError, IndexError):
                        return None
                
                if hasattr(self.controller, 'cameras') and mapped_camera_id in self.controller.cameras:
                    camera = self.controller.cameras[mapped_camera_id]
                    
                    if camera and hasattr(camera, 'capture_array'):
                        # Apply custom settings if provided
                        if settings:
                            # Convert settings to Picamera2 controls
                            controls = {}
                            if hasattr(settings, 'exposure_time') and settings.exposure_time:
                                controls['ExposureTime'] = int(settings.exposure_time * 1000000)  # Convert to microseconds
                            if hasattr(settings, 'iso') and settings.iso:
                                controls['AnalogueGain'] = settings.iso / 100.0
                            
                            if controls:
                                camera.set_controls(controls)
                        
                        # Capture full resolution image using main stream
                        self.logger.info("CAMERA: Capturing high-resolution image (4K+)")
                        
                        # Use still capture for maximum quality
                        image_array = camera.capture_array("main")
                        
                        if image_array is not None and image_array.size > 0:
                            # OPTIMAL: Use camera RGB888 output directly for high-res captures
                            image_bgr = image_array.copy()  # Direct use - optimal performance
                            
                            # No conversions needed - camera provides perfect format
                            self.logger.info(f"CAMERA: High-res capture using optimal native RGB888 format: {image_bgr.shape}, dtype: {image_bgr.dtype}")
                            return image_bgr
                        else:
                            self.logger.error("CAMERA: High-res capture returned empty array")
                            
                # Switch back to streaming mode
                await self._switch_camera_mode("streaming")
                
        except Exception as e:
            self.logger.error(f"CAMERA: High-resolution capture failed: {e}")
            # Ensure we switch back to streaming mode on error
            try:
                await self._switch_camera_mode("streaming")
            except:
                pass
                
        return None
    
    async def set_camera_controls(self, camera_id, controls_dict):
        """
        Set camera controls for autofocus, exposure, etc.
        
        Args:
            camera_id: Camera identifier
            controls_dict: Dictionary of control settings
                          e.g., {'autofocus': True, 'exposure_time': 10000, 'iso': 400}
        """
        try:
            # Map camera ID
            mapped_camera_id = 0
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                try:
                    mapped_camera_id = int(camera_id.split('_')[1]) - 1
                except (ValueError, IndexError):
                    return False
            
            if hasattr(self.controller, 'cameras') and mapped_camera_id in self.controller.cameras:
                camera = self.controller.cameras[mapped_camera_id]
                
                if camera and hasattr(camera, 'set_controls'):
                    # Convert common controls to Picamera2 format
                    picam_controls = {}
                    
                    # Autofocus control
                    if 'autofocus' in controls_dict:
                        if controls_dict['autofocus']:
                            picam_controls['AfMode'] = 1  # Auto focus
                            picam_controls['AfTrigger'] = 0  # Trigger autofocus
                        else:
                            picam_controls['AfMode'] = 0  # Manual focus
                    
                    # Manual focus control
                    if 'focus_position' in controls_dict:
                        picam_controls['LensPosition'] = float(controls_dict['focus_position'])
                    
                    # Exposure controls
                    if 'exposure_time' in controls_dict:
                        # Convert milliseconds to microseconds
                        picam_controls['ExposureTime'] = int(controls_dict['exposure_time'] * 1000)
                    
                    if 'auto_exposure' in controls_dict:
                        if controls_dict['auto_exposure']:
                            picam_controls['AeEnable'] = True
                        else:
                            picam_controls['AeEnable'] = False
                    
                    # ISO/Gain control
                    if 'iso' in controls_dict:
                        picam_controls['AnalogueGain'] = controls_dict['iso'] / 100.0
                    
                    # White balance
                    if 'auto_white_balance' in controls_dict:
                        if controls_dict['auto_white_balance']:
                            picam_controls['AwbEnable'] = True
                        else:
                            picam_controls['AwbEnable'] = False
                            # Set stable white balance gains to reduce flickering
                            picam_controls['ColourGains'] = (1.4, 1.2)  # Daylight balanced
                    
                    if 'white_balance_gains' in controls_dict:
                        gains = controls_dict['white_balance_gains']
                        if isinstance(gains, (list, tuple)) and len(gains) == 2:
                            picam_controls['ColourGains'] = gains
                    
                    # Stabilization settings to reduce flickering
                    if 'stabilize_exposure' in controls_dict and controls_dict['stabilize_exposure']:
                        # Lock exposure to reduce flickering
                        picam_controls['AeEnable'] = False
                        picam_controls['ExposureTime'] = 15000  # 15ms stable exposure for low light
                        
                    if 'stabilize_awb' in controls_dict and controls_dict['stabilize_awb']:
                        # Lock AWB to reduce color shifts - neutral indoor balance
                        picam_controls['AwbEnable'] = False
                        picam_controls['ColourGains'] = (1.3, 1.5)  # Neutral indoor balance
                    
                    # Quick white balance lock for color switching issues
                    if 'lock_white_balance' in controls_dict and controls_dict['lock_white_balance']:
                        picam_controls['AwbEnable'] = False
                        # Use current lighting-appropriate gains
                        if 'wb_mode' in controls_dict:
                            if controls_dict['wb_mode'] == 'daylight':
                                picam_controls['ColourGains'] = (1.4, 1.2)  # Cooler daylight
                            elif controls_dict['wb_mode'] == 'tungsten':
                                picam_controls['ColourGains'] = (1.0, 1.8)  # Warmer tungsten
                            elif controls_dict['wb_mode'] == 'indoor':
                                picam_controls['ColourGains'] = (1.2, 1.4)  # Neutral indoor
                            else:
                                picam_controls['ColourGains'] = (1.3, 1.5)  # Default neutral
                        else:
                            picam_controls['ColourGains'] = (1.3, 1.5)  # Default neutral
                    
                    # Apply controls
                    if picam_controls:
                        camera.set_controls(picam_controls)
                        self.logger.info(f"CAMERA: Applied controls {picam_controls} to camera {camera_id}")
                        return True
                    else:
                        self.logger.warning(f"CAMERA: No valid controls provided for camera {camera_id}")
                        
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to set controls for camera {camera_id}: {e}")
            
        return False
    
    async def trigger_autofocus(self, camera_id):
        """Trigger autofocus on camera"""
        try:
            return await self.set_camera_controls(camera_id, {'autofocus': True})
        except Exception as e:
            self.logger.error(f"CAMERA: Autofocus trigger failed for {camera_id}: {e}")
            return False
    
    async def set_manual_focus(self, camera_id, focus_position):
        """
        Set manual focus position
        
        Args:
            camera_id: Camera identifier
            focus_position: Focus position (0.0 to 10.0, where 0 is near, 10 is far)
        """
        try:
            return await self.set_camera_controls(camera_id, {
                'autofocus': False,
                'focus_position': focus_position
            })
        except Exception as e:
            self.logger.error(f"CAMERA: Manual focus failed for {camera_id}: {e}")
            return False
    
    async def get_camera_controls(self, camera_id):
        """Get current camera control values"""
        try:
            # Map camera ID
            mapped_camera_id = 0
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                try:
                    mapped_camera_id = int(camera_id.split('_')[1]) - 1
                except (ValueError, IndexError):
                    return {}
            
            if hasattr(self.controller, 'cameras') and mapped_camera_id in self.controller.cameras:
                camera = self.controller.cameras[mapped_camera_id]
                
                if camera and hasattr(camera, 'capture_metadata'):
                    # Get current metadata which includes control values
                    metadata = camera.capture_metadata()
                    
                    # Extract useful control information
                    controls = {
                        'exposure_time': metadata.get('ExposureTime', 0) / 1000,  # Convert to ms
                        'analog_gain': metadata.get('AnalogueGain', 1.0),
                        'digital_gain': metadata.get('DigitalGain', 1.0),
                        'focus_position': metadata.get('LensPosition', 0.0),
                        'color_gains': metadata.get('ColourGains', [1.0, 1.0])
                    }
                    
                    return controls
                    
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to get controls for camera {camera_id}: {e}")
            
        return {}
    
    def set_scanning_mode(self, is_scanning: bool):
        """Set scanning mode to optimize camera usage"""
        self._is_scanning = is_scanning
        self._streaming_mode = not is_scanning  # Streaming mode is opposite of scanning mode
        
        if is_scanning:
            self.logger.info("Camera mode set to: SCANNING (both cameras available)")
        else:
            self.logger.info("Camera mode set to: STREAMING (Camera 0 only for web interface)")
        
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
                # Always show both cameras as available, but active cameras depend on mode
                if getattr(self, '_streaming_mode', False):
                    status = {
                        'cameras': ['camera_1', 'camera_2'],  # Both cameras available
                        'active_cameras': ['camera_1'],  # Only Camera 0 active in streaming mode
                        'initialized': True
                    }
                    self.logger.debug(f"Camera status (streaming mode): {status}")
                else:
                    # Scanning mode - both cameras available and active
                    status = {
                        'cameras': ['camera_1', 'camera_2'],  # Both cameras available
                        'active_cameras': ['camera_1', 'camera_2'],  # Both cameras active for scanning
                        'initialized': True
                    }
                    self.logger.info(f"Camera status (scanning mode): {status}")
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
            self.storage_manager = MockStorageManager(config_manager)
            self.logger.info("Initialized with mock hardware (simulation mode)")
        else:
            # Import and use real hardware controllers with adapters
            try:
                # Use NEW SimplifiedFluidNCControllerFixed for timeout fixes and intelligent feedrates
                from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
                from camera.pi_camera_controller import PiCameraController
                from lighting.gpio_led_controller import GPIOLEDController
                from storage.session_manager import SessionManager
                
                motion_config = config_manager.get('motion', {})
                camera_config = config_manager.get('cameras', {})
                lighting_config = config_manager.get('lighting', {})
                storage_config = config_manager.get('storage', {})
                
                # Create motion controller configuration with feedrates from YAML
                controller_config = {
                    'port': motion_config.get('controller', {}).get('port', '/dev/ttyUSB0'),
                    'baud_rate': motion_config.get('controller', {}).get('baudrate', 115200),
                    'command_timeout': motion_config.get('controller', {}).get('timeout', 30.0),
                    'motion_limits': {
                        'x': {
                            'min': motion_config.get('axes', {}).get('x_axis', {}).get('min_limit', 0.0),
                            'max': motion_config.get('axes', {}).get('x_axis', {}).get('max_limit', 200.0),
                            'max_feedrate': motion_config.get('axes', {}).get('x_axis', {}).get('max_feedrate', 1000.0)
                        },
                        'y': {
                            'min': motion_config.get('axes', {}).get('y_axis', {}).get('min_limit', 0.0),
                            'max': motion_config.get('axes', {}).get('y_axis', {}).get('max_limit', 200.0),
                            'max_feedrate': motion_config.get('axes', {}).get('y_axis', {}).get('max_feedrate', 1000.0)
                        },
                        'z': {
                            'min': motion_config.get('axes', {}).get('z_axis', {}).get('min_limit', -180.0),
                            'max': motion_config.get('axes', {}).get('z_axis', {}).get('max_limit', 180.0),
                            'max_feedrate': motion_config.get('axes', {}).get('z_axis', {}).get('max_feedrate', 800.0)
                        },
                        'c': {
                            'min': motion_config.get('axes', {}).get('c_axis', {}).get('min_limit', -90.0),
                            'max': motion_config.get('axes', {}).get('c_axis', {}).get('max_limit', 90.0),
                            'max_feedrate': motion_config.get('axes', {}).get('c_axis', {}).get('max_feedrate', 5000.0)
                        }
                    },
                    'feedrates': motion_config.get('feedrates', {})  # Include feedrate configuration
                }
                
                # Create hardware controllers - NEW enhanced controller with timeout fixes and feedrate management
                fluidnc_controller = SimplifiedFluidNCControllerFixed(controller_config)
                pi_camera_controller = PiCameraController(camera_config)
                gpio_lighting_controller = GPIOLEDController(lighting_config)
                session_manager = SessionManager(storage_config)
                
                # NEW: Direct use without adapter - SimplifiedFluidNCControllerFixed implements full MotionController interface
                self.motion_controller = fluidnc_controller  # No adapter needed!
                self.camera_manager = CameraManagerAdapter(pi_camera_controller, config_manager)
                self.lighting_controller = LightingControllerAdapter(gpio_lighting_controller)
                self.storage_manager = session_manager
                self.logger.info("✅ Initialized with NEW SimplifiedFluidNCControllerFixed - timeout fixes and intelligent feedrates enabled!")
            except ImportError as e:
                self.logger.warning(f"Hardware modules not available, falling back to mocks: {e}")
                self.motion_controller = MockMotionController(config_manager)
                self.camera_manager = MockCameraManager(config_manager)
                self.lighting_controller = MockLightingController(config_manager)
                self.storage_manager = MockStorageManager(config_manager)
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
        Initialize all scanner components with graceful error handling
        
        Returns:
            True if initialization successful (allows partial initialization)
        """
        try:
            self.logger.info("Initializing scan orchestrator")
            
            # Initialize motion controller - allow continuation if in alarm state
            motion_ok = False
            try:
                motion_ok = await self.motion_controller.initialize()
                if motion_ok:
                    # Check if motion controller is in alarm state
                    status = await self.motion_controller.get_status()
                    if status.name == "ALARM":
                        self.logger.warning("⚠️ Motion controller connected but in ALARM state")
                        self.logger.info("💡 Motion controller needs homing - use web interface 'Home' button")
                        self.logger.info("✅ System will continue with camera functionality")
                        motion_ok = True  # Consider alarm state as "connected"
                    else:
                        self.logger.info("✅ Motion controller initialized and ready")
                else:
                    self.logger.error("❌ Motion controller failed to initialize")
            except Exception as e:
                self.logger.error(f"❌ Motion controller initialization error: {e}")
                motion_ok = False
            
            # Initialize camera manager - this is critical for system functionality  
            camera_ok = False
            try:
                camera_ok = await self.camera_manager.initialize()
                if camera_ok:
                    self.logger.info("✅ Camera manager initialized successfully")
                else:
                    self.logger.error("❌ Camera manager failed to initialize")
            except Exception as e:
                self.logger.error(f"❌ Camera manager initialization error: {e}")
                camera_ok = False
            
            # Initialize lighting controller - optional
            lighting_ok = False
            try:
                lighting_ok = await self.lighting_controller.initialize()
                if lighting_ok:
                    self.logger.info("✅ Lighting controller initialized")
                else:
                    self.logger.warning("⚠️ Lighting controller failed - continuing without lighting")
            except Exception as e:
                self.logger.warning(f"⚠️ Lighting controller error (non-critical): {e}")
                lighting_ok = False
            
            # Determine overall initialization success
            # Require at least cameras to work - motion can be in alarm state
            if camera_ok:
                if motion_ok:
                    self.logger.info("✅ Scan orchestrator fully initialized")
                else:
                    self.logger.warning("⚠️ Scan orchestrator initialized with motion controller issues")
                    self.logger.info("💡 Camera functionality available - motion may need attention")
                
                return True
            else:
                self.logger.error("❌ Scan orchestrator initialization failed - cameras required")
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to initialize scan orchestrator: {e}")
            return False
    
    async def _health_check(self) -> bool:
        """Perform system health check"""
        try:
            # Check motion controller
            if not await self.motion_controller.is_connected():
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
            # Use synchronous version to avoid coroutine in web interface
            if hasattr(self.camera_manager, 'get_status_sync'):
                camera_status = self.camera_manager.get_status_sync()
            else:
                # Fallback for other camera controllers
                camera_status = self.camera_manager.get_status()
            
            # Convert CameraStatus to dict if needed
            if hasattr(camera_status, '__dict__'):
                return camera_status.__dict__
            else:
                return camera_status
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