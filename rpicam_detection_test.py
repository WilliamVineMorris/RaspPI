#!/usr/bin/env python3
"""
Raspberry Pi Camera Detection Test
Tests both rpicam-still command and OpenCV camera access methods
"""

import subprocess
import cv2
import time
import os
import sys

def test_rpicam_command():
    """Test if rpicam-still can detect cameras"""
    print("=== Testing rpicam-still command ===")
    
    # Test camera 0
    try:
        print("Testing camera 0 with rpicam-still...")
        result = subprocess.run(['rpicam-still', '--camera', '0', '--timeout', '1', '--nopreview', '-o', '/tmp/test_cam0.jpg'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Camera 0: SUCCESS with rpicam-still")
            # Clean up test file
            if os.path.exists('/tmp/test_cam0.jpg'):
                os.remove('/tmp/test_cam0.jpg')
        else:
            print(f"❌ Camera 0: FAILED - {result.stderr}")
    except Exception as e:
        print(f"❌ Camera 0: ERROR - {e}")
    
    # Test camera 1
    try:
        print("Testing camera 1 with rpicam-still...")
        result = subprocess.run(['rpicam-still', '--camera', '1', '--timeout', '1', '--nopreview', '-o', '/tmp/test_cam1.jpg'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            print("✅ Camera 1: SUCCESS with rpicam-still")
            # Clean up test file
            if os.path.exists('/tmp/test_cam1.jpg'):
                os.remove('/tmp/test_cam1.jpg')
        else:
            print(f"❌ Camera 1: FAILED - {result.stderr}")
    except Exception as e:
        print(f"❌ Camera 1: ERROR - {e}")

def test_opencv_methods():
    """Test different OpenCV camera access methods"""
    print("\n=== Testing OpenCV Methods ===")
    
    # Method 1: Try direct indices
    print("Method 1: Direct camera indices...")
    for i in range(2):
        try:
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ Camera {i}: Working with OpenCV direct index")
                else:
                    print(f"❌ Camera {i}: Opens but cannot read frames")
            else:
                print(f"❌ Camera {i}: Cannot open")
            cap.release()
        except Exception as e:
            print(f"❌ Camera {i}: ERROR - {e}")
    
    # Method 2: Try with CAP_V4L2 backend
    print("\nMethod 2: V4L2 backend...")
    for i in range(2):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_V4L2)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ Camera {i}: Working with V4L2 backend")
                else:
                    print(f"❌ Camera {i}: Opens but cannot read frames (V4L2)")
            else:
                print(f"❌ Camera {i}: Cannot open (V4L2)")
            cap.release()
        except Exception as e:
            print(f"❌ Camera {i}: ERROR (V4L2) - {e}")
    
    # Method 3: Try with GStreamer backend (if available)
    print("\nMethod 3: GStreamer backend...")
    for i in range(2):
        try:
            cap = cv2.VideoCapture(i, cv2.CAP_GSTREAMER)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    print(f"✅ Camera {i}: Working with GStreamer backend")
                else:
                    print(f"❌ Camera {i}: Opens but cannot read frames (GStreamer)")
            else:
                print(f"❌ Camera {i}: Cannot open (GStreamer)")
            cap.release()
        except Exception as e:
            print(f"❌ Camera {i}: ERROR (GStreamer) - {e}")

def check_video_devices():
    """Check what video devices exist"""
    print("\n=== Video Device Check ===")
    
    # Check /dev/video* devices
    video_devices = []
    for i in range(10):
        device_path = f"/dev/video{i}"
        if os.path.exists(device_path):
            video_devices.append(device_path)
    
    print(f"Found video devices: {video_devices}")
    
    # Check camera modules
    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        if 'bcm2835_v4l2' in result.stdout:
            print("✅ bcm2835_v4l2 module loaded (legacy camera)")
        else:
            print("❌ bcm2835_v4l2 module not loaded")
            
        if 'uvcvideo' in result.stdout:
            print("✅ uvcvideo module loaded (USB cameras)")
        else:
            print("❌ uvcvideo module not loaded")
            
    except Exception as e:
        print(f"Could not check kernel modules: {e}")

def check_camera_info():
    """Check camera information"""
    print("\n=== Camera Information ===")
    
    # Check rpicam-hello for camera list
    try:
        result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("Camera list from rpicam-hello:")
            print(result.stdout)
        else:
            print(f"rpicam-hello failed: {result.stderr}")
    except Exception as e:
        print(f"Could not run rpicam-hello: {e}")

def main():
    print("=== Raspberry Pi Camera Detection Diagnostic ===")
    print("This script will test different methods to access your cameras\n")
    
    # Test rpicam command
    test_rpicam_command()
    
    # Check video devices
    check_video_devices()
    
    # Check camera info
    check_camera_info()
    
    # Test OpenCV methods
    test_opencv_methods()
    
    print("\n=== RECOMMENDATIONS ===")
    print("Based on the results above:")
    print("1. If rpicam-still works but OpenCV doesn't:")
    print("   - Your cameras use the modern Pi camera stack")
    print("   - Need to enable legacy camera support OR")
    print("   - Use rpicam commands instead of OpenCV")
    print("\n2. To enable legacy support (if needed):")
    print("   - Add 'start_x=1' to /boot/config.txt")
    print("   - Add 'gpu_mem=128' to /boot/config.txt")
    print("   - Run: sudo modprobe bcm2835-v4l2")
    print("\n3. Alternative: Use rpicam-still for capture in Python")

if __name__ == "__main__":
    main()