#!/usr/bin/env python3
"""
Simple test script for SessionManager implementation
"""

import asyncio
import tempfile
import sys
from pathlib import Path

# Add the project root to sys.path so we can import modules
sys.path.insert(0, str(Path(__file__).parent))

async def test_storage_manager():
    """Test basic SessionManager instantiation"""
    
    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        storage_path = Path(temp_dir)
        
        print(f"Testing SessionManager with path: {storage_path}")
        
        try:
            # Import here after sys.path is set
            from storage.session_manager import SessionManager
            
            print("1. Importing SessionManager... ✅")
            
            # Initialize storage manager with config dict
            print("2. Creating SessionManager...")
            config = {
                'base_path': str(storage_path),
                'backup_enabled': True,
                'compression_enabled': False
            }
            storage = SessionManager(config)
            
            print("   SessionManager created successfully ✅")
            
            # Initialize the storage system
            print("3. Initializing storage...")
            await storage.initialize()
            
            print("   Storage initialized successfully ✅")
            
            print("\n🎉 Basic SessionManager test completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ SessionManager test failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    success = asyncio.run(test_storage_manager())
    if success:
        print("\n✅ All tests passed!")
    else:
        print("\n💥 Tests failed!")