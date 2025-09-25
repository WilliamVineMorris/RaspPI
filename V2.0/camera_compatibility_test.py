#!/usr/bin/env python3
"""
Quick Camera Fix - Update camera config for Arducam 64MP compatibility
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_arducam_compatibility():
    """Test if current config is compatible with Arducam 64MP"""
    
    print("🔍 Arducam 64MP Compatibility Check")
    print("=" * 40)
    
    # Test direct picamera2 with current config resolutions
    try:
        from picamera2 import Picamera2
        
        print("1️⃣ Testing Picamera2 with current config resolutions...")
        
        # Test Camera 0
        print("   • Testing Camera 0...")
        picam2 = Picamera2(0)
        
        # Try current config resolution (3280x2464)
        print("   • Trying config resolution 3280x2464...")
        config = picam2.create_still_configuration(
            main={"size": (3280, 2464), "format": "RGB888"}
        )
        picam2.configure(config)
        print("   ✅ 3280x2464 configuration successful")
        
        # Try preview resolution (1280x720)
        print("   • Trying preview resolution 1280x720...")
        preview_config = picam2.create_preview_configuration(
            main={"size": (1280, 720), "format": "RGB888"}
        )
        picam2.configure(preview_config)
        print("   ✅ 1280x720 configuration successful")
        
        # Test starting camera
        print("   • Testing camera start/stop...")
        picam2.start()
        print("   ✅ Camera started successfully")
        
        picam2.stop()
        print("   ✅ Camera stopped successfully")
        
        return True
        
    except Exception as e:
        print(f"   ❌ Compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_direct_camera_controller():
    """Test our PiCameraController directly"""
    
    print("\n🔍 Direct PiCameraController Test")
    print("=" * 40)
    
    try:
        from camera.pi_camera_controller import PiCameraController
        from core.config_manager import ConfigManager
        
        print("1️⃣ Loading configuration...")
        config_manager = ConfigManager("config/scanner_config.yaml")
        camera_config = config_manager.get('cameras', {})
        print(f"   📊 Camera config: {camera_config}")
        
        print("2️⃣ Creating PiCameraController...")
        controller = PiCameraController(camera_config)
        print("   ✅ Controller created")
        
        print("3️⃣ Testing controller initialization...")
        
        import asyncio
        async def init_test():
            try:
                result = await controller.initialize()
                print(f"   📊 Initialize result: {result}")
                
                if result:
                    print("   ✅ Controller initialized successfully!")
                    
                    # Test getting camera status
                    try:
                        # Use the sync version to avoid async warnings
                        if hasattr(controller, 'get_status_sync'):
                            status = controller.get_status_sync()
                            print(f"   📊 Camera status: {status}")
                        elif hasattr(controller, 'get_status'):
                            # If sync version doesn't exist, note the async warning
                            print("   ⚠️  get_status is async - using with warning")
                            status = controller.get_status()  # This will create warning
                            print(f"   📊 Camera status: {status}")
                    except Exception as e:
                        print(f"   ⚠️  Status check failed: {e}")
                    
                    return True
                else:
                    print("   ❌ Controller initialization returned False")
                    return False
                    
            except Exception as e:
                print(f"   ❌ Controller initialization failed: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        result = asyncio.run(init_test())
        return result
        
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_optimized_camera_config():
    """Create an optimized camera config for Arducam 64MP"""
    
    print("\n🔧 Creating Optimized Camera Config")
    print("=" * 40)
    
    optimized_config = """
# Camera Configuration - Optimized for Arducam 64MP
cameras:
  system_type: "dual_camera"
  
  camera_1:
    port: 0
    name: "Primary Camera"
    resolution:
      capture: [4624, 3472]  # Arducam native high-res mode
      preview: [1280, 720]   # Standard preview
    format: "jpeg"
    quality: 95
    
  camera_2:
    port: 1  
    name: "Secondary Camera"
    resolution:
      capture: [4624, 3472]  # Arducam native high-res mode  
      preview: [1280, 720]   # Standard preview
    format: "jpeg"
    quality: 95
    
  synchronization:
    enable: true
    tolerance_ms: 10
    
  streaming:
    enable: true
    fps: 30
    quality: 70
    
  # Arducam-specific settings
  arducam_config:
    sensor_mode: 2  # Use mode 2 for balanced performance
    use_native_resolution: true
    enable_auto_focus: true
"""
    
    print("📝 Recommended config update:")
    print(optimized_config)
    
    # Offer to update the config
    print("\n💡 This config uses Arducam's native 4624x3472 resolution")
    print("   which should be more compatible than the current 3280x2464")

def main():
    """Test camera compatibility and suggest fixes"""
    
    print("🚨 CAMERA COMPATIBILITY DIAGNOSTIC")
    print("Hardware: Arducam 64MP (confirmed working)")
    print("Issue: Software initialization failing")
    print("=" * 60)
    
    # Test 1: Arducam compatibility with current config
    compat_ok = test_arducam_compatibility()
    
    # Test 2: Direct controller test
    controller_ok = test_direct_camera_controller()
    
    print("\n" + "=" * 60)
    print("📊 DIAGNOSTIC RESULTS")
    print(f"   Arducam Compatibility: {'✅ PASS' if compat_ok else '❌ FAIL'}")
    print(f"   Controller Test: {'✅ PASS' if controller_ok else '❌ FAIL'}")
    
    if compat_ok and controller_ok:
        print("\n✅ CAMERAS SHOULD BE WORKING!")
        print("💡 The issue might be in the web interface integration")
        print("🔧 Try restarting the web interface")
        
    elif compat_ok and not controller_ok:
        print("\n🔧 HARDWARE OK, CONTROLLER ISSUE:")
        print("   • PiCameraController has a bug")
        print("   • Configuration issue")
        print("   • Import or initialization problem")
        
    elif not compat_ok:
        print("\n🔧 RESOLUTION COMPATIBILITY ISSUE:")
        print("   • Current config resolution not compatible with Arducam")
        print("   • Need to update camera configuration")
        create_optimized_camera_config()
        
    else:
        print("\n❌ MULTIPLE ISSUES")
    
    print("\n🎯 NEXT STEPS:")
    print("1. Run this test: python camera_compatibility_test.py")
    print("2. If controller fails, check PiCameraController code")
    print("3. Consider updating camera config to native Arducam resolutions")
    print("4. Restart web interface after any changes")

if __name__ == "__main__":
    main()