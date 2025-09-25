#!/usr/bin/env python3
"""
Hardware Connection Diagnostic Tool
Checks FluidNC and camera connections before starting web interface
"""

import asyncio
import sys
import os
from pathlib import Path
import serial.tools.list_ports

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def check_fluidnc_connection():
    """Check FluidNC connection"""
    print("🔌 Checking FluidNC Connection...")
    
    # List all serial ports
    ports = list(serial.tools.list_ports.comports())
    fluidnc_ports = []
    
    print(f"📡 Found {len(ports)} serial ports:")
    for port in ports:
        print(f"   • {port.device}: {port.description}")
        if 'USB' in port.device or 'ACM' in port.device:
            fluidnc_ports.append(port.device)
    
    if not fluidnc_ports:
        print("❌ No USB/serial ports found for FluidNC")
        print("💡 Check USB connection and try: lsusb")
        return False
    
    # Test FluidNC connection
    try:
        from motion.fluidnc_controller import FluidNCController
        from core.config_manager import ConfigManager
        
        config_manager = ConfigManager(str(Path(__file__).parent / "config" / "scanner_config.yaml"))
        motion_config = config_manager.get('motion', {})
        
        # Override port to first available USB port
        motion_config['controller'] = motion_config.get('controller', {})
        motion_config['controller']['port'] = fluidnc_ports[0]
        
        print(f"🔧 Testing FluidNC on {fluidnc_ports[0]}...")
        
        controller = FluidNCController(motion_config)
        await controller.initialize()
        
        # Test basic communication
        await controller.connect()
        status = await controller.get_status()
        
        if status:
            print(f"✅ FluidNC connected successfully!")
            print(f"   Status: {status.status}")
            print(f"   Position: {status.position}")
            await controller.disconnect()
            return True
        else:
            print("❌ FluidNC connection failed - no response")
            return False
            
    except Exception as e:
        print(f"❌ FluidNC connection error: {e}")
        return False

async def check_camera_connections():
    """Check camera connections"""
    print("\n📷 Checking Camera Connections...")
    
    try:
        from camera.pi_camera_controller import PiCameraController
        from core.config_manager import ConfigManager
        
        config_manager = ConfigManager(str(Path(__file__).parent / "config" / "scanner_config.yaml"))
        camera_config = config_manager.get('camera', {})
        
        controller = PiCameraController(camera_config)
        await controller.initialize()
        
        # Test camera availability
        available_cameras = await controller.get_available_cameras()
        print(f"✅ Found {len(available_cameras)} cameras:")
        
        for camera_name in available_cameras:
            print(f"   • {camera_name}")
            
            # Test basic capture
            try:
                await controller.start_camera(camera_name)
                print(f"   ✅ {camera_name} started successfully")
                
                # Quick test capture
                frame = await controller.capture_single_frame(camera_name)
                if frame is not None:
                    print(f"   ✅ {camera_name} capture test successful")
                else:
                    print(f"   ⚠️  {camera_name} capture returned None")
                    
                await controller.stop_camera(camera_name)
                print(f"   ✅ {camera_name} stopped successfully")
                
            except Exception as e:
                print(f"   ❌ {camera_name} test failed: {e}")
        
        await controller.cleanup()
        return len(available_cameras) > 0
        
    except Exception as e:
        print(f"❌ Camera system error: {e}")
        return False

async def check_system_status():
    """Check overall system status"""
    print("\n🔍 System Status Check")
    print("=" * 40)
    
    # Check config file
    config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
    if config_file.exists():
        print("✅ Configuration file found")
    else:
        print("❌ Configuration file missing")
        return False
    
    # Check storage directories
    from create_storage_dirs import create_storage_directories
    if create_storage_directories():
        print("✅ Storage directories ready")
    else:
        print("❌ Storage directory issues")
    
    # Check hardware
    fluidnc_ok = await check_fluidnc_connection()
    camera_ok = await check_camera_connections()
    
    print(f"\n📊 Hardware Summary:")
    print(f"   • FluidNC: {'✅ Connected' if fluidnc_ok else '❌ Not connected'}")
    print(f"   • Cameras: {'✅ Available' if camera_ok else '❌ Not available'}")
    
    return fluidnc_ok and camera_ok

async def main():
    """Main diagnostic function"""
    print("🚀 Hardware Connection Diagnostic")
    print("=" * 50)
    
    try:
        success = await check_system_status()
        
        if success:
            print("\n🎉 All hardware connections successful!")
            print("✅ Ready to start web interface:")
            print("   python3 run_web_interface_fixed.py --mode production")
        else:
            print("\n⚠️  Some hardware issues detected")
            print("🔧 Web interface will start but some features may be limited")
            print("💡 Check connections and configuration")
            
    except KeyboardInterrupt:
        print("\n🛑 Diagnostic interrupted")
    except Exception as e:
        print(f"❌ Diagnostic error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ Failed to run diagnostic: {e}")
        sys.exit(1)