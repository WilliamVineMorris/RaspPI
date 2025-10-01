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
import json
import cv2
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Protocol, TYPE_CHECKING, Callable

if TYPE_CHECKING:
    import numpy as np

from core.config_manager import ConfigManager
from core.events import EventBus, EventPriority
from core.exceptions import ScannerSystemError, HardwareError, ConfigurationError

from .scan_patterns import ScanPattern, ScanPoint, GridScanPattern
from .scan_state import ScanState, ScanStatus, ScanPhase
from .scan_profiles import ScanProfileManager

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
        
    async def move_to_position(self, position, feedrate: Optional[float] = None) -> bool:
        """Move to 4D position - optimized single command version"""
        await asyncio.sleep(0.3)  # Simulate single coordinated movement
        self._position.update({
            'x': position.x, 
            'y': position.y, 
            'z': position.z, 
            'rotation': position.c
        })
        return True
        
    async def move_with_servo_tilt(self, position, servo_mode: str = "automatic", 
                                 user_y_focus: float = 50.0, manual_servo_angle: float = 0.0,
                                 feedrate: Optional[float] = None) -> bool:
        """Mock servo tilt movement for testing"""
        await asyncio.sleep(0.3)
        # Simulate servo angle calculation
        if servo_mode == "automatic":
            # Mock automatic calculation based on position
            calculated_angle = -30.0 + (position.x - 100) * 0.1  # Mock formula
            position.c = max(-75, min(75, calculated_angle))  # Clamp to limits
        else:
            position.c = manual_servo_angle
            
        self._position.update({
            'x': position.x, 
            'y': position.y, 
            'z': position.z, 
            'rotation': position.c
        })
        return True
        
    def get_servo_tilt_info(self) -> Dict[str, Any]:
        """Mock servo tilt info for testing"""
        return {
            "enabled": True,
            "mode": "mock",
            "last_angle": self._position.get('rotation', 0.0),
            "configuration": {
                "camera_offset": {"x": -10.0, "y": 20.0},
                "turntable_offset": {"x": 30.0, "y": -10.0},
                "angle_limits": {"min": -75.0, "max": 75.0}
            }
        }
        
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
        
    async def capture_high_resolution(self, camera_id, settings=None):
        """Mock high resolution capture"""
        import numpy as np
        await asyncio.sleep(0.5)  # Simulate capture time
        
        # Return mock image data (simulated 4K image)
        mock_image = np.zeros((2592, 4608, 3), dtype=np.uint8)
        mock_image.fill(128)  # Gray image
        return mock_image
    
    async def capture_both_cameras_simultaneously(self, settings=None):
        """Mock simultaneous capture for both cameras"""
        import numpy as np
        await asyncio.sleep(0.8)  # Simulate simultaneous capture time
        
        # Return mock images for both cameras
        mock_image_0 = np.zeros((2592, 4608, 3), dtype=np.uint8)
        mock_image_0.fill(100)  # Darker gray for camera 0
        
        mock_image_1 = np.zeros((2592, 4608, 3), dtype=np.uint8)
        mock_image_1.fill(150)  # Lighter gray for camera 1
        
        return {
            'camera_0': mock_image_0,
            'camera_1': mock_image_1
        }
        
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
            'cameras': ['camera_0', 'camera_1'],
            'active_cameras': ['camera_0', 'camera_1'] if self._initialized else [],
            'initialized': self._initialized
        }
    
    async def apply_quality_settings(self, quality_settings):
        """Mock quality settings application"""
        logger = logging.getLogger(__name__)
        logger.info(f"MOCK CAMERA: Applied quality settings: {quality_settings}")
        return True

