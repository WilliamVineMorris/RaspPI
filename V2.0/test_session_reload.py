#!/usr/bin/env python3
"""
Quick test script to verify the session reload fix works
Tests the new /api/storage/reload endpoint
"""

import requests
import json
import sys

# Configuration
SCANNER_IP = "192.168.1.138"  # Update if needed
BASE_URL = f"http://{SCANNER_IP}:5000"

def test_reload_endpoint():
    """Test the session reload API endpoint"""
    print("=" * 70)
    print("🧪 Testing Session Reload Fix")
    print("=" * 70)
    print()
    
    # Step 1: Check sessions before reload
    print("📋 Step 1: Checking sessions BEFORE reload...")
    try:
        response = requests.get(f"{BASE_URL}/api/storage/sessions", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        sessions_before = len(data.get('sessions', []))
        print(f"   ✅ Currently showing: {sessions_before} sessions")
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        print("   💡 Is the web interface running?")
        sys.exit(1)
    
    # Step 2: Trigger reload
    print("🔄 Step 2: Triggering session index reload...")
    try:
        response = requests.post(f"{BASE_URL}/api/storage/reload", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            print(f"   ✅ Reload successful!")
            print(f"   📊 Sessions before: {data.get('sessions_before', 0)}")
            print(f"   📊 Sessions after:  {data.get('sessions_after', 0)}")
            print(f"   ➕ Sessions added:  {data.get('sessions_added', 0)}")
        else:
            print(f"   ❌ Reload failed: {data.get('error', 'Unknown error')}")
            sys.exit(1)
        print()
    except requests.exceptions.HTTPError as e:
        print(f"   ❌ HTTP Error: {e}")
        if e.response.status_code == 404:
            print("   💡 The reload endpoint might not be deployed yet")
            print("   💡 Make sure you've updated web_interface.py on the Pi")
        sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        sys.exit(1)
    
    # Step 3: Check sessions after reload
    print("📋 Step 3: Checking sessions AFTER reload...")
    try:
        response = requests.get(f"{BASE_URL}/api/storage/sessions", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        sessions_after = len(data.get('sessions', []))
        print(f"   ✅ Now showing: {sessions_after} sessions")
        
        if sessions_after > sessions_before:
            print(f"   🎉 SUCCESS! Found {sessions_after - sessions_before} new sessions!")
        elif sessions_after == sessions_before and sessions_after > 0:
            print(f"   ℹ️  No new sessions found (already had {sessions_after})")
        else:
            print(f"   ⚠️  Still showing 0 sessions")
            print("   💡 Check if sessions_index.json has any content")
        print()
    except Exception as e:
        print(f"   ❌ Error: {e}")
        sys.exit(1)
    
    # Step 4: Display session summary
    if sessions_after > 0:
        print("=" * 70)
        print("📊 Session Summary:")
        print("=" * 70)
        for session in data.get('sessions', [])[:5]:  # Show first 5
            name = session.get('scan_name', 'Unnamed')
            files = session.get('total_files', 0)
            size_mb = session.get('total_size_bytes', 0) / (1024 * 1024)
            status = session.get('status', 'unknown')
            print(f"   • {name}")
            print(f"     Files: {files}, Size: {size_mb:.1f} MB, Status: {status}")
        
        if sessions_after > 5:
            print(f"   ... and {sessions_after - 5} more sessions")
        print()
    
    print("=" * 70)
    print("✅ Test Complete!")
    print("=" * 70)
    print()
    print("💡 Next steps:")
    print("   1. Open web interface: http://192.168.1.138:5000/sessions")
    print("   2. Click '🔄 Reload & Refresh' button")
    print("   3. Your sessions should now appear!")
    print()

if __name__ == "__main__":
    test_reload_endpoint()
