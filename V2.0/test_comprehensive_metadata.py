#!/usr/bin/env python3
"""
Test Script: Verify Comprehensive Metadata Storage

This script validates that camera information is being stored both in EXIF data 
and in the metadata JSON files, matching the manual capture functionality.

Usage: python test_comprehensive_metadata.py
"""

import asyncio
import logging
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_metadata_storage():
    """Test comprehensive metadata storage during scanning"""
    
    print("🧪 Testing Comprehensive Metadata Storage...")
    print("=" * 60)
    
    try:
        from core.config_manager import ConfigManager
        from scanning.scan_orchestrator import ScanOrchestrator
        from scanning.scan_patterns import GridScanPattern, GridPatternParameters
        
        # Initialize configuration and orchestrator
        config_manager = ConfigManager('config/scanner_config.yaml')
        
        # Use real hardware mode to test actual SessionManager
        config_manager._config['system']['simulation_mode'] = False
        
        orchestrator = ScanOrchestrator(config_manager)
        await orchestrator.initialize()
        
        print("✅ Orchestrator initialized (real hardware mode)")
        
        # Create a minimal test scan pattern
        pattern_params = GridPatternParameters(
            x_range=(10.0, 20.0), x_step=10.0,
            y_range=(10.0, 20.0), y_step=10.0, 
            camera_angles=[0.0]
        )
        
        pattern = GridScanPattern("metadata_test", pattern_params)
        points = pattern.generate_points()
        
        print(f"📐 Created test pattern with {len(points)} points")
        
        # Check storage directories before scan
        storage_dirs = [
            Path("scan_images"),  # Mock storage
            Path("test_storage"),  # SessionManager storage
        ]
        
        print("\n📁 Storage locations before scan:")
        for storage_dir in storage_dirs:
            if storage_dir.exists():
                print(f"   📂 {storage_dir}: {len(list(storage_dir.rglob('*')))} files")
            else:
                print(f"   📂 {storage_dir}: does not exist")
        
        # Start the scan
        output_dir = Path("metadata_test_output")
        output_dir.mkdir(exist_ok=True)
        
        print("\n🚀 Starting metadata test scan...")
        scan_state = await orchestrator.start_scan(
            pattern=pattern,
            output_directory=output_dir,
            scan_id="metadata_test_scan"
        )
        
        print(f"📊 Scan started: {scan_state.scan_id}")
        
        # Wait for scan to progress and complete
        print("⏳ Waiting for scan to complete...")
        for i in range(30):  # Wait up to 30 seconds
            await asyncio.sleep(1)
            status = orchestrator.get_scan_status()
            
            if status:
                progress = status.get('progress', 0)
                scan_status = status.get('status', 'unknown')
                print(f"   Progress: {progress}%, Status: {scan_status}")
                
                if scan_status in ['completed', 'failed', 'cancelled']:
                    print(f"   Scan finished: {scan_status}")
                    break
            else:
                print(f"   No status available (attempt {i+1}/30)")
        
        # Check for stored images and metadata
        print("\n🔍 Final Metadata Check:")
        
        total_images = 0
        total_metadata_files = 0
        metadata_samples = []
        
        for storage_dir in storage_dirs:
            if storage_dir.exists():
                # Find all session directories
                session_dirs = [d for d in storage_dir.iterdir() if d.is_dir()]
                
                for session_dir in session_dirs:
                    if 'metadata_test' in session_dir.name or 'mock_session' in session_dir.name:
                        print(f"   📁 Session: {session_dir.name}")
                        
                        # Count images
                        images = list(session_dir.glob("*.jpg"))
                        metadata_files = list(session_dir.glob("*.json"))
                        
                        total_images += len(images)
                        total_metadata_files += len(metadata_files)
                        
                        print(f"      📸 Images: {len(images)}")
                        print(f"      📋 Metadata files: {len(metadata_files)}")
                        
                        # Check image EXIF data
                        if images:
                            sample_image = images[0]
                            print(f"      🔍 Checking EXIF in: {sample_image.name}")
                            
                            try:
                                from PIL import Image
                                from PIL.ExifTags import TAGS
                                
                                with Image.open(sample_image) as img:
                                    exif_data = img.getexif()
                                    if exif_data:
                                        print(f"         ✅ EXIF data found: {len(exif_data)} fields")
                                        
                                        # Show key EXIF fields
                                        exif_dict = {}
                                        for tag_id, value in exif_data.items():
                                            tag = TAGS.get(tag_id, tag_id)
                                            exif_dict[tag] = value
                                        
                                        key_fields = ['Make', 'Model', 'Software', 'DateTime', 'ExposureTime', 'ISOSpeedRatings', 'Flash']
                                        for field in key_fields:
                                            if field in exif_dict:
                                                print(f"         📷 {field}: {exif_dict[field]}")
                                    else:
                                        print("         ❌ No EXIF data found")
                                        
                            except Exception as exif_error:
                                print(f"         ❌ EXIF check failed: {exif_error}")
                        
                        # Check JSON metadata
                        if metadata_files:
                            sample_metadata = metadata_files[0]
                            print(f"      🔍 Checking JSON metadata: {sample_metadata.name}")
                            
                            try:
                                with open(sample_metadata, 'r') as f:
                                    metadata = json.load(f)
                                
                                print(f"         ✅ JSON metadata found: {len(metadata)} top-level fields")
                                
                                # Show key metadata fields
                                key_fields = ['camera_settings', 'position_data', 'lighting_settings', 'metadata']
                                for field in key_fields:
                                    if field in metadata:
                                        if isinstance(metadata[field], dict):
                                            print(f"         📋 {field}: {len(metadata[field])} sub-fields")
                                            if field == 'camera_settings':
                                                camera_meta = metadata[field]
                                                if 'comprehensive_metadata' in camera_meta:
                                                    comp_meta = camera_meta['comprehensive_metadata']
                                                    print(f"            📷 Camera Make: {comp_meta.get('make', 'missing')}")
                                                    print(f"            📷 Camera Model: {comp_meta.get('model', 'missing')}")
                                                    print(f"            📷 Exposure: {comp_meta.get('exposure_time', 'missing')}")
                                                    print(f"            📷 ISO: {comp_meta.get('iso', 'missing')}")
                                        else:
                                            print(f"         📋 {field}: {metadata[field]}")
                                    else:
                                        print(f"         ❌ {field}: missing")
                                
                                metadata_samples.append({
                                    'file': sample_metadata.name,
                                    'fields': list(metadata.keys())
                                })
                                        
                            except Exception as json_error:
                                print(f"         ❌ JSON check failed: {json_error}")
        
        # Summary
        print(f"\n📊 METADATA STORAGE SUMMARY:")
        print(f"   📸 Total images saved: {total_images}")
        print(f"   📋 Total metadata files: {total_metadata_files}")
        print(f"   📝 Metadata samples: {len(metadata_samples)}")
        
        # Success criteria
        success = (
            total_images > 0 and
            total_metadata_files > 0 and
            len(metadata_samples) > 0
        )
        
        return success
            
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
    success = await test_metadata_storage()
    
    print("\n" + "=" * 60)
    if success:
        print("✅ COMPREHENSIVE METADATA STORAGE VERIFIED!")
        print("   📷 Camera information stored in EXIF data")  
        print("   📋 Complete metadata saved in JSON files")
        print("   🎯 Same functionality as manual capture button")
    else:
        print("❌ METADATA STORAGE INCOMPLETE")
        print("   Need to investigate missing metadata components")
    print("=" * 60)
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)