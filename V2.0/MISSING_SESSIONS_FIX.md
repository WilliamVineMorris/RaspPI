# Missing Sessions Fix - October 13, 2025

## Problem
Old scan sessions exist on disk but don't appear in the Sessions web page.

## Root Cause
The V2.0 storage system uses a `sessions_index.json` file to track all sessions. Old sessions created before this index system (or sessions where the index was corrupted/lost) won't appear in the web interface even though their files exist on disk.

## Solution
Run the `rebuild_sessions_index.py` script to scan your storage directory and rebuild the index from existing session folders.

## Usage

### On Raspberry Pi:

#### 1. Check what would be recovered (dry run):
```bash
cd /home/pi/RaspPI/V2.0
python rebuild_sessions_index.py --dry-run
```

This shows you what sessions would be recovered WITHOUT making any changes.

#### 2. Rebuild the index:
```bash
python rebuild_sessions_index.py
```

This will:
- ✅ Scan all session directories in `/home/pi/scanner_data/sessions/`
- ✅ Keep existing sessions in the index
- ✅ Add any missing sessions by reading their metadata
- ✅ Create backup of current index before updating
- ✅ Save updated index

#### 3. If your storage path is different:
```bash
python rebuild_sessions_index.py --path /your/custom/path
```

#### 4. Restart web interface:
```bash
# Stop current web interface (Ctrl+C if running in terminal)
# Then start it again:
python run_web_interface.py
```

#### 5. Refresh Sessions page:
Open browser and go to: `http://raspberrypi.local:5000/sessions`

Click the "Refresh" button or reload the page.

## What Gets Recovered

For each session directory found, the script will:

1. **If `metadata/session.json` exists**: Load full metadata including:
   - Session ID
   - Scan name
   - Description
   - Operator
   - Start/end times
   - Scan parameters
   - File count and total size

2. **If no metadata file exists**: Create basic metadata by:
   - Using directory name as session ID
   - Counting files in the `images/` directory
   - Calculating total size
   - Using file creation time as start time
   - Naming it "Recovered Scan - {session_id}"

## Safety Features

- ✅ **Backup**: Automatically backs up existing index before updating
- ✅ **Non-destructive**: Never deletes or modifies your actual scan files
- ✅ **Dry-run mode**: Test first without making changes
- ✅ **Preserves existing entries**: Keeps all sessions already in index

## Expected Output

```
======================================================================
🔧 Sessions Index Rebuild Tool - V2.0
======================================================================
Base path: /home/pi/scanner_data
Dry run:   False

📁 Scanning for sessions in: /home/pi/scanner_data/sessions
📋 Index file: /home/pi/scanner_data/metadata/sessions_index.json
📚 Loaded existing index with 2 sessions
  ✓ scan_20251010_143022 - already in index
  ✓ scan_20251011_091534 - already in index
  🔍 scan_20251009_152341 - RECOVERED
       Name: Dragon Figurine Scan
       Files: 48
       Size: 125.8 MB
  🔍 scan_20251008_163027 - RECOVERED
       Name: Recovered Scan - scan_20251008_163027
       Files: 36
       Size: 98.3 MB

======================================================================
📊 SUMMARY
======================================================================
  Existing sessions:  2
  Recovered sessions: 2
  Total sessions:     4

💾 Backed up existing index to: sessions_index_backup_1728825025.json
✅ Successfully updated sessions index!
   2 sessions recovered and added to index

======================================================================
✅ Done!
======================================================================

💡 Next steps:
   1. Restart the web interface if it's running
   2. Refresh the Sessions page in your browser
   3. Your old scans should now appear!
```

## Troubleshooting

### Script not finding sessions:
- Check the storage path: `ls /home/pi/scanner_data/sessions/`
- Verify directories exist and have correct permissions
- Try specifying path explicitly: `--path /home/pi/scanner_data`

### Sessions still not appearing in web interface:
1. Make sure you restarted the web interface after running the script
2. Check browser console for JavaScript errors (F12)
3. Try the API directly: `curl http://localhost:5000/api/storage/sessions`

### Permission errors:
```bash
# Make script executable if needed
chmod +x rebuild_sessions_index.py

# Run with sudo if permission denied
sudo python rebuild_sessions_index.py
```

## Alternative: Manual Index Creation

If the script doesn't work, you can manually check/create the index:

```bash
# Check if sessions directory exists
ls -la /home/pi/scanner_data/sessions/

# Check if index exists
cat /home/pi/scanner_data/metadata/sessions_index.json

# Create empty index if missing
mkdir -p /home/pi/scanner_data/metadata
echo '{}' > /home/pi/scanner_data/metadata/sessions_index.json
```

Then run the rebuild script.

## Questions?

The script is safe to run multiple times - it will only add missing sessions and never delete existing ones.
