"""
Scan State Management

This module handles scan state tracking, progress monitoring,
pause/resume functionality, and error recovery for scanning operations.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path
import json

from core.events import EventBus, ScannerEvent

logger = logging.getLogger(__name__)

class ScanStatus(Enum):
    """Scan execution status"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ScanPhase(Enum):
    """Current phase of scanning operation"""
    SETUP = "setup"
    HOMING = "homing" 
    POSITIONING = "positioning"
    CAPTURING = "capturing"
    PROCESSING = "processing"
    CLEANUP = "cleanup"

@dataclass
class ScanProgress:
    """Current scan progress information"""
    current_point: int = 0
    total_points: int = 0
    images_captured: int = 0
    estimated_remaining: float = 0.0  # minutes
    completion_percentage: float = 0.0
    
    @property
    def points_remaining(self) -> int:
        """Points remaining to scan"""
        return max(0, self.total_points - self.current_point)

@dataclass
class ScanTiming:
    """Scan timing information"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    pause_start: Optional[datetime] = None
    total_paused_time: float = 0.0  # seconds
    
    def start(self):
        """Mark scan start"""
        self.start_time = datetime.now()
        
    def pause(self):
        """Mark pause start"""
        if self.pause_start is None:
            self.pause_start = datetime.now()
            
    def resume(self):
        """Resume from pause and accumulate pause time"""
        if self.pause_start is not None:
            pause_duration = (datetime.now() - self.pause_start).total_seconds()
            self.total_paused_time += pause_duration
            self.pause_start = None
            
    def complete(self):
        """Mark scan completion"""
        if self.pause_start is not None:
            self.resume()  # Handle case where scan completes while paused
        self.end_time = datetime.now()
        
    @property
    def elapsed_time(self) -> float:
        """Total elapsed time in seconds (excluding pauses)"""
        if self.start_time is None:
            return 0.0
            
        end = self.end_time or datetime.now()
        total_elapsed = (end - self.start_time).total_seconds()
        
        # Subtract pause time
        pause_time = self.total_paused_time
        if self.pause_start is not None:
            pause_time += (datetime.now() - self.pause_start).total_seconds()
            
        return max(0.0, total_elapsed - pause_time)
    
    @property
    def estimated_total_time(self) -> float:
        """Estimated total scan time in seconds"""
        if self.start_time is None or self.elapsed_time <= 0:
            return 0.0
            
        # This would be set by the orchestrator based on progress
        return 0.0

@dataclass
class ScanError:
    """Scan error information"""
    timestamp: datetime
    error_type: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    recoverable: bool = True

class ScanState:
    """
    Manages the complete state of a scanning operation
    
    Tracks progress, timing, errors, and provides state persistence
    for pause/resume functionality and error recovery.
    """
    
    def __init__(self, scan_id: str, pattern_id: str, output_directory: Path):
        self.scan_id = scan_id
        self.pattern_id = pattern_id
        self.output_directory = Path(output_directory)
        
        # Core state
        self.status = ScanStatus.IDLE
        self.phase = ScanPhase.SETUP
        
        # Progress tracking
        self.progress = ScanProgress()
        self.timing = ScanTiming()
        
        # Error tracking
        self.errors: List[ScanError] = []
        self.last_successful_point: Optional[int] = None
        
        # Settings and metadata
        self.scan_parameters: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {
            'created_at': datetime.now().isoformat(),
            'version': '2.0'
        }
        
        # Event system
        self.event_bus = EventBus()
        
        # State file for persistence
        self.state_file = self.output_directory / f"{scan_id}_state.json"
        
        # Ensure output directory exists
        self.output_directory.mkdir(parents=True, exist_ok=True)
        
        self.logger = logging.getLogger(f"{__name__}.{scan_id}")
        
    def initialize(self, total_points: int, scan_parameters: Dict[str, Any]):
        """Initialize scan state"""
        self.status = ScanStatus.INITIALIZING
        self.progress.total_points = total_points
        self.scan_parameters = scan_parameters.copy()
        
        self.logger.info(f"Initialized scan {self.scan_id} with {total_points} points")
        self._notify_state_change()
        self._save_state()
    
    def start(self):
        """Start the scan"""
        if self.status != ScanStatus.INITIALIZING:
            raise ValueError(f"Cannot start scan from status {self.status}")
            
        self.status = ScanStatus.RUNNING
        self.phase = ScanPhase.HOMING
        self.timing.start()
        
        self.logger.info(f"Started scan {self.scan_id}")
        self._notify_state_change()
        self._save_state()
    
    def pause(self):
        """Pause the scan"""
        if self.status != ScanStatus.RUNNING:
            raise ValueError(f"Cannot pause scan from status {self.status}")
            
        self.status = ScanStatus.PAUSED
        self.timing.pause()
        
        self.logger.info(f"Paused scan {self.scan_id}")
        self._notify_state_change()
        self._save_state()
    
    def resume(self):
        """Resume the scan"""
        if self.status != ScanStatus.PAUSED:
            raise ValueError(f"Cannot resume scan from status {self.status}")
            
        self.status = ScanStatus.RUNNING
        self.timing.resume()
        
        self.logger.info(f"Resumed scan {self.scan_id}")
        self._notify_state_change()
        self._save_state()
    
    def complete(self):
        """Mark scan as completed"""
        self.status = ScanStatus.COMPLETED
        self.phase = ScanPhase.CLEANUP
        self.timing.complete()
        self.progress.completion_percentage = 100.0
        
        self.logger.info(f"Completed scan {self.scan_id} in {self.timing.elapsed_time:.1f}s")
        self._notify_state_change()
        self._save_state()
    
    def fail(self, error_message: str, error_details: Optional[Dict[str, Any]] = None):
        """Mark scan as failed"""
        self.status = ScanStatus.FAILED
        
        error = ScanError(
            timestamp=datetime.now(),
            error_type="scan_failure", 
            message=error_message,
            details=error_details or {},
            recoverable=False
        )
        self.errors.append(error)
        
        self.logger.error(f"Scan {self.scan_id} failed: {error_message}")
        self._notify_state_change()
        self._save_state()
    
    def cancel(self):
        """Cancel the scan"""
        self.status = ScanStatus.CANCELLED
        self.timing.complete()
        
        self.logger.info(f"Cancelled scan {self.scan_id}")
        self._notify_state_change()
        self._save_state()
    
    def update_progress(self, current_point: int, images_captured: Optional[int] = None):
        """Update scan progress"""
        self.progress.current_point = current_point
        self.last_successful_point = current_point
        
        if images_captured is not None:
            self.progress.images_captured = images_captured
            
        # Calculate completion percentage
        if self.progress.total_points > 0:
            self.progress.completion_percentage = (current_point / self.progress.total_points) * 100
            
        # Estimate remaining time
        if current_point > 0 and self.timing.elapsed_time > 0:
            time_per_point = self.timing.elapsed_time / current_point
            remaining_points = self.progress.points_remaining
            self.progress.estimated_remaining = (remaining_points * time_per_point) / 60.0  # minutes
        
        self._notify_progress_update()
        
        # Save state periodically (every 10 points)
        if current_point % 10 == 0:
            self._save_state()
    
    def set_phase(self, phase: ScanPhase):
        """Set current scan phase"""
        self.phase = phase
        self.logger.debug(f"Scan phase: {phase.value}")
        self._notify_state_change()
    
    def add_error(self, error_type: str, message: str, details: Optional[Dict[str, Any]] = None, recoverable: bool = True):
        """Add an error to the scan"""
        error = ScanError(
            timestamp=datetime.now(),
            error_type=error_type,
            message=message, 
            details=details or {},
            recoverable=recoverable
        )
        self.errors.append(error)
        
        level = logging.WARNING if recoverable else logging.ERROR
        self.logger.log(level, f"Scan error ({error_type}): {message}")
        
        self._notify_error(error)
    
    def get_recovery_point(self) -> Optional[int]:
        """Get the point to resume from after error"""
        return self.last_successful_point
    
    def _notify_state_change(self):
        """Notify of state changes"""
        self.event_bus.publish(
            event_type="scan_state_changed",
            data={
                'scan_id': self.scan_id,
                'status': self.status.value,
                'phase': self.phase.value,
                'progress': {
                    'current_point': self.progress.current_point,
                    'total_points': self.progress.total_points,
                    'completion_percentage': self.progress.completion_percentage
                }
            },
            source_module="scan_state"
        )
    
    def _notify_progress_update(self):
        """Notify of progress updates"""
        self.event_bus.publish(
            event_type="scan_progress_updated",
            data={
                'scan_id': self.scan_id,
                'progress': {
                    'current_point': self.progress.current_point,
                    'total_points': self.progress.total_points,
                    'images_captured': self.progress.images_captured,
                    'completion_percentage': self.progress.completion_percentage,
                    'estimated_remaining': self.progress.estimated_remaining
                },
                'timing': {
                    'elapsed_time': self.timing.elapsed_time,
                    'estimated_total': self.timing.estimated_total_time
                }
            },
            source_module="scan_state"
        )
    
    def _notify_error(self, error: ScanError):
        """Notify of errors"""
        self.event_bus.publish(
            event_type="scan_error_occurred",
            data={
                'scan_id': self.scan_id,
                'error': {
                    'type': error.error_type,
                    'message': error.message,
                    'timestamp': error.timestamp.isoformat(),
                    'recoverable': error.recoverable,
                    'details': error.details
                }
            },
            source_module="scan_state"
        )
    
    def _save_state(self):
        """Save current state to file"""
        try:
            state_data = {
                'scan_id': self.scan_id,
                'pattern_id': self.pattern_id,
                'status': self.status.value,
                'phase': self.phase.value,
                'progress': {
                    'current_point': self.progress.current_point,
                    'total_points': self.progress.total_points,
                    'images_captured': self.progress.images_captured,
                    'completion_percentage': self.progress.completion_percentage,
                    'estimated_remaining': self.progress.estimated_remaining
                },
                'timing': {
                    'start_time': self.timing.start_time.isoformat() if self.timing.start_time else None,
                    'end_time': self.timing.end_time.isoformat() if self.timing.end_time else None,
                    'total_paused_time': self.timing.total_paused_time,
                    'elapsed_time': self.timing.elapsed_time
                },
                'last_successful_point': self.last_successful_point,
                'scan_parameters': self.scan_parameters,
                'metadata': self.metadata,
                'errors': [
                    {
                        'timestamp': error.timestamp.isoformat(),
                        'type': error.error_type,
                        'message': error.message,
                        'details': error.details,
                        'recoverable': error.recoverable
                    }
                    for error in self.errors
                ]
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state_data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save state: {e}")
    
    @classmethod
    def load_state(cls, state_file: Path) -> 'ScanState':
        """Load scan state from file"""
        with open(state_file, 'r') as f:
            data = json.load(f)
            
        # Create instance
        instance = cls(
            scan_id=data['scan_id'],
            pattern_id=data['pattern_id'], 
            output_directory=state_file.parent
        )
        
        # Restore state
        instance.status = ScanStatus(data['status'])
        instance.phase = ScanPhase(data['phase'])
        
        # Restore progress
        progress_data = data['progress']
        instance.progress = ScanProgress(**progress_data)
        
        # Restore timing
        timing_data = data['timing']
        instance.timing = ScanTiming()
        if timing_data['start_time']:
            instance.timing.start_time = datetime.fromisoformat(timing_data['start_time'])
        if timing_data['end_time']:
            instance.timing.end_time = datetime.fromisoformat(timing_data['end_time'])
        instance.timing.total_paused_time = timing_data['total_paused_time']
        
        # Restore other data
        instance.last_successful_point = data['last_successful_point']
        instance.scan_parameters = data['scan_parameters']
        instance.metadata = data['metadata']
        
        # Restore errors
        for error_data in data['errors']:
            error = ScanError(
                timestamp=datetime.fromisoformat(error_data['timestamp']),
                error_type=error_data['type'],
                message=error_data['message'],
                details=error_data['details'],
                recoverable=error_data['recoverable']
            )
            instance.errors.append(error)
            
        return instance