#!/usr/bin/env python3
"""
Simple Timing Analysis for FluidNC Commands

This runs the web interface with basic timing logging to track command delays.
"""

import os
import sys
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure detailed logging to see timing
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s,%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('command_timing.log', mode='w')
    ]
)

# Suppress noisy loggers
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)

def main():
    print("🚀 Starting Web Interface with Basic Timing Analysis")
    print("=" * 60)
    print("📊 Command timing will be logged to: command_timing.log")
    print("🌐 Web interface: http://localhost:8080")
    print("🔍 Look for [TIMING] messages in the logs")
    print("=" * 60)
    
    try:
        # Import after setting up logging
        from web.web_interface import ScannerWebInterface
        
        # Create and start web interface
        web_interface = ScannerWebInterface()
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