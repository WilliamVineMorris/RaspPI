#!/usr/bin/env python3
"""
Test Script: Validate Image Storage Fix

This script tests whether images are now being properly saved during scanning operations.

Usage: python test_image_storage_fix.py
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import GridScanPattern, PatternParameters

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_image_storage():
    """Test image storage during scanning"""
    
    print("🧪 Testing Image Storage Fix...")
    print("=" * 50)
    
    try:
        # Initialize configuration and orchestrator
        config_manager = ConfigManager()
        config_manager.load_config('config/scanner_config.yaml')
        
        # Enable simulation mode for testing
        config_manager.set('system.simulation_mode', True)
        
        orchestrator = ScanOrchestrator(config_manager)
        await orchestrator.initialize()
        
        print("✅ Orchestrator initialized")
        
        # Create a simple test scan pattern
        pattern_params = PatternParameters(
            x_start=10.0, x_end=20.0, x_step=10.0,
            y_start=10.0, y_end=20.0, y_step=10.0,
            camera_angles=[0.0]  # Single angle for quick test
        )
        
        pattern = GridScanPattern("test_storage", pattern_params)
        points = pattern.generate_points()
        
        print(f"📐 Created test pattern with {len(points)} points")
        
        # Check output directory before scan
        output_dir = Path("test_scan_output")
        output_dir.mkdir(exist_ok=True)
        
        storage_dir = Path("scan_images")
        if storage_dir.exists():
            print(f"📁 Storage directory exists: {storage_dir}")
            print(f"   Current contents: {list(storage_dir.iterdir())}")
        else:
            print("📁 No storage directory found yet")
        
        # Start the scan
        print("\n🚀 Starting test scan...")
        scan_state = await orchestrator.start_scan(
            pattern=pattern,
            output_directory=output_dir,
            scan_id="storage_test_scan"
        )
        
        print(f"📊 Scan started: {scan_state.scan_id}")
        
        # Wait a bit for scan to progress
        print("⏳ Waiting for scan to progress...")
        for i in range(20):  # Wait up to 20 seconds
            await asyncio.sleep(1)
            status = orchestrator.get_scan_status()
            print(f"   Progress: {status.get('progress', 0)}%, Status: {status.get('status', 'unknown')}")
            
            # Check if images are appearing
            if storage_dir.exists():
                session_dirs = list(storage_dir.iterdir())
                if session_dirs:
                    for session_dir in session_dirs:
                        if session_dir.is_dir():
                            images = list(session_dir.glob("*.jpg"))
                            if images:
                                print(f"   🎉 Found {len(images)} images in {session_dir.name}!")
                                for img in images[:3]:  # Show first 3
                                    print(f"      - {img.name}")
                                if len(images) > 3:
                                    print(f"      ... and {len(images) - 3} more")
            
            if status.get('status') in ['completed', 'failed', 'cancelled']:
                print(f"   Scan finished with status: {status.get('status')}")
                break
        
        # Final check for stored images
        print("\n🔍 Final Storage Check:")
        if storage_dir.exists():
            session_dirs = list(storage_dir.iterdir())
            print(f"   Sessions created: {len(session_dirs)}")
            
            total_images = 0
            for session_dir in session_dirs:
                if session_dir.is_dir():
                    images = list(session_dir.glob("*.jpg"))
                    metadata_files = list(session_dir.glob("*.json"))
                    total_images += len(images)
                    print(f"   📁 {session_dir.name}:")
                    print(f"      Images: {len(images)}")
                    print(f"      Metadata files: {len(metadata_files)}")
                    
                    # Show sample metadata
                    if metadata_files:
                        try:
                            with open(metadata_files[0], 'r') as f:
                                sample_metadata = json.load(f)
                            print(f"      Sample metadata keys: {list(sample_metadata.keys())}")
                        except Exception as e:
                            print(f"      Error reading metadata: {e}")
            
            print(f"   📸 Total images saved: {total_images}")
            
            if total_images > 0:
                print("\n🎉 SUCCESS: Images are being saved correctly!")
                return True
            else:
                print("\n❌ FAILED: No images were saved")
                return False
        else:
            print("   ❌ No storage directory found")
            return False
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        try:
            if 'orchestrator' in locals():
                await orchestrator.shutdown()
        except Exception as e:
            print(f"Warning: Shutdown error: {e}")

async def main():
    """Main test function"""
    success = await test_image_storage()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ IMAGE STORAGE FIX VERIFIED - Images are now being saved!")
    else:
        print("❌ IMAGE STORAGE STILL NOT WORKING - Further investigation needed")
    print("=" * 50)
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)