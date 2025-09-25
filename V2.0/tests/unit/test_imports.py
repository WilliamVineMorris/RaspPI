#!/usr/bin/env python3
"""
Quick import test for SessionManager
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

def test_imports():
    """Test if all modules can be imported"""
    try:
        print("Testing imports...")
        
        # Test core imports
        from storage.base import StorageManager, StorageMetadata, ScanSession, DataType
        print("✅ Storage base classes imported")
        
        from storage.session_manager import SessionManager
        print("✅ SessionManager imported")
        
        from core.config_manager import ConfigManager
        print("✅ ConfigManager imported")
        
        print("\n🎉 All imports successful!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✅ Ready for full testing!")
    else:
        print("\n💥 Fix import issues first!")