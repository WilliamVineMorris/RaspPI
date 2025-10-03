#!/usr/bin/env python3
"""
LED Hardware Debugging Tool
Tests LED hardware configuration and PWM signal polarity
"""

import time
import sys

def check_pwm_status():
    """Check current PWM status"""
    print("\n" + "="*60)
    print("HARDWARE PWM STATUS")
    print("="*60)
    
    try:
        with open('/sys/kernel/debug/pwm', 'r') as f:
            content = f.read()
            print(content)
    except PermissionError:
        print("❌ Permission denied - run with sudo:")
        print("   sudo python debug_led_hardware.py")
        return False
    return True

def read_pwm_channel_info(chip, channel):
    """Read PWM channel configuration"""
    base_path = f'/sys/class/pwm/pwmchip{chip}/pwm{channel}'
    
    info = {}
    try:
        with open(f'{base_path}/period', 'r') as f:
            info['period'] = int(f.read().strip())
        with open(f'{base_path}/duty_cycle', 'r') as f:
            info['duty_cycle'] = int(f.read().strip())
        with open(f'{base_path}/polarity', 'r') as f:
            info['polarity'] = f.read().strip()
        with open(f'{base_path}/enable', 'r') as f:
            info['enabled'] = int(f.read().strip())
    except FileNotFoundError:
        return None
    
    return info

def test_pwm_polarity():
    """Test PWM with normal and inverted polarity"""
    print("\n" + "="*60)
    print("PWM POLARITY TEST")
    print("="*60)
    print("\nThis will test both NORMAL and INVERTED polarity")
    print("Watch your LEDs to see which polarity makes them light up!")
    print()
    
    chip = 0
    channels = [0, 1]  # GPIO 18 (channel 0) and GPIO 13 (channel 1)
    gpio_map = {0: 18, 1: 13}
    
    for channel in channels:
        gpio = gpio_map[channel]
        print(f"\n{'─'*60}")
        print(f"Testing GPIO {gpio} (Chip {chip}, Channel {channel})")
        print(f"{'─'*60}")
        
        # Check if channel is exported
        info = read_pwm_channel_info(chip, channel)
        if info is None:
            print(f"⚠️  Channel {channel} not exported - skipping")
            continue
        
        print(f"\nCurrent state:")
        print(f"  Period: {info['period']} ns ({1000000000/info['period']:.0f} Hz)")
        print(f"  Duty: {info['duty_cycle']} ns ({info['duty_cycle']/info['period']*100:.1f}%)")
        print(f"  Polarity: {info['polarity']}")
        print(f"  Enabled: {'YES' if info['enabled'] else 'NO'}")
        
        # Test NORMAL polarity at 50%
        print(f"\n🔍 TEST 1: NORMAL polarity at 50% brightness")
        try:
            # Set to normal polarity
            with open(f'/sys/class/pwm/pwmchip{chip}/pwm{channel}/polarity', 'w') as f:
                f.write('normal')
            
            # Set 50% duty cycle
            duty_50_percent = info['period'] // 2
            with open(f'/sys/class/pwm/pwmchip{chip}/pwm{channel}/duty_cycle', 'w') as f:
                f.write(str(duty_50_percent))
            
            # Enable if not already
            with open(f'/sys/class/pwm/pwmchip{chip}/pwm{channel}/enable', 'w') as f:
                f.write('1')
            
            print(f"   Set to: polarity=normal, duty=50%")
            print(f"   ⏱️  Holding for 3 seconds...")
            time.sleep(3)
            
            response = input(f"   Did GPIO {gpio} LED light up? (y/n): ").strip().lower()
            normal_works = response == 'y'
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            normal_works = False
        
        # Test INVERTED polarity at 50%
        print(f"\n🔍 TEST 2: INVERTED polarity at 50% brightness")
        try:
            # Set to inverted polarity
            with open(f'/sys/class/pwm/pwmchip{chip}/pwm{channel}/polarity', 'w') as f:
                f.write('inversed')
            
            print(f"   Set to: polarity=inversed, duty=50%")
            print(f"   ⏱️  Holding for 3 seconds...")
            time.sleep(3)
            
            response = input(f"   Did GPIO {gpio} LED light up? (y/n): ").strip().lower()
            inverted_works = response == 'y'
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            inverted_works = False
        
        # Report results
        print(f"\n📊 RESULTS for GPIO {gpio}:")
        if normal_works and not inverted_works:
            print(f"   ✅ Use NORMAL polarity")
        elif inverted_works and not normal_works:
            print(f"   ✅ Use INVERTED polarity")
        elif normal_works and inverted_works:
            print(f"   ⚠️  Both polarities work (check wiring)")
        else:
            print(f"   ❌ Neither polarity works (hardware issue)")
        
        # Reset to normal and turn off
        try:
            with open(f'/sys/class/pwm/pwmchip{chip}/pwm{channel}/polarity', 'w') as f:
                f.write('normal')
            with open(f'/sys/class/pwm/pwmchip{chip}/pwm{channel}/duty_cycle', 'w') as f:
                f.write('0')
        except:
            pass

