#!/usr/bin/env python3
"""
Integer vs Float Parameter Type Investigation
Testing if the issue is related to type conversion between int/float parameters
"""

import requests
import json

def test_parameter_types(base_url):
    """Test the same route with different parameter type formats"""
    print("🔢 PARAMETER TYPE CONVERSION TEST")
    print("=" * 50)
    
    # Test cases with different number formats
    test_cases = [
        # Route, Description, Expected to work
        ("/test_move_simple/1/2/3", "Integers only", True),
        ("/test_move_simple/1.0/2.0/3.0", "Explicit floats", True),
        ("/test_move_simple/1.5/2.5/3.5", "Decimal floats", True),
        ("/test_move_simple/1/2.0/3", "Mixed int/float", True),
        ("/test_move_simple/0/0/0", "All zeros (int)", True),
        ("/test_move_simple/0.0/0.0/0.0", "All zeros (float)", True),
        ("/test_move_simple/-1/-2/-3", "Negative integers", True),
        ("/test_move_simple/-1.0/-2.0/-3.0", "Negative floats", True),
        ("/test_move_simple/10/20/30", "Larger integers", True),
        ("/test_move_simple/10.0/20.0/30.0", "Larger floats", True),
    ]
    
    results = []
    
    for route, description, expected in test_cases:
        print(f"\n🧪 Testing: {description}")
        print(f"   Route: {route}")
        
        try:
            full_url = f"{base_url}{route}"
            response = requests.get(full_url, timeout=5)
            
            status_code = response.status_code
            success = status_code == 200
            
            if success:
                print(f"   ✅ SUCCESS ({status_code})")
                try:
                    data = response.json()
                    if "target" in data:
                        target = data["target"]
                        print(f"   📍 Target: X={target['x']}, Y={target['y']}, Z={target['z']}")
                        print(f"   📊 Types: X={type(target['x'])}, Y={type(target['y'])}, Z={type(target['z'])}")
                except Exception as parse_error:
                    print(f"   ⚠️ JSON parse error: {parse_error}")
            else:
                print(f"   ❌ FAILED ({status_code})")
                try:
                    data = response.json()
                    error_msg = data.get("error", "Unknown error")
                    print(f"   🚫 Error: {error_msg[:100]}")
                except:
                    print(f"   🚫 Raw error: {response.text[:100]}")
            
            results.append({
                "route": route,
                "description": description,
                "expected": expected,
                "actual_success": success,
                "status_code": status_code,
                "response": response.text[:200] if not success else "OK"
            })
            
        except Exception as e:
            print(f"   💥 Exception: {e}")
            results.append({
                "route": route,
                "description": description,
                "expected": expected,
                "actual_success": False,
                "status_code": "ERROR",
                "response": str(e)
            })
    
    # Analysis
    print(f"\n📊 ANALYSIS:")
    print("-" * 30)
    
    successful = [r for r in results if r["actual_success"]]
    failed = [r for r in results if not r["actual_success"]]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if len(successful) > 0:
        print(f"\n🟢 SUCCESSFUL ROUTES:")
        for r in successful:
            print(f"   ✅ {r['route']} - {r['description']}")
    
    if len(failed) > 0:
        print(f"\n🔴 FAILED ROUTES:")
        for r in failed:
            print(f"   ❌ {r['route']} - {r['description']} (Status: {r['status_code']})")
    
    # Pattern analysis
    print(f"\n🔍 PATTERN ANALYSIS:")
    
    int_only_routes = [r for r in results if "/1/2/3" in r["route"] or "/0/0/0" in r["route"] or "/-1/-2/-3" in r["route"] or "/10/20/30" in r["route"]]
    float_only_routes = [r for r in results if ".0" in r["route"] and "1.5" not in r["route"]]
    decimal_routes = [r for r in results if "1.5" in r["route"] or "2.5" in r["route"]]
    mixed_routes = [r for r in results if "/1/2.0/3" in r["route"]]
    
    print(f"   📌 Integer-only routes: {len([r for r in int_only_routes if r['actual_success']])}/{len(int_only_routes)} successful")
    print(f"   📌 Float-only routes: {len([r for r in float_only_routes if r['actual_success']])}/{len(float_only_routes)} successful")
    print(f"   📌 Decimal routes: {len([r for r in decimal_routes if r['actual_success']])}/{len(decimal_routes)} successful")
    print(f"   📌 Mixed routes: {len([r for r in mixed_routes if r['actual_success']])}/{len(mixed_routes)} successful")
    
    # Conclusion
    print(f"\n🎯 CONCLUSION:")
    if len(successful) == 0:
        print("❌ ALL parameter types failed - issue is NOT type conversion")
        print("🔍 The problem is deeper than int/float conversion")
    elif len(successful) == len(results):
        print("✅ ALL parameter types worked - no type conversion issue")
    else:
        print("⚠️ MIXED RESULTS - type conversion may be a factor")
        print("🔍 Check which specific formats work vs fail")
    
    return results

def test_flask_route_definition():
    """Test if Flask route definition accepts the parameter types correctly"""
    print(f"\n🔧 FLASK ROUTE DEFINITION TEST")
    print("-" * 30)
    
    print("Expected Flask route: /test_move_simple/<float:x>/<float:y>/<float:z>")
    print("This should accept:")
    print("  ✅ Integers: 1, 2, 3 (auto-converted to float)")
    print("  ✅ Floats: 1.0, 2.0, 3.0")
    print("  ✅ Decimals: 1.5, 2.5, 3.5")
    print("  ✅ Mixed: 1, 2.0, 3")
    print("  ✅ Negative: -1, -2.5")
    print("  ✅ Zero: 0, 0.0")

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔬 INTEGER vs FLOAT PARAMETER INVESTIGATION")
    print("=" * 60)
    print(f"Target: {base_url}")
    print("=" * 60)
    
    # First, test the Flask route definition expectations
    test_flask_route_definition()
    
    # Then test actual parameter types
    results = test_parameter_types(base_url)
    
    # Additional specific tests based on user's observation
    print(f"\n🎯 SPECIFIC USER OBSERVATION TEST:")
    print("-" * 40)
    
    specific_tests = [
        ("/test_move_simple/1/2/3", "User's integer example"),
        ("/test_move_simple/1.0/2.0/3.0", "User's float example"),
    ]
    
    for route, desc in specific_tests:
        print(f"\n🧪 {desc}: {route}")
        try:
            resp = requests.get(f"{base_url}{route}", timeout=5)
            print(f"   Status: {resp.status_code}")
            
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    print(f"   ✅ Success: {data.get('message', 'No message')}")
                except:
                    print(f"   ✅ Success: {resp.text[:50]}")
            else:
                try:
                    data = resp.json()
                    print(f"   ❌ Error: {data.get('error', 'Unknown')[:100]}")
                except:
                    print(f"   ❌ Error: {resp.text[:100]}")
        except Exception as e:
            print(f"   💥 Exception: {e}")
    
    print(f"\n" + "=" * 60)
    print("🏁 TYPE INVESTIGATION COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
