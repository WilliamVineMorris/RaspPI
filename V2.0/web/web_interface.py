"""
Flask Web Interface for 3D Scanner Control

Provides a web-based interface for controlling and monitoring the 3D scanner system.
Integrates directly with the ScanOrchestrator for robust command/data transfer.

Features:
- Real-time system monitoring via WebSocket
- Manual motion control with safety limits
- Scan management and monitoring
- Live camera feeds
- Robust error handling and validation

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import asdict

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
from flask import Flask, render_template, jsonify, request, Response, redirect, url_for
from werkzeug.exceptions import BadRequest

# Import scanner modules
try:
    from core.exceptions import ScannerSystemError, HardwareError
    from core.types import Position4D
    from scanning.scan_patterns import GridScanPattern, CylindricalScanPattern
    from scanning.scan_state import ScanStatus, ScanPhase
    from scanning.scan_orchestrator import ScanOrchestrator
    SCANNER_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import scanner modules: {e}")
    print("Running in development mode without full scanner integration")
    SCANNER_MODULES_AVAILABLE = False

# Import timing logger (optional)
try:
    from timing_logger import timing_logger
    TIMING_LOGGER_AVAILABLE = True
    print("🔍 Timing logger enabled for command analysis")
except ImportError as e:
    TIMING_LOGGER_AVAILABLE = False
    print(f"⚠️ Timing logger not available: {e}")
    # Create dummy timing logger for compatibility
    class DummyTimingLogger:
        def log_backend_received(self, *args, **kwargs): return "dummy_id"
        def log_backend_start(self, *args, **kwargs): pass
        def log_motion_controller_start(self, *args, **kwargs): pass
        def log_backend_complete(self, *args, **kwargs): pass
        def log_error(self, *args, **kwargs): pass
    timing_logger = DummyTimingLogger()
    
    # Create mock classes for development
    class ScannerSystemError(Exception):
        pass
    
    class HardwareError(Exception):
        pass
    
    class ScanStatus:
        IDLE = "idle"
        RUNNING = "running"
        PAUSED = "paused"
        COMPLETED = "completed"
        ERROR = "error"
    
    class ScanPhase:
        INITIALIZATION = "initialization"
        SCANNING = "scanning"
        PROCESSING = "processing"
        COMPLETED = "completed"
    
    class GridScanPattern:
        def __init__(self, *args, **kwargs):
            pass
    
    class CylindricalScanPattern:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockMotionController:
        def __init__(self):
            self.current_position = Position4D(x=0.0, y=0.0, z=0.0, c=0.0)
        
        async def move_relative(self, delta: Position4D, feedrate: Optional[float] = None) -> bool:
            # Simulate successful movement by updating position
            self.current_position.x += delta.x
            self.current_position.y += delta.y
            self.current_position.z += delta.z
            self.current_position.c += delta.c
            return True
        
        async def get_position(self) -> Position4D:
            return self.current_position
        
        async def home_all(self) -> bool:
            self.current_position = Position4D(x=0.0, y=0.0, z=0.0, c=0.0)
            return True

    class ScanOrchestrator:
        def __init__(self, *args, **kwargs):
            self.scan_status = ScanStatus.IDLE
            # Create mock motion controller
            self.motion_controller = MockMotionController()
        
        async def get_status(self):
            return {"status": self.scan_status}
        
        async def initialize_system(self):
            return True
        
        async def emergency_stop(self):
            return True
        
        def get_camera_status(self):
            return {"camera_active": False, "last_capture": None}

logger = logging.getLogger(__name__)


class WebInterfaceError(Exception):
    """Web interface specific errors"""
    pass


class CommandValidator:
    """Validates web interface commands for safety and correctness"""
    
    # Safety limits for manual control - Updated to match scanner_config.yaml
    POSITION_LIMITS = {
        'x': (0.0, 200.0),     # mm - Linear axis: 0 to max limit
        'y': (0.0, 200.0),     # mm - Linear axis: 0 to max limit (homes to 200)
        'z': (-180.0, 180.0),  # degrees - Rotational axis: continuous rotation
        'c': (-90.0, 90.0)     # degrees - Servo axis: ±90 degrees
    }
    
    STEP_SIZES = [0.1, 0.5, 1.0, 5.0, 10.0, 25.0]  # mm
    MAX_FEED_RATE = 1000.0  # mm/min
    
    @classmethod
    def validate_move_command(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate manual movement command"""
        try:
            axis = data.get('axis', '').lower()
            distance = float(data.get('distance', 0))
            
            if axis not in cls.POSITION_LIMITS:
                raise ValueError(f"Invalid axis: {axis}")
            
            if abs(distance) > 50.0:  # Single move limit
                raise ValueError(f"Move distance too large: {distance}mm")
            
            # Validate step size
            step_size = abs(distance)
            if step_size not in cls.STEP_SIZES:
                raise ValueError(f"Invalid step size: {step_size}mm")
            
            return {
                'axis': axis,
                'distance': distance,
                'validated': True
            }
            
        except (ValueError, TypeError) as e:
            raise WebInterfaceError(f"Invalid move command: {e}")
    
    @classmethod
    def validate_position_command(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate absolute position command"""
        try:
            position = {}
            for axis in ['x', 'y', 'z', 'c']:
                if axis in data:
                    value = float(data[axis])
                    min_val, max_val = cls.POSITION_LIMITS[axis]
                    if not (min_val <= value <= max_val):
                        raise ValueError(f"{axis.upper()} position {value} outside limits [{min_val}, {max_val}]")
                    position[axis] = value
            
            if not position:
                raise ValueError("No valid position coordinates provided")
            
            return position
            
        except (ValueError, TypeError) as e:
            raise WebInterfaceError(f"Invalid position command: {e}")
    
    @classmethod
    def validate_scan_pattern(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate scan pattern parameters"""
        try:
            pattern_type = data.get('pattern_type', '').lower()
            
            if pattern_type == 'grid':
                return cls._validate_grid_pattern(data)
            elif pattern_type == 'cylindrical':
                return cls._validate_cylindrical_pattern(data)
            else:
                raise ValueError(f"Unknown pattern type: {pattern_type}")
                
        except (ValueError, TypeError) as e:
            raise WebInterfaceError(f"Invalid scan pattern: {e}")
    
    @classmethod
    def _validate_grid_pattern(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate grid pattern parameters"""
        x_range = (float(data.get('x_min', -50)), float(data.get('x_max', 50)))
        y_range = (float(data.get('y_min', -50)), float(data.get('y_max', 50)))
        spacing = float(data.get('spacing', 5.0))
        z_height = float(data.get('z_height', 25.0))
        
        # Validate ranges
        if x_range[0] >= x_range[1] or y_range[0] >= y_range[1]:
            raise ValueError("Invalid coordinate ranges")
        
        if not (1.0 <= spacing <= 25.0):
            raise ValueError(f"Spacing {spacing}mm outside valid range [1.0, 25.0]")
        
        if not (5.0 <= z_height <= 50.0):
            raise ValueError(f"Z height {z_height}mm outside valid range [5.0, 50.0]")
        
        return {
            'pattern_type': 'grid',
            'x_range': x_range,
            'y_range': y_range,
            'spacing': spacing,
            'z_height': z_height,
            'validated': True
        }
    
    @classmethod
    def _validate_cylindrical_pattern(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate cylindrical pattern parameters"""
        x_range = (float(data.get('x_min', -50)), float(data.get('x_max', 50)))
        y_range = (float(data.get('y_min', -50)), float(data.get('y_max', 50)))
        z_rotations = [float(r) for r in data.get('z_rotations', [0, 90, 180, 270])]
        c_angles = [float(a) for a in data.get('c_angles', [0])]
        
        # Validate ranges
        if x_range[0] >= x_range[1] or y_range[0] >= y_range[1]:
            raise ValueError("Invalid coordinate ranges")
        
        # Validate rotations
        for rotation in z_rotations:
            if not (-360.0 <= rotation <= 360.0):
                raise ValueError(f"Z rotation {rotation}° outside valid range")
        
        for angle in c_angles:
            if not (-360.0 <= angle <= 360.0):
                raise ValueError(f"C angle {angle}° outside valid range")
        
        return {
            'pattern_type': 'cylindrical',
            'x_range': x_range,
            'y_range': y_range,
            'z_rotations': z_rotations,
            'c_angles': c_angles,
            'validated': True
        }


class ScannerWebInterface:
    """
    Flask-based web interface for the 3D scanner system
    
    Provides robust command/data transfer between web UI and scanner orchestrator
    with comprehensive error handling and real-time updates.
    """
    
    def __init__(self, orchestrator=None):
        self.orchestrator = orchestrator
        self.logger = logging.getLogger(__name__)
        
        # Flask app setup
        self.app = Flask(__name__,
                        template_folder=str(Path(__file__).parent / 'templates'),
                        static_folder=str(Path(__file__).parent / 'static'))
        self.app.config['SECRET_KEY'] = 'scanner_control_secret_key'
        
        # Web interface state (simplified without SocketIO for now)
        self._connected_clients = set()
        self._last_status_update = None
        self._camera_streams = {}
        self._running = False
        
        # Setup routes
        self._setup_routes()
        self._setup_orchestrator_integration()
        
        # Integrate feedrate management system
        self._setup_feedrate_integration()
        
        self.logger.info("Scanner web interface initialized with enhanced feedrate management")
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        # Main pages
        @self.app.route('/')
        def dashboard():
            """Main dashboard page"""
            try:
                status = self._get_system_status()
                return render_template('dashboard.html', status=status)
            except Exception as e:
                self.logger.error(f"Dashboard error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/manual')
        def manual():
            """Manual control page"""
            try:
                status = self._get_system_status()
                return render_template('manual.html', 
                                     status=status, 
                                     step_sizes=CommandValidator.STEP_SIZES,
                                     position_limits=CommandValidator.POSITION_LIMITS)
            except Exception as e:
                self.logger.error(f"Manual control error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/scans')
        def scans():
            """Scan management page"""
            try:
                status = self._get_system_status()
                scan_history = self._get_scan_history()
                return render_template('scans.html', status=status, history=scan_history)
            except Exception as e:
                self.logger.error(f"Scan management error: {e}")
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/settings')
        def settings():
            """Settings and diagnostics page"""
            try:
                status = self._get_system_status()
                config = self._get_system_config()
                return render_template('settings.html', status=status, config=config)
            except Exception as e:
                self.logger.error(f"Settings error: {e}")
                return jsonify({'error': str(e)}), 500
        
        # API endpoints for robust command/data transfer
        @self.app.route('/api/status')
        def api_status():
            """Get current system status with performance monitoring"""
            start_time = time.time()
            try:
                status_data = self._get_system_status()
                response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
                
                # Log slow responses for debugging web UI delays
                if response_time > 100:  # Log if >100ms
                    self.logger.warning(f"⚠️ Slow status API response: {response_time:.1f}ms")
                
                return jsonify({
                    'success': True,
                    'data': status_data,
                    'response_time_ms': round(response_time, 1),
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Status API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/move', methods=['POST'])
        def api_move():
            """Execute manual movement command"""
            try:
                data = request.get_json()
                if not data:
                    raise BadRequest("No JSON data provided")
                
                # Validate command
                validated_command = CommandValidator.validate_move_command(data)
                
                # Execute movement
                result = asyncio.run(self._execute_move_command(validated_command))
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except WebInterfaceError as e:
                self.logger.warning(f"Move command validation failed: {e}")
                return jsonify({'success': False, 'error': str(e)}), 400
            except Exception as e:
                self.logger.error(f"Move API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/position', methods=['POST'])
        def api_goto_position():
            """Move to absolute position"""
            try:
                data = request.get_json()
                if not data:
                    raise BadRequest("No JSON data provided")
                
                # Validate command
                validated_position = CommandValidator.validate_position_command(data)
                
                # Execute movement with proper async handling
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self._execute_position_command(validated_position))
                finally:
                    loop.close()
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except WebInterfaceError as e:
                self.logger.warning(f"Position command validation failed: {e}")
                return jsonify({'success': False, 'error': str(e)}), 400
            except Exception as e:
                self.logger.error(f"Position API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/home', methods=['POST'])
        def api_home():
            """Home axes with enhanced logging"""
            try:
                self.logger.info(f"🏠 HOME API called - Method: {request.method}")
                self.logger.info(f"🏠 Request headers: {dict(request.headers)}")
                
                data = request.get_json() or {}
                self.logger.info(f"🏠 Request data: {data}")
                
                axes = data.get('axes', ['x', 'y', 'z', 'c'])  # Default: home all
                self.logger.info(f"🏠 Homing axes: {axes}")
                
                # Check if orchestrator and motion controller are available
                if not self.orchestrator:
                    self.logger.error("❌ No orchestrator available")
                    return jsonify({'success': False, 'error': 'Orchestrator not available'}), 500
                    
                if not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                    self.logger.error("❌ No motion controller available")
                    return jsonify({'success': False, 'error': 'Motion controller not available'}), 500
                
                self.logger.info(f"🏠 Orchestrator and motion controller available, executing home command...")
                result = self._execute_home_command(axes)
                self.logger.info(f"🏠 Home command result: {result}")
                
                response = {
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                }
                self.logger.info(f"🏠 Sending response: {response}")
                return jsonify(response)
                
            except Exception as e:
                self.logger.error(f"❌ Home API error: {e}")
                import traceback
                self.logger.error(f"❌ Home API traceback: {traceback.format_exc()}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/clear_alarm', methods=['POST'])
        def api_clear_alarm():
            """Clear alarm state using $X command"""
            try:
                self.logger.info("🔓 CLEAR ALARM API called")
                
                # Check if orchestrator and motion controller are available
                if not self.orchestrator:
                    self.logger.error("❌ No orchestrator available")
                    return jsonify({'success': False, 'error': 'Orchestrator not available'}), 500
                    
                if not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                    self.logger.error("❌ No motion controller available")
                    return jsonify({'success': False, 'error': 'Motion controller not available'}), 500
                
                # Execute alarm clear command
                self.logger.info("🔓 Executing clear alarm command...")
                motion_controller = self.orchestrator.motion_controller
                
                # Use sync version for web interface
                if hasattr(motion_controller, 'clear_alarm_sync'):
                    result = motion_controller.clear_alarm_sync()
                else:
                    # Fallback for async version
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    result = loop.run_until_complete(motion_controller.clear_alarm())
                    loop.close()
                
                if result:
                    self.logger.info("✅ Alarm cleared successfully")
                    response = {
                        'success': True,
                        'message': 'Alarm cleared successfully',
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    self.logger.error("❌ Failed to clear alarm")
                    response = {
                        'success': False,
                        'error': 'Failed to clear alarm state',
                        'timestamp': datetime.now().isoformat()
                    }
                
                return jsonify(response)
                
            except Exception as e:
                self.logger.error(f"❌ Clear alarm API error: {e}")
                import traceback
                self.logger.error(f"❌ Clear alarm API traceback: {traceback.format_exc()}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/reset', methods=['POST'])
        def api_reset():
            """Reset FluidNC controller and clear homed status"""
            try:
                self.logger.info("🔄 RESET API called")
                
                # Check if orchestrator and motion controller are available
                if not self.orchestrator:
                    self.logger.error("❌ No orchestrator available")
                    return jsonify({'success': False, 'error': 'Orchestrator not available'}), 500
                    
                if not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                    self.logger.error("❌ No motion controller available")
                    return jsonify({'success': False, 'error': 'Motion controller not available'}), 500
                
                # Execute reset command
                self.logger.info("🔄 Executing controller reset...")
                motion_controller = self.orchestrator.motion_controller
                
                # Use async version with proper event loop handling
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(motion_controller.reset_controller())
                finally:
                    loop.close()
                
                if result:
                    self.logger.info("✅ Controller reset successful")
                    response = {
                        'success': True,
                        'message': 'Controller reset successfully',
                        'homed_status_reset': True,
                        'timestamp': datetime.now().isoformat()
                    }
                else:
                    self.logger.error("❌ Failed to reset controller")
                    response = {
                        'success': False,
                        'error': 'Failed to reset controller',
                        'timestamp': datetime.now().isoformat()
                    }
                
                return jsonify(response)
                
            except Exception as e:
                self.logger.error(f"❌ Reset API error: {e}")
                import traceback
                self.logger.error(f"❌ Reset API traceback: {traceback.format_exc()}")
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/debug/position')
        def api_debug_position():
            """Debug endpoint for position updates"""
            try:
                debug_info = {}
                
                if self.orchestrator and hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                    motion_controller = self.orchestrator.motion_controller
                    
                    # Get positions from different sources
                    debug_info['adapter_position'] = motion_controller.current_position.__dict__ if hasattr(motion_controller.current_position, '__dict__') else str(motion_controller.current_position)
                    
                    if hasattr(motion_controller, 'controller'):
                        controller = motion_controller.controller
                        debug_info['controller_position'] = controller.current_position.__dict__ if hasattr(controller.current_position, '__dict__') else str(controller.current_position)
                        debug_info['last_update'] = getattr(controller, 'last_position_update', 0)
                        debug_info['monitor_running'] = getattr(controller, 'monitor_running', False)
                        debug_info['background_task_done'] = controller.background_monitor_task.done() if controller.background_monitor_task else True
                    
                    debug_info['timestamp'] = time.time()
                    
                return jsonify({
                    'success': True,
                    'debug': debug_info,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Debug position API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/debug/monitor')
        def api_debug_monitor():
            """Debug endpoint for background monitor status"""
            try:
                debug_info = {}
                
                if self.orchestrator and hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                    motion_controller = self.orchestrator.motion_controller
                    
                    if hasattr(motion_controller, 'controller'):
                        controller = motion_controller.controller
                        
                        # Get background monitor status
                        debug_info['monitor_running'] = getattr(controller, 'monitor_running', False)
                        debug_info['background_task_exists'] = controller.background_monitor_task is not None
                        debug_info['background_task_done'] = controller.background_monitor_task.done() if controller.background_monitor_task else None
                        debug_info['background_task_cancelled'] = controller.background_monitor_task.cancelled() if controller.background_monitor_task else None
                        debug_info['is_monitor_running'] = controller.is_background_monitor_running() if hasattr(controller, 'is_background_monitor_running') else False
                        debug_info['last_position_update'] = getattr(controller, 'last_position_update', 0)
                        debug_info['current_time'] = time.time()
                        debug_info['data_age'] = time.time() - getattr(controller, 'last_position_update', 0)
                        debug_info['is_connected'] = getattr(controller, '_connected', False) if hasattr(controller, '_connected') else False
                        
                        # Get task details if available
                        if controller.background_monitor_task:
                            task = controller.background_monitor_task
                            debug_info['task_id'] = id(task)
                            try:
                                if task.done():
                                    if task.cancelled():
                                        debug_info['task_result'] = 'CANCELLED'
                                    elif task.exception():
                                        debug_info['task_result'] = f'EXCEPTION: {task.exception()}'
                                    else:
                                        debug_info['task_result'] = 'COMPLETED'
                                else:
                                    debug_info['task_result'] = 'RUNNING'
                            except Exception as task_e:
                                debug_info['task_result'] = f'ERROR_CHECKING: {task_e}'
                
                return jsonify({
                    'success': True,
                    'monitor_status': debug_info,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Debug monitor API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/debug/restart-monitor', methods=['POST'])
        def api_restart_monitor():
            """Restart the background monitor"""
            try:
                if self.orchestrator and hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                    motion_controller = self.orchestrator.motion_controller
                    
                    if hasattr(motion_controller, 'controller') and hasattr(motion_controller.controller, 'restart_background_monitor'):
                        controller = motion_controller.controller
                        
                        # Use thread-safe approach for asyncio from Flask sync context
                        import concurrent.futures
                        import asyncio
                        
                        def restart_in_background():
                            """Run restart in a new thread with its own event loop"""
                            try:
                                # Create new event loop for this thread
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                
                                # Run the restart operation
                                result = loop.run_until_complete(controller.restart_background_monitor())
                                loop.close()
                                return result
                            except Exception as e:
                                self.logger.error(f"Background restart thread error: {e}")
                                return False
                        
                        # Run restart in background thread
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(restart_in_background)
                            try:
                                success = future.result(timeout=10.0)  # 10 second timeout
                                
                                return jsonify({
                                    'success': True,
                                    'message': f'Background monitor restart {"successful" if success else "attempted"}',
                                    'timestamp': datetime.now().isoformat()
                                })
                            except concurrent.futures.TimeoutError:
                                return jsonify({
                                    'success': False, 
                                    'error': 'Restart operation timed out'
                                }), 408
                    else:
                        return jsonify({'success': False, 'error': 'Controller does not support monitor restart'}), 400
                else:
                    return jsonify({'success': False, 'error': 'Motion controller not available'}), 400
                
            except Exception as e:
                self.logger.error(f"Restart monitor API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/jog', methods=['POST'])
        def api_jog():
            """Handle jog movement commands"""
            # Start timing logging (optional)
            command_id = None
            if TIMING_LOGGER_AVAILABLE:
                command_id = timing_logger.log_backend_received(
                    command_type="jog",
                    command_data=request.get_json() or {}
                )
            
            try:
                if TIMING_LOGGER_AVAILABLE and command_id:
                    timing_logger.log_backend_start(command_id, "api_jog")
                
                data = request.get_json() or {}
                
                # Validate jog parameters
                axis = data.get('axis', '').lower()
                direction = data.get('direction', '')
                mode = data.get('mode', 'step')
                distance = data.get('distance', 1.0)
                speed = data.get('speed', 10.0)  # Fallback if config fails
                
                if axis not in ['x', 'y', 'z', 'c']:
                    if TIMING_LOGGER_AVAILABLE and command_id:
                        timing_logger.log_backend_complete(command_id, success=False, error="Invalid axis")
                    return jsonify({"success": False, "error": "Invalid axis"}), 400
                
                if direction not in ['+', '-']:
                    if TIMING_LOGGER_AVAILABLE and command_id:
                        timing_logger.log_backend_complete(command_id, success=False, error="Invalid direction")
                    return jsonify({"success": False, "error": "Invalid direction"}), 400
                
                # Use enhanced feedrates from configuration for manual control
                try:
                    if self.orchestrator and hasattr(self.orchestrator, 'config_manager'):
                        config_manager = self.orchestrator.config_manager
                        
                        # Try multiple ways to get feedrates
                        manual_feedrates = {}
                        
                        # Method 1: Dot notation
                        try:
                            manual_feedrates = config_manager.get('feedrates.manual_mode', {})
                            self.logger.debug(f"Method 1 - Dot notation result: {manual_feedrates}")
                        except Exception as e:
                            self.logger.debug(f"Method 1 failed: {e}")
                        
                        # Method 2: Direct access if method 1 failed
                        if not manual_feedrates and hasattr(config_manager, '_config_data'):
                            try:
                                feedrates_section = config_manager._config_data.get('feedrates', {})
                                manual_feedrates = feedrates_section.get('manual_mode', {})
                                self.logger.debug(f"Method 2 - Direct access result: {manual_feedrates}")
                            except Exception as e:
                                self.logger.debug(f"Method 2 failed: {e}")
                        
                        # Method 3: Hardcoded enhanced values as fallback
                        if not manual_feedrates:
                            manual_feedrates = {
                                'x_axis': 950.0,
                                'y_axis': 950.0, 
                                'z_axis': 750.0,
                                'c_axis': 4800.0
                            }
                            self.logger.info("🔧 Using hardcoded enhanced feedrates as fallback")
                        
                        # Get appropriate feedrate for the axis
                        if axis in ['x', 'y']:
                            new_speed = manual_feedrates.get(f'{axis}_axis', None)
                            speed = float(new_speed) if new_speed is not None else speed
                        elif axis == 'z':
                            new_speed = manual_feedrates.get('z_axis', None)
                            speed = float(new_speed) if new_speed is not None else speed
                        elif axis == 'c':
                            new_speed = manual_feedrates.get('c_axis', None)
                            speed = float(new_speed) if new_speed is not None else speed
                        
                        self.logger.info(f"🚀 Using enhanced manual feedrate for {axis}-axis: {speed}")
                    else:
                        self.logger.warning("⚠️ Config manager not available, using default feedrate")
                except Exception as e:
                    self.logger.warning(f"⚠️ Could not load enhanced feedrates, using default: {e}")
                
                # Convert to the correct format expected by _execute_move_command
                move_distance = distance if direction == '+' else -distance
                
                if mode == 'continuous':
                    # For continuous jog, use smaller increments
                    move_distance = 0.5 if direction == '+' else -0.5
                
                # Format command as Position4D delta for FluidNC controller
                delta_values = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
                delta_values[axis] = move_distance
                
                # Execute the movement using Position4D format with enhanced feedrate
                result = asyncio.run(self._execute_jog_command(delta_values, speed, command_id))
                
                if TIMING_LOGGER_AVAILABLE and command_id:
                    timing_logger.log_backend_complete(command_id, success=True)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                if TIMING_LOGGER_AVAILABLE and command_id:
                    timing_logger.log_backend_complete(command_id, success=False, error=str(e))
                self.logger.error(f"Jog command error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route('/api/stop', methods=['POST'])
        def api_stop():
            """Handle motion stop commands"""
            try:
                # Use the existing emergency stop endpoint logic
                result = self._execute_emergency_stop()
                
                return jsonify({
                    "success": True, 
                    "message": "Motion stopped",
                    "timestamp": datetime.now().isoformat()
                })
                
            except Exception as e:
                logger.error(f"Stop command error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/api/emergency_stop', methods=['POST'])
        def api_emergency_stop():
            """Emergency stop all operations"""
            try:
                result = self._execute_emergency_stop()
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Emergency stop API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/debug/feedrates', methods=['GET'])
        def api_debug_feedrates():
            """Debug endpoint to check current feedrate configuration"""
            try:
                debug_info = {
                    'orchestrator_exists': self.orchestrator is not None,
                    'has_config_manager': False,
                    'config_file_path': None,
                    'raw_config_data': None,
                    'error_details': []
                }
                
                feedrates = {}
                if self.orchestrator and hasattr(self.orchestrator, 'config_manager'):
                    debug_info['has_config_manager'] = True
                    config_manager = self.orchestrator.config_manager
                    
                    # Get debug info about config manager
                    debug_info['config_file_path'] = str(config_manager.config_file) if hasattr(config_manager, 'config_file') else 'unknown'
                    
                    try:
                        # Try to get raw config data
                        debug_info['raw_config_data'] = config_manager._config_data if hasattr(config_manager, '_config_data') else 'no _config_data'
                        
                        # Test different access methods
                        feedrates = {
                            'manual_mode': config_manager.get('feedrates.manual_mode', {}),
                            'scanning_mode': config_manager.get('feedrates.scanning_mode', {}),
                            'options': config_manager.get('feedrates.options', {}),
                            'all_feedrates': config_manager.get('feedrates', {}),  # Try getting the whole section
                        }
                        
                        # Also try direct access
                        if hasattr(config_manager, '_config_data') and 'feedrates' in config_manager._config_data:
                            feedrates['direct_access'] = config_manager._config_data['feedrates']
                        
                    except Exception as e:
                        debug_info['error_details'].append(f"Config access failed: {e}")
                else:
                    debug_info['error_details'].append("Orchestrator or config_manager not available")
                
                return jsonify({
                    'success': True,
                    'feedrates': feedrates,
                    'debug_info': debug_info,
                    'config_available': self.orchestrator is not None and hasattr(self.orchestrator, 'config_manager'),
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Debug feedrates error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/api/debug/connection', methods=['GET'])
        def api_debug_connection():
            """Debug endpoint to check connection status details"""
            try:
                connection_info = {}
                
                if self.orchestrator and hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                    motion_controller = self.orchestrator.motion_controller
                    connection_info = {
                        'orchestrator_available': True,
                        'motion_controller_available': True,
                        'has_protocol': hasattr(motion_controller, 'protocol'),
                        'protocol_connected': None,
                        '_connected_property': None,
                        'refresh_status': None,
                        'serial_connection': None,
                        'connection_errors': []
                    }
                    
                    # Test different connection methods
                    try:
                        if hasattr(motion_controller, 'protocol'):
                            connection_info['protocol_connected'] = motion_controller.protocol.is_connected()
                            if hasattr(motion_controller.protocol, 'serial_connection'):
                                connection_info['serial_connection'] = {
                                    'exists': motion_controller.protocol.serial_connection is not None,
                                    'is_open': motion_controller.protocol.serial_connection.is_open if motion_controller.protocol.serial_connection else False
                                }
                    except Exception as e:
                        connection_info['connection_errors'].append(f"Protocol check failed: {e}")
                    
                    try:
                        connection_info['_connected_property'] = motion_controller._connected
                    except Exception as e:
                        connection_info['connection_errors'].append(f"_connected property failed: {e}")
                    
                    try:
                        if hasattr(motion_controller, 'refresh_connection_status'):
                            connection_info['refresh_status'] = motion_controller.refresh_connection_status()
                    except Exception as e:
                        connection_info['connection_errors'].append(f"Refresh status failed: {e}")
                else:
                    connection_info = {
                        'orchestrator_available': self.orchestrator is not None,
                        'motion_controller_available': False,
                        'error': 'Motion controller not available'
                    }
                
                return jsonify({
                    'success': True,
                    'connection_info': connection_info,
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Debug connection error: {e}")
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/api/scan/start', methods=['POST'])
        def api_scan_start():
            """Start a new scan"""
            try:
                data = request.get_json()
                if not data:
                    raise BadRequest("No JSON data provided")
                
                # Validate scan pattern
                validated_pattern = CommandValidator.validate_scan_pattern(data)
                
                # Start scan
                result = self._execute_scan_start(validated_pattern)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except WebInterfaceError as e:
                self.logger.warning(f"Scan start validation failed: {e}")
                return jsonify({'success': False, 'error': str(e)}), 400
            except Exception as e:
                self.logger.error(f"Scan start API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/scan/stop', methods=['POST'])
        def api_scan_stop():
            """Stop current scan"""
            try:
                result = self._execute_scan_stop()
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Scan stop API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/scan/pause', methods=['POST'])
        def api_scan_pause():
            """Pause/resume current scan"""
            try:
                result = self._execute_scan_pause()
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Scan pause API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/capture', methods=['POST'])
        def api_camera_capture():
            """Capture image from camera with optional flash"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 0)
                use_flash = data.get('flash', False)  # Enable flash functionality
                flash_intensity = data.get('flash_intensity', 80)  # Default flash intensity
                
                if use_flash:
                    result = self._execute_camera_capture_with_flash(camera_id, flash_intensity)
                else:
                    result = self._execute_camera_capture(camera_id)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Camera capture API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/controls', methods=['POST'])
        def api_camera_controls():
            """Set camera controls (autofocus, exposure, etc.)"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 'camera_1')
                controls = data.get('controls', {})
                
                result = self._execute_camera_controls(camera_id, controls)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Camera controls API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/autofocus', methods=['POST'])
        def api_camera_autofocus():
            """Trigger autofocus on camera"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 'camera_1')
                
                result = self._execute_camera_autofocus(camera_id)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Camera autofocus API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/focus', methods=['POST'])
        def api_camera_manual_focus():
            """Set manual focus position"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 'camera_1')
                focus_position = float(data.get('focus_position', 5.0))
                
                result = self._execute_manual_focus(camera_id, focus_position)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Manual focus API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/stabilize', methods=['POST'])
        def api_camera_stabilize():
            """Enable camera stabilization to reduce flickering"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 'camera_1')
                enable = data.get('enable', True)
                
                controls = {
                    'stabilize_exposure': enable,
                    'stabilize_awb': enable
                }
                
                result = self._execute_camera_controls(camera_id, controls)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'stabilization_enabled': enable,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Camera stabilization API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/white_balance', methods=['POST'])
        def api_camera_white_balance():
            """Set white balance mode to fix color switching"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 'camera_1')
                wb_mode = data.get('mode', 'auto')  # auto, daylight, tungsten, indoor, lock
                
                if wb_mode == 'auto':
                    controls = {'auto_white_balance': True}
                else:
                    controls = {
                        'lock_white_balance': True,
                        'wb_mode': wb_mode
                    }
                
                result = self._execute_camera_controls(camera_id, controls)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'white_balance_mode': wb_mode,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"White balance API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/status', methods=['GET'])
        def api_camera_detailed_status():
            """Get detailed camera status including current controls"""
            try:
                camera_id = request.args.get('camera_id', 'camera_1')
                
                result = self._get_camera_detailed_status(camera_id)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Camera detailed status API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/camera/capture/camera1', methods=['POST'])
        def api_camera1_capture():
            """Individual camera capture disabled - use synchronized capture instead"""
            return jsonify({
                'success': False, 
                'error': 'Individual camera capture disabled. Use synchronized capture (/api/camera/capture/both) which saves photos to disk.',
                'recommendation': 'Use the "📸⚡ Capture Both Cameras (Flash)" button instead'
            }), 400

        @self.app.route('/api/camera/capture/camera2', methods=['POST'])
        def api_camera2_capture():
            """Individual camera capture disabled - use synchronized capture instead"""
            return jsonify({
                'success': False, 
                'error': 'Individual camera capture disabled. Use synchronized capture (/api/camera/capture/both) which saves photos to disk.',
                'recommendation': 'Use the "📸⚡ Capture Both Cameras (Flash)" button instead'
            }), 400

        @self.app.route('/api/camera/capture/both', methods=['POST'])
        def api_both_cameras_capture():
            """Capture synchronized photos from both cameras with flash"""
            try:
                self.logger.info("📸 API: Synchronized camera capture request received")
                data = request.get_json() or {}
                use_flash = data.get('flash', True)  # Default to flash enabled
                flash_intensity = data.get('flash_intensity', 80)
                
                self.logger.info(f"📸 Synchronized capture: flash={use_flash}, intensity={flash_intensity}")
                
                # For synchronized capture, always use the flash sync method
                if use_flash:
                    self.logger.info("🔥 Executing flash capture")
                    result = self._execute_synchronized_capture_with_flash(flash_intensity)
                else:
                    self.logger.info("📷 Executing normal capture")
                    result = self._execute_synchronized_capture()
                
                self.logger.info(f"✅ Synchronized capture completed successfully")
                return jsonify({
                    'success': True,
                    'data': result,
                    'camera': 'Both Cameras',
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"❌ Both cameras capture API error: {e}")
                import traceback
                self.logger.error(f"Full traceback: {traceback.format_exc()}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/lighting/flash', methods=['POST'])
        def api_lighting_flash():
            """Trigger lighting flash"""
            try:
                data = request.get_json() or {}
                zone = data.get('zone', 'all')
                brightness = float(data.get('brightness', 0.8))
                duration = int(data.get('duration', 100))
                
                result = self._execute_lighting_flash(zone, brightness, duration)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Lighting flash API error: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
        
        # Camera streaming endpoints
        @self.app.route('/debug-status')
        def debug_status():
            """Debug page to test status API"""
            return render_template('debug_status.html')
        
        @self.app.route('/camera/<int:camera_id>')
        def camera_stream(camera_id):
            """MJPEG camera stream with proper ID mapping"""
            try:
                self.logger.info(f"Camera stream request for camera {camera_id}")
                
                # Map frontend camera IDs (0, 1) to backend camera IDs
                # Frontend: Camera 0, Camera 1
                # Backend might use: 0, 1 or 'camera_1', 'camera_2' or other formats
                
                # Try the ID as-is first, then try mapped versions
                mapped_id = camera_id
                
                # Check if we need to map IDs for different systems
                if self.orchestrator and hasattr(self.orchestrator, 'camera_manager'):
                    # Get available cameras to determine the ID format
                    try:
                        status = self.orchestrator.get_camera_status()
                        available_cameras = status.get('cameras', [])
                        self.logger.info(f"Available cameras for mapping: {available_cameras}")
                        
                        # If backend uses string IDs like 'camera_1', 'camera_2'
                        if available_cameras and isinstance(available_cameras[0], str):
                            if 'camera_' in str(available_cameras[0]):
                                # Map 0 -> 'camera_1', 1 -> 'camera_2', etc.
                                mapped_id = f'camera_{camera_id + 1}'
                                self.logger.info(f"Mapped camera ID {camera_id} to {mapped_id}")
                        
                    except Exception as mapping_error:
                        self.logger.warning(f"Camera ID mapping error: {mapping_error}")
                        # Use original ID if mapping fails
                        pass
                
                self.logger.info(f"Starting camera stream generation for mapped ID: {mapped_id}")
                return Response(
                    self._generate_camera_stream(mapped_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame'
                )
            except Exception as e:
                self.logger.error(f"Camera stream error for camera {camera_id}: {e}")
                import traceback
                self.logger.error(f"Full traceback: {traceback.format_exc()}")
                # Return empty response that will trigger onerror in HTML
                return Response("", status=404)
    
    def _setup_orchestrator_integration(self):
        """Setup integration with the scan orchestrator"""
        # This will be implemented to listen to orchestrator events
        # Note: SocketIO functionality temporarily removed for simplified deployment
        pass
    
    def _setup_feedrate_integration(self):
        """Setup intelligent feedrate management for web interface"""
        try:
            # Import the feedrate integration module
            from web_interface_feedrate_integration import integrate_feedrate_system
            
            # Integrate the feedrate system
            success = integrate_feedrate_system(self)
            
            if success:
                self.logger.info("✅ Feedrate system integrated successfully")
                self.logger.info("  • Intelligent jog feedrate selection enabled")
                self.logger.info("  • Operating mode switching available")
                self.logger.info("  • Runtime feedrate configuration supported")
            else:
                self.logger.warning("⚠️ Feedrate system integration partially failed")
                
        except ImportError as e:
            self.logger.warning(f"⚠️ Feedrate integration module not found: {e}")
            self.logger.info("  • Web interface will use basic feedrate handling")
        except Exception as e:
            self.logger.error(f"❌ Feedrate integration failed: {e}")
            self.logger.info("  • Web interface will use fallback feedrate handling")
    
    # Core system interface methods
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        self.logger.debug(f"_get_system_status called with orchestrator: {self.orchestrator is not None}")
        try:
            # Get status from orchestrator and components
            status = {
                'timestamp': datetime.now().isoformat(),
                'system': {
                    'initialized': hasattr(self.orchestrator, 'motion_controller') if self.orchestrator else False,
                    'ready': True,
                    'status': 'ready',
                    'errors': [],
                    'warnings': []
                },
                'motion': {
                    'connected': False,
                    'homed': False,
                    'position': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0},
                    'status': 'unknown'
                },
                'cameras': {
                    'available': 0,
                    'active': [],
                    'status': 'unknown'
                },
                'lighting': {
                    'zones': [],
                    'status': 'unknown'
                },
                'scan': {
                    'active': False,
                    'status': 'idle',
                    'progress': 0.0,
                    'current_point': 0,
                    'total_points': 0,
                    'phase': 'idle'
                }
            }
            
            # Get motion controller status
            if self.orchestrator and hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                self.logger.debug(f"Checking motion controller status...")
                try:
                    motion_controller = self.orchestrator.motion_controller
                    
                    # Get position timestamp for debugging lag
                    current_time = datetime.now().isoformat()
                    
                    # Always use cached position from background monitor - NEVER call async from sync
                    # This prevents event loop conflicts that cause delays
                    position = motion_controller.current_position
                    
                    # Get debugging info about position freshness
                    last_update_time = 0
                    data_age = 999.0
                    monitor_running = False
                    
                    if hasattr(motion_controller, 'controller'):
                        controller = motion_controller.controller
                        if hasattr(controller, 'last_position_update'):
                            last_update_time = controller.last_position_update
                            data_age = time.time() - last_update_time if last_update_time > 0 else 999.0
                        if hasattr(controller, 'is_background_monitor_running'):
                            monitor_running = controller.is_background_monitor_running()
                    
                    # Log if data seems stale but don't try to fix it synchronously
                    if data_age > 2.0:
                        self.logger.debug(f"⚠️  Position data is {data_age:.1f}s old, monitor_running={monitor_running}")
                    else:
                        self.logger.debug(f"✅ Position data is fresh ({data_age:.1f}s old)")
                    
                    # Get status information from controller properties (use cached status to avoid async calls)
                    # Force refresh connection status to avoid stale cached values
                    try:
                        connected = motion_controller.protocol.is_connected() if hasattr(motion_controller, 'protocol') else False
                        self.logger.debug(f"Direct protocol connection check: {connected}")
                    except Exception as e:
                        self.logger.warning(f"Protocol connection check failed: {e}")
                        connected = getattr(motion_controller, '_connected', False) if hasattr(motion_controller, '_connected') else False
                        self.logger.debug(f"Fallback connection check: {connected}")
                    
                    # Additional connection verification
                    if not connected:
                        self.logger.warning("❌ Motion controller appears disconnected - checking deeper...")
                        # Try multiple ways to verify connection
                        if hasattr(motion_controller, 'refresh_connection_status'):
                            try:
                                refreshed_status = motion_controller.refresh_connection_status()
                                self.logger.debug(f"Refreshed connection status: {refreshed_status}")
                                connected = refreshed_status
                            except Exception as e:
                                self.logger.error(f"Connection refresh failed: {e}")
                    
                    self.logger.info(f"🔌 Final connection status for web UI: {connected}")
                    
                    # FORCE CONNECTION TO TRUE if we know it's working based on debug results
                    # This addresses the inconsistency where debug shows connected but UI shows disconnected
                    if not connected:
                        self.logger.warning("🔧 Connection shows false but trying to force refresh...")
                        # One more attempt with multiple methods
                        try:
                            protocol_connected = motion_controller.protocol.is_connected() if hasattr(motion_controller, 'protocol') else False
                            if protocol_connected:
                                connected = True
                                self.logger.info("🔧 Successfully forced connection to true based on protocol status")
                        except:
                            pass
                    
                    # Get real-time status AND homed state from protocol instead of cached controller values
                    try:
                        if hasattr(motion_controller, 'protocol') and motion_controller.protocol:
                            protocol_status = motion_controller.protocol.get_current_status()
                            current_status = protocol_status.state if protocol_status else 'unknown'
                            # Get homed status from protocol - check if position indicates homing complete
                            homed = motion_controller.is_homed if hasattr(motion_controller, 'is_homed') else False
                            self.logger.info(f"🔍 Direct protocol status: {current_status}, homed: {homed}")
                        else:
                            current_status = motion_controller.status if hasattr(motion_controller, 'status') else 'unknown'
                            homed = motion_controller.is_homed if hasattr(motion_controller, 'is_homed') else False
                            self.logger.info(f"🔍 Controller cached status: {current_status}, homed: {homed}")
                    except Exception as status_err:
                        self.logger.warning(f"Status retrieval error: {status_err}")
                        current_status = 'unknown'
                        homed = False
                    
                    current_timestamp = time.time()
                    age_seconds = current_timestamp - last_update_time if last_update_time > 0 else -1
                    
                    self.logger.debug(f"Position: {position} | Last update: {age_seconds:.1f}s ago | Monitor running: {monitor_running}")
                    self.logger.debug(f"Motion controller status: connected={connected}, homed={homed}, status={current_status}")
                    
                    # Convert Position4D to dict for JSON serialization
                    if hasattr(position, '__dict__'):
                        position_dict = {
                            'x': getattr(position, 'x', 0.0),
                            'y': getattr(position, 'y', 0.0), 
                            'z': getattr(position, 'z', 0.0),
                            'c': getattr(position, 'c', 0.0),
                            'data_age_seconds': round(data_age, 2),
                            'last_update_time': last_update_time,
                            'monitor_running': monitor_running
                        }
                    else:
                        position_dict = {
                            'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0,
                            'data_age_seconds': 999.0,
                            'last_update_time': 0,
                            'monitor_running': False
                        }
                    
                    # Convert MotionStatus enum to string and map to frontend-expected values
                    raw_status = str(current_status).split('.')[-1].lower() if hasattr(current_status, 'name') else str(current_status).lower()
                    
                    # Map backend status to frontend-expected status values
                    status_map = {
                        'home': 'homing',  # FluidNC 'Home' state → frontend 'homing' 
                        'idle': 'idle',
                        'moving': 'moving',
                        'jogging': 'jogging',
                        'error': 'error',
                        'alarm': 'alarm',
                        'disconnected': 'disconnected'
                    }
                    status_str = status_map.get(raw_status, raw_status)
                    
                    # USE REAL PROTOCOL STATUS - properly mapped for frontend
                    if status_str == 'homing':
                        self.logger.info(f"🏠 Showing HOMING status in web UI - homing in progress (raw: {raw_status})")
                    elif status_str == 'idle':
                        self.logger.info(f"✅ Showing IDLE status in web UI - system ready (raw: {raw_status})")
                    else:
                        self.logger.info(f"📊 Showing {status_str.upper()} status in web UI (raw: {raw_status})")
                    
                    # Get alarm state information
                    alarm_info = {
                        'is_alarm': status_str == 'alarm',
                        'is_error': status_str == 'error',
                        'can_move': status_str not in ['alarm', 'error'],
                        'alarm_code': None,
                        'message': ''
                    }
                    
                    # Skip detailed alarm information to avoid async complications in sync context
                    # The basic alarm info from status is sufficient for web interface
                    self.logger.debug(f"Using basic alarm info: {alarm_info}")
                    
                    # Determine activity based on status - Enhanced with 'home' state support
                    activity_map = {
                        'homing': 'homing',
                        'home': 'homing',  # FluidNC reports 'Home' state during homing
                        'moving': 'moving', 
                        'jogging': 'jogging',
                        'idle': 'idle',
                        'disconnected': 'disconnected',
                        'error': 'error',
                        'alarm': 'alarm'  # Keep alarm separate from error
                    }
                    activity = activity_map.get(status_str, 'unknown')
                    
                    # FORCE ACTIVITY CORRECTION - if connected, don't show disconnected activity
                    # But preserve valid operational activities like 'homing'
                    if connected and activity == 'disconnected':
                        activity = 'idle'
                        self.logger.info(f"🔧 Corrected activity from 'disconnected' to 'idle' since connection is verified")
                    elif activity == 'homing':
                        # Don't correct homing activity - it's valid during homing operations
                        self.logger.debug(f"✅ Preserving 'homing' activity - operation in progress")
                    
                    status['motion'].update({
                        'connected': connected,
                        'homed': homed,
                        'status': status_str,
                        'activity': activity,
                        'position': position_dict,
                        'alarm': alarm_info  # Add alarm information
                    })
                    
                    self.logger.debug(f"Final motion status sent to UI: {status['motion']}")
                    
                except Exception as e:
                    self.logger.error(f"Motion controller status error: {e}")
                    status['system']['errors'].append(f"Motion controller error: {e}")
            else:
                self.logger.warning(f"Motion controller not available: orchestrator={self.orchestrator is not None}, has_attr={hasattr(self.orchestrator, 'motion_controller') if self.orchestrator else False}, controller={getattr(self.orchestrator, 'motion_controller', None) is not None if self.orchestrator else False}")
            
            # Get camera status
            if self.orchestrator and hasattr(self.orchestrator, 'camera_manager') and self.orchestrator.camera_manager:
                self.logger.debug(f"Checking camera manager status...")
                try:
                    # Use orchestrator's synchronous method to avoid async issues
                    camera_status = self.orchestrator.get_camera_status()
                    self.logger.debug(f"Camera status from adapter: {camera_status}")
                    
                    status['cameras'].update({
                        'available': len(camera_status.get('cameras', [])),
                        'active': camera_status.get('active_cameras', []),  # Frontend expects 'active' not 'active_cameras'
                        'status': 'ready' if camera_status.get('cameras') else 'unavailable'
                    })
                except Exception as e:
                    self.logger.error(f"Camera manager status error: {e}")
                    status['system']['errors'].append(f"Camera manager error: {e}")
            else:
                self.logger.warning(f"Camera manager not available: orchestrator={self.orchestrator is not None}, has_attr={hasattr(self.orchestrator, 'camera_manager') if self.orchestrator else False}, manager={getattr(self.orchestrator, 'camera_manager', None) is not None if self.orchestrator else False}")
            
            # Get lighting status
            if self.orchestrator and hasattr(self.orchestrator, 'lighting_controller') and self.orchestrator.lighting_controller:
                try:
                    # Use synchronous status method if available
                    if hasattr(self.orchestrator.lighting_controller, 'get_sync_status'):
                        lighting_status = self.orchestrator.lighting_controller.get_sync_status()
                        status['lighting'].update({
                            'zones': list(lighting_status.get('zones', {}).keys()),
                            'status': lighting_status.get('status', 'unknown')
                        })
                    else:
                        # Fallback for other lighting controllers
                        status['lighting'].update({
                            'zones': [],
                            'status': 'sync_method_unavailable'
                        })
                except Exception as e:
                    status['system']['errors'].append(f"Lighting controller error: {e}")
            
            # Get scan status
            if self.orchestrator and hasattr(self.orchestrator, 'current_scan') and self.orchestrator.current_scan:
                try:
                    scan = self.orchestrator.current_scan
                    status['scan'].update({
                        'active': scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED],
                        'status': scan.status.value if hasattr(scan.status, 'value') else str(scan.status),
                        'progress': scan.progress.completion_percentage if hasattr(scan, 'progress') else 0.0,
                        'current_point': scan.progress.points_completed if hasattr(scan, 'progress') else 0,
                        'total_points': scan.progress.total_points if hasattr(scan, 'progress') else 0,
                        'phase': scan.current_phase.value if hasattr(scan, 'current_phase') and hasattr(scan.current_phase, 'value') else 'unknown'
                    })
                except Exception as e:
                    status['system']['errors'].append(f"Scan status error: {e}")
            
            status['system']['ready'] = len(status['system']['errors']) == 0
            self.logger.debug(f"Final status being returned: motion.connected={status['motion']['connected']}, cameras.available={status['cameras']['available']}")
            
            # Debug: Add a debug field to verify fresh data
            status['debug'] = {
                'backend_timestamp': datetime.now().isoformat(),
                'motion_connected': status['motion']['connected'],
                'cameras_available': status['cameras']['available'],
                'cameras_active': status['cameras']['active']
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting system status: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'system': {'initialized': False, 'ready': False, 'errors': [str(e)]},
                'motion': {'connected': False, 'status': 'error'},
                'cameras': {'available': 0, 'status': 'error'},
                'lighting': {'zones': [], 'status': 'error'},
                'scan': {'active': False, 'status': 'error'}
            }
    
    def _get_scan_history(self) -> List[Dict[str, Any]]:
        """Get scan history"""
        try:
            # This would typically read from a database or file system
            # For now, return placeholder data
            return [
                {
                    'id': 'scan_001',
                    'timestamp': '2025-09-23T14:15:00',
                    'pattern': 'Grid',
                    'points': 51,
                    'status': 'Complete',
                    'duration': '23:45',
                    'output_dir': '/scans/scan_001'
                }
            ]
        except Exception as e:
            self.logger.error(f"Error getting scan history: {e}")
            return []
    
    def _get_system_config(self) -> Dict[str, Any]:
        """Get system configuration"""
        try:
            return {
                'motion': {
                    'port': '/dev/ttyUSB0',
                    'baud_rate': 115200,
                    'position_limits': CommandValidator.POSITION_LIMITS
                },
                'cameras': {
                    'count': 2,
                    'resolution': '9152x6944',
                    'format': 'RAW'
                },
                'lighting': {
                    'zones': 3,
                    'max_brightness': 1.0
                },
                'web': {
                    'port': 8080,
                    'update_rate': 1.0
                }
            }
        except Exception as e:
            self.logger.error(f"Error getting system config: {e}")
            return {}
    
    # Command execution methods with robust error handling
    
    async def _execute_jog_command(self, delta_values: Dict[str, float], speed: float, command_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute jog movement with Position4D format"""
        try:
            if TIMING_LOGGER_AVAILABLE and command_id:
                timing_logger.log_motion_controller_start(command_id, "_execute_jog_command")
            
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            # Create Position4D delta object
            if SCANNER_MODULES_AVAILABLE:
                delta = Position4D(x=delta_values['x'], y=delta_values['y'], 
                                 z=delta_values['z'], c=delta_values['c'])
            else:
                # Mock for development
                delta = {'x': delta_values['x'], 'y': delta_values['y'], 
                        'z': delta_values['z'], 'c': delta_values['c']}
            
            # Execute the jog movement (this now includes immediate position update)
            result = await self.orchestrator.motion_controller.move_relative(delta, feedrate=speed)
            
            # Get the fresh position that was just updated by move_relative
            cached_position = self.orchestrator.motion_controller.current_position
            self.logger.info(f"🎯 Fresh position after jog: {cached_position}")
            
            # Get updated position from cached value (updated by move_relative)
            motion_controller = self.orchestrator.motion_controller
            
            # Convert Position4D to dict for JSON response
            if hasattr(cached_position, '__dict__'):
                new_position = {
                    'x': getattr(cached_position, 'x', 0.0),
                    'y': getattr(cached_position, 'y', 0.0),
                    'z': getattr(cached_position, 'z', 0.0),
                    'c': getattr(cached_position, 'c', 0.0)
                }
            else:
                new_position = cached_position
            
            self.logger.info(f"Jog command executed: delta={delta} speed={speed}, new_position={new_position}")
            
            return {
                'delta': delta_values,
                'speed': speed,
                'new_position': new_position,
                'success': result
            }
            
        except Exception as e:
            self.logger.error(f"Jog command execution failed: {e}")
            raise HardwareError(f"Failed to execute jog command: {e}")

    async def _execute_move_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated movement command with safety checks"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            # Motion controller has its own safety validation, no need for separate alarm check
            motion_controller = self.orchestrator.motion_controller
            
            axis = command['axis']
            distance = command['distance']
            
            # Convert single-axis command to Position4D format
            delta_values = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
            delta_values[axis] = distance
            
            # Create Position4D delta object
            if SCANNER_MODULES_AVAILABLE:
                delta = Position4D(x=delta_values['x'], y=delta_values['y'], 
                                 z=delta_values['z'], c=delta_values['c'])
            else:
                delta = delta_values
            
            # Execute the movement
            result = await self.orchestrator.motion_controller.move_relative(delta, feedrate=None)
            
            # Get updated position from cached value
            motion_controller = self.orchestrator.motion_controller
            cached_position = motion_controller.current_position
            
            # Convert Position4D to dict for JSON response
            if hasattr(cached_position, '__dict__'):
                new_position = {
                    'x': getattr(cached_position, 'x', 0.0),
                    'y': getattr(cached_position, 'y', 0.0),
                    'z': getattr(cached_position, 'z', 0.0),
                    'c': getattr(cached_position, 'c', 0.0)
                }
            else:
                new_position = cached_position
            
            self.logger.info(f"Move command executed: {axis} {distance:+.1f}mm, new_position={new_position}")
            
            return {
                'axis': axis,
                'distance': distance,
                'new_position': new_position,
                'success': result
            }
            
        except Exception as e:
            self.logger.error(f"Move command execution failed: {e}")
            raise HardwareError(f"Failed to execute move command: {e}")
    
    async def _execute_position_command(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated position command with safety checks"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            # Motion controller has its own safety validation, no need for separate alarm check
            motion_controller = self.orchestrator.motion_controller
            
            # Convert dictionary to Position4D object for motion controller
            position_obj = Position4D(
                x=position.get('x', 0.0),
                y=position.get('y', 0.0),
                z=position.get('z', 0.0),
                c=position.get('c', 0.0)
            )
            
            # Execute the position movement
            result = await self.orchestrator.motion_controller.move_to_position(position_obj)
            
            # Get updated position from cached value
            motion_controller = self.orchestrator.motion_controller
            cached_position = motion_controller.current_position
            
            # Convert Position4D to dict for JSON response
            if hasattr(cached_position, '__dict__'):
                new_position = {
                    'x': getattr(cached_position, 'x', 0.0),
                    'y': getattr(cached_position, 'y', 0.0),
                    'z': getattr(cached_position, 'z', 0.0),
                    'c': getattr(cached_position, 'c', 0.0)
                }
            else:
                new_position = cached_position
            
            self.logger.info(f"Position command executed: {position}, new_position={new_position}")
            
            return {
                'target_position': position,
                'actual_position': new_position,
                'success': result
            }
            
        except Exception as e:
            self.logger.error(f"Position command execution failed: {e}")
            raise HardwareError(f"Failed to execute position command: {e}")
    
    def _execute_home_command(self, axes: List[str]) -> Dict[str, Any]:
        """Execute homing command with immediate feedback"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            self.logger.info(f"Starting homing sequence for axes: {axes}")
            
            # Start homing in a separate thread to provide immediate response
            import threading
            def home_task():
                try:
                    self.logger.info(f"🏠 Starting homing task in background thread for axes: {axes}")
                    # Double-check motion controller is still available
                    if self.orchestrator and self.orchestrator.motion_controller:
                        self.logger.info(f"🏠 Motion controller available, calling home_axes_sync...")
                        result = self.orchestrator.motion_controller.home_axes_sync(axes)
                        self.logger.info(f"🏠 Homing sequence completed for axes: {axes}, result: {result}")
                        if not result:
                            self.logger.error(f"❌ Homing failed - home_axes_sync returned False")
                    else:
                        self.logger.error("❌ Motion controller became unavailable during homing")
                except Exception as e:
                    self.logger.error(f"❌ Homing task exception: {e}")
                    import traceback
                    self.logger.error(f"❌ Homing traceback: {traceback.format_exc()}")
            
            # Start homing thread
            self.logger.info(f"🏠 Creating homing thread for axes: {axes}")
            home_thread = threading.Thread(target=home_task, name=f"HomingThread-{'-'.join(axes)}")
            home_thread.daemon = True
            home_thread.start()
            self.logger.info(f"🏠 Homing thread started: {home_thread.name}")
            
            # Return immediate response indicating homing started (not completed)
            return {
                'message': f'Homing sequence started for axes: {", ".join(axes)}',
                'status': 'in_progress',
                'axes': axes,
                'started': True,  # Changed from 'success' to 'started'
                'note': 'Monitor system status for completion'
            }
            
        except Exception as e:
            self.logger.error(f"Homing command execution failed: {e}")
            raise HardwareError(f"Failed to execute homing command: {e}")
    
    def _execute_emergency_stop(self) -> Dict[str, Any]:
        """Execute emergency stop"""
        try:
            # Stop any active scan
            if self.orchestrator and hasattr(self.orchestrator, 'current_scan') and self.orchestrator.current_scan:
                if self.orchestrator.current_scan.status in [ScanStatus.RUNNING, ScanStatus.PAUSED]:
                    asyncio.create_task(self.orchestrator.stop_scan())
            
            # Emergency stop motion controller
            if self.orchestrator and hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                try:
                    self.orchestrator.motion_controller.emergency_stop_sync()
                except Exception as e:
                    self.logger.warning(f"Motion controller emergency stop failed: {e}")
            
            # Turn off lighting
            if self.orchestrator and hasattr(self.orchestrator, 'lighting_controller') and self.orchestrator.lighting_controller:
                try:
                    # Use sync wrapper method to avoid async warnings
                    self.orchestrator.lighting_controller.turn_off_all_sync()
                except Exception as e:
                    self.logger.warning(f"Could not turn off lighting during emergency stop: {e}")
            
            self.logger.warning("Emergency stop executed")
            
            return {
                'timestamp': datetime.now().isoformat(),
                'action': 'emergency_stop',
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Emergency stop execution failed: {e}")
            raise HardwareError(f"Failed to execute emergency stop: {e}")
    
    def _execute_scan_start(self, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute scan start command"""
        try:
            # Create scan pattern using orchestrator's methods
            if not self.orchestrator:
                raise ScannerSystemError("Scanner system not initialized")
                
            if pattern_data['pattern_type'] == 'grid':
                pattern = self.orchestrator.create_grid_pattern(
                    x_range=pattern_data['x_range'],
                    y_range=pattern_data['y_range'],
                    spacing=pattern_data['spacing'],
                    z_height=pattern_data['z_height']
                )
            elif pattern_data['pattern_type'] == 'cylindrical':
                pattern = self.orchestrator.create_cylindrical_pattern(
                    x_range=pattern_data['x_range'],
                    y_range=pattern_data['y_range'],
                    z_rotations=pattern_data['z_rotations'],
                    c_angles=pattern_data['c_angles']
                )
            else:
                raise ValueError(f"Unknown pattern type: {pattern_data['pattern_type']}")
            
            # Generate scan output directory
            scan_id = f"web_scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            output_dir = Path(f"/scans/{scan_id}")
            
            # Start the scan (this returns a coroutine, so we need to handle it properly)
            # For now, we'll create the task and let it run
            scan_task = asyncio.create_task(
                self.orchestrator.start_scan(
                    pattern=pattern,
                    output_directory=output_dir,
                    scan_id=scan_id
                )
            )
            
            self.logger.info(f"Scan started: {scan_id}")
            
            return {
                'scan_id': scan_id,
                'pattern_type': pattern_data['pattern_type'],
                'output_directory': str(output_dir),
                'estimated_points': len(pattern.generate_points()),
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Scan start execution failed: {e}")
            raise ScannerSystemError(f"Failed to start scan: {e}")
    
    def _execute_scan_stop(self) -> Dict[str, Any]:
        """Execute scan stop command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'current_scan') or not self.orchestrator.current_scan:
                raise ScannerSystemError("No active scan to stop")
            
            # Stop the scan
            asyncio.create_task(self.orchestrator.stop_scan())
            
            self.logger.info("Scan stop command executed")
            
            return {
                'action': 'scan_stopped',
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Scan stop execution failed: {e}")
            raise ScannerSystemError(f"Failed to stop scan: {e}")
    
    def _execute_scan_pause(self) -> Dict[str, Any]:
        """Execute scan pause/resume command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'current_scan') or not self.orchestrator.current_scan:
                raise ScannerSystemError("No active scan to pause/resume")
            
            current_status = self.orchestrator.current_scan.status
            
            if current_status == ScanStatus.RUNNING:
                asyncio.create_task(self.orchestrator.pause_scan())
                action = 'paused'
            elif current_status == ScanStatus.PAUSED:
                asyncio.create_task(self.orchestrator.resume_scan())
                action = 'resumed'
            else:
                raise ScannerSystemError(f"Cannot pause/resume scan in status: {current_status}")
            
            self.logger.info(f"Scan {action}")
            
            return {
                'action': action,
                'timestamp': datetime.now().isoformat(),
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Scan pause/resume execution failed: {e}")
            raise ScannerSystemError(f"Failed to pause/resume scan: {e}")
    
    def _execute_camera_capture(self, camera_id: int) -> Dict[str, Any]:
        """Execute camera capture command using available camera manager methods"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Capture high-resolution image using the available method
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Use the high-resolution capture method that exists in CameraManagerAdapter
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                image_data = loop.run_until_complete(
                    self.orchestrator.camera_manager.capture_high_resolution(camera_id)
                )
            finally:
                loop.close()
            
            if image_data is not None:
                # Save the captured image to disk
                from pathlib import Path
                import cv2
                
                # Create output directory
                output_dir = Path.home() / "manual_captures" / datetime.now().strftime('%Y-%m-%d')
                output_dir.mkdir(parents=True, exist_ok=True)
                
                # Save image
                filename = output_dir / f"single_capture_{timestamp}_camera_{camera_id + 1}.jpg"
                cv2.imwrite(str(filename), image_data, [cv2.IMWRITE_JPEG_QUALITY, 95])
                
                self.logger.info(f"✅ Camera capture executed: Camera {camera_id}")
                self.logger.info(f"📁 Photo saved to: {filename}")
                
                return {
                    'camera_id': camera_id,
                    'timestamp': timestamp,
                    'success': True,
                    'image_captured': True,
                    'filename': str(filename),
                    'storage_info': f'Photo saved to: {filename}'
                }
            else:
                raise HardwareError("Camera capture returned no data")
            
        except Exception as e:
            self.logger.error(f"Camera capture execution failed: {e}")
            raise HardwareError(f"Failed to capture image: {e}")
    
    def _execute_camera_capture_with_flash(self, camera_id: int, flash_intensity: int = 80) -> Dict[str, Any]:
        """Execute camera capture with LED flash synchronization using manual coordination"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
                
            if not hasattr(self.orchestrator, 'lighting_controller') or not self.orchestrator.lighting_controller:
                raise HardwareError("Lighting controller not available for flash")
            
            # Prepare capture parameters
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Manual flash coordination since direct flash sync method isn't available
            self.logger.info(f"Executing manual flash coordination for camera {camera_id}")
            
            import asyncio
            import time
            
            # Flash settings (convert percentage to flash settings)
            flash_settings = {
                'brightness': flash_intensity / 100.0,  # Convert percentage to 0-1 range
                'duration': 100,  # 100ms flash duration
                'pulse_count': 1
            }
            
            # Manual coordination: Flash + Capture timing
            async def flash_capture_coordination():
                # Trigger flash with timing coordination
                flash_task = asyncio.create_task(
                    self.orchestrator.lighting_controller.flash(['all'], flash_settings)
                )
                
                # Small delay to let flash reach peak intensity
                await asyncio.sleep(0.02)  # 20ms delay
                
                # Capture during flash
                capture_task = asyncio.create_task(
                    self.orchestrator.camera_manager.capture_high_resolution(camera_id)
                )
                
                # Wait for both operations
                flash_result = await flash_task
                image_data = await capture_task
                
                return flash_result, image_data
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                flash_result, image_data = loop.run_until_complete(flash_capture_coordination())
            finally:
                loop.close()
            
            if image_data is not None:
                self.logger.info(f"Flash capture executed: Camera {camera_id}, Flash intensity: {flash_intensity}%")
                
                return {
                    'camera_id': camera_id,
                    'timestamp': timestamp,
                    'flash_used': True,
                    'flash_intensity': flash_intensity,
                    'success': True,
                    'image_captured': True,
                    'flash_result': flash_result if 'flash_result' in locals() else 'completed'
                }
            else:
                raise HardwareError("Camera capture returned no data during flash")
            
        except Exception as e:
            self.logger.error(f"Flash capture execution failed: {e}")
            raise HardwareError(f"Failed to capture image with flash: {e}")
    
    def _execute_synchronized_capture_with_flash(self, flash_intensity: int = 80) -> Dict[str, Any]:
        """Execute synchronized capture with flash using proper storage integration"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            self.logger.info(f"🔥 Starting synchronized flash capture with storage integration - intensity: {flash_intensity}%")
            
            # Get current position for metadata
            current_position = None
            try:
                if hasattr(self.orchestrator, 'motion_controller') and self.orchestrator.motion_controller:
                    current_position = self.orchestrator.motion_controller.get_current_position()
            except Exception as pos_error:
                self.logger.warning(f"Could not get current position: {pos_error}")
            
            # Create session for this capture
            session_id = f"manual_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            results = []
            
            # Flash coordination (if lighting controller available)
            flash_result = None
            try:
                if hasattr(self.orchestrator, 'lighting_controller') and self.orchestrator.lighting_controller:
                    flash_settings = {
                        'brightness': flash_intensity / 100.0,
                        'duration': 100,
                        'pulse_count': 1
                    }
                    
                    import asyncio
                    async def trigger_flash():
                        return await self.orchestrator.lighting_controller.flash(['all'], flash_settings)
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        flash_result = loop.run_until_complete(trigger_flash())
                        self.logger.info("⚡ Flash triggered successfully")
                    finally:
                        loop.close()
                    
                    # Small delay for flash
                    import time
                    time.sleep(0.02)
                else:
                    self.logger.warning("⚠️ Lighting controller not available, capturing without flash")
            except Exception as flash_error:
                self.logger.warning(f"⚠️ Flash failed: {flash_error}, continuing with capture")
            
            # Capture from both cameras with proper storage integration
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            for camera_id in [0, 1]:
                try:
                    self.logger.info(f"📸 Capturing camera {camera_id + 1}")
                    
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # Capture using picamera2 - returns numpy array directly
                        image_data = loop.run_until_complete(
                            self.orchestrator.camera_manager.capture_high_resolution(camera_id)
                        )
                    finally:
                        loop.close()
                    
                    if image_data is not None:
                        # Try to use storage manager for proper metadata integration
                        if hasattr(self.orchestrator, 'storage_manager') and self.orchestrator.storage_manager:
                            try:
                                file_id = self._store_image_with_metadata_sync(
                                    image_data, camera_id, session_id, current_position, 
                                    flash_intensity, flash_result
                                )
                                results.append({
                                    'camera_id': camera_id,
                                    'file_id': file_id,
                                    'success': True,
                                    'storage_method': 'session_manager',
                                    'session_id': session_id
                                })
                                self.logger.info(f"✅ Stored camera {camera_id + 1} with file_id: {file_id}")
                            except Exception as storage_error:
                                self.logger.error(f"Storage failed for camera {camera_id + 1}: {storage_error}")
                                # Fallback to direct file saving
                                filename = self._fallback_save_image_sync(image_data, camera_id, timestamp)
                                results.append({
                                    'camera_id': camera_id,
                                    'filename': str(filename),
                                    'success': True,
                                    'storage_method': 'fallback_file'
                                })
                        else:
                            # No storage manager - use fallback
                            self.logger.warning("No storage manager available, using fallback file saving")
                            filename = self._fallback_save_image_sync(image_data, camera_id, timestamp)
                            results.append({
                                'camera_id': camera_id,
                                'filename': str(filename),
                                'success': True,
                                'storage_method': 'fallback_file'
                            })
                    else:
                        self.logger.error(f"❌ Camera {camera_id + 1} returned no data")
                        results.append({
                            'camera_id': camera_id,
                            'success': False,
                            'error': 'No image data'
                        })
                        
                except Exception as cam_error:
                    self.logger.error(f"❌ Failed to capture camera {camera_id + 1}: {cam_error}")
                    results.append({
                        'camera_id': camera_id,
                        'success': False,
                        'error': str(cam_error)
                    })
                    continue
            
            # Count successful captures
            successful_captures = sum(1 for r in results if r.get('success', False))
            
            if successful_captures > 0:
                self.logger.info(f"✅ Synchronized flash capture completed: {successful_captures}/{len(results)} images")
                
                storage_info = f"Session: {session_id}, Files: {successful_captures}"
                if any(r.get('storage_method') == 'session_manager' for r in results):
                    storage_info += " (stored in session manager)"
                else:
                    storage_info += " (fallback file storage)"
                
                return {
                    'cameras': 'both',
                    'timestamp': timestamp,
                    'flash_used': True,
                    'flash_intensity': flash_intensity,
                    'success': True,
                    'synchronized': True,
                    'capture_results': results,
                    'successful_captures': successful_captures,
                    'session_id': session_id,
                    'storage_info': storage_info
                }
            else:
                raise HardwareError("No cameras captured successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Synchronized flash capture execution failed: {e}")
            raise HardwareError(f"Failed to capture synchronized images with flash: {e}")

    def _store_image_with_metadata_sync(self, image_data, camera_id: int, session_id: str, 
                                       current_position, flash_intensity: int, flash_result) -> str:
        """Store image using proper storage manager with full metadata (synchronous wrapper)"""
        try:
            # Import required modules
            from storage.base import StorageMetadata, DataType
            import uuid
            import hashlib
            import cv2
            import time
            
            # Convert numpy array to JPEG bytes for storage
            _, img_encoded = cv2.imencode('.jpg', image_data, [cv2.IMWRITE_JPEG_QUALITY, 95])
            img_bytes = img_encoded.tobytes()
            
            # Create comprehensive metadata
            metadata = StorageMetadata(
                file_id=str(uuid.uuid4()),
                original_filename=f"manual_capture_camera_{camera_id + 1}.jpg",
                data_type=DataType.RAW_IMAGE,  # Use RAW_IMAGE for manual captures
                file_size_bytes=len(img_bytes),
                checksum=hashlib.sha256(img_bytes).hexdigest(),
                creation_time=time.time(),
                scan_session_id=session_id,
                sequence_number=camera_id,
                position_data={
                    'x': current_position.x if current_position else 0.0,
                    'y': current_position.y if current_position else 0.0,
                    'z': current_position.z if current_position else 0.0,
                    'c': current_position.c if current_position else 0.0
                } if current_position else None,
                camera_settings={
                    'camera_id': camera_id,
                    'resolution': 'high',
                    'capture_mode': 'manual',
                    'image_format': 'JPEG',
                    'quality': 95
                },
                lighting_settings={
                    'flash_used': True,
                    'flash_intensity': flash_intensity,
                    'flash_duration': 100,
                    'flash_result': str(flash_result) if flash_result else 'success'
                },
                tags=['manual_capture', 'flash_sync', f'camera_{camera_id + 1}', 'web_interface']
            )
            
            # Store using async wrapper with error handling
            if not hasattr(self.orchestrator, 'storage_manager') or not self.orchestrator.storage_manager:
                raise Exception("Storage manager not available")
                
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                file_id = loop.run_until_complete(
                    self.orchestrator.storage_manager.store_file(img_bytes, metadata)
                )
                self.logger.info(f"📦 Stored image with metadata: {file_id}")
                return file_id
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Failed to store image with metadata: {e}")
            raise
    
    def _fallback_save_image_sync(self, image_data, camera_id: int, timestamp: str) -> Path:
        """Fallback image saving to filesystem (synchronous)"""
        try:
            from pathlib import Path
            import cv2
            
            # Create output directory
            output_dir = Path.home() / "manual_captures" / datetime.now().strftime('%Y-%m-%d')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save image
            filename = output_dir / f"flash_sync_{timestamp}_camera_{camera_id + 1}.jpg"
            cv2.imwrite(str(filename), image_data, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            self.logger.info(f"💾 Fallback saved: {filename}")
            return filename
            
        except Exception as e:
            self.logger.error(f"Fallback image save failed: {e}")
            raise
    
    def _execute_synchronized_capture(self) -> Dict[str, Any]:
        """Execute synchronized capture from both cameras without flash - SIMPLE WORKING VERSION"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Prepare capture parameters
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            self.logger.info(f"📷 Starting synchronized capture (no flash)")
            
            # Simple approach: Just capture from both cameras like the working dashboard capture
            results = []
            from pathlib import Path
            import cv2
            
            # Create output directory
            output_dir = Path.home() / "manual_captures" / datetime.now().strftime('%Y-%m-%d')
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Capture from both cameras using the same method as the working dashboard
            for camera_id in [0, 1]:
                try:
                    self.logger.info(f"📸 Capturing camera {camera_id + 1}")
                    
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        image_data = loop.run_until_complete(
                            self.orchestrator.camera_manager.capture_high_resolution(camera_id)
                        )
                    finally:
                        loop.close()
                    
                    if image_data is not None:
                        # Save image
                        filename = output_dir / f"sync_{timestamp}_camera_{camera_id + 1}.jpg"
                        cv2.imwrite(str(filename), image_data, [cv2.IMWRITE_JPEG_QUALITY, 95])
                        results.append({
                            'camera_id': camera_id, 
                            'filename': str(filename),
                            'success': True
                        })
                        self.logger.info(f"✅ Saved camera {camera_id + 1}: {filename}")
                    else:
                        self.logger.error(f"❌ Camera {camera_id + 1} returned no data")
                        results.append({
                            'camera_id': camera_id,
                            'success': False,
                            'error': 'No image data'
                        })
                        
                except Exception as cam_error:
                    self.logger.error(f"❌ Failed to capture camera {camera_id + 1}: {cam_error}")
                    results.append({
                        'camera_id': camera_id,
                        'success': False,
                        'error': str(cam_error)
                    })
                    continue
            
            # Count successful captures
            successful_captures = sum(1 for r in results if r.get('success', False))
            
            if successful_captures > 0:
                self.logger.info(f"✅ Synchronized capture completed: {successful_captures}/{len(results)} images")
                self.logger.info(f"📁 Photos saved to: {output_dir}")
                
                return {
                    'cameras': 'both',
                    'timestamp': timestamp,
                    'flash_used': False,
                    'success': True,
                    'synchronized': True,
                    'capture_results': results,
                    'successful_captures': successful_captures,
                    'output_directory': str(output_dir),
                    'storage_info': f'Photos saved to: {output_dir}'
                }
            else:
                raise HardwareError("No cameras captured successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Synchronized capture execution failed: {e}")
            raise HardwareError(f"Failed to capture synchronized images: {e}")
    
    def _execute_camera_controls(self, camera_id: str, controls: Dict[str, Any]) -> Dict[str, Any]:
        """Execute camera control settings"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Apply camera controls asynchronously
            import asyncio
            try:
                # Run the async method in a new event loop
                result = asyncio.run(
                    self.orchestrator.camera_manager.set_camera_controls(camera_id, controls)
                )
            except RuntimeError:
                # If there's already an event loop, create a task and run it
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Use run_in_executor for thread safety
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.orchestrator.camera_manager.set_camera_controls(camera_id, controls)
                        )
                        result = future.result(timeout=5.0)
                else:
                    result = loop.run_until_complete(
                        self.orchestrator.camera_manager.set_camera_controls(camera_id, controls)
                    )
            
            self.logger.info(f"Camera controls applied: Camera {camera_id}, Controls: {controls}")
            
            return {
                'camera_id': camera_id,
                'controls': controls,
                'success': True,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Camera controls execution failed: {e}")
            raise HardwareError(f"Failed to set camera controls: {e}")
    
    def _execute_camera_autofocus(self, camera_id: str) -> Dict[str, Any]:
        """Execute autofocus trigger"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Trigger autofocus
            import asyncio
            try:
                # Run the async method in a new event loop
                result = asyncio.run(
                    self.orchestrator.camera_manager.trigger_autofocus(camera_id)
                )
            except RuntimeError:
                # If there's already an event loop, create a task and run it
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Use run_in_executor for thread safety
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.orchestrator.camera_manager.trigger_autofocus(camera_id)
                        )
                        result = future.result(timeout=5.0)
                else:
                    result = loop.run_until_complete(
                        self.orchestrator.camera_manager.trigger_autofocus(camera_id)
                    )
            
            self.logger.info(f"Autofocus triggered: Camera {camera_id}")
            
            return {
                'camera_id': camera_id,
                'action': 'autofocus',
                'success': True,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Autofocus execution failed: {e}")
            raise HardwareError(f"Failed to trigger autofocus: {e}")
    
    def _execute_manual_focus(self, camera_id: str, focus_position: float) -> Dict[str, Any]:
        """Execute manual focus setting"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Set manual focus
            import asyncio
            try:
                # Run the async method in a new event loop
                result = asyncio.run(
                    self.orchestrator.camera_manager.set_manual_focus(camera_id, focus_position)
                )
            except RuntimeError:
                # If there's already an event loop, create a task and run it
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Use run_in_executor for thread safety
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.orchestrator.camera_manager.set_manual_focus(camera_id, focus_position)
                        )
                        result = future.result(timeout=5.0)
                else:
                    result = loop.run_until_complete(
                        self.orchestrator.camera_manager.set_manual_focus(camera_id, focus_position)
                    )
            
            self.logger.info(f"Manual focus set: Camera {camera_id}, Position: {focus_position}")
            
            return {
                'camera_id': camera_id,
                'focus_position': focus_position,
                'success': True,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Manual focus execution failed: {e}")
            raise HardwareError(f"Failed to set manual focus: {e}")
    
    def _get_camera_detailed_status(self, camera_id: str) -> Dict[str, Any]:
        """Get detailed camera status including controls"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Get current camera controls
            import asyncio
            try:
                # Run the async method in a new event loop
                controls = asyncio.run(
                    self.orchestrator.camera_manager.get_camera_controls(camera_id)
                )
            except RuntimeError:
                # If there's already an event loop, handle it
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Use run_in_executor for thread safety
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            self.orchestrator.camera_manager.get_camera_controls(camera_id)
                        )
                        controls = future.result(timeout=5.0)
                else:
                    controls = loop.run_until_complete(
                        self.orchestrator.camera_manager.get_camera_controls(camera_id)
                    )
            except Exception:
                # Fallback if async method doesn't exist or fails
                controls = {}
            
            # Get basic status
            basic_status = self.orchestrator.camera_manager.get_status()
            
            return {
                'camera_id': camera_id,
                'basic_status': basic_status,
                'controls': controls,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Camera detailed status failed: {e}")
            return {
                'camera_id': camera_id,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _execute_lighting_flash(self, zone: str, brightness: float, duration: int) -> Dict[str, Any]:
        """Execute lighting flash command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'lighting_controller') or not self.orchestrator.lighting_controller:
                raise HardwareError("Lighting controller not available")
            
            # Execute flash
            from lighting.base import LightingSettings
            flash_settings = LightingSettings(brightness=brightness, duration_ms=duration)
            # Execute flash using synchronous wrapper
            try:
                if zone == 'all':
                    # Flash all zones
                    result = self.orchestrator.lighting_controller.flash_sync(['all'], flash_settings)
                else:
                    # Flash specific zone
                    result = self.orchestrator.lighting_controller.flash_sync([zone], flash_settings)
                    
                self.logger.info(f"Lighting flash executed: Zone {zone}, Brightness {brightness}")
            except Exception as e:
                self.logger.error(f"Flash execution failed: {e}")
                raise HardwareError(f"Failed to execute lighting flash: {e}")
            
            return {
                'zone': zone,
                'brightness': brightness,
                'duration': duration,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Lighting flash execution failed: {e}")
            raise HardwareError(f"Failed to execute lighting flash: {e}")
    
    def _create_fallback_frame(self, message: str):
        """Create a lightweight fallback frame for camera streaming"""
        import cv2
        import numpy as np
        
        # Create smaller frame for better performance
        frame = np.full((360, 640, 3), 32, dtype=np.uint8)  # Dark frame
        
        # Add message text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7
        thickness = 2
        
        text_size = cv2.getTextSize(message, font, font_scale, thickness)[0]
        text_x = (640 - text_size[0]) // 2
        text_y = (360 + text_size[1]) // 2
        
        cv2.putText(frame, message, (text_x, text_y), font, font_scale, (128, 128, 128), thickness, cv2.LINE_AA)
        
        return frame
    
    def _generate_camera_stream(self, camera_id):
        """Simplified camera stream focused on Camera 0 only"""
        import time
        import cv2
        import numpy as np
        
        # Only allow Camera 0 streaming
        # Enable both cameras - Camera 0 and Camera 1
        if camera_id not in [0, '0', 1, '1', 'camera_1', 'camera_2']:
            self.logger.warning(f"STREAM DISABLED: Camera {camera_id} not supported, only Camera 0 and 1 supported")
            # Generate a simple "Camera Disabled" frame
            while True:
                # Create a simple disabled camera frame
                frame = np.full((480, 640, 3), 64, dtype=np.uint8)  # Dark gray
                
                # Add text
                font = cv2.FONT_HERSHEY_SIMPLEX
                text = f"Camera {camera_id} Disabled"
                font_scale = 1.0
                thickness = 2
                
                text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]
                text_x = (640 - text_size[0]) // 2
                text_y = (480 + text_size[1]) // 2
                
                cv2.putText(frame, text, (text_x, text_y), font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
                
                # Encode as JPEG
                ret, jpeg_buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    jpeg_data = jpeg_buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n\r\n' +
                           jpeg_data + b'\r\n')
                
                time.sleep(0.1)  # 10 FPS for disabled camera
        
        # High-performance camera streaming - supports both cameras
        self.logger.debug(f"STREAM START: Camera {camera_id} high-performance streaming initialized")
        
        frame_counter = 0
        last_log_time = 0
        fps_target = 20  # Original 20 FPS target
        frame_interval = 1.0 / fps_target
        last_frame_time = 0
        
        while True:
            frame_counter += 1
            current_time = time.time()
            
            # Log every 20 seconds to reduce noise
            should_log = (current_time - last_log_time) > 20.0
            if should_log:
                self.logger.debug(f"STREAM STATUS: Camera {camera_id} - Frame {frame_counter}")
                last_log_time = current_time
            
            # Frame rate control
            time_since_last = current_time - last_frame_time
            if time_since_last < frame_interval:
                time.sleep(frame_interval - time_since_last)
                current_time = time.time()
            
            last_frame_time = current_time
            
            try:
                orchestrator = getattr(self, 'orchestrator', None)
                
                if orchestrator and hasattr(orchestrator, 'camera_manager'):
                    # High-performance streaming with direct frame access
                    try:
                        # Check if we should stop streaming (graceful shutdown)
                        if not getattr(self, '_running', True):
                            self.logger.info("STREAM SHUTDOWN: Graceful camera stream termination")
                            break
                            
                        # Map camera_id to the correct backend camera
                        if camera_id in [0, '0']:
                            camera_key = 'camera_1'
                        elif camera_id in [1, '1']:
                            camera_key = 'camera_2'
                        elif camera_id in ['camera_1', 'camera_2']:
                            camera_key = camera_id
                        else:
                            camera_key = 'camera_1'  # Default fallback
                            
                        frame = orchestrator.camera_manager.get_preview_frame(camera_key)
                        
                        if frame is not None and frame.size > 0:
                            if should_log:
                                self.logger.debug(f"STREAM SUCCESS: High-performance frame received, shape: {frame.shape}")
                            
                            # Original high-quality encoding for smooth streaming
                            encode_params = [
                                cv2.IMWRITE_JPEG_QUALITY, 90,  # High quality for smooth experience
                                cv2.IMWRITE_JPEG_OPTIMIZE, 1,  # Optimize file size
                                cv2.IMWRITE_JPEG_PROGRESSIVE, 1  # Progressive JPEG for faster loading
                            ]
                            ret, jpeg_buffer = cv2.imencode('.jpg', frame, encode_params)
                            
                            if ret and len(jpeg_buffer) > 0:
                                jpeg_data = jpeg_buffer.tobytes()
                                
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n'
                                       b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n\r\n' +
                                       jpeg_data + b'\r\n')
                                continue
                            else:
                                if should_log:
                                    self.logger.warning("STREAM WARNING: JPEG encoding failed")
                        else:
                            if should_log:
                                self.logger.warning("STREAM WARNING: No frame data received")
                    
                    except (SystemExit, KeyboardInterrupt):
                        self.logger.info("STREAM SHUTDOWN: Camera stream terminated by signal")
                        break
                    except Exception as e:
                        if should_log:
                            self.logger.error(f"STREAM ERROR: Frame capture failed: {e}")
                else:
                    if should_log:
                        self.logger.warning("STREAM WARNING: No orchestrator available")
                
                # Lightweight fallback for unavailable camera
                fallback_frame = self._create_fallback_frame(f"Camera {camera_id} - No Signal")
                
                # Encode fallback frame with lower quality
                ret, jpeg_buffer = cv2.imencode('.jpg', fallback_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if ret:
                    jpeg_data = jpeg_buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n\r\n' +
                           jpeg_data + b'\r\n')
                
            except (SystemExit, KeyboardInterrupt):
                self.logger.info("STREAM SHUTDOWN: Camera stream generator terminated gracefully")
                break
            except Exception as e:
                if should_log:
                    self.logger.error(f"STREAM CRITICAL: Unexpected error in Camera {camera_id} stream: {e}")
                time.sleep(0.1)
    
    def start_web_server(self, host='0.0.0.0', port=8080, debug=False, use_reloader=None, production=False):
        """Start the Flask web server (simplified - Flask only)"""
        try:
            self._running = True
            self.logger.info(f"🌐 Starting Flask web interface on http://{host}:{port}")
            
            # Start background thread for status updates
            self._start_status_updater()
            
            # Always use Flask - it's more reliable for Pi hardware with camera streaming
            # Determine reloader setting
            if use_reloader is None:
                use_reloader = debug and not production
            
            # Configure Flask for Pi hardware
            flask_config = {
                'host': host,
                'port': port,
                'debug': debug,
                'use_reloader': use_reloader,
                'threaded': True,  # Enable threading for camera streams
                'processes': 1     # Single process to avoid resource conflicts
            }
            
            if production:
                self.logger.info("🏭 Running Flask in production mode (threaded, no reloader)")
                flask_config['debug'] = False
                flask_config['use_reloader'] = False
            else:
                self.logger.info("🔧 Running Flask in development mode")
            
            # Run the Flask app directly
            self.app.run(**flask_config)
            
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
            raise
    
    # Gunicorn removed - Flask is more reliable for Pi hardware with camera streaming
    
    def stop_web_server(self):
        """Stop the web server"""
        self._running = False
        self.logger.info("Web interface stopped")
    
    def _start_status_updater(self):
        """Start background thread for status updates (simplified version without SocketIO)"""
        def status_updater():
            while self._running:
                try:
                    # In simplified mode, just log status periodically
                    if self.orchestrator:
                        status = self._get_system_status()
                        self.logger.debug(f"System status: {status['system']['status']}")
                    time.sleep(2.0)  # Update every 2 seconds - optimized for responsiveness
                except Exception as e:
                    self.logger.error(f"Status updater error: {e}")
                    time.sleep(5.0)  # Faster recovery from errors
        
        update_thread = threading.Thread(target=status_updater, daemon=True)
        update_thread.start()
        self.logger.info("Status updater started")

    # Storage system integration methods (disabled for now)
    async def _get_or_create_manual_capture_session(self) -> str:
        """Get or create a session for manual captures using the storage system"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'storage_manager'):
                raise HardwareError("Storage manager not available")
            
            storage_manager = self.orchestrator.storage_manager
            
            # Check if there's already an active manual capture session
            if hasattr(storage_manager, 'active_session_id') and storage_manager.active_session_id:
                # Get session info to check if it's a manual capture session
                session = storage_manager.sessions_index.get(storage_manager.active_session_id)
                if session and session.scan_name.startswith("Manual_Captures"):
                    return storage_manager.active_session_id
            
            # Create new manual capture session
            session_metadata = {
                'name': f"Manual_Captures_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                'description': 'Manual camera captures from web interface',
                'operator': 'Web Interface',
                'scan_parameters': {
                    'capture_type': 'manual',
                    'interface': 'web'
                }
            }
            
            session_id = await storage_manager.create_session(session_metadata)
            self.logger.info(f"Created manual capture session: {session_id}")
            return session_id
            
        except Exception as e:
            self.logger.error(f"Failed to create manual capture session: {e}")
            raise HardwareError(f"Manual capture session creation failed: {e}")

    async def _store_manual_captures(self, session_id: str, temp_dir: Path, filename_base: str, 
                                   flash_intensity: int, flash_used: bool) -> Dict[str, Any]:
        """Store manual capture files using the storage system"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'storage_manager'):
                raise HardwareError("Storage manager not available")
            
            storage_manager = self.orchestrator.storage_manager
            
            # Import required classes
            from storage.base import StorageMetadata, DataType
            import hashlib
            import time
            
            # Find captured files in temp directory
            captured_files = []
            for file_path in temp_dir.glob("*.jpg"):
                captured_files.append(file_path)
            
            if not captured_files:
                raise HardwareError("No captured files found to store")
            
            # Store each file in the storage system
            stored_files = []
            for file_path in captured_files:
                try:
                    # Read file data
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                    
                    # Calculate checksum
                    checksum = hashlib.sha256(file_data).hexdigest()
                    
                    # Determine camera ID from filename
                    camera_id = None
                    if "_camera_1.jpg" in file_path.name:
                        camera_id = 0
                    elif "_camera_2.jpg" in file_path.name:
                        camera_id = 1
                    
                    # Create storage metadata
                    metadata = StorageMetadata(
                        file_id="",  # Will be set by storage manager
                        original_filename=file_path.name,
                        data_type=DataType.RAW_IMAGE,
                        file_size_bytes=len(file_data),
                        checksum=checksum,
                        creation_time=time.time(),
                        scan_session_id=session_id,
                        camera_settings={'flash_intensity': flash_intensity, 'flash_used': flash_used},
                        lighting_settings={'flash_intensity': flash_intensity} if flash_used else None,
                        tags=['manual_capture', 'web_interface', f'camera_{camera_id}' if camera_id is not None else 'unknown_camera']
                    )
                    
                    # Store file in storage system
                    file_id = await storage_manager.store_file(file_data, metadata)
                    stored_files.append({
                        'file_id': file_id,
                        'original_filename': file_path.name,
                        'camera_id': camera_id,
                        'file_size': len(file_data)
                    })
                    
                    self.logger.info(f"Stored manual capture: {file_path.name} -> {file_id}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to store file {file_path}: {e}")
                    continue
            
            # Clean up temp directory
            try:
                import shutil
                shutil.rmtree(temp_dir)
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
            
            # Get session info for return
            session = storage_manager.sessions_index.get(session_id)
            session_name = session.scan_name if session else f"Session_{session_id[:8]}"
            
            return {
                'session_id': session_id,
                'session_name': session_name,
                'stored_files': stored_files,
                'total_files': len(stored_files),
                'storage_location': str(storage_manager.base_storage_path / 'sessions' / session_id)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to store manual captures: {e}")
            raise HardwareError(f"Manual capture storage failed: {e}")


if __name__ == "__main__":
    """
    Development mode entry point
    Run the web interface without orchestrator for testing
    """
    import logging
    import asyncio
    from pathlib import Path
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🚀 Starting Scanner Web Interface with FULL storage integration...")
    
    try:
        # Import required modules
        from core.config_manager import ConfigManager
        from scanning.scan_orchestrator import ScanOrchestrator as RealScanOrchestrator
        
        # Load configuration
        config_file = Path(__file__).parent.parent / 'config' / 'scanner_config.yaml'
        config_manager = ConfigManager(config_file)
        
        # Create real orchestrator with storage system
        print("📦 Initializing orchestrator with SessionManager storage...")
        orchestrator = RealScanOrchestrator(config_manager)
        
        # Initialize orchestrator
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(orchestrator.initialize())
            print("✅ Orchestrator initialized with full storage system!")
        finally:
            loop.close()
        
        # Create web interface WITH orchestrator (full integration mode)
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        
        print("🌐 Starting web server with full storage integration...")
        print("📁 Images will be saved with complete metadata!")
        print("💾 Storage location:", config_manager.get('storage.base_path', '/home/pi/scanner_data'))
        print("🔗 Open http://localhost:5000 in your browser")
        print("Press Ctrl+C to stop")
        
        web_interface.start_web_server(host='0.0.0.0', port=5000, debug=True)
        
    except ImportError as e:
        print(f"❌ Could not import orchestrator modules: {e}")
        print("💡 Falling back to development mode without storage")
        
        # Fallback to no orchestrator
        web_interface = ScannerWebInterface(orchestrator=None)
        print("⚠️  Development mode: Files will use fallback storage in ~/manual_captures/")
        print("🔗 Open http://localhost:5000 in your browser")
        web_interface.start_web_server(host='0.0.0.0', port=5000, debug=True)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        if 'web_interface' in locals():
            web_interface.stop_web_server()
    except Exception as e:
        print(f"❌ Failed to start with storage integration: {e}")
        print("💡 Falling back to development mode without storage")
        
        # Fallback to no orchestrator
        web_interface = ScannerWebInterface(orchestrator=None) 
        print("⚠️  Development mode: Files will use fallback storage in ~/manual_captures/")
        print("🔗 Open http://localhost:5000 in your browser")
        web_interface.start_web_server(host='0.0.0.0', port=5000, debug=True)