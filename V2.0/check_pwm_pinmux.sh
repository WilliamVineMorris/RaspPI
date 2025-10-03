#!/bin/bash
# Check GPIO pinmux configuration for PWM

echo "=================================================="
echo "GPIO PINMUX AND PWM CONFIGURATION CHECK"
echo "=================================================="
echo ""

echo "📍 Checking GPIO 18 configuration:"
if [ -f /sys/kernel/debug/pinctrl/pinctrl-maps ]; then
    sudo cat /sys/kernel/debug/pinctrl/pinctrl-maps | grep -A 2 "pin 18"
else
    echo "⚠️  pinctrl-maps not available"
fi

echo ""
echo "📍 Checking GPIO 13 configuration:"
if [ -f /sys/kernel/debug/pinctrl/pinctrl-maps ]; then
    sudo cat /sys/kernel/debug/pinctrl/pinctrl-maps | grep -A 2 "pin 13"
else
    echo "⚠️  pinctrl-maps not available"
fi

echo ""
echo "📍 Current boot configuration:"
grep "pwm" /boot/firmware/config.txt || echo "No PWM dtoverlay found"

echo ""
echo "📍 Available PWM chips:"
ls -la /sys/class/pwm/ 2>/dev/null || echo "No PWM chips found"

echo ""
echo "📍 GPIO alternate functions (should show PWM for pins 12,13,18,19):"
for pin in 12 13 18 19; do
    if [ -d "/sys/class/gpio/gpio${pin}" ]; then
        echo "  GPIO ${pin}: Already exported in GPIO mode"
    else
        echo "  GPIO ${pin}: Not exported (good for PWM)"
    fi
done

echo ""
echo "=================================================="
