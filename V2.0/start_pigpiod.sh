#!/bin/bash
# Force start pigpiod - handles common startup issues

echo "==========================================="
echo "FORCE START PIGPIOD"
echo "==========================================="
echo ""

# Step 1: Kill any existing pigpiod
echo "Step 1: Stopping any existing pigpiod processes..."
sudo killall pigpiod 2>/dev/null
sleep 1

if pgrep -x "pigpiod" > /dev/null; then
    echo "  Forcing kill..."
    sudo killall -9 pigpiod 2>/dev/null
    sleep 1
fi

if pgrep -x "pigpiod" > /dev/null; then
    echo "✗ ERROR: Cannot stop existing pigpiod"
    echo "  Try manually: sudo killall -9 pigpiod"
    exit 1
else
    echo "✓ No existing pigpiod processes"
fi
echo ""

# Step 2: Check port availability
echo "Step 2: Checking port 8888..."
if command -v netstat &> /dev/null; then
    if netstat -tuln 2>/dev/null | grep -q ":8888 "; then
        echo "✗ Port 8888 is in use by another process"
        netstat -tulnp 2>/dev/null | grep ":8888"
        echo ""
        echo "Starting pigpiod on alternate port 8889..."
        PIGPIO_PORT="-p 8889"
    else
        echo "✓ Port 8888 available"
        PIGPIO_PORT=""
    fi
elif command -v ss &> /dev/null; then
    if ss -tuln 2>/dev/null | grep -q ":8888 "; then
        echo "✗ Port 8888 is in use"
        echo "Starting pigpiod on alternate port 8889..."
        PIGPIO_PORT="-p 8889"
    else
        echo "✓ Port 8888 available"
        PIGPIO_PORT=""
    fi
else
    echo "⚠  Cannot check port, assuming available"
    PIGPIO_PORT=""
fi
echo ""

# Step 3: Start pigpiod
echo "Step 3: Starting pigpiod..."
if [ -n "$PIGPIO_PORT" ]; then
    echo "  Command: sudo pigpiod $PIGPIO_PORT"
    sudo pigpiod $PIGPIO_PORT
else
    echo "  Command: sudo pigpiod"
    sudo pigpiod
fi

START_RESULT=$?
sleep 2

# Step 4: Verify it's running
echo ""
echo "Step 4: Verifying pigpiod status..."
if pgrep -x "pigpiod" > /dev/null; then
    echo "✓✓✓ pigpiod is RUNNING!"
    echo ""
    echo "Process details:"
    ps aux | grep pigpiod | grep -v grep
    echo ""
    
    # Test connection
    echo "Step 5: Testing connection..."
    python3 << 'EOF'
import pigpio
import sys
try:
    pi = pigpio.pi()
    if pi.connected:
        print("✓✓✓ Successfully connected to pigpiod!")
        print(f"  Hardware: {hex(pi.get_hardware_revision())}")
        print(f"  pigpio version: {pi.get_pigpio_version()}")
        pi.stop()
        print("")
        print("=========================================")
        print("SUCCESS: pigpiod is ready for hardware PWM!")
        print("=========================================")
        print("")
        print("Now run the scanner:")
        print("  python3 run_web_interface.py")
        sys.exit(0)
    else:
        print("✗ Cannot connect to pigpiod")
        print("  pigpiod is running but not accepting connections")
        sys.exit(1)
except Exception as e:
    print(f"✗ Connection error: {e}")
    print("")
    print("Try:")
    print("  sudo killall pigpiod")
    print("  sudo pigpiod")
    sys.exit(1)
EOF
else
    echo "✗✗✗ pigpiod failed to start"
    echo ""
    echo "==========================================="
    echo "MANUAL TROUBLESHOOTING REQUIRED"
    echo "==========================================="
    echo ""
    echo "Try these steps:"
    echo ""
    echo "1. Check system logs:"
    echo "   sudo journalctl -xe | grep pigpio"
    echo "   sudo tail -50 /var/log/syslog | grep pigpio"
    echo ""
    echo "2. Check for GPIO conflicts:"
    echo "   sudo lsof | grep -E '/dev/gpiomem|/dev/mem'"
    echo ""
    echo "3. Check permissions:"
    echo "   ls -l /dev/gpiomem"
    echo "   groups"
    echo ""
    echo "4. Verify pigpio installation:"
    echo "   which pigpiod"
    echo "   pigpiod -v"
    echo ""
    echo "5. Reinstall pigpio:"
    echo "   sudo apt-get install --reinstall pigpio"
    echo ""
    echo "6. Reboot and try again:"
    echo "   sudo reboot"
    echo ""
    exit 1
fi
