"""
History Manager Database - Database-backed replacement for HistoryManager

Provides the same interface as HistoryManager but stores data in PostgreSQL
instead of JSON files. Uses connection pooling for thread-safe concurrent access.

Usage:
    from utils.history_manager_db import HistoryManagerDB

    # Use as drop-in replacement for HistoryManager
    history_manager = HistoryManagerDB(download_type='rep')
    stats = history_manager.get_statistics()
    downloads = history_manager.get_all_downloads()
"""

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import humanize
import re

from config.db_pool import get_connection, return_connection

logger = logging.getLogger(__name__)

# Get database type from environment
DB_TYPE = os.environ.get('DB_TYPE', 'postgresql').lower()


class HistoryManagerDB:
    """
    Database-backed history manager with same interface as HistoryManager

    Thread-safe through connection pooling - each method gets its own connection.
    """

    def __init__(self, download_type: str = 'rep'):
        """
        Initialize history manager for specific download type

        Args:
            download_type: 'rep', 'stm', or 'smt'
        """
        self.download_type = download_type
        self.db_type = DB_TYPE
        self._file_dir = self._get_file_directory()

    def _get_file_directory(self) -> str:
        """Get file directory for this download type"""
        dirs = {
            'rep': 'downloads/rep',
            'stm': 'downloads/stm',
            'smt': 'downloads/smt'
        }
        return dirs.get(self.download_type, 'downloads')

    def _get_connection(self):
        """Get connection from pool"""
        return get_connection()

    def _release_connection(self, conn):
        """Release connection back to pool"""
        if conn:
            return_connection(conn)

    # ==========================================================================
    # Core Methods (same interface as HistoryManager)
    # ==========================================================================

    def load_history(self) -> Dict:
        """
        Load download history (compatibility method)

        Returns:
            Dict with 'last_run' and 'downloads' keys
        """
        downloads = self.get_all_downloads()
        last_run = self._get_last_run()
        return {
            'last_run': last_run,
            'downloads': downloads
        }

    def save_history(self, data: Dict):
        """
        Save history (compatibility method - creates backup before operations)

        For database operations, this is handled automatically via transactions.
        This method mainly updates the last_run timestamp.
        """
        # In DB mode, we don't need to save full history
        # Individual records are inserted/updated separately
        # Just update last_run if provided
        last_run = data.get('last_run')
        if last_run:
            self._update_last_run(last_run)

    def get_all_downloads(self) -> List[Dict]:
        """
        Get all download records for this type

        Returns:
            List of download record dicts
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    filename, document_no, scheme, fiscal_year as year,
                    service_month as month, patient_type, rep_no,
                    file_size, file_path, file_hash, file_exists,
                    downloaded_at as download_date, imported,
                    imported_at, source_url
                FROM download_history
                WHERE download_type = %s
                ORDER BY downloaded_at DESC
            """
            cursor.execute(query, (self.download_type,))

            columns = [desc[0] for desc in cursor.description]
            downloads = []

            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                # Convert datetime to ISO format string
                if record.get('download_date'):
                    record['download_date'] = record['download_date'].isoformat()
                if record.get('imported_at'):
                    record['imported_at'] = record['imported_at'].isoformat()
                downloads.append(record)

            cursor.close()
            return downloads

        except Exception as e:
            logger.error(f"Error getting downloads: {e}")
            return []
        finally:
            self._release_connection(conn)

    def get_download(self, filename: str) -> Optional[Dict]:
        """
        Get single download record by filename

        Args:
            filename: Filename to look up

        Returns:
            Download record dict or None
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    filename, document_no, scheme, fiscal_year as year,
                    service_month as month, patient_type, rep_no,
                    file_size, file_path, file_exists,
                    downloaded_at as download_date, imported,
                    source_url
                FROM download_history
                WHERE download_type = %s AND filename = %s
            """
            cursor.execute(query, (self.download_type, filename))
            row = cursor.fetchone()

            if row:
                columns = [desc[0] for desc in cursor.description]
                record = dict(zip(columns, row))
                if record.get('download_date'):
                    record['download_date'] = record['download_date'].isoformat()
                cursor.close()
                return record

            cursor.close()
            return None

        except Exception as e:
            logger.error(f"Error getting download {filename}: {e}")
            return None
        finally:
            self._release_connection(conn)

    def delete_download(self, filename: str) -> bool:
        """
        Remove download record from history

        Args:
            filename: Filename to delete

        Returns:
            True if deleted successfully
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                DELETE FROM download_history
                WHERE download_type = %s AND filename = %s
            """
            cursor.execute(query, (self.download_type, filename))
            deleted = cursor.rowcount > 0
            conn.commit()
            cursor.close()

            logger.debug(f"Deleted download record: {filename}")
            return deleted

        except Exception as e:
            logger.error(f"Error deleting download {filename}: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            self._release_connection(conn)

    def add_download(self, data: Dict) -> bool:
        """
        Add new download record

        Args:
            data: Download data dict with keys like filename, file_size, etc.

        Returns:
            True if added successfully
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            file_path = f"{self._file_dir}/{data.get('filename')}"

            # Use appropriate UPSERT syntax based on database type
            if self.db_type == 'mysql':
                query = """
                    INSERT INTO download_history
                    (download_type, filename, document_no, scheme, fiscal_year,
                     service_month, patient_type, rep_no, file_size, file_path,
                     source_url, file_exists)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        file_size = VALUES(file_size),
                        file_path = VALUES(file_path),
                        file_exists = VALUES(file_exists),
                        updated_at = CURRENT_TIMESTAMP
                """
            else:
                # PostgreSQL syntax
                query = """
                    INSERT INTO download_history
                    (download_type, filename, document_no, scheme, fiscal_year,
                     service_month, patient_type, rep_no, file_size, file_path,
                     source_url, file_exists)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (download_type, filename) DO UPDATE SET
                        file_size = EXCLUDED.file_size,
                        file_path = EXCLUDED.file_path,
                        file_exists = EXCLUDED.file_exists,
                        updated_at = CURRENT_TIMESTAMP
                """

            cursor.execute(query, (
                self.download_type,
                data.get('filename'),
                data.get('rep_no') or data.get('document_no'),
                data.get('scheme'),
                data.get('year') or data.get('fiscal_year'),
                data.get('month') or data.get('service_month'),
                data.get('patient_type'),
                data.get('rep_no'),
                data.get('file_size'),
                file_path,
                data.get('source_url'),
                True  # file_exists
            ))

            conn.commit()
            cursor.close()
            logger.debug(f"Added download record: {data.get('filename')}")
            return True

        except Exception as e:
            logger.error(f"Error adding download: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            self._release_connection(conn)

    # ==========================================================================
    # Statistics Methods
    # ==========================================================================

    def get_statistics(self) -> Dict:
        """
        Calculate dashboard statistics

        Returns:
            Dict with total_files, total_size, last_run, file_types
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get counts and totals
            query = """
                SELECT
                    COUNT(*) as total_files,
                    COALESCE(SUM(file_size), 0) as total_size,
                    MAX(downloaded_at) as last_download
                FROM download_history
                WHERE download_type = %s
            """
            cursor.execute(query, (self.download_type,))
            row = cursor.fetchone()

            total_files = row[0] or 0
            total_size = row[1] or 0
            last_download = row[2]

            # Get file type breakdown
            type_query = """
                SELECT
                    SUBSTRING(filename FROM 'eclaim_[0-9]+_([A-Z]+)_') as file_type,
                    COUNT(*) as count
                FROM download_history
                WHERE download_type = %s
                GROUP BY file_type
            """
            cursor.execute(type_query, (self.download_type,))
            file_types = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

            # Format last run time
            last_run_formatted = 'Never'
            last_run_raw = None
            if last_download:
                last_run_raw = last_download.isoformat()
                last_run_formatted = humanize.naturaltime(last_download)

            cursor.close()

            return {
                'total_files': total_files,
                'total_size': humanize.naturalsize(total_size),
                'total_size_bytes': total_size,
                'last_run': last_run_formatted,
                'last_run_raw': last_run_raw,
                'file_types': file_types
            }

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'total_files': 0,
                'total_size': '0 Bytes',
                'total_size_bytes': 0,
                'last_run': 'Error',
                'last_run_raw': None,
                'file_types': {}
            }
        finally:
            self._release_connection(conn)

    def get_latest(self, n: int = 5) -> List[Dict]:
        """
        Get n latest downloads

        Args:
            n: Number of records to return

        Returns:
            List of most recent download records
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    filename, scheme, fiscal_year as year,
                    service_month as month, file_size,
                    downloaded_at as download_date
                FROM download_history
                WHERE download_type = %s
                ORDER BY downloaded_at DESC
                LIMIT %s
            """
            cursor.execute(query, (self.download_type, n))

            columns = [desc[0] for desc in cursor.description]
            downloads = []

            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                if record.get('download_date'):
                    record['download_date'] = record['download_date'].isoformat()
                downloads.append(record)

            cursor.close()
            return downloads

        except Exception as e:
            logger.error(f"Error getting latest downloads: {e}")
            return []
        finally:
            self._release_connection(conn)

    def get_date_range_statistics(self) -> Dict:
        """
        Get statistics grouped by month/year

        Returns:
            Dict organized by year and month
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    fiscal_year as year,
                    service_month as month,
                    COUNT(*) as files,
                    COALESCE(SUM(file_size), 0) as size
                FROM download_history
                WHERE download_type = %s
                  AND fiscal_year IS NOT NULL
                  AND service_month IS NOT NULL
                GROUP BY fiscal_year, service_month
                ORDER BY fiscal_year DESC, service_month DESC
            """
            cursor.execute(query, (self.download_type,))

            stats = {}
            for row in cursor.fetchall():
                year, month, files, size = row
                year_str = str(year)
                month_str = str(month)

                if year_str not in stats:
                    stats[year_str] = {}

                stats[year_str][month_str] = {
                    'files': files,
                    'size': size,
                    'size_formatted': humanize.naturalsize(size)
                }

            cursor.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting date range stats: {e}")
            return {}
        finally:
            self._release_connection(conn)

    def get_available_dates(self) -> List[Dict]:
        """
        Get list of available month/year combinations

        Returns:
            List of dicts with month, year, count, label
        """
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            month_names = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }

            query = """
                SELECT
                    fiscal_year as year,
                    service_month as month,
                    COUNT(*) as count
                FROM download_history
                WHERE download_type = %s
                  AND fiscal_year IS NOT NULL
                  AND service_month IS NOT NULL
                GROUP BY fiscal_year, service_month
                ORDER BY fiscal_year DESC, service_month DESC
            """
            cursor.execute(query, (self.download_type,))

            available_dates = []
            for row in cursor.fetchall():
                year, month, count = row
                available_dates.append({
                    'year': year,
                    'month': month,
                    'count': count,
                    'label': f"{month_names.get(month, month)} {year}"
                })

            cursor.close()
            return available_dates

        except Exception as e:
            logger.error(f"Error getting available dates: {e}")
            return []
        finally:
            self._release_connection(conn)

    def get_downloads_by_date(self, month: int, year: int) -> List[Dict]:
        """Get all downloads for specific month/year"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    filename, scheme, fiscal_year as year,
                    service_month as month, file_size,
                    downloaded_at as download_date, imported
                FROM download_history
                WHERE download_type = %s
                  AND fiscal_year = %s
                  AND service_month = %s
                ORDER BY downloaded_at DESC
            """
            cursor.execute(query, (self.download_type, year, month))

            columns = [desc[0] for desc in cursor.description]
            downloads = []

            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                if record.get('download_date'):
                    record['download_date'] = record['download_date'].isoformat()
                downloads.append(record)

            cursor.close()
            return downloads

        except Exception as e:
            logger.error(f"Error getting downloads by date: {e}")
            return []
        finally:
            self._release_connection(conn)

    def get_downloads_by_scheme(self, scheme: str) -> List[Dict]:
        """Get all downloads for a specific scheme"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    filename, scheme, fiscal_year as year,
                    service_month as month, file_size,
                    downloaded_at as download_date, imported
                FROM download_history
                WHERE download_type = %s AND scheme = %s
                ORDER BY downloaded_at DESC
            """
            cursor.execute(query, (self.download_type, scheme))

            columns = [desc[0] for desc in cursor.description]
            downloads = []

            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                if record.get('download_date'):
                    record['download_date'] = record['download_date'].isoformat()
                downloads.append(record)

            cursor.close()
            return downloads

        except Exception as e:
            logger.error(f"Error getting downloads by scheme: {e}")
            return []
        finally:
            self._release_connection(conn)

    def get_statistics_by_scheme(self) -> Dict:
        """Get statistics grouped by insurance scheme"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT
                    COALESCE(scheme, 'ucs') as scheme,
                    COUNT(*) as files,
                    COALESCE(SUM(file_size), 0) as size
                FROM download_history
                WHERE download_type = %s
                GROUP BY scheme
            """
            cursor.execute(query, (self.download_type,))

            stats = {}
            for row in cursor.fetchall():
                scheme, files, size = row
                stats[scheme] = {
                    'files': files,
                    'size': size,
                    'size_formatted': humanize.naturalsize(size)
                }

            cursor.close()
            return stats

        except Exception as e:
            logger.error(f"Error getting scheme stats: {e}")
            return {}
        finally:
            self._release_connection(conn)

    def get_available_schemes(self) -> List[Dict]:
        """Get list of schemes that have downloaded files"""
        stats = self.get_statistics_by_scheme()

        scheme_names = {
            'ucs': 'สิทธิบัตรทอง (UCS)',
            'ofc': 'สิทธิข้าราชการ (OFC)',
            'sss': 'สิทธิประกันสังคม (SSS)',
            'lgo': 'สิทธิ อปท. (LGO)',
            'nhs': 'สิทธิ สปสช. (NHS)',
            'bkk': 'สิทธิ กทม. (BKK)',
            'bmt': 'สิทธิ ขสมก. (BMT)',
            'srt': 'สิทธิ รฟท. (SRT)'
        }

        available_schemes = [
            {
                'scheme': scheme,
                'name': scheme_names.get(scheme, scheme.upper()),
                'count': data['files'],
                'size': data['size'],
                'size_formatted': data['size_formatted']
            }
            for scheme, data in stats.items()
        ]

        available_schemes.sort(key=lambda s: s['count'], reverse=True)
        return available_schemes

    def get_downloads_by_date_and_scheme(self, month: int, year: int,
                                          scheme: str = None) -> List[Dict]:
        """Get downloads filtered by date and optionally scheme"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if scheme:
                query = """
                    SELECT
                        filename, scheme, fiscal_year as year,
                        service_month as month, file_size,
                        downloaded_at as download_date, imported
                    FROM download_history
                    WHERE download_type = %s
                      AND fiscal_year = %s
                      AND service_month = %s
                      AND scheme = %s
                    ORDER BY downloaded_at DESC
                """
                cursor.execute(query, (self.download_type, year, month, scheme))
            else:
                query = """
                    SELECT
                        filename, scheme, fiscal_year as year,
                        service_month as month, file_size,
                        downloaded_at as download_date, imported
                    FROM download_history
                    WHERE download_type = %s
                      AND fiscal_year = %s
                      AND service_month = %s
                    ORDER BY downloaded_at DESC
                """
                cursor.execute(query, (self.download_type, year, month))

            columns = [desc[0] for desc in cursor.description]
            downloads = []

            for row in cursor.fetchall():
                record = dict(zip(columns, row))
                if record.get('download_date'):
                    record['download_date'] = record['download_date'].isoformat()
                downloads.append(record)

            cursor.close()
            return downloads

        except Exception as e:
            logger.error(f"Error getting downloads: {e}")
            return []
        finally:
            self._release_connection(conn)

    # ==========================================================================
    # Helper Methods
    # ==========================================================================

    def _get_last_run(self) -> Optional[str]:
        """Get last download timestamp"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            query = """
                SELECT MAX(downloaded_at) FROM download_history
                WHERE download_type = %s
            """
            cursor.execute(query, (self.download_type,))
            row = cursor.fetchone()
            cursor.close()

            if row and row[0]:
                return row[0].isoformat()
            return None

        except Exception as e:
            logger.error(f"Error getting last run: {e}")
            return None
        finally:
            self._release_connection(conn)

    def _update_last_run(self, timestamp: str):
        """Update last run timestamp (no-op for DB - tracked per record)"""
        # In database mode, last_run is derived from MAX(downloaded_at)
        # No separate storage needed
        pass

    def is_downloaded(self, filename: str) -> bool:
        """Check if file has already been downloaded"""
        return self.get_download(filename) is not None

    def record_download(self, data: Dict) -> bool:
        """Record a new successful download"""
        return self.add_download(data)

    def scan_and_register_files(self, directory: str = None) -> Dict:
        """
        Scan a directory for .xls files and register them in database.
        Files not in database will be added with metadata extracted from filename.

        Args:
            directory (str): Path to scan for files. Defaults based on download_type.

        Returns:
            dict: Report with added, skipped, and error counts
        """
        import re
        from pathlib import Path
        from datetime import datetime

        # Default directories based on download_type
        if directory is None:
            if self.download_type == 'rep':
                directory = 'downloads/rep'
            elif self.download_type == 'stm':
                directory = 'downloads/stm'
            else:
                directory = 'downloads'

        report = {
            'added': 0,
            'skipped': 0,
            'errors': 0,
            'error_files': [],
            'directory': directory,
            'download_type': self.download_type
        }

        scan_dir = Path(directory)
        if not scan_dir.exists():
            report['errors'] = 1
            report['error_files'].append(f'Directory not found: {directory}')
            return report

        # Get all .xls files
        xls_files = list(scan_dir.glob('*.xls'))

        for file_path in xls_files:
            try:
                filename = file_path.name

                # Check if already in history
                if self.get_download(filename) is not None:
                    report['skipped'] += 1
                    continue

                # Extract metadata from filename
                month = None
                year = None
                file_type = None
                scheme = 'ucs'

                # Try eclaim REP format: eclaim_10670_OP_25681001_xxx.xls
                match = re.search(r'eclaim_(\d+)_(\w+)_(\d{4})(\d{2})\d{2}_', filename)
                if match:
                    hospital_code = match.group(1)
                    file_type = match.group(2)  # OP, IP, ORF
                    year = int(match.group(3))  # 2568
                    month = int(match.group(4))  # 10

                # Try STM format: STM_10670_IPUCS256810_01.xls
                stm_match = re.search(r'STM_(\d+)_(\w+)(\d{4})(\d{2})_', filename)
                if stm_match and not match:
                    hospital_code = stm_match.group(1)
                    file_type = stm_match.group(2)  # IPUCS, OPUCS
                    year = int(stm_match.group(3))  # 2568
                    month = int(stm_match.group(4))  # 10

                # Get file size and modification time
                stat = file_path.stat()
                file_size = stat.st_size
                mtime = datetime.fromtimestamp(stat.st_mtime)

                # Create download record
                download_record = {
                    'filename': filename,
                    'file_size': file_size,
                    'download_date': mtime.isoformat(),
                    'file_path': str(file_path),
                    'source': 'file_scan',
                }

                if month:
                    download_record['month'] = month
                    download_record['service_month'] = month
                if year:
                    download_record['year'] = year
                    download_record['fiscal_year'] = year
                if file_type:
                    download_record['file_type'] = file_type
                if scheme:
                    download_record['scheme'] = scheme

                # Add to history
                if self.add_download(download_record):
                    report['added'] += 1
                else:
                    report['skipped'] += 1

            except Exception as e:
                report['errors'] += 1
                report['error_files'].append(f'{filename}: {str(e)}')

        return report


# Factory function for easy initialization
def get_history_manager(download_type: str = 'rep') -> HistoryManagerDB:
    """Get a HistoryManagerDB instance for the specified type"""
    return HistoryManagerDB(download_type=download_type)
