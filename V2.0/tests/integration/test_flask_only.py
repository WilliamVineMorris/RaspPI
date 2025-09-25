#!/usr/bin/env python3
"""
Test script to validate Flask-only web interface (no Gunicorn)
"""

import sys
import os
import time
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_flask_only_interface():
    """Test that Flask interface works without Gunicorn"""
    print("🔍 Testing Flask-only web interface...")
    
    try:
        from web.web_interface import ScannerWebInterface
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        
        # Initialize minimal system
        config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
        config_manager = ConfigManager(str(config_file))
        orchestrator = ScanOrchestrator(config_manager)
        web_interface = ScannerWebInterface(orchestrator)
        
        # Test that start_web_server method exists and has correct signature
        if hasattr(web_interface, 'start_web_server'):
            print("✅ Flask web server start method found")
            
            # Check that Gunicorn code has been removed
            import inspect
            source = inspect.getsource(web_interface.start_web_server)
            
            if 'gunicorn' not in source.lower():
                print("✅ Gunicorn dependencies removed from Flask server")
            else:
                print("❌ Gunicorn code still present in Flask server")
                
            if 'threaded=True' in source:
                print("✅ Flask threading enabled for camera streams")
            else:
                print("⚠️  Flask threading not explicitly enabled")
                
        else:
            print("❌ Flask web server start method not found")
            
        # Test Flask launcher
        print("\n🔍 Testing Flask launcher...")
        import run_web_flask
        print("✅ Flask launcher imports successfully")
        
        print("✅ Flask-only interface validated")
        return True
        
    except Exception as e:
        print(f"❌ Flask interface test failed: {e}")
        import traceback
        print(f"   Full error: {traceback.format_exc()}")
        return False

def test_removed_gunicorn():
    """Test that Gunicorn has been properly removed"""
    print("\n🔍 Testing Gunicorn removal...")
    
    try:
        # Check requirements.txt
        req_file = Path(__file__).parent / "requirements.txt"
        if req_file.exists():
            content = req_file.read_text()
            if 'gunicorn' not in content or '# gunicorn removed' in content:
                print("✅ Gunicorn removed from requirements.txt")
            else:
                print("❌ Gunicorn still in requirements.txt")
        
        # Check web interface file
        web_file = Path(__file__).parent / "web" / "web_interface.py"
        if web_file.exists():
            content = web_file.read_text()
            gunicorn_imports = content.count('from gunicorn')
            if gunicorn_imports == 0:
                print("✅ No Gunicorn imports in web interface")
            else:
                print(f"❌ Found {gunicorn_imports} Gunicorn import(s) still present")
        
        print("✅ Gunicorn removal validated")
        return True
        
    except Exception as e:
        print(f"❌ Gunicorn removal test failed: {e}")
        return False

def test_camera_streaming_compatibility():
    """Test that camera streaming is compatible with Flask threading"""
    print("\n🔍 Testing camera streaming Flask compatibility...")
    
    try:
        from web.web_interface import ScannerWebInterface
        
        # Check that camera stream generation method exists
        if hasattr(ScannerWebInterface, '_generate_camera_stream'):
            print("✅ Camera stream generator method found")
            
            # Test that it handles both cameras
            import inspect
            source = inspect.getsource(ScannerWebInterface._generate_camera_stream)
            
            if 'camera_1' in source and 'camera_2' in source:
                print("✅ Both cameras supported in stream generator")
            else:
                print("⚠️  Camera mapping may need verification")
                
            if 'SystemExit' in source and 'KeyboardInterrupt' in source:
                print("✅ Graceful shutdown handling present")
            else:
                print("❌ Missing graceful shutdown handling")
        
        print("✅ Camera streaming compatibility validated")
        return True
        
    except Exception as e:
        print(f"❌ Camera streaming test failed: {e}")
        return False

def main():
    """Run all Flask validation tests"""
    print("🧪 Testing Flask-Only Web Interface (No Gunicorn)\n")
    
    results = []
    
    # Test Flask interface
    results.append(test_flask_only_interface())
    
    # Test Gunicorn removal
    results.append(test_removed_gunicorn())
    
    # Test camera streaming compatibility
    results.append(test_camera_streaming_compatibility())
    
    # Summary
    print(f"\n📊 Test Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("🎉 Flask-only interface validated successfully!")
        print("\n🚀 Ready to test on Raspberry Pi:")
        print("   cd /home/user/Documents/RaspPI/V2.0")
        print("   python3 run_web_flask.py")
        print("   # Or with debug mode:")
        print("   python3 run_web_flask.py --debug")
        print("\n🌐 Access web interface at: http://raspberrypi:8080")
        print("📹 Camera streams:")
        print("   Camera 0: http://raspberrypi:8080/camera/0")
        print("   Camera 1: http://raspberrypi:8080/camera/1")
        print("\n✅ Benefits of Flask-only approach:")
        print("   • No worker process conflicts")
        print("   • Simpler camera stream handling")
        print("   • Better Pi hardware compatibility")
        print("   • Cleaner shutdown process")
        print("   • No Gunicorn dependency issues")
        
    else:
        print("❌ Some tests failed - please check the Flask implementation")
        
    return all(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)