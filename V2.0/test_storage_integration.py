#!/usr/bin/env python3
"""
Quick test to verify proper storage system integration
This will confirm whether the web interface is using SessionManager or fallback storage
"""

import asyncio
import sys
from pathlib import Path

# Add V2.0 to path if needed
V2_DIR = Path(__file__).parent
if str(V2_DIR) not in sys.path:
    sys.path.insert(0, str(V2_DIR))

async def test_storage_integration():
    """Test that orchestrator properly initializes with storage"""
    
    print("🔍 Testing Storage System Integration...")
    print("=" * 50)
    
    try:
        # Import required modules
        from core.config_manager import ConfigManager
        from scanning.scan_orchestrator import ScanOrchestrator
        from web.web_interface import ScannerWebInterface
        
        print("✅ All imports successful")
        
        # Load configuration
        config_file = V2_DIR / 'config' / 'scanner_config.yaml'
        if not config_file.exists():
            print(f"❌ Config file not found: {config_file}")
            return False
            
        config_manager = ConfigManager(config_file)
        print(f"✅ Config loaded from: {config_file}")
        
        # Check storage configuration
        storage_base = config_manager.get('storage.base_path', 'NOT_CONFIGURED')
        print(f"📁 Storage base path: {storage_base}")
        
        # Create orchestrator
        print("📦 Creating orchestrator...")
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize orchestrator
        print("⚙️  Initializing orchestrator...")
        success = await orchestrator.initialize()
        
        if success:
            print("✅ Orchestrator initialized successfully!")
            
            # Check storage manager type
            if hasattr(orchestrator, 'storage_manager'):
                storage_type = type(orchestrator.storage_manager).__name__
                print(f"💾 Storage Manager Type: {storage_type}")
                
                if storage_type == "SessionManager":
                    print("🎉 PERFECT! Using real SessionManager with full metadata!")
                elif storage_type == "MockStorageManager":
                    print("⚠️  Using MockStorageManager (simulation mode)")
                else:
                    print(f"🤔 Unknown storage manager type: {storage_type}")
            else:
                print("❌ No storage_manager attribute found")
                
            # Test web interface creation
            print("🌐 Testing web interface with orchestrator...")
            web_interface = ScannerWebInterface(orchestrator=orchestrator)
            print("✅ Web interface created with orchestrator!")
            
            # Check if web interface has proper storage access
            if hasattr(web_interface, 'orchestrator') and web_interface.orchestrator is not None:
                if hasattr(web_interface.orchestrator, 'storage_manager'):
                    print("🎯 Web interface has access to storage system!")
                    return True
                else:
                    print("❌ Web interface orchestrator missing storage_manager")
                    return False
            else:
                print("❌ Web interface has no orchestrator")
                return False
                
        else:
            print("❌ Orchestrator initialization failed")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test function"""
    print("🧪 Storage Integration Test")
    print("This will verify if the web interface properly connects to storage")
    print()
    
    # Run the async test
    result = asyncio.run(test_storage_integration())
    
    print()
    print("=" * 50)
    if result:
        print("🎉 SUCCESS: Storage system is properly integrated!")
        print("💡 Your captures will use SessionManager with full metadata")
        print("📁 Files will be organized in sessions with complete metadata")
    else:
        print("❌ ISSUE: Storage system integration has problems")
        print("💡 Captures may fall back to manual storage")
        print("🔧 Check the error messages above for details")
    
    print()
    print("To start web interface with storage:")
    print("   python web/web_interface.py")
    print("or:")
    print("   python run_web_interface.py")

if __name__ == "__main__":
    main()