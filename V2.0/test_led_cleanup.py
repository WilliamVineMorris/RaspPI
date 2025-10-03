#!/usr/bin/env python3
"""
Test LED cleanup on script exit.
This script turns on LEDs, then exits after a few seconds.
The LEDs should automatically turn off on exit.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigurationManager

async def test_cleanup():
    """Test that LEDs turn off when script exits"""
    
    print("=" * 60)
    print("LED Cleanup Test")
    print("=" * 60)
    print()
    
    # Load configuration
    config_manager = ConfigurationManager()
    config = config_manager.get_config()
    lighting_config = config.get('lighting', {})
    
    print("1. Initializing LED controller...")
    controller = GPIOLEDController(lighting_config)
    
    # Initialize controller
    await controller.initialize()
    print("   ✅ Controller initialized")
    print()
    
    # Turn on LEDs
    print("2. Turning on LEDs at 50% brightness...")
    for zone_id in controller.zone_configs.keys():
        await controller.set_brightness(zone_id, 0.5)
        print(f"   💡 Zone '{zone_id}' ON at 50%")
    print()
    
    # Wait a few seconds
    print("3. LEDs are ON - waiting 5 seconds...")
    for i in range(5, 0, -1):
        print(f"   Exiting in {i}...", end='\r')
        await asyncio.sleep(1)
    print()
    print()
    
    # Script will exit here - cleanup should turn off LEDs automatically
    print("4. Exiting script now...")
    print("   🛡️  Cleanup handlers should turn off LEDs automatically")
    print()
    print("Watch for:")
    print("   - '🛡️  Cleanup: Turning off all LEDs before exit...'")
    print("   - '✅ Cleanup complete - all LEDs turned off'")
    print()
    
    # Exit without manually turning off LEDs
    # The atexit handler should do it automatically

if __name__ == "__main__":
    try:
        asyncio.run(test_cleanup())
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted with Ctrl+C - cleanup should still run!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🔍 Check if LEDs are OFF now!")
    print("If they're still ON, the cleanup didn't work.")
