# Comprehensive Codebase Analysis: 4DOF Scanner Control System

## Executive Summary

This is a **modular Python-based web-controlled 3D scanning system** designed for Raspberry Pi 5 hardware. The system orchestrates a 4-degree-of-freedom (4DOF) motion platform with dual cameras and LED lighting to perform automated photogrammetry scanning.

**Key Statistics:**
- **Primary Entry Point:** `run_web_interface.py`
- **Core Architecture:** Modular event-driven design with adapter pattern
- **Languages:** Python 3.10+
- **Main Framework:** Flask (web interface), AsyncIO (concurrency)
- **Target Platform:** Raspberry Pi 5 with custom hardware
- **Total Modules:** 8 core subsystems with 40+ Python files
- **Lines of Code:** ~15,000+ lines (production code)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    WEB INTERFACE (Flask)                        │
│              run_web_interface.py → web_interface.py            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   SCAN ORCHESTRATOR                             │
│              (Central Coordination Engine)                      │
│              scanning/scan_orchestrator.py                      │
└──────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
       │          │           │          │          │
       ▼          ▼           ▼          ▼          ▼
   ┌──────┐  ┌──────┐  ┌──────────┐ ┌──────┐  ┌──────┐
   │MOTION│  │CAMERA│  │ LIGHTING │ │STORAGE│ │ CORE │
   │      │  │      │  │          │ │       │ │      │
   └──────┘  └──────┘  └──────────┘ └───────┘ └──────┘
       │          │           │          │          │
       ▼          ▼           ▼          ▼          ▼
   FluidNC    PiCamera2   GPIO PWM   Session    Events
   (G-code)   (libcamera) (Hardware) Manager    Config
```

### 1.2 Module Hierarchy

The system follows a **layered adapter pattern** architecture:

```
Layer 1: WEB INTERFACE
  ├── run_web_interface.py (launcher)
  ├── web/start_web_interface.py (initialization)
  └── web/web_interface.py (Flask routes & WebSocket)

Layer 2: ORCHESTRATION
  ├── scanning/scan_orchestrator.py (coordination)
  ├── scanning/scan_patterns.py (path generation)
  ├── scanning/scan_state.py (state management)
  └── scanning/scan_profiles.py (scan templates)

Layer 3: HARDWARE ADAPTERS
  ├── motion/adapter.py → fluidnc_controller.py
  ├── camera/adapter.py → pi_camera_controller.py
  └── lighting/adapter.py → gpio_led_controller.py

Layer 4: CORE INFRASTRUCTURE
  ├── core/events.py (event bus)
  ├── core/config_manager.py (YAML config)
  ├── core/types.py (data structures)
  ├── core/exceptions.py (error hierarchy)
  ├── core/coordinate_transform.py (coordinate systems)
  └── storage/session_manager.py (data persistence)
```

---

## 2. Module Communication Architecture

### 2.1 Communication Patterns

The system uses **three primary communication mechanisms**:

#### A. Direct Module Access
Modules can directly import and call each other for synchronous operations:
```python
# Example from scan_orchestrator.py
from motion.adapter import StandardMotionAdapter
from camera.adapter import StandardCameraAdapter

# Direct method calls
await self.motion_adapter.move_to_position(position)
result = await self.camera_adapter.capture_at_position(position)
```

#### B. Event-Driven Communication (Loose Coupling)
Event bus for asynchronous notifications and inter-module events:

```python
# Core event system: core/events.py
EventBus.publish(
    event_type="motion.position_reached",
    data={"position": position.to_dict()},
    source_module="motion",
    priority=EventPriority.NORMAL
)

# Subscribers listen for events
EventBus.subscribe("motion.position_reached", callback_function)
```

**Key Event Types:**
- **System Events:** `system.startup`, `system.shutdown`, `system.ready`
- **Motion Events:** `motion.completed`, `position.reached`, `motion.home_complete`
- **Camera Events:** `photo.captured`, `camera.sync_lost`
- **LED Events:** `flash.triggered`, `led.safety_violation`
- **Scan Events:** `scan.started`, `scan.position_complete`, `scan.completed`
- **Emergency Events:** `emergency.stop`, `safety.violation`

#### C. Configuration-Based Coordination
Centralized configuration enables module discovery:

```python
# core/config_manager.py loads scanner_config.yaml
config_manager = ConfigManager('config/scanner_config.yaml')

# Modules self-configure from YAML
motion_config = config_manager.get_motion_config()
camera_config = config_manager.get_camera_config()
```

### 2.2 Data Flow Diagram

```
USER COMMAND (Web Browser)
    │
    ▼
┌─────────────────────────┐
│ Flask Route Handler     │ ← web/web_interface.py
│ /api/motion/jog         │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ Command Validator       │ ← Validates safety limits
│ CommandValidator class  │
└─────────┬───────────────┘
          │
          ▼
┌─────────────────────────┐
│ Scan Orchestrator       │ ← scanning/scan_orchestrator.py
│ orchestrator.motion_*() │
└─────────┬───────────────┘
          │
          ├─────────────────────────────────┐
          ▼                                 ▼
┌─────────────────────┐          ┌─────────────────────┐
│ Motion Adapter      │          │ Event Bus           │
│ StandardMotion      │          │ Publish Event       │
│ Adapter             │          └─────────────────────┘
└─────────┬───────────┘
          │
          ▼
