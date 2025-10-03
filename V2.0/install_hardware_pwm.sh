#!/bin/bash
# Hardware PWM Fix - Quick Installation Script
# Run this on the Raspberry Pi to install and test the hardware PWM fix

set -e  # Exit on error

echo "=================================================="
echo "  Hardware PWM Fix - Installation Script"
echo "=================================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "❌ ERROR: Not running on Raspberry Pi!"
    exit 1
fi

echo "✅ Running on: $(cat /proc/device-tree/model)"
echo ""

# Navigate to project directory
cd ~/RaspPI/V2.0 || {
    echo "❌ ERROR: Project directory not found!"
    echo "   Expected: ~/RaspPI/V2.0"
    exit 1
}

echo "📁 Project directory: $(pwd)"
echo ""

# Check if dtoverlay is configured
echo "🔍 Checking dtoverlay configuration..."
if grep -q "dtoverlay=pwm-2chan" /boot/firmware/config.txt; then
    echo "✅ dtoverlay=pwm-2chan found in config.txt"
    grep "dtoverlay=pwm-2chan" /boot/firmware/config.txt
else
    echo "❌ WARNING: dtoverlay=pwm-2chan NOT found in /boot/firmware/config.txt"
    echo "   You may need to add: dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4"
    echo "   Then reboot before continuing"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# Check if PWM chips exist
echo "🔍 Checking PWM chip availability..."
if [ -d "/sys/class/pwm/pwmchip0" ]; then
    echo "✅ PWM chip 0 found: $(ls -la /sys/class/pwm/ | grep pwmchip0)"
else
    echo "❌ ERROR: PWM chip 0 not found!"
    echo "   dtoverlay may not be loaded. Try rebooting."
    exit 1
fi

if [ -d "/sys/class/pwm/pwmchip1" ]; then
    echo "✅ PWM chip 1 found: $(ls -la /sys/class/pwm/ | grep pwmchip1)"
fi
echo ""

# Install rpi-hardware-pwm
echo "📦 Installing rpi-hardware-pwm library..."
pip install rpi-hardware-pwm

# Verify installation
echo ""
echo "🔍 Verifying installation..."
python3 -c "from rpi_hardware_pwm import HardwarePWM; print('✅ rpi-hardware-pwm library imported successfully')" || {
    echo "❌ ERROR: Failed to import rpi-hardware-pwm"
    exit 1
}
echo ""

# Show current PWM status
echo "📊 Current PWM status:"
echo "----------------------------------------"
sudo cat /sys/kernel/debug/pwm
echo "----------------------------------------"
echo ""

# Test manual PWM activation
echo "🧪 Testing hardware PWM on GPIO 18 (channel 0)..."
echo ""

# Cleanup any previous exports
echo 0 | sudo tee /sys/class/pwm/pwmchip0/unexport 2>/dev/null || true
sleep 0.5

# Export channel 0
echo "   Exporting PWM channel 0..."
echo 0 | sudo tee /sys/class/pwm/pwmchip0/export
sleep 0.5

# Set period (1kHz = 1,000,000 ns)
echo "   Setting period to 1kHz (1,000,000 ns)..."
echo 1000000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/period
sleep 0.2

# Set duty cycle (20% = 200,000 ns)
echo "   Setting duty cycle to 20% (200,000 ns)..."
echo 200000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/duty_cycle
sleep 0.2

# Enable PWM
echo "   Enabling PWM..."
echo 1 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable
sleep 0.2

echo ""
echo "✨ LED on GPIO 18 should now be lit at 20% brightness!"
echo ""
echo "📊 PWM status while active:"
echo "----------------------------------------"
sudo cat /sys/kernel/debug/pwm | head -n 5
echo "----------------------------------------"
echo ""

read -p "Can you see the LED lit? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "✅ Hardware PWM test SUCCESSFUL!"
else
    echo "⚠️  LED not visible - check wiring and LED connections"
fi

# Turn off test PWM
echo ""
echo "🔌 Turning off test PWM..."
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable
sleep 0.2
echo 0 | sudo tee /sys/class/pwm/pwmchip0/unexport
echo ""

echo "=================================================="
echo "  Installation Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo "1. Start web interface: python run_web_interface.py"
echo "2. Check logs for: 'Using rpi-hardware-pwm library'"
echo "3. Verify PWM: sudo cat /sys/kernel/debug/pwm"
echo "4. Test lighting from dashboard"
echo ""
echo "Expected PWM output when running:"
echo "  pwm-0   (rpi_hardware_pwm    ): requested enabled period: 1000000 ns duty: XXXXXX ns"
echo ""
echo "Documentation: See HARDWARE_PWM_FIX_V2.md for full details"
echo ""
