#!/usr/bin/env python3
"""
Web Interface with Real Hardware Orchestrator

This creates the web interface with a real orchestrator for Pi hardware testing.
"""

import os
import sys
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure logging for timing analysis
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s,%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('hardware_timing.log', mode='w')
    ]
)

# Suppress noisy loggers
logging.getLogger('werkzeug').setLevel(logging.WARNING)

def initialize_real_orchestrator():
    """Initialize the real scanner orchestrator with hardware"""
    try:
        from core.config_manager import ConfigManager
        from scanning.scan_orchestrator import ScanOrchestrator
        
        print("Initializing configuration...")
        config_manager = ConfigManager()
        
        print("Creating real orchestrator with hardware controllers...")
        orchestrator = ScanOrchestrator(config_manager)
        
        print("✅ Real orchestrator initialized successfully!")
        return orchestrator
        
    except Exception as e:
        print(f"❌ Failed to initialize real orchestrator: {e}")
        print("💡 Falling back to mock orchestrator for testing...")
        
        # Fall back to mock
        from web.start_web_interface import create_mock_orchestrator
        return create_mock_orchestrator()

def main():
    print("🚀 Starting Web Interface with Real Hardware")
    print("=" * 60)
    print("🔧 Attempting to connect to FluidNC and cameras...")
    print("📊 Hardware timing will be logged to: hardware_timing.log")
    print("🌐 Web interface: http://localhost:8080")
    print("🔍 Look for [TIMING] messages for command analysis")
    print("=" * 60)
    
    try:
        # Initialize real orchestrator
        orchestrator = initialize_real_orchestrator()
        
        # Import and create web interface with orchestrator
        from web.web_interface import ScannerWebInterface
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        
        print("✅ Web interface ready with orchestrator!")
        print("🎮 Manual controls should work with real hardware")
        
        # Start the web server
        web_interface.start_web_server(host='0.0.0.0', port=8080, debug=False)
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        
        # Generate timing report if available
        try:
            from timing_logger import timing_logger
            report = timing_logger.generate_performance_report()
            if report.get('total_commands', 0) > 0:
                print("\n📊 TIMING SUMMARY:")
                print(f"Commands executed: {report['total_commands']}")
                total_stats = report.get('total_duration_stats', {})
                if total_stats.get('count', 0) > 0:
                    print(f"Average duration: {total_stats.get('avg', 0):.1f}ms")
        except:
            pass
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()