class MockLightingController:
    """Mock lighting controller for testing"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._initialized = False
        self._zones = ['inner', 'outer']  # Mock zones matching GPIO config
        
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
        
    async def trigger_for_capture(self, camera_controller, zone_ids: List[str], settings: Any) -> Any:
        """Mock synchronized flash-capture method"""
        await asyncio.sleep(0.05)  # Simulate LED rise time (increased to match real controller)
        
        # Mock camera capture during flash
        camera_result = None
        if hasattr(camera_controller, 'capture_both_cameras_simultaneously'):
            try:
                camera_result = await camera_controller.capture_both_cameras_simultaneously()
            except Exception:
                pass
        
        # Return mock flash result with camera data
        flash_result = {
            'success': True,
            'zones_activated': zone_ids,
            'actual_brightness': {zone_id: 0.8 for zone_id in zone_ids},
            'duration_ms': 150,
            'timestamp': time.time()
        }
        
        # Add camera result to flash result
        if hasattr(flash_result, '__dict__'):
            flash_result['camera_result'] = camera_result
        
        return flash_result
        
    async def turn_off_all(self) -> bool:
        return True
        
    async def get_status(self, zone_id: Optional[str] = None) -> Any:
        if zone_id:
            return "ready" if self._initialized else "disconnected"
        else:
            return {zone_id: "ready" if self._initialized else "disconnected" 
                   for zone_id in self._zones}

class MockStorageManager:
    """Mock storage manager for testing - now saves files to disk!"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self._initialized = False
        self._sessions = {}
        self._current_session_id = None
        
        # Create output directory for saved files
        from pathlib import Path
        self.base_dir = Path("scan_images")
        self.base_dir.mkdir(exist_ok=True)
        
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
        
        # 💾 ACTUALLY SAVE THE FILE TO DISK!
        try:
            if self._current_session_id:
                session_dir = self.base_dir / self._current_session_id
                session_dir.mkdir(exist_ok=True)
                
                # Create filename from metadata
                camera_id = metadata.get('camera_id', 'unknown')
                point_index = metadata.get('point_index', 0)
                timestamp = metadata.get('timestamp', time.time())
                
                filename = f"{camera_id}_point_{point_index:03d}_{int(timestamp)}.jpg"
                file_path = session_dir / filename
                
                # Save the image file
                with open(file_path, 'wb') as f:
                    f.write(file_data)
                
                print(f"✅ SAVED IMAGE: {file_path}")  # Console output for immediate feedback
                
                # Store metadata
                metadata_file = session_dir / f"{filename}.json"
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f, indent=2, default=str)
                
        except Exception as e:
            print(f"❌ FAILED to save file: {e}")
        
        if self._current_session_id and self._current_session_id in self._sessions:
            self._sessions[self._current_session_id]['files'].append({
                'file_id': file_id,
                'size': len(file_data),
                'metadata': metadata,
                'file_path': str(file_path) if 'file_path' in locals() else None
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
    
    async def clear_alarm(self) -> bool:
        """Clear alarm state using $X command"""
        try:
            self.logger.info("🔓 ScanOrchestrator: Clearing alarm state")
            
            # Check if motion controller has clear_alarm method
            if hasattr(self.controller, 'clear_alarm'):
                result = await self.controller.clear_alarm()
                if result:
                    self.logger.info("✅ ScanOrchestrator: Alarm cleared successfully")
                else:
                    self.logger.error("❌ ScanOrchestrator: Failed to clear alarm")
                return result
            else:
                self.logger.error("❌ ScanOrchestrator: Motion controller does not support clear_alarm")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ ScanOrchestrator clear_alarm error: {e}")
            return False
    
    def clear_alarm_sync(self) -> bool:
        """Synchronous wrapper for clearing alarm state"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.clear_alarm())
            loop.close()
            return result
        except Exception as e:
            self.logger.error(f"❌ ScanOrchestrator sync clear_alarm error: {e}")
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
        self._is_capturing = False  # More specific flag for active capture moments
        
        # Picamera2 dual-configuration system
        self._stream_configs = {}     # 1080p streaming configurations per camera
        self._capture_configs = {}    # High-res capture configurations per camera
        self._current_mode = "streaming"  # Current camera mode
        
        # Performance and resource management
        self._camera_instances = {}   # Store camera instances for each mode
        self._last_mode_switch = 0
        self._mode_switch_cooldown = 1.0  # Minimum seconds between mode switches
        
        # Camera resource locking (simplified for dual-mode)
        import threading
        self._mode_lock = threading.Lock()  # Lock for mode switching
        # Initialize per-camera locks for simultaneous capture (will be created later)
        self._capture_locks = {}
        
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
                # Load camera resolution from configuration
                await self._load_camera_configuration()
                
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
            
    async def _load_camera_configuration(self):
        """Load camera configuration from YAML file"""
        try:
            # Check if custom quality settings are already applied and preserve their resolution
            existing_custom_resolution = None
            if hasattr(self, '_quality_settings') and 'resolution' in self._quality_settings:
                existing_custom_resolution = self._quality_settings['resolution']
                self.logger.info(f"CAMERA: Found existing custom resolution: {existing_custom_resolution}")
            
            # Load resolution from camera configuration only if no custom settings exist
            if existing_custom_resolution:
                capture_resolution = existing_custom_resolution
                self.logger.info(f"CAMERA: Preserving custom resolution: {capture_resolution}")
            else:
                camera_1_config = self.config_manager.get('cameras.camera_1', {})
                if camera_1_config and 'resolution' in camera_1_config:
                    resolution_config = camera_1_config['resolution']
                    # Handle both dict format (resolution.capture) and list format ([width, height])
                    if isinstance(resolution_config, dict):
                        capture_resolution = resolution_config.get('capture', [3280, 2464])
                    elif isinstance(resolution_config, list):
                        capture_resolution = resolution_config
                    else:
                        capture_resolution = [3280, 2464]
                    self.logger.info(f"CAMERA: Loaded capture resolution from config: {capture_resolution}")
                else:
                    capture_resolution = [3280, 2464]  # Default from YAML
                    self.logger.info(f"CAMERA: Using default capture resolution: {capture_resolution}")
            
            # Initialize or preserve quality settings
            if hasattr(self, '_quality_settings') and self._quality_settings:
                # Preserve existing custom quality settings, only update resolution if needed
                if 'resolution' not in self._quality_settings or not self._quality_settings['resolution']:
                    self._quality_settings['resolution'] = capture_resolution
                    self.logger.info(f"CAMERA: Updated existing quality settings with resolution: {capture_resolution}")
                else:
                    self.logger.info(f"CAMERA: Preserving existing quality settings including resolution: {self._quality_settings['resolution']}")
            else:
                # Initialize quality settings with resolution from config/defaults
                self._quality_settings = {
                    'jpeg_quality': 95,  # Default high quality
                    'color_format': 'BGR',
                    'compression_level': 1,
                    'resolution': capture_resolution
                }
                self.logger.info(f"CAMERA: Initialized new quality settings with resolution: {capture_resolution}")
            
            self.logger.info(f"CAMERA: Configuration loaded - final resolution: {self._quality_settings.get('resolution', capture_resolution)}")
            
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to load camera configuration: {e}")
            # Set safe defaults
            self._quality_settings = {
                'jpeg_quality': 95,
                'color_format': 'BGR', 
                'compression_level': 1,
                'resolution': [3280, 2464]
            }
    
    async def _setup_dual_mode_configurations(self):
        """Setup optimized camera configurations for streaming and capture"""
        try:
            # Configure BOTH cameras for dual-mode operation
            for camera_id in [0, 1]:
                if hasattr(self.controller, 'cameras') and camera_id in self.controller.cameras:
                    camera = self.controller.cameras[camera_id]
                    
                    if camera:
                        # OPTIMAL: Keep 1080p 16:9 for smooth livestream as requested
                        stream_config = camera.create_video_configuration(
                            main={"size": (1920, 1080), "format": "RGB888"},  # Keep 1080p for livestream
                            lores={"size": (640, 480), "format": "YUV420"},  # Thumbnail for processing
                            display="lores"  # Use low-res for display efficiency
                        )
                        
                        # OPTIMIZED SINGLE-STREAM: Use configured resolution from YAML
                        config_resolution = tuple(self._quality_settings['resolution']) if hasattr(self, '_quality_settings') else (3280, 2464)
                        capture_config = camera.create_still_configuration(
                            main={"size": config_resolution, "format": "RGB888"},  # Use configured resolution
                            raw=None,  # Explicitly disable RAW to prevent ISP buffer queue errors
                            buffer_count=1  # Minimal buffer allocation for still photos
                        )
                        self.logger.info(f"CAMERA: Camera {camera_id} capture config set to {config_resolution}")
                        
                        # Store configurations per camera
                        if not hasattr(self, '_stream_configs'):
                            self._stream_configs = {}
                            self._capture_configs = {}
                        
                        self._stream_configs[camera_id] = stream_config
                        self._capture_configs[camera_id] = capture_config
                        
                        self.logger.info(f"CAMERA: Camera {camera_id} configured for dual-mode operation")
            
            # Start camera 0 in streaming mode initially
            if hasattr(self.controller, 'cameras') and 0 in self.controller.cameras:
                camera = self.controller.cameras[0]
                if camera and 0 in self._stream_configs:
                    camera.configure(self._stream_configs[0])
                    camera.start()
                    self.logger.info("CAMERA: Camera 0 started in streaming mode")
            
            self._current_mode = "streaming"
            self.logger.info("CAMERA: OPTIMAL CONFIGURATION - RGB888 native output provides perfect colors")
                    
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to setup dual-mode configurations: {e}")
    
    async def _switch_camera_mode(self, target_mode: str):
        """Efficiently switch between streaming and capture modes"""
        with self._mode_lock:
            if self._current_mode == target_mode:
                return True  # Already in target mode
            
            current_time = time.time()
            if (current_time - self._last_mode_switch) < self._mode_switch_cooldown:
                await asyncio.sleep(self._mode_switch_cooldown - (current_time - self._last_mode_switch))
            
            try:
                if target_mode == "streaming":
                    # Check if we're in an active scan - preserve exposure settings if so
                    in_active_scan = False
                    if hasattr(self, 'current_scan') and self.current_scan:
                        scan_status = self.current_scan.status
                        in_active_scan = scan_status.value in ['running', 'paused']
                    
                    # Stop and reconfigure camera 0 for streaming
                    if hasattr(self.controller, 'cameras') and 0 in self.controller.cameras:
                        camera = self.controller.cameras[0]
                        if camera:
                            # Store calibrated settings if in scan mode
                            calibrated_settings = None
                            if (in_active_scan and hasattr(self.controller, '_calibrated_settings') and 
                                0 in self.controller._calibrated_settings):
                                calibrated_settings = self.controller._calibrated_settings[0]
                                self.logger.info("🔄 Camera 0: Preserving calibrated settings during scan livestream switch")
                            
                            camera.stop()
                            if hasattr(self, '_stream_configs') and 0 in self._stream_configs:
                                camera.configure(self._stream_configs[0])
                            else:
                                # Fallback configuration - keep 1080p for livestream
                                config = camera.create_video_configuration(
                                    main={"size": (1920, 1080), "format": "RGB888"}  # Keep 1080p
                                )
                                camera.configure(config)
                            camera.start()
                            
                            # Reapply calibrated settings during active scan
                            if calibrated_settings:
                                restore_controls = {
                                    'AeEnable': False,  # Keep auto-exposure disabled during scan
                                    'ExposureTime': calibrated_settings['exposure_time'],
                                    'AnalogueGain': calibrated_settings['analogue_gain']
                                }
                                camera.set_controls(restore_controls)
                                self.logger.info(f"🎯 Camera 0: Maintained calibrated exposure during livestream: "
                                               f"{calibrated_settings['exposure_time']}μs, gain: {calibrated_settings['analogue_gain']:.2f}")
                            else:
                                # Only enable auto-exposure when NOT in scan mode
                                camera.set_controls({
                                    'AeEnable': True,   # Enable auto-exposure for normal livestream
                                    'AwbEnable': True   # Enable auto white balance
                                })
                                self.logger.debug("Camera 0: Auto-exposure enabled for normal livestream")
                            
                            self.logger.info("CAMERA: Switched to streaming mode")
                    
                elif target_mode == "capture":
                    # Stop and reconfigure BOTH cameras for high-res capture
                    for camera_id in [0, 1]:
                        if hasattr(self.controller, 'cameras') and camera_id in self.controller.cameras:
                            camera = self.controller.cameras[camera_id]
                            if camera:
                                try:
                                    # Store calibrated settings before camera restart (CRITICAL FIX)
                                    calibrated_settings = None
                                    if (hasattr(self.controller, '_calibrated_settings') and 
                                        camera_id in self.controller._calibrated_settings):
                                        calibrated_settings = self.controller._calibrated_settings[camera_id]
                                        self.logger.info(f"🔄 Camera {camera_id}: Preserving calibrated exposure settings during mode switch")
                                    
                                    # Always stop camera before reconfiguring (fix for "Camera must be stopped" error)
                                    camera.stop()
                                    self.logger.debug(f"CAMERA: Stopped camera {camera_id} before reconfiguration")
                                    
                                    # Enhanced ISP buffer cleanup after camera stop
                                    import gc
                                    gc.collect()  # Force garbage collection to release ISP buffers
                                    
                                    # Extended delay to ensure complete buffer release and ISP pipeline reset
                                    await asyncio.sleep(0.3)
                                    
                                    # Configure for capture
                                    if hasattr(self, '_capture_configs') and camera_id in self._capture_configs:
                                        camera.configure(self._capture_configs[camera_id])
                                    else:
                                        # Optimized single-stream fallback with minimal memory
                                        config = camera.create_still_configuration(
                                            main={"size": (9152, 6944), "format": "RGB888"},
                                            raw=None,  # Prevent automatic RAW stream addition
                                            buffer_count=1  # Minimal buffer allocation
                                        )
                                        camera.configure(config)
                                    
                                    camera.start()
                                    
                                    # CRITICAL: Restore calibrated settings from backup if needed, then apply
                                    if hasattr(self.controller, 'restore_calibrated_settings_if_lost'):
                                        await self.controller.restore_calibrated_settings_if_lost()
                                    
                                    # Check again if calibrated settings are available after potential restore
                                    if (hasattr(self.controller, '_calibrated_settings') and 
                                        camera_id in self.controller._calibrated_settings):
                                        calibrated_settings = self.controller._calibrated_settings[camera_id]
                                    
                                    if calibrated_settings:
                                        # Apply with extra force after camera restart
                                        restore_controls = {
                                            'AeEnable': False,  # Disable auto-exposure
                                            'AwbEnable': False, # Disable auto white balance
                                            'ExposureTime': calibrated_settings['exposure_time'],
                                            'AnalogueGain': calibrated_settings['analogue_gain']
                                        }
                                        camera.set_controls(restore_controls)
                                        
                                        # Wait extra time for settings to stick after camera restart
                                        await asyncio.sleep(0.2)
                                        
                                        # Mark as locked
                                        if 'locked' in calibrated_settings:
                                            calibrated_settings['locked'] = True
                                        
                                        self.logger.info(f"🔐 Camera {camera_id}: LOCKED calibrated exposure after restart: "
                                                       f"{calibrated_settings['exposure_time']}μs, gain: {calibrated_settings['analogue_gain']:.2f}")
                                    
                                    self.logger.info(f"CAMERA: Camera {camera_id} switched to capture mode")
                                    
                                except Exception as camera_error:
                                    self.logger.error(f"CAMERA: Failed to switch camera {camera_id} to capture mode: {camera_error}")
                                    raise
                    
                    self.logger.info("CAMERA: Switched to capture mode")
                
                self._current_mode = target_mode
                self._last_mode_switch = time.time()
                return True
                
            except Exception as e:
                self.logger.error(f"CAMERA: Mode switch to {target_mode} failed: {e}")
                # Try to recover to streaming mode
                if target_mode != "streaming":
                    await self._switch_camera_mode("streaming")
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
                    
                    # Encode and save with custom quality settings
                    import cv2
                    
                    # Use stored quality settings or default
                    jpeg_quality = 95  # Default high quality
                    if hasattr(self, '_quality_settings') and self._quality_settings:
                        jpeg_quality = self._quality_settings.get('jpeg_quality', 95)
                    
                    self.logger.info(f"CAMERA: Saving image with JPEG quality: {jpeg_quality}")
                    success = cv2.imwrite(str(output_path), high_res_image, [
                        cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality),
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
            
            # Support both Camera 0 and Camera 1 using physical IDs
            if camera_id not in [0, 1, '0', '1', 'camera_0', 'camera_1']:
                return None
            
            # Map camera ID to physical camera index
            mapped_camera_id = 0  # Default to camera 0
            if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                try:
                    mapped_camera_id = int(camera_id.split('_')[1])  # camera_0 -> 0, camera_1 -> 1
                except (ValueError, IndexError):
                    return None
            elif isinstance(camera_id, (int, str)):
                mapped_camera_id = int(camera_id)
            
            # Rate-limited debug logging
            if not hasattr(self, '_last_debug_log') or (current_time - self._last_debug_log) > 20.0:
                self.logger.info(f"CAMERA: Native preview frame requested for {camera_id} -> camera {mapped_camera_id}")
                self._last_debug_log = current_time
            if hasattr(self.controller, 'cameras') and mapped_camera_id in self.controller.cameras:
                camera = self.controller.cameras[mapped_camera_id]
                
                if camera and hasattr(camera, 'capture_array'):
                    try:
                        # CRITICAL: Don't switch camera modes during active capture moments
                        # This prevents the live stream from interfering with scan capture resolution
                        # but allows live stream to work normally during scan movements/preparation
                        if self._is_capturing:
                            # During active capture, use the camera in its current mode without switching
                            # This preserves the high-resolution capture configuration
                            self.logger.debug(f"CAMERA: Active capture in progress - using current mode for preview (no mode switch)")
                        elif self._current_mode != "streaming":
                            # Only switch to streaming mode when NOT actively capturing
                            # This allows live stream during scan movements/preparation but prevents interference during captures
                            # Run the async mode switch in a new event loop for sync method
                            try:
                                import asyncio
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                loop.run_until_complete(self._switch_camera_mode("streaming"))
                                loop.close()
                            except Exception as mode_switch_error:
                                self.logger.warning(f"CAMERA: Mode switch failed: {mode_switch_error}")
                            time.sleep(0.1)  # Brief wait for mode switch
                        
                        # Use Picamera2's native capture with streaming-optimized config
                        # This gets the main stream directly but needs format handling
                        frame_array = camera.capture_array("main")
                        
                        if frame_array is not None and frame_array.size > 0:
                            # Handle the actual format returned by the camera
                            self.logger.info(f"CAMERA: Raw frame captured: {frame_array.shape}, dtype: {frame_array.dtype}")
                            
                            if len(frame_array.shape) == 3:
                                if frame_array.shape[2] == 4:
                                    # XBGR8888 format (4 channels) - camera is in streaming mode
                                    frame_bgr = frame_array[:, :, :3]  # Take first 3 channels (BGR)
                                    self.logger.info(f"CAMERA: Converted XBGR8888 to BGR: {frame_bgr.shape}")
                                elif frame_array.shape[2] == 3:
                                    # RGB888 format (3 channels) - check if conversion is needed
                                    # Picamera2 typically outputs RGB, but let's test if colors look correct
                                    if not hasattr(self, '_color_test_done'):
                                        # Test frame: if it's already BGR, don't convert; if RGB, convert
                                        # For now, assume it's RGB and needs conversion to BGR
                                        frame_bgr = frame_array.copy()  # Try using directly first
                                        self.logger.info(f"CAMERA: Using RGB888 frame directly (no conversion): {frame_bgr.shape}")
                                        self._color_test_done = True
                                    else:
                                        # Use the frame directly without conversion for now
                                        frame_bgr = frame_array.copy()
                                else:
                                    # Other channel counts - use as is
                                    frame_bgr = frame_array.copy()
                                    self.logger.info(f"CAMERA: Using raw format: {frame_bgr.shape}")
                            else:
                                # Grayscale or other formats
                                frame_bgr = frame_array.copy()
                                self.logger.info(f"CAMERA: Using grayscale/raw format: {frame_bgr.shape}")
                                
                            # Optional: Apply minimal enhancement for better web display
                            # Only if the frame appears too dark/flat
                            try:
                                mean_brightness = np.mean(frame_bgr)
                                if mean_brightness < 80:  # Dark frame
                                    frame_bgr = cv2.convertScaleAbs(frame_bgr, alpha=1.2, beta=15)
                            except Exception as enhance_error:
                                self.logger.debug(f"CAMERA: Enhancement skipped: {enhance_error}")
                            
                            # Performance logging
                            if not hasattr(self, '_last_success_log') or (current_time - self._last_success_log) > 20.0:
                                self.logger.info(f"CAMERA: Native frame processed: {frame_bgr.shape}, dtype: {frame_bgr.dtype}")
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
        # Map camera ID to physical camera index first
        mapped_camera_id = 0  # Default to camera 0
        if isinstance(camera_id, str) and camera_id.startswith('camera_'):
            try:
                mapped_camera_id = int(camera_id.split('_')[1])  # camera_0 -> 0, camera_1 -> 1
            except (ValueError, IndexError):
                return None
        elif isinstance(camera_id, (int, str)):
            mapped_camera_id = int(camera_id)
        
        # Validate camera ID is within valid range (0 or 1)
        if mapped_camera_id not in [0, 1]:
            self.logger.warning(f"CAMERA: Invalid camera ID {mapped_camera_id} (from {camera_id})")
            return None
        
        try:
            # Create async lock for this camera if it doesn't exist
            if mapped_camera_id not in self._capture_locks:
                self._capture_locks[mapped_camera_id] = asyncio.Lock()
            
            # For simultaneous capture, ensure cameras are in capture mode
            # Mode switching should happen before calling capture_high_resolution
            # so we don't need to do it here for each camera individually
            
            # Use per-camera async lock to allow simultaneous capture
            async with self._capture_locks[mapped_camera_id]:
                
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
                        self.logger.info(f"CAMERA: Capturing high-resolution image (4K+) from physical camera {mapped_camera_id}")
                        
                        # Use still capture for maximum quality with timeout
                        try:
                            self.logger.info(f"CAMERA: Starting capture for camera {mapped_camera_id} ({camera_id})")
                            image_array = camera.capture_array("main")
                            
                            if image_array is not None and image_array.size > 0:
                                # OPTIMAL: Use camera RGB888 output directly for high-res captures
                                image_bgr = image_array.copy()  # Direct use - optimal performance
                                
                                # No conversions needed - camera provides perfect format
                                self.logger.info(f"CAMERA: High-res capture successful for {camera_id}: {image_bgr.shape}, dtype: {image_bgr.dtype}")
                                
                                # Ensure mode switch back to streaming after successful capture
                                await self._switch_camera_mode("streaming")
                                return image_bgr
                            else:
                                self.logger.error(f"CAMERA: High-res capture returned empty array for {camera_id}")
                                
                        except Exception as capture_error:
                            self.logger.error(f"CAMERA: Capture array failed for {camera_id}: {capture_error}")
                            raise  # Re-raise to trigger outer exception handling
                            
                    else:
                        self.logger.error(f"CAMERA: Camera {mapped_camera_id} not available or missing capture method")
                else:
                    self.logger.error(f"CAMERA: Camera system not properly initialized for {camera_id}")
                    
                # Always try to switch back to streaming mode
                await self._switch_camera_mode("streaming")
                
        except Exception as e:
            self.logger.error(f"CAMERA: High-resolution capture failed: {e}")
            # Ensure we switch back to streaming mode on error
            try:
                await self._switch_camera_mode("streaming")
            except:
                pass
                
        return None
    
    async def capture_both_cameras_simultaneously(self, settings=None):
        """
        Capture from both cameras simultaneously for optimal dual-camera performance
        
        Args:
            settings: Optional camera settings
            
        Returns:
            Dict: Results from both cameras {'camera_0': image_array, 'camera_1': image_array}
        """
        results = {}
        
        try:
            # Set capturing flag to prevent live stream interference during capture
            self._is_capturing = True
            
            # Switch to capture mode ONCE for both cameras
            await self._switch_camera_mode("capture")
            self.logger.info("CAMERA: Both cameras prepared for simultaneous capture")
            
            # Simplified fallback capture function (ISP methods are preferred)
            async def capture_camera_direct(camera_id: str, mapped_id: int):
                """Simplified fallback camera capture"""
                try:
                    # Use camera controller's ISP-aware capture if available
                    if hasattr(self.controller, 'capture_with_isp_management'):
                        image_array = await self.controller.capture_with_isp_management(mapped_id, "main")
                        
                        if image_array is not None:
                            import cv2
                            if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                                image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                            else:
                                image_bgr = image_array.copy()
                            
                            self.logger.info(f"CAMERA: Fallback ISP capture successful for {camera_id}: {image_bgr.shape}")
                            return {'image': image_bgr, 'metadata': {}}
                    
                    # Original direct access fallback
                    if hasattr(self.controller, 'cameras') and mapped_id in self.controller.cameras:
                        camera = self.controller.cameras[mapped_id]
                        
                        if camera and hasattr(camera, 'capture_array'):
                            # Apply calibrated exposure settings if available (scan mode)
                            calibrated_applied = False
                            if (hasattr(self.controller, '_calibrated_settings') and 
                                mapped_id in self.controller._calibrated_settings):
                                
                                calibrated = self.controller._calibrated_settings[mapped_id]
                                
                                # ROBUST EXPOSURE LOCK: Apply settings multiple times with verification
                                for attempt in range(3):  # Try up to 3 times to ensure settings stick
                                    calibrated_controls = {
                                        'AeEnable': False,  # Disable auto-exposure FIRST
                                        'AwbEnable': False, # Also disable auto white balance to prevent drift
                                        'ExposureTime': calibrated['exposure_time'],
                                        'AnalogueGain': calibrated['analogue_gain']
                                    }
                                    camera.set_controls(calibrated_controls)
                                    
                                    # Wait for settings to take effect
                                    import time
                                    time.sleep(0.15)  # Increased delay for Pi hardware
                                    
                                    # Verify settings actually took
                                    try:
                                        metadata_check = camera.capture_metadata()
                                        actual_exposure = metadata_check.get('ExposureTime', 0)
                                        actual_gain = metadata_check.get('AnalogueGain', 0)
                                        
                                        # Check if settings are close enough (within 10%)
                                        exposure_ok = abs(actual_exposure - calibrated['exposure_time']) < (calibrated['exposure_time'] * 0.1)
                                        gain_ok = abs(actual_gain - calibrated['analogue_gain']) < (calibrated['analogue_gain'] * 0.1)
                                        
                                        if exposure_ok and gain_ok:
                                            self.logger.info(f"✅ Camera {camera_id} scan settings LOCKED (attempt {attempt+1}): "
                                                           f"target={calibrated['exposure_time']}μs/{calibrated['analogue_gain']:.2f}, "
                                                           f"actual={actual_exposure}μs/{actual_gain:.2f}")
                                            calibrated_applied = True
                                            break
                                        else:
                                            self.logger.warning(f"⚠️ Camera {camera_id} settings mismatch (attempt {attempt+1}): "
                                                              f"target={calibrated['exposure_time']}μs/{calibrated['analogue_gain']:.2f}, "
                                                              f"actual={actual_exposure}μs/{actual_gain:.2f}")
                                    
                                    except Exception as verify_error:
                                        self.logger.warning(f"⚠️ Camera {camera_id} settings verification failed (attempt {attempt+1}): {verify_error}")
                                
                                if not calibrated_applied:
                                    self.logger.error(f"🚨 Camera {camera_id} FAILED to lock calibrated settings after 3 attempts!")
                                else:
                                    # Final verification before capture
                                    final_metadata = camera.capture_metadata()
                                    self.logger.info(f"🔒 Camera {camera_id} FINAL verification before capture: "
                                                   f"exposure={final_metadata.get('ExposureTime', 0)}μs, "
                                                   f"gain={final_metadata.get('AnalogueGain', 0):.2f}")
                                
                                calibrated_applied = True
                            
                            # Apply custom settings if provided (do this quickly)
                            if settings and not calibrated_applied:
                                controls = {}
                                if hasattr(settings, 'exposure_time') and settings.exposure_time:
                                    controls['ExposureTime'] = int(settings.exposure_time * 1000000)
                                if hasattr(settings, 'iso') and settings.iso:
                                    controls['AnalogueGain'] = settings.iso / 100.0
                                
                                if controls:
                                    camera.set_controls(controls)
                            
                            # CRITICAL: Final settings lock immediately before capture
                            if (hasattr(self.controller, '_calibrated_settings') and 
                                mapped_id in self.controller._calibrated_settings and calibrated_applied):
                                calibrated = self.controller._calibrated_settings[mapped_id]
                                
                                # Double-check exposure lock is still active
                                pre_capture_metadata = camera.capture_metadata()
                                current_exposure = pre_capture_metadata.get('ExposureTime', 0)
                                current_gain = pre_capture_metadata.get('AnalogueGain', 0)
                                
                                # If settings have drifted, reapply them with force
                                exposure_drift = abs(current_exposure - calibrated['exposure_time']) > (calibrated['exposure_time'] * 0.05)
                                gain_drift = abs(current_gain - calibrated['analogue_gain']) > (calibrated['analogue_gain'] * 0.05)
                                
                                if exposure_drift or gain_drift:
                                    self.logger.warning(f"🚨 Camera {camera_id} DRIFT detected before capture! "
                                                      f"Expected: {calibrated['exposure_time']}μs/{calibrated['analogue_gain']:.2f}, "
                                                      f"Actual: {current_exposure}μs/{current_gain:.2f}")
                                    
                                    # Force reapply settings
                                    final_controls = {
                                        'AeEnable': False,  # Force auto-exposure OFF
                                        'AwbEnable': False, # Force auto-white-balance OFF
                                        'ExposureTime': calibrated['exposure_time'],
                                        'AnalogueGain': calibrated['analogue_gain']
                                    }
                                    camera.set_controls(final_controls)
                                    time.sleep(0.1)  # Allow settings to apply
                                    
                                    # Verify correction
                                    corrected_metadata = camera.capture_metadata()
                                    self.logger.info(f"� Camera {camera_id} drift corrected: "
                                                   f"new={corrected_metadata.get('ExposureTime', 0)}μs/"
                                                   f"{corrected_metadata.get('AnalogueGain', 0):.2f}")
                                else:
                                    self.logger.debug(f"✅ Camera {camera_id} exposure stable before capture: "
                                                    f"{current_exposure}μs/{current_gain:.2f}")
                            
                            # Start capture immediately without waiting for other camera
                            self.logger.info(f"CAMERA: Starting simultaneous capture for camera {mapped_id} ({camera_id})")
                            
                            # Use asyncio to run the blocking capture with metadata collection
                            import asyncio
                            import concurrent.futures
                            
                            def capture_with_metadata(camera_obj):
                                """Capture image and return both image and metadata with ISP buffer management"""
                                try:
                                    # ISP Buffer Management: Clear any existing buffers before capture
                                    import gc
                                    import time
                                    
                                    # Force garbage collection to free memory before capture
                                    gc.collect()
                                    
                                    # Small delay to ensure ISP pipeline is ready
                                    time.sleep(0.05)
                                    
                                    # In Picamera2, metadata is often available during/after capture
                                    # First capture the image with buffer management
                                    image_array = camera_obj.capture_array("main")
                                    
                                    # Immediately clear any internal buffers after capture
                                    gc.collect()
                                    
                                    # Then try to get metadata immediately after capture
                                    metadata = {}
                                    
                                    # Try different ways to get metadata from Picamera2
                                    if hasattr(camera_obj, 'capture_metadata'):
                                        try:
                                            if callable(camera_obj.capture_metadata):
                                                metadata.update(camera_obj.capture_metadata())
                                            else:
                                                metadata.update(camera_obj.capture_metadata)
                                        except:
                                            pass
                                    
                                    # Try to get current controls as metadata
                                    if hasattr(camera_obj, 'controls') and hasattr(camera_obj.controls, 'keys'):
                                        try:
                                            metadata.update({'controls': dict(camera_obj.controls)})
                                        except:
                                            pass
                                    
                                    return image_array, metadata
                                    
                                except Exception as e:
                                    self.logger.error(f"Capture with metadata failed: {e}")
                                    return None, {}
                            
                            loop = asyncio.get_event_loop()
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                # Run capture with metadata collection in thread pool
                                image_array, capture_metadata = await loop.run_in_executor(executor, capture_with_metadata, camera)
            
                            if image_array is not None and image_array.size > 0:
                                # Handle different camera formats properly
                                import cv2
                                self.logger.info(f"CAMERA: Raw capture shape for {camera_id}: {image_array.shape}")
                                
                                if len(image_array.shape) == 3:
                                    if image_array.shape[2] == 4:
                                        # XBGR8888 format (4 channels) - convert to BGR by dropping alpha
                                        image_bgr = image_array[:, :, :3]  # Take first 3 channels (BGR)
                                        self.logger.info(f"CAMERA: Converted XBGR8888 to BGR for {camera_id}")
                                    elif image_array.shape[2] == 3:
                                        # RGB format (3 channels) - convert to BGR
                                        image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                                        self.logger.info(f"CAMERA: Converted RGB to BGR for {camera_id}")
                                    else:
                                        # Other formats - use as is
                                        image_bgr = image_array.copy()
                                        self.logger.info(f"CAMERA: Using raw format for {camera_id}")
                                else:
                                    # Grayscale or other formats
                                    image_bgr = image_array.copy()
                                    self.logger.info(f"CAMERA: Using grayscale/raw format for {camera_id}")
                                
                                # Log captured metadata
                                if capture_metadata and isinstance(capture_metadata, dict):
                                    self.logger.info(f"CAMERA: Captured metadata for {camera_id}: {list(capture_metadata.keys())}")
                                else:
                                    self.logger.info(f"CAMERA: No metadata captured for {camera_id}")
                                    capture_metadata = {}
                                
                                self.logger.info(f"CAMERA: Simultaneous capture successful for {camera_id}: {image_bgr.shape}")
                                return {'image': image_bgr, 'metadata': capture_metadata}
                            else:
                                self.logger.error(f"CAMERA: Simultaneous capture returned empty array for {camera_id}")
                                return None
                    
                except Exception as e:
                    # Check for specific ISP buffer errors
                    error_msg = str(e).lower()
                    if any(keyword in error_msg for keyword in ['buffer', 'isp', 'queue', 'v4l2', 'enomem']):
                        self.logger.error(f"CAMERA: ISP buffer error for {camera_id}: {e}")
                        self.logger.info(f"CAMERA: Attempting buffer recovery for {camera_id}...")
                        
                        # Force garbage collection and retry once
                        import gc
                        import time
                        gc.collect()
                        time.sleep(0.2)  # Allow ISP buffers to clear
                        
                        try:
                            # Retry capture with buffer management
                            if hasattr(self.controller, 'cameras') and mapped_id in self.controller.cameras:
                                camera = self.controller.cameras[mapped_id]
                                if camera and hasattr(camera, 'capture_array'):
                                    self.logger.info(f"CAMERA: Retry capture for {camera_id} after buffer recovery")
                                    image_array = camera.capture_array("main")
                                    if image_array is not None and image_array.size > 0:
                                        import cv2
                                        self.logger.info(f"CAMERA: Retry capture shape for {camera_id}: {image_array.shape}")
                                        
                                        if len(image_array.shape) == 3:
                                            if image_array.shape[2] == 4:
                                                # XBGR8888 format (4 channels) - convert to BGR by dropping alpha
                                                image_bgr = image_array[:, :, :3]  # Take first 3 channels (BGR)
                                                self.logger.info(f"CAMERA: Retry converted XBGR8888 to BGR for {camera_id}")
                                            elif image_array.shape[2] == 3:
                                                # RGB format (3 channels) - convert to BGR
                                                image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                                                self.logger.info(f"CAMERA: Retry converted RGB to BGR for {camera_id}")
                                            else:
                                                # Other formats - use as is
                                                image_bgr = image_array.copy()
                                        else:
                                            # Grayscale or other formats
                                            image_bgr = image_array.copy()
                                        
                                        self.logger.info(f"CAMERA: Buffer recovery successful for {camera_id}: {image_bgr.shape}")
                                        return {'image': image_bgr, 'metadata': {}}
                        except Exception as retry_error:
                            self.logger.error(f"CAMERA: Buffer recovery failed for {camera_id}: {retry_error}")
                    else:
                        self.logger.error(f"CAMERA: General capture error for {camera_id}: {e}")
                    
                    return None
                
                except Exception as e:
                    self.logger.error(f"CAMERA: Capture failed for {camera_id}: {e}")
                    return None
            
            # Use camera controller's resolution-aware ISP capture system
            self.logger.info("CAMERA: Using resolution-aware ISP-managed dual camera capture...")
            
            # Determine target resolution - RESPECT current camera configuration first
            target_resolution = None
            try:
                # PRIMARY: Check current camera configuration (already set resolution)
                if hasattr(self.controller, 'cameras'):
                    for camera_id in [0, 1]:
                        if camera_id in self.controller.cameras:
                            camera = self.controller.cameras[camera_id]
                            if camera and hasattr(camera, 'camera_configuration'):
                                try:
                                    config = camera.camera_configuration
                                    if config and 'main' in config:
                                        current_size = config['main'].get('size')
                                        if current_size:
                                            target_resolution = current_size
                                            self.logger.info(f"CAMERA: Respecting current camera configuration: {target_resolution}")
                                            break
                                except Exception:
                                    continue
                
                # SECONDARY: Try quality settings if no current config found
                if target_resolution is None and hasattr(self, '_quality_settings') and self._quality_settings:
                    if 'resolution' in self._quality_settings:
                        target_resolution = tuple(self._quality_settings['resolution'])
                        self.logger.info(f"CAMERA: Using quality settings resolution: {target_resolution}")
                
                # TERTIARY: Check capture configs for resolution
                if target_resolution is None and hasattr(self, '_capture_configs'):
                    if self._capture_configs:
                        for camera_id, config in self._capture_configs.items():
                            try:
                                if hasattr(config, 'main') and 'size' in config.main:
                                    target_resolution = config.main['size']
                                    self.logger.info(f"CAMERA: Using capture config resolution: {target_resolution}")
                                    break
                            except Exception:
                                continue
            except Exception as resolution_error:
                self.logger.debug(f"Resolution detection failed: {resolution_error}")
            
            # LAST RESORT: Default to safe moderate resolution only if nothing else found
            if target_resolution is None:
                target_resolution = (4608, 2592)  # 12MP - good quality, manageable memory
                self.logger.info(f"CAMERA: No resolution detected, using default: {target_resolution}")
            
            # Prepare cameras with resolution awareness
            if hasattr(self.controller, 'prepare_cameras_for_capture'):
                await self.controller.prepare_cameras_for_capture(target_resolution=target_resolution)
            
            # Use resolution-aware capture system
            if hasattr(self.controller, 'capture_dual_resolution_aware'):
                self.logger.info(f"CAMERA: Using resolution-aware capture for {target_resolution}")
                capture_results = await self.controller.capture_dual_resolution_aware(
                    target_resolution=target_resolution,
                    delay_ms=500 if target_resolution[0] >= 8000 else 200
                )
                
                # Convert resolution-aware results to expected format
                camera_results = []
                for camera_id in ['camera_0', 'camera_1']:
                    if camera_id in capture_results and capture_results[camera_id] is not None:
                        image_array = capture_results[camera_id]
                        
                        # Convert RGB to BGR format for consistency
                        import cv2
                        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                        else:
                            image_bgr = image_array.copy()
                        
                        camera_results.append({'image': image_bgr, 'metadata': {}})
                        self.logger.info(f"CAMERA: Resolution-aware capture successful for {camera_id}: {image_bgr.shape}")
                    else:
                        camera_results.append(None)
                        self.logger.error(f"CAMERA: Resolution-aware capture failed for {camera_id}")
                        
            elif hasattr(self.controller, 'capture_dual_high_res_sequential'):
                self.logger.info("CAMERA: Using legacy high-resolution sequential capture")
                capture_results = await self.controller.capture_dual_high_res_sequential(delay_ms=500)
                
                # Convert legacy results to expected format
                camera_results = []
                for camera_id in ['camera_0', 'camera_1']:
                    if camera_id in capture_results and capture_results[camera_id] is not None:
                        image_array = capture_results[camera_id]
                        
                        # Convert RGB to BGR format
                        import cv2
                        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                        else:
                            image_bgr = image_array.copy()
                        
                        camera_results.append({'image': image_bgr, 'metadata': {}})
                        self.logger.info(f"CAMERA: Legacy capture successful for {camera_id}: {image_bgr.shape}")
                    else:
                        camera_results.append(None)
                        self.logger.error(f"CAMERA: Legacy capture failed for {camera_id}")
                        
            elif hasattr(self.controller, 'capture_dual_sequential_isp'):
                self.logger.info("CAMERA: Using standard ISP sequential capture mode")
                capture_results = await self.controller.capture_dual_sequential_isp("main", delay_ms=200)
                
                # Convert results to expected format
                camera_results = []
                for camera_id in ['camera_0', 'camera_1']:
                    if camera_id in capture_results and capture_results[camera_id] is not None:
                        image_array = capture_results[camera_id]
                        
                        # Convert RGB to BGR format
                        import cv2
                        if len(image_array.shape) == 3 and image_array.shape[2] == 3:
                            image_bgr = cv2.cvtColor(image_array, cv2.COLOR_RGB2BGR)
                        else:
                            image_bgr = image_array.copy()
                        
                        camera_results.append({'image': image_bgr, 'metadata': {}})
                        self.logger.info(f"CAMERA: ISP-managed capture successful for {camera_id}: {image_bgr.shape}")
                    else:
                        camera_results.append(None)
                        self.logger.error(f"CAMERA: ISP-managed capture failed for {camera_id}")
            else:
                # Fallback to original method if ISP methods not available
                self.logger.warning("CAMERA: ISP methods not available, using fallback capture")
                camera_results = []
                for camera_id, mapped_id in [('camera_0', 0), ('camera_1', 1)]:
                    try:
                        result = await capture_camera_direct(camera_id, mapped_id)
                        camera_results.append(result)
                        await asyncio.sleep(0.2)  # Increased delay for fallback
                    except Exception as e:
                        self.logger.error(f"CAMERA: Fallback capture failed for {camera_id}: {e}")
                        camera_results.append(None)
            
            # Process results
            for i, (camera_id, result) in enumerate(zip(['camera_0', 'camera_1'], camera_results)):
                if isinstance(result, Exception):
                    self.logger.error(f"CAMERA: Exception in {camera_id}: {result}")
                    results[camera_id] = None
                else:
                    # Handle new structure with metadata
                    if result is not None and isinstance(result, dict) and 'image' in result:
                        # New structure with metadata
                        results[camera_id] = result  # Keep both image and metadata
                        self.logger.info(f"CAMERA: {camera_id} simultaneous capture: SUCCESS (with metadata)")
                    elif result is not None:
                        # Backward compatibility - just image array
                        results[camera_id] = {'image': result, 'metadata': {}}
                        self.logger.info(f"CAMERA: {camera_id} simultaneous capture: SUCCESS (image only)")
                    else:
                        results[camera_id] = None
                        self.logger.warning(f"CAMERA: {camera_id} simultaneous capture: FAILED")
            
            self.logger.info(f"CAMERA: Simultaneous capture complete - {sum(1 for v in results.values() if v is not None)}/2 cameras successful")
            
        except Exception as e:
            self.logger.error(f"CAMERA: Simultaneous capture operation failed: {e}")
            results = {'camera_0': None, 'camera_1': None}
        
        finally:
            # Always reset capturing flag when capture completes (success or failure)
            self._is_capturing = False
            
            # Always switch back to streaming mode
            try:
                await self._switch_camera_mode("streaming")
            except Exception as cleanup_error:
                self.logger.warning(f"CAMERA: Cleanup mode switch failed: {cleanup_error}")
        
        return results
    
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
                        'cameras': ['camera_0', 'camera_1'],  # Both cameras available
                        'active_cameras': ['camera_0'],  # Only Camera 0 active in streaming mode
                        'initialized': True
                    }
                    self.logger.debug(f"Camera status (streaming mode): {status}")
                else:
                    # Scanning mode - both cameras available and active
                    status = {
                        'cameras': ['camera_0', 'camera_1'],  # Both cameras available
                        'active_cameras': ['camera_0', 'camera_1'],  # Both cameras active for scanning
                        'initialized': True
                    }
                    self.logger.info(f"Camera status (scanning mode): {status}")
                return status
            else:
                status = {
                    'cameras': ['camera_0', 'camera_1'],  # Still available but not active
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
    
    async def apply_quality_settings(self, quality_settings):
        """Apply quality settings to camera hardware (JPEG quality, format options)"""
        try:
            self.logger.info(f"CAMERA: Applying quality settings: {quality_settings}")
            
            # Extract settings with defaults
            jpeg_quality = quality_settings.get('jpeg_quality', 85)
            color_format = quality_settings.get('color_format', 'RGB888')
            compression_level = quality_settings.get('compression_level', 1)
            
            # Validate JPEG quality (0-100)
            if not 0 <= jpeg_quality <= 100:
                self.logger.warning(f"Invalid JPEG quality {jpeg_quality}, clamping to 0-100 range")
                jpeg_quality = max(0, min(100, jpeg_quality))
            
            # Store settings for use during capture (Pi cameras don't support runtime quality changes)
            # Quality will be applied during actual capture operations
            if not hasattr(self, '_quality_settings'):
                self._quality_settings = {}
            
            self._quality_settings.update({
                'jpeg_quality': jpeg_quality,
                'color_format': color_format,
                'compression_level': compression_level
            })
            
            # Include resolution if specified in quality settings
            if 'resolution' in quality_settings:
                self._quality_settings['resolution'] = list(quality_settings['resolution'])
                self.logger.info(f"CAMERA: Updated resolution in quality settings: {self._quality_settings['resolution']}")
            
            # Also store default quality for CameraSettings objects
            self._default_jpeg_quality = jpeg_quality
            
            self.logger.info(f"CAMERA: Stored quality settings for capture - JPEG quality: {jpeg_quality}")
            
            # Update camera configurations if resolution changed
            if 'resolution' in quality_settings:
                custom_resolution = tuple(quality_settings['resolution'])
                await self._update_camera_configurations(custom_resolution)
            
            return True
            
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to apply quality settings: {e}")
            return False
    
    async def _update_camera_configurations(self, custom_resolution):
        """Update camera configurations with custom resolution"""
        try:
            self.logger.info(f"CAMERA: Updating camera configurations for custom resolution: {custom_resolution}")
            
            # Validate and potentially adjust resolution for Pi hardware compatibility
            width, height = custom_resolution
            total_pixels = width * height
            validated_resolution = custom_resolution
            
            # Pi hardware limits - Only step down for extremely large resolutions
            if total_pixels > 70_000_000:  # Only for truly excessive resolutions (>70MP)
                self.logger.warning(f"CAMERA: Extremely large resolution detected ({total_pixels:,} pixels)")
                
                # Only step down for impossibly large resolutions
                if total_pixels > 80_000_000:  # Beyond any reasonable sensor
                    validated_resolution = (9152, 6944)  # Max 64MP fallback
                    self.logger.warning(f"CAMERA: Capped at maximum sensor resolution: {validated_resolution}")
                else:
                    self.logger.info(f"CAMERA: Large resolution ({total_pixels:,} pixels) - using enhanced buffer management")
            
            custom_resolution = validated_resolution
            
            # Log resolution info for debugging
            if total_pixels > 50_000_000:  # ~50MP threshold
                self.logger.info(f"CAMERA: High resolution detected ({total_pixels:,} pixels) - using optimized buffer allocation")
            elif total_pixels > 25_000_000:  # ~25MP threshold
                self.logger.debug(f"CAMERA: Moderately large resolution ({total_pixels:,} pixels) - normal operation")
            
            # Update capture configurations for both cameras
            for camera_id in [0, 1]:
                if hasattr(self.controller, 'cameras') and camera_id in self.controller.cameras:
                    camera = self.controller.cameras[camera_id]
                    
                    if camera:
                        try:
                            # Create new capture configuration with resolution-appropriate buffers
                            # OPTIMIZED SINGLE-STREAM: Custom resolution with minimal memory
                            new_capture_config = camera.create_still_configuration(
                                main={"size": custom_resolution, "format": "RGB888"},
                                raw=None,  # Explicitly prevent automatic RAW stream addition
                                buffer_count=1  # Minimal buffer allocation for still capture
                            )
                            
                            # Update stored configuration
                            if hasattr(self, '_capture_configs'):
                                self._capture_configs[camera_id] = new_capture_config
                                self.logger.info(f"CAMERA: Updated camera {camera_id} capture config to {custom_resolution}")
                                
                                # Add delay between camera configurations to prevent simultaneous memory allocation
                                if camera_id == 0:  # After first camera, wait before configuring second
                                    await asyncio.sleep(0.5)
                                    self.logger.debug(f"CAMERA: Delay added between camera configurations for memory management")
                                
                        except Exception as config_error:
                            self.logger.error(f"CAMERA: Failed to create capture config for camera {camera_id}: {config_error}")
                            # Fallback to max supported resolution instead of stepping down too much
                            fallback_resolution = (9152, 6944)  # 64MP fallback maintains capability
                            self.logger.warning(f"CAMERA: Falling back to max supported resolution: {fallback_resolution}")
                            
                            fallback_config = camera.create_still_configuration(
                                main={"size": fallback_resolution, "format": "RGB888"},
                                raw=None,  # Prevent automatic RAW stream addition
                                buffer_count=1  # Minimal buffer allocation
                            )
                            
                            if hasattr(self, '_capture_configs'):
                                self._capture_configs[camera_id] = fallback_config
                                
                            # Update stored quality settings to reflect fallback
                            if hasattr(self, '_quality_settings') and self._quality_settings:
                                self._quality_settings['resolution'] = list(fallback_resolution)
                                self.logger.info(f"CAMERA: Updated stored resolution to fallback: {fallback_resolution}")
            
            self.logger.info(f"CAMERA: Camera configuration update completed")
            
        except Exception as e:
            self.logger.error(f"CAMERA: Failed to update camera configurations: {e}")
            # Final fallback - ensure we have working configurations
            await self._ensure_working_camera_configs()
    
    async def _ensure_working_camera_configs(self):
        """Ensure cameras have working configurations as final fallback"""
        try:
            self.logger.info("CAMERA: Applying fallback configurations for camera stability")
            safe_resolution = (9152, 6944)  # Safe 64MP resolution - system proven capable
            
            for camera_id in [0, 1]:
                if hasattr(self.controller, 'cameras') and camera_id in self.controller.cameras:
                    camera = self.controller.cameras[camera_id]
                    
                    if camera:
                        # OPTIMIZED SINGLE-STREAM: Safe configuration with minimal memory allocation
                        safe_config = camera.create_still_configuration(
                            main={"size": safe_resolution, "format": "RGB888"},
                            raw=None,  # Prevent automatic RAW stream - eliminates V4L2 buffer errors
                            buffer_count=1  # Minimal buffer allocation for still photos
                        )
                        
                        if hasattr(self, '_capture_configs'):
                            self._capture_configs[camera_id] = safe_config
                            
            # Update stored settings to safe values
            if hasattr(self, '_quality_settings') and self._quality_settings:
                self._quality_settings['resolution'] = list(safe_resolution)
                
            self.logger.info(f"CAMERA: Fallback configurations applied - resolution: {safe_resolution}")
            
        except Exception as e:
            self.logger.error(f"CAMERA: Even fallback configuration failed: {e}")
    

    
    def _apply_quality_to_settings(self, settings):
        """Apply stored quality settings to CameraSettings object"""
        if hasattr(self, '_default_jpeg_quality') and hasattr(settings, 'quality'):
            original_quality = settings.quality
            settings.quality = self._default_jpeg_quality
            if original_quality != settings.quality:
                self.logger.info(f"CAMERA: Applied custom JPEG quality: {original_quality} → {settings.quality}")
        return settings

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
        
    async def trigger_for_capture(self, camera_controller, zone_ids: List[str], settings: Any) -> Any:
        """Delegate to controller's synchronized flash-capture method"""
        if hasattr(self.controller, 'trigger_for_capture'):
            return await self.controller.trigger_for_capture(camera_controller, zone_ids, settings)
        else:
            # Fallback to regular flash for controllers without sync support
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
        
        # Homing confirmation callback
        self._homing_confirmation_callback: Optional[Callable] = None
        
        # Global notification callback
        self._notification_callback: Optional[Callable] = None
        
        # Focus control - Independent autofocus enabled by default for best results
        self._scan_focus_values: Dict[str, float] = {}  # Focus values for each camera
        self._primary_focus_value: Optional[float] = None  # Primary focus value for synced mode
        self._focus_mode = 'auto'  # 'auto', 'manual', or 'fixed'
        self._focus_sync_enabled = False  # Independent focus by default for best camera performance
        
        # Performance tracking
        self._timing_stats = {
            'movement_time': 0.0,
            'capture_time': 0.0,
            'processing_time': 0.0
        }
        
        # Subscribe to events
        self._setup_event_handlers()
        
        # Initialize profile manager
        profiles_dir = Path.home() / '.scanner_profiles'
        self.profile_manager = ScanProfileManager(profiles_dir)
        self.logger.info(f"Profile manager initialized with {len(self.profile_manager.quality_profiles)} quality and {len(self.profile_manager.speed_profiles)} speed profiles")
    
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
            else:
                # Verify lighting zones are loaded correctly
                if hasattr(self.lighting_controller, 'controller'):
                    # Using adapter - check underlying controller
                    actual_controller = self.lighting_controller.controller
                    if hasattr(actual_controller, 'list_zones'):
                        zones = await actual_controller.list_zones()
                        self.logger.info(f"✅ Lighting controller initialized with zones: {zones}")
                        for zone in zones:
                            if hasattr(actual_controller, 'get_zone_info'):
                                zone_info = await actual_controller.get_zone_info(zone)
                                self.logger.info(f"   🔸 Zone '{zone}': GPIO pins {zone_info.get('gpio_pins', 'unknown')}, "
                                               f"max brightness {zone_info.get('max_brightness', 'unknown')}")
                else:
                    self.logger.info("✅ Lighting controller initialized (mock mode)")
            
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
            # Check motion controller - handle both sync and async is_connected methods
            if hasattr(self.motion_controller.is_connected, '__call__'):
                if asyncio.iscoroutinefunction(self.motion_controller.is_connected):
                    connected = await self.motion_controller.is_connected()
                else:
                    connected = self.motion_controller.is_connected()
                if not connected:
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
    
    def set_notification_callback(self, callback):
        """Set callback for global notifications"""
        self._notification_callback = callback
        
    def _add_notification(self, message: str, type_: str = 'info', duration: int = 5000):
        """Add a global notification"""
        if self._notification_callback:
            self._notification_callback(message, type_, duration)
        else:
            self.logger.info(f"NOTIFICATION: {message}")
    
    async def apply_scan_profiles(self, quality_name: str = 'medium', speed_name: str = 'medium') -> Dict[str, Any]:
        """Apply quality and speed profiles to current scan
        
        Args:
            quality_name: Name of quality profile to use
            speed_name: Name of speed profile to use
            
        Returns:
            Dictionary with applied settings
        """
        try:
            settings = self.profile_manager.get_scan_settings(quality_name, speed_name)
            
            # Apply camera settings from quality profile
            quality_settings = settings['camera_settings']
            if hasattr(self.camera_manager, 'apply_quality_settings'):
                await self.camera_manager.apply_quality_settings({
                    'resolution': quality_settings['resolution'],
                    'jpeg_quality': quality_settings['jpeg_quality'],
                    'capture_timeout': quality_settings['capture_timeout'],
                    'iso_preference': quality_settings['iso_preference'],
                    'exposure_mode': quality_settings['exposure_mode']
                })
            
            # Apply motion settings from speed profile
            motion_settings = settings['motion_settings']
            if hasattr(self.motion_controller, 'apply_speed_settings'):
                await self.motion_controller.apply_speed_settings({
                    'feedrate_multiplier': motion_settings['feedrate_multiplier'],
                    'settling_delay': motion_settings['settling_delay'],
                    'acceleration_factor': motion_settings['acceleration_factor'],
                    'motion_precision': motion_settings['motion_precision']
                })
            
            self.logger.info(f"Applied scan profiles - Quality: {quality_name}, Speed: {speed_name}")
            self.logger.debug(f"Quality settings: {quality_settings}")
            self.logger.debug(f"Motion settings: {motion_settings}")
            
            return settings
            
        except Exception as e:
            self.logger.error(f"Failed to apply scan profiles: {e}")
            return {}
    
    async def apply_custom_scan_settings(self, quality_settings: Optional[Dict[str, Any]] = None, speed_settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Apply custom quality and speed settings directly to scan
        
        Args:
            quality_settings: Custom quality/camera settings to apply
            speed_settings: Custom speed/motion settings to apply
            
        Returns:
            Dictionary with applied settings
        """
        try:
            applied_settings = {'camera_settings': {}, 'motion_settings': {}}
            
            # Create temporary custom profiles and apply them through the existing system
            quality_profile_name = 'custom_active'
            speed_profile_name = 'custom_active'
            
            # If custom quality settings provided, create/update temporary quality profile
            if quality_settings:
                self.logger.info(f"🎯 Creating temporary custom quality profile with settings: {quality_settings}")
                try:
                    # Create a temporary custom quality profile
                    custom_quality_profile = self.profile_manager.create_custom_quality_profile(
                        base_profile='medium',  # Use medium as base
                        modifications=quality_settings,
                        custom_name='temp_custom_quality'
                    )
                    quality_profile_name = 'temp_custom_quality'
                    applied_settings['camera_settings'] = quality_settings.copy()
                except Exception as e:
                    self.logger.warning(f"Failed to create custom quality profile: {e}")
                    quality_profile_name = 'medium'  # Fallback
            
            # If custom speed settings provided, create/update temporary speed profile
            if speed_settings:
                self.logger.info(f"🎯 Creating temporary custom speed profile with settings: {speed_settings}")
                try:
                    # Create a temporary custom speed profile
                    custom_speed_profile = self.profile_manager.create_custom_speed_profile(
                        base_profile='medium',  # Use medium as base
                        modifications=speed_settings,
                        custom_name='temp_custom_speed'
                    )
                    speed_profile_name = 'temp_custom_speed'
                    applied_settings['motion_settings'] = speed_settings.copy()
                except Exception as e:
                    self.logger.warning(f"Failed to create custom speed profile: {e}")
                    speed_profile_name = 'medium'  # Fallback
            
            # Now apply the profiles through the existing system
            profile_settings = await self.apply_scan_profiles(quality_profile_name, speed_profile_name)
            
            # Merge the profile settings with our applied settings
            if 'camera_settings' in profile_settings:
                applied_settings['camera_settings'].update(profile_settings['camera_settings'])
            if 'motion_settings' in profile_settings:
                applied_settings['motion_settings'].update(profile_settings['motion_settings'])
            
            self.logger.info(f"✅ Applied custom scan settings - Quality: {quality_settings is not None}, Speed: {speed_settings is not None}")
            return applied_settings
            
        except Exception as e:
            self.logger.error(f"Failed to apply custom scan settings: {e}")
            return {'camera_settings': {}, 'motion_settings': {}}
    
    async def is_system_busy(self) -> bool:
        """Check if system is busy with active operations that should block new scans"""
        # Check for active scan
        if self.current_scan and self.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED, ScanStatus.INITIALIZING]:
            return True
            
        # Check if motion controller is homing (for real hardware controllers)
        if hasattr(self.motion_controller, 'is_homing'):
            try:
                if self.motion_controller.is_homing():
                    return True
            except Exception:
                pass
            
        # Check if motion controller status indicates busy state
        # Use get_current_status for FluidNC controllers
        status_methods = ['get_current_status', 'get_status']
        for method_name in status_methods:
            if hasattr(self.motion_controller, method_name):
                try:
                    method = getattr(self.motion_controller, method_name)
                    # Check if method is a coroutine and await it properly
                    if asyncio.iscoroutinefunction(method):
                        status = await method()
                    else:
                        status = method()
                    
                    if status and isinstance(status, str):
                        # FluidNC states that indicate system is busy
                        busy_states = ['home', 'jog', 'hold']
                        status_lower = status.lower()
                        if any(state in status_lower for state in busy_states):
                            return True
                        # If status is 'run' but no active scan, system might be homing
                        if 'run' in status_lower and not self.current_scan:
                            return True  # Likely homing or other motion in progress
                    break  # Found a working status method
                except Exception as e:
                    self.logger.debug(f"Error checking motion controller status via {method_name}: {e}")
                    continue
                
        return False
    
    async def start_scan(self, 
                        pattern: ScanPattern,
                        output_directory: Union[str, Path],
                        scan_id: Optional[str] = None,
                        scan_parameters: Optional[Dict[str, Any]] = None,
                        homing_confirmation_callback: Optional[Callable] = None) -> ScanState:
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
        # CRITICAL: Check if system is busy before allowing new scan
        if await self.is_system_busy():
            # Get detailed status for error message
            status_details = []
            if self.current_scan and self.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED, ScanStatus.INITIALIZING]:
                status_details.append(f"Active scan: {self.current_scan.status.value}")
            if hasattr(self.motion_controller, 'get_status'):
                try:
                    motion_status = self.motion_controller.get_status()
                    if motion_status:
                        status_details.append(f"Motion: {motion_status}")
                except Exception:
                    pass
            
            error_msg = f"Cannot start scan - system is busy. {', '.join(status_details) if status_details else 'Please wait for current operations to complete.'}"
            self.logger.warning(f"🚫 {error_msg}")
            raise ScannerSystemError(error_msg)
        
        # Check for active scans and clean up completed ones
        if self.current_scan:
            if self.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED, ScanStatus.INITIALIZING]:
                raise ScannerSystemError("Cannot start scan: another scan is active")
            else:
                # Clear completed/failed/cancelled scans
                self.logger.info(f"Clearing previous scan state: {self.current_scan.status}")
                self.current_scan = None
                self.current_pattern = None
                self.scan_task = None
        
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
        
        # Store homing confirmation callback for this scan
        self._homing_confirmation_callback = homing_confirmation_callback
        
        # Initialize scan parameters
        scan_parameters = scan_parameters or {}
        scan_parameters.update({
            'pattern_type': pattern.pattern_type.value,
            'pattern_parameters': self._extract_relevant_pattern_parameters(pattern.parameters.__dict__),
            'total_points': len(pattern.generate_points()),
            'camera_settings': self.camera_manager.get_current_settings(),
            'motion_settings': self.motion_controller.get_current_settings()
        })
        
        # Initialize scan state
        self.current_scan.initialize(
            total_points=len(pattern.generate_points()),
            scan_parameters=scan_parameters
        )
        
        # 💾 CREATE STORAGE SESSION with complete metadata (only if no session exists)
        session_id = None
        try:
            # Generate all scan points for complete metadata
            scan_points = pattern.generate_points()
            
            # Check if scan_id corresponds to an existing session directory (from web interface)
            existing_session_dir = None
            if hasattr(self.storage_manager, 'base_storage_path'):
                potential_session_path = self.storage_manager.base_storage_path / 'sessions' / scan_id
                if potential_session_path.exists():
                    existing_session_dir = potential_session_path
                    session_id = scan_id
                    self.logger.info(f"📁 Using existing storage session directory: {scan_id}")
            
            if not existing_session_dir:
                # Create new session only if one doesn't exist
                # Create comprehensive session metadata using SessionManager expected fields
                session_metadata = {
                    'name': scan_parameters.get('scan_name', scan_id),  # SessionManager expects 'name' field
                    'description': f"{pattern.pattern_type.value} scan with {len(scan_points)} positions",
                    'operator': scan_parameters.get('operator', 'Scanner_System'),
                    'scan_parameters': {
                        'scan_id': scan_id,
                        'pattern_type': pattern.pattern_type.value,
                        'pattern_id': pattern.pattern_id,
                        'total_points': len(scan_points),
                        'created_at': datetime.now().isoformat(),
                        'pattern_parameters': self._extract_relevant_pattern_parameters(pattern.parameters.__dict__),
                        'web_parameters': scan_parameters,
                        'output_directory': str(output_directory),
                        # Add complete scan positions array
                        'scan_positions': [{
                            'point_index': i,
                            'position': {
                                'x': point.position.x,
                                'y': point.position.y,
                                'z': point.position.z,
                                'c': point.position.c
                            },
                            'capture_count': point.capture_count,
                            'dwell_time': point.dwell_time
                        } for i, point in enumerate(scan_points)],
                        'hardware_config': {
                            'motion_settings': self.motion_controller.get_current_settings() if hasattr(self.motion_controller, 'get_current_settings') else {},
                            'camera_settings': self.camera_manager.get_current_settings() if hasattr(self.camera_manager, 'get_current_settings') else {}
                        }
                    }
                }
                
                session_id = await self.storage_manager.create_session(session_metadata)
                self.logger.info(f"📁 Created NEW storage session: {session_id} with {len(scan_points)} positions")
            else:
                self.logger.info(f"📁 Using EXISTING storage session: {session_id} for scan")
        except Exception as e:
            self.logger.error(f"❌ Failed to create/access storage session: {e}")
            # Continue anyway - better to have scan without storage than no scan
            session_id = scan_id  # Use the provided scan_id as fallback
        
        # 📋 GENERATE SCAN POSITIONS METADATA FILE and store in storage manager
        try:
            # Generate positions file with actual settings (custom settings are already applied at this point)
            positions_metadata = await self._generate_scan_positions_file(pattern, Path(output_directory), scan_id, prefer_calibrated=True)
            
            # Also save positions file to session directory if session exists
            if 'session_id' in locals() and positions_metadata:
                try:
                    # Save positions metadata directly to session directory
                    if hasattr(self.storage_manager, 'base_storage_path'):
                        session_path = self.storage_manager.base_storage_path / 'sessions' / session_id / 'metadata'
                    else:
                        # Fallback for mock storage manager
                        session_path = Path.cwd() / 'sessions' / session_id / 'metadata'
                    
                    if session_path.exists():
                        positions_file = session_path / f"{scan_id}_scan_positions.json"
                        
                        # Save positions file content to session metadata directory
                        import json
                        with open(positions_file, 'w') as f:
                            json.dump(positions_metadata, f, indent=2, default=str)
                        
                        self.logger.info(f"📋 Stored positions metadata in session directory: {positions_file}")
                    else:
                        self.logger.warning(f"⚠️ Session directory not found: {session_path}")
                        
                except Exception as storage_e:
                    self.logger.warning(f"⚠️ Failed to store positions in session directory: {storage_e}")
            
            self.logger.info(f"📋 Generated scan positions metadata file")
        except Exception as e:
            self.logger.error(f"❌ Failed to generate scan positions file: {e}")
            # Continue anyway - this is just metadata
        
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
    
    def _extract_relevant_pattern_parameters_legacy(self, pattern_params) -> dict:
        """Extract only the relevant pattern parameters, filtering out base PatternParameters"""
        # Convert to dict if it's a dataclass
        if hasattr(pattern_params, '__dict__'):
            all_params = pattern_params.__dict__
        else:
            all_params = pattern_params
        
        # Filter out base PatternParameters that are inherited but not specific to the pattern
        base_params = {'min_x', 'max_x', 'min_y', 'max_y', 'min_z', 'max_z', 'min_c', 'max_c', 
                      'overlap_percentage', 'max_distance', 'max_feedrate', 'safety_margin'}
        
        # Keep only pattern-specific parameters
        relevant_params = {k: v for k, v in all_params.items() if k not in base_params}
        
        return relevant_params
    
    async def _get_actual_camera_settings(self, prefer_calibrated: bool = True) -> dict:
        """Get actual calibrated camera settings instead of template values"""
        # Start with sensible defaults, but use actual camera config if available
        default_resolution = [9152, 6944]  # Default ArduCam 64MP full resolution
        
        # Check if we have actual camera configurations with custom resolution
        if hasattr(self, '_capture_configs') and self._capture_configs:
            # Use actual resolution from camera configuration
            try:
                camera_config = list(self._capture_configs.values())[0]  # Get first camera config
                if 'main' in camera_config and 'size' in camera_config['main']:
                    default_resolution = list(camera_config['main']['size'])
                    self.logger.debug(f"📋 Using actual camera config resolution: {default_resolution}")
            except Exception as e:
                self.logger.debug(f"📋 Could not extract resolution from camera config: {e}")
        
        # Also check camera manager's quality settings as a secondary source
        elif hasattr(self.camera_manager, '_quality_settings') and self.camera_manager._quality_settings:
            if 'resolution' in self.camera_manager._quality_settings:
                fallback_resolution = self.camera_manager._quality_settings['resolution']
                if isinstance(fallback_resolution, (list, tuple)) and len(fallback_resolution) >= 2:
                    default_resolution = list(fallback_resolution)
                    self.logger.debug(f"📋 Using camera manager quality settings resolution: {default_resolution}")
        
        actual_settings = {
            'exposure_time': '1/30s',  # Sensible default for ArduCam 64MP
            'iso': 800,               # Sensible default for indoor scanning
            'capture_format': 'JPEG',
            'resolution': default_resolution,  # Use actual or default resolution
            'quality': 95,  # Default quality
            'calibration_source': 'default_values'  # Track source of settings
        }
        
        # Apply custom settings from camera manager if available
        if hasattr(self.camera_manager, '_quality_settings') and self.camera_manager._quality_settings:
            custom_settings = self.camera_manager._quality_settings
            self.logger.info(f"📋 Applying custom camera settings: {custom_settings}")
            
            # Apply custom resolution if specified, with safety validation
            if 'resolution' in custom_settings:
                requested_resolution = custom_settings['resolution']
                # Apply resolution directly (validation happens in CameraManagerAdapter)
                actual_settings['resolution'] = requested_resolution
                
            # Apply custom JPEG quality
            if 'jpeg_quality' in custom_settings:
                actual_settings['quality'] = int(custom_settings['jpeg_quality'])
                
            # Apply other custom settings if present
            if 'exposure_time' in custom_settings:
                actual_settings['exposure_time'] = f"1/{1000000//custom_settings['exposure_time']}s" if custom_settings['exposure_time'] > 1000 else f"{custom_settings['exposure_time']/1000000}s"
                
            if 'analogue_gain' in custom_settings:
                # Convert analogue gain to approximate ISO (rough approximation)
                actual_settings['iso'] = int(100 * custom_settings['analogue_gain'])
                
            actual_settings['calibration_source'] = 'custom_profile_applied'
            self.logger.info(f"📋 Updated camera settings with custom profile: Resolution: {actual_settings['resolution']}, Quality: {actual_settings['quality']}")
            
            # Update stored resolution to match what was actually applied
            if hasattr(self, '_capture_configs') and self._capture_configs:
                try:
                    # Update the resolution in our settings to match actual camera config
                    camera_config = list(self._capture_configs.values())[0]
                    if 'main' in camera_config and 'size' in camera_config['main']:
                        actual_settings['resolution'] = list(camera_config['main']['size'])
                        self.logger.info(f"📋 Final resolution from camera config: {actual_settings['resolution']}")
                except Exception as e:
                    self.logger.debug(f"📋 Could not update resolution from camera config: {e}")
        else:
            self.logger.debug("📋 No custom camera settings available, using defaults")
        
        try:
            # Check if camera manager is available and accessible
            camera_controller = None
            
            # Try different ways to access the camera controller
            if hasattr(self, 'camera_manager') and self.camera_manager:
                # Check for direct controller access (CameraManagerAdapter pattern)
                if hasattr(self.camera_manager, 'controller') and self.camera_manager.controller:
                    camera_controller = self.camera_manager.controller
                    self.logger.debug("📋 Camera controller accessed via camera_manager.controller")
                # Check for internal controller access
                elif hasattr(self.camera_manager, '_controller') and self.camera_manager._controller:
                    camera_controller = self.camera_manager._controller
                    self.logger.debug("📋 Camera controller accessed via camera_manager._controller")
                # Check if camera manager has controller method
                elif hasattr(self.camera_manager, 'camera_controller') and self.camera_manager.camera_controller:
                    camera_controller = self.camera_manager.camera_controller
                    self.logger.debug("📋 Camera controller accessed via camera_manager.camera_controller")
                # Check if camera manager is itself the controller (Pi setup)
                elif hasattr(self.camera_manager, '_calibrated_settings'):
                    camera_controller = self.camera_manager
                    self.logger.debug("📋 Camera manager is acting as controller directly")
                else:
                    self.logger.debug("📋 Camera manager exists but no controller interface found")
            else:
                self.logger.debug("📋 No camera manager available or camera manager is None")

            # Check if we have a valid controller with calibrated settings
            if camera_controller and hasattr(camera_controller, '_calibrated_settings') and camera_controller._calibrated_settings:
                self.logger.debug("📋 Found camera controller with calibrated settings")
                calibrated = camera_controller._calibrated_settings
                
                # Use Camera 0 calibrated settings as reference (both cameras should be similar)
                if calibrated and (0 in calibrated or 1 in calibrated):
                    ref_cam = 0 if 0 in calibrated else 1
                    ref_settings = calibrated[ref_cam]
                    
                    if isinstance(ref_settings, dict) and 'exposure_time' in ref_settings:
                        # Convert microseconds to readable format
                        exposure_us = ref_settings.get('exposure_time', 32746)
                        
                        # Convert common exposure times to readable fractions
                        if exposure_us == 32746:
                            actual_settings['exposure_time'] = '1/30s'
                        elif exposure_us == 16373:
                            actual_settings['exposure_time'] = '1/60s'
                        elif exposure_us == 66666:
                            actual_settings['exposure_time'] = '1/15s'
                        elif exposure_us == 100000:
                            actual_settings['exposure_time'] = '1/10s'
                        else:
                            # For other values, show as fractional seconds
                            exposure_s = exposure_us / 1000000.0
                            # Try to convert to common fractions
                            if exposure_s > 0.001:  # Greater than 1ms
                                fraction_denom = int(1.0 / exposure_s)
                                actual_settings['exposure_time'] = f'1/{fraction_denom}s'
                            else:
                                actual_settings['exposure_time'] = f'{exposure_s:.6f}s'
                        
                        # Get analogue gain and convert to ISO equivalent
                        analogue_gain = ref_settings.get('analogue_gain', 8.0)
                        actual_settings['iso'] = int(analogue_gain * 100)  # Convert gain to ISO
                        actual_settings['calibration_source'] = 'camera_calibrated'
                        
                        # Add focus information if available
                        if 'focus_value' in ref_settings:
                            actual_settings['focus_position'] = ref_settings['focus_value']
                        
                        # Add calibration timestamp if available
                        if 'timestamp' in ref_settings:
                            actual_settings['calibration_timestamp'] = ref_settings['timestamp']
                        
                        self.logger.info(f"📋 Using calibrated camera settings: "
                                       f"{actual_settings['exposure_time']}, ISO {actual_settings['iso']}")
                        return actual_settings
                    else:
                        self.logger.warning("📋 Invalid calibrated settings format, using defaults")
                        actual_settings['calibration_source'] = 'invalid_calibration_format'
                else:
                    if prefer_calibrated:
                        self.logger.warning("📋 No calibrated settings available, using sensible defaults")
                        actual_settings['calibration_source'] = 'no_calibration_available'
                    else:
                        self.logger.debug("📋 Calibration not required at this stage, using defaults")
                        actual_settings['calibration_source'] = 'planning_stage_defaults'
            else:
                # Camera controller not available or no calibrated settings
                if prefer_calibrated:
                    # Try to initialize camera controller if not yet done
                    initialization_attempted = False
                    if hasattr(self, 'camera_manager') and self.camera_manager:
                        try:
                            if hasattr(self.camera_manager, 'controller') and not hasattr(self.camera_manager.controller, '_calibrated_settings'):
                                self.logger.debug("📋 Attempting to initialize camera controller for calibrated settings...")
                                await self.camera_manager.initialize()
                                initialization_attempted = True
                        except Exception as init_error:
                            self.logger.debug(f"📋 Camera controller initialization attempt failed: {init_error}")
                    
                    if initialization_attempted:
                        self.logger.info("📋 Camera controller initialization attempted - settings will be updated during scan execution")
                    else:
                        self.logger.warning("📋 Camera controller not accessible or no calibrated settings available")
                    
                    actual_settings['calibration_source'] = 'controller_unavailable'
                    
                    # Add note that settings will be updated during scan execution
                    actual_settings['will_update_during_scan'] = True
                    self.logger.info("📋 Camera settings will be updated with calibrated values during scan execution")
                else:
                    self.logger.debug("📋 Using planning-stage defaults (controller will be available during execution)")
                    actual_settings['calibration_source'] = 'planning_stage_defaults'
                    actual_settings['will_update_during_scan'] = True
                
        except Exception as e:
            self.logger.warning(f"📋 Failed to get calibrated settings: {e}, using defaults")
            actual_settings['calibration_source'] = f'error_{type(e).__name__}'
        
        return actual_settings

    async def _generate_scan_positions_file(self, pattern: ScanPattern, output_directory: Path, scan_id: str, 
                                           prefer_calibrated: bool = False) -> dict:
        """Generate a detailed metadata file with all scan point positions using actual camera settings"""
        try:
            # Generate all scan points
            scan_points = pattern.generate_points()
            
            # Get camera settings - prefer planning stage defaults during initial generation
            actual_camera_settings = await self._get_actual_camera_settings(prefer_calibrated=prefer_calibrated)
            
            # Determine appropriate note based on settings source
            settings_source = actual_camera_settings.get('calibration_source', 'unknown')
            if settings_source == 'camera_calibrated':
                settings_note = 'Camera settings reflect actual calibrated values from scan execution'
            elif settings_source == 'custom_profile_applied':
                settings_note = 'Camera settings reflect custom user profile (quality, resolution, exposure) - applied to hardware'
            elif settings_source == 'planning_stage_defaults':
                settings_note = 'Camera settings are planning defaults - will be updated with calibrated values during scan execution'
            elif settings_source == 'controller_unavailable':
                settings_note = 'Camera controller not available during positions file generation - using sensible defaults'
            else:
                settings_note = f'Camera settings source: {settings_source} - may be updated during scan execution'
            
            # Create positions metadata with actual camera settings information
            positions_metadata = {
                'scan_info': {
                    'scan_id': scan_id,
                    'pattern_type': pattern.pattern_type.value,
                    'pattern_id': pattern.pattern_id,
                    'total_points': len(scan_points),
                    'generated_at': datetime.now().isoformat(),
                    'pattern_parameters': self._extract_relevant_pattern_parameters(pattern.parameters.__dict__),
                    'camera_settings_info': {
                        'settings_source': settings_source,
                        'settings_generated_at': datetime.now().isoformat(),
                        'note': settings_note,
                        'will_be_updated': settings_source in ['planning_stage_defaults', 'controller_unavailable', 'no_calibration_available']
                    }
                },
                'scan_positions': []
            }
            
            # Add each scan point with detailed position information
            for i, point in enumerate(scan_points):
                point_info = {
                    'point_index': i,
                    'position': {
                        'x': point.position.x,
                        'y': point.position.y,
                        'z': point.position.z,
                        'c': point.position.c
                    },
                    'capture_settings': {
                        'capture_count': point.capture_count,
                        'dwell_time': point.dwell_time
                    }
                }
                
                # Use actual calibrated camera settings instead of template values
                point_info['camera_settings'] = actual_camera_settings.copy()
                
                # Add lighting settings if available
                if point.lighting_settings:
                    point_info['lighting_settings'] = point.lighting_settings
                
                positions_metadata['scan_positions'].append(point_info)
            
            # Ensure output directory exists
            output_directory.mkdir(parents=True, exist_ok=True)
            
            # Write positions metadata to JSON file
            positions_file = output_directory / f"{scan_id}_scan_positions.json"
            with open(positions_file, 'w') as f:
                import json
                json.dump(positions_metadata, f, indent=2, default=str)
            
            # Validate and log the camera settings used
            first_point_settings = positions_metadata['scan_positions'][0]['camera_settings']
            self.logger.info(f"📋 Scan positions saved to: {positions_file}")
            self.logger.info(f"📸 Camera settings in scan positions file: "
                           f"Exposure: {first_point_settings['exposure_time']}, "
                           f"ISO: {first_point_settings['iso']}, "
                           f"Resolution: {first_point_settings['resolution']}, "
                           f"Source: {first_point_settings['calibration_source']}")
            
            return positions_metadata
            
        except Exception as e:
            self.logger.error(f"❌ Failed to generate scan positions file: {e}")
            raise

    async def _update_scan_positions_with_calibration(self, scan_id: str, output_directory: Path):
        """Update scan positions file with actual calibrated camera settings after calibration"""
        try:
            positions_file = output_directory / f"{scan_id}_scan_positions.json"
            
            if not positions_file.exists():
                self.logger.warning(f"📋 Positions file not found for updating: {positions_file}")
                return
            
            # Get actual calibrated settings
            calibrated_settings = await self._get_actual_camera_settings(prefer_calibrated=True)
            
            # Only update if we actually have calibrated settings
            if calibrated_settings.get('calibration_source') != 'camera_calibrated':
                self.logger.debug("📋 No calibrated settings available for positions file update")
                return
            
            # Read existing positions file
            import json
            with open(positions_file, 'r') as f:
                positions_data = json.load(f)
            
            # Update camera settings info in scan_info
            positions_data['scan_info']['camera_settings_info'].update({
                'settings_source': calibrated_settings['calibration_source'],
                'settings_updated_at': datetime.now().isoformat(),
                'note': 'Camera settings updated with actual calibrated values after scan calibration',
                'will_be_updated': False
            })
            
            # Update camera settings in all scan positions
            for position in positions_data['scan_positions']:
                position['camera_settings'].update({
                    'exposure_time': calibrated_settings['exposure_time'],
                    'iso': calibrated_settings['iso'],
                    'calibration_source': calibrated_settings['calibration_source']
                })
                
                # Add calibration timestamp if available
                if 'calibration_timestamp' in calibrated_settings:
                    position['camera_settings']['calibration_timestamp'] = calibrated_settings['calibration_timestamp']
                
                # Add focus position if available
                if 'focus_position' in calibrated_settings:
                    position['camera_settings']['focus_position'] = calibrated_settings['focus_position']
            
            # Write updated positions file
            with open(positions_file, 'w') as f:
                json.dump(positions_data, f, indent=2, default=str)
            
            self.logger.info(f"📋 Updated scan positions file with calibrated settings: "
                           f"Exposure: {calibrated_settings['exposure_time']}, "
                           f"ISO: {calibrated_settings['iso']}")
            
        except Exception as e:
            self.logger.warning(f"📋 Failed to update positions file with calibration: {e}")
            # Don't raise - this is not critical to scan execution
    
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
            
            # Add scan started notification after homing is complete
            scan_name = self.current_scan.scan_parameters.get('scan_name', self.current_scan.scan_id)
            self._add_notification(
                f"🚀 Scan '{scan_name}' started successfully!", 
                'success', 
                5000
            )
            
            # Focus will be set up at the first scan point for object-based focusing
            self.logger.info("Focus will be configured at first scan point")
            
            # Execute scan points
            self.logger.info("Starting scan points execution")
            await self._execute_scan_points()
            self.logger.info("Scan points execution completed")
            
            # Complete the scan
            if not self._stop_requested and not self._emergency_stop:
                self.current_scan.complete()
                self.logger.info(f"Scan {self.current_scan.scan_id} completed successfully")
                # Add completion notification
                scan_name = self.current_scan.scan_parameters.get('scan_name', self.current_scan.scan_id)
                self._add_notification(
                    f"✅ Scan '{scan_name}' completed successfully!", 
                    'success', 
                    8000
                )
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
        """Home the motion system using pre-confirmed preference"""
        if self._check_stop_conditions():
            return
        
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.HOMING)
        
        # Check if homing was pre-confirmed via scan parameters
        should_home = True  # Default to homing for safety
        
        # DEBUG: Log what we have access to
        self.logger.info(f"🔍 DEBUG: current_scan type: {type(self.current_scan)}")
        self.logger.info(f"🔍 DEBUG: hasattr scan_parameters: {hasattr(self.current_scan, 'scan_parameters') if self.current_scan else 'No current_scan'}")
        
        if hasattr(self.current_scan, 'scan_parameters') and self.current_scan.scan_parameters:
            self.logger.info(f"🔍 DEBUG: scan_parameters keys: {list(self.current_scan.scan_parameters.keys())}")
            should_home = self.current_scan.scan_parameters.get('homing_confirmed', True)
            self.logger.info(f"🏠 Using pre-confirmed homing preference: {'proceed' if should_home else 'skip'}")
        else:
            self.logger.info("🏠 No homing preference found - defaulting to homing for safety")
        
        if not should_home:
            self.logger.info("🚫 Skipping homing as requested - proceeding without homing")
            self.logger.warning("⚠️  Scan proceeding without homing - positions may be inaccurate!")
            return
        else:
            self.logger.info("✅ Proceeding with homing sequence")
        
        self.logger.info("🏠 Starting homing sequence for motion system")
        
        # Use the working synchronous homing method that the web UI uses
        # Run it in a thread pool to make it async-compatible
        import asyncio
        import concurrent.futures
        
        def sync_home():
            # Check if the synchronous method exists (real hardware), otherwise use async method
            if hasattr(self.motion_controller, 'home_axes_sync'):
                return self.motion_controller.home_axes_sync()
            else:
                # Fallback for mock controllers - this will still fail but with proper error handling
                return False
        
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                success = await asyncio.get_event_loop().run_in_executor(executor, sync_home)
            
            if not success:
                raise HardwareError("Failed to home motion system")
            else:
                self.logger.info("✅ Homing completed successfully - all axes homed")
                # Add homing completion notification
                self._add_notification(
                    "🏠 System homing completed successfully!", 
                    'success', 
                    5000
                )
        except Exception as e:
            self.logger.error(f"Homing error: {e}")
            raise HardwareError("Failed to home motion system")
    
    async def _setup_scan_focus(self):
        """Setup focus for the scan at first scan point - perform object-based autofocus and set consistent focus for both cameras"""
        try:
            if self._focus_mode == 'fixed':
                self.logger.info("Focus mode is fixed, skipping focus setup")
                return
            
            # Get available cameras
            available_cameras = []
            if hasattr(self.camera_manager, 'controller') and self.camera_manager.controller:
                # Get camera IDs from the controller
                if hasattr(self.camera_manager.controller, 'cameras'):
                    for cam_id in self.camera_manager.controller.cameras.keys():
                        available_cameras.append(f"camera{cam_id}")
                else:
                    # Default to camera0 and camera1
                    available_cameras = ["camera0", "camera1"]
            else:
                self.logger.warning("No camera controller available, skipping focus setup")
                return
            
            # Import LightingSettings at the beginning for calibration flash control
            from lighting.base import LightingSettings
            
            self.logger.info(f"Setting up focus for cameras: {available_cameras}")
            
            if self._focus_mode == 'manual' and self._primary_focus_value is not None:
                # Use manual focus value for all cameras
                self.logger.info(f"Setting manual focus value {self._primary_focus_value:.3f} for all cameras")
                for camera_id in available_cameras:
                    success = await self.camera_manager.controller.set_focus_value(camera_id, self._primary_focus_value)
                    if success:
                        self._scan_focus_values[camera_id] = self._primary_focus_value
                        self.logger.info(f"✅ Set manual focus for {camera_id}: {self._primary_focus_value:.3f}")
                    else:
                        self.logger.warning(f"❌ Failed to set manual focus for {camera_id}")
                        
            elif self._focus_mode == 'auto':
                if self._focus_sync_enabled:
                    # Synchronized focus mode: calibrate primary camera and copy focus to others
                    primary_camera = available_cameras[0]
                    self.logger.info(f"🔄 Synchronized focus mode: Performing calibration on primary camera: {primary_camera}")
                    
                    # Store custom exposure settings before calibration to restore after
                    custom_exposure_backup = None
                    if hasattr(self, '_quality_settings') and self._quality_settings:
                        if 'exposure_time' in self._quality_settings:
                            custom_exposure_backup = {
                                'exposure_time': self._quality_settings['exposure_time'],
                                'analogue_gain': self._quality_settings.get('analogue_gain', None)
                            }
                            self.logger.info(f"🔄 CALIBRATION: Backing up custom exposure settings: {custom_exposure_backup}")
                    
                    # Enable flash at 30% brightness for the entire calibration process
                    try:
                        calibration_flash_settings = LightingSettings(brightness=0.3, duration_ms=0)  # Continuous light
                        await self.lighting_controller.set_brightness(['inner', 'outer'], calibration_flash_settings)
                        self.logger.info("💡 CALIBRATION: Enabled 30% flash for calibration process")
                    except Exception as flash_error:
                        self.logger.warning(f"⚠️ CALIBRATION: Could not enable flash: {flash_error}")
                    
                    try:
                        calibration_result = await self.camera_manager.controller.auto_calibrate_camera(primary_camera)
                    finally:
                        # Always turn off the flash after calibration, even if it fails
                        try:
                            off_settings = LightingSettings(brightness=0.0, duration_ms=0)
                            await self.lighting_controller.set_brightness(['inner', 'outer'], off_settings)
                            self.logger.info("💡 CALIBRATION: Disabled flash after calibration")
                        except Exception as flash_off_error:
                            self.logger.warning(f"⚠️ CALIBRATION: Could not disable flash: {flash_off_error}")
                    
                    if calibration_result and 'focus' in calibration_result:
                        focus_value = calibration_result['focus']
                        self._primary_focus_value = focus_value
                        self._scan_focus_values[primary_camera] = focus_value
                        
                        # Restore custom exposure settings if they were provided
                        if custom_exposure_backup:
                            self.logger.info(f"🔄 CALIBRATION: Restoring custom exposure settings after focus calibration")
                            if hasattr(self.camera_manager.controller, '_calibrated_settings') and primary_camera in self.camera_manager.controller._calibrated_settings:
                                # Keep the focus value but restore custom exposure
                                calibrated_settings = self.camera_manager.controller._calibrated_settings[primary_camera]
                                calibrated_settings['exposure_time'] = custom_exposure_backup['exposure_time']
                                if custom_exposure_backup['analogue_gain'] is not None:
                                    calibrated_settings['analogue_gain'] = custom_exposure_backup['analogue_gain']
                                self.logger.info(f"🔄 CALIBRATION: Updated calibrated settings to preserve custom exposure: {calibrated_settings}")
                            
                            # Also restore in our quality settings
                            self._quality_settings.update(custom_exposure_backup)
                            self.logger.info(f"🔄 CALIBRATION: Custom exposure preserved - Focus: {focus_value:.3f}, Exposure: {custom_exposure_backup['exposure_time']}")
                        else:
                            self.logger.info(f"🔄 CALIBRATION: No custom exposure settings to preserve - using auto-calibrated values")
                        
                        # Log primary camera calibration
                        exposure = calibration_result.get('exposure_time', 0)
                        gain = calibration_result.get('analogue_gain', 1.0)
                        brightness = calibration_result.get('brightness_score', 0.5)
                        
                        self.logger.info(f"✅ Primary camera calibration completed:")
                        self.logger.info(f"   Focus: {focus_value:.3f}, Exposure: {exposure/1000:.1f}ms, Gain: {gain:.2f}")
                        
                        # Update scan positions file with actual calibrated settings
                        if hasattr(self, 'current_scan') and self.current_scan and hasattr(self.current_scan, 'scan_id'):
                            try:
                                scan_output_dir = Path(self.current_scan.output_directory) if hasattr(self.current_scan, 'output_directory') else None
                                if scan_output_dir:
                                    await self._update_scan_positions_with_calibration(self.current_scan.scan_id, scan_output_dir)
                            except Exception as pos_update_error:
                                self.logger.warning(f"📋 Failed to update positions file with calibration: {pos_update_error}")
                        
                        # Apply the same focus value to all other cameras (but let them auto-expose independently)
                        for camera_id in available_cameras:
                            if camera_id != primary_camera:
                                success = await self.camera_manager.controller.set_focus_value(camera_id, focus_value)
                                if success:
                                    self._scan_focus_values[camera_id] = focus_value
                                    self.logger.info(f"✅ Synchronized focus {focus_value:.3f} applied to {camera_id}")
                                    
                                    # Let secondary cameras do their own exposure calibration
                                    try:
                                        # Enable flash for secondary camera calibration
                                        try:
                                            sec_calibration_flash_settings = LightingSettings(brightness=0.3, duration_ms=0)
                                            await self.lighting_controller.set_brightness(['inner', 'outer'], sec_calibration_flash_settings)
                                            self.logger.info(f"💡 CALIBRATION: Enabled 30% flash for {camera_id} calibration")
                                        except Exception as flash_error:
                                            self.logger.warning(f"⚠️ CALIBRATION: Could not enable flash for {camera_id}: {flash_error}")
                                        
                                        try:
                                            secondary_calib = await self.camera_manager.controller.auto_calibrate_camera(camera_id)
                                            sec_exposure = secondary_calib.get('exposure_time', 0)
                                            sec_gain = secondary_calib.get('analogue_gain', 1.0)
                                            self.logger.info(f"✅ {camera_id} exposure calibrated: {sec_exposure/1000:.1f}ms, gain: {sec_gain:.2f}")
                                        finally:
                                            # Turn off flash after secondary calibration
                                            try:
                                                off_settings = LightingSettings(brightness=0.0, duration_ms=0)
                                                await self.lighting_controller.set_brightness(['inner', 'outer'], off_settings)
                                                self.logger.info(f"💡 CALIBRATION: Disabled flash after {camera_id} calibration")
                                            except Exception as flash_off_error:
                                                self.logger.warning(f"⚠️ CALIBRATION: Could not disable flash: {flash_off_error}")
                                    except Exception as calib_error:
                                        self.logger.warning(f"⚠️ {camera_id} exposure calibration failed: {calib_error}")
                                else:
                                    self.logger.warning(f"❌ Failed to sync focus to {camera_id}")
                    else:
                        self.logger.error("❌ Primary camera calibration failed")
                        
                else:
                    # Independent focus mode: each camera gets its own autofocus
                    self.logger.info(f"🎯 Independent focus mode: Performing autofocus on each camera")
                    
                    # Add overall timeout to prevent scan from stalling  
                    focus_timeout = 40.0  # Maximum time for all cameras to calibrate (15s per camera + buffer)
                    focus_start_time = asyncio.get_event_loop().time()
                    
                    for camera_id in available_cameras:
                        # Check if we're running out of time
                        elapsed_time = asyncio.get_event_loop().time() - focus_start_time
                        if elapsed_time > focus_timeout:
                            self.logger.warning(f"⏱️ Focus setup timeout reached, skipping remaining cameras")
                            break
                            
                        self.logger.info(f"Performing camera calibration (focus + exposure) on {camera_id}...")
                        
                        try:
                            # Enable flash for calibration
                            try:
                                ind_calibration_flash_settings = LightingSettings(brightness=0.3, duration_ms=0)
                                await self.lighting_controller.set_brightness(['inner', 'outer'], ind_calibration_flash_settings)
                                self.logger.info(f"💡 CALIBRATION: Enabled 30% flash for {camera_id} calibration")
                            except Exception as flash_error:
                                self.logger.warning(f"⚠️ CALIBRATION: Could not enable flash for {camera_id}: {flash_error}")
                            
                            try:
                                # Add per-camera timeout for full calibration
                                calibration_result = await asyncio.wait_for(
                                    self.camera_manager.controller.auto_calibrate_camera(camera_id),
                                    timeout=15.0  # 15 second timeout for calibration (longer than just focus)
                                )
                            finally:
                                # Turn off flash after calibration
                                try:
                                    off_settings = LightingSettings(brightness=0.0, duration_ms=0)
                                    await self.lighting_controller.set_brightness(['inner', 'outer'], off_settings)
                                    self.logger.info(f"💡 CALIBRATION: Disabled flash after {camera_id} calibration")
                                except Exception as flash_off_error:
                                    self.logger.warning(f"⚠️ CALIBRATION: Could not disable flash: {flash_off_error}")
                            
                            if calibration_result and 'focus' in calibration_result:
                                focus_value = calibration_result['focus']
                                self._scan_focus_values[camera_id] = focus_value
                                
                                # Log calibration results with exact values that will be used in scans
                                exposure = calibration_result.get('exposure_time', 0)
                                gain = calibration_result.get('analogue_gain', 1.0)
                                brightness = calibration_result.get('brightness_score', 0.5)
                                
                                self.logger.info(f"✅ Camera calibration completed for {camera_id}:")
                                self.logger.info(f"   Focus: {focus_value:.3f}")
                                self.logger.info(f"   Exposure: {exposure}μs ({exposure/1000:.1f}ms)")
                                self.logger.info(f"   Gain: {gain:.2f} (ISO ~{int(gain*100)})")
                                self.logger.info(f"   Brightness: {brightness:.2f}")
                                
                                # Store the exact calibrated values for verification
                                if not hasattr(self, '_expected_scan_settings'):
                                    self._expected_scan_settings = {}
                                self._expected_scan_settings[camera_id] = {
                                    'exposure_time': exposure,
                                    'analogue_gain': gain,
                                    'iso_equivalent': int(gain * 100),
                                    'exposure_fraction': f"1/{int(1000000/exposure)}" if exposure > 0 else "1/30"
                                }
                            else:
                                self.logger.warning(f"⚠️ Camera calibration returned no values for {camera_id}, using defaults")
                                # Set a reasonable default focus value (middle range)
                                self._scan_focus_values[camera_id] = 0.5
                                
                        except asyncio.TimeoutError:
                            self.logger.warning(f"⏱️ Camera calibration timeout for {camera_id}, using defaults")
                            self._scan_focus_values[camera_id] = 0.5  # Default focus
                        except Exception as e:
                            self.logger.warning(f"❌ Camera calibration error for {camera_id}: {e}, using defaults")
                            self._scan_focus_values[camera_id] = 0.5  # Default focus
                    
                    # Ensure we have focus values for all cameras
                    for camera_id in available_cameras:
                        if camera_id not in self._scan_focus_values:
                            self.logger.info(f"🔧 Setting default focus for {camera_id}")
                            self._scan_focus_values[camera_id] = 0.5
                    
                    # Log summary of focus values
                    if self._scan_focus_values:
                        focus_summary = ", ".join([f"{cam}: {val:.3f}" for cam, val in self._scan_focus_values.items()])
                        self.logger.info(f"📊 Focus values set: {focus_summary}")
                    else:
                        self.logger.warning("⚠️ No focus values were set, scan will use camera defaults")
            
            # Log final focus setup summary
            if self._focus_sync_enabled and self._primary_focus_value is not None:
                self.logger.info(f"Focus setup completed. Mode: {self._focus_mode}, Sync: enabled, Value: {self._primary_focus_value:.3f}")
            else:
                focus_summary = ", ".join([f"{cam}: {val:.3f}" for cam, val in self._scan_focus_values.items()])
                self.logger.info(f"Focus setup completed. Mode: {self._focus_mode}, Sync: disabled, Values: {focus_summary}")
            
        except Exception as e:
            self.logger.error(f"Focus setup failed: {e}")
            self.logger.info("🔄 Continuing scan with camera default focus settings...")
            # Ensure we don't leave the focus system in a broken state
            self._scan_focus_values = {}
            self._primary_focus_value = None
    
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
                
                # Setup focus at first point so cameras can focus on the object
                if i == 0:
                    self.logger.info("🎯 Setting up focus at first scan point for object-based focusing")
                    await self._setup_scan_focus()
                    self.logger.info("✅ Focus setup completed at first scan point")
                
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
        """Move to a scan point with proper motion completion waiting"""
        move_start = time.time()
        
        if self.current_scan:
            self.current_scan.set_phase(ScanPhase.POSITIONING)
        
        self.logger.info(f"📐 Moving to scan point: X={point.position.x:.1f}, Y={point.position.y:.1f}, Z={point.position.z:.1f}°, C={point.position.c:.1f}°")
        
        # OPTIMIZED: Move to full 4D position with optional servo tilt calculation
        # Servo tilt is now configurable per scan, not applied by default
        try:
            # Convert core.types.Position4D to motion.base.Position4D if needed
            from motion.base import Position4D as MotionPosition4D
            motion_pos = MotionPosition4D(
                x=point.position.x, 
                y=point.position.y, 
                z=point.position.z, 
                c=point.position.c
            )
            
            # Check if servo tilt is enabled for this specific scan
            servo_mode = getattr(self.current_scan, 'servo_tilt_mode', 'none') if self.current_scan else 'none'
            
            if servo_mode == 'focus_point':
                y_focus = getattr(self.current_scan, 'servo_y_focus', 50.0) if self.current_scan else 50.0
                self.logger.info(f"🎯 Using focus point servo tilt with Y focus: {y_focus}mm")
                
                # Use the focus point servo tilt method if available
                if hasattr(self.motion_controller, 'move_with_servo_tilt'):
                    success = await self.motion_controller.move_with_servo_tilt(
                        position=motion_pos,
                        servo_mode="automatic",
                        user_y_focus=y_focus
                    )
                else:
                    self.logger.warning("Motion controller doesn't support servo tilt, using standard move")
                    success = await self.motion_controller.move_to_position(motion_pos)
                    
            elif servo_mode == 'manual':
                manual_angle = getattr(self.current_scan, 'servo_manual_angle', 0.0) if self.current_scan else 0.0
                self.logger.info(f"🎯 Using manual servo tilt: {manual_angle}°")
                
                # Use manual servo tilt if available
                if hasattr(self.motion_controller, 'move_with_servo_tilt'):
                    success = await self.motion_controller.move_with_servo_tilt(
                        position=motion_pos,
                        servo_mode="manual",
                        manual_servo_angle=manual_angle
                    )
                else:
                    motion_pos.c = manual_angle  # Set C-axis directly
                    success = await self.motion_controller.move_to_position(motion_pos)
                    
            else:
                # No servo tilt (default) - use standard position move
                success = await self.motion_controller.move_to_position(motion_pos)
                
            if not success:
                raise HardwareError(f"Failed to move to scan position {point.position}")
                
        except Exception as e:
            logger.error(f"Motion error during scan: {e}")
            raise HardwareError(f"Failed to move to scan position {point.position}: {e}")
        
        # Extended stabilization delay for scanning precision
        # This ensures all motion has completely stopped and any vibrations have settled
        scan_stabilization_delay = self.config.get('scanning', {}).get('scan_stabilization_delay', 2.0)
        general_delay = self.config.get('scanning', {}).get('default_stabilization_delay', 1.0)
        
        if scan_stabilization_delay > general_delay:
            self.logger.debug(f"⏱️ Using extended scan stabilization delay: {scan_stabilization_delay}s (vs {general_delay}s general)")
        else:
            self.logger.debug(f"⏱️ Waiting {scan_stabilization_delay}s for motion stabilization...")
        
        await asyncio.sleep(scan_stabilization_delay)
        
        self.logger.info(f"✅ Movement to scan point completed and stabilized")
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
                    zones = point.lighting_settings.get('zones', ['inner', 'outer'])
                    
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
            
            # ⚡ FLASH coordination with PROPER SYNCHRONIZATION
            flash_result = None
            try:
                if hasattr(self, 'lighting_controller') and self.lighting_controller:
                    from lighting.base import LightingSettings
                    
                    flash_settings = LightingSettings(
                        brightness=0.7,      # 70% intensity as requested
                        duration_ms=600      # Extended 600ms flash duration for better camera synchronization
                    )
                    
                    # Use both inner and outer zones for maximum illumination
                    zones_to_flash = ['inner', 'outer']
                    
                    # SYNCHRONIZED FLASH + CAPTURE using LED controller method
                    self.logger.info("⚡ Starting synchronized flash + capture...")
                    
                    # Use the dedicated synchronized method from LED controller
                    flash_result = await self.lighting_controller.trigger_for_capture(
                        self.camera_manager,
                        zones_to_flash,
                        flash_settings
                    )
                    
                    # Extract camera result from flash operation
                    camera_data_dict = None
                    if hasattr(flash_result, '__dict__') and 'camera_result' in flash_result.__dict__:
                        camera_data_dict = flash_result.camera_result
                    
                    # If no camera result from synchronized method, try direct capture
                    if not camera_data_dict:
                        self.logger.info("📸 Fallback to direct camera capture...")
                        if hasattr(self, 'camera_manager') and self.camera_manager:
                            camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
                    
                    if flash_result and hasattr(flash_result, 'success') and flash_result.success:
                        self.logger.info(f"⚡ Flash synchronized with capture - zones: {flash_result.zones_activated}")
                    else:
                        self.logger.warning(f"⚡ Flash synchronization had issues but capture completed")
                else:
                    self.logger.info("� No lighting controller available - capturing without flash")
                    # Capture without flash
                    if not hasattr(self, 'camera_manager') or not self.camera_manager:
                        raise Exception("Camera manager not available")
                    camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
            except Exception as flash_error:
                self.logger.warning(f"⚠️ Synchronized flash failed: {flash_error}, attempting capture without flash")
                # Fallback: capture without flash
                try:
                    if hasattr(self, 'camera_manager') and self.camera_manager:
                        camera_data_dict = await self.camera_manager.capture_both_cameras_simultaneously()
                    else:
                        raise Exception("Camera manager not available")
                except Exception as capture_error:
                    raise Exception(f"Both flash and capture failed: Flash={flash_error}, Capture={capture_error}")
            
            # Convert result to expected format (for both flash and non-flash cases)
            capture_results = []
            if camera_data_dict and isinstance(camera_data_dict, dict):
                # Camera manager returns: {'camera_0': {'image': array, 'metadata': {}}, 'camera_1': {...}}
                for camera_id in ['camera_0', 'camera_1']:
                    camera_result = camera_data_dict.get(camera_id)
                    
                    if camera_result and isinstance(camera_result, dict) and 'image' in camera_result:
                        # Extract image data and metadata from nested structure
                        image_data = camera_result['image']
                        camera_metadata = camera_result.get('metadata', {})
                        
                        capture_results.append({
                            'camera_id': camera_id,
                            'success': True,
                            'image_data': image_data,
                            'metadata': {
                                'scan_point': point_index, 
                                'timestamp': timestamp,
                                **camera_metadata  # Include camera capture metadata
                            },
                            'error': None
                        })
                        
                        # Log successful capture with shape
                        if hasattr(image_data, 'shape'):
                            self.logger.info(f"✅ Successfully captured from {camera_id}: shape {image_data.shape}")
                        else:
                            self.logger.info(f"✅ Successfully captured from {camera_id}: {type(image_data)}")
                            
                    else:
                        capture_results.append({
                            'camera_id': camera_id,
                            'success': False,
                            'image_data': None,
                            'metadata': {},
                            'error': 'No image data in camera result'
                        })
                        self.logger.warning(f"❌ Failed to capture from {camera_id}: invalid result structure")
                
                # Log capture summary
                successful_captures = len([r for r in capture_results if r['success']])
                self.logger.info(f"📸 Captured from {successful_captures}/{len(capture_results)} cameras at scan point {point_index}")
                
            else:
                self.logger.error("Camera manager returned invalid result format")
                capture_results = [
                    {'camera_id': 'camera_0', 'success': False, 'error': 'Invalid capture result format'},
                    {'camera_id': 'camera_1', 'success': False, 'error': 'Invalid capture result format'}
                ]
            
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
            
            # 💾 SAVE CAPTURED IMAGES TO STORAGE
            if images_captured > 0:
                try:
                    await self._save_captured_images(capture_results, point, point_index)
                except Exception as storage_error:
                    self.logger.error(f"❌ Failed to save images to storage: {storage_error}")
                    if self.current_scan:
                        self.current_scan.add_error(
                            "storage_error",
                            f"Failed to save images at point {point_index}: {storage_error}",
                            {'point_index': point_index, 'images_captured': images_captured},
                            recoverable=True
                        )
            
            self._timing_stats['capture_time'] += time.time() - capture_start
            return images_captured
            
        except Exception as e:
            self._timing_stats['capture_time'] += time.time() - capture_start
            raise HardwareError(f"Failed to capture images at point {point_index}: {e}")
    
    async def _save_captured_images(self, capture_results: List[Dict], point: ScanPoint, point_index: int):
        """Save captured images using SAME METHOD as working web interface"""
        import uuid
        import hashlib
        from storage.base import StorageMetadata, DataType
        from PIL import Image
        import io
        
        for result in capture_results:
            if result['success'] and result.get('image_data') is not None:
                try:
                    # Extract image data and metadata (same as web interface)
                    image_data = result['image_data']
                    camera_id_str = result['camera_id']  # e.g., "camera_0"
                    camera_id = int(camera_id_str.split('_')[1]) if '_' in camera_id_str else 0  # Extract numeric ID
                    camera_metadata = result.get('metadata', {})
                    
                    # 🎯 Use SAME image processing method as web interface
                    img_bytes = self._embed_scan_metadata_in_jpeg(
                        image_data, camera_id, point, point_index, camera_metadata
                    )
                    
                    # Create position data (same as web interface)
                    position_dict = {
                        'x': point.position.x,
                        'y': point.position.y,
                        'z': point.position.z,
                        'c': point.position.c
                    }
                    
                    # 📷 Get comprehensive camera metadata (same as web interface)
                    comprehensive_camera_metadata = self._get_scan_camera_metadata(camera_id, camera_metadata, 80)  # 80% flash intensity for scan
                    
                    # Get custom quality for metadata
                    metadata_quality = 95  # Default
                    if hasattr(self.camera_manager, '_quality_settings') and self.camera_manager._quality_settings:
                        metadata_quality = self.camera_manager._quality_settings.get('jpeg_quality', 95)
                    
                    # Create comprehensive metadata (same structure as web interface)
                    storage_metadata = StorageMetadata(
                        file_id=str(uuid.uuid4()),
                        original_filename=f"scan_point_{point_index:03d}_camera_{camera_id}.jpg",
                        data_type=DataType.SCAN_IMAGE,
                        file_size_bytes=len(img_bytes),
                        checksum=hashlib.sha256(img_bytes).hexdigest(),
                        creation_time=time.time(),
                        scan_session_id=None,  # Will be filled by storage manager
                        sequence_number=point_index,
                        position_data=position_dict,
                        camera_settings={
                            'camera_id': camera_id,
                            'physical_camera': camera_id_str,
                            'resolution': 'high',
                            'capture_mode': 'scan_sequence', 
                            'image_format': 'JPEG',
                            'quality': int(metadata_quality),
                            'actual_resolution': '4608x2592',
                            'sensor_type': 'Arducam 64MP',
                            'capture_timestamp': time.time(),
                            'embedded_exif': comprehensive_camera_metadata,
                            'picamera2_metadata': camera_metadata,  # Raw Picamera2 metadata
                            'comprehensive_metadata': comprehensive_camera_metadata  # Processed metadata
                        },
                        lighting_settings={
                            'flash_used': hasattr(self, 'lighting_controller') and self.lighting_controller is not None,
                            'scan_lighting': 'auto'
                        },
                        tags=['scan_capture', f'point_{point_index}', camera_id_str, 'automated_scan'],
                        file_extension='.jpg',
                        filename=f"scan_point_{point_index:03d}_camera_{camera_id}",
                        scan_point_id=f"point_{point_index:03d}",
                        camera_id=str(camera_id),
                        metadata={
                            'capture_type': 'automated_scan',
                            'scan_point_index': point_index,
                            'synchronized': True,
                            'camera_metadata': camera_metadata,
                            'scan_position': position_dict,
                            'point_coordinates': f"X:{point.position.x:.3f}, Y:{point.position.y:.3f}, Z:{point.position.z:.1f}°, C:{point.position.c:.1f}°"
                        }
                    )
                    
                    # Store file in storage manager
                    file_id = await self.storage_manager.store_file(
                        img_bytes,
                        storage_metadata
                    )
                    
                    self.logger.info(f"💾 Saved scan image from {camera_id_str} at point {point_index}: {file_id}")
                    
                except Exception as e:
                    self.logger.error(f"❌ Error saving image from {result.get('camera_id', 'unknown')}: {e}")
    
    def _embed_scan_metadata_in_jpeg(self, image_data, camera_id: int, point: ScanPoint, 
                                   point_index: int, capture_metadata=None) -> bytes:
        """Embed scan metadata into JPEG using SAME METHOD as web interface"""
        try:
            from PIL import Image
            import io
            import time
            
            # Create PIL Image from numpy array with proper color handling
            if len(image_data.shape) == 3:
                # RGB image - convert properly to avoid color inversion
                img_pil = Image.fromarray(image_data, 'RGB')
            else:
                # Grayscale image
                img_pil = Image.fromarray(image_data, 'L')
            
            # Try to use piexif for proper EXIF handling (same as web interface)
            try:
                import piexif
                
                # Create EXIF dictionary structure
                exif_dict = {
                    "0th": {},  # Main image IFD
                    "Exif": {},  # EXIF SubIFD
                    "GPS": {},  # GPS IFD
                    "1st": {},  # Thumbnail IFD
                    "thumbnail": None
                }
                
                # Basic camera identification (same as web interface)
                exif_dict["0th"][piexif.ImageIFD.Make] = "Arducam"
                exif_dict["0th"][piexif.ImageIFD.Model] = f"64MP IMX519 Camera {camera_id}"
                exif_dict["0th"][piexif.ImageIFD.Software] = "4DOF Scanner V2.0"
                exif_dict["Exif"][piexif.ExifIFD.LensModel] = "Fixed 2.8mm f/1.8"
                
                # Date and time (same as web interface)
                timestamp = time.strftime("%Y:%m:%d %H:%M:%S")
                exif_dict["0th"][piexif.ImageIFD.DateTime] = timestamp
                exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = timestamp
                exif_dict["Exif"][piexif.ExifIFD.DateTimeDigitized] = timestamp
                
                # Add scan-specific metadata
                exif_dict["0th"][piexif.ImageIFD.ImageDescription] = f"Scan Point {point_index:03d} at X:{point.position.x:.1f} Y:{point.position.y:.1f} Z:{point.position.z:.1f}° C:{point.position.c:.1f}°"
                exif_dict["0th"][piexif.ImageIFD.Artist] = "Automated 4DOF Scanner"
                
                # 📷 Extract REAL camera metadata from capture_metadata (same as web interface)
                if capture_metadata and isinstance(capture_metadata, dict):
                    self.logger.info(f"📷 Using actual Picamera2 metadata: {list(capture_metadata.keys())}")
                    
                    # Extract real values from Picamera2 metadata (same as web interface)
                    if 'ExposureTime' in capture_metadata:
                        exposure_us = capture_metadata['ExposureTime']
                        if exposure_us > 0:
                            exposure_sec = exposure_us / 1000000.0
                            if exposure_sec >= 1:
                                exif_dict["Exif"][piexif.ExifIFD.ExposureTime] = (int(exposure_sec), 1)
                            else:
                                # Convert to fraction like 1/60
                                denominator = int(1 / exposure_sec)
                                exif_dict["Exif"][piexif.ExifIFD.ExposureTime] = (1, denominator)
                    
                    if 'AnalogueGain' in capture_metadata:
                        # Convert analogue gain to ISO equivalent
                        gain = capture_metadata['AnalogueGain']
                        iso_equivalent = int(gain * 100)  # Same conversion as web interface
                        exif_dict["Exif"][piexif.ExifIFD.ISOSpeedRatings] = iso_equivalent
                    
                    if 'FocusFoM' in capture_metadata:
                        # Use fixed focal length specs
                        exif_dict["Exif"][piexif.ExifIFD.FocalLength] = (27, 10)  # 2.7mm
                    
                    if 'Lux' in capture_metadata:
                        # Light level can inform metering mode
                        exif_dict["Exif"][piexif.ExifIFD.MeteringMode] = 5  # Pattern
                
                # Fallback to reasonable defaults if no metadata available (same as web interface)
                if piexif.ExifIFD.ExposureTime not in exif_dict["Exif"]:
                    exif_dict["Exif"][piexif.ExifIFD.ExposureTime] = (1, 60)  # 1/60 second
                if piexif.ExifIFD.ISOSpeedRatings not in exif_dict["Exif"]:
                    exif_dict["Exif"][piexif.ExifIFD.ISOSpeedRatings] = 100
                if piexif.ExifIFD.FocalLength not in exif_dict["Exif"]:
                    exif_dict["Exif"][piexif.ExifIFD.FocalLength] = (27, 10)  # 2.7mm
                
                # Aperture (same as web interface)
                exif_dict["Exif"][piexif.ExifIFD.FNumber] = (18, 10)  # f/1.8
                # Calculate APEX aperture value: APEX = 2 * log2(f_number)
                import math
                f_number = 1.8
                apex_value = 2 * math.log2(f_number)
                exif_dict["Exif"][piexif.ExifIFD.ApertureValue] = (int(apex_value * 100), 100)
                
                # Flash information (scan always uses flash)
                exif_dict["Exif"][piexif.ExifIFD.Flash] = 0x0001  # Flash fired
                
                # Standard values (same as web interface)
                exif_dict["Exif"][piexif.ExifIFD.MeteringMode] = 5  # Pattern
                
                # Position data in GPS fields (creative use)
                exif_dict["GPS"][piexif.GPSIFD.GPSLatitude] = self._float_to_rational(point.position.x)
                exif_dict["GPS"][piexif.GPSIFD.GPSLongitude] = self._float_to_rational(point.position.y)
                exif_dict["GPS"][piexif.GPSIFD.GPSAltitude] = self._float_to_rational(point.position.z)
                
                # Convert EXIF dict to bytes
                exif_bytes = piexif.dump(exif_dict)
                
                # Save to bytes with EXIF
                output = io.BytesIO()
                img_pil.save(output, format='JPEG', quality=95, exif=exif_bytes)
                return output.getvalue()
                
            except ImportError:
                self.logger.warning("piexif not available, saving without EXIF metadata")
                # Fallback without EXIF
                output = io.BytesIO()
                # Use custom quality settings if available
                jpeg_quality = 95  # Default
                if hasattr(self, 'camera_manager') and hasattr(self.camera_manager, '_quality_settings'):
                    jpeg_quality = self.camera_manager._quality_settings.get('jpeg_quality', 95)
                
                img_pil.save(output, format='JPEG', quality=int(jpeg_quality))
                return output.getvalue()
                
        except Exception as e:
            self.logger.error(f"Failed to embed metadata in JPEG: {e}")
            # Ultra-fallback: simple cv2 encoding
            import cv2
            # Use the same custom quality for fallback encoding
            success, encoded_image = cv2.imencode('.jpg', image_data, [cv2.IMWRITE_JPEG_QUALITY, int(jpeg_quality)])
            if success:
                return encoded_image.tobytes()
            else:
                raise Exception(f"Failed to encode image: {e}")
    
    def _float_to_rational(self, value: float) -> tuple:
        """Convert float to rational number for EXIF (same as web interface)"""
        # Simple rational approximation
        if value == 0:
            return ((0, 1), (0, 1), (0, 1))
        
        # Convert to degrees, minutes, seconds format for position
        degrees = int(abs(value))
        minutes_float = (abs(value) - degrees) * 60
        minutes = int(minutes_float)
        seconds = int((minutes_float - minutes) * 60 * 1000)  # milliseconds precision
        
        return ((degrees, 1), (minutes, 1), (seconds, 1000))
    
    def _get_scan_camera_metadata(self, camera_id: int, capture_metadata: dict, flash_intensity: int) -> dict:
        """Get comprehensive camera metadata for scan (same as web interface)"""
        try:
            # Use camera controller to get complete metadata (same approach as web interface)
            if hasattr(self, 'camera_manager') and self.camera_manager:
                if hasattr(self.camera_manager, 'controller') and self.camera_manager.controller:
                    controller = self.camera_manager.controller
                    
                    # Get complete metadata from camera controller
                    if hasattr(controller, 'create_complete_camera_metadata'):
                        complete_metadata = controller.create_complete_camera_metadata(camera_id, capture_metadata)
                        
                        # Extract for storage format (same as web interface)
                        specs = complete_metadata.get('camera_specifications', {})
                        dynamic = complete_metadata.get('capture_settings', {})
                        
                        return {
                            'make': specs.get('make', 'Arducam'),
                            'model': specs.get('model', f'64MP Camera {camera_id}'),
                            'sensor_model': specs.get('sensor_model', 'Sony IMX519'),
                            'focal_length': f"{specs.get('focal_length_mm', 2.74)}mm",
                            'focal_length_35mm_equiv': f"{specs.get('focal_length_35mm_equiv', 20.2):.1f}mm",
                            'aperture': specs.get('aperture_string', 'f/1.8'),
                            'exposure_time': dynamic.get('exposure_time', self._extract_exposure_from_metadata(capture_metadata)),
                            'iso': dynamic.get('iso_equivalent', self._extract_iso_from_metadata(capture_metadata)),
                            'metering_mode': 'pattern',
                            'flash_fired': flash_intensity > 0,
                            'lens_position': dynamic.get('focus_position', capture_metadata.get('LensPosition', 'auto') if capture_metadata else 'auto'),
                            'focus_fom': dynamic.get('focus_measure', capture_metadata.get('FocusFoM', 0) if capture_metadata else 0),
                            'color_temperature': f"{dynamic.get('color_temperature_k', capture_metadata.get('ColourTemperature', 'auto') if capture_metadata else 'auto')}K",
                            'lux_level': dynamic.get('light_level_lux', capture_metadata.get('Lux', 0) if capture_metadata else 0),
                            'calibration_source': specs.get('calibration_source', 'estimated')
                        }
            
            # Fallback if camera controller not available (same as web interface)
            self.logger.warning("📷 Camera controller not available, using fallback metadata")
            return {
                'make': 'Arducam',
                'model': f'64MP Camera {camera_id}',
                'sensor_model': 'Sony IMX519',
                'focal_length': '2.74mm (estimated)',
                'aperture': 'f/1.8 (estimated)',
                'exposure_time': self._extract_exposure_from_metadata(capture_metadata),
                'iso': self._extract_iso_from_metadata(capture_metadata),
                'metering_mode': 'pattern',
                'flash_fired': flash_intensity > 0,
                'lens_position': capture_metadata.get('LensPosition', 'auto') if capture_metadata else 'auto',
                'focus_fom': capture_metadata.get('FocusFoM', 0) if capture_metadata else 0,
                'color_temperature': f"{capture_metadata.get('ColourTemperature', 'auto')}K" if capture_metadata else 'auto',
                'lux_level': capture_metadata.get('Lux', 0) if capture_metadata else 0,
                'calibration_source': 'fallback'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get camera metadata: {e}")
            return {
                'make': 'Arducam',
                'model': f'64MP Camera {camera_id}',
                'focal_length': 'unknown',
                'aperture': 'unknown',
                'exposure_time': 'unknown',
                'iso': 100,
                'flash_fired': flash_intensity > 0
            }
    
    def _extract_exposure_from_metadata(self, capture_metadata: dict) -> str:
        """Extract exposure time from Picamera2 metadata (same as web interface)"""
        if not capture_metadata:
            return '1/60s'
        
        if 'ExposureTime' in capture_metadata:
            exposure_us = capture_metadata['ExposureTime']
            exposure_sec = exposure_us / 1000000.0
            if exposure_sec >= 1:
                return f"{exposure_sec:.2f}s"
            else:
                return f"1/{int(1/exposure_sec)}s"
        
        return '1/60s'  # fallback
    
    def _extract_iso_from_metadata(self, capture_metadata: dict) -> int:
        """Extract ISO equivalent from Picamera2 metadata (same as web interface)"""
        if not capture_metadata:
            return 100
        
        if 'AnalogueGain' in capture_metadata:
            gain = capture_metadata['AnalogueGain']
            return int(gain * 100)  # Same conversion as web interface
        
        return 100  # fallback
    
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
            # Generate final report (removed final homing)
            await self._generate_scan_report()
            
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}")
        
        finally:
            # Clear all scan state to allow new scans
            self.current_pattern = None
            self.current_scan = None
            self.scan_task = None
            self._stop_requested = False
            self._emergency_stop = False
            self.logger.info("Scan state fully cleared - ready for new scan")
    
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
        if not self.current_scan:
            self.logger.info("No active scan to stop")
            return False
        
        # Check if scan is in a state that can be stopped
        if self.current_scan.status not in [ScanStatus.RUNNING, ScanStatus.PAUSED, ScanStatus.INITIALIZING]:
            self.logger.info(f"Scan cannot be stopped from status: {self.current_scan.status}")
            # If scan is in a final state but current_scan is still set, clear it
            if self.current_scan.status in [ScanStatus.COMPLETED, ScanStatus.FAILED, ScanStatus.CANCELLED]:
                self.current_scan = None
                self.current_pattern = None
                self._stop_requested = False
            return False
        
        # Request stop and mark scan as cancelled
        self._stop_requested = True
        self.current_scan.cancel()
        self.logger.info("Scan stop requested and marked as cancelled")
        
        # If there's a scan task running, try to cancel it safely
        if self.scan_task and not self.scan_task.done():
            try:
                # Try to cancel the task instead of waiting for it
                self.scan_task.cancel()
                self.logger.info("Scan task cancelled")
                
                # Give a brief moment for cancellation to propagate
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.logger.warning(f"Could not cancel scan task: {e}, forcing cleanup")
        
        # Ensure state is cleared
        self.current_scan = None
        self.current_pattern = None
        self.scan_task = None
        self._stop_requested = False
        
        self.logger.info("Scan stopped and state cleared")
        return True
    
    async def force_stop_all_operations(self) -> bool:
        """Force stop all operations - for emergency dashboard use"""
        try:
            self.logger.warning("🛑 FORCE STOP: Canceling all operations from dashboard")
            
            # Set all stop flags
            self._stop_requested = True
            self._emergency_stop = True
            
            # Force cancel any active scan
            if self.current_scan:
                self.current_scan.cancel()
                self.logger.info(f"Force cancelled active scan: {self.current_scan.scan_id}")
            
            # Cancel any running scan task
            if self.scan_task and not self.scan_task.done():
                self.scan_task.cancel()
                self.logger.info("Force cancelled scan task")
                await asyncio.sleep(0.1)  # Brief wait for cancellation
            
            # Force clear all state
            self.current_scan = None
            self.current_pattern = None
            self.scan_task = None
            self._stop_requested = False
            self._emergency_stop = False
            
            # Add notification for user feedback
            self._add_notification("🛑 All operations stopped", "warning", 3000)
            
            self.logger.warning("🛑 FORCE STOP completed - all operations cancelled")
            return True
            
        except Exception as e:
            self.logger.error(f"Error in force stop: {e}")
            # Still try to clear state even if error occurred
            self.current_scan = None
            self.current_pattern = None
            self.scan_task = None
            self._stop_requested = False
            self._emergency_stop = False
            return False
    
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
                                 radius: float,
                                 y_range: tuple[float, float],
                                 y_step: float = 20.0,
                                 y_positions: Optional[List[float]] = None,
                                 z_rotations: Optional[List[float]] = None,
                                 c_angles: Optional[List[float]] = None,
                                 servo_tilt_params: Optional[Dict[str, Any]] = None):
        """
        Create a cylindrical scan pattern for turntable scanner with fixed radius
        
        Args:
            radius: Fixed camera radius (distance from object center) in mm
            y_range: Vertical camera movement range (start, end) in mm  
            y_step: Vertical step size in mm
            y_positions: Explicit Y positions in mm (overrides y_range/y_step if provided)
            z_rotations: Turntable rotation angles in degrees (None for default)
            c_angles: Camera pivot angles in degrees (None for default, overridden by servo_tilt_params)
            servo_tilt_params: Servo tilt configuration dict with 'mode', 'manual_angle', 'y_focus'
        """
        from .scan_patterns import CylindricalPatternParameters, CylindricalScanPattern
        
        # Create pattern parameters with fixed radius (x_start = x_end)
        # Ensure Z-axis rotations are provided for cylindrical scan
        if z_rotations is None or len(z_rotations) == 0:
            z_rotations = list(range(0, 360, 60))  # Default: 6 positions
            logger.warning(f"No Z-rotations provided for cylindrical scan, using default: {z_rotations}")
            
        # Calculate servo angles based on tilt parameters
        if servo_tilt_params and servo_tilt_params.get('mode') != 'none':
            # Generate Y positions if not provided
            if y_positions is None:
                y_positions = []
                y = y_range[0]
                while y <= y_range[1]:
                    y_positions.append(y)
                    y += y_step
            
            if servo_tilt_params['mode'] == 'focus_point':
                # Calculate servo angle for each Y position to focus on target
                import math
                y_focus = servo_tilt_params['y_focus']
                c_angles = []
                
                for y_pos in y_positions:
                    # Calculate focus offset from current Y position to target focus point
                    focus_offset = y_focus - y_pos
                    # Calculate servo angle: angle = atan(offset / radius)
                    servo_angle = math.atan(focus_offset / radius) * (180.0 / math.pi)
                    c_angles.append(servo_angle)
                
                logger.info(f"🎯 Calculated {len(c_angles)} servo focus angles for Y positions:")
                for y_pos, angle in zip(y_positions, c_angles):
                    logger.info(f"   Y={y_pos}mm -> Servo={angle:.1f}° (focus={y_focus}mm, offset={y_focus-y_pos:.1f}mm)")
                    
            elif servo_tilt_params['mode'] == 'manual':
                # Use manual angle for all positions
                manual_angle = servo_tilt_params['manual_angle']
                c_angles = [manual_angle] * len(y_positions) if y_positions else [manual_angle]
                logger.info(f"🎯 Using manual servo angle: {manual_angle}° for {len(c_angles)} positions")
        else:
            # No servo tilt or legacy c_angles parameter
            if c_angles is None or len(c_angles) == 0:
                c_angles = [0.0]  # Default: servo at center
                logger.info("🎯 Using default servo angle: 0° (no tilt)")
            else:
                logger.info(f"🎯 Using provided servo angles: {c_angles}")
        
        parameters = CylindricalPatternParameters(
            x_start=radius,      # Fixed camera radius
            x_end=radius,        # Same as start for fixed position
            y_start=y_range[0],
            y_end=y_range[1],
            x_step=1.0,          # Not used when x_start = x_end
            y_step=y_step,
            y_positions=y_positions,  # 🎯 NEW: Explicit Y positions
            z_rotations=z_rotations,  # Z-axis: cylinder rotation angles
            c_angles=c_angles,        # C-axis: calculated servo angles
            safety_margin=0.5
        )
        
        # Log final pattern configuration
        logger.info(f"📐 Final cylindrical pattern: C-axis (servo) angles={c_angles} ({len(c_angles)} angles)")
        
        # Generate pattern ID
        pattern_id = f"cylindrical_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return CylindricalScanPattern(pattern_id=pattern_id, parameters=parameters)
    
    # Focus Control Methods
    def set_focus_mode(self, mode: str) -> bool:
        """
        Set the focus mode for scans
        
        Args:
            mode: Focus mode ('auto', 'manual', or 'fixed')
                - 'auto': Perform autofocus before scan and apply to all cameras
                - 'manual': Use specified manual focus value
                - 'fixed': Use camera's default autofocus behavior
                
        Returns:
            True if mode was set successfully
        """
        if mode not in ['auto', 'manual', 'fixed']:
            self.logger.error(f"Invalid focus mode: {mode}. Must be 'auto', 'manual', or 'fixed'")
            return False
            
        self._focus_mode = mode
        self.logger.info(f"Focus mode set to: {mode}")
        return True
    
    def set_manual_focus_value(self, focus_value: float) -> bool:
        """
        Set manual focus value for all cameras (only used in manual mode)
        
        Args:
            focus_value: Focus value (0.0 = near, 1.0 = infinity)
            
        Returns:
            True if value was set successfully
        """
        if not 0.0 <= focus_value <= 1.0:
            self.logger.error(f"Invalid focus value: {focus_value}. Must be between 0.0 and 1.0")
            return False
            
        self._primary_focus_value = focus_value
        self.logger.info(f"Manual focus value set to: {focus_value:.3f}")
        return True
        
    def set_manual_focus_value_per_camera(self, camera_values: Dict[str, float]) -> bool:
        """
        Set individual manual focus values for each camera
        
        Args:
            camera_values: Dictionary mapping camera_id to focus value (0.0-1.0)
            
        Returns:
            True if all values were set successfully
        """
        for camera_id, value in camera_values.items():
            if not 0.0 <= value <= 1.0:
                self.logger.error(f"Invalid focus value for {camera_id}: {value}. Must be between 0.0 and 1.0")
                return False
        
        self._scan_focus_values = camera_values.copy()
        self._focus_sync_enabled = False  # Individual values means no sync
        
        focus_summary = ", ".join([f"{cam}: {val:.3f}" for cam, val in camera_values.items()])
        self.logger.info(f"Individual manual focus values set: {focus_summary}")
        return True
        
    def set_focus_sync_enabled(self, enabled: bool):
        """Enable or disable focus synchronization between cameras
        
        Args:
            enabled: If True, cameras will use the same focus value.
                    If False, each camera will have independent focus.
        """
        self._focus_sync_enabled = enabled
        self.logger.info(f"Focus synchronization {'enabled' if enabled else 'disabled'}")
        
    def is_focus_sync_enabled(self) -> bool:
        """Check if focus synchronization is enabled"""
        return self._focus_sync_enabled
    
    def get_focus_settings(self) -> Dict[str, Any]:
        """
        Get current focus settings
        
        Returns:
            Dictionary with current focus mode, sync setting, and values
        """
        return {
            'focus_mode': self._focus_mode,
            'sync_enabled': self._focus_sync_enabled,
            'primary_value': self._primary_focus_value,
            'camera_values': self._scan_focus_values.copy()
        }
    
    async def perform_autofocus(self, camera_id: Optional[str] = None) -> Optional[float]:
        """
        Perform autofocus on specified camera or primary camera
        
        Args:
            camera_id: Camera to focus (defaults to camera0)
            
        Returns:
            Focus value if successful, None otherwise
        """
        try:
            if not hasattr(self.camera_manager, 'controller') or not self.camera_manager.controller:
                self.logger.error("No camera controller available for autofocus")
                return None
            
            target_camera = camera_id or "camera0"
            self.logger.info(f"Performing manual autofocus on {target_camera}")
            
            focus_value = await self.camera_manager.controller.auto_focus_and_get_value(target_camera)
            
            if focus_value is not None:
                self.logger.info(f"✅ Autofocus completed: {focus_value:.3f}")
            else:
                self.logger.error("❌ Autofocus failed")
                
            return focus_value
            
        except Exception as e:
            self.logger.error(f"Autofocus error: {e}")
            return None
    
    def _extract_relevant_pattern_parameters(self, pattern_params_dict: dict) -> dict:
        """Extract only the relevant parameters specific to the pattern type, excluding base class parameters"""
        # Define which parameters are specific to each pattern type
        cylindrical_specific = {
            'x_start', 'x_end', 'x_step', 'y_start', 'y_end', 'y_step', 'y_positions',
            'z_rotations', 'z_step', 'c_angles', 'c_step', 'scan_pattern'
        }
        
        grid_specific = {
            'x_start', 'x_end', 'x_step', 'y_start', 'y_end', 'y_step', 
            'z_height', 'spacing', 'scan_pattern'
        }
        
        # Filter out base PatternParameters that aren't pattern-specific
        base_params_to_exclude = {
            'min_x', 'max_x', 'min_y', 'max_y', 'min_z', 'max_z', 'min_c', 'max_c',
            'overlap_percentage', 'max_distance', 'max_feedrate', 'safety_margin'
        }
        
        # Return only the relevant parameters
        return {k: v for k, v in pattern_params_dict.items() 
                if k not in base_params_to_exclude}
    
    async def test_lighting_zones(self) -> Dict[str, Any]:
        """Test both inner and outer LED flash zones"""
        self.logger.info("🔸 Testing lighting zones...")
        
        results = {
            'inner': {'success': False, 'error': None},
            'outer': {'success': False, 'error': None},
            'zones_available': []
        }
        
        try:
            if not self.lighting_controller or not self.lighting_controller.is_available():
                results['error'] = "Lighting controller not available"
                return results
            
            # Get available zones
            if hasattr(self.lighting_controller, 'controller'):
                actual_controller = self.lighting_controller.controller
                if hasattr(actual_controller, 'list_zones'):
                    results['zones_available'] = await actual_controller.list_zones()
                    self.logger.info(f"🔸 Available zones: {results['zones_available']}")
            
            # Test inner zone
            try:
                if 'inner' in results['zones_available']:
                    from lighting.base import LightingSettings
                    settings = LightingSettings(
                        brightness=0.5,  # 50% for testing
                        duration_ms=200  # 200ms flash
                    )
                    
                    flash_result = await self.lighting_controller.flash(['inner'], settings)
                    results['inner']['success'] = flash_result.success if hasattr(flash_result, 'success') else bool(flash_result)
                    self.logger.info(f"✅ Inner zone test: {'SUCCESS' if results['inner']['success'] else 'FAILED'}")
                    
                    # Small delay between tests
                    await asyncio.sleep(0.5)
                else:
                    results['inner']['error'] = "Inner zone not found in configuration"
            except Exception as e:
                results['inner']['error'] = str(e)
                self.logger.error(f"❌ Inner zone test failed: {e}")
            
            # Test outer zone
            try:
                if 'outer' in results['zones_available']:
                    from lighting.base import LightingSettings
                    settings = LightingSettings(
                        brightness=0.5,  # 50% for testing  
                        duration_ms=200  # 200ms flash
                    )
                    
                    flash_result = await self.lighting_controller.flash(['outer'], settings)
                    results['outer']['success'] = flash_result.success if hasattr(flash_result, 'success') else bool(flash_result)
                    self.logger.info(f"✅ Outer zone test: {'SUCCESS' if results['outer']['success'] else 'FAILED'}")
                else:
                    results['outer']['error'] = "Outer zone not found in configuration"
            except Exception as e:
                results['outer']['error'] = str(e)
                self.logger.error(f"❌ Outer zone test failed: {e}")
            
            # Test both zones simultaneously
            try:
                if 'inner' in results['zones_available'] and 'outer' in results['zones_available']:
                    from lighting.base import LightingSettings
                    settings = LightingSettings(
                        brightness=0.3,  # 30% for combined test
                        duration_ms=300  # 300ms flash
                    )
                    
                    flash_result = await self.lighting_controller.flash(['inner', 'outer'], settings)
                    combined_success = flash_result.success if hasattr(flash_result, 'success') else bool(flash_result)
                    results['combined'] = {'success': combined_success}
                    self.logger.info(f"✅ Combined zones test: {'SUCCESS' if combined_success else 'FAILED'}")
            except Exception as e:
                results['combined'] = {'success': False, 'error': str(e)}
                self.logger.error(f"❌ Combined zones test failed: {e}")
                
        except Exception as e:
            self.logger.error(f"❌ Lighting zone test error: {e}")
            results['error'] = str(e)
        
        return results
    
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