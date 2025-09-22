# 3D Scanner Web Interface

A comprehensive Flask-based web interface for controlling and monitoring the 3D scanner system with robust command/data transfer capabilities.

## 🚀 Quick Start

### Simple Testing (No Hardware Required)
```bash
# Run simple web interface with mock responses
cd web/
python simple_web_interface.py
```
Visit: http://localhost:5000

### Full Interface (Development Mode)
```bash
# Run full interface with hardware detection and mock fallback
cd web/
python start_web_interface.py --mode development --debug
```

### Production Mode
```bash
# Run with real hardware only (no fallback)
cd web/
python start_web_interface.py --mode production --host 0.0.0.0 --port 80
```

## 📁 Web Interface Structure

```
web/
├── start_web_interface.py      # Main initialization script
├── web_interface.py            # Complete Flask application with orchestrator integration
├── simple_web_interface.py     # Simplified testing version with mocks
├── templates/                  # HTML templates
│   ├── base.html              # Base template with navigation
│   ├── dashboard.html         # System status and monitoring
│   ├── manual.html            # Manual motion controls
│   ├── scans.html             # Scan management and history
│   └── settings.html          # System configuration
├── static/                    # Static assets
│   ├── css/
│   │   └── scanner.css        # Complete responsive styling
│   └── js/
│       ├── scanner-base.js    # Core JavaScript functionality
│       ├── dashboard.js       # Dashboard-specific features
│       ├── manual-control.js  # Manual control interface
│       ├── scans.js           # Scan management
│       └── settings.js        # Settings interface
└── README.md                  # This file
```

## 🎛️ Features

### Dashboard
- **Real-time System Status**: Motion, camera, lighting, and scan progress
- **Live Position Display**: Current X, Y, Z, C coordinates
- **Error and Warning Indicators**: System health monitoring
- **Recent Activity Log**: Operation history and messages

### Manual Controls
- **Precision Movement**: Step sizes from 0.1mm to 10mm
- **Direct Position Input**: Move to specific coordinates
- **Multi-axis Homing**: Home individual or all axes
- **Emergency Stop**: Immediate motion halt
- **Position Limits**: Safety boundaries with visual feedback

### Scan Management
- **Pattern Creation**: Grid and cylindrical scan patterns
- **Real-time Progress**: Completion percentage and point tracking
- **Scan History**: Previous scan records and results
- **Pattern Validation**: Parameter checking and error prevention
- **Export Options**: Scan data and configuration export

### Settings
- **Motion Configuration**: Speed, acceleration, limits
- **Camera Settings**: Resolution, exposure, capture parameters
- **Lighting Control**: Zone configuration and flash settings
- **System Configuration**: Logging, simulation mode, calibration

## 🔧 API Endpoints

### System Status
- `GET /api/status` - Complete system status
- `POST /api/control/emergency_stop` - Emergency stop all systems

### Motion Control
- `POST /api/control/move` - Relative axis movement
- `POST /api/control/position` - Absolute positioning
- `POST /api/control/home` - Axis homing

### Scan Operations
- `POST /api/scan/start` - Start new scan with pattern
- `POST /api/scan/stop` - Stop active scan
- `POST /api/scan/pause` - Pause/resume scan

### Camera Functions
- `POST /api/camera/capture` - Capture image
- `GET /api/camera/preview/<camera_id>` - Camera preview stream

### Lighting Control
- `POST /api/lighting/flash` - Flash lighting zones

## 🛠️ Configuration Options

### Command Line Arguments
```bash
python start_web_interface.py [options]

Options:
  --mode {production,development,mock}  Operating mode (default: development)
  --host HOST                          Host to bind to (default: 0.0.0.0)
  --port PORT                          Port to bind to (default: 5000)
  --debug                              Enable debug mode
  --log-level {DEBUG,INFO,WARNING,ERROR} Logging level (default: INFO)
```

### Operating Modes

#### Production Mode
- Uses real hardware controllers only
- No fallback to mock systems
- Optimized for deployment
- Minimal debug output

