"""
Abstract LED Lighting Control Interface

Defines the standard interface for LED lighting control systems.
This enables support for different LED configurations and control methods
while maintaining consistent API for zone-based illumination control.

SAFETY CRITICAL: GPIO pins must never exceed 90% duty cycle to prevent hardware damage.

Author: Scanner System Development
Created: September 2025
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable, Union
from enum import Enum
import asyncio
import time
from pathlib import Path

from core.exceptions import LEDError
from core.events import ScannerEvent


class LightingStatus(Enum):
    """LED lighting status states"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    ACTIVE = "active"
    FADING = "fading"
    ERROR = "error"
    CALIBRATING = "calibrating"


class FlashMode(Enum):
    """LED flash modes"""
    CONTINUOUS = "continuous"    # Continuous illumination
    STROBE = "strobe"           # Strobe flash
    TRIGGER = "trigger"         # Triggered flash
    PATTERN = "pattern"         # Pattern-based illumination


class LEDType(Enum):
    """LED types supported"""
    WHITE = "white"
    RGB = "rgb"
    WARM_WHITE = "warm_white"
    COOL_WHITE = "cool_white"
    INFRARED = "infrared"


@dataclass
class LEDZone:
    """Configuration for an LED zone"""
    zone_id: str
    gpio_pins: List[int]
    led_type: LEDType
    max_current_ma: int
    position: Tuple[float, float, float]  # X, Y, Z position in mm
    direction: Tuple[float, float, float]  # Direction vector (normalized)
    beam_angle: float  # Beam angle in degrees
    max_brightness: float = 1.0  # Maximum brightness (0.0-1.0)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'zone_id': self.zone_id,
            'gpio_pins': self.gpio_pins,
            'led_type': self.led_type.value,
            'max_current_ma': self.max_current_ma,
            'position': self.position,
            'direction': self.direction,
            'beam_angle': self.beam_angle,
            'max_brightness': self.max_brightness
        }


@dataclass
class LightingSettings:
    """LED lighting configuration settings"""
    brightness: float = 0.5  # 0.0-1.0
    duration_ms: Optional[float] = None  # Flash duration in milliseconds (0 = constant mode)
    fade_time_ms: float = 100  # Fade in/out time
    strobe_frequency: Optional[float] = None  # Hz for strobe mode
    pattern_file: Optional[Path] = None  # Pattern definition file
    constant_mode: bool = False  # If True, use constant lighting instead of timed flash
    
    def __post_init__(self):
        # Safety validation
        if not 0.0 <= self.brightness <= 1.0:
            raise ValueError("Brightness must be between 0.0 and 1.0")
        
        if self.strobe_frequency and self.strobe_frequency <= 0:
            raise ValueError("Strobe frequency must be positive")
        
        # Auto-enable constant mode if duration is 0
        if self.duration_ms == 0:
            self.constant_mode = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'brightness': self.brightness,
            'duration_ms': self.duration_ms,
            'fade_time_ms': self.fade_time_ms,
            'strobe_frequency': self.strobe_frequency,
            'pattern_file': str(self.pattern_file) if self.pattern_file else None,
            'constant_mode': self.constant_mode
        }


@dataclass
class FlashResult:
    """Result of a flash operation"""
    success: bool
    zones_activated: List[str]
    actual_brightness: Dict[str, float]
    duration_ms: Optional[float] = None
    timestamp: Optional[float] = None
    error_message: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


@dataclass
class PowerMetrics:
    """Power consumption metrics"""
    total_current_ma: float
    voltage_v: float
    power_consumption_w: float
    duty_cycles: Dict[str, float]  # Zone ID -> current duty cycle
    temperature_c: Optional[float] = None
    
    @property
    def max_duty_cycle(self) -> float:
        """Get maximum duty cycle across all zones"""
        return max(self.duty_cycles.values()) if self.duty_cycles else 0.0
    
    @property
    def is_safe(self) -> bool:
        """Check if power metrics are within safe limits"""
        return self.max_duty_cycle < 0.90  # Safety limit: <90% duty cycle


