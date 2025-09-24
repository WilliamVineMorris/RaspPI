#!/usr/bin/env python3
"""
Fixed Web Interface with Proper Orchestrator Initialization

This creates the web interface with a proper orchestrator so manual controls work.
"""

import os
import sys
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s,%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def create_mock_orchestrator():
    """Create a mock orchestrator for testing manual controls"""
    from datetime import datetime
    from core.types import Position4D
    
    class MockMotionController:
        """Mock motion controller that simulates movement"""
        
        def __init__(self):
            self.current_position = Position4D(0, 0, 0, 0)
            self.connected = True
            
        async def move_relative(self, delta, feedrate=None, command_id=None):
            """Simulate relative movement"""
            print(f"🎮 Mock Movement: {delta} at feedrate {feedrate}")
            # Update position
            self.current_position = Position4D(
                self.current_position.x + delta.x,
                self.current_position.y + delta.y,
                self.current_position.z + delta.z,
                self.current_position.c + delta.c
            )
            print(f"📍 New Position: {self.current_position}")
            return True
            
        async def get_position(self):
            return self.current_position
            
        def is_connected(self):
            return True
            
        def get_status(self):
            return "idle"
    
    class MockCameraManager:
        """Mock camera manager"""
        def __init__(self):
            self.available_cameras = 2
            
        def get_camera_count(self):
            return self.available_cameras
    
    class MockOrchestrator:
        """Mock orchestrator with working motion controller"""
        
        def __init__(self):
            self.current_scan = None
            self.motion_controller = MockMotionController()
            self.camera_manager = MockCameraManager()
            print("✅ Mock orchestrator created with motion controller")
            
    return MockOrchestrator()

def main():
    print("🚀 Starting Web Interface with Mock Orchestrator")
    print("=" * 60)
    print("🎮 Manual controls should now work!")
    print("🌐 Web interface: http://localhost:8080")
    print("=" * 60)
    
    try:
        # Create mock orchestrator for testing
        print("Creating mock orchestrator...")
        orchestrator = create_mock_orchestrator()
        
        # Import and create web interface with orchestrator
        from web.web_interface import ScannerWebInterface
        print("Creating web interface with orchestrator...")
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        
        print("✅ Web interface created successfully!")
        print("🎮 Testing manual controls should now work")
        
        # Start the web server
        web_interface.start_web_server(host='0.0.0.0', port=8080, debug=False)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()