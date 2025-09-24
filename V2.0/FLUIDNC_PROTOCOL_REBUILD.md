# FluidNC Protocol-Compliant Communication System

## Overview

This document describes the new FluidNC communication system that properly implements the FluidNC real-time reporting protocol, eliminating message confusion and significantly improving response times.

## Problems with Current Implementation

### 1. **Mixed Command Types**
- Current system treats all commands the same way
- Immediate commands (?) mixed with line-based commands (G-code)
- Response parsing expects "ok" from status queries (which don't send "ok")

### 2. **Serial Stream Competition**
- Background monitor competes with command/response for serial stream
- Lock contention causes delays and message loss
- Multiple processes reading from same serial connection

### 3. **Auto-Report Interference**
- FluidNC auto-reports every ~200ms interfere with command responses
- Commands get status reports instead of "ok" responses
- Message parsing confusion causes timeouts and retries

### 4. **Response Timing Issues**
- Complex response parsing with multiple fallback strategies
- Heavy processing overhead on every message
- Position verification requiring multiple queries and retries

## New Protocol-Compliant System

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FluidNC Hardware                             │
└─────────────────────┬───────────────────────────────────────────┘
                      │ USB Serial
                      │ Auto-reports (200ms) + Command responses
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│               FluidNCProtocol                                   │
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │ Message Reader  │    │ Command Handler  │                  │
│  │   (Single)      │    │   (Queued)       │                  │
│  └─────────────────┘    └──────────────────┘                  │
│           │                       │                           │
│           ▼                       ▼                           │
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │ Message Router  │    │ Response Futures │                  │
│  │ by Message Type │    │   (Command ID)   │                  │
│  └─────────────────┘    └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────────┐
│                FluidNCCommunicator                              │
│  ┌─────────────────┐    ┌──────────────────┐                  │
│  │ Status Handler  │    │  Motion Control  │                  │
│  │ (Auto-reports)  │    │   (G-code)       │                  │
│  └─────────────────┘    └──────────────────┘                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. **FluidNCProtocol** - Low-Level Protocol Handler
- **Single Message Reader**: One async task reads all serial data
- **Message Type Routing**: Separates status reports, command responses, alarms
- **Command Queue**: Proper sequencing of line-based commands
- **Response Futures**: Async/await for command responses

#### 2. **FluidNCCommunicator** - High-Level Interface  
- **Motion Control Methods**: move_to_position(), home_all(), etc.
- **Real-Time Status**: Uses auto-reports for position updates
- **Event Handlers**: Status changes, alarms, position updates

### Protocol Compliance

#### **Immediate Commands** (Single Characters)
```python
# Status request - processed immediately, no "ok" response
await protocol.send_immediate_command('?')

# Feed hold - processed immediately  
await protocol.send_immediate_command('!')

# Resume - processed immediately
await protocol.send_immediate_command('~')

# Reset - processed immediately
await protocol.send_immediate_command('\x18')
```

#### **Line-Based Commands** (G-code)
```python
# G-code commands - queued, wait for "ok" response
response = await protocol.send_line_command('G1 X10 Y20 F100')
# response will be "ok" or "error:N"
```

#### **Auto-Report Processing**
```python
# FluidNC automatically sends status reports:
# <Idle|MPos:10.000,20.000,30.000,40.000|FS:0,0>
# <Run|MPos:10.100,20.050,30.000,40.000|FS:100,500>

# These are processed automatically and trigger handlers:
async def on_status_update(message):
    position = extract_position(message.data)
    update_current_position(position)
```

## Performance Improvements

### 1. **Eliminated Message Confusion**
- Immediate commands don't expect "ok" responses
- Line commands properly wait for actual responses
- Auto-reports processed separately from command responses

### 2. **Real-Time Position Updates**
- No more manual position queries during movement
- Auto-reports provide position at 200ms intervals
- Movement completion detected via status changes + position stability

### 3. **Reduced Lock Contention**
- Single serial reader eliminates competition
- Message routing distributes data to appropriate handlers
- No more blocking status queries during movements

### 4. **Faster Movement Completion**
```python
# Old system: Multiple status queries with timeouts
# New system: Real-time status monitoring
while status != IDLE:
    await asyncio.sleep(0.05)  # 50ms responsiveness
```

## Usage Examples

### Basic Setup
```python
import serial
from motion.fluidnc_protocol import FluidNCCommunicator

# Create serial connection
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.1)

# Create communicator
comm = FluidNCCommunicator(ser)
await comm.start()  # Enables auto-reporting

# Motion control
await comm.move_to_position(Position4D(x=10, y=20, z=30, c=0))
```

### Movement with Timing
```python
start_time = time.time()

# Send movement command
await comm.move_to_position(target_position)

completion_time = time.time() - start_time
print(f"Movement completed in {completion_time:.3f}s")
```

### Real-Time Monitoring
```python
# Register for position updates
async def on_position_change(message):
    position = extract_position(message.data)
    print(f"New position: {position}")

comm.protocol.add_message_handler(MessageType.STATUS_REPORT, on_position_change)
```

## Expected Performance Gains

### **Movement Timing**
- **Current**: 1-10+ seconds (with retries and timeouts)
- **New**: 0.2-0.5 seconds (real-time completion detection)

### **Position Updates**  
- **Current**: Manual queries with caching delays
- **New**: Real-time auto-reports every 200ms

### **Command Response**
- **Current**: Mixed responses cause timeouts
- **New**: Proper command/response pairing

### **Web UI Responsiveness**
- **Current**: Polling with stale data issues
- **New**: Real-time position updates without polling overhead

## Integration Steps

### 1. **Test New Protocol** 
```bash
cd RaspPI/V2.0
python test_fluidnc_protocol.py
```

### 2. **Replace FluidNC Controller**
- Swap `FluidNCController` with `EnhancedFluidNCController` 
- Update imports in main application
- Test with existing web interface

### 3. **Monitor Performance**
- Check movement completion times
- Verify position update accuracy  
- Validate web UI responsiveness

### 4. **Fine-Tune Settings**
- Adjust FluidNC auto-report intervals ($10 setting)
- Optimize polling frequencies
- Configure command timeouts

## Migration Strategy

### Phase 1: Protocol Testing
- Test new protocol with existing hardware
- Verify message parsing and command handling
- Measure performance improvements

### Phase 2: Controller Integration  
- Replace motion controller in scanning system
- Update web interface integration
- Test movement sequences and homing

### Phase 3: Production Deployment
- Full system testing with enhanced protocol
- Performance monitoring and optimization
- Documentation updates

## Troubleshooting

### **Message Parsing Issues**
- Enable debug logging: `logging.getLogger('motion.fluidnc_protocol').setLevel(logging.DEBUG)`
- Check message format compatibility
- Verify FluidNC firmware version

### **Command Timeouts**
- Check serial connection stability
- Verify FluidNC is not in alarm state
- Increase command timeouts if needed

### **Position Updates**  
- Verify auto-reporting is enabled ($10=3)
- Check message handler registration
- Monitor protocol statistics

## Conclusion

The new protocol-compliant system eliminates the fundamental communication issues causing delays and provides:

- ✅ **Proper FluidNC protocol implementation**
- ✅ **Real-time position updates without polling**
- ✅ **Fast movement completion detection**  
- ✅ **Eliminated message confusion and timeouts**
- ✅ **Improved web UI responsiveness**
- ✅ **Simplified communication architecture**

This should resolve the position detection delays and provide the responsive, real-time system needed for the scanner interface.