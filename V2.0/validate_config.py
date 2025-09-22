#!/usr/bin/env python3
"""
Configuration Validation Utility

Quick utility to validate scanner configuration files and provide helpful
error messages for configuration issues.

Usage:
    python validate_config.py [config_file]
    python validate_config.py --generate-template [output_file]

Author: Scanner System Development
Created: September 2025
"""

import sys
import json
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config_manager import ConfigManager
from core.exceptions import ConfigurationError


def validate_configuration(config_file: str) -> bool:
    """Validate a configuration file"""
    print(f"🔍 Validating configuration: {config_file}")
    
    try:
        config_manager = ConfigManager(config_file)
        print("✅ Configuration validation successful!")
        
        # Print summary
        print("\n📋 Configuration Summary:")
        print(f"   System name: {config_manager.get('system.name', 'Unknown')}")
        print(f"   Simulation mode: {config_manager.get('system.simulation_mode', False)}")
        
        # Motion axes
        axes = config_manager.get('motion.axes', {})
        print(f"   Motion axes: {len(axes)} configured")
        for axis_name, axis_config in axes.items():
            axis_type = axis_config.get('type', 'unknown')
            units = axis_config.get('units', 'unknown')
            print(f"     {axis_name}: {axis_type} ({units})")
        
        # Cameras
        cameras = config_manager.get('cameras', {})
        print(f"   Cameras: {len(cameras)} configured")
        for cam_name, cam_config in cameras.items():
            port = cam_config.get('port', 'unknown')
            resolution = cam_config.get('resolution', [0, 0])
            print(f"     {cam_name}: port {port}, {resolution[0]}x{resolution[1]}")
        
        return True
        
    except ConfigurationError as e:
        print(f"❌ Configuration validation failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def generate_template_config(output_file: str):
    """Generate a template configuration file"""
    print(f"📝 Generating template configuration: {output_file}")
    
    template_config = {
        "system": {
            "name": "4DOF Scanner V2.0",
            "debug_mode": False,
            "simulation_mode": False,
            "log_level": "INFO"
        },
        "platform": {
            "type": "raspberry_pi_5",
            "gpio_library": "pigpio",
            "camera_interface": "libcamera"
        },
        "motion": {
            "controller": {
                "type": "fluidnc",
                "connection": "usb",
                "port": "/dev/ttyUSB0",
                "baudrate": 115200,
                "timeout": 10.0
            },
            "axes": {
                "x_axis": {
                    "type": "linear",
                    "units": "mm",
                    "min_limit": 0.0,
                    "max_limit": 200.0,
                    "max_feedrate": 1000.0,
                    "home_position": 0.0,
                    "home_direction": "negative"
                },
                "y_axis": {
                    "type": "linear",
                    "units": "mm",
                    "min_limit": 0.0,
                    "max_limit": 200.0,
                    "max_feedrate": 1000.0,
                    "home_position": 0.0,
                    "home_direction": "negative"
                },
                "z_axis": {
                    "type": "rotational",
                    "units": "degrees",
                    "min_limit": -999999.0,
                    "max_limit": 999999.0,
                    "max_feedrate": 360.0,
                    "home_position": 0.0,
                    "continuous": True
                },
                "c_axis": {
                    "type": "rotational",
                    "units": "degrees",
                    "min_limit": -90.0,
                    "max_limit": 90.0,
                    "max_feedrate": 180.0,
                    "home_position": 0.0
                }
            }
        },
        "cameras": {
            "camera_1": {
                "port": 0,
                "resolution": [1920, 1080],
                "name": "main",
                "framerate": 30
            },
            "camera_2": {
                "port": 1,
                "resolution": [1920, 1080],
                "name": "secondary",
                "framerate": 30
            }
        },
        "lighting": {
            "system_type": "dual_zone_pwm",
            "led_zones": {
                "zone_1": {
                    "gpio_pin": 18,
                    "name": "Primary LED Array",
                    "max_intensity": 90.0
                },
                "zone_2": {
                    "gpio_pin": 19,
                    "name": "Secondary LED Array",
                    "max_intensity": 90.0
                }
            },
            "flash_profiles": {
                "standard": {
                    "pre_flash_ms": 50,
                    "main_flash_ms": 100,
                    "intensity_percent": 70.0
                },
                "macro": {
                    "pre_flash_ms": 30,
                    "main_flash_ms": 150,
                    "intensity_percent": 85.0
                },
                "low_power": {
                    "pre_flash_ms": 20,
                    "main_flash_ms": 80,
                    "intensity_percent": 50.0
                }
            }
        },
        "storage": {
            "base_directory": "/home/pi/scanner_data",
            "organization": {
                "use_date_folders": True,
                "use_session_folders": True
            },
            "retention": {
                "max_sessions": 100,
                "max_age_days": 30
            }
        },
        "web_interface": {
            "enabled": True,
            "port": 8080,
            "host": "0.0.0.0"
        },
        "scanning": {
            "default_stabilization_delay": 1.0,
            "default_capture_delay": 0.5,
            "path_planning": {
                "default_overlap_percent": 20,
                "default_safety_margin": 5.0
            },
            "session_management": {
                "auto_save_metadata": True,
                "auto_generate_thumbnails": True,
                "max_session_duration_hours": 4
            }
        }
    }
    
    # Determine output format based on file extension
    output_path = Path(output_file)
    
    if output_path.suffix.lower() == '.json':
        with open(output_file, 'w') as f:
            json.dump(template_config, f, indent=2)
        print(f"✅ JSON template configuration saved to: {output_file}")
    else:
        # Default to YAML
        try:
            import yaml
            with open(output_file, 'w') as f:
                yaml.dump(template_config, f, default_flow_style=False, indent=2)
            print(f"✅ YAML template configuration saved to: {output_file}")
        except ImportError:
            # Fallback to JSON if yaml not available
            json_file = output_path.with_suffix('.json')
            with open(json_file, 'w') as f:
                json.dump(template_config, f, indent=2)
            print(f"⚠️  YAML not available, saved JSON template to: {json_file}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Configuration Validation Utility')
    parser.add_argument('config_file', nargs='?', help='Configuration file to validate')
    parser.add_argument('--generate-template', metavar='OUTPUT_FILE', 
                       help='Generate template configuration file')
    
    args = parser.parse_args()
    
    if args.generate_template:
        generate_template_config(args.generate_template)
    elif args.config_file:
        if not Path(args.config_file).exists():
            print(f"❌ Configuration file not found: {args.config_file}")
            sys.exit(1)
        
        success = validate_configuration(args.config_file)
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()