class LightingController(ABC):
    """
    Abstract base class for LED lighting control systems
    
    SAFETY CRITICAL: All implementations must enforce duty cycle limits
    to prevent hardware damage. GPIO pins must never exceed 90% duty cycle.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = LightingStatus.DISCONNECTED
        self.led_zones: Dict[str, LEDZone] = {}
        self.current_brightness: Dict[str, float] = {}
        self.current_settings: Dict[str, LightingSettings] = {}
        self.event_callbacks: List[Callable] = []
        self.last_flash_time: Optional[float] = None
        self.safety_enabled = True  # Always start with safety enabled
        self._max_duty_cycle = 0.89  # Safety limit: 89% max duty cycle
    
    # Connection Management
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize LED lighting system
        
        Returns:
            True if initialization successful
            
        Raises:
            LEDError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """
        Shutdown lighting system and turn off all LEDs
        
        Returns:
            True if shutdown successful
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if lighting system is available and ready"""
        pass
    
    # Zone Configuration
    @abstractmethod
    async def configure_zone(self, zone: LEDZone) -> bool:
        """
        Configure LED zone
        
        Args:
            zone: LED zone configuration
            
        Returns:
            True if configuration successful
            
        Raises:
            LEDError: If configuration fails
        """
        pass
    
    @abstractmethod
    async def remove_zone(self, zone_id: str) -> bool:
        """
        Remove LED zone configuration
        
        Args:
            zone_id: Zone identifier to remove
            
        Returns:
            True if removal successful
        """
        pass
    
    @abstractmethod
    async def list_zones(self) -> List[str]:
        """
        List configured LED zones
        
        Returns:
            List of zone identifiers
        """
        pass
    
    @abstractmethod
    async def get_zone_info(self, zone_id: str) -> Dict[str, Any]:
        """
        Get LED zone information
        
        Args:
            zone_id: Zone identifier
            
        Returns:
            Dictionary with zone information
        """
        pass
    
    # Basic Lighting Control
    @abstractmethod
    async def set_brightness(self, zone_id: str, brightness: float) -> bool:
        """
        Set brightness for LED zone
        
        Args:
            zone_id: Zone identifier
            brightness: Brightness level (0.0-1.0)
            
        Returns:
            True if brightness set successfully
            
        Raises:
            LEDError: If brightness setting fails
        """
        pass
    
    @abstractmethod
    async def set_all_brightness(self, brightness: float) -> bool:
        """
        Set brightness for all LED zones
        
        Args:
            brightness: Brightness level (0.0-1.0)
            
        Returns:
            True if brightness set successfully
        """
        pass
    
    @abstractmethod
    async def turn_on(self, zone_id: str, brightness: float = 1.0) -> bool:
        """
        Turn on LED zone
        
        Args:
            zone_id: Zone identifier
            brightness: Brightness level (0.0-1.0)
            
        Returns:
            True if zone turned on successfully
        """
        pass
    
    @abstractmethod
    async def turn_off(self, zone_id: str) -> bool:
        """
        Turn off LED zone
        
        Args:
            zone_id: Zone identifier
            
        Returns:
            True if zone turned off successfully
        """
        pass
    
    @abstractmethod
    async def turn_off_all(self) -> bool:
        """
        Turn off all LED zones
        
        Returns:
            True if all zones turned off successfully
        """
        pass
    
    # Advanced Lighting Operations
    @abstractmethod
    async def flash(self, zone_ids: List[str], settings: LightingSettings) -> FlashResult:
        """
        Flash LED zones with specified settings
        
        Args:
            zone_ids: List of zone identifiers to flash
            settings: Flash settings
            
        Returns:
            Flash operation result
            
        Raises:
            LEDError: If flash operation fails
        """
        pass
    
    @abstractmethod
    async def synchronized_flash(self, zone_settings: Dict[str, LightingSettings]) -> FlashResult:
        """
        Flash multiple zones with synchronized timing
        
        Args:
            zone_settings: Dictionary mapping zone IDs to flash settings
            
        Returns:
            Flash operation result
        """
        pass
    
    @abstractmethod
    async def trigger_for_capture(self, camera_controller, zone_ids: List[str], 
                                 settings: LightingSettings) -> FlashResult:
        """
        Trigger LED flash synchronized with camera capture
        
        Args:
            camera_controller: Camera controller for synchronization
            zone_ids: List of zone identifiers to flash
            settings: Flash settings
            
        Returns:
            Flash operation result with camera sync info
        """
        pass
    
    @abstractmethod
    async def fade_to(self, zone_id: str, target_brightness: float, duration_ms: float) -> bool:
        """
        Fade LED zone to target brightness
        
        Args:
            zone_id: Zone identifier
            target_brightness: Target brightness (0.0-1.0)
            duration_ms: Fade duration in milliseconds
            
        Returns:
            True if fade completed successfully
        """
        pass
    
    @abstractmethod
    async def strobe(self, zone_id: str, frequency: float, duration_ms: float, 
                    brightness: float = 1.0) -> bool:
        """
        Strobe LED zone at specified frequency
        
        Args:
            zone_id: Zone identifier
            frequency: Strobe frequency in Hz
            duration_ms: Strobe duration in milliseconds
            brightness: Strobe brightness (0.0-1.0)
            
        Returns:
            True if strobe completed successfully
        """
        pass
    
    # Pattern Control
    @abstractmethod
    async def load_pattern(self, pattern_file: Path) -> bool:
        """
        Load lighting pattern from file
        
        Args:
            pattern_file: Path to pattern definition file
            
        Returns:
            True if pattern loaded successfully
        """
        pass
    
    @abstractmethod
    async def execute_pattern(self, pattern_name: str, repeat: int = 1) -> bool:
        """
        Execute loaded lighting pattern
        
        Args:
            pattern_name: Name of pattern to execute
            repeat: Number of times to repeat pattern
            
        Returns:
            True if pattern executed successfully
        """
        pass
    
    @abstractmethod
    async def stop_pattern(self) -> bool:
        """
        Stop currently executing pattern
        
        Returns:
            True if pattern stopped successfully
        """
        pass
    
    # Camera Synchronization
    @abstractmethod
    async def trigger_for_capture(self, camera_controller, zone_ids: List[str], 
                                 settings: LightingSettings) -> FlashResult:
        """
        Trigger LED flash synchronized with camera capture
        
        Args:
            camera_controller: Camera controller for synchronization
            zone_ids: List of zone identifiers to flash
            settings: Flash settings
            
        Returns:
            Flash operation result with camera sync info
        """
        pass
    
    @abstractmethod
    async def calibrate_camera_sync(self, camera_controller, test_flashes: int = 5) -> float:
        """
        Calibrate LED flash timing with camera
        
        Args:
            camera_controller: Camera controller for calibration
            test_flashes: Number of test flashes for calibration
            
        Returns:
            Average synchronization delay in milliseconds
        """
        pass
    
    # Status and Monitoring
    @abstractmethod
    async def get_status(self, zone_id: Optional[str] = None) -> Union[LightingStatus, Dict[str, LightingStatus]]:
        """
        Get lighting status
        
        Args:
            zone_id: Specific zone ID or None for all zones
            
        Returns:
            Lighting status or dictionary of statuses
        """
        pass
    
    @abstractmethod
    async def get_brightness(self, zone_id: str) -> float:
        """
        Get current brightness for zone
        
        Args:
            zone_id: Zone identifier
            
        Returns:
            Current brightness level (0.0-1.0)
        """
        pass
    
    @abstractmethod
    async def get_power_metrics(self) -> PowerMetrics:
        """
        Get power consumption metrics
        
        Returns:
            Current power metrics
        """
        pass
    
    @abstractmethod
    async def get_last_error(self, zone_id: str) -> Optional[str]:
        """
        Get last error message for zone
        
        Args:
            zone_id: Zone identifier
            
        Returns:
            Last error message or None
        """
        pass
    
    # Safety and Validation
    def validate_brightness(self, brightness: float) -> bool:
        """Validate brightness value is within safe limits"""
        return 0.0 <= brightness <= 1.0
    
    def validate_duty_cycle(self, duty_cycle: float) -> bool:
        """Validate duty cycle is within safety limits"""
        return 0.0 <= duty_cycle <= self._max_duty_cycle
    
    def calculate_duty_cycle(self, brightness: float, zone_id: str) -> float:
        """
        Calculate duty cycle for given brightness and zone
        
        Args:
            brightness: Desired brightness (0.0-1.0)
            zone_id: Zone identifier
            
        Returns:
            Required duty cycle (0.0-1.0)
        """
        if zone_id not in self.led_zones:
            return 0.0
        
        zone = self.led_zones[zone_id]
        max_brightness = zone.max_brightness
        
        # Calculate duty cycle with safety limit
        duty_cycle = brightness * max_brightness
        return min(duty_cycle, self._max_duty_cycle)
    
    async def emergency_shutdown(self) -> bool:
        """
        Emergency shutdown - turn off all LEDs immediately
        
        Returns:
            True if emergency shutdown successful
        """
        try:
            await self.turn_off_all()
            self.status = LightingStatus.ERROR
            self._notify_event("emergency_shutdown", {"reason": "Safety emergency"})
            return True
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.critical(f"Emergency shutdown failed: {e}")
            return False
    
    # Event Handling
    def add_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Add callback for lighting events"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Remove event callback"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def _notify_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Notify all event callbacks"""
        from core.events import ScannerEvent, EventPriority
        
        # Determine priority based on event type
        priority = EventPriority.CRITICAL if "emergency" in event_type else EventPriority.NORMAL
        
        event = ScannerEvent(
            event_type=event_type,
            data=data or {},
            source_module="lighting",
            priority=priority
        )
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in lighting event callback: {e}")
    
    # Utility Methods
    def create_zone_from_config(self, zone_config: Dict[str, Any]) -> LEDZone:
        """Create LED zone from configuration dictionary"""
        return LEDZone(
            zone_id=zone_config['zone_id'],
            gpio_pins=zone_config['gpio_pins'],
            led_type=LEDType(zone_config['led_type']),
            max_current_ma=zone_config['max_current_ma'],
            position=tuple(zone_config['position']),
            direction=tuple(zone_config['direction']),
            beam_angle=zone_config['beam_angle'],
            max_brightness=zone_config.get('max_brightness', 1.0)
        )
    
    def estimate_flash_duration(self, settings: LightingSettings) -> float:
        """
        Estimate flash duration based on settings
        
        Args:
            settings: Flash settings
            
        Returns:
            Estimated duration in milliseconds
        """
        if settings.duration_ms:
            return settings.duration_ms
        
        # Default flash duration for different modes
        base_duration = 50.0  # milliseconds
        
        if settings.strobe_frequency:
            return 1000.0 / settings.strobe_frequency  # One strobe cycle
        
        return base_duration + (2 * settings.fade_time_ms)


# Utility functions for lighting operations
def create_flash_settings(brightness: float = 0.8, duration_ms: float = 100) -> LightingSettings:
    """Create settings for camera flash"""
    return LightingSettings(
        brightness=brightness,
        duration_ms=duration_ms,
        fade_time_ms=10  # Quick fade for flash
    )


def create_continuous_settings(brightness: float = 0.5) -> LightingSettings:
    """Create settings for continuous illumination"""
    return LightingSettings(
        brightness=brightness,
        fade_time_ms=200  # Smooth fade for continuous
    )


def validate_power_safety(metrics: PowerMetrics, max_current_a: float = 2.0) -> bool:
    """
    Validate power metrics are within safety limits
    
    Args:
        metrics: Power metrics to validate
        max_current_a: Maximum allowed current in amperes
        
    Returns:
        True if power metrics are safe
    """
    # Check duty cycle safety
    if not metrics.is_safe:
        return False
    
    # Check current limits
    if metrics.total_current_ma > (max_current_a * 1000):
        return False
    
    # Check temperature if available
    if metrics.temperature_c and metrics.temperature_c > 70.0:  # 70°C limit
        return False
    
    return True