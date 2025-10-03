#!/bin/bash
# Automatic Hardware PWM Fix for Raspberry Pi 5
# This script corrects the dtoverlay configuration for proper hardware PWM

set -e

echo "=================================================="
echo "  Hardware PWM Fix - Automatic Configuration"
echo "=================================================="
echo ""

# Check if running on Raspberry Pi
if [ ! -f /proc/device-tree/model ]; then
    echo "❌ ERROR: Not running on Raspberry Pi!"
    exit 1
fi

echo "✅ Running on: $(cat /proc/device-tree/model)"
echo ""

# Check if config.txt exists
CONFIG_FILE="/boot/firmware/config.txt"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: $CONFIG_FILE not found!"
    exit 1
fi

echo "📋 Checking current PWM configuration..."
echo ""

# Show current PWM overlay
if grep -q "dtoverlay=pwm" "$CONFIG_FILE"; then
    echo "Current configuration:"
    grep "dtoverlay=pwm" "$CONFIG_FILE"
    echo ""
else
    echo "⚠️  No PWM dtoverlay found in config.txt"
    echo ""
fi

# Check what needs to be changed
NEEDS_FIX=false

if grep -q "dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4" "$CONFIG_FILE"; then
    echo "🔍 FOUND INCORRECT CONFIGURATION:"
    echo "   dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4"
    echo ""
    echo "   Problem: func=2 and func2=4 are WRONG for Pi 5!"
    echo "   GPIO pins won't route to hardware PWM with these values."
    echo ""
    NEEDS_FIX=true
elif grep -q "dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5" "$CONFIG_FILE"; then
    echo "✅ Configuration is already CORRECT!"
    echo "   dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5"
    echo ""
    echo "If LEDs still don't work, the issue is elsewhere."
    echo "Try running: sudo python debug_led_hardware.py"
    exit 0
else
    echo "⚠️  Unknown or missing PWM configuration"
    echo ""
    NEEDS_FIX=true
fi

if [ "$NEEDS_FIX" = false ]; then
    exit 0
fi

# Confirm before making changes
echo "=================================================="
echo "  PROPOSED FIX"
echo "=================================================="
echo ""
echo "Will change:"
echo "  FROM: dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4"
echo "  TO:   dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5"
echo ""
echo "This sets GPIO 18 and 13 to ALT5 mode (correct for Pi 5 PWM0)."
echo ""
echo "⚠️  A backup will be created at: ${CONFIG_FILE}.backup"
echo ""

read -p "Apply fix? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Fix cancelled by user."
    exit 0
fi

echo ""
echo "📝 Creating backup..."
sudo cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"
echo "✅ Backup created: ${CONFIG_FILE}.backup"
echo ""

echo "🔧 Applying fix..."

# Apply the fix
if grep -q "dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4" "$CONFIG_FILE"; then
    sudo sed -i 's/dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4/dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5/' "$CONFIG_FILE"
    echo "✅ Configuration updated!"
else
    # Add the line if not found
    echo "" | sudo tee -a "$CONFIG_FILE"
    echo "# Hardware PWM for LED control (GPIO 18 = PWM0_0, GPIO 13 = PWM0_1)" | sudo tee -a "$CONFIG_FILE"
    echo "dtoverlay=pwm-2chan,pin=18,func=5,pin2=13,func2=5" | sudo tee -a "$CONFIG_FILE"
    echo "✅ Configuration added!"
fi

echo ""
echo "📋 New configuration:"
grep "dtoverlay=pwm" "$CONFIG_FILE"
echo ""

# Unexport any GPIO conflicts
echo "🔍 Checking for GPIO conflicts..."
if [ -d "/sys/class/gpio/gpio18" ]; then
    echo "   Unexporting GPIO 18..."
    echo 18 | sudo tee /sys/class/gpio/unexport 2>/dev/null || true
fi
if [ -d "/sys/class/gpio/gpio13" ]; then
    echo "   Unexporting GPIO 13..."
    echo 13 | sudo tee /sys/class/gpio/unexport 2>/dev/null || true
fi
echo "✅ No GPIO conflicts"
echo ""

echo "=================================================="
echo "  FIX APPLIED SUCCESSFULLY!"
echo "=================================================="
echo ""
echo "⚠️  REBOOT REQUIRED for changes to take effect!"
echo ""
echo "After reboot, test manually:"
echo ""
echo "  1. Check PWM chips:"
echo "     ls -la /sys/class/pwm/"
echo ""
echo "  2. Test hardware PWM on GPIO 18:"
echo "     echo 0 | sudo tee /sys/class/pwm/pwmchip0/export"
echo "     echo 2500000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/period"
echo "     echo 1250000 | sudo tee /sys/class/pwm/pwmchip0/pwm0/duty_cycle"
echo "     echo 1 | sudo tee /sys/class/pwm/pwmchip0/pwm0/enable"
echo ""
echo "     LED should light up at 50%!"
echo ""
echo "  3. Start scanner system:"
echo "     cd ~/RaspPI/V2.0"
echo "     python run_web_interface.py"
echo ""
echo "  4. Test from dashboard:"
echo "     http://3dscanner:5000 → Click 'Test Lighting'"
echo ""

read -p "Reboot now? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔄 Rebooting..."
    sudo reboot
else
    echo ""
    echo "Remember to reboot before testing!"
    echo "Run: sudo reboot"
fi
