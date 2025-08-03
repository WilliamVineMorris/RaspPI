#!/usr/bin/env python3
"""
Quick Route Test - Focus on multi-parameter route issue
"""

import requests
import json
from datetime import datetime

def quick_test_route(base_url, route, description):
    """Quick test of a specific route"""
    full_url = f"{base_url}{route}"
    try:
        print(f"Testing {route}: ", end="")
        response = requests.get(full_url, timeout=3)
        
        if response.status_code == 200:
            print(f"✅ SUCCESS ({response.status_code})")
            try:
                data = response.json()
                if "message" in data:
                    print(f"   Response: {data['message']}")
            except:
                print(f"   Response: {response.text[:50]}...")
        else:
            print(f"❌ FAILED ({response.status_code})")
            try:
                data = response.json()
                if "error" in data:
                    print(f"   Error: {data['error']}")
            except:
                print(f"   Error: {response.text[:100]}")
        
        return response.status_code == 200
        
    except requests.exceptions.Timeout:
        print(f"⏰ TIMEOUT")
        return False
    except Exception as e:
        print(f"💥 ERROR: {e}")
        return False

def main():
    base_url = "http://192.168.1.169:5000"
    
    print("🔬 QUICK ROUTE INVESTIGATION")
    print("=" * 50)
    print(f"Target: {base_url}")
    print("=" * 50)
    
    # Test cases organized by complexity
    print("\n📌 BASIC ROUTES (No parameters):")
    basic_routes = [
        ("/ping", "Basic ping"),
        ("/grbl_status", "GRBL status"),
        ("/button_test", "Button test"),
        ("/test_json", "JSON test"),
        ("/debug_routes", "Debug routes"),
        ("/scan_status", "Scan status"),
        ("/emergency_stop", "Emergency stop"),
        ("/capture_single_photo", "Capture photo"),
        ("/get_current_position", "Get position"),
        ("/return_home", "Return home"),
        ("/test_connection", "Test connection"),
        ("/test_step_movements", "Test step movements")
    ]
    
    basic_success = 0
    for route, desc in basic_routes:
        if quick_test_route(base_url, route, desc):
            basic_success += 1
    
    print(f"\n📊 Basic routes: {basic_success}/{len(basic_routes)} successful")
    
    print("\n📌 SINGLE PARAMETER ROUTES:")
    single_param_routes = [
        ("/switch_mode/video", "Switch mode (VideoServer route)")
    ]
    
    single_success = 0
    for route, desc in single_param_routes:
        if quick_test_route(base_url, route, desc):
            single_success += 1
    
    print(f"\n📊 Single parameter routes: {single_success}/{len(single_param_routes)} successful")
    
    print("\n📌 MULTI-PARAMETER ROUTES (The Problem Routes):")
    multi_param_routes = [
        ("/move_to/5/0/5", "Move to position (3 params)"),
        ("/test_move_simple/1/2/3", "Test move simple (3 params)"),
        ("/start_grid_scan/0/0/10/10/2/2", "Grid scan (6 params)"),
        ("/start_circular_scan/5/5/3/8", "Circular scan (4 params)")
    ]
    
    multi_success = 0
    for route, desc in multi_param_routes:
        if quick_test_route(base_url, route, desc):
            multi_success += 1
    
    print(f"\n📊 Multi-parameter routes: {multi_success}/{len(multi_param_routes)} successful")
    
    print("\n" + "=" * 50)
    print("🎯 ANALYSIS:")
    
    if basic_success > 0 and multi_success == 0:
        print("❌ CONFIRMED: Multi-parameter routes are failing")
        print("✅ Basic routes work fine")
        print("🔍 This indicates a Flask routing configuration issue")
    elif basic_success == 0:
        print("❌ Server connection issues")
    elif multi_success > 0:
        print("✅ Multi-parameter routes are working")
    
    # Test Flask route registration debugging
    print(f"\n📌 FLASK ROUTE DEBUG:")
    if quick_test_route(base_url, "/debug_routes", "Get all registered routes"):
        print("   Detailed route list should be available above")
    
    print("=" * 50)
    print("🏁 QUICK TEST COMPLETE")

if __name__ == "__main__":
    main()
