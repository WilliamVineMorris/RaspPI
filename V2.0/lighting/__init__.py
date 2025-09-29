"""
LED Lighting Control Module

Controls LED flash arrays including:
- PWM-based flash control
- Dual-zone lighting management
- Flash synchronization with cameras
- Safety features and monitoring
"""

from typing import Dict, Any

from .base import (
    LightingController, LEDZone, LightingSettings, FlashResult, 
    PowerMetrics, LightingStatus, FlashMode, LEDType
)
from .gpio_led_controller import GPIOLEDController

# Import gpiozero controller if available
try:
    from .gpiozero_led_controller import GPIOZeroLEDController
    GPIOZERO_CONTROLLER_AVAILABLE = True
except ImportError:
    GPIOZeroLEDController = None
    GPIOZERO_CONTROLLER_AVAILABLE = False

def create_lighting_controller(config: Dict[str, Any]) -> LightingController:
    """Create appropriate LED controller based on config"""
    controller_type = config.get('controller_type', 'gpio')
    
    if controller_type == 'gpiozero':
        if not GPIOZERO_CONTROLLER_AVAILABLE:
            raise ImportError("gpiozero controller requested but not available")
        return GPIOZeroLEDController(config)
    elif controller_type == 'gpio':
        return GPIOLEDController(config)
    else:
        raise ValueError(f"Unknown controller type: {controller_type}")

__all__ = [
    'LightingController',
    'GPIOLEDController',
    'GPIOZeroLEDController', 
    'LEDZone',
    'LightingSettings',
    'FlashResult',
    'PowerMetrics',
    'LightingStatus',
    'FlashMode',
    'LEDType',
    'create_lighting_controller'
]