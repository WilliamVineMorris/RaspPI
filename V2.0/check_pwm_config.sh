#!/bin/bash
# Check and fix dtoverlay PWM configuration

echo "=================================================="
echo "  PWM dtoverlay Configuration Checker"
echo "=================================================="
echo ""

echo "🔍 Current dtoverlay configuration:"
echo "──────────────────────────────────────────────────"
grep -n "dtoverlay=pwm" /boot/firmware/config.txt || echo "No PWM dtoverlay found!"
echo "──────────────────────────────────────────────────"
echo ""

echo "🔍 Checking which GPIO functions are set:"
echo "──────────────────────────────────────────────────"
# Check GPIO 18 function
gpio_func_18=$(raspi-gpio get 18 2>/dev/null | grep -o "func=[A-Z0-9]*")
echo "GPIO 18: $gpio_func_18"

# Check GPIO 13 function  
gpio_func_13=$(raspi-gpio get 13 2>/dev/null | grep -o "func=[A-Z0-9]*")
echo "GPIO 13: $gpio_func_13"
echo "──────────────────────────────────────────────────"
echo ""

echo "📋 Expected for hardware PWM:"
echo "  GPIO 18: func=ALT5 (PWM0)"
echo "  GPIO 13: func=ALT0 (PWM1)"
echo ""

echo "💡 Your current setting:"
echo "  dtoverlay=pwm-2chan,pin=18,func=2,pin2=13,func2=4"
echo ""
echo "🔧 PROBLEM: This creates PWM chips but doesn't set GPIO alt functions!"
echo ""
echo "✅ SOLUTION: The hardware PWM library needs GPIO pins in ALT mode,"
echo "   but direct GPIO control (gpiozero/lgpio) can't use ALT mode pins."
echo ""
echo "🎯 RECOMMENDATION:"
echo "   Since direct GPIO works (HIGH=ON, LOW=OFF), use SOFTWARE PWM"
echo "   via lgpio, which is fast enough for LED control."
echo ""
echo "   Hardware PWM is overkill for LEDs - software PWM at 400Hz is"
echo "   perfectly adequate and works with your existing wiring!"
echo ""
