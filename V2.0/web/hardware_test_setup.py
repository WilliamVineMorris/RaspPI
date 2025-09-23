#!/usr/bin/env python3
"""
Hardware Test Setup Script for 3D Scanner Web Interface

This script configures the web interface for hardware testing on Raspberry Pi.
It ensures all components are properly configured for real hardware operation.
"""

import os
import sys
import yaml
import logging
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

def setup_hardware_config():
    """Setup configuration for hardware testing"""
    config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
    
    print("🔧 Configuring for hardware testing...")
    
    # Load current config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Update for hardware mode
    config['system']['simulation_mode'] = False
    config['system']['debug_level'] = 'INFO'
    
    # FluidNC settings for hardware
    config['motion']['controller_type'] = 'fluidnc'
    config['motion']['connection']['port'] = '/dev/ttyUSB0'
    config['motion']['connection']['baud_rate'] = 115200
    
    # Camera settings for Pi cameras
    config['cameras']['primary']['device_id'] = 0
    config['cameras']['secondary']['device_id'] = 1
    config['cameras']['interface'] = 'libcamera'
    
    # LED GPIO settings
    config['lighting']['controller_type'] = 'gpio_pwm'
    config['lighting']['safety']['max_duty_cycle'] = 0.9
    
    # Save updated config
    with open(config_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, indent=2)
    
    print("✅ Hardware configuration updated")
    return config

def check_hardware_dependencies():
    """Check if required hardware libraries are available"""
    print("🔍 Checking hardware dependencies...")
    
    missing_deps = []
    
    # Check for Pi camera libraries
    try:
        import picamera2
        print("  ✅ picamera2 library found")
    except ImportError:
        missing_deps.append("picamera2")
        print("  ❌ picamera2 library missing")
    
    # Check for GPIO libraries
    try:
        import pigpio
        print("  ✅ pigpio library found")
    except ImportError:
        missing_deps.append("pigpio")
        print("  ❌ pigpio library missing")
    
    # Check for serial communication
    try:
        import serial
        print("  ✅ pyserial library found")
    except ImportError:
        missing_deps.append("pyserial")
        print("  ❌ pyserial library missing")
    
    if missing_deps:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing_deps)}")
        print("Install with: pip install " + " ".join(missing_deps))
        return False
    
    print("✅ All hardware dependencies found")
    return True

def check_hardware_connections():
    """Check hardware connections and permissions"""
    print("🔌 Checking hardware connections...")
    
    # Check USB devices (FluidNC)
    usb_devices = list(Path("/dev").glob("ttyUSB*"))
    if usb_devices:
        print(f"  ✅ USB devices found: {[str(d) for d in usb_devices]}")
    else:
        print("  ⚠️  No USB devices found - connect FluidNC")
    
    # Check camera devices
    video_devices = list(Path("/dev").glob("video*"))
    if video_devices:
        print(f"  ✅ Video devices found: {[str(d) for d in video_devices]}")
    else:
        print("  ⚠️  No video devices found - check camera connections")
    
    # Check GPIO access
    if os.path.exists("/dev/gpiomem"):
        print("  ✅ GPIO interface available")
    else:
        print("  ⚠️  GPIO interface not accessible")
    
    return True

def create_hardware_startup_script():
    """Create startup script for hardware mode"""
    startup_script = Path(__file__).parent / "start_hardware_interface.py"
    
    script_content = '''#!/usr/bin/env python3
"""
Hardware Interface Startup Script

Starts the web interface in hardware mode with all real hardware components.
"""

import sys
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from web.start_web_interface import main

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start 3D Scanner Web Interface - Hardware Mode")
    parser.add_argument("--host", default="0.0.0.0", help="Host address")
    parser.add_argument("--port", type=int, default=5000, help="Port number")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # Force hardware mode
    sys.argv = [
        sys.argv[0],
        "--mode", "hardware",
        "--host", args.host,
        "--port", str(args.port)
    ]
    
    if args.debug:
        sys.argv.extend(["--debug"])
    
    print("🚀 Starting web interface in HARDWARE mode...")
    print("⚠️  Ensure all hardware is connected and powered on!")
    
    main()
'''
    
    with open(startup_script, 'w') as f:
        f.write(script_content)
    
    startup_script.chmod(0o755)  # Make executable
    print(f"✅ Hardware startup script created: {startup_script}")

def main():
    """Main setup function"""
    print("=" * 80)
    print("🔬 3D Scanner Hardware Test Setup")
    print("=" * 80)
    
    # Setup configuration
    config = setup_hardware_config()
    
    # Check dependencies
    deps_ok = check_hardware_dependencies()
    
    # Check hardware
    hardware_ok = check_hardware_connections()
    
    # Create startup script
    create_hardware_startup_script()
    
    print("\n" + "=" * 80)
    print("📋 Hardware Test Setup Summary")
    print("=" * 80)
    print(f"Configuration: ✅ Updated for hardware mode")
    print(f"Dependencies: {'✅ Ready' if deps_ok else '❌ Missing packages'}")
    print(f"Hardware Check: {'✅ Devices detected' if hardware_ok else '⚠️  Check connections'}")
    
    print("\n🚀 To start hardware testing:")
    print("   python start_hardware_interface.py")
    print("\n⚠️  IMPORTANT:")
    print("   - Ensure FluidNC is connected via USB")
    print("   - Verify both Pi cameras are connected")
    print("   - Check LED GPIO connections")
    print("   - Test in a safe environment")
    
    if not deps_ok:
        print("\n❌ Install missing dependencies first!")
        return 1
    
    print("\n✅ Hardware setup complete - ready for testing!")
    return 0

if __name__ == "__main__":
    sys.exit(main())