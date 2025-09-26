#!/usr/bin/env python3
"""
Test with corrected camera IDs (camera_0 and camera_1)
"""

import asyncio
import sys
from pathlib import Path

# Add V2.0 to path if needed
V2_DIR = Path(__file__).parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

async def test_corrected_camera_ids():
    """Test camera capture with corrected physical IDs"""
    
    print("🔍 Testing Camera Capture with Corrected Physical IDs")
    print("Using camera_0 and camera_1 (physical cameras 0 and 1)")
    print("=" * 60)
    
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
        
        # Test camera status first
        try:
            camera_status = orchestrator.get_camera_status()
            print(f"📊 Camera Status: {camera_status}")
        except Exception as status_error:
            print(f"⚠️  Camera status error: {status_error}")
        
        # Test sequential capture with corrected IDs
        if hasattr(orchestrator, 'camera_manager') and orchestrator.camera_manager:
            print("\n📷 Testing sequential capture with corrected camera IDs...")
            
            results = []
            # Use corrected physical camera IDs
            camera_ids = ['camera_0', 'camera_1']
            
            for camera_index, camera_id in enumerate(camera_ids):
                print(f"\n  📸 Testing {camera_id} (physical camera {camera_index})...")
                
                # Add delay between cameras for resource management
                if camera_index > 0:
                    print(f"  ⏳ Waiting 2s for camera resource cleanup...")
                    await asyncio.sleep(2.0)
                
                try:
                    # Capture with timeout
                    start_time = asyncio.get_event_loop().time()
                    image_data = await asyncio.wait_for(
                        orchestrator.camera_manager.capture_high_resolution(camera_id),
                        timeout=20  # Increased timeout
                    )
                    end_time = asyncio.get_event_loop().time()
                    
                    capture_time = end_time - start_time
                    
                    if image_data is not None:
                        print(f"  ✅ {camera_id} capture SUCCESS! Shape: {image_data.shape}, Time: {capture_time:.2f}s")
                        results.append({
                            'camera_id': camera_index,
                            'camera_name': camera_id,
                            'success': True,
                            'shape': image_data.shape,
                            'capture_time': capture_time
                        })
                    else:
                        print(f"  ❌ {camera_id} returned no data")
                        results.append({
                            'camera_id': camera_index,
                            'camera_name': camera_id,
                            'success': False,
                            'error': 'No image data returned',
                            'capture_time': capture_time
                        })
                        
                except asyncio.TimeoutError:
                    print(f"  ⚠️  {camera_id} capture timed out after 20s")
                    results.append({
                        'camera_id': camera_index,
                        'camera_name': camera_id,
                        'success': False,
                        'error': 'Timeout after 20s'
                    })
                except Exception as cam_error:
                    print(f"  ❌ {camera_id} capture error: {cam_error}")
                    results.append({
                        'camera_id': camera_index,
                        'camera_name': camera_id,
                        'success': False,
                        'error': str(cam_error)
                    })
                
                # Brief cleanup delay
                print(f"  ⏳ Brief cleanup delay...")
                await asyncio.sleep(0.5)
            
            # Summary
            successful_captures = sum(1 for r in results if r.get('success', False))
            print(f"\n📊 Final Results:")
            print(f"   Total cameras tested: {len(results)}")
            print(f"   Successful captures: {successful_captures}")
            
            for result in results:
                status = "✅" if result.get('success') else "❌"
                camera_name = result.get('camera_name', 'unknown')
                if result.get('success'):
                    shape = result.get('shape', 'unknown')
                    capture_time = result.get('capture_time', 0)
                    print(f"   {status} {camera_name}: {shape} ({capture_time:.2f}s)")
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
    print("🧪 Corrected Camera ID Test")
    print("Testing camera_0 and camera_1 (matching physical hardware)")
    print()
    
    result = asyncio.run(test_corrected_camera_ids())
    
    print()
    print("=" * 60)
    if result:
        print("🎉 SUCCESS: Both cameras working with corrected IDs!")
        print("📸 camera_0 and camera_1 successfully captured")
        print("✅ Web interface should now work with both cameras")
    else:
        print("❌ ISSUE: One or more cameras still failing")
        print("🔧 Check camera hardware and resource management")
    
    print()
    print("Next: Test web interface with:")
    print("  python run_web_interface.py")

if __name__ == "__main__":
    main()