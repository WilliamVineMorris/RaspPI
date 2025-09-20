#!/usr/bin/env python3
"""
Raspberry Pi Camera Flash Test with rpicam-still Support
Supports both OpenCV and rpicam-still camera access methods
Optimized for Arducam 64MP cameras with LED flash integration
"""

import cv2
import time
import json
import serial
import subprocess
import os
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any

class RPiCameraManager:
    """Manages Raspberry Pi cameras using both OpenCV and rpicam-still methods"""
    
    def __init__(self):
        self.opencv_cameras = {}
        self.rpicam_available = False
        self.rpicam_cameras = []
        self.detection_complete = False
        
    def detect_cameras(self) -> Dict[str, Any]:
        """Detect available cameras using multiple methods"""
        if self.detection_complete:
            return self._get_detection_summary()
            
        print("🔍 Scanning for available cameras...")
        
        # Test rpicam-still availability
        self._test_rpicam_availability()
        
        # Test OpenCV cameras
        self._test_opencv_cameras()
        
        self.detection_complete = True
        return self._get_detection_summary()
    
    def _test_rpicam_availability(self):
        """Test if rpicam-still can access cameras"""
        try:
            # Check if rpicam-hello can list cameras
            result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                self.rpicam_available = True
                print("✅ rpicam-still system available")
                
                # Parse camera list
                for line in result.stdout.split('\n'):
                    if 'Available cameras' in line or ': ' in line:
                        if ': ' in line and 'Available cameras' not in line:
                            camera_num = line.split(':')[0].strip()
                            if camera_num.isdigit():
                                self.rpicam_cameras.append(int(camera_num))
                
                # If parsing failed, test cameras 0 and 1 directly
                if not self.rpicam_cameras:
                    for cam_id in [0, 1]:
                        if self._test_rpicam_camera(cam_id):
                            self.rpicam_cameras.append(cam_id)
            else:
                print("❌ rpicam-still system not available")
                
        except Exception as e:
            print(f"❌ rpicam-still test failed: {e}")
    
    def _test_rpicam_camera(self, camera_id: int) -> bool:
        """Test a specific camera with rpicam-still"""
        try:
            result = subprocess.run([
                'rpicam-still', '--camera', str(camera_id), 
                '--timeout', '1', '--nopreview', '-o', '/tmp/test_cam.jpg'
            ], capture_output=True, text=True, timeout=10)
            
            success = result.returncode == 0
            # Clean up test file
            if os.path.exists('/tmp/test_cam.jpg'):
                os.remove('/tmp/test_cam.jpg')
            return success
        except:
            return False
    
    def _test_opencv_cameras(self):
        """Test OpenCV camera access"""
        for i in range(2):  # Test cameras 0 and 1
            try:
                # Try different backends
                for backend_name, backend in [("default", None), ("V4L2", cv2.CAP_V4L2)]:
                    if backend is None:
                        cap = cv2.VideoCapture(i)
                    else:
                        cap = cv2.VideoCapture(i, backend)
                    
                    if cap.isOpened():
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            self.opencv_cameras[i] = backend_name
                            print(f"✅ Camera {i}: OpenCV ({backend_name})")
                            cap.release()
                            break
                        
                    cap.release()
                    
                if i not in self.opencv_cameras:
                    print(f"❌ Camera {i}: OpenCV failed")
                    
            except Exception as e:
                print(f"❌ Camera {i}: OpenCV error - {e}")
    
    def _get_detection_summary(self) -> Dict[str, Any]:
        """Get summary of camera detection results"""
        return {
            'rpicam_available': self.rpicam_available,
            'rpicam_cameras': self.rpicam_cameras,
            'opencv_cameras': list(self.opencv_cameras.keys()),
            'opencv_backends': self.opencv_cameras,
            'recommended_method': self._get_recommended_method()
        }
    
    def _get_recommended_method(self) -> str:
        """Determine the best camera access method"""
        if self.rpicam_cameras and len(self.rpicam_cameras) >= 2:
            return "rpicam"
        elif self.opencv_cameras and len(self.opencv_cameras) >= 2:
            return "opencv"
        elif self.rpicam_cameras:
            return "rpicam"
        elif self.opencv_cameras:
            return "opencv"
        else:
            return "none"
    
    def capture_image_rpicam(self, camera_id: int, output_path: str, 
                           width: int = 4608, height: int = 2592) -> bool:
        """Capture image using rpicam-still"""
        try:
            cmd = [
                'rpicam-still',
                '--camera', str(camera_id),
                '--output', output_path,
                '--width', str(width),
                '--height', str(height),
                '--timeout', '2000',
                '--nopreview'
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return result.returncode == 0 and os.path.exists(output_path)
            
        except Exception as e:
            print(f"rpicam capture error: {e}")
            return False
    
    def capture_image_opencv(self, camera_id: int, output_path: str) -> bool:
        """Capture image using OpenCV"""
        try:
            backend = None
            if camera_id in self.opencv_cameras:
                backend_name = self.opencv_cameras[camera_id]
                if backend_name == "V4L2":
                    backend = cv2.CAP_V4L2
            
            if backend is None:
                cap = cv2.VideoCapture(camera_id)
            else:
                cap = cv2.VideoCapture(camera_id, backend)
            
            if not cap.isOpened():
                return False
            
            # Set high resolution for 64MP cameras
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 4608)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 2592)
            
            ret, frame = cap.read()
            cap.release()
            
            if ret and frame is not None:
                cv2.imwrite(output_path, frame)
                return os.path.exists(output_path)
            
            return False
            
        except Exception as e:
            print(f"OpenCV capture error: {e}")
            return False

