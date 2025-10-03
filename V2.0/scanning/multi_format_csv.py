"""
Multi-Format CSV Handler for 4DOF Scanner

Supports three coordinate system formats for CSV import/export:

1. CAMERA_RELATIVE (Cylindrical): User-friendly camera-centric coordinates
   - radius, height, rotation, tilt
   
2. FLUIDNC (Machine): Direct hardware control coordinates
   - x, y, z, c (FluidNC machine coordinates)
   
3. CARTESIAN (World): 3D world space coordinates  
   - x, y, z, c (Cartesian positions with tilt)
"""

import csv
import io
import logging
from enum import Enum
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

from core.types import Position4D
from core.coordinate_transform import (
    CoordinateTransformer,
    CameraRelativePosition,
    CartesianPosition
)
from scanning.scan_patterns import ScanPoint, CameraSettings

logger = logging.getLogger(__name__)


class CoordinateFormat(Enum):
    """CSV coordinate format types"""
    CAMERA_RELATIVE = "camera_relative"  # radius, height, rotation, tilt
    FLUIDNC = "fluidnc"                  # x, y, z, c (machine coords)
    CARTESIAN = "cartesian"              # x, y, z, c (world coords)


@dataclass
class CSVExportOptions:
    """Options for CSV export"""
    format: CoordinateFormat = CoordinateFormat.CAMERA_RELATIVE
    include_index: bool = True
    decimal_places: int = 3
    include_header_comments: bool = True
    

@dataclass
class CSVImportResult:
    """Result of CSV import operation"""
    success: bool
    format_detected: CoordinateFormat
    points: List[ScanPoint]
    errors: List[str]
    warnings: List[str]
    

