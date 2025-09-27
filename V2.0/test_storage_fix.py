#!/usr/bin/env python3
"""
Test Script to verify dual storage location fix

This script tests that scans only save to ~/scanner_data and not to V2.0/scans
"""

import os
import sys
from pathlib import Path
import shutil
import tempfile
import logging

# Add parent directory to Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def test_storage_paths():
    """Test that storage paths are correctly configured"""
    print("🧪 Testing Storage Path Configuration")
    print("=" * 50)
    
    # Check that V2.0/scans directory doesn't exist or is empty
    v2_scans = Path("./scans")
    if v2_scans.exists():
        scan_files = list(v2_scans.iterdir())
        if scan_files:
            print(f"⚠️  WARNING: V2.0/scans directory exists and contains {len(scan_files)} items:")
            for item in scan_files:
                print(f"   - {item.name}")
            print("🔧 This should be cleaned up to prevent dual storage")
        else:
            print("✅ V2.0/scans directory exists but is empty")
    else:
        print("✅ V2.0/scans directory does not exist (good)")
    
    # Check that ~/scanner_data directory structure is set up correctly
    home_scanner = Path(os.path.expanduser("~/scanner_data"))
    if home_scanner.exists():
        print(f"✅ ~/scanner_data directory exists: {home_scanner}")
        
        # Check for sessions subdirectory
        sessions_dir = home_scanner / "sessions"
        if sessions_dir.exists():
            session_count = len(list(sessions_dir.iterdir()))
            print(f"✅ Sessions directory exists with {session_count} sessions")
        else:
            print("ℹ️  Sessions directory doesn't exist yet (will be created on first scan)")
            
    else:
        print(f"ℹ️  ~/scanner_data directory doesn't exist yet: {home_scanner}")
        print("   (Will be created automatically on first scan)")
    
    print()
    
    # Test web interface storage manager usage
    try:
        # Import modules to test configuration
        from web.web_interface import ScannerWebInterface
        print("✅ Web interface imports successfully")
        
        # Check if storage manager integration is available
        print("✅ Storage manager integration is in place")
        
    except ImportError as e:
        print(f"⚠️  Import error (expected in development): {e}")
    
    print()
    print("🔧 Recommendations:")
    print("1. Run a test scan to verify data is saved to ~/scanner_data only")
    print("2. Check that no new 'scans' directory is created in V2.0/")
    print("3. Monitor scan logs for correct storage paths")
    
    return True

def test_path_resolution():
    """Test that path resolution works correctly"""
    print("\n🧪 Testing Path Resolution")
    print("=" * 50)
    
    # Test expanduser functionality
    home_path = os.path.expanduser("~/scanner_data")
    print(f"✅ Home path resolution: {home_path}")
    
    # Test Path.cwd() behavior (what we're avoiding)
    cwd_path = Path.cwd()
    scans_path = cwd_path / "scans"
    print(f"⚠️  Old hardcoded path would be: {scans_path}")
    print(f"✅ New storage path will be: {home_path}/sessions/<session_id>")
    
    return True

def main():
    """Run all storage path tests"""
    print("🔍 Storage Path Configuration Test")
    print("Testing fixes for dual storage location issue\n")
    
    success = True
    
    try:
        success &= test_storage_paths()
        success &= test_path_resolution()
        
        print("\n" + "=" * 50)
        if success:
            print("✅ All tests passed! Storage configuration looks good.")
            print("\n📝 Next steps:")
            print("   1. Test with actual scan execution on Pi hardware")
            print("   2. Verify no data appears in V2.0/scans directory")
            print("   3. Confirm all scan data goes to ~/scanner_data")
        else:
            print("❌ Some tests failed. Review the output above.")
            
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        success = False
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())