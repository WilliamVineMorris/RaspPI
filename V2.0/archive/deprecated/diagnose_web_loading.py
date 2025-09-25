#!/usr/bin/env python3
"""
Web Interface Loading Diagnostic Tool
Check why webpage doesn't finish loading and camera streams are missing
"""

import requests
import time
import sys
import os
from pathlib import Path

def test_web_resources():
    """Test if all web resources load properly"""
    print("🌐 Testing Web Interface Resources...")
    
    base_url = "http://localhost:8080"
    
    # Critical resources that must load
    resources = [
        ("/", "Main page"),
        ("/manual", "Manual control page"),
        ("/api/status", "Status API"),
        ("/static/css/scanner.css", "Main stylesheet"),
        ("/static/js/scanner-base.js", "Base JavaScript"),
        ("/static/js/manual-control.js", "Manual control JavaScript"),
        ("/camera/0", "Camera 0 stream"),
        ("/camera/1", "Camera 1 stream")
    ]
    
    results = {}
    
    for path, description in resources:
        url = base_url + path
        print(f"🔍 Testing {description}: {path}")
        
        try:
            if path.startswith("/camera/"):
                # Camera streams need different handling
                response = requests.get(url, timeout=5, stream=True)
                if response.status_code == 200:
                    # Check if it's actually streaming
                    content_type = response.headers.get('content-type', '')
                    if 'multipart' in content_type or 'image' in content_type:
                        print(f"   ✅ Camera stream active: {content_type}")
                        results[path] = True
                    else:
                        print(f"   ❌ Not a valid stream: {content_type}")
                        results[path] = False
                else:
                    print(f"   ❌ Stream failed: {response.status_code}")
                    results[path] = False
            else:
                # Regular web resources
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    size = len(response.content)
                    print(f"   ✅ Loaded: {size} bytes")
                    results[path] = True
                else:
                    print(f"   ❌ Failed: {response.status_code}")
                    results[path] = False
                    
        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection failed - is server running?")
            results[path] = False
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout (resource too slow)")
            results[path] = False
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results[path] = False
        
        time.sleep(0.5)  # Brief pause between tests
    
    return results

def test_api_responses():
    """Test API endpoints for proper JSON responses"""
    print("\n🔌 Testing API Endpoints...")
    
    base_url = "http://localhost:8080"
    
    api_tests = [
        ("/api/status", "GET", "System status"),
        ("/api/camera/status", "GET", "Camera status"),  
        ("/api/motion/status", "GET", "Motion status")
    ]
    
    for path, method, description in api_tests:
        url = base_url + path
        print(f"🔍 Testing {description}: {method} {path}")
        
        try:
            if method == "GET":
                response = requests.get(url, timeout=10)
            else:
                response = requests.post(url, timeout=10)
            
            print(f"   Status: {response.status_code}")
            
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                try:
                    data = response.json()
                    print(f"   ✅ Valid JSON response")
                    
                    # Show key information
                    if 'cameras' in data:
                        print(f"   📷 Cameras: {data['cameras']}")
                    if 'motion' in data:
                        print(f"   🔧 Motion: {data['motion']}")
                    if 'system' in data:
                        print(f"   ⚙️  System: {data['system']}")
                        
                except Exception as e:
                    print(f"   ❌ JSON parse error: {e}")
            else:
                print(f"   ⚠️  Non-JSON response: {content_type}")
                print(f"   Content preview: {response.text[:100]}...")
                
        except Exception as e:
            print(f"   ❌ Request failed: {e}")

def check_static_files():
    """Check if static files exist on disk"""
    print("\n📁 Checking Static Files on Disk...")
    
    static_dir = Path(__file__).parent / "web" / "static"
    template_dir = Path(__file__).parent / "web" / "templates"
    
    critical_files = [
        (static_dir / "css" / "scanner.css", "Main stylesheet"),
        (static_dir / "js" / "scanner-base.js", "Base JavaScript"),
        (static_dir / "js" / "manual-control.js", "Manual control JS"),
        (template_dir / "manual.html", "Manual control template"),
        (template_dir / "base.html", "Base template")
    ]
    
    for file_path, description in critical_files:
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"   ✅ {description}: {size} bytes")
        else:
            print(f"   ❌ Missing: {description} at {file_path}")

def diagnose_camera_issues():
    """Diagnose camera-specific issues"""
    print("\n📷 Camera Stream Diagnosis...")
    
    # Check if cameras are physically available
    try:
        result = os.system("libcamera-hello --list-cameras > /tmp/camera_diag.txt 2>&1")
        
        if os.path.exists("/tmp/camera_diag.txt"):
            with open("/tmp/camera_diag.txt", "r") as f:
                output = f.read()
            
            if "Available cameras" in output:
                print("✅ libcamera detects cameras")
                camera_lines = [line for line in output.split('\n') if ':' in line and ('imx' in line.lower() or 'arducam' in line.lower())]
                for line in camera_lines:
                    print(f"   📷 {line.strip()}")
            else:
                print("❌ libcamera shows no cameras")
                print(f"   Output: {output[:200]}...")
        
    except Exception as e:
        print(f"❌ Camera check failed: {e}")
    
    # Test camera streams specifically
    print("\n🎥 Testing Camera Stream URLs...")
    for cam_id in [0, 1]:
        url = f"http://localhost:8080/camera/{cam_id}"
        try:
            response = requests.get(url, timeout=3, stream=True)
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                print(f"   ✅ Camera {cam_id}: {content_type}")
            else:
                print(f"   ❌ Camera {cam_id}: HTTP {response.status_code}")
        except Exception as e:
            print(f"   ❌ Camera {cam_id}: {e}")

def main():
    """Main diagnostic function"""
    print("🚀 Web Interface Loading Diagnostic")
    print("=" * 50)
    
    # Check if server is running
    try:
        response = requests.get("http://localhost:8080", timeout=3)
        print("✅ Web server is responding")
    except:
        print("❌ Web server not responding!")
        print("💡 Start server first: python3 run_web_interface_fixed.py --mode production")
        return
    
    # Run diagnostics
    print("\n" + "=" * 50)
    
    # Test all web resources
    results = test_web_resources()
    
    # Test API endpoints
    test_api_responses()
    
    # Check static files
    check_static_files()
    
    # Diagnose camera issues
    diagnose_camera_issues()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 DIAGNOSTIC SUMMARY")
    
    failed_resources = [path for path, success in results.items() if not success]
    
    if failed_resources:
        print("❌ Issues found:")
        for resource in failed_resources:
            print(f"   • {resource} failed to load")
        
        print("\n🔧 Recommendations:")
        if any("/camera/" in r for r in failed_resources):
            print("   • Camera streams not working - check camera initialization")
            print("   • Try: python3 check_hardware.py")
        if any("/static/" in r for r in failed_resources):
            print("   • Static files missing - check web directory structure")
        if any("/api/" in r for r in failed_resources):
            print("   • API issues - check server logs")
            
    else:
        print("✅ All resources loading successfully")
        print("💡 If webpage still doesn't finish loading, check browser console for JavaScript errors")

if __name__ == "__main__":
    main()