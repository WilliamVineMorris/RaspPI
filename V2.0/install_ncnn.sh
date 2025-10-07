#!/bin/bash

echo "============================================================"
echo "NCNN Installation for Raspberry Pi"
echo "============================================================"

# Activate virtual environment
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate

echo ""
echo "[1/2] Installing NCNN from PyPI (quick method)..."
pip install ncnn

echo ""
echo "[2/2] Verifying installation..."
python3 -c "import ncnn; print('✅ NCNN installed successfully')" && {
    echo ""
    echo "============================================================"
    echo "✅ NCNN Installation Complete!"
    echo "============================================================"
    echo ""
    echo "You can now run:"
    echo "  python3 test_yolo_detection.py --with-camera"
    echo ""
} || {
    echo ""
    echo "============================================================"
    echo "❌ Installation verification failed"
    echo "============================================================"
    echo ""
    echo "Try building from source for better compatibility:"
    echo "  See Method 2 in NCNN_INSTALLATION.md"
    echo ""
}
