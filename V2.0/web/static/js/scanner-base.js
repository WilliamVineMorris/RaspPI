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
        updateInterval: 2000,           // Status update interval (ms) - increased for HTTP polling
        requestTimeout: 10000,          // API request timeout (ms)
        showDebugLogs: false            // Enable debug logging
    },

    // State management
    state: {
        connected: false,
        systemStatus: null,
        lastUpdate: null,
        pendingRequests: new Map()
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
            this.log('Setting up HTTP polling...');
            this.state.connected = true;
            this.updateConnectionStatus(true);
            
            // Start polling immediately
            this.pollStatus();
            
            // Set up regular polling
            this.pollingInterval = setInterval(() => {
                this.pollStatus();
            }, this.config.updateInterval);
            
            this.log('HTTP polling established');
        } catch (error) {
            this.log('Error setting up HTTP polling:', error);
            this.showAlert('Failed to establish connection', 'error');
        }
    },

    /**
     * Poll for status updates via HTTP
     */
    pollStatus() {
        if (document.hidden) {
            // Skip polling when page is not visible
            return;
        }
        
        this.apiRequest('/api/status')
            .then(status => {
                this.handleStatusUpdate(status);
                if (!this.state.connected) {
                    this.state.connected = true;
                    this.updateConnectionStatus(true);
                }
            })
            .catch(error => {
                this.log('Polling error:', error);
                if (this.state.connected) {
                    this.state.connected = false;
                    this.updateConnectionStatus(false);
                }
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
     * Start periodic status updates
     */
    startStatusUpdater() {
        setInterval(() => {
            if (this.state.connected && this.socket) {
                this.socket.emit('request_status');
            }
        }, this.config.updateInterval);
    },

    /**
     * Handle status updates from server
     */
    handleStatusUpdate(status) {
        this.state.systemStatus = status;
        this.state.lastUpdate = new Date();
        
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
        console.log('updateSystemStatus called with:', JSON.stringify(status, null, 2));
        
        // Extract the data object from the API response
        const data = status.data || status;
        
        // Detailed debugging of each property access
        console.log('Extracted data object:', data);
        console.log('Raw data.motion:', data.motion);
        console.log('Raw data.motion?.connected:', data.motion?.connected);
        console.log('Raw data.cameras:', data.cameras);
        console.log('Raw data.cameras?.available:', data.cameras?.available);
        
        console.log('Motion connected:', data.motion?.connected);
        console.log('Motion connected type:', typeof data.motion?.connected);
        console.log('Cameras available:', data.cameras?.available);
        console.log('Cameras available type:', typeof data.cameras?.available);
        console.log('Cameras available > 0:', data.cameras?.available > 0);
        console.log('Boolean(data.cameras?.available):', Boolean(data.cameras?.available));
        console.log('Number(data.cameras?.available):', Number(data.cameras?.available));
        
        // Step by step boolean evaluation
        const motionConnected = data.motion?.connected;
        const camerasAvailable = data.cameras?.available;
        
        console.log('Extracted motionConnected:', motionConnected, 'type:', typeof motionConnected);
        console.log('Extracted camerasAvailable:', camerasAvailable, 'type:', typeof camerasAvailable);
        
        // More robust boolean checks
        const motionReady = Boolean(motionConnected);
        const cameraReady = Boolean(camerasAvailable) && Number(camerasAvailable) > 0;
        const lightingReady = Boolean(data.lighting?.zones?.length) && data.lighting.zones.length > 0;
        const scanActive = Boolean(data.scan?.active);
        
        console.log('Calculated ready states:');
        console.log('  motionReady:', motionReady);
        console.log('  cameraReady:', cameraReady);
        console.log('  lightingReady:', lightingReady);
        console.log('  scanActive:', scanActive);
        
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
    },

    /**
     * Update individual status indicator
     */
    updateStatusIndicator(elementId, isReady, statusText) {
        console.log(`updateStatusIndicator: ${elementId}, isReady=${isReady}, statusText=${statusText}`);
        const element = document.getElementById(elementId);
        if (element) {
            const newClassName = `status-indicator ${isReady ? 'ready' : 'error'}`;
            element.className = newClassName;
            console.log(`Updated ${elementId} className to: ${newClassName}`);
            console.log(`Element current className is now: ${element.className}`);
            console.log(`Element current style: color=${element.style.color}`);
        } else {
            console.log(`Element ${elementId} not found!`);
        }

        const textElement = document.getElementById(elementId.replace('Status', 'State'));
        if (textElement) {
            textElement.textContent = statusText || 'Unknown';
            console.log(`Updated ${elementId.replace('Status', 'State')} text to: ${textElement.textContent}`);
        } else {
            console.log(`Text element ${elementId.replace('Status', 'State')} not found!`);
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
                <div>Position: <span id="currentPosition">X:${parseFloat(data.motion.position?.x || 0).toFixed(1)} Y:${parseFloat(data.motion.position?.y || 0).toFixed(1)} Z:${parseFloat(data.motion.position?.z || 0).toFixed(1)} C:${parseFloat(data.motion.position?.c || 0).toFixed(1)}</span></div>
                <div>State: <span id="motionState">${data.motion.status || 'Unknown'}</span></div>
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
     * Show alert message to user
     */
    showAlert(message, type = 'info', duration = 5000) {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;

        const alertId = `alert_${Date.now()}`;
        const alertElement = document.createElement('div');
        alertElement.id = alertId;
        alertElement.className = `alert ${type}`;
        alertElement.innerHTML = `
            <span>${message}</span>
            <button onclick="ScannerBase.dismissAlert('${alertId}')" style="margin-left: auto; background: none; border: none; font-size: 1.2rem; cursor: pointer;">&times;</button>
        `;

        alertContainer.appendChild(alertElement);

        // Auto-dismiss after duration
        if (duration > 0) {
            setTimeout(() => {
                this.dismissAlert(alertId);
            }, duration);
        }
    },

    /**
     * Dismiss alert by ID
     */
    dismissAlert(alertId) {
        const alertElement = document.getElementById(alertId);
        if (alertElement) {
            alertElement.remove();
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
        ScannerBase.addLogEntry('Emergency stop initiated', 'warning');
        
        const response = await ScannerBase.apiRequest('/api/emergency_stop', {
            method: 'POST'
        });
        
        ScannerBase.showAlert('Emergency stop executed', 'warning');
        ScannerBase.addLogEntry('Emergency stop completed', 'warning');
        
    } catch (error) {
        ScannerBase.showAlert(`Emergency stop failed: ${error.message}`, 'error');
        ScannerBase.addLogEntry(`Emergency stop failed: ${error.message}`, 'error');
    } finally {
        ScannerBase.hideLoading();
    }
};

window.refreshStatus = function() {
    if (ScannerBase.socket?.connected) {
        ScannerBase.socket.emit('request_status');
        ScannerBase.showAlert('Status refreshed', 'success', 2000);
    } else {
        ScannerBase.showAlert('Cannot refresh status - not connected', 'warning');
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