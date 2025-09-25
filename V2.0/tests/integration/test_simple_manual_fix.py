#!/usr/bin/env python3
"""
Simple test to validate manual control fixes
Tests just the core import and basic functionality
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_imports():
    """Test that we can import the required modules"""
    print("\n=== Testing Imports ===")
    
    try:
        from web.web_interface import ScannerWebInterface
        print("✅ ScannerWebInterface import successful")
    except Exception as e:
        print(f"❌ ScannerWebInterface import failed: {e}")
        return False
    
    try:
        from web.start_web_interface import create_mock_orchestrator
        print("✅ create_mock_orchestrator import successful")
    except Exception as e:
        print(f"❌ create_mock_orchestrator import failed: {e}")
        return False
    
    return True

def test_mock_orchestrator():
    """Test that we can create a mock orchestrator"""
    print("\n=== Testing Mock Orchestrator ===")
    
    try:
        from web.start_web_interface import create_mock_orchestrator
        mock_orchestrator = create_mock_orchestrator()
        print("✅ Mock orchestrator creation successful")
        
        # Test motion controller exists
        if hasattr(mock_orchestrator, 'motion_controller'):
            print("✅ Motion controller exists in mock orchestrator")
        else:
            print("❌ Motion controller missing from mock orchestrator")
            return False
        
        return True
    except Exception as e:
        print(f"❌ Mock orchestrator test failed: {e}")
        return False

def test_web_interface_creation():
    """Test that we can create the web interface"""
    print("\n=== Testing Web Interface Creation ===")
    
    try:
        from web.web_interface import ScannerWebInterface
        from web.start_web_interface import create_mock_orchestrator
        
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        print("✅ Web interface creation successful")
        
        return True
    except Exception as e:
        print(f"❌ Web interface creation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing manual control fixes...")
    
    success = True
    success &= test_imports()
    success &= test_mock_orchestrator()
    success &= test_web_interface_creation()
    
    if success:
        print("\n🎉 All basic tests passed!")
        print("The manual control fixes should work properly.")
        print("\nYou can now test the web interface:")
        print("  python run_web_interface.py")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())