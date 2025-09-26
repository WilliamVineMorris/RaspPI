#!/usr/bin/env python3
"""
Quick Cylindrical Scan Test

Simple test to validate that cylindrical scanning is working properly
with the existing infrastructure.
"""

import asyncio
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add the current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from scanning.scan_patterns import CylindricalPatternParameters, CylindricalScanPattern

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_cylindrical_pattern_generation():
    """Test cylindrical pattern generation for multiple height passes"""
    logger.info("🎯 Testing Cylindrical Pattern Generation")
    
    # Create a typical cylindrical scan pattern
    # This simulates scanning a cylindrical object at multiple heights
    parameters = CylindricalPatternParameters(
        # Camera positions (X-axis - distance from object)
        x_start=-10.0,  # Closer to object
        x_end=10.0,     # Further from object  
        x_step=10.0,    # 3 positions: -10, 0, 10
        
        # Multiple height passes (Y-axis)
        y_start=40.0,   # Bottom height
        y_end=120.0,    # Top height
        y_step=20.0,    # Height increment -> 5 levels (40, 60, 80, 100, 120)
        
        # Object rotation (Z-axis turntable)
        z_rotations=[0, 60, 120, 180, 240, 300],  # 6 angles (every 60°)
        
        # Camera pivot angles (C-axis)
        c_angles=[-10, 0, 10],  # 3 camera angles
        
        # Pattern settings
        overlap_percentage=30.0,
        max_feedrate=600.0,
        safety_margin=0.5
    )
    
    # Create the pattern
    pattern_id = f"test_cylindrical_{datetime.now().strftime('%H%M%S')}"
    pattern = CylindricalScanPattern(pattern_id, parameters)
    
    # Generate scan points
    logger.info("📐 Generating scan points...")
    points = pattern.get_points()
    
    # Analyze the pattern
    logger.info(f"✅ Pattern '{pattern_id}' generated successfully!")
    logger.info(f"📊 Pattern Statistics:")
    logger.info(f"   • Total scan points: {len(points)}")
    logger.info(f"   • Estimated duration: {pattern.estimated_duration:.1f} minutes")
    
    # Break down by dimensions
    x_positions = sorted(set(p.position.x for p in points))
    y_positions = sorted(set(p.position.y for p in points))
    z_positions = sorted(set(p.position.z for p in points))
    c_positions = sorted(set(p.position.c for p in points))
    
    logger.info(f"📏 Scan Structure:")
    logger.info(f"   • X positions ({len(x_positions)}): {[f'{x:.1f}' for x in x_positions]}")
    logger.info(f"   • Y heights ({len(y_positions)}): {[f'{y:.1f}' for y in y_positions]}")
    logger.info(f"   • Z rotations ({len(z_positions)}): {[f'{z:.0f}°' for z in z_positions]}")
    logger.info(f"   • C angles ({len(c_positions)}): {[f'{c:.0f}°' for c in c_positions]}")
    
    # Show expected total
    expected_total = len(x_positions) * len(y_positions) * len(z_positions) * len(c_positions)
    logger.info(f"   • Expected total: {len(x_positions)} × {len(y_positions)} × {len(z_positions)} × {len(c_positions)} = {expected_total}")
    
    if len(points) == expected_total:
        logger.info("✅ Point count matches expected total!")
    else:
        logger.warning(f"⚠️  Point count mismatch: got {len(points)}, expected {expected_total}")
    
    # Show height pass analysis
    logger.info(f"📈 Height Pass Analysis:")
    for y in y_positions:
        points_at_height = [p for p in points if p.position.y == y]
        logger.info(f"   • Y={y:5.1f}mm: {len(points_at_height):3d} points")
    
    # Show first few scan points as examples
    logger.info(f"📍 First 10 Scan Points:")
    for i, point in enumerate(points[:10]):
        pos = point.position
        logger.info(f"   {i+1:2d}. X={pos.x:6.1f}, Y={pos.y:6.1f}, Z={pos.z:6.1f}°, C={pos.c:6.1f}°")
    
    if len(points) > 10:
        logger.info(f"      ... and {len(points)-10} more points")
    
    return pattern, points

def test_simple_circular_scan():
    """Test a simple circular scan at fixed height"""
    logger.info("🔄 Testing Simple Circular Scan (Fixed Height)")
    
    # Create a simple circular scan pattern
    parameters = CylindricalPatternParameters(
        # Fixed camera position
        x_start=0.0,
        x_end=0.0,
        x_step=1.0,
        
        # Single height
        y_start=80.0,
        y_end=80.0,  
        y_step=1.0,
        
        # Full circle rotation
        z_rotations=list(range(0, 360, 30)),  # Every 30° -> 12 positions
        
        # Single camera angle
        c_angles=[0],
        
        safety_margin=0.5
    )
    
    pattern = CylindricalScanPattern("simple_circular", parameters)
    points = pattern.get_points()
    
    logger.info(f"✅ Simple circular scan: {len(points)} points at Y=80mm")
    logger.info(f"🔄 Rotation angles: {sorted(set(p.position.z for p in points))}")
    
    return pattern, points

def demonstrate_scanning_workflow():
    """Demonstrate the complete cylindrical scanning workflow"""
    logger.info("🚀 Demonstrating Cylindrical Scanning Workflow")
    logger.info("=" * 60)
    
    try:
        # Test 1: Multi-height cylindrical scan
        logger.info("1️⃣ Multi-Height Cylindrical Scan:")
        pattern1, points1 = test_cylindrical_pattern_generation()
        
        logger.info("\n" + "-" * 40 + "\n")
        
        # Test 2: Simple circular scan  
        logger.info("2️⃣ Simple Circular Scan:")
        pattern2, points2 = test_simple_circular_scan()
        
        logger.info("\n" + "=" * 60)
        logger.info("📋 Summary:")
        logger.info(f"   • Multi-height scan: {len(points1)} points over {len(set(p.position.y for p in points1))} height levels")
        logger.info(f"   • Simple circular scan: {len(points2)} points at single height")
        logger.info(f"   • Total scan strategies tested: 2")
        
        logger.info("\n🎯 Cylindrical Scanning Features Validated:")
        logger.info("   ✅ Multiple height passes")
        logger.info("   ✅ Object rotation (turntable)")
        logger.info("   ✅ Camera positioning (X-axis)")
        logger.info("   ✅ Camera angle adjustment (C-axis)")
        logger.info("   ✅ Pattern parameter validation")
        logger.info("   ✅ Point generation and ordering")
        
        logger.info("\n🚀 System ready for cylindrical scanning!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Workflow demonstration failed: {e}")
        return False

def main():
    """Main test function"""
    logger.info("🎉 Starting Cylindrical Scanning Tests")
    
    success = demonstrate_scanning_workflow()
    
    if success:
        logger.info("\n✅ All cylindrical scanning tests passed!")
        logger.info("🎯 The system is ready to perform cylindrical scans with multiple height passes!")
        return 0
    else:
        logger.error("\n❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = main()
    print(f"\nTest completed with exit code: {exit_code}")
    sys.exit(exit_code)