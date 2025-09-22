#!/usr/bin/env python3
"""
Quick test to validate GPIO cleanup fixes
"""

import asyncio
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_gpio_cleanup():
    """Test improved GPIO cleanup"""
    try:
        from lighting.gpio_led_controller import GPIOLEDController
        
        # Test configuration
        config = {
            'controller_type': 'gpio',
            'pwm_frequency': 1000,
            'zones': {
                'test_zone': {
                    'gpio_pins': [18, 19],
                    'led_type': 'cool_white',
                    'max_current_ma': 800,
                    'position': [0.0, 0.0, 100.0],
                    'direction': [0.0, 0.0, -1.0],
                    'beam_angle': 45.0,
                    'max_brightness': 1.0
                }
            }
        }
        
        logger.info("🧪 Testing GPIO LED controller cleanup...")
        
        # Create and initialize controller
        controller = GPIOLEDController(config)
        await controller.initialize()
        logger.info("✓ Controller initialized")
        
        # Test basic operations
        await controller.set_brightness('test_zone', 0.5)
        logger.info("✓ Brightness set")
        
        # First shutdown
        await controller.shutdown()
        logger.info("✓ First shutdown complete")
        
        # Second shutdown (should be safe)
        await controller.shutdown()
        logger.info("✓ Second shutdown complete (no errors)")
        
        logger.info("🎉 GPIO cleanup test PASSED - No exceptions!")
        return True
        
    except Exception as e:
        logger.error(f"❌ GPIO cleanup test FAILED: {e}")
        return False

async def main():
    """Main test"""
    success = await test_gpio_cleanup()
    
    if success:
        logger.info("🚀 All cleanup tests passed!")
    else:
        logger.error("💥 Cleanup tests failed!")
        
if __name__ == "__main__":
    asyncio.run(main())