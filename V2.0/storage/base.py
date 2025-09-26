"""
Abstract Data Storage Interface

Defines the standard interface for data storage and management systems.
This enables support for different storage backends while maintaining
consistent API for scan data, images, and metadata management.

Author: Scanner System Development
Created: September 2025
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple, Callable, Union, BinaryIO
from enum import Enum
import asyncio
from pathlib import Path
import time

from core.exceptions import StorageError
from core.events import ScannerEvent


class StorageStatus(Enum):
    """Storage system status states"""
    DISCONNECTED = "disconnected"
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    SYNCING = "syncing"
    ERROR = "error"
    FULL = "full"


class DataType(Enum):
    """Types of data stored"""
    SCAN_IMAGE = "scan_image"
    RAW_IMAGE = "raw_image"
    PROCESSED_IMAGE = "processed_image"
    POINT_CLOUD = "point_cloud"
    MESH_DATA = "mesh_data"
    SCAN_METADATA = "scan_metadata"
    SCAN_PATH = "scan_path"
    CALIBRATION_DATA = "calibration_data"
    LOG_DATA = "log_data"
    BACKUP_DATA = "backup_data"


class CompressionType(Enum):
    """Compression types supported"""
    NONE = "none"
    GZIP = "gzip"
    LZMA = "lzma"
    ZSTD = "zstd"


@dataclass
class StorageLocation:
    """Storage location configuration"""
    name: str
    path: Path
    capacity_gb: Optional[float] = None
    is_primary: bool = False
    auto_backup: bool = False
    compression: CompressionType = CompressionType.NONE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'name': self.name,
            'path': str(self.path),
            'capacity_gb': self.capacity_gb,
            'is_primary': self.is_primary,
            'auto_backup': self.auto_backup,
            'compression': self.compression.value
        }


@dataclass
class StorageMetadata:
    """Metadata for stored files"""
    file_id: str
    original_filename: str
    data_type: DataType
    file_size_bytes: int
    checksum: str
    creation_time: float
    scan_session_id: Optional[str] = None
    sequence_number: Optional[int] = None
    position_data: Optional[Dict[str, float]] = None
    camera_settings: Optional[Dict[str, Any]] = None
    lighting_settings: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    file_extension: Optional[str] = None
    filename: Optional[str] = None
    scan_point_id: Optional[str] = None
    camera_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'file_id': self.file_id,
            'original_filename': self.original_filename,
            'data_type': self.data_type.value,
            'file_size_bytes': self.file_size_bytes,
            'checksum': self.checksum,
            'creation_time': self.creation_time,
            'scan_session_id': self.scan_session_id,
            'sequence_number': self.sequence_number,
            'position_data': self.position_data,
            'camera_settings': self.camera_settings,
            'lighting_settings': self.lighting_settings,
            'tags': self.tags,
            'file_extension': self.file_extension,
            'filename': self.filename,
            'scan_point_id': self.scan_point_id,
            'camera_id': self.camera_id,
            'metadata': self.metadata
        }


@dataclass
class ScanSession:
    """Scan session information"""
    session_id: str
    start_time: float
    end_time: Optional[float] = None
    scan_name: str = "Untitled Scan"
    description: str = ""
    operator: str = "Unknown"
    total_files: int = 0
    total_size_bytes: int = 0
    scan_parameters: Optional[Dict[str, Any]] = None
    status: str = "active"
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Get session duration in seconds"""
        if self.end_time:
            return self.end_time - self.start_time
        return None
    
    @property
    def is_active(self) -> bool:
        """Check if session is currently active"""
        return self.status == "active" and self.end_time is None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'session_id': self.session_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'scan_name': self.scan_name,
            'description': self.description,
            'operator': self.operator,
            'total_files': self.total_files,
            'total_size_bytes': self.total_size_bytes,
            'scan_parameters': self.scan_parameters,
            'status': self.status
        }


@dataclass
class StorageStats:
    """Storage system statistics"""
    total_capacity_gb: float
    used_space_gb: float
    available_space_gb: float
    file_count: int
    session_count: int
    last_backup_time: Optional[float] = None
    
    @property
    def usage_percentage(self) -> float:
        """Get storage usage percentage"""
        if self.total_capacity_gb > 0:
            return (self.used_space_gb / self.total_capacity_gb) * 100.0
        return 0.0
    
    @property
    def is_nearly_full(self) -> bool:
        """Check if storage is nearly full (>90%)"""
        return self.usage_percentage > 90.0


