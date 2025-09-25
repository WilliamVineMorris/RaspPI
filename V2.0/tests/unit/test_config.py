#!/usr/bin/env python3
"""
Quick Configuration Test Script

Tests the configuration loading and validation to identify any issues.
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def test_configuration():
    """Test configuration loading and validation"""
    print("🔧 Testing Configuration Loading...")
    
    try:
        # Test import
        from core.config_manager import ConfigManager
        print("  ✅ ConfigManager imported successfully")
        
        # Create test config
        config_path = Path(__file__).parent / "config" / "test_hardware_config.yaml"
        config_path.parent.mkdir(exist_ok=True)
        
        with open(config_path, 'w') as f:
            f.write("""
# Test Hardware Configuration
system:
  name: "Test Scanner"
  simulation_mode: false
  log_level: "INFO"

motion:
  controller:
    type: "fluidnc"
    connection: "usb"
    port: "/dev/ttyUSB0"
    baudrate: 115200
    timeout: 10.0
  axes:
    x_axis:
      type: "linear"
      units: "mm"
      min_limit: 0.0
      max_limit: 200.0
      home_position: 0.0
      max_feedrate: 1000.0
      steps_per_mm: 800.0
      has_limits: true
      homing_required: true
    y_axis:
      type: "linear"
      units: "mm"
      min_limit: 0.0
      max_limit: 200.0
      home_position: 0.0
      max_feedrate: 1000.0
      steps_per_mm: 800.0
      has_limits: true
      homing_required: true
    z_axis:
      type: "rotational"
      units: "degrees"
      min_limit: -360.0
      max_limit: 360.0
      home_position: 0.0
      max_feedrate: 500.0
      steps_per_degree: 10.0
      continuous_rotation: true
    c_axis:
      type: "linear"
      units: "degrees"
      min_limit: -90.0
      max_limit: 90.0
      home_position: 0.0
      max_feedrate: 300.0
      steps_per_degree: 5.0

cameras:
  primary:
    type: "pi_camera"
    device_id: 0
    interface: "libcamera"
    resolution: [1920, 1080]
    enabled: true
  secondary:
    type: "pi_camera"
    device_id: 1
    interface: "libcamera"
    resolution: [1920, 1080]
    enabled: true

lighting:
  controller:
    type: "gpio_pwm"
    enabled: false

storage:
  base_path: "/home/user/scanner_data"
  backup_enabled: true
""")
        
        print(f"  ✅ Test config created: {config_path}")
        
        # Test config loading
        config_manager = ConfigManager(config_path)
        print("  ✅ ConfigManager initialized successfully")
        
        # Test access to config
        motion_config = config_manager.get_motion_config()
        print(f"  ✅ Motion config loaded: {motion_config.controller.type}")
        
        camera_config = config_manager.get_camera_config()
        print(f"  ✅ Camera config loaded: {len(camera_config)} cameras")
        
        print("\n🎉 Configuration test PASSED - all fields valid!")
        return True
        
    except Exception as e:
        print(f"\n❌ Configuration test FAILED: {e}")
        import traceback
        print("Full error:")
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("🧪 Configuration Test Tool")
    print("=" * 60)
    
    success = test_configuration()
    
    if success:
        print("\n✅ Configuration is valid - hardware mode should work!")
        print("Try: python web/start_web_interface.py --mode hardware --debug")
    else:
        print("\n❌ Configuration issues detected - fix before hardware mode")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())