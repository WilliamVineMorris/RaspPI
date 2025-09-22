"""
Example configuration for GPIO LED lighting system
"""

# GPIO LED Configuration Example
LIGHTING_CONFIG = {
    "controller_type": "gpio",
    "pwm_frequency": 1000,  # Hz
    
    # LED Zone Configurations
    "zones": {
        "top_ring": {
            "gpio_pins": [18, 19],  # GPIO pins for this zone
            "led_type": "cool_white",
            "max_current_ma": 800,
            "position": [0.0, 0.0, 100.0],  # X, Y, Z position in mm
            "direction": [0.0, 0.0, -1.0],  # Pointing down
            "beam_angle": 45.0,
            "max_brightness": 1.0
        },
        
        "side_ring": {
            "gpio_pins": [20, 21], 
            "led_type": "warm_white",
            "max_current_ma": 600,
            "position": [0.0, 0.0, 50.0],
            "direction": [0.0, 0.0, -1.0],
            "beam_angle": 60.0,
            "max_brightness": 0.8
        },
        
        "flash_zone": {
            "gpio_pins": [22, 23, 24],
            "led_type": "cool_white", 
            "max_current_ma": 1200,
            "position": [0.0, 0.0, 150.0],
            "direction": [0.0, 0.0, -1.0],
            "beam_angle": 30.0,
            "max_brightness": 1.0
        }
    },
    
    # Safety Configuration
    "safety": {
        "max_duty_cycle": 0.89,  # 89% maximum to prevent overheating
        "thermal_protection": True,
        "flash_timeout_seconds": 5.0
    },
    
    # Default Lighting Settings
    "defaults": {
        "brightness": 0.5,
        "fade_time_ms": 100,
        "flash_duration_ms": 50
    }
}

# Scanning Integration Settings
SCAN_LIGHTING_PATTERNS = {
    "standard_scan": {
        "brightness": 0.8,
        "duration_ms": 100,
        "zones": ["top_ring", "side_ring"]
    },
    
    "high_detail": {
        "brightness": 1.0,
        "duration_ms": 150,
        "zones": ["flash_zone"]
    },
    
    "low_reflectance": {
        "brightness": 0.6,
        "duration_ms": 200,
        "zones": ["top_ring", "side_ring", "flash_zone"]
    }
}