"""
Download Manager - Core orchestration

Main entry point for download operations. Coordinates sessions, progress tracking,
and source isolation.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .session import SessionManager, DownloadSession
from .models import ProgressInfo, SessionStatus, SessionSummary

logger = logging.getLogger(__name__)


class DownloadManager:
    """
    Core Download Manager

    Orchestrates download operations with:
    - Session isolation (REP/STM/SMT run independently)
    - Accurate progress tracking
    - Database-backed state
    - Concurrent download support
    """

    def __init__(self):
        self.session_manager = SessionManager()
        logger.info("DownloadManager initialized")

    def create_session(self, source_type: str, params: Dict[str, Any]) -> str:
        """
        Create new download session

        Args:
            source_type: Download source (rep, stm, smt)
            params: Download parameters
                - fiscal_year: int
                - service_month: int (optional)
                - scheme: str (optional)
                - max_workers: int (optional)
                - auto_import: bool (optional)

        Returns:
            session_id: UUID of created session

        Raises:
            ValueError: If session already active for this source

        Example:
            >>> manager = DownloadManager()
            >>> session_id = manager.create_session('rep', {
            ...     'fiscal_year': 2569,
            ...     'service_month': 1,
            ...     'scheme': 'ucs'
            ... })
        """
        try:
            session_id = self.session_manager.create_session(source_type, params)
            logger.info(f"Created session {session_id} for {source_type}")
            return session_id

        except ValueError as e:
            logger.warning(f"Cannot create session for {source_type}: {e}")
            raise

    def get_session(self, session_id: str) -> Optional[DownloadSession]:
        """Get session by ID"""
        return self.session_manager.get_session(session_id)

    def get_progress(self, session_id: str) -> Optional[ProgressInfo]:
        """
        Get current progress for a session

        Args:
            session_id: Session UUID

        Returns:
            ProgressInfo object or None if session not found

        Example:
            >>> progress = manager.get_progress(session_id)
            >>> print(f"{progress.processed}/{progress.total_discovered} files")
            >>> print(f"{progress.downloaded} new, {progress.skipped} skipped")
        """
        session = self.get_session(session_id)
        if not session:
            return None

        return session.get_progress()

    def update_progress(self, session_id: str, **kwargs):
        """
        Update session progress

        Args:
            session_id: Session UUID
            **kwargs: Progress fields to update
                - total_discovered: int
                - downloaded: int
                - skipped: int
                - failed: int
                - status: SessionStatus
                - current_file: str
                etc.

        Example:
            >>> manager.update_progress(session_id,
            ...     total_discovered=394,
            ...     downloaded=2,
            ...     skipped=392,
            ...     processed=394
            ... )
        """
        self.session_manager.update_session_progress(session_id, **kwargs)

    def cancel_session(self, session_id: str):
        """
        Cancel active session

        Args:
            session_id: Session UUID
        """
        logger.info(f"Cancelling session {session_id}")
        self.session_manager.cancel_session(session_id)

    def complete_session(self, session_id: str, error: Optional[str] = None):
        """
        Mark session as complete or failed

        Args:
            session_id: Session UUID
            error: Error message if failed
        """
        if error:
            logger.error(f"Session {session_id} failed: {error}")
        else:
            logger.info(f"Session {session_id} completed")

        self.session_manager.complete_session(session_id, error)

    def get_active_sessions(self) -> List[ProgressInfo]:
        """
        Get all currently active sessions

        Returns:
            List of ProgressInfo for active sessions

        Example:
            >>> active = manager.get_active_sessions()
            >>> for progress in active:
            ...     print(f"{progress.source_type}: {progress.progress_percent}%")
        """
        sessions = self.session_manager.get_active_sessions()
        return [s.get_progress() for s in sessions]

    def can_start_download(self, source_type: str) -> tuple[bool, Optional[str]]:
        """
        Check if download can start for source

        Args:
            source_type: Source type to check

        Returns:
            (can_start: bool, reason: str or None)

        Example:
            >>> can_start, reason = manager.can_start_download('rep')
            >>> if not can_start:
            ...     print(f"Cannot start: {reason}")
        """
        can_start = self.session_manager.can_start_session(source_type)

        if can_start:
            return True, None
        else:
            # Find active session for this source
            active_sessions = self.get_active_sessions()
            for progress in active_sessions:
                if progress.source_type == source_type:
                    return False, (
                        f"A {source_type.upper()} download is already running "
                        f"({progress.processed}/{progress.total_discovered} files). "
                        f"Please wait or cancel the existing download."
                    )

            return False, f"A {source_type.upper()} download is already running."

    def get_session_summary(self, session_id: str) -> Optional[SessionSummary]:
        """
        Get summary of completed session

        Args:
            session_id: Session UUID

        Returns:
            SessionSummary or None
        """
        session = self.get_session(session_id)
        if not session:
            return None

        duration = None
        if session.started_at and session.completed_at:
            duration = (session.completed_at - session.started_at).total_seconds()

        return SessionSummary(
            session_id=session.session_id,
            source_type=session.source_type,
            status=session.status,
            fiscal_year=session.params.get('fiscal_year'),
            service_month=session.params.get('service_month'),
            total_discovered=session.total_discovered,
            downloaded=session.downloaded,
            skipped=session.skipped,
            failed=session.failed,
            started_at=session.started_at,
            completed_at=session.completed_at,
            duration_seconds=duration
        )


# Global singleton instance
_manager_instance: Optional[DownloadManager] = None


def get_download_manager() -> DownloadManager:
    """
    Get global DownloadManager instance (singleton)

    Returns:
        DownloadManager instance

    Example:
        >>> from utils.download_manager import get_download_manager
        >>> manager = get_download_manager()
        >>> session_id = manager.create_session('rep', {...})
    """
    global _manager_instance

    if _manager_instance is None:
        _manager_instance = DownloadManager()

    return _manager_instance
