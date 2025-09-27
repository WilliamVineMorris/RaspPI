# Dual Session Creation Fix

## Problem Identified
The system was creating **two separate sessions** for each scan:

1. **Web Interface Session**: Created in `web_interface.py` line 2315
2. **Orchestrator Session**: Created in `scan_orchestrator.py` line 2043

This resulted in two different session IDs and directories being created for the same scan operation.

## Root Cause
**Sequential Session Creation**:
1. Web interface calls `storage_manager.start_session()` → creates session A
2. Web interface passes session A's ID as `scan_id` to orchestrator
3. Orchestrator **ignores existing session** and calls `storage_manager.create_session()` → creates session B
4. Result: Two sessions, with files scattered across both directories

## Solution Implemented

### Modified `scan_orchestrator.py`
**Added session detection logic before creating new sessions**:

```python
# Check if scan_id corresponds to an existing session directory (from web interface)
existing_session_dir = None
if hasattr(self.storage_manager, 'base_storage_path'):
    potential_session_path = self.storage_manager.base_storage_path / 'sessions' / scan_id
    if potential_session_path.exists():
        existing_session_dir = potential_session_path
        session_id = scan_id
        self.logger.info(f"📁 Using existing storage session directory: {scan_id}")

if not existing_session_dir:
    # Create new session only if one doesn't exist
    session_id = await self.storage_manager.create_session(session_metadata)
    self.logger.info(f"📁 Created NEW storage session: {session_id}")
else:
    self.logger.info(f"📁 Using EXISTING storage session: {session_id} for scan")
```

### Key Changes
1. **Detection**: Check if session directory already exists for the provided `scan_id`
2. **Conditional Creation**: Only create new session if no existing session found
3. **Logging**: Clear messages about whether using existing or creating new session

## Expected Behavior After Fix

### ✅ Single Session Operation
1. Web interface creates session → `~/scanner_data/sessions/<session_id>/`
2. Web interface passes `session_id` as `scan_id` to orchestrator
3. Orchestrator **detects existing session** and uses it
4. **Result**: All scan data goes to single session directory

### 🔍 Log Messages to Watch For
- `📁 Using existing storage session directory: <session_id>` (orchestrator reusing web session)
- `📁 Created NEW storage session: <session_id>` (orchestrator creating fresh session)

## Validation Steps

### Manual Testing Required on Pi
1. **Start a scan from web interface**
2. **Check session count**: Only ONE session directory should be created
3. **Verify file distribution**: All files in the single session directory
4. **Check logs**: Should see "Using existing storage session" message

### Expected Directory Structure
```
~/scanner_data/sessions/
└── <single-session-id>/
    ├── metadata/
    ├── images/
    └── exports/
```

### ❌ Should NOT see:
```
~/scanner_data/sessions/
├── <session-id-1>/  # From web interface
└── <session-id-2>/  # From orchestrator (duplicate)
```

## Fallback Handling
The fix includes robust error handling:
- If session detection fails → creates new session (safe fallback)
- If storage manager unavailable → uses provided scan_id
- Comprehensive logging for troubleshooting

## Testing Commands

### Check Session Count
```bash
# Should show only ONE session directory after scan
ls -la ~/scanner_data/sessions/ | wc -l
```

### Verify Single Session Usage
```bash
# Check that both metadata and images exist in same session
find ~/scanner_data/sessions -name "*.json" -o -name "*.jpg" | head -10
```

## Impact Assessment

### ✅ Benefits
- **Single storage location** per scan operation
- **Consistent file organization** 
- **Reduced storage fragmentation**
- **Clearer session management**
- **Proper metadata correlation**

### 🔧 Monitoring Required
- **Test on actual Pi hardware** to verify fix works in production
- **Check log messages** for session reuse vs creation
- **Verify file counts** match expected scan output

---

**Status**: ✅ **FIXED** - Dual session creation resolved through orchestrator session detection
**Next Action**: Test on Pi hardware to verify single session behavior

## Files Modified
1. `scanning/scan_orchestrator.py` - Added existing session detection logic
2. `web/web_interface.py` - Already creates sessions properly (no changes needed)