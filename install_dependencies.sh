#!/bin/bash
# Quick dependency installation script for Raspberry Pi 5

echo "🚀 Installing dependencies for Integrated Camera System..."

# System updates
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Essential tools
echo "🔧 Installing build tools..."
sudo apt install -y build-essential cmake pkg-config git python3-pip python3-dev python3-venv

# Camera dependencies
echo "📷 Installing camera dependencies..."
sudo apt install -y python3-picamera2 python3-libcamera

# OpenCV dependencies
echo "🖼️  Installing OpenCV dependencies..."
sudo apt install -y libopencv-dev python3-opencv libatlas-base-dev

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv ~/camera_env
source ~/camera_env/bin/activate

# Python packages
echo "📦 Installing Python packages..."
pip install --upgrade pip
pip install numpy opencv-python flask pyserial requests picamera2

# User permissions
echo "🔐 Setting up user permissions..."
sudo usermod -a -G dialout $USER

# Enable camera
echo "📷 Enabling camera interface..."
if ! grep -q "start_x=1" /boot/config.txt; then
    echo 'start_x=1' | sudo tee -a /boot/config.txt
fi
if ! grep -q "gpu_mem=128" /boot/config.txt; then
    echo 'gpu_mem=128' | sudo tee -a /boot/config.txt
fi

echo "✅ Installation complete!"
echo "🔄 Please reboot your Raspberry Pi to apply camera settings:"
echo "    sudo reboot"
echo ""
echo "🚀 After reboot, activate the virtual environment:"
echo "    source ~/camera_env/bin/activate"
echo "    python test_dependencies.py"