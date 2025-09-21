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
        """FFmpeg-based side-by-side preview with multiple fallback methods"""
        print("🎞️ FFmpeg side-by-side preview:")
        print("  - Combines both camera feeds into one window")
        print("  - Multiple methods will be tried")
        print("  - Press 'q' in FFmpeg window to quit")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras")
            return
        
        # First, let's test if we can create simple camera streams
        print("🔍 Testing basic camera functionality...")
        for camera_id in available_cameras[:2]:
            try:
                test_result = subprocess.run([
                    'rpicam-vid', '--camera', str(camera_id), '--timeout', '1000', '--nopreview',
                    '--codec', 'mjpeg', '--output', f'/tmp/test_cam_{camera_id}.mjpeg'
                ], capture_output=True, timeout=10)
                
                if test_result.returncode == 0:
                    print(f"✅ Camera {camera_id} test successful")
                    # Clean up test file
                    test_file = f'/tmp/test_cam_{camera_id}.mjpeg'
                    if os.path.exists(test_file):
                        os.remove(test_file)
                else:
                    print(f"❌ Camera {camera_id} test failed: {test_result.stderr.decode()}")
                    
            except Exception as e:
                print(f"❌ Camera {camera_id} test error: {e}")
        
        # Try methods in order of reliability
        methods = [
            ("Web Stream Method", self._try_web_stream_method),
            ("Simple MJPEG Test", self._try_simple_mjpeg_test),
            ("MJPEG Streaming", self._try_mjpeg_ffmpeg_method),
            ("Raw YUV Method", self._try_raw_ffmpeg_method),
            ("File-based H.264", self._try_file_based_ffmpeg_method),
            ("UDP Streaming", self._try_udp_ffmpeg_method)
        ]
        
        for i, (name, method) in enumerate(methods, 1):
            try:
                print(f"\n🔄 Trying method {i}/{len(methods)}: {name}")
                if method(available_cameras):
                    print(f"✅ {name} completed successfully")
                    return  # Success, exit
                else:
                    print(f"❌ {name} failed")
            except Exception as e:
                print(f"❌ {name} error: {e}")
                continue
        
        print("\n❌ All FFmpeg methods failed")
        print("💡 If FFmpeg issues persist, here are alternatives:")
        print("  1. Option 4 (Custom OpenCV viewer) - Most reliable")
        print("  2. Option 2 (Side-by-side windows) - Uses native rpicam-hello") 
        print("  3. Option 1 (Fast switching) - Simple and reliable")
        
        # Offer to try the reliable custom viewer
        try:
            choice = input("\nWould you like to try the Custom OpenCV viewer instead? (y/n): ").strip().lower()
            if choice in ['y', 'yes']:
                print("\n🎨 Launching Custom OpenCV viewer...")
                self._custom_opencv_viewer(available_cameras)
        except:
            pass
    
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