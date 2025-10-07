#!/usr/bin/env python3
"""
Convert YOLO11n PyTorch Model to NCNN Format

This script converts yolo11n.pt to NCNN format optimized for Raspberry Pi.
The NCNN format provides faster inference on ARM processors.

Usage:
    python3 convert_yolo_to_ncnn.py

Requirements:
    - ultralytics package installed (pip install ultralytics)
    - yolo11n.pt in models/ directory
"""

import sys
from pathlib import Path

def convert_yolo_to_ncnn():
    """Convert YOLO11n PyTorch model to NCNN format"""
    
    print("=" * 60)
    print("YOLO11n → NCNN Conversion")
    print("=" * 60)
    
    # Check if ultralytics is installed
    print("\n[1/4] Checking dependencies...")
    try:
        from ultralytics import YOLO
        print("✅ Ultralytics installed")
    except ImportError:
        print("❌ Ultralytics not installed")
        print("   Install with: pip install ultralytics")
        return False
    
    # Check if yolo11n.pt exists
    print("\n[2/4] Checking for YOLO11n PyTorch model...")
    model_path = Path("models/yolo11n.pt")
    
    if not model_path.exists():
        print(f"❌ Model not found: {model_path}")
        print("\n   Please download yolo11n.pt:")
        print("   1. Download from: https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt")
        print("   2. Place in: models/yolo11n.pt")
        print("\n   Or download automatically:")
        print("   python3 -c \"from ultralytics import YOLO; YOLO('yolo11n.pt')\"")
        return False
    
    print(f"✅ Found PyTorch model: {model_path}")
    model_size = model_path.stat().st_size / 1024 / 1024  # MB
    print(f"   Size: {model_size:.1f} MB")
    
    # Load and export model
    print("\n[3/4] Converting to NCNN format...")
    print("   This may take 30-60 seconds...")
    
    try:
        # Load YOLO11n model
        print("   Loading PyTorch model...")
        model = YOLO(str(model_path))
        
        # Export to NCNN
        print("   Exporting to NCNN...")
        model.export(format="ncnn", imgsz=640)
        
        print("✅ Conversion successful!")
        
    except Exception as e:
        print(f"❌ Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Verify output
    print("\n[4/4] Verifying NCNN model files...")
    
    # Ultralytics creates 'yolo11n_ncnn_model' directory
    ncnn_dir = Path("yolo11n_ncnn_model")
    
    if not ncnn_dir.exists():
        print(f"❌ Output directory not found: {ncnn_dir}")
        return False
    
    # Check for NCNN files
    param_file = ncnn_dir / "model.ncnn.param"
    bin_file = ncnn_dir / "model.ncnn.bin"
    
    if not param_file.exists():
        print(f"❌ Param file not found: {param_file}")
        return False
    
    if not bin_file.exists():
        print(f"❌ Bin file not found: {bin_file}")
        return False
    
    param_size = param_file.stat().st_size / 1024  # KB
    bin_size = bin_file.stat().st_size / 1024 / 1024  # MB
    
    print(f"✅ NCNN model files verified:")
    print(f"   - {param_file}: {param_size:.1f} KB")
    print(f"   - {bin_file}: {bin_size:.1f} MB")
    
    # Move to models directory if needed
    target_dir = Path("models/yolo11n_ncnn_model")
    
    if ncnn_dir.resolve() != target_dir.resolve():
        print(f"\n   Moving to: {target_dir}")
        
        # Remove existing directory if present
        if target_dir.exists():
            import shutil
            shutil.rmtree(target_dir)
        
        # Move directory
        import shutil
        shutil.move(str(ncnn_dir), str(target_dir))
        
        print(f"✅ Moved to: {target_dir}")
    
    print("\n" + "=" * 60)
    print("✅ Conversion Complete!")
    print("=" * 60)
    
    print("\nNCNN model ready at:")
    print(f"   {target_dir}/model.ncnn.param")
    print(f"   {target_dir}/model.ncnn.bin")
    
    print("\nNext steps:")
    print("1. Enable YOLO detection in config/scanner_config.yaml:")
    print("   cameras.focus_zone.mode: 'yolo_detect'")
    print("\n2. Test detection:")
    print("   python3 test_yolo_detection.py")
    print("\n3. Test with cameras:")
    print("   python3 test_yolo_detection.py --with-camera")
    
    return True


def main():
    """Main entry point"""
    try:
        success = convert_yolo_to_ncnn()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Conversion cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
