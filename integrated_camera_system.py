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
import cv2
import io
import numpy as np
import traceback
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from flask import Flask, Response, send_file, jsonify, render_template_string, request

# Try to import Picamera2, but handle gracefully if not available (e.g., on Windows)
try:
    from picamera2 import Picamera2
    PICAMERA_AVAILABLE = True
except ImportError:
    print("Warning: Picamera2 not available - running in test mode")
    Picamera2 = None
    PICAMERA_AVAILABLE = False

# Import our camera positioning system
from camera_positioning_gcode import (
    ArduinoGCodeController, 
    FluidNCController,
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
    """Combined camera positioning and photo capture system (4DOF FluidNC)"""
    
    def __init__(self, controller_port: str = '/dev/ttyUSB0', video_server_port: int = 5000, 
                 use_fluidnc: bool = True):
        """
        Initialize the integrated camera system
        
        Args:
            controller_port: Serial port for FluidNC/GRBL controller
            video_server_port: Port for video streaming server
            use_fluidnc: True for FluidNC (4DOF), False for GRBL (legacy 3DOF)
        """
        # Initialize controller based on type
        if use_fluidnc:
            # Use longer timeout for FluidNC to handle homing operations
            self.controller = FluidNCController(controller_port, timeout=10.0)
            logger.info("Initialized FluidNC controller for 4DOF system with extended timeout")
        else:
            self.controller = ArduinoGCodeController(controller_port)
            logger.info("Initialized GRBL controller for 3DOF system")
            
        self.camera_controller = CameraPositionController(self.controller)
        self.path_planner = PathPlanner(self.controller)
        self.use_fluidnc = use_fluidnc
        
        # Initialize camera system
        self.picam2 = None
        self.video_config = None
        self.still_config = None
        self.current_mode = "video"
        self.mode_lock = threading.Lock()
        
        # Flask app for web interface
        self.app = Flask(__name__)
        self.app.config['DEBUG'] = False  # Disable debug mode but keep logging
        self.video_server_port = video_server_port
        
        logger.info("Flask app created successfully")
        
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
            if not PICAMERA_AVAILABLE:
                logger.warning("Picamera2 not available - running in simulation mode")
                self.picam2 = None
                self.video_config = None
                self.still_config = None
                return
                
            self.picam2 = Picamera2()
            self.video_config = self.picam2.create_video_configuration(main={"size": (1280, 720)})
            self.still_config = self.picam2.create_still_configuration(main={"size": (3280, 2464)})
            self.picam2.configure(self.video_config)
            self.picam2.start()
            logger.info("Camera initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize camera: {e}")
            self.picam2 = None
    
    def ensure_photo_directory(self):
        """Create photo directory if it doesn't exist"""
        if not os.path.exists(self.scan_config.photo_directory):
            os.makedirs(self.scan_config.photo_directory)
            logger.info(f"Created photo directory: {self.scan_config.photo_directory}")
    
    def initialize_positioning_system(self, configure_grbl: bool = False) -> bool:
        """Initialize the FluidNC/GRBL positioning system"""
        logger.info("Initializing positioning system...")
        
        # Check if already connected
        if self.controller.is_connected:
            logger.info("Controller already connected")
            return True
        
        # Connect to controller
        if self.use_fluidnc:
            success = self.controller.connect()
        else:
            success = self.controller.connect(configure_settings=configure_grbl)
            
        if not success:
            logger.error("Failed to connect to controller")
            return False
        
        # Check controller status without unlocking
        try:
            if self.use_fluidnc:
                # FluidNC status check
                response = self.controller._send_raw_gcode("?")
                logger.info(f"FluidNC Status: {response}")
            else:
                # GRBL status check
                response = self.controller._send_raw_gcode("?")
                logger.info(f"GRBL Status: {response}")
        except Exception as e:
            logger.warning(f"Could not get controller status: {e}")
        
        # Initialize without unlocking - let user decide between homing or unlocking
        logger.info("Controller connected successfully.")
        logger.info("⚠️ System may be in alarm state - use Home System or Unlock Controller as needed")
        return True
    
    def test_step_movements(self) -> bool:
        """Test step-by-step movements with detailed logging"""
        logger.info("=== Starting Step Movement Test ===")
        
        if not self.controller.is_connected:
            logger.error("Controller not connected")
            return False
        
        # Get starting position
        start_pos = self.controller.current_position
        logger.info(f"Starting position: X{start_pos.x} Y{start_pos.y} Z{start_pos.z}")
        
        # Test movements in sequence (3DOF for compatibility)
        test_moves = [
            Point(start_pos.x + 5, start_pos.y, start_pos.z),     # Move +5mm in X
            Point(start_pos.x + 5, start_pos.y + 5, start_pos.z), # Move +5mm in Y  
            Point(start_pos.x, start_pos.y + 5, start_pos.z),     # Move back X
            Point(start_pos.x, start_pos.y, start_pos.z)          # Return to start
        ]
        
        move_names = ["X+5mm", "Y+5mm", "X back", "Return to start"]
        
        for i, (move, name) in enumerate(zip(test_moves, move_names)):
            logger.info(f"=== Move {i+1}: {name} to X{move.x} Y{move.y} Z{move.z} ===")
            
            success = self.controller.move_to_point(move, feedrate=200)  # Slow speed
            
            if success:
                logger.info(f"✓ Move {i+1} completed successfully")
                # Verify position
                current = self.controller.current_position
                logger.info(f"Current position: X{current.x} Y{current.y} Z{current.z}")
            else:
                logger.error(f"✗ Move {i+1} failed!")
                return False
            
            time.sleep(2)  # Pause between moves
        
        logger.info("=== Step Movement Test Complete ===")
        return True
    
    def test_grbl_connection(self) -> bool:
        """Test controller connection and basic movement capability"""
        logger.info("Testing controller connection...")
        
        if not self.controller.is_connected:
            logger.error("Controller not connected")
            return False
        
        # Test basic commands
        try:
            # Send status query
            if hasattr(self.controller, 'get_grbl_status'):
                status = self.controller.get_grbl_status()
                logger.info(f"GRBL Status: {status}")
            elif hasattr(self.controller, 'get_status'):
                status = self.controller.get_status()
                logger.info(f"FluidNC Status: {status}")
            
            # Test basic G-code commands
            logger.info("Testing basic G-code commands...")
            self.controller._send_raw_gcode("G21")  # Set units to mm
            self.controller._send_raw_gcode("G90")  # Absolute positioning
            self.controller._send_raw_gcode("G94")  # Feed rate mode
            
            # Test small movement (1mm)
            logger.info("Testing small movement (1mm)...")
            current_pos = self.controller.current_position
            test_pos = Point(current_pos.x + 1, current_pos.y, current_pos.z)
            
            success = self.controller.move_to_point(test_pos, feedrate=100)
            if success:
                logger.info("Test movement successful")
                # Return to original position
                self.controller.move_to_point(current_pos, feedrate=100)
                return True
            else:
                logger.error("Test movement failed")
                return False
                
        except Exception as e:
            logger.error(f"Controller connection test failed: {e}")
            return False
    
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
                    filename = "scan_" + position_name + "_" + timestamp + ".jpg"
                else:
                    filename = "scan_X{:.1f}_Y{:.1f}_Z{:.1f}_{}.jpg".format(position.x, position.y, position.z, timestamp)
                
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
        if not self.controller.is_connected:
            logger.error("Controller not connected")
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
                logger.info(f"Using feedrate: {self.scan_config.movement_feedrate}")
                
                # Move to position
                success = self.controller.move_to_point(
                    position, 
                    feedrate=self.scan_config.movement_feedrate
                )
                
                if not success:
                    logger.error(f"Failed to move to position {i+1}: X{position.x:.1f} Y{position.y:.1f} Z{position.z:.1f}")
                    return False
                else:
                    logger.info(f"Successfully moved to position {i+1}: X{position.x:.1f} Y{position.y:.1f} Z{position.z:.1f}")
                
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
        logger.info("Setting up Flask routes...")
        
        try:
            # Add error handler for unhandled exceptions
            @self.app.errorhandler(Exception)
            def handle_exception(e):
                logger.error(f"Unhandled Flask exception: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return jsonify({"error": f"Server error: {str(e)}"}), 500
            
            logger.info("Added exception handler")
            
            @self.app.route('/')
            def index():
                """Main control interface"""
                return render_template_string(CONTROL_INTERFACE_HTML)
            
            logger.info("Added route: /")
            
            @self.app.route('/ping')
            def ping():
                """Simple ping test"""
                return jsonify({"status": "alive", "message": "Server is responding"})
            
            logger.info("Added route: /ping")
            
            @self.app.route('/grbl_status')
            def grbl_status():
                """Check controller connection and status"""
                try:
                    connected = self.controller.is_connected
                    if connected:
                        if hasattr(self.controller, 'get_grbl_status'):
                            status = self.controller.get_grbl_status()
                        elif hasattr(self.controller, 'get_status'):
                            status = self.controller.get_status()
                        else:
                            status = "Status not available"
                        try:
                            pos = self.controller.current_position
                            if hasattr(pos, 'c'):  # 4DOF
                                position = {"x": pos.x, "y": pos.y, "z": pos.z, "c": pos.c}
                            else:  # 3DOF
                                position = {"x": pos.x, "y": pos.y, "z": pos.z}
                        except Exception as e:
                            position = {"error": f"Failed to get position: {str(e)}"}
                    else:
                        status = "Not connected"
                        position = {"error": "Not connected"}
                    
                    return jsonify({
                        "connected": connected,
                        "controller_status": status,
                        "position": position,
                        "port": getattr(self.controller, 'port', 'Unknown'),
                        "controller_type": "FluidNC" if self.use_fluidnc else "GRBL"
                    })
                except Exception as e:
                    return jsonify({
                        "connected": False,
                        "error": f"Controller status check failed: {str(e)}",
                        "port": getattr(self.controller, 'port', 'Unknown'),
                        "controller_type": "FluidNC" if self.use_fluidnc else "GRBL"
                    })
            
            logger.info("Added route: /grbl_status")
            
            @self.app.route('/debug_routes')
            def debug_routes():
                """Debug: List all registered routes"""
                routes = []
                for rule in self.app.url_map.iter_rules():
                    routes.append({
                        'rule': str(rule),
                        'methods': list(rule.methods) if rule.methods else [],
                        'endpoint': rule.endpoint
                    })
                return jsonify({"routes": routes})
            
            @self.app.route('/favicon.ico')
            def favicon():
                """Handle favicon requests to prevent 404 errors"""
                # Return a 204 No Content response instead of 404
                return '', 204
            
            @self.app.route('/test_json')
            def test_json():
                """Test JSON response"""
                logger.info("Test JSON route called")
                return jsonify({"status": "success", "message": "JSON response working"})
            
            @self.app.route('/video_feed')
            def video_feed():
                """Live video stream"""
                return Response(self._generate_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
            
            @self.app.route('/scan_status')
            def scan_status():
                """Get current scan status"""
                status_data = self.current_scan_data.copy()
                # Add controller connection status
                status_data["controller_connected"] = self.controller.is_connected
                if self.controller.is_connected:
                    if hasattr(self.controller, 'get_grbl_status'):
                        status_data["controller_status"] = self.controller.get_grbl_status()
                    elif hasattr(self.controller, 'get_status'):
                        status_data["controller_status"] = self.controller.get_status()
                    else:
                        status_data["controller_status"] = "Connected"
                else:
                    status_data["controller_status"] = "Disconnected"
                return jsonify(status_data)
            
        except Exception as e:
            logger.error(f"ERROR during basic route setup: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return
            
        # JSON-based routes - POST with JSON bodies
        logger.info("=== REGISTERING JSON-BASED ROUTES ===")
        
        @self.app.route('/move_to', methods=['POST'])
        def move_to_position():
            """Move to specific position using JSON data"""
            logger.info(f"=== MOVE TO POSITION ROUTE CALLED (JSON) ===")
            
            try:
                # Get JSON data from request
                if not request.is_json:
                    return jsonify({"error": "Request must be JSON"}), 400
                
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No JSON data provided"}), 400
                
                # Extract coordinates
                x = float(data.get('x', 0))
                y = float(data.get('y', 0))
                z = float(data.get('z', 0))
                
                logger.info(f"Web interface move request: X{x} Y{y} Z{z}")

                if self.current_scan_data["active"]:
                    return jsonify({"error": "Cannot move during active scan"}), 400

                if not self.controller.is_connected:
                    return jsonify({"error": "Controller not connected"}), 500

                # Create target point (support 4DOF)
                c = float(data.get('c', 0))  # Camera tilt for 4DOF
                target = Point(x, y, z, c)
                logger.info(f"Target position created: X{target.x} Y{target.y} Z{target.z} C{target.c}")
                
                # Get current position
                current = self.controller.current_position
                logger.info(f"Current position: X{current.x} Y{current.y} Z{current.z} C{current.c}")
                
                # Start movement in background thread
                move_thread = threading.Thread(
                    target=self.controller.move_to_point,
                    args=(target,),
                    kwargs={"feedrate": self.scan_config.movement_feedrate}
                )
                move_thread.daemon = True
                move_thread.start()
                
                logger.info(f"Movement thread started successfully")
                return jsonify({
                    "message": f"Moving to X{x} Y{y} Z{z}", 
                    "status": "success",
                    "target": {"x": x, "y": y, "z": z},
                    "current": {"x": current.x, "y": current.y, "z": current.z}
                })
                
            except ValueError as e:
                logger.error(f"Invalid coordinate values: {e}")
                return jsonify({"error": f"Invalid coordinate values: {str(e)}"}), 400
            except Exception as e:
                logger.error(f"Move route error: {e}")
                return jsonify({"error": f"Failed to start movement: {str(e)}"}), 500
        
        @self.app.route('/test_move_simple', methods=['POST'])
        def test_move_simple():
            """Simple move test without threading using JSON data"""
            try:
                # Get JSON data from request
                if not request.is_json:
                    return jsonify({"error": "Request must be JSON"}), 400
                
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No JSON data provided"}), 400
                
                # Extract coordinates with type conversion (support 4DOF)
                x = float(data.get('x', 0))
                y = float(data.get('y', 0))
                z = float(data.get('z', 0))
                c = float(data.get('c', 0))
                
                logger.info(f"Test move request: X{x} Y{y} Z{z} C{c}")

                if not self.controller.is_connected:
                    return jsonify({"error": "Controller not connected"}), 500
                
                target = Point(x, y, z, c)
                current = self.controller.current_position
                feedrate = self.scan_config.movement_feedrate
                
                return jsonify({
                    "message": "Simple move test passed",
                    "target": {"x": target.x, "y": target.y, "z": target.z, "c": target.c},
                    "current": {"x": current.x, "y": current.y, "z": current.z, "c": current.c},
                    "feedrate": feedrate,
                    "status": "success"
                })
                
            except ValueError as e:
                logger.error(f"Invalid coordinate values: {e}")
                return jsonify({"error": f"Invalid coordinate values: {str(e)}"}), 400
            except Exception as e:
                logger.error(f"Test move error: {e}")
                return jsonify({"error": f"Test move failed: {str(e)}"}), 500
        
        @self.app.route('/start_grid_scan', methods=['POST'])
        def start_grid_scan():
            """Start a grid scan using JSON data"""
            try:
                # Get JSON data from request
                if not request.is_json:
                    return jsonify({"error": "Request must be JSON"}), 400
                
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No JSON data provided"}), 400
                
                # Extract grid scan parameters
                x1 = float(data.get('x1', 0))
                y1 = float(data.get('y1', 0))
                x2 = float(data.get('x2', 10))
                y2 = float(data.get('y2', 10))
                grid_x = int(data.get('grid_x', 2))
                grid_y = int(data.get('grid_y', 2))
                
                logger.info(f"Grid scan request: corner1=({x1},{y1}) corner2=({x2},{y2}) grid=({grid_x},{grid_y})")
                
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
                
                return jsonify({
                    "message": "Grid scan started", 
                    "grid_size": [grid_x, grid_y], 
                    "corners": {"corner1": {"x": x1, "y": y1}, "corner2": {"x": x2, "y": y2}},
                    "status": "success"
                })
                
            except ValueError as e:
                logger.error(f"Invalid scan parameters: {e}")
                return jsonify({"error": f"Invalid scan parameters: {str(e)}"}), 400
            except Exception as e:
                logger.error(f"Grid scan error: {e}")
                return jsonify({"error": f"Failed to start grid scan: {str(e)}"}), 500
        
        @self.app.route('/start_circular_scan', methods=['POST'])
        def start_circular_scan():
            """Start a circular scan using JSON data"""
            try:
                # Get JSON data from request
                if not request.is_json:
                    return jsonify({"error": "Request must be JSON"}), 400
                
                data = request.get_json()
                if not data:
                    return jsonify({"error": "No JSON data provided"}), 400
                
                # Extract circular scan parameters
                center_x = float(data.get('center_x', 0))
                center_y = float(data.get('center_y', 0))
                radius = float(data.get('radius', 5))
                positions = int(data.get('positions', 8))
                
                logger.info(f"Circular scan request: center=({center_x},{center_y}) radius={radius} positions={positions}")
                
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
                
                return jsonify({
                    "message": "Circular scan started", 
                    "center": {"x": center_x, "y": center_y}, 
                    "radius": radius,
                    "positions": positions,
                    "status": "success"
                })
                
            except ValueError as e:
                logger.error(f"Invalid scan parameters: {e}")
                return jsonify({"error": f"Invalid scan parameters: {str(e)}"}), 400
            except Exception as e:
                logger.error(f"Circular scan error: {e}")
                return jsonify({"error": f"Failed to start circular scan: {str(e)}"}), 500
        
        logger.info("✅ All JSON-based routes registered successfully")
        
        # Additional routes
        @self.app.route('/emergency_stop')
        def emergency_stop():
            """Emergency stop all operations"""
            self.camera_controller.emergency_stop()
            self.current_scan_data["active"] = False
            return jsonify({"message": "Emergency stop activated", "status": "success"})
        
        @self.app.route('/capture_single_photo')
        def capture_single_photo():
            """Capture a single photo at current position"""
            current_pos = self.controller.current_position
            filename = self.capture_photo_at_position(current_pos, "manual")
            
            if filename:
                return jsonify({"message": "Photo captured", "filename": filename})
            else:
                return jsonify({"error": "Photo capture failed"}), 500
        
        @self.app.route('/test_connection')
        def test_connection():
            """Test GRBL connection and movement"""
            success = self.test_grbl_connection()
            if success:
                return jsonify({"message": "GRBL connection test successful"})
            else:
                return jsonify({"error": "GRBL connection test failed"}), 500
        
        @self.app.route('/test_step_movements')
        def test_step_movements():
            """Test step-by-step movements"""
            success = self.test_step_movements()
            if success:
                return jsonify({"message": "Step movement test completed successfully"})
            else:
                return jsonify({"error": "Step movement test failed"}), 500
        
        @self.app.route('/get_current_position')
        def get_current_position():
            """Get current controller position (4DOF)"""
            pos = self.controller.current_position
            position_data = {"x": pos.x, "y": pos.y, "z": pos.z}
            if hasattr(pos, 'c'):
                position_data["c"] = pos.c
            
            # Get status based on controller type
            status = "Unknown"
            if hasattr(self.controller, 'get_grbl_status'):
                status = self.controller.get_grbl_status()
            elif hasattr(self.controller, 'get_status'):
                status = self.controller.get_status()
            
            return jsonify({
                "position": position_data,
                "controller_status": status,
                "controller_type": "FluidNC" if self.use_fluidnc else "GRBL"
            })
        
        @self.app.route('/return_home')
        def return_home():
            """Return to home position"""
            try:
                logger.info(f"Web interface return home request")
                
                if self.current_scan_data["active"]:
                    logger.warning("Return home request rejected - scan already in progress")
                    return jsonify({"error": "Cannot return home during active scan"}), 400
                
                logger.info(f"Starting return home thread...")
                
                # Start return home in background thread
                home_thread = threading.Thread(
                    target=self.camera_controller.return_to_home
                )
                home_thread.daemon = True
                home_thread.start()
                
                logger.info(f"Return home thread started successfully")
                return jsonify({"message": "Returning to home position"})
                
            except Exception as e:
                logger.error(f"Error starting return home: {e}")
                return jsonify({"error": f"Failed to start return home: {str(e)}"}), 500
        
        # Add new 4DOF routes
        @self.app.route('/home_system', methods=['POST'])
        def home_system():
            """Home all axes of the 4DOF system"""
            try:
                if not self.controller.is_connected:
                    return jsonify({"success": False, "error": "Controller not connected"}), 500
                
                logger.info("Starting system homing sequence...")
                success = self.controller.home_axes()
                
                if success:
                    logger.info("System homing completed successfully")
                    return jsonify({"success": True, "message": "System homed successfully"})
                else:
                    logger.error("System homing failed")
                    return jsonify({"success": False, "error": "Homing sequence failed"}), 500
                    
            except Exception as e:
                logger.error(f"Error during homing: {e}")
                return jsonify({"success": False, "error": f"Homing failed: {str(e)}"}), 500
        
        @self.app.route('/unlock_controller', methods=['POST'])
        def unlock_controller():
            """Unlock controller from alarm state without homing"""
            try:
                if not self.controller.is_connected:
                    return jsonify({"success": False, "error": "Controller not connected"}), 500
                
                logger.info("Unlocking controller...")
                # Send unlock command ($X)
                response = self.controller._send_raw_gcode("$X")
                
                # Check if unlock was successful
                time.sleep(0.5)  # Brief delay for command processing
                status_response = self.controller._send_raw_gcode("?")
                
                logger.info(f"Unlock response: {response}")
                logger.info(f"Status after unlock: {status_response}")
                
                return jsonify({
                    "success": True, 
                    "message": "Controller unlocked successfully",
                    "status": status_response
                })
                    
            except Exception as e:
                logger.error(f"Error during unlock: {e}")
                return jsonify({"success": False, "error": f"Unlock failed: {str(e)}"}), 500
        
        @self.app.route('/move_to_4dof', methods=['POST'])
        def move_to_4dof():
            """Move to specific 4DOF position"""
            try:
                if not request.is_json:
                    return jsonify({"success": False, "error": "Request must be JSON"}), 400
                
                data = request.get_json()
                if not data:
                    return jsonify({"success": False, "error": "No JSON data provided"}), 400
                
                x = float(data.get('x', 0))
                y = float(data.get('y', 0))
                z = float(data.get('z', 0))
                c = float(data.get('c', 0))
                
                if not self.controller.is_connected:
                    return jsonify({"success": False, "error": "Controller not connected"}), 500
                
                target = Point(x, y, z, c)
                success = self.camera_controller.move_to_capture_position(x, y, z, c)
                
                if success:
                    return jsonify({"success": True, "message": f"Moved to X{x} Y{y} Z{z}° C{c}°"})
                else:
                    return jsonify({"success": False, "error": "Movement failed"}), 500
                    
            except Exception as e:
                logger.error(f"4DOF move error: {e}")
                return jsonify({"success": False, "error": f"Move failed: {str(e)}"}), 500
        
        @self.app.route('/controller_status')
        def controller_status():
            """Get detailed controller status including 4DOF position"""
            try:
                connected = self.controller.is_connected
                if connected:
                    # Try to get status from controller
                    try:
                        if hasattr(self.controller, '_send_raw_gcode'):
                            # Send a simple status command and parse response
                            response = self.controller._send_raw_gcode("?")
                            status = response if response else "Connected"
                        else:
                            status = "Connected"
                    except:
                        status = "Connected"
                        
                    try:
                        pos = self.controller.current_position
                        if hasattr(pos, 'c'):  # 4DOF
                            position = {"x": pos.x, "y": pos.y, "z": pos.z, "c": pos.c}
                        else:  # 3DOF
                            position = {"x": pos.x, "y": pos.y, "z": pos.z}
                    except Exception as e:
                        position = {"error": f"Failed to get position: {str(e)}"}
                else:
                    status = "Not connected"
                    position = {"error": "Not connected"}
                
                return jsonify({
                    "connected": connected,
                    "controller_status": status,
                    "position": position,
                    "port": getattr(self.controller, 'port', 'Unknown'),
                    "controller_type": "FluidNC" if self.use_fluidnc else "GRBL"
                })
            except Exception as e:
                return jsonify({
                    "connected": False,
                    "error": f"Controller status check failed: {str(e)}",
                    "port": getattr(self.controller, 'port', 'Unknown'),
                    "controller_type": "FluidNC" if self.use_fluidnc else "GRBL"
                })
        
        @self.app.route('/start_grid_scan_4dof', methods=['POST'])
        def start_grid_scan_4dof():
            """Start a 4DOF grid scan"""
            try:
                if not request.is_json:
                    return jsonify({"success": False, "error": "Request must be JSON"}), 400
                
                data = request.get_json()
                x1, y1 = float(data['x1']), float(data['y1'])
                x2, y2 = float(data['x2']), float(data['y2'])
                grid_x, grid_y = int(data['grid_x']), int(data['grid_y'])
                z, c = float(data['z']), float(data['c'])
                
                corner1 = Point(x1, y1, z, c)
                corner2 = Point(x2, y2, z, c)
                
                success = self.camera_controller.scan_area(corner1, corner2, (grid_x, grid_y))
                
                if success:
                    return jsonify({"success": True, "message": f"4DOF Grid scan started ({grid_x}×{grid_y} points)"})
                else:
                    return jsonify({"success": False, "error": "Grid scan failed to start"}), 500
                    
            except Exception as e:
                logger.error(f"4DOF grid scan error: {e}")
                return jsonify({"success": False, "error": f"Grid scan failed: {str(e)}"}), 500
        
        @self.app.route('/start_circular_scan_4dof', methods=['POST'])
        def start_circular_scan_4dof():
            """Start a 4DOF circular scan"""
            try:
                if not request.is_json:
                    return jsonify({"success": False, "error": "Request must be JSON"}), 400
                
                data = request.get_json()
                center_x, center_y = float(data['center_x']), float(data['center_y'])
                radius = float(data['radius'])
                positions = int(data['positions'])
                z, c = float(data['z']), float(data['c'])
                
                center = Point(center_x, center_y, z, c)
                success = self.camera_controller.circular_scan(center, radius, positions)
                
                if success:
                    return jsonify({"success": True, "message": f"4DOF Circular scan started ({positions} positions)"})
                else:
                    return jsonify({"success": False, "error": "Circular scan failed to start"}), 500
                    
            except Exception as e:
                logger.error(f"4DOF circular scan error: {e}")
                return jsonify({"success": False, "error": f"Circular scan failed: {str(e)}"}), 500
        
        @self.app.route('/start_rotational_scan', methods=['POST'])
        def start_rotational_scan():
            """Start a rotational scan (vary Z-axis)"""
            try:
                if not request.is_json:
                    return jsonify({"success": False, "error": "Request must be JSON"}), 400
                
                data = request.get_json()
                x, y, c = float(data['x']), float(data['y']), float(data['c'])
                z_angles = data['z_angles']
                
                base_position = Point(x, y, 0, c)
                success = self.camera_controller.rotational_scan(base_position, z_angles, c)
                
                if success:
                    return jsonify({"success": True, "message": f"Rotational scan started ({len(z_angles)} positions)"})
                else:
                    return jsonify({"success": False, "error": "Rotational scan failed to start"}), 500
                    
            except Exception as e:
                logger.error(f"Rotational scan error: {e}")
                return jsonify({"success": False, "error": f"Rotational scan failed: {str(e)}"}), 500
        
        @self.app.route('/start_tilt_scan', methods=['POST'])
        def start_tilt_scan():
            """Start a tilt scan (vary C-axis)"""
            try:
                if not request.is_json:
                    return jsonify({"success": False, "error": "Request must be JSON"}), 400
                
                data = request.get_json()
                x, y, z = float(data['x']), float(data['y']), float(data['z'])
                c_angles = data['c_angles']
                
                position = Point(x, y, z, 0)
                success = self.camera_controller.tilt_scan(position, c_angles)
                
                if success:
                    return jsonify({"success": True, "message": f"Tilt scan started ({len(c_angles)} positions)"})
                else:
                    return jsonify({"success": False, "error": "Tilt scan failed to start"}), 500
                    
            except Exception as e:
                logger.error(f"Tilt scan error: {e}")
                return jsonify({"success": False, "error": f"Tilt scan failed: {str(e)}"}), 500
        
        @self.app.route('/start_spherical_scan', methods=['POST'])
        def start_spherical_scan():
            """Start a spherical scan (vary both Z and C axes)"""
            try:
                if not request.is_json:
                    return jsonify({"success": False, "error": "Request must be JSON"}), 400
                
                data = request.get_json()
                center_x, center_y = float(data['center_x']), float(data['center_y'])
                z_angles = data['z_angles']
                c_angles = data['c_angles']
                
                center = Point(center_x, center_y, 0, 0)
                success = self.camera_controller.spherical_scan(center, 0, z_angles, c_angles)
                
                total_positions = len(z_angles) * len(c_angles)
                
                if success:
                    return jsonify({"success": True, "message": f"Spherical scan started ({total_positions} positions)"})
                else:
                    return jsonify({"success": False, "error": "Spherical scan failed to start"}), 500
                    
            except Exception as e:
                logger.error(f"Spherical scan error: {e}")
                return jsonify({"success": False, "error": f"Spherical scan failed: {str(e)}"}), 500
        
        logger.info("Flask routes setup completed successfully")
    
    def _generate_frames(self):
        """Generate video frames for streaming"""
        if not PICAMERA_AVAILABLE or self.picam2 is None:
            # Generate a dummy frame for testing when camera is not available
            dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            dummy_frame[240-50:240+50, 320-150:320+150] = [100, 100, 255]  # Blue rectangle
            cv2.putText(dummy_frame, 'Camera Simulation Mode', (150, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
            
            while True:
                try:
                    ret, buffer = cv2.imencode('.jpg', dummy_frame)
                    frame = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    time.sleep(0.1)  # 10 FPS for simulation
                except Exception as e:
                    logger.error(f"Dummy frame generation error: {e}")
                    break
        else:
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
        
        # Debug: Print all registered routes
        logger.info("=== REGISTERED FLASK ROUTES ===")
        for rule in self.app.url_map.iter_rules():
            methods = list(rule.methods) if rule.methods else []
            logger.info(f"Route: {rule.rule} -> {rule.endpoint} ({methods})")
        logger.info("=== END ROUTES ===")
        
        self.app.run(host='0.0.0.0', port=self.video_server_port, threaded=True, debug=False)
    
    def shutdown(self):
        """Safely shutdown the system without moving"""
        logger.info("Shutting down integrated camera system - leaving position as-is")
        
        # Stop any active scan
        self.current_scan_data["active"] = False
        
        # Disconnect controller without moving
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
    <title>FluidNC 4DOF Camera Positioning System</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .video-container { text-align: center; margin-bottom: 20px; }
        .controls { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .control-panel { border: 1px solid #ccc; padding: 15px; border-radius: 5px; }
        .status { background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin: 10px 0; }
        button { padding: 10px 15px; margin: 5px; border: none; border-radius: 3px; cursor: pointer; }
        .btn-primary { background-color: #007bff; color: white; }
        .btn-primary:disabled { background-color: #6c757d; cursor: not-allowed; }
        .btn-danger { background-color: #dc3545; color: white; }
        .btn-success { background-color: #28a745; color: white; }
        .btn-warning { background-color: #ffc107; color: black; }
        .btn-test { background-color: #ff9800; color: white; }
        input { padding: 5px; margin: 2px 5px 5px 2px; border: 1px solid #ccc; border-radius: 3px; width: 80px; }
        label { display: inline-block; min-width: 120px; font-weight: bold; color: #333; margin-right: 5px; }
        .input-group { margin-bottom: 8px; }
        h4 { margin-bottom: 10px; color: #2c3e50; }
    </style>
</head>
<body>
    <div class="container">
        <h1>FluidNC 4DOF Camera Positioning System</h1>
        
        <div class="video-container">
            <img src="/video_feed" style="max-width: 640px; border: 1px solid #ccc;">
        </div>
        
        <div class="controls">
            <div class="control-panel">
                <h3>Scan Controls</h3>
                <div>
                    <h4>4DOF Grid Scan</h4>
                    <div class="input-group">
                        <label for="grid_x1">Start X (mm):</label>
                        <input type="number" id="grid_x1" placeholder="0-200" value="50" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="grid_y1">Start Y (mm):</label>
                        <input type="number" id="grid_y1" placeholder="0-200" value="50" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="grid_x2">End X (mm):</label>
                        <input type="number" id="grid_x2" placeholder="0-200" value="150" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="grid_y2">End Y (mm):</label>
                        <input type="number" id="grid_y2" placeholder="0-200" value="150" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="grid_size_x">Grid Points X:</label>
                        <input type="number" id="grid_size_x" placeholder="Grid X" value="3" min="2" max="10">
                        <label for="grid_size_y">Grid Points Y:</label>
                        <input type="number" id="grid_size_y" placeholder="Grid Y" value="3" min="2" max="10">
                    </div>
                    <div class="input-group">
                        <label for="grid_z">Z Rotation (°):</label>
                        <input type="number" id="grid_z" placeholder="0-360" value="0" min="0" max="360">
                    </div>
                    <div class="input-group">
                        <label for="grid_c">C Tilt (°):</label>
                        <input type="number" id="grid_c" placeholder="-90 to +90" value="0" min="-90" max="90">
                    </div>
                    <button class="btn-primary" onclick="startGridScan()" id="gridScanBtn" disabled>Start 4DOF Grid Scan</button>
                </div>
                
                <div>
                    <h4>4DOF Circular Scan</h4>
                    <div class="input-group">
                        <label for="circle_x">Center X (mm):</label>
                        <input type="number" id="circle_x" placeholder="0-200" value="100" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="circle_y">Center Y (mm):</label>
                        <input type="number" id="circle_y" placeholder="0-200" value="100" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="circle_radius">Radius (mm):</label>
                        <input type="number" id="circle_radius" placeholder="Radius" value="30" min="5" max="50">
                    </div>
                    <div class="input-group">
                        <label for="circle_positions">Number of Positions:</label>
                        <input type="number" id="circle_positions" placeholder="Positions" value="8" min="4" max="16">
                    </div>
                    <div class="input-group">
                        <label for="circle_z">Z Rotation (°):</label>
                        <input type="number" id="circle_z" placeholder="0-360" value="0" min="0" max="360">
                    </div>
                    <div class="input-group">
                        <label for="circle_c">C Tilt (°):</label>
                        <input type="number" id="circle_c" placeholder="-90 to +90" value="0" min="-90" max="90">
                    </div>
                    <button class="btn-primary" onclick="startCircularScan()" id="circScanBtn" disabled>Start 4DOF Circular Scan</button>
                </div>
            </div>
            
            <div class="control-panel">
                <h3>Manual Controls</h3>
                <div>
                    <h4>System Control</h4>
                    <div class="input-group">
                        <button class="btn-success" onclick="homeSystem()" id="homeBtn">🏠 Home System</button>
                        <button class="btn-warning" onclick="unlockController()" id="unlockBtn">🔓 Unlock Controller</button>
                    </div>
                    <div class="input-group">
                        <span id="systemStatus" style="font-weight: bold; color: red;">⚠️ SYSTEM NOT READY</span>
                        <small style="display: block; color: #666; margin-top: 5px;">
                            FluidNC/GRBL may be in alarm state. Choose Home System (recommended) or Unlock Controller.
                        </small>
                    </div>
                </div>
                
                <div>
                    <h4>4DOF Move To Position</h4>
                    <div class="input-group">
                        <label for="move_x">X Position (mm):</label>
                        <input type="number" id="move_x" placeholder="0-200" value="100" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="move_y">Y Position (mm):</label>
                        <input type="number" id="move_y" placeholder="0-200" value="100" min="0" max="200">
                    </div>
                    <div class="input-group">
                        <label for="move_z">Z Rotation (°):</label>
                        <input type="number" id="move_z" placeholder="0-360" value="0" min="0" max="360">
                    </div>
                    <div class="input-group">
                        <label for="move_c">C Tilt (°):</label>
                        <input type="number" id="move_c" placeholder="-90 to +90" value="0" min="-90" max="90">
                    </div>
                    <button class="btn-primary" onclick="moveToPosition()" id="moveBtn" disabled>Move (Home First)</button>
                    <button class="btn-primary" onclick="getCurrentPosition()">Get Current Position</button>
                </div>
                
                <div>
                    <h4>4DOF Scan Patterns</h4>
                    <div class="input-group">
                        <label for="scan_z">Z Base Rotation (°):</label>
                        <input type="number" id="scan_z" placeholder="0-360" value="0" min="0" max="360">
                    </div>
                    <div class="input-group">
                        <label for="scan_c">C Base Tilt (°):</label>
                        <input type="number" id="scan_c" placeholder="-90 to +90" value="0" min="-90" max="90">
                    </div>
                    <button class="btn-primary" onclick="startRotationalScan()" id="rotScanBtn" disabled>Rotational Scan</button>
                    <button class="btn-primary" onclick="startTiltScan()" id="tiltScanBtn" disabled>Tilt Scan</button>
                    <button class="btn-primary" onclick="startSphericalScan()" id="spherScanBtn" disabled>Spherical Scan</button>
                </div>
                
                <div>
                    <h4>System Tools</h4>
                    <button class="btn-success" onclick="capturePhoto()">📷 Capture Photo</button>
                    <button class="btn-primary" onclick="ping()">📡 Ping Server</button>
                    <button class="btn-primary" onclick="checkControllerStatus()">🔍 Check Controller Status</button>
                    <button class="btn-primary" onclick="testJSON()">🧪 Test JSON Response</button>
                    <button class="btn-primary" onclick="testConnection()">🔗 Test Controller Connection</button>
                    <button class="btn-primary" onclick="testStepMovements()">👣 Test Step Movements</button>
                    <button class="btn-danger" onclick="emergencyStop()">🛑 EMERGENCY STOP</button>
                </div>
            </div>
        </div>
        
        <div class="status" id="status">
            <h3>FluidNC 4DOF System Status</h3>
            <div id="status-content">Loading...</div>
            <div id="position-display" style="margin-top: 10px; padding: 10px; background-color: #e9ecef; border-radius: 5px;">
                <strong>Current Position:</strong> <span id="current-position">Unknown</span>
            </div>
        </div>
    </div>
    
    <script>
        console.log('=== JAVASCRIPT LOADING ===');
        
        // Add global error handler
        window.addEventListener('error', function(e) {
            console.error('JavaScript error:', e.error);
            console.error('Error details:', e.filename, e.lineno, e.colno);
        });
        
        // Check function definitions
        console.log('Functions defined:');
        console.log('- simpleAlert:', typeof simpleAlert);
        console.log('- buttonTest:', typeof buttonTest);
        console.log('- consoleTest:', typeof consoleTest);
        
        function ping() {
            console.log('Pinging server...');
            fetch('/ping')
                .then(function(response) {
                    console.log('Ping response status: ' + response.status);
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                    }
                    return response.json();
                })
                .then(function(data) {
                    console.log('Ping response data:', data);
                    alert('Server ping successful: ' + data.message);
                })
                .catch(function(error) {
                    console.error('Ping error:', error);
                    alert('Server ping failed: ' + error.message);
                });
        }
        
        function checkControllerStatus() {
            console.log('Checking controller status...');
            fetch('/controller_status')
                .then(function(response) {
                    console.log('Controller status response status: ' + response.status);
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                    }
                    return response.json();
                })
                .then(function(data) {
                    console.log('Controller status response data:', data);
                    var message = 'FluidNC Status:\\n' +
                        'Connected: ' + data.connected + '\\n' +
                        'Port: ' + data.port + '\\n' +
                        'Controller Type: ' + data.controller_type + '\\n' +
                        'Status: ' + data.controller_status + '\\n';
                    
                    if (data.position && !data.position.error) {
                        if (data.position.c !== undefined) {
                            // 4DOF position
                            var tilt_angle = data.position.c - 90; // Convert position back to angle
                            message += 'Position: X' + data.position.x + ' Y' + data.position.y + 
                                      ' Z' + data.position.z + '° C' + tilt_angle + '° (' + data.position.c + 'mm)';
                        } else {
                            // 3DOF position
                            message += 'Position: X' + data.position.x + ' Y' + data.position.y + ' Z' + data.position.z;
                        }
                    } else if (data.position && data.position.error) {
                        message += 'Position Error: ' + data.position.error;
                    }
                    
                    if (data.error) {
                        message += '\\nError: ' + data.error;
                    }
                    
                    alert(message);
                })
                .catch(function(error) {
                    console.error('Controller status error:', error);
                    alert('Controller status check failed: ' + error.message);
                });
        }
        
        function updateCurrentPosition() {
            fetch('/controller_status')
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    var positionText = 'Unknown';
                    if (data.position && !data.position.error) {
                        if (data.position.c !== undefined) {
                            // 4DOF position
                            var tilt_angle = data.position.c - 90; // Convert position back to angle
                            positionText = 'X:' + data.position.x + 'mm Y:' + data.position.y + 
                                          'mm Z:' + data.position.z + '° C:' + tilt_angle + '°';
                        } else {
                            // 3DOF position
                            positionText = 'X:' + data.position.x + 'mm Y:' + data.position.y + 'mm Z:' + data.position.z + 'mm';
                        }
                    }
                    document.getElementById('current-position').textContent = positionText;
                })
                .catch(function(error) {
                    document.getElementById('current-position').textContent = 'Error reading position';
                });
        }
        
        function updateStatus() {
            fetch('/scan_status')
                .then(function(response) { return response.json(); })
                .then(function(data) {
                    document.getElementById('status-content').innerHTML = 
                        '<strong>Controller Connected:</strong> ' + data.controller_connected + '<br>' +
                        '<strong>Controller Status:</strong> ' + data.controller_status + '<br>' +
                        '<strong>Scan Active:</strong> ' + data.active + '<br>' +
                        '<strong>Progress:</strong> ' + data.completed_positions + '/' + data.total_positions + '<br>' +
                        '<strong>Photos Captured:</strong> ' + data.photos_captured.length;
                })
                .catch(function(error) {
                    document.getElementById('status-content').innerHTML = 
                        '<strong>Error:</strong> Unable to connect to server';
                });
        }
        
        // Initialize page
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Page loaded, initializing...');
            updateButtonStates();
            updateStatus();
            updateCurrentPosition();
            
            // Update position every 5 seconds
            setInterval(updateCurrentPosition, 5000);
            // Update status every 2 seconds  
            setInterval(updateStatus, 2000);
        });
        
        function startGridScan() {
            if (!isSystemReady) {
                alert('⚠️ Please home the system or unlock the controller first before scanning!');
                return;
            }
            
            var x1 = document.getElementById('grid_x1').value;
            var y1 = document.getElementById('grid_y1').value;
            var x2 = document.getElementById('grid_x2').value;
            var y2 = document.getElementById('grid_y2').value;
            var gx = document.getElementById('grid_size_x').value;
            var gy = document.getElementById('grid_size_y').value;
            var z = document.getElementById('grid_z').value;
            var c = document.getElementById('grid_c').value;
            
            // Convert to numbers and create JSON payload
            var scanData = {
                x1: parseFloat(x1),
                y1: parseFloat(y1),
                x2: parseFloat(x2),
                y2: parseFloat(y2),
                grid_x: parseInt(gx),
                grid_y: parseInt(gy),
                z: parseFloat(z),
                c: parseFloat(c)
            };
            
            console.log('Starting 4DOF grid scan:', scanData);
            
            fetch('/start_grid_scan_4dof', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scanData)
            })
                .then(function(response) {
                    console.log('Grid scan response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Grid scan response data:', data);
                    if (data.success) {
                        alert('✅ 4DOF Grid scan started!');
                    } else {
                        alert('❌ Grid scan failed: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(error) {
                    console.error('Grid scan error:', error);
                    alert('❌ Failed to start grid scan: ' + error.message);
                });
        }
        
        function startCircularScan() {
            if (!isSystemReady) {
                alert('⚠️ Please home the system or unlock the controller first before scanning!');
                return;
            }
            
            var x = document.getElementById('circle_x').value;
            var y = document.getElementById('circle_y').value;
            var r = document.getElementById('circle_radius').value;
            var p = document.getElementById('circle_positions').value;
            var z = document.getElementById('circle_z').value;
            var c = document.getElementById('circle_c').value;
            
            // Convert to numbers and create JSON payload
            var scanData = {
                center_x: parseFloat(x),
                center_y: parseFloat(y),
                radius: parseFloat(r),
                positions: parseInt(p),
                z: parseFloat(z),
                c: parseFloat(c)
            };
            
            console.log('Starting 4DOF circular scan:', scanData);
            
            fetch('/start_circular_scan_4dof', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scanData)
            })
                .then(function(response) {
                    console.log('Circular scan response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Circular scan response data:', data);
                    if (data.success) {
                        alert('✅ 4DOF Circular scan started!');
                    } else {
                        alert('❌ Circular scan failed: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(error) {
                    console.error('Circular scan error:', error);
                    alert('❌ Failed to start circular scan: ' + error.message);
                });
        }
        
        function startRotationalScan() {
            if (!isSystemReady) {
                alert('⚠️ Please home the system or unlock the controller first before scanning!');
                return;
            }
            
            var x = document.getElementById('move_x').value;
            var y = document.getElementById('move_y').value;
            var c = document.getElementById('scan_c').value;
            
            var scanData = {
                x: parseFloat(x),
                y: parseFloat(y),
                c: parseFloat(c),
                z_angles: [0, 45, 90, 135, 180, 225, 270, 315] // 8 positions
            };
            
            console.log('Starting rotational scan:', scanData);
            
            fetch('/start_rotational_scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scanData)
            })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        alert('✅ Rotational scan started!');
                    } else {
                        alert('❌ Rotational scan failed: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(error) {
                    alert('❌ Failed to start rotational scan: ' + error.message);
                });
        }
        
        function startTiltScan() {
            if (!isSystemReady) {
                alert('⚠️ Please home the system or unlock the controller first before scanning!');
                return;
            }
            
            var x = document.getElementById('move_x').value;
            var y = document.getElementById('move_y').value;
            var z = document.getElementById('scan_z').value;
            
            var scanData = {
                x: parseFloat(x),
                y: parseFloat(y),
                z: parseFloat(z),
                c_angles: [-30, -15, 0, 15, 30] // 5 tilt positions
            };
            
            console.log('Starting tilt scan:', scanData);
            
            fetch('/start_tilt_scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scanData)
            })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        alert('✅ Tilt scan started!');
                    } else {
                        alert('❌ Tilt scan failed: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(error) {
                    alert('❌ Failed to start tilt scan: ' + error.message);
                });
        }
        
        function startSphericalScan() {
            if (!isSystemReady) {
                alert('⚠️ Please home the system or unlock the controller first before scanning!');
                return;
            }
            
            var x = document.getElementById('move_x').value;
            var y = document.getElementById('move_y').value;
            
            var scanData = {
                center_x: parseFloat(x),
                center_y: parseFloat(y),
                z_angles: [0, 60, 120, 180, 240, 300], // 6 rotational positions
                c_angles: [-20, 0, 20] // 3 tilt positions
            };
            
            console.log('Starting spherical scan:', scanData);
            
            fetch('/start_spherical_scan', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(scanData)
            })
                .then(function(response) {
                    return response.json();
                })
                .then(function(data) {
                    if (data.success) {
                        alert('✅ Spherical scan started! (18 total positions)');
                    } else {
                        alert('❌ Spherical scan failed: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(error) {
                    alert('❌ Failed to start spherical scan: ' + error.message);
                });
        }
        
        function testMoveSimple() {
            var x = document.getElementById('move_x').value;
            var y = document.getElementById('move_y').value;
            var z = document.getElementById('move_z').value;
            
            // Validate inputs
            if (!x || !y || !z) {
                alert('Please enter all coordinates (X, Y, Z)');
                return;
            }
            
            // Convert to numbers
            var coords = {
                x: parseFloat(x),
                y: parseFloat(y),
                z: parseFloat(z)
            };
            
            console.log('Testing simple move:', coords);
            
            fetch('/test_move_simple', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(coords)
            })
                .then(function(response) {
                    console.log('Test move response status: ' + response.status);
                    if (!response.ok) {
                        throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                    }
                    return response.json();
                })
                .then(function(data) {
                    console.log('Test move response data:', data);
                    if (data.error) {
                        alert('Test Move Error: ' + data.error);
                    } else {
                        var message = 'Test Move Success!\\n' +
                            'Target: X' + data.target.x + ' Y' + data.target.y + ' Z' + data.target.z + '\\n' +
                            'Current: X' + data.current.x + ' Y' + data.current.y + ' Z' + data.current.z + '\\n' +
                            'Feedrate: ' + data.feedrate;
                        alert(message);
                    }
                })
                .catch(function(error) {
                    console.error('Test move error:', error);
                    alert('Test move failed: ' + error.message);
                });
        }
        
        // Global system state
        var isSystemReady = false; // Either homed or unlocked
        var isHomed = false; // Specifically homed
        
        function updateButtonStates() {
            var buttons = ['moveBtn', 'gridScanBtn', 'circScanBtn', 'rotScanBtn', 'tiltScanBtn', 'spherScanBtn'];
            buttons.forEach(function(id) {
                var btn = document.getElementById(id);
                if (btn) {
                    btn.disabled = !isSystemReady;
                    var originalText = btn.textContent.replace(' (Home or Unlock First)', '').replace(' (Home First)', '');
                    btn.textContent = isSystemReady ? originalText : originalText + ' (Home or Unlock First)';
                }
            });
            
            var systemStatus = document.getElementById('systemStatus');
            if (systemStatus) {
                if (isHomed) {
                    systemStatus.textContent = '✅ SYSTEM HOMED';
                    systemStatus.style.color = 'green';
                } else if (isSystemReady) {
                    systemStatus.textContent = '🔓 SYSTEM UNLOCKED';
                    systemStatus.style.color = 'orange';
                } else {
                    systemStatus.textContent = '⚠️ SYSTEM NOT READY';
                    systemStatus.style.color = 'red';
                }
            }
        }
        
        function homeSystem() {
            if (!confirm('This will home all axes. Make sure the system is clear of obstructions. Continue?')) {
                return;
            }
            
            console.log('Homing system...');
            document.getElementById('homeBtn').disabled = true;
            document.getElementById('homeBtn').textContent = '🏠 Homing...';
            
            fetch('/home_system', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
                .then(function(response) {
                    console.log('Home response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Home response data:', data);
                    if (data.success) {
                        isHomed = true;
                        isSystemReady = true;
                        alert('✅ System homed successfully!');
                    } else {
                        alert('❌ Homing failed: ' + (data.error || 'Unknown error'));
                    }
                    updateButtonStates();
                })
                .catch(function(error) {
                    console.error('Home error:', error);
                    alert('❌ Homing failed: ' + error.message);
                })
                .finally(function() {
                    document.getElementById('homeBtn').disabled = false;
                    document.getElementById('homeBtn').textContent = '🏠 Home System';
                });
        }
        
        function unlockController() {
            if (!confirm('This will unlock the controller without homing. Use only if you know the current position is safe. Continue?')) {
                return;
            }
            
            console.log('Unlocking controller...');
            document.getElementById('unlockBtn').disabled = true;
            document.getElementById('unlockBtn').textContent = '🔓 Unlocking...';
            
            fetch('/unlock_controller', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            })
                .then(function(response) {
                    console.log('Unlock response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Unlock response data:', data);
                    if (data.success) {
                        isHomed = false; // Unlocked but not homed
                        isSystemReady = true;
                        alert('✅ Controller unlocked successfully!\\nStatus: ' + (data.status || 'Unknown'));
                    } else {
                        alert('❌ Unlock failed: ' + (data.error || 'Unknown error'));
                    }
                    updateButtonStates();
                })
                .catch(function(error) {
                    console.error('Unlock error:', error);
                    alert('❌ Unlock failed: ' + error.message);
                })
                .finally(function() {
                    document.getElementById('unlockBtn').disabled = false;
                    document.getElementById('unlockBtn').textContent = '🔓 Unlock Controller';
                });
        }
        
        function moveToPosition() {
            if (!isSystemReady) {
                alert('⚠️ Please home the system or unlock the controller first before moving!');
                return;
            }
            
            var x = document.getElementById('move_x').value;
            var y = document.getElementById('move_y').value;
            var z = document.getElementById('move_z').value;
            var c = document.getElementById('move_c').value;
            
            // Validate inputs
            if (x === '' || y === '' || z === '' || c === '') {
                alert('Please enter all coordinates (X, Y, Z, C)');
                return;
            }
            
            // Convert to numbers and validate ranges
            var coords = {
                x: parseFloat(x),
                y: parseFloat(y),
                z: parseFloat(z),
                c: parseFloat(c)
            };
            
            // Validate ranges
            if (coords.x < 0 || coords.x > 200) {
                alert('X coordinate must be between 0-200mm');
                return;
            }
            if (coords.y < 0 || coords.y > 200) {
                alert('Y coordinate must be between 0-200mm');
                return;
            }
            if (coords.z < 0 || coords.z > 360) {
                alert('Z rotation must be between 0-360°');
                return;
            }
            if (coords.c < -90 || coords.c > 90) {
                alert('C tilt must be between -90° to +90°');
                return;
            }
            
            console.log('Moving to 4DOF position:', coords);
            
            fetch('/move_to_4dof', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(coords)
            })
                .then(function(response) {
                    console.log('Move response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Move response data:', data);
                    if (data.success) {
                        alert('✅ Moved to position successfully!');
                        updateCurrentPosition();
                    } else {
                        alert('❌ Move failed: ' + (data.error || 'Unknown error'));
                    }
                })
                .catch(function(error) {
                    console.error('Move error:', error);
                    alert('❌ Failed to move: ' + error.message);
                });
        }
        
        function debugRoutes() {
            console.log('Getting registered routes...');
            fetch('/debug_routes')
                .then(function(response) {
                    console.log('Debug routes response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Registered routes:', data.routes);
                    var routeList = data.routes.map(function(r) { 
                        return r.rule + ' (' + r.methods.join(', ') + ')'; 
                    }).join('\\n');
                    alert('Registered Routes:\\n' + routeList);
                })
                .catch(function(error) {
                    console.error('Debug routes error:', error);
                    alert('Failed to get routes: ' + error.message);
                });
        }
        
        function testJSON() {
            console.log('Testing JSON response...');
            fetch('/test_json')
                .then(function(response) {
                    console.log('Test JSON response status: ' + response.status);
                    console.log('Response headers:', response.headers);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Test JSON response data:', data);
                    alert('JSON test successful: ' + data.message);
                })
                .catch(function(error) {
                    console.error('Test JSON error:', error);
                    alert('JSON test failed: ' + error.message);
                });
        }
        
        function capturePhoto() {
            console.log('Capturing single photo...');
            fetch('/capture_single_photo')
                .then(function(response) {
                    console.log('Capture photo response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Capture photo response data:', data);
                    alert(data.message || data.error);
                })
                .catch(function(error) {
                    console.error('Capture photo error:', error);
                    alert('Failed to capture photo: ' + error.message);
                });
        }
        
        function testConnection() {
            console.log('Testing GRBL connection...');
            fetch('/test_connection')
                .then(function(response) {
                    console.log('Test connection response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Test connection response data:', data);
                    alert(data.message || data.error);
                })
                .catch(function(error) {
                    console.error('Test connection error:', error);
                    alert('Failed to test connection: ' + error.message);
                });
        }
        
        function testStepMovements() {
            console.log('Testing step movements...');
            fetch('/test_step_movements')
                .then(function(response) {
                    console.log('Test step movements response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Test step movements response data:', data);
                    alert(data.message || data.error);
                })
                .catch(function(error) {
                    console.error('Test step movements error:', error);
                    alert('Failed to test step movements: ' + error.message);
                });
        }
        
        function getCurrentPosition() {
            console.log('Getting current position...');
            fetch('/get_current_position')
                .then(function(response) {
                    console.log('Get position response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Get position response data:', data);
                    var pos = data.position;
                    alert('Current Position: X' + pos.x + ' Y' + pos.y + ' Z' + pos.z + '\\nGRBL Status: ' + data.grbl_status);
                })
                .catch(function(error) {
                    console.error('Get position error:', error);
                    alert('Error getting position: ' + error.message);
                });
        }
        
        function returnHome() {
            console.log('Returning to home position...');
            fetch('/return_home')
                .then(function(response) {
                    console.log('Return home response status: ' + response.status);
                    return response.json();
                })
                .then(function(data) {
                    console.log('Return home response data:', data);
                    alert(data.message || data.error);
                })
                .catch(function(error) {
                    console.error('Return home error:', error);
                    alert('Failed to return home: ' + error.message);
                });
        }
        
        function emergencyStop() {
            fetch('/emergency_stop')
                .then(function(response) { return response.json(); })
                .then(function(data) { alert(data.message); });
        }
        
        // Update status every 2 seconds
        setInterval(updateStatus, 2000);
        setInterval(updateCurrentPosition, 5000);
        updateStatus();
        updateCurrentPosition();
        
        // Page initialization - moved to end to ensure all functions are defined
        document.addEventListener('DOMContentLoaded', function() {
            console.log('=== PAGE LOADED ===');
            console.log('Current URL:', window.location.href);
            console.log('Starting status updates...');
            
            // Initialize button states (system starts unhomed)
            updateButtonStates();
            
            // Verify test functions are available
            console.log('=== FUNCTION VERIFICATION ===');
            console.log('Functions loaded successfully');
            console.log('Test functions ready');
            
            // Add test functions to window object for debugging
            window.testFunctions = {
                simpleAlert: simpleAlert,
                buttonTest: buttonTest,
                consoleTest: consoleTest
            };
            
            console.log('Test functions added to window.testFunctions');
            
            // Test basic server connectivity on page load
            ping();
        });
    </script>
</body>
</html>
"""

def main():
    """Main function to run the integrated system"""
    print("Integrated Camera Positioning and Photo Capture System")
    print("FluidNC 4DOF Version")
    print("=" * 60)
    
    # Initialize system with FluidNC (4DOF) by default
    print("Initializing FluidNC 4DOF system...")
    system = IntegratedCameraSystem(use_fluidnc=True)
    
    try:
        # Initialize positioning system
        if not system.initialize_positioning_system():
            print("Failed to initialize FluidNC system!")
            print("Trying GRBL fallback...")
            # Try GRBL fallback
            system = IntegratedCameraSystem(use_fluidnc=False)
            if not system.initialize_positioning_system():
                print("Failed to initialize any positioning system!")
                return
        
        controller_type = "FluidNC 4DOF" if system.use_fluidnc else "GRBL 3DOF"
        print(f"System initialized successfully with {controller_type}!")
        print(f"⚠️ Controller may be in alarm state - use web interface to Home or Unlock")
        print("\nAvailable operations:")
        print("1. Start web interface (FluidNC 4DOF with Home/Unlock options)")
        print("2. Test controller connection and movement") 
        print("3. Test step-by-step movements (5mm steps)")
        print("4. Run test grid scan (with 4DOF if FluidNC)")
        print("5. Run test circular scan")
        print("6. Manual photo capture test")
        if system.use_fluidnc:
            print("7. Test 4DOF rotational scan")
            print("8. Test 4DOF camera tilt scan")
            print("9. Test 4DOF spherical scan")
        print("7. Exit")
        
        choice = input("\nSelect operation (1-7): ").strip()
        
        if choice == "1":
            print(f"Starting web interface on http://localhost:{system.video_server_port}")
            print("💡 Use Home to initialize coordinate system or Unlock for manual control")
            print("Press Ctrl+C to stop...")
            system.start_web_interface()
            
        elif choice == "2":
            print("Testing GRBL connection and movement...")
            success = system.test_grbl_connection()
            print(f"GRBL test {'passed' if success else 'failed'}")
            
        elif choice == "3":
            print("Testing step-by-step movements...")
            success = system.test_step_movements()
            print(f"Step movement test {'passed' if success else 'failed'}")
            
        elif choice == "4":
            print("Running test grid scan...")
            corner1 = Point(0, 0, 5)
            corner2 = Point(10, 10, 5)
            success = system.grid_scan_with_photos(corner1, corner2, (2, 2))
            print(f"Grid scan {'completed' if success else 'failed'}")
            
        elif choice == "5":
            print("Running test circular scan...")
            center = Point(5, 5, 5)
            success = system.circular_scan_with_photos(center, 3, 4)
            print(f"Circular scan {'completed' if success else 'failed'}")
            
        elif choice == "6":
            print("Testing manual photo capture...")
            pos = Point(0, 0, 5, 0)  # 4DOF point
            system.controller.move_to_point(pos, feedrate=500)
            filename = system.capture_photo_at_position(pos, "test")
            print(f"Photo captured: {filename}" if filename else "Photo capture failed")
            
        elif choice == "7":
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
