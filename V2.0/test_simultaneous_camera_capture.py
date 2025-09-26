#!/usr/bin/env python3
"""
Test simultaneous (synchronized) dual camera capture using corrected camera IDs.
This should work better than sequential capture for dual camera systems.
"""

import asyncio
import time
import logging
from pathlib import Path
import sys
import os

# Add the V2.0 directory to the Python path
V2_DIR = Path(__file__).parent
sys.path.insert(0, str(V2_DIR))

from scanning.scan_orchestrator import ScanOrchestrator
from core.config_manager import ConfigManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_simultaneous_camera_capture():
    """Test simultaneous capture from both cameras using asyncio.gather"""
    
    print("🧪 Simultaneous Camera Capture Test")
    print("Testing synchronized capture of camera_0 and camera_1")
    print()
    
    try:
        # Initialize configuration
        print("🔍 Loading configuration...")
        config_path = V2_DIR / "config" / "scanner_config.yaml"
        
        if not config_path.exists():
            print(f"❌ Config file not found: {config_path}")
            return False
            
        config_manager = ConfigManager(config_path)
        print(f"✅ Config loaded: {config_path}")
        
        # Force hardware mode (not simulation) for real camera testing
        # Override simulation mode to ensure we test real cameras
        config_manager._config_data['system'] = config_manager._config_data.get('system', {})
        config_manager._config_data['system']['simulation_mode'] = False
        print("🔧 Forced hardware mode (simulation_mode = False)")
        
        # Create and initialize orchestrator
        print("📦 Creating orchestrator...")
        orchestrator = ScanOrchestrator(config_manager)
        
        print("⚙️  Initializing orchestrator...")
        if not await orchestrator.initialize():
            print("❌ Failed to initialize orchestrator")
            return False
            
        print("✅ Orchestrator initialized successfully!")
        
        # Check camera status
        camera_status = orchestrator.get_camera_status()
        print(f"📊 Camera Status: {camera_status}")
        print()
        
        print("📷 Testing simultaneous dual camera capture...")
        print()
        
        # Define async capture function for individual camera
        async def capture_single_camera(camera_id: str):
            """Capture from a single camera with timeout"""
            start_time = time.time()
            try:
                print(f"  📸 Starting capture for {camera_id}...")
                
                # Use timeout to prevent hanging
                image_data = await asyncio.wait_for(
                    orchestrator.camera_manager.capture_high_resolution(camera_id),
                    timeout=15.0  # 15 second timeout
                )
                
                if image_data is not None:
                    capture_time = time.time() - start_time
                    print(f"  ✅ {camera_id} capture SUCCESS! Shape: {image_data.shape}, Time: {capture_time:.2f}s")
                    return {
                        'camera_id': camera_id,
                        'success': True,
                        'image_shape': image_data.shape,
                        'capture_time': capture_time
                    }
                else:
                    print(f"  ❌ {camera_id} capture returned None")
                    return {
                        'camera_id': camera_id,
                        'success': False,
                        'error': 'No image data returned'
                    }
                    
            except asyncio.TimeoutError:
                print(f"  ⏰ {camera_id} capture TIMEOUT after 15 seconds")
                return {
                    'camera_id': camera_id,
                    'success': False,
                    'error': 'Timeout after 15 seconds'
                }
            except Exception as e:
                print(f"  ❌ {camera_id} capture ERROR: {e}")
                return {
                    'camera_id': camera_id,
                    'success': False,
                    'error': str(e)
                }
        
        # Test simultaneous capture using asyncio.gather
        camera_ids = ['camera_0', 'camera_1']
        
        print("🚀 Starting TRUE SIMULTANEOUS capture of both cameras...")
        print("Using optimized dual-camera capture method...")
        
        simultaneous_start = time.time()
        
        # Use the new simultaneous capture method
        try:
            results = await asyncio.wait_for(
                orchestrator.camera_manager.capture_both_cameras_simultaneously(),
                timeout=30.0  # 30 second timeout for both cameras
            )
            
            simultaneous_total = time.time() - simultaneous_start
            print(f"⏱️  Total simultaneous capture time: {simultaneous_total:.2f}s")
            print()
            
            # Analyze results
            print("📊 SIMULTANEOUS CAPTURE RESULTS:")
            print("=" * 50)
            
            successful_captures = 0
            for camera_id, image_data in results.items():
                if image_data is not None:
                    successful_captures += 1
                    shape = image_data.shape if hasattr(image_data, 'shape') else 'unknown'
                    print(f"✅ {camera_id}: SUCCESS - Shape: {shape}")
                else:
                    print(f"❌ {camera_id}: FAILED - No image data")
            
            print()
            print(f"📈 SUCCESS RATE: {successful_captures}/2 cameras ({successful_captures/2*100:.1f}%)")
            
            if successful_captures == 2:
                print("🎉 TRUE SIMULTANEOUS DUAL CAMERA CAPTURE: SUCCESS!")
                print("Both cameras captured successfully at the same time!")
                return True
            elif successful_captures == 1:
                print("⚠️  PARTIAL SUCCESS: Only one camera captured successfully")
                return False
            else:
                print("❌ COMPLETE FAILURE: No cameras captured successfully")
                return False
                
        except asyncio.TimeoutError:
            print("⏰ TIMEOUT: Simultaneous capture took longer than 30 seconds")
            return False
        except Exception as e:
            print(f"❌ SIMULTANEOUS CAPTURE ERROR: {e}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        logger.exception("Test exception details:")
        return False
        
    finally:
        # Cleanup
        try:
            if 'orchestrator' in locals():
                print("🧹 Cleaning up orchestrator...")
                await orchestrator.shutdown()
                print("✅ Cleanup complete")
        except Exception as cleanup_error:
            print(f"⚠️  Cleanup warning: {cleanup_error}")

def main():
    """Main test runner"""
    print("🔧 Testing simultaneous dual camera capture...")
    print("This should work better than sequential capture for Pi cameras.")
    print()
    
    try:
        result = asyncio.run(test_simultaneous_camera_capture())
        
        print()
        print("=" * 60)
        if result:
            print("🎯 TEST RESULT: SUCCESS - Simultaneous capture working!")
            print("✅ Both cameras can capture simultaneously without hanging")
        else:
            print("💥 TEST RESULT: FAILED - Issues with simultaneous capture")
            print("❌ Check the error messages above for details")
        
        return result
        
    except KeyboardInterrupt:
        print()
        print("⚠️  Test interrupted by user (Ctrl+C)")
        return False
    except Exception as e:
        print(f"💥 Test runner failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)