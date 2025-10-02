#!/usr/bin/env python3
"""
Diagnose PWM Stability Issues

Tests if lgpio/gpiozero hardware PWM has stability issues on Pi 5.
The fact that the same LED driver works perfectly on other microcontrollers
but flickers on Pi 5 suggests a Pi 5/lgpio-specific issue.

Possible causes:
1. lgpio PWM clock instability
2. gpiozero polling/updating PWM unnecessarily
3. DMA conflicts between PWM and other peripherals (cameras)
4. Pi 5 PWM peripheral initialization issues
"""

import time
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

print("="*70)
print("PWM STABILITY DIAGNOSTIC")
print("="*70)
print()
print("This will test if lgpio hardware PWM is stable on Pi 5")
print()

# Test 1: Check if gpiozero is doing unnecessary background updates
print("TEST 1: Checking gpiozero background activity")
print("-"*70)

try:
    from gpiozero import PWMLED, Device
    from gpiozero.pins.lgpio import LGPIOFactory
    
    # Set lgpio factory
    Device.pin_factory = LGPIOFactory()
    print(f"✅ Factory: {Device.pin_factory.__class__.__name__}")
    
    # Create PWMLED at 400Hz
    print("Creating PWMLED on GPIO 13 at 400Hz...")
    led = PWMLED(13, frequency=400)
    
    # Set to 30% and observe
    print("Setting LED to 30% brightness...")
    led.value = 0.3
    
    print()
    print("LED is now on at 30%. Observing for 10 seconds...")
    print("Watch the LED - it should be completely stable")
    print("If it flickers, the issue is with lgpio PWM implementation")
    print()
    
    # Monitor for background updates
    initial_value = led.value
    updates_detected = 0
    
    for i in range(10):
        time.sleep(1)
        current_value = led.value
        if abs(current_value - initial_value) > 0.001:
            updates_detected += 1
            print(f"⚠️  Value changed! {initial_value} → {current_value}")
            initial_value = current_value
        else:
            print(f"✅ Second {i+1}: Value stable at {current_value:.3f}")
    
    print()
    if updates_detected > 0:
        print(f"❌ ISSUE: {updates_detected} unexpected value changes detected!")
        print("   gpiozero is modifying PWM value in background")
    else:
        print("✅ No unexpected value changes - gpiozero is stable")
    
    led.close()
    
except Exception as e:
    print(f"❌ Test 1 failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("="*70)

# Test 2: Direct lgpio hardware PWM test (bypass gpiozero)
print("TEST 2: Direct lgpio hardware PWM test")
print("-"*70)
print("This bypasses gpiozero to test lgpio directly")
print()

try:
    import lgpio
    
    # Open GPIO chip
    h = lgpio.gpiochip_open(0)
    print(f"✅ Opened GPIO chip 0")
    
    # Set GPIO 13 to hardware PWM
    # GPIO 13 is PWM channel 1 (hardware PWM)
    pin = 13
    frequency = 400
    duty_cycle = 30  # 30%
    
    print(f"Setting GPIO {pin} to {frequency}Hz PWM at {duty_cycle}% duty cycle...")
    
    # Set PWM mode
    lgpio.tx_pwm(h, pin, frequency, duty_cycle)
    print(f"✅ Hardware PWM configured")
    
    print()
    print("PWM is now running. Observing for 10 seconds...")
    print("Watch the LED - if stable, lgpio PWM works correctly")
    print("If flickering persists, there may be a Pi 5 hardware PWM bug")
    print()
    
    for i in range(10):
        time.sleep(1)
        print(f"✅ Second {i+1}: PWM running")
    
    # Stop PWM
    lgpio.tx_pwm(h, pin, 0, 0)
    lgpio.gpiochip_close(h)
    print()
    print("✅ Test completed, PWM stopped")
    
except ImportError:
    print("⚠️  lgpio not available for direct testing")
    print("   Install with: pip3 install lgpio")
except Exception as e:
    print(f"❌ Test 2 failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("="*70)
print("DIAGNOSTIC COMPLETE")
print("="*70)
print()
print("RESULTS INTERPRETATION:")
print()
print("If BOTH tests showed stable LED with NO flicker:")
print("  → lgpio/gpiozero PWM implementation is working correctly")
print("  → Flicker during scanning must be caused by:")
print("    - Camera DMA interference with PWM peripheral")
print("    - System CPU load affecting PWM clock")
print("    - Multiple processes accessing GPIO simultaneously")
print()
print("If Test 1 (gpiozero) flickered but Test 2 (direct lgpio) was stable:")
print("  → gpiozero is doing unnecessary background updates")
print("  → Solution: Use direct lgpio PWM instead of gpiozero")
print()
print("If BOTH tests showed flickering:")
print("  → lgpio PWM implementation on Pi 5 has stability issues")
print("  → Solutions:")
print("    1. Use software PWM with high priority thread")
print("    2. Use external PWM controller (PCA9685)")
print("    3. Report bug to lgpio developers")
print()
print("If flickering stopped at 400Hz vs 100Hz:")
print("  → PWM frequency was the issue (now fixed)")
print()
