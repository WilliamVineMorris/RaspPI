#!/usr/bin/env python3
"""
Dual Camera Capture Test with PWM LED Flash Driver
Tests capturing from two cameras simultaneously with synchronized LED flash control
Uses CircuitPython PWM controller for LED driver timing
"""

import cv2
import numpy as np
import time
import os
import threading
from datetime import datetime
from pathlib import Path
import logging
import json
import serial
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

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
        """Connect to CircuitPython board"""
        try:
            logger.info(f"Connecting to flash controller on {self.port}...")
            
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            
            time.sleep(1)  # Wait for connection
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # Test connection
            if self._send_command({"action": "ping"}).get("status") == "ok":
                self.is_connected = True
                logger.info("Flash controller connected successfully")
                return True
            else:
                logger.error("Failed to communicate with flash controller")
                return False
                
        except Exception as e:
            logger.error(f"Flash controller connection error: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from flash controller"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            self.is_connected = False
    
    def _send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Send command to flash controller"""
        if not self.is_connected or not self.serial_connection:
            return {"status": "error", "message": "Not connected"}
        
        try:
            command_json = json.dumps(command) + '\n'
            self.serial_connection.write(command_json.encode())
            
            response_line = self.serial_connection.readline().decode().strip()
            if response_line:
                return json.loads(response_line)
            else:
                return {"status": "error", "message": "No response"}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def trigger_flash(self, config: FlashConfig) -> bool:
        """Trigger a synchronized camera flash"""
        command = {
            "action": "camera_flash",
            "pins": config.gpio_pins,
            "frequency": config.frequency,
            "duty_cycle": config.duty_cycle,
            "pre_flash_ms": config.pre_flash_ms,
            "main_flash_ms": config.main_flash_ms,
            "flash_delay_ms": config.flash_delay_ms
        }
        
        response = self._send_command(command)
        return response.get("status") == "ok"
    
    def set_flash_intensity(self, intensity: float) -> bool:
        """Set flash intensity (10-90%)"""
        command = {
            "action": "set_intensity",
            "duty_cycle": max(10.0, min(90.0, intensity))
        }
        response = self._send_command(command)
        return response.get("status") == "ok"

class DualCameraFlashCapture:
    def __init__(self, camera1_id=0, camera2_id=1, save_dir="flash_captures", 
                 flash_port="/dev/ttyACM0"):
        """
        Initialize dual camera capture system with LED flash
        
        Args:
            camera1_id: First camera device ID
            camera2_id: Second camera device ID  
            save_dir: Directory to save captured images
            flash_port: Serial port for flash controller
        """
        self.camera1_id = camera1_id
        self.camera2_id = camera2_id
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        
        # Camera objects
        self.camera1 = None
        self.camera2 = None
        
        # Flash controller
        self.flash_controller = PWMFlashController(flash_port)
        self.flash_config = FlashConfig()
        
        # Camera settings
        self.resolution = (1920, 1080)
        self.fps = 30
        
        # Capture state
        self.capture_active = False
        self.preview_active = False
        
    def initialize_cameras(self) -> bool:
        """Initialize both cameras"""
        logger.info("Initializing cameras...")
        
        try:
            # Initialize first camera
            self.camera1 = cv2.VideoCapture(self.camera1_id)
            if not self.camera1.isOpened():
                logger.error(f"Failed to open camera {self.camera1_id}")
                return False
            
            # Initialize second camera
            self.camera2 = cv2.VideoCapture(self.camera2_id)
            if not self.camera2.isOpened():
                logger.error(f"Failed to open camera {self.camera2_id}")
                return False
            
            # Configure camera settings
            for camera in [self.camera1, self.camera2]:
                camera.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                camera.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                camera.set(cv2.CAP_PROP_FPS, self.fps)
                camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
            
            logger.info("Cameras initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            return False
    
    def initialize_flash(self) -> bool:
        """Initialize flash controller"""
        return self.flash_controller.connect()
    
    def capture_flash_photo(self, use_pre_flash=True) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Capture synchronized photo with flash
        
        Args:
            use_pre_flash: Whether to use pre-flash for focus/exposure
            
        Returns:
            (success, camera1_frame, camera2_frame)
        """
        if not self.camera1 or not self.camera2:
            logger.error("Cameras not initialized")
            return False, None, None
        
        if not self.flash_controller.is_connected:
            logger.error("Flash controller not connected")
            return False, None, None
        
        try:
            logger.info("Capturing flash photo...")
            
            # Pre-flash for autofocus/autoexposure if enabled
            if use_pre_flash:
                logger.debug("Triggering pre-flash...")
                pre_config = FlashConfig(
                    duty_cycle=20.0,  # Lower intensity pre-flash
                    main_flash_ms=self.flash_config.pre_flash_ms
                )
                self.flash_controller.trigger_flash(pre_config)
                time.sleep(0.2)  # Allow cameras to adjust
            
            # Prepare for capture - read and discard old frames
            for _ in range(3):
                self.camera1.read()
                self.camera2.read()
            
            # Small delay before main flash
            time.sleep(0.05)
            
            # Trigger main flash in separate thread for timing precision
            flash_thread = threading.Thread(
                target=lambda: self.flash_controller.trigger_flash(self.flash_config)
            )
            flash_thread.start()
            
            # Small delay to sync with flash start
            time.sleep(self.flash_config.flash_delay_ms / 1000.0)
            
            # Capture frames from both cameras simultaneously
            start_time = time.time()
            
            def capture_camera1():
                return self.camera1.read()
            
            def capture_camera2():
                return self.camera2.read()
            
            # Use threads for simultaneous capture
            capture1_thread = threading.Thread(target=capture_camera1)
            capture2_thread = threading.Thread(target=capture_camera2)
            
            capture1_thread.start()
            capture2_thread.start()
            
            # Get results
            ret1, frame1 = self.camera1.read()
            ret2, frame2 = self.camera2.read()
            
            capture1_thread.join()
            capture2_thread.join()
            flash_thread.join()
            
            capture_time = time.time() - start_time
            logger.info(f"Flash capture completed in {capture_time:.3f}s")
            
            if ret1 and ret2:
                return True, frame1, frame2
            else:
                logger.error("Failed to capture from one or both cameras")
                return False, None, None
                
        except Exception as e:
            logger.error(f"Flash capture error: {e}")
            return False, None, None
    
    def save_flash_photos(self, frame1: np.ndarray, frame2: np.ndarray, 
                         filename_prefix: str = "flash_capture") -> bool:
        """Save captured flash photos"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            filename1 = self.save_dir / f"{filename_prefix}_cam1_{timestamp}.jpg"
            filename2 = self.save_dir / f"{filename_prefix}_cam2_{timestamp}.jpg"
            
            # Save with high quality
            cv2.imwrite(str(filename1), frame1, [cv2.IMWRITE_JPEG_QUALITY, 95])
            cv2.imwrite(str(filename2), frame2, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            logger.info(f"Flash photos saved: {filename1.name}, {filename2.name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving flash photos: {e}")
            return False
    
    def start_live_preview(self):
        """Start live preview from both cameras"""
        if not self.camera1 or not self.camera2:
            logger.error("Cameras not initialized")
            return
        
        self.preview_active = True
        logger.info("Starting live preview. Press 'q' to quit, 'f' for flash photo, 's' for settings")
        
        while self.preview_active:
            ret1, frame1 = self.camera1.read()
            ret2, frame2 = self.camera2.read()
            
            if ret1 and ret2:
                # Resize for display
                display_size = (640, 360)
                frame1_small = cv2.resize(frame1, display_size)
                frame2_small = cv2.resize(frame2, display_size)
                
                # Combine frames side by side
                combined = np.hstack((frame1_small, frame2_small))
                
                # Add text overlay
                cv2.putText(combined, "Camera 1", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(combined, "Camera 2", (650, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(combined, f"Flash: {self.flash_config.duty_cycle:.0f}%", 
                           (10, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                cv2.imshow("Dual Camera Flash Preview", combined)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('f'):
                    # Capture flash photo
                    success, f1, f2 = self.capture_flash_photo()
                    if success:
                        self.save_flash_photos(f1, f2)
                        print("📸 Flash photo captured!")
                    else:
                        print("❌ Flash photo failed!")
                elif key == ord('s'):
                    # Show settings
                    self._show_settings_menu()
            
            time.sleep(0.033)  # ~30 FPS preview
        
        cv2.destroyAllWindows()
        self.preview_active = False
    
    def _show_settings_menu(self):
        """Display flash settings menu"""
        print("\n" + "="*50)
        print("FLASH SETTINGS")
        print("="*50)
        print(f"1. Flash Intensity: {self.flash_config.duty_cycle:.0f}%")
        print(f"2. Pre-flash Duration: {self.flash_config.pre_flash_ms}ms")
        print(f"3. Main Flash Duration: {self.flash_config.main_flash_ms}ms")
        print(f"4. Flash Delay: {self.flash_config.flash_delay_ms}ms")
        print(f"5. PWM Frequency: {self.flash_config.frequency}Hz")
        print("6. Test Flash")
        print("0. Return to preview")
        
        try:
            choice = input("Enter choice (0-6): ").strip()
            
            if choice == '1':
                intensity = float(input(f"Enter flash intensity (10-90%): ") or str(self.flash_config.duty_cycle))
                self.flash_config.duty_cycle = max(10.0, min(90.0, intensity))
                self.flash_controller.set_flash_intensity(self.flash_config.duty_cycle)
                print(f"✅ Flash intensity set to {self.flash_config.duty_cycle:.0f}%")
                
            elif choice == '2':
                duration = int(input(f"Enter pre-flash duration (ms): ") or str(self.flash_config.pre_flash_ms))
                self.flash_config.pre_flash_ms = max(10, min(500, duration))
                print(f"✅ Pre-flash duration set to {self.flash_config.pre_flash_ms}ms")
                
            elif choice == '3':
                duration = int(input(f"Enter main flash duration (ms): ") or str(self.flash_config.main_flash_ms))
                self.flash_config.main_flash_ms = max(50, min(1000, duration))
                print(f"✅ Main flash duration set to {self.flash_config.main_flash_ms}ms")
                
            elif choice == '4':
                delay = int(input(f"Enter flash delay (ms): ") or str(self.flash_config.flash_delay_ms))
                self.flash_config.flash_delay_ms = max(0, min(100, delay))
                print(f"✅ Flash delay set to {self.flash_config.flash_delay_ms}ms")
                
            elif choice == '5':
                freq = int(input(f"Enter PWM frequency (Hz): ") or str(self.flash_config.frequency))
                self.flash_config.frequency = max(100, min(1000, freq))
                print(f"✅ PWM frequency set to {self.flash_config.frequency}Hz")
                
            elif choice == '6':
                print("Testing flash...")
                if self.flash_controller.trigger_flash(self.flash_config):
                    print("✅ Flash test successful!")
                else:
                    print("❌ Flash test failed!")
                    
        except ValueError:
            print("❌ Invalid input!")
        except KeyboardInterrupt:
            pass
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        
        self.preview_active = False
        
        if self.camera1:
            self.camera1.release()
        if self.camera2:
            self.camera2.release()
        
        self.flash_controller.disconnect()
        cv2.destroyAllWindows()

def get_circuitpython_flash_code() -> str:
    """Generate CircuitPython code for camera flash control"""
    return '''
import json
import time
import board
import pwmio
import asyncio
from microcontroller import pin

# PWM objects for flash control
flash_pwm = {}

def setup_flash_pwm(pin_num, frequency):
    """Setup PWM for LED flash control"""
    try:
        pin_obj = getattr(board, f"GP{pin_num}")
        pwm = pwmio.PWMOut(pin_obj, frequency=frequency, duty_cycle=0)
        flash_pwm[pin_num] = pwm
        return True
    except Exception as e:
        print(f"Error setting up flash PWM on pin {pin_num}: {e}")
        return False

def set_flash_intensity(pin_num, duty_percent):
    """Set flash intensity as percentage"""
    if pin_num in flash_pwm:
        duty_value = int((duty_percent / 100.0) * 65535)
        flash_pwm[pin_num].duty_cycle = duty_value
        return True
    return False

def stop_flash(pin_num):
    """Stop flash PWM"""
    if pin_num in flash_pwm:
        flash_pwm[pin_num].duty_cycle = 0
        return True
    return False

async def camera_flash_sequence(pins, frequency, duty_cycle, pre_flash_ms, main_flash_ms, flash_delay_ms):
    """Execute camera flash sequence"""
    try:
        # Setup PWM for all pins
        for pin_num in pins:
            if not setup_flash_pwm(pin_num, frequency):
                return False
        
        # Wait for flash delay
        if flash_delay_ms > 0:
            await asyncio.sleep(flash_delay_ms / 1000.0)
        
        # Main flash
        for pin_num in pins:
            set_flash_intensity(pin_num, duty_cycle)
        
        # Flash duration
        await asyncio.sleep(main_flash_ms / 1000.0)
        
        # Turn off flash
        for pin_num in pins:
            stop_flash(pin_num)
        
        return True
        
    except Exception as e:
        print(f"Flash sequence error: {e}")
        return False

def process_flash_command(command):
    """Process camera flash commands"""
    try:
        action = command.get("action")
        
        if action == "ping":
            return {"status": "ok", "message": "pong"}
        
        elif action == "camera_flash":
            pins = command.get("pins", [4, 5])
            frequency = command.get("frequency", 300)
            duty_cycle = command.get("duty_cycle", 50.0)
            pre_flash_ms = command.get("pre_flash_ms", 50)
            main_flash_ms = command.get("main_flash_ms", 100)
            flash_delay_ms = command.get("flash_delay_ms", 10)
            
            # Run flash sequence
            success = asyncio.run(camera_flash_sequence(
                pins, frequency, duty_cycle, pre_flash_ms, main_flash_ms, flash_delay_ms
            ))
            
            if success:
                return {"status": "ok", "message": f"Camera flash executed on pins {pins}"}
            else:
                return {"status": "error", "message": "Flash sequence failed"}
        
        elif action == "set_intensity":
            duty_cycle = command.get("duty_cycle", 50.0)
            pins = command.get("pins", [4, 5])
            
            for pin_num in pins:
                if pin_num in flash_pwm:
                    set_flash_intensity(pin_num, duty_cycle)
            
            return {"status": "ok", "message": f"Flash intensity set to {duty_cycle}%"}
        
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"status": "error", "message": f"Command error: {str(e)}"}

# Main flash controller loop
print("Camera Flash Controller Ready")
print("Waiting for flash commands...")

while True:
    try:
        line = input().strip()
        if line:
            command = json.loads(line)
            response = process_flash_command(command)
            print(json.dumps(response))
    
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "message": "Invalid JSON"}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Error: {str(e)}"}))
'''

def main():
    """Main test function"""
    print("=== Dual Camera Flash Capture Test ===")
    print()
    
    # Get configuration from user
    flash_port = input("Enter flash controller serial port (e.g., /dev/ttyACM0 or COM3): ").strip()
    if not flash_port:
        flash_port = "/dev/ttyACM0"
    
    camera1_id = int(input("Enter Camera 1 device ID (default 0): ") or "0")
    camera2_id = int(input("Enter Camera 2 device ID (default 1): ") or "1")
    
    # Create capture system
    capture_system = DualCameraFlashCapture(
        camera1_id=camera1_id,
        camera2_id=camera2_id,
        flash_port=flash_port
    )
    
    try:
        # Initialize systems
        print("\nInitializing cameras...")
        if not capture_system.initialize_cameras():
            print("❌ Failed to initialize cameras")
            return
        
        print("Initializing flash controller...")
        if not capture_system.initialize_flash():
            print("❌ Failed to initialize flash controller")
            print("Make sure CircuitPython board is connected and programmed")
            return
        
        print("✅ All systems initialized successfully!")
        
        # Main menu
        while True:
            print("\n" + "="*50)
            print("DUAL CAMERA FLASH TEST")
            print("="*50)
            print("1. Live preview (press 'f' for flash photo)")
            print("2. Single flash capture")
            print("3. Burst flash capture")
            print("4. Flash settings")
            print("5. Generate CircuitPython flash code")
            print("6. Exit")
            
            choice = input("Enter choice (1-6): ").strip()
            
            if choice == '1':
                capture_system.start_live_preview()
                
            elif choice == '2':
                print("Capturing single flash photo...")
                success, frame1, frame2 = capture_system.capture_flash_photo()
                if success:
                    capture_system.save_flash_photos(frame1, frame2)
                    print("✅ Flash photo captured and saved!")
                else:
                    print("❌ Flash capture failed!")
                    
            elif choice == '3':
                try:
                    count = int(input("Enter number of photos to capture: ") or "5")
                    interval = float(input("Enter interval between captures (seconds): ") or "2.0")
                    
                    print(f"Capturing {count} flash photos with {interval}s interval...")
                    for i in range(count):
                        print(f"Capture {i+1}/{count}...")
                        success, frame1, frame2 = capture_system.capture_flash_photo()
                        if success:
                            capture_system.save_flash_photos(frame1, frame2, f"burst_{i+1:03d}")
                            print(f"✅ Photo {i+1} captured")
                        else:
                            print(f"❌ Photo {i+1} failed")
                        
                        if i < count - 1:  # Don't wait after last photo
                            time.sleep(interval)
                    
                    print(f"✅ Burst capture completed: {count} photos")
                    
                except ValueError:
                    print("❌ Invalid input!")
                    
            elif choice == '4':
                capture_system._show_settings_menu()
                
            elif choice == '5':
                print("\n" + "="*60)
                print("CircuitPython Camera Flash Code (save as code.py):")
                print("="*60)
                print(get_circuitpython_flash_code())
                print("="*60)
                
            elif choice == '6':
                break
                
            else:
                print("Invalid choice. Please try again.")
    
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        capture_system.cleanup()

if __name__ == "__main__":
    main()