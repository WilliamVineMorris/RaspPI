# ZIP Download Fix - Enhanced Logging and Compatibility

## Issue
ZIP download feature was not working - no logs appeared when users clicked download button, suggesting the request wasn't reaching the server or was failing silently.

## Root Causes Identified

### 1. Missing Flask Import
- `after_this_request` was used but not imported from Flask
- Would cause immediate import error when endpoint was called

### 2. Incompatible Parameter
- Used `download_name` parameter in `send_file()` 
- This parameter may not exist in older Flask versions on Pi
- Need to use `Content-Disposition` header instead

### 3. Insufficient Logging
- No logging at function entry
- Couldn't diagnose where the failure was occurring
- No visibility into ZIP creation progress

## Fixes Applied

### ✅ Fix 1: Added Flask Import
**File**: `web/web_interface.py` line 34
```python
# Before
from flask import Flask, render_template, jsonify, request, Response, redirect, url_for

# After  
from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, after_this_request
```

### ✅ Fix 2: Compatible send_file Implementation
**File**: `web/web_interface.py` lines 2612-2627

**Before**:
```python
return send_file(
    temp_zip_path,
    as_attachment=True,
    download_name=zip_filename,  # Not supported in older Flask
    mimetype='application/zip'
)
```

**After**:
```python
# Send file with explicit filename header
response = send_file(
    temp_zip_path,
    as_attachment=True,
    mimetype='application/zip'
)
# Set the download filename in the header (compatible with all Flask versions)
response.headers['Content-Disposition'] = f'attachment; filename="{zip_filename}"'
return response
```

### ✅ Fix 3: Proper Temp File Cleanup
Added `@after_this_request` decorator to ensure temp files are deleted after download:

```python
@after_this_request
def cleanup_temp_file(response):
    """Delete temp file after sending"""
    try:
        if os.path.exists(temp_zip_path):
            os.unlink(temp_zip_path)
            self.logger.debug(f"🗑️  Cleaned up temp ZIP: {temp_zip_path}")
    except Exception as e:
        self.logger.warning(f"Failed to cleanup temp ZIP: {e}")
    return response
```

### ✅ Fix 4: Comprehensive Logging
Added logging at every critical step:

1. **Request Entry** (line 2563):
```python
self.logger.info(f"📥 ZIP download requested for session: {session_id}")
```

2. **Validation Checks** (lines 2566, 2572, 2578):
```python
self.logger.error("Storage manager not available")
self.logger.error(f"Session {session_id} not found in index")
self.logger.error(f"Session directory does not exist: {session_path}")
```

3. **ZIP Creation Start** (line 2583):
```python
self.logger.info(f"📦 Creating ZIP for session: {session.scan_name} ({session_path})")
```

4. **Temp File Created** (line 2598):
```python
self.logger.info(f"📄 Temp ZIP file created: {temp_zip_path}")
```

5. **Progress Updates** (line 2610):
```python
if file_count % 50 == 0:
    self.logger.debug(f"Added {file_count} files to ZIP...")
```

6. **Completion** (line 2614):
```python
self.logger.info(f"📦 Created ZIP for session {session_id}: {zip_filename} ({file_count} files, {zip_size_mb:.1f} MB)")
```

7. **Error Handling** (line 2638):
```python
self.logger.error(f"Failed to create ZIP for session {session_id}: {e}")
import traceback
self.logger.error(f"Traceback: {traceback.format_exc()}")
```

## Expected Log Output (Success Case)

When user clicks download, you should now see:
```
2025-10-13 15:54:30 - web_interface - INFO - 📥 ZIP download requested for session: f85e72e5-225e-4199-90c1-322bfee968f0
2025-10-13 15:54:30 - web_interface - INFO - 📦 Creating ZIP for session: ScanName (/path/to/session)
2025-10-13 15:54:30 - web_interface - INFO - 📄 Temp ZIP file created: /tmp/tmpXXXXXX.zip
2025-10-13 15:54:35 - web_interface - DEBUG - Added 50 files to ZIP...
2025-10-13 15:54:40 - web_interface - DEBUG - Added 100 files to ZIP...
2025-10-13 15:54:45 - web_interface - DEBUG - Added 150 files to ZIP...
2025-10-13 15:54:50 - web_interface - DEBUG - Added 200 files to ZIP...
2025-10-13 15:54:55 - web_interface - DEBUG - Added 250 files to ZIP...
2025-10-13 15:55:00 - web_interface - INFO - 📦 Created ZIP for session f85e72e5...: ScanName.zip (288 files, 650.2 MB)
2025-10-13 15:55:00 - werkzeug - INFO - 192.168.1.42 - - [13/Oct/2025 15:55:00] "GET /api/storage/sessions/f85e72e5.../download HTTP/1.1" 200 -
2025-10-13 15:55:01 - web_interface - DEBUG - 🗑️  Cleaned up temp ZIP: /tmp/tmpXXXXXX.zip
```

