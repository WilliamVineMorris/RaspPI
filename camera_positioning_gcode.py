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
    
    def move_to_point(self, target: Point, feedrate: float = 1000, movement_type: MovementType = MovementType.LINEAR) -> bool:
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
            'c': {'min': 0, 'max': 180}       # C-axis: 0-180mm (0-180°, center=90mm=0° tilt)
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
            return 60.0  # Homing can take up to 60 seconds
        elif gcode_upper.startswith("G1") or gcode_upper.startswith("G0"):  # Movement commands
            return 30.0  # Movement commands can take longer
        elif gcode_upper.startswith("?"):  # Status query
            return 2.0   # Status should be quick
        elif gcode_upper.startswith("$X"):  # Unlock command
            return 10.0  # Unlock might take a moment
        else:
            return self.timeout  # Default timeout for other commands
    
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
            
            # Wait for response - FluidNC sends "ok" when movement is complete
            start_time = time.time()
            response_buffer = ""
            
            while True:
                if self.serial_connection.in_waiting > 0:
                    response = self.serial_connection.readline().decode().strip()
                    
                    # Skip empty responses
                    if not response:
                        continue
                        
                    logger.debug(f"FluidNC response: {response}")
                    
                    # Handle different FluidNC response types
                    if response == "ok":
                        logger.debug(f"Command completed: {gcode}")
                        return True
                    elif response.startswith("[MSG:"):
                        # FluidNC info message - continue waiting for "ok"
                        logger.info(f"FluidNC message: {response}")
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
                        return True
                    else:
                        # Other responses - log but continue waiting for "ok"
                        logger.debug(f"FluidNC other response: {response}")
                        continue
                
                # Timeout check
                elapsed = time.time() - start_time
                if elapsed > command_timeout:
                    logger.error(f"Command timeout after {elapsed:.1f}s (limit: {command_timeout}s): {gcode}")
                    return False
                    
                time.sleep(0.05)  # Reduced sleep for better responsiveness
                
        except Exception as e:
            logger.error(f"Error sending G-code '{gcode}': {e}")
            return False
    
    def validate_position(self, point: Point) -> bool:
        """Validate that position is within axis limits"""
        if not (self.axis_limits['x']['min'] <= point.x <= self.axis_limits['x']['max']):
            logger.error(f"X position {point.x} outside limits [{self.axis_limits['x']['min']}, {self.axis_limits['x']['max']}]")
            return False
        if not (self.axis_limits['y']['min'] <= point.y <= self.axis_limits['y']['max']):
            logger.error(f"Y position {point.y} outside limits [{self.axis_limits['y']['min']}, {self.axis_limits['y']['max']}]")
            return False
        if not (self.axis_limits['z']['min'] <= point.z <= self.axis_limits['z']['max']):
            logger.error(f"Z position {point.z} outside limits [{self.axis_limits['z']['min']}, {self.axis_limits['z']['max']}]")
            return False
        if not (self.axis_limits['c']['min'] <= point.c <= self.axis_limits['c']['max']):
            logger.error(f"C position {point.c} outside limits [{self.axis_limits['c']['min']}, {self.axis_limits['c']['max']}]")
            return False
        return True
    
    def move_to_point(self, point: Point, feedrate: float = 500) -> bool:
        """Move to specified 4DOF point with validation"""
        if not self.validate_position(point):
            return False
            
        # Build G-code command for 4DOF movement
        gcode = f"G1 X{point.x:.3f} Y{point.y:.3f} Z{point.z:.3f} C{point.c:.3f} F{feedrate}"
        
        success = self._send_raw_gcode(gcode)
        if success:
            self.current_position = Point(point.x, point.y, point.z, point.c)
            logger.info(f"Moved to X:{point.x:.1f} Y:{point.y:.1f} Z:{point.z:.1f} C:{point.c:.1f}")
        
        return success
    
    def home_axes(self) -> bool:
        """Home configured axes with proper timeout handling"""
        logger.info("Starting FluidNC homing sequence...")
        
        # Clear any alarm state first
        self._send_raw_gcode("$X")
        time.sleep(0.5)
        
        # Start homing - this can take up to 60 seconds
        logger.info("Homing in progress - this may take up to 60 seconds...")
        success = self._send_raw_gcode("$H")
        
        if success:
            logger.info("Homing completed successfully")
            # Reset current position after homing
            self.current_position = Point(0, 0, 0, 0)
        else:
            logger.error("Homing failed or timed out")
            
        return success
    
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
        """Check if system is homed by analyzing status"""
        status = self.get_status()
        
        if status.startswith('<') and status.endswith('>'):
            # Parse FluidNC status: <Idle|MPos:0.000,0.000,0.000,0.000|FS:0,0|WCO:0.000,0.000,0.000,0.000>
            parts = status[1:-1].split('|')  # Remove < > and split by |
            
            for part in parts:
                # Check for alarm state
                if part.startswith('Alarm'):
                    return False
                # Check for homing state
                if part == 'Home':
                    return True
                # If we have WCO (Work Coordinate Offset), system is likely homed
                if part.startswith('WCO:'):
                    return True
            
            # If status shows Idle/Run/Hold without alarm, consider it homed
            state = parts[0] if parts else ""
            return state in ['Idle', 'Run', 'Hold', 'Jog']
        
        return False
    
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
            # Convert tilt angle to C-axis position: angle + 90 = position
            # -90° → 0mm, 0° → 90mm, +90° → 180mm
            c_position = c_angle + 90
            
            # Validate C-axis limits (0-180mm as per ConfigV1.2)
            if 0 <= c_position <= 180:
                path.append(Point(base_position.x, base_position.y, base_position.z, c_position))
            else:
                logger.warning(f"C-axis angle {c_angle}° (position {c_position}mm) outside limits [0-180mm], skipping")
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
                c = c_angle + 90  # Convert tilt angle to C-axis position (ConfigV1.2 format)
                
                # Validate position before adding to path
                test_point = Point(x, y, z, c)
                if hasattr(self.controller, 'validate_position'):
                    if self.controller.validate_position(test_point):
                        path.append(test_point)
                else:
                    # For backward compatibility with ArduinoGCodeController
                    path.append(Point(x, y, z, c))
        
        return path
    
    def execute_path(self, path: List[Point], feedrate: float = 1000, 
                    pause_between_points: float = 0.1) -> bool:
        """Execute a planned path"""
        if not self.controller.is_connected:
            logger.error("Controller not connected")
            return False
        
        logger.info(f"Executing path with {len(path)} points")
        
        for i, point in enumerate(path):
            success = self.controller.move_to_point(point, feedrate)
            if not success:
                logger.error(f"Failed to move to point {i}: {point}")
                return False
            
            if pause_between_points > 0:
                time.sleep(pause_between_points)
            
            logger.debug(f"Moved to point {i}: X{point.x:.3f} Y{point.y:.3f} Z{point.z:.3f}")
        
        logger.info("Path execution completed")
        return True

