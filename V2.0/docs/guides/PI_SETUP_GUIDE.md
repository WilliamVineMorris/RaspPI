# Pi Setup and Installation Guide

Complete setup guide for installing and configuring the V2.0 scanner framework on Raspberry Pi.

## Prerequisites

- Raspberry Pi 5 (or Pi 4 with 4GB+ RAM recommended)
- 32GB+ microSD card with Raspberry Pi OS Lite or Desktop
- Internet connection for package installation
- SSH access or direct terminal access

## Step 1: System Update

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install system dependencies
sudo apt install -y python3-pip python3-venv git build-essential
sudo apt install -y python3-dev python3-setuptools
```

## Step 2: Python Environment Setup

```bash
# Create virtual environment
python3 -m venv ~/scanner_env

# Activate environment
source ~/scanner_env/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

## Step 3: Install Python Dependencies

```bash
# Install core packages
pip install pyserial pyserial-asyncio pyyaml

# Install async support
pip install asyncio-mqtt

# Install Pi camera support (on Pi)
sudo apt install -y python3-picamera2
# OR if using pip:
# pip install picamera2

# Install optional packages
pip install opencv-python pillow
pip install gpiozero pigpio

# Install development tools
pip install pytest pytest-asyncio
```

## Step 4: Hardware Configuration

### Enable Camera Interface
```bash
sudo raspi-config
# Navigate to: Interface Options → Camera → Enable
sudo reboot
```

### Serial Port Setup
```bash
# Add user to dialout group for serial access
sudo usermod -a -G dialout $USER

# Check serial ports
ls -la /dev/tty*

# Common FluidNC ports: /dev/ttyUSB0, /dev/ttyACM0
```

### GPIO Setup (if using LEDs)
```bash
# Enable GPIO
sudo raspi-config
# Navigate to: Interface Options → SPI/I2C → Enable (if needed)

# Start pigpio daemon for precise timing
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

## Step 5: Download and Setup Project

```bash
# Clone or copy V2.0 files to Pi
mkdir -p ~/Documents/scanner
cd ~/Documents/scanner

# Copy all V2.0 files to this directory
# (use scp, rsync, or git clone)

# Make sure virtual environment is active
source ~/scanner_env/bin/activate
```

## Step 6: Verify Installation

```bash
# Quick dependency check
python -c "import serial; import yaml; print('Core deps OK')"

# Check picamera2 (on Pi only)
python -c "import picamera2; print('Camera OK')" || echo "Camera not available"

# Check for cameras
python -c "
from picamera2 import Picamera2
cameras = Picamera2.global_camera_info()
print(f'Detected {len(cameras)} cameras')
for i, cam in enumerate(cameras):
    print(f'  Camera {i}: {cam}')
" || echo "No cameras or picamera2 not available"

# Check serial ports
python -c "
import serial.tools.list_ports
ports = list(serial.tools.list_ports.comports())
print(f'Serial ports: {[p.device for p in ports]}')
"
```

## Step 7: Run Tests

```bash
# Activate environment if not already active
source ~/scanner_env/bin/activate

# Navigate to V2.0 directory
cd ~/Documents/scanner/V2.0

# Run basic tests (no hardware)
python run_pi_tests.py --quick

# Test with hardware detection
python run_pi_tests.py --verbose

# Test specific components
python test_motion_only.py --verbose
python test_camera_simple.py --no-capture --verbose
```

## Common Issues and Solutions

### ImportError: No module named 'yaml'
```bash
pip install pyyaml
```

### ImportError: No module named 'serial'
```bash
pip install pyserial pyserial-asyncio
```

### Permission denied: '/dev/ttyUSB0'
```bash
sudo usermod -a -G dialout $USER
# Then logout and login again, or reboot
```

### Camera not detected
```bash
# Check camera is enabled
sudo raspi-config
# Interface Options → Camera → Enable → Reboot

# Check camera hardware
vcgencmd get_camera

# Install picamera2
sudo apt install python3-picamera2
```

### No FluidNC connection
- Check USB cable and connection
- Try different USB port
- Check FluidNC power and status LEDs
- Try different serial port: `--port /dev/ttyACM0`

## Environment Variables

Optional environment variables for configuration:

```bash
# Add to ~/.bashrc
export SCANNER_LOG_LEVEL=DEBUG
export SCANNER_CONFIG_FILE=~/scanner_config.yaml
export SCANNER_DATA_DIR=~/scanner_data

# Motion controller defaults
export FLUIDNC_PORT=/dev/ttyUSB0
export FLUIDNC_BAUD=115200

# Camera defaults
export PICAMERA_RESOLUTION=1920x1080
export PICAMERA_FRAMERATE=30
```

## Performance Optimization

### For Raspberry Pi 5
```bash
# GPU memory split (if using cameras heavily)
sudo raspi-config
# Advanced Options → Memory Split → 128 or 256

# Enable hardware acceleration
echo 'gpu_mem=128' | sudo tee -a /boot/config.txt
```

### For Development
```bash
# Install development tools
pip install ipython jupyter
pip install black flake8 mypy  # Code formatting and linting
```

## Startup Service (Optional)

To run scanner on boot:

```bash
# Create service file
sudo tee /etc/systemd/system/scanner.service > /dev/null <<EOF
[Unit]
Description=4DOF Scanner Service
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/Documents/scanner/V2.0
Environment=PATH=/home/pi/scanner_env/bin
ExecStart=/home/pi/scanner_env/bin/python main.py
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Enable service
sudo systemctl enable scanner.service
sudo systemctl start scanner.service

# Check status
sudo systemctl status scanner.service
```

## Next Steps

After successful installation and testing:

1. **Hardware Validation**: Run `python run_pi_tests.py` to verify all components
2. **Configuration**: Create custom configuration files for your setup
3. **Development**: Start implementing additional modules or improvements
4. **Calibration**: Run camera and motion system calibration procedures

## Troubleshooting

### Check Installation
```bash
# Verify virtual environment
which python
pip list | grep -E "(serial|yaml|picamera)"

# Check hardware permissions
groups $USER  # Should include dialout
ls -la /dev/tty* | grep USB

# Test individual components
python -c "from core.exceptions import ScannerError; print('Core OK')"
python -c "from motion.fluidnc_controller import FluidNCController; print('Motion OK')"
python -c "from camera.pi_camera_controller import PiCameraController; print('Camera OK')"
```

### Reset Environment
```bash
# If something goes wrong, recreate environment
rm -rf ~/scanner_env
python3 -m venv ~/scanner_env
source ~/scanner_env/bin/activate
# Reinstall dependencies
```

For additional help, check the test logs in `~/scanner_logs/` or run tests with `--verbose` flag for detailed output.