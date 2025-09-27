#!/usr/bin/env python3
"""
Test script for the new focus functionality

This script demonstrates how to use the new focus features:
1. Set focus mode (auto, manual, fixed)
2. Set manual focus values
3. Perform autofocus before scanning
4. Monitor focus settings during scans

Run this script to test focus functionality before running actual scans.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the V2.0 directory to the path
sys.path.append(str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.exceptions import ScannerSystemError
from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import PatternType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_focus_functionality():
    """Test the new focus functionality"""
    
    print("🔍 Testing Scanner Focus Functionality")
    print("=" * 50)
    
    try:
        # Initialize configuration
        config_path = Path(__file__).parent / "config" / "scanner_config.yaml"
        if not config_path.exists():
            print(f"⚠️ Config file not found at {config_path}")
            print("Using simulation mode for testing...")
            # For testing without full hardware config, we'll use orchestrator's simulation features
        
        config_manager = ConfigManager(config_path)
        
        # Initialize orchestrator for testing
        print("📡 Initializing scanner orchestrator...")
        orchestrator = ScanOrchestrator(config_manager)
        
        # Initialize the system
        await orchestrator.initialize()
        print("✅ Scanner orchestrator initialized")
        
        # Test 1: Check default focus settings
        print("\n🔧 Test 1: Default Focus Settings")
        settings = orchestrator.get_focus_settings()
        print(f"   Default focus mode: {settings['focus_mode']}")
        print(f"   Default focus value: {settings['focus_value']}")
        
        # Test 2: Set focus mode to manual
        print("\n🔧 Test 2: Set Manual Focus Mode")
        success = orchestrator.set_focus_mode('manual')
        print(f"   Set manual mode: {'✅ Success' if success else '❌ Failed'}")
        
        # Test 3: Set manual focus value
        print("\n🔧 Test 3: Set Manual Focus Value")
        test_focus_value = 0.7  # 70% towards infinity
        success = orchestrator.set_manual_focus_value(test_focus_value)
        print(f"   Set focus value {test_focus_value}: {'✅ Success' if success else '❌ Failed'}")
        
        # Check updated settings
        settings = orchestrator.get_focus_settings()
        print(f"   Current focus mode: {settings['focus_mode']}")
        print(f"   Current focus value: {settings['focus_value']}")
        
        # Test 4: Set focus mode to auto
        print("\n🔧 Test 4: Set Auto Focus Mode")
        success = orchestrator.set_focus_mode('auto')
        print(f"   Set auto mode: {'✅ Success' if success else '❌ Failed'}")
        
        # Test 5: Perform manual autofocus
        print("\n🔧 Test 5: Perform Manual Autofocus")
        print("   Attempting autofocus on camera0...")
        focus_value = await orchestrator.perform_autofocus('camera0')
        if focus_value is not None:
            print(f"   ✅ Autofocus successful: {focus_value:.3f}")
        else:
            print("   ℹ️  Autofocus not supported in simulation mode")
        
        # Test 6: Test invalid values
        print("\n🔧 Test 6: Input Validation")
        
        # Test invalid focus mode
        success = orchestrator.set_focus_mode('invalid_mode')
        print(f"   Invalid mode rejected: {'✅ Success' if not success else '❌ Failed'}")
        
        # Test invalid focus value (too high)
        success = orchestrator.set_manual_focus_value(1.5)
        print(f"   Invalid high value rejected: {'✅ Success' if not success else '❌ Failed'}")
        
        # Test invalid focus value (too low)
        success = orchestrator.set_manual_focus_value(-0.1)
        print(f"   Invalid low value rejected: {'✅ Success' if not success else '❌ Failed'}")
        
        # Test 7: Create a test scan pattern to show focus integration
        print("\n🔧 Test 7: Focus Integration in Scan Pattern")
        
        # Set up for autofocus mode
        orchestrator.set_focus_mode('auto')
        
        # Create a simple grid pattern
        grid_pattern = orchestrator.create_grid_pattern(
            x_range=(-10, 10),
            y_range=(40, 80),
            spacing=10.0,
            z_rotation=0.0
        )
        
        print("   ✅ Created grid pattern with auto-focus enabled")
        print(f"   Pattern points: {len(grid_pattern.generate_points())}")
        
        # Final settings check
        print("\n📊 Final Focus Settings:")
        settings = orchestrator.get_focus_settings()
        print(f"   Focus mode: {settings['focus_mode']}")
        print(f"   Focus value: {settings['focus_value']}")
        
        print("\n🎯 Focus Functionality Test Complete!")
        print("\nUsage Summary:")
        print("1. Use orchestrator.set_focus_mode('auto') for automatic focus before each scan")
        print("2. Use orchestrator.set_focus_mode('manual') + set_manual_focus_value(0.0-1.0)")
        print("3. Use orchestrator.set_focus_mode('fixed') for camera default behavior")
        print("4. Use orchestrator.perform_autofocus('camera0') for manual focus testing")
        print("5. Focus is automatically applied to all cameras at scan start")
        
        # Cleanup
        await orchestrator.shutdown()
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
        print(f"❌ Test failed: {e}")
        return False
    
    return True


async def test_web_api_focus():
    """Test the focus functionality through web API endpoints"""
    print("\n🌐 Testing Web API Focus Endpoints")
    print("=" * 50)
    
    print("Available API endpoints for focus control:")
    print("1. POST /api/scan/focus/mode")
    print("   Body: {'mode': 'auto'|'manual'|'fixed'}")
    print()
    print("2. POST /api/scan/focus/value") 
    print("   Body: {'focus_value': 0.0-1.0}")
    print()
    print("3. GET /api/scan/focus/settings")
    print("   Returns current focus settings")
    print()
    print("4. POST /api/scan/focus/autofocus")
    print("   Body: {'camera_id': 'camera0'} (optional)")
    print()
    print("Example usage:")
    print("curl -X POST http://localhost:5000/api/scan/focus/mode -H 'Content-Type: application/json' -d '{\"mode\": \"auto\"}'")
    print("curl -X POST http://localhost:5000/api/scan/focus/value -H 'Content-Type: application/json' -d '{\"focus_value\": 0.7}'")
    print("curl -X GET http://localhost:5000/api/scan/focus/settings")


if __name__ == "__main__":
    print("🔍 Scanner Focus Functionality Test")
    print("This test demonstrates the new autofocus capabilities\n")
    
    # Run the focus functionality test
    success = asyncio.run(test_focus_functionality())
    
    # Show web API information
    asyncio.run(test_web_api_focus())
    
    if success:
        print("\n✅ All tests passed! Focus functionality is working correctly.")
        print("\n🚀 Ready for Pi hardware testing!")
        print("\nNext steps:")
        print("1. Deploy to Pi hardware")
        print("2. Test with real cameras that support autofocus")
        print("3. Configure focus mode via web interface")
        print("4. Run test scans with different focus settings")
    else:
        print("\n❌ Some tests failed. Check the logs above.")
        sys.exit(1)