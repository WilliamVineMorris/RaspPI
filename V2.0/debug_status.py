#!/usr/bin/env python3
"""
Quick test script to check what the status API is returning
"""

import requests
import json
import sys

def test_status_api():
    try:
        # Try to get status from the API
        response = requests.get('http://127.0.0.1:5000/api/status', timeout=5)
        response.raise_for_status()
        
        status = response.json()
        
        print("=== FULL STATUS RESPONSE ===")
        print(json.dumps(status, indent=2))
        
        print("\n=== CAMERA STATUS DETAILS ===")
        cameras = status.get('cameras', {})
        print(f"Available: {cameras.get('available', 'MISSING')}")
        print(f"Active: {cameras.get('active', 'MISSING')}")
        print(f"Active Cameras: {cameras.get('active_cameras', 'MISSING')}")
        print(f"Status: {cameras.get('status', 'MISSING')}")
        
        print("\n=== MOTION STATUS DETAILS ===")
        motion = status.get('motion', {})
        print(f"Connected: {motion.get('connected', 'MISSING')}")
        print(f"Status: {motion.get('status', 'MISSING')}")
        print(f"Position: {motion.get('position', 'MISSING')}")
        
    except requests.exceptions.ConnectionError:
        print("ERROR: Could not connect to web interface. Make sure it's running on http://127.0.0.1:5000")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_status_api()