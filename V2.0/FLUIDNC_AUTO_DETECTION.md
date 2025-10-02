# FluidNC Auto-Detection System

## Overview

Implemented automatic USB port detection for FluidNC controller to handle cases where the USB device enumeration changes (e.g., `/dev/ttyUSB0` → `/dev/ttyUSB1`).

## Problem

USB serial devices can appear on different ports after:
- System reboot
- USB cable reconnection
- Other USB devices being connected/disconnected
- Raspberry Pi firmware updates

Previously, the system was hardcoded to `/dev/ttyUSB0`, causing connection failures when FluidNC appeared on a different port.

## Solution

### Auto-Detection Configuration

Set port to `"auto"` in `config/scanner_config.yaml`:

```yaml
motion:
  controller:
    type: "fluidnc"
    connection: "usb"
    port: "auto"          # Auto-detect FluidNC port
    baudrate: 115200
    timeout: 10.0
```

### How Auto-Detection Works

1. **Scan for USB devices**: Checks `/dev/ttyUSB*` and `/dev/ttyACM*`
2. **Test each port**: Sends `?` (status request) to each device
3. **Identify FluidNC**: Looks for FluidNC-specific response patterns:
   - Lines starting with `<` (status reports)
   - Contains `MPos` or `WPos` (position data)
   - Contains `Grbl` (GRBL compatibility)
4. **Connect**: Uses the first port that responds like FluidNC
5. **Fallback**: If no port responds, uses first available USB device

### Detection Process

```
🔍 Auto-detection started
   ↓
Found USB devices: ['/dev/ttyUSB1', '/dev/ttyUSB2']
   ↓
Testing /dev/ttyUSB1...
   ↓
Sending '?' command
   ↓
Checking response for FluidNC patterns
   ↓
✅ FluidNC detected at /dev/ttyUSB1
   ↓
🔌 Connecting to FluidNC at /dev/ttyUSB1
```

## Configuration Options

### Option 1: Auto-Detection (Recommended)

```yaml
port: "auto"  # Automatically finds FluidNC
```

**Pros:**
- ✅ Works after reboots
- ✅ Works when USB enumeration changes
- ✅ No manual configuration needed

**Cons:**
- ⚠️ Slightly slower startup (tests multiple ports)
- ⚠️ May connect to wrong device if multiple GRBL devices present

### Option 2: Specific Port

```yaml
port: "/dev/ttyUSB1"  # Connect to specific port
```

**Pros:**
- ✅ Faster startup (no detection needed)
- ✅ Guaranteed to use specific device

**Cons:**
- ❌ Breaks if port number changes
- ❌ Requires manual update when port changes

### Option 3: Hybrid Fallback

The system automatically uses hybrid mode:
- If specific port fails (e.g., `/dev/ttyUSB0` doesn't exist)
- System attempts auto-detection as fallback
- Logs which port was actually used

## Usage

### Check Current USB Devices

```bash
# See what USB serial devices are available
ls -la /dev/ttyUSB* /dev/ttyACM* 2>&1 || echo "No devices found"

# Example output:
# crw-rw---- 1 root dialout 188, 1 Oct  2 18:12 /dev/ttyUSB1
```

### Verify FluidNC Detection

```bash
# Start the system and check logs
python3 run_web_interface.py

# Look for these log messages:
# 🔍 Found 2 USB device(s): ['/dev/ttyUSB1', '/dev/ttyUSB2']
# Testing /dev/ttyUSB1 for FluidNC...
# ✅ FluidNC detected at /dev/ttyUSB1
# 🔌 Connecting to FluidNC at /dev/ttyUSB1
```

### Manual Port Detection Script

```bash
# Quick check which port FluidNC is on
python3 find_fluidnc_port.py
```

## Implementation Details

### Code Location

**File:** `motion/simplified_fluidnc_protocol_fixed.py`

**Method:** `_detect_fluidnc_port()`

### Detection Logic

```python
def _detect_fluidnc_port(self) -> Optional[str]:
    """Auto-detect FluidNC controller on USB ports"""
    
    # Find all USB serial devices
    patterns = ['/dev/ttyUSB*', '/dev/ttyACM*']
    possible_ports = []
    for pattern in patterns:
        possible_ports.extend(glob.glob(pattern))
    
    # Test each port
    for port in sorted(possible_ports):
        # Open port briefly
        test_serial = serial.Serial(port, baudrate, timeout=0.5)
        
        # Send status request
        test_serial.write(b'?\n')
        time.sleep(0.2)
        
        # Check response for FluidNC patterns
        response = test_serial.readline().decode()
        if '<' in response or 'MPos' in response:
            return port  # Found FluidNC!
    
    return None  # Not found
```

### Integration with Connection

```python
def connect(self) -> bool:
    """Connect with auto-detection if needed"""
    
    # Auto-detect if port is "auto"
    if self.port == "auto":
        detected_port = self._detect_fluidnc_port()
        if detected_port:
            self.port = detected_port
        else:
            return False  # Detection failed
    
    # Continue with normal connection
    # ...
```

## Troubleshooting

### Issue: "No USB serial devices found"

**Cause:** No USB devices connected or permissions issue

**Solution:**
```bash
# Check USB devices
lsusb

# Check device permissions
ls -la /dev/ttyUSB* /dev/ttyACM*

# Add user to dialout group if needed
sudo usermod -a -G dialout $USER
# Log out and back in for this to take effect
```

### Issue: "FluidNC auto-detection failed"

**Cause:** FluidNC not responding or wrong baudrate

**Solution:**
```bash
# Verify FluidNC is powered on
# Check cable connections
# Try manual connection to verify port:
screen /dev/ttyUSB1 115200
# (Press Ctrl-A, then K to exit screen)

# If FluidNC responds on different baudrate, update config:
# baudrate: 9600  # or whatever works
```

### Issue: Connects to wrong device

**Cause:** Multiple GRBL-compatible devices connected

**Solution:**
1. Disconnect other USB serial devices
2. Use specific port instead of "auto"
3. Check which port is which:
   ```bash
   # Check device info
   udevadm info -a /dev/ttyUSB1 | grep -i serial
   ```

### Issue: Detection takes too long

**Cause:** Testing multiple non-responsive ports

**Solution:**
- Use specific port for faster startup
- Or accept 1-2 second delay for auto-detection reliability

## Benefits

✅ **Reliability**: Works after reboots and USB changes
✅ **Convenience**: No manual port configuration needed  
✅ **Robustness**: Fallback to first port if detection fails
✅ **Logging**: Clear logs show which port was used
✅ **Backward Compatible**: Can still use specific port if desired

## Future Enhancements

Possible improvements:
1. **Cache detected port**: Remember last successful port for faster startup
2. **USB ID matching**: Use USB vendor/product ID to identify FluidNC
3. **udev rules**: Create persistent device names (e.g., `/dev/fluidnc`)
4. **Multi-device support**: Handle multiple FluidNC controllers
5. **Hotplug detection**: Detect when USB device is reconnected

## Summary

The auto-detection system ensures FluidNC connection reliability by:
- 🔍 Automatically scanning for USB devices
- 🧪 Testing each port to identify FluidNC
- ✅ Connecting to the correct port automatically
- 📝 Logging the detection process for troubleshooting

Set `port: "auto"` in config and forget about USB port changes!
