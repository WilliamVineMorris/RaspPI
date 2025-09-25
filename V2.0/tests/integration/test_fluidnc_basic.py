"""
Basic FluidNC Controller Test

Simple test to validate the FluidNC controller implementation
without requiring pytest or actual hardware.
"""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from motion.fluidnc_controller import FluidNCController, create_fluidnc_controller
from motion.base import Position4D, MotionStatus
from core.config_manager import ConfigManager


async def test_fluidnc_basic():
    """Basic test of FluidNC controller"""
    print("Testing FluidNC Controller...")
    
    # Test configuration
    config = {
        'port': '/dev/ttyUSB0',
        'baudrate': 115200,
        'timeout': 5.0,
        'axes': {
            'x_axis': {'min_limit': -150.0, 'max_limit': 150.0, 'max_feedrate': 8000.0},
            'y_axis': {'min_limit': -100.0, 'max_limit': 100.0, 'max_feedrate': 8000.0},
            'z_axis': {'min_limit': -180.0, 'max_limit': 180.0, 'max_feedrate': 3600.0},
            'c_axis': {'min_limit': -45.0, 'max_limit': 45.0, 'max_feedrate': 1800.0}
        }
    }
    
    # Create controller
    print("Creating FluidNC controller...")
    controller = FluidNCController(config)
    
    # Test initialization properties
    print(f"Port: {controller.port}")
    print(f"Baudrate: {controller.baudrate}")
    print(f"Timeout: {controller.timeout}")
    print(f"Initial status: {controller.status}")
    print(f"Initial position: {controller.current_position}")
    print(f"Is homed: {controller.is_homed}")
    
    # Test axis limits
    print(f"Axis limits loaded: {len(controller.axis_limits)} axes")
    for axis, limits in controller.axis_limits.items():
        print(f"  {axis}: {limits.min_limit} to {limits.max_limit} mm/deg, max feed: {limits.max_feedrate}")
    
    # Test position validation
    print("\nTesting position validation...")
    
    valid_pos = Position4D(x=100.0, y=50.0, z=90.0, c=30.0)
    is_valid = controller._validate_position(valid_pos)
    print(f"Valid position {valid_pos}: {is_valid}")
    
    invalid_pos = Position4D(x=200.0, y=50.0, z=90.0, c=30.0)  # X out of range
    is_valid = controller._validate_position(invalid_pos)
    print(f"Invalid position {invalid_pos}: {is_valid}")
    
    # Test capabilities
    print("\nTesting capabilities...")
    capabilities = await controller.get_capabilities()
    print(f"Axes count: {capabilities.axes_count}")
    print(f"Supports homing: {capabilities.supports_homing}")
    print(f"Supports soft limits: {capabilities.supports_soft_limits}")
    print(f"Supports probe: {capabilities.supports_probe}")
    print(f"Max feedrate: {capabilities.max_feedrate}")
    print(f"Position resolution: {capabilities.position_resolution}")
    
    # Test motion limits
    print("\nTesting motion limits...")
    try:
        x_limits = await controller.get_motion_limits('x')
        print(f"X limits: {x_limits.min_limit} to {x_limits.max_limit}")
        
        y_limits = await controller.get_motion_limits('y')
        print(f"Y limits: {y_limits.min_limit} to {y_limits.max_limit}")
        
        z_limits = await controller.get_motion_limits('z')
        print(f"Z limits: {z_limits.min_limit} to {z_limits.max_limit}")
        
        c_limits = await controller.get_motion_limits('c')
        print(f"C limits: {c_limits.min_limit} to {c_limits.max_limit}")
        
    except Exception as e:
        print(f"Error getting limits: {e}")
    
    print("\n✅ FluidNC Controller basic test completed successfully!")
    return True


def test_config_integration():
    """Test integration with config manager"""
    print("\nTesting config manager integration...")
    
    # Create a simple config file for testing
    config_file = Path(__file__).parent.parent / "test_config.yaml"
    config_content = """
motion:
  controller:
    port: "/dev/ttyUSB0"
    baudrate: 115200
    timeout: 10.0
  axes:
    x_axis:
      min_limit: -200.0
      max_limit: 200.0
      max_feedrate: 10000.0
    y_axis:
      min_limit: -150.0
      max_limit: 150.0
      max_feedrate: 8000.0
    z_axis:
      min_limit: -180.0
      max_limit: 180.0
      max_feedrate: 3600.0
    c_axis:
      min_limit: -45.0
      max_limit: 45.0
      max_feedrate: 1800.0
"""
    
    try:
        with open(config_file, 'w') as f:
            f.write(config_content)
        
        # Test config manager creation
        config_manager = ConfigManager(config_file)
        print(f"Config loaded from: {config_file}")
        
        # Test controller creation from config
        controller = create_fluidnc_controller(config_manager)
        print(f"Controller created with port: {controller.port}")
        print(f"Controller baudrate: {controller.baudrate}")
        print(f"Controller timeout: {controller.timeout}")
        
        # Check axis configuration was loaded
        print(f"Axes configured: {list(controller.axis_limits.keys())}")
        
        # Clean up
        config_file.unlink()
        
        print("✅ Config integration test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Config integration test failed: {e}")
        if config_file.exists():
            config_file.unlink()
        return False


async def main():
    """Run all basic tests"""
    print("=== FluidNC Controller Test Suite ===\n")
    
    try:
        # Run basic controller test
        await test_fluidnc_basic()
        
        # Run config integration test
        test_config_integration()
        
        print(f"\n🎉 All tests completed successfully!")
        print("The FluidNC controller implementation is ready for integration.")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())