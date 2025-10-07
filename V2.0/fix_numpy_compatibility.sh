#!/bin/bash

echo "============================================================"
echo "NumPy Compatibility Fix for Picamera2"
echo "============================================================"

# Activate virtual environment
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate

echo ""
echo "[1/3] Checking system numpy version..."
SYSTEM_NUMPY=$(python3 -c "import sys; sys.path.insert(0, '/usr/lib/python3/dist-packages'); import numpy; print(numpy.__version__)" 2>/dev/null || echo "unknown")
echo "System numpy: $SYSTEM_NUMPY"

echo ""
echo "[2/3] Uninstalling venv numpy..."
pip uninstall numpy -y

echo ""
echo "[3/3] Installing compatible numpy version..."
# Try matching system version first
if [ "$SYSTEM_NUMPY" != "unknown" ]; then
    echo "Installing numpy==$SYSTEM_NUMPY to match system..."
    pip install numpy==$SYSTEM_NUMPY
else
    echo "Installing numpy<2.0.0 (safe default for picamera2)..."
    pip install "numpy<2.0.0"
fi

echo ""
echo "============================================================"
echo "Testing picamera2 import..."
python3 -c "import picamera2; print('✅ SUCCESS: picamera2 imports correctly')" && {
    echo "============================================================"
    echo "✅ Fix applied successfully!"
    echo ""
    echo "You can now run:"
    echo "  python3 test_yolo_detection.py --with-camera"
    echo "============================================================"
} || {
    echo "============================================================"
    echo "❌ Import still failing. Try Option 2 (system-site-packages)"
    echo "============================================================"
}
