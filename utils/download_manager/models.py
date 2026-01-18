"""
Data models for Download Manager

All data classes used throughout the download manager system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List


class SessionStatus(Enum):
    """Download session status"""
    PENDING = "pending"
    DISCOVERING = "discovering"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FileStatus(Enum):
    """Individual file status"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass
class FileInfo:
    """Information about a downloadable file"""
    filename: str
    url: str
    file_type: Optional[str] = None  # OP, IP, ORF, etc.
    size_hint: Optional[int] = None  # Expected file size in bytes
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadResult:
    """Result of a file download operation"""
    success: bool
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


@dataclass
class ProgressInfo:
    """Real-time download progress information"""
    session_id: str
    source_type: str
    status: SessionStatus

    # Discovery Phase
    total_discovered: int = 0
    discovery_completed: bool = False

    # Comparison Phase
    already_downloaded: int = 0
    to_download: int = 0

    # Execution Phase
    processed: int = 0        # downloaded + skipped + failed
    downloaded: int = 0       # New files downloaded
    skipped: int = 0          # Files already exist
    failed: int = 0           # Failed downloads

    # Current State
    current_file: Optional[str] = None
    current_worker: Optional[str] = None

    # Timing
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    eta_seconds: Optional[int] = None

    # Control
    cancellable: bool = True
    resumable: bool = True

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage based on processed vs total"""
        if self.total_discovered == 0:
            return 0.0
        return (self.processed / self.total_discovered) * 100

    @property
    def is_complete(self) -> bool:
        """Check if download is complete"""
        return self.processed == self.total_discovered and self.total_discovered > 0

    @property
    def remaining(self) -> int:
        """Calculate remaining files to process"""
        return self.total_discovered - self.processed

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'session_id': self.session_id,
            'source_type': self.source_type,
            'status': self.status.value,
            'discovery': {
                'completed': self.discovery_completed,
                'total_discovered': self.total_discovered,
                'already_downloaded': self.already_downloaded,
                'to_download': self.to_download
            },
            'execution': {
                'processed': self.processed,
                'downloaded': self.downloaded,
                'skipped': self.skipped,
                'failed': self.failed,
                'remaining': self.remaining
            },
            'progress': {
                'percent': round(self.progress_percent, 2),
                'processed_of_total': f"{self.processed}/{self.total_discovered}",
                'current_file': self.current_file,
                'current_worker': self.current_worker
            },
            'timing': {
                'started_at': self.started_at.isoformat() if self.started_at else None,
                'updated_at': self.updated_at.isoformat() if self.updated_at else None,
                'completed_at': self.completed_at.isoformat() if self.completed_at else None,
                'eta_seconds': self.eta_seconds
            },
            'control': {
                'cancellable': self.cancellable,
                'resumable': self.resumable
            }
        }


@dataclass
class SessionSummary:
    """Summary of a completed download session"""
    session_id: str
    source_type: str
    status: SessionStatus
    fiscal_year: Optional[int]
    service_month: Optional[int]

    total_discovered: int
    downloaded: int
    skipped: int
    failed: int

    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]

    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'session_id': self.session_id,
            'source_type': self.source_type,
            'status': self.status.value,
            'fiscal_year': self.fiscal_year,
            'service_month': self.service_month,
            'total_discovered': self.total_discovered,
            'downloaded': self.downloaded,
            'skipped': self.skipped,
            'failed': self.failed,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'error_message': self.error_message
        }
