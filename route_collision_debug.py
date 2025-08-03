#!/usr/bin/env python3
"""
Route Order and Collision Investigation
"""

import requests
import json

def test_route_collision():
    """Test if route patterns are colliding"""
    base_url = "http://192.168.1.169:5000"
    
    print("🔍 ROUTE COLLISION INVESTIGATION")
    print("=" * 50)
    
    # Get all registered routes
    try:
        resp = requests.get(f"{base_url}/debug_routes", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            routes = data.get("routes", [])
            
            print(f"📋 Found {len(routes)} registered routes")
            
            # Focus on parameterized routes
            param_routes = [r for r in routes if "<" in r["rule"]]
            print(f"\n🎯 PARAMETERIZED ROUTES ({len(param_routes)}):")
            
            for route in param_routes:
                rule = route["rule"]
                methods = route.get("methods", [])
                endpoint = route.get("endpoint", "")
                
                print(f"   📍 {rule}")
                print(f"      Methods: {methods}")
                print(f"      Endpoint: {endpoint}")
                
                # Check parameter types
                param_types = []
                if "<float:" in rule:
                    param_types.append("float")
                if "<int:" in rule:
                    param_types.append("int")
                if "<string:" in rule:
                    param_types.append("string")
                
                print(f"      Types: {param_types}")
                print()
            
            # Look for potential conflicts
            print(f"🔍 POTENTIAL CONFLICTS:")
            
            # Check if any routes have similar patterns
            similar_patterns = []
            for i, route1 in enumerate(param_routes):
                for j, route2 in enumerate(param_routes):
                    if i != j:
                        rule1 = route1["rule"]
                        rule2 = route2["rule"]
                        
                        # Check for similar base paths
                        base1 = rule1.split("/<")[0]
                        base2 = rule2.split("/<")[0]
                        
                        if base1 == base2:
                            similar_patterns.append((rule1, rule2))
            
            if similar_patterns:
                print("⚠️ Found similar route patterns:")
                for rule1, rule2 in similar_patterns:
                    print(f"   - {rule1}")
                    print(f"   - {rule2}")
            else:
                print("✅ No obvious route pattern conflicts")
            
            # Test specific collision scenarios
            print(f"\n🧪 COLLISION SCENARIO TESTS:")
            
            # Test 1: Mixed float/int patterns
            print(f"\n📌 Testing mixed float/int parameter handling:")
            mixed_tests = [
                ("/test_move_simple/1/2/3", "3 integers -> should match <float:x>/<float:y>/<float:z>"),
                ("/start_grid_scan/0/0/10/10/2/2", "6 integers -> mixed <float>/<int> pattern"),
            ]
            
            for test_url, description in mixed_tests:
                print(f"\n🔍 {description}")
                print(f"   URL: {test_url}")
                
                try:
                    resp = requests.get(f"{base_url}{test_url}", timeout=3)
                    if resp.status_code == 200:
                        print(f"   ✅ SUCCESS - Correctly routed")
                    else:
                        print(f"   ❌ FAILED - Status: {resp.status_code}")
                        try:
                            error_data = resp.json()
                            error_msg = error_data.get("error", "Unknown")
                            print(f"   🚫 Error: {error_msg[:100]}")
                        except:
                            pass
                except Exception as e:
                    print(f"   💥 Exception: {e}")
            
    except Exception as e:
        print(f"❌ Could not get routes: {e}")

def test_flask_route_order():
    """Test if route registration order affects matching"""
    print(f"\n🔄 ROUTE REGISTRATION ORDER ANALYSIS:")
    print("-" * 40)
    
    print("Flask matches routes in registration order.")
    print("If a more general pattern comes before a specific one,")
    print("it might intercept requests meant for the specific route.")
    
    print(f"\nChecking for order issues...")
    
    # Based on the routes we found, check logical order
    expected_order = [
        "Basic routes (no params)",
        "Single param routes", 
        "Multi-param routes (specific to general)",
        "Catch-all routes"
    ]
    
    print(f"✅ Expected route order: {' -> '.join(expected_order)}")

def main():
    test_route_collision()
    test_flask_route_order()
    
    print(f"\n" + "=" * 50)
    print("🎯 COLLISION ANALYSIS COMPLETE")
    print("=" * 50)
    
    print(f"\n🔧 POTENTIAL FIXES TO TRY:")
    print("1. 🔄 Change route order (register specific routes first)")
    print("2. 🔧 Use consistent parameter types (<float> everywhere)")
    print("3. 🛠️ Add explicit type conversion in route handlers") 
    print("4. 🧪 Test with simpler route patterns")

if __name__ == "__main__":
    main()
