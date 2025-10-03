#!/bin/bash
# Check complete PWM system status

echo "=== GPIO Pin Configuration ==="
echo "GPIO 13:"
pinctrl get 13
echo ""
echo "GPIO 18:"
pinctrl get 18
echo ""

echo "=== PWM Channel Export Status ==="
ls -la /sys/class/pwm/pwmchip0/ 2>/dev/null || echo "pwmchip0 not found"
echo ""

echo "=== Active dtoverlays ==="
dtoverlay -l
echo ""

echo "=== Boot Config PWM Settings ==="
grep -i pwm /boot/firmware/config.txt
echo ""

echo "=== Kernel PWM Debug ==="
sudo cat /sys/kernel/debug/pwm 2>/dev/null || echo "PWM debug not available (need sudo)"
