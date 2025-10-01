#!/usr/bin/env python3
"""
Simple raw PWM test using only gpiozero
Tests if flickering is caused by other code or is a hardware/PWM issue

This script does NOTHING except control PWM on the LED pins.
No events, no logging overhead, no other modules.
"""

import time
from gpiozero import PWMLED
from gpiozero.pins.rpigpio import RPiGPIOFactory

# Configure pins (adjust these to match your scanner_config.yaml)
INNER_LED_PIN = 12  # GPIO12 - adjust if different
OUTER_LED_PIN = 13  # GPIO13 - adjust if different
PWM_FREQUENCY = 300  # Hz - same as your config

def test_steady_brightness():
    """Test 1: Keep LEDs at constant brightness for 30 seconds"""
    print("\n" + "="*60)
    print("TEST 1: STEADY BRIGHTNESS (30 seconds)")
    print("="*60)
    print(f"Setting up PWM at {PWM_FREQUENCY}Hz on pins {INNER_LED_PIN} and {OUTER_LED_PIN}")
    
    # Create PWM LEDs with hardware PWM
    factory = RPiGPIOFactory()
    inner_led = PWMLED(INNER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    outer_led = PWMLED(OUTER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    
    try:
        print("\nSetting both LEDs to 30% brightness...")
        inner_led.value = 0.3
        outer_led.value = 0.3
        
        print("✅ LEDs should be ON at 30% brightness")
        print("👁️  Watch the LEDs for 30 seconds - do they flicker?")
        print("⏱️  Waiting 30 seconds...")
        
        time.sleep(30)
        
        print("\n✅ Test complete - turning off LEDs")
        
    finally:
        inner_led.off()
        outer_led.off()
        inner_led.close()
        outer_led.close()
        print("✅ LEDs turned off and closed")


def test_brightness_changes():
    """Test 2: Gradually change brightness to test PWM response"""
    print("\n" + "="*60)
    print("TEST 2: BRIGHTNESS CHANGES (10 seconds)")
    print("="*60)
    print(f"Setting up PWM at {PWM_FREQUENCY}Hz on pins {INNER_LED_PIN} and {OUTER_LED_PIN}")
    
    # Create PWM LEDs with hardware PWM
    factory = RPiGPIOFactory()
    inner_led = PWMLED(INNER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    outer_led = PWMLED(OUTER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    
    try:
        print("\nRamping brightness from 0% to 50% in 5% steps...")
        print("👁️  Watch for any flickering during transitions")
        
        for brightness in [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50]:
            print(f"  Setting brightness to {brightness*100:.0f}%...")
            inner_led.value = brightness
            outer_led.value = brightness
            time.sleep(1)  # Hold each brightness for 1 second
        
        print("\n✅ Test complete - turning off LEDs")
        
    finally:
        inner_led.off()
        outer_led.off()
        inner_led.close()
        outer_led.close()
        print("✅ LEDs turned off and closed")


def test_simultaneous_vs_sequential():
    """Test 3: Compare simultaneous vs sequential brightness changes"""
    print("\n" + "="*60)
    print("TEST 3: SIMULTANEOUS vs SEQUENTIAL (20 seconds)")
    print("="*60)
    print(f"Setting up PWM at {PWM_FREQUENCY}Hz on pins {INNER_LED_PIN} and {OUTER_LED_PIN}")
    
    # Create PWM LEDs with hardware PWM
    factory = RPiGPIOFactory()
    inner_led = PWMLED(INNER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    outer_led = PWMLED(OUTER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    
    try:
        # Test sequential changes (OLD method - may cause flicker)
        print("\nPart A: SEQUENTIAL brightness changes (10 seconds)")
        print("👁️  Watch for flickering when LEDs change one after another")
        
        for i in range(10):
            print(f"  Cycle {i+1}/10: Sequential change...")
            inner_led.value = 0.3  # Set inner first
            outer_led.value = 0.3  # Set outer second (slight delay)
            time.sleep(0.5)
            inner_led.value = 0.0  # Turn off inner first
            outer_led.value = 0.0  # Turn off outer second (slight delay)
            time.sleep(0.5)
        
        time.sleep(1)
        
        # Test simultaneous changes (NEW method - should reduce flicker)
        print("\nPart B: SIMULTANEOUS brightness changes (10 seconds)")
        print("👁️  Watch for flickering - should be less than Part A")
        
        for i in range(10):
            print(f"  Cycle {i+1}/10: Simultaneous change...")
            # Change both at exactly the same time
            inner_led.value = 0.3
            outer_led.value = 0.3
            time.sleep(0.5)
            inner_led.value = 0.0
            outer_led.value = 0.0
            time.sleep(0.5)
        
        print("\n✅ Test complete - turning off LEDs")
        
    finally:
        inner_led.off()
        outer_led.off()
        inner_led.close()
        outer_led.close()
        print("✅ LEDs turned off and closed")


def test_capture_simulation():
    """Test 4: Simulate the exact capture sequence"""
    print("\n" + "="*60)
    print("TEST 4: CAPTURE SEQUENCE SIMULATION (5 captures)")
    print("="*60)
    print(f"Setting up PWM at {PWM_FREQUENCY}Hz on pins {INNER_LED_PIN} and {OUTER_LED_PIN}")
    
    # Create PWM LEDs with hardware PWM
    factory = RPiGPIOFactory()
    inner_led = PWMLED(INNER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    outer_led = PWMLED(OUTER_LED_PIN, frequency=PWM_FREQUENCY, pin_factory=factory)
    
    try:
        print("\nSimulating 5 image captures with LED flash...")
        print("👁️  This mimics the actual scanning operation")
        
        for capture_num in range(1, 6):
            print(f"\n📸 Capture {capture_num}/5:")
            
            # Turn on LEDs (constant lighting mode)
            print("  💡 Turning ON LEDs at 30%...")
            inner_led.value = 0.3
            outer_led.value = 0.3
            time.sleep(0.05)  # 50ms settling time
            
            # Simulate camera capture time (cameras take ~1-2 seconds)
            print("  📷 Capturing image (simulating 2 second exposure)...")
            time.sleep(2.0)
            
            # Turn off LEDs
            print("  💡 Turning OFF LEDs...")
            inner_led.value = 0.0
            outer_led.value = 0.0
            
            # Delay between captures
            print("  ⏱️  Waiting 1 second before next capture...")
            time.sleep(1.0)
        
        print("\n✅ All captures complete")
        
    finally:
        inner_led.off()
        outer_led.off()
        inner_led.close()
        outer_led.close()
        print("✅ LEDs turned off and closed")


def main():
    """Run all PWM tests"""
    print("\n" + "="*60)
    print("RAW PWM FLICKER TEST - gpiozero only")
    print("="*60)
    print("\nThis script tests ONLY the PWM hardware/library.")
    print("No other scanner code is running.")
    print("\nIf flickering occurs in these tests, the issue is:")
    print("  • Hardware PWM limitation")
    print("  • GPIO driver issue")
    print("  • LED driver incompatibility")
    print("  • Power supply noise")
    print("\nIf NO flickering occurs, the issue is in the scanner code.")
    
    input("\n⚠️  Make sure scanner system is NOT running! Press Enter to continue...")
    
    try:
        # Run all tests
        test_steady_brightness()
        
        input("\nPress Enter to continue to Test 2...")
        test_brightness_changes()
        
        input("\nPress Enter to continue to Test 3...")
        test_simultaneous_vs_sequential()
        
        input("\nPress Enter to continue to Test 4...")
        test_capture_simulation()
        
        print("\n" + "="*60)
        print("ALL TESTS COMPLETE")
        print("="*60)
        print("\nRESULTS INTERPRETATION:")
        print("• If ALL tests showed flickering:")
        print("  → Hardware/PWM issue - try different PWM frequency")
        print("  → Check LED driver specs for PWM frequency requirements")
        print("  → Check power supply stability")
        print("\n• If ONLY Test 3 Part A (sequential) flickered:")
        print("  → The fix we applied should work")
        print("  → Simultaneous updates reduce flicker")
        print("\n• If NO tests showed flickering:")
        print("  → Problem is in scanner code, not PWM hardware")
        print("  → Look for other code interfering with LEDs")
        print("\n• If Test 4 (capture simulation) flickered:")
        print("  → The timing/sequence in captures causes issues")
        print("  → May need different approach for LED control")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Check your config file for correct GPIO pins!")
    print(f"Current pins: Inner={INNER_LED_PIN}, Outer={OUTER_LED_PIN}")
    print("Edit this script if your pins are different.\n")
    
    main()
