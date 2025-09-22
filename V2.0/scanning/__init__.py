"""
3D Scanning Orchestration System

This module provides the high-level scanning workflow coordination,
pattern generation, and orchestration logic that ties together the
motion control, camera systems, and processing pipeline.

Main Components:
- Scan Patterns: Abstract and concrete pattern generators
- Scan Orchestrator: Main coordination engine
- Scan State: Progress tracking and state management
"""

from .scan_patterns import (
    ScanPattern, 
    ScanPoint, 
    PatternType,
    PatternParameters,
    GridScanPattern,
    GridPatternParameters
)

from .scan_state import (
    ScanState,
    ScanStatus, 
    ScanPhase,
    ScanProgress,
    ScanTiming,
    ScanError
)

from .scan_orchestrator import ScanOrchestrator

__all__ = [
    # Pattern system
    'ScanPattern',
    'ScanPoint', 
    'PatternType',
    'PatternParameters',
    'GridScanPattern',
    'GridPatternParameters',
    
    # State management
    'ScanState',
    'ScanStatus',
    'ScanPhase', 
    'ScanProgress',
    'ScanTiming',
    'ScanError',
    
    # Main orchestration
    'ScanOrchestrator'
]