#!/usr/bin/env python3
"""
Test Script: Verify Storage Metadata Fix

This script tests whether the StorageMetadata fix resolves the file saving issue.

Usage: python test_storage_metadata_fix.py
"""

import asyncio
import logging
import sys
import time
import hashlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from storage.base import StorageMetadata, DataType
from storage.session_manager import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_storage_metadata():
    """Test StorageMetadata creation and storage"""
    
    print("🧪 Testing StorageMetadata Fix...")
    print("=" * 50)
    
    try:
        # Create test storage configuration
        storage_config = {
            'base_path': 'test_storage',
            'locations': {
                'primary': {'path': 'test_storage/primary', 'priority': 1}
            }
        }
        
        # Initialize SessionManager
        storage_manager = SessionManager(storage_config)
        await storage_manager.initialize()
        
        print("✅ Storage manager initialized")
        
        # Create a test session
        session_metadata = {
            'scan_id': 'test_storage_fix',
            'pattern_type': 'grid',
            'total_points': 1,
            'created_at': time.time()
        }
        
        session_id = await storage_manager.create_session(session_metadata)
        print(f"📁 Created test session: {session_id}")
        
        # Create test image data
        import numpy as np
        import cv2
        
        # Create a simple test image
        test_image = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        
        # Encode as JPEG
        success, encoded_image = cv2.imencode('.jpg', test_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        if not success:
            print("❌ Failed to encode test image")
            return False
            
        image_bytes = encoded_image.tobytes()
        checksum = hashlib.md5(image_bytes).hexdigest()
        
        # Create proper StorageMetadata object (same as in scan_orchestrator.py)
        timestamp = int(time.time())
        filename = f"camera_0_point_001_{timestamp}.jpg"
        
        storage_metadata = StorageMetadata(
            file_id=f"camera_0_p1_{timestamp}",
            original_filename=filename,
            data_type=DataType.SCAN_IMAGE,
            file_size_bytes=len(image_bytes),
            checksum=checksum,
            creation_time=time.time(),
            scan_session_id=None,  # Will be filled by storage manager
            sequence_number=1,
            position_data={'x': 10.0, 'y': 20.0, 'z': 0.0, 'c': 0.0},
            camera_settings={},
            lighting_settings=None,
            tags=["camera_0", "point_1"],
            file_extension=".jpg",
            filename=filename,
            scan_point_id="point_1",
            camera_id="camera_0",
            metadata={
                'image_shape': test_image.shape,
                'encoding': 'JPEG',
                'quality': 95
            }
        )
        
        print("📝 Created StorageMetadata object with all required fields")
        
        # Test storing the file
        try:
            file_id = await storage_manager.store_file(image_bytes, storage_metadata)
            print(f"🎉 SUCCESS: File stored successfully with ID: {file_id}")
            
            # Check if file actually exists
            storage_path = Path(storage_config['base_path'])
            session_dirs = list(storage_path.glob('**/sessions/*'))
            
            if session_dirs:
                for session_dir in session_dirs:
                    if session_dir.is_dir():
                        jpg_files = list(session_dir.glob('*.jpg'))
                        if jpg_files:
                            print(f"📸 Found saved image: {jpg_files[0]}")
                            file_size = jpg_files[0].stat().st_size
                            print(f"   File size: {file_size} bytes")
                            return True
                            
            print("⚠️ File stored but not found on disk")
            return False
            
        except Exception as storage_error:
            print(f"❌ Storage failed: {storage_error}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        try:
            if 'storage_manager' in locals():
                await storage_manager.shutdown()
        except Exception as e:
            print(f"Warning: Shutdown error: {e}")

async def main():
    """Main test function"""
    success = await test_storage_metadata()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ STORAGE METADATA FIX VERIFIED - Files can now be saved!")
    else:
        print("❌ STORAGE METADATA FIX FAILED - Further investigation needed")
    print("=" * 50)
    
    return success

if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)