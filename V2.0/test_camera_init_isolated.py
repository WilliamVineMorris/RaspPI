#!/usr/bin/env python3
"""
Test Camera Initialization in Isolation
Test the exact initialization path that the web interface uses
"""

import sys
import asyncio
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_camera_initialization():
    """Test the exact camera initialization path used by the web interface"""
    
    print("🔍 Testing Camera Initialization Path")
    print("=" * 50)
    
    try:
        # Step 1: Initialize config manager
        print("1️⃣ Initializing ConfigManager...")
        from core.config_manager import ConfigManager
        config_manager = ConfigManager("config/scanner_config.yaml")
        print("   ✅ ConfigManager created")
        
        # Check simulation mode
        simulation_mode = config_manager.get('system.simulation_mode', False)
        print(f"   📊 Simulation mode: {simulation_mode}")
        
        if simulation_mode:
            print("   ⚠️  Simulation mode is ON - cameras will be mocked")
            return True
        
        # Step 2: Create ScanOrchestrator (this creates camera manager)
        print("2️⃣ Creating ScanOrchestrator...")
        from scanning.scan_orchestrator import ScanOrchestrator
        orchestrator = ScanOrchestrator(config_manager)
        
        camera_manager_type = type(orchestrator.camera_manager).__name__
        print(f"   📊 Camera manager type: {camera_manager_type}")
        
        if camera_manager_type == "MockCameraManager":
            print("   ⚠️  Using MockCameraManager - real cameras not initialized")
            return False
        
        print("   ✅ Real camera manager created")
        
        # Step 3: Initialize camera manager directly
        print("3️⃣ Initializing camera manager...")
        
        try:
            result = await orchestrator.camera_manager.initialize()
            print(f"   📊 Camera manager initialization result: {result}")
            
            if result:
                print("   ✅ Camera manager initialized successfully")
                
                # Check camera status
                status = orchestrator.camera_manager.get_status()
                print(f"   📊 Camera status: {status}")
                
                return True
            else:
                print("   ❌ Camera manager initialization returned False")
                return False
                
        except Exception as e:
            print(f"   ❌ Camera manager initialization failed: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_direct_picamera2():
    """Test picamera2 directly"""
    
    print("\n🔍 Testing Picamera2 Directly")
    print("=" * 40)
    
    try:
        from picamera2 import Picamera2
        print("   ✅ Picamera2 imported")
        
        # Check available cameras
        camera_info = Picamera2.global_camera_info()
        print(f"   📊 Available cameras: {len(camera_info)}")
        
        for i, info in enumerate(camera_info):
            print(f"      Camera {i}: {info}")
        
        if len(camera_info) == 0:
            print("   ❌ No cameras detected by Picamera2")
            return False
        
        # Try to create a camera instance
        print("   • Creating Picamera2 instance...")
        picam2 = Picamera2(0)  # Camera 0
        print("   ✅ Picamera2 instance created")
        
        # Try to configure it
        print("   • Configuring camera...")
        config = picam2.create_preview_configuration()
        picam2.configure(config)
        print("   ✅ Camera configured")
        
        # Try to start it
        print("   • Starting camera...")
        picam2.start()
        print("   ✅ Camera started")
        
        # Stop it
        picam2.stop()
        print("   ✅ Camera stopped")
        
        return True
        
    except ImportError as e:
        print(f"   ❌ Picamera2 import failed: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Picamera2 test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run camera initialization tests"""
    
    print("🚨 CAMERA INITIALIZATION DEBUG")
    print("Finding what changed since yesterday")
    print("=" * 60)
    
    # Test direct picamera2 first
    direct_ok = await test_direct_picamera2()
    
    # Test our camera initialization path
    init_ok = await test_camera_initialization()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print(f"   Direct Picamera2: {'✅ PASS' if direct_ok else '❌ FAIL'}")
    print(f"   Camera Init Path: {'✅ PASS' if init_ok else '❌ FAIL'}")
    
    if direct_ok and init_ok:
        print("\n✅ Cameras should work!")
        print("💡 If web interface still has issues, check:")
        print("   • Web interface startup logs")
        print("   • Camera permission changes")
        print("   • System reboot needed")
    elif direct_ok and not init_ok:
        print("\n🔧 Hardware OK, Software Issue:")
        print("   • Camera initialization code has a bug")
        print("   • Configuration issue")
        print("   • Import path problem")
    elif not direct_ok:
        print("\n🔧 Hardware/Driver Issue:")
        print("   • Picamera2 can't access cameras")
        print("   • Camera hardware problem")
        print("   • Permission or driver issue")
    else:
        print("\n❌ Multiple issues detected")
    
    print("\n🔧 Immediate Actions:")
    print("   1. Run this script on Pi: python test_camera_init_isolated.py")
    print("   2. Check system logs: journalctl -u camera")
    print("   3. Test hardware: libcamera-hello --list-cameras")

if __name__ == "__main__":
    asyncio.run(main())