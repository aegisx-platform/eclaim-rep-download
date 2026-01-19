"""
Download Manager - Core download orchestration system

This package provides a unified download management system that supports
multiple download sources (REP, STM, SMT) with accurate progress tracking,
session isolation, and concurrent downloads.

Key Features:
- Accurate progress tracking (processed = downloaded + skipped)
- Database-backed sessions (survives restarts)
- Source isolation (REP/STM/SMT run independently)
- Cancel & Resume support
- Event-driven architecture
"""

from .manager import DownloadManager, get_download_manager
from .session import SessionManager, DownloadSession
from .models import (
    ProgressInfo,
    SessionStatus,
    FileInfo,
    DownloadResult,
    SessionSummary
)

__version__ = '2.0.0'

__all__ = [
    'DownloadManager',
    'get_download_manager',
    'SessionManager',
    'DownloadSession',
    'ProgressInfo',
    'SessionStatus',
    'FileInfo',
    'DownloadResult',
    'SessionSummary',
]
