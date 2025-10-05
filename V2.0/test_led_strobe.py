#!/usr/bin/env python3
"""
LED Strobe Test Script
Tests LED flash functionality with various strobe patterns
"""

import asyncio
import time
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from lighting.gpiozero_led_controller import GPIOZeroLEDController
from core.events import EventBus


async def strobe_pattern_1(led_controller, zone_name: str, duration: float = 5.0):
    """Fast strobe: 10Hz (100ms on/off)"""
    print(f"\n⚡ Pattern 1: Fast Strobe (10Hz) - {zone_name}")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        await led_controller.set_zone_brightness(zone_name, 1.0)
        await asyncio.sleep(0.05)
        await led_controller.set_zone_brightness(zone_name, 0.0)
        await asyncio.sleep(0.05)
        count += 1
    
    print(f"   Completed {count} flashes")


async def strobe_pattern_2(led_controller, zone_name: str, duration: float = 5.0):
    """Medium strobe: 5Hz (200ms on/off)"""
    print(f"\n⚡ Pattern 2: Medium Strobe (5Hz) - {zone_name}")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        await led_controller.set_zone_brightness(zone_name, 1.0)
        await asyncio.sleep(0.1)
        await led_controller.set_zone_brightness(zone_name, 0.0)
        await asyncio.sleep(0.1)
        count += 1
    
    print(f"   Completed {count} flashes")


async def strobe_pattern_3(led_controller, zone_name: str, duration: float = 5.0):
    """Slow strobe: 2Hz (500ms on/off)"""
    print(f"\n⚡ Pattern 3: Slow Strobe (2Hz) - {zone_name}")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        await led_controller.set_zone_brightness(zone_name, 1.0)
        await asyncio.sleep(0.25)
        await led_controller.set_zone_brightness(zone_name, 0.0)
        await asyncio.sleep(0.25)
        count += 1
    
    print(f"   Completed {count} flashes")


async def strobe_pattern_4(led_controller, zone_name: str, duration: float = 5.0):
    """Double pulse: Quick double flash with pause"""
    print(f"\n⚡ Pattern 4: Double Pulse - {zone_name}")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        # First pulse
        await led_controller.set_zone_brightness(zone_name, 1.0)
        await asyncio.sleep(0.05)
        await led_controller.set_zone_brightness(zone_name, 0.0)
        await asyncio.sleep(0.05)
        
        # Second pulse
        await led_controller.set_zone_brightness(zone_name, 1.0)
        await asyncio.sleep(0.05)
        await led_controller.set_zone_brightness(zone_name, 0.0)
        await asyncio.sleep(0.35)  # Longer pause
        count += 1
    
    print(f"   Completed {count} double-flashes")


async def strobe_pattern_5(led_controller, zone_name: str, duration: float = 5.0):
    """Fade pulse: Smooth fade in/out"""
    print(f"\n⚡ Pattern 5: Fade Pulse - {zone_name}")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        # Fade up
        for brightness in range(0, 101, 10):
            await led_controller.set_zone_brightness(zone_name, brightness / 100.0)
            await asyncio.sleep(0.02)
        
        # Fade down
        for brightness in range(100, -1, -10):
            await led_controller.set_zone_brightness(zone_name, brightness / 100.0)
            await asyncio.sleep(0.02)
        
        count += 1
    
    print(f"   Completed {count} pulses")


async def strobe_pattern_6(led_controller, zone_name: str, duration: float = 5.0):
    """Random strobe: Unpredictable timing"""
    print(f"\n⚡ Pattern 6: Random Strobe - {zone_name}")
    import random
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        brightness = random.choice([0.3, 0.5, 0.7, 1.0])
        on_time = random.uniform(0.02, 0.15)
        off_time = random.uniform(0.05, 0.2)
        
        await led_controller.set_zone_brightness(zone_name, brightness)
        await asyncio.sleep(on_time)
        await led_controller.set_zone_brightness(zone_name, 0.0)
        await asyncio.sleep(off_time)
        count += 1
    
    print(f"   Completed {count} random flashes")


async def strobe_pattern_7_dual(led_controller, duration: float = 5.0):
    """Alternating zones: Inner and outer alternate"""
    print(f"\n⚡ Pattern 7: Alternating Zones (Inner ↔ Outer)")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        # Inner on, outer off
        await led_controller.set_zone_brightness("inner", 1.0)
        await led_controller.set_zone_brightness("outer", 0.0)
        await asyncio.sleep(0.1)
        
        # Inner off, outer on
        await led_controller.set_zone_brightness("inner", 0.0)
        await led_controller.set_zone_brightness("outer", 1.0)
        await asyncio.sleep(0.1)
        count += 1
    
    # Turn both off
    await led_controller.set_zone_brightness("inner", 0.0)
    await led_controller.set_zone_brightness("outer", 0.0)
    
    print(f"   Completed {count} alternations")


