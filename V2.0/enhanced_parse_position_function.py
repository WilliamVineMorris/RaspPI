    def _parse_position_from_status(self, status_response: str) -> Optional[Position4D]:
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
                    r'X([\d\.-]+)\s*Y([\d\.-]+)\s*Z([\d\.-]+)\s*C([\d\.-]+)'                                                 # X Y Z C format without colons
                ]
                
                for pattern in coord_patterns:
                    coord_match = re.search(pattern, clean_response)
                    if coord_match:
                        # Treat as machine position if no explicit type found
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
                                    logger.debug(f"✅ Parsed hybrid position - Work X,Y,C: ({wx:.3f},{wy:.3f},{wc:.3f}), Machine Z: {mz:.3f}")
                                    return position
                            except (ValueError, IndexError) as e:
                                logger.debug(f"Work coordinate parsing failed, using machine only: {e}")
                        
                        # Use machine coordinates only
                        position = Position4D(x=mx, y=my, z=mz, c=mc)
                        logger.debug(f"✅ Parsed machine position: X={mx:.3f}, Y={my:.3f}, Z={mz:.3f}, C={mc:.3f}")
                        return position
                    else:
                        logger.debug(f"Insufficient coordinates found: {len(coords)} (need 4)")
                        
                except (ValueError, IndexError) as e:
                    logger.warning(f"Coordinate conversion error: {e}")
            
            # Strategy 3: Log unrecognized status format for debugging
            if '<' in clean_response and '>' in clean_response:
                # This looks like a status message but we couldn't parse it
                logger.info(f"🔍 Unrecognized status format (will improve parsing): {clean_response}")
                
                # Try to extract any numeric data for debugging
                numbers = re.findall(r'[\d\.-]+', clean_response)
                if len(numbers) >= 4:
                    logger.info(f"🔢 Found {len(numbers)} numbers in message: {numbers[:8]}")  # Show first 8 numbers
            
            return None
                
        except Exception as e:
            logger.error(f"❌ Position parsing exception: {e}")
            logger.error(f"📄 Message was: {status_response}")
            return None