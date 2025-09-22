# 4DOF Scanner Control System V2.0

A modular Python system for controlling a 4-degree-of-freedom scanner with dual cameras and LED lighting on Raspberry Pi 5.

## System Overview

This modular system controls:
- **4DOF Motion**: X/Y linear (200mm), Z rotational (360°), C camera tilt (±90°)
- **Dual Cameras**: Synchronized capture using Pi camera ports 0 and 1
- **LED Flash**: Dual-zone PWM-controlled lighting with safety features
- **FluidNC Control**: USB communication with FluidNC motion controller
- **Web Interface**: Real-time monitoring and control
- **Data Management**: Organized storage with comprehensive metadata

## Hardware Requirements

- Raspberry Pi 5 (8GB recommended)
- FluidNC controller (USB connection)
- Dual cameras on Pi camera ports 0 and 1
- LED arrays connected to PWM-capable GPIO pins
- 4DOF scanner hardware (X, Y, Z-rotational, C-tilt)

## Project Structure

```
V2.0/
├── main.py                    # Application entry point
├── requirements.txt           # Python dependencies
├── config/                    # Configuration files
├── core/                      # Core infrastructure
├── motion/                    # Motion control module
├── camera/                    # Camera control module
├── lighting/                  # LED flash control module
├── planning/                  # Path planning module
├── storage/                   # Data management module
├── web/                       # Web interface module
├── communication/             # Data transfer module
├── orchestration/             # Scan coordination module
└── tests/                     # Unit tests
```

## Quick Start

1. Install dependencies: `pip install -r requirements.txt`
2. Configure system: Edit `config/scanner_config.yaml`
3. Run system: `python main.py`
4. Access web interface: `http://localhost:5000`

## Development

This system is designed for modular development where individual components can be improved or replaced without affecting other modules. Each module implements well-defined interfaces for maximum flexibility.

## Safety Features

- GPIO pin safety (never left in high duty cycle)
- Motion limits and collision detection
- Emergency stop functionality
- Graceful error recovery

## License

This project is part of a Stellenbosch University thesis project.