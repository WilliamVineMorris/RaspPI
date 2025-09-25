#!/usr/bin/env python3
"""
Test Script for Core Infrastructure

Tests the core infrastructure modules in isolation to ensure they work
correctly before being integrated into the main system.

Run this script to verify:
- Exception classes work correctly
- Event bus operates properly
- Configuration manager loads and validates config
- Logging system initializes correctly

Author: Scanner System Development
Created: September 2025
"""

import sys
import os
import tempfile
import yaml
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def get_user_input(prompt: str, default: str = "y") -> str:
    """Get user input with graceful handling for automated testing"""
    try:
        response = input(f"{prompt} [{default}]: ").strip()
        return response if response else default
    except (EOFError, KeyboardInterrupt):
        # Handle automated testing or Ctrl+C gracefully
        print(f"\nUsing default: {default}")
        return default

def test_exceptions():
    """Test custom exception classes"""
    print("Testing exception classes...")
    
    from core.exceptions import (
        ScannerSystemError, ConfigurationError, MotionControlError,
        create_hardware_error, create_motion_error
    )
    
    # Test basic exception
    try:
        raise ScannerSystemError("Test error", error_code="TEST001", module="test")
    except ScannerSystemError as e:
        assert "Test error" in str(e)
        assert e.error_code == "TEST001"
        assert e.module == "test"
        print(f"  ✓ Basic exception: {e}")
    
    # Test derived exception
    try:
        raise ConfigurationError("Config test error")
    except ConfigurationError as e:
        print(f"  ✓ Configuration exception: {e}")
    
    # Test factory functions
    error = create_hardware_error("Hardware test", "test_module", "HW001")
    print(f"  ✓ Factory function: {error}")
    
    print("Exception tests passed!\n")


def test_events():
    """Test event bus system"""
    print("Testing event bus...")
    
    from core.events import EventBus, EventConstants, ScannerEvent, EventPriority
    
    # Create event bus
    event_bus = EventBus()
    
    # Test data
    received_events = []
    
    def test_callback(event: ScannerEvent):
        received_events.append(event)
        print(f"  Received event: {event}")
    
    # Test subscription
    success = event_bus.subscribe(EventConstants.SYSTEM_STARTUP, test_callback, "test_subscriber")
    assert success, "Failed to subscribe to event"
    print("  ✓ Event subscription successful")
    
    # Test publishing
    success = event_bus.publish(
        EventConstants.SYSTEM_STARTUP,
        {"test": "data"},
        "test_module",
        EventPriority.HIGH
    )
    assert success, "Failed to publish event"
    assert len(received_events) == 1, "Event not received"
    print("  ✓ Event publishing successful")
    
    # Test event data
    event = received_events[0]
    assert event.event_type == EventConstants.SYSTEM_STARTUP
    assert event.data["test"] == "data"
    assert event.source_module == "test_module"
    assert event.priority == EventPriority.HIGH
    print("  ✓ Event data correct")
    
    # Test statistics
    stats = event_bus.get_stats()
    assert stats['events_published'] >= 1
    assert stats['events_processed'] >= 1
    print(f"  ✓ Event statistics: {stats}")
    
    print("Event bus tests passed!\n")


def test_config_manager():
    """Test configuration manager"""
    print("Testing configuration manager...")
    
    from core.config_manager import ConfigManager
    from core.exceptions import ConfigurationNotFoundError
    
    # Create temporary config file
    test_config = {
        'system': {
            'log_level': 'INFO',
            'debug_mode': False
        },
        'motion': {
            'controller': {
                'port': '/dev/ttyUSB0'
            },
            'axes': {
                'x_axis': {
                    'type': 'linear',
                    'units': 'mm',
                    'min_limit': 0.0,
                    'max_limit': 200.0,
                    'max_feedrate': 1000
                },
                'y_axis': {
                    'type': 'linear',
                    'units': 'mm',
                    'min_limit': 0.0,
                    'max_limit': 200.0,
                    'max_feedrate': 1000
                },
                'z_axis': {
                    'type': 'rotational',
                    'units': 'degrees',
                    'min_limit': -999999,
                    'max_limit': 999999,
                    'max_feedrate': 360,
                    'continuous': True
                },
                'c_axis': {
                    'type': 'rotational',
                    'units': 'degrees',
                    'min_limit': -90.0,
                    'max_limit': 90.0,
                    'max_feedrate': 180
                }
            }
        },
        'cameras': {
            'camera_1': {
                'port': 0,
                'resolution': {
                    'capture': [3280, 2464],
                    'preview': [1280, 720]
                }
            },
            'camera_2': {
                'port': 1,
                'resolution': {
                    'capture': [3280, 2464],
                    'preview': [1280, 720]
                }
            }
        },
        'lighting': {
            'led_zones': {
                'zone_1': {
                    'gpio_pin': 18,
                    'max_intensity': 85.0
                },
                'zone_2': {
                    'gpio_pin': 19,
                    'max_intensity': 85.0
                }
            }
        },
        'web_interface': {
            'port': 5000
        }
    }
    
    # Write temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(test_config, f)
        temp_config_file = f.name
    
    try:
        # Test config loading
        config = ConfigManager(temp_config_file)
        print("  ✓ Configuration loaded successfully")
        
        # Test basic access
        log_level = config.get('system.log_level')
        assert log_level == 'INFO', f"Expected 'INFO', got '{log_level}'"
        print(f"  ✓ Basic config access: log_level = {log_level}")
        
        # Test default values
        missing_value = config.get('nonexistent.key', 'default')
        assert missing_value == 'default', "Default value not returned"
        print("  ✓ Default value handling works")
        
        # Test typed access
        axis_config = config.get_axis_config('x_axis')
        assert axis_config.type == 'linear'
        assert axis_config.max_limit == 200.0
        print(f"  ✓ Typed axis config: {axis_config}")
        
        # Test validation
        config.validate()
        print("  ✓ Configuration validation passed")
        
        # Test summary
        summary = config.get_summary()
        print(f"  ✓ Configuration summary: {summary}")
        
    finally:
        # Clean up
        os.unlink(temp_config_file)
    
    # Test missing file
    try:
        ConfigManager('/nonexistent/config.yaml')
        assert False, "Should have raised ConfigurationNotFoundError"
    except ConfigurationNotFoundError:
        print("  ✓ Missing file error handling works")
    
    print("Configuration manager tests passed!\n")


