#!/usr/bin/env python3
"""
Simple LED Strobe Script - Quick Test
Usage: python simple_led_strobe.py [pattern] [duration]

Patterns:
  fast    - Fast strobe (10Hz)
  medium  - Medium strobe (5Hz) 
  slow    - Slow strobe (2Hz)
  pulse   - Double pulse pattern
  fade    - Smooth fade in/out
  alt     - Alternating zones
  sync    - Both zones synchronized
  scan    - Camera scanning simulation
  all     - Run all patterns (default)
"""

import asyncio
import time
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from lighting.gpiozero_led_controller import GPIOZeroLEDController
from core.events import EventBus


async def fast_strobe(led_ctrl, duration=5.0):
    """10Hz strobe"""
    print("⚡ Fast strobe (10Hz)...")
    start = time.time()
    while time.time() - start < duration:
        await led_ctrl.set_all_brightness(0.9)
        await asyncio.sleep(0.05)
        await led_ctrl.set_all_brightness(0.0)
        await asyncio.sleep(0.05)


async def medium_strobe(led_ctrl, duration=5.0):
    """5Hz strobe"""
    print("⚡ Medium strobe (5Hz)...")
    start = time.time()
    while time.time() - start < duration:
        await led_ctrl.set_all_brightness(0.9)
        await asyncio.sleep(0.1)
        await led_ctrl.set_all_brightness(0.0)
        await asyncio.sleep(0.1)


async def slow_strobe(led_ctrl, duration=5.0):
    """2Hz strobe"""
    print("⚡ Slow strobe (2Hz)...")
    start = time.time()
    while time.time() - start < duration:
        await led_ctrl.set_all_brightness(0.9)
        await asyncio.sleep(0.25)
        await led_ctrl.set_all_brightness(0.0)
        await asyncio.sleep(0.25)


async def double_pulse(led_ctrl, duration=5.0):
    """Double flash pattern"""
    print("⚡ Double pulse...")
    start = time.time()
    while time.time() - start < duration:
        await led_ctrl.set_all_brightness(0.9)
        await asyncio.sleep(0.05)
        await led_ctrl.set_all_brightness(0.0)
        await asyncio.sleep(0.05)
        await led_ctrl.set_all_brightness(0.9)
        await asyncio.sleep(0.05)
        await led_ctrl.set_all_brightness(0.0)
        await asyncio.sleep(0.35)


async def fade_pulse(led_ctrl, duration=5.0):
    """Smooth fade in/out"""
    print("⚡ Fade pulse...")
    start = time.time()
    while time.time() - start < duration:
        # Fade up
        for b in range(0, 91, 10):
            await led_ctrl.set_all_brightness(b / 100.0)
            await asyncio.sleep(0.02)
        # Fade down
        for b in range(90, -1, -10):
            await led_ctrl.set_all_brightness(b / 100.0)
            await asyncio.sleep(0.02)


async def alternating_zones(led_ctrl, duration=5.0):
    """Alternate inner/outer zones"""
    print("⚡ Alternating zones...")
    zones = led_ctrl.get_zones()
    if len(zones) < 2:
        print("   ⚠️ Need 2 zones for this pattern, using all instead")
        await fast_strobe(led_ctrl, duration)
        return
    
    start = time.time()
    while time.time() - start < duration:
        await led_ctrl.set_zone_brightness(zones[0], 0.9)
        await led_ctrl.set_zone_brightness(zones[1], 0.0)
        await asyncio.sleep(0.1)
        await led_ctrl.set_zone_brightness(zones[0], 0.0)
        await led_ctrl.set_zone_brightness(zones[1], 0.9)
        await asyncio.sleep(0.1)
    await led_ctrl.set_all_off()


async def synchronized_flash(led_ctrl, duration=5.0):
    """Both zones together"""
    print("⚡ Synchronized flash...")
    start = time.time()
    while time.time() - start < duration:
        await led_ctrl.set_all_brightness(0.9)
        await asyncio.sleep(0.1)
        await led_ctrl.set_all_brightness(0.0)
        await asyncio.sleep(0.1)


async def camera_scan_simulation(led_ctrl, duration=10.0):
    """Simulate camera scanning pattern"""
    print("📸 Camera scanning simulation...")
    start = time.time()
    cycle = 0
    
    while time.time() - start < duration:
        # Idle at 10%
        await led_ctrl.set_all_brightness(0.1)
        await asyncio.sleep(0.5)
        
        # Flash at 30% for 650ms (camera capture)
        await led_ctrl.set_all_brightness(0.3)
        await asyncio.sleep(0.65)
        
        # Back to idle
        await led_ctrl.set_all_brightness(0.1)
        await asyncio.sleep(0.3)
        
        cycle += 1
        print(f"   Cycle {cycle}")


async def run_pattern(pattern_name, duration=5.0):
    """Run a specific strobe pattern"""
    print(f"\n{'=' * 60}")
    print(f"LED STROBE TEST: {pattern_name.upper()}")
    print(f"{'=' * 60}\n")
    
    # Initialize
    config = ConfigManager("config/scanner_config.yaml")
    event_bus = EventBus()
    led_ctrl = GPIOZeroLEDController(config, event_bus)
    
    try:
        await led_ctrl.initialize()
        print(f"✅ LED Controller ready")
        print(f"📍 Zones: {led_ctrl.get_zones()}\n")
        
        # Run selected pattern
        patterns = {
            'fast': fast_strobe,
            'medium': medium_strobe,
            'slow': slow_strobe,
            'pulse': double_pulse,
            'fade': fade_pulse,
            'alt': alternating_zones,
            'sync': synchronized_flash,
            'scan': camera_scan_simulation,
        }
        
        if pattern_name == 'all':
            print("Running all patterns...\n")
            for name, func in patterns.items():
                if name != 'scan':
                    await func(led_ctrl, duration=3.0)
                    await asyncio.sleep(0.5)
            # Longer duration for scan
            await camera_scan_simulation(led_ctrl, duration=10.0)
        else:
            pattern_func = patterns.get(pattern_name)
            if pattern_func:
                await pattern_func(led_ctrl, duration)
            else:
                print(f"❌ Unknown pattern: {pattern_name}")
                print(f"Available: {list(patterns.keys())}")
        
        print("\n✅ Test complete!")
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await led_ctrl.set_all_off()
        await led_ctrl.shutdown()
        print("🔌 LEDs off, controller shutdown\n")


if __name__ == "__main__":
    # Parse arguments
    pattern = sys.argv[1] if len(sys.argv) > 1 else 'all'
    duration = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    
    if pattern in ['-h', '--help', 'help']:
        print(__doc__)
        sys.exit(0)
    
    print("\nPress Ctrl+C to stop\n")
    asyncio.run(run_pattern(pattern, duration))
