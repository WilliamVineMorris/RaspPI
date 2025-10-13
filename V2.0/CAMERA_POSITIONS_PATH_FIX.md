# Camera Positions Path Fix

## Issue
Camera positions showed as "Not Available" even for successful scans with 288 captured images.

## Root Cause
**Path mismatch between save location and check location:**

- **Scan Orchestrator** saves camera positions to:
  ```
  /sessions/{session_id}/camera_positions_full.json
  ```
  (Session root directory - see `scan_orchestrator.py` line 4579)

- **Web Interface** was checking:
  ```
  /sessions/{session_id}/metadata/camera_positions_full.json
  ```
  (Metadata subdirectory - incorrect)

## Fix Applied
**File**: `web/web_interface.py` (lines 2391-2394)

**Before**:
```python
has_camera_positions = (metadata_dir / 'camera_positions_full.json').exists() if metadata_dir.exists() else False
```

**After**:
```python
# Camera positions are saved to session root, not metadata subdirectory
has_camera_positions = (session_path / 'camera_positions_full.json').exists()
```

## Files Modified
- `web/web_interface.py` - Updated camera positions detection path

## Testing Steps
1. Copy updated `web_interface.py` to Pi at `/home/user/Documents/RaspPI/V2.0/web/`
2. Restart web server if running
3. Reload sessions page or click "🔄 Reload & Refresh"
4. Click "View" on session `f85e72e5-225a-4199-90c1-322bfee968f0`
5. Verify "CAMERA POSITIONS" shows "✅ Available" instead of "❌ Not Available"

## Expected Result
For successful scans with camera position data:
- **CAMERA POSITIONS**: ✅ Available (green checkmark)

## Related Files
The camera positions export happens in:
- `scanning/scan_orchestrator.py` lines 4560-4640
- Creates multiple formats: JSON, RealityCapture TXT, Meshroom TXT, XMP sidecar files

## Note
This fix only corrects the **detection** of existing camera position files. The actual file generation during scanning was already working correctly - we just weren't finding it because we were looking in the wrong directory.

## Status
✅ **FIXED** - Code updated, ready for deployment to Pi
