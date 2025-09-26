#!/usr/bin/env python3
"""
Test synchronized camera capture to verify both cameras work
"""

import asyncio
import sys
from pathlib import Path

# Add V2.0 to path if needed
V2_DIR = Path(__file__).parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

async def test_synchronized_capture():
    """Test synchronized capture from both cameras"""
    
    print("🔍 Testing Synchronized Camera Capture")
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
        print("📦 Creating orchestrator...")
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize orchestrator
        print("⚙️  Initializing orchestrator...")
        success = await orchestrator.initialize()
        
        if not success:
            print("❌ Orchestrator initialization failed")
            return False
            
        print("✅ Orchestrator initialized successfully!")
        
        # Test synchronized capture like the web interface does
        if hasattr(orchestrator, 'camera_manager') and orchestrator.camera_manager:
            print("📷 Testing synchronized capture...")
            
            results = []
            camera_ids = ['camera_1', 'camera_2']
            
            for camera_index, camera_id in enumerate(camera_ids):
                try:
                    print(f"  📸 Capturing {camera_id}...")
                    
                    # Test high resolution capture
                    image_data = await orchestrator.camera_manager.capture_high_resolution(camera_id)
                    
                    if image_data is not None:
                        print(f"  ✅ {camera_id} capture successful! Image shape: {image_data.shape}")
                        results.append({
                            'camera_id': camera_index,
                            'camera_name': camera_id,
                            'success': True,
                            'shape': image_data.shape
                        })
                    else:
                        print(f"  ❌ {camera_id} returned no data")
                        results.append({
                            'camera_id': camera_index,
                            'camera_name': camera_id,
                            'success': False,
                            'error': 'No image data'
                        })
                        
                except Exception as cam_error:
                    print(f"  ❌ {camera_id} failed: {cam_error}")
                    results.append({
                        'camera_id': camera_index,
                        'camera_name': camera_id,
                        'success': False,
                        'error': str(cam_error)
                    })
            
            # Summary
            successful_captures = sum(1 for r in results if r.get('success', False))
            print(f"\n📊 Capture Results:")
            print(f"   Total cameras tested: {len(results)}")
            print(f"   Successful captures: {successful_captures}")
            
            for result in results:
                status = "✅" if result.get('success') else "❌"
                camera_name = result.get('camera_name', 'unknown')
                if result.get('success'):
                    shape = result.get('shape', 'unknown')
                    print(f"   {status} {camera_name}: {shape}")
                else:
                    error = result.get('error', 'unknown error')
                    print(f"   {status} {camera_name}: {error}")
            
            return successful_captures == 2  # Both cameras should work
        else:
            print("❌ No camera manager available")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Synchronized Camera Capture Test")
    print("This will test if both cameras work in synchronized capture mode")
    print()
    
    result = asyncio.run(test_synchronized_capture())
    
    print()
    print("=" * 50)
    if result:
        print("🎉 SUCCESS: Both cameras working in synchronized mode!")
        print("📸 Web interface 'Both Cameras' button should now capture both")
    else:
        print("❌ ISSUE: One or more cameras failed")
        print("🔧 Check camera connections and initialization")
    
    print()
    print("To test in web interface:")
    print("  1. Start: python run_web_interface.py")
    print("  2. Click 'Both Cameras' button")  
    print("  3. Check that both camera_1 and camera_2 images are saved")

if __name__ == "__main__":
    main()