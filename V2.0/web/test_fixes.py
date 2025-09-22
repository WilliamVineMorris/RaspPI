#!/usr/bin/env python3
"""
Quick test script to verify web interface fixes
"""

import sys
import os
from pathlib import Path

# Add project paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

def test_web_interface():
    """Test the web interface can be imported and initialized"""
    try:
        print("Testing web interface imports...")
        
        # Test import
        from web_interface import ScannerWebInterface
        print("✅ Web interface import successful")
        
        # Test initialization with mock orchestrator
        from start_web_interface import create_mock_orchestrator
        mock_orchestrator = create_mock_orchestrator()
        print("✅ Mock orchestrator created")
        
        # Test web interface creation
        web_interface = ScannerWebInterface(orchestrator=mock_orchestrator)
        print("✅ Web interface initialized")
        
        # Test status method
        status = web_interface._get_system_status()
        print(f"✅ Status method works: {status['system']['status']}")
        
        print("\n🎉 All tests passed! Web interface is ready.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("🧪 Web Interface Fix Verification")
    print("=" * 60)
    
    success = test_web_interface()
    
    if success:
        print("\n🚀 Ready to run:")
        print("python start_web_interface.py --mode mock --debug")
    else:
        print("\n🔧 Additional fixes needed.")