async def strobe_pattern_8_dual(led_controller, duration: float = 5.0):
    """Synchronized flash: Both zones together"""
    print(f"\n⚡ Pattern 8: Synchronized Flash (Both Together)")
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        # Both on
        await led_controller.set_zone_brightness("inner", 1.0)
        await led_controller.set_zone_brightness("outer", 1.0)
        await asyncio.sleep(0.1)
        
        # Both off
        await led_controller.set_zone_brightness("inner", 0.0)
        await led_controller.set_zone_brightness("outer", 0.0)
        await asyncio.sleep(0.1)
        count += 1
    
    print(f"   Completed {count} synchronized flashes")


async def camera_flash_simulation(led_controller, duration: float = 10.0):
    """Simulate camera flash pattern (like actual scanning)"""
    print(f"\n📸 Camera Flash Simulation (scanning pattern)")
    print("   Simulating: idle → flash → capture → idle cycle")
    
    start_time = time.time()
    count = 0
    
    while (time.time() - start_time) < duration:
        # Idle state (10% brightness)
        await led_controller.set_zone_brightness("inner", 0.1)
        await led_controller.set_zone_brightness("outer", 0.1)
        await asyncio.sleep(0.5)
        
        # Flash for capture (30% brightness for 650ms)
        await led_controller.set_zone_brightness("inner", 0.3)
        await led_controller.set_zone_brightness("outer", 0.3)
        await asyncio.sleep(0.65)
        
        # Back to idle
        await led_controller.set_zone_brightness("inner", 0.1)
        await led_controller.set_zone_brightness("outer", 0.1)
        await asyncio.sleep(0.3)
        count += 1
    
    print(f"   Completed {count} flash cycles")


async def run_strobe_test():
    """Main test function"""
    print("=" * 70)
    print("LED STROBE TEST SCRIPT")
    print("=" * 70)
    print("\nInitializing LED controller...")
    
    # Load configuration
    config_manager = ConfigManager("config/scanner_config.yaml")
    event_bus = EventBus()
    
    # Create LED controller
    led_controller = GPIOZeroLEDController(config_manager, event_bus)
    
    try:
        # Initialize
        await led_controller.initialize()
        print("✅ LED Controller initialized")
        
        # Get available zones
        zones = led_controller.get_zones()
        print(f"\n📍 Available LED zones: {zones}")
        
        print("\n" + "=" * 70)
        print("STARTING STROBE PATTERNS")
        print("=" * 70)
        
        # Single zone patterns (test each zone individually)
        for zone in zones:
            print(f"\n{'─' * 70}")
            print(f"Testing Zone: {zone.upper()}")
            print(f"{'─' * 70}")
            
            await strobe_pattern_1(led_controller, zone, duration=3.0)
            await asyncio.sleep(0.5)
            
            await strobe_pattern_2(led_controller, zone, duration=3.0)
            await asyncio.sleep(0.5)
            
            await strobe_pattern_3(led_controller, zone, duration=3.0)
            await asyncio.sleep(0.5)
            
            await strobe_pattern_4(led_controller, zone, duration=3.0)
            await asyncio.sleep(0.5)
            
            await strobe_pattern_5(led_controller, zone, duration=3.0)
            await asyncio.sleep(0.5)
            
            await strobe_pattern_6(led_controller, zone, duration=3.0)
            await asyncio.sleep(1.0)
        
        # Dual zone patterns (if multiple zones available)
        if len(zones) >= 2:
            print(f"\n{'─' * 70}")
            print(f"Testing Dual-Zone Patterns")
            print(f"{'─' * 70}")
            
            await strobe_pattern_7_dual(led_controller, duration=5.0)
            await asyncio.sleep(0.5)
            
            await strobe_pattern_8_dual(led_controller, duration=5.0)
            await asyncio.sleep(0.5)
        
        # Camera flash simulation
        print(f"\n{'─' * 70}")
        print(f"Camera Flash Simulation")
        print(f"{'─' * 70}")
        await camera_flash_simulation(led_controller, duration=10.0)
        
        print("\n" + "=" * 70)
        print("STROBE TEST COMPLETE")
        print("=" * 70)
        
        # Turn off all LEDs
        print("\n🔌 Turning off all LEDs...")
        await led_controller.set_all_off()
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        print("\n🧹 Cleaning up...")
        await led_controller.shutdown()
        print("✅ LED Controller shutdown complete")


if __name__ == "__main__":
    print("\nPress Ctrl+C to stop the test at any time\n")
    asyncio.run(run_strobe_test())
