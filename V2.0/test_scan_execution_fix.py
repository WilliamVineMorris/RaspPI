#!/usr/bin/env python3
"""
Test script to verify scan execution fix

This script tests that scans run completely through all phases:
1. Homing
2. Scan point execution
3. Completion

The fix addresses the issue where scans only executed homing
and didn't proceed to scan the actual points.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(__file__))

from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import GridScanPattern
from core.config_manager import ConfigManager
from core.events import EventBus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_complete_scan_execution():
    """Test that scans execute completely through all phases"""
    
    logger.info("🧪 Testing Complete Scan Execution")
    logger.info("=" * 50)
    
    try:
        # Initialize components
        config_path = Path("config/scanner_config.yaml")
        config_manager = ConfigManager(config_path)
        event_bus = EventBus()
        
        # Create orchestrator
        orchestrator = ScanOrchestrator(config_manager)
        await orchestrator.initialize()
        
        # Create a simple 2x2 grid pattern for testing
        from scanning.scan_patterns import GridPatternParameters
        
        grid_params = GridPatternParameters(
            min_x=-10.0,
            max_x=10.0,
            min_y=-10.0,
            max_y=10.0,
            x_spacing=10.0,  # This gives us 2 points in X
            y_spacing=10.0   # This gives us 2 points in Y
        )
        
        pattern = GridScanPattern(
            pattern_id="test_grid",
            parameters=grid_params
        )
        
        logger.info(f"Created pattern with {len(pattern.generate_points())} points")
        
        # Create output directory
        output_dir = Path("test_scans") / "scan_execution_test"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info("Starting scan...")
        
        # Start the scan
        scan_state = await orchestrator.start_scan(
            pattern=pattern,
            output_directory=output_dir,
            scan_id="execution_test"
        )
        
        logger.info(f"Scan started: {scan_state.scan_id}")
        logger.info(f"Status: {scan_state.status}")
        logger.info(f"Phase: {scan_state.phase}")
        
        # Wait for scan completion
        logger.info("Waiting for scan completion...")
        success = await orchestrator.wait_for_scan_completion(timeout=60)
        
        if success:
            logger.info("✅ Scan completed successfully!")
            
            # Check final status
            final_status = orchestrator.get_scan_status()
            if final_status:
                logger.info(f"Final status: {final_status.get('status')}")
                logger.info(f"Final phase: {final_status.get('phase')}")
                logger.info(f"Points completed: {final_status.get('points_completed')}")
                logger.info(f"Total points: {final_status.get('total_points')}")
                
                # Verify scan went through all phases
                if final_status.get('points_completed', 0) > 0:
                    logger.info("✅ SUCCESS: Scan executed scan points (not just homing)")
                else:
                    logger.error("❌ FAILED: Scan only completed homing, no points executed")
                    return False
            else:
                logger.warning("No final status available")
        else:
            logger.error("❌ Scan did not complete within timeout")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed with exception: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return False
    
    finally:
        try:
            if 'orchestrator' in locals():
                await orchestrator.shutdown()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

async def main():
    """Main test function"""
    
    logger.info("🚀 Starting Scan Execution Fix Test")
    
    try:
        success = await test_complete_scan_execution()
        
        if success:
            logger.info("🎉 ALL TESTS PASSED - Scan execution fix working correctly!")
            return 0
        else:
            logger.error("💥 TEST FAILED - Scan execution issue persists")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Test interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\nTest interrupted")
        sys.exit(1)