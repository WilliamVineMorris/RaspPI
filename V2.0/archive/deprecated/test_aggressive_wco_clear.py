#!/usr/bin/env python3
"""
Test aggressive WCO offset clearing with controller restart fallback.

This script tests the new aggressive approach that includes:
1. Software-based reset attempts
2. Controller restart if software fails
3. Verification of success
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

async def test_aggressive_wco_clearing():
    """Test aggressive WCO offset clearing with controller restart fallback"""
    
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
        
        # Test 1: Check initial state
        logger.info("\n" + "="*50)
        logger.info("TEST 1: INITIAL STATE CHECK")
        logger.info("="*50)
        
        initial_status = await controller._get_status_response()
        if initial_status:
            logger.info(f"Initial status: {initial_status}")
            
            # Check if WCO offset exists
            has_wco_offset = "WCO:" in initial_status and not "WCO:0.000,0.000,0.000" in initial_status
            if has_wco_offset:
                logger.info("⚠️  WCO offset detected - testing clearing")
            else:
                logger.info("✅ No WCO offset detected")
                
                # Create a test offset to verify our clearing works
                logger.info("Creating test offset for validation...")
                try:
                    await controller._send_command('G10 L2 P0 Z10')  # Create 10mm Z offset
                    await asyncio.sleep(1.0)
                    test_status = await controller._get_status_response()
                    if test_status:
                        logger.info(f"Status after creating test offset: {test_status}")
                except Exception as e:
                    logger.warning(f"Could not create test offset: {e}")
        
        initial_position = await controller.get_current_position()
        if initial_position:
            logger.info(f"Initial position: {initial_position}")
        
        # Test 2: Aggressive WCO clearing
        logger.info("\n" + "="*50)
        logger.info("TEST 2: AGGRESSIVE WCO CLEARING")
        logger.info("="*50)
        
        logger.info("Testing aggressive WCO clearing method...")
        success = await controller.reset_work_coordinate_offsets()
        
        if success:
            logger.info("✅ Aggressive WCO clearing completed successfully")
        else:
            logger.warning("⚠️  Aggressive WCO clearing had issues")
        
        # Test 3: Verify final state
        logger.info("\n" + "="*50)
        logger.info("TEST 3: FINAL STATE VERIFICATION")
        logger.info("="*50)
        
        final_status = await controller._get_status_response()
        if final_status:
            logger.info(f"Final status: {final_status}")
            
            # Check if WCO was successfully cleared
            wco_cleared = "WCO:0.000,0.000,0.000" in final_status or "WCO:" not in final_status
            
            if wco_cleared:
                logger.info("🎉 SUCCESS: WCO offsets successfully cleared!")
            else:
                logger.warning("❌ FAILED: WCO offsets persist after aggressive clearing")
        
        final_position = await controller.get_current_position()
        if final_position:
            logger.info(f"Final position: {final_position}")
        
        # Test 4: Analysis
        logger.info("\n" + "="*50)
        logger.info("TEST 4: ANALYSIS")
        logger.info("="*50)
        
        if initial_position and final_position:
            z_change = final_position.z - initial_position.z
            logger.info(f"Z position change: {z_change}°")
            
            if abs(final_position.z - 0.0) < 0.1:
                logger.info("✅ CONCLUSION: Aggressive clearing worked - Z is now 0°")
            elif abs(z_change) > 0.1:
                logger.info(f"📊 CONCLUSION: Z position changed by {z_change}° - partial success")
            else:
                logger.warning("⚠️  CONCLUSION: No significant change in Z position")
        
        logger.info("\n" + "="*50)
        logger.info("RECOMMENDATIONS:")
        logger.info("="*50)
        
        if success and wco_cleared:
            logger.info("✅ Aggressive WCO clearing is working correctly")
            logger.info("- Software commands are sufficient")
            logger.info("- Controller restart fallback available if needed")
        elif success and not wco_cleared:
            logger.info("⚠️  Software commands ineffective, controller restart attempted")
            logger.info("- Check if controller restart cleared offsets")
            logger.info("- May need manual power cycle for complete reset")
        else:
            logger.warning("❌ Aggressive clearing failed")
            logger.info("- Manual power cycle of FluidNC required")
            logger.info("- Check FluidNC firmware version and configuration")
        
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
    logger.info("Aggressive WCO Clearing Test")
    logger.info("Testing software commands + controller restart fallback...")
    success = asyncio.run(test_aggressive_wco_clearing())
    if success:
        logger.info("✅ Test completed")
    else:
        logger.error("❌ Test failed")