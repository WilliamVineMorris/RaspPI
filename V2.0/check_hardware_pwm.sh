#!/bin/bash
# Hardware PWM Diagnostic - Check if pigpio daemon is running and hardware PWM is active

echo "=========================================="
echo "HARDWARE PWM DIAGNOSTIC"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check 1: pigpio daemon
echo "CHECK 1: Pigpio Daemon Status"
echo "------------------------------"
if pgrep -x "pigpiod" > /dev/null
then
    echo -e "${GREEN}✓${NC} pigpiod is RUNNING"
    PIGPIO_RUNNING=1
else
    echo -e "${RED}✗${NC} pigpiod is NOT RUNNING"
    echo -e "${YELLOW}→${NC} Hardware PWM will NOT work!"
    echo -e "${YELLOW}→${NC} Fix: sudo pigpiod"
    PIGPIO_RUNNING=0
fi
echo ""

# Check 2: Config file
echo "CHECK 2: Scanner Configuration"
echo "------------------------------"
if grep -q "use_pigpio_factory: true" config/scanner_config.yaml; then
    echo -e "${GREEN}✓${NC} use_pigpio_factory: true"
else
    echo -e "${RED}✗${NC} use_pigpio_factory not set to true"
    echo -e "${YELLOW}→${NC} Edit config/scanner_config.yaml"
fi

if grep -q "controller_type: \"gpiozero\"" config/scanner_config.yaml; then
    echo -e "${GREEN}✓${NC} controller_type: gpiozero"
else
    echo -e "${YELLOW}⚠${NC}  controller_type may not be set to gpiozero"
fi
echo ""

# Check 3: GPIO pins configured
echo "CHECK 3: LED GPIO Pin Configuration"
echo "------------------------------"
INNER_PIN=$(grep -A 5 "inner:" config/scanner_config.yaml | grep "gpio_pins:" | grep -o '\[.*\]' | tr -d '[]')
OUTER_PIN=$(grep -A 5 "outer:" config/scanner_config.yaml | grep "gpio_pins:" | grep -o '\[.*\]' | tr -d '[]')

echo "Inner LED pin: ${INNER_PIN}"
echo "Outer LED pin: ${OUTER_PIN}"
echo ""

# Check if pins are hardware PWM capable
HARDWARE_PWM_PINS="12 13 18 19"
INNER_IS_HW=0
OUTER_IS_HW=0

for pin in $HARDWARE_PWM_PINS; do
    if [ "$INNER_PIN" = "$pin" ]; then
        echo -e "${GREEN}✓${NC} Inner LED (GPIO $INNER_PIN) supports HARDWARE PWM"
        INNER_IS_HW=1
    fi
    if [ "$OUTER_PIN" = "$pin" ]; then
        echo -e "${GREEN}✓${NC} Outer LED (GPIO $OUTER_PIN) supports HARDWARE PWM"
        OUTER_IS_HW=1
    fi
done

if [ $INNER_IS_HW -eq 0 ]; then
    echo -e "${RED}✗${NC} Inner LED (GPIO $INNER_PIN) does NOT support hardware PWM"
    echo -e "${YELLOW}→${NC} Will use SOFTWARE PWM (may flicker)"
    echo -e "${YELLOW}→${NC} Hardware PWM pins: 12, 13, 18, 19"
fi

if [ $OUTER_IS_HW -eq 0 ]; then
    echo -e "${RED}✗${NC} Outer LED (GPIO $OUTER_PIN) does NOT support hardware PWM"
    echo -e "${YELLOW}→${NC} Will use SOFTWARE PWM (may flicker)"
    echo -e "${YELLOW}→${NC} Hardware PWM pins: 12, 13, 18, 19"
fi
echo ""

# Check 4: Test pigpio connection
echo "CHECK 4: Pigpio Connection Test"
echo "------------------------------"
if [ $PIGPIO_RUNNING -eq 1 ]; then
    python3 << 'EOF'
import pigpio
try:
    pi = pigpio.pi()
    if pi.connected:
        print("\033[0;32m✓\033[0m Pigpio connection successful")
        pi.stop()
    else:
        print("\033[0;31m✗\033[0m Pigpio connection failed")
except Exception as e:
    print(f"\033[0;31m✗\033[0m Error: {e}")
EOF
else
    echo -e "${YELLOW}⚠${NC}  Skipped (pigpiod not running)"
fi
echo ""

# Summary
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo ""

if [ $PIGPIO_RUNNING -eq 1 ] && [ $INNER_IS_HW -eq 1 ]; then
    echo -e "${GREEN}✓ HARDWARE PWM SHOULD BE WORKING${NC}"
    echo ""
    echo "If LEDs still flicker:"
    echo "  1. Check scanner logs for 'Hardware PWM' confirmation"
    echo "  2. Verify no other processes using GPIO pins"
    echo "  3. Try different PWM frequency (500Hz or 1000Hz)"
    echo "  4. Check power supply stability"
else
    echo -e "${RED}✗ HARDWARE PWM IS NOT PROPERLY CONFIGURED${NC}"
    echo ""
    echo "TO FIX:"
    if [ $PIGPIO_RUNNING -eq 0 ]; then
        echo "  1. Start pigpio daemon:"
        echo "     sudo pigpiod"
    fi
    if [ $INNER_IS_HW -eq 0 ] || [ $OUTER_IS_HW -eq 0 ]; then
        echo "  2. Change LED pins to hardware PWM capable:"
        echo "     Edit config/scanner_config.yaml"
        echo "     Use GPIO pins: 12, 13, 18, or 19"
    fi
    echo "  3. Restart scanner system"
fi
echo ""
echo "=========================================="
