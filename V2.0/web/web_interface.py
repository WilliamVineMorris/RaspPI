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
                result = self._execute_move_command(validated_command)
                
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
            """MJPEG camera stream"""
            try:
                return Response(
                    self._generate_camera_stream(camera_id),
                    mimetype='multipart/x-mixed-replace; boundary=frame'
                )
            except Exception as e:
                self.logger.error(f"Camera stream error: {e}")
                return Response("Camera not available", status=503)
    
    def _setup_orchestrator_integration(self):
        """Setup integration with the scan orchestrator"""
        # This will be implemented to listen to orchestrator events
        # Note: SocketIO functionality temporarily removed for simplified deployment
        pass
    
    # Core system interface methods
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        self.logger.info(f"_get_system_status called with orchestrator: {self.orchestrator is not None}")
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
                self.logger.info(f"Checking motion controller status...")
                try:
                    motion_status = self.orchestrator.motion_controller.get_status()
                    position = self.orchestrator.motion_controller.get_position()
                    
                    self.logger.info(f"Motion status from adapter: {motion_status}")
                    self.logger.info(f"Motion position from adapter: {position}")
                    
                    status['motion'].update({
                        'connected': True,
                        'status': motion_status.get('state', 'unknown'),
                        'position': position
                    })
                except Exception as e:
                    self.logger.error(f"Motion controller status error: {e}")
                    status['system']['errors'].append(f"Motion controller error: {e}")
            else:
                self.logger.warning(f"Motion controller not available: orchestrator={self.orchestrator is not None}, has_attr={hasattr(self.orchestrator, 'motion_controller') if self.orchestrator else False}, controller={getattr(self.orchestrator, 'motion_controller', None) is not None if self.orchestrator else False}")
            
            # Get camera status
            if self.orchestrator and hasattr(self.orchestrator, 'camera_manager') and self.orchestrator.camera_manager:
                self.logger.info(f"Checking camera manager status...")
                try:
                    camera_status = self.orchestrator.camera_manager.get_status()
                    self.logger.info(f"Camera status from adapter: {camera_status}")
                    
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
            self.logger.info(f"Final status being returned: motion.connected={status['motion']['connected']}, cameras.available={status['cameras']['available']}")
            
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
    
    def _execute_move_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated movement command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            axis = command['axis']
            distance = command['distance']
            
            # Execute the movement
            result = self.orchestrator.motion_controller.move_relative(axis, distance)
            
            # Get updated position
            new_position = self.orchestrator.motion_controller.get_position()
            
            self.logger.info(f"Move command executed: {axis} {distance:+.1f}mm")
            
            return {
                'axis': axis,
                'distance': distance,
                'new_position': new_position,
                'success': result
            }
            
        except Exception as e:
            self.logger.error(f"Move command execution failed: {e}")
            raise HardwareError(f"Failed to execute move command: {e}")
    
    def _execute_position_command(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validated position command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            # Execute the position movement
            result = self.orchestrator.motion_controller.move_to_position(position)
            
            # Get updated position
            new_position = self.orchestrator.motion_controller.get_position()
            
            self.logger.info(f"Position command executed: {position}")
            
            return {
                'target_position': position,
                'actual_position': new_position,
                'success': result
            }
            
        except Exception as e:
            self.logger.error(f"Position command execution failed: {e}")
            raise HardwareError(f"Failed to execute position command: {e}")
    
    def _execute_home_command(self, axes: List[str]) -> Dict[str, Any]:
        """Execute homing command"""
        try:
            if not self.orchestrator or not hasattr(self.orchestrator, 'motion_controller') or not self.orchestrator.motion_controller:
                raise HardwareError("Motion controller not available")
            
            # Execute homing
            result = self.orchestrator.motion_controller.home_axes(axes)
            
            # Get position after homing
            position = self.orchestrator.motion_controller.get_position()
            
            self.logger.info(f"Homing command executed for axes: {axes}")
            
            return {
                'homed_axes': axes,
                'position_after_homing': position,
                'success': result
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
    
    def _generate_camera_stream(self, camera_id: int):
        """Generate MJPEG stream using Picamera2's native streaming capabilities"""
        import time
        import cv2
        import threading
        from io import BytesIO
        
        # Cache for error recovery
        last_frame = None
        frame_cache_time = 0
        error_count = 0
        max_errors = 10
        
        # Performance timing
        fps_target = 25  # Increased target FPS
        frame_interval = 1.0 / fps_target
        last_frame_time = 0
        
        self.logger.info(f"Starting optimized native stream for camera {camera_id} at {fps_target} FPS")
        
        while True:
            current_time = time.time()
            
            # Frame rate control - precise timing
            time_since_last = current_time - last_frame_time
            if time_since_last < frame_interval:
                time.sleep(frame_interval - time_since_last)
                current_time = time.time()
            
            last_frame_time = current_time
            
            try:
                # Get orchestrator if available
                orchestrator = getattr(self, 'orchestrator', None)
                
                if orchestrator:
                    # Use direct camera access via orchestrator - this is the fastest method
                    try:
                        # Check if we have real cameras
                        if hasattr(orchestrator.camera_adapter, 'controller') and \
                           hasattr(orchestrator.camera_adapter.controller, 'cameras'):
                            
                            cameras = orchestrator.camera_adapter.controller.cameras
                            if camera_id in cameras:
                                camera = cameras[camera_id]
                                
                                # Use Picamera2's native MJPEG streaming if available
                                try:
                                    # Method 1: Direct MJPEG stream (fastest)
                                    mjpeg_stream = BytesIO()
                                    
                                    # Try native MJPEG capture
                                    camera.capture_file(mjpeg_stream, format='jpeg', 
                                                      name='main', wait=False)
                                    mjpeg_stream.seek(0)
                                    
                                    jpeg_data = mjpeg_stream.getvalue()
                                    
                                    if len(jpeg_data) > 0:
                                        # Cache successful frame
                                        last_frame = jpeg_data
                                        frame_cache_time = current_time
                                        error_count = 0
                                        
                                        # Stream the JPEG directly - no conversion needed!
                                        yield (b'--frame\r\n'
                                               b'Content-Type: image/jpeg\r\n'
                                               b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n\r\n' +
                                               jpeg_data + b'\r\n')
                                        continue
                                    
                                except Exception as mjpeg_error:
                                    self.logger.debug(f"Native MJPEG failed: {mjpeg_error}")
                                    
                                    # Method 2: Array capture with optimized JPEG encoding
                                    try:
                                        array = camera.capture_array("main")
                                        
                                        if array is not None and array.size > 0:
                                            # Handle different array formats
                                            if len(array.shape) == 3:
                                                if array.shape[2] == 3:  # RGB or BGR
                                                    # Assume RGB from camera, convert to BGR for OpenCV
                                                    frame_bgr = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                                                else:
                                                    frame_bgr = array
                                            else:
                                                # Grayscale or other format
                                                frame_bgr = array
                                            
                                            # High-quality JPEG encoding optimized for speed
                                            encode_param = [
                                                cv2.IMWRITE_JPEG_QUALITY, 85,  # Good quality/speed balance
                                                cv2.IMWRITE_JPEG_OPTIMIZE, 1,   # Optimize encoding
                                                cv2.IMWRITE_JPEG_PROGRESSIVE, 0  # Disable progressive for speed
                                            ]
                                            
                                            ret, jpeg_buffer = cv2.imencode('.jpg', frame_bgr, encode_param)
                                            
                                            if ret:
                                                jpeg_data = jpeg_buffer.tobytes()
                                                
                                                # Cache successful frame
                                                last_frame = jpeg_data
                                                frame_cache_time = current_time
                                                error_count = 0
                                                
                                                yield (b'--frame\r\n'
                                                       b'Content-Type: image/jpeg\r\n'
                                                       b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n\r\n' +
                                                       jpeg_data + b'\r\n')
                                                continue
                                            
                                    except Exception as array_error:
                                        self.logger.debug(f"Array capture error: {array_error}")
                    
                    except Exception as direct_error:
                        self.logger.debug(f"Direct camera access failed: {direct_error}")
                    
                    # Method 3: Use orchestrator adapter method (most compatible)
                    try:
                        frame = orchestrator.camera_adapter.get_preview_frame(camera_id)
                        
                        if frame is not None:
                            # High-quality JPEG encoding
                            encode_param = [
                                cv2.IMWRITE_JPEG_QUALITY, 85,
                                cv2.IMWRITE_JPEG_OPTIMIZE, 1,
                                cv2.IMWRITE_JPEG_PROGRESSIVE, 0
                            ]
                            
                            ret, jpeg_buffer = cv2.imencode('.jpg', frame, encode_param)
                            
                            if ret:
                                jpeg_data = jpeg_buffer.tobytes()
                                
                                # Cache successful frame
                                last_frame = jpeg_data
                                frame_cache_time = current_time
                                error_count = 0
                                
                                yield (b'--frame\r\n'
                                       b'Content-Type: image/jpeg\r\n'
                                       b'Content-Length: ' + str(len(jpeg_data)).encode() + b'\r\n\r\n' +
                                       jpeg_data + b'\r\n')
                                continue
                    
                    except Exception as adapter_error:
                        self.logger.debug(f"Adapter method failed: {adapter_error}")
                
                # Error handling - use cached frame if available
                error_count += 1
                
                if last_frame and (current_time - frame_cache_time) < 5.0:  # Use cache for 5 seconds
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n'
                           b'Content-Length: ' + str(len(last_frame)).encode() + b'\r\n\r\n' +
                           last_frame + b'\r\n')
                else:
                    # Generate simple error frame
                    import numpy as np
                    error_img = np.zeros((240, 320, 3), dtype=np.uint8)
                    cv2.putText(error_img, f'Camera {camera_id} Error', (10, 50), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    cv2.putText(error_img, f'Attempts: {error_count}', (10, 100), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                    
                    ret, error_buffer = cv2.imencode('.jpg', error_img)
                    if ret:
                        error_frame = error_buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n'
                               b'Content-Length: ' + str(len(error_frame)).encode() + b'\r\n\r\n' +
                               error_frame + b'\r\n')
                
                # Stop if too many consecutive errors
                if error_count >= max_errors:
                    self.logger.error(f"Camera {camera_id} stream failed after {max_errors} errors")
                    break
                    
            except Exception as e:
                self.logger.error(f"Stream generation error for camera {camera_id}: {e}")
                error_count += 1
                
                if error_count >= max_errors:
                    break
                
                # Brief pause before retry
                time.sleep(0.1)
    
    def start_web_server(self, host='0.0.0.0', port=8080, debug=False, use_reloader=None):
        """Start the Flask web server"""
        try:
            self._running = True
            self.logger.info(f"Starting web interface on http://{host}:{port}")
            
            # Start background thread for status updates
            self._start_status_updater()
            
            # Determine reloader setting
            if use_reloader is None:
                use_reloader = debug
            
            # Run the Flask app directly (no SocketIO)
            self.app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
            
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
            raise
    
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