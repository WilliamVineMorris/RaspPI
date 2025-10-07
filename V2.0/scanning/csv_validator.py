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
from scanning.scan_patterns import ScanPoint, FocusMode

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
            optional_columns = ['FocusMode', 'FocusValues']  # Focus control columns
            
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
                    # Parse position values
                    index = int(row['index'])
                    x = float(row['x'])
                    y = float(row['y'])
                    z = float(row['z'])
                    c = float(row['c'])
                    
                    # Parse optional focus parameters
                    focus_mode = row.get('FocusMode', '').strip()
                    focus_values = row.get('FocusValues', '').strip()
                    
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
                    
                    # Validate focus parameters
                    focus_errors, focus_warnings = self._validate_focus_params(
                        row_num, focus_mode, focus_values
                    )
                    errors.extend(focus_errors)
                    warnings.extend(focus_warnings)
                    
                    # If no errors for this point, add to valid list
                    if not point_errors and not focus_errors:
                        point_data = {
                            'index': index,
                            'x': x,
                            'y': y,
                            'z': z,
                            'c': c
                        }
                        # Add focus parameters if present
                        if focus_mode:
                            point_data['focus_mode'] = focus_mode
                        if focus_values:
                            point_data['focus_values'] = focus_values
                        
                        valid_points.append(point_data)
                    
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
    
    def _validate_focus_params(
        self, 
        row_num: int, 
        focus_mode: str, 
        focus_values: str
    ) -> Tuple[List[ValidationError], List[ValidationError]]:
        """
        Validate focus mode and focus values parameters.
        
        Args:
            row_num: Row number for error reporting
            focus_mode: Focus mode string (empty, 'manual', 'af', 'ca', 'default')
            focus_values: Focus values string (empty, single float, or semicolon-separated floats)
            
        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []
        
        # If both are empty, that's fine (use global default)
        if not focus_mode and not focus_values:
            return errors, warnings
        
        # Validate focus mode
        if focus_mode:
            valid_modes = ['manual', 'af', 'ca', 'default', '']
            if focus_mode.lower() not in valid_modes:
                errors.append(ValidationError(
                    row=row_num,
                    column='FocusMode',
                    value=focus_mode,
                    message=f"Invalid focus mode '{focus_mode}'. Must be one of: {', '.join(valid_modes[:-1])}"
                ))
                return errors, warnings  # Don't validate values if mode is invalid
        
        # Validate focus values
        if focus_values:
            try:
                # Check for multiple values (focus stacking)
                if ';' in focus_values:
                    # Parse semicolon-separated values
                    values = [float(v.strip()) for v in focus_values.split(';')]
                    
                    # Validate each lens position
                    for i, val in enumerate(values):
                        if val < 0.0 or val > 15.0:
                            errors.append(ValidationError(
                                row=row_num,
                                column='FocusValues',
                                value=val,
                                message=f"Focus value {val} at position {i} exceeds range [0.0, 15.0]"
                            ))
                    
                    # Warn if many focus positions (slow)
                    if len(values) > 5:
                        warnings.append(ValidationError(
                            row=row_num,
                            column='FocusValues',
                            value=len(values),
                            message=f"{len(values)} focus positions will significantly increase scan time"
                        ))
                else:
                    # Single value
                    val = float(focus_values)
                    if val < 0.0 or val > 15.0:
                        errors.append(ValidationError(
                            row=row_num,
                            column='FocusValues',
                            value=val,
                            message=f"Focus value {val} exceeds range [0.0, 15.0]"
                        ))
            except ValueError as e:
                errors.append(ValidationError(
                    row=row_num,
                    column='FocusValues',
                    value=focus_values,
                    message=f"Invalid focus values format: {e}"
                ))
        
        # Check for incompatible combinations
        if focus_mode and focus_mode.lower() in ['af', 'ca'] and focus_values:
            warnings.append(ValidationError(
                row=row_num,
                column='FocusValues',
                value=focus_values,
                message=f"Focus values ignored when using autofocus mode '{focus_mode}'"
            ))
        
        return errors, warnings
    
    def points_to_csv(self, points: List[ScanPoint]) -> str:
        """
        Convert ScanPoint objects to CSV string
        
        Args:
            points: List of ScanPoint objects
            
        Returns:
            CSV formatted string with focus columns
        """
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header with focus columns
        writer.writerow(['index', 'x', 'y', 'z', 'c', 'FocusMode', 'FocusValues'])
        
        # Write data
        for i, point in enumerate(points):
            try:
                # Ensure all position values are valid numbers
                x = point.position.x if point.position.x is not None else 0.0
                y = point.position.y if point.position.y is not None else 0.0
                z = point.position.z if point.position.z is not None else 0.0
                c = point.position.c if point.position.c is not None else 0.0
                
                # Convert focus_mode to CSV string
                focus_mode_str = ''
                if point.focus_mode:
                    if point.focus_mode == FocusMode.MANUAL:
                        focus_mode_str = 'manual'
                    elif point.focus_mode == FocusMode.AUTOFOCUS_ONCE:
                        focus_mode_str = 'af'
                    elif point.focus_mode == FocusMode.CONTINUOUS_AF:
                        focus_mode_str = 'ca'
                    elif point.focus_mode == FocusMode.DEFAULT:
                        focus_mode_str = 'default'
                
                # Convert focus_values to CSV string
                focus_values_str = ''
                if point.focus_values is not None:
                    if isinstance(point.focus_values, list):
                        # Multiple values: join with semicolons
                        focus_values_str = ';'.join(f"{v:.1f}" for v in point.focus_values)
                    else:
                        # Single value
                        focus_values_str = f"{point.focus_values:.1f}"
                
                writer.writerow([
                    i,
                    f"{x:.3f}",
                    f"{y:.3f}",
                    f"{z:.3f}",
                    f"{c:.3f}",
                    focus_mode_str,
                    focus_values_str
                ])
            except (AttributeError, TypeError) as e:
                logger.error(f"Error converting point {i} to CSV: {e}")
                logger.error(f"Point data: {point}")
                raise ValueError(f"Invalid point at index {i}: {e}")
        
        csv_content = output.getvalue()
        output.close()
        
        logger.info(f"Converted {len(points)} ScanPoints to CSV with focus columns")
        return csv_content
    
    def csv_to_scan_points(self, valid_points: List[Dict[str, Any]]) -> List[ScanPoint]:
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
            
            # Parse focus mode
            focus_mode = None
            focus_mode_str = point_dict.get('focus_mode', '').strip().lower()
            if focus_mode_str:
                if focus_mode_str == 'manual':
                    focus_mode = FocusMode.MANUAL
                elif focus_mode_str == 'af':
                    focus_mode = FocusMode.AUTOFOCUS_ONCE
                elif focus_mode_str == 'ca':
                    focus_mode = FocusMode.CONTINUOUS_AF
                elif focus_mode_str == 'default':
                    focus_mode = FocusMode.DEFAULT
            
            # Parse focus values
            focus_values = None
            focus_values_str = point_dict.get('focus_values', '').strip()
            if focus_values_str:
                if ';' in focus_values_str:
                    # Multiple values (focus stacking)
                    focus_values = [float(v.strip()) for v in focus_values_str.split(';')]
                else:
                    # Single value
                    focus_values = float(focus_values_str)
            
            # Adjust capture_count for focus stacking
            capture_count = 1
            if isinstance(focus_values, list):
                capture_count = len(focus_values)
            
            scan_point = ScanPoint(
                position=position,
                camera_settings=None,  # Use default camera settings
                lighting_settings=None,  # Use default lighting settings
                focus_mode=focus_mode,
                focus_values=focus_values,
                capture_count=capture_count,
                dwell_time=0.5
            )
            
            scan_points.append(scan_point)
        
        logger.info(f"Converted {len(scan_points)} CSV points to ScanPoints with focus parameters")
        return scan_points
