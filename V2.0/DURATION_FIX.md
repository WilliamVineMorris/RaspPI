# Duration Showing "In progress" Fix

## The Problem

Sessions show "COMPLETED" status and actual file counts, but duration shows "In progress" instead of the actual scan duration.

**Example**:
```
Status: COMPLETED ✅
Files: 288
Size: 690.4 MB
Duration: In progress ❌  <- Should show actual time like "2h 15m"
```

## Root Cause

The `formatDuration()` function in JavaScript returns "In progress" when `end_time` is null/undefined:

```javascript
function formatDuration(startTime, endTime) {
    if (!startTime) return 'N/A';
    if (!endTime) return 'In progress';  // ❌ This is triggering
    
    const durationSeconds = endTime - startTime;
    // ...calculate hours/minutes...
}
```

The issue is that when the rebuild script loads existing `session.json` files, they have `end_time: null` in them, and we weren't updating this field when forcing recalculation.

## The Fix ✅

Updated `rebuild_sessions_index.py` to set `end_time` when updating session metadata if it's missing:

```python
elif base_data:
    # Use base metadata but UPDATE file counts with actual values
    base_data['total_files'] = total_files
    base_data['total_size_bytes'] = total_size
    
    # Update status based on actual file count
    if total_files > 0:
        base_data['status'] = 'completed'
    else:
        base_data['status'] = 'incomplete'
    
    # ✅ NEW: Ensure end_time is set (use directory mtime if missing)
    if not base_data.get('end_time'):
        stat_info = session_path.stat()
        base_data['end_time'] = stat_info.st_mtime
    
    return base_data
```

**What it does**:
- Checks if `end_time` is missing/null in the loaded session.json
- If missing, uses the directory's modification time as the end time
- This gives a reasonable estimate of when the scan finished

## Deploy and Test

### Step 1: Copy updated file to Pi
```bash
# File: rebuild_sessions_index.py
# Copy from PC to Pi (via Git or direct copy)
```

### Step 2: Run rebuild with --force again
```bash
cd ~/Documents/RaspPI/V2.0
python rebuild_sessions_index.py --force
```

This will:
- Recalculate file counts (already working ✅)
- Set status to 'completed' (already working ✅)
- **NEW**: Set `end_time` if missing ✅

### Step 3: Reload in browser
1. Go to http://192.168.1.138:5000/sessions
2. Page auto-reloads (from previous fix ✅)
3. Sessions should now show actual durations! ✅

## Expected Result

**Before**:
```
FILES: 288
SIZE: 690.4 MB
STARTED: 10/12/2025, 7:25:22 PM
DURATION: In progress ❌
```

**After**:
```
FILES: 288
SIZE: 690.4 MB
STARTED: 10/12/2025, 7:25:22 PM
DURATION: 2h 15m ✅
```

## How Duration is Calculated

### For Sessions with end_time:
```javascript
durationSeconds = end_time - start_time  // Both are Unix timestamps
// Convert to hours/minutes/seconds
// Example: 8100 seconds = 2h 15m
```

### For Sessions without end_time (after fix):
```python
# Uses directory modification time as estimate
end_time = session_path.stat().st_mtime
```

This is reasonable because:
- Directory mtime updates when files are added/modified
- For completed scans, last file write ≈ scan end time
- Not perfect but better than "In progress"

## Edge Cases

### Case 1: Scan actually in progress
- `end_time` will be null in session.json
- After rebuild, will get directory mtime
- Might show incorrect duration if scan is still running
- **Solution**: Active scans shouldn't be in completed state

### Case 2: Very old sessions
- Directory mtime might not reflect actual scan time
- But gives approximate duration
- Better than "In progress" for completed scans

### Case 3: Session with no files
- Status: 'incomplete'
- Still sets end_time
- Shows duration even for failed scans

## Technical Details

### Unix Timestamps
Both `start_time` and `end_time` are Unix timestamps (seconds since epoch):
```
start_time: 1697300722  (10/12/2025, 7:25:22 PM)
end_time:   1697308822  (10/12/2025, 9:40:22 PM)
duration:   8100 seconds = 2h 15m
```

### Directory stat()
```python
stat_info = session_path.stat()
stat_info.st_ctime  # Creation time
stat_info.st_mtime  # Modification time (last file written)
```

Using `st_mtime` makes sense because:
- It updates when files are added/modified in the directory
- For completed scans, last modification ≈ scan completion time

## Files Modified

✅ **Updated**: `rebuild_sessions_index.py`
- Added `end_time` setting when updating session metadata
- Uses directory mtime if end_time is missing
- Ensures all sessions have both start_time and end_time

## Success Indicators

After running the fixed rebuild script:

✅ Sessions show actual duration instead of "In progress"  
✅ Duration matches expected scan time  
✅ Completed sessions have proper end_time  
✅ Duration format shows hours/minutes correctly  

## Quick Test

Check a specific session's metadata after rebuild:

```bash
# View updated session data
cat /home/user/scanner_data/metadata/sessions_index.json | jq '.["45b1e43a-87c9-4fbd-b6ce-5a9cd7c2639e"]'
```

Should show:
```json
{
  "session_id": "45b1e43a-87c9-4fbd-b6ce-5a9cd7c2639e",
  "start_time": 1697300722,
  "end_time": 1697308822,     ✅ Should be non-null now!
  "scan_name": "tests",
  "status": "completed",
  "total_files": 288,
  "total_size_bytes": 724271104
}
```

Ready to deploy! 🚀
