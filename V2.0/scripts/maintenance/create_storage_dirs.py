#!/usr/bin/env python3
"""
Simple storage directory creator without yaml dependency
"""

import os
import sys
from pathlib import Path

def create_storage_directories():
    """Create storage directories for current user"""
    
    home_dir = os.path.expanduser('~')
    current_user = os.getenv('USER', os.getenv('USERNAME', 'user'))
    
    print(f"🔧 Setting up storage for user: {current_user}")
    print(f"📁 Home directory: {home_dir}")
    
    directories = [
        f"{home_dir}/scanner_data",
        f"{home_dir}/scanner_backups"
    ]
    
    success = True
    for directory in directories:
        path = Path(directory)
        try:
            path.mkdir(parents=True, exist_ok=True)
            print(f"✅ Directory ready: {directory}")
        except Exception as e:
            print(f"❌ Failed to create {directory}: {e}")
            success = False
    
    return success

def main():
    """Main function"""
    print("🚀 Scanner Storage Setup")
    print("=" * 30)
    
    if create_storage_directories():
        print("\n🎯 Storage directories created!")
        print("✅ Ready to run web interface")
        return 0
    else:
        print("\n❌ Storage setup failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())