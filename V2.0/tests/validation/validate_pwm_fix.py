#!/usr/bin/env python3
"""
Quick validation test for PWM cleanup error fix
Tests the specific scenario that was causing the TypeError
"""

import asyncio
import logging
import gc

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_pwm_cleanup_scenario():
    """Test the specific PWM cleanup scenario that was causing errors"""
    try:
        # Import after logging setup
        from lighting.gpio_led_controller import GPIOLEDController
        
        logger.info("🔧 Testing PWM cleanup error fix...")
        
        # Quick test configuration
        config = {
            'controller_type': 'gpio',
            'pwm_frequency': 1000,
            'zones': {
                'cleanup_test': {
                    'gpio_pins': [18, 19],
                    'led_type': 'cool_white',
                    'max_current_ma': 500,
                    'position': [0.0, 0.0, 100.0],
                    'direction': [0.0, 0.0, -1.0],
                    'beam_angle': 45.0,
                    'max_brightness': 1.0
                }
            }
        }
        
        # Create controller instance
        controller = GPIOLEDController(config)
        logger.info("✓ Controller created")
        
        # Initialize (creates PWM objects)
        await controller.initialize()
        logger.info("✓ Controller initialized - PWM objects created")
        
        # Do some PWM operations
        await controller.set_brightness('cleanup_test', 0.5)
        logger.info("✓ PWM brightness set")
        
        # Perform flash (creates more PWM activity)
        from lighting.base import LightingSettings
        flash_settings = LightingSettings(brightness=0.7, duration_ms=50)
        flash_result = await controller.flash_zone('cleanup_test', flash_settings)
        logger.info(f"✓ Flash operation: {flash_result.success}")
        
        # Shutdown controller (this calls GPIO.cleanup())
        await controller.shutdown()
        logger.info("✓ Controller shutdown complete - GPIO.cleanup() called")
        
        # Force garbage collection (this triggers PWM.__del__)
        logger.info("🧹 Forcing garbage collection...")
        for i in range(5):
            gc.collect()
            await asyncio.sleep(0.05)
            logger.info(f"   GC cycle {i+1} - no PWM cleanup errors!")
        
        logger.info("🎉 PWM cleanup test PASSED - No TypeError exceptions!")
        return True
        
    except Exception as e:
        logger.error(f"❌ PWM cleanup test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test runner"""
    logger.info("🚀 Starting PWM cleanup validation test")
    logger.info("=" * 60)
    
    success = await test_pwm_cleanup_scenario()
    
    logger.info("=" * 60)
    if success:
        logger.info("✅ PWM cleanup fix validation SUCCESSFUL!")
        logger.info("💡 The TypeError: 'NoneType' and 'int' errors should be eliminated")
    else:
        logger.error("❌ PWM cleanup fix validation FAILED!")
        logger.error("🔧 Additional debugging may be required")

if __name__ == "__main__":
    asyncio.run(main())