"""
GPIO LED Controller Implementation

Hardware-specific implementation for GPIO-based LED control on Raspberry Pi.
Supports zone-based illumination with PWM brightness control and safety limits.

SAFETY CRITICAL: Enforces duty cycle limits to prevent hardware damage.

Author: Scanner System Development
Created: September 2025
Platform: Raspberry Pi 5
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Union
from pathlib import Path
import json

try:
    # Try pigpio first for precise PWM control (as specified in scanner config)
    import pigpio
    PIGPIO_AVAILABLE = True
    GPIO_LIBRARY = 'pigpio'
except ImportError:
    PIGPIO_AVAILABLE = False
    GPIO_LIBRARY = None
    pigpio = None

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    if not PIGPIO_AVAILABLE:
        GPIO_LIBRARY = 'rpi_gpio'
    
    # Monkey patch to suppress PWM cleanup errors
    # This prevents the "TypeError: unsupported operand type(s) for &: 'NoneType' and 'int'"
    # that occurs when PWM objects are garbage collected after GPIO.cleanup()
    
    try:
        import lgpio
        
        # Store original functions
        _original_tx_pwm = lgpio.tx_pwm
        _original_gpio_write = lgpio.gpio_write
        
        def safe_tx_pwm(handle, gpio, pwm_frequency, pwm_duty_cycle, pwm_offset=0, pwm_cycles=0):
            """Safe version of tx_pwm that handles None handles gracefully"""
            try:
                if handle is not None:
                    return _original_tx_pwm(handle, gpio, pwm_frequency, pwm_duty_cycle, pwm_offset, pwm_cycles)
                else:
                    # Handle is None (GPIO already cleaned up), silently ignore
                    return 0
            except (TypeError, AttributeError):
                # Silently ignore errors during cleanup
                return 0
        
        def safe_gpio_write(handle, gpio, level):
            """Safe version of gpio_write that handles None handles gracefully"""
            try:
                if handle is not None:
                    return _original_gpio_write(handle, gpio, level)
                else:
                    # Handle is None (GPIO already cleaned up), silently ignore
                    return 0
            except (TypeError, AttributeError):
                # Silently ignore errors during cleanup
                return 0
        
        # Replace with safer versions
        lgpio.tx_pwm = safe_tx_pwm
        lgpio.gpio_write = safe_gpio_write
        
        # Also patch internal _lgpio if available
        try:
            import _lgpio
            _original_lgpio_gpio_write = _lgpio._gpio_write
            
            def safe_lgpio_gpio_write(handle, gpio, level):
                """Safe version of _lgpio._gpio_write that handles None handles gracefully"""
                try:
                    if handle is not None:
                        return _original_lgpio_gpio_write(handle, gpio, level)
                    else:
                        # Handle is None (GPIO already cleaned up), silently ignore
                        return 0
                except (TypeError, AttributeError):
                    # Silently ignore errors during cleanup
                    return 0
            
            _lgpio._gpio_write = safe_lgpio_gpio_write
        except (ImportError, AttributeError):
            # _lgpio not available or doesn't have _gpio_write, skip
            pass
        
    except ImportError:
        # lgpio not available (not on Raspberry Pi), skip patching
        pass
    
except ImportError:
    GPIO_AVAILABLE = False
    # Mock GPIO for development/testing
    class MockGPIO:
        BCM = 11
        OUT = 0
        HIGH = True
        LOW = False
        
        @staticmethod
        def setmode(mode): pass
        @staticmethod 
        def setup(pin, mode): pass
        @staticmethod
        def output(pin, state): pass
        @staticmethod
        def PWM(pin, freq): return MockPWM()
        @staticmethod
        def cleanup(): pass
    
    class MockPWM:
        def __init__(self): 
            self.duty_cycle = 0.0
            self._stopped = False
        def start(self, duty): 
            self.duty_cycle = duty
        def ChangeDutyCycle(self, duty): 
            self.duty_cycle = duty
        def stop(self): 
            self._stopped = True
            self.duty_cycle = 0.0
    
    class MockPigpio:
        def __init__(self):
            self.connected = True
        def set_mode(self, pin, mode): pass
        def write(self, pin, level): pass
        def set_PWM_dutycycle(self, pin, duty): pass
        def stop(self): pass
        
    def pi():
        return MockPigpio()
    
    GPIO = MockGPIO()

from .base import (
    LightingController, LEDZone, LightingSettings, FlashResult, 
    PowerMetrics, LightingStatus, FlashMode, LEDType
)
from core.exceptions import LEDError
from core.events import ScannerEvent

logger = logging.getLogger(__name__)


class GPIOLEDController(LightingController):
    """
    GPIO-based LED controller for Raspberry Pi
    
    Features:
    - Zone-based LED control
    - PWM brightness control
    - Safety duty cycle limits (89% max)
    - Flash synchronization
    - Power monitoring
    - Emergency shutdown
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # GPIO Configuration
        self.pwm_frequency = config.get('pwm_frequency', 1000)  # Hz
        self.gpio_library = config.get('gpio_library', 'pigpio')  # Default to pigpio for precision
        self.gpio_mode = GPIO.BCM if GPIO_AVAILABLE else None
        self.pwm_controllers: Dict[str, List[Any]] = {}  # Zone -> [PWM objects]
        self.zone_states: Dict[str, Dict[str, Any]] = {}
        self._active_pwm_objects = []  # Track all PWM objects for cleanup
        
        # Pigpio connection (if available)
        self.pi = None
        
        # Determine which GPIO library to use
        self._use_pigpio = (self.gpio_library == 'pigpio' and PIGPIO_AVAILABLE)
        
        logger.info(f"GPIO LED Controller: Using {GPIO_LIBRARY} library (pigpio available: {PIGPIO_AVAILABLE})")
        
        # Safety Configuration
        self._max_duty_cycle = 0.89  # 89% safety limit
        self._flash_timeout = 5.0  # Maximum flash duration (seconds)
        self._thermal_protection = True
        self._shutdown_complete = False  # Track shutdown state
        
        # Zone Configuration from config
        # Zones are nested under lighting.zones in the YAML structure
        lighting_config = config.get('lighting', {})
        zones_config = lighting_config.get('zones', {})
        self.zone_configs = self._parse_zone_configs(zones_config)
        
        logger.info(f"Initialized GPIO LED controller with {len(self.zone_configs)} zones")
        if self.zone_configs:
            logger.info(f"Available zones: {list(self.zone_configs.keys())}")
        else:
            logger.warning("No LED zones configured - flash functionality will be disabled")
    
    def _parse_zone_configs(self, zones_config: Dict[str, Any]) -> Dict[str, LEDZone]:
        """Parse zone configurations from config"""
        zones = {}
        
        for zone_id, zone_data in zones_config.items():
            try:
                zone = LEDZone(
                    zone_id=zone_id,
                    gpio_pins=zone_data['gpio_pins'],
                    led_type=LEDType(zone_data.get('led_type', 'standard')),
                    max_current_ma=zone_data.get('max_current_ma', 1000),
                    position=tuple(zone_data.get('position', [0.0, 0.0, 0.0])),
                    direction=tuple(zone_data.get('direction', [0.0, 0.0, -1.0])),
                    beam_angle=zone_data.get('beam_angle', 60.0),
                    max_brightness=zone_data.get('max_brightness', 1.0)
                )
                zones[zone_id] = zone
                logger.debug(f"Configured zone '{zone_id}' with {len(zone.gpio_pins)} pins")
                
            except Exception as e:
                logger.error(f"Failed to parse zone '{zone_id}': {e}")
                raise LEDError(f"Invalid zone configuration '{zone_id}': {e}")
        
        return zones
    
    # Connection Management
    async def initialize(self) -> bool:
        """Initialize GPIO and PWM for all zones"""
        try:
            if not GPIO_AVAILABLE and not PIGPIO_AVAILABLE:
                logger.warning("No GPIO library available - using mock implementation")
            
            self.status = LightingStatus.INITIALIZING
            
            # Initialize GPIO library
            if self._use_pigpio:
                # Initialize pigpio connection
                self.pi = pigpio.pi()
                if not self.pi.connected:
                    logger.error("Failed to connect to pigpio daemon")
                    self._use_pigpio = False
                    # Fall back to RPi.GPIO
                    if GPIO_AVAILABLE:
                        GPIO.setmode(GPIO.BCM)
                        logger.info("Fallback to RPi.GPIO")
                    else:
                        raise LEDError("No GPIO library available")
                else:
                    logger.info("Connected to pigpio daemon for precise PWM control")
            else:
                # Use RPi.GPIO
                if GPIO_AVAILABLE:
                    GPIO.setmode(GPIO.BCM)
                    logger.info("Using RPi.GPIO for PWM control")
                else:
                    raise LEDError("No GPIO library available")
            
            # Initialize each zone
            for zone_id, zone in self.zone_configs.items():
                await self._initialize_zone(zone)
            
            # Verify all zones initialized
            if len(self.pwm_controllers) != len(self.zone_configs):
                raise LEDError("Not all zones initialized successfully")
            
            self.status = LightingStatus.READY
            logger.info("GPIO LED controller initialized successfully")
            
            # Send initialization event
            self._notify_event("lighting_initialized", {
                "zones": list(self.zone_configs.keys()),
                "gpio_available": GPIO_AVAILABLE
            })
            
            return True
            
        except Exception as e:
            self.status = LightingStatus.ERROR
            logger.error(f"Failed to initialize GPIO LED controller: {e}")
            raise LEDError(f"Initialization failed: {e}")
    
    async def _initialize_zone(self, zone: LEDZone) -> None:
        """Initialize GPIO pins and PWM for a zone"""
        try:
            pwm_objects = []
            
            for pin in zone.gpio_pins:
                if self._use_pigpio and self.pi:
                    # Using pigpio for precise PWM control
                    self.pi.set_mode(pin, pigpio.OUTPUT)
                    self.pi.write(pin, 0)  # Start with pin LOW
                    
                    # Pigpio PWM is managed differently - store pin number
                    pwm_objects.append({'type': 'pigpio', 'pin': pin, 'pi': self.pi})
                    
                    logger.debug(f"Initialized pigpio PWM on pin {pin} for zone '{zone.zone_id}'")
                    
                else:
                    # Using RPi.GPIO
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
                    
                    # Create PWM controller
                    pwm = GPIO.PWM(pin, self.pwm_frequency)
                    pwm.start(0)  # Start with 0% duty cycle
                    pwm_objects.append({'type': 'rpi_gpio', 'pwm': pwm})
                    
                    # Track PWM object for proper cleanup
                    self._active_pwm_objects.append(pwm)
                    
                    logger.debug(f"Initialized RPi.GPIO PWM on pin {pin} for zone '{zone.zone_id}'")
            
            self.pwm_controllers[zone.zone_id] = pwm_objects
            self.zone_states[zone.zone_id] = {
                'brightness': 0.0,
                'enabled': True,
                'last_update': time.time(),
                'duty_cycle': 0.0
            }
            
            logger.info(f"Zone '{zone.zone_id}' initialized with {len(pwm_objects)} pins")
            
        except Exception as e:
            logger.error(f"Failed to initialize zone '{zone.zone_id}': {e}")
            raise LEDError(f"Zone initialization failed: {e}")
    
    async def shutdown(self) -> bool:
        """Shutdown all LEDs and cleanup GPIO"""
        if self._shutdown_complete:
            logger.debug("GPIO LED controller already shut down")
            return True
            
        try:
            logger.info("Shutting down GPIO LED controller")
            
            # Turn off all LEDs
            await self.turn_off_all()
            
            # Stop all PWM controllers
            for zone_id, pwm_list in self.pwm_controllers.items():
                for i, pwm_obj in enumerate(pwm_list):
                    try:
                        if pwm_obj['type'] == 'pigpio':
                            # Pigpio cleanup - set pin to 0
                            pi = pwm_obj['pi']
                            pin = pwm_obj['pin']
                            pi.set_PWM_dutycycle(pin, 0)
                            logger.debug(f"Stopped pigpio PWM on pin {pin}")
                        else:
                            # RPi.GPIO cleanup
                            pwm_obj['pwm'].stop()
                        logger.debug(f"Stopped PWM {i} for zone '{zone_id}'")
                    except Exception as e:
                        logger.debug(f"PWM {i} stop error (safe to ignore): {e}")
            
            # Clear all references
            self._active_pwm_objects.clear()
            self.pwm_controllers.clear()
            self.zone_states.clear()
            
            # Cleanup GPIO - now safe due to lgpio patching
            if GPIO_AVAILABLE:
                try:
                    GPIO.cleanup()
                    logger.debug("GPIO cleanup completed")
                except Exception as e:
                    logger.warning(f"GPIO cleanup warning: {e}")
            
            self.status = LightingStatus.DISCONNECTED
            self._shutdown_complete = True
            
            logger.info("GPIO LED controller shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"Shutdown failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if controller is ready"""
        return (self.status == LightingStatus.READY and 
                len(self.pwm_controllers) == len(self.zone_configs))
    
    # Zone Configuration
    async def configure_zone(self, zone: LEDZone) -> bool:
        """Configure or reconfigure a zone"""
        try:
            # Shutdown existing zone if it exists
            if zone.zone_id in self.pwm_controllers:
                await self._shutdown_zone(zone.zone_id)
            
            # Add to configuration and initialize
            self.zone_configs[zone.zone_id] = zone
            await self._initialize_zone(zone)
            
            logger.info(f"Zone '{zone.zone_id}' configured successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure zone '{zone.zone_id}': {e}")
            return False
    
    async def _shutdown_zone(self, zone_id: str) -> None:
        """Shutdown a specific zone"""
        if zone_id in self.pwm_controllers:
            for pwm in self.pwm_controllers[zone_id]:
                pwm.stop()
            del self.pwm_controllers[zone_id]
            del self.zone_states[zone_id]
    
    # Zone Configuration (Abstract methods)
    async def remove_zone(self, zone_id: str) -> bool:
        """Remove LED zone configuration"""
        try:
            if zone_id in self.zone_configs:
                await self._shutdown_zone(zone_id)
                del self.zone_configs[zone_id]
                logger.info(f"Zone '{zone_id}' removed")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove zone '{zone_id}': {e}")
            return False
    
    async def list_zones(self) -> List[str]:
        """List all configured zones"""
        return list(self.zone_configs.keys())
    
    async def get_zone_info(self, zone_id: str) -> Dict[str, Any]:
        """Get LED zone information"""
        if zone_id not in self.zone_configs:
            return {}
        
        zone = self.zone_configs[zone_id]
        state = self.zone_states.get(zone_id, {})
        
        return {
            'zone_id': zone_id,
            'gpio_pins': zone.gpio_pins,
            'led_type': zone.led_type.value,
            'max_current_ma': zone.max_current_ma,
            'position': zone.position,
            'direction': zone.direction,
            'beam_angle': zone.beam_angle,
            'max_brightness': zone.max_brightness,
            'current_brightness': state.get('brightness', 0.0),
            'enabled': state.get('enabled', True),
            'last_update': state.get('last_update', 0.0)
        }
    
    # Basic Lighting Control (Abstract methods)
    async def set_all_brightness(self, brightness: float) -> bool:
        """Set brightness for all LED zones"""
        try:
            success = True
            for zone_id in self.zone_configs:
                result = await self.set_brightness(zone_id, brightness)
                success = success and result
            return success
        except Exception as e:
            logger.error(f"Failed to set all brightness: {e}")
            return False
    
    async def turn_on(self, zone_id: str, brightness: float = 1.0) -> bool:
        """Turn on LED zone"""
        return await self.set_brightness(zone_id, brightness)
    
    async def turn_off(self, zone_id: str) -> bool:
        """Turn off LED zone"""
        return await self.set_brightness(zone_id, 0.0)
    
    # Advanced Lighting Operations (Abstract methods)
    async def flash(self, zone_ids: List[str], settings: LightingSettings) -> FlashResult:
        """Flash LED zones with specified settings"""
        try:
            zone_settings = {zone_id: settings for zone_id in zone_ids}
            results = await self.synchronized_flash(zone_settings)
            
            # Combine results for multiple zones
            success = all(result.success for result in results.values())
            zones_activated = [zone_id for zone_id, result in results.items() if result.success]
            actual_brightness = {}
            total_duration = 0.0
            
            for zone_id, result in results.items():
                actual_brightness.update(result.actual_brightness)
                if result.duration_ms:
                    total_duration = max(total_duration, result.duration_ms)
            
            return FlashResult(
                success=success,
                zones_activated=zones_activated,
                actual_brightness=actual_brightness,
                duration_ms=total_duration if total_duration > 0 else None,
                error_message=None if success else "Some zones failed to flash"
            )
            
        except Exception as e:
            logger.error(f"Flash operation failed: {e}")
            return FlashResult(
                success=False,
                zones_activated=[],
                actual_brightness={},
                duration_ms=0,
                error_message=str(e)
            )
    
    async def fade_to(self, zone_id: str, target_brightness: float, duration_ms: float) -> bool:
        """Fade LED zone to target brightness"""
        try:
            if not self._validate_zone(zone_id):
                return False
            
            current_brightness = self.zone_states[zone_id]['brightness']
            steps = int(duration_ms / 50)  # 50ms steps
            if steps <= 0:
                return await self.set_brightness(zone_id, target_brightness)
            
            brightness_step = (target_brightness - current_brightness) / steps
            
            for i in range(steps):
                new_brightness = current_brightness + (brightness_step * (i + 1))
                await self.set_brightness(zone_id, new_brightness)
                await asyncio.sleep(0.05)  # 50ms delay
            
            return True
            
        except Exception as e:
            logger.error(f"Fade operation failed for zone '{zone_id}': {e}")
            return False
    
    async def strobe(self, zone_id: str, frequency: float, duration_ms: float, 
                    brightness: float = 1.0) -> bool:
        """Strobe LED zone at specified frequency"""
        try:
            if not self._validate_zone(zone_id):
                return False
            
            cycle_time = 1.0 / frequency  # Time per cycle in seconds
            half_cycle = cycle_time / 2.0  # On/off time
            end_time = time.time() + (duration_ms / 1000.0)
            
            while time.time() < end_time:
                await self.set_brightness(zone_id, brightness)
                await asyncio.sleep(half_cycle)
                await self.set_brightness(zone_id, 0.0)
                await asyncio.sleep(half_cycle)
            
            return True
            
        except Exception as e:
            logger.error(f"Strobe operation failed for zone '{zone_id}': {e}")
            return False
    
    # Pattern Control (Abstract methods)
    async def execute_pattern(self, pattern_name: str, repeat: int = 1) -> bool:
        """Execute loaded lighting pattern"""
        # Placeholder implementation
        logger.warning(f"Pattern execution not implemented: {pattern_name}")
        return False
    
    async def stop_pattern(self) -> bool:
        """Stop currently executing pattern"""
        # Placeholder implementation
        return await self.turn_off_all()
    
    # Camera Synchronization (Abstract methods)
    async def trigger_for_capture(self, camera_controller, zone_ids: List[str], 
                                 settings: LightingSettings) -> FlashResult:
        """Trigger LED flash synchronized with camera capture"""
        # For now, just do a regular flash
        # TODO: Implement proper camera synchronization
        return await self.flash(zone_ids, settings)
    
    async def calibrate_camera_sync(self, camera_controller, test_flashes: int = 5) -> float:
        """Calibrate LED flash timing with camera"""
        # Placeholder implementation
        logger.warning("Camera synchronization calibration not implemented")
        return 0.0  # Return 0ms delay for now
    
    # Status and Monitoring (Abstract methods)
    async def get_status(self, zone_id: Optional[str] = None) -> Union[LightingStatus, Dict[str, LightingStatus]]:
        """Get lighting status"""
        if zone_id:
            return self.status if zone_id in self.zone_configs else LightingStatus.DISCONNECTED
        else:
            return {zone_id: self.status for zone_id in self.zone_configs}
    
    async def get_brightness(self, zone_id: str) -> float:
        """Get current brightness of a zone"""
        if zone_id in self.zone_states:
            return self.zone_states[zone_id]['brightness']
        return 0.0
    
    async def get_last_error(self) -> Optional[str]:
        """Get last error message"""
        # Simple implementation - could be enhanced to track actual errors
        return None
    
    # Lighting Control
    async def set_brightness(self, zone_id: str, brightness: float) -> bool:
        """Set brightness for a zone"""
        try:
            if not self._validate_zone(zone_id):
                return False
            
            # Clamp brightness to safe range
            zone = self.zone_configs[zone_id]
            max_brightness = zone.max_brightness
            brightness = max(0.0, min(brightness, max_brightness))
            
            # Calculate duty cycle with safety limit
            duty_cycle = brightness * 100.0
            duty_cycle = min(duty_cycle, self._max_duty_cycle * 100.0)
            
            # Apply to all PWM controllers in zone
            for pwm_obj in self.pwm_controllers[zone_id]:
                if pwm_obj['type'] == 'pigpio':
                    # Use pigpio PWM
                    pi = pwm_obj['pi']
                    pin = pwm_obj['pin']
                    # Convert duty cycle percentage to pigpio duty cycle (0-255)
                    pigpio_duty = int((duty_cycle / 100.0) * 255)
                    pi.set_PWM_dutycycle(pin, pigpio_duty)
                else:
                    # Use RPi.GPIO PWM
                    pwm_obj['pwm'].ChangeDutyCycle(duty_cycle)
            
            # Update state
            self.zone_states[zone_id].update({
                'brightness': brightness,
                'duty_cycle': duty_cycle,
                'last_update': time.time()
            })
            
            logger.debug(f"Zone '{zone_id}' brightness set to {brightness:.2f} ({duty_cycle:.1f}%)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set brightness for zone '{zone_id}': {e}")
            return False
    
    async def flash_zone(self, zone_id: str, settings: LightingSettings) -> FlashResult:
        """Flash a specific zone"""
        try:
            if not self._validate_zone(zone_id):
                return FlashResult(
                    success=False,
                    zones_activated=[],
                    actual_brightness={},
                    duration_ms=0,
                    error_message=f"Invalid zone: {zone_id}"
                )
            
            start_time = time.time()
            
            # Set flash brightness
            await self.set_brightness(zone_id, settings.brightness)
            
            # Flash duration
            if settings.duration_ms:
                flash_duration = min(settings.duration_ms / 1000.0, self._flash_timeout)
                await asyncio.sleep(flash_duration)
                
                # Turn off after flash
                await self.set_brightness(zone_id, 0.0)
            
            end_time = time.time()
            actual_duration = (end_time - start_time) * 1000.0
            
            # Calculate power consumption estimate
            zone = self.zone_configs[zone_id]
            estimated_power = (settings.brightness * zone.max_current_ma * 
                              len(zone.gpio_pins) * 3.3)  # Estimated at 3.3V
            
            return FlashResult(
                success=True,
                zones_activated=[zone_id],
                actual_brightness={zone_id: settings.brightness},
                duration_ms=actual_duration,
                error_message=None
            )
            
        except Exception as e:
            logger.error(f"Flash failed for zone '{zone_id}': {e}")
            return FlashResult(
                success=False,
                zones_activated=[],
                actual_brightness={},
                duration_ms=0,
                error_message=str(e)
            )
    
    async def synchronized_flash(self, zone_settings: Dict[str, LightingSettings]) -> Dict[str, FlashResult]:
        """Flash multiple zones simultaneously"""
        try:
            results = {}
            
            # Validate all zones first
            for zone_id in zone_settings:
                if not self._validate_zone(zone_id):
                    results[zone_id] = FlashResult(
                        success=False,
                        zones_activated=[],
                        actual_brightness={},
                        duration_ms=0,
                        error_message=f"Invalid zone: {zone_id}"
                    )
            
            if len(results) > 0:  # Some zones invalid
                return results
            
            # Execute flashes simultaneously
            flash_tasks = []
            for zone_id, settings in zone_settings.items():
                task = asyncio.create_task(self.flash_zone(zone_id, settings))
                flash_tasks.append((zone_id, task))
            
            # Wait for all flashes to complete
            for zone_id, task in flash_tasks:
                results[zone_id] = await task
            
            return results
            
        except Exception as e:
            logger.error(f"Synchronized flash failed: {e}")
            # Return error for all zones
            return {zone_id: FlashResult(
                success=False,
                zones_activated=[],
                actual_brightness={},
                duration_ms=0,
                error_message=str(e)
            ) for zone_id in zone_settings}
    
    async def turn_off_all(self) -> bool:
        """Turn off all LEDs"""
        try:
            success = True
            for zone_id in self.zone_configs:
                result = await self.set_brightness(zone_id, 0.0)
                success = success and result
            
            logger.info("All LEDs turned off")
            return success
            
        except Exception as e:
            logger.error(f"Failed to turn off all LEDs: {e}")
            return False
    
    # Status and Monitoring
    def get_zone_status(self, zone_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a zone"""
        if zone_id not in self.zone_states:
            return None
        
        zone_state = self.zone_states[zone_id].copy()
        zone_config = self.zone_configs[zone_id]
        
        return {
            'zone_id': zone_id,
            'brightness': zone_state['brightness'],
            'duty_cycle': zone_state['duty_cycle'],
            'enabled': zone_state['enabled'],
            'last_update': zone_state['last_update'],
            'pin_count': len(zone_config.gpio_pins),
            'max_brightness': zone_config.max_brightness,
            'led_type': zone_config.led_type.value
        }
    
    def get_power_metrics(self) -> PowerMetrics:
        """Get current power consumption metrics"""
        total_current = 0.0
        duty_cycles = {}
        
        for zone_id, zone_state in self.zone_states.items():
            zone_config = self.zone_configs[zone_id]
            zone_current = zone_state['brightness'] * zone_config.max_current_ma * len(zone_config.gpio_pins)
            total_current += zone_current
            duty_cycles[zone_id] = zone_state['duty_cycle'] / 100.0  # Convert to fraction
        
        voltage = 3.3  # GPIO voltage
        power_watts = (total_current / 1000.0) * voltage  # Convert mA to A, then calculate watts
        
        return PowerMetrics(
            total_current_ma=total_current,
            voltage_v=voltage,
            power_consumption_w=power_watts,
            duty_cycles=duty_cycles
        )
    
    def _validate_zone(self, zone_id: str) -> bool:
        """Validate zone exists and is ready"""
        if zone_id not in self.zone_configs:
            logger.error(f"Zone '{zone_id}' not configured")
            return False
        
        if zone_id not in self.pwm_controllers:
            logger.error(f"Zone '{zone_id}' not initialized")
            return False
        
        if not self.is_available():
            logger.error("LED controller not ready")
            return False
        
        return True
    
    def _notify_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Send event notification"""
        try:
            for callback in self.event_callbacks:
                callback(ScannerEvent(
                    event_type=f"lighting_{event_type}",
                    timestamp=datetime.fromtimestamp(time.time()),
                    data=data
                ))
        except Exception as e:
            logger.warning(f"Event notification failed: {e}")
    
    # Pattern Support
    async def load_pattern(self, pattern_file: Path) -> bool:
        """Load lighting pattern from file"""
        try:
            with open(pattern_file, 'r') as f:
                pattern_data = json.load(f)
            
            # Apply pattern to zones
            for zone_config in pattern_data.get('zones', []):
                zone_id = zone_config['zone_id']
                if zone_id in self.zone_configs:
                    brightness = zone_config.get('brightness', 0.5)
                    await self.set_brightness(zone_id, brightness)
            
            logger.info(f"Loaded lighting pattern from {pattern_file}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load pattern from {pattern_file}: {e}")
            return False


# Factory function for creating controller
def create_lighting_controller(config: Dict[str, Any]) -> GPIOLEDController:
    """Create GPIO LED controller instance"""
    return GPIOLEDController(config)