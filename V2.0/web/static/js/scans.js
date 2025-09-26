/**
 * Scans JavaScript - Comprehensive scan management interface
 * 
 * Provides scan configuration, queue management, and real-time monitoring
 * with advanced pattern generation and progress tracking.
 */

// Scan management functionality
const ScanManager = {
    // Configuration
    config: {
        scanTypes: {
            surface: {
                name: 'Surface Scan',
                defaultPoints: 50,
                timeMultiplier: 1.0,
                sizeMultiplier: 1.0
            },
            volume: {
                name: 'Volume Scan',
                defaultPoints: 200,
                timeMultiplier: 2.5,
                sizeMultiplier: 3.0
            },
            cylindrical: {
                name: 'Cylindrical Scan',
                defaultPoints: 120,
                timeMultiplier: 2.0,
                sizeMultiplier: 2.5
            },
            detail: {
                name: 'Detail Scan',
                defaultPoints: 100,
                timeMultiplier: 1.8,
                sizeMultiplier: 2.0
            }
        },
        resolutionMultipliers: {
            low: { time: 0.5, size: 0.3, quality: 0.4 },
            medium: { time: 1.0, size: 1.0, quality: 1.0 },
            high: { time: 2.0, size: 2.5, quality: 2.0 },
            ultra: { time: 4.0, size: 6.0, quality: 4.0 }
        },
        speedMultipliers: {
            slow: { time: 2.0, quality: 1.5 },
            medium: { time: 1.0, quality: 1.0 },
            fast: { time: 0.6, quality: 0.8 }
        }
    },

    // State management
    state: {
        selectedScanType: 'surface',
        scanQueue: [],
        currentScan: null,
        queueRunning: false,
        templates: new Map()
    },

    /**
     * Initialize scan management interface
     */
    init() {
        ScannerBase.log('Initializing scan manager...');
        
        this.setupScanTypeSelection();
        this.setupParameterControls();
        this.setupAdvancedSettings();
        this.loadScanQueue();
        this.loadScanTemplates();
        
        // Listen for status updates
        document.addEventListener('scanner:statusUpdate', (event) => {
            this.handleStatusUpdate(event.detail.status);
        });

        // Auto-update preview when parameters change
        this.setupAutoPreview();

        ScannerBase.log('Scan manager initialized');
    },

    /**
     * Setup scan type selection
     */
    setupScanTypeSelection() {
        const scanTypeCards = document.querySelectorAll('.scan-type-card');
        scanTypeCards.forEach(card => {
            card.addEventListener('click', () => {
                console.log(`Scan type clicked: ${card.dataset.type}`);
                
                // Update selection
                scanTypeCards.forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                
                // Update state
                this.state.selectedScanType = card.dataset.type;
                
                // Show/hide scan type specific parameters
                this.updateParameterPanels();
                
                // Update preview
                this.updateScanPreview();
                
                ScannerBase.addLogEntry(`Scan type selected: ${this.config.scanTypes[this.state.selectedScanType].name}`, 'info');
            });
        });

        // Select default type and update parameters
        document.querySelector('[data-type="surface"]')?.classList.add('selected');
        this.updateParameterPanels();
    },

    /**
     * Update parameter panels based on selected scan type
     */
    updateParameterPanels() {
        const cylindricalParams = document.getElementById('cylindrical-parameters');
        const gridBoundaries = document.getElementById('grid-boundaries');
        
        console.log(`Updating parameter panels for: ${this.state.selectedScanType}`);
        console.log('cylindricalParams element:', cylindricalParams);
        console.log('gridBoundaries element:', gridBoundaries);
        
        if (this.state.selectedScanType === 'cylindrical') {
            console.log('Showing cylindrical parameters');
            if (cylindricalParams) cylindricalParams.style.display = 'block';
            if (gridBoundaries) gridBoundaries.style.display = 'none';
        } else {
            console.log('Showing grid boundaries');
            if (cylindricalParams) cylindricalParams.style.display = 'none';
            if (gridBoundaries) gridBoundaries.style.display = 'block';
        }
    },

    /**
     * Setup parameter controls
     */
    setupParameterControls() {
        // Basic parameters
        const parameterInputs = document.querySelectorAll('.parameter-input');
        parameterInputs.forEach(input => {
            input.addEventListener('change', () => {
                this.updateScanPreview();
            });
        });

        // Boundary inputs
        const boundaryInputs = document.querySelectorAll('[id^="boundary"]');
        boundaryInputs.forEach(input => {
            input.addEventListener('input', () => {
                this.validateBoundaries();
                this.updateScanPreview();
            });
        });

        // Scan name auto-generation
        const scanNameInput = document.getElementById('scanName');
        if (scanNameInput && !scanNameInput.value) {
            scanNameInput.value = this.generateScanName();
        }
    },

    /**
     * Setup advanced settings
     */
    setupAdvancedSettings() {
        // Point density slider
        const densitySlider = document.getElementById('pointDensity');
        const densityValue = document.getElementById('densityValue');
        if (densitySlider && densityValue) {
            densitySlider.addEventListener('input', (e) => {
                densityValue.textContent = e.target.value;
                this.updateScanPreview();
            });
        }

        // Overlap percentage slider
        const overlapSlider = document.getElementById('overlapPercent');
        const overlapValue = document.getElementById('overlapValue');
        if (overlapSlider && overlapValue) {
            overlapSlider.addEventListener('input', (e) => {
                overlapValue.textContent = `${e.target.value}%`;
                this.updateScanPreview();
            });
        }
    },

    /**
     * Setup auto-preview updates
     */
    setupAutoPreview() {
        // Debounced preview update
        let previewTimer;
        const updatePreview = () => {
            clearTimeout(previewTimer);
            previewTimer = setTimeout(() => {
                this.updateScanPreview();
            }, 300);
        };

        // Listen to all parameter changes
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('parameter-input')) {
                updatePreview();
            }
        });

        // Initial preview
        this.updateScanPreview();
    },

    /**
     * Handle status updates
     */
    handleStatusUpdate(status) {
        if (status.scan) {
            this.updateCurrentScanStatus(status.scan);
        }
        
        // Update queue status if scan queue is running
        if (this.state.queueRunning) {
            this.updateQueueStatus(status);
        }
    },

    /**
     * Update current scan status display
     */
    updateCurrentScanStatus(scanStatus) {
        const panel = document.getElementById('currentScanPanel');
        
        if (scanStatus.active) {
            panel.style.display = 'block';
            
            // Update scan details
            document.getElementById('currentScanName').textContent = scanStatus.name || 'Unknown';
            document.getElementById('currentScanPhase').textContent = scanStatus.phase || 'Processing';
            document.getElementById('currentScanPoint').textContent = 
                `${scanStatus.current_point || 0}/${scanStatus.total_points || 0}`;
            document.getElementById('currentScanProgress').textContent = 
                `${parseFloat(scanStatus.progress || 0).toFixed(1)}%`;
            
            // Update progress bar
            const progressBar = document.getElementById('currentScanProgressBar');
            if (progressBar) {
                progressBar.style.width = `${scanStatus.progress || 0}%`;
            }
            
            // Update timing
            if (scanStatus.elapsed_time) {
                document.getElementById('currentScanElapsed').textContent = 
                    this.formatDuration(scanStatus.elapsed_time);
            }
            
            if (scanStatus.estimated_remaining) {
                document.getElementById('currentScanRemaining').textContent = 
                    this.formatDuration(scanStatus.estimated_remaining);
            }
            
        } else {
            panel.style.display = 'none';
        }
    },

    /**
     * Update scan preview calculations
     */
    updateScanPreview() {
        const scanType = this.config.scanTypes[this.state.selectedScanType];
        const resolution = document.getElementById('scanResolution')?.value || 'medium';
        const speed = document.getElementById('scanSpeed')?.value || 'medium';
        const cameraCount = document.getElementById('cameraCount')?.value || '2';
        const pointDensity = parseInt(document.getElementById('pointDensity')?.value || '5');
        const overlap = parseInt(document.getElementById('overlapPercent')?.value || '50');

        // Get boundaries
        const boundaries = this.getBoundaries();
        const volume = this.calculateVolume(boundaries);

        // Calculate scan parameters
        const basePoints = Math.max(scanType.defaultPoints, Math.round(volume / 1000 * pointDensity));
        const resMultiplier = this.config.resolutionMultipliers[resolution];
        const speedMultiplier = this.config.speedMultipliers[speed];
        
        const totalPoints = Math.round(basePoints * resMultiplier.quality);
        const imagesPerPoint = parseInt(cameraCount) === 1 ? 1 : 2;
        const totalImages = Math.round(totalPoints * imagesPerPoint * (1 + overlap/100));
        
        // Calculate time estimate
        const baseTime = totalPoints * scanType.timeMultiplier * speedMultiplier.time;
        const estimatedTime = Math.round(baseTime * resMultiplier.time / 60); // Convert to minutes
        
        // Calculate data size estimate
        const baseSize = totalImages * 50; // 50MB per image estimate
        const estimatedSize = Math.round(baseSize * resMultiplier.size);

        // Update preview display
        document.getElementById('previewPoints').textContent = totalPoints.toLocaleString();
        document.getElementById('previewTime').textContent = this.formatDuration(estimatedTime * 60);
        document.getElementById('previewSize').textContent = this.formatFileSize(estimatedSize * 1024 * 1024);
        document.getElementById('previewImages').textContent = totalImages.toLocaleString();
    },

    /**
     * Get boundary values
     */
    getBoundaries() {
        return {
            xMin: parseFloat(document.getElementById('boundaryXMin')?.value || -50),
            xMax: parseFloat(document.getElementById('boundaryXMax')?.value || 50),
            yMin: parseFloat(document.getElementById('boundaryYMin')?.value || -50),
            yMax: parseFloat(document.getElementById('boundaryYMax')?.value || 50),
            zMin: parseFloat(document.getElementById('boundaryZMin')?.value || 0),
            zMax: parseFloat(document.getElementById('boundaryZMax')?.value || 100)
        };
    },

    /**
     * Calculate scan volume
     */
    calculateVolume(boundaries) {
        const width = Math.abs(boundaries.xMax - boundaries.xMin);
        const depth = Math.abs(boundaries.yMax - boundaries.yMin);
        const height = Math.abs(boundaries.zMax - boundaries.zMin);
        return width * depth * height;
    },

    /**
     * Validate boundary inputs
     */
    validateBoundaries() {
        const boundaries = this.getBoundaries();
        let isValid = true;

        // Check for valid ranges
        if (boundaries.xMin >= boundaries.xMax) {
            this.showBoundaryError('X Max must be greater than X Min');
            isValid = false;
        }
        if (boundaries.yMin >= boundaries.yMax) {
            this.showBoundaryError('Y Max must be greater than Y Min');
            isValid = false;
        }
        if (boundaries.zMin >= boundaries.zMax) {
            this.showBoundaryError('Z Max must be greater than Z Min');
            isValid = false;
        }

        // Check for reasonable values
        const volume = this.calculateVolume(boundaries);
        if (volume > 1000000) { // 1m³
            this.showBoundaryError('Scan volume is very large - this may take a long time');
        }

        return isValid;
    },

    /**
     * Show boundary validation error
     */
    showBoundaryError(message) {
        ScannerBase.showAlert(message, 'warning', 3000);
    },

    /**
     * Generate automatic scan name
     */
    generateScanName() {
        const now = new Date();
        const timestamp = now.toISOString().slice(0, 19).replace(/[:T]/g, '_');
        const scanType = this.config.scanTypes[this.state.selectedScanType].name.replace(' ', '_');
        return `${scanType}_${timestamp}`;
    },

    /**
     * Preview scan path
     */
    async previewScan() {
        try {
            ScannerBase.showLoading('Generating scan preview...');
            
            const scanConfig = this.collectScanConfiguration();
            
            const response = await ScannerBase.apiRequest('/api/scan/preview', {
                method: 'POST',
                body: JSON.stringify(scanConfig)
            });

            ScannerBase.showAlert('Scan path generated - check manual control view', 'success');
            ScannerBase.addLogEntry(`Scan preview generated: ${response.points} points`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Preview failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Save scan as template
     */
    async saveScanTemplate() {
        const templateName = prompt('Enter template name:');
        if (!templateName) return;

        try {
            const scanConfig = this.collectScanConfiguration();
            scanConfig.template_name = templateName;

            const response = await ScannerBase.apiRequest('/api/scan/template/save', {
                method: 'POST',
                body: JSON.stringify(scanConfig)
            });

            this.state.templates.set(templateName, scanConfig);
            ScannerBase.showAlert('Template saved successfully', 'success');
            ScannerBase.addLogEntry(`Scan template saved: ${templateName}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Template save failed: ${error.message}`, 'error');
        }
    },

    /**
     * Add scan to queue
     */
    async addToQueue() {
        if (!this.validateScanConfiguration()) {
            return;
        }

        try {
            const scanConfig = this.collectScanConfiguration();
            
            const response = await ScannerBase.apiRequest('/api/scan/queue/add', {
                method: 'POST',
                body: JSON.stringify(scanConfig)
            });

            // Add to local queue
            const queueItem = {
                id: response.scan_id,
                name: scanConfig.name,
                type: scanConfig.type,
                status: 'pending',
                config: scanConfig,
                created: new Date(),
                progress: 0
            };
            
            this.state.scanQueue.push(queueItem);
            this.updateQueueDisplay();

            ScannerBase.showAlert('Scan added to queue', 'success');
            ScannerBase.addLogEntry(`Scan queued: ${scanConfig.name}`, 'info');

            // Auto-generate new scan name
            document.getElementById('scanName').value = this.generateScanName();

        } catch (error) {
            ScannerBase.showAlert(`Failed to add scan to queue: ${error.message}`, 'error');
        }
    },

    /**
     * Start scan immediately
     */
    async startScanNow() {
        if (!this.validateScanConfiguration()) {
            return;
        }

        if (!confirm('Start scan immediately? This will interrupt any running operations.')) {
            return;
        }

        try {
            ScannerBase.showLoading('Starting scan...');
            
            const scanConfig = this.collectScanConfiguration();
            
            const response = await ScannerBase.apiRequest('/api/scan/start', {
                method: 'POST',
                body: JSON.stringify(scanConfig)
            });

            this.state.currentScan = {
                id: response.scan_id,
                name: scanConfig.name,
                startTime: new Date()
            };

            ScannerBase.showAlert('Scan started successfully', 'success');
            ScannerBase.addLogEntry(`Scan started: ${scanConfig.name}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Failed to start scan: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Collect current scan configuration
     */
    collectScanConfiguration() {
        const boundaries = this.getBoundaries();
        
        const config = {
            name: document.getElementById('scanName')?.value || this.generateScanName(),
            type: this.state.selectedScanType,
            resolution: document.getElementById('scanResolution')?.value || 'medium',
            speed: document.getElementById('scanSpeed')?.value || 'medium',
            camera_count: parseInt(document.getElementById('cameraCount')?.value || '2'),
            boundaries: boundaries,
            advanced: {
                point_density: parseInt(document.getElementById('pointDensity')?.value || '5'),
                overlap_percent: parseInt(document.getElementById('overlapPercent')?.value || '50'),
                lighting_mode: document.getElementById('lightingMode')?.value || 'auto',
                auto_focus: document.getElementById('autoFocus')?.value || 'enabled'
            }
        };

        // Add scan pattern type and specific parameters
        if (this.state.selectedScanType === 'cylindrical') {
            config.pattern_type = 'cylindrical';
            config.radius = parseInt(document.getElementById('cylindricalRadius')?.value || '30');
            config.y_min = parseInt(document.getElementById('cylindricalYMin')?.value || '40');
            config.y_max = parseInt(document.getElementById('cylindricalYMax')?.value || '120');
            config.y_step = parseInt(document.getElementById('cylindricalYStep')?.value || '20');
            config.rotation_step = parseInt(document.getElementById('cylindricalRotationStep')?.value || '60');
            config.c_angles = [-10, 0, 10]; // Default camera angles
        } else {
            // Default to grid pattern for other scan types
            config.pattern_type = 'grid';
            config.x_min = boundaries.x_min;
            config.x_max = boundaries.x_max;
            config.y_min = boundaries.y_min;
            config.y_max = boundaries.y_max;
            config.spacing = 10.0; // Default spacing
            config.z_height = 25.0; // Default Z height
        }

        return config;
    },

    /**
     * Validate scan configuration
     */
    validateScanConfiguration() {
        // Check scan name
        const scanName = document.getElementById('scanName')?.value;
        if (!scanName || scanName.trim().length === 0) {
            ScannerBase.showAlert('Please enter a scan name', 'warning');
            return false;
        }

        // Check boundaries
        if (!this.validateBoundaries()) {
            return false;
        }

        // Check system readiness
        const status = ScannerBase.state.systemStatus;
        if (!status?.motion?.connected) {
            ScannerBase.showAlert('Motion system not connected', 'error');
            return false;
        }

        if (!status?.cameras?.available || status.cameras.available === 0) {
            ScannerBase.showAlert('No cameras available', 'error');
            return false;
        }

        if (status?.scan?.active) {
            ScannerBase.showAlert('Another scan is already running', 'warning');
            return false;
        }

        return true;
    },

    /**
     * Load scan queue from server
     */
    async loadScanQueue() {
        try {
            const response = await ScannerBase.apiRequest('/api/scan/queue');
            this.state.scanQueue = response.queue || [];
            this.updateQueueDisplay();
        } catch (error) {
            ScannerBase.log('Failed to load scan queue:', error);
        }
    },

    /**
     * Load saved scan templates
     */
    async loadScanTemplates() {
        try {
            const response = await ScannerBase.apiRequest('/api/scan/templates');
            if (response.templates) {
                response.templates.forEach(template => {
                    this.state.templates.set(template.name, template.config);
                });
            }
        } catch (error) {
            ScannerBase.log('Failed to load scan templates:', error);
        }
    },

    /**
     * Update queue display
     */
    updateQueueDisplay() {
        const container = document.getElementById('scanQueueContainer');
        if (!container) return;

        if (this.state.scanQueue.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: var(--text-secondary); padding: 2rem;">No scans in queue</div>';
            return;
        }

        container.innerHTML = this.state.scanQueue.map(item => this.createQueueItemHTML(item)).join('');
    },

    /**
     * Create queue item HTML
     */
    createQueueItemHTML(item) {
        const statusClass = item.status.toLowerCase();
        const created = new Date(item.created).toLocaleString();
        
        return `
            <div class="queue-item ${statusClass}" data-scan-id="${item.id}">
                <div class="queue-header">
                    <h4 class="queue-title">${item.name}</h4>
                    <span class="queue-status ${statusClass}">${item.status}</span>
                </div>
                <div class="queue-details">
                    Type: ${this.config.scanTypes[item.type]?.name || item.type}<br>
                    Created: ${created}<br>
                    ${item.config ? `Points: ~${this.estimatePoints(item.config)}, Time: ~${this.estimateTime(item.config)}` : ''}
                </div>
                ${item.progress > 0 ? `
                    <div class="queue-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${item.progress}%;"></div>
                        </div>
                    </div>
                ` : ''}
                <div class="queue-actions">
                    ${item.status === 'pending' ? `
                        <button class="queue-btn" onclick="ScanManager.startQueueItem('${item.id}')">Start</button>
                        <button class="queue-btn" onclick="ScanManager.editQueueItem('${item.id}')">Edit</button>
                    ` : ''}
                    ${item.status === 'running' ? `
                        <button class="queue-btn" onclick="ScanManager.pauseQueueItem('${item.id}')">Pause</button>
                    ` : ''}
                    <button class="queue-btn danger" onclick="ScanManager.removeQueueItem('${item.id}')">Remove</button>
                </div>
            </div>
        `;
    },

    /**
     * Estimate points for configuration
     */
    estimatePoints(config) {
        const scanType = this.config.scanTypes[config.type];
        if (!scanType) return '--';
        
        const volume = this.calculateVolume(config.boundaries);
        const density = config.advanced?.point_density || 5;
        return Math.round(Math.max(scanType.defaultPoints, volume / 1000 * density)).toLocaleString();
    },

    /**
     * Estimate time for configuration
     */
    estimateTime(config) {
        const scanType = this.config.scanTypes[config.type];
        if (!scanType) return '--';
        
        const resMultiplier = this.config.resolutionMultipliers[config.resolution] || this.config.resolutionMultipliers.medium;
        const speedMultiplier = this.config.speedMultipliers[config.speed] || this.config.speedMultipliers.medium;
        
        const baseTime = scanType.defaultPoints * scanType.timeMultiplier;
        const estimatedTime = baseTime * resMultiplier.time * speedMultiplier.time;
        
        return this.formatDuration(estimatedTime);
    },

    /**
     * Format duration in seconds to readable string
     */
    formatDuration(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        
        if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else if (minutes > 0) {
            return `${minutes}m ${secs}s`;
        } else {
            return `${secs}s`;
        }
    },

    /**
     * Format file size
     */
    formatFileSize(bytes) {
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = bytes;
        let unitIndex = 0;
        
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    },

    /**
     * Start entire queue
     */
    async startQueue() {
        try {
            await ScannerBase.apiRequest('/api/scan/queue/start', {
                method: 'POST'
            });

            this.state.queueRunning = true;
            ScannerBase.showAlert('Scan queue started', 'success');
            ScannerBase.addLogEntry('Scan queue processing started', 'info');

        } catch (error) {
            ScannerBase.showAlert(`Failed to start queue: ${error.message}`, 'error');
        }
    },

    /**
     * Pause queue processing
     */
    async pauseQueue() {
        try {
            await ScannerBase.apiRequest('/api/scan/queue/pause', {
                method: 'POST'
            });

            this.state.queueRunning = false;
            ScannerBase.showAlert('Scan queue paused', 'warning');
            ScannerBase.addLogEntry('Scan queue processing paused', 'warning');

        } catch (error) {
            ScannerBase.showAlert(`Failed to pause queue: ${error.message}`, 'error');
        }
    },

    /**
     * Clear entire queue
     */
    async clearQueue() {
        if (!confirm('Clear entire scan queue? This cannot be undone.')) {
            return;
        }

        try {
            await ScannerBase.apiRequest('/api/scan/queue/clear', {
                method: 'POST'
            });

            this.state.scanQueue = [];
            this.updateQueueDisplay();
            ScannerBase.showAlert('Scan queue cleared', 'info');
            ScannerBase.addLogEntry('Scan queue cleared', 'info');

        } catch (error) {
            ScannerBase.showAlert(`Failed to clear queue: ${error.message}`, 'error');
        }
    },

    /**
     * Remove specific queue item
     */
    async removeQueueItem(scanId) {
        if (!confirm('Remove this scan from the queue?')) {
            return;
        }

        try {
            await ScannerBase.apiRequest(`/api/scan/queue/remove/${scanId}`, {
                method: 'DELETE'
            });

            this.state.scanQueue = this.state.scanQueue.filter(item => item.id !== scanId);
            this.updateQueueDisplay();
            ScannerBase.addLogEntry(`Scan removed from queue: ${scanId}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Failed to remove scan: ${error.message}`, 'error');
        }
    },

    /**
     * Start specific queue item
     */
    async startQueueItem(scanId) {
        try {
            await ScannerBase.apiRequest(`/api/scan/queue/start/${scanId}`, {
                method: 'POST'
            });

            ScannerBase.addLogEntry(`Scan started from queue: ${scanId}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Failed to start scan: ${error.message}`, 'error');
        }
    },

    /**
     * Stop current scan
     */
    async stopCurrentScan() {
        if (!confirm('Stop the current scan? Progress will be lost.')) {
            return;
        }

        try {
            await ScannerBase.apiRequest('/api/scan/stop', {
                method: 'POST'
            });

            this.state.currentScan = null;
            ScannerBase.showAlert('Scan stopped', 'warning');
            ScannerBase.addLogEntry('Current scan stopped by user', 'warning');

        } catch (error) {
            ScannerBase.showAlert(`Failed to stop scan: ${error.message}`, 'error');
        }
    }
};

// Global functions for HTML onclick handlers
window.toggleAdvancedSettings = function() {
    const content = document.getElementById('advancedSettings');
    const icon = document.getElementById('advancedToggleIcon');
    
    if (content.classList.contains('visible')) {
        content.classList.remove('visible');
        icon.textContent = '▼';
    } else {
        content.classList.add('visible');
        icon.textContent = '▲';
    }
};

window.previewScan = () => ScanManager.previewScan();
window.saveScanTemplate = () => ScanManager.saveScanTemplate();
window.addToQueue = () => ScanManager.addToQueue();
window.startScanNow = () => ScanManager.startScanNow();
window.startQueue = () => ScanManager.startQueue();
window.pauseQueue = () => ScanManager.pauseQueue();
window.clearQueue = () => ScanManager.clearQueue();
window.stopCurrentScan = () => ScanManager.stopCurrentScan();

// Initialize scan manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    ScannerBase.init();
    ScanManager.init();
});