/**
 * Settings JavaScript - Hardware-ready system configuration interface
 * 
 * Simplified for hardware testing with essential configuration management.
 */

// Settings management functionality
const SettingsManager = {
    // Configuration
    config: {
        autoSaveDelay: 2000,        // Auto-save delay for settings
        validationTimeout: 1000     // Input validation timeout
    },

    // State management
    state: {
        currentSection: 'motion',
        hasUnsavedChanges: false,
        autoSaveTimer: null
    },

    /**
     * Initialize settings management interface
     */
    init() {
        ScannerBase.log('Initializing settings manager...');
        
        this.setupNavigation();
        this.setupFormHandlers();
        this.loadCurrentSettings();
        
        // Warn about unsaved changes
        window.addEventListener('beforeunload', (e) => {
            if (this.state.hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
                return e.returnValue;
            }
        });

        ScannerBase.log('Settings manager initialized');
    },

    /**
     * Setup section navigation
     */
    setupNavigation() {
        const navLinks = document.querySelectorAll('.nav-link');
        navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const section = link.getAttribute('href').substring(1);
                this.showSection(section);
            });
        });
    },

    /**
     * Setup form input handlers
     */
    setupFormHandlers() {
        // Track changes on all setting inputs
        const settingInputs = document.querySelectorAll('.setting-input, .setting-toggle input, .matrix-input');
        settingInputs.forEach(input => {
            const eventType = input.type === 'range' ? 'input' : 'change';
            input.addEventListener(eventType, () => {
                this.markAsChanged();
                this.scheduleAutoSave();
            });

            // Store original value
            this.state.originalSettings.set(input.id || input.name, this.getInputValue(input));
        });
    },

    /**
     * Setup slider value updates
     */
    setupSliderUpdates() {
        // Image quality slider
        const imageQualitySlider = document.getElementById('imageQuality');
        const qualityValue = document.getElementById('qualityValue');
        if (imageQualitySlider && qualityValue) {
            imageQualitySlider.addEventListener('input', (e) => {
                qualityValue.textContent = e.target.value;
            });
        }

        // Default intensity slider
        const intensitySlider = document.getElementById('defaultIntensity');
        const intensityValue = document.getElementById('intensityValue');
        if (intensitySlider && intensityValue) {
            intensitySlider.addEventListener('input', (e) => {
                intensityValue.textContent = `${e.target.value}%`;
            });
        }

        // Point density slider
        const densitySlider = document.getElementById('defaultPointDensity');
        const densityValue = document.getElementById('densityValueDisplay');
        if (densitySlider && densityValue) {
            densitySlider.addEventListener('input', (e) => {
                densityValue.textContent = e.target.value;
            });
        }

        // Overlap slider
        const overlapSlider = document.getElementById('defaultOverlap');
        const overlapValue = document.getElementById('overlapValueDisplay');
        if (overlapSlider && overlapValue) {
            overlapSlider.addEventListener('input', (e) => {
                overlapValue.textContent = `${e.target.value}%`;
            });
        }
    },

    /**
     * Show specific settings section
     */
    showSection(sectionName) {
        // Update navigation
        document.querySelectorAll('.nav-link').forEach(link => {
            link.classList.remove('active');
        });
        document.querySelector(`[href="#${sectionName}"]`)?.classList.add('active');

        // Update content
        document.querySelectorAll('.settings-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(`${sectionName}-settings`)?.classList.add('active');

        this.state.currentSection = sectionName;

        // Start section-specific updates
        if (sectionName === 'diagnostics') {
            this.updateDiagnostics();
            this.loadSystemLogs();
        }
    },

    /**
     * Load current settings from server
     */
    async loadCurrentSettings() {
        try {
            ScannerBase.showLoading('Loading settings...');

            const response = await ScannerBase.apiRequest('/api/settings');
            
            if (response.settings) {
                this.populateSettings(response.settings);
                this.resetChangeTracking();
            }

        } catch (error) {
            ScannerBase.showAlert(`Failed to load settings: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Populate form with settings data
     */
    populateSettings(settings) {
        Object.entries(settings).forEach(([key, value]) => {
            const element = document.getElementById(key);
            if (element) {
                this.setInputValue(element, value);
            }
        });

        // Update slider displays
        this.updateAllSliderDisplays();
    },

    /**
     * Update all slider displays
     */
    updateAllSliderDisplays() {
        const sliders = [
            { slider: 'imageQuality', display: 'qualityValue' },
            { slider: 'defaultIntensity', display: 'intensityValue', suffix: '%' },
            { slider: 'defaultPointDensity', display: 'densityValueDisplay' },
            { slider: 'defaultOverlap', display: 'overlapValueDisplay', suffix: '%' }
        ];

        sliders.forEach(({ slider, display, suffix = '' }) => {
            const sliderElement = document.getElementById(slider);
            const displayElement = document.getElementById(display);
            if (sliderElement && displayElement) {
                displayElement.textContent = sliderElement.value + suffix;
            }
        });
    },

    /**
     * Get input value based on type
     */
    getInputValue(input) {
        if (input.type === 'checkbox') {
            return input.checked;
        } else if (input.type === 'number' || input.type === 'range') {
            return parseFloat(input.value);
        } else {
            return input.value;
        }
    },

    /**
     * Set input value based on type
     */
    setInputValue(input, value) {
        if (input.type === 'checkbox') {
            input.checked = value;
        } else {
            input.value = value;
        }
    },

    /**
     * Mark settings as changed
     */
    markAsChanged() {
        this.state.hasUnsavedChanges = true;
        
        // Update save button state
        const saveButton = document.querySelector('[onclick="saveSettings()"]');
        if (saveButton) {
            saveButton.textContent = 'Save Settings *';
            saveButton.classList.add('btn-warning');
            saveButton.classList.remove('btn-primary');
        }
    },

    /**
     * Reset change tracking
     */
    resetChangeTracking() {
        this.state.hasUnsavedChanges = false;
        
        // Update save button state
        const saveButton = document.querySelector('[onclick="saveSettings()"]');
        if (saveButton) {
            saveButton.textContent = 'Save Settings';
            saveButton.classList.remove('btn-warning');
            saveButton.classList.add('btn-primary');
        }
    },

    /**
     * Schedule auto-save
     */
    scheduleAutoSave() {
        if (this.state.autoSaveTimer) {
            clearTimeout(this.state.autoSaveTimer);
        }

        this.state.autoSaveTimer = setTimeout(() => {
            this.saveSettings(true); // Silent save
        }, this.config.autoSaveDelay);
    },

    /**
     * Save current settings
     */
    async saveSettings(silent = false) {
        try {
            if (!silent) {
                ScannerBase.showLoading('Saving settings...');
            }

            const settings = this.collectAllSettings();
            
            const response = await ScannerBase.apiRequest('/api/settings', {
                method: 'POST',
                body: JSON.stringify({ settings })
            });

            this.resetChangeTracking();
            
            if (!silent) {
                ScannerBase.showAlert('Settings saved successfully', 'success');
                ScannerBase.addLogEntry('System settings updated', 'info');
            }

        } catch (error) {
            ScannerBase.showAlert(`Failed to save settings: ${error.message}`, 'error');
        } finally {
            if (!silent) {
                ScannerBase.hideLoading();
            }
        }
    },

    /**
     * Collect all current settings
     */
    collectAllSettings() {
        const settings = {};
        const settingInputs = document.querySelectorAll('.setting-input, .setting-toggle input, .matrix-input');
        
        settingInputs.forEach(input => {
            const key = input.id || input.name;
            if (key) {
                settings[key] = this.getInputValue(input);
            }
        });

        return settings;
    },

    /**
     * Reset settings to defaults
     */
    async resetSettings() {
        if (!confirm('Reset all settings to default values? This cannot be undone.')) {
            return;
        }

        try {
            ScannerBase.showLoading('Resetting settings...');

            const response = await ScannerBase.apiRequest('/api/settings/reset', {
                method: 'POST'
            });

            if (response.settings) {
                this.populateSettings(response.settings);
                this.resetChangeTracking();
            }

            ScannerBase.showAlert('Settings reset to defaults', 'info');
            ScannerBase.addLogEntry('Settings reset to factory defaults', 'info');

        } catch (error) {
            ScannerBase.showAlert(`Failed to reset settings: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Cancel unsaved changes
     */
    async cancelChanges() {
        if (!this.state.hasUnsavedChanges) {
            ScannerBase.showAlert('No unsaved changes to cancel', 'info', 2000);
            return;
        }

        if (!confirm('Cancel all unsaved changes?')) {
            return;
        }

        // Reload settings from server
        await this.loadCurrentSettings();
        ScannerBase.showAlert('Changes cancelled', 'info');
    },

    /**
     * Handle status updates
     */
    handleStatusUpdate(status) {
        // Update diagnostic displays if on diagnostics section
        if (this.state.currentSection === 'diagnostics') {
            this.updateDiagnosticDisplays(status);
        }
    },

    /**
     * Start diagnostic updates
     */
    startDiagnosticUpdates() {
        this.state.diagnosticTimer = setInterval(() => {
            if (this.state.currentSection === 'diagnostics') {
                this.updateDiagnostics();
            }
        }, this.config.diagnosticUpdateInterval);
    },

    /**
     * Start log updates
     */
    startLogUpdates() {
        this.state.logTimer = setInterval(() => {
            if (this.state.currentSection === 'diagnostics') {
                this.loadSystemLogs();
            }
        }, this.config.logUpdateInterval);
    },

    /**
     * Update diagnostic information
     */
    async updateDiagnostics() {
        try {
            const response = await ScannerBase.apiRequest('/api/diagnostics');
            this.updateDiagnosticDisplays(response);
        } catch (error) {
            ScannerBase.log('Failed to update diagnostics:', error);
        }
    },

    /**
     * Update diagnostic display elements
     */
    updateDiagnosticDisplays(data) {
        if (!data.system) return;

        const updates = [
            { id: 'cpuUsage', value: `${data.system.cpu_usage?.toFixed(1) || '--'}%` },
            { id: 'memoryUsage', value: `${data.system.memory_usage?.toFixed(1) || '--'}%` },
            { id: 'diskUsage', value: `${data.system.disk_usage?.toFixed(1) || '--'}%` },
            { id: 'temperature', value: `${data.system.temperature?.toFixed(1) || '--'}°C` },
            { id: 'uptime', value: this.formatUptime(data.system.uptime || 0) },
            { id: 'networkStatus', value: data.system.network_connected ? 'Connected' : 'Disconnected' }
        ];

        updates.forEach(({ id, value }) => {
            const element = document.getElementById(id);
            if (element) {
                element.textContent = value;
            }
        });
    },

    /**
     * Load and display system logs
     */
    async loadSystemLogs() {
        try {
            const response = await ScannerBase.apiRequest('/api/logs');
            this.updateLogDisplay(response.logs || []);
        } catch (error) {
            ScannerBase.log('Failed to load system logs:', error);
        }
    },

    /**
     * Update log display
     */
    updateLogDisplay(logs) {
        const logViewer = document.getElementById('systemLogs');
        if (!logViewer) return;

        // Limit to recent logs
        const recentLogs = logs.slice(-this.config.maxLogLines);
        
        logViewer.innerHTML = recentLogs.map(log => {
            const timestamp = new Date(log.timestamp).toLocaleTimeString();
            const levelClass = `log-level-${log.level.toLowerCase()}`;
            
            return `
                <div class="log-entry">
                    <span class="log-timestamp">${timestamp}</span>
                    <span class="${levelClass}">[${log.level}]</span>
                    <span class="log-message">${log.message}</span>
                </div>
            `;
        }).join('');

        // Auto-scroll to bottom
        logViewer.scrollTop = logViewer.scrollHeight;
    },

    /**
     * Format uptime string
     */
    formatUptime(seconds) {
        const days = Math.floor(seconds / 86400);
        const hours = Math.floor((seconds % 86400) / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (days > 0) {
            return `${days}d ${hours}h`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    },

    /**
     * Test motion system
     */
    async testMotionSystem() {
        try {
            ScannerBase.showLoading('Testing motion system...');
            ScannerBase.addLogEntry('Motion system test started', 'info');

            const response = await ScannerBase.apiRequest('/api/test/motion', {
                method: 'POST'
            });

            ScannerBase.showAlert(`Motion test completed: ${response.result}`, 'success');
            ScannerBase.addLogEntry(`Motion test result: ${response.details}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Motion test failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Motion test failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Test camera system
     */
    async testCameras() {
        try {
            ScannerBase.showLoading('Testing cameras...');
            ScannerBase.addLogEntry('Camera system test started', 'info');

            const response = await ScannerBase.apiRequest('/api/test/cameras', {
                method: 'POST'
            });

            ScannerBase.showAlert(`Camera test completed: ${response.cameras_tested} cameras tested`, 'success');
            ScannerBase.addLogEntry(`Camera test result: ${response.details}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Camera test failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Camera test failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Test lighting system
     */
    async testLighting() {
        try {
            ScannerBase.showLoading('Testing lighting...');
            ScannerBase.addLogEntry('Lighting system test started', 'info');

            const response = await ScannerBase.apiRequest('/api/test/lighting', {
                method: 'POST'
            });

            ScannerBase.showAlert(`Lighting test completed: ${response.zones_tested} zones tested`, 'success');
            ScannerBase.addLogEntry(`Lighting test result: ${response.details}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Lighting test failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Lighting test failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Run full diagnostic
     */
    async runFullDiagnostic() {
        try {
            ScannerBase.showLoading('Running full system diagnostic...');
            ScannerBase.addLogEntry('Full system diagnostic started', 'info');

            const response = await ScannerBase.apiRequest('/api/diagnostic/full', {
                method: 'POST'
            });

            const summary = `
                Motion: ${response.motion ? 'PASS' : 'FAIL'}
                Cameras: ${response.cameras ? 'PASS' : 'FAIL'}
                Lighting: ${response.lighting ? 'PASS' : 'FAIL'}
                System: ${response.system ? 'PASS' : 'FAIL'}
            `;

            ScannerBase.showAlert(`Diagnostic completed:\n${summary}`, 'info');
            ScannerBase.addLogEntry(`Full diagnostic completed: ${response.summary}`, 'info');

        } catch (error) {
            ScannerBase.showAlert(`Diagnostic failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`Full diagnostic failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * Create system backup
     */
    async createBackup() {
        try {
            ScannerBase.showLoading('Creating system backup...');
            ScannerBase.addLogEntry('System backup started', 'info');

            const response = await ScannerBase.apiRequest('/api/backup/create', {
                method: 'POST'
            });

            ScannerBase.showAlert(`Backup created: ${response.filename}`, 'success');
            ScannerBase.addLogEntry(`System backup created: ${response.filename}`, 'success');

        } catch (error) {
            ScannerBase.showAlert(`Backup failed: ${error.message}`, 'error');
            ScannerBase.addLogEntry(`System backup failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * System shutdown
     */
    async shutdownSystem() {
        if (!confirm('Shutdown the system? This will power off the scanner and require manual restart.')) {
            return;
        }

        try {
            ScannerBase.showLoading('Shutting down system...');
            ScannerBase.addLogEntry('System shutdown initiated', 'warning');

            await ScannerBase.apiRequest('/api/system/shutdown', {
                method: 'POST'
            });

            ScannerBase.showAlert('System shutdown initiated. The scanner will power off shortly.', 'warning');

        } catch (error) {
            ScannerBase.showAlert(`Shutdown failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    },

    /**
     * System reboot
     */
    async rebootSystem() {
        if (!confirm('Reboot the system? This will restart the scanner and may take several minutes.')) {
            return;
        }

        try {
            ScannerBase.showLoading('Rebooting system...');
            ScannerBase.addLogEntry('System reboot initiated', 'warning');

            await ScannerBase.apiRequest('/api/system/reboot', {
                method: 'POST'
            });

            ScannerBase.showAlert('System reboot initiated. The scanner will restart shortly.', 'warning');

        } catch (error) {
            ScannerBase.showAlert(`Reboot failed: ${error.message}`, 'error');
        } finally {
            ScannerBase.hideLoading();
        }
    }
};

// Global functions for HTML onclick handlers
window.showSection = (section) => SettingsManager.showSection(section);
window.saveSettings = () => SettingsManager.saveSettings();
window.resetSettings = () => SettingsManager.resetSettings();
window.cancelChanges = () => SettingsManager.cancelChanges();

// Diagnostic functions
window.testMotionSystem = () => SettingsManager.testMotionSystem();
window.testCameras = () => SettingsManager.testCameras();
window.testLighting = () => SettingsManager.testLighting();
window.runFullDiagnostic = () => SettingsManager.runFullDiagnostic();

// Log functions
window.refreshLogs = () => SettingsManager.loadSystemLogs();
window.downloadLogs = () => {
    const logs = document.getElementById('systemLogs')?.textContent || '';
    const blob = new Blob([logs], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `system_logs_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
};
window.clearLogs = () => {
    if (confirm('Clear system logs? This cannot be undone.')) {
        document.getElementById('systemLogs').innerHTML = '<div class="log-entry"><span class="log-timestamp">Logs cleared</span></div>';
    }
};

// Maintenance functions
window.createBackup = () => SettingsManager.createBackup();
window.restoreBackup = () => {
    ScannerBase.showAlert('Backup restore functionality coming soon', 'info');
};
window.downloadBackup = () => {
    ScannerBase.showAlert('Backup download functionality coming soon', 'info');
};
window.checkUpdates = () => {
    ScannerBase.showAlert('Update check functionality coming soon', 'info');
};
window.updateSystem = () => {
    ScannerBase.showAlert('System update functionality coming soon', 'info');
};
window.updateFirmware = () => {
    ScannerBase.showAlert('Firmware update functionality coming soon', 'info');
};

// Calibration functions
window.calibrateMotion = () => {
    ScannerBase.showAlert('Motion calibration functionality coming soon', 'info');
};
window.calibrateCameras = () => {
    ScannerBase.showAlert('Camera calibration functionality coming soon', 'info');
};
window.calibrateLighting = () => {
    ScannerBase.showAlert('Lighting calibration functionality coming soon', 'info');
};
window.startCameraCalibration = () => {
    ScannerBase.showAlert('Camera calibration wizard coming soon', 'info');
};

// Utility functions
window.browseStorageLocation = () => {
    ScannerBase.showAlert('File browser functionality coming soon', 'info');
};
window.factoryReset = () => {
    if (!confirm('Perform factory reset? This will erase ALL settings and data. This cannot be undone.')) {
        return;
    }
    ScannerBase.showAlert('Factory reset functionality coming soon', 'warning');
};
window.shutdownSystem = () => SettingsManager.shutdownSystem();
window.rebootSystem = () => SettingsManager.rebootSystem();

// Initialize settings manager when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    ScannerBase.init();
    SettingsManager.init();
});