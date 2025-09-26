"""
Session-based Storage Manager Implementation

Concrete implementation of the StorageManager interface providing:
- Session-based scan data organization
- Multi-location storage with backup
- File integrity validation
- Export and synchronization capabilities

Author: Scanner System Development
Created: September 2025
"""

import asyncio
import logging
import time
import json
import hashlib
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple, Union, BinaryIO
import uuid

from storage.base import (
    StorageManager, StorageStatus, DataType, CompressionType,
    StorageLocation, StorageMetadata, ScanSession, StorageStats
)
from core.exceptions import StorageError, ConfigurationError
from core.events import EventBus, EventPriority

logger = logging.getLogger(__name__)


class SessionManager(StorageManager):
    """
    Session-based storage manager for scan data organization
    
    Features:
    - Hierarchical session organization
    - Multi-location storage with synchronization
    - Automatic backup and integrity checking
    - Export capabilities (ZIP, directory structures)
    - Metadata management and indexing
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Configuration
        self.base_storage_path = Path(config.get('base_path', '/home/pi/scanner_data'))
        self.backup_enabled = config.get('backup_enabled', True)
        self.compression_enabled = config.get('compression_enabled', False)
        self.integrity_checking = config.get('integrity_checking', True)
        
        # Session management
        self.sessions_index: Dict[str, ScanSession] = {}
        self.active_session_id: Optional[str] = None
        
        # Storage state
        self.status = StorageStatus.DISCONNECTED
        self.storage_locations = {}
        self._file_cache = {}
        
        # Event system
        self.event_bus = EventBus()
        
        # Initialize storage structure
        self._initialize_storage_structure()
        
        logger.info(f"SessionManager initialized with base path: {self.base_storage_path}")
    
    def _initialize_storage_structure(self):
        """Initialize the storage directory structure"""
        try:
            # Create base directories
            directories = [
                self.base_storage_path,
                self.base_storage_path / 'sessions',
                self.base_storage_path / 'exports',
                self.base_storage_path / 'backups',
                self.base_storage_path / 'temp',
                self.base_storage_path / 'metadata'
            ]
            
            for directory in directories:
                directory.mkdir(parents=True, exist_ok=True)
                
            # Create sessions index file if it doesn't exist
            index_file = self.base_storage_path / 'metadata' / 'sessions_index.json'
            if not index_file.exists():
                with open(index_file, 'w') as f:
                    json.dump({}, f, indent=2)
                    
            logger.info("Storage directory structure initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize storage structure: {e}")
            raise StorageError(f"Storage initialization failed: {e}")
    
    async def initialize(self) -> bool:
        """Initialize storage system"""
        try:
            # Load sessions index
            await self._load_sessions_index()
            
            # Setup default storage location
            default_location = StorageLocation(
                name="primary",
                path=str(self.base_storage_path),
                location_type="local",
                is_primary=True,
                max_size_gb=100.0,
                backup_enabled=self.backup_enabled
            )
            self.storage_locations["primary"] = default_location
            
            # Setup backup location if enabled
            if self.backup_enabled:
                backup_path = self.base_storage_path / 'backups'
                backup_location = StorageLocation(
                    name="backup",
                    path=str(backup_path),
                    location_type="backup",
                    is_primary=False,
                    max_size_gb=50.0,
                    backup_enabled=False
                )
                self.storage_locations["backup"] = backup_location
            
            self.status = StorageStatus.READY
            
            # Publish initialization event
            await self.event_bus.publish(
                "storage_initialized",
                {"locations": list(self.storage_locations.keys())},
                "storage",
                EventPriority.NORMAL
            )
            
            logger.info(f"Storage system initialized with {len(self.storage_locations)} locations")
            return True
            
        except Exception as e:
            logger.error(f"Storage initialization failed: {e}")
            self.status = StorageStatus.ERROR
            return False
    
    async def shutdown(self) -> bool:
        """Shutdown storage system and finalize current session"""
        try:
            # Finalize active session if any
            if self.active_session_id:
                await self.finalize_session(self.active_session_id)
            
            # Save sessions index
            await self._save_sessions_index()
            
            # Cleanup temporary files
            await self.cleanup_temp_files()
            
            self.status = StorageStatus.DISCONNECTED
            
            # Publish shutdown event
            await self.event_bus.publish(
                "storage_shutdown",
                {"sessions_count": len(self.sessions_index)},
                "storage",
                EventPriority.NORMAL
            )
            
            logger.info("Storage system shutdown complete")
            return True
            
        except Exception as e:
            logger.error(f"Storage shutdown failed: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if storage system is available"""
        return self.status in [StorageStatus.READY, StorageStatus.STORING]
    
    async def _load_sessions_index(self):
        """Load sessions index from disk"""
        try:
            index_file = self.base_storage_path / 'metadata' / 'sessions_index.json'
            
            if index_file.exists():
                with open(index_file, 'r') as f:
                    index_data = json.load(f)
                
                # Convert to ScanSession objects
                for session_id, session_data in index_data.items():
                    session = ScanSession(
                        session_id=session_data['session_id'],
                        start_time=session_data['start_time'],
                        end_time=session_data.get('end_time'),
                        scan_name=session_data.get('scan_name', 'Untitled Scan'),
                        description=session_data.get('description', ''),
                        operator=session_data.get('operator', 'Unknown'),
                        total_files=session_data.get('total_files', 0),
                        total_size_bytes=session_data.get('total_size_bytes', 0),
                        scan_parameters=session_data.get('scan_parameters', {}),
                        status=session_data.get('status', 'active')
                    )
                    self.sessions_index[session_id] = session
                    
            logger.info(f"Loaded {len(self.sessions_index)} sessions from index")
            
        except Exception as e:
            logger.error(f"Failed to load sessions index: {e}")
            self.sessions_index = {}
    
    async def _save_sessions_index(self):
        """Save sessions index to disk"""
        try:
            index_file = self.base_storage_path / 'metadata' / 'sessions_index.json'
            
            # Convert ScanSession objects to dict
            index_data = {}
            for session_id, session in self.sessions_index.items():
                index_data[session_id] = {
                    'session_id': session.session_id,
                    'start_time': session.start_time,
                    'end_time': session.end_time,
                    'scan_name': session.scan_name,
                    'description': session.description,
                    'operator': session.operator,
                    'total_files': session.total_files,
                    'total_size_bytes': session.total_size_bytes,
                    'scan_parameters': session.scan_parameters,
                    'status': session.status
                }
            
            with open(index_file, 'w') as f:
                json.dump(index_data, f, indent=2)
                
            logger.debug("Sessions index saved to disk")
            
        except Exception as e:
            logger.error(f"Failed to save sessions index: {e}")

    # Core Session Management Operations
    
    async def create_session(self, session_metadata: Dict[str, Any]) -> str:
        """Create new scan session"""
        try:
            session_id = str(uuid.uuid4())
            timestamp = time.time()
            
            # Create session object
            session = ScanSession(
                session_id=session_id,
                start_time=timestamp,
                scan_name=session_metadata.get('name', f"Scan_{datetime.fromtimestamp(timestamp).strftime('%Y%m%d_%H%M%S')}"),
                description=session_metadata.get('description', ''),
                operator=session_metadata.get('operator', 'Unknown'),
                scan_parameters=session_metadata.get('scan_parameters', {})
            )
            
            # Create session directory
            session_path = self.base_storage_path / 'sessions' / session_id
            session_path.mkdir(parents=True, exist_ok=True)
            
            # Create subdirectories
            (session_path / 'images').mkdir(exist_ok=True)
            (session_path / 'metadata').mkdir(exist_ok=True)
            (session_path / 'exports').mkdir(exist_ok=True)
            
            # Save session metadata
            metadata_file = session_path / 'metadata' / 'session.json'
            with open(metadata_file, 'w') as f:
                json.dump({
                    'session_id': session_id,
                    'scan_name': session.scan_name,
                    'description': session.description,
                    'operator': session.operator,
                    'start_time': timestamp,
                    'scan_parameters': session.scan_parameters
                }, f, indent=2)
            
            # Add to index
            self.sessions_index[session_id] = session
            self.current_session = session
            self.active_session_id = session_id
            
            # Save index
            await self._save_sessions_index()
            
            # Publish event
            if hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "session_created",
                    {"session_id": session_id, "scan_name": session.scan_name},
                    "storage"
                )
            
            logger.info(f"Created session '{session.scan_name}' with ID: {session_id}")
            return session_id
            
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise StorageError(f"Session creation failed: {e}")
    
    async def finalize_session(self, session_id: str) -> bool:
        """Finalize scan session"""
        try:
            if session_id not in self.sessions_index:
                raise StorageError(f"Session {session_id} not found")
            
            session = self.sessions_index[session_id]
            session.end_time = time.time()
            session.status = 'completed'
            
            # Calculate final statistics
            session_path = self.base_storage_path / 'sessions' / session_id
            total_size = 0
            file_count = 0
            
            for file_path in session_path.rglob('*'):
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size
            
            session.total_files = file_count
            session.total_size_bytes = total_size
            
            # Update session metadata file
            metadata_file = session_path / 'metadata' / 'session.json'
            with open(metadata_file, 'w') as f:
                json.dump({
                    'session_id': session_id,
                    'scan_name': session.scan_name,
                    'description': session.description,
                    'operator': session.operator,
                    'start_time': session.start_time,
                    'end_time': session.end_time,
                    'scan_parameters': session.scan_parameters,
                    'total_files': session.total_files,
                    'total_size_bytes': session.total_size_bytes,
                    'status': session.status
                }, f, indent=2)
            
            # Save index
            await self._save_sessions_index()
            
            # Clear active session
            if self.active_session_id == session_id:
                self.active_session_id = None
                self.current_session = None
            
            # Publish event
            if hasattr(self.event_bus, 'publish'):
                self.event_bus.publish(
                    "session_finalized",
                    {
                        "session_id": session_id,
                        "total_files": session.total_files,
                        "total_size_bytes": session.total_size_bytes
                    },
                    "storage"
                )
            
            logger.info(f"Finalized session {session_id} with {file_count} files ({total_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to finalize session {session_id}: {e}")
            return False
    
    async def get_session(self, session_id: str) -> Optional[ScanSession]:
        """Get session information"""
        return self.sessions_index.get(session_id)
    
    async def list_sessions(self, limit: int = 100) -> List[ScanSession]:
        """List scan sessions (most recent first)"""
        sessions = list(self.sessions_index.values())
        sessions.sort(key=lambda s: s.start_time, reverse=True)
        return sessions[:limit]
    
    # File Storage Operations
    async def store_file(self, file_data: bytes, metadata: StorageMetadata, 
                        location_name: Optional[str] = None) -> str:
        """Store file data with metadata"""
        try:
            if not self.active_session_id:
                raise StorageError("No active session for file storage")
            
            # Generate file ID and path
            file_id = str(uuid.uuid4())
            file_extension = metadata.file_extension or '.dat'
            filename = f"{metadata.filename or file_id}{file_extension}"
            
            session_path = self.base_storage_path / 'sessions' / self.active_session_id
            
            # Determine storage subdirectory based on data type
            if metadata.data_type in [DataType.SCAN_IMAGE, DataType.RAW_IMAGE, DataType.PROCESSED_IMAGE]:
                file_path = session_path / 'images' / filename
            else:
                file_path = session_path / 'metadata' / filename
            
            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file data
            with open(file_path, 'wb') as f:
                f.write(file_data)
            
            # Calculate checksum if integrity checking enabled
            checksum = None
            if self.integrity_checking:
                checksum = hashlib.sha256(file_data).hexdigest()
            
            # Store metadata
            metadata_dict = {
                'file_id': file_id,
                'filename': filename,
                'file_path': str(file_path),
                'session_id': self.active_session_id,
                'data_type': metadata.data_type.value,
                'file_size': len(file_data),
                'checksum': checksum,
                'created_at': datetime.now().isoformat(),
                'scan_point_id': metadata.scan_point_id,
                'camera_id': metadata.camera_id,
                'metadata': metadata.metadata
            }
            
            metadata_file = session_path / 'metadata' / f"{file_id}_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata_dict, f, indent=2)
            
            # Cache file info
            self._file_cache[file_id] = metadata_dict
            
            # Backup if enabled
            if self.backup_enabled and "backup" in self.storage_locations:
                await self._backup_file(file_path, file_id)
            
            logger.debug(f"Stored file {filename} with ID: {file_id}")
            return file_id
            
        except Exception as e:
            logger.error(f"Failed to store file: {e}")
            raise StorageError(f"File storage failed: {e}")
    
    async def retrieve_file(self, file_id: str) -> Tuple[bytes, StorageMetadata]:
        """Retrieve file data and metadata by ID"""
        try:
            # Get metadata first
            metadata = await self.get_metadata(file_id)
            if not metadata:
                raise StorageError(f"File {file_id} not found")
            
            # Check cache first
            if file_id in self._file_cache:
                file_info = self._file_cache[file_id]
                file_path = Path(file_info['file_path'])
                
                if file_path.exists():
                    with open(file_path, 'rb') as f:
                        data = f.read()
                    
                    # Verify integrity if enabled
                    if self.integrity_checking and file_info.get('checksum'):
                        calculated_checksum = hashlib.sha256(data).hexdigest()
                        if calculated_checksum != file_info['checksum']:
                            logger.error(f"Integrity check failed for file {file_id}")
                            raise StorageError(f"File integrity check failed: {file_id}")
                    
                    return data, metadata
            
            # Search for file if not in cache
            for session_id in self.sessions_index:
                session_path = self.base_storage_path / 'sessions' / session_id
                metadata_file = session_path / 'metadata' / f"{file_id}_metadata.json"
                
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        file_info = json.load(f)
                    
                    file_path = Path(file_info['file_path'])
                    if file_path.exists():
                        with open(file_path, 'rb') as f:
                            return f.read()
            
            logger.warning(f"File {file_id} not found")
            return None
            
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_id}: {e}")
            return None
    
    async def delete_file(self, file_id: str) -> bool:
        """Delete file by ID"""
        try:
            # Find and delete file
            for session_id in self.sessions_index:
                session_path = self.base_storage_path / 'sessions' / session_id
                metadata_file = session_path / 'metadata' / f"{file_id}_metadata.json"
                
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        file_info = json.load(f)
                    
                    # Delete actual file
                    file_path = Path(file_info['file_path'])
                    if file_path.exists():
                        file_path.unlink()
                    
                    # Delete metadata
                    metadata_file.unlink()
                    
                    # Remove from cache
                    if file_id in self._file_cache:
                        del self._file_cache[file_id]
                    
                    logger.info(f"Deleted file {file_id}")
                    return True
            
            logger.warning(f"File {file_id} not found for deletion")
            return False
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    # Storage Location Management
    async def add_storage_location(self, location: StorageLocation) -> bool:
        """Add storage location"""
        try:
            self.storage_locations[location.name] = location
            logger.info(f"Added storage location: {location.name}")
            return True
        except Exception as e:
            logger.error(f"Failed to add storage location: {e}")
            return False
    
    async def remove_storage_location(self, name: str) -> bool:
        """Remove storage location"""
        try:
            if name in self.storage_locations:
                del self.storage_locations[name]
                logger.info(f"Removed storage location: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove storage location: {e}")
            return False
    
    async def list_storage_locations(self) -> List[str]:
        """List storage location names"""
        return list(self.storage_locations.keys())
    
    async def get_storage_stats(self, location_name: Optional[str] = None) -> Union[StorageStats, Dict[str, StorageStats]]:
        """Get storage statistics"""
        try:
            if location_name:
                if location_name not in self.storage_locations:
                    raise StorageError(f"Storage location {location_name} not found")
                
                location = self.storage_locations[location_name]
                path = Path(location.path)
                
                # Calculate usage
                total_size = 0
                file_count = 0
                for file_path in path.rglob('*'):
                    if file_path.is_file():
                        file_count += 1
                        total_size += file_path.stat().st_size
                
                # Get available space
                stat = path.stat() if path.exists() else None
                available_space = shutil.disk_usage(path).free if stat else 0
                
                return StorageStats(
                    location_name=location_name,
                    total_size_bytes=total_size,
                    available_space_bytes=available_space,
                    file_count=file_count,
                    session_count=len(self.sessions_index),
                    last_backup=None,  # TODO: Track last backup time
                    health_status="healthy"
                )
            else:
                # Return stats for all locations
                stats = {}
                for loc_name in self.storage_locations:
                    stats[loc_name] = await self.get_storage_stats(loc_name)
                return stats
                
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return StorageStats(
                location_name=location_name or "unknown",
                total_size_bytes=0,
                available_space_bytes=0,
                file_count=0,
                session_count=0,
                health_status="error"
            )
    
    # Export and Backup Operations
    async def export_session(self, session_id: str, export_path: Path, 
                           format: str = "zip") -> Path:
        """Export session data"""
        try:
            if session_id not in self.sessions_index:
                raise StorageError(f"Session {session_id} not found")
            
            session = self.sessions_index[session_id]
            session_path = self.base_storage_path / 'sessions' / session_id
            
            if format.lower() == "zip":
                # Create ZIP export
                export_file = export_path / f"{session.scan_name}_{session_id}.zip"
                export_file.parent.mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(export_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for file_path in session_path.rglob('*'):
                        if file_path.is_file():
                            arcname = file_path.relative_to(session_path)
                            zipf.write(file_path, arcname)
                
                logger.info(f"Exported session {session_id} to {export_file}")
                return export_file
            
            elif format.lower() == "directory":
                # Create directory export
                export_dir = export_path / f"{session.scan_name}_{session_id}"
                shutil.copytree(session_path, export_dir, dirs_exist_ok=True)
                
                logger.info(f"Exported session {session_id} to {export_dir}")
                return export_dir
            
            else:
                raise StorageError(f"Unsupported export format: {format}")
                
        except Exception as e:
            logger.error(f"Failed to export session {session_id}: {e}")
            raise StorageError(f"Session export failed: {e}")
    
    async def _backup_file(self, file_path: Path, file_id: str) -> bool:
        """Backup file to backup location"""
        try:
            if "backup" not in self.storage_locations:
                return False
            
            backup_location = self.storage_locations["backup"]
            backup_path = Path(backup_location.path) / 'files' / f"{file_id}{file_path.suffix}"
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            
            shutil.copy2(file_path, backup_path)
            logger.debug(f"Backed up file {file_id} to {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup file {file_id}: {e}")
            return False
    
    async def backup_session(self, session_id: str, backup_location: str) -> bool:
        """Backup session data to specified location"""
        try:
            if session_id not in self.sessions_index:
                raise StorageError(f"Session {session_id} not found")
            
            session_path = self.base_storage_path / 'sessions' / session_id
            backup_path = Path(backup_location) / f"session_backup_{session_id}"
            
            shutil.copytree(session_path, backup_path, dirs_exist_ok=True)
            
            logger.info(f"Backed up session {session_id} to {backup_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to backup session {session_id}: {e}")
            return False
    
    async def sync_locations(self, source: str, destination: str) -> bool:
        """Synchronize data between storage locations"""
        try:
            if source not in self.storage_locations or destination not in self.storage_locations:
                raise StorageError("Source or destination location not found")
            
            source_path = Path(self.storage_locations[source].path)
            dest_path = Path(self.storage_locations[destination].path)
            
            # Simple sync implementation - copy newer files
            for file_path in source_path.rglob('*'):
                if file_path.is_file():
                    rel_path = file_path.relative_to(source_path)
                    dest_file = dest_path / rel_path
                    
                    if not dest_file.exists() or file_path.stat().st_mtime > dest_file.stat().st_mtime:
                        dest_file.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(file_path, dest_file)
            
            logger.info(f"Synchronized {source} to {destination}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to sync {source} to {destination}: {e}")
            return False
    
    async def verify_integrity(self, file_id: str) -> bool:
        """Verify file integrity using checksum"""
        try:
            if file_id not in self._file_cache:
                logger.warning(f"File {file_id} not in cache for integrity check")
                return False
            
            file_info = self._file_cache[file_id]
            if not file_info.get('checksum'):
                logger.warning(f"No checksum available for file {file_id}")
                return True  # No checksum to verify against
            
            file_path = Path(file_info['file_path'])
            if not file_path.exists():
                logger.error(f"File {file_id} not found at {file_path}")
                return False
            
            with open(file_path, 'rb') as f:
                data = f.read()
            
            calculated_checksum = hashlib.sha256(data).hexdigest()
            stored_checksum = file_info['checksum']
            
            if calculated_checksum == stored_checksum:
                logger.debug(f"Integrity check passed for file {file_id}")
                return True
            else:
                logger.error(f"Integrity check failed for file {file_id}")
                return False
                
        except Exception as e:
            logger.error(f"Integrity check failed for file {file_id}: {e}")
            return False
    
    async def generate_report(self, session_id: str) -> Dict[str, Any]:
        """Generate session report"""
        try:
            if session_id not in self.sessions_index:
                raise StorageError(f"Session {session_id} not found")
            
            session = self.sessions_index[session_id]
            session_path = self.base_storage_path / 'sessions' / session_id
            
            # Collect file statistics
            file_stats = {}
            total_size = 0
            
            for data_type in DataType:
                file_stats[data_type.value] = {
                    'count': 0,
                    'total_size': 0
                }
            
            # Scan session files
            for metadata_file in (session_path / 'metadata').glob('*_metadata.json'):
                if metadata_file.name != 'session.json':
                    with open(metadata_file, 'r') as f:
                        file_info = json.load(f)
                    
                    data_type = file_info.get('data_type', 'unknown')
                    file_size = file_info.get('file_size', 0)
                    
                    if data_type in file_stats:
                        file_stats[data_type]['count'] += 1
                        file_stats[data_type]['total_size'] += file_size
                    
                    total_size += file_size
            
            report = {
                'session_id': session_id,
                'session_name': session.scan_name,
                'created_at': session.start_time,
                'completed_at': session.end_time if session.end_time else None,
                'status': session.status,
                'scan_parameters': session.scan_parameters,
                'file_statistics': file_stats,
                'total_size_bytes': total_size,
                'total_files': sum(stats['count'] for stats in file_stats.values()),
                'generated_at': datetime.now().isoformat()
            }
            
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate report for session {session_id}: {e}")
            raise StorageError(f"Report generation failed: {e}")
    
    # Cleanup Operations
    async def cleanup_temp_files(self) -> bool:
        """Clean up temporary files"""
        try:
            temp_path = self.base_storage_path / 'temp'
            if temp_path.exists():
                shutil.rmtree(temp_path)
                temp_path.mkdir()
            
            logger.info("Temporary files cleaned up")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup temp files: {e}")
            return False
    
    # Additional Storage Location Methods
    async def add_storage_location(self, name: str, path: Path, 
                                 is_primary: bool = False) -> bool:
        """Add new storage location"""
        try:
            location = StorageLocation(
                name=name,
                path=path,
                is_primary=is_primary
            )
            self.storage_locations[name] = location
            
            # Create directory if it doesn't exist
            path.mkdir(parents=True, exist_ok=True)
            
            # Update primary location if needed
            if is_primary:
                for loc_name, loc in self.storage_locations.items():
                    if loc_name != name:
                        loc.is_primary = False
                self.base_storage_path = path
            
            await self._save_storage_config()
            logger.info(f"Added storage location: {name} at {path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add storage location {name}: {e}")
            return False
    
    async def remove_storage_location(self, name: str) -> bool:
        """Remove storage location"""
        try:
            if name in self.storage_locations:
                del self.storage_locations[name]
                await self._save_storage_config()
                logger.info(f"Removed storage location: {name}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to remove storage location {name}: {e}")
            return False
    
    async def list_storage_locations(self) -> List[str]:
        """List configured storage locations"""
        return list(self.storage_locations.keys())
    
    # File Path Operations
    async def store_file_from_path(self, file_path: Path, metadata: StorageMetadata,
                                  location_name: Optional[str] = None) -> str:
        """Store file from filesystem path"""
        try:
            with open(file_path, 'rb') as f:
                file_data = f.read()
            
            # Update metadata with actual file size
            actual_metadata = StorageMetadata(
                file_id=metadata.file_id,
                original_filename=metadata.original_filename,
                data_type=metadata.data_type,
                file_size_bytes=len(file_data),
                checksum=metadata.checksum,
                creation_time=metadata.creation_time,
                scan_session_id=metadata.scan_session_id,
                sequence_number=metadata.sequence_number,
                position_data=metadata.position_data,
                camera_settings=metadata.camera_settings,
                lighting_settings=metadata.lighting_settings,
                tags=metadata.tags
            )
            
            return await self.store_file(file_data, actual_metadata, location_name)
            
        except Exception as e:
            logger.error(f"Failed to store file from path {file_path}: {e}")
            raise StorageError(f"File storage failed: {e}")
    
    async def retrieve_file_to_path(self, file_id: str, output_path: Path) -> StorageMetadata:
        """Retrieve file to filesystem path"""
        try:
            file_data, metadata = await self.retrieve_file(file_id)
            
            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'wb') as f:
                f.write(file_data)
            
            logger.debug(f"Retrieved file {file_id} to {output_path}")
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to retrieve file {file_id} to path: {e}")
            raise StorageError(f"File retrieval failed: {e}")

    # Session Management with Required Interface
    async def start_session(self, scan_name: str, description: str = "", 
                           operator: str = "Unknown") -> ScanSession:
        """Start new scan session (interface method)"""
        session_metadata = {
            'name': scan_name,
            'description': description,
            'operator': operator,
            'scan_parameters': {}
        }
        session_id = await self.create_session(session_metadata)
        return self.sessions_index[session_id]
    
    async def end_session(self, session_id: str) -> bool:
        """End scan session (interface method)"""
        return await self.finalize_session(session_id)
    
    async def get_session(self, session_id: str) -> Optional[ScanSession]:
        """Get scan session information"""
        return self.sessions_index.get(session_id)

    # Additional Abstract Methods
    async def store_scan_batch(self, files: List[Tuple[bytes, StorageMetadata]]) -> List[str]:
        """Store multiple files in batch"""
        file_ids = []
        try:
            for file_data, metadata in files:
                file_id = await self.store_file(file_data, metadata)
                file_ids.append(file_id)
            
            logger.info(f"Stored batch of {len(files)} files")
            return file_ids
            
        except Exception as e:
            logger.error(f"Batch storage failed: {e}")
            raise StorageError(f"Batch storage failed: {e}")
    
    async def retrieve_session_files(self, session_id: str, data_type: Optional[DataType] = None) -> Dict[str, bytes]:
        """Retrieve all files from a session"""
        try:
            session_path = self.base_storage_path / 'sessions' / session_id / 'files'
            files_data = {}
            
            if not session_path.exists():
                return files_data
            
            for file_path in session_path.rglob('*'):
                if file_path.is_file():
                    file_id = file_path.stem
                    
                    # Check data type filter if specified
                    if data_type:
                        metadata_path = session_path.parent / 'metadata' / f"{file_id}.json"
                        if metadata_path.exists():
                            with open(metadata_path, 'r') as f:
                                meta_data = json.load(f)
                                if meta_data.get('data_type') != data_type.value:
                                    continue
                    
                    with open(file_path, 'rb') as f:
                        files_data[file_id] = f.read()
            
            return files_data
            
        except Exception as e:
            logger.error(f"Failed to retrieve session files: {e}")
            return {}
    
    async def backup_session(self, session_id: str, backup_location: str) -> bool:
        """Backup session to specified location"""
        try:
            session_path = self.base_storage_path / 'sessions' / session_id
            backup_path = Path(backup_location) / session_id
            
            if not session_path.exists():
                logger.error(f"Session {session_id} not found")
                return False
            
            # Copy session directory to backup location
            shutil.copytree(session_path, backup_path, dirs_exist_ok=True)
            
            logger.info(f"Backed up session {session_id} to {backup_location}")
            return True
            
        except Exception as e:
            logger.error(f"Session backup failed: {e}")
            return False

    async def sync_to_location(self, location_name: str) -> bool:
        """Sync data to specified location"""
        try:
            if location_name not in self.storage_locations:
                logger.error(f"Storage location {location_name} not found")
                return False
            
            target_location = self.storage_locations[location_name]
            
            # Sync all sessions
            for session_id in self.sessions_index:
                session_path = self.base_storage_path / 'sessions' / session_id
                target_path = target_location.path / 'sessions' / session_id
                
                if session_path.exists():
                    shutil.copytree(session_path, target_path, dirs_exist_ok=True)
            
            logger.info(f"Synced data to location: {location_name}")
            return True
            
        except Exception as e:
            logger.error(f"Sync to {location_name} failed: {e}")
            return False
    
    async def _save_storage_config(self):
        """Save storage locations configuration"""
        try:
            config_file = self.base_storage_path / 'config' / 'storage_locations.json'
            config_file.parent.mkdir(parents=True, exist_ok=True)
            
            config_data = {
                name: location.to_dict() 
                for name, location in self.storage_locations.items()
            }
            
            with open(config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save storage config: {e}")
        """Clean up sessions older than specified days"""
        try:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
            cleaned_count = 0
            
            for session_id, session in list(self.sessions_index.items()):
                # Convert start_time to timestamp if it's a string
                session_time = session.start_time
                if isinstance(session_time, str):
                    session_time = datetime.fromisoformat(session_time).timestamp()
                elif isinstance(session_time, datetime):
                    session_time = session_time.timestamp()
                else:
                    session_time = float(session_time)  # Assume it's already a timestamp
                
                if session_time < cutoff_date and session.status == 'completed':
                    session_path = self.base_storage_path / 'sessions' / session_id
                    if session_path.exists():
                        shutil.rmtree(session_path)
                    
                    del self.sessions_index[session_id]
                    cleaned_count += 1
            
            if cleaned_count > 0:
                await self._save_sessions_index()
            
            logger.info(f"Cleaned up {cleaned_count} old sessions")
            return True
            
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return False

    # Additional required abstract methods
    async def file_exists(self, file_id: str) -> bool:
        """Check if file exists"""
        try:
            metadata_file = self.base_storage_path / 'files' / 'metadata' / f"{file_id}.json"
            return metadata_file.exists()
        except Exception:
            return False
    
    async def update_metadata(self, file_id: str, updates: Dict[str, Any]) -> bool:
        """Update file metadata"""
        try:
            metadata_file = self.base_storage_path / 'files' / 'metadata' / f"{file_id}.json"
            if not metadata_file.exists():
                return False
            
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            metadata.update(updates)
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            return True
        except Exception as e:
            logger.error(f"Failed to update metadata for {file_id}: {e}")
            return False
    
    async def get_metadata(self, file_id: str) -> Optional[StorageMetadata]:
        """Get file metadata"""
        try:
            metadata_file = self.base_storage_path / 'files' / 'metadata' / f"{file_id}.json"
            if not metadata_file.exists():
                return None
            
            with open(metadata_file, 'r') as f:
                metadata_data = json.load(f)
            
            # Convert back to StorageMetadata object
            return StorageMetadata(
                file_id=metadata_data['file_id'],
                original_filename=metadata_data['original_filename'],
                data_type=DataType(metadata_data['data_type']),
                file_size_bytes=metadata_data['file_size_bytes'],
                checksum=metadata_data['checksum'],
                creation_time=metadata_data['creation_time'],
                scan_session_id=metadata_data.get('scan_session_id'),
                sequence_number=metadata_data.get('sequence_number'),
                position_data=metadata_data.get('position_data'),
                camera_settings=metadata_data.get('camera_settings'),
                lighting_settings=metadata_data.get('lighting_settings'),
                tags=metadata_data.get('tags', [])
            )
        except Exception as e:
            logger.error(f"Failed to get metadata for {file_id}: {e}")
            return None
    
    async def search_files(self, criteria: Dict[str, Any]) -> List[str]:
        """Search files by metadata criteria"""
        try:
            matching_files = []
            metadata_dir = self.base_storage_path / 'files' / 'metadata'
            
            if not metadata_dir.exists():
                return matching_files
            
            for metadata_file in metadata_dir.glob('*.json'):
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    # Check if metadata matches all criteria
                    matches = True
                    for key, value in criteria.items():
                        if key not in metadata:
                            matches = False
                            break
                        
                        metadata_value = metadata[key]
                        if isinstance(value, list):
                            # For list criteria, check if any item matches
                            if not any(v in str(metadata_value) for v in value):
                                matches = False
                                break
                        elif str(metadata_value) != str(value):
                            matches = False
                            break
                    
                    if matches:
                        matching_files.append(metadata['file_id'])
                        
                except Exception:
                    continue  # Skip invalid metadata files
            
            return matching_files
            
        except Exception as e:
            logger.error(f"File search failed: {e}")
            return []

    async def archive_old_sessions(self, days_old: int = 30) -> int:
        """Archive old scan sessions"""
        try:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 3600)
            archived_count = 0
            
            archive_path = self.base_storage_path / 'archive'
            archive_path.mkdir(exist_ok=True)
            
            for session_id, session in list(self.sessions_index.items()):
                # Convert start_time to timestamp if it's a string
                session_time = session.start_time
                if isinstance(session_time, str):
                    session_time = datetime.fromisoformat(session_time).timestamp()
                elif isinstance(session_time, datetime):
                    session_time = session_time.timestamp()
                else:
                    session_time = float(session_time)
                
                if session_time < cutoff_date and session.status == 'completed':
                    session_path = self.base_storage_path / 'sessions' / session_id
                    archive_session_path = archive_path / session_id
                    
                    if session_path.exists():
                        # Move session to archive
                        shutil.move(str(session_path), str(archive_session_path))
                        
                        # Update session status in index
                        session.status = 'archived'
                        archived_count += 1
            
            if archived_count > 0:
                await self._save_sessions_index()
            
            logger.info(f"Archived {archived_count} old sessions")
            return archived_count
            
        except Exception as e:
            logger.error(f"Failed to archive old sessions: {e}")
            return 0

    # Additional missing abstract methods
    async def sync_locations(self, source: str, destination: str) -> bool:
        """Synchronize data between storage locations"""
        try:
            if source not in self.storage_locations or destination not in self.storage_locations:
                logger.error(f"Storage locations not found: {source} or {destination}")
                return False
            
            source_path = self.storage_locations[source].path
            dest_path = self.storage_locations[destination].path
            
            # Simple sync implementation - copy all files
            for item in source_path.rglob('*'):
                if item.is_file():
                    relative_path = item.relative_to(source_path)
                    dest_file = dest_path / relative_path
                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest_file)
            
            logger.info(f"Synced data from {source} to {destination}")
            return True
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return False
    
    async def verify_integrity(self, file_id: str) -> bool:
        """Verify file integrity using checksum"""
        try:
            metadata = await self.get_metadata(file_id)
            if not metadata:
                return False
            
            file_data, _ = await self.retrieve_file(file_id)
            if not file_data:
                return False
            
            # Calculate current checksum
            import hashlib
            current_checksum = hashlib.md5(file_data).hexdigest()
            
            return current_checksum == metadata.checksum
            
        except Exception as e:
            logger.error(f"Integrity verification failed for {file_id}: {e}")
            return False
    
    async def export_session(self, session_id: str, export_path: Path, 
                           format: str = "zip") -> Path:
        """Export session data to external format"""
        try:
            session = await self.get_session(session_id)
            if not session:
                raise StorageError(f"Session {session_id} not found")
            
            if format == "zip":
                export_file = export_path / f"{session.scan_name}_{session_id}.zip"
                # This would typically be implemented with the backup logic
                await self.backup_session(session_id, str(export_path))
                return export_file
            else:
                # Directory export
                export_dir = export_path / f"{session.scan_name}_{session_id}"
                export_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy session files
                session_path = self.base_storage_path / 'sessions' / session_id
                if session_path.exists():
                    shutil.copytree(session_path, export_dir, dirs_exist_ok=True)
                
                return export_dir
                
        except Exception as e:
            logger.error(f"Export failed for session {session_id}: {e}")
            raise StorageError(f"Export failed: {e}")
    
    async def generate_report(self, session_id: str) -> Dict[str, Any]:
        """Generate scan session report"""
        # This is already implemented above in the SessionManager
        return await self._generate_session_report(session_id)
    
    async def cleanup_temp_files(self) -> bool:
        """Clean up temporary files"""
        try:
            temp_path = self.base_storage_path / 'temp'
            if temp_path.exists():
                shutil.rmtree(temp_path)
                temp_path.mkdir(exist_ok=True)
            
            logger.info("Cleaned up temporary files")
            return True
            
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {e}")
            return False