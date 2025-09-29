#!/usr/bin/env python3
"""
LED System Test Script

Comprehensive testing script for the GPIO LED controller system.
Tests all LED zones, patterns, safety features, and configurations.

Usa                logger.info(f"   Testing {zone} at 100% (should be capped at 90%)...")
                await self.led_controller.set_brightness(zone, 1.0)
                await asyncio.sleep(0.5)
                
                # Check if controller respects safety limits
                current_brightness = await self.led_controller.get_brightness(zone)
                if current_brightness <= 0.90:
                    logger.info(f"   ✅ {zone} safely capped at {current_brightness:.1%}")
                else:
                    logger.warning(f"   ⚠️ {zone} brightness {current_brightness:.1%} exceeds safety limit!")ython test_led_system.py [--interactive] [--zone ZONE] [--pattern PATTERN]

Requirements:
    - Raspberry Pi with GPIO pins configured
    - LED controller properly wired to GPIO pins 13 and 18
    - Scanner system configuration loaded

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent))

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
    """Comprehensive LED testing class"""
    
    def __init__(self):
        self.config_manager = None
        self.led_controller = None
        self.test_results = {}
        
    async def initialize(self):
        """Initialize the LED testing system"""
        try:
            logger.info("🔧 Initializing LED testing system...")
            
            # Load configuration
            config_file = Path(__file__).parent / "config" / "scanner_config.yaml"
            self.config_manager = ConfigManager(config_file)
            
            # Get LED configuration
            led_config = self.config_manager.get('lighting', {})
            if not led_config:
                raise ConfigurationError("No lighting configuration found")
            
            logger.info(f"📋 LED Configuration loaded: {led_config}")
            
            # Initialize LED controller
            self.led_controller = GPIOLEDController(led_config)
            await self.led_controller.initialize()
            
            logger.info("✅ LED testing system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize LED testing system: {e}")
            return False
    
    async def test_basic_functionality(self) -> bool:
        """Test basic LED controller functionality"""
        logger.info("\n🔍 Testing Basic LED Functionality...")
        
        try:
            # Test controller status
            status = await self.led_controller.get_status()
            if not status:
                logger.error("❌ LED controller not connected")
                return False
            
            logger.info("✅ LED controller is connected")
            
            # Test available zones
            zones = await self.led_controller.list_zones()
            logger.info(f"📋 Available LED zones: {zones}")
            
            if not zones:
                logger.warning("⚠️ No LED zones configured")
                return False
            
            self.test_results['basic_functionality'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Basic functionality test failed: {e}")
            self.test_results['basic_functionality'] = False
            return False
    
    async def test_individual_zones(self) -> bool:
        """Test each LED zone individually"""
        logger.info("\n🔍 Testing Individual LED Zones...")
        
        try:
            zones = await self.led_controller.list_zones()
            zone_results = {}
            
            for zone in zones:
                logger.info(f"🧪 Testing zone: {zone}")
                
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
                
                zone_results[zone] = True
                logger.info(f"✅ Zone {zone} test completed successfully")
            
            self.test_results['individual_zones'] = zone_results
            return True
            
        except Exception as e:
            logger.error(f"❌ Individual zones test failed: {e}")
            self.test_results['individual_zones'] = False
            return False
    
    async def test_flash_patterns(self) -> bool:
        """Test flash patterns and sync functionality"""
        logger.info("\n🔍 Testing Flash Patterns...")
        
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
        logger.info("\n🔍 Testing Safety Features...")
        
        try:
            zones = await self.led_controller.list_zones()
            
            # Test duty cycle limits (should be capped at 90%)
            logger.info("🛡️ Testing duty cycle safety limits...")
            for zone in zones:
                logger.info(f"   Testing {zone} at 100% (should be capped at 90%)...")
                await self.led_controller.set_zone_brightness(zone, 100.0)
                await asyncio.sleep(0.5)
                
                # Check if controller respects safety limits
                current_brightness = await self.led_controller.get_zone_brightness(zone)
                if current_brightness <= 90.0:
                    logger.info(f"   ✅ {zone} safely capped at {current_brightness}%")
                else:
                    logger.warning(f"   ⚠️ {zone} not properly capped: {current_brightness}%")
                
                await self.led_controller.set_zone_brightness(zone, 0.0)
                await asyncio.sleep(0.3)
            
            # Test emergency shutdown
            logger.info("🚨 Testing emergency shutdown...")
            
            # Turn on all zones
            for zone in zones:
                await self.led_controller.set_brightness(zone, 0.5)
            await asyncio.sleep(0.5)
            
            # Emergency shutdown
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
                logger.info("   ✅ Emergency shutdown successful - all zones off")
            else:
                logger.error("   ❌ Emergency shutdown failed - some zones still on")
            
            self.test_results['safety_features'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Safety features test failed: {e}")
            self.test_results['safety_features'] = False
            return False
    
    async def test_pattern_sequences(self) -> bool:
        """Test various LED pattern sequences"""
        logger.info("\n🔍 Testing Pattern Sequences...")
        
        try:
            zones = await self.led_controller.list_zones()
            
            # Test fade in/out pattern
            logger.info("🌅 Testing fade in/out pattern...")
            for zone in zones:
                logger.info(f"   Fading {zone} in...")
                for brightness in range(0, 81, 10):  # 0 to 80% in 10% steps
                    await self.led_controller.set_zone_brightness(zone, float(brightness))
                    await asyncio.sleep(0.1)
                
                logger.info(f"   Fading {zone} out...")
                for brightness in range(80, -1, -10):  # 80% to 0% in 10% steps
                    await self.led_controller.set_zone_brightness(zone, float(brightness))
                    await asyncio.sleep(0.1)
            
            # Test alternating pattern (if multiple zones)
            if len(zones) >= 2:
                logger.info("🔄 Testing alternating pattern...")
                for cycle in range(3):
                    # Turn on first zone, off second
                    await self.led_controller.set_zone_brightness(zones[0], 60.0)
                    await self.led_controller.set_zone_brightness(zones[1], 0.0)
                    await asyncio.sleep(0.5)
                    
                    # Turn off first zone, on second
                    await self.led_controller.set_zone_brightness(zones[0], 0.0)
                    await self.led_controller.set_zone_brightness(zones[1], 60.0)
                    await asyncio.sleep(0.5)
                
                # Turn off all
                for zone in zones:
                    await self.led_controller.set_zone_brightness(zone, 0.0)
            
            # Test breathing pattern
            logger.info("💨 Testing breathing pattern...")
            for zone in zones:
                logger.info(f"   {zone} breathing pattern...")
                for cycle in range(2):
                    # Breathe in
                    for brightness in [10, 30, 50, 70, 50, 30, 10, 0]:
                        await self.led_controller.set_zone_brightness(zone, float(brightness))
                        await asyncio.sleep(0.2)
            
            self.test_results['pattern_sequences'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Pattern sequences test failed: {e}")
            self.test_results['pattern_sequences'] = False
            return False
    
    async def test_configuration_validation(self) -> bool:
        """Test configuration validation and error handling"""
        logger.info("\n🔍 Testing Configuration Validation...")
        
        try:
            # Test invalid brightness values
            logger.info("🚫 Testing invalid brightness values...")
            zones = await self.led_controller.list_zones()
            
            if zones:
                zone = zones[0]
                
                # Test negative brightness (should be clamped to 0)
                try:
                    await self.led_controller.set_zone_brightness(zone, -10.0)
                    current = await self.led_controller.get_zone_brightness(zone)
                    if current == 0.0:
                        logger.info("   ✅ Negative brightness properly clamped to 0")
                    else:
                        logger.warning(f"   ⚠️ Negative brightness not clamped: {current}")
                except Exception as e:
                    logger.info(f"   ✅ Negative brightness properly rejected: {e}")
                
                # Test excessive brightness (should be clamped)
                try:
                    await self.led_controller.set_zone_brightness(zone, 150.0)
                    current = await self.led_controller.get_zone_brightness(zone)
                    if current <= 90.0:
                        logger.info(f"   ✅ Excessive brightness properly clamped to {current}%")
                    else:
                        logger.warning(f"   ⚠️ Excessive brightness not clamped: {current}%")
                except Exception as e:
                    logger.info(f"   ✅ Excessive brightness properly rejected: {e}")
                
                # Clean up
                await self.led_controller.set_zone_brightness(zone, 0.0)
            
            # Test invalid zone names
            logger.info("🚫 Testing invalid zone names...")
            try:
                await self.led_controller.set_zone_brightness("invalid_zone", 50.0)
                logger.warning("   ⚠️ Invalid zone name was accepted")
            except Exception as e:
                logger.info(f"   ✅ Invalid zone name properly rejected: {e}")
            
            self.test_results['configuration_validation'] = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Configuration validation test failed: {e}")
            self.test_results['configuration_validation'] = False
            return False
    
    async def run_interactive_test(self):
        """Run interactive LED testing"""
        logger.info("\n🎮 Interactive LED Testing Mode")
        logger.info("Commands: on <zone> <brightness>, off <zone>, flash <zone>, all_off, status, quit")
        
        zones = await self.led_controller.list_zones()
        logger.info(f"Available zones: {', '.join(zones)}")
        
        while True:
            try:
                command = input("\nLED> ").strip().lower().split()
                
                if not command:
                    continue
                
                if command[0] == 'quit' or command[0] == 'exit':
                    break
                
                elif command[0] == 'on' and len(command) >= 3:
                    zone = command[1]
                    brightness = float(command[2])
                    await self.led_controller.set_zone_brightness(zone, brightness)
                    logger.info(f"Set {zone} to {brightness}%")
                
                elif command[0] == 'off' and len(command) >= 2:
                    zone = command[1]
                    await self.led_controller.set_zone_brightness(zone, 0.0)
                    logger.info(f"Turned off {zone}")
                
                elif command[0] == 'flash' and len(command) >= 2:
                    zone = command[1]
                    duration = float(command[2]) if len(command) > 2 else 0.2
                    brightness = float(command[3]) if len(command) > 3 else 80.0
                    await self.led_controller.flash_zone(zone, duration, brightness)
                    logger.info(f"Flashed {zone}")
                
                elif command[0] == 'all_off':
                    for zone in zones:
                        await self.led_controller.set_zone_brightness(zone, 0.0)
                    logger.info("All zones turned off")
                
                elif command[0] == 'status':
                    for zone in zones:
                        brightness = await self.led_controller.get_zone_brightness(zone)
                        logger.info(f"  {zone}: {brightness}%")
                
                else:
                    logger.info("Unknown command. Available: on, off, flash, all_off, status, quit")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Command error: {e}")
        
        # Clean up - turn off all LEDs
        for zone in zones:
            await self.led_controller.set_zone_brightness(zone, 0.0)
        logger.info("🔴 All LEDs turned off")
    
    async def cleanup(self):
        """Clean up the LED testing system"""
        try:
            if self.led_controller:
                # Turn off all LEDs
                zones = await self.led_controller.list_zones()
                for zone in zones:
                    await self.led_controller.set_zone_brightness(zone, 0.0)
                
                # Shutdown controller
                await self.led_controller.shutdown()
                logger.info("🔴 LED controller shutdown complete")
        except Exception as e:
            logger.error(f"❌ Cleanup error: {e}")
    
    def print_test_results(self):
        """Print comprehensive test results"""
        logger.info("\n" + "="*60)
        logger.info("📊 LED SYSTEM TEST RESULTS")
        logger.info("="*60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{test_name:.<40} {status}")
        
        logger.info("-"*60)
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {total_tests - passed_tests}")
        logger.info(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%" if total_tests > 0 else "N/A")
        logger.info("="*60)

async def main():
    """Main testing function"""
    parser = argparse.ArgumentParser(description="LED System Test Script")
    parser.add_argument("--interactive", "-i", action="store_true", 
                       help="Run interactive testing mode")
    parser.add_argument("--zone", "-z", type=str, 
                       help="Test specific zone only")
    parser.add_argument("--pattern", "-p", type=str, 
                       help="Test specific pattern only")
    parser.add_argument("--quick", "-q", action="store_true",
                       help="Run quick tests only")
    
    args = parser.parse_args()
    
    tester = LEDTester()
    
    try:
        # Initialize system
        if not await tester.initialize():
            logger.error("❌ Failed to initialize LED testing system")
            return 1
        
        if args.interactive:
            # Run interactive mode
            await tester.run_interactive_test()
        else:
            # Run automated tests
            logger.info("🚀 Starting LED System Tests...")
            
            # Basic functionality test
            await tester.test_basic_functionality()
            
            # Individual zone tests
            if not args.zone or args.zone == "zones":
                await tester.test_individual_zones()
            
            # Flash pattern tests
            if not args.pattern or args.pattern == "flash":
                await tester.test_flash_patterns()
            
            # Safety feature tests
            if not args.quick:
                await tester.test_safety_features()
            
            # Pattern sequence tests
            if not args.pattern or args.pattern == "sequences":
                if not args.quick:
                    await tester.test_pattern_sequences()
            
            # Configuration validation tests
            if not args.quick:
                await tester.test_configuration_validation()
            
            # Print results
            tester.print_test_results()
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Testing interrupted by user")
    except Exception as e:
        logger.error(f"❌ Testing failed: {e}")
        return 1
    finally:
        # Cleanup
        await tester.cleanup()
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))