# Storage System & Desktop Integration Assessment

## Current State Analysis

### ✅ What's Already Implemented

#### 1. **Storage System** (`storage/session_manager.py`)
**Status: FULLY FUNCTIONAL**

The storage system is well-architected with:
- ✅ Session-based organization (each scan = one session)
- ✅ Hierarchical directory structure
- ✅ Metadata management (JSON-based indexing)
- ✅ Multi-location support (primary + backup)
- ✅ File integrity checking (MD5 checksums)
- ✅ Backup capabilities
- ✅ Archive functionality for old sessions

**Directory Structure:**
```
/home/pi/scanner_data/
├── sessions/
│   ├── [session_id]/
│   │   ├── scan_point_000_cam0.jpg
│   │   ├── scan_point_000_cam1.jpg
│   │   ├── scan_metadata.json
│   │   └── xmp_sidecar_files/
│   │       ├── scan_point_000_cam0.xmp
│   │       └── scan_point_000_cam1.xmp
├── exports/
├── backups/
├── temp/
└── metadata/
    └── sessions_index.json
```

#### 2. **Camera Position Export** (Already Complete!)
**Status: PRODUCTION READY**

From `CAMERA_POSITION_EXPORT_SUMMARY.md`, the system already exports:
- ✅ **XMP Sidecar Files** - RealityScan compatible
- ✅ **RealityCapture Text File** - Manual import backup
- ✅ **Meshroom Text File** - Meshroom geolocation
- ✅ **JSON Full Data** - Complete metadata

**Export happens automatically during scans!**

#### 3. **Existing Export Features**

**In `storage/session_manager.py`:**
- ✅ `export_session()` - Export session to ZIP or directory
- ✅ `backup_session()` - Backup specific session
- ✅ `archive_old_sessions()` - Archive old scans
- ✅ `get_storage_stats()` - Get storage usage info

**In `web/web_interface.py`:**
- ✅ `/api/scan/export_csv` - Export scan parameters to CSV

### ⚠️ What's Missing for Desktop Integration

#### 1. **No Network Export API**
- ❌ No endpoint to list available scan sessions
- ❌ No endpoint to download session data remotely
- ❌ No endpoint to check export status
- ❌ No network file transfer capability

#### 2. **No Desktop Client Protocol**
- ❌ No defined API for PC software to communicate with Pi
- ❌ No session discovery mechanism
- ❌ No progress tracking for large downloads

#### 3. **No Export Queue System**
- ❌ Cannot prepare exports in background
- ❌ No notification when export is ready
- ❌ No batch export capability

## Desktop Integration Requirements

### Use Case: Transfer Scans to PC for Processing

**User Story:**
1. User completes scan on Raspberry Pi
2. Opens desktop software on PC (Windows/Linux)
3. Desktop app discovers Pi scanner on network
4. User browses available scan sessions
5. User selects session(s) to download
6. Desktop app downloads images + metadata
7. Desktop app launches photogrammetry processing

### Technical Requirements

#### A. **Discovery & Connection**
- Pi scanner broadcasts availability on local network
- Desktop app finds Pi scanner automatically
- Optional: Manual IP/hostname connection

#### B. **Session Management**
- List all available scan sessions with metadata:
  - Session name, date, scan count, file size
  - Thumbnail preview
  - Completion status
- Filter/search sessions by date, name, status

#### C. **Data Transfer**
- Download complete session (images + metadata + XMP files)
- Progress tracking with speed/ETA
- Resume capability for interrupted transfers
- Integrity verification (checksums)

#### D. **Export Formats**
- ZIP archive (compressed, single download)
- Directory structure (organized folders)
- Selective download (only specific cameras/points)

#### E. **Processing Integration**
- Auto-detect and launch photogrammetry software
- Import camera positions automatically
- Batch processing support

## Recommended Implementation Plan

### Phase 1: REST API for Session Discovery (1-2 days)

**New Endpoints in `web/web_interface.py`:**

```python
# List all scan sessions
GET /api/storage/sessions
Response: [{
    "session_id": "abc123",
    "scan_name": "Dragon Scan",
    "start_time": "2025-10-13T10:30:00",
    "total_files": 288,
    "total_size_mb": 1250,
    "status": "completed",
    "thumbnail": "base64_encoded_preview"
}]

# Get session details
GET /api/storage/sessions/<session_id>
Response: {
    "session_id": "abc123",
    "scan_name": "Dragon Scan",
    "scan_parameters": {...},
    "file_list": ["file1.jpg", "file2.jpg", ...],
    "metadata_available": true,
    "xmp_available": true
}

# Get storage statistics
GET /api/storage/stats
Response: {
    "total_capacity_gb": 128,
    "used_space_gb": 45,
    "available_space_gb": 83,
    "session_count": 12,
    "total_files": 3456
}

# Delete session (cleanup)
DELETE /api/storage/sessions/<session_id>
Response: {"success": true, "freed_space_mb": 1250}
```

### Phase 2: Export Preparation System (2-3 days)

**New Endpoints:**

