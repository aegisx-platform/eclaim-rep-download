"""
Session Management for Download Manager

Handles download session lifecycle, state persistence, and isolation.
"""

import uuid
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from .models import SessionStatus, ProgressInfo, FileStatus
from config.database import get_db_connection, DB_TYPE


class DownloadSession:
    """Represents a single download session"""

    def __init__(self, session_id: str, source_type: str, params: Dict[str, Any]):
        self.session_id = session_id
        self.source_type = source_type
        self.params = params
        self.status = SessionStatus.PENDING

        # Progress tracking
        self.total_discovered = 0
        self.already_downloaded = 0
        self.to_download = 0
        self.processed = 0
        self.downloaded = 0
        self.skipped = 0
        self.failed = 0

        # Timing
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.updated_at = datetime.now()

        # Control
        self.cancellable = True
        self.resumable = True
        self.cancelled = False

        # Lock for thread-safe updates
        self._lock = threading.Lock()

    def get_progress(self) -> ProgressInfo:
        """Get current progress information"""
        with self._lock:
            return ProgressInfo(
                session_id=self.session_id,
                source_type=self.source_type,
                status=self.status,
                total_discovered=self.total_discovered,
                discovery_completed=self.status != SessionStatus.DISCOVERING,
                already_downloaded=self.already_downloaded,
                to_download=self.to_download,
                processed=self.processed,
                downloaded=self.downloaded,
                skipped=self.skipped,
                failed=self.failed,
                started_at=self.started_at,
                updated_at=self.updated_at,
                completed_at=self.completed_at,
                cancellable=self.cancellable,
                resumable=self.resumable
            )

    def update_progress(self, **kwargs):
        """Thread-safe progress update"""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            self.updated_at = datetime.now()

    def is_active(self) -> bool:
        """Check if session is currently active (not completed, failed, or cancelled)"""
        return self.status in (
            SessionStatus.PENDING,
            SessionStatus.DISCOVERING,
            SessionStatus.DOWNLOADING
        )

    def is_complete(self) -> bool:
        """Check if session is complete"""
        return self.status in (
            SessionStatus.COMPLETED,
            SessionStatus.FAILED,
            SessionStatus.CANCELLED
        )


