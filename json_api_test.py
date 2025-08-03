#!/usr/bin/env python3
"""
Test JSON-based API Implementation
"""

import requests
import json

def test_json_api(base_url):
    """Test the new JSON-based API endpoints"""
    print("🧪 TESTING JSON-BASED API")
    print("=" * 40)
    
    # Test cases with JSON payloads
    test_cases = [
        {
            "name": "Move To Position",
            "endpoint": "/move_to",
            "method": "POST",
            "payload": {"x": 5.0, "y": 0.0, "z": 5.0},
            "description": "Move to position using JSON"
        },
        {
            "name": "Test Move Simple",
            "endpoint": "/test_move_simple", 
            "method": "POST",
            "payload": {"x": 1, "y": 2, "z": 3},
            "description": "Simple move test with integers (should work now)"
        },
        {
            "name": "Grid Scan",
            "endpoint": "/start_grid_scan",
            "method": "POST", 
            "payload": {
                "x1": 0.0,
                "y1": 0.0,
                "x2": 10.0,
                "y2": 10.0,
                "grid_x": 2,
                "grid_y": 2
            },
            "description": "Grid scan with mixed int/float types"
        },
        {
            "name": "Circular Scan",
            "endpoint": "/start_circular_scan",
            "method": "POST",
            "payload": {
                "center_x": 5,
                "center_y": 5,
                "radius": 3.5,
                "positions": 8
            },
            "description": "Circular scan with mixed types"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n🔍 Testing: {test_case['name']}")
        print(f"   Endpoint: {test_case['endpoint']}")
        print(f"   Payload: {json.dumps(test_case['payload'], indent=2)}")
        
        try:
            response = requests.post(
                f"{base_url}{test_case['endpoint']}",
                json=test_case['payload'],
                headers={'Content-Type': 'application/json'},
                timeout=5
            )
            
            status_code = response.status_code
            success = status_code == 200
            
            if success:
                print(f"   ✅ SUCCESS ({status_code})")
                try:
                    data = response.json()
                    print(f"   📋 Response: {data.get('message', 'No message')}")
                    if 'target' in data:
                        target = data['target']
                        print(f"   📍 Target: {target}")
                    if 'current' in data:
                        current = data['current']
                        print(f"   📍 Current: {current}")
                except Exception as e:
                    print(f"   ⚠️ JSON parse error: {e}")
            else:
                print(f"   ❌ FAILED ({status_code})")
                try:
                    data = response.json()
                    print(f"   🚫 Error: {data.get('error', 'Unknown error')}")
                except:
                    print(f"   🚫 Raw response: {response.text[:100]}")
            
            results.append({
                "name": test_case['name'],
                "success": success,
                "status_code": status_code,
                "endpoint": test_case['endpoint']
            })
            
        except Exception as e:
            print(f"   💥 Exception: {e}")
            results.append({
                "name": test_case['name'],
                "success": False,
                "status_code": "ERROR",
                "endpoint": test_case['endpoint']
            })
    
    # Summary
    print(f"\n📊 TEST SUMMARY:")
    print("-" * 30)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        print(f"\n🟢 WORKING ENDPOINTS:")
        for r in successful:
            print(f"   ✅ {r['endpoint']} - {r['name']}")
    
    if failed:
        print(f"\n🔴 FAILED ENDPOINTS:")
        for r in failed:
            print(f"   ❌ {r['endpoint']} - {r['name']} (Status: {r['status_code']})")
    
    return results

def test_basic_endpoints(base_url):
    """Test that basic endpoints still work"""
    print(f"\n🔧 TESTING BASIC ENDPOINTS")
    print("-" * 30)
    
    basic_tests = [
        ("/ping", "Ping test"),
        ("/grbl_status", "GRBL status"),
        ("/scan_status", "Scan status")
    ]
    
    for endpoint, name in basic_tests:
        try:
            resp = requests.get(f"{base_url}{endpoint}", timeout=3)
            if resp.status_code == 200:
                print(f"   ✅ {endpoint} - {name}")
            else:
                print(f"   ❌ {endpoint} - {name} ({resp.status_code})")
        except Exception as e:
            print(f"   💥 {endpoint} - {name} (Error: {e})")

def compare_old_vs_new_api(base_url):
    """Compare old URL-based vs new JSON-based API"""
    print(f"\n🔄 COMPARING OLD vs NEW API")
    print("-" * 30)
    
    # Test old URL-based endpoint (should fail)
    print("🔴 Testing OLD URL-based API:")
    try:
        resp = requests.get(f"{base_url}/test_move_simple/1/2/3", timeout=3)
        print(f"   Old API Status: {resp.status_code} (Expected: 404 or 500)")
    except Exception as e:
        print(f"   Old API Error: {e}")
    
    # Test new JSON-based endpoint (should work) 
    print("🟢 Testing NEW JSON-based API:")
    try:
        resp = requests.post(
            f"{base_url}/test_move_simple",
            json={"x": 1, "y": 2, "z": 3},
            timeout=3
        )
        print(f"   New API Status: {resp.status_code} (Expected: 200)")
        if resp.status_code == 200:
            data = resp.json()
            print(f"   New API Message: {data.get('message', 'No message')}")
    except Exception as e:
        print(f"   New API Error: {e}")

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔬 JSON API IMPLEMENTATION TEST")
    print("=" * 50)
    print(f"Target: {base_url}")
    print("=" * 50)
    
    # Test basic functionality first
    test_basic_endpoints(base_url)
    
    # Test new JSON API
    results = test_json_api(base_url)
    
    # Compare old vs new
    compare_old_vs_new_api(base_url)
    
    print(f"\n🎯 CONCLUSION:")
    successful_json = len([r for r in results if r["success"]])
    
    if successful_json == len(results):
        print("✅ JSON API implementation is working perfectly!")
        print("🎉 Integer/float routing issues are resolved!")
    elif successful_json > 0:
        print(f"⚠️ Partial success: {successful_json}/{len(results)} endpoints working")
        print("🔧 Some endpoints may need additional fixes")
    else:
        print("❌ JSON API implementation has issues")
        print("🛠️ Check server logs and route registration")
    
    print(f"\n" + "=" * 50)
    print("🏁 TEST COMPLETE")
    print("=" * 50)

if __name__ == "__main__":
    main()
