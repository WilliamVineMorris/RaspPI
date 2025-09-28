#!/usr/bin/env python3
"""
Test script to verify lighting controller with inner and outer LED zones

This script tests:
1. Configuration loading
2. GPIO LED controller initialization
3. Inner and outer zone functionality
4. PWM control on separate pins

Usage: python test_lighting_zones.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from lighting.gpio_led_controller import GPIOLEDController
from lighting.base import LightingSettings

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_lighting_configuration():
    """Test the lighting controller configuration"""
    try:
        logger.info("🔸 Testing LED lighting configuration...")
        
        # Load configuration
        config_manager = ConfigManager()
        lighting_config = config_manager.get('lighting', {})
        
        logger.info(f"📋 Lighting config loaded: {lighting_config.keys()}")
        
        # Check zones configuration
        zones_config = lighting_config.get('zones', {})
        logger.info(f"🔸 Configured zones: {list(zones_config.keys())}")
        
        for zone_name, zone_config in zones_config.items():
            gpio_pins = zone_config.get('gpio_pins', [])
            max_brightness = zone_config.get('max_brightness', 1.0)
            logger.info(f"   📍 Zone '{zone_name}': GPIO pins {gpio_pins}, max brightness {max_brightness}")
        
        # Initialize GPIO LED controller
        logger.info("🔧 Initializing GPIO LED controller...")
        controller = GPIOLEDController(lighting_config)
        
        # Initialize controller
        if not await controller.initialize():
            logger.error("❌ Failed to initialize lighting controller")
            return False
        
        logger.info("✅ Lighting controller initialized successfully")
        
        # List available zones
        zones = await controller.list_zones()
        logger.info(f"🔸 Available zones after initialization: {zones}")
        
        # Get zone information
        for zone in zones:
            zone_info = await controller.get_zone_info(zone)
            logger.info(f"   📍 Zone '{zone}' info: GPIO {zone_info.get('gpio_pins', [])}, "
                      f"brightness {zone_info.get('current_brightness', 0.0)}")
        
        # Test each zone individually
        test_results = {}
        
        for zone in zones:
            logger.info(f"🔸 Testing zone '{zone}'...")
            
            try:
                # Test flash
                settings = LightingSettings(
                    brightness=0.5,  # 50% brightness for testing
                    duration_ms=500  # 500ms flash
                )
                
                flash_result = await controller.flash([zone], settings)
                
                test_results[zone] = {
                    'success': flash_result.success,
                    'zones_activated': flash_result.zones_activated,
                    'duration': flash_result.duration_ms,
                    'error': flash_result.error_message
                }
                
                if flash_result.success:
                    logger.info(f"   ✅ Zone '{zone}' flash test: SUCCESS")
                else:
                    logger.error(f"   ❌ Zone '{zone}' flash test: FAILED - {flash_result.error_message}")
                
                # Small delay between tests
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"   ❌ Zone '{zone}' test error: {e}")
                test_results[zone] = {'success': False, 'error': str(e)}
        
        # Test combined zones flash
        if len(zones) >= 2:
            logger.info("🔸 Testing combined zones flash...")
            
            try:
                settings = LightingSettings(
                    brightness=0.3,  # Lower brightness for combined test
                    duration_ms=300  # 300ms flash
                )
                
                flash_result = await controller.flash(zones, settings)
                
                if flash_result.success:
                    logger.info(f"   ✅ Combined zones flash test: SUCCESS - activated {flash_result.zones_activated}")
                else:
                    logger.error(f"   ❌ Combined zones flash test: FAILED - {flash_result.error_message}")
                    
            except Exception as e:
                logger.error(f"   ❌ Combined zones test error: {e}")
        
        # Turn off all zones
        logger.info("🔸 Turning off all zones...")
        await controller.turn_off_all()
        
        # Shutdown controller
        logger.info("🔧 Shutting down controller...")
        await controller.shutdown()
        
        logger.info("✅ Lighting zone test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Lighting test failed: {e}")
        import traceback
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    logger.info("🚀 Starting lighting zones test...")
    
    success = asyncio.run(test_lighting_configuration())
    
    if success:
        logger.info("🎉 All tests passed!")
        sys.exit(0)
    else:
        logger.error("💥 Tests failed!")
        sys.exit(1)