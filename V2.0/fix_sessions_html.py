#!/usr/bin/env python3
"""
Fix corrupted sessions.html file by replacing it with a clean version.
Run this script on the Raspberry Pi to automatically fix the JavaScript syntax errors.
"""

import os
import shutil
from pathlib import Path

def fix_sessions_html():
    """Replace the corrupted sessions.html with a clean version."""
    
    # Get the current script directory
    script_dir = Path(__file__).parent
    web_templates_dir = script_dir / "web" / "templates"
    
    # File paths
    corrupted_file = web_templates_dir / "sessions.html"
    clean_file = web_templates_dir / "sessions_clean.html"
    backup_file = web_templates_dir / "sessions_backup_corrupted.html"
    
    print("🔧 Fixing corrupted sessions.html file...")
    
    # Check if files exist
    if not corrupted_file.exists():
        print(f"❌ Error: {corrupted_file} not found")
        return False
        
    if not clean_file.exists():
        print(f"❌ Error: {clean_file} not found")
        return False
    
    try:
        # Create backup of corrupted file
        print(f"📦 Creating backup: {backup_file}")
        shutil.copy2(corrupted_file, backup_file)
        
        # Replace with clean version
        print(f"🔄 Replacing with clean version...")
        shutil.copy2(clean_file, corrupted_file)
        
        print("✅ Successfully fixed sessions.html!")
        print("📝 Backup saved as sessions_backup_corrupted.html")
        print("🚀 Please restart the web server to apply changes")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing file: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("🛠️  Sessions.html File Fixer")
    print("=" * 50)
    
    success = fix_sessions_html()
    
    if success:
        print("\n🎉 File fixed successfully!")
        print("Next steps:")
        print("1. Restart the web server (Ctrl+C then restart)")
        print("2. Navigate to http://3dscanner.local:5000/sessions")
        print("3. Test download functionality")
    else:
        print("\n❌ Failed to fix file. Please check error messages above.")
    
    print("=" * 50)