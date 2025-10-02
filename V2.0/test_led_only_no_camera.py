#!/usr/bin/env python3
"""
Test LEDs WITHOUT camera capture to isolate flickering cause

This script runs LEDs at constant 30% brightness for 60 seconds WITHOUT
any camera capture. This helps determine if:
1. PWM/power issues (flicker even without camera)
2. Camera CPU load issues (no flicker without camera)
"""

import asyncio
import sys
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigManager
from core.exceptions import ConfigurationError

async def test_led_stability():
    """Test LED stability without camera interference"""
    
    print("="*70)
    print("LED STABILITY TEST - No Camera Capture")
    print("="*70)
    print()
    print("This test runs LEDs at 30% brightness for 60 seconds")
    print("WITHOUT any camera capture to isolate the flickering cause.")
    print()
    print("INSTRUCTIONS:")
    print("1. Watch the LEDs closely for any flickering")
    print("2. Note if flickering is constant or intermittent")
    print("3. Press Ctrl+C to stop early if needed")
    print()
    input("Press ENTER to start test...")
    
    try:
        # Load configuration
        print("\n📋 Loading configuration...")
        config_mgr = ConfigManager()
        config = config_mgr.get_config()
        
        # Initialize LED controller
        print("💡 Initializing LED controller...")
        led_controller = GPIOLEDController(config['lighting'])
        await led_controller.initialize()
        
        print("\n" + "="*70)
        print("🔦 LEDs ON at 30% brightness")
        print("="*70)
        print()
        print("Watch for flickering for the next 60 seconds...")
        print("(Press Ctrl+C to stop early)")
        print()
        
        # Turn on LEDs
        await led_controller.set_brightness("all", 0.3)
        
        # Wait 60 seconds
        start_time = time.time()
        try:
            for remaining in range(60, 0, -1):
                print(f"\rTime remaining: {remaining:2d} seconds", end="", flush=True)
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️ Test interrupted by user")
        
        elapsed = time.time() - start_time
        
        print("\n")
        print("="*70)
        print("🔦 LEDs OFF")
        print("="*70)
        
        # Turn off LEDs
        await led_controller.set_brightness("all", 0.0)
        await asyncio.sleep(0.5)
        
        # Shutdown
        print("\n💤 Shutting down LED controller...")
        await led_controller.shutdown()
        
        # Results
        print("\n" + "="*70)
        print("TEST RESULTS")
        print("="*70)
        print(f"Test duration: {elapsed:.1f} seconds")
        print()
        print("Did you observe any flickering?")
        print()
        print("IF YES (flickering WITHOUT camera):")
        print("  → Issue is PWM frequency, power supply, or LED circuit")
        print("  → Solutions:")
        print("    1. Increase PWM frequency from 100Hz to 300-500Hz")
        print("    2. Check power supply (should be 25W+ for Pi 5)")
        print("    3. Verify LED driver circuit has proper current limiting")
        print()
        print("IF NO (no flickering WITHOUT camera):")
        print("  → Issue is camera CPU load interfering with LED control")
        print("  → Solutions:")
        print("    1. Lower camera resolution during capture")
        print("    2. Increase LED control thread priority")
        print("    3. Consider dedicated LED controller hardware")
        print()
        
    except ConfigurationError as e:
        print(f"\n❌ Configuration error: {e}")
        print("Make sure scanner_config.yaml is properly configured")
        return False
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    try:
        result = asyncio.run(test_led_stability())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)