class PWMFlashController:
    """Controls PWM LED flash via CircuitPython/Arduino"""
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.connected = False
        
    def connect(self) -> bool:
        """Connect to the PWM controller"""
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2)  # Allow connection to stabilize
            
            # Test connection
            self.serial_conn.write(b"STATUS\n")
            response = self.serial_conn.readline().decode().strip()
            
            if "READY" in response or "OK" in response:
                self.connected = True
                print(f"✅ PWM Flash Controller connected on {self.port}")
                return True
            else:
                print(f"❌ PWM Controller not responding correctly: {response}")
                return False
                
        except Exception as e:
            print(f"❌ PWM Flash Controller connection failed: {e}")
            return False
    
    def trigger_flash(self, intensity: int = 80, duration_ms: int = 100) -> bool:
        """Trigger LED flash with specified intensity and duration"""
        if not self.connected:
            print("⚠️ PWM Controller not connected - simulating flash")
            time.sleep(duration_ms / 1000.0)
            return True
            
        try:
            command = f"FLASH {intensity} {duration_ms}\n"
            self.serial_conn.write(command.encode())
            
            # Wait for flash duration
            time.sleep(duration_ms / 1000.0)
            
            # Check response
            response = self.serial_conn.readline().decode().strip()
            return "OK" in response
            
        except Exception as e:
            print(f"Flash trigger error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from PWM controller"""
        if self.serial_conn:
            self.serial_conn.close()
            self.connected = False

class ArducamFlashCapture:
    """Main class for Arducam 64MP camera capture with LED flash"""
    
    def __init__(self):
        self.camera_manager = RPiCameraManager()
        self.flash_controller = PWMFlashController()
        self.detection_results = None
        
    def initialize(self) -> bool:
        """Initialize camera and flash systems"""
        print("=== Arducam 64MP Camera Flash Test ===")
        print("Optimized for high-resolution photography with LED flash")
        print("Note: This script supports both single and dual camera setups\n")
        
        # Detect cameras
        self.detection_results = self.camera_manager.detect_cameras()
        
        # Connect flash controller (optional)
        print("\n🔌 Connecting to PWM Flash Controller...")
        self.flash_controller.connect()
        
        # Check if we have any working cameras
        method = self.detection_results['recommended_method']
        if method == "none":
            print("\n❌ No working cameras found!")
            print("No cameras detected. Please check connections and try again.")
            return False
        
        print(f"\n✅ Camera system ready using {method} method")
        return True
    
    def capture_dual_photos(self, flash_intensity: int = 80, 
                          flash_duration: int = 100) -> List[str]:
        """Capture photos from both cameras with flash"""
        method = self.detection_results['recommended_method']
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        captured_files = []
        
        if method == "rpicam":
            cameras = self.detection_results['rpicam_cameras']
        else:
            cameras = self.detection_results['opencv_cameras']
        
        # Use available cameras (up to 2)
        cameras_to_use = cameras[:2]
        
        print(f"\n📸 Capturing from {len(cameras_to_use)} camera(s) using {method} method...")
        
        for i, camera_id in enumerate(cameras_to_use):
            print(f"\nCapturing from Camera {camera_id}...")
            
            # Trigger flash
            print("💡 Triggering LED flash...")
            self.flash_controller.trigger_flash(flash_intensity, flash_duration)
            
            # Capture image
            filename = f"arducam_64mp_cam{camera_id}_{timestamp}.jpg"
            
            if method == "rpicam":
                success = self.camera_manager.capture_image_rpicam(camera_id, filename)
            else:
                success = self.camera_manager.capture_image_opencv(camera_id, filename)
            
            if success:
                print(f"✅ Saved: {filename}")
                captured_files.append(filename)
            else:
                print(f"❌ Failed to capture from camera {camera_id}")
            
            # Small delay between captures
            if i < len(cameras_to_use) - 1:
                time.sleep(1)
        
        return captured_files
    
    def run_test_sequence(self):
        """Run the complete test sequence"""
        if not self.initialize():
            return
        
        print("\n" + "="*50)
        print("CAMERA DETECTION SUMMARY")
        print("="*50)
        
        results = self.detection_results
        print(f"rpicam-still available: {results['rpicam_available']}")
        print(f"rpicam cameras: {results['rpicam_cameras']}")
        print(f"OpenCV cameras: {results['opencv_cameras']}")
        print(f"Recommended method: {results['recommended_method']}")
        
        print("\n" + "="*50)
        print("STARTING CAPTURE SEQUENCE")
        print("="*50)
        
        try:
            # Test capture sequence
            captured_files = self.capture_dual_photos(
                flash_intensity=80,
                flash_duration=150
            )
            
            print(f"\n✅ Capture complete! {len(captured_files)} files saved:")
            for file in captured_files:
                print(f"  📁 {file}")
                
        except KeyboardInterrupt:
            print("\n⚠️ Test interrupted by user")
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
        finally:
            # Cleanup
            self.flash_controller.disconnect()
            print("\n🔌 Flash controller disconnected")
            print("Test complete!")

def main():
    """Main function"""
    capture_system = ArducamFlashCapture()
    capture_system.run_test_sequence()

if __name__ == "__main__":
    main()