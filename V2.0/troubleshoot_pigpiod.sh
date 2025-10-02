#!/bin/bash
# Pigpio Daemon Troubleshooting Script

echo "==========================================="
echo "PIGPIO DAEMON TROUBLESHOOTING"
echo "==========================================="
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check 1: Is pigpiod running?
echo "CHECK 1: Current pigpiod status"
echo "------------------------------"
if pgrep -x "pigpiod" > /dev/null
then
    echo -e "${GREEN}✓${NC} pigpiod is running"
    echo "Process details:"
    ps aux | grep pigpiod | grep -v grep
else
    echo -e "${RED}✗${NC} pigpiod is NOT running"
fi
echo ""

# Check 2: Is port 8888 in use?
echo "CHECK 2: Port 8888 status (pigpio default)"
echo "------------------------------"
if netstat -tuln 2>/dev/null | grep -q ":8888 "; then
    echo -e "${YELLOW}⚠${NC}  Port 8888 is in use"
    echo "Details:"
    sudo netstat -tulnp | grep ":8888"
elif command -v ss &> /dev/null; then
    if ss -tuln 2>/dev/null | grep -q ":8888 "; then
        echo -e "${YELLOW}⚠${NC}  Port 8888 is in use"
        echo "Details:"
        sudo ss -tulnp | grep ":8888"
    else
        echo -e "${GREEN}✓${NC} Port 8888 is available"
    fi
else
    echo -e "${YELLOW}⚠${NC}  Cannot check port status (netstat/ss not available)"
fi
echo ""

# Check 3: Check for error messages
echo "CHECK 3: System logs for pigpiod errors"
echo "------------------------------"
if [ -f /var/log/syslog ]; then
    echo "Recent pigpiod messages:"
    sudo tail -20 /var/log/syslog | grep pigpio || echo "No recent pigpiod log entries"
elif journalctl --version &> /dev/null; then
    echo "Recent pigpiod messages:"
    sudo journalctl -u pigpiod -n 20 --no-pager || echo "No pigpiod service logs"
else
    echo "Cannot check logs"
fi
echo ""

# Check 4: Try to start pigpiod with verbose output
echo "CHECK 4: Attempting to start pigpiod"
echo "------------------------------"
echo "Running: sudo pigpiod"
sudo pigpiod 2>&1
RESULT=$?
echo "Return code: $RESULT"

if [ $RESULT -eq 0 ]; then
    echo -e "${GREEN}✓${NC} pigpiod started successfully"
else
    echo -e "${RED}✗${NC} pigpiod failed to start"
    echo ""
    echo "Common causes:"
    echo "  - Already running (kill existing: sudo killall pigpiod)"
    echo "  - Port 8888 in use"
    echo "  - Permission issues"
    echo "  - GPIO already in use by another process"
fi
echo ""

# Wait a moment and check if it's running
sleep 1
echo "CHECK 5: Verify pigpiod is running"
echo "------------------------------"
if pgrep -x "pigpiod" > /dev/null
then
    echo -e "${GREEN}✓${NC} pigpiod is NOW running!"
    echo ""
    echo "Testing connection:"
    python3 << 'EOF'
import pigpio
import sys
try:
    pi = pigpio.pi()
    if pi.connected:
        print("✓ Successfully connected to pigpiod")
        print(f"  Hardware revision: {pi.get_hardware_revision()}")
        print(f"  pigpio version: {pi.get_pigpio_version()}")
        pi.stop()
        sys.exit(0)
    else:
        print("✗ Cannot connect to pigpiod")
        sys.exit(1)
except Exception as e:
    print(f"✗ Error connecting: {e}")
    sys.exit(1)
EOF
else
    echo -e "${RED}✗${NC} pigpiod is still NOT running"
    echo ""
    echo "==========================================="
    echo "TROUBLESHOOTING STEPS"
    echo "==========================================="
    echo ""
    echo "1. Kill any existing pigpiod processes:"
    echo "   sudo killall pigpiod"
    echo ""
    echo "2. Check for processes using GPIO:"
    echo "   sudo lsof | grep /dev/gpiomem"
    echo "   sudo lsof | grep /dev/mem"
    echo ""
    echo "3. Try starting with different port:"
    echo "   sudo pigpiod -p 8889"
    echo ""
    echo "4. Check permissions:"
    echo "   ls -l /dev/gpiomem"
    echo "   groups | grep gpio"
    echo ""
    echo "5. Reinstall pigpio:"
    echo "   sudo apt-get install --reinstall pigpio"
fi
echo ""
echo "==========================================="
