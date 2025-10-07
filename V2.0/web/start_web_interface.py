#!/usr/bin/env python3
"""
Complete 3D Scanner Web Interface Initialization Script
Provides both development and production modes for the web interface
"""

import sys
import os
import logging
import argparse
from pathlib import Path
from typing import Optional

# Add current directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from core.types import Position4D

def setup_logging(level: str = "INFO") -> None:
    """Setup comprehensive logging"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('web_interface.log', mode='a')
        ]
    )

def create_mock_orchestrator():
    """Create a mock orchestrator for development mode"""
    from datetime import datetime
    
    class MockOrchestrator:
        """Mock orchestrator for development and testing"""
        
        def __init__(self):
            self.current_scan = None
            self.motion_controller = MockMotionController()
            self.camera_manager = MockCameraManager()
            self.camera_adapter = MockCameraAdapter()  # Add camera adapter
            self.lighting_controller = MockLightingController()
            
        def create_grid_pattern(self, **kwargs):
            return f"MockGridPattern({kwargs})"
            
        def create_cylindrical_pattern(self, **kwargs):
            return f"MockCylindricalPattern({kwargs})"
            
        def start_scan(self, pattern, **kwargs):
            print(f"Mock: Starting scan with pattern {pattern}")
            return "mock_scan_id"
            
        def stop_scan(self):
            print("Mock: Stopping scan")
            
        def pause_scan(self):
            print("Mock: Pausing scan")
            
        def resume_scan(self):
            print("Mock: Resuming scan")
            
        def get_camera_status(self):
            """Mock camera status for development mode"""
            return {
                "camera_active": False,
                "last_capture": None,
                "preview_active": True,
                "available_cameras": ["camera_1", "camera_2"]
            }
    
    class MockCameraAdapter:
        """Mock camera adapter that matches the real adapter interface"""
        
        def __init__(self):
            self.controller = MockCameraController()
            
        def get_preview_frame(self, camera_id):
            # Generate a proper mock frame
            try:
                import cv2
                import numpy as np
                import time
                
                # Handle both int and string camera IDs
                display_id = camera_id
                if isinstance(camera_id, str) and camera_id.startswith('camera_'):
                    # Extract number from 'camera_1' for display
                    try:
                        display_id = int(camera_id.split('_')[1])
                    except (ValueError, IndexError):
                        display_id = camera_id
                elif isinstance(camera_id, int):
                    display_id = camera_id
                
                # Create a mock frame with camera info
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                
                # Add gradient background based on camera ID
                color_offset = hash(str(camera_id)) % 100
                for y in range(frame.shape[0]):
                    for x in range(frame.shape[1]):
                        frame[y, x] = [
                            int((255 - color_offset) * x / frame.shape[1]) % 256,  # Red gradient
                            int((255 + color_offset) * y / frame.shape[0]) % 256,  # Green gradient
                            (128 + color_offset) % 256  # Blue with offset
                        ]
                
                # Add camera ID text
                cv2.putText(frame, f'Camera {display_id} (Mock)', (50, 100), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 3)
                cv2.putText(frame, f'Camera {display_id} (Mock)', (48, 98), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
                
                # Add ID type info
                cv2.putText(frame, f'ID: {camera_id} ({type(camera_id).__name__})', (50, 150), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                
                # Add timestamp
                timestamp = time.strftime("%H:%M:%S.%f")[:-3]
                cv2.putText(frame, timestamp, (50, 200), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                
                # Add some dynamic content (moving circle)
                center_x = int(320 + 100 * np.sin(time.time() * 2 + hash(str(camera_id))))
                center_y = int(240 + 50 * np.cos(time.time() * 3 + hash(str(camera_id))))
                cv2.circle(frame, (center_x, center_y), 30, (0, 255, 255), -1)
                
                # Add frame counter
                frame_count = int(time.time() * 10) % 1000
                cv2.putText(frame, f'Frame: {frame_count}', (50, 250), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
                
                return frame
                
            except ImportError:
                # If OpenCV not available, return None
                return None
        
        def get_status(self):
            return {
                'cameras': ['camera_1', 'camera_2'], 
                'active_cameras': ['camera_1', 'camera_2'], 
                'initialized': True
            }
        
        def set_scanning_mode(self, is_scanning):
            print(f"Mock: Setting scanning mode to {is_scanning}")
    
    class MockCameraController:
        """Mock camera controller with cameras dict"""
        
        def __init__(self):
            self.cameras = {0: self, 1: self}  # Mock cameras for IDs 0 and 1
    
    class MockMotionController:
        def __init__(self):
            self._position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
            self.current_position = Position4D(x=0.0, y=0.0, z=0.0, c=0.0)  # Add this attribute
            
        def get_status(self):
            return {'status': 'ready', 'moving': False}
            
        def get_position(self):
            return self._position.copy()
            
        def move_relative(self, axis, distance):
            self._position[axis] += distance
            # Update current_position to match - properly handles both dict and Position4D
            if isinstance(self._position, dict):
                self.current_position = Position4D(
                    x=self._position['x'], 
                    y=self._position['y'], 
                    z=self._position['z'], 
                    c=self._position['c']
                )
            print(f"Mock: Moving {axis} by {distance}mm to {self._position[axis]}, C-axis now at {self.current_position.c}°")
            return True
            
        def move_to_position(self, position):
            # Handle both dict and Position4D input
            if isinstance(position, Position4D):
                self._position['x'] = position.x
                self._position['y'] = position.y
                self._position['z'] = position.z
                self._position['c'] = position.c
                self.current_position = position
            else:
                self._position.update(position)
                self.current_position = Position4D(
                    x=self._position.get('x', 0.0), 
                    y=self._position.get('y', 0.0), 
                    z=self._position.get('z', 0.0), 
                    c=self._position.get('c', 0.0)
                )
            print(f"Mock: Moving to position x={self.current_position.x}, y={self.current_position.y}, z={self.current_position.z}, c={self.current_position.c}°")
            return True
            
        def home_axes(self, axes):
            for axis in axes:
                self._position[axis] = 0.0
            # Update current_position to match
            self.current_position = Position4D(
                x=self._position['x'], 
                y=self._position['y'], 
                z=self._position['z'], 
                c=self._position['c']
            )
            print(f"Mock: Homing axes {axes}")
            return True
            
        def refresh_connection_status(self):
            """Mock connection status refresh"""
            return True  # Always connected in mock mode
            
        def is_connected(self):
            """Mock connection check"""
            return True  # Always connected in mock mode
            
        @property 
        def _connected(self):
            """Mock connection property"""
            return True  # Always connected in mock mode
            
        def emergency_stop(self):
            print("Mock: EMERGENCY STOP!")
    
    class MockCameraManager:
        def get_status(self):
            return {
                'cameras': ['camera_1', 'camera_2'],
                'active_cameras': ['camera_1', 'camera_2'],
                'initialized': True
            }
            
        def capture_image(self, camera_id, filename):
            print(f"Mock: Capturing image from {camera_id} to {filename}")
            
        def get_preview_frame(self, camera_id):
            # Generate a proper mock frame instead of returning None
            try:
                import cv2
                import numpy as np
                import time
                
                # Create a mock frame with camera info
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
                
                # Add gradient background
                for y in range(frame.shape[0]):
                    for x in range(frame.shape[1]):
                        frame[y, x] = [
                            int(255 * x / frame.shape[1]),  # Red gradient
                            int(255 * y / frame.shape[0]),  # Green gradient
                            128  # Blue constant
                        ]
                
                # Add camera ID text
                cv2.putText(frame, f'Mock Camera {camera_id}', (50, 100), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
                
                # Add timestamp
                timestamp = time.strftime("%H:%M:%S")
                cv2.putText(frame, timestamp, (50, 200), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                
                # Add some dynamic content (moving circle)
                center_x = int(320 + 100 * np.sin(time.time() * 2))
                center_y = int(240 + 50 * np.cos(time.time() * 2))
                cv2.circle(frame, (center_x, center_y), 30, (0, 255, 255), -1)
                
                return frame
                
            except ImportError:
                # If OpenCV not available, return None
                return None
    
    class MockLightingController:
        def get_status(self):
            return {
                'zones': ['zone_1', 'zone_2', 'zone_3', 'zone_4'],
                'status': 'ready',
                'initialized': True
            }
        
        def get_sync_status(self, zone_id=None):
            """Synchronous status method for web interface compatibility"""
            return {
                'zones': {'zone_1': {}, 'zone_2': {}, 'zone_3': {}, 'zone_4': {}},
                'status': 'ready',
                'initialized': True
            }
            
        def flash_all_zones(self, settings):
            print(f"Mock: Flashing all zones with settings {settings}")
            
        def flash_zone(self, zone, settings):
            print(f"Mock: Flashing {zone} with settings {settings}")
            
        def turn_off_all(self):
            print("Mock: Turning off all lighting")
    
    return MockOrchestrator()

def initialize_real_orchestrator():
    """Initialize the real scanner orchestrator with optional GPIO"""
    import os
    
    # Skip hardware initialization if this is Flask's debug reloader process
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        print("⚠️  Skipping hardware initialization in debug reloader process")
        return create_mock_orchestrator()
    
    try:
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        import asyncio
        
        # Create config manager with existing scanner config
        config_file = Path(__file__).parent.parent / "config" / "scanner_config.yaml"
        
        # Use existing config file if it exists, otherwise create a minimal one
        config_file.parent.mkdir(exist_ok=True)
        if not config_file.exists():
            with open(config_file, 'w') as f:
                f.write("""
