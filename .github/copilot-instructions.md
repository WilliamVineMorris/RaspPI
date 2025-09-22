# GitHub Copilot Instructions - 4DOF Scanner Control System (RaspPI)

## Project Overview
This is a modular Python system for controlling a 4-degree-of-freedom scanner with dual cameras and LED lighting on Raspberry Pi 5. The V2.0 codebase emphasizes **modular design** with abstract interfaces enabling testable, hardware-independent development.

**Working Directory**: Focus on `RaspPI/V2.0/` - this contains the complete modular rewrite.

## Core Architecture Patterns

### Module Interface System
- All modules implement abstract base classes from `*/base.py` files for easy replacement/upgrade
- Modules can be imported directly but must remain modular and interchangeable
- Event-driven communication via `core/events.py` EventBus for loose coupling
- Configuration centralized in `config/scanner_config.yaml` with `core/config_manager.py`
- Hierarchical exceptions in `core/exceptions.py` with module-specific error types

**Critical Pattern**: Always extend abstract classes, maintain module interchangeability:
```python
# Example from motion/base.py
class MotionController(ABC):
    @abstractmethod
    async def move_to_position(self, position: Position4D) -> bool:
```

### 4DOF Position System
- Use `Position4D(x, y, z, c)` dataclass consistently across all modules
- X/Y: Linear motion (0-200mm), Z: Continuous rotation (degrees), C: Camera tilt (±90°)
- Safety validation built into all interfaces (see `motion/base.py` validation methods)

### Safety-Critical LED Control
- **HARDWARE SAFETY**: GPIO pins must NEVER exceed 90% duty cycle (`lighting/base.py`)
- Always validate with `validate_duty_cycle()` before any GPIO operations
- Use `emergency_shutdown()` for safety violations - this prevents hardware damage

## Development Journey Understanding

### Current Implementation Status
Based on development progression:
- ✅ **Core Infrastructure**: Complete (`core/` modules fully implemented)
- ✅ **Abstract Interfaces**: Complete (all `*/base.py` files defined)
- 🔄 **Concrete Implementations**: In progress (FluidNC motion controller next)
- ⏳ **Hardware Integration**: Pending (Pi cameras, GPIO LEDs, USB FluidNC)

### Critical Configuration Fix Applied
The `core/config_manager.py` was fixed to properly handle `ConfigurationNotFoundError` without wrapping it in generic `ConfigurationError`. This maintains proper exception hierarchy for testing.

## Development Workflows

### Testing Strategy (Proven Working)
- **Core Validation**: `python test_core_infrastructure.py` (interactive, creates temp files)
- **Automation Ready**: `python run_automated_tests.py` (non-interactive, CI-friendly)
- **Test Philosophy**: Modules tested in isolation before integration

### Configuration Management
- **Hardware Config**: `config/scanner_config.yaml` (axes limits, hardware specs)
- **Environment Overrides**: Use `SCANNER_SIMULATION=true` for development without hardware
- **Type Safety**: Configuration accessed via `AxisConfig` dataclasses, not raw dictionaries

### PC→GitHub→Pi Development Workflow
This codebase is designed for development on PC, version control via GitHub, then deployment to Pi:
- Simulation mode enables full development without hardware
- Abstract interfaces allow different implementations (real hardware vs simulators)
- Modular design enables easy component replacement/upgrade
- Event-driven architecture provides loose coupling while maintaining direct module access

## Hardware Integration Points (RaspPI Specific)

### Critical Hardware Connections
- **FluidNC**: USB serial (`/dev/ttyUSB0`, 115200 baud) for motion control
- **Pi Cameras**: Dual cameras on ports 0 and 1 with <10ms sync tolerance
- **GPIO LEDs**: PWM control via pigpio library for precise timing
- **Safety Systems**: Emergency stops, motion limits, GPIO duty cycle protection

### Pi5-Specific Considerations
- Uses `libcamera` interface (not legacy camera stack)
- Requires `pigpio` for precise PWM timing control
- GPIO safety limits prevent hardware damage from stuck high signals

## Module-Specific Conventions

### Motion Control (`motion/`)
- FluidNC G-code communication for 4DOF positioning
- Async operations with safety checks and position interpolation
- `MotionStatus` enum for state management
- **Modularity**: Implement `MotionController` abstract base class for easy controller swapping

### Camera Control (`camera/`)
- Dual camera synchronization with timing validation
- `CaptureResult` and `SyncCaptureResult` dataclasses for operation results
- Flash synchronization with LED controller via events
- **Modularity**: Implement `CameraController` base class to support different camera types

### Event System (`core/events.py`)
- Use `EventPriority.CRITICAL` for safety-related events
- Thread-safe event bus with statistics tracking
- Event constants in `EventConstants` class
- **Purpose**: Enables loose coupling while allowing direct module imports

### Storage (`storage/`)
- Session-based organization with comprehensive metadata
- Multi-location backup with integrity validation
- Export capabilities (ZIP, directory structures)
- **Modularity**: Implement `StorageManager` base class for different storage backends

## Key Files for Immediate Productivity
- `V2.0/main.py`: Application entry point and module orchestration
- `V2.0/core/events.py`: Central communication system (understand this first)
- `V2.0/motion/base.py`: 4DOF positioning interface with safety validation
- `V2.0/config/scanner_config.yaml`: Complete hardware configuration
- `V2.0/test_core_infrastructure.py`: Validates core functionality works

## Development Environment Setup
- **Platform**: Raspberry Pi 5 (Python 3.10+)
- **Dependencies**: `pip install -r requirements.txt` in `V2.0/` directory
- **Testing**: Run core tests before implementing new modules
- **Simulation**: Set `system.simulation_mode: true` for hardware-independent development

## Safety Requirements (Hardware Protection)
- **GPIO Protection**: Never exceed 90% duty cycle on LED control pins
- **Motion Safety**: Validate all positions against hardware limits before movement
- **Emergency Systems**: Implement emergency stop in all hardware controllers
- **Exception Handling**: Use module-specific error types for proper error recovery