┌─────────────────────────┐
│ FluidNC Controller      │ ← motion/fluidnc_controller.py
│ Send G-code via Serial  │
└─────────┬───────────────┘
          │
          ▼
    [HARDWARE]
    FluidNC Board → Stepper Motors
```

---

## 3. Core Subsystem Analysis

### 3.1 Motion Control System

**Location:** `motion/`

**Purpose:** Controls 4DOF motion platform via FluidNC G-code controller

**Architecture:**
```
base.py (Abstract Interface)
    ↓
adapter.py (Standardization Layer)
    ↓
fluidnc_controller.py (Hardware Implementation)
    ↓
fluidnc_protocol.py (G-code Communication)
    ↓
servo_tilt.py (Camera Tilt Calculations)
```

**Key Components:**

1. **Abstract Base (`motion/base.py`):**
   - Defines `MotionController` interface
   - Position validation with `Position4D` dataclass
   - Axis type definitions: `LINEAR`, `ROTATIONAL`
   - Safety limits enforcement

2. **Adapter Layer (`motion/adapter.py`):**
   - `StandardMotionAdapter` provides uniform interface
   - Axis normalization (Z-axis wraps at ±180°)
   - Continuous rotation support
   - Position caching and validation

3. **FluidNC Controller (`motion/fluidnc_controller.py`):**
   - Serial communication over USB (115200 baud)
   - G-code command generation
   - Real-time position tracking via status reports (`?` queries)
   - Homing sequence management
   - Emergency stop capability

4. **Servo Tilt (`motion/servo_tilt.py`):**
   - Calculates optimal camera tilt angles
   - Focus point tracking (Y-axis depth)
   - Automatic tilt based on camera-to-object geometry

**Communication Flow:**
```
Web Command → Orchestrator → Adapter → FluidNC Controller
                                           ↓
                                    Serial Port (/dev/ttyUSB0)
                                           ↓
                                    FluidNC Firmware
                                           ↓
                                    Stepper Motors
```

**4DOF Axis Configuration:**
- **X-Axis:** Linear (0-200mm) - Horizontal camera position
- **Y-Axis:** Linear (0-200mm) - Vertical camera position
- **Z-Axis:** Rotational (±180°, continuous) - Turntable rotation
- **C-Axis:** Rotational (±90°, limited) - Camera servo tilt

### 3.2 Camera Control System

**Location:** `camera/`

**Purpose:** Dual Raspberry Pi camera synchronization and image capture

**Architecture:**
```
base.py (Abstract Interface)
    ↓
adapter.py (Standardization + Motion Sync)
    ↓
pi_camera_controller.py (PiCamera2 Implementation)
```

**Key Components:**

1. **Abstract Base (`camera/base.py`):**
   - `CameraController` interface
   - `CameraSettings` dataclass (exposure, ISO, resolution)
   - `CaptureResult` and `SyncCaptureResult` data structures
   - Camera status enumeration

2. **Adapter Layer (`camera/adapter.py`):**
   - `StandardCameraAdapter` with motion awareness
   - Rotation timing modes: `STOP_AND_CAPTURE`, `CONTINUOUS`, `PREDICTIVE`
   - Position tolerance validation (default 0.1°)
   - LED flash coordination
   - Dual camera synchronization (<10ms tolerance)

3. **Pi Camera Controller (`camera/pi_camera_controller.py`):**
   - PiCamera2 (libcamera) interface for Pi 5
   - Dual camera management (ports 0 and 1)
   - Hardware-accelerated JPEG encoding
   - EXIF metadata embedding
   - ArduCam autofocus support
   - Preview frame generation for web streaming

**Camera Workflow:**
```
1. Motion to position → Wait for stabilization (100ms)
2. Verify position accuracy
3. Trigger LED flash (if enabled)
4. Capture from both cameras simultaneously
5. Embed position metadata in EXIF
6. Save images with session organization
7. Publish capture event
```

**Resolution Support:**
- **High Resolution:** 4608×2592 (ArduCam 64MP actual)
- **Preview:** 640×480 (for web streaming)
- **Format:** JPEG with configurable quality

### 3.3 LED Lighting System

**Location:** `lighting/`

**Purpose:** Multi-zone LED flash synchronization with **critical GPIO safety**

**Architecture:**
```
base.py (Abstract Interface + Safety)
    ↓
adapter.py (Standardization + Safety Validation)
    ↓
gpiozero_led_controller.py (GPIO Implementation)
```

**Key Components:**

1. **Abstract Base (`lighting/base.py`):**
   - `LightingController` interface
   - **CRITICAL:** `validate_duty_cycle()` ensures ≤90% to prevent GPIO damage
   - `LEDZone` configuration
   - `FlashResult` with timing metadata

2. **Adapter Layer (`lighting/adapter.py`):**
   - `StandardLightingAdapter` with safety enforcement
   - Rotation-aware lighting patterns
   - Emergency shutdown capabilities
   - Thermal monitoring support
   - Safety violation tracking

3. **GPIO Controller (`lighting/gpiozero_led_controller.py`):**
   - Hardware PWM via `rpi-hardware-pwm` library
   - Direct GPIO control (pins 18, 19)
   - Flash duration control (2ms typical)
   - Coordinated multi-zone flashing

**Safety Architecture:**
```
Command → validate_duty_cycle() → [PASS/FAIL]
              │                       │
              │ FAIL                  │ PASS
              ▼                       ▼
    emergency_shutdown()      Execute flash command
              │                       │
              ▼                       ▼
    Log safety violation      Monitor completion
