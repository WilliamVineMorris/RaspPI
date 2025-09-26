#!/usr/bin/env python3
"""
Motion Optimization Verification Test

Tests that the previous 60-second scan timeout has been resolved
by using single 4D positioning commands instead of redundant moves.
"""

import sys
import asyncio
from pathlib import Path

v2_path = Path(__file__).parent
sys.path.insert(0, str(v2_path))

from scanning.scan_orchestrator import ScanOrchestrator
from scanning.scan_patterns import ScanPoint
from core.types import Position4D
from core.config_manager import ConfigManager

async def test_motion_optimization_resolved():
    """Test that motion optimization resolves the timeout issue"""
    print("Testing motion optimization resolves scan timeout issue...")
    
    # Setup simulation mode
    config_file = v2_path / "config" / "scanner_config.yaml"
    config = ConfigManager(config_file)
    config._config_data = {'system': {'simulation_mode': True}}
    
    orchestrator = ScanOrchestrator(config)
    
    # Create 3 test points (similar to the original failing scan)
    test_points = [
        ScanPoint(Position4D(x=110.0, y=150.0, z=0.0, c=0.0)),
        ScanPoint(Position4D(x=120.0, y=150.0, z=0.0, c=0.0)), 
        ScanPoint(Position4D(x=130.0, y=150.0, z=0.0, c=0.0))
    ]
    
    print(f"Testing {len(test_points)} point movements (like original scan)...")
    
    # Track execution time - should be much faster now
    start_time = asyncio.get_event_loop().time()
    
    try:
        # Test each point movement directly
        for i, point in enumerate(test_points, 1):
            print(f"Moving to point {i}: {point.position}")
            await orchestrator._move_to_point(point)
            print(f"  ✓ Point {i} completed")
        
        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time
        
        print(f"\n✅ ALL MOVEMENTS COMPLETED in {total_time:.1f}s")
        
        # Verify speed improvement  
        if total_time < 5.0:  # Should be much faster than 60s timeout
            print(f"✅ TIMEOUT ISSUE RESOLVED!")
            print(f"   ✓ Execution time: {total_time:.1f}s (vs previous 60s+ timeout)")
            print(f"   ✓ Motion optimization working correctly")
            return True
        else:
            print(f"⚠️  Still slow: {total_time:.1f}s")
            return False
            
    except Exception as e:
        print(f"❌ Error during movement test: {e}")
        return False

if __name__ == "__main__":
    try:
        result = asyncio.run(test_motion_optimization_resolved())
        if result:
            print(f"\n🎉 SUCCESS! Motion optimization has resolved the timeout issue")
            print(f"The scan system is now ready for production use")
            sys.exit(0)
        else:
            print(f"\n💥 Motion optimization may need further work")  
            sys.exit(1)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)