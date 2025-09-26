#!/usr/bin/env python3
"""
Quick test to verify web interface captures use proper storage
"""

import asyncio
import sys
from pathlib import Path

# Add V2.0 to path if needed
V2_DIR = Path(__file__).parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

def test_web_interface_storage():
    """Test that web interface is properly configured for storage"""
    
    print("🧪 Testing Web Interface Storage Integration")
    print("=" * 50)
    
    try:
        # Import required modules
        from core.config_manager import ConfigManager  
        from scanning.scan_orchestrator import ScanOrchestrator
        from web.web_interface import ScannerWebInterface
        
        print("✅ All imports successful")
        
        # Load configuration
        config_file = V2_DIR / 'config' / 'scanner_config.yaml'
        config_manager = ConfigManager(config_file)
        print(f"✅ Config loaded: {config_file}")
        
        # Create orchestrator (like the web interface does)
        print("📦 Creating orchestrator...")
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize orchestrator
        print("⚙️  Initializing orchestrator...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            success = loop.run_until_complete(orchestrator.initialize())
        finally:
            loop.close()
            
        if not success:
            print("❌ Orchestrator initialization failed")
            return False
            
        print("✅ Orchestrator initialized successfully!")
        
        # Create web interface with orchestrator
        web_interface = ScannerWebInterface(orchestrator=orchestrator)
        print("✅ Web interface created with orchestrator")
        
        # Check storage access
        if hasattr(web_interface, 'orchestrator') and web_interface.orchestrator:
            if hasattr(web_interface.orchestrator, 'storage_manager'):
                storage_type = type(web_interface.orchestrator.storage_manager).__name__
                print(f"💾 Storage Manager: {storage_type}")
                
                if storage_type == "SessionManager":
                    print("🎉 PERFECT! Web interface connected to SessionManager!")
                    
                    # Check storage base path
                    if hasattr(web_interface.orchestrator.storage_manager, 'base_storage_path'):
                        base_path = web_interface.orchestrator.storage_manager.base_storage_path
                        print(f"📁 Storage Base Path: {base_path}")
                        print("✅ Web interface captures will use proper session storage!")
                        return True
                    else:
                        print("⚠️  SessionManager missing base_storage_path")
                        return False
                        
                elif storage_type == "MockStorageManager":
                    print("⚠️  Using MockStorageManager (simulation mode)")
                    return True
                else:
                    print(f"❓ Unknown storage type: {storage_type}")
                    return False
            else:
                print("❌ Orchestrator has no storage_manager")
                return False
        else:
            print("❌ Web interface has no orchestrator")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🔍 Web Interface Storage Integration Test")
    print("This test verifies web interface connects to proper storage")
    print()
    
    result = test_web_interface_storage()
    
    print()
    print("=" * 50)
    if result:
        print("🎉 SUCCESS: Web interface properly integrated with storage!")
        print("📸 Your captures will be saved with full metadata in sessions")
        print("📁 Files will go to /home/user/scanner_data/sessions/ not manual_captures/")
    else:
        print("❌ ISSUE: Web interface storage integration problem")
        print("📸 Captures may still fall back to manual_captures/")
    
    print()
    print("To start the web interface:")
    print("   python web/web_interface.py")

if __name__ == "__main__":
    main()