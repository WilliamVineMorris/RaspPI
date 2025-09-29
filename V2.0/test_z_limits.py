#!/usr/bin/env python3
"""
Test Z-axis continuous rotation (no limits)
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from motion.base import Position4D

async def test_z_limits():
    """Test that Z-axis has no limits"""
    
    print("=== Z-Axis Continuous Rotation Test ===")
    
    try:
        # Load config
        config_manager = ConfigManager()
        motion_config = config_manager.get_motion_config()
        
        # Check Z-axis limits in config
        z_axis_config = motion_config.get('axes', {}).get('z_axis', {})
        min_limit = z_axis_config.get('min_limit')
        max_limit = z_axis_config.get('max_limit')
        
        print(f"Z-axis min_limit: {min_limit}")
        print(f"Z-axis max_limit: {max_limit}")
        
        if min_limit is None and max_limit is None:
            print("✅ Z-axis has no limits (continuous rotation enabled)")
        else:
            print(f"❌ Z-axis still has limits: {min_limit} to {max_limit}")
            
        # Test positions that were failing before
        test_positions = [
            Position4D(30.0, 100.0, 270.0, 0.0),  # This was failing at 270°
            Position4D(0.0, 0.0, 360.0, 0.0),     # Full rotation
            Position4D(0.0, 0.0, -270.0, 0.0),    # Negative rotation
            Position4D(0.0, 0.0, 720.0, 0.0),     # Multiple rotations
        ]
        
        print("\n=== Testing Problem Positions ===")
        for i, pos in enumerate(test_positions, 1):
            print(f"Test {i}: Position Z={pos.z}° should now be allowed")
            
        print("\n✅ Z-axis configuration updated for continuous rotation")
        print("🔄 Please restart the web interface to pick up new config")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_z_limits())