def test_logging():
    """Test logging setup"""
    print("Testing logging setup...")
    
    from core.logging_setup import setup_logging, get_logger
    
    # Create temporary log directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Setup logging
        logger = setup_logging(
            log_level="DEBUG",
            log_dir=Path(temp_dir),
            enable_console=False,  # Disable console for test
            enable_file=True
        )
        
        print("  ✓ Logging setup successful")
        
        # Test module logger
        test_logger = get_logger('test_component', 'test_module')
        test_logger.info("Test log message")
        test_logger.warning("Test warning message")
        test_logger.error("Test error message")
        
        print("  ✓ Module logger works")
        
        # Check log files were created
        log_files = list(Path(temp_dir).glob("*.log"))
        assert len(log_files) > 0, "No log files created"
        print(f"  ✓ Log files created: {[f.name for f in log_files]}")
        
        # Check log content
        main_log = Path(temp_dir) / "scanner_system.log"
        if main_log.exists():
            content = main_log.read_text()
            assert "Test log message" in content, "Log message not found in file"
            print("  ✓ Log content verified")
    
    print("Logging tests passed!\n")


def test_integration():
    """Test integration between modules"""
    print("Testing module integration...")
    
    from core.config_manager import ConfigManager
    from core.logging_setup import setup_simple_logging
    from core.events import global_event_bus, EventConstants
    from core.exceptions import ScannerSystemError
    
    # Setup simple logging
    logger = setup_simple_logging("INFO")
    
    # Test that modules can work together
    try:
        # Publish system startup event
        global_event_bus.publish(
            EventConstants.SYSTEM_STARTUP,
            {"test": "integration"},
            "integration_test"
        )
        
        logger.info("Integration test completed successfully")
        print("  ✓ Modules integrate correctly")
        
    except Exception as e:
        raise ScannerSystemError(f"Integration test failed: {e}")
    
    print("Integration tests passed!\n")


def main():
    """Run all core infrastructure tests"""
    print("=" * 60)
    print("Core Infrastructure Test Suite")
    print("=" * 60)
    print("\nThis will test the core infrastructure components:")
    print("- Exception handling system")
    print("- Event bus communication")
    print("- Configuration management")
    print("- Logging system")
    print("- Module integration")
    
    # Check if running in interactive mode
    interactive = get_user_input("\nRun tests interactively?", "y").lower() in ['y', 'yes']
    
    if interactive:
        print("\n📝 Note: This test suite creates temporary files and logs.")
        print("   No permanent changes will be made to your system.")
        
        proceed = get_user_input("Proceed with tests?", "y").lower()
        if proceed not in ['y', 'yes']:
            print("Tests cancelled.")
            return False
    
    print("\n" + "=" * 60)
    print("Starting Tests...")
    print("=" * 60)
    
    try:
        # Run tests with progress indicators
        print("\n[1/5] Testing exception system...")
        test_exceptions()
        
        if interactive:
            get_user_input("Press Enter to continue to event bus tests")
        
        print("[2/5] Testing event bus...")
        test_events()
        
        if interactive:
            get_user_input("Press Enter to continue to configuration tests")
        
        print("[3/5] Testing configuration manager...")
        test_config_manager()
        
        if interactive:
            get_user_input("Press Enter to continue to logging tests")
        
        print("[4/5] Testing logging system...")
        test_logging()
        
        if interactive:
            get_user_input("Press Enter to continue to integration tests")
        
        print("[5/5] Testing module integration...")
        test_integration()
        
        print("=" * 60)
        print("🎉 ALL CORE INFRASTRUCTURE TESTS PASSED!")
        print("=" * 60)
        print("✅ Exception system: Working correctly")
        print("✅ Event bus: Working correctly") 
        print("✅ Configuration manager: Working correctly")
        print("✅ Logging system: Working correctly")
        print("✅ Module integration: Working correctly")
        print("=" * 60)
        print("🚀 The core modules are ready for the next development phase!")
        print("   You can now proceed to implement the abstract interfaces.")
        print("=" * 60)
        
        if interactive:
            get_user_input("\nPress Enter to exit")
        
        return True
        
    except Exception as e:
        print("=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        
        if interactive:
            show_traceback = get_user_input("Show detailed error traceback?", "y").lower()
            if show_traceback in ['y', 'yes']:
                import traceback
                traceback.print_exc()
        else:
            import traceback
            traceback.print_exc()
            
        print("\n💡 Troubleshooting tips:")
        print("   - Ensure all required dependencies are installed (see requirements.txt)")
        print("   - Check that you're in the correct directory (RaspPI/V2.0)")
        print("   - Verify Python version is 3.10 or higher")
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)