```

**Critical Safety Rules:**
1. **NEVER exceed 90% duty cycle** (prevents GPIO overheat)
2. Emergency shutdown on any safety violation
3. Thermal monitoring (60°C limit)
4. Flash duration limits (max 100ms)

### 3.4 Storage System

**Location:** `storage/`

**Purpose:** Session-based scan data organization with backup

**Architecture:**
```
base.py (Abstract Interface)
    ↓
session_manager.py (Session Organization)
```

**Key Features:**

1. **Session Organization:**
   - Hierarchical directory structure
   - Unique session IDs with timestamps
   - Metadata JSON files per session
   - Multi-location backup support

2. **Directory Structure:**
```
/home/pi/scanner_data/
├── sessions/
│   ├── session_20250105_143022/
│   │   ├── images/
│   │   │   ├── camera_1/
│   │   │   │   ├── img_001.jpg (with EXIF position data)
│   │   │   │   └── img_002.jpg
│   │   │   └── camera_2/
│   │   ├── metadata/
│   │   │   ├── session_info.json
│   │   │   ├── camera_positions.csv (multi-format export)
│   │   │   └── scan_parameters.json
│   │   └── exports/
│   │       └── session_export.zip
│   └── session_20250105_150145/
├── backups/
├── exports/
└── metadata/
    └── sessions_index.json
```

3. **Data Integrity:**
   - SHA-256 checksums for image validation
   - Atomic write operations
   - Backup synchronization
   - Export capabilities (ZIP, directory copy)

4. **Metadata Management:**
   - JSON session manifests
   - CSV camera position exports (multiple coordinate formats)
   - EXIF embedding in images (GPS coordinates for photogrammetry)
   - Scan parameter recording

### 3.5 Core Infrastructure

**Location:** `core/`

#### A. Event System (`core/events.py`)

**Purpose:** Centralized event bus for module communication

**Features:**
- Thread-safe event publishing
- Priority-based handling (`LOW`, `NORMAL`, `HIGH`, `CRITICAL`)
- Event history tracking (1000 events)
- Async and sync callback support
- Statistics tracking

**Usage Pattern:**
```python
# Publishing
await event_bus.publish(
    event_type=EventConstants.MOTION_COMPLETED,
    data={"position": position.to_dict()},
    source_module="motion",
    priority=EventPriority.NORMAL
)

# Subscribing
event_bus.subscribe(
    event_type=EventConstants.MOTION_COMPLETED,
    callback=handle_motion_complete,
    subscriber_name="camera_controller"
)
```

#### B. Configuration Manager (`core/config_manager.py`)

**Purpose:** YAML-based configuration with validation

**Features:**
- Type-safe configuration access
- Environment variable overrides
- Configuration hot-reloading
- Dataclass wrappers (`AxisConfig`, `CameraConfig`, `LEDZoneConfig`)
- Default value handling

**Configuration File:** `config/scanner_config.yaml`

```yaml
system:
  name: "3D Scanner"
  simulation_mode: false
  log_level: "INFO"

motion:
  controller:
    type: "fluidnc"
    port: "/dev/ttyUSB0"
    baudrate: 115200
  axes:
    x_axis:
      type: "linear"
      min_limit: 0.0
      max_limit: 200.0
    z_axis:
      type: "rotational"
      continuous: true

cameras:
  camera_1:
    port: 0
    resolution: [4608, 2592]
    
lighting:
  led_zones:
    zone_1:
      gpio_pin: 18
      max_intensity: 80  # 80% for safety
```

#### C. Type System (`core/types.py`)

**Core Data Structures:**

1. **Position4D:**
   - 4-axis position tracking
   - Built-in validation
   - Distance calculation
   - JSON serialization

2. **CameraSettings:**
   - Exposure, ISO, white balance
   - Focus distance
   - Resolution configuration

3. **SystemStatus:**
   - Overall system health
   - Module readiness flags
   - Emergency stop state

#### D. Exception Hierarchy (`core/exceptions.py`)

**Hierarchical Error Handling:**

```
ScannerSystemError (base)
├── ConfigurationError
│   ├── ConfigurationNotFoundError
│   └── ConfigurationValidationError
├── HardwareError
│   ├── HardwareConnectionError
│   ├── HardwareTimeoutError
│   └── HardwareNotReadyError
├── MotionControlError
│   ├── MotionLimitError
│   ├── MotionSafetyError
│   └── FluidNCError
├── CameraError
│   ├── CameraConnectionError
│   └── CameraSyncError
└── LEDError
    └── LEDSafetyError
```

**Benefits:**
- Specific error handling per subsystem
- Error code tracking
- Module attribution
- Proper exception chaining

#### E. Coordinate Systems (`core/coordinate_transform.py`)

**Three Coordinate Systems:**

1. **CAMERA-RELATIVE (User-Facing):**
   - Cylindrical coordinates: (radius, height, rotation, tilt)
   - Intuitive for scanning setup

2. **FLUIDNC (Machine Coordinates):**
   - Linear + rotational: (x, y, z, c)
   - Direct hardware control

3. **CARTESIAN (World Coordinates):**
   - 3D space: (x, y, z, c)
   - For photogrammetry export

**Transformer Class:**
```python
transformer = CoordinateTransformer(config_manager)

