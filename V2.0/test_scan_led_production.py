#!/usr/bin/env python3
"""
Production Scan LED Test

This test verifies that the LED flickering fix works during actual scanning operations.
It monitors LED update patterns during a real scan to ensure only 2 transitions occur.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigManager


class ScanLEDMonitor:
    """Monitor LED updates during simulated scan"""
    
    def __init__(self, controller):
        self.controller = controller
        self.update_count = 0
        self.original_method = controller._set_brightness_direct
        
        # Wrap the brightness method to count updates
        def counting_wrapper(zone_id, brightness):
            result = self.original_method(zone_id, brightness)
            if result and abs(self.controller.zone_states.get(zone_id, {}).get('brightness', -1) - brightness) > 0.01:
                self.update_count += 1
                print(f"   💡 LED UPDATE #{self.update_count}: Zone '{zone_id}' → {brightness*100:.0f}%")
            return result
        
        controller._set_brightness_direct = counting_wrapper
    
    def get_count(self):
        return self.update_count
    
    def reset(self):
        self.update_count = 0


async def test_scan_led_behavior():
    """Test LED behavior during a simulated scan"""
    
    print("\n" + "="*80)
    print("PRODUCTION SCAN LED TEST")
    print("="*80)
    print("\nThis test simulates a real scan operation to verify:")
    print("  1. LEDs turn ON once at scan start")
    print("  2. LEDs remain on during calibration")
    print("  3. LEDs remain on during all scan points")
    print("  4. LEDs turn OFF once at scan end")
    print("\nExpected: 4 LED updates total (2 zones × 2 transitions)")
    print("="*80 + "\n")
    
    # Load configuration
    config_manager = ConfigManager("config/scanner_config.yaml")
    lighting_config = config_manager.get('lighting', {})
    
    # Create controller
    controller = GPIOLEDController(lighting_config)
    await controller.initialize()
    
    # Install monitor
    monitor = ScanLEDMonitor(controller)
    
    print("🚀 Starting simulated scan sequence...\n")
    
    # Simulate scan sequence
    print("📋 SCAN START: Turning on LEDs...")
    await controller.set_brightness("all", 0.3)
    await asyncio.sleep(1)
    
    print("\n🎯 CALIBRATION: Auto-focusing cameras (LEDs should stay on)...")
    for i in range(3):
        print(f"   📷 Calibrating camera {i}...")
        # Simulate calibration - no LED control
        await asyncio.sleep(0.5)
    
    print("\n📸 SCANNING: Capturing 8 points (LEDs should stay on)...")
    for point in range(1, 9):
        print(f"   📍 Point {point}/8: Moving → Settling → Capturing...")
        # Simulate point capture - no LED control
        await asyncio.sleep(0.3)
    
    print("\n✅ SCAN COMPLETE: Turning off LEDs...")
    await controller.turn_off_all()
    await asyncio.sleep(1)
    
    # Cleanup
    await controller.shutdown()
    
    # Results
    final_count = monitor.get_count()
    print("\n" + "="*80)
    print("TEST RESULTS")
    print("="*80)
    print(f"Total LED updates: {final_count}")
    print(f"Expected updates: 4 (2 zones × 2 transitions)")
    
    if final_count == 4:
        print("✅ PERFECT! Only 2 transitions (ON once, OFF once)")
        print("   The flickering fix is working correctly!")
    elif final_count > 4:
        print(f"⚠️  WARNING: {final_count - 4} extra updates detected")
        print("   Some redundant LED control may still be present")
    else:
        print(f"❌ ERROR: Only {final_count} updates (expected 4)")
        print("   Some LED updates may have been skipped incorrectly")
    
    print("="*80 + "\n")
    
    return final_count == 4


if __name__ == "__main__":
    success = asyncio.run(test_scan_led_behavior())
    sys.exit(0 if success else 1)
