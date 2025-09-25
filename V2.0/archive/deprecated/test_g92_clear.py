#!/usr/bin/env python3
"""
Test FluidNC G92 offset clearing functionality.

This script specifically tests clearing the persistent G92 Z-axis offset
that's causing the Z position to be stuck at 53.999° instead of 0°.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add the project directory to the path
project_dir = Path(__file__).parent
sys.path.insert(0, str(project_dir))

from core.config_manager import ConfigManager
from motion.fluidnc_controller import create_fluidnc_controller
from core.logging_setup import setup_logging

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

async def test_g92_offset_clearing():
    """Test G92 offset clearing specifically for Z-axis"""
    
    # Load configuration - use existing config file
    config_path = project_dir / "config" / "scanner_config.yaml"
    if not config_path.exists():
        # Try alternative config name
        config_path = project_dir / "config" / "config.yaml"
        if not config_path.exists():
            logger.error(f"No config file found. Tried: {config_path}")
            return False
    
    config_manager = ConfigManager(config_path)
    
    # Create controller
    controller = create_fluidnc_controller(config_manager)
    
    try:
        # Connect to FluidNC
        logger.info("Connecting to FluidNC...")
        await controller.connect()
        logger.info("✅ Connected successfully!")
        
        # Test 1: Check current state
        logger.info("\n=== Test 1: Current Coordinate State ===")
        await controller._send_command('$#')  # Show all coordinate offsets
        await asyncio.sleep(1.0)
        await controller._send_command('$G')  # Show current coordinate system
        await asyncio.sleep(1.0)
        
        # Test 2: Get current position (should show Z=53.999)
        logger.info("\n=== Test 2: Current Position Before G92 Clear ===")
        position = await controller.get_current_position()
        if position:
            logger.info(f"Current position: {position}")
            if abs(position.z - 53.999) < 0.1:
                logger.info("✅ Confirmed: Z position shows 53.999° (expected problem)")
            else:
                logger.warning(f"Unexpected Z position: {position.z}")
        else:
            logger.error("❌ Could not get current position")
            return False
        
        # Test 3: Clear G92 offsets specifically
        logger.info("\n=== Test 3: Clearing G92 Offsets ===")
        logger.info("Sending G92.1 command to clear all G92 offsets...")
        await controller._send_command('G92.1')  # Clear G92 offsets
        await asyncio.sleep(2.0)  # Give FluidNC time to process
        
        # Verify G92 offsets are cleared
        logger.info("Checking if G92 offsets were cleared...")
        await controller._send_command('$#')  # Should show G92 all zeros now
        await asyncio.sleep(1.0)
        
        # Test 4: Check position after G92 clear
        logger.info("\n=== Test 4: Position After G92 Clear ===")
        position_after_clear = await controller.get_current_position()
        if position_after_clear:
            logger.info(f"Position after G92 clear: {position_after_clear}")
            
            if abs(position_after_clear.z - 0.0) < 0.1:
                logger.info("🎉 SUCCESS: Z position is now 0° - G92 offset cleared!")
            elif abs(position_after_clear.z - 53.999) < 0.1:
                logger.warning("⚠️  G92 clear didn't work - Z still at 53.999°")
                
                # Try alternative approach - complete system reset
                logger.info("\n=== Alternative: Complete System Reset ===")
                logger.warning("Trying complete system reset ($RST=#)...")
                await controller._send_command('$RST=#')
                await asyncio.sleep(3.0)  # Give more time for system reset
                
                # Check again
                position_after_reset = await controller.get_current_position()
                if position_after_reset:
                    logger.info(f"Position after system reset: {position_after_reset}")
                    if abs(position_after_reset.z - 0.0) < 0.1:
                        logger.info("🎉 SUCCESS: System reset cleared the Z offset!")
                    else:
                        logger.error("❌ FAILED: Z offset persists even after system reset")
            else:
                logger.info(f"Z position changed to {position_after_clear.z}° (investigating...)")
        else:
            logger.error("❌ Could not get position after G92 clear")
        
        # Test 5: Final coordinate state check
        logger.info("\n=== Test 5: Final Coordinate State ===")
        await controller._send_command('$#')  # Show final state
        await asyncio.sleep(1.0)
        
        return True
        
    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False
        
    finally:
        # Disconnect
        try:
            await controller.disconnect()
            logger.info("Disconnected from FluidNC")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

if __name__ == "__main__":
    # Run the test
    logger.info("=== FluidNC G92 Offset Clearing Test ===")
    success = asyncio.run(test_g92_offset_clearing())
    if success:
        logger.info("✅ Test completed")
    else:
        logger.error("❌ Test failed")