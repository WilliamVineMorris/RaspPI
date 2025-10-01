#!/usr/bin/env python3
"""
Hardware PWM Verification Test

This test verifies that:
1. GPIO 13 and 18 are using HARDWARE PWM (not software PWM)
2. Hardware PWM at 100Hz is immune to CPU load/console activity
3. LEDs remain stable even with heavy logging

Expected: ZERO flickering during heavy console output
"""

import asyncio
import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigManager


async def stress_test_hardware_pwm():
    """Test hardware PWM stability under CPU load"""
    
    print("\n" + "="*80)
    print("HARDWARE PWM VERIFICATION TEST")
    print("="*80)
    print("\nThis test verifies GPIO 13 and 18 are using HARDWARE PWM")
    print("Hardware PWM should be immune to:")
    print("  • CPU load from console logging")
    print("  • Python I/O operations")
    print("  • SSH/network activity")
    print("\nDuring this test, watch the LEDs carefully.")
    print("With true hardware PWM, you should see ZERO flickering")
    print("even during heavy console output.")
    print("="*80 + "\n")
    
    # Load configuration
    config_manager = ConfigManager("config/scanner_config.yaml")
    lighting_config = config_manager.get('lighting', {})
    
    print(f"🔧 Configuration: PWM frequency = {lighting_config.get('pwm_frequency')}Hz")
    print(f"🔧 GPIO pins: {lighting_config['zones']}")
    print()
    
    # Create controller
    controller = GPIOLEDController(lighting_config)
    
    print("📋 Initializing LED controller...")
    await controller.initialize()
    print()
    
    # Test 1: Stable ON with no console activity
    print("="*80)
    print("TEST 1: Baseline - LEDs ON with minimal console output")
    print("="*80)
    print("🔵 Setting LEDs to 30%...")
    await controller.set_brightness("all", 0.3)
    print("⏳ Holding for 5 seconds (watch for flicker)...")
    await asyncio.sleep(5)
    print("✅ Test 1 complete\n")
    
    # Test 2: Heavy console output
    print("="*80)
    print("TEST 2: CPU Stress - Heavy console logging while LEDs ON")
    print("="*80)
    print("🔵 LEDs at 30%, starting heavy logging...")
    print("⏳ If you see flickering during this output, PWM is SOFTWARE-based")
    print("⏳ If LEDs stay stable, PWM is HARDWARE-based\n")
    
    # Generate 100 lines of output rapidly
    for i in range(100):
        print(f"   📊 Log entry {i+1:3d}/100 - CPU activity simulation - "
              f"timestamp: {time.time():.6f}")
        await asyncio.sleep(0.05)  # 50ms between messages (20 msgs/sec)
    
    print("\n✅ Test 2 complete - Did you observe any flickering?\n")
    
    # Test 3: Varying brightness with heavy logging
    print("="*80)
    print("TEST 3: Brightness Changes + Heavy Logging")
    print("="*80)
    print("🔵 Cycling through brightness levels with console output...\n")
    
    for brightness in [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]:
        print(f"💡 Setting brightness to {brightness*100:.0f}%")
        await controller.set_brightness("all", brightness)
        
        # Heavy logging at each brightness
        for i in range(20):
            print(f"   📊 Brightness {brightness*100:.0f}% - Log {i+1}/20 - Time: {time.time():.6f}")
            await asyncio.sleep(0.03)
        
        await asyncio.sleep(0.2)
    
    print("\n✅ Test 3 complete\n")
    
    # Test 4: Return to steady state
    print("="*80)
    print("TEST 4: Final Stability Check")
    print("="*80)
    print("🔵 Setting LEDs to 30%...")
    await controller.set_brightness("all", 0.3)
    print("⏳ Holding for 10 seconds (final flicker check)...")
    await asyncio.sleep(10)
    print("✅ Test 4 complete\n")
    
    # Cleanup
    print("🔵 Turning off LEDs...")
    await controller.turn_off_all()
    await asyncio.sleep(1)
    
    await controller.shutdown()
    
    # Results
    print("\n" + "="*80)
    print("TEST COMPLETE - Please answer these questions:")
    print("="*80)
    print("\n1. Did you see flickering during TEST 2 (heavy logging)?")
    print("   YES → GPIO pins are using SOFTWARE PWM (needs fixing)")
    print("   NO  → GPIO pins are using HARDWARE PWM (correct!)")
    
    print("\n2. Did LEDs stay stable during brightness changes in TEST 3?")
    print("   YES → Hardware PWM is working perfectly")
    print("   NO  → May need to check LED driver or power supply")
    
    print("\n3. Did you see any flicker at all during any test?")
    print("   YES → Issue is hardware (driver/power), not software PWM")
    print("   NO  → Perfect! Hardware PWM + software fix = zero flicker")
    
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(stress_test_hardware_pwm())
