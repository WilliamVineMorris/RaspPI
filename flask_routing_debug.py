#!/usr/bin/env python3
"""
Flask Version and Route Pattern Investigation
"""

import requests
import json

def check_flask_version_and_routing():
    """Check Flask version and routing behavior"""
    base_url = "http://192.168.1.169:5000"
    
    print("🔧 FLASK ROUTING INVESTIGATION")
    print("=" * 40)
    
    # First check what Flask version is running
    try:
        resp = requests.get(f"{base_url}/debug_routes", timeout=5)
        if resp.status_code == 200:
            headers = dict(resp.headers)
            server_info = headers.get('Server', 'Unknown')
            print(f"📊 Server Info: {server_info}")
            
            # Extract Flask/Werkzeug versions
            if 'Werkzeug' in server_info:
                print(f"🐍 Python/Werkzeug detected in server header")
    except Exception as e:
        print(f"❌ Could not get server info: {e}")
    
    print(f"\n🧪 DETAILED ROUTE MATCHING TEST:")
    print("-" * 40)
    
    # Test exact URL patterns to understand Flask's routing
    test_patterns = [
        # Pattern, Description, Should Work According to Flask Docs
        ("/test_move_simple/1/2/3", "Integers (should auto-convert)", True),
        ("/test_move_simple/1.0/2.0/3.0", "Explicit floats", True),
        ("/test_move_simple/1./2./3.", "Trailing dots", True),
        ("/test_move_simple/1.00/2.00/3.00", "Multiple zeros", True),
        ("/test_move_simple/01/02/03", "Leading zeros", True),
        ("/test_move_simple/1e0/2e0/3e0", "Scientific notation", True),
    ]
    
    for pattern, description, expected in test_patterns:
        print(f"\n🔍 Testing: {description}")
        print(f"   URL: {pattern}")
        
        try:
            resp = requests.get(f"{base_url}{pattern}", timeout=3)
            success = resp.status_code == 200
            
            if success:
                print(f"   ✅ SUCCESS - Status: {resp.status_code}")
                try:
                    data = resp.json()
                    target = data.get("target", {})
                    print(f"   📍 Parsed as: X={target.get('x')}, Y={target.get('y')}, Z={target.get('z')}")
                except:
                    pass
            else:
                print(f"   ❌ FAILED - Status: {resp.status_code}")
                
            result_match = "✅ EXPECTED" if success == expected else "⚠️ UNEXPECTED"
            print(f"   📊 Result: {result_match}")
            
        except Exception as e:
            print(f"   💥 ERROR: {e}")
    
    print(f"\n🎯 HYPOTHESIS:")
    print("-" * 20)
    print("If Flask routing is working correctly:")
    print("  ✅ Integers should be auto-converted to floats")
    print("  ✅ Route '<float:x>' should match '1', '1.0', '1.', etc.")
    print("  ✅ The issue might be in the route handler, not routing")
    print("\nIf Flask routing is broken:")
    print("  ❌ Integer URLs don't match '<float:x>' pattern")
    print("  ❌ This is a Flask configuration or version issue")

def main():
    check_flask_version_and_routing()
    
    print(f"\n" + "=" * 40)
    print("🏁 INVESTIGATION COMPLETE")
    print("=" * 40)
    
    print(f"\n🎯 NEXT STEPS:")
    print("1. Check Flask/Werkzeug version compatibility")
    print("2. Test if route pattern needs modification")
    print("3. Consider if route registration order matters")
    print("4. Check for URL encoding issues")

if __name__ == "__main__":
    main()
