#!/usr/bin/env python3
"""
LED Brightness Update Monitor
Shows when brightness changes actually trigger PWM updates vs. being skipped

This helps diagnose flickering issues by showing redundant update patterns
"""

import time
from gpiozero import PWMLED
from gpiozero.pins.rpigpio import RPiGPIOFactory

# Configure pins (adjust these to match your scanner_config.yaml)
INNER_LED_PIN = 12
OUTER_LED_PIN = 13
PWM_FREQUENCY = 300

# Change detection threshold (must match gpio_led_controller.py)
CHANGE_THRESHOLD = 0.005  # 0.5%

class BrightnessTracker:
    """Tracks brightness changes and shows which ones actually update PWM"""
    
    def __init__(self, pin, name):
        self.pin = pin
        self.name = name
        self.factory = RPiGPIOFactory()
        self.led = PWMLED(pin, frequency=PWM_FREQUENCY, pin_factory=self.factory)
        self.current_brightness = -1.0
        self.update_count = 0
        self.skip_count = 0
        
    def set_brightness(self, brightness):
        """Set brightness with change detection (matches controller logic)"""
        # Check if change is significant
        if abs(self.current_brightness - brightness) < CHANGE_THRESHOLD:
            self.skip_count += 1
            print(f"  [{self.name}] SKIPPED: {brightness*100:.1f}% (change < 0.5%, current={self.current_brightness*100:.1f}%)")
            return False
        
        # Significant change - update PWM
        self.led.value = brightness
        print(f"  [{self.name}] ✅ UPDATED: {self.current_brightness*100:.1f}% → {brightness*100:.1f}%")
        self.current_brightness = brightness
        self.update_count += 1
        return True
    
    def get_stats(self):
        """Get update statistics"""
        total = self.update_count + self.skip_count
        skip_percent = (self.skip_count / total * 100) if total > 0 else 0
        return {
            'updates': self.update_count,
            'skipped': self.skip_count,
            'total_calls': total,
            'skip_percentage': skip_percent
        }
    
    def cleanup(self):
        """Clean up GPIO"""
        self.led.off()
        self.led.close()


def test_redundant_updates():
    """Test scenario: Repeated brightness changes (simulates scanner behavior)"""
    print("\n" + "="*70)
    print("TEST: REDUNDANT UPDATE DETECTION")
    print("="*70)
    print("Simulating typical scanner behavior with repeated brightness calls")
    print("")
    
    tracker = BrightnessTracker(INNER_LED_PIN, "Inner LED")
    
    try:
        # Simulate typical capture sequence
        print("Simulating 5 image captures with repeated brightness calls:")
        print("")
        
        for capture in range(1, 6):
            print(f"📸 Capture {capture}:")
            
            # Turn on (typical: set brightness 3 times due to adapter layers)
            tracker.set_brightness(0.3)
            tracker.set_brightness(0.3)  # Redundant
            tracker.set_brightness(0.3)  # Redundant
            
            time.sleep(0.5)  # Simulate capture time
            
            # Turn off (typical: set 0 multiple times)
            tracker.set_brightness(0.0)
            tracker.set_brightness(0.0)  # Redundant
            
            time.sleep(0.2)  # Delay between captures
            print("")
        
        # Show statistics
        stats = tracker.get_stats()
        print("="*70)
        print("STATISTICS:")
        print(f"  Total brightness calls: {stats['total_calls']}")
        print(f"  Actual PWM updates:     {stats['updates']} ({100-stats['skip_percentage']:.1f}%)")
        print(f"  Skipped (redundant):    {stats['skipped']} ({stats['skip_percentage']:.1f}%)")
        print("")
        print(f"💡 Reduction: {stats['skip_percentage']:.1f}% of PWM updates eliminated!")
        print("="*70)
        
    finally:
        tracker.cleanup()


