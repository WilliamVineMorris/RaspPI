#!/usr/bin/env python3
"""
Simple fixed web interface launcher that uses existing working infrastructure
"""

import sys
import os
import argparse
from pathlib import Path

def main():
    """Main launcher that delegates to existing working system"""
    
    # Add current directory to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    # Parse arguments
    parser = argparse.ArgumentParser(description='Scanner Web Interface - Fixed Version')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--port', type=int, default=8080, help='Port to bind to')
    parser.add_argument('--mode', choices=['development', 'production'], default='development', 
                       help='Server mode')
    parser.add_argument('--force-flask', action='store_true', 
                       help='Force Flask dev server even in production mode')
    
    args = parser.parse_args()
    
    print("🚀 Scanner Web Interface - Fixed Version")
    print("=" * 50)
    
    if args.force_flask:
        print("🔧 Forcing Flask development server")
        use_production = False
    else:
        use_production = (args.mode == 'production')
        if use_production:
            print("🏭 Using production mode (optimized for Pi)")
        else:
            print("🔧 Using development mode")
    
    print(f"🌐 Starting on http://{args.host}:{args.port}")
    print("🛑 Press Ctrl+C to stop")
    print()
    
    try:
        # Use the existing working web interface system
        from web.start_web_interface import main as start_web
        
        # Override the default arguments
        original_argv = sys.argv
        sys.argv = [
            'start_web_interface.py',
            '--host', args.host,
            '--port', str(args.port)
        ]
        
        if use_production and not args.force_flask:
            sys.argv.extend(['--mode', 'production'])
        else:
            sys.argv.extend(['--mode', 'development'])
        
        # Run the existing system
        return start_web()
        
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        return 0
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Try running from the V2.0 directory")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Check the logs above for details")
        return 1
    finally:
        # Restore original argv
        if 'original_argv' in locals():
            sys.argv = original_argv

if __name__ == "__main__":
    sys.exit(main())