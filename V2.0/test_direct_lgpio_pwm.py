#!/usr/bin/env python3
"""
Direct lgpio PWM Test - No gpiozero abstraction layer

Since gpiozero test showed flickering, this tests if direct lgpio
is more stable. If direct lgpio is stable, we should switch from
gpiozero to direct lgpio control.
"""

import time
import sys

print("="*70)
print("DIRECT LGPIO PWM TEST")
print("="*70)
print()
print("This bypasses gpiozero entirely and uses lgpio directly.")
print("If this is stable but gpiozero flickered, we'll switch to lgpio.")
print()
input("Press ENTER to start 60-second test...")

try:
    import lgpio
    
    # Open GPIO chip
    h = lgpio.gpiochip_open(0)
    print(f"✅ Opened GPIO chip 0")
    
    # GPIO 13 for inner LED
    pin = 13
    frequency = 400  # 400Hz as requested
    duty_cycle = 30  # 30% brightness
    
    print(f"\n🔧 Configuring GPIO {pin}...")
    print(f"   Frequency: {frequency}Hz")
    print(f"   Duty Cycle: {duty_cycle}%")
    print()
    
    # Claim GPIO as output
    lgpio.gpio_claim_output(h, pin)
    print(f"✅ GPIO {pin} claimed as output")
    
    # Set hardware PWM
    lgpio.tx_pwm(h, pin, frequency, duty_cycle)
    print(f"✅ Hardware PWM started")
    
    print()
    print("="*70)
    print("🔦 LED ON at 30% brightness (400Hz PWM)")
    print("="*70)
    print()
    print("WATCH THE LED for flickering for the next 60 seconds...")
    print("(Press Ctrl+C to stop early)")
    print()
    
    # Wait 60 seconds
    start_time = time.time()
    try:
        for remaining in range(60, 0, -1):
            print(f"\rTime remaining: {remaining:2d} seconds", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
    
    elapsed = time.time() - start_time
    
    print("\n")
    print("="*70)
    print("🔦 LED OFF - Stopping PWM")
    print("="*70)
    
    # Stop PWM
    lgpio.tx_pwm(h, pin, 0, 0)
    lgpio.gpio_free(h, pin)
    lgpio.gpiochip_close(h)
    
    print()
    print("="*70)
    print("TEST RESULTS")
    print("="*70)
    print(f"Test duration: {elapsed:.1f} seconds")
    print()
    print("Did you observe any flickering?")
    print()
    print("CASE A: NO flickering with direct lgpio")
    print("  → Direct lgpio is stable!")
    print("  → Solution: Switch LED controller from gpiozero to direct lgpio")
    print("  → I will implement a direct lgpio LED controller")
    print()
    print("CASE B: Still flickering with direct lgpio")
    print("  → lgpio PWM itself has timing issues on Pi 5")
    print("  → Solutions:")
    print("    1. Try different GPIO pins (GPIO 18 instead of 13)")
    print("    2. Add hardware PWM stabilization (capacitors)")
    print("    3. Use external PWM controller (PCA9685)")
    print()
    print("Please report back which case you observed!")
    print("="*70)

except ImportError:
    print("❌ lgpio not installed!")
    print("   Install: pip3 install lgpio --break-system-packages")
    sys.exit(1)
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
