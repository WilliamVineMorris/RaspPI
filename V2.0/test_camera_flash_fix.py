#!/usr/bin/env python3
"""
Test Camera Flash Functionality

Quick test to verify that the camera flash capture is working correctly
after fixing the async coordination issues.

Usage:
    python test_camera_flash_fix.py

Created: September 2025
"""

import requests
import json
import time
from datetime import datetime

def test_camera_endpoints():
    """Test the camera capture endpoints"""
    
    BASE_URL = "http://localhost:5000"  # Adjust for your setup
    
    print("🧪 Testing Camera Flash Functionality After Async Fix")
    print(f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Test cases
    test_cases = [
        {
            'name': 'Individual Camera without Flash',
            'endpoint': '/api/camera/capture/camera1',
            'payload': {'flash': False}
        },
        {
            'name': 'Individual Camera with Flash',
            'endpoint': '/api/camera/capture/camera1', 
            'payload': {'flash': True, 'flash_intensity': 80}
        },
        {
            'name': 'Both Cameras with Flash',
            'endpoint': '/api/camera/capture/both',
            'payload': {'flash': True, 'flash_intensity': 80}
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"🔬 Test {i}: {test_case['name']}")
        print(f"📡 Endpoint: {test_case['endpoint']}")
        print(f"📤 Payload: {json.dumps(test_case['payload'], indent=2)}")
        
        try:
            response = requests.post(
                BASE_URL + test_case['endpoint'],
                json=test_case['payload'],
                timeout=30
            )
            
            print(f"📊 Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success: {result.get('success', False)}")
                
                if result.get('success'):
                    data = result.get('data', {})
                    print(f"📸 Camera: {data.get('camera_id', 'N/A')}")
                    print(f"⚡ Flash Used: {data.get('flash_used', False)}")
                    print(f"🎯 Flash Intensity: {data.get('flash_intensity', 'N/A')}%")
                    print(f"🖼️ Image Captured: {data.get('image_captured', False)}")
                else:
                    print(f"❌ Error in response: {result}")
            else:
                print(f"❌ HTTP Error: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print("🔌 Connection Error: Web interface not running")
            print("   Start the web interface first: python run_web_interface.py")
        except requests.exceptions.Timeout:
            print("⏰ Timeout: Request took longer than 30 seconds")
        except Exception as e:
            print(f"💥 Exception: {e}")
        
        print("-" * 60)
        time.sleep(2)  # Brief pause between tests
    
    print("🏁 Camera flash testing completed!")
    print()
    print("📝 Expected Results:")
    print("  • Non-flash capture: success=True, flash_used=False")
    print("  • Flash capture: success=True, flash_used=True, flash_intensity=80")  
    print("  • Both cameras: success=True, synchronized=True, flash_used=True")
    print()
    print("🚨 If any tests fail, check:")
    print("  • Web interface is running (python run_web_interface.py)")
    print("  • Camera hardware is connected and functional")
    print("  • LED lighting system is available and configured")
    print("  • No async/await errors in the logs")

if __name__ == "__main__":
    test_camera_endpoints()