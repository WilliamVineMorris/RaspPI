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
    
    class MockMotionController:
        def __init__(self):
            self._position = {'x': 0.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
            
        def get_status(self):
            return {'status': 'ready', 'moving': False}
            
        def get_position(self):
            return self._position.copy()
            
        def move_relative(self, axis, distance):
            self._position[axis] += distance
            print(f"Mock: Moving {axis} by {distance}mm to {self._position[axis]}")
            return True
            
        def move_to_position(self, position):
            self._position.update(position)
            print(f"Mock: Moving to position {position}")
            return True
            
        def home_axes(self, axes):
            for axis in axes:
                self._position[axis] = 0.0
            print(f"Mock: Homing axes {axes}")
            return True
            
        def emergency_stop(self):
            print("Mock: EMERGENCY STOP!")
    
    class MockCameraManager:
        def get_status(self):
            return {
                'cameras': ['camera_0', 'camera_1'],
                'active_camera': 'camera_0',
                'status': 'ready'
            }
            
        def capture_image(self, camera_id, filename):
            print(f"Mock: Capturing image from {camera_id} to {filename}")
            
        def get_preview_frame(self, camera_id):
            print(f"Mock: Getting preview frame from {camera_id}")
            return None  # Would return actual frame data
    
    class MockLightingController:
        def get_status(self):
            return {
                'zones': ['zone_1', 'zone_2', 'zone_3', 'zone_4'],
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
    """Initialize the real scanner orchestrator"""
    try:
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        import asyncio
        
        # Create config manager with default config
        config_file = Path(__file__).parent.parent / "config" / "default_config.yaml"
        if not config_file.exists():
            # Create minimal config if it doesn't exist
            config_file.parent.mkdir(exist_ok=True)
            with open(config_file, 'w') as f:
                f.write("""
system:
  simulation_mode: true
  log_level: INFO

motion:
  fluidnc:
    serial_port: "/dev/ttyUSB0"
    baud_rate: 115200

cameras:
  pi_camera:
    enabled: true
    resolution: [1920, 1080]

lighting:
  pwm_controller:
    enabled: true
""")
        
        config_manager = ConfigManager(config_file)
        
        # Create orchestrator
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize all subsystems asynchronously
        print("Initializing scanner subsystems...")
        
        # Run initialization in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(orchestrator.initialize())
        finally:
            loop.close()
        
        print("✅ Real scanner orchestrator initialized successfully")
        return orchestrator
        
    except ImportError as e:
        print(f"❌ Could not import scanner modules: {e}")
        print("💡 Falling back to mock mode")
        return create_mock_orchestrator()
        
    except Exception as e:
        print(f"❌ Failed to initialize real orchestrator: {e}")
        print("💡 Falling back to mock mode")
        return create_mock_orchestrator()

def start_web_interface(
    orchestrator=None,
    host: str = "0.0.0.0",
    port: int = 5000,
    debug: bool = False
):
    """Start the web interface with orchestrator"""
    try:
        from web_interface import ScannerWebInterface
        
        # Create web interface
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        
        # Start server
        print(f"🚀 Starting web interface on http://{host}:{port}")
        web_interface.start_web_server(host=host, port=port, debug=debug)
        
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
        choices=["production", "development", "mock"],
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
        
    elif args.mode == "mock":
        print("🎭 Mock Mode: Using simulated hardware...")
        orchestrator = create_mock_orchestrator()
    
    # Start web interface
    try:
        start_web_interface(
            orchestrator=orchestrator,
            host=args.host,
            port=args.port,
            debug=args.debug
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