#!/usr/bin/env python3
"""
Simple web interface troubleshooting script
"""

import sys
import os
import time
import requests
import json

def test_web_interface_loading():
    """Test if web interface loads properly"""
    print("🌐 Web Interface Loading Test")
    print("=" * 40)
    
    base_url = "http://localhost:8080"  # Default port
    
    tests = [
        ("/", "Main page"),
        ("/manual", "Manual control page"),
        ("/api/status", "Status API"),
        ("/static/css/scanner.css", "CSS file"),
        ("/static/js/scanner-base.js", "JavaScript base"),
        ("/static/js/manual-control.js", "Manual control JS")
    ]
    
    results = []
    
    for endpoint, description in tests:
        url = base_url + endpoint
        print(f"🔍 Testing {description}: {url}")
        
        try:
            response = requests.get(url, timeout=10)
            status = response.status_code
            size = len(response.content)
            content_type = response.headers.get('content-type', 'unknown')
            
            if status == 200:
                print(f"   ✅ OK - Status: {status}, Size: {size} bytes, Type: {content_type}")
                results.append((description, True, status, size))
            else:
                print(f"   ❌ Failed - Status: {status}")
                results.append((description, False, status, 0))
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - Is web server running?")
            results.append((description, False, "Connection Error", 0))
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout")
            results.append((description, False, "Timeout", 0))
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append((description, False, str(e), 0))
    
    # Summary
    print("\n" + "=" * 40)
    print("📊 Test Summary:")
    
    passed = sum(1 for _, success, _, _ in results if success)
    total = len(results)
    
    for description, success, status, size in results:
        status_icon = "✅" if success else "❌"
        print(f"   {status_icon} {description}: {status}")
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed < total:
        print("\n🔧 Troubleshooting Tips:")
        print("   1. Check if web server is running:")
        print("      python3 run_web_interface_fixed.py --mode development")
        print("   2. Try forcing Flask server:")
        print("      python3 run_web_interface_fixed.py --force-flask")
        print("   3. Check server logs for errors")
    
    return passed == total

def test_api_responses():
    """Test API response format"""
    print("\n🔌 API Response Format Test")
    print("=" * 40)
    
    api_endpoints = [
        "/api/status",
        "/api/debug/restart-monitor"  # POST endpoint
    ]
    
    for endpoint in api_endpoints:
        url = f"http://localhost:8080{endpoint}"
        print(f"🔍 Testing {endpoint}")
        
        try:
            if endpoint.endswith("restart-monitor"):
                # POST request
                response = requests.post(url, 
                                       headers={'Content-Type': 'application/json'},
                                       timeout=10)
            else:
                # GET request
                response = requests.get(url, timeout=10)
            
            content_type = response.headers.get('content-type', '')
            
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    print(f"   ✅ Valid JSON response")
                    print(f"   📊 Status: {response.status_code}")
                    print(f"   📝 Keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON despite content-type")
                    print(f"   📄 Response: {response.text[:100]}...")
            else:
                print(f"   ⚠️  Non-JSON response: {content_type}")
                print(f"   📄 Content: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   ❌ Error: {e}")

def main():
    """Main test function"""
    print("🚀 Web Interface Troubleshooting Tool")
    print("=" * 50)
    
    # Test basic loading
    web_works = test_web_interface_loading()  
    
    if web_works:
        # Test API if web interface loads
        test_api_responses()
        
        print("\n🎯 Recommendations:")
        print("   ✅ Web interface appears to be working")
        print("   📱 Try accessing from browser: http://raspberrypi:8080")
        print("   🔄 Test restart monitor button in Manual Control tab")
    else:
        print("\n🔧 Next Steps:")
        print("   1. Start web interface:")
        print("      python3 run_web_interface_fixed.py --mode development")
        print("   2. Check for errors in terminal output")
        print("   3. Try different port if 8080 is busy")

if __name__ == "__main__":
    main()