# Camera → FluidNC conversion
fluidnc_pos = transformer.camera_to_fluidnc(
    CameraRelativePosition(radius=150, height=100, rotation=45, tilt=10)
)

# Export for photogrammetry software
cartesian_pos = transformer.camera_to_cartesian(camera_pos)
```

### 3.6 Scanning System

**Location:** `scanning/`

#### A. Scan Orchestrator (`scanning/scan_orchestrator.py`)

**Role:** Central coordination engine for complete scan workflows

**Responsibilities:**
1. Initialize all hardware subsystems
2. Validate scan parameters
3. Execute scan patterns
4. Coordinate motion → camera → LED sequence
5. Handle pause/resume/emergency stop
6. Generate scan metadata
7. Manage scan state transitions

**Scan Execution Flow:**
```
1. Initialize system
   ├── Connect to FluidNC
   ├── Initialize cameras
   └── Setup LED zones

2. Load scan pattern
   └── Generate position sequence

3. For each position:
   ├── Move to position (with servo tilt calculation)
   ├── Wait for motion completion
   ├── Trigger LED flash
   ├── Capture dual camera images
   ├── Save to session storage
   └── Update progress

4. Complete scan
   ├── Generate metadata
   ├── Export camera positions (CSV/JSON)
   └── Create session manifest
```

#### B. Scan Patterns (`scanning/scan_patterns.py`)

**Pattern Types:**

1. **GridScanPattern:**
   - Rectangular grid coverage
   - Configurable X, Y, Z steps
   - Camera angle variation

2. **CylindricalScanPattern:** (Primary for 3D scanning)
   - Circular rotation (Z-axis)
   - Height variation (Y-axis)
   - Radial distance (X-axis)
   - Servo tilt optimization
   - **Best for cylindrical objects on turntable**

**Pattern Configuration:**
```python
pattern = CylindricalScanPattern(
    pattern_id="cylinder_scan_001",
    parameters=PatternParameters(
        min_x=100.0,    # Minimum radius
        max_x=150.0,    # Maximum radius
        min_y=50.0,     # Minimum height
        max_y=150.0,    # Maximum height
        min_z=0.0,      # Start rotation
        max_z=360.0,    # End rotation (full circle)
        overlap_percentage=30.0  # Image overlap
    )
)

points = pattern.generate_points()
# Returns List[ScanPoint] with Position4D for each capture
```

#### C. Scan State (`scanning/scan_state.py`)

**State Machine:**
```
ScanStatus:
├── IDLE
├── INITIALIZING
├── RUNNING
├── PAUSED
├── COMPLETED
└── ERROR

ScanPhase:
├── INITIALIZATION
├── HOMING
├── SCANNING
├── PROCESSING
└── COMPLETED
```

**State Tracking:**
- Current position index
- Estimated completion time
- Error history
- Pause/resume timestamps

#### D. Scan Profiles (`scanning/scan_profiles.py`)

**Predefined Scan Templates:**
- Low quality (fast preview)
- Medium quality (balanced)
- High quality (maximum detail)
- Custom configurations

### 3.7 Web Interface

**Location:** `web/`

#### A. Entry Points

1. **`run_web_interface.py`:** Production launcher
2. **`web/start_web_interface.py`:** Initialization logic
3. **`web/web_interface.py`:** Flask application (5169 lines)

#### B. Flask Routes Architecture

**API Endpoints:**

**System Status:**
- `GET /api/status` - Overall system health
- `GET /api/hardware_status` - Hardware connection status

**Motion Control:**
- `POST /api/motion/jog` - Manual axis movement
- `POST /api/motion/home` - Homing sequence
- `POST /api/motion/goto` - Absolute positioning
- `POST /api/motion/emergency_stop` - Emergency halt
- `GET /api/motion/position` - Current position

**Camera Operations:**
- `GET /api/camera/status` - Camera readiness
- `GET /api/camera/preview/<camera_id>` - MJPEG stream
- `POST /api/camera/capture` - Manual capture
- `POST /api/camera/settings` - Update camera settings

**Lighting Control:**
- `GET /api/lighting/status` - LED zone status
- `POST /api/lighting/flash` - Trigger flash
- `POST /api/lighting/set_intensity` - Adjust brightness

**Scanning:**
- `POST /api/scan/start` - Start automated scan
- `POST /api/scan/pause` - Pause scan
- `POST /api/scan/resume` - Resume scan
- `POST /api/scan/stop` - Stop and save
- `GET /api/scan/progress` - Real-time progress

**Storage & Export:**
- `GET /api/storage/sessions` - List all sessions
- `GET /api/storage/session/<id>` - Session details
- `POST /api/storage/export` - Export session as ZIP
- `GET /api/storage/csv/<format>` - Export positions CSV

#### C. WebSocket Communication

**Real-Time Updates:**
```javascript
// Client connects to WebSocket
socket = new WebSocket('ws://raspberrypi:5000/ws');

