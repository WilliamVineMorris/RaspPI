#!/usr/bin/env python3
"""
Clean Web Interface Test

Test the web interface without any timing modifications to ensure
manual controls work properly.
"""

import os
import sys
import logging

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s,%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

def main():
    print("🚀 Starting Clean Web Interface Test")
    print("=" * 50)
    print("🌐 Web interface: http://localhost:8080")
    print("🎮 Test manual controls to verify functionality")
    print("=" * 50)
    
    try:
        # Import the working web interface
        from web.start_web_interface import main as start_web
        
        # Override sys.argv to use simple configuration
        sys.argv = [
            'start_web_interface.py',
            '--host', '0.0.0.0',
            '--port', '8080',
            '--mode', 'development'
        ]
        
        return start_web()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())