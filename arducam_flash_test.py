#!/usr/bin/env python3
"""
Dual Camera Flash Capture Test with Arducam 64MP Support
Tests capturing from two cameras simultaneously with synchronized LED flash control
Optimized for Arducam 64MP cameras with high-resolution capture modes
"""

import cv2
import numpy as np
import time
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
import logging
import json
import serial
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
import tempfile
import signal
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class FlashConfig:
    """LED Flash configuration parameters"""
    frequency: int = 300      # 300Hz PWM frequency
    duty_cycle: float = 50.0  # Flash intensity (10-90%)
    gpio_pins: Optional[list] = None    # GPIO pins [4, 5]
    pre_flash_ms: int = 50    # Pre-flash duration for AF/AE
    main_flash_ms: int = 100  # Main flash duration
    flash_delay_ms: int = 10  # Delay between camera trigger and flash
    
    def __post_init__(self):
        if self.gpio_pins is None:
            self.gpio_pins = [4, 5]

class PWMFlashController:
    """Simplified PWM controller for camera flash integration"""
    
    def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.is_connected = False
    
    def connect(self) -> bool:
        """Connect to the CircuitPython board"""
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            
            # Test connection with a simple command
            time.sleep(2)  # Allow CircuitPython to initialize
            self.serial_connection.write(b'ping\n')
            response = self.serial_connection.readline().decode().strip()
            
            if 'pong' in response.lower():
                self.is_connected = True
                logger.info(f"Flash controller connected on {self.port}")
                return True
            else:
                logger.warning(f"Unexpected response from flash controller: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to flash controller: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the CircuitPython board"""
        if self.serial_connection:
            try:
                self.serial_connection.close()
                self.is_connected = False
                logger.info("Flash controller disconnected")
            except:
                pass
    
    def trigger_flash(self, config: FlashConfig) -> bool:
        """Trigger flash with specified configuration"""
        if not self.is_connected:
            logger.warning("Flash controller not connected")
            return False
        
        try:
            # Send flash command
            command = f"flash,{config.frequency},{config.duty_cycle},{config.main_flash_ms}\n"
            self.serial_connection.write(command.encode())
            
            # Wait for confirmation
            response = self.serial_connection.readline().decode().strip()
            
            if 'flash_complete' in response.lower():
                logger.info("Flash triggered successfully")
                return True
            else:
                logger.warning(f"Flash trigger failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Flash trigger error: {e}")
            return False

class ArducamFlashTest:
    """Main test class for dual camera flash capture"""
    
    def __init__(self):
        self.flash_controller = PWMFlashController()
        self.output_dir = Path('./camera_captures')
        self.output_dir.mkdir(exist_ok=True)
        
        # Set up signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        """Handle CTRL+C gracefully"""
        print("\n🛑 Received interrupt signal. Shutting down...")
        self.flash_controller.disconnect()
        cv2.destroyAllWindows()
        sys.exit(0)
    
    def check_cameras(self) -> list:
        """Check available cameras using rpicam-hello"""
        print("🔍 Scanning for available cameras...")
        available_cameras = []
        
        try:
            result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'Available cameras:' in line:
                        continue
                    if ':' in line and ('arducam' in line.lower() or 'camera' in line.lower()):
                        try:
                            camera_id = int(line.split(':')[0])
                            available_cameras.append(camera_id)
                            print(f"  📷 Camera {camera_id}: {line.split(':', 1)[1].strip()}")
                        except:
                            continue
            
            if not available_cameras:
                print("❌ No cameras detected")
            else:
                print(f"✅ Found {len(available_cameras)} camera(s)")
                
        except Exception as e:
            print(f"❌ Camera detection failed: {e}")
            
        return available_cameras
    
    def dual_camera_preview_menu(self, available_cameras: list):
        """Enhanced dual camera preview with multiple options"""
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras for dual preview")
            return
        
        print("\n🎬 Dual Camera Preview Options:")
        print("1. Fast switching (3-second intervals)")
        print("2. Side-by-side windows")
        print("3. FFmpeg side-by-side (experimental)")
        print("4. Custom OpenCV viewer")
        
        try:
            choice = input("Select preview mode (1-4): ").strip()
            
            if choice == '1':
                self._fast_switching_preview(available_cameras)
            elif choice == '2':
                self._simultaneous_windows_preview(available_cameras)
            elif choice == '3':
                self._ffmpeg_side_by_side_preview(available_cameras)
            elif choice == '4':
                self._custom_opencv_viewer(available_cameras)
            else:
                print("Invalid choice")
                
        except KeyboardInterrupt:
            print("\nPreview cancelled")
    
    def _fast_switching_preview(self, available_cameras: list):
        """Fast switching between cameras every 3 seconds"""
        print("🔄 Fast switching preview:")
        print("  - Switches between cameras every 3 seconds")
        print("  - Press CTRL+C to stop")
        print("  - Clear camera identification")
        
        try:
            while True:
                for camera_id in available_cameras:
                    print(f"📷 Showing Camera {camera_id}")
                    
                    process = subprocess.Popen([
                        'rpicam-hello',
                        '--camera', str(camera_id),
                        '--timeout', '3000',
                        '--info-text', f'"Camera {camera_id} - %fps fps"'
                    ])
                    
                    process.wait()
                    
        except KeyboardInterrupt:
            print("\nFast switching preview stopped")
    
    def _simultaneous_windows_preview(self, available_cameras: list):
        """Show both cameras in separate windows simultaneously"""
        print("🪟 Simultaneous windows preview:")
        print("  - Opens separate preview window for each camera")
        print("  - Shows both cameras at the same time")
        print("  - Press CTRL+C to stop")
        
        processes = []
        
        try:
            for i, camera_id in enumerate(available_cameras[:2]):
                x_offset = i * 650  # Position windows side by side
                
                process = subprocess.Popen([
                    'rpicam-hello',
                    '--camera', str(camera_id),
                    '--timeout', '0',
                    '--info-text', f'"Camera {camera_id} - %fps fps"',
                    '--preview', f'0,0,640,480'
                ])
                
                processes.append(process)
                time.sleep(1)  # Small delay between camera starts
            
            print("✅ Both camera previews started")
            print("Press CTRL+C to stop...")
            
            # Wait for user interrupt
            while all(p.poll() is None for p in processes):
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\nStopping simultaneous previews...")
        finally:
            for process in processes:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except:
                    process.kill()
    
    def _ffmpeg_side_by_side_preview(self, available_cameras: list):
        """FFmpeg-based side-by-side preview with interactive method selection"""
        print("🎞️ FFmpeg side-by-side preview:")
        print("  - Multiple streaming methods available")
        print("  - Interactive method testing")
        print("  - Press 'q' in windows/streams to quit")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras")
            return
        
        # First, test basic camera functionality
        print("🔍 Testing basic camera functionality...")
        for camera_id in available_cameras[:2]:
            try:
                test_result = subprocess.run([
                    'rpicam-vid', '--camera', str(camera_id), '--timeout', '1000', '--nopreview',
                    '--codec', 'mjpeg', '--output', f'/tmp/test_cam_{camera_id}.mjpeg'
                ], capture_output=True, timeout=10)
                
                if test_result.returncode == 0:
                    print(f"✅ Camera {camera_id} test successful")
                    test_file = f'/tmp/test_cam_{camera_id}.mjpeg'
                    if os.path.exists(test_file):
                        os.remove(test_file)
                else:
                    print(f"❌ Camera {camera_id} test failed: {test_result.stderr.decode()}")
                    
            except Exception as e:
                print(f"❌ Camera {camera_id} test error: {e}")
        
        # Interactive method selection
        methods = [
            ("Real-time Video Stream", self._try_video_stream_method, "🎥 Live MJPEG video streams with web interface"),
            ("Pipe-based Streaming", self._try_pipe_streaming_method, "🔧 Direct stdout pipe streaming"),
            ("Simple Dual Images", self._try_simple_dual_images, "📸 Static image refresh method"),
            ("MJPEG Video Stream", self._try_mjpeg_video_stream, "📺 VLC-compatible HTTP streams"),
            ("Alternating Camera Stream", self._try_alternating_stream_method, "🔄 Alternating dual camera display"),
            ("Web Image Stream", self._try_web_stream_method, "🌐 Web-based still image updates"),
            ("Simple MJPEG Test", self._try_simple_mjpeg_test, "📹 Single camera FFmpeg test"),
            ("MJPEG File Streaming", self._try_mjpeg_ffmpeg_method, "📁 File-based dual MJPEG"),
            ("Raw YUV Method", self._try_raw_ffmpeg_method, "🎬 Raw video streaming"),
            ("File-based H.264", self._try_file_based_ffmpeg_method, "📼 H.264 file streaming"),
            ("UDP Streaming", self._try_udp_ffmpeg_method, "🌐 UDP network streaming")
        ]
        
        while True:
            print(f"\n{'='*60}")
            print("🎛️  INTERACTIVE STREAMING METHOD SELECTOR")
            print(f"{'='*60}")
            print("Available streaming methods:")
            
            for i, (name, method, description) in enumerate(methods, 1):
                print(f"{i:2}. {name:<25} - {description}")
            
            print(f"{len(methods)+1:2}. Exit to main menu")
            
            try:
                choice = input(f"\nSelect method to test (1-{len(methods)+1}): ").strip()
                
                if choice == str(len(methods)+1):
                    print("Returning to main menu...")
                    break
                
                try:
                    method_idx = int(choice) - 1
                    if 0 <= method_idx < len(methods):
                        name, method, description = methods[method_idx]
                        print(f"\n🚀 Testing: {name}")
                        print(f"📝 Description: {description}")
                        print("-" * 50)
                        
                        try:
                            success = method(available_cameras)
                            if success:
                                print(f"✅ {name} completed successfully!")
                            else:
                                print(f"❌ {name} failed or was stopped")
                        except KeyboardInterrupt:
                            print(f"\n⏹️  {name} stopped by user")
                        except Exception as e:
                            print(f"❌ {name} error: {e}")
                        
                        print("\nReturning to method selector...")
                        time.sleep(2)
                    else:
                        print("❌ Invalid selection")
                except ValueError:
                    print("❌ Please enter a valid number")
                    
            except KeyboardInterrupt:
                print("\nExiting method selector...")
                break
    
    def _try_video_stream_method(self, available_cameras: list) -> bool:
        """Fixed real-time video streaming using separate TCP ports for each camera"""
        print("🎥 Trying fixed real-time video streaming...")
        print("This creates live TCP MJPEG video streams for both cameras simultaneously")
        
        try:
            import threading
            import http.server
            import socketserver
            import socket
            
            if len(available_cameras) < 2:
                print("❌ Need at least 2 cameras")
                return False
            
            camera1_id, camera2_id = available_cameras[0], available_cameras[1]
            
            # Create a custom HTTP handler for MJPEG streaming
            class DualMJPEGHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/':
                        self.send_dual_camera_page()
                    elif self.path == '/camera1.mjpg':
                        self.stream_tcp_camera(8091)
                    elif self.path == '/camera2.mjpg':
                        self.stream_tcp_camera(8092)
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def send_dual_camera_page(self):
                    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Fixed Dual Camera Stream</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; margin: 0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .camera-container {{ display: inline-block; margin: 15px; vertical-align: top; }}
        .camera-stream {{ border: 3px solid #007bff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        h3 {{ color: #666; margin: 10px 0; }}
        .status {{ color: #28a745; margin: 10px; font-size: 16px; font-weight: bold; }}
        .info {{ background: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Fixed Dual Camera Stream</h1>
        <div class="status">✅ Both cameras streaming simultaneously at 30 FPS</div>
        
        <div>
            <div class="camera-container">
                <h3>📷 Camera {camera1_id}</h3>
                <img class="camera-stream" src="/camera1.mjpg" width="640" height="480" alt="Camera {camera1_id} Stream" />
            </div>
            
            <div class="camera-container">
                <h3>📷 Camera {camera2_id}</h3>
                <img class="camera-stream" src="/camera2.mjpg" width="640" height="480" alt="Camera {camera2_id} Stream" />
            </div>
        </div>
        
        <div class="info">
            <strong>🎯 Fixed Streaming Architecture</strong><br>
            Each camera streams on separate TCP ports to avoid conflicts.<br>
            Camera {camera1_id}: TCP port 8091 | Camera {camera2_id}: TCP port 8092<br>
            Press Ctrl+C in the terminal to stop streaming.
        </div>
    </div>
</body>
</html>
"""
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html_content.encode())
                
                def stream_tcp_camera(self, tcp_port):
                    """Stream from TCP port where camera is outputting MJPEG with retries"""
                    self.send_response(200)
                    self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                    self.send_header('Cache-Control', 'no-cache')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    
                    max_retries = 10
                    retry_delay = 1
                    
                    for attempt in range(max_retries):
                        try:
                            print(f"Attempting to connect to camera TCP port {tcp_port} (attempt {attempt + 1})")
                            
                            # Connect to camera's TCP stream
                            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            sock.settimeout(10)
                            sock.connect(('localhost', tcp_port))
                            
                            print(f"✅ Connected to camera TCP port {tcp_port}")
                            
                            buffer = b''
                            frame_count = 0
                            
                            while True:
                                try:
                                    data = sock.recv(8192)
                                    if not data:
                                        print(f"No more data from port {tcp_port}")
                                        break
                                    
                                    buffer += data
                                    
                                    # Look for JPEG frames in buffer
                                    while True:
                                        start = buffer.find(b'\xff\xd8')  # JPEG start
                                        if start == -1:
                                            break
                                        
                                        end = buffer.find(b'\xff\xd9', start)  # JPEG end
                                        if end == -1:
                                            break
                                        
                                        # Extract complete JPEG frame
                                        frame = buffer[start:end + 2]
                                        buffer = buffer[end + 2:]
                                        
                                        # Send frame to browser
                                        self.wfile.write(b'\r\n--frame\r\n')
                                        self.wfile.write(b'Content-Type: image/jpeg\r\n')
                                        self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                                        self.wfile.write(frame)
                                        
                                        frame_count += 1
                                        if frame_count % 30 == 0:  # Log every 30 frames
                                            print(f"📺 Port {tcp_port}: {frame_count} frames streamed")
                                        
                                except socket.timeout:
                                    print(f"Timeout reading from port {tcp_port}")
                                    break
                                except Exception as e:
                                    print(f"Error reading frame from port {tcp_port}: {e}")
                                    break
                            
                            sock.close()
                            return  # Successfully streamed
                            
                        except ConnectionRefusedError:
                            print(f"❌ Connection refused to port {tcp_port} (attempt {attempt + 1})")
                            if attempt < max_retries - 1:
                                print(f"Retrying in {retry_delay} seconds...")
                                time.sleep(retry_delay)
                                continue
                            else:
                                print(f"❌ Failed to connect to port {tcp_port} after {max_retries} attempts")
                                break
                        except Exception as e:
                            print(f"TCP streaming error on port {tcp_port}: {e}")
                            if attempt < max_retries - 1:
                                time.sleep(retry_delay)
                                continue
                            else:
                                break
                    
                    # If we get here, all attempts failed
                    error_msg = f"Failed to connect to camera stream on port {tcp_port}"
                    self.wfile.write(f"--frame\r\nContent-Type: text/plain\r\n\r\n{error_msg}\r\n".encode())
                
                def log_message(self, format, *args):
                    pass  # Suppress HTTP log messages
            
            # Start camera processes on separate TCP ports
            cam_processes = []
            tcp_ports = [8091, 8092]
            
            for i, camera_id in enumerate([camera1_id, camera2_id]):
                tcp_port = tcp_ports[i]
                
                print(f"Starting camera {camera_id} on TCP port {tcp_port}...")
                
                # First check if camera is available
                test_cmd = ['rpicam-hello', '--camera', str(camera_id), '--timeout', '1000']
                test_result = subprocess.run(test_cmd, capture_output=True, timeout=10)
                
                if test_result.returncode != 0:
                    print(f"❌ Camera {camera_id} not available or busy")
                    continue
                
                # Start the camera stream
                process = subprocess.Popen([
                    'rpicam-vid',
                    '--camera', str(camera_id),
                    '--timeout', '0',  # Infinite
                    '--width', '640',
                    '--height', '480',
                    '--framerate', '15',  # Reduced framerate for stability
                    '--codec', 'mjpeg',
                    '--quality', '80',
                    '--listen',  # TCP server mode
                    '--output', f'tcp://0.0.0.0:{tcp_port}',
                    '--nopreview',
                    '--flush'  # Ensure immediate output
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                
                # Give this camera time to fully start
                print(f"Waiting for camera {camera_id} to initialize...")
                time.sleep(4)
                
                # Check if process is still running
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    print(f"❌ Camera {camera_id} process failed:")
                    print(f"   stdout: {stdout.decode()}")
                    print(f"   stderr: {stderr.decode()}")
                    continue
                
                print(f"✅ Camera {camera_id} process started successfully")
            
            if not cam_processes:
                raise Exception("No camera processes started successfully")
            
            # Wait for TCP streams to be ready
            print("Waiting for TCP streams to initialize...")
            time.sleep(8)  # Give more time for streams to be ready
            
            # Test TCP connections with retries
            ready_cameras = []
            for i, tcp_port in enumerate(tcp_ports[:len(cam_processes)]):
                camera_id = [camera1_id, camera2_id][i]
                
                for attempt in range(5):
                    try:
                        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        test_sock.settimeout(3)
                        test_sock.connect(('localhost', tcp_port))
                        
                        # Try to read a small amount of data to verify stream
                        test_sock.settimeout(2)
                        test_data = test_sock.recv(100)
                        test_sock.close()
                        
                        if test_data:
                            print(f"✅ Camera {camera_id} TCP stream ready on port {tcp_port} - {len(test_data)} bytes received")
                            ready_cameras.append(camera_id)
                            break
                        else:
                            print(f"⚠️ Camera {camera_id} TCP connected but no data (attempt {attempt + 1}/5)")
                    except Exception as e:
                        print(f"⚠️ Camera {camera_id} TCP test failed (attempt {attempt + 1}/5): {e}")
                        if attempt < 4:
                            time.sleep(2)
                
                if camera_id not in ready_cameras:
                    print(f"❌ Camera {camera_id} TCP stream not ready after 5 attempts")
            
            if not ready_cameras:
                raise Exception("No TCP streams are ready")
            
            # Start HTTP server
            http_port = 8080
            
            def start_server():
                with socketserver.TCPServer(("", http_port), DualMJPEGHandler) as httpd:
                    print(f"HTTP server started on port {http_port}")
                    httpd.serve_forever()
            
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()
            
            print(f"✅ Fixed dual camera streaming ready!")
            print(f"🎥 Open your browser: http://localhost:{http_port}")
            print(f"📱 Or from another device: http://{self._get_local_ip()}:{http_port}")
            print("\n🎯 Both cameras should now stream simultaneously!")
            print("📊 Architecture: Separate TCP ports prevent conflicts")
            print("Press Ctrl+C to stop streaming")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping video streams...")
            
            return True
            
        except Exception as e:
            print(f"❌ Fixed video streaming failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup
            print("Cleaning up video streams...")
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except:
                    try:
                        process.kill()
                    except:
                        pass
    
    def _try_alternating_stream_method(self, available_cameras: list) -> bool:
        """Alternating camera display - shows cameras one at a time to avoid conflicts"""
        print("🔄 Trying alternating camera stream...")
        print("This switches between cameras every few seconds to avoid conflicts")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras")
            return False
        
        try:
            import threading
            import http.server
            
            camera1_id, camera2_id = available_cameras[0], available_cameras[1]
            current_camera = 0
            switch_interval = 3  # Switch every 3 seconds
            
            class AlternatingHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/' or self.path == '/index.html':
                        self.send_main_page()
                    elif self.path == '/current_camera.jpg':
                        self.send_current_camera_image()
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def send_main_page(self):
                    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Alternating Dual Camera</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; margin: 0; padding: 20px; }}
        .container {{ max-width: 800px; margin: 0 auto; }}
        .camera-display {{ border: 3px solid #28a745; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .status {{ color: #28a745; margin: 10px; font-size: 16px; font-weight: bold; }}
        .info {{ background: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        #cameraLabel {{ color: #666; margin: 10px 0; font-size: 18px; }}
    </style>
    <script>
        function updateImage() {{
            var img = document.getElementById('cameraImg');
            var label = document.getElementById('cameraLabel');
            var timestamp = new Date().getTime();
            img.src = '/current_camera.jpg?' + timestamp;
            
            // Update every second
            setTimeout(updateImage, 1000);
        }}
        
        window.onload = function() {{
            updateImage();
        }}
    </script>
</head>
<body>
    <div class="container">
        <h1>🔄 Alternating Dual Camera Stream</h1>
        <div class="status">✅ Switching between cameras every {switch_interval} seconds</div>
        
        <div id="cameraLabel">📷 Current Camera: Loading...</div>
        <img id="cameraImg" class="camera-display" width="640" height="480" alt="Camera Stream" />
        
        <div class="info">
            <strong>🎯 Alternating Camera Display</strong><br>
            Camera {camera1_id} and Camera {camera2_id} alternate to prevent conflicts.<br>
            Images update every second, cameras switch every {switch_interval} seconds.<br>
            Press Ctrl+C in the terminal to stop streaming.
        </div>
    </div>
</body>
</html>
"""
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html_content.encode())
                
                def send_current_camera_image(self):
                    """Capture and send image from current camera"""
                    try:
                        current_cam_id = [camera1_id, camera2_id][current_camera]
                        temp_file = f'/tmp/current_camera_{current_cam_id}.jpg'
                        
                        # Clean up any existing file
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        
                        # Capture image with improved settings
                        capture_cmd = [
                            'rpicam-still',
                            '--camera', str(current_cam_id),
                            '--width', '640',
                            '--height', '480',
                            '--quality', '85',
                            '--timeout', '1000',  # 1 second timeout
                            '--output', temp_file,
                            '--nopreview',
                            '--immediate'  # Take photo immediately
                        ]
                        
                        result = subprocess.run(capture_cmd, capture_output=True, timeout=5)
                        
                        if result.returncode == 0 and os.path.exists(temp_file):
                            # Send the image
                            with open(temp_file, 'rb') as f:
                                image_data = f.read()
                            
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', str(len(image_data)))
                            self.send_header('Cache-Control', 'no-cache')
                            self.send_header('X-Camera-ID', str(current_cam_id))  # Add camera ID header
                            self.end_headers()
                            self.wfile.write(image_data)
                            
                            # Cleanup
                            os.remove(temp_file)
                            
                            # Log success occasionally
                            if hasattr(self, '_image_count'):
                                self._image_count += 1
                            else:
                                self._image_count = 1
                            
                            if self._image_count % 10 == 0:
                                print(f"📸 Served {self._image_count} images from camera {current_cam_id}")
                                
                        else:
                            # Send error image
                            error_msg = f"Camera {current_cam_id} capture failed"
                            if result.stderr:
                                error_msg += f": {result.stderr.decode()}"
                            self.send_error_image(error_msg)
                    
                    except subprocess.TimeoutExpired:
                        self.send_error_image(f"Camera {current_cam_id} timeout")
                    except Exception as e:
                        self.send_error_image(f"Error: {e}")
                
                def send_error_image(self, message):
                    """Send a simple error message as text"""
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"Error: {message}".encode())
                
                def log_message(self, format, *args):
                    pass  # Suppress HTTP log messages
            
            # Camera switching function
            def switch_cameras():
                nonlocal current_camera
                while True:
                    time.sleep(switch_interval)
                    current_camera = 1 - current_camera  # Switch between 0 and 1
                    cam_name = [camera1_id, camera2_id][current_camera]
                    print(f"🔄 Switched to Camera {cam_name}")
            
            # Start camera switching thread
            switch_thread = threading.Thread(target=switch_cameras, daemon=True)
            switch_thread.start()
            
            # Start HTTP server
            http_port = 8080
            server = http.server.HTTPServer(('localhost', http_port), AlternatingHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            
            print(f"✅ Alternating camera streaming ready!")
            print(f"🎥 Open your browser: http://localhost:{http_port}")
            print(f"📱 Or from another device: http://{self._get_local_ip()}:{http_port}")
            print(f"\n🔄 Cameras will alternate every {switch_interval} seconds")
            print(f"📷 Camera {camera1_id} ↔️ Camera {camera2_id}")
            print("Press Ctrl+C to stop streaming")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping alternating stream...")
            
            server.shutdown()
            return True
            
        except Exception as e:
            print(f"❌ Alternating stream failed: {e}")
            return False

    def _try_pipe_streaming_method(self, available_cameras: list) -> bool:
        """Direct pipe-based streaming - avoids TCP connection limits"""
        print("🔧 Trying pipe-based streaming...")
        print("This captures camera output directly via pipes - should avoid TCP issues")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras")
            return False
        
        try:
            import threading
            import http.server
            import queue
            
            camera1_id, camera2_id = available_cameras[0], available_cameras[1]
            
            # Queues to hold latest frames from each camera
            camera_frames = {camera1_id: queue.Queue(maxsize=2), camera2_id: queue.Queue(maxsize=2)}
            camera_processes = {}
            
            class PipeStreamHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    print(f"🌐 HTTP Request: {self.path} from {self.client_address[0]}")
                    
                    if self.path == '/':
                        self.send_dual_camera_page()
                    elif self.path == '/camera1.mjpg':
                        print(f"📺 Browser requesting Camera {camera1_id} stream")
                        self.stream_camera_pipe(camera1_id)
                    elif self.path == '/camera2.mjpg':
                        print(f"📺 Browser requesting Camera {camera2_id} stream")
                        self.stream_camera_pipe(camera2_id)
                    else:
                        print(f"❌ Unknown path requested: {self.path}")
                        self.send_response(404)
                        self.end_headers()
                
                def send_dual_camera_page(self):
                    print(f"📄 Sending HTML page with camera streams: {camera1_id} and {camera2_id}")
                    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Dual Camera MJPEG Streams</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; margin: 0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .camera-container {{ display: inline-block; margin: 15px; vertical-align: top; }}
        .camera-stream {{ border: 3px solid #007bff; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        h3 {{ color: #666; margin: 10px 0; }}
        .status {{ color: #007bff; margin: 10px; font-size: 16px; font-weight: bold; }}
        .info {{ background: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎥 Dual Camera MJPEG Streams</h1>
        <div class="status">✅ Live video streams from both cameras</div>
        
        <div>
            <div class="camera-container">
                <h3>📷 Camera {camera1_id}</h3>
                <img class="camera-stream" src="/camera1.mjpg" width="640" height="480" alt="Camera {camera1_id} Stream" />
            </div>
            
            <div class="camera-container">
                <h3>📷 Camera {camera2_id}</h3>
                <img class="camera-stream" src="/camera2.mjpg" width="640" height="480" alt="Camera {camera2_id} Stream" />
            </div>
        </div>
        
        <div class="info">
            <strong>🎯 MJPEG Video Streaming</strong><br>
            Both cameras streaming live video via MJPEG protocol.<br>
            Direct streams: <a href="/camera1.mjpg">Camera {camera1_id}</a> | <a href="/camera2.mjpg">Camera {camera2_id}</a><br>
            Press Ctrl+C in terminal to stop.
        </div>
    </div>
</body>
</html>
"""
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html_content.encode())
                
                def stream_camera_pipe(self, camera_id):
                    """Stream from camera pipe queue with corrected MJPEG format"""
                    print(f"🎬 Starting MJPEG stream for camera {camera_id}")
                    
                    # Check queue status before starting
                    queue_size = camera_frames[camera_id].qsize()
                    print(f"📊 Camera {camera_id} queue status: {queue_size} frames available")
                    
                    try:
                        # Send proper MJPEG streaming headers immediately
                        self.send_response(200)
                        self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                        self.send_header('Pragma', 'no-cache') 
                        self.send_header('Expires', '0')
                        self.send_header('Connection', 'close')  # Changed from keep-alive
                        self.end_headers()
                        
                        # Send initial boundary immediately
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.flush()
                        
                        # Get first frame immediately if available
                        try:
                            if not camera_frames[camera_id].empty():
                                first_frame = camera_frames[camera_id].get_nowait()
                                if first_frame and len(first_frame) > 100:
                                    print(f"🚀 Camera {camera_id}: Sending first frame immediately")
                                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                                    self.wfile.write(f'Content-Length: {len(first_frame)}\r\n\r\n'.encode())
                                    self.wfile.write(first_frame)
                                    self.wfile.write(b'\r\n--frame\r\n')
                                    self.wfile.flush()
                        except:
                            pass
                        
                        frame_count = 1  # Already sent first frame
                        consecutive_failures = 0
                        
                        while True:
                            try:
                                # Get frame from queue with shorter timeout
                                frame_data = camera_frames[camera_id].get(timeout=0.5)
                                consecutive_failures = 0  # Reset failure counter
                                
                                if frame_data and len(frame_data) > 100:
                                    # Send MJPEG frame with simpler format
                                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                                    self.wfile.write(f'Content-Length: {len(frame_data)}\r\n\r\n'.encode())
                                    self.wfile.write(frame_data)
                                    self.wfile.write(b'\r\n--frame\r\n')
                                    self.wfile.flush()
                                    
                                    frame_count += 1
                                    if frame_count % 30 == 0:
                                        print(f"📺 Camera {camera_id}: {frame_count} frames streamed (queue: {camera_frames[camera_id].qsize()})")
                                        
                            except queue.Empty:
                                consecutive_failures += 1
                                if consecutive_failures > 5:
                                    print(f"⏳ Camera {camera_id}: No frames available, ending stream")
                                    break
                                continue
                            except (ConnectionResetError, BrokenPipeError) as e:
                                print(f"🔌 Camera {camera_id}: Client disconnected - {e}")
                                break
                            except Exception as e:
                                print(f"📡 Camera {camera_id}: Stream error - {e}")
                                break
                                
                    except (ConnectionResetError, BrokenPipeError) as e:
                        print(f"🔌 Camera {camera_id}: Connection broken during setup - {e}")
                    except Exception as e:
                        print(f"❌ Camera {camera_id}: MJPEG streaming error - {e}")
                    
                    print(f"🛑 MJPEG stream ended for camera {camera_id}")
                
                def log_message(self, format, *args):
                    pass
            
            def camera_pipe_reader(camera_id):
                """Direct memory streaming - proper simultaneous camera handling"""
                try:
                    print(f"Starting direct memory stream for camera {camera_id}")
                    
                    # Start camera process with different ports to avoid conflicts
                    port = 9000 + camera_id
                    
                    process = subprocess.Popen([
                        'rpicam-vid',
                        '--camera', str(camera_id),
                        '--timeout', '0',
                        '--width', '640',
                        '--height', '480',
                        '--framerate', '15',
                        '--codec', 'mjpeg',
                        '--inline',  # Put stream headers inline
                        '--listen',  # Listen mode
                        '--output', f'tcp://0.0.0.0:{port}',
                        '--nopreview'
                    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    camera_processes[camera_id] = process
                    
                    # Give camera time to start listening
                    time.sleep(3)
                    
                    # Check if process started successfully
                    if process.poll() is not None:
                        stdout, stderr = process.communicate()
                        print(f"❌ Camera {camera_id} TCP server failed:")
                        if stderr:
                            print(f"   stderr: {stderr.decode()}")
                        return
                    
                    print(f"✅ Camera {camera_id} TCP server listening on port {port}")
                    
                    # TCP client to read from camera's stream
                    def tcp_frame_reader():
                        frame_count = 0
                        max_retries = 5
                        
                        for attempt in range(max_retries):
                            try:
                                import socket
                                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                sock.settimeout(5)
                                sock.connect(('localhost', port))
                                print(f"📡 Connected to camera {camera_id} TCP stream")
                                
                                buffer = b''
                                
                                while True:
                                    try:
                                        data = sock.recv(8192)
                                        if not data:
                                            print(f"Camera {camera_id} TCP stream ended")
                                            break
                                        
                                        buffer += data
                                        
                                        # Extract JPEG frames
                                        while True:
                                            start = buffer.find(b'\xff\xd8')
                                            if start == -1:
                                                break
                                            
                                            end = buffer.find(b'\xff\xd9', start + 2)
                                            if end == -1:
                                                break
                                            
                                            frame = buffer[start:end + 2]
                                            buffer = buffer[end + 2:]
                                            
                                            if len(frame) > 2000:
                                                # Keep queue small and fresh
                                                while camera_frames[camera_id].qsize() > 1:
                                                    try:
                                                        camera_frames[camera_id].get_nowait()
                                                    except:
                                                        break
                                                
                                                try:
                                                    camera_frames[camera_id].put_nowait(frame)
                                                    frame_count += 1
                                                    
                                                    if frame_count % 100 == 0:
                                                        print(f"📹 Camera {camera_id}: {frame_count} frames via TCP -> Queue size: {camera_frames[camera_id].qsize()}")
                                                except queue.Full:
                                                    print(f"⚠️ Camera {camera_id}: Queue full, dropping frame")
                                    
                                    except socket.timeout:
                                        print(f"⚠️ Camera {camera_id} TCP timeout")
                                        continue
                                    except Exception as e:
                                        print(f"TCP read error for camera {camera_id}: {e}")
                                        break
                                
                                sock.close()
                                break  # Success, exit retry loop
                                
                            except ConnectionRefusedError:
                                print(f"❌ Camera {camera_id} TCP connection refused (attempt {attempt + 1}/{max_retries})")
                                if attempt < max_retries - 1:
                                    time.sleep(2)
                                    continue
                                else:
                                    print(f"❌ Failed to connect to camera {camera_id} after {max_retries} attempts")
                                    break
                            except Exception as e:
                                print(f"TCP connection error for camera {camera_id}: {e}")
                                if attempt < max_retries - 1:
                                    time.sleep(2)
                                    continue
                                else:
                                    break
                    
                    # Start TCP reader thread
                    reader_thread = threading.Thread(target=tcp_frame_reader, daemon=True)
                    reader_thread.start()
                    
                    # Monitor process
                    while process.poll() is None:
                        time.sleep(1)
                    
                    print(f"Camera {camera_id} TCP process ended")
                    
                except Exception as e:
                    print(f"❌ Camera {camera_id} direct streaming error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Start camera pipe readers
            # Start camera processes with TCP servers on different ports
            for camera_id in [camera1_id, camera2_id]:
                thread = threading.Thread(target=camera_pipe_reader, args=(camera_id,), daemon=True)
                thread.start()
                time.sleep(2)  # Stagger camera starts
            
            # Wait for cameras to start producing frames
            print("Waiting for TCP camera streams to start...")
            time.sleep(8)  # Extra time for TCP servers
            
            # Check if we have frames
            frames_ready = 0
            for camera_id in [camera1_id, camera2_id]:
                if not camera_frames[camera_id].empty():
                    queue_size = camera_frames[camera_id].qsize()
                    print(f"✅ Camera {camera_id} TCP stream ready - {queue_size} frames in queue")
                    frames_ready += 1
                else:
                    print(f"⚠️ Camera {camera_id} TCP stream not ready yet")
            
            if frames_ready == 0:
                raise Exception("No camera TCP streams available")
            elif frames_ready < 2:
                print(f"⚠️ Only {frames_ready}/2 cameras producing frames, but continuing...")
            
            # Start HTTP server
            http_port = 8080
            server = http.server.HTTPServer(('localhost', http_port), PipeStreamHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            
            print(f"✅ TCP-based dual camera streaming ready!")
            print(f"🎥 Open your browser: http://localhost:{http_port}")
            print(f"📱 Or from another device: http://{self._get_local_ip()}:{http_port}")
            print(f"\n🔧 Using direct TCP streaming (no file operations)")
            print(f"📹 Active cameras: {[cam_id for cam_id in [camera1_id, camera2_id] if not camera_frames[cam_id].empty()]}")
            print("Press Ctrl+C to stop streaming")
            
            # Monitor frame production
            def monitor_frames():
                while True:
                    time.sleep(10)
                    print(f"📊 Frame Monitor:")
                    for camera_id in [camera1_id, camera2_id]:
                        queue_size = camera_frames[camera_id].qsize()
                        process = camera_processes.get(camera_id)
                        process_status = "running" if process and process.poll() is None else "stopped"
                        print(f"   � Camera {camera_id}: {queue_size} frames queued, process {process_status}")
            
            monitor_thread = threading.Thread(target=monitor_frames, daemon=True)
            monitor_thread.start()
            
            # Keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping pipe streaming...")
            
            server.shutdown()
            return True
            
        except Exception as e:
            print(f"❌ Pipe streaming failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup
            print("Cleaning up camera processes...")
            for camera_id, process in camera_processes.items():
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except:
                    try:
                        process.kill()
                    except:
                        pass

    def _try_simple_dual_images(self, available_cameras: list) -> bool:
        """Simple dual image display - takes photos from both cameras and refreshes"""
        print("📸 Trying simple dual image method...")
        print("This takes still photos from both cameras and refreshes them regularly")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras")
            return False
        
        try:
            import threading
            import http.server
            
            camera1_id, camera2_id = available_cameras[0], available_cameras[1]
            
            class DualImageHandler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/':
                        self.send_main_page()
                    elif self.path == '/camera1.jpg':
                        self.send_camera_image(camera1_id)
                    elif self.path == '/camera2.jpg':
                        self.send_camera_image(camera2_id)
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def send_main_page(self):
                    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Simple Dual Camera Images</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; margin: 0; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .camera-container {{ display: inline-block; margin: 15px; vertical-align: top; }}
        .camera-image {{ border: 3px solid #28a745; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        h3 {{ color: #666; margin: 10px 0; }}
        .status {{ color: #28a745; margin: 10px; font-size: 16px; font-weight: bold; }}
        .info {{ background: #e9ecef; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .controls {{ margin: 20px 0; }}
        button {{ padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; background: #007bff; color: white; cursor: pointer; }}
        button:hover {{ background: #0056b3; }}
    </style>
    <script>
        var refreshInterval;
        var isRunning = false;
        
        function updateImages() {{
            var timestamp = new Date().getTime();
            document.getElementById('camera1').src = '/camera1.jpg?' + timestamp;
            document.getElementById('camera2').src = '/camera2.jpg?' + timestamp;
            console.log('📸 Updated both camera images');
        }}
        
        function startAutoRefresh() {{
            if (!isRunning) {{
                refreshInterval = setInterval(updateImages, 2000); // Every 2 seconds
                isRunning = true;
                document.getElementById('startBtn').textContent = '⏹️ Stop Auto Refresh';
                console.log('🔄 Started auto refresh');
            }} else {{
                clearInterval(refreshInterval);
                isRunning = false;
                document.getElementById('startBtn').textContent = '▶️ Start Auto Refresh';
                console.log('⏹️ Stopped auto refresh');
            }}
        }}
        
        window.onload = function() {{
            updateImages(); // Initial load
            startAutoRefresh(); // Start automatically
        }};
    </script>
</head>
<body>
    <div class="container">
        <h1>📸 Simple Dual Camera Images</h1>
        <div class="status">✅ Static image method - highly reliable</div>
        
        <div class="controls">
            <button onclick="updateImages()">📷 Take New Photos</button>
            <button id="startBtn" onclick="startAutoRefresh()">⏹️ Stop Auto Refresh</button>
        </div>
        
        <div>
            <div class="camera-container">
                <h3>📷 Camera {camera1_id}</h3>
                <img id="camera1" class="camera-image" width="640" height="480" alt="Camera {camera1_id}" />
            </div>
            
            <div class="camera-container">
                <h3>📷 Camera {camera2_id}</h3>
                <img id="camera2" class="camera-image" width="640" height="480" alt="Camera {camera2_id}" />
            </div>
        </div>
        
        <div class="info">
            <strong>📸 Simple Image Method</strong><br>
            Takes individual photos from each camera and refreshes every 2 seconds.<br>
            No streaming conflicts - each camera is used independently.<br>
            Use controls above to manually update or toggle auto-refresh.
        </div>
    </div>
</body>
</html>
"""
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(html_content.encode())
                
                def send_camera_image(self, camera_id):
                    """Capture and send fresh image from specified camera"""
                    try:
                        temp_file = f'/tmp/dual_camera_{camera_id}.jpg'
                        
                        # Clean up existing file
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        
                        # Capture fresh image
                        capture_cmd = [
                            'rpicam-still',
                            '--camera', str(camera_id),
                            '--width', '640',
                            '--height', '480',
                            '--quality', '90',
                            '--timeout', '1000',
                            '--output', temp_file,
                            '--nopreview',
                            '--immediate'
                        ]
                        
                        result = subprocess.run(capture_cmd, capture_output=True, timeout=5)
                        
                        if result.returncode == 0 and os.path.exists(temp_file):
                            with open(temp_file, 'rb') as f:
                                image_data = f.read()
                            
                            self.send_response(200)
                            self.send_header('Content-Type', 'image/jpeg')
                            self.send_header('Content-Length', str(len(image_data)))
                            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                            self.send_header('Pragma', 'no-cache')
                            self.send_header('Expires', '0')
                            self.end_headers()
                            self.wfile.write(image_data)
                            
                            # Cleanup
                            os.remove(temp_file)
                            print(f"📸 Served fresh image from camera {camera_id}")
                        else:
                            self.send_error_response(f"Camera {camera_id} capture failed")
                    
                    except Exception as e:
                        self.send_error_response(f"Camera {camera_id} error: {e}")
                
                def send_error_response(self, message):
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(f"Error: {message}".encode())
                
                def log_message(self, format, *args):
                    pass
            
            # Start HTTP server
            http_port = 8080
            server = http.server.HTTPServer(('localhost', http_port), DualImageHandler)
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            
            print(f"✅ Simple dual camera images ready!")
            print(f"📸 Open your browser: http://localhost:{http_port}")
            print(f"📱 Or from another device: http://{self._get_local_ip()}:{http_port}")
            print(f"\n📷 Cameras: {camera1_id} and {camera2_id}")
            print("🔄 Images refresh automatically every 2 seconds")
            print("Press Ctrl+C to stop")
            
            # Keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping simple dual images...")
            
            server.shutdown()
            return True
            
        except Exception as e:
            print(f"❌ Simple dual images failed: {e}")
            return False

    def _try_mjpeg_video_stream(self, available_cameras: list) -> bool:
        """Alternative MJPEG streaming method using VLC-compatible streams"""
        print("📺 Trying VLC-compatible MJPEG streaming...")
        print("This creates streams that can be opened in VLC Media Player")
        
        try:
            # Start MJPEG streams on different ports
            cam_processes = []
            stream_ports = []
            
            for i, camera_id in enumerate(available_cameras[:2]):
                port = 8090 + i
                stream_ports.append(port)
                
                print(f"Starting MJPEG HTTP stream for camera {camera_id} on port {port}...")
                process = subprocess.Popen([
                    'rpicam-vid',
                    '--camera', str(camera_id),
                    '--timeout', '0',
                    '--width', '640',
                    '--height', '480',
                    '--framerate', '25',
                    '--codec', 'mjpeg',
                    '--listen',  # HTTP server mode
                    '--output', f'tcp://0.0.0.0:{port}'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(2)
            
            # Wait for streams to start
            time.sleep(3)
            
            print("✅ MJPEG HTTP streams started!")
            print(f"🎥 Camera 0 stream: http://localhost:{stream_ports[0]}")
            if len(stream_ports) > 1:
                print(f"🎥 Camera 1 stream: http://localhost:{stream_ports[1]}")
            
            print("\n📺 You can open these URLs in:")
            print("  • VLC Media Player (Media → Open Network Stream)")
            print("  • Any web browser")
            print("  • Video streaming applications")
            
            print("\n💡 For side-by-side viewing:")
            print("  • Open VLC twice with different stream URLs")
            print("  • Or use a multi-stream video player")
            
            print("\nPress Ctrl+C to stop streams")
            
            # Keep running
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping MJPEG streams...")
            
            return True
            
        except Exception as e:
            print(f"❌ MJPEG video streaming failed: {e}")
            return False
        finally:
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    process.kill()
    
    def _try_web_stream_method(self, available_cameras: list) -> bool:
        """Try web-based streaming that works without SDL/display"""
        print("🌐 Trying web streaming method...")
        print("This method creates a local web server to view the cameras")
        
        try:
            import http.server
            import socketserver
            import threading
            import urllib.parse
            
            # Create a simple HTML file for dual camera viewing
            html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Dual Camera Stream</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; background: #f0f0f0; }
        .camera-container { display: inline-block; margin: 10px; }
        .camera-frame { border: 2px solid #333; border-radius: 8px; }
        h1 { color: #333; }
        .refresh-info { color: #666; margin: 10px; }
    </style>
    <script>
        function refreshImages() {
            var img1 = document.getElementById('cam1');
            var img2 = document.getElementById('cam2');
            var timestamp = new Date().getTime();
            img1.src = 'camera_0_latest.jpg?' + timestamp;
            img2.src = 'camera_1_latest.jpg?' + timestamp;
        }
        
        setInterval(refreshImages, 1000); // Refresh every second
        
        window.onload = function() {
            refreshImages();
        }
    </script>
</head>
<body>
    <h1>🎥 Dual Camera Stream</h1>
    <div class="refresh-info">Images refresh every second</div>
    
    <div class="camera-container">
        <h3>Camera 0</h3>
        <img id="cam1" class="camera-frame" width="640" height="480" alt="Camera 0" />
    </div>
    
    <div class="camera-container">
        <h3>Camera 1</h3>
        <img id="cam2" class="camera-frame" width="640" height="480" alt="Camera 1" />
    </div>
    
    <div style="margin-top: 20px;">
        <button onclick="refreshImages()">🔄 Manual Refresh</button>
        <p>Press Ctrl+C in terminal to stop streaming</p>
    </div>
</body>
</html>
"""
            
            # Create web directory
            web_dir = "/tmp/dual_camera_web"
            os.makedirs(web_dir, exist_ok=True)
            
            # Write HTML file
            with open(f"{web_dir}/index.html", "w") as f:
                f.write(html_content)
            
            # Start camera capture processes
            cam_processes = []
            for camera_id in available_cameras[:2]:
                output_file = f"{web_dir}/camera_{camera_id}_latest.jpg"
                
                # Remove existing file
                if os.path.exists(output_file):
                    os.remove(output_file)
                
                print(f"Starting web capture for camera {camera_id}...")
                
                # Use rpicam-still in a loop to continuously capture images
                process = subprocess.Popen([
                    'bash', '-c', f'''
                    while true; do
                        rpicam-still --camera {camera_id} --timeout 100 --width 640 --height 480 --nopreview -o {output_file} 2>/dev/null
                        sleep 0.5
                    done
                    '''
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(1)
            
            # Wait for initial images
            print("Waiting for initial camera captures...")
            time.sleep(3)
            
            # Check if images are being created
            for camera_id in available_cameras[:2]:
                output_file = f"{web_dir}/camera_{camera_id}_latest.jpg"
                if not os.path.exists(output_file):
                    raise Exception(f"Camera {camera_id} image not created")
                print(f"✅ Camera {camera_id} image ready: {os.path.getsize(output_file)} bytes")
            
            # Start web server
            class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=web_dir, **kwargs)
                
                def log_message(self, format, *args):
                    pass  # Suppress HTTP log messages
            
            port = 8080
            
            def start_server():
                with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
                    httpd.serve_forever()
            
            server_thread = threading.Thread(target=start_server, daemon=True)
            server_thread.start()
            
            print(f"✅ Web server started!")
            print(f"🌐 Open your browser and go to: http://localhost:{port}")
            print(f"📱 Or from another device: http://{self._get_local_ip()}:{port}")
            print("\nThe page will show both cameras side by side, refreshing every second")
            print("Press Ctrl+C to stop the web stream")
            
            # Keep running until interrupted
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nStopping web stream...")
            
            return True
            
        except Exception as e:
            print(f"❌ Web stream method failed: {e}")
            return False
        finally:
            # Cleanup
            print("Cleaning up web stream...")
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    process.kill()
            
            # Clean up web directory
            try:
                import shutil
                if os.path.exists(web_dir):
                    shutil.rmtree(web_dir)
            except:
                pass
    
    def _get_local_ip(self):
        """Get local IP address"""
        try:
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except:
            return "127.0.0.1"
    
    def _try_simple_mjpeg_test(self, available_cameras: list) -> bool:
        """Simple test to see if we can display one camera with FFmpeg"""
        print("📹 Testing simple single camera FFmpeg display...")
        
        try:
            camera_id = available_cameras[0]
            temp_file = f"/tmp/simple_test_cam_{camera_id}.mjpeg"
            
            # Remove existing file
            if os.path.exists(temp_file):
                os.remove(temp_file)
            
            print(f"Starting camera {camera_id} MJPEG stream...")
            cam_process = subprocess.Popen([
                'rpicam-vid',
                '--camera', str(camera_id),
                '--timeout', '0',
                '--width', '640',
                '--height', '480',
                '--framerate', '10',
                '--codec', 'mjpeg',
                '--output', temp_file,
                '--nopreview',
                '--flush'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for file to be created
            print("Waiting for stream file...")
            for i in range(10):
                time.sleep(1)
                if os.path.exists(temp_file) and os.path.getsize(temp_file) > 1000:
                    print(f"✅ Stream file ready: {os.path.getsize(temp_file)} bytes")
                    break
                print(f"Waiting... {i+1}/10")
            else:
                # Check what went wrong
                if cam_process.poll() is not None:
                    stdout, stderr = cam_process.communicate()
                    print(f"Camera process failed:")
                    print(f"stdout: {stdout.decode()}")
                    print(f"stderr: {stderr.decode()}")
                raise Exception("Stream file not ready")
            
            # Try to display with FFmpeg
            print("Testing FFmpeg display...")
            ffmpeg_cmd = [
                'ffmpeg',
                '-re', '-f', 'mjpeg', '-i', temp_file,
                '-vf', 'format=yuv420p',  # Convert pixel format for SDL compatibility
                '-f', 'sdl', '-window_title', 'Single Camera Test', 'display'
            ]
            
            print("FFmpeg command:", ' '.join(ffmpeg_cmd))
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for FFmpeg to start
            print("Starting FFmpeg (will run for 10 seconds)...")
            try:
                ffmpeg_process.wait(timeout=10)
                print("FFmpeg completed")
            except subprocess.TimeoutExpired:
                print("FFmpeg timeout - terminating")
                ffmpeg_process.terminate()
                
            # Get FFmpeg output
            stdout, stderr = ffmpeg_process.communicate(timeout=5)
            if stderr:
                stderr_text = stderr.decode()
                print(f"FFmpeg stderr: {stderr_text}")
                
                # Check for specific errors
                if "Unsupported pixel format" in stderr_text:
                    print("❌ FFmpeg SDL has pixel format issues")
                    return False
                elif "Operation not permitted" in stderr_text:
                    print("❌ FFmpeg SDL permission denied")
                    return False
                elif "No such file or directory" in stderr_text and "display" in stderr_text:
                    print("❌ FFmpeg SDL display not available (likely headless system)")
                    return False
                    
            return True
            
        except Exception as e:
            print(f"Simple test failed: {e}")
            return False
        finally:
            # Cleanup
            try:
                cam_process.terminate()
                cam_process.wait(timeout=2)
            except:
                cam_process.kill()
            
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def _try_mjpeg_ffmpeg_method(self, available_cameras: list) -> bool:
        """Try MJPEG streaming - most reliable method"""
        print("� Trying MJPEG streaming method...")
        
        cam_processes = []
        temp_files = []
        
        try:
            # Start MJPEG streams to files
            for i, camera_id in enumerate(available_cameras[:2]):
                temp_file = f"/tmp/camera_{camera_id}_stream.mjpeg"
                temp_files.append(temp_file)
                
                # Remove existing file
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                
                process = subprocess.Popen([
                    'rpicam-vid',
                    '--camera', str(camera_id),
                    '--timeout', '0',
                    '--width', '640',
                    '--height', '480',
                    '--framerate', '15',
                    '--codec', 'mjpeg',
                    '--output', temp_file,
                    '--nopreview',
                    '--flush'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(1)
            
            # Wait for files to be created
            print("Waiting for camera streams to start...")
            time.sleep(3)
            
            # Check if streams are working
            for temp_file in temp_files:
                if not os.path.exists(temp_file) or os.path.getsize(temp_file) < 1000:
                    raise Exception(f"Stream file {temp_file} not ready")
            
            # FFmpeg command for MJPEG with pixel format conversion
            ffmpeg_cmd = [
                'ffmpeg',
                '-re',  # Real-time reading
                '-f', 'mjpeg',
                '-i', temp_files[0],
                '-re',
                '-f', 'mjpeg',
                '-i', temp_files[1],
                '-filter_complex', '[0:v]scale=640:480,format=yuv420p[left];[1:v]scale=640:480,format=yuv420p[right];[left][right]hstack=inputs=2[out]',
                '-map', '[out]',
                '-f', 'sdl',
                '-window_title', 'Dual Camera MJPEG View',
                'display'
            ]
            
            print("🎬 Starting MJPEG FFmpeg viewer...")
            print("Press 'q' in the video window to quit")
            
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stderr=subprocess.PIPE)
            ffmpeg_process.wait()
            
            return True
            
        except Exception as e:
            print(f"MJPEG method failed: {e}")
            return False
        finally:
            # Clean up
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    process.kill()
            
            # Clean up temp files
            for temp_file in temp_files:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                except:
                    pass
    
    def _try_raw_ffmpeg_method(self, available_cameras: list) -> bool:
        """Try raw YUV streaming method"""
        print("🎥 Trying raw YUV method...")
        
        cam_processes = []
        
        try:
            # Start YUV streams
            for i, camera_id in enumerate(available_cameras[:2]):
                port = 5010 + i
                process = subprocess.Popen([
                    'rpicam-vid',
                    '--camera', str(camera_id),
                    '--timeout', '0',
                    '--width', '640',
                    '--height', '480',
                    '--framerate', '10',
                    '--codec', 'yuv420',
                    '--output', f'udp://127.0.0.1:{port}',
                    '--nopreview'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(1)
            
            time.sleep(2)
            
            # FFmpeg command for raw YUV
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'rawvideo',
                '-pixel_format', 'yuv420p',
                '-video_size', '640x480',
                '-framerate', '10',
                '-i', 'udp://127.0.0.1:5010',
                '-f', 'rawvideo',
                '-pixel_format', 'yuv420p',
                '-video_size', '640x480',
                '-framerate', '10',
                '-i', 'udp://127.0.0.1:5011',
                '-filter_complex', '[0:v][1:v]hstack=inputs=2[out]',
                '-map', '[out]',
                '-f', 'sdl',
                'Dual Camera Raw View'
            ]
            
            print("🎬 Starting raw YUV FFmpeg viewer...")
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
            ffmpeg_process.wait()
            
            return True
            
        except Exception as e:
            print(f"Raw YUV method failed: {e}")
            return False
        finally:
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    process.kill()
    
    def _try_file_based_ffmpeg_method(self, available_cameras: list) -> bool:
        """Try file-based streaming with better timing"""
        print("📁 Trying file-based streaming method...")
        
        cam_processes = []
        stream_files = []
        
        try:
            # Create temporary stream files
            for i, camera_id in enumerate(available_cameras[:2]):
                stream_file = f"/tmp/camera_{camera_id}_h264.stream"
                stream_files.append(stream_file)
                
                if os.path.exists(stream_file):
                    os.remove(stream_file)
                
                process = subprocess.Popen([
                    'rpicam-vid',
                    '--camera', str(camera_id),
                    '--timeout', '0',
                    '--width', '640',
                    '--height', '480',
                    '--framerate', '10',
                    '--codec', 'h264',
                    '--profile', 'baseline',  # Use baseline profile for better compatibility
                    '--level', '3.1',
                    '--bitrate', '1000000',
                    '--intra', '30',  # Force keyframes every 30 frames
                    '--output', stream_file,
                    '--nopreview',
                    '--flush'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(1)
            
            print("Waiting for H.264 streams...")
            time.sleep(4)
            
            # FFmpeg with better H.264 handling
            ffmpeg_cmd = [
                'ffmpeg',
                '-analyzeduration', '1000000',
                '-probesize', '1000000',
                '-fflags', '+genpts',
                '-re',
                '-i', stream_files[0],
                '-analyzeduration', '1000000', 
                '-probesize', '1000000',
                '-fflags', '+genpts',
                '-re',
                '-i', stream_files[1],
                '-filter_complex', '[0:v]scale=640:480[left];[1:v]scale=640:480[right];[left][right]hstack=inputs=2[out]',
                '-map', '[out]',
                '-f', 'sdl',
                'Dual Camera File Stream'
            ]
            
            print("🎬 Starting file-based FFmpeg viewer...")
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
            ffmpeg_process.wait()
            
            return True
            
        except Exception as e:
            print(f"File-based method failed: {e}")
            return False
        finally:
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except:
                    process.kill()
            
            for stream_file in stream_files:
                try:
                    if os.path.exists(stream_file):
                        os.remove(stream_file)
                except:
                    pass
    
    def _try_udp_ffmpeg_method(self, available_cameras: list) -> bool:
        """Try original UDP method with better error handling"""
        print("🌐 Trying UDP streaming method (original)...")
        
        cam_processes = []
        
        try:
            # Start camera streams with better H.264 settings
            for i, camera_id in enumerate(available_cameras[:2]):
                port = 5000 + i
                process = subprocess.Popen([
                    'rpicam-vid',
                    '--camera', str(camera_id),
                    '--timeout', '0',
                    '--width', '640',
                    '--height', '480',
                    '--framerate', '15',
                    '--codec', 'h264',
                    '--profile', 'baseline',
                    '--level', '3.1',
                    '--bitrate', '1000000',
                    '--intra', '15',  # More frequent keyframes
                    '--output', f'udp://127.0.0.1:{port}',
                    '--nopreview'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(2)
            
            time.sleep(3)
            
            # FFmpeg with improved H.264 handling
            ffmpeg_cmd = [
                'ffmpeg',
                '-analyzeduration', '2000000',
                '-probesize', '2000000',
                '-fflags', '+genpts+discardcorrupt',
                '-f', 'h264',
                '-i', 'udp://127.0.0.1:5000',
                '-analyzeduration', '2000000',
                '-probesize', '2000000', 
                '-fflags', '+genpts+discardcorrupt',
                '-f', 'h264',
                '-i', 'udp://127.0.0.1:5001',
                '-filter_complex', '[0:v]scale=640:480[left];[1:v]scale=640:480[right];[left][right]hstack=inputs=2[out]',
                '-map', '[out]',
                '-f', 'sdl',
                'Dual Camera UDP View'
            ]
            
            print("🎬 Starting UDP FFmpeg viewer...")
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
            ffmpeg_process.wait()
            
            return True
            
        except Exception as e:
            print(f"UDP method failed: {e}")
            return False
        finally:
            for process in cam_processes:
                try:
                    process.terminate()
                    process.wait(timeout=3)
                except:
                    process.kill()
    
    def _custom_opencv_viewer(self, available_cameras: list):
        """Custom OpenCV-based dual camera viewer"""
        print("🎨 Custom OpenCV dual camera viewer:")
        print("  - Captures frames from both cameras")
        print("  - Shows side-by-side comparison")
        print("  - Press 'q' to quit, 's' to save screenshot")
        print("  - Press 'c' to capture both cameras")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras for custom viewer")
            return
        
        try:
            print("🎬 Starting custom dual camera capture...")
            
            capture_count = 0
            start_time = time.time()
            
            while True:
                frames = []
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Capture from both cameras sequentially
                for camera_id in available_cameras[:2]:
                    frame = self._capture_opencv_frame(camera_id)
                    if frame is not None:
                        # Resize and add labels
                        frame = cv2.resize(frame, (640, 480))
                        cv2.putText(frame, f'Camera {camera_id} - {timestamp}', 
                                  (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        frames.append(frame)
                    else:
                        # Create placeholder frame
                        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.putText(black_frame, f'Camera {camera_id} - No Signal', 
                                  (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                        frames.append(black_frame)
                
                # Combine frames side by side
                if len(frames) >= 2:
                    combined_frame = np.hstack((frames[0], frames[1]))
                    
                    # Add frame counter and timing info
                    cv2.putText(combined_frame, f'Frame: {capture_count} | Runtime: {int(time.time() - start_time)}s', 
                              (10, combined_frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # Display the combined frame
                    cv2.imshow('Custom Dual Camera Viewer - Press Q to quit', combined_frame)
                    
                    capture_count += 1
                
                # Handle key presses
                key = cv2.waitKey(100) & 0xFF  # 100ms delay for ~10fps
                if key == ord('q') or key == 27:  # 'q' or ESC
                    print("Exiting custom camera viewer...")
                    break
                elif key == ord('s'):  # Save screenshot
                    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"dual_camera_capture_{timestamp_file}.jpg"
                    cv2.imwrite(filename, combined_frame)
                    print(f"Screenshot saved: {filename}")
                elif key == ord('c'):  # Capture individual frames
                    timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
                    for i, frame in enumerate(frames):
                        filename = f"camera_{available_cameras[i]}_capture_{timestamp_file}.jpg"
                        cv2.imwrite(filename, frame)
                        print(f"Saved: {filename}")
                
                # Optional: Add a small delay to prevent excessive CPU usage
                time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("\nCustom viewer interrupted by user")
        except Exception as e:
            print(f"❌ Custom viewer error: {e}")
            print("Falling back to fast switching...")
            self._fast_switching_preview(available_cameras)
        finally:
            cv2.destroyAllWindows()
    
    def _capture_opencv_frame(self, camera_id: int):
        """Capture a single frame using rpicam-still for OpenCV processing"""
        try:
            temp_file = f"/tmp/opencv_frame_{camera_id}_{int(time.time())}.jpg"
            
            # Capture frame with rpicam-still
            result = subprocess.run([
                'rpicam-still',
                '--camera', str(camera_id),
                '--timeout', '1',
                '--width', '640',
                '--height', '480',
                '--nopreview',
                '-o', temp_file
            ], capture_output=True, timeout=3)
            
            if result.returncode == 0 and os.path.exists(temp_file):
                # Read the image with OpenCV
                frame = cv2.imread(temp_file)
                # Clean up temp file
                os.remove(temp_file)
                return frame
            
            return None
            
        except Exception as e:
            return None
    
    def capture_dual_with_flash(self, available_cameras: list):
        """Capture from both cameras with synchronized flash"""
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras for dual capture")
            return
        
        # Get flash configuration
        flash_config = self.get_flash_config()
        
        print(f"\n📸 Dual camera flash capture:")
        print(f"  - Cameras: {available_cameras[:2]}")
        print(f"  - Flash: {flash_config.duty_cycle}% intensity, {flash_config.main_flash_ms}ms")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare capture commands for both cameras
        capture_processes = []
        output_files = []
        
        for camera_id in available_cameras[:2]:
            output_file = self.output_dir / f"dual_camera_{camera_id}_{timestamp}.jpg"
            output_files.append(output_file)
            
            # Prepare capture command
            cmd = [
                'rpicam-still',
                '--camera', str(camera_id),
                '--timeout', '100',
                '--width', '4096',
                '--height', '3072',
                '--quality', '95',
                '--immediate',
                '--nopreview',
                '-o', str(output_file)
            ]
            
            capture_processes.append(cmd)
        
        try:
            print("🔄 Starting synchronized capture...")
            
            # Start both cameras simultaneously
            procs = []
            for cmd in capture_processes:
                proc = subprocess.Popen(cmd)
                procs.append(proc)
                time.sleep(0.1)  # Small stagger to avoid resource conflicts
            
            # Trigger flash after a short delay
            time.sleep(0.2)
            flash_success = self.flash_controller.trigger_flash(flash_config)
            
            # Wait for captures to complete
            for proc in procs:
                proc.wait()
            
            # Verify captures
            successful_captures = []
            for i, output_file in enumerate(output_files):
                if output_file.exists() and output_file.stat().st_size > 100000:  # At least 100KB
                    successful_captures.append((available_cameras[i], output_file))
                    print(f"✅ Camera {available_cameras[i]}: {output_file}")
                else:
                    print(f"❌ Camera {available_cameras[i]}: Capture failed")
            
            if successful_captures:
                print(f"\n🎉 Dual capture complete! {len(successful_captures)}/2 cameras successful")
                if flash_success:
                    print("⚡ Flash fired successfully")
                else:
                    print("⚠️ Flash may not have fired properly")
            else:
                print("❌ All captures failed")
                
        except Exception as e:
            print(f"❌ Dual capture error: {e}")
    
    def get_flash_config(self) -> FlashConfig:
        """Get flash configuration from user or use defaults"""
        try:
            print("\n⚡ Flash Configuration:")
            print("Press Enter for defaults")
            
            duty_input = input(f"Flash intensity (10-90%, default 50): ").strip()
            duty_cycle = float(duty_input) if duty_input else 50.0
            duty_cycle = max(10.0, min(90.0, duty_cycle))
            
            duration_input = input(f"Flash duration (ms, default 100): ").strip()
            main_flash_ms = int(duration_input) if duration_input else 100
            main_flash_ms = max(10, min(500, main_flash_ms))
            
            return FlashConfig(
                duty_cycle=duty_cycle,
                main_flash_ms=main_flash_ms
            )
            
        except ValueError:
            print("Using default flash settings")
            return FlashConfig()
    
    def run_main_menu(self):
        """Main interactive menu"""
        print("🎯 Arducam Dual Camera Flash Test System")
        print("=" * 50)
        
        # Check for cameras
        available_cameras = self.check_cameras()
        if not available_cameras:
            print("❌ No cameras found. Exiting.")
            return
        
        # Try to connect flash controller
        if self.flash_controller.connect():
            print("⚡ Flash controller ready")
        else:
            print("⚠️ Flash controller not connected - capture only mode")
        
        while True:
            print("\n📋 Main Menu:")
            print("1. Dual camera preview")
            print("2. Single camera test")
            print("3. Dual camera flash capture")
            print("4. Flash controller test")
            print("5. Camera information")
            print("6. Exit")
            
            try:
                choice = input("\nSelect option (1-6): ").strip()
                
                if choice == '1':
                    self.dual_camera_preview_menu(available_cameras)
                elif choice == '2':
                    self.single_camera_test(available_cameras)
                elif choice == '3':
                    self.capture_dual_with_flash(available_cameras)
                elif choice == '4':
                    self.test_flash_controller()
                elif choice == '5':
                    self.show_camera_info(available_cameras)
                elif choice == '6':
                    print("👋 Exiting...")
                    break
                else:
                    print("❌ Invalid choice. Please select 1-6.")
                    
            except KeyboardInterrupt:
                print("\n👋 Exiting...")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Cleanup
        self.flash_controller.disconnect()
        cv2.destroyAllWindows()
    
    def single_camera_test(self, available_cameras: list):
        """Test individual cameras"""
        print("\n📷 Single Camera Test")
        
        for i, camera_id in enumerate(available_cameras):
            print(f"{i+1}. Camera {camera_id}")
        
        try:
            choice = int(input("Select camera to test: ")) - 1
            if 0 <= choice < len(available_cameras):
                camera_id = available_cameras[choice]
                print(f"Testing Camera {camera_id}...")
                
                subprocess.run([
                    'rpicam-hello',
                    '--camera', str(camera_id),
                    '--timeout', '5000'
                ])
            else:
                print("Invalid camera selection")
        except ValueError:
            print("Invalid input")
    
    def test_flash_controller(self):
        """Test flash controller functionality"""
        if not self.flash_controller.is_connected:
            print("❌ Flash controller not connected")
            return
        
        print("\n⚡ Flash Controller Test")
        config = FlashConfig(duty_cycle=30.0, main_flash_ms=200)
        
        print("Testing flash in 3 seconds...")
        for i in range(3, 0, -1):
            print(f"{i}...")
            time.sleep(1)
        
        success = self.flash_controller.trigger_flash(config)
        if success:
            print("✅ Flash test successful")
        else:
            print("❌ Flash test failed")
    
    def show_camera_info(self, available_cameras: list):
        """Show detailed camera information"""
        print("\n📋 Camera Information:")
        
        for camera_id in available_cameras:
            print(f"\n📷 Camera {camera_id}:")
            try:
                # Get camera info
                result = subprocess.run([
                    'rpicam-hello',
                    '--camera', str(camera_id),
                    '--timeout', '1',
                    '--info-text', f'"Camera {camera_id} Info"'
                ], capture_output=True, text=True)
                
                if result.returncode == 0:
                    print("  ✅ Camera operational")
                else:
                    print("  ❌ Camera error")
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")

def main():
    """Main entry point"""
    try:
        test = ArducamFlashTest()
        test.run_main_menu()
    except KeyboardInterrupt:
        print("\n👋 Program interrupted by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()