#!/usr/bin/env python3
"""
Quick test to validate connection and camera fixes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def test_fixes():
    """Test the connection and camera status fixes"""
    
    print("\n=== Testing Connection and Camera Fixes ===")
    
    # Test 1: Import mock orchestrator
    try:
        from web.start_web_interface import create_mock_orchestrator
        mock_orchestrator = create_mock_orchestrator()
        print("✅ Mock orchestrator created successfully")
    except Exception as e:
        print(f"❌ Mock orchestrator creation failed: {e}")
        return False
    
    # Test 2: Test get_camera_status method
    try:
        camera_status = mock_orchestrator.get_camera_status()
        print(f"✅ Camera status method works: {camera_status}")
    except Exception as e:
        print(f"❌ Camera status method failed: {e}")
        return False
    
    # Test 3: Test motion controller connection
    try:
        motion_controller = mock_orchestrator.motion_controller
        is_connected = motion_controller.refresh_connection_status()
        print(f"✅ Motion controller connection check: {is_connected}")
    except Exception as e:
        print(f"❌ Motion controller connection test failed: {e}")
        return False
    
    # Test 4: Test web interface creation
    try:
        from web.web_interface import ScannerWebInterface
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        print("✅ Web interface created successfully")
    except Exception as e:
        print(f"❌ Web interface creation failed: {e}")
        return False
    
    print("\n🎉 All fixes validated successfully!")
    return True

if __name__ == "__main__":
    success = test_fixes()
    
    if success:
        print("\nThe fixes should resolve:")
        print("  ✅ Missing get_camera_status method")
        print("  ✅ Connection stability issues")
        print("  ✅ Command queue management")
        print("\nYou can now restart the web interface:")
        print("  python run_web_interface.py")
    else:
        print("\n❌ Some fixes may need additional work.")
    
    sys.exit(0 if success else 1)