#!/bin/bash
# Comprehensive LED Hardware Diagnostic

echo "=================================================="
echo "LED HARDWARE DIAGNOSTIC - COMPREHENSIVE TEST"
echo "=================================================="
echo ""

echo "📍 Step 1: Check PWM chip and channel availability"
echo "----------------------------------------"
echo "Available PWM chips:"
ls -la /sys/class/pwm/ 2>/dev/null

echo ""
echo "PWM chip 0 channels:"
ls -la /sys/class/pwm/pwmchip0/ 2>/dev/null

echo ""
echo "📍 Step 2: Check current PWM status"
echo "----------------------------------------"
sudo cat /sys/kernel/debug/pwm

echo ""
echo "📍 Step 3: Check pinctrl configuration"
echo "----------------------------------------"
echo "GPIO 18:" 
pinctrl get 18
echo "GPIO 13:"
pinctrl get 13

echo ""
echo "📍 Step 4: Check if PWM channels are already exported"
echo "----------------------------------------"
if [ -d "/sys/class/pwm/pwmchip0/pwm0" ]; then
    echo "✅ PWM0 (GPIO 18) is exported"
    echo "   Period: $(cat /sys/class/pwm/pwmchip0/pwm0/period 2>/dev/null || echo 'N/A')"
    echo "   Duty:   $(cat /sys/class/pwm/pwmchip0/pwm0/duty_cycle 2>/dev/null || echo 'N/A')"
    echo "   Enable: $(cat /sys/class/pwm/pwmchip0/pwm0/enable 2>/dev/null || echo 'N/A')"
else
    echo "⚠️  PWM0 not exported"
fi

if [ -d "/sys/class/pwm/pwmchip0/pwm1" ]; then
    echo "✅ PWM1 (GPIO 13) is exported"
    echo "   Period: $(cat /sys/class/pwm/pwmchip0/pwm1/period 2>/dev/null || echo 'N/A')"
    echo "   Duty:   $(cat /sys/class/pwm/pwmchip0/pwm1/duty_cycle 2>/dev/null || echo 'N/A')"
    echo "   Enable: $(cat /sys/class/pwm/pwmchip0/pwm1/enable 2>/dev/null || echo 'N/A')"
else
    echo "⚠️  PWM1 not exported"
fi

echo ""
echo "📍 Step 5: Test DIRECT voltage on GPIO 18"
echo "----------------------------------------"
echo "Testing with lgpio library..."

python3 << 'EOFDIRECT'
import lgpio
import time

try:
    h = lgpio.gpiochip_open(0)
    
    # Reclaim GPIO 18 from PWM and set as output
    print("Reclaiming GPIO 18 as standard GPIO...")
    lgpio.gpio_claim_output(h, 18)
    
    print("Setting GPIO 18 HIGH (3.3V)...")
    lgpio.gpio_write(h, 18, 1)
    print("⏱️  Holding for 3 seconds...")
    time.sleep(3)
    
    response = input("Did GPIO 18 LED light up? (y/n): ").strip().lower()
    
    print("Setting GPIO 18 LOW (0V)...")
    lgpio.gpio_write(h, 18, 0)
    
    lgpio.gpiochip_close(h)
    
    if response == 'y':
        print("✅ LED circuit works with direct GPIO!")
        print("   Issue is with PWM signal routing, not hardware.")
    else:
        print("❌ LED doesn't work even with direct GPIO HIGH")
        print("   Possible issues:")
        print("   - LED power supply not connected")
        print("   - MOSFET/driver circuit issue")
        print("   - LED polarity reversed")
        print("   - Current limiting resistor too high")
    
except Exception as e:
    print(f"❌ Error: {e}")
    print("   lgpio not available or GPIO in use")
EOFDIRECT

echo ""
echo "📍 Step 6: Check PWM peripheral registers (advanced)"
echo "----------------------------------------"
echo "PWM0 peripheral base: 0x1f00098000"
if command -v devmem2 &> /dev/null; then
    echo "Reading PWM0 control register..."
    sudo devmem2 0x1f00098000 || echo "devmem2 not available"
else
    echo "devmem2 not installed (optional diagnostic tool)"
fi

echo ""
echo "=================================================="
echo "DIAGNOSTIC COMPLETE"
echo "=================================================="
echo ""
echo "Next steps based on results:"
echo "1. If direct GPIO HIGH lights LED → PWM routing issue"
echo "2. If direct GPIO HIGH doesn't light LED → Hardware/wiring issue"
echo "3. Check /boot/firmware/config.txt dtoverlay settings"
echo ""
