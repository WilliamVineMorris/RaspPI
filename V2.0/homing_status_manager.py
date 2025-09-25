#!/usr/bin/env python3
"""
Fixed Homing Status Manager

Updated to work with the FixedFluidNCController which has proper homing completion detection.
This manager now uses the working homing system from the successful tests.

Author: Scanner System Development
Created: September 26, 2025
"""

import logging
import asyncio
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, Callable, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class HomingStatus(Enum):
    """Homing status states"""
    UNKNOWN = "unknown"
    NOT_REQUIRED = "not_required"  # Already homed
    REQUIRED = "required"  # In alarm state, needs homing
    IN_PROGRESS = "in_progress"  # Currently homing
    COMPLETED = "completed"  # Just completed
    FAILED = "failed"  # Homing failed
    ERROR = "error"  # System error

@dataclass
class HomingState:
    """Comprehensive homing state information"""
    status: HomingStatus
    message: str
    can_home: bool
    requires_user_action: bool
    timestamp: datetime
    progress_info: Dict[str, Any]
    recommendations: list[str]

class FixedHomingStatusManager:
    """
    Fixed Homing Status Manager with proper completion detection.
    
    This manager works with the FixedFluidNCController which properly waits for
    the "MSG:DBG: Homing done" message and verifies final "Idle" status.
    """
    
    def __init__(self, motion_controller):
        self.motion_controller = motion_controller
        self.current_state = HomingState(
            status=HomingStatus.UNKNOWN,
            message="Checking homing status...",
            can_home=False,
            requires_user_action=True,
            timestamp=datetime.now(),
            progress_info={},
            recommendations=["Check system connection"]
        )
        
        # Status callbacks for web interface
        self.status_callbacks: list[Callable[[HomingState], None]] = []
        
        # Homing progress tracking
        self.homing_start_time: Optional[datetime] = None
        self.last_homing_status: Optional[str] = None
    
    def add_status_callback(self, callback: Callable[[HomingState], None]):
        """Add callback for status updates"""
        self.status_callbacks.append(callback)
    
    def _notify_callbacks(self):
        """Notify all callbacks of status change"""
        for callback in self.status_callbacks:
            try:
                callback(self.current_state)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    async def check_homing_status(self) -> HomingState:
        """Check current homing status and requirements"""
        try:
            # Get motion controller status
            if not await self.motion_controller.is_connected():
                self.current_state = HomingState(
                    status=HomingStatus.ERROR,
                    message="Motion controller not connected",
                    can_home=False,
                    requires_user_action=True,
                    timestamp=datetime.now(),
                    progress_info={'connection': False},
                    recommendations=[
                        "Check FluidNC USB connection",
                        "Verify /dev/ttyUSB0 port",
                        "Run connection diagnostics"
                    ]
                )
                self._notify_callbacks()
                return self.current_state
            
            # Get controller status
            status = await self.motion_controller.get_status()
            
            if status.name == "ALARM":
                self.current_state = HomingState(
                    status=HomingStatus.REQUIRED,
                    message="FluidNC in ALARM state - homing required",
                    can_home=True,
                    requires_user_action=True,
                    timestamp=datetime.now(),
                    progress_info={
                        'controller_state': 'ALARM',
                        'connection': True
                    },
                    recommendations=[
                        "Click 'Home All Axes' button below",
                        "Ensure axes can move freely",
                        "Check limit switches are connected"
                    ]
                )
                
            elif status.name == "HOMING":
                # Currently homing
                elapsed_time = None
                if self.homing_start_time:
                    elapsed_time = (datetime.now() - self.homing_start_time).total_seconds()
                
                self.current_state = HomingState(
                    status=HomingStatus.IN_PROGRESS,
                    message=f"Homing in progress{f' ({elapsed_time:.1f}s)' if elapsed_time else ''}",
                    can_home=False,
                    requires_user_action=False,
                    timestamp=datetime.now(),
                    progress_info={
                        'controller_state': 'HOMING',
                        'elapsed_time': elapsed_time,
                        'connection': True
                    },
                    recommendations=[
                        "Wait for homing to complete",
                        "Do not interrupt the process",
                        "Ensure axes move freely"
                    ]
                )
                
            elif status.name == "IDLE":
                # Check if recently completed homing
                recent_completion = (
                    self.current_state.status == HomingStatus.IN_PROGRESS and
                    (datetime.now() - self.current_state.timestamp).total_seconds() < 30
                )
                
                if recent_completion:
                    self.current_state = HomingState(
                        status=HomingStatus.COMPLETED,
                        message="Homing completed successfully! System ready.",
                        can_home=True,
                        requires_user_action=False,
                        timestamp=datetime.now(),
                        progress_info={
                            'controller_state': 'IDLE',
                            'connection': True,
                            'homed': True
                        },
                        recommendations=[
                            "System is ready for operation",
                            "You can now move axes manually",
                            "Start scanning if needed"
                        ]
                    )
                else:
                    self.current_state = HomingState(
                        status=HomingStatus.NOT_REQUIRED,
                        message="System ready - already homed",
                        can_home=True,
                        requires_user_action=False,
                        timestamp=datetime.now(),
                        progress_info={
                            'controller_state': 'IDLE',
                            'connection': True,
                            'homed': True
                        },
                        recommendations=[
                            "System is operational",
                            "Use manual controls or start scanning"
                        ]
                    )
            else:
                # Other states
                self.current_state = HomingState(
                    status=HomingStatus.UNKNOWN,
                    message=f"Controller state: {status.name}",
                    can_home=False,
                    requires_user_action=True,
                    timestamp=datetime.now(),
                    progress_info={
                        'controller_state': status.name,
                        'connection': True
                    },
                    recommendations=[
                        f"Controller in {status.name} state",
                        "Check FluidNC status manually",
                        "May need manual intervention"
                    ]
                )
            
            self._notify_callbacks()
            return self.current_state
            
        except Exception as e:
            logger.error(f"Error checking homing status: {e}")
            self.current_state = HomingState(
                status=HomingStatus.ERROR,
                message=f"Status check failed: {e}",
                can_home=False,
                requires_user_action=True,
                timestamp=datetime.now(),
                progress_info={'error': str(e)},
                recommendations=[
                    "Check system connections",
                    "Restart the controller",
                    "Contact support if persistent"
                ]
            )
            self._notify_callbacks()
            return self.current_state
    
    async def manual_unlock(self) -> bool:
        """Manually unlock (clear alarm) without homing"""
        try:
            logger.info("🔓 Manual unlock requested...")
            
            # Update status
            self.current_state = HomingState(
                status=HomingStatus.IN_PROGRESS,
                message="Clearing alarm state...",
                can_home=False,
                requires_user_action=False,
                timestamp=datetime.now(),
                progress_info={'phase': 'unlocking'},
                recommendations=[
                    "Clearing alarm - please wait"
                ]
            )
            self._notify_callbacks()
            
            # Use the clear_alarm method
            success = await self.motion_controller.clear_alarm()
            
            if success:
                # Check final status
                await asyncio.sleep(1.0)  # Wait for status to update
                status = await self.motion_controller.get_status()
                
                if status.name == "IDLE":
                    self.current_state = HomingState(
                        status=HomingStatus.NOT_REQUIRED,
                        message="Alarm cleared - system unlocked (position unknown)",
                        can_home=True,
                        requires_user_action=False,
                        timestamp=datetime.now(),
                        progress_info={'phase': 'unlocked', 'success': True, 'position_known': False},
                        recommendations=[
                            "Alarm cleared successfully!",
                            "⚠️ Position is unknown - home when safe",
                            "You can now move axes manually",
                            "Consider homing for accurate positioning"
                        ]
                    )
                else:
                    self.current_state = HomingState(
                        status=HomingStatus.FAILED,
                        message="Unlock failed - still in alarm state",
                        can_home=True,
                        requires_user_action=True,
                        timestamp=datetime.now(),
                        progress_info={'phase': 'failed', 'success': False},
                        recommendations=[
                            "Manual unlock failed",
                            "Check limit switches",
                            "Manually move axes away from limits",
                            "Try power cycling FluidNC"
                        ]
                    )
            else:
                self.current_state = HomingState(
                    status=HomingStatus.FAILED,
                    message="Unlock command failed",
                    can_home=True,
                    requires_user_action=True,
                    timestamp=datetime.now(),
                    progress_info={'phase': 'failed', 'success': False},
                    recommendations=[
                        "Unlock command failed",
                        "Check FluidNC connection",
                        "Try manual FluidNC commands",
                        "Power cycle if necessary"
                    ]
                )
            
            self._notify_callbacks()
            return success
            
        except Exception as e:
            logger.error(f"Manual unlock failed: {e}")
            self.current_state = HomingState(
                status=HomingStatus.FAILED,
                message=f"Unlock error: {e}",
                can_home=True,
                requires_user_action=True,
                timestamp=datetime.now(),
                progress_info={'error': str(e)},
                recommendations=[
                    "Check system connections",
                    "Verify FluidNC status",
                    "Try power cycling"
                ]
            )
            self._notify_callbacks()
            return False

    async def start_homing(self, progress_callback=None) -> bool:
        """Start homing sequence with progress tracking"""
        try:
            logger.info("🏠 Starting homing sequence with status tracking...")
            
            # Record start time
            self.homing_start_time = datetime.now()
            
            # Update status
            self.current_state = HomingState(
                status=HomingStatus.IN_PROGRESS,
                message="Starting homing sequence...",
                can_home=False,
                requires_user_action=False,
                timestamp=datetime.now(),
                progress_info={'phase': 'starting'},
                recommendations=[
                    "Homing starting - please wait",
                    "Ensure axes can move freely"
                ]
            )
            self._notify_callbacks()
            
            # Use the enhanced homing method with callback
            success = await self.motion_controller.home_with_status_callback(
                status_callback=self._homing_progress_callback
            )
            
            if success:
                self.current_state = HomingState(
                    status=HomingStatus.COMPLETED,
                    message="Homing completed successfully!",
                    can_home=True,
                    requires_user_action=False,
                    timestamp=datetime.now(),
                    progress_info={'phase': 'completed', 'success': True, 'position_known': True},
                    recommendations=[
                        "Homing successful!",
                        "System ready for operation",
                        "Position is now accurately known"
                    ]
                )
            else:
                self.current_state = HomingState(
                    status=HomingStatus.FAILED,
                    message="Homing failed - check system",
                    can_home=True,
                    requires_user_action=True,
                    timestamp=datetime.now(),
                    progress_info={'phase': 'failed', 'success': False},
                    recommendations=[
                        "Check limit switches",
                        "Ensure axes move freely",
                        "Check FluidNC configuration",
                        "Try manual unlock if homing impossible"
                    ]
                )
            
            self._notify_callbacks()
            return success
            
        except Exception as e:
            logger.error(f"Homing sequence failed: {e}")
            self.current_state = HomingState(
                status=HomingStatus.FAILED,
                message=f"Homing error: {e}",
                can_home=True,
                requires_user_action=True,
                timestamp=datetime.now(),
                progress_info={'error': str(e)},
                recommendations=[
                    "Check system connections",
                    "Verify FluidNC status",
                    "Try manual unlock if needed"
                ]
            )
            self._notify_callbacks()
            return False
    
    def _homing_progress_callback(self, phase: str, message: str):
        """Callback for homing progress updates"""
        try:
            elapsed_time = None
            if self.homing_start_time:
                elapsed_time = (datetime.now() - self.homing_start_time).total_seconds()
            
            # Map phases to user-friendly messages
            phase_messages = {
                'starting': 'Preparing to home...',
                'clearing_alarm': 'Clearing alarm state...',
                'homing': 'Moving axes to home positions...',
                'complete': 'Homing completed successfully!',
                'error': f'Homing error: {message}'
            }
            
            display_message = phase_messages.get(phase, message)
            if elapsed_time and phase in ['homing', 'clearing_alarm']:
                display_message += f' ({elapsed_time:.1f}s)'
            
            self.current_state = HomingState(
                status=HomingStatus.IN_PROGRESS,
                message=display_message,
                can_home=False,
                requires_user_action=False,
                timestamp=datetime.now(),
                progress_info={
                    'phase': phase,
                    'elapsed_time': elapsed_time,
                    'detailed_message': message
                },
                recommendations=[
                    "Homing in progress - please wait",
                    "Do not interrupt the process"
                ] if phase != 'error' else [
                    "Homing encountered an error",
                    "Check the detailed message above"
                ]
            )
            
            self._notify_callbacks()
            
        except Exception as e:
            logger.error(f"Homing progress callback error: {e}")
    
    def get_status_for_web(self) -> Dict[str, Any]:
        """Get status formatted for web interface"""
        return {
            'homing_required': self.current_state.status == HomingStatus.REQUIRED,
            'homing_in_progress': self.current_state.status == HomingStatus.IN_PROGRESS,
            'can_home': self.current_state.can_home,
            'can_manual_unlock': self.current_state.status == HomingStatus.REQUIRED or self.current_state.status == HomingStatus.FAILED,
            'status': self.current_state.status.value,
            'message': self.current_state.message,
            'requires_user_action': self.current_state.requires_user_action,
            'recommendations': self.current_state.recommendations,
            'progress_info': self.current_state.progress_info,
            'position_known': self.current_state.progress_info.get('position_known', False),
            'timestamp': self.current_state.timestamp.isoformat()
        }