#!/usr/bin/env python3
"""
Integrated Camera Positioning and Photo Capture System

This module combines the GRBL-based camera positioning system with live video streaming
and high-resolution photo capture at each movement position. It provides automated
scanning capabilities with photo documentation at specified positions.

Features:
- Live video streaming during movement
- High-resolution photo capture at stationary positions
- GRBL motion control integration
- Path planning and execution
- Web interface for monitoring and control
"""

import serial
import time
import math
import threading
import requests
import json
import os
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime
from flask import Flask, Response, send_file, jsonify, render_template_string
from picamera2 import Picamera2
import cv2
import io

# Import our camera positioning system
from camera_positioning_gcode import (
    ArduinoGCodeController, 
    CameraPositionController, 
    PathPlanner, 
    Point, 
    MovementType
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CaptureMode(Enum):
    """Photo capture modes"""
    STREAMING_ONLY = "streaming"
    PHOTO_AT_POSITION = "photo_position"
    PHOTO_AND_STREAMING = "both"

@dataclass
class ScanConfig:
    """Configuration for scanning operations"""
    photo_directory: str = "captured_photos"
    capture_mode: CaptureMode = CaptureMode.PHOTO_AT_POSITION
    stabilization_delay: float = 1.0  # Seconds to wait after movement before photo
    movement_feedrate: float = 500    # mm/min movement speed
    safe_height: float = 10.0         # Safe Z height for movements

class IntegratedCameraSystem:
    """Combined camera positioning and photo capture system"""
    
    def __init__(self, grbl_port: str = '/dev/ttyUSB0', video_server_port: int = 5000):
        """
        Initialize the integrated camera system
        
        Args:
            grbl_port: Serial port for GRBL controller
            video_server_port: Port for video streaming server
        """
        # Initialize GRBL controller
        self.grbl_controller = ArduinoGCodeController(grbl_port)
        self.camera_controller = CameraPositionController(self.grbl_controller)
        self.path_planner = PathPlanner(self.grbl_controller)
        
        # Initialize camera system
        self.picam2 = None
        self.video_config = None
        self.still_config = None
        self.current_mode = "video"
        self.mode_lock = threading.Lock()
        
        # Flask app for web interface
        self.app = Flask(__name__)
        self.video_server_port = video_server_port
        
        # Scan configuration
        self.scan_config = ScanConfig()
        self.current_scan_data = {
            "active": False,
            "total_positions": 0,
            "completed_positions": 0,
            "current_position": None,
            "photos_captured": []
        }
        
        # Initialize camera
        self._init_camera()
        
        # Setup Flask routes
        self._setup_routes()
        
        # Photo storage
        self.ensure_photo_directory()
    
    def _init_camera(self):
        """Initialize Picamera2 with video and still configurations"""
        try:
            self.picam2 = Picamera2()
            self.video_config = self.picam2.create_video_configuration(main={"size": (1280, 720)})
            self.still_config = self.picam2.create_still_configuration(main={"size": (3280, 2464)})
            self.picam2.configure(self.video_config)
            self.picam2.start()
            logger.info("Camera initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            raise
    
    def ensure_photo_directory(self):
        """Create photo directory if it doesn't exist"""
        if not os.path.exists(self.scan_config.photo_directory):
            os.makedirs(self.scan_config.photo_directory)
            logger.info(f"Created photo directory: {self.scan_config.photo_directory}")
    
    def initialize_positioning_system(self, configure_grbl: bool = False) -> bool:
        """Initialize the GRBL positioning system"""
        logger.info("Initializing GRBL positioning system...")
        success = self.camera_controller.initialize_system(configure_grbl=configure_grbl)
        if success:
            logger.info("GRBL positioning system initialized successfully")
        else:
            logger.error("Failed to initialize GRBL positioning system")
        return success
    
    def capture_photo_at_position(self, position: Point, position_name: str = None) -> str:
        """
        Capture high-resolution photo at current position
        
        Args:
            position: Current position for metadata
            position_name: Optional name for the position
            
        Returns:
            Filename of captured photo
        """
        try:
            with self.mode_lock:
                # Generate filename with position data
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if position_name:
                    filename = f"scan_{position_name}_{timestamp}.jpg"
                else:
                    filename = f"scan_X{position.x:.1f}_Y{position.y:.1f}_Z{position.z:.1f}_{timestamp}.jpg"
                
                filepath = os.path.join(self.scan_config.photo_directory, filename)
                
                # Stop streaming and switch to high-res mode
                self.picam2.stop()
                self.picam2.configure(self.still_config)
                self.picam2.start()
                
                # Stabilization delay after movement
                time.sleep(self.scan_config.stabilization_delay)
                
                # Capture photo to file
                self.picam2.capture_file(filepath)
                
                # Resume video streaming
                self.picam2.stop()
                self.picam2.configure(self.video_config)
                self.picam2.start()
                
                # Add metadata
                photo_info = {
                    "filename": filename,
                    "filepath": filepath,
                    "position": {"x": position.x, "y": position.y, "z": position.z},
                    "timestamp": timestamp,
                    "position_name": position_name
                }
                
                self.current_scan_data["photos_captured"].append(photo_info)
                
                logger.info(f"Photo captured: {filename} at position X{position.x:.1f} Y{position.y:.1f} Z{position.z:.1f}")
                return filename
                
        except Exception as e:
            logger.error(f"Failed to capture photo: {e}")
            # Ensure video mode is restored
            try:
                self.picam2.stop()
                self.picam2.configure(self.video_config)
                self.picam2.start()
            except:
                pass
            return None
    
    def execute_scan_with_photos(self, scan_path: List[Point], scan_name: str = "scan") -> bool:
        """
        Execute a scan path with photo capture at each position
        
        Args:
            scan_path: List of points to visit
            scan_name: Name for this scan session
            
        Returns:
            True if scan completed successfully
        """
        if not self.grbl_controller.is_connected:
            logger.error("GRBL controller not connected")
            return False
        
        # Initialize scan data
        self.current_scan_data.update({
            "active": True,
            "total_positions": len(scan_path),
            "completed_positions": 0,
            "current_position": None,
            "photos_captured": [],
            "scan_name": scan_name,
            "start_time": datetime.now().isoformat()
        })
        
        logger.info(f"Starting scan '{scan_name}' with {len(scan_path)} positions")
        
        try:
            for i, position in enumerate(scan_path):
                # Update current position
                self.current_scan_data["current_position"] = {
                    "x": position.x, "y": position.y, "z": position.z
                }
                
                logger.info(f"Moving to position {i+1}/{len(scan_path)}: X{position.x:.1f} Y{position.y:.1f} Z{position.z:.1f}")
                
                # Move to position
                success = self.grbl_controller.move_to_point(
                    position, 
                    feedrate=self.scan_config.movement_feedrate
                )
                
                if not success:
                    logger.error(f"Failed to move to position {i+1}")
                    return False
                
                # Capture photo if configured
                if self.scan_config.capture_mode in [CaptureMode.PHOTO_AT_POSITION, CaptureMode.PHOTO_AND_STREAMING]:
                    position_name = f"{scan_name}_pos_{i+1:03d}"
                    filename = self.capture_photo_at_position(position, position_name)
                    
                    if filename:
                        logger.info(f"Photo captured: {filename}")
                    else:
                        logger.warning(f"Failed to capture photo at position {i+1}")
                
                # Update progress
                self.current_scan_data["completed_positions"] = i + 1
                
                # Brief pause between positions
                time.sleep(0.5)
            
            # Scan completed
            self.current_scan_data.update({
                "active": False,
                "completed": True,
                "end_time": datetime.now().isoformat()
            })
            
            logger.info(f"Scan '{scan_name}' completed successfully! Captured {len(self.current_scan_data['photos_captured'])} photos")
            
            # Generate scan report
            self._generate_scan_report()
            
            return True
            
        except Exception as e:
            logger.error(f"Scan failed: {e}")
            self.current_scan_data.update({
                "active": False,
                "error": str(e)
            })
            return False
    
    def grid_scan_with_photos(self, corner1: Point, corner2: Point, grid_size: Tuple[int, int] = (5, 5)) -> bool:
        """Perform grid scan with photo capture"""
        # Generate scan path
        min_point = Point(min(corner1.x, corner2.x), min(corner1.y, corner2.y), self.scan_config.safe_height)
        max_point = Point(max(corner1.x, corner2.x), max(corner1.y, corner2.y), self.scan_config.safe_height)
        
        scan_path = self.path_planner.generate_grid_scan_path(min_point, max_point, grid_size[0], grid_size[1])
        
        scan_name = f"grid_{grid_size[0]}x{grid_size[1]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return self.execute_scan_with_photos(scan_path, scan_name)
    
    def circular_scan_with_photos(self, center: Point, radius: float, num_positions: int = 8) -> bool:
        """Perform circular scan with photo capture"""
        center.z = self.scan_config.safe_height
        scan_path = self.path_planner.generate_circular_path(center, radius, 0, 360, num_positions)
        
        scan_name = f"circular_r{radius}_{num_positions}pos_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        return self.execute_scan_with_photos(scan_path, scan_name)
    
    def _generate_scan_report(self):
        """Generate a JSON report of the completed scan"""
        try:
            report_filename = f"scan_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            report_path = os.path.join(self.scan_config.photo_directory, report_filename)
            
            with open(report_path, 'w') as f:
                json.dump(self.current_scan_data, f, indent=2)
            
            logger.info(f"Scan report saved: {report_filename}")
        except Exception as e:
            logger.error(f"Failed to generate scan report: {e}")
    
    # Flask routes for web interface
    def _setup_routes(self):
        """Setup Flask routes for web interface"""
        
        @self.app.route('/')
        def index():
            """Main control interface"""
            return render_template_string(CONTROL_INTERFACE_HTML)
        
        @self.app.route('/video_feed')
        def video_feed():
            """Live video stream"""
            return Response(self._generate_frames(),
                          mimetype='multipart/x-mixed-replace; boundary=frame')
        
        @self.app.route('/scan_status')
        def scan_status():
            """Get current scan status"""
            return jsonify(self.current_scan_data)
        
        @self.app.route('/start_grid_scan/<float:x1>/<float:y1>/<float:x2>/<float:y2>/<int:grid_x>/<int:grid_y>')
        def start_grid_scan(x1, y1, x2, y2, grid_x, grid_y):
            """Start a grid scan"""
            if self.current_scan_data["active"]:
                return jsonify({"error": "Scan already in progress"}), 400
            
            corner1 = Point(x1, y1, self.scan_config.safe_height)
            corner2 = Point(x2, y2, self.scan_config.safe_height)
            
            # Start scan in background thread
            scan_thread = threading.Thread(
                target=self.grid_scan_with_photos, 
                args=(corner1, corner2, (grid_x, grid_y))
            )
            scan_thread.daemon = True
            scan_thread.start()
            
            return jsonify({"message": "Grid scan started", "grid_size": [grid_x, grid_y]})
        
        @self.app.route('/start_circular_scan/<float:center_x>/<float:center_y>/<float:radius>/<int:positions>')
        def start_circular_scan(center_x, center_y, radius, positions):
            """Start a circular scan"""
            if self.current_scan_data["active"]:
                return jsonify({"error": "Scan already in progress"}), 400
            
            center = Point(center_x, center_y, self.scan_config.safe_height)
            
            # Start scan in background thread
            scan_thread = threading.Thread(
                target=self.circular_scan_with_photos,
                args=(center, radius, positions)
            )
            scan_thread.daemon = True
            scan_thread.start()
            
            return jsonify({"message": "Circular scan started", "center": [center_x, center_y], "radius": radius})
        
        @self.app.route('/emergency_stop')
        def emergency_stop():
            """Emergency stop all operations"""
            self.camera_controller.emergency_stop()
            self.current_scan_data["active"] = False
            return jsonify({"message": "Emergency stop activated"})
        
        @self.app.route('/move_to/<float:x>/<float:y>/<float:z>')
        def move_to_position(x, y, z):
            """Move to specific position"""
            if self.current_scan_data["active"]:
                return jsonify({"error": "Cannot move during active scan"}), 400
            
            target = Point(x, y, z)
            success = self.grbl_controller.move_to_point(target)
            
            if success:
                return jsonify({"message": f"Moved to X{x} Y{y} Z{z}"})
            else:
                return jsonify({"error": "Movement failed"}), 500
        
        @self.app.route('/capture_single_photo')
        def capture_single_photo():
            """Capture a single photo at current position"""
            current_pos = self.grbl_controller.current_position
            filename = self.capture_photo_at_position(current_pos, "manual")
            
            if filename:
                return jsonify({"message": "Photo captured", "filename": filename})
            else:
                return jsonify({"error": "Photo capture failed"}), 500
        
        @self.app.route('/return_home')
        def return_home():
            """Return to home position"""
            if self.current_scan_data["active"]:
                return jsonify({"error": "Cannot return home during active scan"}), 400
            
            success = self.camera_controller.return_to_home()
            if success:
                return jsonify({"message": "Returned to home position"})
            else:
                return jsonify({"error": "Failed to return home"}), 500
    
    def _generate_frames(self):
        """Generate video frames for streaming"""
        while True:
            try:
                frame = self.picam2.capture_array()
                ret, buffer = cv2.imencode('.jpg', frame)
                frame = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            except Exception as e:
                logger.error(f"Frame generation error: {e}")
                break
    
    def start_web_interface(self):
        """Start the web interface server"""
        logger.info(f"Starting web interface on port {self.video_server_port}")
        self.app.run(host='0.0.0.0', port=self.video_server_port, threaded=True, debug=False)
    
    def shutdown(self):
        """Safely shutdown the system"""
        logger.info("Shutting down integrated camera system")
        
        # Stop any active scan
        self.current_scan_data["active"] = False
        
        # Return to home and disconnect GRBL
        try:
            self.camera_controller.shutdown()
        except:
            pass
        
        # Stop camera
        try:
            if self.picam2:
                self.picam2.stop()
        except:
            pass

# HTML template for control interface
CONTROL_INTERFACE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Integrated Camera Positioning System</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .video-container { text-align: center; margin-bottom: 20px; }
        .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .control-panel { border: 1px solid #ccc; padding: 15px; border-radius: 5px; }
        .status { background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin: 10px 0; }
        button { padding: 10px 15px; margin: 5px; border: none; border-radius: 3px; cursor: pointer; }
        .btn-primary { background-color: #007bff; color: white; }
        .btn-danger { background-color: #dc3545; color: white; }
        .btn-success { background-color: #28a745; color: white; }
        input { padding: 5px; margin: 2px; border: 1px solid #ccc; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Integrated Camera Positioning System</h1>
        
        <div class="video-container">
            <img src="/video_feed" style="max-width: 640px; border: 1px solid #ccc;">
        </div>
        
        <div class="controls">
            <div class="control-panel">
                <h3>Scan Controls</h3>
                <div>
                    <h4>Grid Scan</h4>
                    <input type="number" id="grid_x1" placeholder="X1" value="0">
                    <input type="number" id="grid_y1" placeholder="Y1" value="0">
                    <input type="number" id="grid_x2" placeholder="X2" value="20">
                    <input type="number" id="grid_y2" placeholder="Y2" value="20"><br>
                    <input type="number" id="grid_size_x" placeholder="Grid X" value="3">
                    <input type="number" id="grid_size_y" placeholder="Grid Y" value="3">
                    <button class="btn-primary" onclick="startGridScan()">Start Grid Scan</button>
                </div>
                
                <div>
                    <h4>Circular Scan</h4>
                    <input type="number" id="circle_x" placeholder="Center X" value="10">
                    <input type="number" id="circle_y" placeholder="Center Y" value="10">
                    <input type="number" id="circle_radius" placeholder="Radius" value="5">
                    <input type="number" id="circle_positions" placeholder="Positions" value="8">
                    <button class="btn-primary" onclick="startCircularScan()">Start Circular Scan</button>
                </div>
            </div>
            
            <div class="control-panel">
                <h3>Manual Controls</h3>
                <div>
                    <h4>Move To Position</h4>
                    <input type="number" id="move_x" placeholder="X" value="0">
                    <input type="number" id="move_y" placeholder="Y" value="0">
                    <input type="number" id="move_z" placeholder="Z" value="5">
                    <button class="btn-primary" onclick="moveToPosition()">Move</button>
                </div>
                
                <div>
                    <button class="btn-success" onclick="capturePhoto()">Capture Photo</button>
                    <button class="btn-primary" onclick="returnHome()">Return Home</button>
                    <button class="btn-danger" onclick="emergencyStop()">EMERGENCY STOP</button>
                </div>
            </div>
        </div>
        
        <div class="status" id="status">
            <h3>System Status</h3>
            <div id="status-content">Loading...</div>
        </div>
    </div>
    
    <script>
        function updateStatus() {
            fetch('/scan_status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status-content').innerHTML = 
                        '<strong>Scan Active:</strong> ' + data.active + '<br>' +
                        '<strong>Progress:</strong> ' + data.completed_positions + '/' + data.total_positions + '<br>' +
                        '<strong>Photos Captured:</strong> ' + data.photos_captured.length;
                });
        }
        
        function startGridScan() {
            const x1 = document.getElementById('grid_x1').value;
            const y1 = document.getElementById('grid_y1').value;
            const x2 = document.getElementById('grid_x2').value;
            const y2 = document.getElementById('grid_y2').value;
            const gx = document.getElementById('grid_size_x').value;
            const gy = document.getElementById('grid_size_y').value;
            
            fetch(`/start_grid_scan/${x1}/${y1}/${x2}/${y2}/${gx}/${gy}`)
                .then(response => response.json())
                .then(data => alert(data.message || data.error));
        }
        
        function startCircularScan() {
            const x = document.getElementById('circle_x').value;
            const y = document.getElementById('circle_y').value;
            const r = document.getElementById('circle_radius').value;
            const p = document.getElementById('circle_positions').value;
            
            fetch(`/start_circular_scan/${x}/${y}/${r}/${p}`)
                .then(response => response.json())
                .then(data => alert(data.message || data.error));
        }
        
        function moveToPosition() {
            const x = document.getElementById('move_x').value;
            const y = document.getElementById('move_y').value;
            const z = document.getElementById('move_z').value;
            
            fetch(`/move_to/${x}/${y}/${z}`)
                .then(response => response.json())
                .then(data => alert(data.message || data.error));
        }
        
        function capturePhoto() {
            fetch('/capture_single_photo')
                .then(response => response.json())
                .then(data => alert(data.message || data.error));
        }
        
        function returnHome() {
            fetch('/return_home')
                .then(response => response.json())
                .then(data => alert(data.message || data.error));
        }
        
        function emergencyStop() {
            fetch('/emergency_stop')
                .then(response => response.json())
                .then(data => alert(data.message));
        }
        
        // Update status every 2 seconds
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
"""

def main():
    """Main function to run the integrated system"""
    print("Integrated Camera Positioning and Photo Capture System")
    print("=" * 60)
    
    # Initialize system
    system = IntegratedCameraSystem()
    
    try:
        # Initialize positioning system
        print("Initializing GRBL positioning system...")
        if not system.initialize_positioning_system():
            print("Failed to initialize positioning system!")
            return
        
        print("System initialized successfully!")
        print("\nAvailable operations:")
        print("1. Start web interface")
        print("2. Run test grid scan")
        print("3. Run test circular scan")
        print("4. Manual photo capture test")
        print("5. Exit")
        
        choice = input("\nSelect operation (1-5): ").strip()
        
        if choice == "1":
            print(f"Starting web interface on http://localhost:{system.video_server_port}")
            print("Press Ctrl+C to stop...")
            system.start_web_interface()
            
        elif choice == "2":
            print("Running test grid scan...")
            corner1 = Point(0, 0, 5)
            corner2 = Point(10, 10, 5)
            success = system.grid_scan_with_photos(corner1, corner2, (3, 3))
            print(f"Grid scan {'completed' if success else 'failed'}")
            
        elif choice == "3":
            print("Running test circular scan...")
            center = Point(5, 5, 5)
            success = system.circular_scan_with_photos(center, 3, 6)
            print(f"Circular scan {'completed' if success else 'failed'}")
            
        elif choice == "4":
            print("Testing manual photo capture...")
            pos = Point(0, 0, 5)
            system.grbl_controller.move_to_point(pos)
            filename = system.capture_photo_at_position(pos, "test")
            print(f"Photo captured: {filename}" if filename else "Photo capture failed")
            
        elif choice == "5":
            print("Exiting...")
        
        else:
            print("Invalid choice")
    
    except KeyboardInterrupt:
        print("\nShutdown requested...")
    
    except Exception as e:
        print(f"Error: {e}")
    
    finally:
        system.shutdown()
        print("System shutdown complete")

if __name__ == "__main__":
    main()
