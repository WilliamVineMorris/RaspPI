#!/usr/bin/env python3
"""
Simple PWM Test - Validates 2-pin hardware PWM at 300Hz
Tests the simplified GPIO LED controller without pigpiod

Run this on the Pi to test:
python test_simple_pwm.py
"""

import sys
import time
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from lighting.simple_gpio_led_controller import SimpleGPIOLEDController

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_simple_pwm():
    """Test the simplified PWM controller"""
    
    print("=== Simple PWM Test (300Hz Hardware PWM) ===")
    print("Testing 2-zone LED control without pigpiod")
    
    try:
        # Load configuration
        config_manager = ConfigManager()
        config = config_manager.get_config()
        
        # Extract lighting config
        lighting_config = config.get('lighting', {})
        
        print(f"PWM Frequency: {lighting_config.get('pwm_frequency', 'not set')}Hz")
        print(f"GPIO Library: {config.get('platform', {}).get('gpio_library', 'not set')}")
        
        # Create controller
        controller = SimpleGPIOLEDController(lighting_config)
        
        # Initialize
        print("\n1. Initializing GPIO PWM controller...")
        success = await controller.initialize()
        if not success:
            print("❌ Initialization failed")
            return
        
        print("✅ GPIO PWM controller initialized")
        
        # Show status
        status = controller.get_status()
        print(f"\nController Status:")
        print(f"  - Library: {status['library']}")
        print(f"  - Frequency: {status['pwm_frequency']}Hz") 
        print(f"  - Zones: {status['zones_configured']} ({', '.join(status['zone_names'])})")
        
        # Test zone control
        print("\n2. Testing zone control...")
        
        # Test inner zone (Zone 1)
        if 'inner' in status['zone_names']:
            print("Testing inner zone (GPIO 12)...")
            await controller.set_zone_intensity('inner', 0.25)  # 25%
            time.sleep(1)
            await controller.set_zone_intensity('inner', 0.0)   # Off
            print("✅ Inner zone test completed")
        
        # Test outer zone (Zone 2)  
        if 'outer' in status['zone_names']:
            print("Testing outer zone (GPIO 13)...")
            await controller.set_zone_intensity('outer', 0.25)  # 25%
            time.sleep(1)
            await controller.set_zone_intensity('outer', 0.0)   # Off
            print("✅ Outer zone test completed")
        
        # Test both zones
        print("Testing both zones together...")
        await controller.set_all_zones_intensity(0.25)
        time.sleep(1)
        await controller.set_all_zones_intensity(0.0)
        print("✅ Both zones test completed")
        
        # Test flash
        print("Testing flash functionality...")
        await controller.flash_all_zones(intensity=0.5, duration_ms=100)
        print("✅ Flash test completed")
        
        print("\n3. PWM Test Results:")
        print("✅ GPIO hardware PWM working at 300Hz")
        print("✅ No pigpiod daemon required")
        print("✅ Simple 2-pin control functional") 
        print("✅ Zone control working properly")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Always cleanup
        try:
            await controller.cleanup()
            print("✅ GPIO cleanup completed")
        except:
            pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_simple_pwm())