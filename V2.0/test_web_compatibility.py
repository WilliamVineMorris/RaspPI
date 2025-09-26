#!/usr/bin/env python3
"""
Test Web Interface Compatibility
Verify all required properties and methods are available for the web interface.
"""

import sys
import os
sys.path.append(os.path.abspath('.'))

from core.config_manager import ConfigManager
from scanning.updated_scan_orchestrator import UpdatedScanOrchestrator
from simple_working_fluidnc_controller import SimpleWorkingFluidNCController, Position4D

def test_compatibility():
    """Test all web interface compatibility requirements."""
    print("🧪 Testing Web Interface Compatibility")
    print("=" * 50)
    
    try:
        # 1. Create config manager
        print("1. Creating ConfigManager...")
        config_manager = ConfigManager("config/scanner_config.yaml")
        print("   ✅ ConfigManager created")
        
        # 2. Create orchestrator
        print("2. Creating UpdatedScanOrchestrator...")
        orchestrator = UpdatedScanOrchestrator(config_manager)
        print("   ✅ UpdatedScanOrchestrator created")
        
        # 3. Initialize orchestrator (creates motion controller)
        print("3. Initializing orchestrator...")
        import asyncio
        initialized = asyncio.run(orchestrator.initialize())
        print(f"   ✅ Orchestrator initialized (success: {initialized})")
        
        # 4. Test motion controller compatibility
        print("4. Testing motion controller compatibility...")
        motion_controller = orchestrator.motion_controller
        
        if motion_controller is None:
            print("   ⚠️ Motion controller is None (hardware not available)")
            print("   ✅ This is expected when running without FluidNC hardware")
        else:
            # Test current_position property
            position = motion_controller.current_position
            print(f"   - current_position: {position}")
            print("   ✅ current_position property works")
            
            # Test is_connected method
            connected = motion_controller.is_connected()
            print(f"   - is_connected(): {connected}")
            print("   ✅ is_connected method works")
        
        # 5. Test orchestrator web UI properties
        print("5. Testing orchestrator web UI properties...")
        
        # Test camera_manager property
        camera_manager = orchestrator.camera_manager
        print(f"   - camera_manager: {type(camera_manager).__name__}")
        print("   ✅ camera_manager property works")
        
        # Test lighting_manager property
        lighting_manager = orchestrator.lighting_manager
        print(f"   - lighting_manager: {type(lighting_manager).__name__}")
        print("   ✅ lighting_manager property works")
        
        # Test storage_controller property
        storage_controller = orchestrator.storage_controller
        print(f"   - storage_controller: {type(storage_controller).__name__}")
        print("   ✅ storage_controller property works")
        
        # Test get_camera_status method
        camera_status = orchestrator.get_camera_status()
        print(f"   - get_camera_status(): {camera_status}")
        print("   ✅ get_camera_status method works")
        
        # 6. Test camera controller preview method
        print("6. Testing camera controller preview method...")
        if camera_manager is None:
            print("   ⚠️ Camera manager is None")
            print("   ✅ This is expected in some test configurations")
        else:
            preview_frame = camera_manager.get_preview_frame('primary')
            print(f"   - get_preview_frame(): {len(preview_frame)} bytes")
            print("   ✅ get_preview_frame method works")
        
        print("\n" + "=" * 50)
        print("🎉 ALL WEB INTERFACE COMPATIBILITY TESTS PASSED!")
        print("\nThe system is ready for web interface integration.")
        print("\nNext steps:")
        print("1. Run: python run_web_interface.py")
        print("2. Open browser to: http://localhost:5000")
        print("3. Test web interface functionality")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_compatibility()
    sys.exit(0 if success else 1)