// Server pushes updates
{
  "type": "status_update",
  "data": {
    "motion": {"x": 100.5, "y": 50.2, "z": 45.0, "c": 10.0},
    "scan_progress": 45.2,
    "cameras_active": true
  }
}
```

**Event Types:**
- `status_update` - System status (1Hz)
- `scan_progress` - Scan completion percentage
- `position_update` - Real-time position (10Hz)
- `error_notification` - Error alerts
- `log_message` - System logs

#### D. Frontend Structure

**HTML Templates:**
```
web/templates/
├── index.html (Dashboard)
├── manual_control.html (Jog interface)
├── scanning.html (Scan management)
├── camera.html (Live preview)
└── storage.html (Data management)
```

**JavaScript:**
- WebSocket client management
- Real-time status updates
- MJPEG stream handling
- Form validation
- Error handling and notifications

#### E. Development Modes

**Mock Mode:**
```bash
python run_web_interface.py --mode mock --debug
```
- Simulated hardware
- No GPIO/serial requirements
- Safe for PC development

**Hardware Mode:**
```bash
python run_web_interface.py --mode hardware
```
- Real FluidNC connection
- Actual camera capture
- GPIO LED control

**Production Mode:**
```bash
python run_web_interface.py --mode production --port 80
```
- Optimized for deployment
- No debug overhead
- Automatic hardware initialization

---

## 4. Key Dependencies & Packages

### 4.1 Core Python Packages

**From `requirements.txt`:**

**Hardware Communication:**
- `pyserial>=3.5` - Serial communication with FluidNC
- `pyserial-asyncio>=0.6` - Async serial operations

**Camera & Image Processing:**
- `picamera2>=0.3.0` - Raspberry Pi camera interface (libcamera)
- `opencv-python>=4.5.0` - Image processing and preview
- `pillow>=8.0.0` - Image format handling

**Web Interface:**
- `flask>=2.0.0` - Web framework
- `flask-cors>=3.0.0` - Cross-origin resource sharing

**GPIO Control (Pi5-Specific):**
- `gpiozero>=1.6.0` - GPIO abstraction layer
- `pigpio>=1.78` - Precise PWM timing
- `rpi-hardware-pwm>=0.2.0` - Direct hardware PWM access

**Data Handling:**
- `numpy>=1.21.0` - Numerical operations
- `pyyaml>=6.0` - Configuration file parsing
- `requests>=2.25.0` - HTTP requests
- `psutil>=5.8.0` - System monitoring

**Async Support:**
- `asyncio` (built-in) - Async/await patterns
- `asyncio-mqtt>=0.13.0` - MQTT support (future)

**Testing:**
- `pytest>=7.0.0` - Test framework
- `pytest-asyncio>=0.21.0` - Async test support

**Optional:**
- `matplotlib>=3.5.0` - Visualization
- `scipy>=1.7.0` - Path planning algorithms

### 4.2 System-Level Dependencies

**Raspberry Pi 5 Requirements:**
```bash
# Camera interface
sudo apt install python3-picamera2 python3-opencv

# GPIO control
sudo apt install python3-gpiozero

# PWM daemon
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

### 4.3 Hardware PWM Configuration

**Device Tree Overlay:**
```bash
# /boot/config.txt
dtoverlay=pwm-2chan,pin=18,func=2,pin2=19,func2=2
```

This enables hardware PWM on GPIO pins 18 and 19 for LED control.

---

## 5. Data Structures & Type System

### 5.1 Core Data Types

**Position4D (4-axis position):**
```python
@dataclass
class Position4D:
    x: float  # mm (linear)
    y: float  # mm (linear)
    z: float  # degrees (rotational)
    c: float  # degrees (tilt)
    
    def distance_to(self, other: Position4D) -> float
    def to_dict(self) -> Dict[str, float]
    def copy(self) -> Position4D
```

**CameraSettings:**
```python
@dataclass
class CameraSettings:
    exposure_time: Optional[float]  # seconds
    iso: Optional[int]              # 100-6400
    white_balance: Optional[str]
    focus_distance: Optional[float] # mm
    resolution: tuple[int, int]     # (width, height)
    capture_format: str             # "JPEG"
```

**ScanPoint (position in scan pattern):**
```python
@dataclass
class ScanPoint:
    position: Position4D
    camera_settings: Optional[CameraSettings]
    lighting_settings: Optional[Dict]
    capture_count: int = 1
    dwell_time: float = 0.5  # stabilization time
```

### 5.2 Configuration Data Structures

**AxisConfig:**
```python
@dataclass
class AxisConfig:
    type: str           # "linear" | "rotational"
    units: str          # "mm" | "degrees"
    min_limit: float
    max_limit: float
    home_position: float
    max_feedrate: float
    continuous: bool = False
```

**StorageSession:**
```python
@dataclass
class ScanSession:
    session_id: str
    name: str
    start_time: datetime
    end_time: Optional[datetime]
    scan_pattern: str
    image_count: int
    metadata: Dict[str, Any]
```

### 5.3 Result Data Structures

**CaptureResult:**
```python
@dataclass
class CaptureResult:
    success: bool
    image_path: Optional[Path]
    timestamp: datetime
    camera_id: str
    settings: CameraSettings
    error_message: Optional[str]
```

**SyncCaptureResult (dual camera):**
```python
@dataclass
class SyncCaptureResult:
    success: bool
    camera1_result: CaptureResult
    camera2_result: Optional[CaptureResult]
    sync_timestamp: datetime
    sync_tolerance_ms: float
    position: Position4D
```

---

## 6. Testing & Development Workflow

### 6.1 Test Structure

**Test Files:** `tests/` and root-level `test_*.py`

**Key Test Categories:**
1. **Core Infrastructure Tests:**
   - `test_core_infrastructure.py` (interactive validation)
   - `run_automated_tests.py` (CI-friendly)

