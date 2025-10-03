#!/bin/bash
# PWM Channel Mapping Test - Find the correct channel for GPIO 18

echo "=================================================="
echo "PWM CHANNEL MAPPING DIAGNOSTIC"
echo "=================================================="
echo ""
echo "Your pinctrl shows:"
echo "  GPIO 18: a3 (ALT3) = PWM0_CHAN2"
echo "  GPIO 13: a0 (ALT0) = PWM0_CHAN1"
echo ""
echo "⚠️  CRITICAL DISCOVERY:"
echo "  GPIO 18 = PWM0_CHAN2 (not CHAN0!)"
echo "  GPIO 13 = PWM0_CHAN1"
echo ""
echo "This means we need to export pwm2 and pwm1, not pwm0 and pwm1!"
echo ""

# Clean up any previous exports
echo "Cleaning up previous PWM exports..."
for i in 0 1 2 3; do
    echo $i | sudo tee /sys/class/pwm/pwmchip0/unexport 2>/dev/null || true
done
sleep 1

echo ""
echo "📍 TEST 1: PWM Channel 2 (should control GPIO 18)"
echo "----------------------------------------"

# Export PWM channel 2
echo "Exporting PWM channel 2..."
echo 2 | sudo tee /sys/class/pwm/pwmchip0/export
sleep 1

if [ ! -d "/sys/class/pwm/pwmchip0/pwm2" ]; then
    echo "❌ Failed to export PWM channel 2"
    exit 1
fi

echo "✅ PWM channel 2 exported"

# Configure channel 2
echo "Setting period to 2500000 ns (400Hz)..."
echo 2500000 | sudo tee /sys/class/pwm/pwmchip0/pwm2/period

echo "Setting duty cycle to 1250000 ns (50%)..."
echo 1250000 | sudo tee /sys/class/pwm/pwmchip0/pwm2/duty_cycle

echo "Enabling PWM channel 2..."
echo 1 | sudo tee /sys/class/pwm/pwmchip0/pwm2/enable

echo ""
echo "✨ PWM channel 2 is now active at 50% duty cycle"
echo ""
read -p "Does GPIO 18 LED light up NOW? (y/n): " response1
echo ""

if [ "$response1" = "y" ]; then
    echo "🎉 SUCCESS! GPIO 18 = PWM0 Channel 2"
    echo ""
    echo "✅ SOLUTION FOUND:"
    echo "   GPIO 18 requires PWM channel 2 (not channel 0)"
    echo "   GPIO 13 requires PWM channel 1"
    GPIO18_WORKS=true
else
    echo "❌ GPIO 18 still doesn't light up with channel 2"
    GPIO18_WORKS=false
fi

# Clean up channel 2
echo "Disabling PWM channel 2..."
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm2/enable
echo 2 | sudo tee /sys/class/pwm/pwmchip0/unexport
sleep 1

echo ""
echo "📍 TEST 2: PWM Channel 1 (should control GPIO 13)"
echo "----------------------------------------"

echo "Exporting PWM channel 1..."
echo 1 | sudo tee /sys/class/pwm/pwmchip0/export
sleep 1

if [ ! -d "/sys/class/pwm/pwmchip0/pwm1" ]; then
    echo "❌ Failed to export PWM channel 1"
    exit 1
fi

echo "✅ PWM channel 1 exported"

# Configure channel 1
echo "Setting period to 2500000 ns (400Hz)..."
echo 2500000 | sudo tee /sys/class/pwm/pwmchip0/pwm1/period

echo "Setting duty cycle to 1250000 ns (50%)..."
echo 1250000 | sudo tee /sys/class/pwm/pwmchip0/pwm1/duty_cycle

echo "Enabling PWM channel 1..."
echo 1 | sudo tee /sys/class/pwm/pwmchip0/pwm1/enable

echo ""
echo "✨ PWM channel 1 is now active at 50% duty cycle"
echo ""
read -p "Does GPIO 13 LED light up NOW? (y/n): " response2
echo ""

if [ "$response2" = "y" ]; then
    echo "🎉 SUCCESS! GPIO 13 = PWM0 Channel 1"
    GPIO13_WORKS=true
else
    echo "❌ GPIO 13 doesn't light up with channel 1"
    GPIO13_WORKS=false
fi

# Clean up
echo "Cleaning up..."
echo 0 | sudo tee /sys/class/pwm/pwmchip0/pwm1/enable
echo 1 | sudo tee /sys/class/pwm/pwmchip0/unexport

echo ""
echo "=================================================="
echo "RESULTS SUMMARY"
echo "=================================================="
echo ""

if [ "$GPIO18_WORKS" = true ]; then
    echo "✅ GPIO 18: Works with PWM channel 2"
else
    echo "❌ GPIO 18: Doesn't work with PWM channel 2"
fi

if [ "$GPIO13_WORKS" = true ]; then
    echo "✅ GPIO 13: Works with PWM channel 1"
else
    echo "❌ GPIO 13: Doesn't work with PWM channel 1"
fi

echo ""
if [ "$GPIO18_WORKS" = true ] || [ "$GPIO13_WORKS" = true ]; then
    echo "🔧 NEXT STEP: Update software to use correct PWM channels!"
    echo ""
    echo "Code needs to be updated to use:"
    if [ "$GPIO18_WORKS" = true ]; then
        echo "  - GPIO 18 → PWM chip 0, channel 2 (not channel 0)"
    fi
    if [ "$GPIO13_WORKS" = true ]; then
        echo "  - GPIO 13 → PWM chip 0, channel 1"
    fi
    echo ""
    echo "I will update the gpio_led_controller.py mapping now..."
else
    echo "⚠️  Neither GPIO works with hardware PWM"
    echo "   Possible issues:"
    echo "   1. LED power supply not connected"
    echo "   2. MOSFET/driver circuit problem"
    echo "   3. Need inverted polarity"
    echo ""
    echo "   Run: chmod +x diagnose_led_complete.sh"
    echo "        ./diagnose_led_complete.sh"
fi

echo ""
