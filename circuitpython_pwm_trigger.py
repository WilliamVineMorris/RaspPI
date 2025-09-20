#!/usr/bin/env python3
"""
CircuitPython PWM Trigger Controller
Sends serial commands to a CircuitPython board to trigger PWM signals at 300Hz
on GPIO pins 4 and 5 with 10% duty cycle, then back to zero.
"""

import serial
import time
import json
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class PWMConfig:
    """PWM configuration parameters"""
    frequency: int = 300      # 300Hz
    duty_cycle: float = 10.0  # 10% duty cycle
    gpio_pins: Optional[list] = None    # GPIO pins [4, 5]
    duration_ms: int = 100   # Duration to keep PWM active (ms)
    
    def __post_init__(self):
        if self.gpio_pins is None:
            self.gpio_pins = [4, 5]

class CircuitPythonPWMController:
    def __init__(self, port: str = '/dev/ttyACM0', baudrate: int = 115200, timeout: float = 2.0):
        """
        Initialize PWM controller for CircuitPython board
        
        Args:
            port: Serial port for CircuitPython board (e.g., '/dev/ttyACM0', 'COM3')
            baudrate: Serial communication speed
            timeout: Serial communication timeout
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_connection = None
        self.is_connected = False
        
    def connect(self) -> bool:
        """Establish connection to CircuitPython board"""
        try:
            logger.info(f"Connecting to CircuitPython board on {self.port}...")
            
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            
            # Wait for connection to stabilize
            time.sleep(2)
            
            # Clear any existing data
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()
            
            # Test connection with ping
            if self.ping_board():
                self.is_connected = True
                logger.info("Successfully connected to CircuitPython board")
                return True
            else:
                logger.error("Failed to establish communication with board")
                return False
                
        except serial.SerialException as e:
            logger.error(f"Serial connection error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error connecting: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from CircuitPython board"""
        if self.serial_connection and self.serial_connection.is_open:
            logger.info("Disconnecting from CircuitPython board...")
            self.serial_connection.close()
            self.is_connected = False
            logger.info("Disconnected")
    
    def send_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send JSON command to CircuitPython board and get response
        
        Args:
            command: Dictionary command to send
            
        Returns:
            Response dictionary from board
        """
        if not self.is_connected or not self.serial_connection:
            return {"status": "error", "message": "Not connected to board"}
        
        try:
            # Send command as JSON
            command_json = json.dumps(command) + '\n'
            self.serial_connection.write(command_json.encode())
            logger.debug(f"Sent command: {command}")
            
            # Wait for response
            response_line = self.serial_connection.readline().decode().strip()
            
            if response_line:
                try:
                    response = json.loads(response_line)
                    logger.debug(f"Received response: {response}")
                    return response
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON response: {response_line}")
                    return {"status": "error", "message": f"Invalid response: {response_line}"}
            else:
                logger.warning("No response received from board")
                return {"status": "error", "message": "No response from board"}
                
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            return {"status": "error", "message": str(e)}
    
    def ping_board(self) -> bool:
        """Test communication with board"""
        ping_command = {"action": "ping"}
        response = self.send_command(ping_command)
        return response.get("status") == "ok" and response.get("message") == "pong"
    
    def start_pwm(self, config: PWMConfig) -> bool:
        """
        Start PWM on specified pins
        
        Args:
            config: PWM configuration
            
        Returns:
            True if successful, False otherwise
        """
        command = {
            "action": "start_pwm",
            "pins": config.gpio_pins,
            "frequency": config.frequency,
            "duty_cycle": config.duty_cycle
        }
        
        response = self.send_command(command)
        success = response.get("status") == "ok"
        
        if success:
            logger.info(f"Started PWM on pins {config.gpio_pins} at {config.frequency}Hz, {config.duty_cycle}% duty")
        else:
            logger.error(f"Failed to start PWM: {response.get('message', 'Unknown error')}")
            
        return success
    
    def stop_pwm(self, pins: list) -> bool:
        """
        Stop PWM on specified pins
        
        Args:
            pins: List of GPIO pins to stop PWM on
            
        Returns:
            True if successful, False otherwise
        """
        command = {
            "action": "stop_pwm",
            "pins": pins
        }
        
        response = self.send_command(command)
        success = response.get("status") == "ok"
        
        if success:
            logger.info(f"Stopped PWM on pins {pins}")
        else:
            logger.error(f"Failed to stop PWM: {response.get('message', 'Unknown error')}")
            
        return success
    
    def trigger_pwm_pulse(self, config: PWMConfig) -> bool:
        """
        Trigger a PWM pulse for specified duration then stop
        
        Args:
            config: PWM configuration including duration
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Triggering PWM pulse: {config.frequency}Hz, {config.duty_cycle}% for {config.duration_ms}ms")
        
        # Start PWM
        if not self.start_pwm(config):
            return False
        
        # Wait for specified duration
        time.sleep(config.duration_ms / 1000.0)
        
        # Stop PWM (ensure gpio_pins is not None)
        pins = config.gpio_pins if config.gpio_pins is not None else [4, 5]
        return self.stop_pwm(pins)
    
    def get_board_status(self) -> Dict[str, Any]:
        """Get current board status"""
        command = {"action": "status"}
        return self.send_command(command)

