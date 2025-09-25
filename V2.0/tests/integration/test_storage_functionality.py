#!/usr/bin/env python3
"""
Comprehensive SessionManager functionality test
"""

import asyncio
import tempfile
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_storage_functionality():
    """Test SessionManager core functionality"""
    
    try:
        from storage.session_manager import SessionManager
        from storage.base import StorageMetadata, DataType
        
        # Create temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir)
            print(f"Testing with storage path: {storage_path}")
            
            # Initialize storage manager
            print("\n1. Creating SessionManager...")
            config = {
                'base_path': str(storage_path),
                'backup_enabled': True,
                'compression_enabled': False
            }
            storage = SessionManager(config)
            print("✅ SessionManager created")
            
            # Initialize storage
            print("\n2. Initializing storage...")
            await storage.initialize()
            print("✅ Storage initialized")
            
            # Create a session
            print("\n3. Creating scan session...")
            session = await storage.create_session(
                scan_name="Test Scan",
                description="Test session for validation", 
                operator="Test User",
                scan_parameters={"x_range": 100, "y_range": 100}
            )
            print(f"✅ Session created: {session.session_id}")
            
            # Store a test file
            print("\n4. Storing test file...")
            test_data = b"This is test image data for validation"
            test_checksum = hashlib.md5(test_data).hexdigest()
            
            metadata = StorageMetadata(
                file_id="test_001",
                original_filename="test_image.jpg",
                data_type=DataType.SCAN_IMAGE,
                file_size_bytes=len(test_data),
                checksum=test_checksum,
                creation_time=datetime.now().timestamp(),
                scan_session_id=session.session_id,
                sequence_number=1,
                position_data={"x": 10.0, "y": 20.0, "z": 30.0, "c": 45.0},
                camera_settings={"exposure": 100, "gain": 1.5},
                lighting_settings={"pattern": "uniform", "intensity": 80},
                tags=["test", "validation"]
            )
            
            file_id = await storage.store_file(test_data, metadata)
            print(f"✅ File stored with ID: {file_id}")
            
            # Test file retrieval
            print("\n5. Testing file retrieval...")
            retrieved_data, retrieved_metadata = await storage.retrieve_file(file_id)
            
            if retrieved_data == test_data:
                print("✅ File data matches original")
            else:
                print("❌ File data mismatch!")
                return False
            
            # Test file existence
            print("\n6. Testing file existence...")
            exists = await storage.file_exists(file_id)
            print(f"✅ File exists: {exists}")
            
            # List sessions
            print("\n7. Testing session listing...")
            sessions = await storage.list_sessions()
            print(f"✅ Found {len(sessions)} sessions")
            
            # Finalize session
            print("\n8. Finalizing session...")
            success = await storage.finalize_session(session.session_id)
            print(f"✅ Session finalized: {success}")
            
            # Test session retrieval
            print("\n9. Testing session retrieval...")
            retrieved_session = await storage.get_session(session.session_id)
            if retrieved_session:
                print(f"✅ Session retrieved: {retrieved_session.scan_name}")
            else:
                print("❌ Session retrieval failed!")
                return False
            
            print("\n🎉 All storage functionality tests passed!")
            return True
            
    except Exception as e:
        print(f"\n❌ Storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_storage_functionality())
    if success:
        print("\n✅ Storage implementation is working correctly!")
    else:
        print("\n💥 Storage implementation needs fixes!")