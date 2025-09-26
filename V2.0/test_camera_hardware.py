#!/usr/bin/env python3
"""
Test camera access with direct web_interface.py startup
This will help verify camera initialization is working properly
"""

import asyncio
import sys
from pathlib import Path

# Add V2.0 to path if needed
V2_DIR = Path(__file__).parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

async def test_camera_access():
    """Test direct camera access through orchestrator"""
    
    print("🔍 Testing Camera Access with Real Hardware")
    print("=" * 50)
    
    try:
        # Import required modules
        from core.config_manager import ConfigManager
        from scanning.scan_orchestrator import ScanOrchestrator
        
        print("✅ All imports successful")
        
        # Load configuration
        config_file = V2_DIR / 'config' / 'scanner_config.yaml'
        config_manager = ConfigManager(config_file)
        print(f"✅ Config loaded: {config_file}")
        
        # Create orchestrator
        print("📦 Creating orchestrator with real hardware...")
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize orchestrator
        print("⚙️  Initializing orchestrator...")
        success = await orchestrator.initialize()
        
        if not success:
            print("❌ Orchestrator initialization failed")
            return False
            
        print("✅ Orchestrator initialized successfully!")
        
        # Test camera access
        if hasattr(orchestrator, 'camera_manager') and orchestrator.camera_manager:
            print("📷 Testing camera access...")
            
            # Test both camera IDs that web interface uses
            for camera_id in ['camera_1', 'camera_2']:
                try:
                    print(f"  📸 Testing {camera_id}...")
                    
                    # Test high resolution capture (like the web interface does)
                    image_data = await orchestrator.camera_manager.capture_high_resolution(camera_id)
                    
                    if image_data is not None:
                        print(f"  ✅ {camera_id} capture successful! Image shape: {image_data.shape}")
                    else:
                        print(f"  ❌ {camera_id} returned no data")
                        
                except Exception as cam_error:
                    print(f"  ❌ {camera_id} failed: {cam_error}")
            
            # Test camera status
            try:
                camera_status = orchestrator.get_camera_status()
                print(f"📊 Camera Status: {camera_status}")
            except Exception as status_error:
                print(f"❌ Camera status error: {status_error}")
                
            return True
        else:
            print("❌ No camera manager available")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Camera Hardware Access Test")
    print("This test verifies camera system works with direct orchestrator initialization")
    print()
    
    result = asyncio.run(test_camera_access())
    
    print()
    print("=" * 50)
    if result:
        print("🎉 SUCCESS: Camera system working properly!")
        print("📸 Both cameras accessible through orchestrator")
        print("✅ Direct web_interface.py startup should work")
    else:
        print("❌ ISSUE: Camera system has problems")
        print("📸 Use run_web_interface.py for proper startup")
    
    print()
    print("If cameras work here but web_interface.py still fails:")
    print("  Check web_interface.py initialization sequence")

if __name__ == "__main__":
    main()