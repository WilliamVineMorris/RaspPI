#!/usr/bin/env python3
"""
Test Edge Detection System
Tests the edge-based object         print(f"\n   Image shape: {image.shape}")
        
        # Save raw image for inspection
        test_output_dir = Path("calibration/edge_detection_test")
        test_output_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(test_output_dir / "raw_capture.jpg"), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
        print(f"💾 Saved raw capture: {test_output_dir / 'raw_capture.jpg'}")
        
        # Try multiple sensitivity levels
        print(f"\n🔍 Testing different edge detection sensitivities...")
        
        sensitivity_configs = [
            (30, 100, "Very Sensitive"),
            (50, 150, "Default"),
            (20, 80, "Maximum Sensitivity")
        ]
        
        best_result = None
        best_desc = None
        
        for canny1, canny2, desc in sensitivity_configs:
            test_config = config.copy()
            test_config['canny_threshold1'] = canny1
            test_config['canny_threshold2'] = canny2
            test_config['detection_output_dir'] = f'calibration/edge_test_{desc.replace(" ", "_")}'
            
            test_detector = EdgeDetector(test_config)
            result = test_detector.detect_object(image, f"camera_{desc.replace(' ', '_')}")
            
            if result:
                print(f"   ✅ {desc} (Canny {canny1}/{canny2}): FOUND object at {result}")
                if best_result is None:
                    best_result = result
                    best_desc = desc
            else:
                print(f"   ⚠️ {desc} (Canny {canny1}/{canny2}): No detection")
        
        if best_result:
            print(f"\n✅ BEST RESULT: {best_desc}")
            result = best_result
        else:
            print(f"\n⚠️ No detections at any sensitivity level")
            print(f"   Check raw_capture.jpg to see if object is visible")
            result = None
        
        # Run detection with default config for final report
        if not result:
            result = detector.detect_object(image, "test_camera")ctor for focus window positioning
"""

import sys
import cv2
import numpy as np
from pathlib import Path

# Add V2.0 to path
sys.path.insert(0, str(Path(__file__).parent))

