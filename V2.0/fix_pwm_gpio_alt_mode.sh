#!/bin/bash
# Fix GPIO pins for hardware PWM by setting ALT function modes
# This is needed because dtoverlay isn't loaded at runtime

echo "=== Fixing GPIO ALT Function Modes for Hardware PWM ==="
echo ""

echo "Before fix:"
echo "GPIO 13:"
pinctrl get 13
echo "GPIO 18:"
pinctrl get 18
echo ""

echo "Setting GPIO 13 to ALT0 (PWM0_CHAN1)..."
sudo pinctrl set 13 a0
echo ""

echo "Setting GPIO 18 to ALT5 (PWM0_CHAN2)..."
sudo pinctrl set 18 a5
echo ""

echo "After fix:"
echo "GPIO 13:"
pinctrl get 13
echo "GPIO 18:"
pinctrl get 18
echo ""

echo "✅ GPIO pins configured for hardware PWM!"
echo "🔸 GPIO 13 = PWM0_CHAN1 (ALT0)"
echo "🔸 GPIO 18 = PWM0_CHAN2 (ALT5)"
echo ""
echo "Now test with: python run_web_interface.py"
