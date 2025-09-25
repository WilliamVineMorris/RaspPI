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
    """Create a proper mock orchestrator using the working system"""
    try:
        from web.start_web_interface import create_mock_orchestrator as create_proper_mock
        print("✅ Using proper mock orchestrator from working system")
        return create_proper_mock()
    except ImportError as e:
        print(f"⚠️ Could not import proper mock, creating minimal fallback: {e}")
        
        # Fallback minimal mock if import fails
        class MockOrchestrator:
            def __init__(self):
                self.current_scan = None
                self.motion_controller = None
                self.camera_manager = None
                print("⚠️ Using minimal fallback mock orchestrator")
                
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