from camera.edge_detector import EdgeDetector
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_edge_detection():
    """Test edge detection with sample configuration"""
    
    print("=" * 60)
    print("Edge Detection Test")
    print("=" * 60)
    
    # Configuration
    config = {
        'search_region': 0.7,
        'gaussian_blur': 5,
        'canny_threshold1': 50,
        'canny_threshold2': 150,
        'min_contour_area': 0.01,
        'max_contour_area': 0.5,
        'padding': 0.2,
        'detection_output_dir': 'calibration/edge_detection_test'
    }
    
    # Initialize detector
    detector = EdgeDetector(config)
    print(f"\n✅ Edge detector initialized")
    
    # Option 1: Test with camera (if available)
    try:
        from picamera2 import Picamera2
        
        print("\n📷 Camera detected - capturing test image...")
        picam2 = Picamera2()
        config_cam = picam2.create_still_configuration(main={"size": (1920, 1080)})
        picam2.configure(config_cam)
        picam2.start()
        
        import time
        
        # CRITICAL: ArduCam cameras need manual focus control (not libcamera AF API)
        print("🔍 Running ArduCam autofocus to get sharp image...")
        try:
            # Import ArduCam focus control
            import os
            import subprocess
            
            # Check if running on actual hardware with ArduCam
            has_arducam = os.path.exists('/dev/v4l-subdev0') or os.path.exists('/dev/v4l-subdev2')
            
            if has_arducam:
                print("   Detected ArduCam hardware - using manual focus control")
                
                # ArduCam autofocus: Sweep through focus range and find sharpest
                best_sharpness = 0
                best_focus = 5.0  # Default middle position
                
                # Quick focus sweep (0-10 range for ArduCam)
                for focus_pos in [2.0, 4.0, 6.0, 8.0, 10.0]:
                    # Set focus position via v4l2-ctl
                    try:
                        subprocess.run(
                            ['v4l2-ctl', '-d', '/dev/v4l-subdev0', '-c', f'focus_absolute={int(focus_pos * 100)}'],
                            capture_output=True, timeout=1
                        )
                    except:
                        pass  # v4l2-ctl might not be available
                    
                    time.sleep(0.3)
                    
                    # Capture frame and measure sharpness
                    try:
                        test_frame = picam2.capture_array("main")
                        # Simple sharpness metric: variance of Laplacian
                        gray = cv2.cvtColor(test_frame, cv2.COLOR_RGB2GRAY)
                        sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
                        
                        print(f"   Focus {focus_pos:.1f}: sharpness={sharpness:.0f}")
                        
                        if sharpness > best_sharpness:
                            best_sharpness = sharpness
                            best_focus = focus_pos
                    except Exception as e:
                        print(f"   Warning: Sharpness test failed at {focus_pos}: {e}")
                
                # Set best focus position
                print(f"   ✅ Best focus: {best_focus:.1f} (sharpness={best_sharpness:.0f})")
                try:
                    subprocess.run(
                        ['v4l2-ctl', '-d', '/dev/v4l-subdev0', '-c', f'focus_absolute={int(best_focus * 100)}'],
                        capture_output=True, timeout=1
                    )
                except:
                    pass
                
                time.sleep(0.5)  # Let focus settle
            else:
                print("   No ArduCam detected - using standard libcamera autofocus")
                from libcamera import controls
                
                # Standard libcamera autofocus
                picam2.set_controls({
                    "AfMode": controls.AfModeEnum.Continuous,
                    "AfTrigger": controls.AfTriggerEnum.Start
                })
                
                time.sleep(2)
                
                metadata = picam2.capture_metadata()
                af_state = metadata.get("AfState", "unknown")
                lens_position = metadata.get("LensPosition", "unknown")
                print(f"   Autofocus state: {af_state}, lens: {lens_position}")
                
        except Exception as af_error:
            print(f"   ⚠️ Autofocus failed: {af_error}")
            print(f"   Continuing with default focus position...")
            time.sleep(2)  # Let camera warm up anyway
        
        image = picam2.capture_array("main")
        picam2.stop()
        
        print(f"   Image shape: {image.shape}")
        
        # Run detection
        result = detector.detect_object(image, "test_camera")
        
        if result:
            x, y, w, h = result
            print(f"\n✅ Detection successful!")
            print(f"   Focus window: ({x}, {y}, {w}, {h}) pixels")
            print(f"   Area: {w * h / (image.shape[0] * image.shape[1]) * 100:.1f}% of image")
            
            # Show normalized version
            normalized = detector.get_focus_window_normalized(image, "test_camera")
            if normalized:
                print(f"   Normalized: ({normalized[0]:.3f}, {normalized[1]:.3f}, {normalized[2]:.3f}, {normalized[3]:.3f})")
        else:
            print(f"\n⚠️ No objects detected")
            
        print(f"\n💾 Check visualization: calibration/edge_detection_test/test_camera_edge_detection.jpg")
        
    except ImportError:
        print("\n⚠️ Picamera2 not available - testing with synthetic image...")
        
        # Option 2: Create synthetic test image
        width, height = 1920, 1080
        image = np.ones((height, width, 3), dtype=np.uint8) * 150  # Gray background
        
        # Draw a simple object (rectangle with some detail)
        obj_x, obj_y = 800, 400
        obj_w, obj_h = 400, 300
        
        # Object body
        cv2.rectangle(image, (obj_x, obj_y), (obj_x + obj_w, obj_y + obj_h), (100, 150, 200), -1)
        
        # Add some edges/detail
        cv2.rectangle(image, (obj_x + 50, obj_y + 50), (obj_x + 150, obj_y + 150), (50, 100, 150), 3)
        cv2.circle(image, (obj_x + 300, obj_y + 150), 80, (200, 100, 100), 5)
        
        print(f"\n🎨 Created synthetic test image ({width}x{height})")
        
        # Run detection
        result = detector.detect_object(image, "synthetic_test")
        
        if result:
            x, y, w, h = result
            print(f"\n✅ Detection successful!")
            print(f"   Focus window: ({x}, {y}, {w}, {h}) pixels")
            print(f"   Expected center around: ({obj_x + obj_w//2}, {obj_y + obj_h//2})")
            
            # Calculate center of detected window
            det_cx = x + w // 2
            det_cy = y + h // 2
            obj_cx = obj_x + obj_w // 2
            obj_cy = obj_y + obj_h // 2
            
            distance = ((det_cx - obj_cx)**2 + (det_cy - obj_cy)**2)**0.5
            print(f"   Detected center: ({det_cx}, {det_cy})")
            print(f"   Distance from object center: {distance:.1f} pixels")
            
            if distance < 200:
                print(f"   ✅ Accuracy: GOOD (within 200px)")
            else:
                print(f"   ⚠️ Accuracy: Check visualization for details")
        else:
            print(f"\n⚠️ No objects detected in synthetic image")
            
        print(f"\n💾 Check visualization: calibration/edge_detection_test/synthetic_test_edge_detection.jpg")
    
    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


def test_different_thresholds():
    """Test different Canny threshold combinations"""
    
    print("\n" + "=" * 60)
    print("Threshold Sensitivity Test")
    print("=" * 60)
    
    # Create simple test image
    width, height = 800, 600
    image = np.ones((height, width, 3), dtype=np.uint8) * 128
    
    # Draw object with varying edge strength
    cv2.rectangle(image, (250, 150), (550, 450), (80, 80, 80), -1)  # Weak edges
    cv2.rectangle(image, (300, 200), (500, 400), (200, 200, 200), 3)  # Strong edges
    
    # Test different threshold combinations
    thresholds = [
        (30, 100, "Very sensitive"),
        (50, 150, "Default"),
        (70, 200, "Conservative")
    ]
    
    for i, (t1, t2, desc) in enumerate(thresholds):
        config = {
            'search_region': 0.7,
            'gaussian_blur': 5,
            'canny_threshold1': t1,
            'canny_threshold2': t2,
            'min_contour_area': 0.01,
            'max_contour_area': 0.5,
            'padding': 0.2,
            'detection_output_dir': f'calibration/edge_test_{i}'
        }
        
        detector = EdgeDetector(config)
        result = detector.detect_object(image, f"threshold_test_{i}_{desc.replace(' ', '_')}")
        
        if result:
            print(f"   {desc} ({t1}/{t2}): ✅ Detected {result}")
        else:
            print(f"   {desc} ({t1}/{t2}): ⚠️ No detection")
    
    print("=" * 60)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test edge detection system')
    parser.add_argument('--thresholds', action='store_true', 
                       help='Test different threshold combinations')
    
    args = parser.parse_args()
    
    if args.thresholds:
        test_different_thresholds()
    else:
        test_edge_detection()
