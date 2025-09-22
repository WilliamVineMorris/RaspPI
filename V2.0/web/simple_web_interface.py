#!/usr/bin/env python3
"""
Simple Flask Web Interface for Scanner System
Simplified version for testing without dependencies
"""

import logging
from pathlib import Path
from flask import Flask, render_template, jsonify, request
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleWebInterface:
    """Simplified web interface for testing"""
    
    def __init__(self):
        # Flask app setup
        self.app = Flask(__name__,
                        template_folder=str(Path(__file__).parent / 'templates'),
                        static_folder=str(Path(__file__).parent / 'static'))
        self.app.config['SECRET_KEY'] = 'scanner_control_secret_key'
        self.logger = logger
        
        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        def get_mock_status():
            """Get mock system status for templates"""
            return {
                'system': {
                    'status': 'ready',
                    'timestamp': datetime.now().isoformat(),
                    'errors': [],
                    'warnings': []
                },
                'motion': {
                    'status': 'ready',
                    'position': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0},
                    'homed': [True, True, True, True],
                    'moving': False
                },
                'camera': {
                    'status': 'ready',
                    'cameras': ['camera_0', 'camera_1'],
                    'active_camera': 'camera_0',
                    'resolution': '1920x1080'
                },
                'lighting': {
                    'status': 'ready',
                    'zones': ['zone_1', 'zone_2', 'zone_3', 'zone_4']
                },
                'scan': {
                    'active': False,
                    'status': 'idle',
                    'progress': 0.0,
                    'current_point': 0,
                    'total_points': 0,
                    'phase': 'idle'
                },
                'timestamp': datetime.now().isoformat()
            }
        
        @self.app.route('/')
        def index():
            status = get_mock_status()
            return render_template('dashboard.html', status=status)
        
        @self.app.route('/dashboard')
        def dashboard():
            status = get_mock_status()
            return render_template('dashboard.html', status=status)
        
        @self.app.route('/manual')
        def manual():
            status = get_mock_status()
            # Add position limits and other manual control data
            position_limits = {
                'x': [-100, 100],
                'y': [-100, 100], 
                'z': [0, 50],
                'c': [-360, 360]
            }
            return render_template('manual.html', status=status, position_limits=position_limits)
        
        @self.app.route('/scans')
        def scans():
            # Mock scan data
            scan_history = [
                {
                    'id': 'scan_001',
                    'name': 'Test Scan 1',
                    'timestamp': '2025-09-20T10:30:00',
                    'status': 'completed',
                    'points': 100,
                    'duration': '00:15:30'
                },
                {
                    'id': 'scan_002', 
                    'name': 'Test Scan 2',
                    'timestamp': '2025-09-21T14:20:00',
                    'status': 'completed',
                    'points': 150,
                    'duration': '00:22:45'
                }
            ]
            status = get_mock_status()
            return render_template('scans.html', status=status, scan_history=scan_history)
        
        @self.app.route('/settings')
        def settings():
            status = get_mock_status()
            return render_template('settings.html', status=status)
        
        # API routes with mock responses
        @self.app.route('/api/status')
        def get_status():
            """Mock system status"""
            return jsonify({
                'system': {
                    'status': 'ready',
                    'timestamp': datetime.now().isoformat(),
                    'errors': [],
                    'warnings': []
                },
                'motion': {
                    'status': 'ready',
                    'position': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0},
                    'homed': [True, True, True, True],
                    'moving': False
                },
                'camera': {
                    'status': 'ready',
                    'cameras': ['camera_0', 'camera_1'],
                    'active_camera': 'camera_0',
                    'resolution': '1920x1080'
                },
                'lighting': {
                    'status': 'ready',
                    'zones': ['zone_1', 'zone_2', 'zone_3', 'zone_4']
                },
                'scan': {
                    'active': False,
                    'status': 'idle',
                    'progress': 0.0,
                    'current_point': 0,
                    'total_points': 0,
                    'phase': 'idle'
                }
            })
        
        @self.app.route('/api/control/move', methods=['POST'])
        def move_axis():
            """Mock axis movement"""
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': f"Mock move: {data.get('axis')} by {data.get('distance')}mm",
                'position': {'x': 10.0, 'y': 20.0, 'z': 5.0, 'c': 0.0}
            })
        
        @self.app.route('/api/control/position', methods=['POST'])
        def move_to_position():
            """Mock position movement"""
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': f"Mock move to position: {data.get('position')}",
                'position': data.get('position', {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0})
            })
        
        @self.app.route('/api/control/home', methods=['POST'])
        def home_axes():
            """Mock homing"""
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': f"Mock homing: {data.get('axes', [])}",
                'position': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
            })
        
        @self.app.route('/api/control/emergency_stop', methods=['POST'])
        def emergency_stop():
            """Mock emergency stop"""
            return jsonify({
                'success': True,
                'message': 'Mock emergency stop activated'
            })
        
        @self.app.route('/api/scan/start', methods=['POST'])
        def start_scan():
            """Mock scan start"""
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': f"Mock scan started with pattern: {data.get('pattern_type', 'unknown')}",
                'scan_id': 'mock_scan_001'
            })
        
        @self.app.route('/api/scan/stop', methods=['POST'])
        def stop_scan():
            """Mock scan stop"""
            return jsonify({
                'success': True,
                'message': 'Mock scan stopped'
            })
        
        @self.app.route('/api/scan/pause', methods=['POST'])
        def pause_resume_scan():
            """Mock scan pause/resume"""
            return jsonify({
                'success': True,
                'message': 'Mock scan paused/resumed'
            })
        
        @self.app.route('/api/camera/capture', methods=['POST'])
        def capture_image():
            """Mock image capture"""
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': f"Mock image captured from {data.get('camera_id', 'unknown')}",
                'filename': f"mock_image_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            })
        
        @self.app.route('/api/lighting/flash', methods=['POST'])
        def flash_lighting():
            """Mock lighting flash"""
            data = request.get_json()
            return jsonify({
                'success': True,
                'message': f"Mock lighting flash: {data.get('zone', 'all')} zones"
            })
        
        # Add mock camera preview routes
        @self.app.route('/camera/<camera_id>')
        def camera_preview(camera_id):
            """Mock camera preview"""
            return jsonify({
                'success': True,
                'message': f"Mock camera {camera_id} preview",
                'preview_url': f'/static/mock_preview_{camera_id}.jpg'
            })
    
    def run(self, host='0.0.0.0', port=5000, debug=True):
        """Run the web interface"""
        self.logger.info(f"Starting Simple Web Interface on http://{host}:{port}")
        self.app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    """
    Simple development server
    """
    print("="*60)
    print("Scanner Web Interface - Simple Development Version")
    print("="*60)
    print("Features:")
    print("- All web templates and styling")
    print("- Mock API responses for testing")
    print("- No hardware dependencies")
    print("- Full UI functionality testing")
    print("="*60)
    print("")
    print("Starting server...")
    print("Open http://localhost:5000 in your browser")
    print("Press Ctrl+C to stop")
    print("")
    
    try:
        web_interface = SimpleWebInterface()
        web_interface.run(host='0.0.0.0', port=5000, debug=True)
    except KeyboardInterrupt:
        print("\nShutting down...")