## Expected Log Output (Error Cases)

### If storage manager not available:
```
2025-10-13 15:54:30 - web_interface - INFO - 📥 ZIP download requested for session: abc123...
2025-10-13 15:54:30 - web_interface - ERROR - Storage manager not available
2025-10-13 15:54:30 - werkzeug - INFO - 192.168.1.42 - - [13/Oct/2025 15:54:30] "GET /api/storage/sessions/abc123.../download HTTP/1.1" 503 -
```

### If session not found:
```
2025-10-13 15:54:30 - web_interface - INFO - 📥 ZIP download requested for session: invalid-id
2025-10-13 15:54:30 - web_interface - ERROR - Session invalid-id not found in index
2025-10-13 15:54:30 - werkzeug - INFO - 192.168.1.42 - - [13/Oct/2025 15:54:30] "GET /api/storage/sessions/invalid-id/download HTTP/1.1" 404 -
```

### If ZIP creation fails:
```
2025-10-13 15:54:30 - web_interface - INFO - 📥 ZIP download requested for session: f85e72e5...
2025-10-13 15:54:30 - web_interface - INFO - 📦 Creating ZIP for session: ScanName (/path/to/session)
2025-10-13 15:54:30 - web_interface - INFO - 📄 Temp ZIP file created: /tmp/tmpXXXXXX.zip
2025-10-13 15:54:31 - web_interface - ERROR - Failed to create ZIP for session f85e72e5...: [Errno 28] No space left on device
2025-10-13 15:54:31 - web_interface - ERROR - Traceback: ...
2025-10-13 15:54:31 - werkzeug - INFO - 192.168.1.42 - - [13/Oct/2025 15:54:31] "GET /api/storage/sessions/f85e72e5.../download HTTP/1.1" 500 -
```

## Testing Steps

### 1. Deploy Updated Code
```bash
# Copy updated web_interface.py to Pi
scp web/web_interface.py user@pi:/home/user/Documents/RaspPI/V2.0/web/
```

### 2. Restart Web Server
If not auto-reloading, restart the scanner system

### 3. Attempt Download
1. Open sessions page in browser
2. Click "⬇️ Download" on any session
3. Confirm the download dialog

### 4. Monitor Logs
Watch the terminal for log output - you should now see detailed progress

### 5. Verify Download
- Check browser downloads folder for ZIP file
- Filename should be `{ScanName}.zip`
- Extract and verify directory structure
- Check all files present

## Performance Expectations

### Small Session (16 files, 40 MB)
- ZIP creation: 1-3 seconds
- Download start: Immediate after creation
- Total time: 3-5 seconds

### Large Session (288 files, 690 MB)
- ZIP creation: 20-40 seconds (depends on Pi disk speed)
- Download start: Immediate after creation  
- Total time: 30-50 seconds + download time

**Note**: Progress logs every 50 files help user know it's working

## Troubleshooting

### Still No Logs Appearing
1. Check Flask is actually reloading the code:
   ```bash
   grep "after_this_request" /home/user/Documents/RaspPI/V2.0/web/web_interface.py
   ```
   Should show the import

2. Check Python process has restarted (check process start time)

### "500 Internal Server Error"
- Check logs for full traceback
- Common causes:
  - Out of disk space (need ~700 MB free for temp ZIP)
  - Permission issues with /tmp directory
  - Corrupted session files

### ZIP Downloads but is Corrupted
- Check disk space during creation
- Verify temp file wasn't deleted too early
- Check filesystem errors in system logs

### Download Starts but Browser Cancels
- Large file timeout - normal for 690 MB
- Check browser network timeout settings
- Consider chunked transfer for very large files

## Files Modified

1. **`web/web_interface.py`**:
   - Line 34: Added `after_this_request` import
   - Lines 2560-2640: Complete ZIP download endpoint with logging
   - Lines 2612-2627: Temp file cleanup handler
   - Lines 2617-2627: Compatible send_file implementation

2. **No frontend changes needed** - `sessions.html` already correct

## Status
✅ **READY FOR TESTING** - Deploy and test on Pi hardware

## Next Steps
1. Deploy updated `web_interface.py` to Pi
2. Test download with small session (16 files)
3. Test download with large session (288 files)  
4. Monitor logs to confirm endpoint is reached
5. Report results for further optimization if needed
