"""
Simplified GPIO LED Controller for 2-zone PWM at 300Hz
Uses only RPi.GPIO for hardware PWM - no pigpiod daemon required

Simple, direct hardware PWM implementation for:
- Zone 1 (Inner): GPIO 12 
- Zone 2 (Outer): GPIO 13
- Frequency: 300Hz
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    GPIO = None

from core.exceptions import HardwareError, LightingError
from lighting.base import LightingController, LightingZone

logger = logging.getLogger(__name__)

@dataclass
class PWMChannel:
    """Simple PWM channel for GPIO control"""
    pin: int
    pwm_object: Any  # RPi.GPIO.PWM object
    zone_id: str

class SimpleGPIOLEDController(LightingController):
    """
    Simplified LED controller using only RPi.GPIO hardware PWM
    
    No pigpiod daemon required - direct hardware PWM control
    Perfect for simple 2-zone LED control at 300Hz
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize simple GPIO LED controller"""
        super().__init__(config)
        
        # Validate GPIO availability
        if not GPIO_AVAILABLE:
            raise HardwareError("RPi.GPIO not available - required for LED control")
        
        # Extract configuration
        self.pwm_frequency = config.get('pwm_frequency', 300)  # Default to 300Hz as requested
        
        # Simple PWM tracking
        self.pwm_channels: Dict[str, List[PWMChannel]] = {}
        self._initialized = False
        
        logger.info(f"Simple GPIO LED Controller initialized - {self.pwm_frequency}Hz hardware PWM")
    
    async def initialize(self) -> bool:
        """Initialize GPIO and PWM for configured zones"""
        try:
            if self._initialized:
                return True
            
            # Set GPIO mode
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            
            # Initialize each zone
            for zone in self.zones:
                zone_channels = []
                
                for pin in zone.gpio_pins:
                    logger.info(f"Setting up GPIO {pin} for zone '{zone.zone_id}' at {self.pwm_frequency}Hz")
                    
                    # Setup GPIO pin
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
                    
                    # Create hardware PWM
                    pwm = GPIO.PWM(pin, self.pwm_frequency)
                    pwm.start(0)  # Start at 0% duty cycle
                    
                    channel = PWMChannel(
                        pin=pin,
                        pwm_object=pwm,
                        zone_id=zone.zone_id
                    )
                    zone_channels.append(channel)
                    
                    logger.debug(f"GPIO {pin} initialized for zone '{zone.zone_id}'")
                
                self.pwm_channels[zone.zone_id] = zone_channels
            
            self._initialized = True
            logger.info(f"Simple GPIO LED controller initialized - {len(self.zones)} zones, {self.pwm_frequency}Hz")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize GPIO LED controller: {e}")
            await self.cleanup()
            raise LightingError(f"GPIO LED initialization failed: {e}")
    
    async def set_zone_intensity(self, zone_id: str, intensity: float) -> bool:
        """Set LED intensity for a specific zone"""
        try:
            # Validate zone
            if zone_id not in self.pwm_channels:
                raise LightingError(f"Zone '{zone_id}' not found")
            
            # Validate and clamp intensity
            intensity = max(0.0, min(1.0, intensity))
            
            # Convert to duty cycle percentage (0-100)
            duty_cycle = intensity * 100
            
            # Apply safety limit (never exceed 90%)
            if duty_cycle > 90.0:
                logger.warning(f"Duty cycle {duty_cycle}% exceeds 90% safety limit, clamping")
                duty_cycle = 90.0
            
            # Set PWM duty cycle for all pins in zone
            for channel in self.pwm_channels[zone_id]:
                channel.pwm_object.ChangeDutyCycle(duty_cycle)
                logger.debug(f"GPIO {channel.pin} zone '{zone_id}' set to {duty_cycle:.1f}%")
            
            logger.info(f"Zone '{zone_id}' intensity set to {intensity:.2f} ({duty_cycle:.1f}%)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set zone '{zone_id}' intensity: {e}")
            raise LightingError(f"Zone intensity control failed: {e}")
    
    async def set_all_zones_intensity(self, intensity: float) -> bool:
        """Set intensity for all zones"""
        try:
            success = True
            for zone_id in self.pwm_channels:
                if not await self.set_zone_intensity(zone_id, intensity):
                    success = False
            
            logger.info(f"All zones intensity set to {intensity:.2f}")
            return success
            
        except Exception as e:
            logger.error(f"Failed to set all zones intensity: {e}")
            raise LightingError(f"All zones intensity control failed: {e}")
    
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
            raise LightingError(f"Zone flash failed: {e}")
    
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
            raise LightingError(f"All zones flash failed: {e}")
    
    async def emergency_shutdown(self) -> bool:
        """Emergency LED shutdown - turn off all PWM immediately"""
        try:
            logger.warning("Emergency LED shutdown initiated")
            
            # Turn off all PWM channels immediately
            for zone_channels in self.pwm_channels.values():
                for channel in zone_channels:
                    try:
                        channel.pwm_object.ChangeDutyCycle(0)
                        GPIO.output(channel.pin, GPIO.LOW)
                    except:
                        pass  # Ignore errors during emergency shutdown
            
            logger.info("Emergency LED shutdown completed")
            return True
            
        except Exception as e:
            logger.error(f"Emergency shutdown failed: {e}")
            return False
    
    async def cleanup(self) -> bool:
        """Clean up GPIO resources"""
        try:
            logger.info("Cleaning up GPIO LED controller")
            
            # Stop all PWM
            for zone_channels in self.pwm_channels.values():
                for channel in zone_channels:
                    try:
                        channel.pwm_object.stop()
                        GPIO.output(channel.pin, GPIO.LOW)
                    except:
                        pass  # Ignore cleanup errors
            
            # Clear tracking
            self.pwm_channels.clear()
            
            # Cleanup GPIO
            try:
                GPIO.cleanup()
            except:
                pass  # GPIO.cleanup() can sometimes fail - ignore
            
            self._initialized = False
            logger.info("GPIO LED controller cleanup completed")
            return True
            
        except Exception as e:
            logger.error(f"GPIO cleanup failed: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get controller status"""
        return {
            'initialized': self._initialized,
            'gpio_available': GPIO_AVAILABLE,
            'pwm_frequency': self.pwm_frequency,
            'zones_configured': len(self.pwm_channels),
            'zone_names': list(self.pwm_channels.keys()) if self._initialized else [],
            'library': 'RPi.GPIO'
        }

# Add missing import
import asyncio