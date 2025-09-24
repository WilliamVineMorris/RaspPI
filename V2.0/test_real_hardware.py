#!/usr/bin/env python3
"""
Force real hardware mode - no fallback to mock
This will show exactly what's preventing real hardware initialization
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

def force_real_hardware():
    """Force real hardware initialization with detailed error reporting"""
    
    print("\n=== Forcing Real Hardware Initialization ===")
    
    try:
        from scanning.scan_orchestrator import ScanOrchestrator
        from core.config_manager import ConfigManager
        from pathlib import Path
        import asyncio
        
        print("✅ Successfully imported scanner modules")
        
        # Create config
        config_file = Path(__file__).parent / "config" / "hardware_config.yaml"
        if not config_file.exists():
            print(f"❌ Config file not found: {config_file}")
            return False
            
        print(f"✅ Config file found: {config_file}")
        
        config_manager = ConfigManager(config_file)
        print("✅ Config manager created")
        
        # Create orchestrator
        orchestrator = ScanOrchestrator(config_manager)
        print("✅ ScanOrchestrator created")
        
        # Initialize
        print("🔄 Initializing scanner subsystems...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(orchestrator.initialize())
            print("✅ Real scanner orchestrator initialized successfully!")
            
            # Test motion controller
            if hasattr(orchestrator, 'motion_controller'):
                print("✅ Motion controller available")
                is_connected = orchestrator.motion_controller.refresh_connection_status()
                print(f"🔌 Motion controller connected: {is_connected}")
            else:
                print("❌ No motion controller found")
                
            return True
            
        finally:
            loop.close()
            
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("💡 This suggests missing scanner modules or dependencies")
        return False
        
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        print(f"🔍 Full error details:\n{traceback.format_exc()}")
        return False

if __name__ == "__main__":
    success = force_real_hardware()
    
    if success:
        print("\n🎉 Real hardware initialization successful!")
        print("The web interface should use real motion controller.")
    else:
        print("\n❌ Real hardware initialization failed.")
        print("This is why the system falls back to mock mode.")
        print("\nCommon issues:")
        print("  - FluidNC not connected to /dev/ttyUSB0")
        print("  - Serial port permissions")
        print("  - Missing scanner module dependencies")
    
    sys.exit(0 if success else 1)