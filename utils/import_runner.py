#!/usr/bin/env python3
"""
Import Runner - Manage background import processes with progress tracking
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from config.db_pool import get_connection, return_connection


class ImportRunner:
    """Manage background import processes with progress tracking (using database)"""

    def __init__(self):
        self.pid_file = Path('/tmp/eclaim_import.pid')

    def is_running(self) -> bool:
        """Check if import is currently running"""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists using os.kill with signal 0
            import os
            os.kill(pid, 0)
            return True
        except (ValueError, OSError, ProcessLookupError):
            # PID file exists but process is dead
            self.pid_file.unlink(missing_ok=True)
            return False

    def get_progress(self) -> Dict:
        """
        Get current import progress from database

        Returns progress for most recent processing/pending import
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get most recent processing or pending import
            cursor.execute("""
                SELECT filename, file_type, status, total_records,
                       imported_records, failed_records, error_message,
                       import_started_at, import_completed_at
                FROM eclaim_imported_files
                WHERE status IN ('processing', 'pending')
                ORDER BY
                    CASE WHEN import_started_at IS NULL THEN 1 ELSE 0 END,
                    import_started_at DESC,
                    created_at DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            cursor.close()

            if row:
                progress = {
                    'running': self.is_running() and row[2] == 'processing',
                    'status': row[2],
                    'filename': row[0],
                    'file_type': row[1],
                    'total_records': row[3] or 0,
                    'imported_records': row[4] or 0,
                    'failed_records': row[5] or 0,
                    'error_message': row[6],
                    'started_at': row[7].isoformat() if row[7] else None,
                    'completed_at': row[8].isoformat() if row[8] else None
                }
                return_connection(conn)
                return progress
            else:
                return_connection(conn)
                return {
                    'running': False,
                    'status': 'idle'
                }

        except Exception as e:
            if conn:
                return_connection(conn)
            return {
                'running': False,
                'status': 'error',
                'error': f'Database error: {str(e)}'
            }

    def start_single_import(self, filepath: str) -> Dict:
        """
        Start importing a single file in background

        Args:
            filepath: Path to file to import

        Returns:
            Dict with success status and PID
        """
        if self.is_running():
            return {
                'success': False,
                'error': 'Import already running'
            }

        # Note: Progress is tracked in eclaim_imported_files table
        # The import process (eclaim_import.py) will INSERT/UPDATE the record

        # Start import process in background
        cmd = [
            sys.executable,
            'eclaim_import.py',
            filepath
        ]

        # Write to log file instead of PIPE to prevent deadlock
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        with open(log_file, 'w') as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.environ.get('APP_ROOT', str(Path(__file__).parent.parent)),
                start_new_session=True  # Detach from parent
            )

        # Save PID
        self.pid_file.write_text(str(process.pid))

        return {
            'success': True,
            'pid': process.pid,
            'import_id': progress['import_id']
        }

    def start_bulk_import(self, directory: str) -> Dict:
        """
        Start importing all files in directory in background

        Args:
            directory: Path to directory containing files

        Returns:
            Dict with success status and PID
        """
        if self.is_running():
            return {
                'success': False,
                'error': 'Import already running'
            }

        # Count files to import
        files = list(Path(directory).glob('*.xls'))
        total_files = len(files)

        # Initialize progress file
        progress = {
            'import_id': f"import_bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'type': 'bulk',
            'status': 'running',
            'total_files': total_files,
            'completed_files': 0,
            'current_file': None,
            'started_at': datetime.now().isoformat(),
            'records_imported': 0,
            'failed_files': [],
            'errors': []
        }

        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

        # Start import process in background
        cmd = [
            sys.executable,
            'eclaim_import.py',
            '--directory', directory
        ]

        # Write to log file instead of PIPE to prevent deadlock
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"import_bulk_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        with open(log_file, 'w') as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.environ.get('APP_ROOT', str(Path(__file__).parent.parent)),
                start_new_session=True  # Detach from parent
            )

        # Save PID
        self.pid_file.write_text(str(process.pid))

        return {
            'success': True,
            'pid': process.pid,
            'import_id': progress['import_id']
        }

    def stop(self) -> bool:
        """Stop running import process"""
        if not self.is_running():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            subprocess.run(['kill', str(pid)], check=True)
            self.pid_file.unlink(missing_ok=True)

            # Update progress file
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)

                progress['status'] = 'cancelled'
                progress['completed_at'] = datetime.now().isoformat()

                with open(self.progress_file, 'w') as f:
                    json.dump(progress, f, indent=2)

            return True

        except (ValueError, subprocess.CalledProcessError):
            return False

    def cleanup(self):
        """Cleanup old progress files and PID files"""
        self.pid_file.unlink(missing_ok=True)

        # Keep progress file for history, but mark as completed if stale
        if self.progress_file.exists() and not self.is_running():
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)

                if progress.get('status') == 'running':
                    progress['status'] = 'interrupted'
                    progress['completed_at'] = datetime.now().isoformat()

                    with open(self.progress_file, 'w') as f:
                        json.dump(progress, f, indent=2)
            except (json.JSONDecodeError, IOError):
                pass
