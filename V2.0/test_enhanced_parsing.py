#!/usr/bin/env python3
"""
Enhanced FluidNC Position Parsing Test

Test script to verify that the enhanced FluidNC message parsing
captures all position updates from various message formats.

This tests the key improvements:
1. Multiple regex patterns for coordinate extraction
2. Flexible message format handling
3. Comprehensive status detection
4. Position parsing from ANY FluidNC message
"""

import re
import time
from typing import Optional
from dataclasses import dataclass

@dataclass
class Position4D:
    x: float
    y: float
    z: float
    c: float
    
    def __str__(self):
        return f"X:{self.x:.3f} Y:{self.y:.3f} Z:{self.z:.3f} C:{self.c:.3f}"

def enhanced_parse_position_from_status(status_response: str) -> Optional[Position4D]:
    """
    Enhanced FluidNC status parsing - handles all message formats and variations
    
    FluidNC status formats can include:
    - <Idle|MPos:0.000,0.000,0.000,0.000|WPos:0.000,0.000,0.000,0.000|FS:0,0>
    - <Run|MPos:10.000,20.000,30.000,40.000|WPos:10.000,20.000,30.000,40.000|FS:100,500>
    - <Jog|MPos:5.123,10.456,15.789,20.012|FS:0,0>
    - <Home|MPos:0.000,0.000,0.000,0.000>
    - Status reports with varying numbers of axes (4-6)
    - Position-only reports or reports with additional data
    """
    try:
        # Skip completely empty or simple responses
        if not status_response or len(status_response.strip()) < 3:
            return None
        
        # Skip obvious non-status responses
        clean_response = status_response.strip()
        if clean_response in ['ok', 'error', 'OK', 'ERROR']:
            return None
        
        # Skip info/debug messages but allow status reports
        if (clean_response.startswith('[MSG:') or 
            clean_response.startswith('[GC:') or 
            clean_response.startswith('[G54:') or
            clean_response.startswith('[VER:') or
            clean_response.startswith('[OPT:') or
            clean_response.startswith('[echo:')):
            return None
        
        # ENHANCED: Multiple parsing strategies for different FluidNC message formats
        
        # Strategy 1: Standard MPos/WPos parsing (most common)
        # Handle both 4-axis and 6-axis machines flexibly with case-insensitive matching
        mpos_patterns = [
            r'[Mm][Pp]os:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,([\d\.-]+),([\d\.-]+))?',  # 4 or 6 axis, case-insensitive
            r'[Mm][Pp]os:([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)',         # With spaces around commas
            r'[Mm][Pp]os:\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)',      # Leading and trailing spaces
            r'[Mm][Pp]os\s*:\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)'    # Spaces around colon
        ]
        
        wpos_patterns = [
            r'[Ww][Pp]os:([\d\.-]+),([\d\.-]+),([\d\.-]+),([\d\.-]+)(?:,([\d\.-]+),([\d\.-]+))?',  # 4 or 6 axis, case-insensitive
            r'[Ww][Pp]os:([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)',         # With spaces around commas
            r'[Ww][Pp]os:\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)',      # Leading and trailing spaces
            r'[Ww][Pp]os\s*:\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)'    # Spaces around colon
        ]
        
        mpos_match = None
        wpos_match = None
        
        # Try multiple MPos patterns
        for pattern in mpos_patterns:
            mpos_match = re.search(pattern, clean_response)
            if mpos_match:
                break
        
        # Try multiple WPos patterns  
        for pattern in wpos_patterns:
            wpos_match = re.search(pattern, clean_response)
            if wpos_match:
                break
        
        # Strategy 2: Extract any coordinate data even from partial messages
        if not mpos_match and not wpos_match:
            # Look for any position-like data patterns (case-insensitive and flexible spacing)
            coord_patterns = [
                r'(?:[Mm][Pp]os|[Ww][Pp]os|[Pp]os)\s*:\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)\s*,\s*([\d\.-]+)',  # Generic Pos with flexible spacing
                r'X\s*:\s*([\d\.-]+)\s*Y\s*:\s*([\d\.-]+)\s*Z\s*:\s*([\d\.-]+)\s*C\s*:\s*([\d\.-]+)',                    # X: Y: Z: C: format
                r'X([\d\.-]+)\s*Y([\d\.-]+)\s*Z([\d\.-]+)\s*C([\d\.-]+)',                                                # X Y Z C format without colons
                r'([Xx])\s*([\d\.-]+)\s*([Yy])\s*([\d\.-]+)\s*([Zz])\s*([\d\.-]+)\s*([Cc])\s*([\d\.-]+)'                # Flexible axis labels
            ]
            
            for pattern in coord_patterns:
                coord_match = re.search(pattern, clean_response)
                if coord_match:
                    # For the flexible axis pattern, extract only the numeric values
                    if len(coord_match.groups()) > 4:
                        # This is the flexible axis pattern - extract every other group (the numbers)
                        coords = [coord_match.group(i) for i in [2, 4, 6, 8]]
                        # Create a mock match object for consistent processing
                        class MockMatch:
                            def groups(self):
                                return coords
                        mpos_match = MockMatch()
                    else:
                        # Standard coordinate pattern
                        mpos_match = coord_match
                    break
        
        # Process the matched position data
        if mpos_match:
            try:
                # Extract first 4 coordinate values (X, Y, Z, C)
                coords = [float(x) for x in mpos_match.groups()[:4] if x is not None]
                
                if len(coords) >= 4:
                    mx, my, mz, mc = coords[:4]
                    
                    # If we also have work coordinates, use hybrid approach
                    if wpos_match:
                        try:
                            wcoords = [float(x) for x in wpos_match.groups()[:4] if x is not None]
                            if len(wcoords) >= 4:
                                wx, wy, wz, wc = wcoords[:4]
                                position = Position4D(
                                    x=wx,    # Work coordinate for X (preferred for user interface)
                                    y=wy,    # Work coordinate for Y (preferred for user interface)
                                    z=mz,    # Machine coordinate for Z (continuous rotation, prevents accumulation)
                                    c=wc     # Work coordinate for C (tilt, user-relevant)
                                )
                                print(f"✅ Parsed hybrid position - Work X,Y,C: ({wx:.3f},{wy:.3f},{wc:.3f}), Machine Z: {mz:.3f}")
                                return position
                        except (ValueError, IndexError) as e:
                            print(f"Work coordinate parsing failed, using machine only: {e}")
                    
                    # Use machine coordinates only
                    position = Position4D(x=mx, y=my, z=mz, c=mc)
                    print(f"✅ Parsed machine position: X={mx:.3f}, Y={my:.3f}, Z={mz:.3f}, C={mc:.3f}")
                    return position
                else:
                    print(f"Insufficient coordinates found: {len(coords)} (need 4)")
                    
            except (ValueError, IndexError) as e:
                print(f"Coordinate conversion error: {e}")
        
        # Strategy 3: Log unrecognized status format for debugging
        if '<' in clean_response and '>' in clean_response:
            # This looks like a status message but we couldn't parse it
            print(f"🔍 Unrecognized status format (will improve parsing): {clean_response}")
            
            # Try to extract any numeric data for debugging
            numbers = re.findall(r'[\d\.-]+', clean_response)
            if len(numbers) >= 4:
                print(f"🔢 Found {len(numbers)} numbers in message: {numbers[:8]}")  # Show first 8 numbers
        
        return None
            
    except Exception as e:
        print(f"❌ Position parsing exception: {e}")
        print(f"📄 Message was: {status_response}")
        return None