def create_circuitpython_code() -> str:
    """
    Generate CircuitPython code to run on the microcontroller board
    This code should be saved as code.py on the CircuitPython board
    """
    return '''
import json
import time
import board
import pwmio
import digitalio
from microcontroller import pin

# PWM objects dictionary
pwm_pins = {}

def setup_pwm(pin_num, frequency):
    """Setup PWM on specified pin"""
    try:
        pin_obj = getattr(board, f"GP{pin_num}")  # For Pico: GP4, GP5
        pwm = pwmio.PWMOut(pin_obj, frequency=frequency, duty_cycle=0)
        pwm_pins[pin_num] = pwm
        return True
    except Exception as e:
        print(f"Error setting up PWM on pin {pin_num}: {e}")
        return False

def set_duty_cycle(pin_num, duty_percent):
    """Set duty cycle as percentage (0-100)"""
    if pin_num in pwm_pins:
        # Convert percentage to 16-bit value (0-65535)
        duty_value = int((duty_percent / 100.0) * 65535)
        pwm_pins[pin_num].duty_cycle = duty_value
        return True
    return False

def stop_pwm(pin_num):
    """Stop PWM on specified pin"""
    if pin_num in pwm_pins:
        pwm_pins[pin_num].duty_cycle = 0
        pwm_pins[pin_num].deinit()
        del pwm_pins[pin_num]
        return True
    return False

def process_command(command):
    """Process incoming JSON command"""
    try:
        action = command.get("action")
        
        if action == "ping":
            return {"status": "ok", "message": "pong"}
        
        elif action == "start_pwm":
            pins = command.get("pins", [])
            frequency = command.get("frequency", 300)
            duty_cycle = command.get("duty_cycle", 10.0)
            
            success = True
            for pin_num in pins:
                if not setup_pwm(pin_num, frequency):
                    success = False
                    break
                if not set_duty_cycle(pin_num, duty_cycle):
                    success = False
                    break
            
            if success:
                return {"status": "ok", "message": f"PWM started on pins {pins}"}
            else:
                return {"status": "error", "message": "Failed to start PWM"}
        
        elif action == "stop_pwm":
            pins = command.get("pins", [])
            
            success = True
            for pin_num in pins:
                if not stop_pwm(pin_num):
                    success = False
            
            if success:
                return {"status": "ok", "message": f"PWM stopped on pins {pins}"}
            else:
                return {"status": "error", "message": "Failed to stop PWM"}
        
        elif action == "status":
            active_pins = list(pwm_pins.keys())
            return {
                "status": "ok", 
                "active_pins": active_pins,
                "message": f"PWM active on pins: {active_pins}"
            }
        
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"status": "error", "message": f"Command processing error: {str(e)}"}

# Main loop
print("CircuitPython PWM Controller Ready")
print("Waiting for JSON commands...")

while True:
    try:
        # Read line from serial
        line = input().strip()
        if line:
            # Parse JSON command
            command = json.loads(line)
            
            # Process command
            response = process_command(command)
            
            # Send JSON response
            print(json.dumps(response))
    
    except json.JSONDecodeError:
        print(json.dumps({"status": "error", "message": "Invalid JSON"}))
    except Exception as e:
        print(json.dumps({"status": "error", "message": f"Error: {str(e)}"}))
'''

