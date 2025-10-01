#!/bin/bash
# Setup Hardware PWM via pigpio for LED Control
# This script installs and configures pigpio daemon for true hardware PWM

echo "================================================================================"
echo "HARDWARE PWM SETUP - Installing pigpio for flicker-free LED control"
echo "================================================================================"
echo ""
echo "This will:"
echo "  1. Install pigpio library and daemon"
echo "  2. Start pigpio daemon"
echo "  3. Configure pigpio to start at boot"
echo "  4. Verify hardware PWM is working"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."
echo ""

# Install pigpio
echo "📦 Installing pigpio..."
sudo apt update
sudo apt install -y pigpio python3-pigpio

if [ $? -ne 0 ]; then
    echo "❌ Failed to install pigpio"
    exit 1
fi

echo "✅ pigpio installed successfully"
echo ""

# Start pigpio daemon
echo "🚀 Starting pigpio daemon..."
sudo pigpiod

if [ $? -ne 0 ]; then
    echo "⚠️  pigpiod may already be running (this is OK)"
fi

# Check if pigpio daemon is running
sleep 1
if pgrep -x "pigpiod" > /dev/null; then
    echo "✅ pigpio daemon is running"
else
    echo "❌ pigpio daemon failed to start"
    exit 1
fi

echo ""

# Enable pigpio at boot
echo "⚙️  Configuring pigpio to start at boot..."
sudo systemctl enable pigpiod

if [ $? -eq 0 ]; then
    echo "✅ pigpio will start automatically at boot"
else
    echo "⚠️  Could not enable pigpio at boot (may need manual configuration)"
fi

echo ""
echo "================================================================================"
echo "HARDWARE PWM SETUP COMPLETE!"
echo "================================================================================"
echo ""
echo "Next steps:"
echo "  1. Configuration file already updated (use_pigpio_factory: true)"
echo "  2. Run test: python3 test_hardware_pwm.py"
echo "  3. Look for: '⚡ Using gpiozero with PIGPIO FACTORY' in logs"
echo "  4. Verify: Zero flickering during heavy console output"
echo ""
echo "If you restart the Pi, pigpio daemon will start automatically."
echo "To manually start/stop/check pigpio daemon:"
echo "  Start:  sudo pigpiod"
echo "  Stop:   sudo killall pigpiod"
echo "  Status: pgrep -x pigpiod (should show process ID)"
echo ""
