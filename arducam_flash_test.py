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

class ArducamFlashCapture:
    """Dual camera capture system optimized for Arducam 64MP cameras with LED flash"""
    
    def __init__(self, camera1_id=0, camera2_id=1, save_dir="arducam_captures", 
                 flash_port="/dev/ttyACM0"):
        """
        Initialize dual Arducam capture system with LED flash
        
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
        
        # Arducam 64MP optimized resolutions
        self.resolutions = {
            "preview": (1920, 1080),      # Full HD for live preview
            "photo": (9152, 6944),        # Full 64MP resolution (9152x6944)
            "high": (4576, 3472),         # Quarter resolution for speed
            "medium": (3840, 2160),       # 4K resolution
            "fast": (2592, 1944),         # Fast capture mode
        }
        self.current_resolution = "high"  # Default balanced mode
        
        # Camera settings
        self.preview_fps = 15      # Lower FPS for high-res preview
        self.photo_fps = 3         # Very low FPS for 64MP capture
        self.buffer_size = 3       # Larger buffer for high-res
        
        # Capture state
        self.preview_active = False
        
    def initialize_cameras(self) -> bool:
        """Initialize Arducam cameras with smart detection"""
        logger.info("Detecting and initializing Arducam cameras...")
        
        try:
            # Try to initialize first camera
            self.camera1 = cv2.VideoCapture(self.camera1_id)
            camera1_ok = self.camera1.isOpened()
            
            if not camera1_ok:
                logger.error(f"Failed to open camera {self.camera1_id}")
                return False
            
            # Try to initialize second camera
            self.camera2 = cv2.VideoCapture(self.camera2_id)
            camera2_ok = self.camera2.isOpened()
            
            if not camera2_ok:
                logger.warning(f"Camera {self.camera2_id} not available - running in single camera mode")
                self.camera2.release()
                self.camera2 = None
            
            # Configure available cameras
            cameras_to_configure = [self.camera1]
            if self.camera2:
                cameras_to_configure.append(self.camera2)
            
            # Arducam 64MP specific optimizations
            for camera in cameras_to_configure:
                # Use MJPEG codec for better performance
                try:
                    camera.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*'MJPG'))
                except:
                    logger.warning("Could not set MJPEG codec")
                
                # Optimize buffer and settings
                camera.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
                
                # Try to enable autofocus for Arducam
                try:
                    camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
                    camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)  # Partial auto exposure
                except:
                    logger.warning("Could not set autofocus/exposure settings")
            
            # Set initial resolution to preview mode
            self._set_camera_mode("preview")
            
            # Verify settings
            w, h = self.camera1.get(cv2.CAP_PROP_FRAME_WIDTH), self.camera1.get(cv2.CAP_PROP_FRAME_HEIGHT)
            fps = self.camera1.get(cv2.CAP_PROP_FPS)
            
            camera_count = len(cameras_to_configure)
            logger.info(f"Arducam cameras initialized: {camera_count} camera(s) @ {w}x{h} @ {fps}fps")
            
            if not self.camera2:
                logger.info("Note: Running in single camera mode - only Camera 1 will be used")
            
            return True
            
        except Exception as e:
            logger.error(f"Camera initialization error: {e}")
            return False
    
    def _set_camera_mode(self, mode: str):
        """Set camera resolution based on mode"""
        if mode not in self.resolutions:
            logger.warning(f"Unknown mode: {mode}, using 'high'")
            mode = "high"
        
        resolution = self.resolutions[mode]
        fps = self.preview_fps if mode == "preview" else self.photo_fps
        
        # Configure camera 1
        if self.camera1 is not None:
            self.camera1.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.camera1.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
            self.camera1.set(cv2.CAP_PROP_FPS, fps)
        
        # Configure camera 2 if available
        if self.camera2 is not None:
            self.camera2.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
            self.camera2.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])
            self.camera2.set(cv2.CAP_PROP_FPS, fps)
        
        self.current_resolution = mode
        camera_count = "dual" if self.camera2 else "single"
        logger.info(f"Camera mode ({camera_count}): {mode} ({resolution[0]}x{resolution[1]} @ {fps}fps)")
    
    def set_resolution_mode(self, mode: str) -> bool:
        """Change camera resolution mode"""
        if mode in self.resolutions:
            self._set_camera_mode(mode)
            return True
        return False
    
    def initialize_flash(self) -> bool:
        """Initialize flash controller"""
        return self.flash_controller.connect()
    
    def capture_flash_photo_rpicam(self, camera_id: int, use_pre_flash=True, high_resolution=False) -> Tuple[bool, str]:
        """
        Capture photo using rpicam-still with flash (for Pi cameras)
        
        Args:
            camera_id: Camera index (0 or 1)
            use_pre_flash: Whether to use pre-flash for focus/exposure
            high_resolution: Whether to capture at full 64MP resolution
            
        Returns:
            (success, filename) - returns filename if successful
        """
        import subprocess
        
        if not self.flash_controller.is_connected:
            logger.warning("Flash controller not connected - proceeding without flash")
        
        try:
            # Set resolution based on mode
            if high_resolution:
                width, height = 9152, 6944  # Full 64MP
                logger.info("Capturing at full 64MP resolution...")
            else:
                width, height = 4608, 2592  # Half resolution for faster capture
                logger.info("Capturing at high resolution...")
            
            # Pre-flash for autofocus/autoexposure
            if use_pre_flash and self.flash_controller.is_connected:
                logger.debug("Triggering pre-flash for AF/AE...")
                pre_config = FlashConfig(
                    duty_cycle=20.0,  # Lower intensity pre-flash
                    main_flash_ms=self.flash_config.pre_flash_ms
                )
                self.flash_controller.trigger_flash(pre_config)
                time.sleep(0.5)  # Allow time for Arducam AF/AE
            
            # Generate filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = self.save_dir / f"arducam_64mp_cam{camera_id}_{timestamp}.jpg"
            
            # Trigger main flash in separate thread
            flash_thread = None
            if self.flash_controller.is_connected:
                flash_thread = threading.Thread(
                    target=lambda: self.flash_controller.trigger_flash(self.flash_config)
                )
                flash_thread.start()
                # Small delay for flash timing
                time.sleep(self.flash_config.flash_delay_ms / 1000.0)
            
            # Capture with rpicam-still
            cmd = [
                'rpicam-still',
                '--camera', str(camera_id),
                '--output', str(filename),
                '--width', str(width),
                '--height', str(height),
                '--timeout', '3000',  # 3 second timeout
                '--nopreview',
                '--immediate',  # Capture immediately
                '--quality', '98'  # High quality JPEG
            ]
            
            start_time = time.time()
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            capture_time = time.time() - start_time
            
            # Wait for flash to complete
            if flash_thread:
                flash_thread.join()
            
            if result.returncode == 0 and filename.exists():
                size_mb = filename.stat().st_size / (1024*1024)
                logger.info(f"Capture completed in {capture_time:.3f}s - {filename.name} ({size_mb:.1f}MB)")
                return True, str(filename)
            else:
                logger.error(f"rpicam-still failed: {result.stderr}")
                return False, ""
                
        except Exception as e:
            logger.error(f"Flash capture error: {e}")
            return False, ""

    def capture_flash_photo(self, use_pre_flash=True, high_resolution=False) -> Tuple[bool, Optional[np.ndarray], Optional[np.ndarray]]:
        """
        Capture synchronized photo with flash optimized for Arducam 64MP
        
        Args:
            use_pre_flash: Whether to use pre-flash for focus/exposure
            high_resolution: Whether to capture at full 64MP resolution
            
        Returns:
            (success, camera1_frame, camera2_frame) - camera2_frame will be None in single camera mode
        """
        if not self.camera1:
            logger.error("Camera 1 not initialized")
            return False, None, None
        
        if not self.flash_controller.is_connected:
            logger.error("Flash controller not connected")
            return False, None, None
        
        try:
            # Switch to photo resolution if requested
            original_mode = self.current_resolution
            if high_resolution:
                logger.info("Switching to full 64MP resolution...")
                self.set_resolution_mode("photo")
                time.sleep(2)  # Allow cameras to adjust to 64MP mode
            
            # Pre-flash for autofocus/autoexposure
            if use_pre_flash:
                logger.debug("Triggering pre-flash for AF/AE...")
                pre_config = FlashConfig(
                    duty_cycle=20.0,  # Lower intensity pre-flash
                    main_flash_ms=self.flash_config.pre_flash_ms
                )
                self.flash_controller.trigger_flash(pre_config)
                time.sleep(0.5)  # Allow more time for Arducam AF/AE
            
            # Prepare for capture - clear buffers
            for _ in range(5):  # More buffer clears for high-res
                if self.camera1:
                    self.camera1.read()
                if self.camera2:
                    self.camera2.read()
            
            camera_mode = "dual" if self.camera2 else "single"
            logger.info(f"Capturing flash photo at {self.current_resolution} resolution ({camera_mode} camera)")
            
            # Trigger main flash
            flash_thread = threading.Thread(
                target=lambda: self.flash_controller.trigger_flash(self.flash_config)
            )
            flash_thread.start()
            
            # Sync timing for flash
            time.sleep(self.flash_config.flash_delay_ms / 1000.0)
            
            # Capture with timing
            start_time = time.time()
            
            # Capture from camera 1 (always available)
            ret1, frame1 = self.camera1.read()
            
            # Capture from camera 2 if available
            if self.camera2:
                ret2, frame2 = self.camera2.read()
            else:
                ret2, frame2 = True, None  # Single camera mode
            
            flash_thread.join()
            capture_time = time.time() - start_time
            
            # Switch back to original resolution
            if high_resolution and original_mode != "photo":
                self.set_resolution_mode(original_mode)
            
            if ret1 and ret2 and frame1 is not None:
                logger.info(f"64MP flash capture completed in {capture_time:.3f}s ({camera_mode} camera)")
                return True, frame1, frame2
            else:
                logger.error("Failed to capture from camera(s)")
                return False, None, None
                
        except Exception as e:
            logger.error(f"Flash capture error: {e}")
            return False, None, None
    
    def save_flash_photos(self, frame1: np.ndarray, frame2: Optional[np.ndarray], 
                         filename_prefix: str = "arducam_flash") -> bool:
        """Save captured flash photos with high quality"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            
            # Always save camera 1
            filename1 = self.save_dir / f"{filename_prefix}_cam1_{timestamp}.jpg"
            cv2.imwrite(str(filename1), frame1, [cv2.IMWRITE_JPEG_QUALITY, 98])
            size1 = filename1.stat().st_size / (1024*1024)  # MB
            
            saved_files = [f"{filename1.name} ({size1:.1f}MB)"]
            
            # Save camera 2 if available
            if frame2 is not None:
                filename2 = self.save_dir / f"{filename_prefix}_cam2_{timestamp}.jpg"
                cv2.imwrite(str(filename2), frame2, [cv2.IMWRITE_JPEG_QUALITY, 98])
                size2 = filename2.stat().st_size / (1024*1024)  # MB
                saved_files.append(f"{filename2.name} ({size2:.1f}MB)")
            
            logger.info(f"Photos saved: {', '.join(saved_files)}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving photos: {e}")
            return False
    
    def start_live_preview(self):
        """Start live preview optimized for Arducam"""
        if not self.camera1:
            logger.error("Camera 1 not initialized")
            return
        
        # Ensure preview mode
        self.set_resolution_mode("preview")
        
        self.preview_active = True
        camera_mode = "dual" if self.camera2 else "single"
        logger.info(f"Arducam live preview started ({camera_mode} camera)")
        logger.info("Controls: 'q'=quit, 'f'=flash photo, 'F'=64MP photo, 'r'=resolution, 's'=settings")
        
        while self.preview_active:
            ret1, frame1 = self.camera1.read()
            
            # Get frame2 if camera2 is available
            if self.camera2:
                ret2, frame2 = self.camera2.read()
            else:
                ret2, frame2 = True, None
            
            if ret1 and ret2:
                # Create display
                display_size = (640, 360)
                frame1_small = cv2.resize(frame1, display_size)
                
                if frame2 is not None:
                    # Dual camera display
                    frame2_small = cv2.resize(frame2, display_size)
                    combined = np.hstack((frame1_small, frame2_small))
                    
                    # Add overlay information
                    cv2.putText(combined, "Arducam Camera 1", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(combined, "Arducam Camera 2", (650, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    # Single camera display
                    combined = frame1_small
                    cv2.putText(combined, "Arducam Camera (Single Mode)", (10, 30), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Common overlay
                cv2.putText(combined, f"Flash: {self.flash_config.duty_cycle:.0f}%", 
                           (10, 340), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                cv2.putText(combined, f"Mode: {self.current_resolution}", 
                           (10, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                window_title = f"Arducam 64MP Preview ({camera_mode.title()} Camera)"
                cv2.imshow(window_title, combined)
                
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('f'):
                    # Standard flash photo
                    success, f1, f2 = self.capture_flash_photo(high_resolution=False)
                    if success and f1 is not None:
                        self.save_flash_photos(f1, f2)
                        print("📸 Flash photo captured!")
                    else:
                        print("❌ Flash photo failed!")
                elif key == ord('F'):
                    # Full 64MP flash photo
                    print("📸 Capturing full 64MP flash photo (this may take a moment)...")
                    success, f1, f2 = self.capture_flash_photo(high_resolution=True)
                    if success and f1 is not None:
                        self.save_flash_photos(f1, f2, "64MP_flash")
                        print("✅ 64MP flash photo captured!")
                    else:
                        print("❌ 64MP flash photo failed!")
                elif key == ord('r'):
                    self._show_resolution_menu()
                elif key == ord('s'):
                    self._show_settings_menu()
            
            time.sleep(0.067)  # ~15 FPS preview
        
        cv2.destroyAllWindows()
        self.preview_active = False
    
    def _show_resolution_menu(self):
        """Display resolution settings menu"""
        print("\n" + "="*50)
        print("ARDUCAM RESOLUTION MODES")
        print("="*50)
        for i, (mode, resolution) in enumerate(self.resolutions.items(), 1):
            marker = "★" if mode == self.current_resolution else " "
            megapixels = (resolution[0] * resolution[1]) / 1000000
            print(f"{marker} {i}. {mode.title()}: {resolution[0]}x{resolution[1]} ({megapixels:.1f}MP)")
        print("0. Return to preview")
        
        try:
            choice = input("Enter choice: ").strip()
            if choice == '0':
                return
            
            mode_list = list(self.resolutions.keys())
            if choice.isdigit() and 1 <= int(choice) <= len(mode_list):
                selected_mode = mode_list[int(choice) - 1]
                if self.set_resolution_mode(selected_mode):
                    print(f"✅ Resolution changed to {selected_mode}")
                else:
                    print("❌ Failed to change resolution")
            else:
                print("❌ Invalid choice!")
                
        except (ValueError, KeyboardInterrupt):
            pass
    
    def _show_settings_menu(self):
        """Display flash settings menu"""
        print("\n" + "="*50)
        print("ARDUCAM FLASH SETTINGS")
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
        logger.info("Cleaning up Arducam resources...")
        
        self.preview_active = False
        
        if self.camera1:
            self.camera1.release()
        if self.camera2:
            self.camera2.release()
        
        self.flash_controller.disconnect()
        cv2.destroyAllWindows()

def get_circuitpython_flash_code() -> str:
    """Generate CircuitPython code for Arducam camera flash control"""
    return '''
import json
import time
import board
import pwmio
import asyncio

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

async def camera_flash_sequence(pins, frequency, duty_cycle, pre_flash_ms, main_flash_ms, flash_delay_ms):
    """Execute optimized camera flash sequence for Arducam 64MP"""
    try:
        # Setup PWM for all pins
        for pin_num in pins:
            if not setup_flash_pwm(pin_num, frequency):
                return False
        
        # Flash delay for camera sync
        if flash_delay_ms > 0:
            await asyncio.sleep(flash_delay_ms / 1000.0)
        
        # Main flash with precise timing
        for pin_num in pins:
            set_flash_intensity(pin_num, duty_cycle)
        
        # Flash duration
        await asyncio.sleep(main_flash_ms / 1000.0)
        
        # Turn off flash
        for pin_num in pins:
            set_flash_intensity(pin_num, 0)
        
        return True
        
    except Exception as e:
        print(f"Flash sequence error: {e}")
        return False

def process_flash_command(command):
    """Process Arducam camera flash commands"""
    try:
        action = command.get("action")
        
        if action == "ping":
            return {"status": "ok", "message": "Arducam flash controller ready"}
        
        elif action == "camera_flash":
            pins = command.get("pins", [4, 5])
            frequency = command.get("frequency", 300)
            duty_cycle = command.get("duty_cycle", 50.0)
            pre_flash_ms = command.get("pre_flash_ms", 50)
            main_flash_ms = command.get("main_flash_ms", 100)
            flash_delay_ms = command.get("flash_delay_ms", 10)
            
            # Execute flash sequence
            success = asyncio.run(camera_flash_sequence(
                pins, frequency, duty_cycle, pre_flash_ms, main_flash_ms, flash_delay_ms
            ))
            
            if success:
                return {"status": "ok", "message": f"Arducam flash executed on pins {pins}"}
            else:
                return {"status": "error", "message": "Flash sequence failed"}
        
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"status": "error", "message": f"Command error: {str(e)}"}

# Arducam Flash Controller Main Loop
print("Arducam 64MP Flash Controller Ready")
print("Optimized for high-resolution photography")

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

def detect_available_cameras(max_cameras=2):
    """Detect available camera devices using rpicam-still"""
    import subprocess
    available_cameras = []
    
    print("\n🔍 Scanning for available cameras...")
    
    # Test rpicam-still with cameras 0 and 1 (most common setup)
    for i in range(max_cameras):
        try:
            print(f"  Testing Camera {i} with rpicam-still...")
            result = subprocess.run([
                'rpicam-still', '--camera', str(i), 
                '--timeout', '1', '--nopreview', '-o', '/tmp/test_cam.jpg'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(f"  ✅ Camera {i}: Working with rpicam-still")
                available_cameras.append(i)
                # Clean up test file
                if os.path.exists('/tmp/test_cam.jpg'):
                    os.remove('/tmp/test_cam.jpg')
            else:
                print(f"  ❌ Camera {i}: Failed - {result.stderr.strip()}")
                
        except Exception as e:
            print(f"  ❌ Camera {i}: Error - {e}")
    
    if available_cameras:
        print(f"\n📋 Found {len(available_cameras)} working camera(s): {available_cameras}")
        print("Note: Using rpicam-still for camera access (recommended for Pi cameras)")
    else:
        print("\n❌ No working cameras found!")
        print("Troubleshooting:")
        print("1. Check camera ribbon cable connections")
        print("2. Ensure cameras are enabled: sudo raspi-config")
        print("3. Try: rpicam-still --camera 0 -o test.jpg")
    
    return available_cameras

def main():
    """Main test function for Arducam 64MP dual camera flash system"""
    print("=== Arducam 64MP Camera Flash Test ===")
    print("Optimized for high-resolution photography with LED flash")
    print("Note: This script supports both single and dual camera setups")
    print()
    
    # First, scan for available cameras
    available_cameras = detect_available_cameras()
    
    if not available_cameras:
        print("No cameras detected. Please check connections and try again.")
        return
    
    # Configuration
    flash_port = input("Enter flash controller serial port (default /dev/ttyACM0): ").strip()
    if not flash_port:
        flash_port = "/dev/ttyACM0"
    
    # Create simplified capture system (no OpenCV camera initialization needed)
    capture_system = ArducamFlashCapture(
        camera1_id=0,  # We'll use camera IDs directly in rpicam calls
        camera2_id=1,
        flash_port=flash_port
    )
    
    try:
        # Initialize only flash controller
        print("Initializing flash controller...")
        flash_available = capture_system.initialize_flash()
        if not flash_available:
            print("❌ Failed to initialize flash controller")
            print("Make sure CircuitPython board is connected and programmed")
            
            # Ask if user wants to continue without flash
            continue_without_flash = input("Continue without flash controller? (y/N): ").strip().lower() == 'y'
            if not continue_without_flash:
                return
        
        camera_count = "dual" if len(available_cameras) >= 2 else "single"
        print(f"✅ Arducam 64MP system ready ({camera_count} camera) using rpicam-still!")
        print(f"Available cameras: {available_cameras}")
        
        # Main menu
        while True:
            print("\n" + "="*60)
            print(f"ARDUCAM 64MP CAMERA FLASH TEST ({camera_count.upper()} CAMERA)")
            print("="*60)
            print("1. Live preview (f=flash, F=64MP flash, r=resolution)")
            print("2. Standard flash capture")
            print("3. Full 64MP flash capture")
            print("4. Burst capture mode")
            print("5. Resolution settings")
            print("6. Flash settings")
            print("7. Generate CircuitPython flash code")
            print("8. Exit")
            
            choice = input("Enter choice (1-8): ").strip()
            
            if choice == '1':
                capture_system.start_live_preview()
                
            elif choice == '2':
                print("Capturing standard resolution flash photo...")
                # Capture from available cameras using rpicam-still
                captured_files = []
                for camera_id in available_cameras:
                    success, filename = capture_system.capture_flash_photo_rpicam(camera_id, high_resolution=False)
                    if success:
                        captured_files.append(filename)
                        print(f"✅ Camera {camera_id} captured: {os.path.basename(filename)}")
                    else:
                        print(f"❌ Camera {camera_id} capture failed!")
                        
                if captured_files:
                    print(f"✅ Flash photo captured! {len(captured_files)} file(s) saved.")
                else:
                    print("❌ All captures failed!")
                    
            elif choice == '3':
                print("Capturing full 64MP flash photo (this may take 10+ seconds)...")
                # Capture from available cameras using rpicam-still
                captured_files = []
                for camera_id in available_cameras:
                    success, filename = capture_system.capture_flash_photo_rpicam(camera_id, high_resolution=True)
                    if success:
                        captured_files.append(filename)
                        print(f"✅ Camera {camera_id} captured: {os.path.basename(filename)}")
                    else:
                        print(f"❌ Camera {camera_id} capture failed!")
                        
                if captured_files:
                    print(f"✅ 64MP flash photo captured! {len(captured_files)} file(s) saved.")
                else:
                    print("❌ All captures failed!")
                    
            elif choice == '4':
                try:
                    count = int(input("Enter number of photos to capture: ") or "3")
                    interval = float(input("Enter interval between captures (seconds): ") or "3.0")
                    high_res = input("Use 64MP resolution? (y/N): ").strip().lower() == 'y'
                    
                    print(f"Burst capture: {count} photos, {interval}s interval, {'64MP' if high_res else 'standard'} resolution")
                    
                    for i in range(count):
                        print(f"Capturing photo {i+1}/{count}...")
                        # Capture from all available cameras
                        for camera_id in available_cameras:
                            success, filename = capture_system.capture_flash_photo_rpicam(camera_id, high_resolution=high_res)
                            if success:
                                print(f"✅ Camera {camera_id} photo {i+1} captured: {os.path.basename(filename)}")
                            else:
                                print(f"❌ Camera {camera_id} photo {i+1} failed")
                        
                        if i < count - 1:
                            time.sleep(interval)
                    
                    print(f"✅ Burst capture completed!")
                    
                except ValueError:
                    print("❌ Invalid input!")
                    
            elif choice == '5':
                capture_system._show_resolution_menu()
                
            elif choice == '6':
                capture_system._show_settings_menu()
                
            elif choice == '7':
                print("\n" + "="*70)
                print("CircuitPython Arducam Flash Code (save as code.py):")
                print("="*70)
                print(get_circuitpython_flash_code())
                print("="*70)
                
            elif choice == '8':
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