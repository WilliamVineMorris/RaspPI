#!/usr/bin/env python3
"""
Dual Camera Capture Test for Raspberry Pi 5
Tests capturing from two cameras simultaneously and saves images with timestamps
"""

import cv2
import numpy as np
import time
import os
import threading
from datetime import datetime
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DualCameraCapture:
    def __init__(self, camera1_id=0, camera2_id=1, save_dir="dual_camera_captures"):
        """
        Initialize dual camera capture system
        
        Args:
            camera1_id: Camera device ID for first camera (usually 0)
            camera2_id: Camera device ID for second camera (usually 1)
            save_dir: Directory to save captured images
        """
        self.camera1_id = camera1_id
        self.camera2_id = camera2_id
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        
        # Camera objects
        self.camera1 = None
        self.camera2 = None
        
        # Capture settings
        self.resolution = (1920, 1080)  # Full HD
        self.fps = 30
        
        # Threading
        self.capture_active = False
        self.capture_thread = None
        
    def initialize_cameras(self) -> bool:
        """Initialize both cameras with optimal settings for Pi5"""
        try:
            logger.info("Initializing cameras...")
            
            # Initialize Camera 1
            self.camera1 = cv2.VideoCapture(self.camera1_id)
            if not self.camera1.isOpened():
                logger.error(f"Failed to open camera {self.camera1_id}")
                return False
                
            # Initialize Camera 2
            self.camera2 = cv2.VideoCapture(self.camera2_id)
            if not self.camera2.isOpened():
                logger.error(f"Failed to open camera {self.camera2_id}")
                return False
            
            # Configure Camera 1
            self.camera1.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera1.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera1.set(cv2.CAP_PROP_FPS, self.fps)
            self.camera1.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for lower latency
            
            # Configure Camera 2
            self.camera2.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.camera2.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            self.camera2.set(cv2.CAP_PROP_FPS, self.fps)
            self.camera2.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Warm up cameras
            logger.info("Warming up cameras...")
            for _ in range(10):
                self.camera1.read()
                self.camera2.read()
                time.sleep(0.1)
            
            logger.info("Cameras initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing cameras: {e}")
            return False
    
    def capture_single_frame(self) -> tuple:
        """Capture a single frame from both cameras simultaneously"""
        timestamp = datetime.now()
        
        # Capture frames as close to simultaneously as possible
        ret1, frame1 = self.camera1.read()
        ret2, frame2 = self.camera2.read()
        
        if not ret1:
            logger.warning("Failed to capture from camera 1")
            frame1 = None
            
        if not ret2:
            logger.warning("Failed to capture from camera 2")
            frame2 = None
            
        return frame1, frame2, timestamp
    
    def save_frames(self, frame1, frame2, timestamp):
        """Save captured frames with timestamp"""
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
        
        if frame1 is not None:
            filename1 = self.save_dir / f"cam1_{timestamp_str}.jpg"
            cv2.imwrite(str(filename1), frame1)
            logger.info(f"Saved camera 1 frame: {filename1}")
            
        if frame2 is not None:
            filename2 = self.save_dir / f"cam2_{timestamp_str}.jpg"
            cv2.imwrite(str(filename2), frame2)
            logger.info(f"Saved camera 2 frame: {filename2}")
    
    def display_frames(self, frame1, frame2):
        """Display both camera frames in real-time"""
        display_height = 480
        display_width = 640
        
        if frame1 is not None:
            frame1_resized = cv2.resize(frame1, (display_width, display_height))
            cv2.imshow('Camera 1', frame1_resized)
            
        if frame2 is not None:
            frame2_resized = cv2.resize(frame2, (display_width, display_height))
            cv2.imshow('Camera 2', frame2_resized)
            
        # Create side-by-side view if both frames exist
        if frame1 is not None and frame2 is not None:
            frame1_small = cv2.resize(frame1, (display_width//2, display_height//2))
            frame2_small = cv2.resize(frame2, (display_width//2, display_height//2))
            combined = np.hstack((frame1_small, frame2_small))
            cv2.imshow('Dual Camera View', combined)
    
    def test_capture_performance(self, duration_seconds=10):
        """Test capture performance for specified duration"""
        logger.info(f"Starting {duration_seconds}s performance test...")
        
        start_time = time.time()
        frame_count = 0
        successful_captures = 0
        
        while time.time() - start_time < duration_seconds:
            frame1, frame2, timestamp = self.capture_single_frame()
            
            frame_count += 1
            if frame1 is not None and frame2 is not None:
                successful_captures += 1
                
            # Display frames
            self.display_frames(frame1, frame2)
            
            # Check for exit key
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        elapsed_time = time.time() - start_time
        fps_achieved = frame_count / elapsed_time
        success_rate = (successful_captures / frame_count) * 100 if frame_count > 0 else 0
        
        logger.info(f"Performance test results:")
        logger.info(f"  Duration: {elapsed_time:.2f}s")
        logger.info(f"  Total frames: {frame_count}")
        logger.info(f"  Successful captures: {successful_captures}")
        logger.info(f"  Success rate: {success_rate:.1f}%")
        logger.info(f"  Average FPS: {fps_achieved:.2f}")
        
        return fps_achieved, success_rate
    
    def synchronized_capture_burst(self, num_frames=10, interval=0.5):
        """Capture a burst of synchronized frames"""
        logger.info(f"Capturing {num_frames} synchronized frames...")
        
        for i in range(num_frames):
            frame1, frame2, timestamp = self.capture_single_frame()
            
            if frame1 is not None and frame2 is not None:
                self.save_frames(frame1, frame2, timestamp)
                logger.info(f"Captured frame pair {i+1}/{num_frames}")
            else:
                logger.warning(f"Failed to capture frame pair {i+1}/{num_frames}")
                
            if i < num_frames - 1:  # Don't sleep after last frame
                time.sleep(interval)
    
    def live_preview(self):
        """Live preview of both cameras"""
        logger.info("Starting live preview. Press 'q' to quit, 's' to save frame, 'b' for burst capture")
        
        while True:
            frame1, frame2, timestamp = self.capture_single_frame()
            self.display_frames(frame1, frame2)
            
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                break
            elif key == ord('s'):
                self.save_frames(frame1, frame2, timestamp)
                logger.info("Frame saved!")
            elif key == ord('b'):
                logger.info("Starting burst capture...")
                self.synchronized_capture_burst(5, 0.2)
                logger.info("Burst capture complete!")
    
    def cleanup(self):
        """Clean up camera resources"""
        logger.info("Cleaning up cameras...")
        
        if self.camera1:
            self.camera1.release()
        if self.camera2:
            self.camera2.release()
            
        cv2.destroyAllWindows()
        logger.info("Cleanup complete")

def main():
    """Main test function"""
    print("=== Raspberry Pi 5 Dual Camera Capture Test ===")
    
    # Create capture system
    dual_cam = DualCameraCapture()
    
    try:
        # Initialize cameras
        if not dual_cam.initialize_cameras():
            logger.error("Failed to initialize cameras. Check connections and permissions.")
            return
        
        # Test menu
        while True:
            print("\nDual Camera Test Options:")
            print("1. Live preview")
            print("2. Performance test (10s)")
            print("3. Synchronized burst capture (10 frames)")
            print("4. Single frame capture")
            print("5. Exit")
            
            choice = input("Enter choice (1-5): ").strip()
            
            if choice == '1':
                dual_cam.live_preview()
            elif choice == '2':
                dual_cam.test_capture_performance(10)
            elif choice == '3':
                dual_cam.synchronized_capture_burst(10, 0.5)
            elif choice == '4':
                frame1, frame2, timestamp = dual_cam.capture_single_frame()
                dual_cam.save_frames(frame1, frame2, timestamp)
                print("Single frame captured and saved!")
            elif choice == '5':
                break
            else:
                print("Invalid choice. Please try again.")
    
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
    except Exception as e:
        logger.error(f"Error during test: {e}")
    finally:
        dual_cam.cleanup()

if __name__ == "__main__":
    main()