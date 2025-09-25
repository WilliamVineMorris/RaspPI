#!/usr/bin/env python3
"""
Quick Camera Debug - Find what changed since yesterday
"""

import sys
import logging
import traceback
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging to see all messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

def test_step_by_step():
    """Test camera initialization step by step to find exact failure point"""
    
    print("🔍 Step-by-Step Camera Debug")
    print("=" * 50)
    
    # Step 1: Test imports
    print("\n1️⃣ Testing Imports...")
    try:
        print("   • Importing picamera2...")
        from picamera2 import Picamera2
        print("   ✅ picamera2 imported")
        
        print("   • Importing camera.pi_camera_controller...")
        from camera.pi_camera_controller import PiCameraController
        print("   ✅ PiCameraController imported")
        
        print("   • Importing config manager...")
        from core.config_manager import ConfigManager
        print("   ✅ ConfigManager imported")
        
    except Exception as e:
        print(f"   ❌ Import failed: {e}")
        traceback.print_exc()
        return False
    
    # Step 2: Test config loading
    print("\n2️⃣ Testing Config Loading...")
    try:
        config_manager = ConfigManager("config/scanner_config.yaml")
        camera_config = config_manager.get('cameras', {})
        print(f"   ✅ Config loaded: {camera_config}")
    except Exception as e:
        print(f"   ❌ Config failed: {e}")
        traceback.print_exc()
        return False
    
    # Step 3: Test controller creation
    print("\n3️⃣ Testing Controller Creation...")
    try:
        controller = PiCameraController(camera_config)
        print("   ✅ Controller created")
    except Exception as e:
        print(f"   ❌ Controller creation failed: {e}")
        traceback.print_exc()
        return False
    
    # Step 4: Test basic camera detection
    print("\n4️⃣ Testing Camera Detection...")
    try:
        # Check if cameras are detected by picamera2
        print("   • Checking available cameras...")
        camera_info = Picamera2.global_camera_info()
        print(f"   📊 Found cameras: {len(camera_info)} cameras")
        for i, info in enumerate(camera_info):
            print(f"      Camera {i}: {info}")
        
        if len(camera_info) == 0:
            print("   ❌ No cameras detected by picamera2!")
            return False
        else:
            print(f"   ✅ {len(camera_info)} cameras detected")
            
    except Exception as e:
        print(f"   ❌ Camera detection failed: {e}")
        traceback.print_exc()
        return False
    
    # Step 5: Test controller initialization
    print("\n5️⃣ Testing Controller Initialization...")
    try:
        import asyncio
        
        async def init_test():
            print("   • Calling controller.initialize()...")
            result = await controller.initialize()
            print(f"   📊 Initialize result: {result}")
            return result
        
        result = asyncio.run(init_test())
        
        if result:
            print("   ✅ Controller initialized successfully!")
            return True
        else:
            print("   ❌ Controller initialization returned False")
            return False
            
    except Exception as e:
        print(f"   ❌ Controller initialization failed: {e}")
        traceback.print_exc()
        return False

def test_hardware_directly():
    """Test camera hardware directly with libcamera"""
    print("\n🔍 Direct Hardware Test")
    print("=" * 30)
    
    try:
        import subprocess
        
        print("   • Testing rpicam-hello...")
        result = subprocess.run(['rpicam-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("   ✅ rpicam-hello success:")
            print("   " + result.stdout.replace('\n', '\n   '))
            return True
        else:
            print(f"   ❌ rpicam-hello failed:")
            print("   " + result.stderr.replace('\n', '\n   '))
            return False
            
    except FileNotFoundError:
        print("   ⚠️  rpicam-hello not found")
        return False
    except subprocess.TimeoutExpired:
        print("   ❌ rpicam-hello timed out")
        return False
    except Exception as e:
        print(f"   ❌ Hardware test failed: {e}")
        return False

def check_permissions():
    """Check camera permissions"""
    print("\n🔍 Permission Check")
    print("=" * 25)
    
    try:
        import os
        import grp
        
        # Check if user is in video group
        try:
            video_group = grp.getgrnam('video')
            user_groups = [g.gr_name for g in grp.getgrall() if os.getlogin() in g.gr_mem]
            
            if 'video' in user_groups:
                print("   ✅ User is in video group")
            else:
                print("   ❌ User NOT in video group")
                print("   💡 Run: sudo usermod -a -G video $USER")
                
        except Exception as e:
            print(f"   ⚠️  Could not check video group: {e}")
        
        # Check /dev/video* devices
        video_devices = list(Path('/dev').glob('video*'))
        if video_devices:
            print(f"   📊 Found video devices: {[str(d) for d in video_devices]}")
            
            for device in video_devices:
                try:
                    stat = device.stat()
                    print(f"      {device}: readable={os.access(device, os.R_OK)}")
                except Exception as e:
                    print(f"      {device}: error checking - {e}")
        else:
            print("   ⚠️  No /dev/video* devices found")
            
    except Exception as e:
        print(f"   ❌ Permission check failed: {e}")

def main():
    """Run comprehensive camera debug"""
    print("🚨 CAMERA DEBUG: Finding What Changed Since Yesterday")
    print("=" * 60)
    
    # Test hardware first
    hw_ok = test_hardware_directly()
    
    # Check permissions
    check_permissions()
    
    # Test software step by step
    sw_ok = test_step_by_step()
    
    print("\n" + "=" * 60)
    print("📊 DEBUG SUMMARY")
    print(f"   Hardware Test: {'✅ PASS' if hw_ok else '❌ FAIL'}")
    print(f"   Software Test: {'✅ PASS' if sw_ok else '❌ FAIL'}")
    
    if hw_ok and sw_ok:
        print("\n🎉 Cameras should be working!")
        print("💡 If web interface still shows issues, restart it")
    elif hw_ok and not sw_ok:
        print("\n🔧 Hardware OK, Software Issue:")
        print("   • Check if any files were moved during cleanup")
        print("   • Verify all imports are working")
        print("   • Check logs for detailed error messages")
    elif not hw_ok:
        print("\n🔧 Hardware Issue:")
        print("   • Camera hardware not detected")
        print("   • Check camera connections")
        print("   • Verify camera is enabled in raspi-config")
    else:
        print("\n❌ Both hardware and software issues detected")

if __name__ == "__main__":
    main()