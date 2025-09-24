/**
 * Scanner Base JavaScript - Core functionality for all pages
 * 
 * Provides robust command/data transfer between web UI and Python backend
 * with comprehensive error handling and real-time updates.
 */

// Global scanner base object
window.ScannerBase = {
    // Configuration
    config: {
        updateInterval: 1000,           // Base status update interval (ms) - faster for better responsiveness
        fastUpdateInterval: 250,        // Fast update interval (ms) - much faster during movement
        requestTimeout: 2000,           // API request timeout (ms) - faster failure detection for web UI responsiveness
        showDebugLogs: true,            // Enable debug logging to troubleshoot position delays
        debug: true                     // Master debug flag for position debugging
    },

    // State management
    state: {
        connected: false,
        systemStatus: null,
        lastUpdate: null,
        pendingRequests: new Map(),
        isMoving: false,                // Track if system is currently moving
        fastPolling: false              // Track if we're in fast polling mode
    },

    // Polling interval reference
    pollingInterval: null,

    /**
     * Initialize the scanner base functionality
     */
    init() {
        this.log('Initializing scanner base...');
        this.setupHttpPolling();
        this.setupEventHandlers();
        this.startStatusUpdater();
        this.log('Scanner base initialized');
    },

    /**
     * Setup HTTP polling for status updates (replacing WebSocket)
     */
    setupHttpPolling() {
        try {
            this.log('Setting up smart HTTP polling...');
            this.state.connected = true;
            this.updateConnectionStatus(true);
            
            // Start polling immediately
            this.pollStatus();
            
            // Set up adaptive polling that adjusts based on system state
            this.startAdaptivePolling();
            
            this.log('Smart HTTP polling established');
        } catch (error) {
            this.log('Error setting up HTTP polling:', error);
            this.showAlert('Failed to establish connection', 'error');
        }
    },

    /**
     * Start adaptive polling that switches between fast and slow based on system state
     */
    startAdaptivePolling() {
        const setupPolling = () => {
            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
            }

            const interval = this.state.fastPolling ? 
                this.config.fastUpdateInterval : 
                this.config.updateInterval;

            this.pollingInterval = setInterval(() => {
                this.pollStatus();
            }, interval);

            this.log(`Polling interval set to ${interval}ms (${this.state.fastPolling ? 'fast' : 'slow'} mode)`);
        };

        // Initial setup
        setupPolling();

        // Monitor for state changes that require polling speed adjustment
        setInterval(() => {
            const shouldUseFastPolling = this.shouldUseFastPolling();
            if (shouldUseFastPolling !== this.state.fastPolling) {
                this.state.fastPolling = shouldUseFastPolling;
                setupPolling();
            }
        }, 1000); // Check every second for state changes
    },

    /**
     * Determine if fast polling should be used based on system state
     */
    shouldUseFastPolling() {
        // Use fast polling if:
        // 1. System is moving
        // 2. Recent jog command (within last 10 seconds)
        // 3. Manual control page is active
        
        const recentJog = this.state.lastJogTime && 
                         (Date.now() - this.state.lastJogTime) < 10000;
        
        const onManualPage = window.location.pathname === '/manual';
        
        const systemMoving = this.state.systemStatus && 
                           this.state.systemStatus.motion && 
                           this.state.systemStatus.motion.status === 'MOVING';

        return systemMoving || recentJog || onManualPage;
    },

    /**
     * Poll for status updates via HTTP with request queuing prevention
     */
    pollStatus() {
        if (document.hidden) {
            // Skip polling when page is not visible
            return;
        }
        
        // Prevent request queuing - skip if a status request is already pending
        if (this.state.pendingRequests.has('status')) {
            this.log('Skipping status poll - request already pending');
            return;
        }
        
        // Mark status request as pending
        this.state.pendingRequests.set('status', true);
        
        this.apiRequest('/api/status')
            .then(response => {
                // Extract the data from the API response
                const status = response.data || response;
                this.handleStatusUpdate(status);
                
                // Determine system connection based on motion controller status
                const motionConnected = Boolean(status.motion?.connected);
                const systemConnected = motionConnected; // Base system connection on motion controller
                
                if (systemConnected !== this.state.connected) {
                    this.state.connected = systemConnected;
                    this.updateConnectionStatus(systemConnected);
                }
            })
            .catch(error => {
                this.log('Polling error:', error);
                if (this.state.connected) {
                    this.state.connected = false;
                    this.updateConnectionStatus(false);
                }
            })
            .finally(() => {
                // Always clear the pending request flag
                this.state.pendingRequests.delete('status');
            });
    },

    /**
     * Setup global event handlers
     */
    setupEventHandlers() {
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.log('Page visible, resuming polling...');
                this.pollStatus();
            }
        });

        // Handle online/offline status
        window.addEventListener('online', () => {
            this.log('Network online, resuming polling...');
            this.pollStatus();
        });

        window.addEventListener('offline', () => {
            this.log('Network offline');
            this.showAlert('Network connection lost', 'warning');
        });

        // Handle beforeunload to cleanup
        window.addEventListener('beforeunload', () => {
            if (this.pollingInterval) {
                clearInterval(this.pollingInterval);
            }
        });
    },

    /**
     * Start periodic status updates - REMOVED obsolete WebSocket polling
     * 
     * This method is kept for compatibility but does nothing since we now use HTTP polling
     * exclusively. All status updates are handled by setupHttpPolling().
     */
    startStatusUpdater() {
        // Obsolete WebSocket polling removed - HTTP polling handles all updates
        this.log('Status updater called - using HTTP polling instead');
    },

    /**
     * Handle status updates from server
     */
    handleStatusUpdate(status) {
        this.state.systemStatus = status;
        this.state.lastUpdate = new Date();
        
        // Log position data age for debugging
        if (status.motion && status.motion.position && status.motion.data_age !== undefined) {
            this.log(`Position update: ${JSON.stringify(status.motion.position)}, data age: ${status.motion.data_age}s`);
        }
        
        // Update UI elements
        this.updateSystemStatus(status);
        this.updateFooterTimestamp();
        
        // Trigger custom event for page-specific handling
        this.dispatchEvent('statusUpdate', { status });
    },

    /**
     * Update connection status in UI
     */
    updateConnectionStatus(connected) {
        const statusDot = document.getElementById('statusDot');
        const statusText = document.getElementById('statusText');
        
        if (statusDot && statusText) {
            if (connected) {
                statusDot.className = 'status-dot ready';
                statusText.textContent = 'Connected';
            } else {
                statusDot.className = 'status-dot error';
                statusText.textContent = 'Disconnected';
            }
        }
    },

    /**
     * Update system status in UI
     */
    updateSystemStatus(status) {
        // Only log status updates in debug mode or when there are errors
        if (this.config.debug || status.system?.errors?.length > 0) {
            console.log('System status update:', status);
        }
        
        // Extract the data object from the API response
        const data = status.data || status;
        
        // Step by step boolean evaluation
        const motionConnected = data.motion?.connected;
        const camerasAvailable = data.cameras?.available;
        
        // More robust boolean checks
        const motionReady = Boolean(motionConnected);
        const cameraReady = Boolean(camerasAvailable) && Number(camerasAvailable) > 0;
        const lightingReady = Boolean(data.lighting?.zones?.length) && data.lighting.zones.length > 0;
        const scanActive = Boolean(data.scan?.active);
        
        // Only log ready states in debug mode
        if (this.config.debug) {
            console.log('Ready states:', { motionReady, cameraReady, lightingReady, scanActive });
        }
        
        // Update main status indicators
        this.updateStatusIndicator('motionStatus', motionReady, data.motion?.status);
        this.updateStatusIndicator('cameraStatus', cameraReady, data.cameras?.status);
        this.updateStatusIndicator('lightingStatus', lightingReady, data.lighting?.status);
        this.updateStatusIndicator('scanStatus', scanActive, data.scan?.status);

        // Update position display
        if (data.motion?.position) {
            this.updatePosition(data.motion.position);
        }

        // Update scan progress
        if (data.scan) {
            this.updateScanProgress(data.scan);
        }

        // Update detailed status
        this.updateDetailedStatus(data);
        
        // Dispatch status update event for Dashboard and other listeners
        const statusEvent = new CustomEvent('scanner:statusUpdate', {
            detail: { status: data }
        });
        document.dispatchEvent(statusEvent);
        
        // Only log dispatch in debug mode
        if (this.config.debug) {
            console.log('Dispatched scanner:statusUpdate event');
        }
    },

    /**
     * Update individual status indicator
     */
    updateStatusIndicator(elementId, isReady, statusText) {
        const element = document.getElementById(elementId);
        if (element) {
            const newClassName = `status-indicator ${isReady ? 'ready' : 'error'}`;
            element.className = newClassName;
            
            // Only log in debug mode
            if (this.config.debug) {
                console.log(`Updated ${elementId}: ${newClassName}`);
            }
        }

        const textElement = document.getElementById(elementId.replace('Status', 'State'));
        if (textElement) {
            textElement.textContent = statusText || 'Unknown';
        }
    },

    /**
     * Update position display
     */
    updatePosition(position) {
        const positions = ['X', 'Y', 'Z', 'C'];
        const axes = ['x', 'y', 'z', 'c'];
        
        axes.forEach((axis, index) => {
            const element = document.getElementById(`current${positions[index]}`);
            if (element && position[axis] !== undefined) {
                element.textContent = parseFloat(position[axis]).toFixed(1);
            }
        });

        // Update combined position display
        const positionElement = document.getElementById('currentPosition');
        if (positionElement && position) {
            positionElement.textContent = 
                `X:${parseFloat(position.x || 0).toFixed(1)} ` +
                `Y:${parseFloat(position.y || 0).toFixed(1)} ` +
                `Z:${parseFloat(position.z || 0).toFixed(1)} ` +
                `C:${parseFloat(position.c || 0).toFixed(1)}`;
        }
    },

    /**
     * Update scan progress display
     */
    updateScanProgress(scan) {
        const progressElement = document.getElementById('scanProgress');
        if (progressElement) {
            progressElement.textContent = `${parseFloat(scan.progress || 0).toFixed(1)}%`;
        }

        const pointsElement = document.getElementById('scanPoints');
        if (pointsElement) {
            pointsElement.textContent = `${scan.current_point || 0}/${scan.total_points || 0}`;
        }

        const phaseElement = document.getElementById('scanPhase');
        if (phaseElement) {
            phaseElement.textContent = scan.phase || 'Idle';
        }
    },

    /**
     * Update detailed status displays
     */
    updateDetailedStatus(data) {
        // Motion details
        const motionDetails = document.getElementById('motionDetails');
        if (motionDetails && data.motion) {
            motionDetails.innerHTML = `
                <div>Connection: <span id="motionConnection" class="status-value">${data.motion.connected ? 'Connected' : 'Disconnected'}</span></div>
                <div>Homed: <span id="motionHomed" class="status-value">${data.motion.homed ? 'Yes' : 'No'}</span></div>
                <div>Position: <span id="currentPosition">X:${parseFloat(data.motion.position?.x || 0).toFixed(1)} Y:${parseFloat(data.motion.position?.y || 0).toFixed(1)} Z:${parseFloat(data.motion.position?.z || 0).toFixed(1)} C:${parseFloat(data.motion.position?.c || 0).toFixed(1)}</span></div>
                <div>State: <span id="motionState">${data.motion.status || 'Unknown'}</span></div>
                <div>Activity: <span id="motionActivity" class="status-value">${data.motion.activity || 'idle'}</span></div>
                <div>FluidNC: <span id="fluidncStatus" class="status-value">${data.motion.fluidnc_status || 'Unknown'}</span></div>
            `;
        }

        // Camera details
        const cameraDetails = document.getElementById('cameraDetails');
        if (cameraDetails && data.cameras) {
            cameraDetails.innerHTML = `
                <div>Available: <span id="cameraCount">${data.cameras.available || 0}</span></div>
                <div>Active: <span id="activeCameras">${data.cameras.active?.join(', ') || 'None'}</span></div>
                <div>State: <span id="cameraState">${data.cameras.status || 'Unknown'}</span></div>
            `;
        }

        // Lighting details
        const lightingDetails = document.getElementById('lightingDetails');
        if (lightingDetails && data.lighting) {
            lightingDetails.innerHTML = `
                <div>Zones: <span id="lightingZones">${data.lighting.zones?.length || 0}</span></div>
                <div>Status: <span id="lightingState">${data.lighting.status || 'Unknown'}</span></div>
            `;
        }

        // Scan details
        const scanDetails = document.getElementById('scanDetails');
        if (scanDetails && data.scan) {
            scanDetails.innerHTML = `
                <div>Progress: <span id="scanProgress">${parseFloat(data.scan.progress || 0).toFixed(1)}%</span></div>
                <div>Points: <span id="scanPoints">${data.scan.current_point || 0}/${data.scan.total_points || 0}</span></div>
                <div>Phase: <span id="scanPhase">${data.scan.phase || 'Idle'}</span></div>
                <div>State: <span id="scanState">${data.scan.status || 'Unknown'}</span></div>
            `;
        }
    },

    /**
     * Update footer timestamp
     */
    updateFooterTimestamp() {
        const lastUpdateElement = document.getElementById('lastUpdate');
        if (lastUpdateElement && this.state.lastUpdate) {
            lastUpdateElement.textContent = `Last update: ${this.state.lastUpdate.toLocaleTimeString()}`;
        }

        const footerStatusElement = document.getElementById('footerStatus');
        if (footerStatusElement) {
            footerStatusElement.textContent = this.state.connected ? 'Connected' : 'Disconnected';
        }
    },

    /**
     * Make robust API request with timeout and error handling
     */
    async apiRequest(endpoint, options = {}) {
        const requestId = this.generateRequestId();
        
        try {
            this.log(`API Request [${requestId}]: ${options.method || 'GET'} ${endpoint}`);
            
            // Setup request options with timeout
            const requestOptions = {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Request-ID': requestId
                },
                ...options
            };

            // Add request to pending requests
            const controller = new AbortController();
            requestOptions.signal = controller.signal;
            
            const timeoutId = setTimeout(() => {
                controller.abort();
            }, this.config.requestTimeout);

            this.state.pendingRequests.set(requestId, { controller, timeoutId });

            // Make the request
            const response = await fetch(endpoint, requestOptions);
            
            // Clear timeout and remove from pending
            clearTimeout(timeoutId);
            this.state.pendingRequests.delete(requestId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            this.log(`API Response [${requestId}]:`, data);

            if (!data.success) {
                throw new Error(data.error || 'API request failed');
            }

            return data;

        } catch (error) {
            // Clean up pending request
            const pendingRequest = this.state.pendingRequests.get(requestId);
            if (pendingRequest) {
                clearTimeout(pendingRequest.timeoutId);
                this.state.pendingRequests.delete(requestId);
            }

            this.log(`API Error [${requestId}]:`, error);
            
            if (error.name === 'AbortError') {
                throw new Error('Request timeout - please check your connection');
            }
            
            throw error;
        }
    },

    /**
     * Generate unique request ID
     */
    generateRequestId() {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    },

    /**
     * Show alert message to user with improved placement options
     */
    showAlert(message, type = 'info', duration = 5000, useLogOnly = false) {
        // For non-critical messages, just use the activity log to avoid UI displacement
        if (useLogOnly || type === 'info') {
            this.addLogEntry(message, type);
            return;
        }

        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) {
            // Fallback to activity log if no alert container
            this.addLogEntry(message, type);
            return;
        }

        const alertId = `alert_${Date.now()}_${Math.random().toString(36).substr(2, 5)}`;
        const alertElement = document.createElement('div');
        alertElement.id = alertId;
        alertElement.className = `floating-alert ${type}`;
        
        alertElement.innerHTML = `
            <div class="alert-content">${message}</div>
            <button class="alert-close" onclick="ScannerBase.dismissAlert('${alertId}')" title="Close">×</button>
        `;

        // Add to container at the beginning (newest on top)
        if (alertContainer.firstChild) {
            alertContainer.insertBefore(alertElement, alertContainer.firstChild);
        } else {
            alertContainer.appendChild(alertElement);
        }
        
        // Force reflow and animate in
        requestAnimationFrame(() => {
            alertElement.classList.add('show');
        });

        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                this.dismissAlert(alertId);
            }, duration);
        }

        // Manage alert limit (max 5 alerts)
        this.manageAlertLimit();
    },

    /**
     * Manage maximum number of alerts to prevent screen overflow
     */
    manageAlertLimit() {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;

        const alerts = alertContainer.querySelectorAll('.floating-alert');
        const maxAlerts = 5;
        
        // Remove oldest alerts if we exceed the limit
        if (alerts.length > maxAlerts) {
            for (let i = maxAlerts; i < alerts.length; i++) {
                this.dismissAlert(alerts[i].id);
            }
        }
    },

    /**
     * Dismiss alert by ID with animation
     */
    dismissAlert(alertId) {
        const alertElement = document.getElementById(alertId);
        if (alertElement) {
            // Animate out
            alertElement.style.transform = 'translateX(100%)';
            alertElement.style.opacity = '0';
            
            // Remove from DOM after animation
            setTimeout(() => {
                if (alertElement.parentNode) {
                    alertElement.parentNode.removeChild(alertElement);
                }
            }, 300);
        }
    },

    /**
     * Clear all alerts
     */
    clearAlerts() {
        const alertContainer = document.getElementById('alertContainer');
        if (alertContainer) {
            alertContainer.innerHTML = '';
        }
    },

    /**
     * Show loading overlay
     */
    showLoading(message = 'Processing...') {
        const loadingOverlay = document.getElementById('loadingOverlay');
        const loadingText = loadingOverlay?.querySelector('.loading-text');
        
        if (loadingOverlay) {
            if (loadingText) {
                loadingText.textContent = message;
            }
            loadingOverlay.style.display = 'flex';
        }
    },

    /**
     * Hide loading overlay
     */
    hideLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    },

    /**
     * Dispatch custom event
     */
    dispatchEvent(eventName, detail = {}) {
        const event = new CustomEvent(`scanner:${eventName}`, { detail });
        document.dispatchEvent(event);
    },

    /**
     * Log message (with debug control)
     */
    log(...args) {
        if (this.config.showDebugLogs || args[0]?.includes('Error') || args[0]?.includes('Failed')) {
            console.log('[ScannerBase]', ...args);
        }
    },

    /**
     * Add activity log entry
     */
    addLogEntry(message, type = 'info') {
        const logContainer = document.getElementById('activityLog');
        if (!logContainer) return;

        const timestamp = new Date().toLocaleTimeString();
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${type}`;
        logEntry.innerHTML = `
            <span class="log-timestamp">${timestamp}</span>
            <span class="log-message">${message}</span>
        `;

        logContainer.appendChild(logEntry);

        // Auto-scroll if enabled
        const autoScroll = document.getElementById('autoScroll');
        if (autoScroll?.checked) {
            logContainer.scrollTop = logContainer.scrollHeight;
        }

        // Limit log entries (keep last 100)
        const entries = logContainer.children;
        if (entries.length > 100) {
            entries[0].remove();
        }
    }
};

// Global utility functions
window.emergencyStop = async function() {
    try {
        ScannerBase.showLoading('Emergency stop...');
        ScannerBase.addLogEntry('🚨 Emergency stop initiated', 'warning');
        
        const response = await ScannerBase.apiRequest('/api/emergency_stop', {
            method: 'POST'
        });
        
        // Show overlay alert for emergency stop (critical message)
        ScannerBase.showAlert('🚨 Emergency stop executed', 'warning', 5000, false);
        ScannerBase.addLogEntry('✅ Emergency stop completed successfully', 'warning');
        
    } catch (error) {
        ScannerBase.showAlert(`🚨 Emergency stop failed: ${error.message}`, 'error', 7000, false);
        ScannerBase.addLogEntry(`❌ Emergency stop failed: ${error.message}`, 'error');
    } finally {
        ScannerBase.hideLoading();
    }
};

window.refreshStatus = async function() {
    try {
        ScannerBase.log('Manual status refresh requested');
        
        // Show loading feedback in activity log (non-intrusive)
        ScannerBase.addLogEntry('🔄 Refreshing system status...', 'info');
        
        // Perform the actual refresh and wait for completion
        await ScannerBase.pollStatus();
        
        // Wait a moment for the status to be processed and displayed
        setTimeout(() => {
            ScannerBase.addLogEntry('✅ System status refreshed successfully', 'success');
        }, 500);
        
    } catch (error) {
        ScannerBase.log('Status refresh error:', error);
        ScannerBase.addLogEntry(`❌ Status refresh failed: ${error.message}`, 'error');
        // For errors, still show an overlay alert since they're important
        ScannerBase.showAlert(`Cannot refresh status: ${error.message}`, 'error');
    }
};

window.clearLog = function() {
    const logContainer = document.getElementById('activityLog');
    if (logContainer) {
        logContainer.innerHTML = '';
        ScannerBase.addLogEntry('Activity log cleared', 'info');
    }
};

window.downloadLog = function() {
    const logContainer = document.getElementById('activityLog');
    if (!logContainer) return;

    const entries = Array.from(logContainer.children).map(entry => {
        const timestamp = entry.querySelector('.log-timestamp')?.textContent || '';
        const message = entry.querySelector('.log-message')?.textContent || '';
        return `${timestamp} ${message}`;
    });

    const logContent = entries.join('\n');
    const blob = new Blob([logContent], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `scanner_log_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    ScannerBase.showAlert('Log downloaded', 'success', 2000);
};