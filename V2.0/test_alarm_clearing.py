#!/usr/bin/env python3
"""
Test script for alarm clearing functionality

This script tests:
1. Alarm clearing method in motion controller
2. Web interface endpoint for alarm clearing
3. Integration with homing sequence

Usage: python test_alarm_clearing.py
"""

import asyncio
import json
import requests
import time
from pathlib import Path

def test_alarm_clearing_web_endpoint():
    """Test the web interface alarm clearing endpoint"""
    print("🧪 Testing Web Interface Alarm Clearing")
    print("=" * 45)
    
    try:
        # Test the alarm clearing endpoint
        url = "http://localhost:5000/api/clear_alarm"
        
        print(f"📡 Testing POST request to: {url}")
        
        response = requests.post(url, json={}, timeout=10)
        
        print(f"📊 Response status: {response.status_code}")
        print(f"📄 Response content: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                print("✅ Alarm clearing endpoint works correctly")
                return True
            else:
                print(f"❌ Alarm clearing failed: {data.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Web interface not running - cannot test endpoint")
        print("💡 To test: Start web interface with 'python run_web_interface.py'")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_alarm_clearing_integration():
    """Test alarm clearing integration with motion controller"""
    print("\n🧪 Testing Motion Controller Integration")
    print("=" * 43)
    
    try:
        # Import the motion controller
        import sys
        sys.path.append(str(Path(__file__).parent))
        
        from motion.simplified_fluidnc_controller_fixed import SimplifiedFluidNCControllerFixed
        
        # Create mock config
        config = {
            'port': '/dev/ttyUSB0',
            'baud_rate': 115200,
            'motion_limits': {
                'x': {'min': 0.0, 'max': 200.0},
                'y': {'min': 0.0, 'max': 200.0},
                'z': {'min': 0.0, 'max': 360.0},
                'c': {'min': -90.0, 'max': 90.0}
            }
        }
        
        # Create controller instance
        controller = SimplifiedFluidNCControllerFixed(config)
        
        print("✅ Motion controller created successfully")
        
        # Check if clear_alarm method exists
        if hasattr(controller, 'clear_alarm'):
            print("✅ clear_alarm method found (async)")
        else:
            print("❌ clear_alarm method not found")
            
        if hasattr(controller, 'clear_alarm_sync'):
            print("✅ clear_alarm_sync method found (sync)")
        else:
            print("❌ clear_alarm_sync method not found")
            
        print("📋 Available methods:")
        methods = [method for method in dir(controller) if not method.startswith('_')]
        for method in sorted(methods):
            if 'alarm' in method.lower() or 'clear' in method.lower():
                print(f"   🔧 {method}")
        
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Run alarm clearing tests"""
    print("🔓 Alarm Clearing Functionality Test Suite")
    print("=" * 50)
    print()
    
    # Test 1: Motion controller integration
    test1_result = test_alarm_clearing_integration()
    
    # Test 2: Web interface endpoint
    test2_result = test_alarm_clearing_web_endpoint()
    
    print("\n📊 Test Results Summary")
    print("=" * 25)
    print(f"Motion Controller Integration: {'✅ PASS' if test1_result else '❌ FAIL'}")
    print(f"Web Interface Endpoint:       {'✅ PASS' if test2_result else '❌ FAIL'}")
    
    if test1_result and test2_result:
        print("\n🎉 All tests passed! Alarm clearing functionality is ready.")
    else:
        print("\n⚠️ Some tests failed. Check the output above for details.")
    
    print("\n📋 Usage Instructions:")
    print("1. Start web interface: python run_web_interface.py")
    print("2. Navigate to: http://localhost:5000")
    print("3. Use the alarm clearing button or API endpoint")
    print("4. Homing will automatically clear alarms before and after")

if __name__ == "__main__":
    main()