import serial
import time
import math
import threading
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MovementType(Enum):
    LINEAR = "G1"
    RAPID = "G0"
    ARC_CW = "G2"
    ARC_CCW = "G3"

@dataclass
class Point:
    x: float
    y: float
    z: float = 0.0
    c: float = 0.0  # Camera tilt axis ±90°

@dataclass
class GCodeCommand:
    command_type: MovementType
    target: Point
    feedrate: Optional[float] = None
    comment: Optional[str] = None

class ArduinoGCodeController:
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200, timeout: float = 5.0):
        """
        Initialize Arduino GRBL controller
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0' for Pi, 'COM3' for Windows)
            baudrate: Communication speed
            timeout: Serial timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection: Optional[serial.Serial] = None
        self.is_connected = False
        self.command_queue = []
        self.queue_lock = threading.Lock()
        self.current_position = Point(0, 0, 0)
        self.grbl_version = ""
        self.grbl_settings = {}
        
    def connect(self, configure_settings: bool = False, custom_settings: dict = None) -> bool:
        """Establish serial connection to Arduino with GRBL
        
        Args:
            configure_settings: Whether to configure GRBL settings on startup
            custom_settings: Custom GRBL settings dict, uses defaults if None
        """
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            time.sleep(2)  # Allow Arduino to initialize
            
            # GRBL-specific wake up sequence
            self.serial_connection.write(b"\r\n\r\n")
            time.sleep(2)
            self.serial_connection.flushInput()  # Clear startup messages
            
            # Read current GRBL settings
            self.grbl_settings = self.read_grbl_settings()
            
            # Unlock GRBL (disable alarm state)
            self._send_raw_gcode("$X")
            
            # Configure GRBL settings if requested
            if configure_settings:
                logger.info("Configuring GRBL settings for camera positioning...")
                self.configure_grbl_settings(custom_settings)
            
            # Send initialization commands
            self._send_raw_gcode("G21")  # Set units to millimeters
            self._send_raw_gcode("G90")  # Absolute positioning
            self._send_raw_gcode("G94")  # Feed rate mode (units per minute)
            
            # Set current position as origin (instead of homing)
            self._send_raw_gcode("G92 X0 Y0 Z0")  # Set current position as (0,0,0)
            
            self.is_connected = True
            logger.info(f"Connected to GRBL on {self.port}")
            return True
            
        except serial.SerialException as e:
            logger.error(f"Failed to connect to Arduino: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            self.is_connected = False
            logger.info("Disconnected from Arduino")
    
    def _send_raw_gcode(self, gcode: str) -> bool:
        """Send raw G-code command and wait for GRBL response"""
        if not self.is_connected or not self.serial_connection:
            logger.error("Not connected to Arduino")
            return False
        
        try:
            # Send command
            command = f"{gcode}\n"
            self.serial_connection.write(command.encode())
            logger.debug(f"Sent: {gcode}")
            
            # Wait for response - GRBL sends "ok" when movement is complete
            start_time = time.time()
            while True:
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.readline().decode().strip()
                    
                    # Handle different GRBL response types
                    if response == "ok":
                        logger.debug(f"Command completed: {gcode}")
                        return True
                    elif response.startswith("Grbl"):
                        # GRBL version/startup message
                        self.grbl_version = response
                        logger.info(f"GRBL Version: {response}")
                        return True
                    elif response.startswith("error:"):
                        logger.error(f"GRBL error: {response}")
                        return False
                    elif response.startswith("ALARM:"):
                        logger.error(f"GRBL alarm: {response}")
                        return False
                    elif response.startswith("$"):
                        # GRBL settings response
                        logger.debug(f"GRBL setting: {response}")
                        return True
                    elif response == "":
                        # Empty response - continue waiting
                        continue
                    else:
                        logger.debug(f"GRBL response: {response}")
                        # For movement commands, continue waiting for "ok"
                        if gcode.startswith(('G0', 'G1', 'G2', 'G3')):
                            continue
                        else:
                            return True
                
                # Check for timeout
                if time.time() - start_time > self.timeout:
                    logger.error(f"Timeout waiting for response to: {gcode}")
                    return False
                
                time.sleep(0.01)  # Small delay to prevent busy waiting
                
        except Exception as e:
            logger.error(f"Error sending G-code: {e}")
            return False
    
    def move_to_point(self, target: Point, feedrate: float = 800, movement_type: MovementType = MovementType.LINEAR) -> bool:
        """Move to a specific point and wait for completion"""
        gcode = f"{movement_type.value} X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f} F{feedrate}"
        
        logger.debug(f"Moving to: X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f}")
        
        # Send movement command
        if self._send_raw_gcode(gcode):
            # Additional wait for movement completion using status query
            if self.wait_for_movement_complete():
                self.current_position = target
                logger.debug(f"Successfully moved to: X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f}")
                return True
            else:
                logger.error("Movement did not complete properly")
                return False
        return False
    
    def home_axes(self, axes: str = "XYZ") -> bool:
        """Home specified axes using GRBL homing command (if available)"""
        try:
            # Try homing command
            result = self._send_raw_gcode("$H")
            if result:
                logger.info("Homing completed successfully")
                return True
            else:
                # If homing fails, just set current position as origin
                logger.warning("Homing not available, setting current position as origin")
                return self._send_raw_gcode("G92 X0 Y0 Z0")
        except Exception as e:
            logger.warning(f"Homing failed: {e}. Setting current position as origin")
            return self._send_raw_gcode("G92 X0 Y0 Z0")
    
    def get_grbl_status(self) -> str:
        """Get GRBL real-time status"""
        try:
            if self.serial_connection:
                self.serial_connection.write(b"?")  # Status query
                response = self.serial_connection.readline().decode().strip()
                logger.debug(f"GRBL Status: {response}")
                return response
        except Exception as e:
            logger.error(f"Error getting GRBL status: {e}")
        return ""
    
    def grbl_reset(self) -> bool:
        """Send soft reset to GRBL"""
        try:
            if self.serial_connection:
                self.serial_connection.write(b"\x18")  # Ctrl-X soft reset
                time.sleep(2)
                self.serial_connection.flushInput()
                logger.info("GRBL soft reset sent")
                return True
        except Exception as e:
            logger.error(f"Error sending GRBL reset: {e}")
        return False
    
    def get_grbl_status(self) -> str:
        """Get current GRBL status"""
        if not self.is_connected:
            return "Not connected"
        
        try:
            self.serial_connection.reset_input_buffer()
            self.serial_connection.write(b"?")
            
            start_time = time.time()
            while time.time() - start_time < 2:
                if self.serial_connection.in_waiting > 0:
                    status = self.serial_connection.readline().decode().strip()
                    if status.startswith('<') and status.endswith('>'):
                        return status
                time.sleep(0.1)
            
            return "No status response"
            
        except Exception as e:
            logger.error(f"Error getting GRBL status: {e}")
            return f"Error: {e}"
    
    def get_status(self) -> str:
        """Get status - alias for get_grbl_status for compatibility"""
        return self.get_grbl_status()
    
    def wait_for_movement_complete(self, timeout: float = 30.0) -> bool:
        """Wait for GRBL to complete all movements"""
        start_time = time.time()
        
        while True:
            # Get GRBL status
            try:
                self.serial_connection.write(b"?")
                time.sleep(0.1)
                
                if self.serial_connection.in_waiting > 0:
                    status = self.serial_connection.readline().decode().strip()
                    logger.debug(f"GRBL Status: {status}")
                    
                    # Parse status - look for "Idle" state
                    if "Idle" in status:
                        logger.debug("Movement completed - GRBL is idle")
                        return True
                    elif "Run" in status:
                        logger.debug("Movement in progress...")
                        time.sleep(0.1)
                        continue
                    elif "Alarm" in status:
                        logger.error("GRBL is in alarm state")
                        return False
                
                # Check timeout
                if time.time() - start_time > timeout:
                    logger.error("Timeout waiting for movement completion")
                    return False
                
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error checking movement status: {e}")
                return False
    
    def move_to_point_and_wait(self, point: Point, feedrate: float = 500) -> bool:
        """Move to specified point and wait for completion (GRBL version)"""
        # Send movement command
        gcode = f"G1 X{point.x:.3f} Y{point.y:.3f} Z{point.z:.3f} F{feedrate}"
        
        command_success = self._send_raw_gcode(gcode)
        if not command_success:
            logger.error("GRBL movement command was not accepted")
            return False
        
        logger.debug("GRBL movement command accepted, waiting for completion...")
        
        # Wait for movement to complete
        movement_complete = self.wait_for_movement_complete()
        if movement_complete:
            self.current_position = Point(point.x, point.y, point.z, 0)  # GRBL is 3DOF
            logger.info(f"GRBL moved to X:{point.x:.1f} Y:{point.y:.1f} Z:{point.z:.1f}")
        else:
            logger.error("GRBL movement did not complete successfully")
            
        return movement_complete
    
    def set_relative_mode(self):
        """Set to relative positioning mode"""
        return self._send_raw_gcode("G91")
    
    def set_absolute_mode(self):
        """Set to absolute positioning mode"""
        return self._send_raw_gcode("G90")
    
    def configure_grbl_settings(self, custom_settings: dict = None) -> bool:
        """Configure GRBL settings for camera positioning system"""
        
        # Default settings for camera positioning (modify as needed for your hardware)
        default_settings = {
            # Steps per mm (adjust for your motors/mechanics)
            '$100': '40.0',    # X-axis steps/mm (belt drive example)
            '$101': '40.0',    # Y-axis steps/mm 
            '$102': '40.0',   # Z-axis steps/mm (lead screw example)
            
            # Maximum rates (mm/min)
            '$110': '100',    # X-axis max rate
            '$111': '100',    # Y-axis max rate  
            '$112': '100',    # Z-axis max rate (slower for precision)
            
            # Acceleration (mm/sec²)
            '$120': '30.0',   # X-axis acceleration
            '$121': '30.0',   # Y-axis acceleration
            '$122': '20.0',   # Z-axis acceleration (slower for stability)
            
            # Travel resolution (mm)
            '$12': '0.002',    # Arc tolerance
            
            # Homing settings (disable if no limit switches)
            '$22': '0',        # Homing cycle enable (0=disable, 1=enable)
            '$23': '0',        # Homing direction invert mask
            '$24': '25.0',     # Homing feed rate (mm/min)
            '$25': '100.0',    # Homing seek rate (mm/min)
            
            # Limits and safety
            '$20': '0',        # Soft limits enable (0=disable, 1=enable)
            '$21': '0',        # Hard limits enable (0=disable, 1=enable)
            
            # Spindle settings (not used for camera, but set safe values)
            '$30': '1000',     # Max spindle speed (RPM)
            '$31': '0',        # Min spindle speed (RPM)
        }
        
        # Use custom settings if provided, otherwise use defaults
        settings_to_apply = custom_settings if custom_settings else default_settings
        
        logger.info("Configuring GRBL settings for camera positioning...")
        
        success_count = 0
        total_settings = len(settings_to_apply)
        
        for setting, value in settings_to_apply.items():
            command = f"{setting}={value}"
            if self._send_raw_gcode(command):
                logger.debug(f"Set {setting} = {value}")
                success_count += 1
            else:
                logger.error(f"Failed to set {setting} = {value}")
            
            time.sleep(0.1)  # Small delay between settings
        
        # Save settings to EEPROM
        if success_count > 0:
            logger.info("Saving settings to EEPROM...")
            # Settings are automatically saved in GRBL when changed
            
        logger.info(f"GRBL configuration completed: {success_count}/{total_settings} settings applied")
        return success_count == total_settings
    
    def read_grbl_settings(self) -> dict:
        """Read and return current GRBL settings"""
        if not self.is_connected:
            logger.error("Not connected to GRBL")
            return {}
        
        try:
            # Request all settings
            self.serial_connection.write(b"$$\n")
            time.sleep(1)
            
            settings = {}
            # Read all available responses
            while self.serial_connection.in_waiting > 0:
                line = self.serial_connection.readline().decode().strip()
                if line.startswith('$') and '=' in line:
                    parts = line.split('=')
                    if len(parts) == 2:
                        settings[parts[0]] = parts[1]
            
            logger.info(f"Read {len(settings)} GRBL settings")
            return settings
            
        except Exception as e:
            logger.error(f"Error reading GRBL settings: {e}")
            return {}


class FluidNCController:
    """Controller for FluidNC-based 4DOF camera positioning system"""
    
    def __init__(self, port: str = '/dev/ttyUSB0', baudrate: int = 115200, timeout: float = 5.0):
        """
        Initialize FluidNC controller for 4DOF system
        
        Args:
            port: Serial port (e.g., '/dev/ttyUSB0' for Pi, 'COM3' for Windows)
            baudrate: Communication speed
            timeout: Serial timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection: Optional[serial.Serial] = None
        self.is_connected = False
        self.current_position = Point(0, 0, 0, 0)  # X, Y, Z, C
        self.fluidnc_version = ""
        
        # 4DOF system constraints based on FluidNC ConfigV1.2
        self.axis_limits = {
            'x': {'min': 0, 'max': 200},      # X-axis: 0-200mm
            'y': {'min': 0, 'max': 200},      # Y-axis: 0-200mm  
            'z': {'min': 0, 'max': 360},      # Z-axis: 0-360° (rotational turntable)
            'c': {'min': -90, 'max': 90}      # C-axis: ±90° (FluidNC native coordinate system)
        }
        
        # Safe feedrate limits (from FluidNC config)
        self.max_feedrates = {
            'xy_linear': 900,   # X,Y axes: keep under 1000 (config: 1000)
            'z_rotation': 400,  # Z axis: keep under 500 (config: 500) 
            'c_servo': 5000     # C axis: servo can handle higher speeds (config: 5000)
        }
        
    def connect(self) -> bool:
        """Establish serial connection to FluidNC controller"""
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            time.sleep(2)  # Allow FluidNC to initialize
            
            # FluidNC wake up sequence
            self.serial_connection.write(b"\r\n\r\n")
            time.sleep(2)
            self.serial_connection.reset_input_buffer()  # Clear startup messages
            
            # Unlock FluidNC (disable alarm state)
            self._send_raw_gcode("$X")
            
            # Send initialization commands
            self._send_raw_gcode("G21")  # Set units to millimeters
            self._send_raw_gcode("G90")  # Absolute positioning
            self._send_raw_gcode("G94")  # Feed rate mode (units per minute)
            
            # Set current position as origin
            self._send_raw_gcode("G92 X0 Y0 Z0 C0")  # Set current position as origin
            
            # Enable all axes
            self._send_raw_gcode("M17")  # Enable steppers
            
            self.is_connected = True
            logger.info(f"Connected to FluidNC on {self.port}")
            return True
            
        except serial.SerialException as e:
            logger.error(f"Failed to connect to FluidNC: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            self.is_connected = False
            logger.info("Disconnected from FluidNC")
    
    def _get_command_timeout(self, gcode: str) -> float:
        """Get appropriate timeout for different command types"""
        gcode_upper = gcode.upper().strip()
        
        if gcode_upper == "$H":  # Homing command
            return 120.0  # Increased from 60s - homing can take longer for larger machines
        elif gcode_upper.startswith("G1") or gcode_upper.startswith("G0"):  # Movement commands
            return 60.0  # Increased from 30s - give more time for long movements
        elif gcode_upper.startswith("?"):  # Status query
            return 5.0   # Increased from 2s - give more time for status response
        elif gcode_upper.startswith("$X"):  # Unlock command
            return 15.0  # Increased from 10s - unlock might need more time
        else:
            return 10.0  # Increased default timeout from self.timeout (5s)
    
    def _send_raw_gcode(self, gcode: str) -> bool:
        """Send raw G-code command and wait for FluidNC response"""
        if not self.is_connected or not self.serial_connection:
            logger.error("Not connected to FluidNC")
            return False
        
        try:
            # Send command
            command = f"{gcode}\n"
            self.serial_connection.write(command.encode())
            logger.debug(f"Sent: {gcode}")
            
            # Get appropriate timeout for this command
            command_timeout = self._get_command_timeout(gcode)
            logger.debug(f"Using timeout: {command_timeout}s for command: {gcode}")
            
            # Special handling for homing command
            is_homing = gcode.upper().strip() == "$H"
            
            # Wait for response - FluidNC sends "ok" when movement is complete
            start_time = time.time()
            response_buffer = ""
            homing_in_progress = False
            
            while True:
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.readline().decode().strip()
                    
                    # Skip empty responses
                    if not response:
                        continue
                        
                    logger.debug(f"FluidNC response: {response}")
                    
                    # Handle different FluidNC response types
                    if response == "ok":
                        if is_homing and homing_in_progress:
                            # For homing, "ok" just means command was accepted, not that homing finished
                            logger.debug("Homing command accepted, waiting for completion...")
                            homing_in_progress = True
                            continue
                        else:
                            logger.debug(f"Command completed: {gcode}")
                            return True
                            
                    elif response.startswith("[MSG:"):
                        # FluidNC info message
                        message = response[5:-1] if response.endswith(']') else response[5:]
                        logger.info(f"FluidNC message: {message}")
                        
                        if is_homing:
                            if "Homing" in message or "homing" in message:
                                homing_in_progress = True
                                logger.info("Homing sequence started...")
                            elif "Home" in message and "complete" in message.lower():
                                logger.info("Homing completed!")
                                return True
                        continue
                        
                    elif response.startswith("[GC:"):
                        # FluidNC G-code parser state - continue waiting for "ok"
                        logger.debug(f"FluidNC parser state: {response}")
                        continue
                        
                    elif response.startswith("[PRB:"):
                        # FluidNC probe result - continue waiting for "ok"
                        logger.debug(f"FluidNC probe result: {response}")
                        continue
                        
                    elif response.startswith("error:"):
                        logger.error(f"FluidNC error: {response}")
                        return False
                        
                    elif response.startswith("ALARM:"):
                        logger.error(f"FluidNC alarm: {response}")
                        return False
                        
                    elif response.startswith("$"):
                        # FluidNC settings response
                        logger.debug(f"FluidNC setting: {response}")
                        return True
                        
                    elif response.startswith("<") and response.endswith(">"):
                        # FluidNC status response (for ? command)
                        logger.debug(f"FluidNC status: {response}")
                        
                        if is_homing:
                            # Check if homing is complete by looking at status
                            if "|Home" in response or "Home|" in response:
                                logger.info("Homing completed (detected from status)")
                                return True
                            elif "|Idle" in response and homing_in_progress:
                                # System went from homing to idle - homing complete
                                logger.info("Homing completed (system idle)")
                                return True
                        else:
                            return True
                            
                    else:
                        # Other responses - log but continue waiting
                        logger.debug(f"FluidNC other response: {response}")
                        continue
                
                # Timeout check
                elapsed = time.time() - start_time
                if elapsed > command_timeout:
                    logger.error(f"Command timeout after {elapsed:.1f}s (limit: {command_timeout}s): {gcode}")
                    return False
                    
                time.sleep(0.02)  # Reduced from 0.05s for better responsiveness
                
        except Exception as e:
            logger.error(f"Error sending G-code '{gcode}': {e}")
            return False
    
    def validate_position(self, point: Point) -> bool:
        """Validate that position is within axis limits with safety margins"""
        # Add safety margins to avoid hitting limits during testing
        safety_margin = 5.0  # 5mm safety margin
        
        # Strictly prevent negative X and Y positions
        x_min = 0.0  # No negative X positions allowed
        x_max = self.axis_limits['x']['max'] - safety_margin
        
        y_min = 0.0  # No negative Y positions allowed
        y_max = self.axis_limits['y']['max'] - safety_margin
        
        z_min = self.axis_limits['z']['min']
        z_max = self.axis_limits['z']['max']
        
        c_min = self.axis_limits['c']['min']
        c_max = self.axis_limits['c']['max']
        
        if not (x_min <= point.x <= x_max):
            logger.error(f"X position {point.x:.2f} outside safe limits [{x_min}, {x_max}] (with {safety_margin}mm margin)")
            return False
        if not (y_min <= point.y <= y_max):
            logger.error(f"Y position {point.y:.2f} outside safe limits [{y_min}, {y_max}] (with {safety_margin}mm margin)")
            return False
        if not (z_min <= point.z <= z_max):
            logger.error(f"Z position {point.z:.2f} outside limits [{z_min}, {z_max}]")
            return False
        if not (c_min <= point.c <= c_max):
            logger.error(f"C position {point.c:.2f} outside limits [{c_min}, {c_max}]")
            return False
        return True
    
    def clamp_coordinates(self, point: Point) -> Point:
        """Ensure coordinates are never negative for X and Y axes"""
        clamped_x = max(0.0, point.x)  # No negative X
        clamped_y = max(0.0, point.y)  # No negative Y
        
        # Log if clamping occurred
        if clamped_x != point.x or clamped_y != point.y:
            logger.info(f"Clamped coordinates: ({point.x:.2f},{point.y:.2f}) → ({clamped_x:.2f},{clamped_y:.2f})")
        
        return Point(clamped_x, clamped_y, point.z, point.c)
    
    def validate_feedrate(self, feedrate: float) -> float:
        """Validate and clamp feedrate to safe limits for linear axes"""
        # For combined XYZ movements, use the most restrictive limit
        safe_feedrate = min(feedrate, self.max_feedrates['xy_linear'])
        
        if safe_feedrate != feedrate:
            logger.info(f"Feedrate limited for safety: {feedrate} → {safe_feedrate} mm/min")
            
        return safe_feedrate
    
    def convert_angle_to_fluidnc(self, angle_degrees: float) -> float:
        """Convert tilt angle (±90°) to FluidNC C-axis coordinate"""
        # FluidNC expects ±90° directly, no conversion needed
        return max(-90.0, min(90.0, angle_degrees))
    
    def convert_fluidnc_to_angle(self, fluidnc_pos: float) -> float:
        """Convert FluidNC C-axis coordinate to tilt angle (±90°)"""
        # FluidNC reports ±90° directly, no conversion needed
        return max(-90.0, min(90.0, fluidnc_pos))
    
    def get_safe_test_area(self) -> dict:
        """Get safe area boundaries for testing (with margins)"""
        safety_margin = 10.0  # 10mm safety margin for testing
        
        return {
            'x_min': max(0.0, safety_margin),  # Ensure no negative X
            'x_max': self.axis_limits['x']['max'] - safety_margin,
            'y_min': max(0.0, self.axis_limits['y']['min'] + safety_margin),  # Ensure no negative Y
            'y_max': self.axis_limits['y']['max'] - safety_margin,
            'z_min': self.axis_limits['z']['min'],
            'z_max': self.axis_limits['z']['max'],
            'c_min': self.axis_limits['c']['min'] + 5,   # Stay away from C limits (-85° to +85°)
            'c_max': self.axis_limits['c']['max'] - 5
        }
    
    def create_safe_point(self, x: float, y: float, z: Optional[float] = None, c: Optional[float] = None) -> Point:
        """Create a point that's guaranteed to be within safe limits"""
        if z is None:
            z = 0.0
        if c is None:
            c = 0.0  # Default center position (0° tilt)
            
        safe_area = self.get_safe_test_area()
        
        # Clamp values to safe area
        safe_x = max(safe_area['x_min'], min(x, safe_area['x_max']))
        safe_y = max(safe_area['y_min'], min(y, safe_area['y_max']))
        safe_z = max(safe_area['z_min'], min(z, safe_area['z_max']))
        safe_c = max(safe_area['c_min'], min(c, safe_area['c_max']))
        
        if safe_x != x or safe_y != y or safe_z != z or safe_c != c:
            logger.info(f"Point adjusted for safety: ({x},{y},{z},{c}) → ({safe_x},{safe_y},{safe_z},{safe_c})")
            
        return Point(safe_x, safe_y, safe_z, safe_c)
    
    def move_to_point(self, point: Point, feedrate: float = 800) -> bool:
        """Move to specified 4DOF point with validation (command only - use move_to_point_and_wait for scanning)"""
        # Clamp coordinates to prevent negative X/Y values
        clamped_point = self.clamp_coordinates(point)
        
        # Validate feedrate for safety
        safe_feedrate = self.validate_feedrate(feedrate)
        
        if not self.validate_position(clamped_point):
            return False
            
        # Build G-code command for 4DOF movement
        gcode = f"G1 X{clamped_point.x:.3f} Y{clamped_point.y:.3f} Z{clamped_point.z:.3f} C{clamped_point.c:.3f} F{safe_feedrate}"
        
        success = self._send_raw_gcode(gcode)
        if success:
            # Note: This updates position immediately but movement may still be in progress
            # Use move_to_point_and_wait() for operations requiring movement completion
            self.current_position = Point(clamped_point.x, clamped_point.y, clamped_point.z, clamped_point.c)
            logger.info(f"Movement command sent to X:{clamped_point.x:.1f} Y:{clamped_point.y:.1f} Z:{clamped_point.z:.1f} C:{clamped_point.c:.1f}")
        
        return success
    
    def home_axes(self) -> bool:
        """Home configured axes with proper verification"""
        logger.info("Starting FluidNC homing sequence...")
        
        # First check if already homed
        if self.check_homing_status():
            logger.info("System is already homed")
            return True
        
        # Clear any alarm state first
        logger.info("Clearing any alarm state...")
        self._send_raw_gcode("$X")
        time.sleep(1.0)
        
        # Start homing command
        logger.info("Sending homing command - this may take up to 60 seconds...")
        
        # Send the homing command but don't rely on its return value
        self._send_raw_gcode("$H")
        
        # Now wait for actual homing completion by polling status
        start_time = time.time()
        timeout = 60.0  # 60 second timeout for homing
        check_interval = 2.0  # Check every 2 seconds
        
        logger.info("Monitoring homing progress...")
        
        while time.time() - start_time < timeout:
            time.sleep(check_interval)
            
            # Check if homing is complete
            if self.check_homing_status():
                elapsed = time.time() - start_time
                logger.info(f"Homing completed successfully in {elapsed:.1f} seconds")
                
                # Get actual machine position after homing
                time.sleep(1)  # Give system time to settle
                machine_pos = self.get_machine_position()
                
                logger.info(f"Post-homing machine position: X:{machine_pos.x:.1f} Y:{machine_pos.y:.1f} Z:{machine_pos.z:.1f} C:{machine_pos.c:.1f}")
                
                # Check for small negative offsets and correct them to avoid validation errors
                corrected_pos = machine_pos
                position_corrected = False
                
                if machine_pos.x < 0 and machine_pos.x > -5.0:  # Small negative offset from homing
                    logger.info(f"Correcting small X homing offset: {machine_pos.x:.2f} → 0.0")
                    self._send_raw_gcode("G92 X0")  # Set current X position as 0
                    corrected_pos = Point(0.0, machine_pos.y, machine_pos.z, machine_pos.c)
                    position_corrected = True
                    
                if machine_pos.y > 205.0:  # Y should be ~200mm, allow small tolerance
                    logger.info(f"Correcting Y position offset: {machine_pos.y:.2f} → 200.0")
                    self._send_raw_gcode("G92 Y200")  # Set current Y position as 200
                    corrected_pos = Point(corrected_pos.x, 200.0, machine_pos.z, machine_pos.c)
                    position_corrected = True
                    
                if position_corrected:
                    time.sleep(0.5)  # Let correction settle
                    final_pos = self.get_machine_position()
                    logger.info(f"Corrected position: X:{final_pos.x:.1f} Y:{final_pos.y:.1f} Z:{final_pos.z:.1f} C:{final_pos.c:.1f}")
                    self.current_position = final_pos
                else:
                    self.current_position = machine_pos
                    
                return True
            
            # Show progress
            elapsed = time.time() - start_time
            logger.info(f"Homing in progress... ({elapsed:.0f}s elapsed)")
        
        # Timeout occurred
        logger.error(f"Homing timeout after {timeout} seconds")
        return False
    
    def get_status(self) -> str:
        """Get current FluidNC status"""
        if not self.is_connected or not self.serial_connection:
            return "Not connected"
        
        try:
            # Clear any pending input
            self.serial_connection.reset_input_buffer()
            
            # Send status query
            self.serial_connection.write(b"?\n")
            
            start_time = time.time()
            status_timeout = 3.0  # Status queries should be quick
            
            while time.time() - start_time < status_timeout:
                if self.serial_connection.in_waiting > 0:
                    status = self.serial_connection.readline().decode().strip()
                    
                    # Skip empty responses
                    if not status:
                        continue
                    
                    # FluidNC status format: <Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0|WCO:0.000,0.000,0.000,0.000>
                    if status.startswith('<') and status.endswith('>'):
                        logger.debug(f"Status received: {status}")
                        return status
                    elif status.startswith("[MSG:"):
                        # Info message - continue waiting
                        logger.debug(f"Status query message: {status}")
                        continue
                    else:
                        logger.debug(f"Unexpected status response: {status}")
                        continue
                        
                time.sleep(0.05)
            
            logger.warning("Status query timeout")
            return "Status timeout"
            
        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return f"Error: {e}"
    
    def is_homed(self) -> bool:
        """Check if system is homed using dedicated homing verification"""
        return self.check_homing_status()
    
    def get_machine_position(self) -> Point:
        """Get current machine position from FluidNC status"""
        status = self.get_status()
        
        if status.startswith('<') and status.endswith('>'):
            parts = status[1:-1].split('|')
            
            for part in parts:
                if part.startswith('MPos:'):
                    # Parse machine position: MPos:X,Y,Z,C
                    coords = part[5:].split(',')
                    if len(coords) >= 4:
                        try:
                            x = float(coords[0])
                            y = float(coords[1])
                            z = float(coords[2])
                            c = float(coords[3])
                            return Point(x, y, z, c)
                        except ValueError:
                            logger.error(f"Failed to parse machine position: {part}")
                            break
        
        logger.warning("Could not get machine position from status")
        return self.current_position
    
    def get_work_position(self) -> Point:
        """Get current work position from FluidNC status"""
        status = self.get_status()
        
        if status.startswith('<') and status.endswith('>'):
            parts = status[1:-1].split('|')
            
            for part in parts:
                if part.startswith('WPos:'):
                    # Parse work position: WPos:X,Y,Z,C
                    coords = part[5:].split(',')
                    if len(coords) >= 4:
                        try:
                            x = float(coords[0])
                            y = float(coords[1])
                            z = float(coords[2])
                            c = float(coords[3])
                            return Point(x, y, z, c)
                        except ValueError:
                            logger.error(f"Failed to parse work position: {part}")
                            break
        
        logger.warning("Could not get work position from status")
        return self.current_position
    
    def check_homing_status(self) -> bool:
        """Query FluidNC to check if system is actually homed"""
        try:
            # Get fresh status
            status = self.get_status()
            
            if not status.startswith('<') or not status.endswith('>'):
                logger.warning("Invalid status format for homing check")
                return False
            
            # Parse status: <State|MPos:X,Y,Z,C|FS:0,0|WCO:X,Y,Z,C>
            parts = status[1:-1].split('|')
            state = parts[0] if parts else ""
            
            # Check for alarm state (definitely not homed)
            if 'Alarm' in state:
                logger.debug("System in alarm state - not homed")
                return False
            
            # Look for machine position and work coordinate offset
            has_mpos = False
            has_wco = False
            mpos_values = None
            
            for part in parts:
                if part.startswith('MPos:'):
                    has_mpos = True
                    coords = part[5:].split(',')
                    if len(coords) >= 2:
                        try:
                            # For our config, Y should be ~200mm when homed
                            y_pos = float(coords[1])
                            mpos_values = coords
                            logger.debug(f"Machine Y position: {y_pos}")
                        except ValueError:
                            logger.warning("Could not parse machine position")
                            
                elif part.startswith('WCO:'):
                    has_wco = True
                    logger.debug("Work coordinate offset present")
            
            # System is homed if:
            # 1. Not in alarm state
            # 2. Has machine position data  
            # 3. Has work coordinate offset (indicates coordinate system is established)
            # 4. Y position is near expected home value (200mm for our config)
            
            if has_mpos and has_wco and mpos_values:
                try:
                    y_pos = float(mpos_values[1])
                    # Check if Y is near home position (200mm ± 5mm tolerance)
                    y_homed = abs(y_pos - 200.0) < 5.0
                    
                    logger.debug(f"Homing check: MPos={has_mpos}, WCO={has_wco}, Y={y_pos:.1f}, Y_homed={y_homed}")
                    return y_homed
                    
                except (ValueError, IndexError):
                    logger.warning("Could not validate Y position for homing")
                    return False
            
            logger.debug(f"Homing check failed: MPos={has_mpos}, WCO={has_wco}")
            return False
            
        except Exception as e:
            logger.error(f"Error checking homing status: {e}")
            return False
    
    def wait_for_movement_complete(self, timeout: float = 60.0) -> bool:
        """Wait for FluidNC to complete all movements by monitoring status"""
        start_time = time.time()
        last_status_time = 0
        status_check_interval = 0.05  # Check status every 50ms for faster response
        
        while time.time() - start_time < timeout:
            current_time = time.time()
            
            # Only query status at specified intervals to avoid overwhelming FluidNC
            if current_time - last_status_time >= status_check_interval:
                status = self.get_status()
                last_status_time = current_time
                
                if status.startswith('<') and status.endswith('>'):
                    # Parse status: <State|MPos:X,Y,Z,C|FS:feedrate,spindle>
                    parts = status[1:-1].split('|')
                    state = parts[0] if parts else ""
                    
                    # Check if system is idle (movement complete)
                    if state == 'Idle':
                        logger.debug("Movement completed - system idle")
                        return True
                    elif state in ['Run', 'Jog']:
                        # Still moving - log occasionally for feedback
                        elapsed = current_time - start_time
                        if elapsed > 0 and int(elapsed) % 5 == 0 and elapsed - int(elapsed) < 0.1:
                            logger.info(f"Movement in progress ({elapsed:.1f}s) - state: {state}")
                    elif state.startswith('Alarm'):
                        logger.error("Movement stopped due to alarm")
                        return False
                    else:
                        logger.debug(f"Unknown state during movement: {state}")
            
            time.sleep(0.02)  # Reduced from 0.1s to 0.02s for more responsive monitoring
        
        logger.warning(f"Movement completion timeout after {timeout}s")
        return False
    
    def move_to_point_and_wait(self, point: Point, feedrate: float = 800) -> bool:
        """Move to specified point and wait for completion"""
        # Clamp coordinates to prevent negative X/Y values
        clamped_point = self.clamp_coordinates(point)
        
        # Validate feedrate for safety
        safe_feedrate = self.validate_feedrate(feedrate)
        
        if not self.validate_position(clamped_point):
            return False
            
        # Build G-code command for 4DOF movement
        gcode = f"G1 X{clamped_point.x:.3f} Y{clamped_point.y:.3f} Z{clamped_point.z:.3f} C{clamped_point.c:.3f} F{safe_feedrate}"
        
        # Send movement command
        command_accepted = self._send_raw_gcode(gcode)
        if not command_accepted:
            logger.error("Movement command was not accepted")
            return False
        
        logger.debug("Movement command accepted, waiting for completion...")
        
        # Wait for movement to complete
        movement_complete = self.wait_for_movement_complete()
        if movement_complete:
            self.current_position = Point(clamped_point.x, clamped_point.y, clamped_point.z, clamped_point.c)
            logger.info(f"Moved to X:{clamped_point.x:.1f} Y:{clamped_point.y:.1f} Z:{clamped_point.z:.1f} C:{clamped_point.c:.1f}")
        else:
            logger.error("Movement did not complete successfully")
            
        return movement_complete
    
    def unlock_controller(self) -> bool:
        """Unlock FluidNC controller (clear alarm state)"""
        logger.info("Unlocking FluidNC controller...")
        success = self._send_raw_gcode("$X")
        
        if success:
            logger.info("Controller unlocked successfully")
        else:
            logger.error("Failed to unlock controller")
            
        return success
    
    def get_grbl_status(self) -> str:
        """Get status in GRBL-compatible format for interface compatibility"""
        return self.get_status()


class PathPlanner:
    def __init__(self, controller):
        """Initialize PathPlanner with either ArduinoGCodeController or FluidNCController"""
        self.controller = controller
        self.current_position = Point(0, 0, 0, 0)  # Support 4DOF
        
    def generate_linear_path(self, start: Point, end: Point, steps: int = 10) -> List[Point]:
        """Generate linear interpolation between two points (4DOF)"""
        path = []
        for i in range(steps + 1):
            t = i / steps
            x = start.x + t * (end.x - start.x)
            y = start.y + t * (end.y - start.y)
            z = start.z + t * (end.z - start.z)
            c = start.c + t * (end.c - start.c)
            path.append(Point(x, y, z, c))
        return path
    
    def generate_circular_path(self, center: Point, radius: float, start_angle: float = 0, 
                             end_angle: float = 360, steps: int = 36) -> List[Point]:
        """Generate circular path around center point (XY plane)"""
        path = []
        angle_step = math.radians(end_angle - start_angle) / steps
        
        for i in range(steps + 1):
            angle = math.radians(start_angle) + i * angle_step
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            path.append(Point(x, y, center.z, center.c))
        
        return path
    
    def generate_rotational_scan(self, center: Point, z_angles: List[float], 
                               c_position: float = 90) -> List[Point]:
        """Generate rotational scan path using Z-axis turntable
        
        Args:
            center: Center position (XY coordinates)
            z_angles: List of turntable rotation angles in degrees
            c_position: C-axis position in mm (0-180mm, default 90mm = 0° tilt)
        """
        path = []
        for z_angle in z_angles:
            # Z-axis is rotational: 360° = 360mm in FluidNC
            z_position = z_angle  # Direct mapping: 1° = 1mm
            path.append(Point(center.x, center.y, z_position, c_position))
        return path
    
    def generate_tilt_scan(self, base_position: Point, c_angles: List[float]) -> List[Point]:
        """Generate camera tilt scan at fixed XYZ position
        
        Args:
            base_position: Fixed XYZ position
            c_angles: List of tilt angles in degrees (±90°)
        """
        path = []
        for c_angle in c_angles:
            # C-axis angle is now used directly (±90° system)
            c_position = max(-90.0, min(90.0, c_angle))  # Clamp to ±90°
            
            # Validate C-axis limits (±90° as per updated system)
            if -90 <= c_position <= 90:
                path.append(Point(base_position.x, base_position.y, base_position.z, c_position))
            else:
                logger.warning(f"C-axis angle {c_angle}° outside limits [±90°], skipping")
        return path
    
    def generate_grid_scan_path(self, min_point: Point, max_point: Point, 
                               x_steps: int = 10, y_steps: int = 10) -> List[Point]:
        """Generate zigzag scanning pattern over rectangular area (4DOF)"""
        path = []
        x_step = (max_point.x - min_point.x) / x_steps if x_steps > 0 else 0
        y_step = (max_point.y - min_point.y) / y_steps if y_steps > 0 else 0
        
        for j in range(y_steps + 1):
            y = min_point.y + j * y_step
            
            if j % 2 == 0:  # Even rows: left to right
                for i in range(x_steps + 1):
                    x = min_point.x + i * x_step
                    path.append(Point(x, y, min_point.z, min_point.c))
            else:  # Odd rows: right to left
                for i in range(x_steps, -1, -1):
                    x = min_point.x + i * x_step
                    path.append(Point(x, y, min_point.z, min_point.c))
        
        return path
    
    def generate_spherical_scan(self, center: Point, radius: float, 
                              z_angles: List[float], c_angles: List[float]) -> List[Point]:
        """Generate spherical scan combining XY movement, Z rotation, and C tilt
        
        Args:
            center: Center position for spherical scan
            radius: Radius for XY movement
            z_angles: List of turntable rotation angles (degrees)
            c_angles: List of camera tilt angles (degrees, ±90°)
        """
        path = []
        
        for z_angle in z_angles:
            for c_angle in c_angles:
                # Calculate XY position for spherical coordinates
                # This is a simplified approach - could be enhanced with true spherical coordinates
                x_offset = radius * math.cos(math.radians(c_angle)) * math.cos(math.radians(z_angle))
                y_offset = radius * math.cos(math.radians(c_angle)) * math.sin(math.radians(z_angle))
                
                x = center.x + x_offset
                y = center.y + y_offset
                z = z_angle  # Direct angle mapping for turntable
                c = max(-90.0, min(90.0, c_angle))  # Direct ±90° coordinate system
                
                # Validate position before adding to path
                test_point = Point(x, y, z, c)
                if hasattr(self.controller, 'validate_position'):
                    if self.controller.validate_position(test_point):
                        path.append(test_point)
                else:
                    # For backward compatibility with ArduinoGCodeController
                    path.append(Point(x, y, z, c))
        
        return path
    
    def execute_path(self, path: List[Point], feedrate: float = 900, 
                    pause_between_points: float = 0.2) -> bool:
        """Execute a planned path with proper movement completion waiting"""
        if not self.controller.is_connected:
            logger.error("Controller not connected")
            return False
        
        logger.info(f"Executing path with {len(path)} points at {feedrate}mm/min (optimized for speed)")
        
        for i, point in enumerate(path):
            # Use movement completion waiting for all scanning operations
            success = self.controller.move_to_point_and_wait(point, feedrate)
            
            if not success:
                logger.error(f"Failed to move to point {i}: {point}")
                return False
            
            # Reduced pause for settling/photo capture if specified
            if pause_between_points > 0:
                logger.debug(f"Settling pause: {pause_between_points}s")
                time.sleep(pause_between_points)
            
            # Progress feedback every 10 points for long paths
            if (i + 1) % 10 == 0 or i == len(path) - 1:
                progress = ((i + 1) / len(path)) * 100
                logger.info(f"Path progress: {i+1}/{len(path)} ({progress:.1f}%) - X{point.x:.1f} Y{point.y:.1f}")
            else:
                logger.debug(f"Completed move to point {i+1}/{len(path)}: X{point.x:.3f} Y{point.y:.3f} Z{point.z:.3f}")
        
        logger.info("Path execution completed successfully")
        return True

class CameraPositionController:
    def __init__(self, controller):
        """Initialize with either ArduinoGCodeController or FluidNCController"""
        self.controller = controller
        self.planner = PathPlanner(controller)
        self.safe_height = 10.0  # Safe Z height for movements
        self.default_c_position = 0.0  # Default camera position (0° tilt in ±90° system)
    
    def convert_angle_to_fluidnc(self, angle_degrees: float) -> float:
        """Convert tilt angle (±90°) to FluidNC C-axis coordinate"""
        # FluidNC expects ±90° directly, no conversion needed
        return max(-90.0, min(90.0, angle_degrees))
    
    def convert_fluidnc_to_angle(self, fluidnc_pos: float) -> float:
        """Convert FluidNC C-axis coordinate to tilt angle (±90°)"""
        # FluidNC reports ±90° directly, no conversion needed
        return max(-90.0, min(90.0, fluidnc_pos))
    
    def initialize_system(self, configure_grbl: bool = False, custom_settings: dict = None) -> bool:
        """Initialize the camera positioning system (4DOF)"""
        # Handle different controller types
        if hasattr(self.controller, 'connect'):
            if isinstance(self.controller, FluidNCController):
                success = self.controller.connect()
            else:  # ArduinoGCodeController
                success = self.controller.connect(configure_settings=configure_grbl, 
                                                custom_settings=custom_settings)
        else:
            logger.error("Controller does not have a connect method")
            return False
            
        if not success:
            return False
        
        logger.info("Initializing 4DOF camera positioning system...")
        
        # Try to home, but don't fail if homing isn't available
        try:
            home_success = self.controller.home_axes()
            if home_success:
                logger.info("4DOF system initialized successfully")
            else:
                logger.warning("Homing not available, but system is connected")
        except Exception as e:
            logger.warning(f"Homing failed: {e}, but system is connected")
        
        return True
    
    def move_to_capture_position(self, x: float, y: float, z: float = None, 
                                c: float = None, feedrate: float = 800) -> bool:
        """Move camera to specific 4DOF capture position
        
        Args:
            x, y: Linear position in mm
            z: Rotation angle in degrees (optional)
            c: Camera tilt angle in degrees ±90° (optional, direct FluidNC coordinate)
            feedrate: Movement speed
        """
        if z is None:
            z = self.safe_height
        if c is None:
            c_position = self.default_c_position  # Use default position (0° tilt)
        else:
            c_position = self.convert_angle_to_fluidnc(c)  # Ensure within ±90° range
        
        target = Point(x, y, z, c_position)
        logger.info(f"Moving to 4DOF capture position: X{x} Y{y} Z{z}° C{c}° (FluidNC: {c_position})")
        
        # Use movement completion waiting for capture positioning
        return self.controller.move_to_point_and_wait(target, feedrate)
    
    def scan_area(self, corner1: Point, corner2: Point, grid_size: Tuple[int, int] = (5, 5),
                  capture_height: float = None, c_angle: float = None, 
                  feedrate: float = 800) -> bool:
        """Perform systematic scan of rectangular area (4DOF)
        
        Args:
            corner1, corner2: Corner points defining scan area
            grid_size: (x_steps, y_steps) for grid pattern
            capture_height: Z height for scan (optional)
            c_angle: Camera tilt angle in degrees (optional, converted to position)
            feedrate: Movement speed
        """
        if capture_height is None:
            capture_height = self.safe_height
        if c_angle is None:
            c_position = self.default_c_position
        else:
            c_position = c_angle + 90  # Convert tilt angle to position
        
        # Define scan area with 4DOF
        min_point = Point(min(corner1.x, corner2.x), min(corner1.y, corner2.y), 
                         capture_height, c_position)
        max_point = Point(max(corner1.x, corner2.x), max(corner1.y, corner2.y), 
                         capture_height, c_position)
        
        # Generate scan path
        scan_path = self.planner.generate_grid_scan_path(min_point, max_point, 
                                                        grid_size[0], grid_size[1])
        
        # Execute scan
        logger.info(f"Starting 4DOF area scan: {len(scan_path)} positions")
        return self.planner.execute_path(scan_path, feedrate, pause_between_points=0.5)
    
    def circular_scan(self, center: Point, radius: float, num_positions: int = 8,
                     capture_height: float = None, c_angle: float = None,
                     feedrate: float = 500) -> bool:
        """Perform circular scan around center point (4DOF)
        
        Args:
            center: Center point for circular scan
            radius: Radius of circular path
            num_positions: Number of positions around circle
            capture_height: Z height for scan (optional)
            c_angle: Camera tilt angle in degrees (optional, converted to position)
            feedrate: Movement speed
        """
        if capture_height is None:
            capture_height = self.safe_height
        if c_angle is None:
            c_position = self.default_c_position
        else:
            c_position = c_angle + 90  # Convert tilt angle to position
        
        center.z = capture_height
        center.c = c_position
        
        # Generate circular path
        circular_path = self.planner.generate_circular_path(center, radius, 0, 360, num_positions)
        
        # Execute circular scan
        logger.info(f"Starting 4DOF circular scan: {len(circular_path)} positions")
        return self.planner.execute_path(circular_path, feedrate, pause_between_points=1.0)
    
    def rotational_scan(self, base_position: Point, z_angles: List[float], 
                       c_angle: float = None, feedrate: float = 300) -> bool:
        """Perform rotational scan using Z-axis turntable
        
        Args:
            base_position: Fixed XY position for scan
            z_angles: List of turntable rotation angles in degrees
            c_angle: Camera tilt angle in degrees (optional, converted to position)
            feedrate: Movement speed
        """
        if c_angle is None:
            c_position = self.default_c_position
        else:
            c_position = c_angle + 90  # Convert tilt angle to position
        
        # Generate rotational scan path
        rotation_path = self.planner.generate_rotational_scan(base_position, z_angles, c_position)
        
        logger.info(f"Starting rotational scan: {len(rotation_path)} positions")
        return self.planner.execute_path(rotation_path, feedrate, pause_between_points=1.0)
    
    def tilt_scan(self, base_position: Point, c_angles: List[float], 
                 feedrate: float = 200) -> bool:
        """Perform camera tilt scan at fixed XYZ position"""
        # Generate tilt scan path
        tilt_path = self.planner.generate_tilt_scan(base_position, c_angles)
        
        logger.info(f"Starting camera tilt scan: {len(tilt_path)} positions")
        return self.planner.execute_path(tilt_path, feedrate, pause_between_points=0.5)
    
    def spherical_scan(self, center: Point, radius: float, 
                      z_angles: List[float], c_angles: List[float],
                      feedrate: float = 300) -> bool:
        """Perform comprehensive spherical scan combining rotation and tilt"""
        # Generate spherical scan path
        spherical_path = self.planner.generate_spherical_scan(center, radius, z_angles, c_angles)
        
        logger.info(f"Starting spherical scan: {len(spherical_path)} positions")
        return self.planner.execute_path(spherical_path, feedrate, pause_between_points=1.5)
    
    def return_to_home(self) -> bool:
        """Return camera to origin position (4DOF)"""
        logger.info("Returning to 4DOF origin position")
        # Use center C position (90mm = 0° tilt) for home
        return self.controller.move_to_point(Point(0, 0, 0, 0), feedrate=500)
    
    def emergency_stop(self):
        """Emergency stop - immediately halt all movement"""
        if self.controller.is_connected:
            # GRBL uses Ctrl-X for soft reset (emergency stop)
            self.controller.grbl_reset()
            logger.warning("Emergency stop activated - GRBL reset sent")
    
    def get_system_status(self) -> str:
        """Get current GRBL system status"""
        return self.controller.get_grbl_status()
    
    def unlock_grbl(self) -> bool:
        """Unlock GRBL from alarm state"""
        return self.controller._send_raw_gcode("$X")
    
    def shutdown(self):
        """Safely shutdown the positioning system without moving"""
        logger.info("Shutting down camera positioning system - leaving position as-is")
        # Do not return to home - leave system at current position
        self.controller.disconnect()

# Example usage and test functions
def test_single_axis(axis: str = 'X', distance: float = 50.0, steps: int = 5):
    """Test movement on a single axis only
    
    Args:
        axis: Which axis to test ('X', 'Y', or 'Z')
        distance: Maximum distance to move
        steps: Number of test positions
    """
    controller = ArduinoGCodeController('/dev/ttyUSB0')  # Updated for your port
    camera_system = CameraPositionController(controller)
    
    try:
        # Initialize
        if not camera_system.initialize_system():
            logger.error("Failed to initialize system")
            return False
        
        logger.info(f"Testing {axis}-axis movement with {steps} steps over {distance}mm")
        
        # Generate test positions for single axis
        step_size = distance / steps
        
        for i in range(steps + 1):
            position = i * step_size
            
            if axis.upper() == 'X':
                target = Point(position, 0, 0)
            elif axis.upper() == 'Y':
                target = Point(0, position, 0)
            elif axis.upper() == 'Z':
                target = Point(0, 0, position)
            else:
                logger.error(f"Invalid axis: {axis}. Use 'X', 'Y', or 'Z'")
                return False
            
            logger.info(f"Moving to {axis}={position:.1f}mm")
            success = camera_system.controller.move_to_point(target, feedrate=500)
            
            if not success:
                logger.error(f"Failed to move to position {i}")
                return False
            
            time.sleep(1)  # Pause between movements
        
        # Return to home
        logger.info("Test completed, returning to home")
        camera_system.return_to_home()
        
        return True
        
    except Exception as e:
        logger.error(f"Single axis test failed: {e}")
        return False
    finally:
        camera_system.shutdown()

def test_simple_movement():
    """Test simple movement without homing requirement"""
    controller = ArduinoGCodeController('/dev/ttyUSB0')
    
    try:
        # Just connect, don't initialize system
        if not controller.connect():
            logger.error("Failed to connect to GRBL")
            return False
        
        logger.info("Testing simple movements (no homing required)...")
        
        # Set current position as origin
        controller._send_raw_gcode("G92 X0 Y0 Z0")
        
        # Test small movements
        movements = [
            Point(2, 0, 0),   # Move X 2mm
            Point(2, 2, 0),  # Move Y 2mm
            Point(0, 2, 0),   # Move X back to 0
            Point(0, 0, 0)     # Return to origin
        ]
        
        for i, point in enumerate(movements):
            logger.info(f"Moving to: X{point.x} Y{point.y} Z{point.z}")
            success = controller.move_to_point(point, feedrate=300)
            if not success:
                logger.error(f"Failed movement {i}")
                return False
            time.sleep(2)  # Wait between movements
        
        logger.info("Simple movement test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Simple movement test failed: {e}")
        return False
    finally:
        controller.disconnect()

def test_grbl_settings():
    """Test GRBL settings configuration and viewing"""
    controller = ArduinoGCodeController('/dev/ttyUSB0')
    
    try:
        logger.info("Testing GRBL settings...")
        
        # Connect without configuring settings first
        if not controller.connect():
            logger.error("Failed to connect to GRBL")
            return False
        
        # Read current settings
        logger.info("Current GRBL settings:")
        current_settings = controller.read_grbl_settings()
        
        # Display key settings
        key_settings = ['$100', '$101', '$102', '$110', '$111', '$112', '$120', '$121', '$122']
        for setting in key_settings:
            if setting in current_settings:
                description = {
                    '$100': 'X-axis steps/mm',
                    '$101': 'Y-axis steps/mm', 
                    '$102': 'Z-axis steps/mm',
                    '$110': 'X-axis max rate (mm/min)',
                    '$111': 'Y-axis max rate (mm/min)',
                    '$112': 'Z-axis max rate (mm/min)',
                    '$120': 'X-axis acceleration (mm/sec²)',
                    '$121': 'Y-axis acceleration (mm/sec²)',
                    '$122': 'Z-axis acceleration (mm/sec²)'
                }
                print(f"  {setting} = {current_settings[setting]} ({description.get(setting, 'Unknown')})")
        
        # Ask if user wants to configure settings
        configure = input("\nDo you want to configure GRBL settings for camera positioning? (y/N): ").strip().lower()
        
        if configure == 'y':
            logger.info("Configuring GRBL settings...")
            success = controller.configure_grbl_settings()
            if success:
                logger.info("GRBL settings configured successfully!")
            else:
                logger.warning("Some GRBL settings failed to configure")
        
        return True
        
    except Exception as e:
        logger.error(f"GRBL settings test failed: {e}")
        return False
    finally:
        controller.disconnect()

def test_grbl_connection():
    """Test GRBL connection and basic functionality"""
    controller = ArduinoGCodeController('/dev/ttyUSB0')  # Updated for your port
    
    try:
        # Test connection
        logger.info("Testing GRBL connection...")
        if not controller.connect():
            logger.error("Failed to connect to GRBL")
            return False
        
        # Check GRBL status
        logger.info("Checking GRBL status...")
        status = controller.get_grbl_status()
        logger.info(f"GRBL Status: {status}")
        
        # Test unlock (in case of alarm state)
        logger.info("Unlocking GRBL...")
        controller._send_raw_gcode("$X")
        
        # Test basic commands
        logger.info("Testing basic G-code commands...")
        controller._send_raw_gcode("G21")  # Set units to mm
        controller._send_raw_gcode("G90")  # Absolute positioning
        controller._send_raw_gcode("G94")  # Feed rate mode
        
        # Small movement test (safe values)
        logger.info("Testing small movement...")
        controller._send_raw_gcode("G1 X1 Y1 F100")  # Move 1mm at slow speed
        time.sleep(2)
        controller._send_raw_gcode("G1 X0 Y0 F100")  # Return to origin
        
        logger.info("GRBL test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"GRBL test failed: {e}")
        return False
    finally:
        controller.disconnect()

def test_basic_movement():
    """Test basic movement functionality"""
    controller = ArduinoGCodeController('/dev/ttyUSB0')  # Updated for your port
    camera_system = CameraPositionController(controller)
    
    try:
        # Initialize
        if not camera_system.initialize_system():
            logger.error("Failed to initialize system")
            return False
        
        # Test movements
        test_positions = [
            (5, 5, 3),    # 5mm x, 5mm y, 3mm z
            (10, 5, 3),   # 10mm x, 5mm y, 3mm z
            (10, 10, 3),  # 10mm x, 10mm y, 3mm z
            (5, 10, 3)    # 5mm x, 10mm y, 3mm z
        ]
        
        for x, y, z in test_positions:
            camera_system.move_to_capture_position(x, y, z)
            time.sleep(2)
        
        # Return home
        camera_system.return_to_home()
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        return False
    finally:
        camera_system.shutdown()

if __name__ == "__main__":
    print("Camera Positioning G-code Controller (GRBL)")
    print("Available tests:")
    print("1. Test GRBL connection")
    print("2. Configure/View GRBL settings")
    print("3. Simple movement test (no homing)")
    print("4. Single axis test (X, Y, or Z)")
    print("5. Basic movement test (square pattern)")
    print("6. Exit")
    
    choice = input("Select test (1-6): ").strip()
    
    if choice == "1":
        print("Testing GRBL connection...")
        test_grbl_connection()
    elif choice == "2":
        print("Configuring/Viewing GRBL settings...")
        test_grbl_settings()
    elif choice == "3":
        print("Running simple movement test...")
        test_simple_movement()
    elif choice == "4":
        axis = input("Enter axis to test (X/Y/Z): ").strip().upper()
        if axis in ['X', 'Y', 'Z']:
            distance = float(input(f"Enter maximum {axis} distance (mm, default 20): ") or "20")
            steps = int(input("Enter number of steps (default 3): ") or "3")
            print(f"Running single {axis}-axis test...")
            test_single_axis(axis, distance, steps)
        else:
            print("Invalid axis. Please enter X, Y, or Z.")
    elif choice == "5":
        print("Running basic movement test...")
        test_basic_movement()
    elif choice == "6":
        print("Exiting...")
    else:
        print("Invalid choice. Running simple movement test...")
        test_simple_movement()