2. **Module-Specific Tests:**
   - `test_motion_system.py`
   - `test_camera_hardware.py`
   - `test_led_system.py`
   - `test_storage_integration.py`

3. **Integration Tests:**
   - `test_complete_system_integration.py`
   - `test_web_interface_comprehensive.py`
   - `test_scanning_system.py`

4. **Hardware Tests (Pi-only):**
   - `test_pi_hardware.py`
   - `test_fluidnc_protocol.py`
   - `test_hardware_pwm.py`

### 6.2 Development Workflow

**PC Development:**
```bash
# Mock mode - no hardware required
python run_web_interface.py --mode mock --debug --log-level DEBUG

# Develops entire system without Pi hardware
# Uses mock motion, cameras, and LED controllers
```

**Pi Deployment:**
```bash
# 1. Clone repository
git clone <repo> && cd RaspPI/V2.0

# 2. Install dependencies
pip install -r requirements.txt
sudo apt install python3-picamera2 python3-opencv python3-gpiozero

# 3. Run hardware tests
python test_pi_hardware.py

# 4. Start web interface
python run_web_interface.py --mode hardware --port 5000
```

**Testing Protocol:**
1. **NEVER run Pi hardware code on PC**
2. **Always test on actual Pi after code changes**
3. **Use mock mode for logic development**
4. **Wait for user confirmation before proceeding**

### 6.3 Debugging Tools

**Diagnostic Scripts:**
- `check_hardware.py` - Verify all hardware connections
- `debug_fluidnc_connection.py` - Serial port diagnostics
- `debug_camera.py` - Camera interface testing
- `debug_led_hardware.py` - GPIO PWM validation
- `diagnose_coordinate_offset.py` - Coordinate system validation

**Logging:**
```python
# Hierarchical logging throughout codebase
logger = logging.getLogger(__name__)

# Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
logger.info("System initialized")
logger.error("Hardware connection failed")
```

---

## 7. Deployment & Production

### 7.1 Production Startup

**Systemd Service:**
```ini
[Unit]
Description=3D Scanner Web Interface
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/scanner/RaspPI/V2.0
ExecStart=/usr/bin/python3 run_web_interface.py --mode production --port 80
Restart=always

[Install]
WantedBy=multi-user.target
```

**Start Commands:**
```bash
# Production mode
sudo python run_web_interface.py --mode production --port 80

# Or with systemd
sudo systemctl enable scanner.service
sudo systemctl start scanner.service
```

### 7.2 Configuration Management

**Environment Variables:**
```bash
export SCANNER_SIMULATION=false
export SCANNER_LOG_LEVEL=INFO
export FLUIDNC_PORT=/dev/ttyUSB0
export WEB_PORT=5000
```

**Config File:** `config/scanner_config.yaml`

### 7.3 Monitoring & Logging

**Log Files:**
- `web_interface.log` - Web server logs
- `motion_controller.log` - Motion system logs
- `camera_controller.log` - Camera operations
- `scan_sessions.log` - Scan execution logs

**System Monitoring:**
```python
# Real-time stats via web interface
GET /api/status
{
  "uptime": 3600,
  "cpu_percent": 25.3,
  "memory_percent": 42.1,
  "disk_usage": 15.2,
  "active_scan": "scan_001",
  "hardware": {
    "motion": "connected",
    "cameras": "ready",
    "leds": "ready"
  }
}
```

---

## 8. Safety & Error Handling

### 8.1 Safety Systems

**Motion Safety:**
- Position limit validation before movement
- Emergency stop capability (hardware + software)
- Continuous rotation wrapping (Z-axis)
- Soft limit enforcement
- Collision detection (via FluidNC alarms)

**LED Safety (CRITICAL):**
- **90% duty cycle hard limit** (prevents GPIO damage)
- Duty cycle validation on every command
- Emergency shutdown on safety violations
- Thermal monitoring (60°C limit)
- Automatic shutdown on errors

**Camera Safety:**
- Position verification before capture
- Sync tolerance checking (<10ms)
- Motion stabilization delays
- Exposure time limits

### 8.2 Error Recovery

**Exception Handling Strategy:**
```python
try:
    # Hardware operation
    await motion_controller.move_to_position(target)
except MotionSafetyError as e:
    # Safety violation - emergency stop
    await emergency_shutdown()
    logger.critical(f"Safety violation: {e}")
except MotionTimeoutError as e:
    # Timeout - retry or abort
    logger.error(f"Motion timeout: {e}")
    await retry_with_backoff()
except MotionControlError as e:
    # General error - log and notify
    logger.error(f"Motion error: {e}")
    notify_user(e)
```

**Recovery Actions:**
- Automatic retry with exponential backoff
- Emergency stop for safety violations
- User notification via web interface
- State preservation for resume capability
- Detailed error logging with stack traces

### 8.3 Graceful Degradation

**Fallback Mechanisms:**
1. **Camera Failure:** Continue with single camera
2. **LED Failure:** Capture with ambient light
3. **Motion Timeout:** Retry with slower feedrate
4. **Storage Full:** Switch to backup location

---

## 9. Advanced Features

### 9.1 Coordinate System Transformations

**Three-Way Transformation:**

