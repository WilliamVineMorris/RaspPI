#!/usr/bin/env python3
"""
Test sequential camera capture with safer timing
"""

import asyncio
import sys
from pathlib import Path

# Add V2.0 to path if needed
V2_DIR = Path(__file__).parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

async def safe_camera_capture(orchestrator, camera_id, timeout=10):
    """Capture with timeout to prevent hanging"""
    try:
        # Add timeout to prevent hanging
        image_data = await asyncio.wait_for(
            orchestrator.camera_manager.capture_high_resolution(camera_id),
            timeout=timeout
        )
        return image_data
    except asyncio.TimeoutError:
        print(f"  ⚠️  {camera_id} capture timed out after {timeout}s")
        return None
    except Exception as e:
        print(f"  ❌ {camera_id} capture error: {e}")
        return None

async def test_sequential_capture():
    """Test sequential camera capture with proper timing"""
    
    print("🔍 Testing Sequential Camera Capture with Timeout Protection")
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
        
        # Test sequential capture with delays
        if hasattr(orchestrator, 'camera_manager') and orchestrator.camera_manager:
            print("📷 Testing sequential capture with timeout protection...")
            
            results = []
            camera_ids = ['camera_0', 'camera_1']
            
            for camera_index, camera_id in enumerate(camera_ids):
                print(f"\n  📸 Capturing {camera_id}...")
                
                # Add delay between cameras
                if camera_index > 0:
                    print(f"  ⏳ Waiting 1s for camera resource cleanup...")
                    await asyncio.sleep(1.0)
                
                # Capture with timeout
                start_time = asyncio.get_event_loop().time()
                image_data = await safe_camera_capture(orchestrator, camera_id, timeout=15)
                end_time = asyncio.get_event_loop().time()
                
                capture_time = end_time - start_time
                
                if image_data is not None:
                    print(f"  ✅ {camera_id} capture successful! Shape: {image_data.shape}, Time: {capture_time:.2f}s")
                    results.append({
                        'camera_id': camera_index,
                        'camera_name': camera_id,
                        'success': True,
                        'shape': image_data.shape,
                        'capture_time': capture_time
                    })
                else:
                    print(f"  ❌ {camera_id} capture failed or timed out")
                    results.append({
                        'camera_id': camera_index,
                        'camera_name': camera_id,
                        'success': False,
                        'error': 'Capture failed or timed out',
                        'capture_time': capture_time
                    })
                
                # Brief cleanup delay
                await asyncio.sleep(0.2)
            
            # Summary
            successful_captures = sum(1 for r in results if r.get('success', False))
            print(f"\n📊 Sequential Capture Results:")
            print(f"   Total cameras tested: {len(results)}")
            print(f"   Successful captures: {successful_captures}")
            
            for result in results:
                status = "✅" if result.get('success') else "❌"
                camera_name = result.get('camera_name', 'unknown')
                capture_time = result.get('capture_time', 0)
                if result.get('success'):
                    shape = result.get('shape', 'unknown')
                    print(f"   {status} {camera_name}: {shape} ({capture_time:.2f}s)")
                else:
                    error = result.get('error', 'unknown error')
                    print(f"   {status} {camera_name}: {error} ({capture_time:.2f}s)")
            
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
    print("🧪 Sequential Camera Capture Test with Timeout Protection")
    print("This test uses timeouts and delays to prevent camera hanging")
    print()
    
    result = asyncio.run(test_sequential_capture())
    
    print()
    print("=" * 60)
    if result:
        print("🎉 SUCCESS: Both cameras working in sequential mode!")
        print("📸 Web interface 'Both Cameras' should now work reliably")
    else:
        print("❌ ISSUE: One or more cameras failed or timed out")
        print("🔧 Check camera resource management and timing")
    
    print()
    print("If this test works, try the web interface:")
    print("  python run_web_interface.py")

if __name__ == "__main__":
    main()