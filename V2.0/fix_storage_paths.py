#!/usr/bin/env python3
"""
Fix storage paths in scanner config for current user
"""

import os
import sys
from pathlib import Path
import yaml

def fix_storage_paths():
    """Fix storage paths to use current user instead of hardcoded 'pi' user"""
    
    config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
    
    if not config_file.exists():
        print(f"❌ Config file not found: {config_file}")
        return False
    
    # Get current user
    current_user = os.getenv('USER', os.getenv('USERNAME', 'user'))
    home_dir = os.path.expanduser('~')
    
    print(f"🔧 Fixing storage paths for user: {current_user}")
    print(f"📁 Home directory: {home_dir}")
    
    try:
        # Read current config
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Update storage paths
        if 'storage' in config:
            old_base = config['storage'].get('base_directory', '')
            old_backup = config['storage'].get('backup', {}).get('backup_location', '')
            
            # Set new paths
            config['storage']['base_directory'] = f"{home_dir}/scanner_data"
            if 'backup' in config['storage']:
                config['storage']['backup']['backup_location'] = f"{home_dir}/scanner_backups"
            
            print(f"📝 Updated base_directory: {old_base} → {config['storage']['base_directory']}")
            print(f"📝 Updated backup_location: {old_backup} → {config['storage']['backup']['backup_location']}")
        
        # Write updated config
        with open(config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        
        print("✅ Config file updated successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error updating config: {e}")
        return False

def create_storage_directories():
    """Create storage directories if they don't exist"""
    home_dir = os.path.expanduser('~')
    
    directories = [
        f"{home_dir}/scanner_data",
        f"{home_dir}/scanner_backups"
    ]
    
    for directory in directories:
        path = Path(directory)
        if not path.exists():
            try:
                path.mkdir(parents=True, exist_ok=True)
                print(f"📁 Created directory: {directory}")
            except Exception as e:
                print(f"❌ Failed to create {directory}: {e}")
                return False
        else:
            print(f"✅ Directory exists: {directory}")
    
    return True

def main():
    """Main function"""
    print("🚀 Scanner Storage Path Fixer")
    print("=" * 40)
    
    success = fix_storage_paths()
    if success:
        success = create_storage_directories()
    
    if success:
        print("\n🎯 Storage paths fixed! You can now run:")
        print("   python3 run_web_interface_fixed.py --mode production")
    else:
        print("\n❌ Fix failed. Check the errors above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())