class StorageManager(ABC):
    """
    Abstract base class for data storage management systems
    
    This interface supports storing scan data, images, metadata, and provides
    backup and synchronization capabilities for multi-location storage.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.status = StorageStatus.DISCONNECTED
        self.storage_locations: Dict[str, StorageLocation] = {}
        self.current_session: Optional[ScanSession] = None
        self.event_callbacks: List[Callable] = []
        self._file_cache: Dict[str, Dict[str, Any]] = {}
    
    # System Management
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize storage system
        
        Returns:
            True if initialization successful
            
        Raises:
            StorageError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def shutdown(self) -> bool:
        """
        Shutdown storage system and finalize current session
        
        Returns:
            True if shutdown successful
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if storage system is available"""
        pass
    
    # Storage Location Management
    @abstractmethod
    async def add_storage_location(self, location: StorageLocation) -> bool:
        """
        Add storage location
        
        Args:
            location: Storage location configuration
            
        Returns:
            True if location added successfully
        """
        pass
    
    @abstractmethod
    async def remove_storage_location(self, name: str) -> bool:
        """
        Remove storage location
        
        Args:
            name: Storage location name
            
        Returns:
            True if location removed successfully
        """
        pass
    
    @abstractmethod
    async def list_storage_locations(self) -> List[str]:
        """
        List configured storage locations
        
        Returns:
            List of storage location names
        """
        pass
    
    @abstractmethod
    async def get_storage_stats(self, location_name: Optional[str] = None) -> Union[StorageStats, Dict[str, StorageStats]]:
        """
        Get storage statistics
        
        Args:
            location_name: Specific location or None for all locations
            
        Returns:
            Storage statistics
        """
        pass
    
    # Session Management
    @abstractmethod
    async def start_session(self, scan_name: str, description: str = "", 
                           operator: str = "Unknown") -> ScanSession:
        """
        Start new scan session
        
        Args:
            scan_name: Name for the scan session
            description: Session description
            operator: Operator name
            
        Returns:
            Created scan session
            
        Raises:
            StorageError: If session creation fails
        """
        pass
    
    @abstractmethod
    async def end_session(self, session_id: str) -> bool:
        """
        End scan session
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if session ended successfully
        """
        pass
    
    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[ScanSession]:
        """
        Get scan session information
        
        Args:
            session_id: Session identifier
            
        Returns:
            Scan session or None if not found
        """
        pass
    
    @abstractmethod
    async def list_sessions(self, limit: int = 100) -> List[ScanSession]:
        """
        List scan sessions
        
        Args:
            limit: Maximum number of sessions to return
            
        Returns:
            List of scan sessions (most recent first)
        """
        pass
    
    # File Storage Operations
    @abstractmethod
    async def store_file(self, file_data: bytes, metadata: StorageMetadata, 
                        location_name: Optional[str] = None) -> str:
        """
        Store file data with metadata
        
        Args:
            file_data: File data to store
            metadata: File metadata
            location_name: Target storage location (primary if None)
            
        Returns:
            File identifier for retrieval
            
        Raises:
            StorageError: If storage fails
        """
        pass
    
    @abstractmethod
    async def store_file_from_path(self, file_path: Path, metadata: StorageMetadata,
                                  location_name: Optional[str] = None) -> str:
        """
        Store file from filesystem path
        
        Args:
            file_path: Path to file to store
            metadata: File metadata
            location_name: Target storage location
            
        Returns:
            File identifier for retrieval
        """
        pass
    
    @abstractmethod
    async def retrieve_file(self, file_id: str) -> Tuple[bytes, StorageMetadata]:
        """
        Retrieve file data and metadata
        
        Args:
            file_id: File identifier
            
        Returns:
            Tuple of (file_data, metadata)
            
        Raises:
            StorageError: If retrieval fails
        """
        pass
    
    @abstractmethod
    async def retrieve_file_to_path(self, file_id: str, output_path: Path) -> StorageMetadata:
        """
        Retrieve file to filesystem path
        
        Args:
            file_id: File identifier
            output_path: Output file path
            
        Returns:
            File metadata
        """
        pass
    
    @abstractmethod
    async def delete_file(self, file_id: str) -> bool:
        """
        Delete stored file
        
        Args:
            file_id: File identifier
            
        Returns:
            True if deletion successful
        """
        pass
    
    @abstractmethod
    async def file_exists(self, file_id: str) -> bool:
        """
        Check if file exists
        
        Args:
            file_id: File identifier
            
        Returns:
            True if file exists
        """
        pass
    
    # Metadata Operations
    @abstractmethod
    async def update_metadata(self, file_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update file metadata
        
        Args:
            file_id: File identifier
            updates: Metadata updates
            
        Returns:
            True if update successful
        """
        pass
    
    @abstractmethod
    async def get_metadata(self, file_id: str) -> Optional[StorageMetadata]:
        """
        Get file metadata
        
        Args:
            file_id: File identifier
            
        Returns:
            File metadata or None if not found
        """
        pass
    
    @abstractmethod
    async def search_files(self, criteria: Dict[str, Any]) -> List[str]:
        """
        Search files by metadata criteria
        
        Args:
            criteria: Search criteria (data_type, session_id, tags, etc.)
            
        Returns:
            List of matching file identifiers
        """
        pass
    
    # Batch Operations
    @abstractmethod
    async def store_scan_batch(self, files: List[Tuple[bytes, StorageMetadata]]) -> List[str]:
        """
        Store multiple files in batch
        
        Args:
            files: List of (file_data, metadata) tuples
            
        Returns:
            List of file identifiers
        """
        pass
    
    @abstractmethod
    async def retrieve_session_files(self, session_id: str, data_type: Optional[DataType] = None) -> Dict[str, bytes]:
        """
        Retrieve all files from a session
        
        Args:
            session_id: Session identifier
            data_type: Optional data type filter
            
        Returns:
            Dictionary mapping file_id to file_data
        """
        pass
    
    # Backup and Sync
    @abstractmethod
    async def backup_session(self, session_id: str, backup_location: str) -> bool:
        """
        Backup session data to specified location
        
        Args:
            session_id: Session to backup
            backup_location: Backup storage location
            
        Returns:
            True if backup successful
        """
        pass
    
    @abstractmethod
    async def sync_locations(self, source: str, destination: str) -> bool:
        """
        Synchronize data between storage locations
        
        Args:
            source: Source storage location
            destination: Destination storage location
            
        Returns:
            True if sync successful
        """
        pass
    
    @abstractmethod
    async def verify_integrity(self, file_id: str) -> bool:
        """
        Verify file integrity using checksum
        
        Args:
            file_id: File identifier
            
        Returns:
            True if file integrity is valid
        """
        pass
    
    # Data Export
    @abstractmethod
    async def export_session(self, session_id: str, export_path: Path, 
                           format: str = "zip") -> Path:
        """
        Export session data to external format
        
        Args:
            session_id: Session to export
            export_path: Export destination path
            format: Export format (zip, tar, directory)
            
        Returns:
            Path to exported data
        """
        pass
    
    @abstractmethod
    async def generate_report(self, session_id: str) -> Dict[str, Any]:
        """
        Generate scan session report
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session report dictionary
        """
        pass
    
    # Cleanup Operations
    @abstractmethod
    async def cleanup_temp_files(self) -> bool:
        """
        Clean up temporary files
        
        Returns:
            True if cleanup successful
        """
        pass
    
    @abstractmethod
    async def archive_old_sessions(self, days_old: int = 30) -> int:
        """
        Archive old scan sessions
        
        Args:
            days_old: Sessions older than this will be archived
            
        Returns:
            Number of sessions archived
        """
        pass
    
    # Event Handling
    def add_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Add callback for storage events"""
        self.event_callbacks.append(callback)
    
    def remove_event_callback(self, callback: Callable[[ScannerEvent], None]):
        """Remove event callback"""
        if callback in self.event_callbacks:
            self.event_callbacks.remove(callback)
    
    def _notify_event(self, event_type: str, data: Optional[Dict[str, Any]] = None):
        """Notify all event callbacks"""
        from core.events import ScannerEvent, EventPriority
        
        # Determine priority based on event type
        priority = EventPriority.HIGH if "error" in event_type or "full" in event_type else EventPriority.NORMAL
        
        event = ScannerEvent(
            event_type=event_type,
            data=data or {},
            source_module="storage",
            priority=priority
        )
        
        for callback in self.event_callbacks:
            try:
                callback(event)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error in storage event callback: {e}")
    
    # Utility Methods
    def generate_file_id(self, session_id: str, sequence: int) -> str:
        """Generate unique file identifier"""
        timestamp = int(time.time() * 1000)  # milliseconds
        return f"{session_id}_{sequence:04d}_{timestamp}"
    
    def calculate_checksum(self, data: bytes) -> str:
        """Calculate checksum for data integrity"""
        import hashlib
        return hashlib.sha256(data).hexdigest()
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format"""
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        size = float(size_bytes)
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        return f"{size:.2f} {units[unit_index]}"
    
    def create_metadata_template(self, data_type: DataType, session_id: str) -> StorageMetadata:
        """Create metadata template for specific data type"""
        return StorageMetadata(
            file_id="",  # Will be set when storing
            original_filename="",
            data_type=data_type,
            file_size_bytes=0,
            checksum="",
            creation_time=time.time(),
            scan_session_id=session_id
        )


# Utility functions for storage operations
def create_scan_metadata(session_id: str, sequence: int, position_data: Dict[str, float]) -> StorageMetadata:
    """Create metadata for scan image"""
    return StorageMetadata(
        file_id="",
        original_filename=f"scan_{sequence:04d}.jpg",
        data_type=DataType.SCAN_IMAGE,
        file_size_bytes=0,
        checksum="",
        creation_time=time.time(),
        scan_session_id=session_id,
        sequence_number=sequence,
        position_data=position_data
    )


def create_storage_location(name: str, path: str, capacity_gb: Optional[float] = None) -> StorageLocation:
    """Create storage location configuration"""
    return StorageLocation(
        name=name,
        path=Path(path),
        capacity_gb=capacity_gb,
        is_primary=(name == "primary"),
        auto_backup=True
    )


def validate_storage_space(stats: StorageStats, required_gb: float) -> bool:
    """
    Validate sufficient storage space is available
    
    Args:
        stats: Storage statistics
        required_gb: Required space in GB
        
    Returns:
        True if sufficient space available
    """
    # Require 10% buffer above requested space
    required_with_buffer = required_gb * 1.1
    return stats.available_space_gb >= required_with_buffer