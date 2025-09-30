#!/usr/bin/env python3
"""
Test script to identify missing abstract methods in GPIOLEDController
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from lighting.gpio_led_controller import GPIOLEDController
    print("✅ GPIOLEDController can be imported")
    
    # Try to instantiate (this will fail if abstract methods are missing)
    try:
        config = {
            'zones': {
                'inner': {'gpio_pins': [13], 'led_type': 'WHITE_LED', 'max_current_ma': 1000},
                'outer': {'gpio_pins': [18], 'led_type': 'WHITE_LED', 'max_current_ma': 1000}
            },
            'gpio_library': 'gpiozero',  # Fixed: use gpio_library instead of controller_type
            'pwm_frequency': 300
        }
        controller = GPIOLEDController(config)
        print("✅ GPIOLEDController can be instantiated - all abstract methods implemented!")
        
        # Quick test of a method
        print(f"🔍 Controller status: {controller.status}")
        print(f"🔍 Is available: {controller.is_available()}")
        
    except TypeError as e:
        print(f"❌ Cannot instantiate GPIOLEDController: {e}")
        
        # Parse the error to see which methods are missing
        error_str = str(e)
        if "abstract method" in error_str:
            # Extract method name from error message
            import re
            methods = re.findall(r"abstract method[s]? ([^']*)", error_str)
            print(f"🔍 Missing abstract method(s): {methods}")
        
except ImportError as e:
    print(f"❌ Cannot import GPIOLEDController: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()