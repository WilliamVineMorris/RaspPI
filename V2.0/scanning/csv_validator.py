"""
CSV Scan Point Validator and Converter

Handles validation, import, and export of scan points in CSV format.
Validates points against hardware limits from scanner configuration.
"""

import csv
import io
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

from core.types import Position4D
from scanning.scan_patterns import ScanPoint

logger = logging.getLogger(__name__)

@dataclass
class ValidationError:
    """Single validation error for a scan point"""
    row: int
    column: str
    value: Any
    message: str
    
@dataclass
class ValidationResult:
    """Result of CSV validation"""
    success: bool
    valid_points: List[Dict[str, float]]
    errors: List[ValidationError]
    warnings: List[ValidationError]
    
    @property
    def point_count(self) -> int:
        return len(self.valid_points)
    
    @property
    def error_count(self) -> int:
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        return len(self.warnings)

class ScanPointValidator:
    """
    Validates scan points against hardware limits
    Converts between CSV format and ScanPoint objects
    """
    
    def __init__(self, hardware_limits: Dict[str, Dict[str, List[float]]]):
        """
        Initialize validator with hardware limits
        
        Args:
            hardware_limits: Dictionary from scanner_config.yaml axes section
                            Format: {'x': {'limits': [min, max]}, 'y': {...}, ...}
        """
        self.limits = {
            'x': hardware_limits.get('x', {}).get('limits', [0.0, 200.0]),
            'y': hardware_limits.get('y', {}).get('limits', [0.0, 200.0]),
            'z': hardware_limits.get('z', {}).get('limits', [0.0, 360.0]),
            'c': hardware_limits.get('c', {}).get('limits', [-90.0, 90.0])
        }
        
        # Warning threshold (warn if within this distance from limits)
        self.warning_margin = 1.0  # mm or degrees
        
        logger.info(f"Scan validator initialized with limits: {self.limits}")
    
    def validate_csv_file(self, csv_content: str) -> ValidationResult:
        """
        Validate CSV file content
        
        Args:
            csv_content: CSV file content as string
            
        Returns:
            ValidationResult with success status, valid points, and errors
        """
        errors = []
        warnings = []
        valid_points = []
        
        try:
            # Parse CSV
            csv_file = io.StringIO(csv_content)
            reader = csv.DictReader(csv_file)
            
            # Validate header
            required_columns = ['index', 'x', 'y', 'z', 'c']
            if not reader.fieldnames or not all(col in reader.fieldnames for col in required_columns):
                errors.append(ValidationError(
                    row=0,
                    column='header',
                    value=reader.fieldnames,
                    message=f"CSV must have columns: {', '.join(required_columns)}"
                ))
                return ValidationResult(success=False, valid_points=[], errors=errors, warnings=warnings)
            
            # Validate each row
            expected_index = 0
            for row_num, row in enumerate(reader, start=1):
                try:
                    # Parse values
                    index = int(row['index'])
                    x = float(row['x'])
                    y = float(row['y'])
                    z = float(row['z'])
                    c = float(row['c'])
                    
                    # Validate index sequence
                    if index != expected_index:
                        errors.append(ValidationError(
                            row=row_num,
                            column='index',
                            value=index,
                            message=f"Index {index} out of sequence (expected {expected_index})"
                        ))
                        continue
                    
                    # Validate each coordinate
                    point_errors, point_warnings = self._validate_point(row_num, x, y, z, c)
                    errors.extend(point_errors)
                    warnings.extend(point_warnings)
                    
                    # If no errors for this point, add to valid list
                    if not point_errors:
                        valid_points.append({
                            'index': index,
                            'x': x,
                            'y': y,
                            'z': z,
                            'c': c
                        })
                    
                    expected_index += 1
                    
                except ValueError as e:
                    errors.append(ValidationError(
                        row=row_num,
                        column='parsing',
                        value=row,
                        message=f"Failed to parse row: {str(e)}"
                    ))
                except KeyError as e:
                    errors.append(ValidationError(
                        row=row_num,
                        column=str(e),
                        value=None,
                        message=f"Missing required column: {str(e)}"
                    ))
            
            # Check if we have any points
            if expected_index == 0:
                errors.append(ValidationError(
                    row=0,
                    column='data',
                    value=None,
                    message="CSV file contains no data rows"
                ))
            
        except Exception as e:
            errors.append(ValidationError(
                row=0,
                column='file',
                value=None,
                message=f"Failed to parse CSV file: {str(e)}"
            ))
        
        success = len(errors) == 0 and len(valid_points) > 0
        
        logger.info(f"CSV validation complete: {len(valid_points)} valid points, "
                   f"{len(errors)} errors, {len(warnings)} warnings")
        
        return ValidationResult(
            success=success,
            valid_points=valid_points,
            errors=errors,
            warnings=warnings
        )
    
    def _validate_point(self, row_num: int, x: float, y: float, z: float, c: float) -> Tuple[List[ValidationError], List[ValidationError]]:
        """
        Validate a single point's coordinates
        
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        # Validate X
        if x < self.limits['x'][0] or x > self.limits['x'][1]:
            errors.append(ValidationError(
                row=row_num,
                column='x',
                value=x,
                message=f"X-coordinate {x} exceeds limits [{self.limits['x'][0]}, {self.limits['x'][1]}]"
            ))
        elif (x - self.limits['x'][0] < self.warning_margin or 
              self.limits['x'][1] - x < self.warning_margin):
            warnings.append(ValidationError(
                row=row_num,
                column='x',
                value=x,
                message=f"X-coordinate {x} within {self.warning_margin}mm of limit"
            ))
        
        # Validate Y
        if y < self.limits['y'][0] or y > self.limits['y'][1]:
            errors.append(ValidationError(
                row=row_num,
                column='y',
                value=y,
                message=f"Y-coordinate {y} exceeds limits [{self.limits['y'][0]}, {self.limits['y'][1]}]"
            ))
        elif (y - self.limits['y'][0] < self.warning_margin or 
              self.limits['y'][1] - y < self.warning_margin):
            warnings.append(ValidationError(
                row=row_num,
                column='y',
                value=y,
                message=f"Y-coordinate {y} within {self.warning_margin}mm of limit"
            ))
        
        # Validate Z (rotation, typically 0-360 but can wrap)
        if z < self.limits['z'][0] or z > self.limits['z'][1]:
            errors.append(ValidationError(
                row=row_num,
                column='z',
                value=z,
                message=f"Z-rotation {z}° exceeds limits [{self.limits['z'][0]}, {self.limits['z'][1]}]"
            ))
        
        # Validate C (camera tilt, typically ±90°)
        if c < self.limits['c'][0] or c > self.limits['c'][1]:
            errors.append(ValidationError(
                row=row_num,
                column='c',
                value=c,
                message=f"C-angle {c}° exceeds limits [{self.limits['c'][0]}, {self.limits['c'][1]}]"
            ))
        elif (c - self.limits['c'][0] < self.warning_margin or 
              self.limits['c'][1] - c < self.warning_margin):
            warnings.append(ValidationError(
                row=row_num,
                column='c',
                value=c,
                message=f"C-angle {c}° within {self.warning_margin}° of limit"
            ))
        
        return errors, warnings
    
    def points_to_csv(self, points: List[ScanPoint]) -> str:
        """
        Convert ScanPoint objects to CSV string
        
        Args:
            points: List of ScanPoint objects
            
        Returns:
            CSV formatted string
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['index', 'x', 'y', 'z', 'c'])
        
        # Write data
        for i, point in enumerate(points):
            writer.writerow([
                i,
                f"{point.position.x:.3f}",
                f"{point.position.y:.3f}",
                f"{point.position.z:.3f}",
                f"{point.position.c:.3f}"
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"Converted {len(points)} ScanPoints to CSV")
        return csv_content
    
    def csv_to_scan_points(self, valid_points: List[Dict[str, float]]) -> List[ScanPoint]:
        """
        Convert validated point dictionaries to ScanPoint objects
        
        Args:
            valid_points: List of validated point dictionaries from CSV
            
        Returns:
            List of ScanPoint objects ready for scanning
        """
        scan_points = []
        
        for point_dict in valid_points:
            position = Position4D(
                x=point_dict['x'],
                y=point_dict['y'],
                z=point_dict['z'],
                c=point_dict['c']
            )
            
            scan_point = ScanPoint(
                position=position,
                camera_settings=None,  # Use default camera settings
                lighting_settings=None,  # Use default lighting settings
                capture_count=1,
                dwell_time=0.5
            )
            
            scan_points.append(scan_point)
        
        logger.info(f"Converted {len(scan_points)} CSV points to ScanPoints")
        return scan_points
