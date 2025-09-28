#!/usr/bin/env python3
"""
LED Zone Test Script

Test the GPIO LED controller with the configured inner and outer zones.
This script verifies that both zones can be controlled independently via PWM.

GPIO Configuration:
- Inner zone: GPIO 12 (PWM-capable)
- Outer zone: GPIO 13 (PWM-capable)

Usage:
    python test_led_zones.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from lighting.gpio_led_controller import GPIOLEDController
from lighting.base import LightingSettings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_led_zones():
    """Test both inner and outer LED zones"""
    try:
        logger.info("🔸 LED Zone Test Starting...")
        
        # Load configuration
        config_file = Path(__file__).parent / 'config' / 'scanner_config.yaml'
        config_manager = ConfigManager(config_file)
        lighting_config = config_manager.get('lighting', {})
        
        logger.info(f"📋 Lighting config loaded: {len(lighting_config.get('zones', {}))} zones")
        
        # Initialize LED controller
        led_controller = GPIOLEDController(lighting_config)
        
        # Initialize the controller
        if not await led_controller.initialize():
            logger.error("❌ Failed to initialize LED controller")
            return False
        
        logger.info("✅ LED controller initialized successfully")
        
        # List available zones
        if hasattr(led_controller, 'list_zones'):
            zones = await led_controller.list_zones()
            logger.info(f"🔸 Available zones: {zones}")
        else:
            zones = list(led_controller.zone_configs.keys())
            logger.info(f"🔸 Configured zones: {zones}")
        
        # Test each zone individually
        test_results = {}
        
        for zone_id in ['inner', 'outer']:
            if zone_id in zones:
                logger.info(f"🔸 Testing zone: {zone_id}")
                
                try:
                    # Test zone info
                    if hasattr(led_controller, 'get_zone_info'):
                        zone_info = await led_controller.get_zone_info(zone_id)
                        logger.info(f"   📋 Zone '{zone_id}' info: GPIO pins {zone_info.get('gpio_pins', 'unknown')}")
                    
                    # Test flash
                    settings = LightingSettings(
                        brightness=0.5,  # 50% brightness for safety
                        duration_ms=500   # 500ms flash
                    )
                    
                    flash_result = await led_controller.flash([zone_id], settings)
                    
                    if flash_result.success:
                        logger.info(f"✅ Zone '{zone_id}' flash test: SUCCESS")
                        test_results[zone_id] = 'SUCCESS'
                    else:
                        logger.error(f"❌ Zone '{zone_id}' flash test: FAILED - {flash_result.error_message}")
                        test_results[zone_id] = f'FAILED: {flash_result.error_message}'
                    
                    # Brief pause between tests
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"❌ Zone '{zone_id}' test error: {e}")
                    test_results[zone_id] = f'ERROR: {e}'
            else:
                logger.warning(f"⚠️ Zone '{zone_id}' not available")
                test_results[zone_id] = 'NOT_AVAILABLE'
        
        # Test both zones simultaneously
        if 'inner' in zones and 'outer' in zones:
            logger.info("🔸 Testing both zones simultaneously...")
            
            try:
                settings = LightingSettings(
                    brightness=0.3,  # Lower brightness for simultaneous test
                    duration_ms=300   # 300ms flash
                )
                
                flash_result = await led_controller.flash(['inner', 'outer'], settings)
                
                if flash_result.success:
                    logger.info("✅ Simultaneous zone flash test: SUCCESS")
                    test_results['simultaneous'] = 'SUCCESS'
                else:
                    logger.error(f"❌ Simultaneous zone flash test: FAILED - {flash_result.error_message}")
                    test_results['simultaneous'] = f'FAILED: {flash_result.error_message}'
                    
            except Exception as e:
                logger.error(f"❌ Simultaneous test error: {e}")
                test_results['simultaneous'] = f'ERROR: {e}'
        
        # Cleanup
        await led_controller.shutdown()
        logger.info("🔄 LED controller shutdown complete")
        
        # Summary
        logger.info("📊 LED Zone Test Results:")
        for zone, result in test_results.items():
            logger.info(f"   🔸 {zone}: {result}")
        
        # Overall success
        success_count = sum(1 for result in test_results.values() if result == 'SUCCESS')
        total_tests = len(test_results)
        
        if success_count == total_tests:
            logger.info("🎉 All LED zone tests PASSED!")
            return True
        else:
            logger.warning(f"⚠️ LED zone tests: {success_count}/{total_tests} passed")
            return False
            
    except Exception as e:
        logger.error(f"❌ LED zone test failed: {e}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(test_led_zones())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🔄 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Test script error: {e}")
        sys.exit(1)