# Hardware Configuration for 3D Scanner
system:
  name: "3D Scanner Hardware Mode"
  simulation_mode: false
  log_level: "INFO"

motion:
  controller:
    type: "fluidnc"
    connection: "usb"
    port: "/dev/ttyUSB0"
    baudrate: 115200
    timeout: 10.0
  axes:
    x_axis:
      type: "linear"
      units: "mm"
      min_limit: 0.0
      max_limit: 200.0
      home_position: 0.0
      max_feedrate: 1000.0
      steps_per_mm: 800.0
      has_limits: true
      homing_required: true
    y_axis:
      type: "linear"
      units: "mm"
      min_limit: 0.0
      max_limit: 200.0
      home_position: 0.0
      max_feedrate: 1000.0
      steps_per_mm: 800.0
      has_limits: true
      homing_required: true
    z_axis:
      type: "rotational"
      units: "degrees"
      min_limit: -360.0
      max_limit: 360.0
      home_position: 0.0
      max_feedrate: 500.0
      steps_per_degree: 10.0
      continuous_rotation: true
    c_axis:
      type: "linear"
      units: "degrees"
      min_limit: -90.0
      max_limit: 90.0
      home_position: 0.0
      max_feedrate: 300.0
      steps_per_degree: 5.0

cameras:
  camera_1:
    port: 0
    resolution: [1920, 1080]
    interface: "libcamera"
    enabled: true
  camera_2:
    port: 1
    resolution: [1920, 1080]
    interface: "libcamera"
    enabled: true