class SessionManager:
    """
    Manages download sessions with database persistence and source isolation

    Key features:
    - One active session per source type (REP/STM/SMT run independently)
    - Database-backed state (survives server restarts)
    - Thread-safe operations
    """

    def __init__(self):
        # Active sessions by source type
        self._active_sessions: Dict[str, Optional[DownloadSession]] = {
            'rep': None,
            'stm': None,
            'smt': None
        }

        # Locks per source for thread safety
        self._session_locks: Dict[str, threading.Lock] = {
            'rep': threading.Lock(),
            'stm': threading.Lock(),
            'smt': threading.Lock()
        }

    def can_start_session(self, source_type: str) -> bool:
        """Check if new session can start for this source"""
        with self._session_locks[source_type]:
            active = self._active_sessions.get(source_type)
            return active is None or not active.is_active()

    def create_session(self, source_type: str, params: Dict[str, Any]) -> str:
        """
        Create new download session

        Args:
            source_type: Source type (rep, stm, smt)
            params: Download parameters (fiscal_year, etc.)

        Returns:
            session_id: UUID of created session

        Raises:
            ValueError: If session already active for this source
        """
        if not self.can_start_session(source_type):
            raise ValueError(
                f"A {source_type} download is already running. "
                f"Please wait or cancel the existing session."
            )

        with self._session_locks[source_type]:
            # Generate session ID
            session_id = str(uuid.uuid4())

            # Create session object
            session = DownloadSession(session_id, source_type, params)

            # Save to database
            self._save_session_to_db(session)

            # Track as active
            self._active_sessions[source_type] = session

            return session_id

    def get_session(self, session_id: str) -> Optional[DownloadSession]:
        """Get session by ID (check active sessions first, then DB)"""
        # Check active sessions
        for session in self._active_sessions.values():
            if session and session.session_id == session_id:
                return session

        # Load from database
        return self._load_session_from_db(session_id)

    def update_session_progress(self, session_id: str, **kwargs):
        """Update session progress and persist to database"""
        session = self.get_session(session_id)
        if not session:
            return

        # Update in-memory
        session.update_progress(**kwargs)

        # Persist to database
        self._update_session_in_db(session)

    def complete_session(self, session_id: str, error: Optional[str] = None):
        """Mark session as complete or failed"""
        session = self.get_session(session_id)
        if not session:
            return

        with session._lock:
            session.completed_at = datetime.now()

            if error:
                session.status = SessionStatus.FAILED
            elif session.cancelled:
                session.status = SessionStatus.CANCELLED
            else:
                session.status = SessionStatus.COMPLETED

        # Persist to database
        self._update_session_in_db(session)

        # Remove from active sessions
        with self._session_locks[session.source_type]:
            if self._active_sessions.get(session.source_type) == session:
                self._active_sessions[session.source_type] = None

    def cancel_session(self, session_id: str):
        """Cancel active session"""
        session = self.get_session(session_id)
        if not session:
            return

        with session._lock:
            session.cancelled = True
            session.status = SessionStatus.CANCELLED
            session.completed_at = datetime.now()

        self._update_session_in_db(session)

    def get_active_sessions(self) -> List[DownloadSession]:
        """Get all currently active sessions"""
        return [s for s in self._active_sessions.values() if s and s.is_active()]

    # Database operations

    def _save_session_to_db(self, session: DownloadSession):
        """Save new session to database"""
        conn = get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            query = """
                INSERT INTO download_sessions (
                    id, source_type, status,
                    fiscal_year, service_month, scheme, params,
                    total_discovered, already_downloaded, to_download,
                    processed, downloaded, skipped, failed,
                    created_at, started_at, completed_at, updated_at,
                    cancellable, resumable
                ) VALUES (
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
            """

            cursor.execute(query, (
                session.session_id,
                session.source_type,
                session.status.value,
                session.params.get('fiscal_year'),
                session.params.get('service_month'),
                session.params.get('scheme'),
                json.dumps(session.params),
                session.total_discovered,
                session.already_downloaded,
                session.to_download,
                session.processed,
                session.downloaded,
                session.skipped,
                session.failed,
                session.created_at,
                session.started_at,
                session.completed_at,
                session.updated_at,
                session.cancellable,
                session.resumable
            ))

            conn.commit()
            cursor.close()
        finally:
            conn.close()

    def _update_session_in_db(self, session: DownloadSession):
        """Update existing session in database"""
        conn = get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()

            query = """
                UPDATE download_sessions SET
                    status = %s,
                    total_discovered = %s,
                    already_downloaded = %s,
                    to_download = %s,
                    processed = %s,
                    downloaded = %s,
                    skipped = %s,
                    failed = %s,
                    started_at = %s,
                    completed_at = %s,
                    updated_at = %s
                WHERE id = %s
            """

            cursor.execute(query, (
                session.status.value,
                session.total_discovered,
                session.already_downloaded,
                session.to_download,
                session.processed,
                session.downloaded,
                session.skipped,
                session.failed,
                session.started_at,
                session.completed_at,
                session.updated_at,
                session.session_id
            ))

            conn.commit()
            cursor.close()
        finally:
            conn.close()

    def _load_session_from_db(self, session_id: str) -> Optional[DownloadSession]:
        """Load session from database"""
        conn = get_db_connection()
        if not conn:
            return None

        try:
            cursor = conn.cursor()

            query = """
                SELECT
                    id, source_type, status,
                    fiscal_year, service_month, scheme, params,
                    total_discovered, already_downloaded, to_download,
                    processed, downloaded, skipped, failed,
                    created_at, started_at, completed_at, updated_at,
                    cancellable, resumable
                FROM download_sessions
                WHERE id = %s
            """

            cursor.execute(query, (session_id,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                return None

            # Parse params JSON
            params = json.loads(row[6]) if row[6] else {}

            # Create session object
            session = DownloadSession(row[0], row[1], params)
            session.status = SessionStatus(row[2])
            session.total_discovered = row[7] or 0
            session.already_downloaded = row[8] or 0
            session.to_download = row[9] or 0
            session.processed = row[10] or 0
            session.downloaded = row[11] or 0
            session.skipped = row[12] or 0
            session.failed = row[13] or 0
            session.created_at = row[14]
            session.started_at = row[15]
            session.completed_at = row[16]
            session.updated_at = row[17]
            session.cancellable = row[18]
            session.resumable = row[19]

            return session

        finally:
            conn.close()
