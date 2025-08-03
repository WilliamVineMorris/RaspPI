#!/usr/bin/env python3
"""
Route Investigation Test - Comprehensive analysis of route availability
This script will systematically test different route patterns to identify
which routes are available and which return 404 errors.
"""

import requests
import json
from datetime import datetime

def test_route(base_url, route, description):
    """Test a specific route and return detailed results"""
    full_url = f"{base_url}{route}"
    try:
        print(f"\n🔍 Testing: {description}")
        print(f"   URL: {full_url}")
        
        response = requests.get(full_url, timeout=5)
        
        result = {
            "route": route,
            "description": description,
            "status_code": response.status_code,
            "success": response.status_code in [200, 201, 202],
            "url": full_url,
            "response_time": response.elapsed.total_seconds()
        }
        
        # Try to parse JSON response
        try:
            result["response_data"] = response.json()
        except:
            result["response_data"] = response.text[:200] + "..." if len(response.text) > 200 else response.text
        
        # Color-coded output
        status_symbol = "✅" if result["success"] else "❌"
        print(f"   {status_symbol} Status: {response.status_code}")
        
        if result["success"]:
            print(f"   📊 Response time: {result['response_time']:.3f}s")
            if isinstance(result["response_data"], dict):
                print(f"   📋 Response: {json.dumps(result['response_data'], indent=6)}")
            else:
                print(f"   📋 Response: {result['response_data'][:100]}...")
        else:
            print(f"   🚫 Error: {response.status_code} - {response.reason}")
            print(f"   📋 Response: {result['response_data']}")
        
        return result
        
    except requests.exceptions.RequestException as e:
        result = {
            "route": route,
            "description": description,
            "status_code": "ERROR",
            "success": False,
            "url": full_url,
            "error": str(e)
        }
        print(f"   💥 Connection Error: {e}")
        return result

