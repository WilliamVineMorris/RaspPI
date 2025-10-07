#!/bin/bash
# YOLO11n NCNN Model Conversion Script
# Converts YOLO11n PyTorch model to NCNN format for Raspberry Pi

set -e  # Exit on error

echo "=========================================="
echo "YOLO11n → NCNN Conversion"
echo "=========================================="
echo ""

# Check if we're in the V2.0 directory
if [ ! -f "config/scanner_config.yaml" ]; then
    echo "❌ Error: Must run from V2.0 directory"
    echo "   cd ~/scanner/V2.0"
    echo "   bash setup_yolo_model.sh"
    exit 1
fi

# Create models directory
echo "[1/5] Creating models directory..."
mkdir -p models
echo "✅ Directory ready: models/"

# Check if NCNN model already exists
if [ -f "models/yolo11n_ncnn_model/model.ncnn.param" ] && [ -f "models/yolo11n_ncnn_model/model.ncnn.bin" ]; then
    echo ""
    echo "⚠️  NCNN model already exists:"
    ls -lh models/yolo11n_ncnn_model/
    echo ""
    read -p "Re-convert? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "✅ Using existing NCNN model files"
        exit 0
    fi
fi

# Check if yolo11n.pt exists
echo ""
echo "[2/5] Checking for YOLO11n PyTorch model..."
if [ ! -f "models/yolo11n.pt" ]; then
    echo "❌ Error: models/yolo11n.pt not found"
    echo ""
    echo "Please add yolo11n.pt to the models/ directory:"
    echo ""
    echo "Option 1: Download manually"
    echo "   wget -O models/yolo11n.pt https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
    echo ""
    echo "Option 2: Let ultralytics download it"
    echo "   python3 -c \"from ultralytics import YOLO; YOLO('yolo11n.pt')\""
    echo "   Then move yolo11n.pt to models/ directory"
    exit 1
fi

echo "✅ Found PyTorch model: models/yolo11n.pt"
pt_size=$(stat -f%z "models/yolo11n.pt" 2>/dev/null || stat -c%s "models/yolo11n.pt")
pt_mb=$((pt_size / 1024 / 1024))
echo "   Size: ${pt_mb} MB"

# Check Python packages
echo ""
echo "[3/5] Checking Python dependencies..."

if ! python3 -c "import ultralytics" 2>/dev/null; then
    echo "❌ Error: ultralytics not installed"
    echo "   Install with: pip install ultralytics"
    exit 1
fi
echo "✅ ultralytics installed"

# Run conversion
echo ""
echo "[4/5] Converting to NCNN format..."
echo "   This may take 30-60 seconds..."
echo ""

python3 convert_yolo_to_ncnn.py || {
    echo "❌ Conversion failed"
    exit 1
}

# Verify files
echo ""
echo "[5/5] Final verification..."

if [ ! -f "models/yolo11n_ncnn_model/model.ncnn.param" ]; then
    echo "❌ Error: model.ncnn.param not found"
    exit 1
fi

if [ ! -f "models/yolo11n_ncnn_model/model.ncnn.bin" ]; then
    echo "❌ Error: model.ncnn.bin not found"
    exit 1
fi

echo "✅ NCNN model files verified:"
ls -lh models/yolo11n_ncnn_model/

# Check file sizes
param_size=$(stat -f%z "models/yolo11n_ncnn_model/model.ncnn.param" 2>/dev/null || stat -c%s "models/yolo11n_ncnn_model/model.ncnn.param")
bin_size=$(stat -f%z "models/yolo11n_ncnn_model/model.ncnn.bin" 2>/dev/null || stat -c%s "models/yolo11n_ncnn_model/model.ncnn.bin")

param_kb=$((param_size / 1024))
bin_mb=$((bin_size / 1024 / 1024))

echo ""
echo "Model file sizes:"
echo "   model.ncnn.param: ${param_kb} KB"
echo "   model.ncnn.bin:   ${bin_mb} MB"

echo ""
echo "=========================================="
echo "✅ YOLO11n Model Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Enable YOLO detection in config/scanner_config.yaml:"
echo "   cameras.focus_zone.mode: 'yolo_detect'"
echo ""
echo "2. Test installation:"
echo "   python3 test_yolo_detection.py"
echo ""
echo "3. Test with cameras:"
echo "   python3 test_yolo_detection.py --with-camera"
echo ""
echo "4. View detection images:"
echo "   ls -lh calibration/focus_detection/"
echo ""
