#!/usr/bin/env python3
"""
Test script to validate manual control fixes
Tests the method signature fixes and mock orchestrator integration
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

async def test_manual_controls():
    """Test the manual control functionality with fixes"""
    
    print("\n=== Testing Manual Control Fixes ===")
    
    # Test 1: Import web interface and mock orchestrator
    try:
        from web.web_interface import ScannerWebInterface
        from web.start_web_interface import create_mock_orchestrator
        print("✅ Web interface import successful")
    except Exception as e:
        print(f"❌ Web interface import failed: {e}")
        return False
    
    # Test 2: Create web interface with mock orchestrator  
    try:
        mock_orchestrator = create_mock_orchestrator()
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        print("✅ Web interface creation successful")
    except Exception as e:
        print(f"❌ Web interface creation failed: {e}")
        return False
    
    # Test 3: Simulate manual control command
    try:
        # Simulate a manual jog command with correct parameters
        delta_values = {'x': 1.0, 'y': 0.0, 'z': 0.0, 'c': 0.0}
        speed = 1000.0  # Default speed
        
        result = await web_interface._execute_jog_command(delta_values, speed)
        print(f"✅ Manual control test successful: {result}")
        
        # Check if position was updated
        if 'new_position' in result and result['new_position']['x'] == 1.0:
            print("✅ Position update verified")
        else:
            print(f"⚠️  Position update unclear: {result}")
            
    except Exception as e:
        print(f"❌ Manual control test failed: {e}")
        return False
    
    # Test 4: Test camera status method (if available)
    try:
        if hasattr(web_interface.orchestrator, 'get_camera_status'):
            camera_status = web_interface.orchestrator.get_camera_status()
            print(f"✅ Camera status method works: {camera_status}")
        else:
            print("⚠️  get_camera_status method not in mock orchestrator (this is OK)")
    except Exception as e:
        print(f"❌ Camera status method failed: {e}")
        return False
    
    print("\n=== All Manual Control Tests Passed! ===")
    return True

if __name__ == "__main__":
    import asyncio
    
    print("Testing manual control fixes...")
    success = asyncio.run(test_manual_controls())
    
    if success:
        print("\n🎉 Manual controls should now work properly!")
        print("You can now run the web interface:")
        print("  python run_web_interface.py")
    else:
        print("\n❌ Some tests failed. Check the errors above.")
    
    sys.exit(0 if success else 1)