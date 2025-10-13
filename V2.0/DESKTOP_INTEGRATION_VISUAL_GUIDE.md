# Desktop Integration - Quick Visual Guide

## Current System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi Scanner                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐   ┌───────────────┐  │
│  │   Camera     │───▶│   Storage    │──▶│   Export      │  │
│  │  Controller  │    │   Manager    │   │   (XMP files) │  │
│  └──────────────┘    └──────────────┘   └───────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Web Interface (Flask)                     │   │
│  │  • Scan control                                      │   │
│  │  • Camera preview                                    │   │
│  │  • Status monitoring                                 │   │
│  │  ⚠️ NO EXPORT API ⚠️                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            │ Port 5000                       │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             │ Local Network
                             │
                    ❌ NO CONNECTION ❌
                             │
                             ▼
┌────────────────────────────────────────────────────────────┐
│                       PC / Desktop                          │
│                                                              │
│  User manually:                                             │
│  1. SSH into Pi                                             │
│  2. SCP/FTP files manually                                  │
│  3. Import into photogrammetry software                     │
└─────────────────────────────────────────────────────────────┘
```

## Proposed System with Desktop Integration

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi Scanner                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐    ┌──────────────┐   ┌───────────────┐  │
│  │   Camera     │───▶│   Storage    │──▶│   Export      │  │
│  │  Controller  │    │   Manager    │   │   Worker      │  │
│  └──────────────┘    └──────────────┘   └───────────────┘  │
│         │                    │                    │          │
│         ▼                    ▼                    ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │         Enhanced Web Interface (Flask)               │   │
│  │                                                       │   │
│  │  Existing Routes:                                    │   │
│  │  • /api/scan/start                                   │   │
│  │  • /api/status                                       │   │
│  │  • /api/camera/preview                               │   │
│  │                                                       │   │
│  │  ✅ NEW Storage API Routes:                         │   │
│  │  • GET  /api/storage/sessions         (list scans)  │   │
│  │  • GET  /api/storage/sessions/<id>    (details)     │   │
│  │  • POST /api/storage/sessions/<id>/export           │   │
│  │  • GET  /api/storage/exports/<id>/download          │   │
│  │  • GET  /api/storage/stats            (disk usage)  │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            │ HTTP REST API                   │
└────────────────────────────┼─────────────────────────────────┘
                             │
                             │ Local Network (192.168.1.xxx)
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  Desktop Client Application                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │               Scanner Discovery                       │   │
│  │  • Auto-find Pi on network (mDNS)                    │   │
│  │  • Manual IP entry fallback                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │             Session Browser                           │   │
│  │  ┌─────┬──────────────┬───────┬──────┬──────────┐  │   │
│  │  │ ☑   │ Dragon Scan  │ 288   │ 1.2GB│ Download │  │   │
│  │  │ ☐   │ Car Model    │ 144   │ 850MB│ Download │  │   │
│  │  │ ☐   │ Statue       │ 192   │ 1.0GB│ Download │  │   │
│  │  └─────┴──────────────┴───────┴──────┴──────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │            Download Manager                           │   │
│  │  Progress: ████████████░░░░  75%                     │   │
│  │  Speed: 12.5 MB/s    ETA: 45 seconds                │   │
│  │  • Resume on disconnect                              │   │
│  │  • Verify checksums                                  │   │
│  │  • Extract ZIP automatically                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                                 │
│                            ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │        Photogrammetry Integration                     │   │
│  │  • Auto-detect RealityScan / Meshroom               │   │
│  │  • Import camera positions (XMP)                     │   │
│  │  • Launch processing                                 │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow - Download Session

```
Desktop App                     Pi Scanner                   Storage System
     │                               │                             │
     │  1. List Sessions             │                             │
     ├──────────────────────────────▶│                             │
     │                               │  Get sessions_index.json    │
     │                               ├────────────────────────────▶│
     │                               │◀────────────────────────────┤
     │◀──────────────────────────────┤   Return session list       │
     │  [{session1}, {session2}...]  │                             │
     │                               │                             │
     │  2. Request Export            │                             │
     ├──────────────────────────────▶│                             │
     │  POST /sessions/abc123/export │                             │
     │                               │  Create ZIP in background   │
     │                               ├────────────────────────────▶│
     │                               │  - Copy images              │
     │                               │  - Copy XMP files           │
     │                               │  - Copy metadata            │
     │                               │  - Calculate checksum       │
     │◀──────────────────────────────┤                             │
     │  {export_id: "exp456",        │◀────────────────────────────┤
     │   status: "preparing"}        │   Export ready              │
     │                               │                             │
     │  3. Poll Status (every 2s)    │                             │
     ├──────────────────────────────▶│                             │
     │◀──────────────────────────────┤                             │
     │  {status: "ready",            │                             │
     │   download_url: "/exports/... │                             │
     │                               │                             │
     │  4. Download ZIP              │                             │
     ├──────────────────────────────▶│                             │
     │                               │  Stream ZIP file            │
     │                               ├────────────────────────────▶│
     │◀══════════════════════════════╪═════════════════════════════│
     │    Binary stream (ZIP file)   │                             │
     │                               │                             │
     │  5. Verify & Extract          │                             │
     ├──────┐                        │                             │
     │      │ Check MD5              │                             │
     │      │ Extract to folder      │                             │
     │◀─────┘                        │                             │
     │                               │                             │
     │  6. Launch Photogrammetry     │                             │
     ├──────┐                        │                             │
     │      │ Open RealityScan       │                             │
     │      │ Import with XMP        │                             │
     │◀─────┘                        │                             │
```

## File Organization - Before & After Transfer

### On Pi (`/home/pi/scanner_data/sessions/abc123/`)
```
Before Export Request:
├── scan_point_000_cam0.jpg      (15 MB)
├── scan_point_000_cam1.jpg      (15 MB)
├── scan_point_001_cam0.jpg      (15 MB)
├── scan_point_001_cam1.jpg      (15 MB)
├── ... (288 files total)
├── xmp_sidecar_files/
│   ├── scan_point_000_cam0.xmp
│   ├── scan_point_000_cam1.xmp
│   └── ... (288 files)
├── scan_metadata.json
└── camera_positions_full.json

After Export Request:
└── /exports/exp456/
    └── Dragon_Scan_abc123.zip   (1.2 GB)
        Contains all above files
```

### On PC (`C:/Users/YourName/ScannerDownloads/Dragon_Scan/`)
```
After Download & Extract:
├── scan_point_000_cam0.jpg
├── scan_point_000_cam0.xmp      ← Ready for RealityScan
├── scan_point_000_cam1.jpg
├── scan_point_000_cam1.xmp
├── scan_point_001_cam0.jpg
├── scan_point_001_cam0.xmp
├── ... (576 files total - images + XMP)
├── scan_metadata.json
└── camera_positions_full.json
```

## Implementation Phases

### Phase 1: Minimal Viable Product (1 hour)
```
┌────────────────────────────────────────┐
│  Add 3 API endpoints to Pi:            │
│  • List sessions                       │
│  • Get session details                 │
│  • Serve files directly                │
└────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────┐
│  Create simple Python script on PC:    │
│  • Fetch session list                  │
│  • Download files with requests        │
│  • Show progress bar                   │
└────────────────────────────────────────┘
```

### Phase 2: Professional Solution (4-6 hours)
```
┌────────────────────────────────────────┐
│  Add export worker on Pi:              │
│  • Background ZIP creation             │
│  • Progress tracking                   │
│  • Automatic cleanup                   │
└────────────────────────────────────────┘
              │
              ▼
┌────────────────────────────────────────┐
│  Create GUI desktop app:               │
│  • Scanner discovery                   │
│  • Session browser with thumbnails     │
│  • Download queue management           │
│  • Integration with photogrammetry     │
└────────────────────────────────────────┘
```

### Phase 3: Advanced Features (Optional)
```
┌────────────────────────────────────────┐
│  • Cloud sync (Google Drive, etc.)     │
│  • WebSocket live preview              │
│  • Remote scan control                 │
│  • Batch processing automation         │
│  • Multi-scanner management            │
└────────────────────────────────────────┘
```

## Quick Start Checklist

**On Raspberry Pi:**
- [ ] Add `/api/storage/sessions` endpoint
- [ ] Add `/api/storage/sessions/<id>` endpoint
- [ ] Add file serving capability
- [ ] Test with curl/browser

**On PC:**
- [ ] Create `PC/download_scan.py`
- [ ] Install requests: `pip install requests`
- [ ] Configure Pi IP address
- [ ] Test download

**Estimated time: 45 minutes for basic working system**

---

Ready to implement? Let me know which phase you want to start with!
