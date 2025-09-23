#!/usr/bin/env python3
"""
Test script to verify all async warning fixes
"""

import sys
import os
import warnings
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_no_async_warnings():
    """Test that we can create web interface without async warnings"""
    print("🧪 Testing Async Warning Fixes")
    print("=" * 50)
    
    # Capture warnings
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        
        try:
            # Test 1: Import and create orchestrator
            print("\n1. Creating real orchestrator setup...")
            from start_web_interface import initialize_real_orchestrator
            
            # This will use mock if hardware fails
            orchestrator = initialize_real_orchestrator()
            print(f"   ✅ Orchestrator created: {type(orchestrator).__name__}")
            
            # Test 2: Create web interface
            print("\n2. Creating web interface...")
            from web_interface import ScannerWebInterface
            
            interface = ScannerWebInterface(orchestrator=orchestrator)
            print("   ✅ Web interface created")
            
            # Test 3: Get system status (this was causing the warnings)
            print("\n3. Testing system status (potential async warning source)...")
            status = interface._get_system_status()
            print(f"   ✅ System status retrieved")
            print(f"   Motion: {status['motion']['status']}")
            print(f"   Cameras: {status['cameras']['status']}")
            print(f"   Lighting: {status['lighting']['status']}")
            
            # Test 4: Check for async warnings
            runtime_warnings = [warning for warning in w if issubclass(warning.category, RuntimeWarning) and 'coroutine' in str(warning.message)]
            
            if runtime_warnings:
                print(f"\n❌ Found {len(runtime_warnings)} async warnings:")
                for warning in runtime_warnings:
                    print(f"   - {warning.message}")
                    print(f"     File: {warning.filename}:{warning.lineno}")
                return False
            else:
                print("\n✅ No async warnings detected!")
                
            return True
            
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False

def test_lighting_controller_methods():
    """Test lighting controller adapter methods"""
    print("\n" + "=" * 50)
    print("🔧 Testing Lighting Controller Adapter")
    print("=" * 50)
    
    try:
        from scanning.scan_orchestrator import LightingControllerAdapter
        from lighting.gpio_led_controller import GPIOLEDController
        
        # Create mock GPIO controller
        class MockGPIOController:
            def is_available(self):
                return True
            
            async def get_status(self, zone_id=None):
                return {'zones': {}, 'initialized': True}
        
        # Test adapter
        mock_controller = MockGPIOController()
        adapter = LightingControllerAdapter(mock_controller)
        
        # Test sync status method
        if hasattr(adapter, 'get_sync_status'):
            status = adapter.get_sync_status()
            print(f"   ✅ Sync status method works: {status}")
        else:
            print("   ❌ Sync status method not found")
            return False
            
        return True
        
    except Exception as e:
        print(f"   ❌ Lighting adapter test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("================================================================================")
    print("🔬 Async Warning Fix Verification")
    print("================================================================================")
    
    test1_result = test_no_async_warnings()
    test2_result = test_lighting_controller_methods()
    
    print("\n" + "=" * 50)
    print("📊 Test Results")
    print("=" * 50)
    
    if test1_result:
        print("✅ PASS: No async warnings in web interface")
    else:
        print("❌ FAIL: Async warnings still present")
    
    if test2_result:
        print("✅ PASS: Lighting controller adapter working")
    else:
        print("❌ FAIL: Lighting controller adapter issues")
    
    if test1_result and test2_result:
        print("\n🎉 All async warning fixes are working correctly!")
        print("Hardware mode should start without RuntimeWarnings.")
        return 0
    else:
        print("\n⚠️  Some issues remain. Check the failed tests above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())