class MultiFormatCSVHandler:
    """
    Handles CSV import/export in multiple coordinate formats.
    
    Automatically detects format on import and converts between formats.
    """
    
    def __init__(self, transformer: CoordinateTransformer):
        """
        Initialize handler with coordinate transformer.
        
        Args:
            transformer: Coordinate transformer for conversions
        """
        self.transformer = transformer
    
    def export_to_csv(
        self, 
        points: List[ScanPoint],
        options: CSVExportOptions = CSVExportOptions()
    ) -> str:
        """
        Export scan points to CSV in specified format.
        
        Args:
            points: List of ScanPoint objects
            options: Export options including format
            
        Returns:
            CSV content as string
        """
        output = io.StringIO()
        
        # Write header comments if requested
        if options.include_header_comments:
            self._write_header_comments(output, options.format)
        
        # Create CSV writer
        writer = csv.writer(output)
        
        # Write column headers
        headers = self._get_headers(options.format, options.include_index)
        writer.writerow(headers)
        
        # Write data rows
        for i, point in enumerate(points):
            row = self._convert_point_to_row(
                point, 
                i, 
                options.format,
                options.include_index,
                options.decimal_places
            )
            writer.writerow(row)
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"Exported {len(points)} points to CSV in {options.format.value} format")
        return csv_content
    
    def import_from_csv(self, csv_content: str) -> CSVImportResult:
        """
        Import scan points from CSV, auto-detecting format.
        
        Args:
            csv_content: CSV file content as string
            
        Returns:
            CSVImportResult with success status and converted points
        """
        errors = []
        warnings = []
        
        try:
            # Parse CSV
            csv_file = io.StringIO(csv_content)
            
            # Skip header comments
            lines = csv_content.strip().split('\n')
            csv_lines = [line for line in lines if not line.startswith('#')]
            csv_file = io.StringIO('\n'.join(csv_lines))
            
            reader = csv.DictReader(csv_file)
            
            # Detect format from headers
            fieldnames_list = list(reader.fieldnames) if reader.fieldnames else None
            format_detected = self._detect_format(fieldnames_list)
            if format_detected is None:
                errors.append(f"Could not detect CSV format. Headers: {reader.fieldnames}")
                return CSVImportResult(
                    success=False,
                    format_detected=CoordinateFormat.FLUIDNC,  # Default
                    points=[],
                    errors=errors,
                    warnings=warnings
                )
            
            logger.info(f"Detected CSV format: {format_detected.value}")
            
            # Parse rows and convert to ScanPoints
            points = []
            for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
                try:
                    scan_point = self._convert_row_to_point(row, format_detected)
                    points.append(scan_point)
                except ValueError as e:
                    errors.append(f"Row {row_num}: {e}")
                except Exception as e:
                    errors.append(f"Row {row_num}: Unexpected error - {e}")
            
            success = len(errors) == 0 and len(points) > 0
            
            logger.info(f"Imported {len(points)} points from CSV ({format_detected.value} format)")
            if errors:
                logger.warning(f"Import had {len(errors)} errors")
            
            return CSVImportResult(
                success=success,
                format_detected=format_detected,
                points=points,
                errors=errors,
                warnings=warnings
            )
            
        except Exception as e:
            logger.error(f"CSV import failed: {e}")
            return CSVImportResult(
                success=False,
                format_detected=CoordinateFormat.FLUIDNC,
                points=[],
                errors=[str(e)],
                warnings=[]
            )
    
    def _write_header_comments(self, output: io.StringIO, format_type: CoordinateFormat):
        """Write informative header comments to CSV file"""
        output.write("# 4DOF Scanner Scan Points\n")
        output.write(f"# Coordinate Format: {format_type.value}\n")
        output.write("#\n")
        
        if format_type == CoordinateFormat.CAMERA_RELATIVE:
            output.write("# Columns:\n")
            output.write("#   radius: Distance from turntable center to camera (mm)\n")
            output.write("#   height: Height of camera above turntable surface (mm)\n")
            output.write("#   rotation: Turntable rotation angle (degrees, 0-360)\n")
            output.write("#   tilt: Camera servo tilt angle (degrees, negative=down, positive=up)\n")
        elif format_type == CoordinateFormat.FLUIDNC:
            output.write("# Columns:\n")
            output.write("#   x: FluidNC X-axis position (mm, 0-200)\n")
            output.write("#   y: FluidNC Y-axis position (mm, 0-200)\n")
            output.write("#   z: FluidNC Z-axis rotation (degrees)\n")
            output.write("#   c: FluidNC C-axis servo angle (degrees)\n")
        elif format_type == CoordinateFormat.CARTESIAN:
            output.write("# Columns:\n")
            output.write("#   x: X position in 3D world space (mm)\n")
            output.write("#   y: Y position in 3D world space (mm)\n")
            output.write("#   z: Z position (height) in 3D world space (mm)\n")
            output.write("#   c: Camera tilt angle (degrees)\n")
        
        output.write("#\n")
    
    def _get_headers(self, format_type: CoordinateFormat, include_index: bool) -> List[str]:
        """Get CSV column headers for format"""
        if format_type == CoordinateFormat.CAMERA_RELATIVE:
            headers = ['radius', 'height', 'rotation', 'tilt']
        elif format_type == CoordinateFormat.CARTESIAN:
            headers = ['x', 'y', 'z', 'c']
        else:  # FLUIDNC
            headers = ['x', 'y', 'z', 'c']
        
        if include_index:
            headers = ['index'] + headers
        
        return headers
    
    def _detect_format(self, fieldnames: Optional[List[str]]) -> Optional[CoordinateFormat]:
        """
        Detect CSV format from column headers.
        
        Args:
            fieldnames: List of column names
            
        Returns:
            Detected CoordinateFormat or None if unrecognized
        """
        if not fieldnames:
            return None
        
        # Remove 'index' if present for comparison
        cols = [f.lower().strip() for f in fieldnames if f.lower().strip() != 'index']
        
        # Check for camera-relative format (unique column: radius or height)
        if 'radius' in cols and 'height' in cols:
            return CoordinateFormat.CAMERA_RELATIVE
        
        # Both FLUIDNC and CARTESIAN use x,y,z,c
        # Cannot distinguish without additional context, default to FLUIDNC
        if all(col in cols for col in ['x', 'y', 'z', 'c']):
            # Check if there's a format hint in the file or metadata
            # For now, assume FLUIDNC as it's the machine format
            return CoordinateFormat.FLUIDNC
        
        return None
    
    def _convert_point_to_row(
        self,
        point: ScanPoint,
        index: int,
        format_type: CoordinateFormat,
        include_index: bool,
        decimal_places: int
    ) -> List[str]:
        """
        Convert ScanPoint to CSV row in specified format.
        
        Args:
            point: ScanPoint object
            index: Point index number
            format_type: Target coordinate format
            include_index: Whether to include index column
            decimal_places: Number of decimal places for formatting
            
        Returns:
            List of formatted values for CSV row
        """
        # ScanPoint stores FluidNC coordinates in point.position
        fluidnc_pos = point.position
        
        if format_type == CoordinateFormat.FLUIDNC:
            # Direct FluidNC coordinates
            values = [
                f"{fluidnc_pos.x:.{decimal_places}f}",
                f"{fluidnc_pos.y:.{decimal_places}f}",
                f"{fluidnc_pos.z:.{decimal_places}f}",
                f"{fluidnc_pos.c:.{decimal_places}f}"
            ]
        
        elif format_type == CoordinateFormat.CAMERA_RELATIVE:
            # Convert to camera-relative cylindrical
            camera_pos = self.transformer.fluidnc_to_camera(fluidnc_pos)
            values = [
                f"{camera_pos.radius:.{decimal_places}f}",
                f"{camera_pos.height:.{decimal_places}f}",
                f"{camera_pos.rotation:.{decimal_places}f}",
                f"{camera_pos.tilt:.{decimal_places}f}"
            ]
        
        elif format_type == CoordinateFormat.CARTESIAN:
            # Convert to Cartesian world coordinates
            cart_pos = self.transformer.fluidnc_to_cartesian(fluidnc_pos)
            values = [
                f"{cart_pos.x:.{decimal_places}f}",
                f"{cart_pos.y:.{decimal_places}f}",
                f"{cart_pos.z:.{decimal_places}f}",
                f"{cart_pos.c:.{decimal_places}f}"
            ]
        
        if include_index:
            values = [str(index)] + values
        
        return values
    
    def _convert_row_to_point(
        self,
        row: Dict[str, str],
        format_type: CoordinateFormat
    ) -> ScanPoint:
        """
        Convert CSV row to ScanPoint.
        
        Args:
            row: Dictionary of column values
            format_type: Source coordinate format
            
        Returns:
            ScanPoint object with FluidNC coordinates
        """
        try:
            if format_type == CoordinateFormat.FLUIDNC:
                # Direct FluidNC coordinates
                fluidnc_pos = Position4D(
                    x=float(row['x']),
                    y=float(row['y']),
                    z=float(row['z']),
                    c=float(row['c'])
                )
            
            elif format_type == CoordinateFormat.CAMERA_RELATIVE:
                # Camera-relative to FluidNC
                camera_pos = CameraRelativePosition(
                    radius=float(row['radius']),
                    height=float(row['height']),
                    rotation=float(row['rotation']),
                    tilt=float(row['tilt'])
                )
                fluidnc_pos = self.transformer.camera_to_fluidnc(camera_pos)
            
            elif format_type == CoordinateFormat.CARTESIAN:
                # Cartesian to FluidNC
                cart_pos = CartesianPosition(
                    x=float(row['x']),
                    y=float(row['y']),
                    z=float(row['z']),
                    c=float(row['c'])
                )
                fluidnc_pos = self.transformer.cartesian_to_fluidnc(cart_pos)
            
            # Create ScanPoint with default camera settings
            scan_point = ScanPoint(
                position=fluidnc_pos,
                camera_settings=CameraSettings(
                    exposure_time=0.1,
                    iso=200,
                    capture_format="JPEG",
                    resolution=(4624, 3472)
                ),
                capture_count=1,
                dwell_time=0.2
            )
            
            return scan_point
            
        except KeyError as e:
            raise ValueError(f"Missing required column: {e}")
        except ValueError as e:
            raise ValueError(f"Invalid numeric value: {e}")
