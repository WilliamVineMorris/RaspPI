#!/usr/bin/env python3
"""
Comprehensive Timing Logger for FluidNC Command Pipeline Analysis

This module provides detailed timing analysis for the complete command pipeline:
Web UI → Backend API → Motion Controller → FluidNC Protocol → Hardware Execution

Usage:
    from timing_logger import TimingLogger, timing_logger
    
    # Log command receipt
    timing_logger.log_command_received("jog_relative", {"x": 1.0})
    
    # Log backend processing
    timing_logger.log_backend_start("motion_controller.move_relative")
    
    # Log FluidNC communication
    timing_logger.log_fluidnc_send("G1 X1.0 F100")
    timing_logger.log_fluidnc_response("ok")
    
    # Log completion
    timing_logger.log_command_complete("jog_relative")
"""

import time
import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
from datetime import datetime
import threading

# Configure dedicated timing logger
timing_logger_instance = logging.getLogger("timing_analysis")
timing_handler = logging.FileHandler("timing_analysis.log", mode='w')
timing_formatter = logging.Formatter(
    '%(asctime)s.%(msecs)03d | %(message)s',
    datefmt='%H:%M:%S'
)
timing_handler.setFormatter(timing_formatter)
timing_logger_instance.addHandler(timing_handler)
timing_logger_instance.setLevel(logging.INFO)

@dataclass
class CommandTiming:
    """Tracks timing for a single command through the pipeline"""
    command_id: str
    command_type: str
    command_data: Dict[str, Any]
    
    # Timestamps (in seconds since epoch)
    web_ui_timestamp: Optional[float] = None
    backend_received_timestamp: Optional[float] = None
    backend_start_timestamp: Optional[float] = None
    motion_controller_start_timestamp: Optional[float] = None
    fluidnc_send_timestamp: Optional[float] = None
    fluidnc_response_timestamp: Optional[float] = None
    backend_complete_timestamp: Optional[float] = None
    web_ui_complete_timestamp: Optional[float] = None
    
    # Additional data
    fluidnc_command: Optional[str] = None
    fluidnc_response: Optional[str] = None
    error_message: Optional[str] = None
    
    def get_phase_duration(self, start_phase: str, end_phase: str) -> Optional[float]:
        """Calculate duration between two phases in milliseconds"""
        start_time = getattr(self, f"{start_phase}_timestamp", None)
        end_time = getattr(self, f"{end_phase}_timestamp", None)
        
        if start_time is not None and end_time is not None:
            return (end_time - start_time) * 1000  # Convert to milliseconds
        return None
    
    def get_total_duration(self) -> Optional[float]:
        """Get total command duration in milliseconds"""
        if self.web_ui_timestamp and self.web_ui_complete_timestamp:
            return (self.web_ui_complete_timestamp - self.web_ui_timestamp) * 1000
        elif self.backend_received_timestamp and self.backend_complete_timestamp:
            return (self.backend_complete_timestamp - self.backend_received_timestamp) * 1000
        return None

