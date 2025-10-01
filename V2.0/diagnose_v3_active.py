#!/usr/bin/env python3
"""
LED Flickering Diagnostic - Check if V3 changes are active

This script tests if:
1. Thread lock is initialized
2. 1% threshold is active
3. Brightness changes are being blocked properly
"""

import sys
sys.path.insert(0, '/home/pi/RaspPI/V2.0')

from lighting.gpio_led_controller import GPIOLEDController
import yaml

def test_v3_features():
    """Test if V3 anti-flickering features are active"""
    print("="*70)
    print("LED FLICKERING V3 DIAGNOSTIC")
    print("="*70)
    
    # Load config
    print("\n1. Loading configuration...")
    with open('/home/pi/RaspPI/V2.0/config/scanner_config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    lighting_config = config['lighting']
    print(f"   Controller type: {lighting_config.get('controller_type')}")
    print(f"   PWM frequency: {lighting_config.get('pwm_frequency')}Hz")
    
    # Initialize controller
    print("\n2. Initializing LED controller...")
    controller = GPIOLEDController(lighting_config)
    
    # Check for V3 features
    print("\n3. Checking V3 features:")
    
    # Check for thread lock
    has_lock = hasattr(controller, '_led_update_lock')
    print(f"   ✓ Thread lock present: {has_lock}")
    if has_lock:
        print(f"     Lock type: {type(controller._led_update_lock)}")
    else:
        print("   ❌ ERROR: Thread lock missing! V3 not active!")
    
    # Check zones
    print(f"\n4. Available zones: {list(controller.zone_configs.keys())}")
    
    # Test threshold by setting same brightness multiple times
    print("\n5. Testing 1% threshold:")
    if controller.zone_configs:
        zone_id = list(controller.zone_configs.keys())[0]
        print(f"   Testing zone: {zone_id}")
        
        # These should trigger update (>1% change)
        print("\n   Setting brightness to 30% (should update)...")
        result1 = controller._set_brightness_direct(zone_id, 0.30)
        print(f"   Result: {result1}")
        
        # These should be blocked (<1% change)
        print("\n   Setting brightness to 30.5% (0.5% change, should SKIP)...")
        result2 = controller._set_brightness_direct(zone_id, 0.305)
        print(f"   Result: {result2}")
        
        print("\n   Setting brightness to 30% again (0% change, should SKIP)...")
        result3 = controller._set_brightness_direct(zone_id, 0.30)
        print(f"   Result: {result3}")
        
        print("\n   Setting brightness to 32% (2% change, should UPDATE)...")
        result4 = controller._set_brightness_direct(zone_id, 0.32)
        print(f"   Result: {result4}")
        
        print("\n   Setting brightness to 0% (should UPDATE)...")
        result5 = controller._set_brightness_direct(zone_id, 0.0)
        print(f"   Result: {result5}")
        
        # Check current state
        state = controller.zone_states[zone_id]
        print(f"\n   Final zone state:")
        print(f"     Brightness: {state['brightness']*100:.1f}%")
        print(f"     Duty cycle: {state['duty_cycle']:.1f}%")
    
    print("\n6. Cleanup...")
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(controller.shutdown())
    
    print("\n" + "="*70)
    print("DIAGNOSTIC COMPLETE")
    print("="*70)
    
    if has_lock:
        print("\n✅ V3 features are ACTIVE")
        print("   - Thread lock: Present")
        print("   - 1% threshold: Should be active")
        print("\nIf still flickering, try:")
        print("  1. Restart the scanner service")
        print("  2. Check PWM frequency (try 1000Hz)")
        print("  3. Check power supply stability")
    else:
        print("\n❌ V3 features NOT ACTIVE")
        print("   - Thread lock: MISSING")
        print("\nAction required:")
        print("  1. Restart Python/scanner to reload code")
        print("  2. Check git pull/sync completed")

if __name__ == "__main__":
    try:
        test_v3_features()
    except Exception as e:
        print(f"\n❌ Error during diagnostic: {e}")
        import traceback
        traceback.print_exc()
