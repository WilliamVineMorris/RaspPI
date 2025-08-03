#!/usr/bin/env python3
"""
Direct Route Debug Test
"""

import requests
import json

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔍 CHECKING REGISTERED ROUTES")
    print("=" * 40)
    
    try:
        # Get all registered routes
        response = requests.get(f"{base_url}/debug_routes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", [])
            
            print(f"✅ Found {len(routes)} registered routes:")
            print("-" * 40)
            
            # Categorize routes
            no_params = []
            single_param = []
            multi_param = []
            
            for route in routes:
                rule = route["rule"]
                param_count = rule.count("<")
                
                if param_count == 0:
                    no_params.append(rule)
                elif param_count == 1:
                    single_param.append(rule)
                else:
                    multi_param.append(rule)
            
            print(f"\n📌 NO PARAMETERS ({len(no_params)}):")
            for route in sorted(no_params):
                print(f"   {route}")
            
            print(f"\n📌 SINGLE PARAMETER ({len(single_param)}):")
            for route in sorted(single_param):
                print(f"   {route}")
            
            print(f"\n📌 MULTI-PARAMETER ({len(multi_param)}):")
            for route in sorted(multi_param):
                print(f"   {route}")
            
            # Test specific multi-parameter routes
            print(f"\n🧪 TESTING MULTI-PARAMETER ROUTES:")
            test_routes = [
                "/move_to/5/0/5",
                "/test_move_simple/1/2/3"
            ]
            
            for test_route in test_routes:
                try:
                    print(f"\nTesting: {test_route}")
                    resp = requests.get(f"{base_url}{test_route}", timeout=3)
                    print(f"   Status: {resp.status_code}")
                    if resp.status_code != 200:
                        print(f"   Response: {resp.text[:200]}")
                    else:
                        try:
                            data = resp.json()
                            print(f"   Response: {data}")
                        except:
                            print(f"   Response: {resp.text[:100]}")
                except Exception as e:
                    print(f"   Error: {e}")
        
        else:
            print(f"❌ Failed to get routes: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