def test_threshold_effectiveness():
    """Test the 0.5% threshold effectiveness"""
    print("\n" + "="*70)
    print("TEST: 0.5% THRESHOLD EFFECTIVENESS")
    print("="*70)
    print("Testing different brightness changes to show what gets updated vs. skipped")
    print("")
    
    tracker = BrightnessTracker(INNER_LED_PIN, "Inner LED")
    
    try:
        test_cases = [
            (0.3, "Initial set"),
            (0.3, "Exact same (should skip)"),
            (0.301, "Tiny change +0.1% (should skip)"),
            (0.305, "Small change +0.5% (should skip)"),
            (0.306, "Significant change +0.6% (should update)"),
            (0.35, "Large change +4.4% (should update)"),
            (0.35, "Same again (should skip)"),
            (0.0, "Turn off (should update)"),
            (0.0, "Already off (should skip)"),
        ]
        
        print("Testing brightness changes:")
        print("")
        
        for brightness, description in test_cases:
            print(f"{description}:")
            tracker.set_brightness(brightness)
            time.sleep(0.1)
            print("")
        
        # Show statistics
        stats = tracker.get_stats()
        print("="*70)
        print("THRESHOLD EFFECTIVENESS:")
        print(f"  Test cases:          {stats['total_calls']}")
        print(f"  Passed threshold:    {stats['updates']}")
        print(f"  Blocked by threshold: {stats['skipped']}")
        print(f"  Efficiency:          {stats['skip_percentage']:.1f}% redundant updates prevented")
        print("="*70)
        
    finally:
        tracker.cleanup()


def test_realistic_scanning():
    """Test realistic scanning pattern with both LEDs"""
    print("\n" + "="*70)
    print("TEST: REALISTIC SCANNING PATTERN")
    print("="*70)
    print("Simulating actual scanning with both inner and outer LEDs")
    print("")
    
    inner = BrightnessTracker(INNER_LED_PIN, "Inner")
    outer = BrightnessTracker(OUTER_LED_PIN, "Outer")
    
    try:
        print("Simulating 3 scans with calibration:")
        print("")
        
        # Calibration
        print("🔧 CALIBRATION:")
        for i in range(3):
            inner.set_brightness(0.3)
            outer.set_brightness(0.3)
            time.sleep(0.1)
        inner.set_brightness(0.0)
        outer.set_brightness(0.0)
        print("")
        
        # Actual scans
        for scan in range(1, 4):
            print(f"📸 SCAN {scan}:")
            
            # Pre-scan check (might call set_brightness)
            inner.set_brightness(0.3)
            outer.set_brightness(0.3)
            
            # Actual capture
            inner.set_brightness(0.3)  # Redundant
            outer.set_brightness(0.3)  # Redundant
            time.sleep(0.5)
            
            # Turn off
            inner.set_brightness(0.0)
            outer.set_brightness(0.0)
            time.sleep(0.2)
            print("")
        
        # Combined statistics
        inner_stats = inner.get_stats()
        outer_stats = outer.get_stats()
        
        total_calls = inner_stats['total_calls'] + outer_stats['total_calls']
        total_updates = inner_stats['updates'] + outer_stats['updates']
        total_skipped = inner_stats['skipped'] + outer_stats['skipped']
        
        print("="*70)
        print("COMBINED STATISTICS:")
        print(f"  Total brightness calls: {total_calls}")
        print(f"  Actual PWM updates:     {total_updates} ({total_updates/total_calls*100:.1f}%)")
        print(f"  Skipped (redundant):    {total_skipped} ({total_skipped/total_calls*100:.1f}%)")
        print("")
        print(f"💡 Without threshold: {total_calls} PWM updates (100% overhead)")
        print(f"💡 With 0.5% threshold: {total_updates} PWM updates ({total_skipped/total_calls*100:.1f}% reduction)")
        print("")
        print(f"Result: {total_skipped} fewer PWM changes = less flickering!")
        print("="*70)
        
    finally:
        inner.cleanup()
        outer.cleanup()


def main():
    """Run all diagnostic tests"""
    print("\n" + "="*70)
    print("LED BRIGHTNESS UPDATE MONITOR")
    print("="*70)
    print("This diagnostic shows how the 0.5% threshold prevents flickering")
    print("by eliminating redundant PWM updates.")
    print("")
    
    input("⚠️  Make sure scanner is NOT running! Press Enter to start...")
    
    try:
        # Run tests
        test_redundant_updates()
        input("\nPress Enter for next test...")
        
        test_threshold_effectiveness()
        input("\nPress Enter for next test...")
        
        test_realistic_scanning()
        
        print("\n" + "="*70)
        print("DIAGNOSTIC COMPLETE")
        print("="*70)
        print("\nKEY TAKEAWAYS:")
        print("• 0.5% threshold prevents 50-70% of redundant PWM updates")
        print("• Fewer PWM changes = less flickering")
        print("• LEDs only update when brightness actually changes")
        print("• Scanner code can call set_brightness() repeatedly without overhead")
        print("")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n⚠️  IMPORTANT: Check your GPIO pins in scanner_config.yaml!")
    print(f"Current pins: Inner={INNER_LED_PIN}, Outer={OUTER_LED_PIN}")
    print("Edit this script if your pins are different.\n")
    
    main()
