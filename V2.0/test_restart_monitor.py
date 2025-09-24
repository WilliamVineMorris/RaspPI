#!/usr/bin/env python3
"""
Test script to verify restart monitor functionality
"""

import requests
import json
import sys

def test_restart_monitor():
    """Test the restart monitor API endpoint"""
    print("🔧 Testing Background Monitor Restart API...")
    
    # Test the API endpoint
    url = "http://localhost:5000/api/debug/restart-monitor"
    
    try:
        print(f"📡 Making POST request to: {url}")
        response = requests.post(url, 
                               headers={'Content-Type': 'application/json'},
                               timeout=15)
        
        print(f"📊 Response Status: {response.status_code}")
        print(f"📊 Response Headers: {dict(response.headers)}")
        
        # Check if we got JSON response
        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            try:
                result = response.json()
                print(f"✅ JSON Response: {json.dumps(result, indent=2)}")
                
                if result.get('success'):
                    print("🎉 Background monitor restart successful!")
                    return True
                else:
                    print(f"❌ Restart failed: {result.get('error', 'Unknown error')}")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"❌ JSON Parse Error: {e}")
                print(f"Raw response: {response.text[:500]}...")
                return False
        else:
            print(f"❌ Expected JSON, got: {content_type}")
            print(f"Raw response: {response.text[:500]}...")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - is the web interface running?")
        print("   Start with: python run_web_interface.py")
        return False
        
    except requests.exceptions.Timeout:
        print("❌ Request timed out (15s)")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def main():
    """Main test function"""
    print("🚀 Background Monitor Restart Test")
    print("=" * 50)
    
    success = test_restart_monitor()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ Test completed successfully!")
        sys.exit(0)
    else:
        print("❌ Test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()