#!/usr/bin/env python3
"""
Use the Original Working Web Interface System

This bypasses all my timing modifications and uses the original working system
to verify that manual controls work properly.
"""

import os
import sys

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("🚀 Starting Original Working Web Interface")
    print("=" * 60)
    print("🔧 Using the original working system")
    print("🎮 Manual controls should work perfectly")
    print("🌐 Web interface: http://localhost:8080")
    print("=" * 60)
    
    try:
        # Use the original working web interface system directly
        from web.start_web_interface import main as start_web
        
        # Set up arguments for development mode
        original_argv = sys.argv
        sys.argv = [
            'start_web_interface.py',
            '--host', '0.0.0.0',
            '--port', '8080',
            '--mode', 'development'
        ]
        
        print("✅ Using original working system...")
        return start_web()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        return 0
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        # Restore original argv
        if 'original_argv' in locals():
            sys.argv = original_argv

if __name__ == "__main__":
    sys.exit(main())