def main():
    """Main test function"""
    print("=== CircuitPython PWM Trigger Controller ===")
    print()
    
    # Ask user for serial port
    port = input("Enter CircuitPython board serial port (e.g., /dev/ttyACM0 or COM3): ").strip()
    if not port:
        port = "/dev/ttyACM0"  # Default for Linux
    
    # Create controller
    controller = CircuitPythonPWMController(port=port)
    
    try:
        # Connect to board
        if not controller.connect():
            print("Failed to connect to CircuitPython board.")
            print("Make sure:")
            print("1. Board is connected via USB")
            print("2. CircuitPython is installed")
            print("3. The code.py file contains the PWM controller code")
            print("4. Correct serial port is specified")
            return
        
        # Create PWM configuration
        pwm_config = PWMConfig(
            frequency=300,
            duty_cycle=10.0,
            gpio_pins=[4, 5],
            duration_ms=1000
        )
        
        # Test menu
        while True:
            print("\nPWM Controller Options:")
            print("1. Single PWM pulse (300Hz, 10%, 1s)")
            print("2. Custom PWM pulse")
            print("3. Start continuous PWM")
            print("4. Stop all PWM")
            print("5. Board status")
            print("6. Generate CircuitPython code")
            print("7. Exit")
            
            choice = input("Enter choice (1-7): ").strip()
            
            if choice == '1':
                print("Triggering PWM pulse...")
                success = controller.trigger_pwm_pulse(pwm_config)
                print("✅ PWM pulse completed!" if success else "❌ PWM pulse failed!")
                
            elif choice == '2':
                try:
                    freq = int(input("Enter frequency (Hz, default 300): ") or "300")
                    duty = float(input("Enter duty cycle (%, default 10): ") or "10")
                    duration = int(input("Enter duration (ms, default 1000): ") or "1000")
                    pins_input = input("Enter GPIO pins (comma-separated, default 4,5): ") or "4,5"
                    pins = [int(p.strip()) for p in pins_input.split(',')]
                    
                    custom_config = PWMConfig(
                        frequency=freq,
                        duty_cycle=duty,
                        gpio_pins=pins,
                        duration_ms=duration
                    )
                    
                    print(f"Triggering custom PWM: {freq}Hz, {duty}%, {duration}ms on pins {pins}")
                    success = controller.trigger_pwm_pulse(custom_config)
                    print("✅ Custom PWM pulse completed!" if success else "❌ Custom PWM pulse failed!")
                    
                except ValueError:
                    print("❌ Invalid input values!")
                
            elif choice == '3':
                print("Starting continuous PWM...")
                success = controller.start_pwm(pwm_config)
                print("✅ PWM started!" if success else "❌ Failed to start PWM!")
                
            elif choice == '4':
                print("Stopping all PWM...")
                success = controller.stop_pwm([4, 5])
                print("✅ PWM stopped!" if success else "❌ Failed to stop PWM!")
                
            elif choice == '5':
                status = controller.get_board_status()
                print(f"Board status: {status}")
                
            elif choice == '6':
                print("\n" + "="*50)
                print("CircuitPython Code (save as code.py on board):")
                print("="*50)
                print(create_circuitpython_code())
                print("="*50)
                
            elif choice == '7':
                break
                
            else:
                print("Invalid choice. Please try again.")
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        controller.disconnect()

if __name__ == "__main__":
    main()