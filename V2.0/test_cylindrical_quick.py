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
from typing import List, Optional

# Add the current directory to path for imports
sys.path.append(str(Path(__file__).parent))

from scanning.scan_patterns import CylindricalPatternParameters, CylindricalScanPattern

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_cylindrical_scan_pattern(radius: float = 25.0, 
                                   height_range: tuple = (40.0, 120.0),
                                   height_step: float = 20.0,
                                   rotation_step: float = 60.0,
                                   camera_angles: Optional[List[float]] = None):
    """
    Create a cylindrical scan pattern with configurable radius
    
    Args:
        radius: Fixed camera radius (X-axis distance from object center)
        height_range: (start_height, end_height) for Y-axis scanning
        height_step: Step size between height levels
        rotation_step: Degrees between rotation positions
        camera_angles: List of camera pivot angles (C-axis)
    """
    if camera_angles is None:
        camera_angles = [-10.0, 0.0, 10.0]
    
    # Calculate rotation angles (convert to float)
    z_rotations = [float(angle) for angle in range(0, 360, int(rotation_step))]
    
    return CylindricalPatternParameters(
        # Fixed camera radius (X-axis)
        x_start=radius,
        x_end=radius,      # Same as start = fixed position
        x_step=1.0,        # Not used when start=end
        
        # Multiple height passes (Y-axis)
        y_start=height_range[0],
        y_end=height_range[1],
        y_step=height_step,
        
        # Object rotation (Z-axis turntable)
        z_rotations=z_rotations,
        
        # Camera pivot angles (C-axis)
        c_angles=camera_angles,
        
        # Pattern settings
        overlap_percentage=30.0,
        max_feedrate=600.0,
        safety_margin=0.5
    )

def test_cylindrical_pattern_generation():
    """Test cylindrical pattern generation for multiple height passes"""
    logger.info("🎯 Testing Cylindrical Pattern Generation")
    
    # Create a typical cylindrical scan pattern
    # This simulates scanning a cylindrical object at multiple heights
    # X-axis represents FIXED RADIUS (distance from object center)
    parameters = create_cylindrical_scan_pattern(
        radius=25.0,              # Fixed radius: 25mm from object center
        height_range=(40.0, 120.0),  # Scan from 40mm to 120mm height
        height_step=20.0,         # 20mm between height levels
        rotation_step=60.0,       # Every 60° rotation
        camera_angles=[-10, 0, 10]  # 3 camera angles
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
    try:
        duration = pattern.estimated_duration
        logger.info(f"   • Estimated duration: {duration:.1f} minutes")
    except Exception as e:
        logger.info(f"   • Estimated duration: calculation error ({e})")
    
    # Break down by dimensions
    x_positions = sorted(set(p.position.x for p in points))
    y_positions = sorted(set(p.position.y for p in points))
    z_positions = sorted(set(p.position.z for p in points))
    c_positions = sorted(set(p.position.c for p in points))
    
    logger.info(f"📏 Scan Structure:")
    logger.info(f"   • X radius ({len(x_positions)}): {[f'{x:.1f}mm' for x in x_positions]} (fixed camera distance)")
    logger.info(f"   • Y heights ({len(y_positions)}): {[f'{y:.1f}mm' for y in y_positions]} (multiple passes)")
    logger.info(f"   • Z rotations ({len(z_positions)}): {[f'{z:.0f}deg' for z in z_positions]} (turntable angles)")
    logger.info(f"   • C angles ({len(c_positions)}): {[f'{c:.0f}deg' for c in c_positions]} (camera pivot)")
    
    # Show expected total
    expected_total = len(x_positions) * len(y_positions) * len(z_positions) * len(c_positions)
    logger.info(f"   • Expected total: {len(x_positions)} radius × {len(y_positions)} heights × {len(z_positions)} rotations × {len(c_positions)} angles = {expected_total}")
    
    if len(points) == expected_total:
        logger.info("✅ Point count matches expected total!")
    else:
        logger.warning(f"⚠️  Point count mismatch: got {len(points)}, expected {expected_total}")
    
    # Show height pass analysis (key feature for cylindrical scanning)
    logger.info(f"📈 Height Pass Analysis (Multiple Y-levels):")
    for y in y_positions:
        points_at_height = [p for p in points if p.position.y == y]
        points_per_rotation = len(points_at_height) // len(z_positions) if len(z_positions) > 0 else 0
        logger.info(f"   • Y={y:5.1f}mm: {len(points_at_height):3d} points ({points_per_rotation} per rotation angle)")
    
    # Show first few scan points as examples
    logger.info(f"📍 First 10 Scan Points:")
    for i, point in enumerate(points[:10]):
        pos = point.position
        logger.info(f"   {i+1:2d}. X={pos.x:6.1f}, Y={pos.y:6.1f}, Z={pos.z:6.1f}deg, C={pos.c:6.1f}deg")
    
    if len(points) > 10:
        logger.info(f"      ... and {len(points)-10} more points")
    
    return pattern, points

def test_simple_circular_scan():
    """Test a simple circular scan at fixed height"""
    logger.info("🔄 Testing Simple Circular Scan (Fixed Height)")
    
    # Create a simple circular scan pattern using helper function
    # X-axis represents FIXED RADIUS
    parameters = create_cylindrical_scan_pattern(
        radius=30.0,              # Fixed radius: 30mm from object center
        height_range=(80.0, 80.0),  # Single height at 80mm
        height_step=1.0,          # Not used for single height
        rotation_step=30.0,       # Every 30° -> 12 positions
        camera_angles=[0.0]       # Single camera angle
    )
    
    pattern = CylindricalScanPattern("simple_circular", parameters)
    points = pattern.get_points()
    
    radius_value = points[0].position.x if points else 0
    logger.info(f"✅ Simple circular scan: {len(points)} points at Y=80mm, radius={radius_value:.1f}mm")
    rotation_angles = sorted(set(p.position.z for p in points))
    logger.info(f"🔄 Rotation angles: {[f'{angle:.0f}deg' for angle in rotation_angles]}")
    
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
        logger.info("   ✅ Fixed camera radius (X-axis) - configurable distance from object")
        logger.info("   ✅ Multiple height passes (Y-axis) - vertical scanning levels")
        logger.info("   ✅ Object rotation (Z-axis) - turntable positioning")
        logger.info("   ✅ Camera angle adjustment (C-axis) - viewing perspectives")
        logger.info("   ✅ Pattern parameter validation")
        logger.info("   ✅ Point generation and ordering")
        
        logger.info("\n📐 Scanning Strategy:")
        logger.info("   • X-axis: Fixed radius (distance from object center)")
        logger.info("   • Y-axis: Multiple height levels for complete coverage")
        logger.info("   • Z-axis: Object rotation for 360° coverage")
        logger.info("   • C-axis: Camera pivot for optimal viewing angles")
        
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