#!/usr/bin/env python3
"""
Route Registration Conflict Analysis
"""

import requests
import json

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔍 ROUTE REGISTRATION CONFLICT ANALYSIS")
    print("=" * 50)
    
    try:
        # Get all registered routes with full details
        response = requests.get(f"{base_url}/debug_routes", timeout=5)
        if response.status_code == 200:
            data = response.json()
            routes = data.get("routes", [])
            
            print(f"✅ Found {len(routes)} total routes\n")
            
            # Look for conflicts and duplicates
            route_rules = {}
            conflicts = []
            
            for route in routes:
                rule = route["rule"]
                methods = route.get("methods", [])
                endpoint = route.get("endpoint", "")
                
                # Check for duplicates
                if rule in route_rules:
                    conflicts.append((rule, route_rules[rule], route))
                else:
                    route_rules[rule] = route
                
                # Focus on multi-parameter routes
                if rule.count("<") > 1:
                    print(f"🎯 Multi-param route: {rule}")
                    print(f"   Methods: {methods}")
                    print(f"   Endpoint: {endpoint}")
                    print()
            
            if conflicts:
                print("⚠️  CONFLICTS FOUND:")
                for rule, route1, route2 in conflicts:
                    print(f"   Duplicate rule: {rule}")
                    print(f"     Route 1: {route1}")
                    print(f"     Route 2: {route2}")
            else:
                print("✅ No route conflicts detected")
            
            # Test specific URL patterns
            print("\n🧪 TESTING URL PATTERN MATCHING:")
            
            test_urls = [
                "/test_move_simple/1/2/3",
                "/test_move_simple/1.0/2.0/3.0",
                "/move_to/5/0/5",
                "/move_to/5.5/0.0/5.1"
            ]
            
            for test_url in test_urls:
                print(f"\nTesting URL: {test_url}")
                
                # Check if URL matches any registered pattern
                matches = []
                for rule, route_info in route_rules.items():
                    # Simple pattern matching check
                    if rule.startswith("/test_move_simple/") and test_url.startswith("/test_move_simple/"):
                        matches.append(rule)
                    elif rule.startswith("/move_to/") and test_url.startswith("/move_to/"):
                        matches.append(rule)
                
                print(f"   Potential matches: {matches}")
                
                # Try the actual request
                try:
                    resp = requests.get(f"{base_url}{test_url}", timeout=3)
                    print(f"   Actual result: {resp.status_code}")
                    if resp.status_code != 200:
                        try:
                            error_data = resp.json()
                            print(f"   Error: {error_data.get('error', 'Unknown error')}")
                        except:
                            print(f"   Error text: {resp.text[:100]}")
                except Exception as e:
                    print(f"   Request failed: {e}")
            
        else:
            print(f"❌ Failed to get debug routes: {response.status_code}")
    
    except Exception as e:
        print(f"❌ Analysis failed: {e}")

if __name__ == "__main__":
    main()
