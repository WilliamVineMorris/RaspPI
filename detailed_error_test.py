#!/usr/bin/env python3
"""
Debug Multi-Parameter Route Errors
"""

import requests
import json

def test_route_detailed(base_url, route, description):
    """Test route with detailed error analysis"""
    full_url = f"{base_url}{route}"
    print(f"\n🔍 Testing: {description}")
    print(f"URL: {full_url}")
    
    try:
        response = requests.get(full_url, timeout=10)
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        # Try to get response as JSON
        try:
            data = response.json()
            print(f"JSON Response: {json.dumps(data, indent=2)}")
        except:
            print(f"Text Response: {response.text}")
        
        return response.status_code, response.text
        
    except Exception as e:
        print(f"ERROR: {e}")
        return None, str(e)

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔬 DETAILED MULTI-PARAMETER ROUTE ERROR ANALYSIS")
    print("=" * 60)
    
    # Test cases that we know are failing
    test_cases = [
        ("/test_move_simple/1/2/3", "Test move simple - should be safest"),
        ("/move_to/5/0/5", "Move to position"),
        ("/get_current_position", "Get current position (no params - should work)"),
        ("/grbl_status", "GRBL status (no params - should work)"),
    ]
    
    for route, description in test_cases:
        status, response = test_route_detailed(base_url, route, description)
        print("-" * 60)
    
    print("\n🎯 ADDITIONAL DEBUG:")
    
    # Check if we can get more detailed error info
    print("\n📋 Checking Flask app state...")
    try:
        # Try to ping to make sure server is responsive
        resp = requests.get(f"{base_url}/ping", timeout=5)
        print(f"Ping successful: {resp.status_code}")
        
        # Try to get scan status to see if system is initialized
        resp = requests.get(f"{base_url}/scan_status", timeout=5)
        print(f"Scan status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            print(f"GRBL connected: {data.get('grbl_connected', 'Unknown')}")
        
    except Exception as e:
        print(f"Basic checks failed: {e}")
    
    print("\n🔧 HYPOTHESIS TESTING:")
    print("If the issue is inside the route handlers, we should see:")
    print("1. 500 Internal Server Error (not 404)")
    print("2. JSON error response with details")
    print("3. Specific error message about what failed")

if __name__ == "__main__":
    main()