```python
# Request export preparation
POST /api/storage/sessions/<session_id>/prepare_export
Body: {
    "format": "zip",  # or "directory"
    "include_xmp": true,
    "include_metadata": true,
    "cameras": ["camera_0", "camera_1"]  # optional filter
}
Response: {
    "export_id": "export_xyz",
    "status": "preparing",
    "estimated_size_mb": 1250
}

# Check export status
GET /api/storage/exports/<export_id>/status
Response: {
    "export_id": "export_xyz",
    "status": "ready",  # or "preparing", "failed"
    "progress_percent": 100,
    "download_url": "/api/storage/exports/export_xyz/download",
    "expires_at": "2025-10-14T10:30:00"
}

# Download prepared export
GET /api/storage/exports/<export_id>/download
Response: Binary file stream (ZIP or TAR)
```

**Background Export Worker:**
```python
class ExportWorker:
    """Background worker for preparing session exports"""
    
    async def prepare_export(self, session_id, export_config):
        # 1. Copy files to temp export directory
        # 2. Optionally compress to ZIP
        # 3. Calculate checksum
        # 4. Mark as ready for download
        # 5. Schedule cleanup after 24 hours
```

### Phase 3: Desktop Client Application (3-5 days)

**Technology Options:**

**Option A: Python Desktop App** (Recommended for rapid development)
- **Framework**: PyQt6 or Tkinter
- **Advantages**: 
  - Easy integration with photogrammetry tools
  - Cross-platform (Windows/Linux/Mac)
  - Can reuse existing Python codebase
- **File**: `PC/ScannerDesktopClient.py`

**Option B: Web-Based Dashboard** (Best for simplicity)
- **Framework**: Same Flask + HTML/JS as Pi web interface
- **Advantages**:
  - No installation required
  - Access from any device with browser
  - Reuse existing web UI code
- **File**: `PC/WebDashboard/`

**Option C: Electron App** (Most polished UI)
- **Framework**: Electron + React
- **Advantages**:
  - Modern UI
  - Native app feel
  - Bundled installer
- **Disadvantages**: More complex, larger file size

**Core Features:**
```python
class ScannerDesktopClient:
    """Desktop client for managing scanner exports"""
    
    def __init__(self):
        self.scanner_ip = None
        self.available_sessions = []
        self.active_downloads = {}
    
    async def discover_scanner(self):
        """Discover Pi scanner on local network"""
        # Try mDNS/Bonjour discovery
        # Fallback to manual IP entry
    
    async def list_sessions(self):
        """Fetch available scan sessions from Pi"""
        response = await self.get(f"http://{self.scanner_ip}/api/storage/sessions")
        return response.json()
    
    async def download_session(self, session_id, destination_path):
        """Download session with progress tracking"""
        # 1. Request export preparation
        # 2. Poll for readiness
        # 3. Download with progress bar
        # 4. Verify integrity
        # 5. Extract if ZIP
        # 6. Launch photogrammetry software
```

### Phase 4: Advanced Features (Optional, 2-3 days)

**A. Live Preview During Scanning:**
```python
# Stream low-res preview images during active scan
GET /api/storage/sessions/<session_id>/preview
WebSocket: Real-time image thumbnails
```

**B. Remote Scan Control:**
```python
# Start scan from desktop
POST /api/scan/start
Body: {scan_template_id, scan_name}

# Monitor scan progress remotely
GET /api/scan/status
WebSocket: Real-time progress updates
```

**C. Cloud Sync Integration:**
```python
# Automatic upload to cloud storage
POST /api/storage/sessions/<session_id>/sync_cloud
Body: {
    "provider": "google_drive",  # or "dropbox", "onedrive"
    "credentials": {...}
}
```

## File Structure After Implementation

```
RaspPI/V2.0/
├── storage/
│   ├── base.py                    [Existing]
│   ├── session_manager.py         [Existing - Minor updates]
│   └── export_worker.py           [NEW - Background export prep]
├── web/
│   ├── web_interface.py           [UPDATE - Add storage APIs]
│   └── export_handler.py          [NEW - Export management]
└── api/
    └── storage_api.py             [NEW - Dedicated storage endpoints]

PC/
├── ScannerDesktopClient.py        [NEW - Main desktop app]
├── scanner_discovery.py           [NEW - Network discovery]
├── download_manager.py            [NEW - Download handling]
└── requirements.txt               [NEW - Desktop dependencies]
```

## Quick Start Implementation Guide

### Step 1: Add Storage API Endpoints (30 minutes)

Edit `web/web_interface.py`, add after existing routes:

