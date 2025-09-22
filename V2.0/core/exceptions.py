"""
Custom Exception Classes for Scanner System

Defines hierarchical exception classes for different types of errors
that can occur in the scanner system. This allows for specific error
handling and better debugging.

Author: Scanner System Development
Created: September 2025
"""

from typing import Optional

class ScannerSystemError(Exception):
    """Base exception for all scanner system errors"""
    
    def __init__(self, message: str, error_code: Optional[str] = None, module: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        self.module = module
        super().__init__(self.message)
    
    def __str__(self):
        parts = [self.message]
        if self.module:
            parts.append(f"Module: {self.module}")
        if self.error_code:
            parts.append(f"Code: {self.error_code}")
        return " | ".join(parts)


# Configuration Errors
class ConfigurationError(ScannerSystemError):
    """Raised when configuration is invalid or missing"""
    pass


class ConfigurationNotFoundError(ConfigurationError):
    """Raised when configuration file is not found"""
    pass


class ConfigurationValidationError(ConfigurationError):
    """Raised when configuration values are invalid"""
    pass


# Hardware Communication Errors
class HardwareError(ScannerSystemError):
    """Base class for hardware-related errors"""
    pass


class HardwareConnectionError(HardwareError):
    """Raised when hardware connection fails"""
    pass


class HardwareTimeoutError(HardwareError):
    """Raised when hardware operation times out"""
    pass


class HardwareNotReadyError(HardwareError):
    """Raised when hardware is not ready for operation"""
    pass


# Motion Control Errors
class MotionControlError(HardwareError):
    """Base class for motion control errors"""
    pass


class MotionLimitError(MotionControlError):
    """Raised when motion exceeds configured limits"""
    pass


class MotionSafetyError(MotionControlError):
    """Raised when motion violates safety constraints"""
    pass


class MotionTimeoutError(MotionControlError):
    """Raised when motion operation times out"""
    pass


class FluidNCError(MotionControlError):
    """Raised for FluidNC-specific errors"""
    pass


class FluidNCConnectionError(FluidNCError):
    """Raised when FluidNC connection fails"""
    pass


class FluidNCCommandError(FluidNCError):
    """Raised when FluidNC command fails"""
    pass


# Camera Control Errors
class CameraError(HardwareError):
    """Base class for camera-related errors"""
    pass


class CameraNotFoundError(CameraError):
    """Raised when camera is not detected"""
    pass


class CameraInitializationError(CameraError):
    """Raised when camera initialization fails"""
    pass


class CameraCaptureError(CameraError):
    """Raised when photo capture fails"""
    pass


class CameraSyncError(CameraError):
    """Raised when dual camera synchronization fails"""
    pass


class StreamingError(CameraError):
    """Raised when video streaming fails"""
    pass


class CameraConfigurationError(CameraError):
    """Raised when camera configuration fails"""
    pass


class CameraConnectionError(CameraError):
    """Raised when camera connection fails"""
    pass


# LED Control Errors
class LEDError(HardwareError):
    """Base class for LED control errors"""
    pass


class LEDInitializationError(LEDError):
    """Raised when LED initialization fails"""
    pass


class LEDSafetyError(LEDError):
    """Raised when LED operation violates safety constraints"""
    pass


class LEDTimingError(LEDError):
    """Raised when LED timing synchronization fails"""
    pass


class GPIOError(LEDError):
    """Raised for GPIO-related errors"""
    pass


# Path Planning Errors
class PathPlanningError(ScannerSystemError):
    """Base class for path planning errors"""
    pass


class PathValidationError(PathPlanningError):
    """Raised when scan path is invalid"""
    pass


class CollisionDetectionError(PathPlanningError):
    """Raised when collision is detected in path"""
    pass


class PathGenerationError(PathPlanningError):
    """Raised when path generation fails"""
    pass


# Storage and Data Errors
class StorageError(ScannerSystemError):
    """Base class for storage-related errors"""
    pass


class StorageSpaceError(StorageError):
    """Raised when insufficient storage space"""
    pass


class FileWriteError(StorageError):
    """Raised when file write operation fails"""
    pass


class MetadataError(StorageError):
    """Raised when metadata generation fails"""
    pass


class DataCorruptionError(StorageError):
    """Raised when data corruption is detected"""
    pass


# Web Interface Errors
class WebInterfaceError(ScannerSystemError):
    """Base class for web interface errors"""
    pass


class WebServerError(WebInterfaceError):
    """Raised when web server fails"""
    pass


class APIError(WebInterfaceError):
    """Raised when API operation fails"""
    pass


# Communication Errors
class CommunicationError(ScannerSystemError):
    """Base class for communication errors"""
    pass


class NetworkError(CommunicationError):
    """Raised when network communication fails"""
    pass


class DataTransferError(CommunicationError):
    """Raised when data transfer fails"""
    pass


# Orchestration Errors
class OrchestrationError(ScannerSystemError):
    """Base class for orchestration errors"""
    pass


class ScanExecutionError(OrchestrationError):
    """Raised when scan execution fails"""
    pass


class ModuleCoordinationError(OrchestrationError):
    """Raised when module coordination fails"""
    pass


class WorkflowError(OrchestrationError):
    """Raised when workflow execution fails"""
    pass


# Recovery and Emergency Errors
class EmergencyStopError(ScannerSystemError):
    """Raised when emergency stop is triggered"""
    pass


class RecoveryError(ScannerSystemError):
    """Raised when error recovery fails"""
    pass


class SystemShutdownError(ScannerSystemError):
    """Raised during system shutdown issues"""
    pass


# Utility functions for error handling
def create_hardware_error(message: str, module: str, error_code: Optional[str] = None) -> HardwareError:
    """Factory function to create hardware errors with consistent formatting"""
    return HardwareError(message, error_code=error_code, module=module)


def create_motion_error(message: str, error_code: Optional[str] = None) -> MotionControlError:
    """Factory function to create motion control errors"""
    return MotionControlError(message, error_code=error_code, module="motion")


def create_camera_error(message: str, error_code: Optional[str] = None) -> CameraError:
    """Factory function to create camera errors"""
    return CameraError(message, error_code=error_code, module="camera")


def create_led_error(message: str, error_code: Optional[str] = None) -> LEDError:
    """Factory function to create LED errors"""
    return LEDError(message, error_code=error_code, module="lighting")


# Exception mapping for easy error type identification
ERROR_TYPE_MAP = {
    'config': ConfigurationError,
    'hardware': HardwareError,
    'motion': MotionControlError,
    'camera': CameraError,
    'led': LEDError,
    'planning': PathPlanningError,
    'storage': StorageError,
    'web': WebInterfaceError,
    'communication': CommunicationError,
    'orchestration': OrchestrationError
}


def get_error_class(error_type: str) -> type:
    """Get exception class by error type string"""
    return ERROR_TYPE_MAP.get(error_type, ScannerSystemError)


# Convenient aliases for common usage
ScannerError = ScannerSystemError
MotionError = MotionControlError