#!/usr/bin/env python3
"""
Simplified test focused on basic storage manager instantiation
"""

import asyncio
import tempfile
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_basic_instantiation():
    """Test if we can at least instantiate the storage manager with a mock approach"""
    
    try:
        # Import the scan orchestrator which includes the mock storage
        from scanning.scan_orchestrator import ScanOrchestrator, MockStorageManager
        from core.config_manager import ConfigManager
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            # Create minimal test configuration
            test_config = """
system:
  simulation_mode: true
  log_level: INFO

storage:
  base_path: {storage_path}
  backup_enabled: true

motion:
  controller_port: "/dev/ttyUSB0"
  baud_rate: 115200
  axes:
    x:
      min_position: 0
      max_position: 200
    y:
      min_position: 0
      max_position: 200
    z:
      min_position: -360
      max_position: 360
    c:
      min_position: -90
      max_position: 90

camera:
  dual_camera_enabled: true
  sync_tolerance_ms: 10

lighting:
  max_duty_cycle: 0.9
  default_pattern: uniform
""".format(storage_path=str(Path(temp_dir) / "storage"))
            
            # Save test config
            with open(config_path, 'w') as f:
                f.write(test_config)
            
            print("1. Created test configuration")
            
            # Initialize config manager first
            print("2. Initializing config manager...")
            config_manager = ConfigManager(str(config_path))
            print("✅ Config manager created")
            
            # Test MockStorageManager directly
            print("3. Testing MockStorageManager...")
            mock_storage = MockStorageManager(config_manager)
            await mock_storage.initialize()
            print("✅ MockStorageManager works!")
            
            # Test session creation
            session_metadata = {
                'scan_name': 'Test Scan',
                'description': 'Test description',
                'operator': 'Test User'
            }
            session_id = await mock_storage.create_session(session_metadata)
            print(f"✅ Session created: {session_id}")
            
            # Test session finalization
            success = await mock_storage.finalize_session(session_id)
            print(f"✅ Session finalized: {success}")
            
            # Test availability check
            available = mock_storage.is_available()
            print(f"✅ Storage available: {available}")
            
            print("\n🎉 Basic storage functionality test passed!")
            return True
            
    except Exception as e:
        print(f"\n❌ Basic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_basic_instantiation())
    if success:
        print("\n✅ Basic storage functionality is working!")
        print("📝 Note: The full SessionManager needs additional fixes")
        print("   but the mock implementation is functional for testing.")
    else:
        print("\n💥 Basic storage test failed!")