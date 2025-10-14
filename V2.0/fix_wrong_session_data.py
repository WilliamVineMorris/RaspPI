#!/usr/bin/env python3
"""
Fix Wrong Session Data - Force Recalculation
============================================

This script forces recalculation of session metadata when sessions
show incorrect file counts/sizes due to being saved with partial data.

Run this on the Pi when sessions show wrong data.
"""

import requests
import json
import sys
import time

# Configuration
SCANNER_IP = "3dscanner.local"  # or "192.168.1.138"
BASE_URL = f"http://{SCANNER_IP}:5000"

def force_session_reload():
    """Force reload sessions index and recalculate metadata"""
    print("🔧 Forcing session metadata recalculation...")
    print("=" * 60)
    
    try:
        # Get current session count
        print("📋 Step 1: Getting current sessions...")
        response = requests.get(f"{BASE_URL}/api/storage/sessions", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            sessions_before = len(data.get('sessions', []))
            print(f"   Current sessions in index: {sessions_before}")
            
            # Show problematic sessions
            for session in data.get('sessions', []):
                if session.get('session_id', '').startswith('11245ff5'):  # The "blade" session
                    print(f"   📂 Found 'blade' session:")
                    print(f"      Files: {session.get('total_files', 0)}")
                    print(f"      Size: {session.get('total_size_bytes', 0) / (1024*1024):.1f} MB")
                    print(f"      Status: {session.get('status', 'unknown')}")
        else:
            print(f"   ❌ Error getting sessions: {data.get('error', 'Unknown')}")
            return False
        
        print()
        print("📊 Step 2: Forcing sessions index reload...")
        
        # Force reload sessions index
        response = requests.post(f"{BASE_URL}/api/storage/reload", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            print(f"   ✅ Reload successful!")
            print(f"   Sessions before: {data.get('sessions_before', 0)}")
            print(f"   Sessions after: {data.get('sessions_after', 0)}")
            print(f"   New sessions found: {data.get('sessions_added', 0)}")
            print(f"   Updated sessions: {data.get('newly_discovered', 0)}")
        else:
            print(f"   ❌ Reload failed: {data.get('error', 'Unknown')}")
            return False
        
        print()
        print("🔍 Step 3: Checking updated session data...")
        
        # Get updated session data
        response = requests.get(f"{BASE_URL}/api/storage/sessions", timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            print(f"   Sessions now: {len(data.get('sessions', []))}")
            
            # Show updated blade session
            for session in data.get('sessions', []):
                if session.get('session_id', '').startswith('11245ff5'):  # The "blade" session
                    print(f"   📂 Updated 'blade' session:")
                    print(f"      Files: {session.get('total_files', 0)} (should be > 20)")
                    print(f"      Size: {session.get('total_size_bytes', 0) / (1024*1024):.1f} MB (should be > 45.9)")
                    print(f"      Status: {session.get('status', 'unknown')}")
                    
                    if session.get('total_files', 0) > 20:
                        print(f"   ✅ File count updated correctly!")
                    else:
                        print(f"   ⚠️  File count still looks low")
        
        print()
        print("=" * 60)
        print("✅ Force reload complete!")
        print()
        print("💡 Next steps:")
        print("1. Refresh the sessions page in your browser")
        print("2. Check if 'blade' session now shows correct file count")
        print("3. If still wrong, run rebuild script with --force flag")
        
        return True
        
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to scanner at {SCANNER_IP}")
        print("💡 Check:")
        print("   - Is the web server running?")
        print("   - Is the IP address correct?")
        return False
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
        print("💡 The server might be busy processing")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("🛠️  Fix Wrong Session Data Tool")
    print("=" * 60)
    print()
    print("This will force recalculation of session metadata")
    print("Use this when sessions show wrong file counts/sizes")
    print()
    
    if input("Continue? (y/N): ").lower() != 'y':
        print("Cancelled.")
        return
    
    print()
    success = force_session_reload()
    
    if success:
        print("🎉 Done! Check the sessions page to see if data is now correct.")
    else:
        print("❌ Failed. You may need to run the rebuild script manually:")
        print("   cd ~/Documents/RaspPI/V2.0")
        print("   python rebuild_sessions_index.py --force")

if __name__ == "__main__":
    main()