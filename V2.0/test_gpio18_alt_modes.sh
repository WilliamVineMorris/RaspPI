#!/bin/bash
# Test all ALT function modes for GPIO 18 to find which one gives PWM0_CHAN2

echo "=== Testing ALT modes for GPIO 18 ==="
echo ""

for alt in a0 a1 a2 a3 a4 a5; do
    echo "Testing ALT mode: $alt"
    sudo pinctrl set 18 $alt
    result=$(pinctrl get 18)
    echo "Result: $result"
    
    # Check if it shows PWM
    if echo "$result" | grep -q "PWM"; then
        echo "✅ FOUND PWM! ALT mode $alt works for GPIO 18"
        echo ""
    fi
    
    sleep 0.5
done

echo "=== Final state ==="
pinctrl get 18
