#!/usr/bin/env python3
"""
Quick test to validate cylindrical scan fixes:
1. Single servo angle (C-axis fixed)  
2. Z-axis rotation (cylinder rotation)
3. Correct point calculations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scanning.scan_patterns import CylindricalPatternParameters, CylindricalScanPattern

def test_cylindrical_scan_fixes():
    """Test that cylindrical scan properly uses Z-axis rotation with fixed C-axis"""
    
    print("🔧 Testing Cylindrical Scan Fixes")
    print("=" * 50)
    
    # Test parameters that should generate 10 points (5 heights × 2 rotations)
    params = CylindricalPatternParameters(
        x_start=30.0,     # Fixed radius
        x_end=30.0,       # Same as start
        y_start=40.0,     # Height start
        y_end=80.0,       # Height end  
        y_step=10.0,      # Height step (5 levels: 40, 50, 60, 70, 80)
        z_rotations=[0.0, 180.0],  # Z-axis: 2 cylinder rotations
        c_angles=[0.0],   # C-axis: single fixed servo angle
        safety_margin=0.5
    )
    
    # Create pattern
    pattern = CylindricalScanPattern("test_cylindrical", params)
    
    # Generate points
    points = pattern.generate_points()
    
    print(f"📊 Generated {len(points)} scan points")
    print(f"Expected: 5 heights × 2 rotations = 10 points")
    
    # Analyze axis usage
    z_values = sorted(list(set(p.position.z for p in points)))
    c_values = sorted(list(set(p.position.c for p in points)))
    y_values = sorted(list(set(p.position.y for p in points)))
    
    print(f"\n🔄 Z-axis rotations (cylinder): {z_values}")
    print(f"📷 C-axis angles (servo): {c_values}")
    print(f"📏 Y-axis heights: {y_values}")
    
    # Check correctness
    success = True
    
    if len(points) != 10:
        print(f"❌ FAIL: Expected 10 points, got {len(points)}")
        success = False
    else:
        print("✅ Point count correct")
    
    if len(z_values) != 2 or z_values != [0.0, 180.0]:
        print(f"❌ FAIL: Expected Z-axis [0.0, 180.0], got {z_values}")
        success = False
    else:
        print("✅ Z-axis rotation correct")
    
    if len(c_values) != 1 or c_values[0] != 0.0:
        print(f"❌ FAIL: Expected single C-axis [0.0], got {c_values}")
        success = False
    else:
        print("✅ C-axis fixed correctly")
    
    if len(y_values) != 5:
        print(f"❌ FAIL: Expected 5 Y levels, got {len(y_values)}")
        success = False
    else:
        print("✅ Y-axis levels correct")
    
    # Show sample points
    print(f"\n📋 Sample scan points:")
    for i, point in enumerate(points[:6]):
        pos = point.position
        print(f"  {i+1:2d}. X:{pos.x:6.1f}, Y:{pos.y:6.1f}, Z:{pos.z:6.1f}°, C:{pos.c:6.1f}°")
    
    if len(points) > 6:
        print(f"  ... ({len(points)-6} more points)")
    
    print(f"\n{'✅ ALL TESTS PASSED' if success else '❌ SOME TESTS FAILED'}")
    return success

if __name__ == "__main__":
    test_cylindrical_scan_fixes()