```python
# Camera-relative (user-friendly)
camera_pos = CameraRelativePosition(
    radius=150.0,    # mm from turntable center
    height=100.0,    # mm above turntable
    rotation=45.0,   # degrees
    tilt=10.0        # degrees
)

# Convert to FluidNC (machine coordinates)
fluidnc_pos = transformer.camera_to_fluidnc(camera_pos)
# Result: Position4D(x=X_machine, y=Y_machine, z=45.0, c=10.0)

# Convert to Cartesian (for photogrammetry export)
cart_pos = transformer.camera_to_cartesian(camera_pos)
# Result: CartesianPosition(x=X_world, y=Y_world, z=Z_world, c=10.0)
```

**Use Cases:**
- User inputs camera radius/height (intuitive)
- System controls FluidNC in machine coordinates
- Exports Cartesian for Meshroom/RealityScan

### 9.2 Servo Tilt Optimization

**Automatic Camera Angle Calculation:**

```python
from motion.servo_tilt import calculate_servo_tilt_angle

# Given scanner position and focus point
tilt_angle = calculate_servo_tilt_angle(
    camera_position=(100.0, 150.0),  # (x, y) in mm
    turntable_position=(120.0, 50.0),
    user_y_focus=50.0  # mm - depth of focus
)

# Result: optimal tilt angle to keep object in focus
```

**Benefits:**
- Automatic focus tracking
- Optimized coverage for cylindrical scans
- User-specified focus depth

### 9.3 Multi-Format CSV Export

**Position Export for Photogrammetry:**

```python
from scanning.multi_format_csv import MultiFormatCSVHandler

handler = MultiFormatCSVHandler()

# Export in multiple coordinate formats
handler.export_positions(
    session_path=Path("/home/pi/scanner_data/sessions/scan_001"),
    output_formats=[
        CoordinateFormat.CAMERA_RELATIVE,  # User-friendly
        CoordinateFormat.FLUIDNC,          # Machine coordinates
        CoordinateFormat.CARTESIAN,        # Photogrammetry software
        CoordinateFormat.GPS_EXIF          # GPS coordinates for EXIF
    ]
)
```

**Output Files:**
- `camera_positions_camera.csv`
- `camera_positions_fluidnc.csv`
- `camera_positions_cartesian.csv`
- `camera_positions_gps.csv`

**GPS EXIF Integration:**
Embeds camera positions as GPS coordinates in EXIF data for Meshroom/RealityScan compatibility.

### 9.4 Background Status Monitoring

**Continuous Hardware Polling:**

```python
# FluidNC status queries every 100ms
async def _background_monitor(self):
    while self.monitor_running:
        status = await self._query_status()
        self.current_position = parse_position(status)
        await asyncio.sleep(0.1)
```

**Benefits:**
- Real-time position tracking
- WebSocket position updates (10Hz)
- Automatic connection recovery
- Hardware fault detection

---

## 10. Performance Optimization

### 10.1 Async/Await Architecture

**Non-Blocking Operations:**

```python
# Concurrent hardware operations
async def capture_and_move():
    # Start movement and capture simultaneously
    move_task = asyncio.create_task(motion.move_to(next_pos))
    capture_task = asyncio.create_task(camera.capture())
    
    # Wait for both
    await asyncio.gather(move_task, capture_task)
```

### 10.2 Caching & State Management

**Position Caching:**
- Last known position cached to avoid redundant queries
- Cache invalidation on movement commands
- 100ms cache timeout

**Configuration Caching:**
- YAML config loaded once
- File modification detection
- Hot-reload capability

### 10.3 Image Processing Pipeline

**Dual Camera Optimization:**
- Parallel capture from both cameras
- Hardware JPEG encoding (GPU-accelerated)
- Async file I/O
- Streaming preview generation

---

## 11. Future Development Considerations

### 11.1 Potential Enhancements

**Hardware:**
- Additional LED zones (4+ zones)
- Laser distance sensor integration
- Accelerometer for vibration detection
- Temperature sensors for thermal monitoring

**Software:**
- Adaptive scanning (AI-based path planning)
- Real-time 3D reconstruction preview
- Cloud storage synchronization
- Mobile app remote control
- MQTT integration for IoT

**Algorithms:**
- Spiral scan patterns
- AI-driven focus optimization
- Automatic exposure bracketing
- HDR capture support

### 11.2 Known Limitations

**Current System:**
- Single FluidNC controller dependency
- Limited to 2 cameras (hardware)
- Manual calibration required
- No real-time reconstruction

**Workarounds:**
- Mock mode for development
- Graceful hardware fallback
- Comprehensive error handling

---

## 12. Documentation & Resources

### 12.1 Inline Documentation

**Every Module Has:**
- Comprehensive docstrings
- Type hints throughout
- Usage examples in docstrings
- Safety warnings for critical operations

**Example:**
```python
async def move_to_position(
    self, 
    position: Position4D, 
    feedrate: Optional[float] = None
) -> bool:
    """
    Move to absolute 4D position with safety validation
    
    Args:
        position: Target position in machine coordinates
        feedrate: Optional feedrate override (mm/min)
        
    Returns:
        True if movement successful
        
    Raises:
        MotionSafetyError: If position violates safety limits
        MotionTimeoutError: If movement exceeds timeout
        
    Safety:
        - Validates position against configured limits
        - Checks for emergency stop state
        - Normalizes Z-axis rotation to ±180°
    """
```

### 12.2 Project Documentation Files

