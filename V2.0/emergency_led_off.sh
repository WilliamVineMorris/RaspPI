#!/bin/bash
# Emergency LED shutdown script
# Use this if LEDs are stuck ON after script crashes

echo "🚨 Emergency LED shutdown..."
echo ""

echo "1. Turning off Hardware PWM channels..."
for pwm in /sys/class/pwm/pwmchip0/pwm*; do
    if [ -d "$pwm" ]; then
        pwm_name=$(basename $pwm)
        echo "   Setting $pwm_name duty_cycle to 0..."
        echo 0 | sudo tee $pwm/duty_cycle > /dev/null 2>&1
    fi
done
echo "   ✅ PWM duty cycles set to 0"
echo ""

echo "2. Setting GPIO pins to OUTPUT LOW..."
for pin in 13 18; do
    echo "   GPIO $pin -> OUTPUT LOW"
    sudo pinctrl set $pin op dl
done
echo "   ✅ GPIO pins set to LOW"
echo ""

echo "3. Verifying GPIO states..."
echo "   GPIO 13:"
pinctrl get 13
echo "   GPIO 18:"
pinctrl get 18
echo ""

echo "4. Checking PWM debug status..."
sudo cat /sys/kernel/debug/pwm 2>/dev/null | grep -A 1 "pwm-[12]" || echo "   (PWM debug not available)"
echo ""

echo "✅ Emergency LED shutdown complete!"
echo "All LEDs should be OFF now."
