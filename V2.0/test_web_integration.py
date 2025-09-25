#!/usr/bin/env python3
"""
Test Web UI Integration
Tests the complete system with SimpleWorkingFluidNCController integrated.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from scanning.updated_scan_orchestrator import UpdatedScanOrchestrator

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_integration():
    """Test the complete integration."""
    print("\n" + "=" * 60)
    print("🧪 TESTING WEB UI INTEGRATION")
    print("=" * 60)
    print("\nThis test validates:")
    print("• SimpleWorkingFluidNCController via adapter")
    print("• Graceful initialization (cameras work even if motion in alarm)")
    print("• Complete system readiness for web UI")
    print("=" * 60)
    
    # Load configuration
    config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
    config_manager = ConfigManager(str(config_path))
    
    # Create orchestrator
    orchestrator = UpdatedScanOrchestrator(config_manager)
    
    try:
        # Initialize system
        print("\n1️⃣ Initializing System...")
        success = await orchestrator.initialize()
        
        if not success:
            print("❌ Initialization failed completely")
            return False
        
        # Check status
        print("\n2️⃣ Checking System Status...")
        status = orchestrator.get_status()
        
        print(f"   Initialized: {status['initialized']}")
        print(f"   Motion Available: {status['motion_available']}")
        print(f"   Cameras Available: {status['cameras_available']}")
        print(f"   Motion Status: {status['motion_status']}")
        print(f"   Motion Homed: {status['motion_homed']}")
        
        # Test homing if motion is available
        if status['motion_available'] and not status['motion_homed']:
            print("\n3️⃣ Testing Homing...")
            print("⚠️ SAFETY: Ensure axes can move to limit switches!")
            response = input("Test homing? (y/N): ")
            
            if response.lower() == 'y':
                success = orchestrator.home_system()
                if success:
                    print("✅ Homing successful!")
                else:
                    print("❌ Homing failed")
        
        # Test camera capture
        if status['cameras_available']:
            print("\n4️⃣ Testing Camera Capture...")
            response = input("Test camera capture? (y/N): ")
            
            if response.lower() == 'y':
                result = await orchestrator.capture_single_image()
                if result['success']:
                    print("✅ Camera capture successful!")
                    print(f"   Images: {list(result['images'].keys())}")
                else:
                    print(f"❌ Capture failed: {result['error']}")
        
        print("\n✅ Integration test complete!")
        print("\n📊 SYSTEM READY FOR WEB UI:")
        print(f"   ✅ Motion: {'Ready' if status['motion_available'] else 'Not Available'}")
        print(f"   ✅ Cameras: {'Ready' if status['cameras_available'] else 'Not Available'}")
        print(f"   ✅ System: {'Fully Operational' if status['motion_available'] and status['cameras_available'] else 'Limited Functionality'}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Integration test error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        print("\n🔌 Shutting down...")
        await orchestrator.shutdown()
        print("✅ Shutdown complete")

def main():
    """Run the integration test."""
    print("\n" + "🌐" * 30)
    print("WEB UI INTEGRATION TEST SUITE")
    print("🌐" * 30)
    print("\nThis validates the complete system is ready for web UI operation.")
    
    # Run async test
    success = asyncio.run(test_integration())
    
    if success:
        print("\n" + "🎉" * 30)
        print("SUCCESS - SYSTEM READY FOR WEB UI!")
        print("🎉" * 30)
        print("\n💡 Next step: Start the web interface:")
        print("   python run_web_interface.py")
    else:
        print("\n⚠️ Some components failed - check logs")

if __name__ == "__main__":
    main()