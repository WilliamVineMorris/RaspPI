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
from typing import Dict, Any, Optional, List, Union, Protocol

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

class ScanOrchestrator:
    """
    Main orchestration engine for 3D scanning operations
    
    Coordinates motion controller, cameras, scan patterns, and state management
    to perform complete scanning workflows with error recovery and progress tracking.
    """
    
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
from typing import Dict, Any, Optional, List, Union, Protocol

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
            
            # Create dummy file
            try:
                filepath.write_text(f"Mock image data for {camera_id}")
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
        
        # Initialize components (using mocks for now)
        self.motion_controller = MockMotionController(config_manager)
        self.camera_manager = MockCameraManager(config_manager)
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
        
        self.logger = logging.getLogger(__name__)
        
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
                if task.exception():
                    self.logger.error(f"Scan task failed with exception: {task.exception()}")
            except asyncio.CancelledError:
                self.logger.info("Scan task was cancelled")
        
        self.scan_task.add_done_callback(task_done_callback)
        
        return self.current_scan
    
    async def _execute_scan(self):
        """Main scan execution loop"""
        if not self.current_scan or not self.current_pattern:
            return
        
        try:
            # Start the scan
            self.current_scan.start()
            self.logger.info(f"Scan {self.current_scan.scan_id} started")
            
            # Home the system
            await self._home_system()
            
            # Execute scan points
            await self._execute_scan_points()
            
            # Complete the scan
            if not self._stop_requested and not self._emergency_stop:
                self.current_scan.complete()
                self.logger.info(f"Scan {self.current_scan.scan_id} completed successfully")
            else:
                self.current_scan.cancel()
                self.logger.info(f"Scan {self.current_scan.scan_id} cancelled")
                
        except Exception as e:
            self.logger.error(f"Scan execution failed: {e}")
            if self.current_scan:
                self.current_scan.fail(str(e), {'exception_type': type(e).__name__})
        
        finally:
            await self._cleanup_scan()
    
    async def _home_system(self):
        """Home the motion system"""
        if self._check_stop_conditions():
            return
        
        self.current_scan.set_phase(ScanPhase.HOMING)
        self.logger.info("Homing motion system")
        
        if not await self.motion_controller.home():
            raise HardwareError("Failed to home motion system")
    
    async def _execute_scan_points(self):
        """Execute all scan points"""
        if not self.current_pattern or not self.current_scan:
            return
        
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
        
        # Set Z height if specified
        if point.position.z is not None:
            if not await self.motion_controller.move_z_to(point.position.z):
                raise HardwareError(f"Failed to move to Z position {point.position.z}")
        
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
                    'timestamp': timestamp
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
            self.current_scan.pause()
            self._pause_requested = False
            
            # Wait until resume is requested (with timeout to prevent infinite loops)
            pause_timeout = 30.0  # 30 second timeout
            pause_start = time.time()
            
            while self.current_scan.status == ScanStatus.PAUSED:
                if self._stop_requested or self._emergency_stop:
                    break
                if time.time() - pause_start > pause_timeout:
                    self.logger.warning("Pause timeout reached, auto-resuming scan")
                    self.current_scan.resume()
                    break
                await asyncio.sleep(0.1)
    
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
    
    def create_grid_pattern(self, 
                           x_range: tuple[float, float],
                           y_range: tuple[float, float],
                           spacing: float,
                           z_height: Optional[float] = None,
                           rotations: Optional[List[float]] = None) -> GridScanPattern:
        """Create a grid scan pattern"""
        from .scan_patterns import GridPatternParameters
        
        # Handle Z height - if single height provided, use small range
        if z_height is not None:
            min_z = z_height
            max_z = z_height + 0.1  # Small increment to satisfy validation
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
                                 c_angles: Optional[List[float]] = None) -> 'CylindricalScanPattern':
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