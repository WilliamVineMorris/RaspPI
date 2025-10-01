#!/bin/bash
# LED Flickering Fix - Quick Test Script
# Run this on the Raspberry Pi to verify the fix

echo "======================================"
echo "LED FLICKERING FIX - TESTING PROTOCOL"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}STEP 1: Check Configuration${NC}"
echo "Verifying scanner_config.yaml settings..."
echo ""

# Check controller type
CONTROLLER=$(grep "controller_type:" config/scanner_config.yaml | head -1)
echo "  $CONTROLLER"

# Check PWM frequency
PWM_FREQ=$(grep "pwm_frequency:" config/scanner_config.yaml | head -1)
echo "  $PWM_FREQ"

# Check GPIO library
GPIO_LIB=$(grep "gpio_library:" config/scanner_config.yaml | head -1)
echo "  $GPIO_LIB"

echo ""
echo -e "${GREEN}✓${NC} Configuration check complete"
echo ""

echo -e "${YELLOW}STEP 2: Test Raw PWM (Baseline)${NC}"
echo "This will test hardware PWM without scanner code..."
read -p "Press Enter to run raw PWM test (or Ctrl+C to skip)..."
python3 test_raw_pwm.py
echo ""

echo -e "${YELLOW}STEP 3: Test Scanner System${NC}"
echo "This will start the full scanner system..."
echo ""
echo "What to watch for:"
echo "  • Live stream should be stable"
echo "  • LEDs should NOT flicker during:"
echo "    - Calibration (30% brightness)"
echo "    - Image captures"
echo "    - Turning on/off"
echo ""
read -p "Press Enter to start scanner web interface (or Ctrl+C to skip)..."
python3 run_web_interface.py

echo ""
echo "======================================"
echo "TESTING COMPLETE"
echo "======================================"
echo ""
echo "If LEDs still flicker:"
echo "  1. Check LED_FLICKERING_FIX.md for troubleshooting"
echo "  2. Try different PWM frequencies (100Hz, 500Hz, 1000Hz)"
echo "  3. Check power supply stability"
echo "  4. Verify LED driver specifications"
echo ""
