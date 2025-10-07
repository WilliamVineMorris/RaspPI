#!/usr/bin/env python3
"""
YOLO11n NCNN Detection Test Script

Quick test to verify YOLO11n NCNN installation and detection functionality.
Run this before using YOLO detection in production.
"""

import sys
import asyncio
from pathlib import Path

# Add V2.0 to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_yolo_detection():
    """Test YOLO11n NCNN detection system"""
    
    print("=" * 60)
    print("YOLO11n NCNN Detection Test")
    print("=" * 60)
    
    # Test 1: Check NCNN installation
    print("\n[1/6] Checking NCNN installation...")
    try:
        import ncnn
        print(f"✅ NCNN installed: version {getattr(ncnn, '__version__', 'unknown')}")
    except ImportError as e:
        print(f"❌ NCNN not installed: {e}")
        print("   Install with: pip install ncnn")
        print("   Or build from source: https://github.com/Tencent/ncnn/tree/master/python")
        return False
    
    # Test 2: Check OpenCV
    print("\n[2/6] Checking OpenCV installation...")
    try:
        import cv2
        print(f"✅ OpenCV installed: version {cv2.__version__}")
    except ImportError as e:
        print(f"❌ OpenCV not installed: {e}")
        print("   Install with: pip install opencv-python")
        return False
    
    # Test 3: Check model files
    print("\n[3/6] Checking YOLO11n model files...")
    model_param = Path("models/yolo11n_ncnn/yolo11n.param")
    model_bin = Path("models/yolo11n_ncnn/yolo11n.bin")
    
    if model_param.exists() and model_bin.exists():
        param_size = model_param.stat().st_size / 1024  # KB
        bin_size = model_bin.stat().st_size / 1024 / 1024  # MB
        print(f"✅ Model files found:")
        print(f"   - yolo11n.param: {param_size:.1f} KB")
        print(f"   - yolo11n.bin: {bin_size:.1f} MB")
    else:
        print(f"❌ Model files not found:")
        print(f"   Expected: {model_param.parent}")
        print("\n   Download with:")
        print("   wget -O models/yolo11n_ncnn.zip \\")
        print("     https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n_ncnn_model.zip")
        print("   unzip models/yolo11n_ncnn.zip -d models/yolo11n_ncnn/")
        return False
    
    # Test 4: Load detector
    print("\n[4/6] Loading YOLO11n detector...")
    try:
        from camera.yolo11n_ncnn_detector import YOLO11nNCNNDetector
        
        config = {
            'model_param': str(model_param),
            'model_bin': str(model_bin),
            'confidence_threshold': 0.25,
            'padding': 0.15,
            'min_area': 0.05,
            'detection_output_dir': 'calibration/focus_detection'
        }
        
        detector = YOLO11nNCNNDetector(config)
        print("✅ Detector initialized")
        
        # Load model
        if detector.load_model():
            print("✅ Model loaded successfully")
        else:
            print("❌ Failed to load model")
            return False
            
    except Exception as e:
        print(f"❌ Detector initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Test on sample image
    print("\n[5/6] Testing detection on sample image...")
    try:
        import numpy as np
        
        # Create a simple test image with a colored rectangle (simulating an object)
        test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        # Add a "bottle-like" rectangle in center
        cv2.rectangle(test_image, (200, 100), (400, 400), (100, 150, 200), -1)
        
        print("   Running inference on 640×480 test image...")
        result = detector.detect_object(test_image, camera_id="test_camera")
        
        if result:
            x, y, w, h = result
            print(f"✅ Detection successful!")
            print(f"   Focus window: [{x:.3f}, {y:.3f}, {w:.3f}, {h:.3f}]")
        else:
            print("⚠️  No objects detected in test image (this is expected for simple test)")
            print("   Detection will work better with real camera images")
            
    except Exception as e:
        print(f"❌ Detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 6: Cleanup
    print("\n[6/6] Cleaning up...")
    try:
        detector.unload_model()
        print("✅ Model unloaded successfully")
    except Exception as e:
        print(f"⚠️  Cleanup warning: {e}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Enable YOLO detection in config/scanner_config.yaml:")
    print("   cameras.focus_zone.mode: 'yolo_detect'")
    print("2. Run camera calibration to test with real cameras")
    print("3. Check calibration/focus_detection/ for visualization images")
    
    return True


async def test_with_camera():
    """Test YOLO detection with actual Pi cameras"""
    
    print("\n" + "=" * 60)
    print("Testing YOLO Detection with Pi Cameras")
    print("=" * 60)
    
    try:
        from camera.pi_camera_controller import PiCameraController
        from core.config_manager import ConfigManager
        
        print("\n[1/3] Loading configuration...")
        config = ConfigManager('config/scanner_config.yaml')
        camera_config = config.get_section('cameras')
        
        print("[2/3] Initializing camera controller...")
        controller = PiCameraController(camera_config)
        
        if not await controller.initialize():
            print("❌ Failed to initialize camera controller")
            return False
        
        print("✅ Camera controller initialized")
        
        print("\n[3/3] Running calibration (triggers YOLO detection)...")
        result = await controller.auto_calibrate_camera('camera0')
        
        print(f"\n✅ Calibration complete!")
        print(f"   Focus: {result.get('focus', 'N/A')}")
        print(f"   Exposure: {result.get('exposure_time', 'N/A')}")
        print(f"   Gain: {result.get('analogue_gain', 'N/A')}")
        
        print("\n📷 Check detection visualization:")
        print("   ls -lh calibration/focus_detection/")
        
        await controller.shutdown()
        
        return True
        
    except Exception as e:
        print(f"❌ Camera test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test YOLO11n NCNN detection")
    parser.add_argument('--with-camera', action='store_true',
                       help='Test with actual Pi cameras (requires hardware)')
    
    args = parser.parse_args()
    
    if args.with_camera:
        # Test with real cameras
        success = asyncio.run(test_with_camera())
    else:
        # Basic detector test
        success = asyncio.run(test_yolo_detection())
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
