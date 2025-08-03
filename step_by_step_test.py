#!/usr/bin/env python3
"""
Test Simple Route Functionality Step by Step
"""

import requests
import json
import time

def test_basic_functionality(base_url):
    """Test if basic system components are working"""
    print("🔧 TESTING BASIC SYSTEM FUNCTIONALITY")
    print("-" * 40)
    
    # Test 1: Ping
    try:
        resp = requests.get(f"{base_url}/ping", timeout=3)
        print(f"✅ Ping: {resp.status_code}")
    except Exception as e:
        print(f"❌ Ping failed: {e}")
        return False
    
    # Test 2: GRBL Status
    try:
        resp = requests.get(f"{base_url}/grbl_status", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ GRBL Status: Connected={data.get('connected')}")
            print(f"   Position: {data.get('position')}")
        else:
            print(f"❌ GRBL Status failed: {resp.status_code}")
            return False
    except Exception as e:
        print(f"❌ GRBL Status error: {e}")
        return False
    
    # Test 3: Get Current Position (simple route)
    try:
        resp = requests.get(f"{base_url}/get_current_position", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            print(f"✅ Get Position: {data.get('position')}")
        else:
            print(f"❌ Get Position failed: {resp.status_code}")
    except Exception as e:
        print(f"❌ Get Position error: {e}")
    
    return True

def test_multi_param_route_repeatedly(base_url, route, count=5):
    """Test the same multi-parameter route multiple times to check for intermittent issues"""
    print(f"\n🔄 TESTING {route} {count} TIMES")
    print("-" * 40)
    
    results = []
    for i in range(count):
        try:
            resp = requests.get(f"{base_url}{route}", timeout=5)
            status = resp.status_code
            
            if status == 200:
                print(f"  Test {i+1}: ✅ SUCCESS ({status})")
                try:
                    data = resp.json()
                    if "message" in data:
                        print(f"    Message: {data['message']}")
                except:
                    pass
            else:
                print(f"  Test {i+1}: ❌ FAILED ({status})")
                try:
                    data = resp.json()
                    if "error" in data:
                        print(f"    Error: {data['error'][:100]}")
                except:
                    print(f"    Raw response: {resp.text[:100]}")
            
            results.append(status)
            time.sleep(0.5)  # Small delay between tests
            
        except Exception as e:
            print(f"  Test {i+1}: 💥 EXCEPTION: {e}")
            results.append("ERROR")
    
    # Analyze results
    success_count = len([r for r in results if r == 200])
    print(f"\n📊 Results: {success_count}/{count} successful")
    
    if success_count == 0:
        print("🔴 CONSISTENT FAILURE - Route always fails")
    elif success_count == count:
        print("🟢 CONSISTENT SUCCESS - Route always works")
    else:
        print("🟡 INTERMITTENT ISSUE - Sometimes works, sometimes fails")
        print(f"   Pattern: {results}")
    
    return results

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔬 STEP-BY-STEP ROUTE FUNCTIONALITY TEST")
    print("=" * 50)
    
    # Step 1: Test basic functionality
    if not test_basic_functionality(base_url):
        print("❌ Basic functionality failed - stopping test")
        return
    
    # Step 2: Test multi-parameter routes repeatedly
    test_routes = [
        "/test_move_simple/1/2/3",
        "/move_to/5/0/5",
    ]
    
    for route in test_routes:
        results = test_multi_param_route_repeatedly(base_url, route, 3)
        
        # If we get consistent failures, try to analyze further
        if all(r != 200 for r in results):
            print(f"\n🔍 DETAILED ERROR ANALYSIS FOR {route}:")
            try:
                resp = requests.get(f"{base_url}{route}", timeout=10)
                print(f"Status: {resp.status_code}")
                print(f"Headers: {dict(resp.headers)}")
                print(f"Response: {resp.text}")
            except Exception as e:
                print(f"Detailed test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🏁 TEST COMPLETE")

if __name__ == "__main__":
    main()
