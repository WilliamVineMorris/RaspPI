# Command Timing Analysis Implementation

## Overview
Created comprehensive timing analysis system to investigate command execution delays in the FluidNC scanner control system.

## Files Created/Modified

### 1. `timing_logger.py` - NEW
**Purpose**: Comprehensive timing logger for command pipeline analysis

**Key Features**:
- Thread-safe command tracking from Web UI → Backend → Motion Controller → FluidNC
- Detailed phase breakdown with millisecond precision
- Automatic summary generation for completed commands
- Performance statistics and reporting
- Dedicated log file: `timing_analysis.log`

**Usage**:
```python
from timing_logger import timing_logger

# Log command received from web UI
command_id = timing_logger.log_backend_received("jog", {"axis": "z", "direction": "+"})

# Log backend processing stages
timing_logger.log_backend_start(command_id, "api_jog")
timing_logger.log_motion_controller_start(command_id, "_execute_jog_command")

# Log FluidNC communication
timing_logger.log_fluidnc_send(command_id, "G1 Z1.0")
timing_logger.log_fluidnc_response(command_id, "ok")

# Log completion
timing_logger.log_backend_complete(command_id, success=True)
```

### 2. `web/web_interface.py` - MODIFIED
**Changes Made**:
- Added timing_logger import and integration
- Enhanced `/api/jog` endpoint with timing tracking
- Added command_id parameter to `_execute_jog_command()`
- Complete timing coverage from API request to response

**Timing Points Added**:
- `log_backend_received()` - When API receives request
- `log_backend_start()` - When processing begins
- `log_motion_controller_start()` - When motion controller called
- `log_backend_complete()` - When API response sent

### 3. `motion/simplified_fluidnc_controller_fixed.py` - MODIFIED
**Changes Made**:
- Added timing_logger import with graceful fallback
- Enhanced `move_relative()` method with command_id parameter
- Enhanced `_send_command()` method with FluidNC timing
- Complete motion control timing coverage

**Timing Points Added**:
- `log_fluidnc_send()` - When G-code sent to FluidNC
- `log_fluidnc_response()` - When FluidNC responds
- Error logging for failed commands

### 4. `motion/simplified_fluidnc_protocol_fixed.py` - MODIFIED
**Changes Made**:
- Added detailed internal timing to `send_command_with_motion_wait()`
- Millisecond-precision logging for each phase
- Command delay timing analysis
- Motion completion wait timing

**Internal Timing Points**:
- Command delay enforcement duration
- Command transmission time
- Response wait time
- Motion completion wait time
- Total command execution time

### 5. `run_web_interface_with_timing.py` - NEW
**Purpose**: Run web interface with timing analysis enabled

**Features**:
- Starts web interface with timing logging
- Generates performance summary on shutdown
- Clear usage instructions
- Debug logging enabled

## Timing Analysis Pipeline

```
Web UI Request → Backend API → Motion Controller → FluidNC Protocol → Hardware
     |              |               |                  |              |
   [Web UI]    [Backend Recv]   [Motion Start]    [FluidNC Send]  [Response]
     |              |               |                  |              |
     └──────────── TIMING LOGGER TRACKS ALL PHASES ─────────────────┘
```

## Expected Timing Breakdown

When running timing analysis, you'll see logs like:
```
⏱️  WEB_UI_SEND         | CMD:jog_0001 | Data: {"axis": "z", "direction": "+"}
⏱️  BACKEND_RECEIVED     | CMD:jog_0001 | 
⏱️  BACKEND_START        | CMD:jog_0001 | Method: api_jog
⏱️  MOTION_START         | CMD:jog_0001 | Method: _execute_jog_command
⏱️  FLUIDNC_SEND         | CMD:jog_0001 | G-code: F750.0
⏱️  FLUIDNC_RESPONSE     | CMD:jog_0001 | Response: ok
⏱️  FLUIDNC_SEND         | CMD:jog_0001 | G-code: G90
⏱️  FLUIDNC_RESPONSE     | CMD:jog_0001 | Response: ok
⏱️  FLUIDNC_SEND         | CMD:jog_0001 | G-code: G1 X0.000 Y0.000 Z1.000 A0.000
⏱️  FLUIDNC_RESPONSE     | CMD:jog_0001 | Response: ok
⏱️  BACKEND_COMPLETE     | CMD:jog_0001 | Status: SUCCESS

📋 COMMAND SUMMARY: jog_0001 (jog)
🕐 TOTAL DURATION: 277.1ms
📊 PHASE BREAKDOWN:
  ⏱️  Backend Queue          :    2.1ms
  ⏱️  Backend Processing     :    1.5ms
  ⏱️  Motion Controller      :    3.2ms
  ⏱️  FluidNC Transmission   :  270.3ms  ← IDENTIFIED BOTTLENECK
```

## Investigation Areas Identified

### 1. FluidNC Protocol Delays
The protocol has several built-in delays:
- **Command delay enforcement**: Minimum time between commands
- **Motion completion wait**: Waits for machine to return to Idle state
- **Response timeouts**: Maximum wait times for responses

### 2. Command Sequencing
Each jog command sends multiple G-code commands:
1. `F750.0` - Set feedrate
2. `G90` - Absolute positioning mode  
3. `G1 X0.000 Y0.000 Z1.000 A0.000` - Move command

### 3. Motion Completion Logic
The system waits for motion to complete before accepting next command, which may cause perceived delays.

## Next Steps for Testing

1. **Run the timing logger**:
   ```bash
   python run_web_interface_with_timing.py
   ```

2. **Test manual jogging** using the web interface

3. **Analyze timing_analysis.log** to identify bottlenecks

4. **Look for patterns** in the phase breakdown

5. **Focus on optimizing** the slowest phases identified

## Expected Results

This timing system will precisely identify:
- Which phase takes the longest (likely FluidNC transmission)
- Whether delays are from command queuing or motion completion waits
- Exact timing of first vs subsequent commands
- Impact of different jog distances and speeds

The analysis should reveal whether the 277ms delays are from:
- Protocol command delays
- Motion completion waits  
- Hardware response times
- Command sequencing overhead