**Markdown Docs (50+ files):**
- `README.md` - Project overview
- `COMPLETE_DEVELOPMENT_SUMMARY.md` - Development history
- `PI_SETUP_GUIDE.md` - Raspberry Pi setup instructions
- `HARDWARE_INTEGRATION_SUMMARY.md` - Hardware details
- `COORDINATE_SYSTEM_INTEGRATION.md` - Coordinate math
- `CAMERA_FOCUS_ZONES_SUMMARY.md` - Focus system
- `LED_FLICKERING_COMPLETE_SOLUTION.md` - LED troubleshooting
- `PHOTOGRAMMETRY_CAMERA_POSITIONS.md` - Export guide

### 12.3 Example Usage Scripts

**In `V2.0/` directory:**
- `example_scan.py` - Basic scan workflow
- `example_cylindrical_scan.py` - Cylindrical pattern demo
- `production_scan_test.py` - Production workflow validation

---

## 13. Summary & Key Takeaways

### 13.1 System Strengths

✅ **Modular Architecture:**
- Clean separation of concerns
- Adapter pattern enables hardware swapping
- Event-driven communication minimizes coupling

✅ **Safety-First Design:**
- Multiple safety validation layers
- Critical GPIO protection (90% duty cycle limit)
- Emergency stop at every level
- Comprehensive error handling

✅ **Developer-Friendly:**
- Mock mode for PC development
- Extensive type hints
- Clear documentation
- Comprehensive testing

✅ **Production-Ready:**
- Web-based remote control
- Session-based data organization
- Multi-format export capabilities
- Automatic backup and recovery

### 13.2 Core Communication Patterns

1. **Direct Module Access:**
   - Orchestrator → Adapters → Hardware Controllers
   - Synchronous for critical operations

2. **Event Bus:**
   - Async notifications between modules
   - Loose coupling for non-critical events
   - Statistics and monitoring

3. **Configuration:**
   - Centralized YAML configuration
   - Environment variable overrides
   - Type-safe access via dataclasses

### 13.3 Critical Dependencies

**Hardware:**
- FluidNC (G-code motion controller)
- Raspberry Pi 5 (libcamera, GPIO)
- Dual Pi Cameras (ArduCam 64MP)
- Hardware PWM (GPIO 18, 19)

**Software:**
- Python 3.10+ (async/await)
- Flask (web interface)
- PiCamera2 (camera control)
- PySerial (FluidNC communication)
- OpenCV (image processing)
- GPIOZero/pigpio (LED control)

### 13.4 Development Best Practices

🔒 **Safety Rules:**
1. NEVER exceed 90% duty cycle on GPIO
2. Always validate positions before movement
3. Use emergency stop for safety violations
4. Test on real Pi hardware before deployment

🔧 **Testing Protocol:**
1. Develop in mock mode on PC
2. Deploy to Pi for hardware testing
3. User confirms results before continuing
4. Never assume mock behavior matches hardware

📊 **Reporting Metrics:**
- 8 core subsystems
- 40+ production Python files
- ~15,000 lines of code
- 3 coordinate systems
- 4 degrees of freedom
- 2 synchronized cameras
- 50+ API endpoints
- Real-time WebSocket updates

---

## 14. Quick Reference

### 14.1 File Locations

| Component | Path |
|-----------|------|
| **Entry Point** | `run_web_interface.py` |
| **Web App** | `web/web_interface.py` |
| **Orchestrator** | `scanning/scan_orchestrator.py` |
| **Motion Control** | `motion/fluidnc_controller.py` |
| **Camera Control** | `camera/pi_camera_controller.py` |
| **LED Control** | `lighting/gpiozero_led_controller.py` |
| **Storage** | `storage/session_manager.py` |
| **Configuration** | `config/scanner_config.yaml` |
| **Events** | `core/events.py` |
| **Types** | `core/types.py` |

### 14.2 Command Reference

```bash
# Start web interface (mock mode)
python run_web_interface.py --mode mock --debug

# Start with real hardware
python run_web_interface.py --mode hardware --port 5000

# Production deployment
sudo python run_web_interface.py --mode production --port 80

# Run tests
python test_core_infrastructure.py
python run_automated_tests.py

# Check hardware
python check_hardware.py
python diagnose_fluidnc_connection.py
```

### 14.3 API Quick Reference

```bash
# System status
GET /api/status

# Jog motion
POST /api/motion/jog {"axis": "x", "distance": 10.0}

# Start scan
POST /api/scan/start {"pattern": "cylindrical", ...}

# Get camera preview
GET /api/camera/preview/camera_1

# Trigger LED flash
POST /api/lighting/flash {"zones": ["zone_1"], ...}

# Export session
POST /api/storage/export {"session_id": "scan_001"}
```

---

## Conclusion

This 4DOF Scanner Control System represents a **sophisticated, production-ready photogrammetry automation platform** with:

- **Robust architecture** using adapter patterns and event-driven design
- **Safety-critical systems** for hardware protection
- **Comprehensive testing** infrastructure
- **Real-time web control** with WebSocket updates
- **Professional data management** with multi-format export
- **Modular design** enabling easy hardware upgrades

The codebase is well-structured for both **development** (mock mode) and **production deployment** (hardware mode), with extensive documentation and error handling throughout.

For further development or refinement, the modular architecture allows targeted improvements to individual subsystems without affecting the broader system integration.

---

**Document Version:** 1.0  
**Generated:** January 2025  
**Codebase Version:** V2.0  
**Project:** 4DOF Scanner Control System (RaspPI)
