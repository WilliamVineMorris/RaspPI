#!/usr/bin/env python3
"""
Silent LED Test - No console logging to eliminate electrical interference

This test runs the same sequence but with ZERO console output during the test,
only printing results at the end. This eliminates CPU load and electrical noise
from logging operations.

If flickering stops → the issue is console/SSH activity causing electrical interference
If flickering persists → the issue is the LED driver or power supply
"""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigManager


async def silent_test():
    """Run LED test with ZERO logging output during test"""
    
    # Suppress ALL logging during test
    import logging
    logging.getLogger().setLevel(logging.CRITICAL)
    
    # Load configuration
    config_manager = ConfigManager("config/scanner_config.yaml")
    lighting_config = config_manager.get('lighting', {})
    
    # Create controller
    controller = GPIOLEDController(lighting_config)
    
    # Initialize (silent)
    await controller.initialize()
    
    print("\n" + "="*80)
    print("SILENT LED TEST - No logging during test to eliminate interference")
    print("="*80)
    print("\n🔕 Test sequence starting in 2 seconds...")
    print("   Watch the LEDs carefully for any flickering\n")
    await asyncio.sleep(2)
    
    # Start test (NO logging from here until end)
    print("🔵 Test 1: Turn on to 30% (holding for 10 seconds)...")
    await controller.set_brightness("all", 0.3)
    await asyncio.sleep(10)  # Hold steady for 10 seconds - watch for flicker
    
    print("🔵 Test 2: Change to 50% (holding for 5 seconds)...")
    await controller.set_brightness("all", 0.5)
    await asyncio.sleep(5)  # Hold steady
    
    print("🔵 Test 3: Back to 30% (holding for 10 seconds)...")
    await controller.set_brightness("all", 0.3)
    await asyncio.sleep(10)  # Hold steady - longest test
    
    print("🔵 Test 4: Turn off...")
    await controller.turn_off_all()
    await asyncio.sleep(2)
    
    # Cleanup
    await controller.shutdown()
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nDid you observe any flickering during the 10-second hold periods?")
    print("If YES → Issue is hardware (LED driver, power supply, or GPIO)")
    print("If NO  → Issue was console logging causing CPU/electrical interference")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(silent_test())
