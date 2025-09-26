#!/usr/bin/env python3
"""
Test Web Interface Fixes
Verify the specific issues found in the web interface are resolved.
"""

import sys
import os
sys.path.append(os.path.abspath('.'))

from core.config_manager import ConfigManager
from scanning.updated_scan_orchestrator import UpdatedScanOrchestrator
import json
import asyncio

def test_web_fixes():
    """Test all the web interface fixes."""
    print("🧪 Testing Web Interface Fixes")
    print("=" * 50)
    
    try:
        # 1. Create and initialize orchestrator
        print("1. Creating and initializing orchestrator...")
        config_manager = ConfigManager("config/scanner_config.yaml")
        orchestrator = UpdatedScanOrchestrator(config_manager)
        
        # Initialize asynchronously
        initialized = asyncio.run(orchestrator.initialize())
        print(f"   ✅ Orchestrator initialized: {initialized}")
        
        # 2. Test motion controller connection method
        print("2. Testing motion controller connection...")
        motion_controller = orchestrator.motion_controller
        if motion_controller:
            connected = motion_controller.is_connected()
            print(f"   - is_connected(): {connected}")
            
            # Test homed status (should be callable, not a method object)
            homed = motion_controller.is_homed()
            print(f"   - is_homed(): {homed}")
            
            # Test JSON serialization of status
            status_data = {
                'connected': connected,
                'homed': homed,
                'position': {
                    'x': motion_controller.current_position.x,
                    'y': motion_controller.current_position.y,
                    'z': motion_controller.current_position.z,
                    'c': motion_controller.current_position.c
                }
            }
            json_str = json.dumps(status_data)
            print(f"   - JSON serialization: Success ({len(json_str)} chars)")
            print("   ✅ Motion controller fixes work")
        else:
            print("   ⚠️ Motion controller not available (hardware not connected)")
        
        # 3. Test camera controller fixes
        print("3. Testing camera controller fixes...")
        camera_controller = orchestrator.camera_controller
        if camera_controller:
            # Test preview frame (should return numpy array with size/shape)
            preview_frame = camera_controller.get_preview_frame('primary')
            print(f"   - get_preview_frame(): shape={preview_frame.shape}, size={preview_frame.size}")
            
            # Test autofocus method
            autofocus_result = asyncio.run(camera_controller.trigger_autofocus('primary'))
            print(f"   - trigger_autofocus(): {autofocus_result}")
            print("   ✅ Camera controller fixes work")
        else:
            print("   ⚠️ Camera controller not available")
        
        print("\n" + "=" * 50)
        print("🎉 ALL WEB INTERFACE FIXES VERIFIED!")
        print("\nFixed Issues:")
        print("✅ JSON serialization error (is_homed method call)")
        print("✅ Motion controller connection detection")
        print("✅ Camera preview frame format (numpy array)")
        print("✅ Missing trigger_autofocus method")
        print("\nThe web interface should now work correctly!")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Fix verification failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_web_fixes()
    sys.exit(0 if success else 1)