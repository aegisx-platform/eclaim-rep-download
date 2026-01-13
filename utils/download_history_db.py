#!/usr/bin/env python3
"""
Download History Database Manager

Manages download history in the database instead of JSON files.
Provides methods to track, query, and manage downloaded files.

Usage:
    from utils.download_history_db import DownloadHistoryDB

    history = DownloadHistoryDB()
    history.connect()

    # Check if already downloaded
    if history.is_downloaded('stm', 'STM_10670_IPUCS256810_01.xls'):
        print("Already downloaded")

    # Record new download
    history.record_download('stm', {
        'filename': 'STM_10670_IPUCS256810_01.xls',
        'document_no': '10670_IPUCS256810_01',
        'scheme': 'ucs',
        'fiscal_year': 2569,
        'file_size': 4692480,
    })

    history.disconnect()
"""

import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Database driver imports
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pymysql
    from pymysql.cursors import DictCursor
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class DownloadHistoryDB:
    """
    Database-backed download history manager

    Replaces JSON file-based tracking with database storage for:
    - REP files (download_history.json)
    - STM files (stm_download_history.json)
    - SMT files (smt_download_history.json)
    """

    def __init__(self, db_config: Dict = None, db_type: str = None):
        """
        Initialize download history manager

        Args:
            db_config: Database configuration dict
            db_type: Database type ('postgresql' or 'mysql')
        """
        if db_config is None:
            from config.database import get_db_config
            db_config = get_db_config()

        self.db_config = db_config
        self.db_type = db_type or os.getenv('DB_TYPE', 'postgresql')
        self.conn = None
        self.cursor = None
        self._connected = False

    def connect(self):
        """Establish database connection"""
        if self._connected:
            return

        try:
            if self.db_type == 'postgresql':
                self.conn = psycopg2.connect(**self.db_config)
                self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            elif self.db_type == 'mysql':
                self.conn = pymysql.connect(**self.db_config)
                self.cursor = self.conn.cursor(DictCursor)

            self._connected = True
            logger.debug(f"Download history DB connected ({self.db_type})")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        self._connected = False
        logger.debug("Download history DB disconnected")

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

    # ==========================================================================
    # Core Query Methods
    # ==========================================================================

    def is_downloaded(self, download_type: str, filename: str,
                      check_file_exists: bool = True,
                      include_failed: bool = False) -> bool:
        """
        Check if a file has already been downloaded successfully

        Args:
            download_type: Type of download ('rep', 'stm', 'smt')
            filename: Filename to check
            check_file_exists: Also verify the physical file exists
            include_failed: If True, also return True for failed downloads

        Returns:
            True if downloaded successfully (and file exists if check_file_exists=True)
        """
        self.connect()

        # Only check successful downloads by default (failed can be retried)
        status_condition = "download_status IN ('success', 'downloading')"
        if include_failed:
            status_condition = "download_status IN ('success', 'downloading', 'failed')"

        query = f"""
            SELECT id, file_path, file_exists, download_status
            FROM download_history
            WHERE download_type = %s AND filename = %s AND {status_condition}
        """

        self.cursor.execute(query, (download_type, filename))
        record = self.cursor.fetchone()

        if not record:
            return False

        # If we don't need to check file existence, just return True
        if not check_file_exists:
            return True

        # Check if file actually exists
        file_path = record.get('file_path')
        if file_path and Path(file_path).exists():
            return True

        # File doesn't exist - update record
        self._update_file_exists(record['id'], False)
        return False

    def is_downloaded_by_document(self, download_type: str, document_no: str,
                                   check_file_exists: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Check if a document has already been downloaded

        Args:
            download_type: Type of download ('rep', 'stm', 'smt')
            document_no: Document number to check
            check_file_exists: Also verify the physical file exists

        Returns:
            Tuple of (is_downloaded, filename)
        """
        self.connect()

        query = """
            SELECT id, filename, file_path, file_exists
            FROM download_history
            WHERE download_type = %s AND document_no = %s
        """

        self.cursor.execute(query, (download_type, document_no))
        record = self.cursor.fetchone()

        if not record:
            return False, None

        filename = record.get('filename')

        if not check_file_exists:
            return True, filename

        # Check if file actually exists
        file_path = record.get('file_path')
        if file_path and Path(file_path).exists():
            return True, filename

        # File doesn't exist - update record
        self._update_file_exists(record['id'], False)
        return False, filename

    def _update_file_exists(self, record_id: int, exists: bool):
        """Update file_exists status for a record"""
        query = """
            UPDATE download_history
            SET file_exists = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """
        self.cursor.execute(query, (exists, record_id))
        self.conn.commit()

    # ==========================================================================
    # Record Methods
    # ==========================================================================

    def record_download(self, download_type: str, data: Dict,
                        status: str = 'success') -> int:
        """
        Record a new download (success or failed)

        Args:
            download_type: Type of download ('rep', 'stm', 'smt')
            data: Download data dict with keys:
                - filename (required)
                - document_no
                - scheme
                - fiscal_year
                - service_month
                - patient_type
                - rep_no
                - file_size
                - file_path
                - file_hash
                - source_url
                - download_params (dict)
                - error_message (for failed downloads)
            status: Download status ('pending', 'downloading', 'success', 'failed')

        Returns:
            ID of created record
        """
        self.connect()

        # Calculate file hash if file exists and hash not provided
        file_path = data.get('file_path')
        file_hash = data.get('file_hash')
        if file_path and not file_hash and Path(file_path).exists():
            file_hash = self._calculate_hash(file_path)

        download_params = data.get('download_params')
        if download_params and isinstance(download_params, dict):
            download_params = json.dumps(download_params)

        # Determine file_exists based on status
        file_exists = status == 'success' and file_path and Path(file_path).exists()

        if self.db_type == 'postgresql':
            query = """
                INSERT INTO download_history
                (download_type, filename, document_no, scheme, fiscal_year,
                 service_month, patient_type, rep_no, file_size, file_path,
                 file_hash, source_url, download_params, file_exists,
                 download_status, error_message, last_attempt_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (download_type, filename) DO UPDATE SET
                    file_size = COALESCE(EXCLUDED.file_size, download_history.file_size),
                    file_path = COALESCE(EXCLUDED.file_path, download_history.file_path),
                    file_hash = COALESCE(EXCLUDED.file_hash, download_history.file_hash),
                    file_exists = EXCLUDED.file_exists,
                    download_status = EXCLUDED.download_status,
                    error_message = EXCLUDED.error_message,
                    retry_count = CASE
                        WHEN EXCLUDED.download_status = 'failed' THEN download_history.retry_count + 1
                        WHEN EXCLUDED.download_status = 'success' THEN 0
                        ELSE download_history.retry_count
                    END,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    downloaded_at = CASE
                        WHEN EXCLUDED.download_status = 'success' THEN CURRENT_TIMESTAMP
                        ELSE download_history.downloaded_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """
        else:
            query = """
                INSERT INTO download_history
                (download_type, filename, document_no, scheme, fiscal_year,
                 service_month, patient_type, rep_no, file_size, file_path,
                 file_hash, source_url, download_params, file_exists,
                 download_status, error_message, last_attempt_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    file_size = COALESCE(VALUES(file_size), file_size),
                    file_path = COALESCE(VALUES(file_path), file_path),
                    file_hash = COALESCE(VALUES(file_hash), file_hash),
                    file_exists = VALUES(file_exists),
                    download_status = VALUES(download_status),
                    error_message = VALUES(error_message),
                    retry_count = CASE
                        WHEN VALUES(download_status) = 'failed' THEN retry_count + 1
                        WHEN VALUES(download_status) = 'success' THEN 0
                        ELSE retry_count
                    END,
                    last_attempt_at = CURRENT_TIMESTAMP,
                    downloaded_at = CASE
                        WHEN VALUES(download_status) = 'success' THEN CURRENT_TIMESTAMP
                        ELSE downloaded_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
            """

        values = (
            download_type,
            data.get('filename'),
            data.get('document_no'),
            data.get('scheme'),
            data.get('fiscal_year'),
            data.get('service_month'),
            data.get('patient_type'),
            data.get('rep_no'),
            data.get('file_size'),
            file_path,
            file_hash,
            data.get('source_url'),
            download_params,
            file_exists,
            status,
            data.get('error_message'),
        )

        self.cursor.execute(query, values)

        if self.db_type == 'postgresql':
            record_id = self.cursor.fetchone()['id']
        else:
            record_id = self.cursor.lastrowid
            if record_id == 0:
                self.cursor.execute(
                    "SELECT id FROM download_history WHERE download_type = %s AND filename = %s",
                    (download_type, data.get('filename'))
                )
                record_id = self.cursor.fetchone()['id']

        self.conn.commit()
        logger.debug(f"Recorded download ({status}): {download_type}/{data.get('filename')} (id={record_id})")
        return record_id

    def record_failed_download(self, download_type: str, data: Dict,
                               error_message: str) -> int:
        """
        Record a failed download for later retry

        Args:
            download_type: Type of download ('rep', 'stm', 'smt')
            data: Download data dict (same as record_download)
            error_message: Error message describing why download failed

        Returns:
            ID of created/updated record
        """
        data['error_message'] = error_message
        return self.record_download(download_type, data, status='failed')

    def mark_imported(self, download_type: str, filename: str,
                      import_file_id: int, import_table: str):
        """
        Mark a download as imported

        Args:
            download_type: Type of download
            filename: Filename
            import_file_id: ID in the import tracking table
            import_table: Name of import table (e.g., 'stm_imported_files')
        """
        self.connect()

        query = """
            UPDATE download_history
            SET imported = TRUE,
                imported_at = CURRENT_TIMESTAMP,
                import_file_id = %s,
                import_table = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE download_type = %s AND filename = %s
        """

        self.cursor.execute(query, (import_file_id, import_table, download_type, filename))
        self.conn.commit()
        logger.debug(f"Marked as imported: {download_type}/{filename}")

    def delete_record(self, download_type: str, filename: str):
        """Delete a download record"""
        self.connect()

        query = """
            DELETE FROM download_history
            WHERE download_type = %s AND filename = %s
        """

        self.cursor.execute(query, (download_type, filename))
        self.conn.commit()
        logger.debug(f"Deleted record: {download_type}/{filename}")

    # ==========================================================================
    # Query Methods
    # ==========================================================================

    def get_downloads(self, download_type: str = None,
                      fiscal_year: int = None,
                      scheme: str = None,
                      imported: bool = None,
                      file_exists: bool = None,
                      limit: int = 100,
                      offset: int = 0) -> List[Dict]:
        """
        Get download records with optional filters

        Args:
            download_type: Filter by type ('rep', 'stm', 'smt')
            fiscal_year: Filter by fiscal year
            scheme: Filter by scheme
            imported: Filter by import status
            file_exists: Filter by file existence
            limit: Max records to return
            offset: Offset for pagination

        Returns:
            List of download records
        """
        self.connect()

        conditions = []
        params = []

        if download_type:
            conditions.append("download_type = %s")
            params.append(download_type)
        if fiscal_year:
            conditions.append("fiscal_year = %s")
            params.append(fiscal_year)
        if scheme:
            conditions.append("scheme = %s")
            params.append(scheme)
        if imported is not None:
            conditions.append("imported = %s")
            params.append(imported)
        if file_exists is not None:
            conditions.append("file_exists = %s")
            params.append(file_exists)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT * FROM download_history
            WHERE {where_clause}
            ORDER BY downloaded_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        self.cursor.execute(query, params)
        return list(self.cursor.fetchall())

    def get_stats(self, download_type: str = None) -> Dict:
        """
        Get download statistics

        Args:
            download_type: Optional filter by type

        Returns:
            Dict with statistics including failed counts
        """
        self.connect()

        where_clause = "WHERE download_type = %s" if download_type else ""
        params = (download_type,) if download_type else ()

        query = f"""
            SELECT
                download_type,
                COUNT(*) as total,
                SUM(CASE WHEN file_exists THEN 1 ELSE 0 END) as files_exist,
                SUM(CASE WHEN imported THEN 1 ELSE 0 END) as imported,
                SUM(CASE WHEN download_status = 'success' THEN 1 ELSE 0 END) as success,
                SUM(CASE WHEN download_status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN download_status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(COALESCE(file_size, 0)) as total_size,
                MIN(downloaded_at) as first_download,
                MAX(downloaded_at) as last_download
            FROM download_history
            {where_clause}
            GROUP BY download_type
        """

        self.cursor.execute(query, params)
        results = self.cursor.fetchall()

        if download_type:
            return dict(results[0]) if results else {}

        return {r['download_type']: dict(r) for r in results}

    def get_last_download(self, download_type: str) -> Optional[Dict]:
        """Get the most recent download record"""
        self.connect()

        query = """
            SELECT * FROM download_history
            WHERE download_type = %s
            ORDER BY downloaded_at DESC
            LIMIT 1
        """

        self.cursor.execute(query, (download_type,))
        result = self.cursor.fetchone()
        return dict(result) if result else None

    def get_failed_downloads(self, download_type: str = None,
                             limit: int = 100) -> List[Dict]:
        """
        Get failed downloads that can be retried

        Args:
            download_type: Optional filter by type
            limit: Max records to return

        Returns:
            List of failed download records
        """
        self.connect()

        where_clause = "WHERE download_status = 'failed'"
        params = []

        if download_type:
            where_clause += " AND download_type = %s"
            params.append(download_type)

        query = f"""
            SELECT * FROM download_history
            {where_clause}
            ORDER BY last_attempt_at DESC
            LIMIT %s
        """
        params.append(limit)

        self.cursor.execute(query, params)
        return [dict(r) for r in self.cursor.fetchall()]

    def get_failed_count(self, download_type: str = None) -> int:
        """Get count of failed downloads"""
        self.connect()

        where_clause = "WHERE download_status = 'failed'"
        params = []

        if download_type:
            where_clause += " AND download_type = %s"
            params.append(download_type)

        query = f"SELECT COUNT(*) as count FROM download_history {where_clause}"
        self.cursor.execute(query, params)
        result = self.cursor.fetchone()
        return result['count'] if result else 0

    def reset_for_retry(self, download_type: str, filename: str) -> bool:
        """
        Reset a failed download to allow retry

        Args:
            download_type: Type of download
            filename: Filename to reset

        Returns:
            True if record was updated
        """
        self.connect()

        query = """
            UPDATE download_history
            SET download_status = 'pending',
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE download_type = %s
              AND filename = %s
              AND download_status = 'failed'
        """

        self.cursor.execute(query, (download_type, filename))
        updated = self.cursor.rowcount > 0
        self.conn.commit()

        if updated:
            logger.debug(f"Reset for retry: {download_type}/{filename}")
        return updated

    def reset_all_failed(self, download_type: str = None) -> int:
        """
        Reset all failed downloads for retry

        Args:
            download_type: Optional filter by type

        Returns:
            Number of records reset
        """
        self.connect()

        where_clause = "WHERE download_status = 'failed'"
        params = []

        if download_type:
            where_clause += " AND download_type = %s"
            params.append(download_type)

        query = f"""
            UPDATE download_history
            SET download_status = 'pending',
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
            {where_clause}
        """

        self.cursor.execute(query, params)
        count = self.cursor.rowcount
        self.conn.commit()

        logger.info(f"Reset {count} failed downloads for retry")
        return count

    def delete_failed(self, download_type: str = None) -> int:
        """
        Delete all failed download records

        Args:
            download_type: Optional filter by type

        Returns:
            Number of records deleted
        """
        self.connect()

        where_clause = "WHERE download_status = 'failed'"
        params = []

        if download_type:
            where_clause += " AND download_type = %s"
            params.append(download_type)

        query = f"DELETE FROM download_history {where_clause}"

        self.cursor.execute(query, params)
        count = self.cursor.rowcount
        self.conn.commit()

        logger.info(f"Deleted {count} failed download records")
        return count

    # ==========================================================================
    # Maintenance Methods
    # ==========================================================================

    def sync_file_exists(self, download_type: str = None) -> Dict:
        """
        Sync file_exists status by checking actual files

        Returns:
            Dict with counts of updated records
        """
        self.connect()

        where_clause = "WHERE download_type = %s" if download_type else ""
        params = (download_type,) if download_type else ()

        query = f"""
            SELECT id, file_path, file_exists
            FROM download_history
            {where_clause}
        """

        self.cursor.execute(query, params)
        records = self.cursor.fetchall()

        updated = 0
        missing = 0

        for record in records:
            file_path = record.get('file_path')
            current_exists = record.get('file_exists')
            actual_exists = file_path and Path(file_path).exists()

            if current_exists != actual_exists:
                self._update_file_exists(record['id'], actual_exists)
                updated += 1
                if not actual_exists:
                    missing += 1

        return {
            'checked': len(records),
            'updated': updated,
            'missing': missing
        }

    def cleanup_orphaned_records(self, download_type: str = None) -> int:
        """
        Remove records where files no longer exist

        Returns:
            Number of deleted records
        """
        # First sync file_exists status
        self.sync_file_exists(download_type)

        self.connect()

        where_clause = "download_type = %s AND" if download_type else ""
        params = (download_type,) if download_type else ()

        query = f"""
            DELETE FROM download_history
            WHERE {where_clause} file_exists = FALSE AND imported = FALSE
        """

        self.cursor.execute(query, params)
        deleted = self.cursor.rowcount
        self.conn.commit()

        logger.info(f"Cleaned up {deleted} orphaned records")
        return deleted

    # ==========================================================================
    # Utility Methods
    # ==========================================================================

    def _calculate_hash(self, filepath: str) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()


# Convenience functions for backward compatibility
def get_download_history_db() -> DownloadHistoryDB:
    """Get a configured DownloadHistoryDB instance"""
    return DownloadHistoryDB()


def is_already_downloaded(download_type: str, filename: str) -> bool:
    """Quick check if file is already downloaded"""
    with DownloadHistoryDB() as db:
        return db.is_downloaded(download_type, filename)
