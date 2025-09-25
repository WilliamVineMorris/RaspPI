#!/usr/bin/env python3
"""
Integration test for storage with scan orchestrator
"""

import asyncio
import tempfile
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

async def test_scan_integration():
    """Test storage integration with scan orchestrator"""
    
    try:
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "test_config.yaml"
            
            # Create minimal test configuration
            test_config = {
                'system': {
                    'simulation_mode': True,
                    'log_level': 'INFO'
                },
                'storage': {
                    'base_path': str(Path(temp_dir) / "storage"),
                    'backup_enabled': True
                },
                'motion': {
                    'axes': {
                        'x': {'min_position': 0, 'max_position': 200},
                        'y': {'min_position': 0, 'max_position': 200}, 
                        'z': {'min_position': -360, 'max_position': 360},
                        'c': {'min_position': -90, 'max_position': 90}
                    }
                },
                'camera': {
                    'dual_camera_enabled': True,
                    'sync_tolerance_ms': 10
                },
                'lighting': {
                    'max_duty_cycle': 0.9,
                    'default_pattern': 'uniform'
                }
            }
            
            # Save test config
            import yaml
            with open(config_path, 'w') as f:
                yaml.dump(test_config, f)
            
            print("1. Created test configuration")
            
            # Initialize config manager
            config_manager = ConfigManager(str(config_path))
            await config_manager.initialize()
            print("✅ Config manager initialized")
            
            # Initialize scan orchestrator  
            print("\n2. Creating scan orchestrator...")
            orchestrator = ScanOrchestrator(config_manager)
            await orchestrator.initialize()
            print("✅ Scan orchestrator initialized")
            
            # Check if storage is properly integrated
            print("\n3. Checking storage integration...")
            if hasattr(orchestrator, 'storage_manager'):
                print("✅ Storage manager is integrated")
                
                # Test storage through orchestrator
                if orchestrator.storage_manager:
                    sessions = await orchestrator.storage_manager.list_sessions()
                    print(f"✅ Can list sessions: {len(sessions)} found")
                else:
                    print("❌ Storage manager is None")
                    return False
            else:
                print("❌ Storage manager not found in orchestrator")
                return False
            
            # Test scan preparation (which should create session)
            print("\n4. Testing scan preparation...")
            scan_params = {
                'name': 'Integration Test Scan',
                'description': 'Testing storage integration',
                'x_range': (0, 50),
                'y_range': (0, 50),
                'z_positions': [0, 90, 180, 270],
                'c_positions': [-45, 0, 45]
            }
            
            # This should create a session in the storage system
            prepared = await orchestrator.prepare_scan(scan_params)
            print(f"✅ Scan preparation: {prepared}")
            
            # Shutdown
            print("\n5. Shutting down...")
            await orchestrator.shutdown()
            print("✅ Clean shutdown")
            
            print("\n🎉 Integration test passed!")
            return True
            
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_scan_integration())
    if success:
        print("\n✅ Storage integration is working!")
    else:
        print("\n💥 Integration needs fixes!")