```python
@self.app.route('/api/storage/sessions', methods=['GET'])
def api_storage_sessions():
    """List all scan sessions"""
    try:
        if not hasattr(self.orchestrator, 'storage_manager'):
            return jsonify({"error": "Storage not available"}), 503
        
        sessions = []
        sessions_index = self.orchestrator.storage_manager.sessions_index
        
        for session_id, session in sessions_index.items():
            sessions.append({
                "session_id": session_id,
                "scan_name": session.scan_name,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "total_files": session.total_files,
                "total_size_bytes": session.total_size_bytes,
                "status": session.status
            })
        
        # Sort by start time (newest first)
        sessions.sort(key=lambda x: x['start_time'], reverse=True)
        
        return jsonify({"sessions": sessions, "count": len(sessions)})
    
    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        return jsonify({"error": str(e)}), 500

@self.app.route('/api/storage/sessions/<session_id>', methods=['GET'])
def api_storage_session_details(session_id):
    """Get detailed session information"""
    try:
        session = await self.orchestrator.storage_manager.get_session(session_id)
        if not session:
            return jsonify({"error": "Session not found"}), 404
        
        # Get file list
        session_path = self.orchestrator.storage_manager.base_storage_path / 'sessions' / session_id
        files = []
        if session_path.exists():
            for file in session_path.glob('*.jpg'):
                files.append({
                    "filename": file.name,
                    "size_bytes": file.stat().st_size
                })
        
        return jsonify({
            **session.to_dict(),
            "files": files,
            "file_count": len(files)
        })
    
    except Exception as e:
        logger.error(f"Failed to get session details: {e}")
        return jsonify({"error": str(e)}), 500
```

### Step 2: Create Simple PC Download Script (15 minutes)

Create `PC/download_scan.py`:

```python
#!/usr/bin/env python3
"""
Simple script to download scan from Raspberry Pi
"""
import requests
import json
from pathlib import Path

# Configuration
SCANNER_IP = "192.168.1.xxx"  # Replace with your Pi's IP
DOWNLOAD_DIR = Path.home() / "ScannerDownloads"

def list_available_scans():
    """List available scans on Pi"""
    response = requests.get(f"http://{SCANNER_IP}:5000/api/storage/sessions")
    data = response.json()
    
    print(f"\n📋 Available Scans ({data['count']} total):\n")
    for i, session in enumerate(data['sessions']):
        print(f"{i+1}. {session['scan_name']}")
        print(f"   ID: {session['session_id']}")
        print(f"   Files: {session['total_files']}")
        print(f"   Size: {session['total_size_bytes'] / 1024**2:.1f} MB")
        print()
    
    return data['sessions']

def download_scan(session_id, scan_name):
    """Download scan session"""
    print(f"🔽 Downloading {scan_name}...")
    
    # Get session details
    response = requests.get(f"http://{SCANNER_IP}:5000/api/storage/sessions/{session_id}")
    session_data = response.json()
    
    # Create download directory
    download_path = DOWNLOAD_DIR / scan_name
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Download each file
    for file in session_data['files']:
        filename = file['filename']
        file_url = f"http://{SCANNER_IP}:5000/sessions/{session_id}/{filename}"
        
        print(f"  Downloading {filename}...")
        file_response = requests.get(file_url, stream=True)
        
        with open(download_path / filename, 'wb') as f:
            for chunk in file_response.iter_content(chunk_size=8192):
                f.write(chunk)
    
    print(f"✅ Download complete: {download_path}")

if __name__ == "__main__":
    # List scans
    sessions = list_available_scans()
    
    # Get user choice
    choice = int(input("Enter scan number to download: ")) - 1
    
    if 0 <= choice < len(sessions):
        download_scan(sessions[choice]['session_id'], sessions[choice]['scan_name'])
    else:
        print("❌ Invalid choice")
```

### Step 3: Test the Integration (10 minutes)

```bash
# On Raspberry Pi:
cd ~/Documents/RaspPI/V2.0
python run_web_interface.py

# On PC:
cd PC
python download_scan.py
```

## Priority Recommendations

### 🔥 IMMEDIATE (Do This First)
1. **Add storage API endpoints** (Step 1 above) - 30 minutes
2. **Create simple download script** (Step 2 above) - 15 minutes
3. **Test with one scan** - 10 minutes

**Why**: Gets basic functionality working in <1 hour

### 📈 SHORT TERM (Next Session)
4. **Add export preparation worker** - 2 hours
5. **Add ZIP download endpoint** - 1 hour
6. **Create GUI desktop app** - 4 hours

**Why**: Professional workflow with progress tracking

### 🚀 FUTURE ENHANCEMENTS (Later)
7. **Add scanner discovery (mDNS)** - 2 hours
8. **Add cloud sync** - 4 hours
9. **Add live preview** - 3 hours

**Why**: Nice-to-have features for advanced users

## Key Insights

1. **Storage system is solid** - No major changes needed to core storage
2. **Export already works** - Just need network access to it
3. **Camera positions already exported** - XMP files ready for photogrammetry
4. **Main gap is network API** - Need endpoints to expose existing functionality
5. **Simple solution first** - Basic HTTP download before complex protocols

## Next Steps

Would you like me to:
1. **Implement the basic API endpoints** (30 min task)?
2. **Create the simple PC download script** (15 min task)?
3. **Design a more sophisticated desktop app UI**?
4. **Add progress tracking and resumable downloads**?

Let me know which direction you'd like to go, and I'll provide the specific implementation!
