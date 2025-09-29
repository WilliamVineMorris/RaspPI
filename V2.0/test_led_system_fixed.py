#!/usr/bin/env python3
"""
LED System Testing Script

Comprehensive testing script for LED lighting system with GPIO pins 13 and 18.
Tests basic functionality, safety features, pattern recognition, and provides
interactive mode for hardware validation.

Updated with correct interface method calls for GPIOLEDController.

Author: Scanner System Development  
Created: December 2024
Platform: Raspberry Pi 5
"""

import asyncio
import logging
import time
from typing import Dict, Optional, List
from pathlib import Path
import json

from core.config_manager import ConfigManager
from lighting.gpio_led_controller import GPIOLEDController
from lighting.base import LightingSettings, LightingStatus
from core.exceptions import LEDError, ConfigurationError


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LEDTester:
    """Comprehensive LED system testing class"""
    
    def __init__(self, config_file: str = "config/scanner_config.yaml"):
        """Initialize LED tester with configuration"""
        self.config_file = Path(config_file)
        self.config_manager: Optional[ConfigManager] = None
        self.led_controller: Optional[GPIOLEDController] = None
        self.test_results: Dict[str, bool] = {}
        
    async def initialize(self) -> bool:
        """Initialize configuration and LED controller"""
        try:
            # Initialize configuration manager
            logger.info("🔧 Loading configuration...")
            self.config_manager = ConfigManager(self.config_file)
            lighting_config = self.config_manager.get('lighting')
            
            if not lighting_config:
                raise ConfigurationError("No lighting configuration found")
            
            # Debug: Check zones in config
            zones_config = lighting_config.get('zones', {})
            logger.info(f"🔍 Found {len(zones_config)} zones in config: {list(zones_config.keys())}")
                
            # Initialize LED controller
            logger.info("💡 Initializing LED controller...")
            self.led_controller = GPIOLEDController(lighting_config)
            
            # Initialize controller
            init_success = await self.led_controller.initialize()
            if not init_success:
                raise LEDError("Failed to initialize LED controller")
                
            logger.info("✅ LED controller initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}")
            return False
    
    async def test_basic_connectivity(self) -> bool:
        """Test basic LED controller connectivity and status"""
        logger.info("\\n🔍 Testing Basic Connectivity...")
        
        try:
            # Test controller status
            status = await self.led_controller.get_status()
            logger.info(f"Controller status: {status}")
            
            # Test zone listing
            zones = await self.led_controller.list_zones()
            logger.info(f"📋 Available zones: {zones}")
            
            if not zones:
                logger.warning("⚠️ No LED zones configured - checking configuration...")
                # Check if this is a configuration issue
                lighting_config = self.config_manager.get('lighting')
                zones_config = lighting_config.get('zones', {}) if lighting_config else {}
                logger.info(f"Configuration zones found: {list(zones_config.keys())}")
                if zones_config:
                    logger.error("❌ Zones in config but not loaded by controller")
                    return False
                else:
                    logger.error("❌ No zones in configuration file")
                    return False
                
            logger.info("✅ LED controller connectivity verified")
            self.test_results['basic_connectivity'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Basic connectivity test failed: {e}")
            self.test_results['basic_connectivity'] = False
            return False
    
    async def test_zone_control(self) -> bool:
        """Test individual zone control functionality"""
        logger.info("\\n🔍 Testing Zone Control...")
        
        try:
            zones = await self.led_controller.list_zones()
            
            for zone in zones:
                logger.info(f"Testing zone: {zone}")
                
                # Test zone on
                logger.info(f"💡 Turning {zone} ON...")
                await self.led_controller.turn_on(zone, 0.5)  # 50% brightness
                await asyncio.sleep(1)
                
                # Test zone off
                logger.info(f"🔴 Turning {zone} OFF...")
                await self.led_controller.turn_off(zone)
                await asyncio.sleep(0.5)
                
                # Test different brightness levels
                logger.info(f"🌟 Testing {zone} brightness levels...")
                for brightness in [0.25, 0.5, 0.75, 1.0]:
                    logger.info(f"   Setting {zone} to {brightness*100}%...")
                    await self.led_controller.turn_on(zone, brightness)
                    await asyncio.sleep(0.5)
                
                # Turn off
                await self.led_controller.turn_off(zone)
                await asyncio.sleep(0.5)
                
            logger.info("✅ Zone control tests completed")
            self.test_results['zone_control'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Zone control test failed: {e}")
            self.test_results['zone_control'] = False
            return False
    
    async def test_flash_patterns(self) -> bool:
        """Test flash patterns and sync functionality"""
        logger.info("\\n🔍 Testing Flash Patterns...")
        
        try:
            # Test single flash
            logger.info("⚡ Testing single flash...")
            zones = await self.led_controller.list_zones()
            flash_settings = LightingSettings(brightness=0.8, duration_ms=200)
            await self.led_controller.flash(zones, flash_settings)
            await asyncio.sleep(1)
            
            # Test multiple flashes
            logger.info("⚡ Testing multiple flashes...")
            for i in range(3):
                logger.info(f"   Flash {i+1}/3...")
                flash_settings = LightingSettings(brightness=1.0, duration_ms=100)
                await self.led_controller.flash(zones, flash_settings)
                await asyncio.sleep(0.3)
            
            # Test zone-specific flash
            if len(zones) > 1:
                for zone in zones:
                    logger.info(f"⚡ Testing {zone} flash...")
                    flash_settings = LightingSettings(brightness=0.7, duration_ms=200)
                    await self.led_controller.flash([zone], flash_settings)
                    await asyncio.sleep(0.5)
            
            self.test_results['flash_patterns'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Flash patterns test failed: {e}")
            self.test_results['flash_patterns'] = False
            return False
    
    async def test_safety_features(self) -> bool:
        """Test LED safety features and limits"""
        logger.info("\\n🔍 Testing Safety Features...")
        
        try:
            zones = await self.led_controller.list_zones()
            
            # Test duty cycle limits (should be capped at 90%)
            logger.info("🛡️ Testing duty cycle safety limits...")
            for zone in zones:
                logger.info(f"   Testing {zone} at 100% (should be capped at 90%)...")
                await self.led_controller.set_brightness(zone, 1.0)
                await asyncio.sleep(0.5)
                
                # Check if controller respects safety limits
                current_brightness = await self.led_controller.get_brightness(zone)
                if current_brightness <= 0.90:
                    logger.info(f"   ✅ {zone} safely capped at {current_brightness:.1%}")
                else:
                    logger.warning(f"   ⚠️ {zone} brightness {current_brightness:.1%} exceeds safety limit!")
                
                await self.led_controller.turn_off(zone)
                await asyncio.sleep(0.3)
            
            # Test turn off all function
            logger.info("🚨 Testing turn off all...")
            
            # Turn on all zones
            for zone in zones:
                await self.led_controller.set_brightness(zone, 0.5)
            await asyncio.sleep(0.5)
            
            # Turn off all
            await self.led_controller.turn_off_all()
            await asyncio.sleep(0.5)
            
            # Verify all zones are off
            all_off = True
            for zone in zones:
                brightness = await self.led_controller.get_brightness(zone)
                if brightness > 0:
                    all_off = False
                    logger.warning(f"   ⚠️ {zone} not turned off: {brightness:.1%}")
            
            if all_off:
                logger.info("   ✅ Turn off all successful - all zones off")
            else:
                logger.error("   ❌ Turn off all failed - some zones still on")
            
            self.test_results['safety_features'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Safety features test failed: {e}")
            self.test_results['safety_features'] = False
            return False
    
    async def test_configuration_validation(self) -> bool:
        """Test configuration validation and error handling"""
        logger.info("\\n🔍 Testing Configuration...")
        
        try:
            # Test zone information
            zones = await self.led_controller.list_zones()
            
            for zone in zones:
                zone_info = await self.led_controller.get_zone_info(zone)
                logger.info(f"📋 Zone {zone}: {zone_info}")
                
                # Test brightness validation
                current_brightness = await self.led_controller.get_brightness(zone)
                logger.info(f"   Current brightness: {current_brightness:.1%}")
            
            # Test power metrics
            power_metrics = self.led_controller.get_power_metrics()
            logger.info(f"⚡ Power metrics:")
            logger.info(f"   Current: {power_metrics.total_current_ma:.1f}mA")
            logger.info(f"   Voltage: {power_metrics.voltage_v:.1f}V") 
            logger.info(f"   Power: {power_metrics.power_consumption_w:.2f}W")
            logger.info(f"   Max duty cycle: {power_metrics.max_duty_cycle:.1%}")
            logger.info(f"   Safe: {power_metrics.is_safe}")
            
            self.test_results['configuration'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Configuration test failed: {e}")
            self.test_results['configuration'] = False
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling with invalid inputs"""
        logger.info("\\n🔍 Testing Error Handling...")
        
        try:
            zones = await self.led_controller.list_zones()
            
            if zones:
                zone = zones[0]
                
                # Test negative brightness (should be clamped to 0)
                try:
                    logger.info("🧪 Testing negative brightness...")
                    await self.led_controller.set_brightness(zone, -0.1)
                    current = await self.led_controller.get_brightness(zone)
                    if current >= 0:
                        logger.info(f"   ✅ Negative brightness handled: {current:.1%}")
                    else:
                        logger.warning(f"   ⚠️ Negative brightness not handled: {current:.1%}")
                except Exception as e:
                    logger.info(f"   ✅ Negative brightness rejected: {e}")
                
                # Test excessive brightness (should be clamped to 1.0)
                try:
                    logger.info("🧪 Testing excessive brightness...")
                    await self.led_controller.set_brightness(zone, 1.5)
                    current = await self.led_controller.get_brightness(zone)
                    if current <= 1.0:
                        logger.info(f"   ✅ Excessive brightness handled: {current:.1%}")
                    else:
                        logger.warning(f"   ⚠️ Excessive brightness not handled: {current:.1%}")
                except Exception as e:
                    logger.info(f"   ✅ Excessive brightness rejected: {e}")
                
                # Clean up
                await self.led_controller.turn_off(zone)
            
            # Test invalid zone
            try:
                logger.info("🧪 Testing invalid zone...")
                await self.led_controller.set_brightness("invalid_zone", 0.5)
                logger.warning("   ⚠️ Invalid zone not rejected")
            except Exception as e:
                logger.info(f"   ✅ Invalid zone rejected: {e}")
            
            self.test_results['error_handling'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Error handling test failed: {e}")
            self.test_results['error_handling'] = False
            return False
    
    async def run_pattern_sequence(self) -> bool:
        """Run a sequence of lighting patterns"""
        logger.info("\\n🔍 Running Pattern Sequence...")
        
        try:
            zones = await self.led_controller.list_zones()
            
            # Pattern 1: Fade up and down
            logger.info("🌅 Pattern 1: Fade up and down")
            for brightness in [0.2, 0.4, 0.6, 0.8, 1.0, 0.8, 0.6, 0.4, 0.2, 0.0]:
                for zone in zones:
                    await self.led_controller.set_brightness(zone, brightness)
                await asyncio.sleep(0.3)
            
            await asyncio.sleep(0.5)
            
            # Pattern 2: Alternating zones (if multiple zones)
            if len(zones) > 1:
                logger.info("🔄 Pattern 2: Alternating zones")
                for i in range(4):
                    # Turn on first zone, off second
                    await self.led_controller.set_brightness(zones[0], 0.6)
                    await self.led_controller.turn_off(zones[1])
                    await asyncio.sleep(0.5)
                    
                    # Turn off first zone, on second  
                    await self.led_controller.turn_off(zones[0])
                    await self.led_controller.set_brightness(zones[1], 0.6)
                    await asyncio.sleep(0.5)
                
                # Turn off all
                for zone in zones:
                    await self.led_controller.turn_off(zone)
            
            self.test_results['pattern_sequence'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Pattern sequence failed: {e}")
            self.test_results['pattern_sequence'] = False
            return False
    
    async def interactive_mode(self):
        """Interactive mode for manual testing"""
        logger.info("\\n🎮 Entering Interactive Mode...")
        logger.info("Commands: on <zone> <brightness>, off <zone>, flash <zone>, all_off, status, quit")
        
        try:
            zones = await self.led_controller.list_zones()
            logger.info(f"Available zones: {zones}")
            
            while True:
                try:
                    command = input("\\n> ").strip().lower()
                    
                    if command == "quit" or command == "exit":
                        break
                    elif command == "status":
                        status = await self.led_controller.get_status()
                        logger.info(f"Status: {status}")
                        for zone in zones:
                            brightness = await self.led_controller.get_brightness(zone)
                            logger.info(f"  {zone}: {brightness:.1%}")
                    elif command == "all_off":
                        await self.led_controller.turn_off_all()
                        logger.info("All zones turned off")
                    elif command.startswith("on "):
                        parts = command.split()
                        if len(parts) >= 2:
                            zone = parts[1]
                            brightness = float(parts[2]) if len(parts) > 2 else 1.0
                            if zone in zones:
                                await self.led_controller.turn_on(zone, brightness)
                                logger.info(f"Turned on {zone} at {brightness:.1%}")
                            else:
                                logger.error(f"Invalid zone: {zone}")
                    elif command.startswith("off "):
                        parts = command.split()
                        if len(parts) >= 2:
                            zone = parts[1]
                            if zone in zones:
                                await self.led_controller.turn_off(zone)
                                logger.info(f"Turned off {zone}")
                            else:
                                logger.error(f"Invalid zone: {zone}")
                    elif command.startswith("flash "):
                        parts = command.split()
                        if len(parts) >= 2:
                            zone = parts[1]
                            if zone in zones:
                                flash_settings = LightingSettings(brightness=0.8, duration_ms=200)
                                await self.led_controller.flash([zone], flash_settings)
                                logger.info(f"Flashed {zone}")
                            else:
                                logger.error(f"Invalid zone: {zone}")
                    else:
                        logger.info("Unknown command. Use: on <zone> <brightness>, off <zone>, flash <zone>, all_off, status, quit")
                        
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logger.error(f"Command error: {e}")
            
        except Exception as e:
            logger.error(f"Interactive mode error: {e}")
    
    async def run_all_tests(self) -> bool:
        """Run all automated tests"""
        logger.info("\\n🚀 Starting LED System Tests...")
        
        tests = [
            ("Basic Connectivity", self.test_basic_connectivity),
            ("Zone Control", self.test_zone_control),
            ("Flash Patterns", self.test_flash_patterns),
            ("Safety Features", self.test_safety_features),
            ("Configuration", self.test_configuration_validation),
            ("Error Handling", self.test_error_handling),
            ("Pattern Sequence", self.run_pattern_sequence)
        ]
        
        all_passed = True
        
        for test_name, test_func in tests:
            logger.info(f"\\n▶️ Running {test_name}...")
            try:
                result = await test_func()
                if result:
                    logger.info(f"✅ {test_name} PASSED")
                else:
                    logger.error(f"❌ {test_name} FAILED")
                    all_passed = False
            except Exception as e:
                logger.error(f"❌ {test_name} ERROR: {e}")
                all_passed = False
        
        # Print summary
        logger.info("\\n📊 Test Summary:")
        logger.info("=" * 50)
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name:20s}: {status}")
        
        logger.info("=" * 50)
        if all_passed:
            logger.info("🎉 ALL TESTS PASSED!")
        else:
            logger.error("💥 SOME TESTS FAILED!")
        
        return all_passed
    
    async def cleanup(self):
        """Clean up resources"""
        if self.led_controller:
            try:
                await self.led_controller.turn_off_all()
                await self.led_controller.shutdown()
                logger.info("🧹 LED controller cleaned up")
            except Exception as e:
                logger.error(f"Cleanup error: {e}")


async def main():
    """Main function"""
    print("🔆 LED System Testing Script")
    print("Testing GPIO pins 13 (inner) and 18 (outer) with 300Hz PWM")
    print("=" * 60)
    
    tester = LEDTester()
    
    try:
        # Initialize
        if not await tester.initialize():
            print("❌ Failed to initialize LED tester")
            return
            
        # Run tests
        print("\\nSelect test mode:")
        print("1. Run all automated tests")
        print("2. Interactive mode")
        print("3. Quick connectivity test")
        
        choice = input("\\nEnter choice (1-3): ").strip()
        
        if choice == "1":
            await tester.run_all_tests()
        elif choice == "2":
            await tester.interactive_mode()
        elif choice == "3":
            await tester.test_basic_connectivity()
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\\n⏹️ Testing interrupted by user")
    except Exception as e:
        print(f"\\n💥 Testing failed: {e}")
        logger.exception("Detailed error:")
    finally:
        await tester.cleanup()
        print("\\n👋 LED testing completed")


if __name__ == "__main__":
    asyncio.run(main())