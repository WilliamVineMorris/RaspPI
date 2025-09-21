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
        """FFmpeg-based side-by-side preview (experimental)"""
        print("🎞️ FFmpeg side-by-side preview:")
        print("  - Combines both camera feeds into one window")
        print("  - Experimental - may not work on all systems")
        print("  - Press 'q' in FFmpeg window to quit")
        
        if len(available_cameras) < 2:
            print("❌ Need at least 2 cameras")
            return
        
        try:
            # Method 1: UDP streaming approach
            print("🔄 Trying UDP streaming method...")
            
            cam_processes = []
            
            # Start camera streams
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
                    '--output', f'udp://127.0.0.1:{port}',
                    '--nopreview'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                cam_processes.append(process)
                time.sleep(2)
            
            # Give cameras time to start
            time.sleep(3)
            
            # FFmpeg to combine streams
            ffmpeg_cmd = [
                'ffmpeg',
                '-f', 'h264',
                '-i', 'udp://127.0.0.1:5000',
                '-f', 'h264', 
                '-i', 'udp://127.0.0.1:5001',
                '-filter_complex', '[0:v]scale=640:480[left];[1:v]scale=640:480[right];[left][right]hstack=inputs=2[out]',
                '-map', '[out]',
                '-f', 'sdl',
                'Dual Camera View'
            ]
            
            print("🎬 Starting FFmpeg viewer...")
            ffmpeg_process = subprocess.Popen(ffmpeg_cmd)
            ffmpeg_process.wait()
            
        except Exception as e:
            print(f"❌ FFmpeg method failed: {e}")
            print("💡 Tip: Install FFmpeg or try other preview methods")
        finally:
            # Clean up camera processes
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