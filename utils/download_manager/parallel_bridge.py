"""
Parallel Downloader Bridge

Integrates existing parallel_downloader.py with new DownloadManager system.
Provides backward compatibility while using new session management.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from utils.parallel_downloader import ParallelDownloader
from .manager import get_download_manager
from .models import SessionStatus

logger = logging.getLogger(__name__)


class ParallelDownloadBridge:
    """
    Bridge between legacy parallel downloader and new DownloadManager

    This allows us to:
    - Use new session management (isolation, DB persistence)
    - Keep existing parallel download logic
    - Maintain backward compatibility with UI
    """

    def __init__(self):
        self.manager = get_download_manager()
        self.active_downloaders: Dict[str, ParallelDownloader] = {}

    def start_download(self, credentials: list, params: Dict[str, Any]) -> str:
        """
        Start parallel download using new session management

        Args:
            credentials: List of credential dicts
            params: Download parameters
                - fiscal_year: int
                - service_month: int (optional)
                - scheme: str (optional)
                - max_workers: int

        Returns:
            session_id: UUID of created session
        """
        # Extract source type (default to 'rep' for now)
        source_type = params.get('source_type', 'rep')

        # Check if can start
        can_start, reason = self.manager.can_start_download(source_type)
        if not can_start:
            raise ValueError(reason)

        # Create session
        session_id = self.manager.create_session(source_type, params)
        logger.info(f"Created session {session_id} for parallel {source_type} download")

        # Update session to DISCOVERING status
        self.manager.update_progress(
            session_id,
            status=SessionStatus.DISCOVERING,
            started_at=datetime.now()
        )

        # Create parallel downloader instance
        downloader = ParallelDownloader(
            credentials=credentials,
            month=params.get('service_month'),
            year=params.get('fiscal_year'),
            scheme=params.get('scheme', 'ucs'),
            max_workers=params.get('max_workers', 3)
        )

        # Monkey-patch progress updates to go through DownloadManager
        original_update = downloader._update_progress

        def wrapped_update(**kwargs):
            try:
                # Call original update (updates in-memory state)
                original_update(**kwargs)

                # Also update DownloadManager (sync to database)
                self._sync_progress_to_manager(session_id, downloader)
            except Exception as e:
                logger.error(f"Error in wrapped_update: {e}", exc_info=True)

        downloader._update_progress = wrapped_update
        logger.info(f"Monkey-patched _update_progress for session {session_id}")

        # Store downloader
        self.active_downloaders[session_id] = downloader

        return session_id

    def _sync_progress_to_manager(self, session_id: str, downloader: ParallelDownloader):
        """Sync progress from parallel downloader (in-memory) to DownloadManager (database)"""
        try:
            # Read progress from downloader's in-memory state
            with downloader.progress_lock:
                progress = downloader.progress.copy()

            # Map to DownloadManager progress
            total = progress.get('total', 0)
            completed = progress.get('completed', 0)
            skipped = progress.get('skipped', 0)
            failed = progress.get('failed', 0)
            processed = completed + skipped + failed

            # Determine status
            status = SessionStatus.DOWNLOADING
            if progress.get('status') == 'completed':
                status = SessionStatus.COMPLETED
            elif progress.get('status') == 'failed':
                status = SessionStatus.FAILED
            elif progress.get('status') == 'cancelled':
                status = SessionStatus.CANCELLED

            # Debug log
            logger.debug(f"[Bridge] Syncing progress: {processed}/{total} (status={status.value})")

            # Update DownloadManager
            self.manager.update_progress(
                session_id,
                status=status,
                total_discovered=total,
                processed=processed,
                downloaded=completed,
                skipped=skipped,
                failed=failed,
                # Map discovery phase
                already_downloaded=skipped,
                to_download=total - skipped,
                discovery_completed=total > 0
            )

            # Mark as complete if done
            if status in (SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED):
                error = progress.get('error_message') if status == SessionStatus.FAILED else None
                self.manager.complete_session(session_id, error)
                logger.info(f"[Bridge] Session {session_id} completed: {processed}/{total}")

                # Clean up
                if session_id in self.active_downloaders:
                    del self.active_downloaders[session_id]

        except Exception as e:
            logger.error(f"[Bridge] Error syncing progress for session {session_id}: {e}", exc_info=True)

    def get_progress(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get progress for session (backward compatible format)

        Returns progress in legacy format for UI compatibility
        """
        progress_info = self.manager.get_progress(session_id)
        if not progress_info:
            return None

        # Convert to legacy format
        return {
            'running': progress_info.status in (SessionStatus.DISCOVERING, SessionStatus.DOWNLOADING),
            'status': progress_info.status.value,
            'total': progress_info.total_discovered,
            'completed': progress_info.downloaded,
            'skipped': progress_info.skipped,
            'failed': progress_info.failed,
            'processed': progress_info.processed,  # NEW: for accurate UI
            # Legacy compatibility
            'current_files': {},
            'workers': [],
            # New fields
            'session_id': session_id,
            'discovery_completed': progress_info.discovery_completed,
            'already_downloaded': progress_info.already_downloaded,
            'to_download': progress_info.to_download
        }

    def cancel_download(self, session_id: str):
        """Cancel active download"""
        self.manager.cancel_session(session_id)

        # Also cancel the downloader instance if exists
        if session_id in self.active_downloaders:
            downloader = self.active_downloaders[session_id]
            if hasattr(downloader, 'cancel'):
                downloader.cancel()

    def get_active_sessions(self):
        """Get all active download sessions"""
        return self.manager.get_active_sessions()


# Global singleton
_bridge_instance: Optional[ParallelDownloadBridge] = None


def get_parallel_bridge() -> ParallelDownloadBridge:
    """Get global ParallelDownloadBridge instance"""
    global _bridge_instance

    if _bridge_instance is None:
        _bridge_instance = ParallelDownloadBridge()

    return _bridge_instance