def test_gpio_states():
    """Test GPIO pin states directly"""
    print("\n" + "="*60)
    print("GPIO PIN STATE TEST")
    print("="*60)
    
    try:
        import lgpio
        
        # Open GPIO chip
        h = lgpio.gpiochip_open(0)
        
        gpio_pins = [13, 18]
        
        for pin in gpio_pins:
            # Set as output
            lgpio.gpio_claim_output(h, pin)
            
            print(f"\nTesting GPIO {pin}:")
            
            # Test HIGH
            print(f"  Setting HIGH (3.3V)...")
            lgpio.gpio_write(h, pin, 1)
            time.sleep(2)
            response = input(f"  Did GPIO {pin} LED light up? (y/n): ").strip().lower()
            high_works = response == 'y'
            
            # Test LOW
            print(f"  Setting LOW (0V)...")
            lgpio.gpio_write(h, pin, 0)
            time.sleep(2)
            response = input(f"  Did GPIO {pin} LED turn off (or light up)? (off/on): ").strip().lower()
            low_state = response
            
            print(f"\n📊 GPIO {pin} Results:")
            if high_works and low_state == 'off':
                print(f"   ✅ Normal operation: HIGH=ON, LOW=OFF")
            elif not high_works and low_state == 'on':
                print(f"   ✅ Inverted operation: LOW=ON, HIGH=OFF")
            else:
                print(f"   ❌ Unexpected behavior - check wiring")
            
            # Turn off
            lgpio.gpio_write(h, pin, 0)
        
        lgpio.gpiochip_close(h)
        
    except ImportError:
        print("❌ lgpio not available - skipping GPIO test")
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    print("\n" + "="*60)
    print("LED HARDWARE DEBUGGING TOOL")
    print("="*60)
    print("\nThis tool will test:")
    print("  1. Current PWM status")
    print("  2. PWM polarity (normal vs inverted)")
    print("  3. Direct GPIO control")
    print("\n⚠️  Make sure LEDs are connected to GPIO 13 and 18!")
    print()
    
    input("Press ENTER to start...")
    
    # Check PWM status
    if not check_pwm_status():
        return
    
    # Test PWM polarity
    try:
        test_pwm_polarity()
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    
    # Test GPIO states
    print()
    response = input("Run direct GPIO test? (y/n): ").strip().lower()
    if response == 'y':
        try:
            test_gpio_states()
        except KeyboardInterrupt:
            print("\n\n⚠️  Test interrupted by user")
    
    print("\n" + "="*60)
    print("TESTING COMPLETE")
    print("="*60)
    print("\nBased on the results, update scanner_config.yaml if needed:")
    print("  - If LEDs need INVERTED polarity, we'll update the code")
    print("  - If LEDs light with GPIO LOW, wiring may be inverted")
    print()

if __name__ == '__main__':
    main()
