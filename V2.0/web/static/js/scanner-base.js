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
        updateInterval: 1000,           // Status update interval (ms)
        reconnectDelay: 5000,          // WebSocket reconnect delay (ms)
        maxReconnectAttempts: 10,      // Maximum reconnection attempts
        requestTimeout: 10000,         // API request timeout (ms)
        showDebugLogs: false           // Enable debug logging
    },

    // State management
    state: {
        connected: false,
        systemStatus: null,
        lastUpdate: null,
        reconnectAttempts: 0,
        pendingRequests: new Map()
    },

    // WebSocket connection
    socket: null,

    /**
     * Initialize the scanner base functionality
     */
    init() {
        this.log('Initializing scanner base...');
        this.setupWebSocket();
        this.setupEventHandlers();
        this.startStatusUpdater();
        this.log('Scanner base initialized');
    },

    /**
     * Setup WebSocket connection for real-time updates
     */
    setupWebSocket() {
        try {
            // Connect to WebSocket
            this.socket = io();

            this.socket.on('connect', () => {
                this.log('WebSocket connected');
                this.state.connected = true;
                this.state.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
                this.showAlert('Connected to scanner', 'success');
            });

            this.socket.on('disconnect', () => {
                this.log('WebSocket disconnected');
                this.state.connected = false;
                this.updateConnectionStatus(false);
                this.showAlert('Disconnected from scanner', 'warning');
                this.scheduleReconnect();
            });

            this.socket.on('status_update', (status) => {
                this.handleStatusUpdate(status);
            });

            this.socket.on('connect_error', (error) => {
                this.log('WebSocket connection error:', error);
                this.scheduleReconnect();
            });

        } catch (error) {
            this.log('Error setting up WebSocket:', error);
            this.showAlert('Failed to establish real-time connection', 'error');
        }
    },

    /**
     * Setup global event handlers
     */
    setupEventHandlers() {
        // Handle page visibility changes
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.socket && !this.socket.connected) {
                this.log('Page visible, attempting reconnection...');
                this.socket.connect();
            }
        });

        // Handle online/offline status
        window.addEventListener('online', () => {
            this.log('Network online, attempting reconnection...');
            if (this.socket && !this.socket.connected) {
                this.socket.connect();
            }
        });

        window.addEventListener('offline', () => {
            this.log('Network offline');
            this.showAlert('Network connection lost', 'warning');
        });

        // Handle beforeunload to cleanup
        window.addEventListener('beforeunload', () => {
            if (this.socket) {
                this.socket.disconnect();
            }
        });
    },

    /**
     * Schedule WebSocket reconnection with exponential backoff
     */
    scheduleReconnect() {
        if (this.state.reconnectAttempts >= this.config.maxReconnectAttempts) {
            this.log('Maximum reconnection attempts reached');
            this.showAlert('Unable to connect to scanner. Please refresh the page.', 'error');
            return;
        }

        this.state.reconnectAttempts++;
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(2, this.state.reconnectAttempts - 1),
            30000
        );

        this.log(`Scheduling reconnection attempt ${this.state.reconnectAttempts} in ${delay}ms`);
        
        setTimeout(() => {
            if (this.socket && !this.socket.connected) {
                this.log('Attempting to reconnect...');
                this.socket.connect();
            }
        }, delay);
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
        // Update main status indicators
        this.updateStatusIndicator('motionStatus', status.motion?.connected, status.motion?.status);
        this.updateStatusIndicator('cameraStatus', status.cameras?.available > 0, status.cameras?.status);
        this.updateStatusIndicator('lightingStatus', status.lighting?.zones?.length > 0, status.lighting?.status);
        this.updateStatusIndicator('scanStatus', status.scan?.active, status.scan?.status);

        // Update position display
        if (status.motion?.position) {
            this.updatePosition(status.motion.position);
        }

        // Update scan progress
        if (status.scan) {
            this.updateScanProgress(status.scan);
        }

        // Update detailed status
        this.updateDetailedStatus(status);
    },

    /**
     * Update individual status indicator
     */
    updateStatusIndicator(elementId, isReady, statusText) {
        const element = document.getElementById(elementId);
        if (element) {
            element.className = `status-indicator ${isReady ? 'ready' : 'error'}`;
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
    updateDetailedStatus(status) {
        // Motion details
        const motionDetails = document.getElementById('motionDetails');
        if (motionDetails && status.motion) {
            motionDetails.innerHTML = `
                <div>Position: <span id="currentPosition">X:${parseFloat(status.motion.position?.x || 0).toFixed(1)} Y:${parseFloat(status.motion.position?.y || 0).toFixed(1)} Z:${parseFloat(status.motion.position?.z || 0).toFixed(1)} C:${parseFloat(status.motion.position?.c || 0).toFixed(1)}</span></div>
                <div>State: <span id="motionState">${status.motion.status || 'Unknown'}</span></div>
            `;
        }

        // Camera details
        const cameraDetails = document.getElementById('cameraDetails');
        if (cameraDetails && status.cameras) {
            cameraDetails.innerHTML = `
                <div>Available: <span id="cameraCount">${status.cameras.available || 0}</span></div>
                <div>Active: <span id="activeCameras">${status.cameras.active?.join(', ') || 'None'}</span></div>
            `;
        }

        // Lighting details
        const lightingDetails = document.getElementById('lightingDetails');
        if (lightingDetails && status.lighting) {
            lightingDetails.innerHTML = `
                <div>Zones: <span id="lightingZones">${status.lighting.zones?.length || 0}</span></div>
                <div>Status: <span id="lightingState">${status.lighting.status || 'Unknown'}</span></div>
            `;
        }

        // Scan details
        const scanDetails = document.getElementById('scanDetails');
        if (scanDetails && status.scan) {
            scanDetails.innerHTML = `
                <div>Progress: <span id="scanProgress">${parseFloat(status.scan.progress || 0).toFixed(1)}%</span></div>
                <div>Points: <span id="scanPoints">${status.scan.current_point || 0}/${status.scan.total_points || 0}</span></div>
                <div>Phase: <span id="scanPhase">${status.scan.phase || 'Idle'}</span></div>
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