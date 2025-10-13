#!/usr/bin/env python3
"""
Rebuild Sessions Index - V2.0 Storage System
=============================================

This script scans the storage directory for existing scan sessions
and rebuilds the sessions_index.json file. Use this when:
- Old sessions are not appearing in the Sessions web page
- After migrating from V1.0 to V2.0
- After manual file operations

Author: Scanner System Development
Date: October 13, 2025
"""

import json
import logging
from pathlib import Path
from datetime import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_storage_path():
    """Get the storage path from config or use default"""
    # Try to read from config
    config_file = Path(__file__).parent / 'config' / 'scanner_config.yaml'
    
    if config_file.exists():
        try:
            import yaml
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                base_path = config.get('storage', {}).get('base_path')
                if base_path:
                    return Path(base_path)
        except Exception as e:
            logger.warning(f"Could not read config: {e}")
    
    # Default path
    return Path('/home/pi/scanner_data')


def scan_session_directory(session_path: Path, force_recalculate: bool = False) -> dict:
    """
    Extract session metadata from directory
    
    Args:
        session_path: Path to session directory
        force_recalculate: If True, recalculate file counts even if session.json exists
    """
    try:
        session_id = session_path.name
        
        # Try to load session.json for base metadata
        metadata_file = session_path / 'metadata' / 'session.json'
        base_data = None
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    base_data = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load {metadata_file}: {e}")
        
        # Count files in images directory
        images_dir = session_path / 'images'
        total_files = 0
        total_size = 0
        
        if images_dir.exists():
            for file in images_dir.rglob('*'):
                if file.is_file():
                    total_files += 1
                    total_size += file.stat().st_size
        
        # If we have base_data and NOT forcing recalculation, use its file counts
        if base_data and not force_recalculate:
            # Use existing metadata as-is (may have wrong file counts)
            return base_data
        elif base_data:
            # Use base metadata but UPDATE file counts with actual values
            base_data['total_files'] = total_files
            base_data['total_size_bytes'] = total_size
            
            # Update status based on actual file count
            if total_files > 0:
                base_data['status'] = 'completed'
            else:
                base_data['status'] = 'incomplete'
            
            # Ensure end_time is set (use directory mtime if missing)
            if not base_data.get('end_time'):
                stat_info = session_path.stat()
                base_data['end_time'] = stat_info.st_mtime
            
            return base_data
        else:
            # No session.json found - create new metadata from scratch
            stat_info = session_path.stat()
            
            return {
                'session_id': session_id,
                'start_time': stat_info.st_ctime,
                'end_time': stat_info.st_mtime,
                'scan_name': f"Recovered Scan - {session_id}",
                'description': 'Recovered from existing session directory',
                'operator': 'Unknown',
                'total_files': total_files,
                'total_size_bytes': total_size,
                'scan_parameters': {},
                'status': 'completed' if total_files > 0 else 'incomplete'
            }
    
    except Exception as e:
        logger.error(f"Error scanning {session_path}: {e}")
        return None