#### Development Mode
- Attempts real hardware initialization
- Falls back to mock controllers if hardware unavailable
- Enhanced error reporting
- Debug-friendly logging

#### Mock Mode
- Pure simulation mode
- No hardware dependencies
- Full UI functionality testing
- Safe for development and demos

## 🎨 User Interface Features

### Responsive Design
- **Mobile-friendly**: Works on tablets and phones
- **Desktop optimized**: Full-featured interface for computers
- **High contrast**: Clear visibility in workshop environments
- **Touch-friendly**: Large buttons and controls

### Real-time Updates
- **Live status polling**: Automatic status refresh
- **Progress indicators**: Visual feedback for operations
- **Error notifications**: Immediate problem alerts
- **Connection status**: Hardware availability indicators

### Professional Styling
- **Dark theme**: Reduces eye strain in low-light environments
- **Color-coded status**: Green/yellow/red system indicators
- **Grid layouts**: Organized information presentation
- **Smooth animations**: Professional user experience

## 🔐 Safety Features

### Emergency Controls
- **Emergency Stop Button**: Prominent red button on all pages
- **Motion Limits**: Software limits prevent crashes
- **Hardware Validation**: Checks before executing commands
- **Error Recovery**: Graceful handling of failures

### Input Validation
- **Parameter Checking**: Range and type validation
- **Coordinate Limits**: Boundary enforcement
- **Pattern Validation**: Scan parameter verification
- **Command Queuing**: Prevents conflicting operations

## 🧪 Testing and Development

### Simple Testing
```bash
# Test templates and basic functionality
python simple_web_interface.py
```

### Hardware Testing
```bash
# Test with real hardware
python start_web_interface.py --mode development --debug --log-level DEBUG
```

### API Testing
```bash
# Test individual endpoints
curl -X GET http://localhost:5000/api/status
curl -X POST http://localhost:5000/api/control/move -H "Content-Type: application/json" -d '{"axis": "x", "distance": 10}'
```

## 🚀 Deployment

### Local Development
```bash
cd web/
python start_web_interface.py --mode development --debug
```

### Production Server
```bash
cd web/
python start_web_interface.py --mode production --host 0.0.0.0 --port 80
```

### Service Deployment
Create systemd service for automatic startup:
```ini
[Unit]
Description=3D Scanner Web Interface
After=network.target

[Service]
Type=simple
User=scanner
WorkingDirectory=/home/scanner/RaspPI/V2.0/web
ExecStart=/home/scanner/RaspPI/V2.0/venv/bin/python start_web_interface.py --mode production
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🔧 Troubleshooting

### Common Issues

#### Module Import Errors
- Ensure you're in the correct directory (`web/` or project root)
- Check that all required Python packages are installed
- Verify Python path includes the project directories

#### Hardware Connection Issues
- Use `--mode mock` for testing without hardware
- Check serial port permissions and connections
- Review hardware initialization logs

#### Template Rendering Errors
- Verify all template files exist in `templates/` directory
- Check for missing template variables
- Review Flask route configurations

#### Network Access Issues
- Use `--host 0.0.0.0` to allow external connections
- Check firewall settings for the specified port
- Verify network interface configuration

### Debug Mode
Enable detailed logging and error reporting:
```bash
python start_web_interface.py --debug --log-level DEBUG
```

### Log Files
- Application logs: `web_interface.log`
- Flask debug output: Console
- Hardware logs: Check individual controller modules

## 📞 Support

For issues and development:
1. Check the troubleshooting section above
2. Review log files for error details
3. Test in mock mode to isolate hardware issues
4. Verify all dependencies are installed correctly

## 🎯 Next Steps

The web interface is now fully functional! You can:
1. **Test immediately**: Use simple mode for UI testing
2. **Integrate hardware**: Connect real controllers in development mode
3. **Deploy production**: Run with full hardware integration
4. **Customize**: Modify templates, styling, and functionality as needed

The foundation is solid - time to control your 3D scanner through the web! 🎉