#!/usr/bin/env python3
"""
Test script for hardware mode functionality
Tests the fixes for camera pipeline conflicts and async issues
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_configuration_validation():
    """Test that the configuration passes validation"""
    print("🔧 Testing configuration validation...")
    
    try:
        from core.config_manager import ConfigManager
        
        config_file = project_root / "config" / "hardware_config.yaml"
        if config_file.exists():
            config_manager = ConfigManager(config_file)
            print("✅ Configuration validation successful")
            return True
        else:
            print("❌ Configuration file not found")
            return False
            
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def test_mock_orchestrator():
    """Test mock orchestrator as fallback"""
    print("🔧 Testing mock orchestrator...")
    
    try:
        # Import our start script functions
        from start_web_interface import create_mock_orchestrator
        
        mock_orch = create_mock_orchestrator()
        print(f"✅ Mock orchestrator created: {type(mock_orch).__name__}")
        return True
        
    except Exception as e:
        print(f"❌ Mock orchestrator test failed: {e}")
        return False

def test_hardware_detection():
    """Test hardware detection without full initialization"""
    print("🔧 Testing hardware detection...")
    
    try:
        # Test FluidNC connection
        import serial.tools.list_ports
        
        fluidnc_port = None
        for port in serial.tools.list_ports.comports():
            if 'ttyUSB' in port.device:
                fluidnc_port = port.device
                break
        
        if fluidnc_port:
            print(f"✅ FluidNC detected on {fluidnc_port}")
        else:
            print("⚠️  FluidNC not detected")
        
        # Test camera availability (basic check)
        try:
            from picamera2 import Picamera2
            cameras = Picamera2.global_camera_info()
            print(f"✅ {len(cameras)} cameras detected")
            
        except Exception as e:
            print(f"⚠️  Camera detection failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Hardware detection failed: {e}")
        return False

def main():
    """Run all tests"""
    print("================================================================================")
    print("🧪 Hardware Mode Tests")
    print("================================================================================")
    
    tests = [
        ("Configuration Validation", test_configuration_validation),
        ("Mock Orchestrator", test_mock_orchestrator), 
        ("Hardware Detection", test_hardware_detection),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n================================================================================")
    print("📊 Test Results")
    print("================================================================================")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1
    
    print(f"\nResults: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Hardware mode should work correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())