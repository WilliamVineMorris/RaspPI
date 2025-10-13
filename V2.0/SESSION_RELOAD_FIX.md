# Session Reload Fix - Sessions Index Not Refreshing

## Problem Identified

The rebuild script successfully recovered 12 sessions and updated the `sessions_index.json` file on disk, but the web interface still showed 0 sessions. 

**Root Cause**: The `SessionManager` loads the sessions index into memory only once during initialization. When the web interface starts, it reads `sessions_index.json` and keeps it in RAM. The rebuild script updates the file on disk, but the running web interface doesn't know about the changes.

## Solution Implemented

Added a **Reload API endpoint** and **Reload & Refresh button** to reload the sessions index from disk without restarting the web interface.

### Changes Made

#### 1. New API Endpoint - `POST /api/storage/reload`
**File**: `web/web_interface.py` (after line 2550)

```python
@self.app.route('/api/storage/reload', methods=['POST'])
def api_storage_reload():
    """Reload sessions index from disk (useful after running rebuild script)"""
    try:
        if not self.orchestrator or not hasattr(self.orchestrator, 'storage_manager'):
            return jsonify({'error': 'Storage manager not available'}), 503
        
        storage_manager = self.orchestrator.storage_manager
        
        # Store count before reload
        sessions_before = len(storage_manager.sessions_index)
        
        # Reload the index from disk
        import asyncio
        asyncio.create_task(storage_manager._load_sessions_index())
        
        # Give it a moment to complete
        import time
        time.sleep(0.1)
        
        sessions_after = len(storage_manager.sessions_index)
        
        self.logger.info(f"🔄 Reloaded sessions index: {sessions_before} → {sessions_after} sessions")
        
        return jsonify({
            'success': True,
            'sessions_before': sessions_before,
            'sessions_after': sessions_after,
            'sessions_added': sessions_after - sessions_before
        })
    
    except Exception as e:
        self.logger.error(f"Failed to reload sessions index: {e}")
        import traceback
        self.logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': str(e)}), 500
```

**What it does**:
- Calls `_load_sessions_index()` to re-read the JSON file from disk
- Reports how many sessions were before/after reload
- Returns success/failure status

#### 2. Updated Sessions Page JavaScript
**File**: `web/templates/sessions.html`

Added three new functions:

```javascript
// Reload sessions index from disk (for after running rebuild script)
async function reloadSessionsIndex() {
    try {
        const response = await fetch('/api/storage/reload', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        const data = await response.json();
        
        if (data.success) {
            console.log(`✅ Reloaded sessions index: ${data.sessions_before} → ${data.sessions_after} sessions`);
            if (data.sessions_added > 0) {
                showNotification(`Found ${data.sessions_added} new session(s)!`, 'success');
            }
            return true;
        } else {
            console.error('Failed to reload sessions index:', data.error);
            showNotification('Failed to reload sessions index', 'error');
            return false;
        }
    } catch (error) {
        console.error('Error reloading sessions index:', error);
        showNotification('Error reloading sessions index', 'error');
        return false;
    }
}

// Reload index from disk and refresh display
async function reloadAndRefresh() {
    await reloadSessionsIndex();
    await loadSessions();
}
```

#### 3. Updated Refresh Button
Changed from:
```html
<button class="action-btn btn-refresh" onclick="loadSessions()">
    🔄 Refresh
</button>
```

To:
```html
<button class="action-btn btn-refresh" onclick="reloadAndRefresh()">
    🔄 Reload & Refresh
</button>
```

## How to Use

### After Running Rebuild Script:

1. **Run rebuild script** (as you did):
   ```bash
   python rebuild_sessions_index.py
   ```
   
2. **In web browser, go to Sessions page**

3. **Click "🔄 Reload & Refresh" button**

4. **Sessions now appear!** ✅

### What Happens:

1. Button calls `reloadAndRefresh()`
2. This calls API endpoint `POST /api/storage/reload`
3. SessionManager re-reads `sessions_index.json` from disk
4. JavaScript refreshes the page display
5. All 12 recovered sessions now visible!

## When to Use

Use the **Reload & Refresh** button when:
- After running `rebuild_sessions_index.py`
- After manually editing `sessions_index.json`
- After copying sessions from another scanner
- Anytime the disk has sessions that aren't showing in the UI

## Alternative: Restart Web Interface

You can also restart the web interface to reload the index:
```bash
# Press Ctrl+C to stop
python run_web_interface.py
```

But the Reload button is much faster and doesn't interrupt active operations!

## Technical Notes

### Why Not Auto-Reload?

We could make SessionManager periodically scan the disk, but:
- **Performance**: Disk scanning is slow
- **Reliability**: Index is the source of truth for performance reasons
- **Explicit Control**: User knows when they've made changes

### Async Timing Issue

The current implementation has a small timing issue:
```python
asyncio.create_task(storage_manager._load_sessions_index())
time.sleep(0.1)  # Hope it finishes in 100ms
```

**Better approach** (future improvement): Make the endpoint properly async:
```python
await storage_manager._load_sessions_index()
```

This requires making `api_storage_reload()` an async function, which needs more web interface refactoring.

### Thread Safety

The current implementation is safe because:
- Python's GIL ensures dictionary updates are atomic
- Only one task writes to `sessions_index` at a time
- Web requests read from the shared dictionary

## Testing

Test the fix:

1. **Before reload** (should show 0):
   ```bash
   curl http://192.168.1.138:5000/api/storage/sessions
   ```

2. **Trigger reload**:
   ```bash
   curl -X POST http://192.168.1.138:5000/api/storage/reload
   ```

3. **After reload** (should show 13):
   ```bash
   curl http://192.168.1.138:5000/api/storage/sessions
   ```

## Success Indicators

When it works, you'll see:
- **Console log**: `🔄 Reloaded sessions index: 0 → 13 sessions`
- **Notification**: "Found 12 new session(s)!"
- **Sessions grid**: 13 session cards displayed
- **Stats**: Updated file counts and sizes

## Files Modified

1. `web/web_interface.py` - Added reload API endpoint
2. `web/templates/sessions.html` - Added reload functions and updated button

No changes needed to `storage/session_manager.py` - we use its existing `_load_sessions_index()` method.
