#!/usr/bin/env python3
"""
Camera Initialization Diagnostic
Check why cameras are not initializing in the web interface
"""

import sys
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_camera_imports():
    """Test if camera modules can be imported"""
    print("🔍 Testing Camera Module Imports")
    print("=" * 40)
    
    try:
        from camera.pi_camera_controller import PiCameraController
        print("✅ PiCameraController imported successfully")
    except ImportError as e:
        print(f"❌ PiCameraController import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ PiCameraController import error: {e}")
        return False
    
    return True

def test_config_loading():
    """Test configuration loading"""
    print("\n🔍 Testing Configuration Loading")
    print("=" * 40)
    
    try:
        from core.config_manager import ConfigManager
        config_manager = ConfigManager("config/scanner_config.yaml")
        
        # Get camera config
        camera_config = config_manager.get('cameras', {})
        print(f"✅ Camera config loaded: {camera_config}")
        
        # Check simulation mode
        simulation_mode = config_manager.get('system.simulation_mode', False)
        print(f"📊 Simulation mode: {simulation_mode}")
        
        return True, camera_config, simulation_mode
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return False, {}, True

def test_camera_hardware():
    """Test actual camera hardware availability"""
    print("\n🔍 Testing Camera Hardware")
    print("=" * 40)
    
    try:
        # Try basic camera check
        import subprocess
        result = subprocess.run(['libcamera-hello', '--list-cameras'], 
                              capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0:
            print("✅ libcamera-hello found cameras:")
            print(result.stdout)
            return True
        else:
            print(f"❌ libcamera-hello failed: {result.stderr}")
            return False
            
    except FileNotFoundError:
        print("❌ libcamera-hello not found - may not be on Pi")
        return False
    except subprocess.TimeoutExpired:
        print("❌ libcamera-hello timed out")
        return False
    except Exception as e:
        print(f"❌ Camera hardware test failed: {e}")
        return False

def test_direct_camera_init():
    """Test direct camera controller initialization"""
    print("\n🔍 Testing Direct Camera Controller Initialization")
    print("=" * 40)
    
    try:
        from camera.pi_camera_controller import PiCameraController
        from core.config_manager import ConfigManager
        
        config_manager = ConfigManager("config/scanner_config.yaml")
        camera_config = config_manager.get('cameras', {})
        
        print(f"📊 Using camera config: {camera_config}")
        
        # Create controller
        controller = PiCameraController(camera_config)
        print("✅ PiCameraController created")
        
        # Try to initialize
        import asyncio
        async def init_test():
            try:
                result = await controller.initialize()
                return result
            except Exception as e:
                print(f"❌ Initialization failed: {e}")
                return False
        
        result = asyncio.run(init_test())
        
        if result:
            print("✅ Camera controller initialized successfully")
            return True
        else:
            print("❌ Camera controller initialization returned False")
            return False
            
    except Exception as e:
        print(f"❌ Direct camera init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_orchestrator_camera_init():
    """Test camera initialization through orchestrator"""
    print("\n🔍 Testing Orchestrator Camera Initialization")
    print("=" * 40)
    
    try:
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        
        config_manager = ConfigManager("config/scanner_config.yaml")
        
        # Create orchestrator
        orchestrator = ScanOrchestrator(config_manager)
        print("✅ ScanOrchestrator created")
        
        # Check what type of camera manager was created
        camera_manager_type = type(orchestrator.camera_manager).__name__
        print(f"📊 Camera manager type: {camera_manager_type}")
        
        # Try to initialize
        import asyncio
        async def init_test():
            try:
                result = await orchestrator.camera_manager.initialize()
                return result
            except Exception as e:
                print(f"❌ Camera manager initialization failed: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        result = asyncio.run(init_test())
        
        if result:
            print("✅ Camera manager initialized successfully")
            
            # Check status
            status = orchestrator.camera_manager.get_status()
            print(f"📊 Camera status: {status}")
            return True
        else:
            print("❌ Camera manager initialization returned False")
            return False
            
    except Exception as e:
        print(f"❌ Orchestrator camera init failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run camera diagnostics"""
    print("🔍 Camera Initialization Diagnostics")
    print("=" * 50)
    
    tests_passed = 0
    total_tests = 5
    
    # Test 1: Module imports
    if test_camera_imports():
        tests_passed += 1
    
    # Test 2: Configuration
    config_ok, camera_config, simulation_mode = test_config_loading()
    if config_ok:
        tests_passed += 1
    
    # Test 3: Hardware availability (only if not Windows)
    import platform
    if platform.system() != "Windows":
        if test_camera_hardware():
            tests_passed += 1
    else:
        print("\n⚠️  Skipping hardware test on Windows")
        total_tests -= 1
    
    # Test 4: Direct controller init (only if not simulation mode)
    if not simulation_mode:
        if test_direct_camera_init():
            tests_passed += 1
    else:
        print("\n⚠️  Skipping direct init test - simulation mode enabled")
        total_tests -= 1
    
    # Test 5: Orchestrator init
    if test_orchestrator_camera_init():
        tests_passed += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"📊 DIAGNOSTIC SUMMARY: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("✅ All camera tests passed!")
        print("💡 Camera should be working - check web interface logs for other issues")
    else:
        print("❌ Some camera tests failed")
        print("🔧 Suggestions:")
        if not config_ok:
            print("   • Check scanner_config.yaml for camera configuration")
        if simulation_mode:
            print("   • Disable simulation_mode in config to use real cameras")
        print("   • Ensure you're running on Raspberry Pi with cameras connected")
        print("   • Check camera permissions and libcamera installation")

if __name__ == "__main__":
    main()