class TimingLogger:
    """Thread-safe timing logger for command pipeline analysis"""
    
    def __init__(self):
        self._active_commands: Dict[str, CommandTiming] = {}
        self._completed_commands: List[CommandTiming] = []
        self._lock = threading.Lock()
        self._command_counter = 0
    
    def _generate_command_id(self, command_type: str) -> str:
        """Generate unique command ID"""
        with self._lock:
            self._command_counter += 1
            return f"{command_type}_{self._command_counter:04d}"
    
    def _log_timing_event(self, event_type: str, command_id: str, details: str = ""):
        """Log timing event with consistent format"""
        timestamp = time.time()
        timing_logger_instance.info(
            f"⏱️  {event_type:<20} | CMD:{command_id} | {details}"
        )
        return timestamp
    
    def log_web_ui_send(self, command_type: str, command_data: Dict[str, Any]) -> str:
        """Log command sent from web UI"""
        command_id = self._generate_command_id(command_type)
        timestamp = self._log_timing_event(
            "WEB_UI_SEND", 
            command_id, 
            f"Data: {json.dumps(command_data, default=str)}"
        )
        
        with self._lock:
            self._active_commands[command_id] = CommandTiming(
                command_id=command_id,
                command_type=command_type,
                command_data=command_data,
                web_ui_timestamp=timestamp
            )
        
        return command_id
    
    def log_backend_received(self, command_id: Optional[str] = None, command_type: Optional[str] = None, command_data: Optional[Dict[str, Any]] = None):
        """Log command received by backend API"""
        # If no command_id provided, create new command (for commands that start at backend)
        if command_id is None:
            command_id = self._generate_command_id(command_type or "unknown")
            with self._lock:
                self._active_commands[command_id] = CommandTiming(
                    command_id=command_id,
                    command_type=command_type or "unknown",
                    command_data=command_data or {}
                )
        
        timestamp = self._log_timing_event("BACKEND_RECEIVED", command_id)
        
        with self._lock:
            if command_id in self._active_commands:
                self._active_commands[command_id].backend_received_timestamp = timestamp
        
        return command_id
    
    def log_backend_start(self, command_id: str, method_name: str):
        """Log backend processing start"""
        timestamp = self._log_timing_event(
            "BACKEND_START", 
            command_id, 
            f"Method: {method_name}"
        )
        
        with self._lock:
            if command_id in self._active_commands:
                self._active_commands[command_id].backend_start_timestamp = timestamp
    
    def log_motion_controller_start(self, command_id: str, method_name: str):
        """Log motion controller processing start"""
        timestamp = self._log_timing_event(
            "MOTION_START", 
            command_id, 
            f"Method: {method_name}"
        )
        
        with self._lock:
            if command_id in self._active_commands:
                self._active_commands[command_id].motion_controller_start_timestamp = timestamp
    
    def log_fluidnc_send(self, command_id: str, gcode_command: str):
        """Log FluidNC command transmission"""
        timestamp = self._log_timing_event(
            "FLUIDNC_SEND", 
            command_id, 
            f"G-code: {gcode_command.strip()}"
        )
        
        with self._lock:
            if command_id in self._active_commands:
                cmd = self._active_commands[command_id]
                cmd.fluidnc_send_timestamp = timestamp
                cmd.fluidnc_command = gcode_command.strip()
    
    def log_fluidnc_response(self, command_id: str, response: str):
        """Log FluidNC response received"""
        timestamp = self._log_timing_event(
            "FLUIDNC_RESPONSE", 
            command_id, 
            f"Response: {response.strip()}"
        )
        
        with self._lock:
            if command_id in self._active_commands:
                cmd = self._active_commands[command_id]
                cmd.fluidnc_response_timestamp = timestamp
                cmd.fluidnc_response = response.strip()
    
    def log_backend_complete(self, command_id: str, success: bool = True, error: Optional[str] = None):
        """Log backend processing completion"""
        status = "SUCCESS" if success else "ERROR"
        details = f"Status: {status}"
        if error:
            details += f" | Error: {error}"
        
        timestamp = self._log_timing_event("BACKEND_COMPLETE", command_id, details)
        
        with self._lock:
            if command_id in self._active_commands:
                cmd = self._active_commands[command_id]
                cmd.backend_complete_timestamp = timestamp
                if error:
                    cmd.error_message = error
    
    def log_web_ui_complete(self, command_id: str):
        """Log web UI receives completion response"""
        timestamp = self._log_timing_event("WEB_UI_COMPLETE", command_id)
        
        with self._lock:
            if command_id in self._active_commands:
                cmd = self._active_commands[command_id]
                cmd.web_ui_complete_timestamp = timestamp
                
                # Move to completed commands and generate summary
                self._completed_commands.append(cmd)
                del self._active_commands[command_id]
                
                # Log timing summary
                self._log_command_summary(cmd)
    
    def _log_command_summary(self, cmd: CommandTiming):
        """Log detailed timing summary for completed command"""
        timing_logger_instance.info("=" * 80)
        timing_logger_instance.info(f"📋 COMMAND SUMMARY: {cmd.command_id} ({cmd.command_type})")
        timing_logger_instance.info("=" * 80)
        
        # Phase durations
        phases = [
            ("Web UI → Backend", "web_ui", "backend_received"),
            ("Backend Queue", "backend_received", "backend_start"),
            ("Backend Processing", "backend_start", "motion_controller_start"),
            ("Motion Controller", "motion_controller_start", "fluidnc_send"),
            ("FluidNC Transmission", "fluidnc_send", "fluidnc_response"),
            ("Backend Completion", "fluidnc_response", "backend_complete"),
            ("Response to Web UI", "backend_complete", "web_ui_complete"),
        ]
        
        total_duration = cmd.get_total_duration()
        if total_duration:
            timing_logger_instance.info(f"🕐 TOTAL DURATION: {total_duration:.1f}ms")
        
        timing_logger_instance.info("📊 PHASE BREAKDOWN:")
        for phase_name, start_phase, end_phase in phases:
            duration = cmd.get_phase_duration(start_phase, end_phase)
            if duration is not None:
                timing_logger_instance.info(f"  ⏱️  {phase_name:<25}: {duration:6.1f}ms")
            else:
                timing_logger_instance.info(f"  ❓  {phase_name:<25}: N/A")
        
        # Command details
        timing_logger_instance.info(f"🎯 Command Data: {json.dumps(cmd.command_data, default=str)}")
        if cmd.fluidnc_command:
            timing_logger_instance.info(f"📤 FluidNC Command: {cmd.fluidnc_command}")
        if cmd.fluidnc_response:
            timing_logger_instance.info(f"📥 FluidNC Response: {cmd.fluidnc_response}")
        if cmd.error_message:
            timing_logger_instance.info(f"❌ Error: {cmd.error_message}")
        
        timing_logger_instance.info("=" * 80)
    
    def log_error(self, command_id: str, error_message: str, phase: str = "unknown"):
        """Log error during command processing"""
        self._log_timing_event(
            f"ERROR_{phase.upper()}", 
            command_id, 
            f"Error: {error_message}"
        )
        
        with self._lock:
            if command_id in self._active_commands:
                self._active_commands[command_id].error_message = error_message
    
    def get_active_commands(self) -> List[str]:
        """Get list of currently active command IDs"""
        with self._lock:
            return list(self._active_commands.keys())
    
    def get_command_status(self, command_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a command"""
        with self._lock:
            if command_id in self._active_commands:
                return asdict(self._active_commands[command_id])
            
            # Check completed commands
            for cmd in reversed(self._completed_commands):
                if cmd.command_id == command_id:
                    return asdict(cmd)
        
        return None
    
    def clear_completed_commands(self, keep_last_n: int = 50):
        """Clear old completed commands to prevent memory bloat"""
        with self._lock:
            if len(self._completed_commands) > keep_last_n:
                self._completed_commands = self._completed_commands[-keep_last_n:]
    
    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate performance analysis report"""
        with self._lock:
            if not self._completed_commands:
                return {"error": "No completed commands to analyze"}
            
            # Calculate statistics
            total_durations = []
            phase_durations = {
                "web_ui_to_backend": [],
                "backend_queue": [],
                "backend_processing": [],
                "motion_controller": [],
                "fluidnc_transmission": [],
                "backend_completion": [],
                "response_to_web_ui": []
            }
            
            for cmd in self._completed_commands:
                total = cmd.get_total_duration()
                if total:
                    total_durations.append(total)
                
                # Collect phase durations
                phases = [
                    ("web_ui_to_backend", "web_ui", "backend_received"),
                    ("backend_queue", "backend_received", "backend_start"),
                    ("backend_processing", "backend_start", "motion_controller_start"),
                    ("motion_controller", "motion_controller_start", "fluidnc_send"),
                    ("fluidnc_transmission", "fluidnc_send", "fluidnc_response"),
                    ("backend_completion", "fluidnc_response", "backend_complete"),
                    ("response_to_web_ui", "backend_complete", "web_ui_complete"),
                ]
                
                for phase_key, start_phase, end_phase in phases:
                    duration = cmd.get_phase_duration(start_phase, end_phase)
                    if duration is not None:
                        phase_durations[phase_key].append(duration)
            
            # Calculate statistics
            def calc_stats(durations: List[float]) -> Dict[str, float]:
                if not durations:
                    return {"min": 0, "max": 0, "avg": 0, "count": 0}
                
                return {
                    "min": min(durations),
                    "max": max(durations),
                    "avg": sum(durations) / len(durations),
                    "count": len(durations)
                }
            
            report = {
                "total_commands": len(self._completed_commands),
                "active_commands": len(self._active_commands),
                "total_duration_stats": calc_stats(total_durations),
                "phase_stats": {phase: calc_stats(durations) 
                               for phase, durations in phase_durations.items()}
            }
            
            return report

# Global timing logger instance
timing_logger = TimingLogger()

def log_startup():
    """Log timing logger startup"""
    timing_logger_instance.info("🚀 TIMING LOGGER STARTED")
    timing_logger_instance.info("=" * 80)
    timing_logger_instance.info("📊 Command Pipeline Timing Analysis")
    timing_logger_instance.info("🔍 Tracking: Web UI → Backend → Motion Controller → FluidNC")
    timing_logger_instance.info("=" * 80)

# Log startup when module is imported
log_startup()