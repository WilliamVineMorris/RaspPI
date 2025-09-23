/**
 * Dashboard JavaScript - Main system overview interface
 * 
 * Provides comprehensive system monitoring and quick control functionality
 * with real-time status updates and emergency controls.
 */

// Dashboard-specific functionality
const Dashboard = {
    // Configuration
    config: {
        refreshInterval: 1000,
        chartUpdateInterval: 5000,
        maxDataPoints: 50
    },

    // Data storage for charts
    data: {
        temperature: [],
        system_load: [],
        memory_usage: [],
        scan_progress: []
    },

    /**
     * Initialize dashboard
     */
    init() {
        ScannerBase.log('Initializing dashboard...');
        
        this.setupEventHandlers();
        this.setupQuickActions();
        this.setupControlButtons();
        
        // Listen for status updates
        document.addEventListener('scanner:statusUpdate', (event) => {
            this.handleStatusUpdate(event.detail.status);
        });

        ScannerBase.log('Dashboard initialized');
    },

    /**
     * Setup dashboard-specific event handlers
     */
    setupEventHandlers() {
        // Auto-scroll toggle for activity log
        const autoScrollToggle = document.getElementById('autoScroll');
        if (autoScrollToggle) {
            autoScrollToggle.addEventListener('change', (e) => {
                const logContainer = document.getElementById('activityLog');
                if (e.target.checked && logContainer) {
                    logContainer.scrollTop = logContainer.scrollHeight;
                }
            });
        }

        // Camera feed selection
        const cameraSelects = document.querySelectorAll('.camera-select');
        cameraSelects.forEach(select => {
            select.addEventListener('change', (e) => {
                this.switchCameraFeed(e.target.dataset.feedId, e.target.value);
            });
        });

        // Panel toggle functionality
        this.setupPanelToggles();
    },

    /**
     * Setup panel toggle functionality
     */
    setupPanelToggles() {
        const toggleButtons = document.querySelectorAll('.panel-toggle');
        toggleButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                const panel = e.target.closest('.status-panel');
                const content = panel.querySelector('.panel-content');
                
                if (content.style.display === 'none') {
                    content.style.display = 'block';
                    e.target.textContent = '−';
                } else {
                    content.style.display = 'none';
                    e.target.textContent = '+';
                }
            });
        });
    },

    /**
     * Setup quick action buttons
     */
    setupQuickActions() {
        // Home position button
        const homeButton = document.getElementById('homePosition');
        if (homeButton) {
            // Store original text for restoration after homing
            homeButton.dataset.originalText = homeButton.textContent;
            homeButton.addEventListener('click', () => this.homePosition());
        }

        // Start scan button
        const startScanButton = document.getElementById('startQuickScan');
        if (startScanButton) {
            startScanButton.addEventListener('click', () => this.startQuickScan());
        }

        // Test cameras button
        const testCamerasButton = document.getElementById('testCameras');
        if (testCamerasButton) {
            testCamerasButton.addEventListener('click', () => this.testCameras());
        }

        // Toggle lighting button
        const toggleLightingButton = document.getElementById('toggleLighting');
        if (toggleLightingButton) {
            toggleLightingButton.addEventListener('click', () => this.toggleLighting());
        }
    },

    /**
     * Setup system control buttons
     */
    setupControlButtons() {
        // Initialize system button
        const initButton = document.getElementById('initializeSystem');
        if (initButton) {
            initButton.addEventListener('click', () => this.initializeSystem());
        }

        // Shutdown system button
        const shutdownButton = document.getElementById('shutdownSystem');
        if (shutdownButton) {
            shutdownButton.addEventListener('click', () => this.shutdownSystem());
        }
    },

    /**
     * Handle dashboard-specific status updates
     */
    handleStatusUpdate(status) {
        // Update system metrics
        this.updateSystemMetrics(status);
        
        // Update motion controller status
        this.updateMotionStatus(status);
        
        // Update camera feeds
        this.updateCameraFeeds(status);
        
        // Update scan summary
        this.updateScanSummary(status);
        
        // Update quick action availability
        this.updateQuickActionStates(status);
    },

    /**
     * Update system metrics display
     */
    updateSystemMetrics(status) {
        // Update uptime
        if (status.system?.uptime) {
            const uptimeElement = document.getElementById('systemUptime');
            if (uptimeElement) {
                uptimeElement.textContent = this.formatUptime(status.system.uptime);
            }
        }

        // Update temperature
        if (status.system?.temperature) {
            const tempElement = document.getElementById('systemTemp');
            if (tempElement) {
                tempElement.textContent = `${parseFloat(status.system.temperature).toFixed(1)}°C`;
            }
        }

        // Update memory usage
        if (status.system?.memory) {
            const memElement = document.getElementById('memoryUsage');
            if (memElement) {
                const usedPercent = (status.system.memory.used / status.system.memory.total) * 100;
                memElement.textContent = `${usedPercent.toFixed(1)}%`;
            }
        }

        // Update disk usage
        if (status.system?.disk) {
            const diskElement = document.getElementById('diskUsage');
            if (diskElement) {
                const usedPercent = (status.system.disk.used / status.system.disk.total) * 100;
                diskElement.textContent = `${usedPercent.toFixed(1)}%`;
            }
        }
    },

    /**
     * Update motion controller status display
     */
    updateMotionStatus(status) {
        if (!status.motion) return;

        // Update motion status indicator
        const motionStatusElement = document.getElementById('motionStatus');
        if (motionStatusElement) {
            const isConnected = status.motion.connected;
            motionStatusElement.className = `status-indicator ${isConnected ? 'ready' : 'error'}`;
        }

        // Update connection status
        const connectionElement = document.getElementById('motionConnection');
        if (connectionElement) {
            const connected = status.motion.connected || false;
            connectionElement.textContent = connected ? 'Connected' : 'Disconnected';
            connectionElement.className = `status-value ${connected ? 'connected' : 'disconnected'}`;
        }

        // Update homed status
        const homedElement = document.getElementById('motionHomed');
        if (homedElement) {
            const homed = status.motion.homed || false;
            homedElement.textContent = homed ? 'Yes' : 'No';
            homedElement.className = `status-value ${homed ? 'homed' : 'not-homed'}`;
        }

        // Update position display
        if (status.motion.position) {
            const positionElement = document.getElementById('currentPosition');
            if (positionElement) {
                const pos = status.motion.position;
                positionElement.textContent = `X:${parseFloat(pos.x || 0).toFixed(1)} Y:${parseFloat(pos.y || 0).toFixed(1)} Z:${parseFloat(pos.z || 0).toFixed(1)} C:${parseFloat(pos.c || 0).toFixed(1)}`;
            }
        }

        // Update state
        const stateElement = document.getElementById('motionState');
        if (stateElement) {
            const state = status.motion.status || 'unknown';
            stateElement.textContent = this.formatMotionState(state);
        }

        // Update activity
        const activityElement = document.getElementById('motionActivity');
        if (activityElement) {
            const activity = status.motion.activity || 'idle';
            activityElement.textContent = this.formatMotionActivity(activity);
            activityElement.className = `status-value ${this.getActivityClass(activity)}`;
        }

        // Update FluidNC status
        const fluidncElement = document.getElementById('fluidncStatus');
        if (fluidncElement) {
            const fluidncStatus = status.motion.fluidnc_status || 'Unknown';
            fluidncElement.textContent = fluidncStatus;
            
            // Color code FluidNC status
            let statusClass = 'idle';
            switch(fluidncStatus.toLowerCase()) {
                case 'idle': statusClass = 'idle'; break;
                case 'run':
                case 'jogging': statusClass = 'busy'; break;
                case 'homing': statusClass = 'busy'; break;
                case 'alarm':
                case 'error': statusClass = 'error'; break;
                default: statusClass = 'idle';
            }
            fluidncElement.className = `status-value ${statusClass}`;
        }
    },

    /**
     * Format motion state for display
     */
    formatMotionState(state) {
        const stateMap = {
            'idle': 'Idle',
            'busy': 'Busy',
            'homing': 'Homing',
            'error': 'Error',
            'alarm': 'Alarm',
            'unknown': 'Unknown'
        };
        return stateMap[state] || state;
    },

    /**
     * Format motion activity for display
     */
    formatMotionActivity(activity) {
        const activityMap = {
            'idle': 'Idle',
            'homing': 'Homing',
            'moving': 'Moving',
            'positioning': 'Positioning',
            'unknown': 'Unknown'
        };
        return activityMap[activity] || activity;
    },

    /**
     * Get CSS class for activity status
     */
    getActivityClass(activity) {
        switch(activity) {
            case 'idle': return 'idle';
            case 'homing':
            case 'moving':
            case 'positioning': return 'busy';
            case 'error': return 'error';
            default: return 'idle';
        }
    },

    /**
     * Update camera feed displays
     */
    updateCameraFeeds(status) {
        if (!status.cameras) return;

        // Update camera availability in selects
        const cameraSelects = document.querySelectorAll('.camera-select');
        cameraSelects.forEach(select => {
            // Clear existing options except "Select Camera"
            const defaultOption = select.querySelector('option[value=""]');
            select.innerHTML = '';
            if (defaultOption) {
                select.appendChild(defaultOption);
            } else {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'Select Camera';
                select.appendChild(option);
            }

            // Add available cameras
            if (status.cameras.available_cameras) {
                status.cameras.available_cameras.forEach(camera => {
                    const option = document.createElement('option');
                    option.value = camera.id;
                    option.textContent = `Camera ${camera.id} (${camera.resolution})`;
                    select.appendChild(option);
                });
            }
        });

        // Update feed status indicators
        const feedContainers = document.querySelectorAll('.camera-feed');
        feedContainers.forEach(container => {
            const statusElement = container.querySelector('.feed-status');
            if (statusElement) {
                const isActive = status.cameras.active?.length > 0;
                statusElement.textContent = isActive ? 'Active' : 'Inactive';
                statusElement.className = `feed-status ${isActive ? 'active' : 'inactive'}`;
            }
        });
    },

    /**
     * Update scan summary display
     */
    updateScanSummary(status) {
        if (!status.scan) return;

        // Update scan count
        const scanCountElement = document.getElementById('totalScans');
        if (scanCountElement) {
            scanCountElement.textContent = status.scan.total_scans || 0;
        }

        // Update completed scans
        const completedElement = document.getElementById('completedScans');
        if (completedElement) {
            completedElement.textContent = status.scan.completed_scans || 0;
        }

        // Update scan time
        const scanTimeElement = document.getElementById('scanTime');
        if (scanTimeElement && status.scan.estimated_time) {
            scanTimeElement.textContent = this.formatDuration(status.scan.estimated_time);
        }

        // Update current scan status
        const currentScanElement = document.getElementById('currentScanStatus');
        if (currentScanElement) {
            if (status.scan.active) {
                currentScanElement.textContent = `Running - ${status.scan.phase || 'Processing'}`;
                currentScanElement.className = 'scan-status running';
            } else {
                currentScanElement.textContent = 'Idle';
                currentScanElement.className = 'scan-status idle';
            }
        }
    },

    /**
     * Update quick action button states
     */
    updateQuickActionStates(status) {
        // Home position button
        const homeButton = document.getElementById('homePosition');
        if (homeButton) {
            const canHome = status.motion?.connected && !status.scan?.active;
            homeButton.disabled = !canHome;
            homeButton.title = canHome ? 'Move all axes to home position' : 'Motion system not ready or scan active';
        }

        // Start scan button
        const startScanButton = document.getElementById('startQuickScan');
        if (startScanButton) {
            const canScan = status.motion?.connected && status.cameras?.available > 0 && !status.scan?.active;
            startScanButton.disabled = !canScan;
            startScanButton.title = canScan ? 'Start a quick test scan' : 'System not ready for scanning';
        }

        // Test cameras button
        const testCamerasButton = document.getElementById('testCameras');
        if (testCamerasButton) {
            const canTest = status.cameras?.available > 0 && !status.scan?.active;
            testCamerasButton.disabled = !canTest;
            testCamerasButton.title = canTest ? 'Test camera capture' : 'No cameras available or scan active';
        }

        // Toggle lighting button
        const toggleLightingButton = document.getElementById('toggleLighting');
        if (toggleLightingButton) {
            const canToggle = status.lighting?.zones?.length > 0;
            toggleLightingButton.disabled = !canToggle;
            
            if (canToggle) {
                const allZonesOn = status.lighting.zones.every(zone => zone.intensity > 0);
                toggleLightingButton.textContent = allZonesOn ? 'Turn Off Lights' : 'Turn On Lights';
                toggleLightingButton.title = allZonesOn ? 'Turn off all lighting zones' : 'Turn on all lighting zones';
            } else {
                toggleLightingButton.textContent = 'Toggle Lighting';
                toggleLightingButton.title = 'Lighting system not available';
            }
        }
    },

    /**
     * Switch camera feed
     */
    async switchCameraFeed(feedId, cameraId) {
        if (!cameraId) return;

        try {
            ScannerBase.showLoading('Switching camera feed...');
            
            const response = await ScannerBase.apiRequest('/api/camera/stream', {
                method: 'POST',
                body: JSON.stringify({
                    camera_id: cameraId,
                    feed_id: feedId
                })
            });

            // Update feed URL
            const feedElement = document.getElementById(feedId);
            if (feedElement) {
                feedElement.src = `/video_feed/${cameraId}`;
            }

            ScannerBase.showAlert(`Camera ${cameraId} feed activated`, 'success', 3000);
            ScannerBase.addLogEntry(`Camera feed switched to Camera ${cameraId}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Failed to switch camera feed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Camera feed switch failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Home all axes to reference position with real-time progress monitoring
     */
    async homePosition() {
        const homeButton = document.getElementById('homePosition');
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
            ScannerBase.showAlert('🏠 Homing sequence started - please wait...', 'info', 3000);

            // Start the homing request (this returns immediately due to threading)
            const response = await ScannerBase.apiRequest('/api/home', {
                method: 'POST'
            });

            // Show immediate confirmation that homing started
            ScannerBase.addLogEntry('✅ Homing request sent - monitoring progress...', 'success');
            ScannerBase.showAlert('⚡ Homing in progress - monitoring status...', 'info', 2000);

            // Start progress monitoring
            let checkCount = 0;
            let homingDetected = false;
            const maxChecks = 120; // 2 minutes timeout (120 * 1000ms)
            
            progressInterval = setInterval(async () => {
                checkCount++;
                const elapsed = Math.round((Date.now() - startTime) / 1000);
                
                try {
                    // Get current status
                    const status = await ScannerBase.apiRequest('/api/status');
                    
                    // Update progress display
                    ScannerBase.showLoading(`🏠 Homing in progress... (${elapsed}s)`);
                    
                    // Check if homing is complete - need MINIMUM TIME + idle status + homed flag
                    // Prevent premature completion detection by requiring at least 15 seconds
                    const minimumHomingTime = 15; // seconds
                    const isHomed = status.motion.homed || status.motion.is_homed || false;
                    if (status.motion && status.motion.status === 'idle' && isHomed && elapsed >= minimumHomingTime) {
                        // Additional validation: ensure we've detected active homing before completion
                        if (!homingDetected) {
                            ScannerBase.addLogEntry(`⚠️ Premature completion detected (${elapsed}s) - waiting for actual homing sequence...`, 'warning');
                            return; // Continue monitoring
                        }
                        
                        // Add a small delay to ensure coordinates are properly set
                        ScannerBase.showLoading(`✅ Homing complete - finalizing coordinates... (${elapsed}s)`);
                        
                        // Wait 2 seconds before declaring completion
                        setTimeout(() => {
                            // Homing completed successfully
                            clearInterval(progressInterval);
                            progressInterval = null;
                            
                            ScannerBase.hideLoading();
                            ScannerBase.showAlert('🎉 All axes homed successfully!', 'success', 5000);
                            ScannerBase.addLogEntry(`✅ Homing completed successfully in ${elapsed + 2} seconds`, 'success');
                            
                            // Re-enable button
                            if (homeButton) {
                                homeButton.disabled = false;
                                homeButton.textContent = homeButton.dataset.originalText || '🏠 Home All';
                                homeButton.style.opacity = '1';
                            }
                        }, 2000);
                        return;
                    }
                    
                    // Check if homing is still in progress - look for homing status OR Home state in FluidNC
                    if (status.motion && (status.motion.status === 'homing' || 
                        status.motion.fluidnc_status === 'Homing' ||
                        (status.motion.raw_status && status.motion.raw_status.includes('<Home|')))) {
                        if (!homingDetected) {
                            homingDetected = true;
                            ScannerBase.addLogEntry(`🔄 Homing sequence detected (FluidNC: ${status.motion.fluidnc_status || 'Unknown'})`, 'info');
                            ScannerBase.showAlert('⚡ Physical homing in progress...', 'info', 2000);
                        }
                        ScannerBase.showLoading(`🏠 Physical homing in progress... (${elapsed}s)`);
                        
                        // Log detailed status for debugging
                        ScannerBase.log(`Active homing: state=${status.motion.status}, fluidnc=${status.motion.fluidnc_status}, homed=${status.motion.homed || status.motion.is_homed}, elapsed=${elapsed}s`);
                        return; // Continue monitoring
                    }
                    
                    // Check if we're in coordinate reset phase (idle but not homed yet)
                    if (homingDetected && status.motion && status.motion.status === 'idle' && 
                        !(status.motion.homed || status.motion.is_homed) && elapsed < minimumHomingTime) {
                        ScannerBase.showLoading(`🔄 Resetting coordinates... (${elapsed}s)`);
                        ScannerBase.log(`Coordinate reset phase: state=${status.motion.status}, fluidnc=${status.motion.fluidnc_status}, homed=${status.motion.homed || status.motion.is_homed}, elapsed=${elapsed}s`);
                        return; // Continue monitoring
                    }
                    
                    // Check for errors
                    if (status.motion && status.motion.status === 'error') {
                        throw new Error('Motion controller reported error during homing');
                    }
                    
                    // Update progress every 10 seconds with more detailed logging
                    if (checkCount % 10 === 0) {
                        const phase = homingDetected ? 'coordinate reset' : 'waiting for homing start';
                        ScannerBase.addLogEntry(`⏳ Homing process: ${phase}... (${elapsed}s elapsed)`, 'info');
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
                homeButton.textContent = homeButton.dataset.originalText || '🏠 Home Position';
                homeButton.style.opacity = '1';
            }
        }
    },

    /**
     * Start a quick test scan
     */
    async startQuickScan() {
        try {
            ScannerBase.showLoading('Starting quick scan...');
            ScannerBase.addLogEntry('Initiating quick test scan...', 'info');

            const response = await ScannerBase.apiRequest('/api/scan/quick', {
                method: 'POST',
                body: JSON.stringify({
                    scan_type: 'test',
                    points: 10,
                    speed: 'fast'
                })
            });

            ScannerBase.showAlert('Quick scan started', 'success');
            ScannerBase.addLogEntry(`Quick scan started - ID: ${response.scan_id}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Failed to start scan: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Quick scan failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Test camera capture
     */
    async testCameras() {
        try {
            ScannerBase.showLoading('Testing cameras...');
            ScannerBase.addLogEntry('Testing camera capture...', 'info');

            const response = await ScannerBase.apiRequest('/api/camera/test', {
                method: 'POST'
            });

            ScannerBase.showAlert(`Camera test completed - ${response.cameras_tested} cameras tested`, 'success');
            ScannerBase.addLogEntry(`Camera test completed: ${response.results}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Camera test failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Camera test failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Toggle all lighting zones
     */
    async toggleLighting() {
        try {
            ScannerBase.showLoading('Toggling lighting...');
            ScannerBase.addLogEntry('Toggling lighting zones...', 'info');

            const response = await ScannerBase.apiRequest('/api/lighting/toggle', {
                method: 'POST'
            });

            const action = response.all_zones_on ? 'on' : 'off';
            ScannerBase.showAlert(`All lighting zones turned ${action}`, 'success');
            ScannerBase.addLogEntry(`Lighting zones turned ${action}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Lighting toggle failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Lighting toggle failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Initialize system components
     */
    async initializeSystem() {
        if (!confirm('Initialize all system components? This may take several minutes.')) {
            return;
        }

        try {
            ScannerBase.showLoading('Initializing system...');
            ScannerBase.addLogEntry('System initialization started...', 'info');

            const response = await ScannerBase.apiRequest('/api/system/initialize', {
                method: 'POST'
            });

            ScannerBase.showAlert('System initialization completed', 'success');
            ScannerBase.addLogEntry('System initialization completed successfully', 'success');

        } catch (error) {
            ScannerBase.showAlert(`System initialization failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`System initialization failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Shutdown system safely
     */
    async shutdownSystem() {
        if (!confirm('Shutdown the scanner system? This will stop all operations and power down the system.')) {
            return;
        }

        try {
            ScannerBase.showLoading('Shutting down system...');
            ScannerBase.addLogEntry('System shutdown initiated...', 'warning');

            const response = await ScannerBase.apiRequest('/api/system/shutdown', {
                method: 'POST'
            });

            ScannerBase.showAlert('System shutdown initiated', 'warning');
            ScannerBase.addLogEntry('System shutdown completed', 'warning');

        } catch (error) {
            ScannerBase.showAlert(`Shutdown failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Shutdown failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Format uptime string
     */
    formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) {
            return `${days}d ${hours}h ${minutes}m`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    },

    /**
     * Format duration string
     */
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        } else {
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        }
    }
};

// Make Dashboard available globally
window.Dashboard = Dashboard;