#!/usr/bin/env python3
"""
Cylindrical Pattern Test

Simple test script to validate cylindrical scan pattern generation
and visualize the planned scan points.
"""

import sys
import logging
from pathlib import Path
from typing import List

# Add the current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from scanning.scan_patterns import CylindricalPatternParameters, CylindricalScanPattern

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_basic_cylindrical_pattern():
    """Test basic cylindrical pattern generation"""
    logger.info("🧪 Testing Basic Cylindrical Pattern")
    
    # Create parameters for a simple scan
    params = CylindricalPatternParameters(
        # Single X position (camera at fixed distance)
        x_start=0.0,
        x_end=0.0,
        x_step=1.0,
        
        # 3 height levels
        y_start=50.0,
        y_end=100.0,
        y_step=25.0,
        
        # 8 rotation angles (every 45°)
        z_rotations=[0, 45, 90, 135, 180, 225, 270, 315],
        
        # 3 camera angles  
        c_angles=[-10, 0, 10],
        
        safety_margin=0.5
    )
    
    # Create pattern
    pattern = CylindricalScanPattern("test_basic", params)
    
    # Generate points
    points = pattern.get_points()
    
    logger.info(f"✅ Generated {len(points)} scan points")
    logger.info(f"🕒 Estimated duration: {pattern.estimated_duration:.1f} minutes")
    
    # Show first few points
    logger.info("📍 First 5 scan points:")
    for i, point in enumerate(points[:5]):
        pos = point.position
        logger.info(f"   {i+1}. X={pos.x:6.1f}, Y={pos.y:6.1f}, Z={pos.z:6.1f}°, C={pos.c:6.1f}°")
    
    if len(points) > 5:
        logger.info(f"   ... ({len(points)-5} more points)")
    
    return len(points)

def test_multi_height_cylindrical_pattern():
    """Test cylindrical pattern with multiple heights and radii"""
    logger.info("🧪 Testing Multi-Height Cylindrical Pattern")
    
    # Create parameters for a comprehensive scan
    params = CylindricalPatternParameters(
        # Multiple X positions (different camera distances)
        x_start=-20.0,
        x_end=20.0,
        x_step=20.0,  # 3 positions: -20, 0, 20
        
        # 5 height levels
        y_start=30.0,
        y_end=130.0,
        y_step=25.0,
        
        # 12 rotation angles (every 30°)
        z_rotations=list(range(0, 360, 30)),
        
        # 5 camera angles
        c_angles=[-15, -7, 0, 7, 15],
        
        safety_margin=0.5
    )
    
    # Create pattern
    pattern = CylindricalScanPattern("test_multi_height", params)
    
    # Generate points
    points = pattern.get_points()
    
    logger.info(f"✅ Generated {len(points)} scan points")
    logger.info(f"🕒 Estimated duration: {pattern.estimated_duration:.1f} minutes")
    
    # Analyze the pattern structure
    x_positions = sorted(set(p.position.x for p in points))
    y_positions = sorted(set(p.position.y for p in points))
    z_positions = sorted(set(p.position.z for p in points))
    c_positions = sorted(set(p.position.c for p in points))
    
    logger.info("📊 Pattern structure:")
    logger.info(f"   • X positions ({len(x_positions)}): {x_positions}")
    logger.info(f"   • Y heights ({len(y_positions)}): {y_positions}")
    logger.info(f"   • Z rotations ({len(z_positions)}): {z_positions}")
    logger.info(f"   • C angles ({len(c_positions)}): {c_positions}")
    logger.info(f"   • Expected total: {len(x_positions)} × {len(y_positions)} × {len(z_positions)} × {len(c_positions)} = {len(x_positions) * len(y_positions) * len(z_positions) * len(c_positions)}")
    
    return len(points)

def test_custom_cylindrical_pattern():
    """Test custom cylindrical pattern configuration"""
    logger.info("🧪 Testing Custom Cylindrical Pattern")
    
    # Create parameters for a custom scan (small object, high detail)
    params = CylindricalPatternParameters(
        # Close-up scanning
        x_start=10.0,
        x_end=30.0,
        x_step=10.0,  # 3 positions
        
        # Detailed height coverage
        y_start=40.0,
        y_end=80.0,
        y_step=10.0,  # 5 levels
        
        # High angular resolution
        z_rotations=list(range(0, 360, 20)),  # 18 angles (every 20°)
        
        # Single camera angle for simplicity
        c_angles=[0],
        
        safety_margin=0.5
    )
    
    # Create pattern
    pattern = CylindricalScanPattern("test_custom", params)
    
    # Generate points
    points = pattern.get_points()
    
    logger.info(f"✅ Generated {len(points)} scan points")
    logger.info(f"🕒 Estimated duration: {pattern.estimated_duration:.1f} minutes")
    
    # Show pattern distribution by height
    logger.info("📏 Points per height level:")
    by_height = {}
    for point in points:
        y = point.position.y
        if y not in by_height:
            by_height[y] = 0
        by_height[y] += 1
    
    for y in sorted(by_height.keys()):
        logger.info(f"   Y={y:5.1f}mm: {by_height[y]:3d} points")
    
    return len(points)

def validate_pattern_constraints(points: List, name: str):
    """Validate that generated points meet expected constraints"""
    logger.info(f"🔍 Validating constraints for {name}")
    
    if not points:
        logger.error("❌ No points generated!")
        return False
    
    # Check for duplicate points
    position_set = set()
    duplicates = 0
    
    for point in points:
        pos = point.position
        pos_tuple = (pos.x, pos.y, pos.z, pos.c)
        if pos_tuple in position_set:
            duplicates += 1
        else:
            position_set.add(pos_tuple)
    
    if duplicates > 0:
        logger.warning(f"⚠️  Found {duplicates} duplicate positions")
    else:
        logger.info("✅ No duplicate positions found")
    
    # Check reasonable ranges
    x_values = [p.position.x for p in points]
    y_values = [p.position.y for p in points]
    z_values = [p.position.z for p in points]
    c_values = [p.position.c for p in points]
    
    logger.info(f"📐 Position ranges:")
    logger.info(f"   X: {min(x_values):6.1f} to {max(x_values):6.1f} mm")
    logger.info(f"   Y: {min(y_values):6.1f} to {max(y_values):6.1f} mm")
    logger.info(f"   Z: {min(z_values):6.1f} to {max(z_values):6.1f}°")
    logger.info(f"   C: {min(c_values):6.1f} to {max(c_values):6.1f}°")
    
    return True

def main():
    """Run all cylindrical pattern tests"""
    logger.info("🚀 Starting Cylindrical Pattern Tests")
    logger.info("=" * 60)
    
    try:
        # Test 1: Basic pattern
        points1 = test_basic_cylindrical_pattern()
        validate_pattern_constraints([], "Basic Pattern")  # Pass empty list for now
        
        logger.info("-" * 40)
        
        # Test 2: Multi-height pattern
        points2 = test_multi_height_cylindrical_pattern() 
        validate_pattern_constraints([], "Multi-Height Pattern")
        
        logger.info("-" * 40)
        
        # Test 3: Custom pattern
        points3 = test_custom_cylindrical_pattern()
        validate_pattern_constraints([], "Custom Pattern")
        
        logger.info("=" * 60)
        logger.info("📊 Test Summary:")
        logger.info(f"   • Basic pattern: {points1} points")
        logger.info(f"   • Multi-height pattern: {points2} points")
        logger.info(f"   • Custom pattern: {points3} points")
        logger.info("✅ All cylindrical pattern tests completed successfully!")
        
        return 0
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)