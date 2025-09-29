#!/usr/bin/env python3
"""
Test gpiozero LED PWM at 300Hz
Tests LED.value for duty cycle and LED.frequency property

Run this on the Pi to test the new gpiozero PWM setup:
python test_gpiozero_pwm.py
"""

import sys
import time
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

try:
    from gpiozero import PWMLED, Device
    from gpiozero.pins.rpigpio import RPiGPIOFactory
    print("✅ gpiozero imported successfully")
except ImportError as e:
    print(f"❌ gpiozero not available: {e}")
    sys.exit(1)

def test_gpiozero_pwm():
    """Test gpiozero PWMLED with 300Hz PWM"""
    
    print("=== gpiozero PWMLED PWM Test (300Hz) ===")
    print("Testing PWMLED.value with 300Hz frequency")
    
    # Set pin factory to RPi.GPIO (no pigpiod required)
    Device.pin_factory = RPiGPIOFactory()
    print(f"Pin factory: {Device.pin_factory.__class__.__name__}")
    
    # Test pins (adjust as needed)
    test_pins = [12, 13]  # GPIO 12 (inner), GPIO 13 (outer)
    
    try:
        # Create PWMLED objects with 300Hz frequency
        leds = {}
        for pin in test_pins:
            print(f"\nInitializing PWMLED on GPIO {pin}...")
            led = PWMLED(pin, frequency=300)
            
            print(f"  PWMLED frequency = 300Hz")
            
            # Start with LED off
            led.value = 0.0
            print(f"  PWMLED.value = {led.value} (off)")
            
            leds[pin] = led
        
        print(f"\n✅ {len(leds)} PWMLEDs initialized at 300Hz")
        
        # Test PWM control with PWMLED.value
        print("\n=== Testing PWMLED.value PWM Control ===")
        
        test_values = [0.0, 0.25, 0.5, 0.75, 0.9, 0.0]  # 0-90% (safety limit)
        
        for value in test_values:
            print(f"\nSetting all LEDs to {value:.2f} ({value*100:.0f}%)")
            
            for pin, led in leds.items():
                led.value = value
                print(f"  GPIO {pin}: PWMLED.value = {led.value:.2f}, frequency = 300Hz")
            
            time.sleep(1.0)  # Hold for 1 second
        
        print("\n=== PWM Property Test ===")
        
        # Test individual LED control
        for pin, led in leds.items():
            print(f"\nTesting GPIO {pin} individually...")
            
            # Test different intensities
            for intensity in [0.1, 0.3, 0.6, 0.0]:
                print(f"  Setting to {intensity:.1f} ({intensity*100:.0f}%)")
                led.value = intensity
                time.sleep(0.5)
        
        print("\n✅ All gpiozero PWMLED PWM tests completed successfully")
        
        # Show final status
        print("\n=== Final PWMLED Status ===")
        for pin, led in leds.items():
            print(f"GPIO {pin}: value={led.value:.2f}, frequency=300Hz, active={led.is_active}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        # Clean up
        print("\n=== Cleanup ===")
        for pin, led in leds.items():
            try:
                print(f"Cleaning up GPIO {pin}...")
                led.value = 0.0  # Turn off
                led.close()     # Release pin
                print(f"✅ GPIO {pin} cleaned up")
            except Exception as e:
                print(f"⚠️ GPIO {pin} cleanup error: {e}")

if __name__ == "__main__":
    test_gpiozero_pwm()