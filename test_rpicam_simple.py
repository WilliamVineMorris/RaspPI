#!/usr/bin/env python3
"""
Simple test script for rpicam-still camera detection and capture
"""

import subprocess
import os
import time

def test_camera_detection():
    """Test camera detection with rpicam-still"""
    print("=== Testing Camera Detection ===")
    
    available_cameras = []
    
    for camera_id in [0, 1]:
        try:
            print(f"Testing camera {camera_id}...")
            result = subprocess.run([
                'rpicam-still', '--camera', str(camera_id), 
                '--timeout', '1', '--nopreview', '-o', '/tmp/test_cam.jpg'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(f"✅ Camera {camera_id}: Working")
                available_cameras.append(camera_id)
                # Clean up test file
                if os.path.exists('/tmp/test_cam.jpg'):
                    os.remove('/tmp/test_cam.jpg')
            else:
                print(f"❌ Camera {camera_id}: Failed")
                print(f"   Error: {result.stderr.strip()}")
                
        except Exception as e:
            print(f"❌ Camera {camera_id}: Exception - {e}")
    
    return available_cameras

def test_capture(camera_id):
    """Test high-quality capture from a camera"""
    print(f"\n=== Testing Capture from Camera {camera_id} ===")
    
    timestamp = int(time.time())
    filename = f"test_capture_cam{camera_id}_{timestamp}.jpg"
    
    try:
        cmd = [
            'rpicam-still',
            '--camera', str(camera_id),
            '--output', filename,
            '--width', '4608',
            '--height', '2592',
            '--timeout', '3000',
            '--nopreview',
            '--quality', '95'
        ]
        
        print(f"Capturing with command: {' '.join(cmd)}")
        start_time = time.time()
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        
        capture_time = time.time() - start_time
        
        if result.returncode == 0 and os.path.exists(filename):
            file_size = os.path.getsize(filename) / (1024 * 1024)  # MB
            print(f"✅ Capture successful!")
            print(f"   File: {filename}")
            print(f"   Size: {file_size:.1f} MB")
            print(f"   Time: {capture_time:.2f} seconds")
            return True
        else:
            print(f"❌ Capture failed!")
            print(f"   Error: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"❌ Capture exception: {e}")
        return False

def main():
    print("Simple rpicam-still Test Script")
    print("="*40)
    
    # Test detection
    cameras = test_camera_detection()
    
    if not cameras:
        print("\n❌ No cameras detected!")
        return
    
    print(f"\n📋 Found {len(cameras)} working camera(s): {cameras}")
    
    # Test capture from each camera
    for camera_id in cameras:
        success = test_capture(camera_id)
        if not success:
            print(f"Warning: Camera {camera_id} detection succeeded but capture failed")
    
    print("\n✅ Test completed!")

if __name__ == "__main__":
    main()