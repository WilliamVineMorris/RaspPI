# NCNN Installation Required

## 🔴 Error: `name 'ncnn' is not defined`

The YOLO detector initialization failed because the **NCNN Python package is not installed** in your virtual environment.

```
❌ Failed to initialize YOLO detector: name 'ncnn' is not defined
```

---

## ✅ Solution: Install NCNN Python Package

### Quick Fix (Recommended)

```bash
# Activate virtual environment
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate

# Install ncnn-python
pip install ncnn
```

---

## 📦 Installation Methods

### Method 1: Install from PyPI (Easiest)

```bash
pip install ncnn
```

**Pros**: 
- ✅ Quick and easy
- ✅ Works on most systems

**Cons**:
- ⚠️ May not have latest optimizations for Pi 5
- ⚠️ Generic ARM build

**Recommended for**: Quick testing and development

---

### Method 2: Build from Source (Best Performance)

For **optimal Raspberry Pi 5 performance**, build from source with Pi-specific optimizations:

```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install -y build-essential git cmake libprotobuf-dev protobuf-compiler

# Clone NCNN repository
cd ~
git clone https://github.com/Tencent/ncnn.git
cd ncnn

# Create build directory
mkdir -p build
cd build

# Configure with Pi 5 optimizations
cmake -DCMAKE_BUILD_TYPE=Release \
      -DNCNN_VULKAN=OFF \
      -DNCNN_BUILD_TOOLS=ON \
      -DNCNN_BUILD_EXAMPLES=OFF \
      -DNCNN_BUILD_TESTS=OFF \
      -DNCNN_ARM82=ON \
      -DNCNN_ARM82DOT=ON \
      ..

# Build (use all 4 cores)
make -j4

# Install
sudo make install

# Build Python bindings
cd ../python
pip install -e .
```

**Pros**:
- ✅ Optimized for Pi 5 ARM architecture
- ✅ Latest features and fixes
- ✅ Best inference performance

**Cons**:
- ⏱️ Takes 15-30 minutes to compile
- 💾 Requires build tools

**Recommended for**: Production deployment

---

## 🔧 Quick Installation Script

Save this as `install_ncnn.sh`:

```bash
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
python3 -c "import ncnn; print(f'✅ NCNN installed successfully: version {ncnn.__version__ if hasattr(ncnn, \"__version__\") else \"unknown\"}')" && {
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
```

**Usage**:
```bash
chmod +x install_ncnn.sh
./install_ncnn.sh
```

---

## ✔️ Verification Steps

### Step 1: Check Installation

```bash
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate
python3 -c "import ncnn; print('✅ NCNN imported successfully')"
```

**Expected output**:
```
✅ NCNN imported successfully
```

### Step 2: Check NCNN Version (if available)

```bash
python3 -c "import ncnn; print(f'NCNN version: {ncnn.__version__ if hasattr(ncnn, \"__version__\") else \"unknown\"}')"
```

### Step 3: Test YOLO Detection

```bash
python3 test_yolo_detection.py --with-camera
```

**Expected output** (initialization):
```
[2/3] Initializing camera controller...
🎯 YOLO11n NCNN object detection enabled for autofocus windows
🎯 YOLO11n NCNN Detector initialized: confidence=0.30, padding=0.15
✅ Camera controller initialized
```

**Expected output** (during calibration):
```
[3/3] Running calibration (triggers YOLO detection)...
📂 Loading YOLO11n NCNN model from models/yolo11n_ncnn_model
✅ YOLO11n NCNN model loaded successfully
```

---

## 🐛 Troubleshooting

### Error: `pip install ncnn` fails

**Try updating pip first**:
```bash
pip install --upgrade pip setuptools wheel
pip install ncnn
```

### Error: `No module named '_ncnn'`

This indicates the C++ extension didn't build properly. **Build from source** (Method 2).

### Error: Still getting `name 'ncnn' is not defined`

**Check you're in the correct virtual environment**:
```bash
which python3
# Should show: /home/user/Documents/RaspPI/V2.0/scanner_env/bin/python3
```

**Verify ncnn is installed in venv**:
```bash
pip list | grep ncnn
```

Should show:
```
ncnn    X.X.X
```

---

## 📊 Performance Comparison

| Installation Method | Inference Time | Compatibility | Installation Time |
|---------------------|----------------|---------------|-------------------|
| **PyPI (pip)**      | ~250-400ms     | Good          | ~1 minute         |
| **Build from source** | ~200-300ms   | Excellent     | ~20 minutes       |

For **initial testing**: Use PyPI method  
For **production**: Build from source

---

## 🚀 Complete Setup Workflow

```bash
# 1. Activate virtual environment
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate

# 2. Install NCNN
pip install ncnn

# 3. Verify NCNN
python3 -c "import ncnn; print('✅ NCNN OK')"

# 4. Convert YOLO model (if not done yet)
python3 convert_yolo_to_ncnn.py

# 5. Test YOLO detection
python3 test_yolo_detection.py --with-camera

# 6. Check detection images
ls -lh calibration/focus_detection/
```

---

## 📋 Requirements Check

Before installing, verify you have these installed:

```bash
# Check Python version (need 3.10+)
python3 --version

# Check pip
pip --version

# Check if in virtual environment
which python3
```

---

## 🔄 Update Requirements.txt

After successful installation, the `requirements.txt` already includes NCNN but it's commented:

```txt
# NCNN for optimized inference on Raspberry Pi
# Install from source for best performance: https://github.com/Tencent/ncnn/tree/master/python
# Or use: pip install ncnn (may not have ARM optimizations)
# ncnn>=1.0.0  # Uncomment if installing via pip
```

You can uncomment the last line if using pip install:

```bash
nano requirements.txt
# Find and uncomment: ncnn>=1.0.0
```

---

## Summary

**Problem**: NCNN Python package not installed  
**Solution**: `pip install ncnn`  
**Verification**: `python3 -c "import ncnn; print('OK')"`  
**Next Step**: `python3 test_yolo_detection.py --with-camera`

---

## Quick Commands

```bash
# Install NCNN
source ~/Documents/RaspPI/V2.0/scanner_env/bin/activate
pip install ncnn

# Test
python3 -c "import ncnn; print('✅ NCNN installed')"
python3 test_yolo_detection.py --with-camera

# Check results
ls -lh calibration/focus_detection/
```

---

**Status**: NCNN package missing  
**Action Required**: Install NCNN  
**Estimated Time**: 1-2 minutes (PyPI) or 20-30 minutes (build from source)  
**Expected Result**: YOLO detection working with visualization images
