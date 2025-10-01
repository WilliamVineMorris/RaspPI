#!/usr/bin/env python3
"""
LED Update Diagnostic Tool

This script patches the LED controller to log EVERY single PWM update
with high-precision timestamps, so we can identify what's causing flickering.

Usage:
    python3 debug_led_updates.py

The script will:
1. Patch the LED controller to log ALL updates (even skipped ones)
2. Run for 30 seconds during a scan
3. Show you the pattern of LED updates

This will reveal if there are:
- Continuous micro-updates (brightness bouncing)
- Unexpected updates from background tasks
- Timing patterns that correlate with camera operations
"""

import asyncio
import time
import sys
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from lighting.gpio_led_controller import GPIOLEDController
from core.config_manager import ConfigManager

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

logger = logging.getLogger(__name__)


class DiagnosticLEDController(GPIOLEDController):
    """LED Controller with diagnostic logging for every update attempt"""
    
    def __init__(self, config):
        super().__init__(config)
        self._update_count = 0
        self._skip_count = 0
        self._actual_update_count = 0
        self._start_time = time.time()
        self._last_update_time = {}
        
    def _set_brightness_direct(self, zone_id: str, brightness: float) -> bool:
        """Override to log EVERY update attempt, including skipped ones"""
        current_time = time.time()
        elapsed = current_time - self._start_time
        
        # Get current brightness before any checks
        current_brightness = self.zone_states.get(zone_id, {}).get('brightness', -1.0)
        brightness_change = abs(current_brightness - brightness)
        
        # Log this update attempt
        self._update_count += 1
        last_time = self._last_update_time.get(zone_id, self._start_time)
        time_since_last = (current_time - last_time) * 1000  # ms
        
        # Check if this will be skipped by 1% threshold
        will_skip_threshold = brightness_change < 0.01
        
        # Check if this will be skipped by state tracking
        is_on = brightness > 0.01
        was_on = self._led_active.get(zone_id, False)
        will_skip_state = is_on == was_on and brightness_change < 0.02
        
        # Determine action
        if will_skip_threshold:
            action = "⏭️  SKIP-THRESHOLD"
            self._skip_count += 1
        elif will_skip_state:
            action = "⏭️  SKIP-STATE"
            self._skip_count += 1
        else:
            action = "✅ UPDATE"
            self._actual_update_count += 1
            self._last_update_time[zone_id] = current_time
        
        # LOG EVERY ATTEMPT with high detail
        logger.info(
            f"{action} | Zone:{zone_id:6s} | "
            f"{current_brightness*100:5.1f}%→{brightness*100:5.1f}% | "
            f"Δ={brightness_change*100:4.1f}% | "
            f"Since:{time_since_last:6.1f}ms | "
            f"T+{elapsed:7.3f}s | "
            f"Total:{self._update_count} Skip:{self._skip_count} Actual:{self._actual_update_count}"
        )
        
        # Call parent implementation
        return super()._set_brightness_direct(zone_id, brightness)
    
    def print_summary(self):
        """Print diagnostic summary"""
        elapsed = time.time() - self._start_time
        update_rate = self._update_count / elapsed
        actual_rate = self._actual_update_count / elapsed
        
        print("\n" + "="*80)
        print("LED UPDATE DIAGNOSTIC SUMMARY")
        print("="*80)
        print(f"Total Runtime: {elapsed:.1f} seconds")
        print(f"Update Attempts: {self._update_count}")
        print(f"  - Skipped (threshold): {self._skip_count}")
        print(f"  - Actual PWM updates: {self._actual_update_count}")
        print(f"Update Rate: {update_rate:.1f} attempts/sec")
        print(f"Actual PWM Rate: {actual_rate:.1f} updates/sec")
        print("\nZone Last Update Times:")
        for zone, last_time in self._last_update_time.items():
            age = time.time() - last_time
            print(f"  {zone}: {age:.3f}s ago")
        print("="*80)


async def run_diagnostic():
    """Run diagnostic monitoring"""
    try:
        logger.info("="*80)
        logger.info("LED UPDATE DIAGNOSTIC TOOL")
        logger.info("="*80)
        logger.info("This tool will monitor ALL LED update attempts for 30 seconds")
        logger.info("Including updates that are skipped by the 1% threshold")
        logger.info("-"*80)
        
        # Load configuration
        config_manager = ConfigManager("config/scanner_config.yaml")
        lighting_config = config_manager.get('lighting', {})
        
        logger.info(f"Lighting config: {lighting_config}")
        
        # Create diagnostic controller
        controller = DiagnosticLEDController(lighting_config)
        
        # Initialize
        logger.info("Initializing LED controller...")
        if not await controller.initialize():
            logger.error("❌ Failed to initialize LED controller!")
            return
        
        logger.info("✅ LED controller initialized")
        logger.info("-"*80)
        logger.info("Starting 30-second monitoring period...")
        logger.info("Legend:")
        logger.info("  ✅ UPDATE       - Actual PWM update sent to hardware")
        logger.info("  ⏭️  SKIP-THRESHOLD - Skipped (change < 1%)")
        logger.info("  ⏭️  SKIP-STATE     - Skipped (state unchanged, < 2%)")
        logger.info("-"*80)
        
        # Test sequence:
        # 1. Turn on LEDs at 30%
        logger.info("\n🔵 TEST 1: Turn on LEDs at 30%")
        await controller.set_brightness("all", 0.3)
        await asyncio.sleep(5)
        
        # 2. Repeated set to same brightness (should be skipped)
        logger.info("\n🔵 TEST 2: Repeated set to 30% (should skip)")
        for i in range(5):
            await controller.set_brightness("all", 0.3)
            await asyncio.sleep(0.5)
        
        # 3. Small changes below 1% threshold
        logger.info("\n🔵 TEST 3: Small changes (< 1% threshold, should skip)")
        for brightness in [0.301, 0.302, 0.303, 0.304, 0.305]:
            await controller.set_brightness("all", brightness)
            await asyncio.sleep(0.5)
        
        # 4. Larger change above 1% threshold
        logger.info("\n🔵 TEST 4: Larger change (> 1% threshold, should update)")
        await controller.set_brightness("all", 0.5)
        await asyncio.sleep(2)
        
        # 5. Back to 30%
        logger.info("\n🔵 TEST 5: Back to 30%")
        await controller.set_brightness("all", 0.3)
        await asyncio.sleep(2)
        
        # 6. Turn off
        logger.info("\n🔵 TEST 6: Turn off LEDs")
        await controller.turn_off_all()
        await asyncio.sleep(2)
        
        # 7. Rapid repeated off commands (should all skip)
        logger.info("\n🔵 TEST 7: Rapid repeated OFF commands (should all skip)")
        for i in range(10):
            await controller.turn_off_all()
            await asyncio.sleep(0.1)
        
        logger.info("\n✅ Diagnostic monitoring complete!")
        
        # Print summary
        controller.print_summary()
        
        # Cleanup
        logger.info("\nCleaning up...")
        await controller.shutdown()
        
    except KeyboardInterrupt:
        logger.info("\n⚠️  Interrupted by user")
    except Exception as e:
        logger.error(f"❌ Diagnostic failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(run_diagnostic())
