#!/usr/bin/env python3
"""
Quick script to set camera to direct BGR mode
"""

import requests
import json

def set_direct_bgr():
    """Set camera to direct BGR mode"""
    try:
        url = "http://localhost:8080/api/camera/color_format"
        data = {
            "camera_id": "camera_1",
            "mode": "bgr_direct"
        }
        
        response = requests.post(url, json=data, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Camera set to direct BGR mode successfully!")
                print(f"Mode: {result.get('color_mode')}")
                print("Colors should now appear correctly in the stream.")
            else:
                print(f"❌ Failed to set BGR mode: {result.get('error')}")
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            print(response.text)
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to camera server. Make sure the web interface is running.")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    print("Setting camera to direct BGR mode...")
    set_direct_bgr()