lighting:
  led_zones:
    zone_1:
      gpio_pin: 18
      max_intensity: 80
      name: "Front Left"
    zone_2:
      gpio_pin: 19
      max_intensity: 80
      name: "Front Right"
  controller:
    type: "gpio_pwm"
    enabled: false  # Disabled for initial testing
    
storage:
  base_path: "/home/user/scanner_data"
  backup_enabled: true
""")
        
        config_manager = ConfigManager(config_file)
        
        # Create orchestrator
        orchestrator = ScanOrchestrator(config_manager)
        
        print("⚠️  Note: GPIO/LED lighting disabled for initial testing")
        
        # Initialize all subsystems asynchronously
        print("Initializing scanner subsystems...")
        
        # Run initialization in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(orchestrator.initialize())
        finally:
            loop.close()
        
        print("✅ Real scanner orchestrator initialized (motion + cameras)")
        return orchestrator
        
    except ImportError as e:
        print(f"❌ Could not import scanner modules: {e}")
        print(f"� ImportError details: {type(e).__name__}: {e}")
        print("�💡 Falling back to mock mode")
        return create_mock_orchestrator()
        
    except Exception as e:
        print(f"❌ Failed to initialize real orchestrator: {e}")
        print(f"🔍 Exception details: {type(e).__name__}: {e}")
        import traceback
        print(f"🔍 Full traceback:\n{traceback.format_exc()}")
        print("💡 Falling back to mock mode")
        return create_mock_orchestrator()

def start_web_interface(
    orchestrator=None,
    host: str = "0.0.0.0",
    port: int = 5000,
    debug: bool = False,
    production: bool = False
):
    """Start the web interface with orchestrator"""
    try:
        from web_interface import ScannerWebInterface
        
        # Create web interface
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        
        # For hardware mode, disable Flask's auto-reloader to prevent camera conflicts
        use_reloader = debug and orchestrator.__class__.__name__ == 'MockOrchestrator'
        
        # Start server
        print(f"🚀 Starting web interface on http://{host}:{port}")
        if production and not debug:
            print("🏭 Production mode with Gunicorn WSGI server")
        elif use_reloader:
            print("🔄 Debug mode with auto-reloader enabled (mock mode)")
        else:
            print("🔧 Debug mode without auto-reloader (hardware mode)")
            
        web_interface.start_web_server(host=host, port=port, debug=debug, use_reloader=use_reloader, production=production)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down web interface...")
        if hasattr(web_interface, 'stop_web_server'):
            web_interface.stop_web_server()
            
    except Exception as e:
        print(f"❌ Failed to start web interface: {e}")
        raise

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="3D Scanner Web Interface")
    parser.add_argument(
        "--mode",
        choices=["production", "development", "mock", "hardware"],
        default="development",
        help="Operating mode (default: development)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind to (default: 5000)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    print("=" * 80)
    print("🔬 3D Scanner Web Interface")
    print("=" * 80)
    print(f"Mode: {args.mode}")
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Debug: {args.debug}")
    print(f"Log Level: {args.log_level}")
    print("=" * 80)
    
    # Initialize orchestrator based on mode
    orchestrator = None
    
    if args.mode == "production":
        print("🏭 Production Mode: Initializing real hardware...")
        orchestrator = initialize_real_orchestrator()
        
    elif args.mode == "development":
        print("🛠️  Development Mode: Attempting real hardware with mock fallback...")
        orchestrator = initialize_real_orchestrator()
        
    elif args.mode == "hardware":
        print("🔧 Hardware Mode: Real hardware components only...")
        orchestrator = initialize_real_orchestrator()
        
    elif args.mode == "mock":
        print("🎭 Mock Mode: Using simulated hardware...")
        orchestrator = create_mock_orchestrator()
    
    # Start web interface
    try:
        start_web_interface(
            orchestrator=orchestrator,
            host=args.host,
            port=args.port,
            debug=args.debug,
            production=(args.mode == "production")
        )
    except Exception as e:
        logger.error(f"Failed to start web interface: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    """
    Usage Examples:
    
    # Development mode with real hardware fallback to mock
    python start_web_interface.py --mode development --debug
    
    # Production mode with real hardware only
    python start_web_interface.py --mode production --host 0.0.0.0 --port 80
    
    # Mock mode for pure testing
    python start_web_interface.py --mode mock --debug --log-level DEBUG
    
    # Custom host and port
    python start_web_interface.py --host 192.168.1.100 --port 8080
    """
    exit(main())