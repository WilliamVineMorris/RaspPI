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
        
    def connect(self) -> bool:
        """Establish serial connection to Arduino with GRBL"""
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
            
            # Check GRBL version
            self._send_raw_gcode("$$")  # Get GRBL settings
            
            # Unlock GRBL (disable alarm state)
            self._send_raw_gcode("$X")
            
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
            
            # Wait for response - GRBL can send multiple types
            response = self.serial_connection.readline().decode().strip()
            
            # Handle different GRBL response types
            if response == "ok":
                logger.debug(f"Command acknowledged: {gcode}")
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
                # Empty response - might be normal for some commands
                logger.debug(f"Empty response for: {gcode}")
                return True
            else:
                logger.warning(f"Unexpected GRBL response: {response}")
                return True  # Continue anyway for unknown responses
                
        except Exception as e:
            logger.error(f"Error sending G-code: {e}")
            return False
    
    def move_to_point(self, target: Point, feedrate: float = 1000, movement_type: MovementType = MovementType.LINEAR) -> bool:
        """Move to a specific point"""
        gcode = f"{movement_type.value} X{target.x:.3f} Y{target.y:.3f} Z{target.z:.3f} F{feedrate}"
        
        if self._send_raw_gcode(gcode):
            self.current_position = target
            return True
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
    
    def set_relative_mode(self):
        """Set to relative positioning mode"""
        return self._send_raw_gcode("G91")
    
    def set_absolute_mode(self):
        """Set to absolute positioning mode"""
        return self._send_raw_gcode("G90")

class PathPlanner:
    def __init__(self, controller: ArduinoGCodeController):
        self.controller = controller
        self.current_position = Point(0, 0, 0)
        
    def generate_linear_path(self, start: Point, end: Point, steps: int = 10) -> List[Point]:
        """Generate linear interpolation between two points"""
        path = []
        for i in range(steps + 1):
            t = i / steps
            x = start.x + t * (end.x - start.x)
            y = start.y + t * (end.y - start.y)
            z = start.z + t * (end.z - start.z)
            path.append(Point(x, y, z))
        return path
    
    def generate_circular_path(self, center: Point, radius: float, start_angle: float = 0, 
                             end_angle: float = 360, steps: int = 36) -> List[Point]:
        """Generate circular path around center point"""
        path = []
        angle_step = math.radians(end_angle - start_angle) / steps
        
        for i in range(steps + 1):
            angle = math.radians(start_angle) + i * angle_step
            x = center.x + radius * math.cos(angle)
            y = center.y + radius * math.sin(angle)
            path.append(Point(x, y, center.z))
        
        return path
    
    def generate_grid_scan_path(self, min_point: Point, max_point: Point, 
                               x_steps: int = 10, y_steps: int = 10) -> List[Point]:
        """Generate zigzag scanning pattern over rectangular area"""
        path = []
        x_step = (max_point.x - min_point.x) / x_steps
        y_step = (max_point.y - min_point.y) / y_steps
        
        for j in range(y_steps + 1):
            y = min_point.y + j * y_step
            
            if j % 2 == 0:  # Even rows: left to right
                for i in range(x_steps + 1):
                    x = min_point.x + i * x_step
                    path.append(Point(x, y, min_point.z))
            else:  # Odd rows: right to left
                for i in range(x_steps, -1, -1):
                    x = min_point.x + i * x_step
                    path.append(Point(x, y, min_point.z))
        
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
    def __init__(self, gcode_controller: ArduinoGCodeController):
        self.controller = gcode_controller
        self.planner = PathPlanner(gcode_controller)
        self.safe_height = 10.0  # Reduced safe Z height for safer testing
        
    def initialize_system(self) -> bool:
        """Initialize the camera positioning system"""
        if not self.controller.connect():
            return False
        
        logger.info("Initializing camera positioning system...")
        
        # Try to home, but don't fail if homing isn't available
        home_success = self.controller.home_axes()
        if home_success:
            logger.info("System initialized successfully")
        else:
            logger.warning("Homing not available, but system is connected")
        
        return True  # Continue even if homing fails
    
    def move_to_capture_position(self, x: float, y: float, z: float = None, 
                                feedrate: float = 1000) -> bool:
        """Move camera to specific capture position"""
        if z is None:
            z = self.safe_height
        
        target = Point(x, y, z)
        logger.info(f"Moving to capture position: X{x} Y{y} Z{z}")
        
        return self.controller.move_to_point(target, feedrate)
    
    def scan_area(self, corner1: Point, corner2: Point, grid_size: Tuple[int, int] = (5, 5),
                  capture_height: float = None, feedrate: float = 500) -> bool:
        """Perform systematic scan of rectangular area"""
        if capture_height is None:
            capture_height = self.safe_height
        
        # Define scan area
        min_point = Point(min(corner1.x, corner2.x), min(corner1.y, corner2.y), capture_height)
        max_point = Point(max(corner1.x, corner2.x), max(corner1.y, corner2.y), capture_height)
        
        # Generate scan path
        scan_path = self.planner.generate_grid_scan_path(min_point, max_point, 
                                                        grid_size[0], grid_size[1])
        
        # Execute scan
        logger.info(f"Starting area scan: {len(scan_path)} positions")
        return self.planner.execute_path(scan_path, feedrate, pause_between_points=0.5)
    
    def circular_scan(self, center: Point, radius: float, num_positions: int = 8,
                     capture_height: float = None, feedrate: float = 500) -> bool:
        """Perform circular scan around center point"""
        if capture_height is None:
            capture_height = self.safe_height
        
        center.z = capture_height
        
        # Generate circular path
        circular_path = self.planner.generate_circular_path(center, radius, 0, 360, num_positions)
        
        # Execute circular scan
        logger.info(f"Starting circular scan: {len(circular_path)} positions")
        return self.planner.execute_path(circular_path, feedrate, pause_between_points=1.0)
    
    def return_to_home(self) -> bool:
        """Return camera to origin position"""
        logger.info("Returning to origin position")
        return self.controller.move_to_point(Point(0, 0, 0), feedrate=500)
    
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
        """Safely shutdown the positioning system"""
        logger.info("Shutting down camera positioning system")
        self.return_to_home()
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
            Point(10, 0, 0),   # Move X 10mm
            Point(10, 10, 0),  # Move Y 10mm
            Point(0, 10, 0),   # Move X back to 0
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
            (50, 50, 30),
            (100, 50, 30),
            (100, 100, 30),
            (50, 100, 30)
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
    print("2. Simple movement test (no homing)")
    print("3. Single axis test (X, Y, or Z)")
    print("4. Basic movement test (square pattern)")
    print("5. Exit")
    
    choice = input("Select test (1-5): ").strip()
    
    if choice == "1":
        print("Testing GRBL connection...")
        test_grbl_connection()
    elif choice == "2":
        print("Running simple movement test...")
        test_simple_movement()
    elif choice == "3":
        axis = input("Enter axis to test (X/Y/Z): ").strip().upper()
        if axis in ['X', 'Y', 'Z']:
            distance = float(input(f"Enter maximum {axis} distance (mm, default 20): ") or "20")
            steps = int(input("Enter number of steps (default 3): ") or "3")
            print(f"Running single {axis}-axis test...")
            test_single_axis(axis, distance, steps)
        else:
            print("Invalid axis. Please enter X, Y, or Z.")
    elif choice == "4":
        print("Running basic movement test...")
        test_basic_movement()
    elif choice == "5":
        print("Exiting...")
    else:
        print("Invalid choice. Running simple movement test...")
        test_simple_movement()