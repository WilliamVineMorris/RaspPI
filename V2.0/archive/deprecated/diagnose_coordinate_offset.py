#!/usr/bin/env python3
"""
FluidNC Coordinate Offset Diagnostic Tool

This script diagnoses whether the 53.999° Z-offset is from:
1. FluidNC configuration issue
2. Accumulated error from testing
3. Persistent coordinate offsets

It uses FluidNC-specific commands to determine the source.
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

async def diagnose_coordinate_offset():
    """Diagnose the source of the Z-axis 53.999° offset"""
    
    # Load configuration
    config_path = project_dir / "config" / "scanner_config.yaml"
    if not config_path.exists():
        config_path = project_dir / "config" / "config.yaml"
        if not config_path.exists():
            logger.error("No config file found")
            return False
    
    config_manager = ConfigManager(config_path)
    controller = create_fluidnc_controller(config_manager)
    
    try:
        # Connect to FluidNC
        logger.info("Connecting to FluidNC...")
        await controller.connect()
        logger.info("✅ Connected successfully!")
        
        # Phase 1: Document current state
        logger.info("\n" + "="*60)
        logger.info("PHASE 1: CURRENT COORDINATE STATE ANALYSIS")
        logger.info("="*60)
        
        logger.info("Current coordinate systems:")
        await controller._send_command('$#')
        await asyncio.sleep(1.0)
        
        logger.info("Current G-code state:")
        await controller._send_command('$G')
        await asyncio.sleep(1.0)
        
        logger.info("Current position:")
        position = await controller.get_current_position()
        if position:
            logger.info(f"Position: {position}")
            z_offset = position.z
            logger.info(f"Z-axis offset: {z_offset}°")
        
        # Phase 2: Test FluidNC complete system reset
        logger.info("\n" + "="*60)
        logger.info("PHASE 2: FLUIDNC COMPLETE SYSTEM RESET TEST")
        logger.info("="*60)
        
        logger.info("Applying FluidNC complete system reset ($RST=#)...")
        await controller._send_command('$RST=#')
        await asyncio.sleep(4.0)  # Give plenty of time for reset
        
        logger.info("Coordinate systems after $RST=#:")
        await controller._send_command('$#')
        await asyncio.sleep(1.0)
        
        logger.info("Position after system reset:")
        position_after_reset = await controller.get_current_position()
        if position_after_reset:
            logger.info(f"Position: {position_after_reset}")
            
            if abs(position_after_reset.z - 0.0) < 0.1:
                logger.info("🎉 SUCCESS: System reset cleared Z offset - was accumulated error!")
                conclusion = "ACCUMULATED_ERROR"
            elif abs(position_after_reset.z - z_offset) < 0.1:
                logger.warning("⚠️  Z offset persists after system reset")
                conclusion = "CONFIGURATION_OR_HARDWARE"
            else:
                logger.info(f"Z offset changed to {position_after_reset.z}°")
                conclusion = "PARTIAL_SUCCESS"
        
        # Phase 3: Additional G92 clearing
        logger.info("\n" + "="*60)
        logger.info("PHASE 3: ADDITIONAL G92 OFFSET CLEARING")
        logger.info("="*60)
        
        logger.info("Clearing G92 offsets (G92.1)...")
        await controller._send_command('G92.1')
        await asyncio.sleep(1.0)
        
        logger.info("Coordinate systems after G92.1:")
        await controller._send_command('$#')
        await asyncio.sleep(1.0)
        
        logger.info("Final position check:")
        final_position = await controller.get_current_position()
        if final_position:
            logger.info(f"Final position: {final_position}")
        
        # Phase 4: Analysis and conclusion
        logger.info("\n" + "="*60)
        logger.info("PHASE 4: DIAGNOSTIC CONCLUSION")
        logger.info("="*60)
        
        if position and final_position:
            initial_z = position.z
            final_z = final_position.z
            
            logger.info(f"Initial Z position: {initial_z}°")
            logger.info(f"Final Z position: {final_z}°")
            logger.info(f"Change: {final_z - initial_z}°")
            
            if abs(final_z - 0.0) < 0.1:
                logger.info("✅ DIAGNOSIS: ACCUMULATED ERROR FROM TESTING")
                logger.info("The 53.999° offset was accumulated error that FluidNC system reset cleared.")
                logger.info("This is NOT a configuration issue.")
            elif abs(initial_z - final_z) < 0.1:
                logger.warning("⚠️  DIAGNOSIS: CONFIGURATION OR HARDWARE ISSUE")
                logger.info("The offset persists after complete reset, suggesting:")
                logger.info("- FluidNC configuration issue")
                logger.info("- Hardware encoder/stepper position issue")
                logger.info("- Persistent non-volatile setting")
            else:
                logger.info("📊 DIAGNOSIS: PARTIAL IMPROVEMENT")
                logger.info("Some offset was cleared but not all - mixed issue.")
        
        # Phase 5: Recommendations
        logger.info("\n" + "="*60)
        logger.info("PHASE 5: RECOMMENDATIONS")
        logger.info("="*60)
        
        if abs(final_position.z - 0.0) < 0.1:
            logger.info("✅ RECOMMENDED ACTION: Issue resolved")
            logger.info("- The FluidNC system reset cleared the accumulated error")
            logger.info("- Future testing should include coordinate reset after each session")
            logger.info("- Consider adding $RST=# to initialization sequence")
        else:
            logger.info("🔧 RECOMMENDED ACTION: Further investigation needed")
            logger.info("- Check FluidNC configuration for Z-axis settings")
            logger.info("- Verify Z-axis encoder/stepper calibration")
            logger.info("- Consider power cycle and NVRAM reset")
        
        return True
        
    except Exception as e:
        logger.error(f"Diagnostic failed with error: {e}")
        return False
        
    finally:
        # Disconnect
        try:
            await controller.disconnect()
            logger.info("Disconnected from FluidNC")
        except Exception as e:
            logger.error(f"Error disconnecting: {e}")

if __name__ == "__main__":
    logger.info("FluidNC Coordinate Offset Diagnostic Tool")
    logger.info("Investigating source of 53.999° Z-axis offset...")
    success = asyncio.run(diagnose_coordinate_offset())
    if success:
        logger.info("✅ Diagnostic completed")
    else:
        logger.error("❌ Diagnostic failed")