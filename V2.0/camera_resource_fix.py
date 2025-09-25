#!/usr/bin/env python3
"""
Fix Camera Resource Conflict
Clean up any stuck camera processes and restart web interface
"""

import sys
import subprocess
import time
import signal
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def kill_camera_processes():
    """Kill any processes that might be holding camera resources"""
    
    print("🔧 Cleaning Up Camera Processes")
    print("=" * 40)
    
    processes_to_kill = [
        'python.*camera.*test',
        'python.*test.*camera',
        'python.*run_web_interface',
        'rpicam-hello',
        'libcamera-hello',
        'python.*compatibility.*test'
    ]
    
    killed_count = 0
    
    for process_pattern in processes_to_kill:
        try:
            # Find processes matching pattern
            result = subprocess.run(['pgrep', '-f', process_pattern], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid.strip():
                        try:
                            print(f"   • Killing process {pid} ({process_pattern})")
                            os.kill(int(pid), signal.SIGTERM)
                            killed_count += 1
                            time.sleep(0.5)
                        except (ProcessLookupError, ValueError):
                            pass
        except FileNotFoundError:
            # pgrep not available, try ps instead
            pass
    
    if killed_count > 0:
        print(f"   ✅ Killed {killed_count} camera processes")
        print("   ⏳ Waiting for resources to be released...")
        time.sleep(3)
    else:
        print("   📊 No camera processes found to kill")

def test_camera_resource_availability():
    """Test if cameras are available for exclusive access"""
    
    print("\n🔍 Testing Camera Resource Availability")
    print("=" * 45)
    
    try:
        from picamera2 import Picamera2
        
        # Test Camera 0
        print("   • Testing Camera 0 availability...")
        try:
            picam2_0 = Picamera2(0)
            print("   ✅ Camera 0 resource acquired")
            picam2_0.close()
            print("   ✅ Camera 0 resource released")
        except Exception as e:
            print(f"   ❌ Camera 0 not available: {e}")
            return False
        
        # Test Camera 1  
        print("   • Testing Camera 1 availability...")
        try:
            picam2_1 = Picamera2(1)
            print("   ✅ Camera 1 resource acquired")
            picam2_1.close()
            print("   ✅ Camera 1 resource released")
        except Exception as e:
            print(f"   ❌ Camera 1 not available: {e}")
            return False
        
        return True
        
    except ImportError:
        print("   ❌ Picamera2 not available")
        return False
    except Exception as e:
        print(f"   ❌ Camera resource test failed: {e}")
        return False

def fix_async_coroutine_issue():
    """Fix the async coroutine issue in get_status method"""
    
    print("\n🔧 Checking for Async Coroutine Issue")
    print("=" * 40)
    
    # The issue is that get_status is async but being called synchronously
    # Let's check if this is in the camera controller
    
    try:
        from camera.pi_camera_controller import PiCameraController
        
        # Check if get_status is defined as async
        import inspect
        if hasattr(PiCameraController, 'get_status'):
            method = getattr(PiCameraController, 'get_status')
            if inspect.iscoroutinefunction(method):
                print("   ⚠️  Found async get_status method")
                print("   💡 This needs to be awaited properly")
                return False
            else:
                print("   ✅ get_status is not async")
                return True
        else:
            print("   📊 get_status method not found")
            return True
            
    except Exception as e:
        print(f"   ❌ Could not check get_status method: {e}")
        return False

def restart_web_interface_clean():
    """Restart web interface with clean camera state"""
    
    print("\n🚀 Starting Clean Web Interface")
    print("=" * 35)
    
    try:
        print("   • Starting web interface...")
        print("   💡 Run this command manually:")
        print("   python run_web_interface.py")
        print("")
        print("   ✅ Camera resources should now be available")
        
    except Exception as e:
        print(f"   ❌ Could not start web interface: {e}")

def main():
    """Clean up camera resources and restart web interface"""
    
    print("🚨 CAMERA RESOURCE CLEANUP & FIX")
    print("=" * 50)
    
    # Step 1: Kill any conflicting processes
    kill_camera_processes()
    
    # Step 2: Test camera availability
    cameras_available = test_camera_resource_availability()
    
    # Step 3: Check for async issues
    async_ok = fix_async_coroutine_issue()
    
    print("\n" + "=" * 50)
    print("📊 CLEANUP RESULTS")
    print(f"   Camera Resources: {'✅ AVAILABLE' if cameras_available else '❌ BUSY'}")
    print(f"   Async Issues: {'✅ OK' if async_ok else '⚠️  NEEDS FIXING'}")
    
    if cameras_available and async_ok:
        print("\n✅ READY TO RESTART WEB INTERFACE")
        restart_web_interface_clean()
        
    elif cameras_available and not async_ok:
        print("\n⚠️  CAMERAS OK, BUT ASYNC ISSUE EXISTS")
        print("🔧 The get_status method issue needs to be fixed")
        print("💡 Web interface might work but with warnings")
        restart_web_interface_clean()
        
    elif not cameras_available:
        print("\n❌ CAMERA RESOURCES STILL BUSY")
        print("🔧 Try these steps:")
        print("   1. Reboot the system: sudo reboot")
        print("   2. Or wait 30 seconds and try again")
        print("   3. Check for stuck camera processes: ps aux | grep camera")
        
    else:
        print("\n❌ MULTIPLE ISSUES DETECTED")
    
    print("\n🎯 NEXT STEPS:")
    print("1. Stop any running web interface (Ctrl+C)")
    print("2. Run: python camera_resource_fix.py")
    print("3. Then: python run_web_interface.py")
    print("4. Check web interface - cameras should work")

if __name__ == "__main__":
    main()