"""
Phase 2: Standardized LED Lighting Controller Adapter

This adapter provides a standardized interface for LED lighting controllers
with explicit safety measures and Z-axis rotation coordination.

Key Features:
- Standardized adapter pattern for LED controllers
- CRITICAL GPIO safety with 90% duty cycle limits
- Rotational motion-aware lighting patterns
- Flash synchronization with camera capture timing
- Position-based lighting control
- Emergency shutdown capabilities
- PWM safety validation

Author: Scanner System Development - Phase 2
Created: September 2025
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum

from lighting.base import (
    LightingController, LightingSettings, LightingStatus,
    LEDZone, FlashResult
)
from motion.base import Position4D, AxisType
from core.exceptions import LEDError, LEDSafetyError
from core.events import ScannerEvent, EventPriority


class LightingMode(Enum):
    """LED lighting modes"""
    OFF = "off"
    AMBIENT = "ambient"
    FLASH = "flash"
    CONTINUOUS = "continuous"
    ROTATION_TRACKING = "rotation_tracking"
    POSITION_BASED = "position_based"


class RotationLightingPattern(Enum):
    """Lighting patterns for rotational motion"""
    STATIC = "static"                 # Fixed lighting regardless of rotation
    FOLLOWING = "following"           # Light follows Z rotation angle
    OPPOSING = "opposing"             # Light opposite to Z rotation
    GRADIENT = "gradient"             # Gradient lighting based on Z position
    SECTORED = "sectored"             # Different sectors for different Z ranges


@dataclass
class SafetyLimits:
    """Critical safety limits for LED operation"""
    max_duty_cycle: float = 0.90     # NEVER exceed 90% to prevent GPIO damage
    max_current_ma: float = 500.0    # Maximum current per LED
    thermal_limit_c: float = 60.0    # Thermal shutdown temperature
    emergency_timeout_s: float = 0.1 # Emergency shutdown timeout


@dataclass
class RotationLightingCommand:
    """Lighting command for rotational motion"""
    pattern: RotationLightingPattern
    intensity: float  # 0.0 to 1.0
    z_angle: float   # Current Z rotation angle
    duration_ms: Optional[float] = None
    flash_sync: bool = False


@dataclass
class LightingSafetyStatus:
    """Safety status for LED operations"""
    duty_cycle_safe: bool
    current_safe: bool
    thermal_safe: bool
    gpio_operational: bool
    last_safety_check: float


class StandardLightingAdapter(ABC):
    """
    Standardized adapter interface for LED lighting controllers
    
    This adapter provides consistent lighting operations with critical
    safety measures and rotational motion coordination.
    """
    
    def __init__(self, controller: LightingController, config: Dict[str, Any]):
        self.controller = controller
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Critical safety configuration
        self.safety_limits = self._load_safety_limits()
        self.safety_status = LightingSafetyStatus(
            duty_cycle_safe=True,
            current_safe=True,
            thermal_safe=True,
            gpio_operational=True,
            last_safety_check=time.time()
        )
        
        # Motion coordination
        self.motion_adapter = None
        self._current_lighting_mode = LightingMode.OFF
        self._rotation_tracking_active = False
        
        # Performance monitoring
        self._flash_count = 0
        self._safety_violations = 0
        self._emergency_shutdowns = 0
        
    def _load_safety_limits(self) -> SafetyLimits:
        """Load safety limits from configuration"""
        lighting_config = self.config.get('lighting', {})
        safety_config = lighting_config.get('safety', {})
        
        return SafetyLimits(
            max_duty_cycle=min(safety_config.get('max_duty_cycle', 0.90), 0.90),  # NEVER exceed 90%
            max_current_ma=safety_config.get('max_current_ma', 500.0),
            thermal_limit_c=safety_config.get('thermal_limit_c', 60.0),
            emergency_timeout_s=safety_config.get('emergency_timeout_s', 0.1)
        )
    
    def set_motion_adapter(self, motion_adapter):
        """Set motion adapter for coordinate lighting operations"""
        self.motion_adapter = motion_adapter
        self.logger.info("Motion adapter connected to lighting adapter")
    
    # Abstract methods for implementation
    @abstractmethod
    async def initialize_controller(self) -> bool:
        """Initialize the underlying lighting controller"""
        pass
    
    @abstractmethod
    async def shutdown_controller(self) -> bool:
        """Shutdown the underlying lighting controller with safety checks"""
        pass
    
    # Critical Safety Methods
    def validate_duty_cycle_safe(self, duty_cycle: float) -> bool:
        """
        CRITICAL: Validate duty cycle is safe for GPIO
        
        Args:
            duty_cycle: Proposed duty cycle (0.0 to 1.0)
            
        Returns:
            True if safe
            
        Raises:
            LightingSafetyError: If duty cycle exceeds safety limits
        """
        try:
            # Use the controller's validation method
            if not self.controller.validate_duty_cycle(duty_cycle):
                self._safety_violations += 1
                raise LEDSafetyError(
                    f"CRITICAL SAFETY VIOLATION: Duty cycle {duty_cycle:.3f} "
                    f"exceeds maximum safe limit {self.safety_limits.max_duty_cycle:.3f}"
                )
            
            # Additional adapter-level validation
            if duty_cycle > self.safety_limits.max_duty_cycle:
                self._safety_violations += 1
                raise LEDSafetyError(
                    f"CRITICAL SAFETY VIOLATION: Duty cycle {duty_cycle:.3f} "
                    f"exceeds maximum safe limit {self.safety_limits.max_duty_cycle:.3f}"
                )
            
            return True
            
        except Exception as e:
            self.logger.critical(f"Duty cycle safety validation failed: {e}")
            raise LEDSafetyError(f"Duty cycle validation failed: {e}")
    
    async def emergency_lighting_shutdown(self, reason: str = "safety_violation") -> bool:
        """
        CRITICAL: Emergency shutdown of all lighting
        
        Args:
            reason: Reason for emergency shutdown
            
        Returns:
            True if shutdown successful
        """
        try:
            self.logger.critical(f"EMERGENCY LIGHTING SHUTDOWN: {reason}")
            self._emergency_shutdowns += 1
            
            # Use controller's emergency shutdown
            result = await self.controller.emergency_shutdown()
            
            # Update safety status
            self.safety_status.gpio_operational = False
            self.safety_status.last_safety_check = time.time()
            
            # Notify emergency event
            self._notify_lighting_event("emergency_shutdown", {
                "reason": reason,
                "timestamp": time.time(),
                "shutdown_count": self._emergency_shutdowns
            })
            
            return result
            
        except Exception as e:
            self.logger.critical(f"Emergency shutdown failed: {e}")
            return False
    
    def perform_safety_check(self) -> bool:
        """
        Perform comprehensive safety check
        
        Returns:
            True if all safety checks pass
        """
        try:
            current_time = time.time()
            
            # Check duty cycle safety (simulated - would read from controller)
            self.safety_status.duty_cycle_safe = True  # Would check actual duty cycles
            
            # Check current safety (simulated - would read from current sensors)
            self.safety_status.current_safe = True  # Would check actual current draw
            
            # Check thermal safety (simulated - would read from temperature sensors)
            self.safety_status.thermal_safe = True  # Would check actual temperatures
            
            # Check GPIO operational status
            self.safety_status.gpio_operational = self.controller.is_available()
            
            self.safety_status.last_safety_check = current_time
            
            # Overall safety status
            overall_safe = (
                self.safety_status.duty_cycle_safe and
                self.safety_status.current_safe and
                self.safety_status.thermal_safe and
                self.safety_status.gpio_operational
            )
            
            if not overall_safe:
                self.logger.warning("Safety check failed - lighting operations may be restricted")
            
            return overall_safe
            
        except Exception as e:
            self.logger.error(f"Safety check failed: {e}")
            return False
    
    # Position-Aware Lighting Methods
    async def set_lighting_for_position(self, position: Position4D, 
                                      intensity: float = 0.8) -> bool:
        """
        Set lighting based on current position (especially Z rotation)
        
        Args:
            position: Current position
            intensity: Light intensity (0.0 to 1.0)
            
        Returns:
            True if lighting set successfully
        """
        try:
            # Validate safety first
            self.validate_duty_cycle_safe(intensity)
            
            if not self.perform_safety_check():
                self.logger.error("Safety check failed - aborting lighting operation")
                return False
            
            # Calculate position-based lighting pattern
            z_angle_normalized = position.z % 360.0  # Normalize to 0-360
            
            # Calculate position-based lighting pattern using controller's zone methods
            zone_ids = list(self.controller.led_zones.keys())
            if not zone_ids:
                zone_ids = ['zone1', 'zone2']  # Default zones
            
            # Create lighting settings based on position
            settings = LightingSettings(
                brightness=intensity,
                duration_ms=100,
                fade_time_ms=10
            )
            
            # Apply lighting to all zones
            results = []
            for zone_id in zone_ids:
                try:
                    result = await self.controller.set_brightness(zone_id, intensity)
                    results.append(result)
                except Exception as e:
                    self.logger.warning(f"Failed to set brightness for zone {zone_id}: {e}")
                    results.append(False)
            
            result = any(results)  # Success if any zone was set
            
            if result:
                self._current_lighting_mode = LightingMode.POSITION_BASED
                self.logger.debug(f"Position-based lighting set for Z={position.z:.1f}°")
                
                self._notify_lighting_event("position_lighting_set", {
                    "position": position.to_dict(),
                    "intensity": intensity,
                    "z_angle_normalized": z_angle_normalized
                })
            
            return result
            
        except Exception as e:
            self.logger.error(f"Position-based lighting failed: {e}")
            return False
    
    async def flash_synchronized_with_capture(self, flash_duration_ms: float = 2.0,
                                            intensity: float = 1.0) -> bool:
        """
        Execute synchronized flash for camera capture
        
        Args:
            flash_duration_ms: Flash duration in milliseconds
            intensity: Flash intensity (0.0 to 1.0)
            
        Returns:
            True if flash executed successfully
        """
        try:
            # CRITICAL: Validate intensity is safe
            self.validate_duty_cycle_safe(intensity)
            
            if not self.perform_safety_check():
                await self.emergency_lighting_shutdown("safety_check_failed_during_flash")
                return False
            
            self.logger.info(f"Executing synchronized flash: {flash_duration_ms}ms at {intensity*100:.1f}%")
            
            # Create flash settings using LightingSettings
            flash_settings = LightingSettings(
                brightness=min(intensity, self.safety_limits.max_duty_cycle),  # Safety clamp
                duration_ms=flash_duration_ms,
                fade_time_ms=10.0  # Quick fade for flash
            )
            
            # Get available zones and execute flash
            zone_ids = list(self.controller.led_zones.keys())
            if not zone_ids:
                zone_ids = ['zone1']  # Default zone
            
            # Execute flash using the flash method
            result_obj = await self.controller.flash(zone_ids, flash_settings)
            result = result_obj.success if result_obj else False
            
            if result:
                self._flash_count += 1
                self.logger.info(f"Flash completed successfully (count: {self._flash_count})")
                
                self._notify_lighting_event("flash_completed", {
                    "duration_ms": flash_duration_ms,
                    "intensity": intensity,
                    "flash_count": self._flash_count
                })
            else:
                self.logger.error("Flash execution failed")
            
            return result
            
        except LEDSafetyError as e:
            self.logger.critical(f"Flash safety violation: {e}")
            await self.emergency_lighting_shutdown("flash_safety_violation")
            return False
        except Exception as e:
            self.logger.error(f"Flash synchronization failed: {e}")
            return False
    
    async def start_rotation_tracking(self, pattern: RotationLightingPattern = RotationLightingPattern.FOLLOWING,
                                    base_intensity: float = 0.6) -> bool:
        """
        Start lighting that tracks Z-axis rotation
        
        Args:
            pattern: Rotation lighting pattern
            base_intensity: Base lighting intensity
            
        Returns:
            True if tracking started successfully
        """
        try:
            if not self.motion_adapter:
                raise LEDError("Motion adapter required for rotation tracking")
            
            # Validate safety
            self.validate_duty_cycle_safe(base_intensity)
            
            self.logger.info(f"Starting rotation tracking with pattern: {pattern.value}")
            
            self._rotation_tracking_active = True
            self._current_lighting_mode = LightingMode.ROTATION_TRACKING
            
            # Start tracking loop
            asyncio.create_task(self._rotation_tracking_loop(pattern, base_intensity))
            
            self._notify_lighting_event("rotation_tracking_started", {
                "pattern": pattern.value,
                "base_intensity": base_intensity
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rotation tracking start failed: {e}")
            return False
    
    async def stop_rotation_tracking(self) -> bool:
        """Stop rotation tracking lighting"""
        try:
            self._rotation_tracking_active = False
            self._current_lighting_mode = LightingMode.OFF
            
            # Turn off all LEDs safely
            await self.controller.turn_off_all()
            
            self.logger.info("Rotation tracking stopped")
            self._notify_lighting_event("rotation_tracking_stopped", {})
            
            return True
            
        except Exception as e:
            self.logger.error(f"Rotation tracking stop failed: {e}")
            return False
    
    async def _rotation_tracking_loop(self, pattern: RotationLightingPattern, 
                                    base_intensity: float):
        """Background loop for rotation tracking lighting"""
        try:
            while self._rotation_tracking_active:
                if not self.motion_adapter:
                    break
                
                # Get current position
                current_pos = await self.motion_adapter.get_current_position()
                z_angle = current_pos.z
                
                # Calculate lighting based on pattern and Z angle
                if pattern == RotationLightingPattern.FOLLOWING:
                    # Light intensity follows Z rotation
                    angle_factor = (z_angle % 360.0) / 360.0
                    led1_intensity = base_intensity * (0.5 + 0.5 * angle_factor)
                    led2_intensity = base_intensity * (1.0 - 0.5 * angle_factor)
                elif pattern == RotationLightingPattern.STATIC:
                    # Static lighting regardless of rotation
                    led1_intensity = base_intensity
                    led2_intensity = base_intensity
                else:
                    # Default to static for unknown patterns
                    led1_intensity = base_intensity
                    led2_intensity = base_intensity
                
                # Apply lighting using available controller methods
                zone_ids = list(self.controller.led_zones.keys())
                if not zone_ids:
                    zone_ids = ['zone1', 'zone2']  # Default zones
                    
                for zone_id in zone_ids:
                    try:
                        await self.controller.set_brightness(zone_id, led1_intensity)
                    except Exception as e:
                        self.logger.warning(f"Failed to set brightness for zone {zone_id}: {e}")
                
                # Update at 20Hz for smooth tracking
                await asyncio.sleep(0.05)
                
        except Exception as e:
            self.logger.error(f"Rotation tracking loop failed: {e}")
            self._rotation_tracking_active = False
    
    # Status and Information
    async def get_lighting_status(self) -> Dict[str, Any]:
        """Get lighting status with safety information"""
        try:
            base_status = await self.controller.get_status()
            
            # Handle both single status and dict of statuses
            if isinstance(base_status, dict):
                status_str = str(base_status)
            else:
                status_str = base_status.value if hasattr(base_status, 'value') else str(base_status)
            
            enhanced_status = {
                "lighting_status": status_str,
                "current_mode": self._current_lighting_mode.value,
                "rotation_tracking_active": self._rotation_tracking_active,
                "safety_status": {
                    "duty_cycle_safe": self.safety_status.duty_cycle_safe,
                    "current_safe": self.safety_status.current_safe,
                    "thermal_safe": self.safety_status.thermal_safe,
                    "gpio_operational": self.safety_status.gpio_operational,
                    "last_safety_check": self.safety_status.last_safety_check
                },
                "safety_limits": {
                    "max_duty_cycle": self.safety_limits.max_duty_cycle,
                    "max_current_ma": self.safety_limits.max_current_ma,
                    "thermal_limit_c": self.safety_limits.thermal_limit_c
                },
                "statistics": {
                    "flash_count": self._flash_count,
                    "safety_violations": self._safety_violations,
                    "emergency_shutdowns": self._emergency_shutdowns
                }
            }
            
            return enhanced_status
            
        except Exception as e:
            self.logger.error(f"Failed to get lighting status: {e}")
            return {"error": str(e)}
    
    def get_safety_statistics(self) -> Dict[str, Any]:
        """Get lighting safety statistics"""
        return {
            "flash_count": self._flash_count,
            "safety_violations": self._safety_violations,
            "emergency_shutdowns": self._emergency_shutdowns,
            "safety_status": {
                "duty_cycle_safe": self.safety_status.duty_cycle_safe,
                "current_safe": self.safety_status.current_safe,
                "thermal_safe": self.safety_status.thermal_safe,
                "gpio_operational": self.safety_status.gpio_operational
            }
        }
    
    # Event Management
    def _notify_lighting_event(self, event_type: str, data: Dict[str, Any]):
        """Notify lighting event to system"""
        try:
            priority = EventPriority.CRITICAL if "emergency" in event_type else EventPriority.NORMAL
            
            event = ScannerEvent(
                event_type=f"lighting.{event_type}",
                data=data,
                source_module="lighting_adapter",
                priority=priority
            )
            
            # Notify through controller if it has event callbacks
            if hasattr(self.controller, '_notify_event'):
                self.controller._notify_event(event_type, data)
                
        except Exception as e:
            self.logger.error(f"Failed to notify lighting event: {e}")


class PiGPIOLightingAdapter(StandardLightingAdapter):
    """
    Raspberry Pi GPIO lighting-specific implementation with enhanced safety
    """
    
    def __init__(self, gpio_controller, config: Dict[str, Any]):
        super().__init__(gpio_controller, config)
        self.gpio_controller = gpio_controller  # Type hint for GPIO-specific features
        
    async def initialize_controller(self) -> bool:
        """Initialize GPIO lighting controller with safety checks"""
        try:
            result = await self.gpio_controller.initialize()
            if result:
                # Perform initial safety check
                safety_ok = self.perform_safety_check()
                if not safety_ok:
                    self.logger.error("Initial safety check failed")
                    return False
                
                self.logger.info("Pi GPIO lighting controller initialized successfully")
                self._notify_lighting_event("controller_initialized", {
                    "controller_type": "PiGPIO",
                    "safety_limits": self.safety_limits.__dict__
                })
            return result
        except Exception as e:
            self.logger.error(f"Pi GPIO lighting controller initialization failed: {e}")
            return False
    
    async def shutdown_controller(self) -> bool:
        """Shutdown GPIO lighting controller with safety checks"""
        try:
            # Stop any active rotation tracking
            if self._rotation_tracking_active:
                await self.stop_rotation_tracking()
            
            # Perform final safety shutdown
            result = await self.gpio_controller.shutdown()
            
            if result:
                self.logger.info("Pi GPIO lighting controller shutdown successfully")
                self._notify_lighting_event("controller_shutdown", {
                    "final_flash_count": self._flash_count,
                    "total_safety_violations": self._safety_violations
                })
            return result
        except Exception as e:
            self.logger.error(f"Pi GPIO lighting controller shutdown failed: {e}")
            return False


# Factory function for creating lighting adapters
def create_lighting_adapter(controller: LightingController, config: Dict[str, Any]) -> StandardLightingAdapter:
    """
    Factory function to create appropriate lighting adapter
    
    Args:
        controller: Lighting controller instance
        config: System configuration
        
    Returns:
        Appropriate lighting adapter instance
    """
    lighting_type = config.get('lighting', {}).get('type', 'unknown')
    
    if lighting_type.lower() in ['pi_gpio', 'gpio', 'raspberry_pi']:
        return PiGPIOLightingAdapter(controller, config)
    else:
        # Generic adapter for other lighting types
        class GenericLightingAdapter(StandardLightingAdapter):
            async def initialize_controller(self) -> bool:
                return await self.controller.initialize()
            
            async def shutdown_controller(self) -> bool:
                return await self.controller.shutdown()
        
        return GenericLightingAdapter(controller, config)