class CameraPositionController:
    def __init__(self, controller):
        """Initialize with either ArduinoGCodeController or FluidNCController"""
        self.controller = controller
        self.planner = PathPlanner(controller)
        self.safe_height = 10.0  # Safe Z height for movements
        self.default_c_position = 90.0  # Default camera position (90mm = 0° tilt in ConfigV1.2)
        
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
                                c: float = None, feedrate: float = 1000) -> bool:
        """Move camera to specific 4DOF capture position
        
        Args:
            x, y: Linear position in mm
            z: Rotation angle in degrees (optional)
            c: Camera tilt angle in degrees ±90° (optional, will be converted to 0-180mm)
            feedrate: Movement speed
        """
        if z is None:
            z = self.safe_height
        if c is None:
            c_position = self.default_c_position  # Use default position (90mm = 0° tilt)
        else:
            c_position = c + 90  # Convert tilt angle to position: -90° → 0mm, 0° → 90mm, +90° → 180mm
        
        target = Point(x, y, z, c_position)
        logger.info(f"Moving to 4DOF capture position: X{x} Y{y} Z{z}° C{c}° (pos:{c_position})")
        
        return self.controller.move_to_point(target, feedrate)
    
    def scan_area(self, corner1: Point, corner2: Point, grid_size: Tuple[int, int] = (5, 5),
                  capture_height: float = None, c_angle: float = None, 
                  feedrate: float = 500) -> bool:
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
        return self.controller.move_to_point(Point(0, 0, 0, 90), feedrate=500)
    
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