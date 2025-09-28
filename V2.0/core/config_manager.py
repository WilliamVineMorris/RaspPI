"""
Configuration Manager for Scanner System

Handles loading, validation, and management of system configuration
from YAML files. Provides type-safe access to configuration values
with validation and default fallbacks.

Author: Scanner System Development
Created: September 2025
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union, List
from dataclasses import dataclass

from .exceptions import (
    ConfigurationError, 
    ConfigurationNotFoundError, 
    ConfigurationValidationError
)

logger = logging.getLogger(__name__)


@dataclass
class AxisConfig:
    """Configuration for a single motion axis"""
    type: str  # "linear" or "rotational"
    units: str  # "mm" or "degrees"
    min_limit: float
    max_limit: float
    home_position: float
    max_feedrate: float
    continuous: bool = False


@dataclass
class CameraConfig:
    """Configuration for a single camera"""
    port: int
    name: str
    capture_resolution: tuple
    preview_resolution: tuple
    format: str
    quality: int


@dataclass
class LEDZoneConfig:
    """Configuration for a single LED zone"""
    gpio_pin: int
    name: str
    max_intensity: float


class ConfigManager:
    """
    Centralized configuration management for scanner system
    
    Features:
    - YAML configuration file loading
    - Type-safe configuration access
    - Configuration validation
    - Default value handling
    - Environment variable overrides
    - Configuration change detection
    """
    
    def __init__(self, config_file: Union[str, Path]):
        self.config_file = Path(config_file)
        self._config_data: Dict[str, Any] = {}
        self._file_mtime: Optional[float] = None
        self._validated = False
        
        # Load configuration
        self.reload()
    
    def reload(self) -> bool:
        """
        Reload configuration from file
        
        Returns:
            True if reload successful
        """
        try:
            if not self.config_file.exists():
                raise ConfigurationNotFoundError(
                    f"Configuration file not found: {self.config_file}"
                )
            
            # Check if file has changed
            current_mtime = self.config_file.stat().st_mtime
            if self._file_mtime == current_mtime and self._config_data:
                logger.debug("Configuration file unchanged, skipping reload")
                return True
            
            # Load YAML configuration
            with open(self.config_file, 'r', encoding='utf-8') as file:
                self._config_data = yaml.safe_load(file) or {}
            
            self._file_mtime = current_mtime
            self._validated = False
            
            # Apply environment variable overrides
            self._apply_env_overrides()
            
            # Validate configuration
            self.validate()
            
            logger.info(f"Configuration loaded from {self.config_file}")
            return True
            
        except ConfigurationNotFoundError:
            # Re-raise file not found errors without wrapping
            raise
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {self.config_file}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _apply_env_overrides(self):
        """Apply environment variable overrides to configuration"""
        # Allow certain config values to be overridden by environment variables
        env_mappings = {
            'SCANNER_DEBUG': 'system.debug_mode',
            'SCANNER_SIMULATION': 'system.simulation_mode',
            'SCANNER_LOG_LEVEL': 'system.log_level',
            'FLUIDNC_PORT': 'motion.controller.port',
            'WEB_PORT': 'web_interface.port',
            'LED_GPIO_INNER': 'lighting.zones.inner.gpio_pins.0',
            'LED_GPIO_OUTER': 'lighting.zones.outer.gpio_pins.0',
        }
        
        for env_var, config_path in env_mappings.items():
            env_value = os.getenv(env_var)
            if env_value is not None:
                self._set_nested_value(config_path, env_value)
                logger.debug(f"Applied environment override: {config_path} = {env_value}")
    
    def _set_nested_value(self, path: str, value: Any):
        """Set a nested configuration value using dot notation"""
        keys = path.split('.')
        current = self._config_data
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Convert string values to appropriate types
        if isinstance(value, str):
            if value.lower() in ('true', 'false'):
                value = value.lower() == 'true'
            elif value.isdigit():
                value = int(value)
            elif value.replace('.', '').isdigit():
                value = float(value)
        
        current[keys[-1]] = value
    
    def validate(self) -> bool:
        """
        Validate configuration values
        
        Returns:
            True if validation successful
            
        Raises:
            ConfigurationValidationError: If validation fails
        """
        try:
            self._validate_system_config()
            self._validate_motion_config()
            self._validate_camera_config()
            self._validate_lighting_config()
            self._validate_web_config()
            
            self._validated = True
            logger.info("Configuration validation successful")
            return True
            
        except Exception as e:
            raise ConfigurationValidationError(f"Configuration validation failed: {e}")
    
    def _validate_system_config(self):
        """Validate system configuration section"""
        required_fields = ['system.log_level']
        for field in required_fields:
            if not self.get(field):
                raise ConfigurationValidationError(f"Missing required field: {field}")
        
        # Validate log level
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        log_level = self.get('system.log_level')
        if log_level not in valid_log_levels:
            raise ConfigurationValidationError(
                f"Invalid log level '{log_level}'. Must be one of: {valid_log_levels}"
            )
    
    def _validate_motion_config(self):
        """Validate motion control configuration"""
        motion_config = self.get('motion', {})
        
        # Validate controller config
        controller = motion_config.get('controller', {})
        if not controller.get('port'):
            raise ConfigurationValidationError("Motion controller port not specified")
        
        # Validate axes
        axes = motion_config.get('axes', {})
        required_axes = ['x_axis', 'y_axis', 'z_axis', 'c_axis']
        
        for axis_name in required_axes:
            if axis_name not in axes:
                raise ConfigurationValidationError(f"Missing axis configuration: {axis_name}")
            
            axis = axes[axis_name]
            required_axis_fields = ['type', 'units', 'min_limit', 'max_limit', 'max_feedrate']
            for field in required_axis_fields:
                if field not in axis:
                    raise ConfigurationValidationError(
                        f"Missing field '{field}' in {axis_name} configuration"
                    )
            
            # Validate axis limits
            if axis['min_limit'] >= axis['max_limit']:
                raise ConfigurationValidationError(
                    f"Invalid limits for {axis_name}: min_limit must be < max_limit"
                )
    
    def _validate_camera_config(self):
        """Validate camera configuration"""
        cameras = self.get('cameras', {})
        
        # Check for required cameras
        for camera_name in ['camera_1', 'camera_2']:
            if camera_name not in cameras:
                raise ConfigurationValidationError(f"Missing camera configuration: {camera_name}")
            
            camera = cameras[camera_name]
            required_fields = ['port', 'resolution']
            for field in required_fields:
                if field not in camera:
                    raise ConfigurationValidationError(
                        f"Missing field '{field}' in {camera_name} configuration"
                    )
    
    def _validate_lighting_config(self):
        """Validate LED lighting configuration"""
        lighting = self.get('lighting', {})
        zones = lighting.get('zones', {})
        
        # Validate LED zones - check for inner and outer zones as configured in YAML
        expected_zones = ['inner', 'outer']
        for zone_name in expected_zones:
            if zone_name not in zones:
                # Make this a warning instead of error for flexibility
                print(f"Warning: LED zone '{zone_name}' not configured (optional)")
                continue
            
            zone = zones[zone_name]
            if 'gpio_pins' not in zone:
                raise ConfigurationValidationError(
                    f"Missing gpio_pins in {zone_name} zone configuration"
                )
            
            # Validate GPIO pins
            gpio_pins = zone['gpio_pins']
            if not isinstance(gpio_pins, list) or not gpio_pins:
                raise ConfigurationValidationError(
                    f"gpio_pins must be a non-empty list in {zone_name} zone"
                )
            
            for gpio_pin in gpio_pins:
                if not isinstance(gpio_pin, int) or gpio_pin < 0 or gpio_pin > 40:
                    raise ConfigurationValidationError(
                    f"Invalid GPIO pin {gpio_pin} in {zone_name}. Must be 0-40"
                )
            
            # Validate max intensity
            max_intensity = zone.get('max_intensity', 100)
            if max_intensity > 90:
                raise ConfigurationValidationError(
                    f"Safety violation: max_intensity in {zone_name} exceeds 90%"
                )
    
    def _validate_web_config(self):
        """Validate web interface configuration"""
        web = self.get('web_interface', {})
        
        # Validate port
        port = web.get('port', 5000)
        if not isinstance(port, int) or port < 1000 or port > 65535:
            raise ConfigurationValidationError(
                f"Invalid web port {port}. Must be between 1000-65535"
            )
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        
        Args:
            key: Configuration key in dot notation (e.g., 'motion.controller.port')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        try:
            keys = key.split('.')
            value = self._config_data
            
            for k in keys:
                value = value[k]
            
            return value
            
        except (KeyError, TypeError):
            return default
    
    def get_axis_config(self, axis_name: str) -> AxisConfig:
        """Get typed axis configuration"""
        axis_data = self.get(f'motion.axes.{axis_name}')
        if not axis_data:
            raise ConfigurationError(f"Axis configuration not found: {axis_name}")
        
        return AxisConfig(
            type=axis_data['type'],
            units=axis_data['units'],
            min_limit=float(axis_data['min_limit']),
            max_limit=float(axis_data['max_limit']),
            home_position=float(axis_data.get('home_position', 0.0)),
            max_feedrate=float(axis_data['max_feedrate']),
            continuous=bool(axis_data.get('continuous', False))
        )
    
    def get_camera_config(self, camera_name: str) -> CameraConfig:
        """Get typed camera configuration"""
        camera_data = self.get(f'cameras.{camera_name}')
        if not camera_data:
            raise ConfigurationError(f"Camera configuration not found: {camera_name}")
        
        return CameraConfig(
            port=int(camera_data['port']),
            name=camera_data.get('name', camera_name),
            capture_resolution=tuple(camera_data['resolution']['capture']),
            preview_resolution=tuple(camera_data['resolution']['preview']),
            format=camera_data.get('format', 'jpeg'),
            quality=int(camera_data.get('quality', 95))
        )
    
    def get_led_zone_config(self, zone_name: str) -> LEDZoneConfig:
        """Get typed LED zone configuration"""
        zone_data = self.get(f'lighting.zones.{zone_name}')
        if not zone_data:
            raise ConfigurationError(f"LED zone configuration not found: {zone_name}")
        
        # Handle new structure with gpio_pins list
        gpio_pins = zone_data.get('gpio_pins', [])
        gpio_pin = gpio_pins[0] if gpio_pins else 0
        
        return LEDZoneConfig(
            gpio_pin=int(gpio_pin),
            name=zone_data.get('name', zone_name),
            max_intensity=float(zone_data.get('max_brightness', 90.0))
        )
    
    def get_all_axes(self) -> Dict[str, AxisConfig]:
        """Get all axis configurations"""
        axes_data = self.get('motion.axes', {})
        return {
            axis_name: self.get_axis_config(axis_name)
            for axis_name in axes_data.keys()
        }
    
    def get_all_cameras(self) -> Dict[str, CameraConfig]:
        """Get all camera configurations"""
        cameras_data = self.get('cameras', {})
        camera_configs = {}
        
        for camera_name in cameras_data.keys():
            if camera_name not in ['system_type', 'synchronization', 'streaming']:
                camera_configs[camera_name] = self.get_camera_config(camera_name)
        
        return camera_configs
    
    def get_all_led_zones(self) -> Dict[str, LEDZoneConfig]:
        """Get all LED zone configurations"""
        zones_data = self.get('lighting.zones', {})
        return {
            zone_name: self.get_led_zone_config(zone_name)
            for zone_name in zones_data.keys()
        }
    
    def is_simulation_mode(self) -> bool:
        """Check if system is in simulation mode"""
        return self.get('system.simulation_mode', False)
    
    def is_debug_mode(self) -> bool:
        """Check if system is in debug mode"""
        return self.get('system.debug_mode', False)
    
    def get_fluidnc_port(self) -> str:
        """Get FluidNC controller port"""
        return self.get('motion.controller.port', '/dev/ttyUSB0')
    
    def get_web_port(self) -> int:
        """Get web interface port"""
        return self.get('web_interface.port', 5000)
    
    def has_changed(self) -> bool:
        """Check if configuration file has changed since last load"""
        if not self.config_file.exists():
            return False
        
        current_mtime = self.config_file.stat().st_mtime
        return current_mtime != self._file_mtime
    
    def get_summary(self) -> Dict[str, Any]:
        """Get configuration summary for logging/debugging"""
        return {
            'config_file': str(self.config_file),
            'file_exists': self.config_file.exists(),
            'validated': self._validated,
            'simulation_mode': self.is_simulation_mode(),
            'debug_mode': self.is_debug_mode(),
            'log_level': self.get('system.log_level'),
            'motion_controller': self.get('motion.controller.type'),
            'camera_count': len(self.get_all_cameras()),
            'led_zone_count': len(self.get_all_led_zones()),
            'web_port': self.get_web_port()
        }