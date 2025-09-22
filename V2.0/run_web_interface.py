#!/usr/bin/env python3
"""
Production Launcher for 3D Scanner Web Interface
Simplified production deployment script
"""

import sys
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def main():
    """Production launcher"""
    try:
        # Import and run the full initialization system
        from web.start_web_interface import main as start_main
        return start_main()
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Make sure you're running from the project root directory")
        return 1
    except Exception as e:
        print(f"❌ Failed to start web interface: {e}")
        return 1

if __name__ == "__main__":
    """
    Production Usage:
    
    # From project root directory:
    python run_web_interface.py
    
    # Or with arguments:
    python run_web_interface.py --mode production --port 80
    """
    exit(main())