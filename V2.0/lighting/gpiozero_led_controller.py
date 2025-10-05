"""
GPIO Zero LED Controller Implementation

Simple and clean LED control using gpiozero library with hardware PWM.
Uses LED.value for duty cycle control and frequency property for 300Hz PWM.

Key Features:
- Uses gpiozero.LED class with PWM support
- LED.value property for duty cycle (0.0 to 1.0)
- LED.frequency property for 300Hz PWM frequency
- Automatic hardware PWM when frequency is set
- No daemon dependencies (pigpiod not required)

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
    from gpiozero import PWMLED, Device
    from gpiozero.pins.pigpio import PiGPIOFactory
    from gpiozero.pins.rpigpio import RPiGPIOFactory
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    PWMLED = None
    Device = None

from core.exceptions import (
    HardwareError, 
    LEDError, 
    LEDSafetyError,
    ConfigurationError
)
from lighting.base import LightingController, LightingZone
from core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

class GPIOZeroLEDController(LightingController):
    """
    GPIO Zero LED Controller for simple PWM control
    
    Uses gpiozero.LED with:
    - LED.value for duty cycle (0.0 to 1.0)
    - LED.frequency for PWM frequency (300Hz)
    - Hardware PWM when supported
    - No pigpiod daemon required for RPi.GPIO pin factory
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize GPIO Zero LED controller"""
        super().__init__(config)
        
        # Validate gpiozero availability
        if not GPIOZERO_AVAILABLE:
            raise HardwareError("gpiozero library not available - required for LED control")
        
        # Extract configuration
        self.pwm_frequency = config.get('pwm_frequency', 300)  # Default 300Hz as requested
        self.use_pigpio_factory = config.get('use_pigpio_factory', False)  # Default to RPi.GPIO factory
        
        # Configure pin factory (RPi.GPIO is simpler and doesn't need pigpiod)
        if self.use_pigpio_factory:
            try:
                Device.pin_factory = PiGPIOFactory()
                logger.info("Using PiGPIO factory (requires pigpiod)")
            except Exception as e:
                logger.warning(f"PiGPIO factory failed, falling back to RPi.GPIO: {e}")
                Device.pin_factory = RPiGPIOFactory()
        else:
            Device.pin_factory = RPiGPIOFactory()
            logger.info("Using RPi.GPIO factory (no pigpiod required)")
        
        # LED objects by zone
        self.led_objects: Dict[str, List[PWMLED]] = {}
        self._initialized = False
        
        logger.info(f"GPIO Zero LED Controller initialized - {self.pwm_frequency}Hz PWM")
    
    async def initialize(self) -> bool:
        """Initialize LED objects for all configured zones"""
        try:
            if self._initialized:
                return True
            
            logger.info("Initializing GPIO Zero LED controller...")
            
            # Initialize LED objects for each zone
            for zone in self.zones:
                zone_leds = []
                
                for pin in zone.gpio_pins:
                    logger.info(f"Setting up PWMLED on GPIO {pin} for zone '{zone.zone_id}' at {self.pwm_frequency}Hz")
                    
                    # Create PWMLED object with frequency parameter
                    led = PWMLED(pin, frequency=self.pwm_frequency)
                    
                    # Start at 0% duty cycle (LED off)
                    led.value = 0.0
                    
                    zone_leds.append(led)
                    
                    logger.debug(f"GPIO {pin} PWMLED initialized for zone '{zone.zone_id}' (frequency: {self.pwm_frequency}Hz)")
                
                self.led_objects[zone.zone_id] = zone_leds
            
            self._initialized = True
            logger.info(f"GPIO Zero LED controller initialized - {len(self.zones)} zones at {self.pwm_frequency}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GPIO Zero LED controller: {e}")
            await self.cleanup()
            raise LEDError(f"LED initialization failed: {e}")
    
    async def set_zone_intensity(self, zone_id: str, intensity: float) -> bool:
        """Set LED intensity for a specific zone using LED.value"""
        try:
            # Validate zone
            if zone_id not in self.led_objects:
                raise LEDError(f"Zone '{zone_id}' not found")
            
            # Validate and clamp intensity (0.0 to 1.0)
            intensity = max(0.0, min(1.0, intensity))
            
            # Apply safety limit (never exceed 0.9 = 90%)
            if intensity > 0.9:
                logger.warning(f"Intensity {intensity:.2f} exceeds 0.9 safety limit, clamping")
                intensity = 0.9
            
            # Set LED value (duty cycle) for all LEDs in zone
            for led in self.led_objects[zone_id]:
                led.value = intensity  # gpiozero LED.value sets PWM duty cycle
                logger.debug(f"GPIO {led.pin.number} zone '{zone_id}' set to {intensity:.2f} ({intensity*100:.1f}%)")
            
            logger.info(f"Zone '{zone_id}' intensity set to {intensity:.2f} ({intensity*100:.1f}%)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set zone '{zone_id}' intensity: {e}")
            raise LEDError(f"Zone intensity control failed: {e}")
    
    async def set_all_zones_intensity(self, intensity: float) -> bool:
        """Set intensity for all zones"""
        try:
            success = True
            for zone_id in self.led_objects:
                if not await self.set_zone_intensity(zone_id, intensity):
                    success = False
            
            logger.info(f"All zones intensity set to {intensity:.2f}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to set all zones intensity: {e}")
            raise LEDError(f"All zones intensity control failed: {e}")
    
    async def flash_zone(self, zone_id: str, intensity: float = 1.0, 
                        duration_ms: int = 50) -> bool:
        """Flash a specific zone"""
        try:
            # Set intensity
            await self.set_zone_intensity(zone_id, intensity)
            
            # Wait for flash duration
            await asyncio.sleep(duration_ms / 1000.0)
            
            # Turn off
            await self.set_zone_intensity(zone_id, 0.0)
            
            logger.debug(f"Zone '{zone_id}' flashed at {intensity:.2f} for {duration_ms}ms")
            return True
            
        except Exception as e:
            logger.error(f"Failed to flash zone '{zone_id}': {e}")
            raise LEDError(f"Zone flash failed: {e}")
    
    async def flash_all_zones(self, intensity: float = 1.0, 
                             duration_ms: int = 50) -> bool:
        """Flash all zones simultaneously"""
        try:
            # Set all zones
            await self.set_all_zones_intensity(intensity)
            
            # Wait for flash duration
            await asyncio.sleep(duration_ms / 1000.0)
            
            # Turn off all
            await self.set_all_zones_intensity(0.0)
            
            logger.debug(f"All zones flashed at {intensity:.2f} for {duration_ms}ms")
            return True
            
        except Exception as e:
            logger.error(f"Failed to flash all zones: {e}")
            raise LEDError(f"All zones flash failed: {e}")
    
    async def emergency_shutdown(self) -> bool:
        """Emergency LED shutdown - turn off all LEDs immediately"""
        try:
            logger.warning("Emergency LED shutdown initiated")
            
            # Turn off all LEDs immediately
            for zone_leds in self.led_objects.values():
                for led in zone_leds:
                    try:
                        led.value = 0.0  # Turn off LED
                    except:
                        pass  # Ignore errors during emergency shutdown
            
            logger.info("Emergency LED shutdown completed")
            return True
            
        except Exception as e:
            logger.error(f"Emergency shutdown failed: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up LED resources"""
        try:
            logger.info("Cleaning up GPIO Zero LED controller")
            
            # Turn off and close all LEDs
            for zone_leds in self.led_objects.values():
                for led in zone_leds:
                    try:
                        led.value = 0.0  # Turn off
                        led.close()     # Release GPIO
                    except:
                        pass  # Ignore cleanup errors
            
            # Clear tracking
            self.led_objects.clear()
            
            self._initialized = False
            logger.info("GPIO Zero LED controller cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"LED cleanup failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        zone_status = {}
        
        # Get status for each zone
        for zone_id, zone_leds in self.led_objects.items():
            led_status = []
            for led in zone_leds:
                try:
                    led_status.append({
                        'pin': led.pin.number,
                        'value': led.value,
                        'frequency': self.pwm_frequency,  # PWMLED doesn't expose frequency property
                        'active': led.is_active
                    })
                except:
                    led_status.append({'pin': 'unknown', 'status': 'error'})
            
            zone_status[zone_id] = led_status
        
        return {
            'initialized': self._initialized,
            'gpiozero_available': GPIOZERO_AVAILABLE,
            'pwm_frequency': self.pwm_frequency,
            'pin_factory': str(Device.pin_factory.__class__.__name__) if Device and Device.pin_factory else None,
            'zones_configured': len(self.led_objects),
            'zone_names': list(self.led_objects.keys()) if self._initialized else [],
            'zone_status': zone_status,
            'library': 'gpiozero'
        }
    
    async def shutdown(self) -> bool:
        """Shutdown the LED controller"""
        return await self.cleanup()
    
    async def is_available(self) -> bool:
        """Check if LED controller is available"""
        return GPIOZERO_AVAILABLE and self._initialized