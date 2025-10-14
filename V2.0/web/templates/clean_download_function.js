// Clean downloadSession function to replace the corrupted one in sessions.html

// Track ongoing downloads to prevent duplicates
const activeDownloads = new Set();

// Download entire session as ZIP file
async function downloadSession(sessionId, scanName) {
    // Prevent multiple simultaneous downloads of the same session
    if (activeDownloads.has(sessionId)) {
        console.log('Download already in progress for session:', sessionId);
        return;
    }
    
    if (!confirm(`Download "${scanName}" as ZIP file?\n\nThis will create a ZIP archive and may take 10-30 seconds depending on scan size.`)) {
        return;
    }
    
    // Mark this session as being downloaded
    activeDownloads.add(sessionId);
    
    // Disable the download button and show spinner
    const downloadButtons = document.querySelectorAll(`button[data-session-id="${sessionId}"].btn-download`);
    downloadButtons.forEach(btn => {
        btn.disabled = true;
        btn.style.opacity = '0.6';
        btn.style.cursor = 'not-allowed';
        btn.innerHTML = '⏳ Creating ZIP...';
    });
    
    try {
        // Start download by navigating browser to download URL
        const downloadUrl = `/api/storage/sessions/${sessionId}/download`;
        window.location.href = downloadUrl;
        
        // Reset button after a delay
        setTimeout(() => {
            downloadButtons.forEach(btn => {
                btn.disabled = false;
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.innerHTML = '⬇️ Download';
            });
            activeDownloads.delete(sessionId);
        }, 5000);
        
    } catch (error) {
        console.error('Error downloading session:', error);
        // Reset buttons on error
        downloadButtons.forEach(btn => {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.cursor = 'pointer';
            btn.innerHTML = '⬇️ Download';
        });
        activeDownloads.delete(sessionId);
        showAlert('Failed to download session', 'error');
    }
}