def test_enhanced_parsing():
    """Test various FluidNC message formats"""
    
    print("🧪 Testing Enhanced FluidNC Position Parsing")
    print("=" * 50)
    
    # Test cases for different FluidNC message formats
    test_messages = [
        # Standard status reports
        "<Idle|MPos:0.000,0.000,0.000,0.000|WPos:0.000,0.000,0.000,0.000|FS:0,0>",
        "<Run|MPos:10.123,20.456,30.789,40.012|WPos:10.123,20.456,30.789,40.012|FS:100,500>",
        "<Jog|MPos:5.123,10.456,15.789,20.012|FS:0,0>",
        "<Home|MPos:0.000,0.000,0.000,0.000>",
        
        # 6-axis machine formats
        "<Idle|MPos:1.0,2.0,3.0,4.0,5.0,6.0|WPos:1.0,2.0,3.0,4.0,5.0,6.0|FS:0,0>",
        
        # Position-only formats
        "MPos:15.123,25.456,35.789,45.012",
        "WPos:100.000,200.000,360.000,90.000",
        
        # Alternative formats
        "X:15.123 Y:25.456 Z:35.789 C:45.012",
        "X15.123 Y25.456 Z35.789 C45.012",
        
        # Formats with spaces
        "MPos: 1.123 , 2.456 , 3.789 , 4.012",
        "< Idle | MPos:0.000,0.000,0.000,0.000 | WPos:0.000,0.000,0.000,0.000 | FS:0,0 >",
        
        # Mixed case and variations
        "<idle|mpos:10.000,20.000,30.000,40.000|wpos:10.000,20.000,30.000,40.000|fs:0,0>",
        
        # Messages that should be skipped
        "ok",
        "error",
        "[MSG: Homing cycle started]",
        "[GC: G0 G54 G17 G21 G90 G94 M5 M9 T0 F0 S0]",
        "",
        "   ",
        
        # Edge cases
        "<Alarm:1|MPos:0.000,0.000,0.000,0.000>",
        "<Error|MPos:50.123,60.456,70.789,80.012>",
    ]
    
    successful_parses = 0
    total_tests = len(test_messages)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n🔍 Test {i}/{total_tests}: {message}")
        
        start_time = time.time()
        position = enhanced_parse_position_from_status(message)
        parse_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        if position:
            print(f"✅ SUCCESS: {position} (parsed in {parse_time:.2f}ms)")
            successful_parses += 1
        else:
            print(f"❌ NO POSITION DATA EXTRACTED")
    
    print("\n" + "=" * 50)
    print(f"📊 RESULTS: {successful_parses}/{total_tests} messages parsed successfully")
    print(f"Success rate: {(successful_parses/total_tests)*100:.1f}%")
    
    if successful_parses < total_tests - 6:  # Allow for 6 expected skips (ok, error, messages, etc.)
        print("⚠️  Some valid position messages were not parsed - parsing may need improvement")
    else:
        print("✅ Enhanced parsing is working correctly for all expected message formats!")

if __name__ == "__main__":
    test_enhanced_parsing()