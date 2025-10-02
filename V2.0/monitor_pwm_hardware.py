#!/usr/bin/env python3
"""
Monitor actual PWM hardware state during LED operation

This checks if hardware PWM is actually being used correctly and
monitors for any unwanted state changes.
"""

import time
import subprocess
import sys

def check_pwm_state(pin):
    """Check PWM state for a GPIO pin"""
    try:
        # For Pi 5 with lgpio, PWM info is in /sys/class/pwm/
        # GPIO 13 = PWM0 channel 1
        # GPIO 18 = PWM0 channel 2
        
        if pin == 13:
            pwm_chip = "pwmchip0"
            pwm_channel = "pwm1"
        elif pin == 18:
            pwm_chip = "pwmchip2"
            pwm_channel = "pwm0"
        else:
            return None
        
        pwm_path = f"/sys/class/pwm/{pwm_chip}/{pwm_channel}"
        
        # Check if PWM is exported
        enabled_path = f"{pwm_path}/enable"
        period_path = f"{pwm_path}/period"
        duty_cycle_path = f"{pwm_path}/duty_cycle"
        
        try:
            with open(enabled_path, 'r') as f:
                enabled = f.read().strip()
            with open(period_path, 'r') as f:
                period = int(f.read().strip())
            with open(duty_cycle_path, 'r') as f:
                duty_cycle = int(f.read().strip())
            
            frequency = 1_000_000_000 / period  # Convert ns to Hz
            duty_percent = (duty_cycle / period) * 100
            
            return {
                'enabled': enabled == '1',
                'frequency_hz': frequency,
                'period_ns': period,
                'duty_cycle_ns': duty_cycle,
                'duty_percent': duty_percent
            }
        except FileNotFoundError:
            return {'error': 'PWM channel not exported'}
            
    except Exception as e:
        return {'error': str(e)}

def main():
    """Monitor PWM state"""
    print("="*70)
    print("PWM Hardware State Monitor")
    print("="*70)
    print()
    print("Monitoring GPIO 13 (inner LED) and GPIO 18 (outer LED)")
    print("Press Ctrl+C to stop")
    print()
    
    print(f"{'Time':<12} {'Pin':<6} {'Enabled':<10} {'Freq(Hz)':<12} {'Duty%':<10}")
    print("-"*70)
    
    try:
        while True:
            timestamp = time.strftime("%H:%M:%S")
            
            for pin in [13, 18]:
                state = check_pwm_state(pin)
                
                if state and 'error' not in state:
                    enabled = "YES" if state['enabled'] else "NO"
                    freq = f"{state['frequency_hz']:.1f}"
                    duty = f"{state['duty_percent']:.1f}"
                    
                    print(f"{timestamp:<12} GPIO{pin:<3} {enabled:<10} {freq:<12} {duty:<10}")
                elif state:
                    print(f"{timestamp:<12} GPIO{pin:<3} ERROR: {state.get('error', 'Unknown')}")
            
            print()
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")

if __name__ == "__main__":
    if sys.platform != "linux":
        print("❌ This script must run on Linux (Raspberry Pi)")
        sys.exit(1)
    
    main()