def main():
    """Main test function"""
    # Raspberry Pi IP and port
    base_url = "http://192.168.1.169:5000"
    
    print("=" * 70)
    print("🔬 COMPREHENSIVE ROUTE INVESTIGATION TEST")
    print("=" * 70)
    print(f"📍 Target: {base_url}")
    print(f"🕐 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # Define test cases organized by category
    test_cases = [
        # === BASIC ROUTES (Known to work) ===
        ("🟢 BASIC ROUTES", [
            ("/ping", "Basic ping test"),
            ("/grbl_status", "GRBL status check"),
            ("/video_feed", "Video feed stream"),
            ("/capture_photo", "Photo capture"),
            ("/status", "Server status (VideoServer route)"),
            ("/health", "Health check (VideoServer route)"),
            ("/button_test", "Button test (integrated system route)"),
            ("/test_json", "JSON test (integrated system route)"),
            ("/debug_routes", "Route debugging (integrated system route)"),
        ]),
        
        # === SINGLE PARAMETER ROUTES ===
        ("🟡 SINGLE PARAMETER ROUTES", [
            ("/switch_mode/video", "Switch to video mode (VideoServer)"),
            ("/switch_mode/photo", "Switch to photo mode (VideoServer)"),
        ]),
        
        # === MULTI-PARAMETER ROUTES (The problem routes) ===
        ("🔴 MULTI-PARAMETER ROUTES (The Problem Routes)", [
            ("/move_to/5/0/5", "Move to position X=5 Y=0 Z=5"),
            ("/move_to/10.5/5.5/2.0", "Move to position with decimals"),
            ("/test_move_simple/1/2/3", "Simple move test"),
            ("/start_grid_scan/0/0/10/10/2/2", "Grid scan 2x2"),
            ("/start_circular_scan/5/5/3/8", "Circular scan"),
            ("/get_current_position", "Get current position"),
            ("/return_home", "Return to home position"),
            ("/capture_single_photo", "Capture single photo"),
            ("/test_connection", "Test GRBL connection"),
            ("/test_step_movements", "Test step movements"),
            ("/emergency_stop", "Emergency stop"),
        ]),
        
        # === EDGE CASES ===
        ("🟠 EDGE CASES", [
            ("/move_to/0/0/0", "Move to origin"),
            ("/move_to/-5/5/10", "Move with negative coordinates"),
            ("/start_grid_scan/0/0/5/5/1/1", "Single point grid"),
            ("/test_move_simple/999/999/999", "Large coordinate test"),
        ])
    ]
    
    # Store all results
    all_results = []
    
    # Run tests by category
    for category_name, routes in test_cases:
        print(f"\n{'=' * 70}")
        print(f"📂 {category_name}")
        print("=" * 70)
        
        category_results = []
        for route, description in routes:
            result = test_route(base_url, route, description)
            category_results.append(result)
            all_results.append(result)
        
        # Category summary
        successful = [r for r in category_results if r["success"]]
        failed = [r for r in category_results if not r["success"]]
        
        print(f"\n📊 Category Summary:")
        print(f"   ✅ Successful: {len(successful)}/{len(category_results)}")
        print(f"   ❌ Failed: {len(failed)}/{len(category_results)}")
        
        if failed:
            print(f"   🚫 Failed routes:")
            for result in failed:
                print(f"      - {result['route']} ({result['status_code']})")
    
    # Overall analysis
    print(f"\n{'=' * 70}")
    print("📈 OVERALL ANALYSIS")
    print("=" * 70)
    
    successful_routes = [r for r in all_results if r["success"]]
    failed_routes = [r for r in all_results if not r["success"]]
    
    print(f"✅ Total Successful: {len(successful_routes)}/{len(all_results)}")
    print(f"❌ Total Failed: {len(failed_routes)}/{len(all_results)}")
    
    # Pattern analysis
    print(f"\n🔍 PATTERN ANALYSIS:")
    
    # Count by parameter patterns
    no_params = [r for r in all_results if "/" not in r["route"][1:]]  # Remove leading /
    single_param = [r for r in all_results if r["route"].count("/") == 2]  # /route/param
    multi_param = [r for r in all_results if r["route"].count("/") > 2]   # /route/p1/p2/...
    
    print(f"   📌 No parameters: {len([r for r in no_params if r['success']])}/{len(no_params)} successful")
    print(f"   📌 Single parameter: {len([r for r in single_param if r['success']])}/{len(single_param)} successful")
    print(f"   📌 Multiple parameters: {len([r for r in multi_param if r['success']])}/{len(multi_param)} successful")
    
    # Specific analysis for multi-parameter routes
    if multi_param:
        print(f"\n🎯 MULTI-PARAMETER ROUTE ANALYSIS:")
        print(f"   🔴 ALL multi-parameter routes failed: {all(not r['success'] for r in multi_param)}")
        print(f"   📋 Multi-parameter routes that failed:")
        for result in multi_param:
            if not result["success"]:
                param_count = result["route"].count("/") - 1
                print(f"      - {result['route']} ({param_count} params, status: {result['status_code']})")
    
    # Server identification
    print(f"\n🖥️  SERVER IDENTIFICATION:")
    video_server_routes = ["/video_feed", "/capture_photo", "/status", "/health"]
    integrated_routes = ["/ping", "/grbl_status", "/button_test", "/test_json"]
    
    video_available = any(r["route"] in video_server_routes and r["success"] for r in all_results)
    integrated_available = any(r["route"] in integrated_routes and r["success"] for r in all_results)
    
    print(f"   📺 VideoServer.py routes available: {video_available}")
    print(f"   🔧 integrated_camera_system.py routes available: {integrated_available}")
    
    if video_available and not any(r["route"].startswith("/move_to") and r["success"] for r in all_results):
        print(f"   ⚠️  CONCLUSION: VideoServer.py is running (lacks multi-parameter routes)")
    elif integrated_available and any(r["route"].startswith("/move_to") and r["success"] for r in all_results):
        print(f"   ✅ CONCLUSION: integrated_camera_system.py is running")
    else:
        print(f"   ❓ CONCLUSION: Mixed or unclear server state")
    
    # Final recommendations
    print(f"\n🎯 RECOMMENDATIONS:")
    if not any(r["route"].startswith("/move_to") and r["success"] for r in all_results):
        print(f"   1. ⚠️  Stop VideoServer.py process")
        print(f"   2. 🚀 Start integrated_camera_system.py instead")
        print(f"   3. 🔄 Re-test multi-parameter routes")
    else:
        print(f"   ✅ System appears to be running correctly")
    
    # Generate report file
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "target_url": base_url,
        "total_tests": len(all_results),
        "successful_tests": len(successful_routes),
        "failed_tests": len(failed_routes),
        "pattern_analysis": {
            "no_parameters": {"total": len(no_params), "successful": len([r for r in no_params if r['success']])},
            "single_parameter": {"total": len(single_param), "successful": len([r for r in single_param if r['success']])},
            "multiple_parameters": {"total": len(multi_param), "successful": len([r for r in multi_param if r['success']])}
        },
        "detailed_results": all_results
    }
    
    report_filename = f"route_investigation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    try:
        with open(report_filename, 'w') as f:
            json.dump(report_data, f, indent=2)
        print(f"\n📄 Detailed report saved: {report_filename}")
    except Exception as e:
        print(f"\n❌ Failed to save report: {e}")
    
    print(f"\n{'=' * 70}")
    print("🏁 INVESTIGATION COMPLETE")
    print("=" * 70)

if __name__ == "__main__":
    main()
