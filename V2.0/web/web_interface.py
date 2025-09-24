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
    
    class ScanOrchestrator:
        def __init__(self, *args, **kwargs):
            self.scan_status = ScanStatus.IDLE
        
        async def get_status(self):
            return {"status": self.scan_status}
        
        async def initialize_system(self):
            return True
        
        async def emergency_stop(self):
            return True

logger = logging.getLogger(__name__)


class WebInterfaceError(Exception):
    """Web interface specific errors"""
    pass


class CommandValidator:
    """Validates web interface commands for safety and correctness"""
    
    # Safety limits for manual control
    POSITION_LIMITS = {
        'x': (-100.0, 100.0),  # mm
        'y': (-100.0, 100.0),  # mm
        'z': (0.0, 50.0),      # mm
        'c': (-360.0, 360.0)   # degrees
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
        
        self.logger.info("Scanner web interface initialized")
    
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
            """Get current system status"""
            try:
                return jsonify({
                    'success': True,
                    'data': self._get_system_status(),
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
                
                # Execute movement
                result = self._execute_position_command(validated_position)
                
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
            """Home axes"""
            try:
                data = request.get_json() or {}
                axes = data.get('axes', ['x', 'y', 'z', 'c'])  # Default: home all
                
                result = self._execute_home_command(axes)
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
                self.logger.error(f"Home API error: {e}")
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
                        debug_info['is_connected'] = controller.is_connected() if hasattr(controller, 'is_connected') else False
                        
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
            try:
                data = request.get_json() or {}
                
                # Validate jog parameters
                axis = data.get('axis', '').lower()
                direction = data.get('direction', '')
                mode = data.get('mode', 'step')
                distance = data.get('distance', 1.0)
                speed = data.get('speed', 10.0)
                
                if axis not in ['x', 'y', 'z', 'c']:
                    return jsonify({"success": False, "error": "Invalid axis"}), 400
                
                if direction not in ['+', '-']:
                    return jsonify({"success": False, "error": "Invalid direction"}), 400
                
                # Convert to the correct format expected by _execute_move_command
                move_distance = distance if direction == '+' else -distance
                
                if mode == 'continuous':
                    # For continuous jog, use smaller increments
                    move_distance = 0.5 if direction == '+' else -0.5
                
                # Format command as Position4D delta for FluidNC controller
                delta_values = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
                delta_values[axis] = move_distance
                
                # Execute the movement using Position4D format
                result = asyncio.run(self._execute_jog_command(delta_values, speed))
                
                return jsonify({
                    'success': True,
                    'data': result,
                    'timestamp': datetime.now().isoformat()
                })
                
            except Exception as e:
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
            """Capture image from camera"""
            try:
                data = request.get_json() or {}
                camera_id = data.get('camera_id', 0)
                
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
                    
                    # Get status information from controller properties
                    connected = motion_controller.is_connected() if hasattr(motion_controller, 'is_connected') else False
                    homed = motion_controller.is_homed if hasattr(motion_controller, 'is_homed') else False
                    current_status = motion_controller.status if hasattr(motion_controller, 'status') else 'unknown'
                    
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
                    
                    # Convert MotionStatus enum to string
                    status_str = str(current_status).split('.')[-1].lower() if hasattr(current_status, 'name') else str(current_status).lower()
                    
                    # Get alarm state information
                    alarm_info = {
                        'is_alarm': status_str == 'alarm',
                        'is_error': status_str == 'error',
                        'can_move': status_str not in ['alarm', 'error'],
                        'alarm_code': None,
                        'message': ''
                    }
                    
                    # Try to get detailed alarm information from the controller
                    if hasattr(motion_controller, 'controller') and hasattr(motion_controller.controller, 'get_alarm_state'):
                        try:
                            # Get alarm details asynchronously but safely
                            import concurrent.futures
                            import asyncio
                            
                            def get_alarm_info():
                                # Run in a separate thread to avoid blocking the main web thread
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                                try:
                                    return loop.run_until_complete(motion_controller.controller.get_alarm_state())
                                except Exception as e:
                                    self.logger.warning(f"Could not get alarm details: {e}")
                                    return alarm_info
                                finally:
                                    loop.close()
                            
                            # Quick async call with timeout
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(get_alarm_info)
                                try:
                                    detailed_alarm_info = future.result(timeout=0.1)  # 100ms timeout
                                    alarm_info.update(detailed_alarm_info)
                                except concurrent.futures.TimeoutError:
                                    self.logger.debug("Alarm info timeout - using basic status")
                                except Exception as e:
                                    self.logger.debug(f"Alarm info error: {e}")
                        except Exception as e:
                            self.logger.debug(f"Could not get detailed alarm info: {e}")
                    
                    # Determine activity based on status
                    activity_map = {
                        'homing': 'homing',
                        'moving': 'moving', 
                        'jogging': 'jogging',
                        'idle': 'idle',
                        'disconnected': 'disconnected',
                        'error': 'error',
                        'alarm': 'alarm'  # Keep alarm separate from error
                    }
                    activity = activity_map.get(status_str, 'unknown')
                    
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
                    camera_status = self.orchestrator.camera_manager.get_status()
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
    
    async def _execute_jog_command(self, delta_values: Dict[str, float], speed: float) -> Dict[str, Any]:
        """Execute jog movement with Position4D format"""
        try:
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
            
            # Execute the jog movement
            result = await self.orchestrator.motion_controller.move_relative(delta, feedrate=speed)
            
            # Force fresh position update after jog movement
            try:
                fresh_position = await self.orchestrator.motion_controller.get_current_position()
                self.logger.info(f"🎯 Fresh position after jog: {fresh_position}")
                cached_position = fresh_position
            except Exception as pos_e:
                self.logger.warning(f"Could not get fresh position after jog: {pos_e}")
                # Fall back to cached position from controller
                cached_position = self.orchestrator.motion_controller.current_position
            
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
            
            # SAFETY CHECK: Get alarm state before allowing movement
            motion_controller = self.orchestrator.motion_controller
            if hasattr(motion_controller, 'controller') and hasattr(motion_controller.controller, 'get_alarm_state'):
                try:
                    alarm_info = await motion_controller.controller.get_alarm_state()
                    if alarm_info.get('is_alarm', False):
                        raise HardwareError(f"Movement blocked - FluidNC in ALARM state. {alarm_info.get('message', '')}")
                    if alarm_info.get('is_error', False):
                        raise HardwareError(f"Movement blocked - FluidNC in ERROR state. {alarm_info.get('message', '')}")
                    if not alarm_info.get('can_move', True):
                        raise HardwareError(f"Movement blocked - FluidNC not ready for movement. Status: {alarm_info.get('status', 'unknown')}")
                except Exception as safety_e:
                    # If we can't check safety, err on the side of caution
                    self.logger.warning(f"Could not verify system safety before movement: {safety_e}")
                    # But allow movement if it's just a communication issue
                    if "alarm" in str(safety_e).lower():
                        raise  # Re-raise alarm-related errors
            
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
            result = await self.orchestrator.motion_controller.move_relative(delta)
            
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
            
            # SAFETY CHECK: Get alarm state before allowing movement
            motion_controller = self.orchestrator.motion_controller
            if hasattr(motion_controller, 'controller') and hasattr(motion_controller.controller, 'get_alarm_state'):
                try:
                    alarm_info = await motion_controller.controller.get_alarm_state()
                    if alarm_info.get('is_alarm', False):
                        raise HardwareError(f"Position movement blocked - FluidNC in ALARM state. {alarm_info.get('message', '')}")
                    if alarm_info.get('is_error', False):
                        raise HardwareError(f"Position movement blocked - FluidNC in ERROR state. {alarm_info.get('message', '')}")
                    if not alarm_info.get('can_move', True):
                        raise HardwareError(f"Position movement blocked - FluidNC not ready. Status: {alarm_info.get('status', 'unknown')}")
                except Exception as safety_e:
                    # If we can't check safety, err on the side of caution
                    self.logger.warning(f"Could not verify system safety before position movement: {safety_e}")
                    # But allow movement if it's just a communication issue
                    if "alarm" in str(safety_e).lower():
                        raise  # Re-raise alarm-related errors
            
            # Execute the position movement
            result = await self.orchestrator.motion_controller.move_to_position(position)
            
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
                    result = self.orchestrator.motion_controller.home_axes(axes)
                    self.logger.info(f"Homing sequence completed for axes: {axes}, result: {result}")
                except Exception as e:
                    self.logger.error(f"Homing failed: {e}")
            
            # Start homing thread
            home_thread = threading.Thread(target=home_task)
            home_thread.daemon = True
            home_thread.start()
            
            # Return immediate response
            return {
                'message': f'Homing sequence started for axes: {", ".join(axes)}',
                'status': 'in_progress',
                'axes': axes,
                'success': True
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
        """Execute camera capture command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'camera_manager') or not self.orchestrator.camera_manager:
                raise HardwareError("Camera manager not available")
            
            # Capture image
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"manual_capture_{camera_id}_{timestamp}.jpg"
            
            # This would be implemented based on your camera manager API
            result = asyncio.create_task(
                self.orchestrator.camera_manager.capture_image(camera_id, filename)
            )
            
            self.logger.info(f"Camera capture executed: Camera {camera_id}")
            
            return {
                'camera_id': camera_id,
                'filename': filename,
                'timestamp': timestamp,
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Camera capture execution failed: {e}")
            raise HardwareError(f"Failed to capture image: {e}")
    
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
                    time.sleep(5.0)  # Update every 5 seconds
                except Exception as e:
                    self.logger.error(f"Status updater error: {e}")
                    time.sleep(10.0)
        
        update_thread = threading.Thread(target=status_updater, daemon=True)
        update_thread.start()
        self.logger.info("Status updater started")


if __name__ == "__main__":
    """
    Development mode entry point
    Run the web interface without orchestrator for testing
    """
    import logging
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create web interface without orchestrator (development mode)
    web_interface = ScannerWebInterface(orchestrator=None)
    
    print("Starting Scanner Web Interface in development mode...")
    print("Open http://localhost:5000 in your browser")
    print("Press Ctrl+C to stop")
    
    try:
        web_interface.start_web_server(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
        web_interface.stop_web_server()