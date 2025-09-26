#!/usr/bin/env python3
"""
Test Camera Flash API Endpoints

Test script to validate the new camera capture endpoints with flash functionality.
This can be used to test the API before deploying to the Pi.

Created: September 2025
"""

import requests
import json
import time
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"  # Adjust for your Pi's IP
API_ENDPOINTS = {
    'camera1': '/api/camera/capture/camera1',
    'camera2': '/api/camera/capture/camera2', 
    'both': '/api/camera/capture/both',
    'general': '/api/camera/capture'
}

def test_camera_capture(endpoint_name: str, endpoint: str, payload: dict = None):
    """Test a camera capture endpoint"""
    url = BASE_URL + endpoint
    
    if payload is None:
        payload = {"flash": True, "flash_intensity": 80}
    
    print(f"\n🧪 Testing {endpoint_name}: {endpoint}")
    print(f"📤 Payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        
        print(f"📊 Status Code: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success: {result.get('success', False)}")
            print(f"📸 Data: {json.dumps(result.get('data', {}), indent=2)}")
        else:
            print(f"❌ Error Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"🔌 Connection Error: Could not connect to {BASE_URL}")
        print("   Make sure the web interface is running on the Pi")
    except requests.exceptions.Timeout:
        print(f"⏰ Timeout: Request took longer than 30 seconds")
    except Exception as e:
        print(f"💥 Exception: {e}")

def main():
    """Run camera capture API tests"""
    print("🎯 Camera Flash API Test Suite")
    print(f"🔗 Testing against: {BASE_URL}")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test individual camera captures with flash
    test_cases = [
        {
            'name': 'Camera 1 with Flash',
            'endpoint': 'camera1',
            'payload': {"flash": True, "flash_intensity": 80}
        },
        {
            'name': 'Camera 2 with Flash', 
            'endpoint': 'camera2',
            'payload': {"flash": True, "flash_intensity": 80}
        },
        {
            'name': 'Both Cameras with Flash',
            'endpoint': 'both',
            'payload': {"flash": True, "flash_intensity": 80}
        },
        {
            'name': 'Camera 1 without Flash',
            'endpoint': 'camera1',
            'payload': {"flash": False}
        },
        {
            'name': 'General API with Flash',
            'endpoint': 'general',
            'payload': {"camera_id": 0, "flash": True, "flash_intensity": 90}
        },
        {
            'name': 'General API without Flash',
            'endpoint': 'general', 
            'payload': {"camera_id": 1, "flash": False}
        }
    ]
    
    for test_case in test_cases:
        endpoint_url = API_ENDPOINTS[test_case['endpoint']]
        test_camera_capture(
            test_case['name'],
            endpoint_url,
            test_case['payload']
        )
        time.sleep(2)  # Brief delay between tests
    
    print(f"\n🏁 Test Suite Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n📝 Notes:")
    print("   • Flash functionality requires both camera_manager and lighting_controller")
    print("   • Individual camera buttons default to flash enabled")
    print("   • Flash intensity range: 0-100 (default: 80)")
    print("   • Synchronized capture uses the camera manager's flash sync method")

if __name__ == "__main__":
    main()