#!/usr/bin/env python3
"""
Quick Camera Detection Script
Quickly identifies available camera devices for Arducam setup
"""

import cv2
import time

def quick_camera_scan():
    """Quick scan for working cameras"""
    print("=== Quick Camera Detection ===")
    print("Scanning camera devices 0-9...")
    print()
    
    working_cameras = []
    
    for i in range(10):
        try:
            print(f"Testing camera {i}...", end=" ")
            
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Try to read a frame
                ret, frame = cap.read()
                if ret and frame is not None:
                    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                    print(f"✅ WORKING - {int(width)}x{int(height)}")
                    working_cameras.append(i)
                else:
                    print("❌ Cannot capture frames")
                cap.release()
            else:
                print("❌ Cannot open")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n" + "="*40)
    print("RESULTS:")
    print("="*40)
    
    if working_cameras:
        print(f"✅ Working cameras: {working_cameras}")
        print("\nFor dual camera setup, use:")
        if len(working_cameras) >= 2:
            print(f"  Camera 1 ID: {working_cameras[0]}")
            print(f"  Camera 2 ID: {working_cameras[1]}")
        else:
            print(f"  Camera 1 ID: {working_cameras[0]}")
            print("  Only one camera available")
    else:
        print("❌ No working cameras found!")
        print("\nTroubleshooting:")
        print("1. Check USB connections")
        print("2. Check camera power")
        print("3. Try: sudo modprobe uvcvideo")
        print("4. Check permissions: sudo usermod -a -G video $USER")

if __name__ == "__main__":
    quick_camera_scan()