def rebuild_sessions_index(base_path: Path, dry_run: bool = False, force_recalculate: bool = False):
    """
    Rebuild the sessions index by scanning the sessions directory
    
    Args:
        base_path: Base storage path
        dry_run: If True, only show what would be done without making changes
        force_recalculate: If True, recalculate metadata even for existing sessions
    """
    
    sessions_dir = base_path / 'sessions'
    index_file = base_path / 'metadata' / 'sessions_index.json'
    
    logger.info(f"📁 Scanning for sessions in: {sessions_dir}")
    logger.info(f"📋 Index file: {index_file}")
    logger.info(f"🔄 Force recalculate: {force_recalculate}")
    
    if not sessions_dir.exists():
        logger.error(f"❌ Sessions directory not found: {sessions_dir}")
        return
    
    # Load existing index
    existing_index = {}
    if index_file.exists():
        try:
            with open(index_file, 'r') as f:
                existing_index = json.load(f)
            logger.info(f"📚 Loaded existing index with {len(existing_index)} sessions")
        except Exception as e:
            logger.warning(f"⚠️  Could not load existing index: {e}")
    
    # Scan all session directories
    new_index = {}
    discovered = 0
    recovered = 0
    updated = 0
    
    for session_dir in sorted(sessions_dir.iterdir()):
        if session_dir.is_dir():
            session_id = session_dir.name
            
            # Check if already in index
            if session_id in existing_index and not force_recalculate:
                logger.info(f"  ✓ {session_id} - already in index")
                new_index[session_id] = existing_index[session_id]
                discovered += 1
            else:
                # New session found OR forcing recalculation - scan it
                session_data = scan_session_directory(session_dir, force_recalculate=force_recalculate)
                
                if session_data:
                    if session_id in existing_index:
                        logger.info(f"  � {session_id} - UPDATED")
                        updated += 1
                    else:
                        logger.info(f"  �🔍 {session_id} - RECOVERED")
                        recovered += 1
                    
                    logger.info(f"       Name: {session_data.get('scan_name')}")
                    logger.info(f"       Files: {session_data.get('total_files', 0)}")
                    logger.info(f"       Size: {session_data.get('total_size_bytes', 0) / (1024*1024):.1f} MB")
                    new_index[session_id] = session_data
    
    # Summary
    logger.info("")
    logger.info("="*70)
    logger.info(f"📊 SUMMARY")
    logger.info("="*70)
    logger.info(f"  Existing sessions:  {discovered}")
    logger.info(f"  Recovered sessions: {recovered}")
    logger.info(f"  Updated sessions:   {updated}")
    logger.info(f"  Total sessions:     {len(new_index)}")
    logger.info("")
    
    if dry_run:
        logger.info("🔍 DRY RUN - No changes made")
        logger.info(f"   Would update: {index_file}")
        return
    
    # Save new index
    if recovered > 0 or updated > 0 or len(new_index) != len(existing_index):
        try:
            # Ensure metadata directory exists
            index_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup existing index
            if index_file.exists():
                backup_file = index_file.parent / f'sessions_index_backup_{int(datetime.now().timestamp())}.json'
                import shutil
                shutil.copy(index_file, backup_file)
                logger.info(f"💾 Backed up existing index to: {backup_file}")
            
            # Write new index
            with open(index_file, 'w') as f:
                json.dump(new_index, f, indent=2)
            
            logger.info(f"✅ Successfully updated sessions index!")
            if recovered > 0:
                logger.info(f"   {recovered} sessions recovered and added to index")
            if updated > 0:
                logger.info(f"   {updated} sessions updated with recalculated metadata")
            
        except Exception as e:
            logger.error(f"❌ Failed to save index: {e}")
            import traceback
            logger.error(traceback.format_exc())
    else:
        logger.info("✓ No changes needed - index is up to date")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Rebuild sessions index from existing scan directories'
    )
    parser.add_argument(
        '--path',
        type=str,
        help='Base storage path (default: from config or /home/pi/scanner_data)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force recalculation of metadata for all sessions (even if already in index)'
    )
    
    args = parser.parse_args()
    
    # Get storage path
    if args.path:
        base_path = Path(args.path)
    else:
        base_path = get_storage_path()
    
    logger.info("="*70)
    logger.info("🔧 Sessions Index Rebuild Tool - V2.0")
    logger.info("="*70)
    logger.info(f"Base path: {base_path}")
    logger.info(f"Dry run:   {args.dry_run}")
    logger.info(f"Force:     {args.force}")
    logger.info("")
    
    if not base_path.exists():
        logger.error(f"❌ Storage path does not exist: {base_path}")
        return 1
    
    # Run rebuild
    rebuild_sessions_index(base_path, dry_run=args.dry_run, force_recalculate=args.force)
    
    logger.info("")
    logger.info("="*70)
    logger.info("✅ Done!")
    logger.info("="*70)
    logger.info("")
    logger.info("💡 Next steps:")
    logger.info("   1. Restart the web interface if it's running")
    logger.info("   2. Refresh the Sessions page in your browser")
    logger.info("   3. Your old scans should now appear!")
    logger.info("")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
