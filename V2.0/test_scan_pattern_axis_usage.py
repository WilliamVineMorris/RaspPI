#!/usr/bin/env python3
"""
Test Grid vs Cylindrical Scanning Axis Usage

This test demonstrates the correct axis usage for different scan patterns:

Grid Scan:
- X, Y: Linear positioning 
- Z: Fixed cylinder angle (or slight variations)
- C: Fixed servo angle

Cylindrical Scan:  
- X: Fixed radius (camera distance)
- Y: Vertical positioning
- Z: Rotating cylinder (0°, 45°, 90°, 135°, etc.)
- C: Fixed servo angle (consistent camera viewpoint)
"""

import sys
from pathlib import Path
import asyncio

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.types import Position4D
from scanning.scan_patterns import (
    GridScanPattern, GridPatternParameters,
    CylindricalScanPattern, CylindricalPatternParameters
)

def test_grid_pattern():
    """Test grid pattern axis usage"""
    print("=== GRID SCAN PATTERN ===")
    
    # Create grid pattern parameters
    grid_params = GridPatternParameters(
        min_x=10.0, max_x=50.0,     # X range: 10-50mm
        min_y=20.0, max_y=60.0,     # Y range: 20-60mm  
        min_z=0.0, max_z=0.1,       # Z: Fixed cylinder angle (~0°)
        min_c=-10.0, max_c=10.1,    # C: Servo range (-10° to 10°)
        x_spacing=20.0,             # 20mm grid spacing
        y_spacing=20.0,
        z_spacing=1.0,              # Minimal Z variation
        c_steps=3                   # 3 servo positions
    )
    
    # Create grid pattern
    grid_pattern = GridScanPattern("test_grid", grid_params)
    grid_points = grid_pattern.generate_points()
    
    print(f"Grid scan generated {len(grid_points)} points:")
    print("Expected: X,Y vary for coverage, Z~fixed, C may vary")
    
    for i, point in enumerate(grid_points[:6]):  # Show first 6 points
        pos = point.position
        print(f"  Point {i+1}: X={pos.x:5.1f}, Y={pos.y:5.1f}, Z={pos.z:6.1f}°, C={pos.c:6.1f}°")
    
    if len(grid_points) > 6:
        print(f"  ... and {len(grid_points) - 6} more points")

def test_cylindrical_pattern():
    """Test cylindrical pattern axis usage"""
    print("\n=== CYLINDRICAL SCAN PATTERN ===")
    
    # Create cylindrical pattern parameters
    cyl_params = CylindricalPatternParameters(
        x_start=30.0, x_end=30.0,   # X: Fixed radius (30mm)
        y_start=25.0, y_end=45.0,   # Y: Height range (25-45mm)
        y_step=20.0,                # 20mm Y steps
        z_rotations=[0, 90, 180, 270],  # Z: Cylinder rotations
        c_angles=[0.0],             # C: Fixed servo angle
    )
    
    # Create cylindrical pattern
    cyl_pattern = CylindricalScanPattern("test_cylindrical", cyl_params)
    cyl_points = cyl_pattern.generate_points()
    
    print(f"Cylindrical scan generated {len(cyl_points)} points:")
    print("Expected: X fixed (radius), Y varies (height), Z rotates (cylinder), C fixed (servo)")
    
    for i, point in enumerate(cyl_points[:8]):  # Show first 8 points
        pos = point.position
        print(f"  Point {i+1}: X={pos.x:5.1f}, Y={pos.y:5.1f}, Z={pos.z:6.1f}°, C={pos.c:6.1f}°")
    
    if len(cyl_points) > 8:
        print(f"  ... and {len(cyl_points) - 8} more points")

def analyze_pattern_differences():
    """Analyze the differences between patterns"""
    print("\n=== PATTERN ANALYSIS ===")
    
    # Quick patterns for comparison
    grid_params = GridPatternParameters(
        min_x=20.0, max_x=40.0, min_y=30.0, max_y=50.0,
        min_z=0.0, max_z=0.1, min_c=10.0, max_c=10.1,
        x_spacing=20.0, y_spacing=20.0
    )
    
    cyl_params = CylindricalPatternParameters(
        x_start=30.0, x_end=30.0, y_start=30.0, y_end=50.0,
        y_step=20.0, z_rotations=[0, 180], c_angles=[10.0]
    )
    
    grid_pattern = GridScanPattern("analysis_grid", grid_params)
    cyl_pattern = CylindricalScanPattern("analysis_cyl", cyl_params)
    
    grid_points = grid_pattern.generate_points()
    cyl_points = cyl_pattern.generate_points()
    
    print(f"Grid scan: {len(grid_points)} points")
    print(f"Cylindrical scan: {len(cyl_points)} points")
    
    if grid_points:
        g_pos = grid_points[0].position
        print(f"Grid example: X={g_pos.x}, Y={g_pos.y}, Z={g_pos.z}°, C={g_pos.c}°")
    
    if cyl_points:
        c_pos = cyl_points[0].position
        print(f"Cylindrical example: X={c_pos.x}, Y={c_pos.y}, Z={c_pos.z}°, C={c_pos.c}°")
    
    print("\n=== AXIS USAGE SUMMARY ===")
    print("Grid Scan:")
    print("  • X, Y: Variable (coverage area)")
    print("  • Z: Fixed or minimal variation (cylinder position)")  
    print("  • C: Fixed or small variation (servo angle)")
    print()
    print("Cylindrical Scan:")
    print("  • X: Fixed (camera radius/distance)")
    print("  • Y: Variable (camera height)")
    print("  • Z: Variable (CYLINDER ROTATION) ← Key difference!")
    print("  • C: Fixed (SERVO ANGLE) ← Should stay consistent!")

def main():
    """Run pattern tests"""
    print("Testing Grid vs Cylindrical Scanning Patterns")
    print("=" * 60)
    
    try:
        test_grid_pattern()
        test_cylindrical_pattern()
        analyze_pattern_differences()
        
        print("\n✅ Pattern testing completed successfully!")
        print("\nFor your hardware:")
        print("  • Use GRID scan for X,Y coverage with fixed cylinder")
        print("  • Use CYLINDRICAL scan to rotate Z-axis (cylinder) with fixed C-axis (servo)")
        
    except Exception as e:
        print(f"\n❌ Pattern testing failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)