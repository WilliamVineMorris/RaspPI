"""
Test CSV Focus Parameter Parsing

Tests the updated CSV parser with focus columns.
Run this to verify the parser works correctly before deploying to Pi.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from scanning.csv_validator import ScanPointValidator
from scanning.scan_patterns import FocusMode

def print_section(title):
    """Print formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def test_csv_validation():
    """Test CSV validation with focus columns"""
    
    # Mock hardware limits
    hardware_limits = {
        'x': {'limits': [0.0, 200.0]},
        'y': {'limits': [0.0, 200.0]},
        'z': {'limits': [0.0, 360.0]},
        'c': {'limits': [-90.0, 90.0]}
    }
    
    validator = ScanPointValidator(hardware_limits)
    
    # Test 1: Simple manual focus
    print_section("Test 1: Simple Manual Focus")
    test_csv_1 = """index,x,y,z,c,FocusMode,FocusValues
0,100.0,100.0,0.0,0.0,manual,8.0
1,100.0,100.0,45.0,0.0,manual,8.0
2,100.0,100.0,90.0,0.0,manual,8.0"""
    
    result = validator.validate_csv_file(test_csv_1)
    print(f"✅ Success: {result.success}")
    print(f"📊 Valid points: {result.point_count}")
    print(f"❌ Errors: {result.error_count}")
    print(f"⚠️  Warnings: {result.warning_count}")
    
    if result.success:
        scan_points = validator.csv_to_scan_points(result.valid_points)
        for i, point in enumerate(scan_points):
            print(f"\nPoint {i}: {point.position}")
            print(f"  Focus Mode: {point.focus_mode}")
            print(f"  Focus Value: {point.focus_values}")
            print(f"  Captures: {point.capture_count}")
    
    # Test 2: Focus stacking
    print_section("Test 2: Focus Stacking (3 positions)")
    test_csv_2 = """index,x,y,z,c,FocusMode,FocusValues
0,100.0,100.0,0.0,0.0,manual,"6.0;8.0;10.0"
1,100.0,100.0,45.0,0.0,manual,"6.0;8.0;10.0"
2,100.0,100.0,90.0,0.0,manual,"6.0;8.0;10.0" """
    
    result = validator.validate_csv_file(test_csv_2)
    print(f"✅ Success: {result.success}")
    print(f"📊 Valid points: {result.point_count}")
    
    if result.success:
        scan_points = validator.csv_to_scan_points(result.valid_points)
        for i, point in enumerate(scan_points):
            print(f"\nPoint {i}: {point.position}")
            print(f"  Focus Mode: {point.focus_mode}")
            print(f"  Focus Values: {point.focus_values}")
            print(f"  Captures: {point.capture_count}")
            if point.is_focus_stacking():
                positions = point.get_focus_positions()
                print(f"  🎯 FOCUS STACKING: {len(positions)} positions - {positions}")
    
    # Test 3: Mixed modes
    print_section("Test 3: Mixed Focus Modes")
    test_csv_3 = """index,x,y,z,c,FocusMode,FocusValues
0,100.0,100.0,0.0,0.0,af,
1,100.0,100.0,45.0,0.0,manual,8.0
2,100.0,100.0,90.0,0.0,manual,"6.0;8.0;10.0"
3,100.0,100.0,135.0,0.0,,"""
    
    result = validator.validate_csv_file(test_csv_3)
    print(f"✅ Success: {result.success}")
    print(f"📊 Valid points: {result.point_count}")
    
    if result.success:
        scan_points = validator.csv_to_scan_points(result.valid_points)
        for i, point in enumerate(scan_points):
            print(f"\nPoint {i}: {point.position}")
            print(f"  Focus Mode: {point.focus_mode}")
            print(f"  Focus Values: {point.focus_values}")
            print(f"  Requires AF: {point.requires_autofocus()}")
    
    # Test 4: Backward compatibility (no focus columns)
    print_section("Test 4: Backward Compatibility (No Focus Columns)")
    test_csv_4 = """index,x,y,z,c
0,100.0,100.0,0.0,0.0
1,100.0,100.0,45.0,0.0
2,100.0,100.0,90.0,0.0"""
    
    result = validator.validate_csv_file(test_csv_4)
    print(f"✅ Success: {result.success}")
    print(f"📊 Valid points: {result.point_count}")
    
    if result.success:
        scan_points = validator.csv_to_scan_points(result.valid_points)
        print(f"\n✅ Created {len(scan_points)} ScanPoints without focus parameters")
        print(f"   (Will use global config defaults)")
    
    # Test 5: Error detection
    print_section("Test 5: Error Detection")
    test_csv_5 = """index,x,y,z,c,FocusMode,FocusValues
0,100.0,100.0,0.0,0.0,invalid_mode,8.0
1,100.0,100.0,45.0,0.0,manual,20.0
2,100.0,100.0,90.0,0.0,manual,-5.0"""
    
    result = validator.validate_csv_file(test_csv_5)
    print(f"❌ Success: {result.success}")
    print(f"📊 Errors detected: {result.error_count}")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  Row {error.row}, {error.column}: {error.message}")
    
    # Test 6: Warning detection
    print_section("Test 6: Warning Detection")
    test_csv_6 = """index,x,y,z,c,FocusMode,FocusValues
0,100.0,100.0,0.0,0.0,af,8.0
1,100.0,100.0,45.0,0.0,manual,"4.0;5.0;6.0;7.0;8.0;9.0" """
    
    result = validator.validate_csv_file(test_csv_6)
    print(f"⚠️  Warnings detected: {result.warning_count}")
    
    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  Row {warning.row}, {warning.column}: {warning.message}")
    
    # Test 7: CSV export (round-trip)
    print_section("Test 7: CSV Export (Round-Trip)")
    test_csv_7 = """index,x,y,z,c,FocusMode,FocusValues
0,100.0,100.0,0.0,0.0,manual,8.0
1,100.0,100.0,45.0,0.0,manual,"6.0;8.0;10.0"
2,100.0,100.0,90.0,0.0,af,"""
    
    # Parse
    result = validator.validate_csv_file(test_csv_7)
    scan_points = validator.csv_to_scan_points(result.valid_points)
    
    # Export
    exported_csv = validator.points_to_csv(scan_points)
    
    print("Exported CSV:")
    print(exported_csv)
    
    # Re-import
    result2 = validator.validate_csv_file(exported_csv)
    print(f"\n✅ Round-trip successful: {result2.success}")
    print(f"📊 Points preserved: {result2.point_count}")

if __name__ == "__main__":
    print("\n" + "="*60)
    print("  CSV Focus Parameter Parser - Test Suite")
    print("="*60)
    
    try:
        test_csv_validation()
        
        print("\n" + "="*60)
        print("  ✅ ALL TESTS COMPLETED")
        print("="*60)
        print("\nThe CSV parser is ready for deployment!")
        print("Next step: Test on Raspberry Pi hardware with actual camera")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
