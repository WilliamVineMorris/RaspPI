/**
 * Manual Control JavaScript - Precise motion and component control
 * 
 * Provides comprehensive manual control interface for motion, cameras,
 * and lighting with real-time feedback and safety validation.
 */

// Manual control functionality
const ManualControl = {
    // Configuration
    config: {
        jogSpeeds: [1, 5, 10, 25, 50, 100],
        defaultJogSpeed: 10,
        maxJogDistance: 100,
        positionPrecision: 1,
        lightingUpdateDelay: 300
    },

    // State management
    state: {
        currentJogSpeed: 10,
        activeAxis: null,
        isDragging: false,
        lightingTimers: new Map()
    },

    /**
     * Initialize manual control interface
     */
    init() {
        ScannerBase.log('Initializing manual control...');
        
        this.setupMotionControls();
        this.setupCameraControls();
        this.setupLightingControls();
        this.setupKeyboardControls();
        this.setupEventHandlers();
        
        // Listen for status updates
        document.addEventListener('scanner:statusUpdate', (event) => {
            this.handleStatusUpdate(event.detail.status);
        });

        // Start periodic position updates to ensure UI stays synchronized
        this.startPositionUpdateTimer();

        ScannerBase.log('Manual control initialized');
    },

    /**
     * Start periodic position updates to keep UI synchronized
     */
    startPositionUpdateTimer() {
        // Update position display every 250ms to be very responsive to FluidNC's 200ms auto-reports
        setInterval(async () => {
            if (!this.state.isJogging) {
                try {
                    const status = await ScannerBase.apiRequest('/api/status');
                    if (status.motion && status.motion.position) {
                        this.updatePositionDisplays(status.motion.position);
                    }
                } catch (error) {
                    // Don't spam errors for periodic updates - just log quietly
                    ScannerBase.log('Periodic position update failed: ' + error.message);
                }
            }
        }, 250); // Reduced from 500ms to 250ms for maximum responsiveness
    },

    /**
     * Setup motion control interface
     */
    setupMotionControls() {
        // Jog speed selector
        const jogSpeedSelect = document.getElementById('jogSpeed');
        if (jogSpeedSelect) {
            // Clear and populate speed options
            jogSpeedSelect.innerHTML = '';
            this.config.jogSpeeds.forEach(speed => {
                const option = document.createElement('option');
                option.value = speed;
                option.textContent = `${speed} mm/min`;
                if (speed === this.config.defaultJogSpeed) {
                    option.selected = true;
                }
                jogSpeedSelect.appendChild(option);
            });

            jogSpeedSelect.addEventListener('change', (e) => {
                this.state.currentJogSpeed = parseFloat(e.target.value);
                ScannerBase.addLogEntry(`Jog speed changed to ${this.state.currentJogSpeed} mm/min`, 'info');
            });
        }

        // Jog distance input
        const jogDistanceInput = document.getElementById('jogDistance');
        if (jogDistanceInput) {
            jogDistanceInput.addEventListener('change', (e) => {
                const distance = parseFloat(e.target.value);
                if (distance > this.config.maxJogDistance) {
                    e.target.value = this.config.maxJogDistance;
                    ScannerBase.showAlert(`Maximum jog distance is ${this.config.maxJogDistance}mm`, 'warning');
                }
            });
        }

        // Axis jog buttons
        this.setupAxisJogButtons();
        
        // Coordinate input controls
        this.setupCoordinateInputs();
        
        // Control mode buttons
        this.setupControlModeButtons();
    },

    /**
     * Setup axis jog buttons
     */
    setupAxisJogButtons() {
        const axes = ['X', 'Y', 'Z', 'C'];
        const directions = ['+', '-'];
        
        axes.forEach(axis => {
            directions.forEach(direction => {
                const buttonId = `jog${axis}${direction === '+' ? 'Plus' : 'Minus'}`;
                const button = document.getElementById(buttonId);
                
                if (button) {
                    // Mouse events for continuous jogging
                    button.addEventListener('mousedown', (e) => {
                        e.preventDefault();
                        this.startContinuousJog(axis, direction);
                    });
                    
                    button.addEventListener('mouseup', () => {
                        this.stopContinuousJog();
                    });
                    
                    button.addEventListener('mouseleave', () => {
                        this.stopContinuousJog();
                    });
                    
                    // Click event for single step
                    button.addEventListener('click', (e) => {
                        if (!this.state.isDragging) {
                            this.singleStepJog(axis, direction);
                        }
                    });
                }
            });
        });
    },

    /**
     * Setup coordinate input controls
     */
    setupCoordinateInputs() {
        // Go to position button
        const gotoButton = document.getElementById('gotoPosition');
        if (gotoButton) {
            gotoButton.addEventListener('click', () => this.gotoPosition());
        }

        // Set position button
        const setPositionButton = document.getElementById('setPosition');
        if (setPositionButton) {
            setPositionButton.addEventListener('click', () => this.setCurrentPosition());
        }

        // Coordinate input validation
        const coordinateInputs = document.querySelectorAll('.coordinate-input');
        coordinateInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                this.validateCoordinateInput(e.target);
            });
        });
    },

    /**
     * Setup control mode buttons
     */
    setupControlModeButtons() {
        // Home button
        const homeButton = document.getElementById('homeAxes');
        if (homeButton) {
            // Store original text for restoration after homing
            homeButton.dataset.originalText = homeButton.textContent;
            homeButton.addEventListener('click', () => this.homeAllAxes());
        }

        // Stop button
        const stopButton = document.getElementById('stopMotion');
        if (stopButton) {
            stopButton.addEventListener('click', () => this.stopMotion());
        }

        // Enable/disable motors
        const motorsToggle = document.getElementById('toggleMotors');
        if (motorsToggle) {
            motorsToggle.addEventListener('click', () => this.toggleMotors());
        }
    },

    /**
     * Setup camera control interface
     */
    setupCameraControls() {
        // Camera selection
        const cameraSelect = document.getElementById('selectedCamera');
        if (cameraSelect) {
            cameraSelect.addEventListener('change', (e) => {
                this.selectCamera(e.target.value);
            });
        }

        // Capture controls
        const captureButton = document.getElementById('captureImage');
        if (captureButton) {
            captureButton.addEventListener('click', () => this.captureImage());
        }

        const previewButton = document.getElementById('togglePreview');
        if (previewButton) {
            previewButton.addEventListener('click', () => this.togglePreview());
        }

        // Camera settings
        this.setupCameraSettings();
    },

    /**
     * Setup camera settings controls
     */
    setupCameraSettings() {
        const settings = ['exposure', 'gain', 'brightness', 'contrast'];
        
        settings.forEach(setting => {
            const slider = document.getElementById(`camera${setting.charAt(0).toUpperCase() + setting.slice(1)}`);
            const value = document.getElementById(`${setting}Value`);
            
            if (slider && value) {
                slider.addEventListener('input', (e) => {
                    value.textContent = e.target.value;
                    this.updateCameraSetting(setting, e.target.value);
                });
            }
        });
    },

    /**
     * Setup lighting control interface
     */
    setupLightingControls() {
        // Master controls
        const masterIntensity = document.getElementById('masterIntensity');
        const masterValue = document.getElementById('masterIntensityValue');
        
        if (masterIntensity && masterValue) {
            masterIntensity.addEventListener('input', (e) => {
                masterValue.textContent = `${e.target.value}%`;
                this.updateMasterIntensity(e.target.value);
            });
        }

        const allLightsToggle = document.getElementById('toggleAllLights');
        if (allLightsToggle) {
            allLightsToggle.addEventListener('click', () => this.toggleAllLights());
        }

        // Individual zone controls will be setup dynamically
        this.setupZoneControls();
    },

    /**
     * Setup lighting zone controls
     */
    setupZoneControls() {
        // This will be populated when status updates arrive with zone information
        const zonesContainer = document.getElementById('lightingZones');
        if (zonesContainer) {
            // Clear existing controls
            zonesContainer.innerHTML = '<h4>Lighting Zones</h4>';
        }
    },

    /**
     * Setup keyboard controls
     */
    setupKeyboardControls() {
        document.addEventListener('keydown', (e) => {
            // Only process if not in input field
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            this.handleKeyboardInput(e);
        });

        document.addEventListener('keyup', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            this.handleKeyboardRelease(e);
        });
    },

    /**
     * Setup event handlers
     */
    setupEventHandlers() {
        // Prevent context menu on jog buttons
        const jogButtons = document.querySelectorAll('.jog-btn');
        jogButtons.forEach(button => {
            button.addEventListener('contextmenu', (e) => e.preventDefault());
        });

        // Handle window focus loss to stop continuous operations
        window.addEventListener('blur', () => {
            this.stopContinuousJog();
        });
    },

    /**
     * Handle status updates
     */
    handleStatusUpdate(status) {
        this.updateMotionStatus(status);
        this.updateCameraStatus(status);
        this.updateLightingStatus(status);
    },

    /**
     * Update position displays with current axis values
     */
    updatePositionDisplays(position) {
        if (!position) {
            ScannerBase.log('No position data provided to updatePositionDisplays');
            return;
        }

        const axes = ['x', 'y', 'z', 'c'];
        axes.forEach(axis => {
            const element = document.getElementById(`current${axis.toUpperCase()}`);
            if (element) {
                const value = parseFloat(position[axis] || 0).toFixed(this.config.positionPrecision);
                element.textContent = value;
                ScannerBase.log(`Updated ${axis.toUpperCase()} position display: ${value}`);
            } else {
                ScannerBase.log(`Element current${axis.toUpperCase()} not found`);
            }
        });
    },

    /**
     * Update motion control status
     */
    updateMotionStatus(status) {
        if (!status.motion) return;

        // Update position displays
        if (status.motion.position) {
            const axes = ['x', 'y', 'z', 'c'];
            axes.forEach(axis => {
                const element = document.getElementById(`current${axis.toUpperCase()}`);
                if (element) {
                    element.textContent = parseFloat(status.motion.position[axis] || 0).toFixed(this.config.positionPrecision);
                }
            });
        }

        // Update detailed motion controller status
        this.updateMotionConnectionStatus(status.motion.connected || false);
        this.updateMotionHomedStatus(status.motion.homed || false);
        this.updateMotionStateStatus(status.motion.status || 'unknown');
        this.updateMotionActivity(status.motion.activity || 'idle');

        // Update control availability
        const isReady = status.motion.connected && !status.scan?.active;
        const motionControls = document.querySelectorAll('.motion-control');
        motionControls.forEach(control => {
            control.disabled = !isReady;
        });
    },

    /**
     * Update motion connection status
     */
    updateMotionConnectionStatus(connected) {
        const textElement = document.getElementById('motionConnectionText');
        const dotElement = document.getElementById('motionConnectionDot');
        
        if (textElement) {
            textElement.textContent = connected ? 'Connected' : 'Disconnected';
            textElement.className = connected ? 'status-good' : 'status-error';
        }
        
        if (dotElement) {
            dotElement.className = `status-indicator ${connected ? 'ready' : 'error'}`;
        }
    },

    /**
     * Update motion homed status
     */
    updateMotionHomedStatus(homed) {
        const textElement = document.getElementById('motionHomedText');
        const dotElement = document.getElementById('motionHomedDot');
        
        if (textElement) {
            textElement.textContent = homed ? 'Homed' : 'Not Homed';
            textElement.className = homed ? 'status-good' : 'status-warning';
        }
        
        if (dotElement) {
            dotElement.className = `status-indicator ${homed ? 'ready' : 'warning'}`;
        }
    },

    /**
     * Update motion state status
     */
    updateMotionStateStatus(state) {
        const textElement = document.getElementById('motionStateText');
        const dotElement = document.getElementById('motionStateDot');
        
        if (textElement) {
            textElement.textContent = this.formatMotionState(state);
        }
        
        if (dotElement) {
            const isHealthy = ['idle', 'ready', 'homed'].includes(state.toLowerCase());
            dotElement.className = `status-indicator ${isHealthy ? 'ready' : 'warning'}`;
        }
    },

    /**
     * Update motion activity
     */
    updateMotionActivity(activity) {
        const textElement = document.getElementById('motionActivityText');
        
        if (textElement) {
            textElement.textContent = this.formatMotionActivity(activity);
        }
    },

    /**
     * Format motion state for display
     */
    formatMotionState(state) {
        const stateMap = {
            'idle': 'Idle',
            'ready': 'Ready',
            'moving': 'Moving',
            'homing': 'Homing',
            'error': 'Error',
            'alarm': 'Alarm',
            'unknown': 'Unknown'
        };
        return stateMap[state.toLowerCase()] || state;
    },

    /**
     * Format motion activity for display
     */
    formatMotionActivity(activity) {
        const activityMap = {
            'idle': 'Idle',
            'jogging': 'Jogging',
            'homing': 'Homing',
            'moving': 'Moving to Position',
            'scanning': 'Scanning',
            'error': 'Error'
        };
        return activityMap[activity.toLowerCase()] || activity;
    },

    /**
     * Update camera control status
     */
    updateCameraStatus(status) {
        if (!status.cameras) return;

        // Update camera selection dropdown
        const cameraSelect = document.getElementById('selectedCamera');
        if (cameraSelect && status.cameras.available_cameras) {
            const currentValue = cameraSelect.value;
            cameraSelect.innerHTML = '<option value="">Select Camera</option>';
            
            status.cameras.available_cameras.forEach(camera => {
                const option = document.createElement('option');
                option.value = camera.id;
                option.textContent = `Camera ${camera.id} (${camera.resolution})`;
                if (camera.id === currentValue) {
                    option.selected = true;
                }
                cameraSelect.appendChild(option);
            });
        }

        // Update camera controls availability
        const cameraControls = document.querySelectorAll('.camera-control');
        const hasCamera = status.cameras.available > 0;
        cameraControls.forEach(control => {
            control.disabled = !hasCamera;
        });
    },

    /**
     * Update lighting control status
     */
    updateLightingStatus(status) {
        if (!status.lighting || !status.lighting.zones) return;

        // Update zone controls
        const zonesContainer = document.getElementById('lightingZones');
        if (zonesContainer) {
            const zones = status.lighting.zones;
            
            // Create zone controls if they don't exist
            zones.forEach(zone => {
                let zoneElement = document.getElementById(`zone${zone.id}`);
                if (!zoneElement) {
                    zoneElement = this.createZoneControl(zone);
                    zonesContainer.appendChild(zoneElement);
                }
                
                // Update zone values
                this.updateZoneControl(zoneElement, zone);
            });
        }

        // Update master intensity
        const masterSlider = document.getElementById('masterIntensity');
        const masterValue = document.getElementById('masterIntensityValue');
        if (masterSlider && masterValue && status.lighting.master_intensity !== undefined) {
            masterSlider.value = status.lighting.master_intensity;
            masterValue.textContent = `${status.lighting.master_intensity}%`;
        }
    },

    /**
     * Create lighting zone control
     */
    createZoneControl(zone) {
        const zoneDiv = document.createElement('div');
        zoneDiv.id = `zone${zone.id}`;
        zoneDiv.className = 'zone-control';
        zoneDiv.innerHTML = `
            <div class="zone-header">
                <label>Zone ${zone.id}</label>
                <button class="zone-toggle" data-zone="${zone.id}">Toggle</button>
            </div>
            <div class="zone-slider">
                <input type="range" min="0" max="100" value="${zone.intensity}" 
                       class="intensity-slider" data-zone="${zone.id}">
                <span class="intensity-value">${zone.intensity}%</span>
            </div>
        `;

        // Add event listeners
        const slider = zoneDiv.querySelector('.intensity-slider');
        const valueSpan = zoneDiv.querySelector('.intensity-value');
        const toggleBtn = zoneDiv.querySelector('.zone-toggle');

        slider.addEventListener('input', (e) => {
            valueSpan.textContent = `${e.target.value}%`;
            this.updateZoneIntensity(zone.id, e.target.value);
        });

        toggleBtn.addEventListener('click', () => {
            this.toggleZone(zone.id);
        });

        return zoneDiv;
    },

    /**
     * Update zone control display
     */
    updateZoneControl(element, zone) {
        const slider = element.querySelector('.intensity-slider');
        const value = element.querySelector('.intensity-value');
        const toggle = element.querySelector('.zone-toggle');

        if (slider) slider.value = zone.intensity;
        if (value) value.textContent = `${zone.intensity}%`;
        if (toggle) {
            toggle.textContent = zone.intensity > 0 ? 'Turn Off' : 'Turn On';
            toggle.className = `zone-toggle ${zone.intensity > 0 ? 'on' : 'off'}`;
        }
    },

    /**
     * Handle keyboard input for motion control
     */
    handleKeyboardInput(e) {
        const keyMap = {
            'ArrowLeft': { axis: 'X', direction: '-' },
            'ArrowRight': { axis: 'X', direction: '+' },
            'ArrowUp': { axis: 'Y', direction: '+' },
            'ArrowDown': { axis: 'Y', direction: '-' },
            'PageUp': { axis: 'Z', direction: '+' },
            'PageDown': { axis: 'Z', direction: '-' },
            'Home': { axis: 'C', direction: '+' },
            'End': { axis: 'C', direction: '-' }
        };

        const mapping = keyMap[e.code];
        if (mapping && !this.state.activeAxis) {
            e.preventDefault();
            this.startContinuousJog(mapping.axis, mapping.direction);
        }

        // Emergency stop
        if (e.code === 'Space' || e.code === 'Escape') {
            e.preventDefault();
            this.stopMotion();
        }
    },

    /**
     * Handle keyboard release
     */
    handleKeyboardRelease(e) {
        const keyMap = {
            'ArrowLeft': 'X', 'ArrowRight': 'X',
            'ArrowUp': 'Y', 'ArrowDown': 'Y',
            'PageUp': 'Z', 'PageDown': 'Z',
            'Home': 'C', 'End': 'C'
        };

        if (keyMap[e.code] && this.state.activeAxis === keyMap[e.code]) {
            this.stopContinuousJog();
        }
    },

    /**
     * Start continuous jogging
     */
    startContinuousJog(axis, direction) {
        if (this.state.activeAxis) return; // Already jogging

        this.state.activeAxis = axis;
        this.state.isDragging = true;

        // Visual feedback
        const button = document.getElementById(`jog${axis}${direction === '+' ? 'Plus' : 'Minus'}`);
        if (button) {
            button.classList.add('active');
        }

        ScannerBase.addLogEntry(`Continuous jog started: ${axis}${direction}`, 'info');

        // Start continuous movement
        this.sendJogCommand(axis, direction, 'continuous');
    },

    /**
     * Stop continuous jogging
     */
    stopContinuousJog() {
        if (!this.state.activeAxis) return;

        const axis = this.state.activeAxis;
        this.state.activeAxis = null;
        this.state.isDragging = false;

        // Remove visual feedback
        const jogButtons = document.querySelectorAll('.jog-btn');
        jogButtons.forEach(btn => btn.classList.remove('active'));

        ScannerBase.addLogEntry(`Continuous jog stopped: ${axis}`, 'info');

        // Send stop command
        this.sendStopCommand();
    },

    /**
     * Single step jog
     */
    singleStepJog(axis, direction) {
        const distance = document.getElementById('jogDistance')?.value || 1;
        ScannerBase.addLogEntry(`Single step jog: ${axis}${direction} ${distance}mm`, 'info');
        
        this.sendJogCommand(axis, direction, 'step', distance);
    },

    /**
     * Send jog command to server
     */
    async sendJogCommand(axis, direction, mode, distance = null) {
        try {
            const payload = {
                axis: axis.toLowerCase(),
                direction: direction,
                speed: this.state.currentJogSpeed,
                mode: mode
            };

            if (distance) {
                payload.distance = parseFloat(distance);
            }

            await ScannerBase.apiRequest('/api/jog', {
                method: 'POST',
                body: JSON.stringify(payload)
            });

            // Immediately request updated position after jog command with multiple checks
            // to catch the movement completion reliably
            let checkCount = 0;
            const maxChecks = 10;
            const checkInterval = 200; // Check every 200ms
            
            const checkPosition = async () => {
                checkCount++;
                try {
                    const status = await ScannerBase.apiRequest('/api/status');
                    if (status.motion && status.motion.position) {
                        this.updatePositionDisplays(status.motion.position);
                        
                        // Continue checking for a few more cycles to ensure we catch the final position
                        if (checkCount < maxChecks) {
                            setTimeout(checkPosition, checkInterval);
                        }
                    }
                } catch (error) {
                    // Ignore errors for immediate updates but stop checking
                    ScannerBase.log('Position check failed: ' + error.message);
                }
            };
            
            // Start checking after a brief delay
            setTimeout(checkPosition, 100);

        } catch (error) {
            ScannerBase.showAlert(`Jog command failed: ${error.message}`, 'error');
            this.stopContinuousJog();
        }
    },

    /**
     * Send stop command
     */
    async sendStopCommand() {
        try {
            await ScannerBase.apiRequest('/api/stop', {
                method: 'POST'
            });
        } catch (error) {
            ScannerBase.showAlert(`Stop command failed: ${error.message}`, 'error');
        }
    },

    /**
     * Go to specific position
     */
    async gotoPosition() {
        const x = document.getElementById('gotoX')?.value;
        const y = document.getElementById('gotoY')?.value;
        const z = document.getElementById('gotoZ')?.value;
        const c = document.getElementById('gotoC')?.value;

        if (!x && !y && !z && !c) {
            ScannerBase.showAlert('Please enter at least one coordinate', 'warning');
            return;
        }

        try {
            ScannerBase.showLoading('Moving to position...');
            
            const position = {};
            if (x !== '') position.x = parseFloat(x);
            if (y !== '') position.y = parseFloat(y);
            if (z !== '') position.z = parseFloat(z);
            if (c !== '') position.c = parseFloat(c);

            await ScannerBase.apiRequest('/api/move', {
                method: 'POST',
                body: JSON.stringify({ position })
            });

            ScannerBase.showAlert('Move command sent', 'success');
            ScannerBase.addLogEntry(`Moving to position: ${JSON.stringify(position)}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Move failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Set current position as zero
     */
    async setCurrentPosition() {
        if (!confirm('Set current position as new zero point?')) {
            return;
        }

        try {
            ScannerBase.showLoading('Setting position...');

            await ScannerBase.apiRequest('/api/position/set', {
                method: 'POST',
                body: JSON.stringify({
                    x: 0, y: 0, z: 0, c: 0
                })
            });

            ScannerBase.showAlert('Position set successfully', 'success');
            ScannerBase.addLogEntry('Current position set as zero', 'info');

        } catch (error) {
            ScannerBase.showAlert(`Set position failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Home all axes with real-time progress monitoring
     */
    async homeAllAxes() {
        if (!confirm('Home all axes? This will move all axes to their reference positions.')) {
            return;
        }

        const homeButton = document.querySelector('[onclick*="homeAllAxes"]') || 
                          document.getElementById('homeAllAxes') ||
                          document.querySelector('button[title*="home"]');
        let progressInterval = null;
        let startTime = Date.now();
        
        try {
            // Disable button and show immediate feedback
            if (homeButton) {
                homeButton.disabled = true;
                homeButton.textContent = '🏠 Homing...';
                homeButton.style.opacity = '0.6';
            }

            ScannerBase.showLoading('🏠 Initializing homing sequence...');
            ScannerBase.addLogEntry('🚀 Starting homing sequence for all axes...', 'info');

            // Start the homing request (this returns immediately due to threading)
            const response = await ScannerBase.apiRequest('/api/home', {
                method: 'POST'
            });

            // Don't show immediate confirmation - wait for actual homing detection
            ScannerBase.addLogEntry('⏳ Homing request sent - waiting for FluidNC to start homing sequence...', 'info');

            // Start progress monitoring
            let checkCount = 0;
            let homingDetected = false;
            let homingStartTime = null;
            let initialHomedState = null;
            const maxChecks = 180; // 3 minutes timeout (180 * 1000ms)
            
            progressInterval = setInterval(async () => {
                checkCount++;
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                
                try {
                    // Get current status
                    const status = await ScannerBase.apiRequest('/api/status');
                    
                    // Log current motion status for tracking phases
                    const motionState = status.motion?.status || 'unknown';
                    const fluidncState = status.motion?.fluidnc_status || 'unknown';
                    const isHomed = status.motion?.homed || status.motion?.is_homed || false;
                    
                    // Record initial homed state to detect transitions
                    if (initialHomedState === null) {
                        initialHomedState = isHomed;
                        ScannerBase.addLogEntry(`📋 Initial state: Motion=${motionState}, FluidNC=${fluidncState}, Homed=${isHomed}`, 'info');
                    }
                    
                    // Show detailed status every 5 seconds during active homing
                    if (checkCount % 5 === 0 || homingDetected) {
                        ScannerBase.addLogEntry(`📊 Status: Motion=${motionState}, FluidNC=${fluidncState}, Homed=${isHomed}, Time=${elapsed}s`, 'info');
                    }
                    
                    // Update progress display based on detected phase
                    if (homingDetected) {
                        const homingElapsed = homingStartTime ? Math.round((Date.now() - homingStartTime) / 1000) : 0;
                        if (motionState === 'homing') {
                            ScannerBase.showLoading(`🏠 Physical homing active... (${elapsed}s total, ${homingElapsed}s homing)`);
                        } else if (motionState === 'idle' && !isHomed) {
                            ScannerBase.showLoading(`🔄 Clearing axes and setting coordinates... (${elapsed}s total, ${homingElapsed}s since homing)`);
                        } else if (motionState === 'idle' && isHomed) {
                            ScannerBase.showLoading(`✅ Finalizing homing sequence... (${elapsed}s total, ${homingElapsed}s since homing)`);
                        } else {
                            ScannerBase.showLoading(`🏠 Homing in progress... (${elapsed}s total)`);
                        }
                    } else {
                        ScannerBase.showLoading(`⏳ Waiting for homing to start... (${elapsed}s)`);
                    }
                    
                    // ULTRA-STRICT completion criteria - ALL must be true:
                    // 1. Homing was actually detected (not initial state)
                    // 2. At least 45 seconds since homing was detected (multi-axis takes time)
                    // 3. Motion is idle (NOT <Home|...> state) AND homed
                    // 4. At least 60 seconds total elapsed time (conservative for multi-axis)
                    // 5. State transition from not-homed to homed occurred
                    // 6. NO fluidnc_status indicating active homing
                    const homingElapsed = homingStartTime ? Math.round((Date.now() - homingStartTime) / 1000) : 0;
                    const minimumHomingTime = 45; // seconds since homing detection (increased for multi-axis)
                    const minimumTotalTime = 60; // seconds total (increased for multi-axis)
                    
                    // Additional check: ensure FluidNC is NOT in active homing state
                    const isActivelyHoming = motionState === 'homing' || 
                                           fluidncState === 'Homing' || 
                                           (status.motion?.raw_status && status.motion.raw_status.includes('<Home|'));
                    
                    if (homingDetected && 
                        homingElapsed >= minimumHomingTime && 
                        elapsed >= minimumTotalTime &&
                        status.motion && 
                        motionState === 'idle' &&  // Must be idle, not <Home|...>
                        !isActivelyHoming &&       // Must NOT be actively homing
                        isHomed &&
                        initialHomedState !== null) {
                        
                        // Additional safety check: ensure we had a state transition
                        if (initialHomedState === true && isHomed === true) {
                            ScannerBase.addLogEntry(`⚠️ No state transition detected - may have been already homed. Continuing to monitor...`, 'warning');
                            if (elapsed < 90) { // Give it even more time for multi-axis
                                return;
                            }
                        }
                        
                        // Final validation before completion
                        ScannerBase.addLogEntry(`🔍 Final validation: homingDetected=${homingDetected}, homingElapsed=${homingElapsed}s, totalElapsed=${elapsed}s, motionState=${motionState}, isActivelyHoming=${isActivelyHoming}, isHomed=${isHomed}`, 'info');
                        
                        // Add a delay to ensure coordinates are properly set
                        ScannerBase.showLoading(`✅ All axes homed - finalizing coordinates... (${elapsed}s total)`);
                        
                        // Wait 5 seconds before declaring completion
                        setTimeout(() => {
                            // Homing completed successfully
                            clearInterval(progressInterval);
                            progressInterval = null;
                            
                            ScannerBase.hideLoading();
                            // Use overlay alert only for final success (important message)
                            ScannerBase.showAlert('🎉 All axes homed successfully!', 'success', 5000, false);
                            ScannerBase.addLogEntry(`✅ All axes homing completed successfully in ${elapsed + 5} seconds (${homingElapsed + 5}s since detection)`, 'success');
                            
                            // Re-enable button with original text
                            if (homeButton) {
                                homeButton.disabled = false;
                                homeButton.textContent = homeButton.dataset.originalText || '🏠 Home All';
                                homeButton.style.opacity = '1';
                            }
                            
                            // Update position displays
                            if (status.motion && status.motion.position) {
                                this.updatePositionDisplays(status.motion.position);
                            }
                        }, 5000);
                        return;
                    }
                    
                    // Check if homing is still in progress - look for homing status OR Home state in FluidNC
                    if (status.motion && (status.motion.status === 'homing' || 
                        status.motion.fluidnc_status === 'Homing' ||
                        (status.motion.raw_status && status.motion.raw_status.includes('<Home|')))) {
                        if (!homingDetected) {
                            homingDetected = true;
                            homingStartTime = Date.now(); // Record when homing actually started
                            ScannerBase.addLogEntry(`🔄 Homing sequence started (FluidNC: ${status.motion.fluidnc_status || 'Homing'})`, 'info');
                        }
                        
                        // Log detailed status for debugging
                        ScannerBase.log(`Active homing: state=${status.motion.status}, fluidnc=${status.motion.fluidnc_status}, homed=${status.motion.homed || status.motion.is_homed}, elapsed=${elapsed}s`);
                        return; // Continue monitoring
                    }
                    
                    // Check if we're in coordinate reset phase (idle but not homed yet)
                    if (homingDetected && status.motion && status.motion.status === 'idle' && 
                        !isHomed && elapsed < 90) { // Extended time for coordinate reset
                        const homingElapsed = homingStartTime ? Math.round((Date.now() - homingStartTime) / 1000) : 0;
                        ScannerBase.log(`Coordinate reset phase: state=${status.motion.status}, fluidnc=${status.motion.fluidnc_status}, homed=${isHomed}, homingElapsed=${homingElapsed}s`);
                        return; // Continue monitoring
                    }
                    
                    // Check for errors
                    if (status.motion && status.motion.status === 'error') {
                        throw new Error('Motion controller reported error during homing');
                    }
                    
                    // Update progress every 15 seconds with more detailed logging
                    if (checkCount % 15 === 0) {
                        const phase = homingDetected ? 'coordinate reset/finalizing' : 'waiting for homing to start';
                        ScannerBase.addLogEntry(`⏳ Homing progress: ${phase}... (${elapsed}s elapsed)`, 'info');
                        ScannerBase.log(`Homing status check: motion.status=${status.motion?.status}, fluidnc_status=${status.motion?.fluidnc_status}, homed=${status.motion?.homed || status.motion?.is_homed}, homingDetected=${homingDetected}, phase=${phase}, raw_status=${status.motion?.raw_status?.substring(0,50) || 'none'}`);
                    }
                    
                } catch (statusError) {
                    ScannerBase.log(`Status check error during homing: ${statusError.message}`);
                }
                
                // Timeout check
                if (checkCount >= maxChecks) {
                    clearInterval(progressInterval);
                    progressInterval = null;
                    throw new Error(`Homing timeout after ${elapsed} seconds`);
                }
                
            }, 1000); // Check every second

        } catch (error) {
            // Clean up on error
            if (progressInterval) {
                clearInterval(progressInterval);
                progressInterval = null;
            }
            
            ScannerBase.hideLoading();
            ScannerBase.showAlert(`❌ Homing failed: ${error.message}`, 'error', 8000);
            ScannerBase.addLogEntry(`❌ Homing failed: ${error.message}`, 'error');
            
            // Re-enable button
            if (homeButton) {
                homeButton.disabled = false;
                homeButton.textContent = homeButton.dataset.originalText || '🏠 Home All';
                homeButton.style.opacity = '1';
            }
        }
    },

    /**
     * Stop all motion
     */
    async stopMotion() {
        try {
            await ScannerBase.apiRequest('/api/emergency_stop', {
                method: 'POST'
            });

            ScannerBase.showAlert('Motion stopped', 'warning');
            ScannerBase.addLogEntry('Motion emergency stop executed', 'warning');

        } catch (error) {
            ScannerBase.showAlert(`Stop failed: ${error.message}`, 'error');
        }
    },

    /**
     * Toggle motor enable state
     */
    async toggleMotors() {
        try {
            await ScannerBase.apiRequest('/api/motors/toggle', {
                method: 'POST'
            });

            ScannerBase.addLogEntry('Motor enable state toggled', 'info');

        } catch (error) {
            ScannerBase.showAlert(`Motor toggle failed: ${error.message}`, 'error');
        }
    },

    /**
     * Validate coordinate input
     */
    validateCoordinateInput(input) {
        const value = parseFloat(input.value);
        const min = parseFloat(input.min);
        const max = parseFloat(input.max);

        if (!isNaN(value)) {
            if (!isNaN(min) && value < min) {
                input.value = min;
                ScannerBase.showAlert(`Value limited to minimum: ${min}`, 'warning', 2000);
            } else if (!isNaN(max) && value > max) {
                input.value = max;
                ScannerBase.showAlert(`Value limited to maximum: ${max}`, 'warning', 2000);
            }
        }
    },

    /**
     * Select camera for control
     */
    async selectCamera(cameraId) {
        if (!cameraId) return;

        try {
            await ScannerBase.apiRequest('/api/camera/select', {
                method: 'POST',
                body: JSON.stringify({ camera_id: cameraId })
            });

            ScannerBase.addLogEntry(`Camera ${cameraId} selected`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Camera selection failed: ${error.message}`, 'error');
        }
    },

    /**
     * Capture image with selected camera
     */
    async captureImage() {
        const cameraId = document.getElementById('selectedCamera')?.value;
        if (!cameraId) {
            ScannerBase.showAlert('Please select a camera first', 'warning');
            return;
        }

        try {
            ScannerBase.showLoading('Capturing image...');

            const response = await ScannerBase.apiRequest('/api/camera/capture', {
                method: 'POST',
                body: JSON.stringify({ camera_id: cameraId })
            });

            ScannerBase.showAlert('Image captured successfully', 'success');
            ScannerBase.addLogEntry(`Image captured: ${response.filename}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Capture failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Toggle camera preview
     */
    async togglePreview() {
        const cameraId = document.getElementById('selectedCamera')?.value;
        if (!cameraId) {
            ScannerBase.showAlert('Please select a camera first', 'warning');
            return;
        }

        try {
            await ScannerBase.apiRequest('/api/camera/preview/toggle', {
                method: 'POST',
                body: JSON.stringify({ camera_id: cameraId })
            });

            ScannerBase.addLogEntry(`Preview toggled for camera ${cameraId}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Preview toggle failed: ${error.message}`, 'error');
        }
    },

    /**
     * Update camera setting
     */
    async updateCameraSetting(setting, value) {
        const cameraId = document.getElementById('selectedCamera')?.value;
        if (!cameraId) return;

        try {
            await ScannerBase.apiRequest('/api/camera/settings', {
                method: 'POST',
                body: JSON.stringify({
                    camera_id: cameraId,
                    settings: { [setting]: parseInt(value) }
                })
            });

        } catch (error) {
            ScannerBase.showAlert(`Setting update failed: ${error.message}`, 'error');
        }
    },

    /**
     * Update master lighting intensity
     */
    updateMasterIntensity(intensity) {
        // Clear existing timer
        if (this.state.lightingTimers.has('master')) {
            clearTimeout(this.state.lightingTimers.get('master'));
        }

        // Set new timer for debounced update
        const timer = setTimeout(async () => {
            try {
                await ScannerBase.apiRequest('/api/lighting/master', {
                    method: 'POST',
                    body: JSON.stringify({ intensity: parseInt(intensity) })
                });
            } catch (error) {
                ScannerBase.showAlert(`Lighting update failed: ${error.message}`, 'error');
            }
        }, this.config.lightingUpdateDelay);

        this.state.lightingTimers.set('master', timer);
    },

    /**
     * Update zone intensity
     */
    updateZoneIntensity(zoneId, intensity) {
        // Clear existing timer
        const timerId = `zone${zoneId}`;
        if (this.state.lightingTimers.has(timerId)) {
            clearTimeout(this.state.lightingTimers.get(timerId));
        }

        // Set new timer for debounced update
        const timer = setTimeout(async () => {
            try {
                await ScannerBase.apiRequest('/api/lighting/zone', {
                    method: 'POST',
                    body: JSON.stringify({
                        zone_id: zoneId,
                        intensity: parseInt(intensity)
                    })
                });
            } catch (error) {
                ScannerBase.showAlert(`Zone lighting update failed: ${error.message}`, 'error');
            }
        }, this.config.lightingUpdateDelay);

        this.state.lightingTimers.set(timerId, timer);
    },

    /**
     * Toggle all lights
     */
    async toggleAllLights() {
        try {
            ScannerBase.showLoading('Toggling lights...');

            await ScannerBase.apiRequest('/api/lighting/toggle_all', {
                method: 'POST'
            });

            ScannerBase.addLogEntry('All lights toggled', 'info');

        } catch (error) {
            ScannerBase.showAlert(`Light toggle failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Toggle individual zone
     */
    async toggleZone(zoneId) {
        try {
            await ScannerBase.apiRequest('/api/lighting/zone/toggle', {
                method: 'POST',
                body: JSON.stringify({ zone_id: zoneId })
            });

            ScannerBase.addLogEntry(`Zone ${zoneId} toggled`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Zone toggle failed: ${error.message}`, 'error');
        }
    }
};

// Initialize when the page loads
document.addEventListener('DOMContentLoaded', () => {
    if (typeof ScannerBase !== 'undefined') {
        ManualControl.init();
    }
});

// Simple global functions for onclick handlers in HTML
function jogAxis(axis, distance) {
    console.log(`Jogging ${axis} by ${distance}`);
    
    const data = {
        axis: axis.toLowerCase(),
        direction: distance > 0 ? '+' : '-',
        mode: 'step',
        distance: Math.abs(distance)
    };
    
    fetch('/api/jog', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`${axis} jogged successfully`);
        } else {
            console.error(`Jog failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Jog error:', error);
    });
}

function getStepSize() {
    const stepSelect = document.getElementById('stepSize');
    return parseFloat(stepSelect ? stepSelect.value : 1.0);
}

function homeAxes(axes) {
    console.log(`Homing axes: ${axes}`);
    
    fetch('/api/home', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({axes: axes})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Homing started');
        } else {
            console.error(`Homing failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Homing error:', error);
    });
}

function homeAllAxes() {
    if (ManualControl && ManualControl.homeAllAxes) {
        ManualControl.homeAllAxes();
    } else {
        homeAxes(['x', 'y', 'z', 'c']);
    }
}

function gotoPosition() {
    const x = document.getElementById('targetX')?.value;
    const y = document.getElementById('targetY')?.value;
    const z = document.getElementById('targetZ')?.value;
    const c = document.getElementById('targetC')?.value;
    
    const position = {};
    if (x) position.x = parseFloat(x);
    if (y) position.y = parseFloat(y);
    if (z) position.z = parseFloat(z);
    if (c) position.c = parseFloat(c);
    
    console.log('Going to position:', position);
    
    fetch('/api/position', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(position)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Position command sent');
        } else {
            console.error(`Position move failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Position error:', error);
    });
}

function capturePhoto() {
    console.log('Capturing photo');
    
    fetch('/api/camera/capture', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({camera_id: 'camera_1'})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Photo captured');
        } else {
            console.error(`Capture failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Capture error:', error);
    });
}

function captureFromCamera(cameraId) {
    console.log(`Capturing from camera ${cameraId}`);
    
    fetch('/api/camera/capture', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({camera_id: `camera_${cameraId + 1}`})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log(`Photo captured from camera ${cameraId}`);
        } else {
            console.error(`Capture failed: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Capture error:', error);
    });
}

// Auto-refresh camera preview
document.addEventListener('DOMContentLoaded', function() {
    const cameraImg = document.getElementById('activePreview');
    if (cameraImg) {
        setInterval(() => {
            const timestamp = new Date().getTime();
            const currentSrc = cameraImg.src.split('?')[0];
            cameraImg.src = currentSrc + '?t=' + timestamp;
        }, 5000);
    }
});

// Initialize manual control when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    ScannerBase.init();
    ManualControl.init();
});