#!/usr/bin/env python3
"""
STM Import Runner - Manage background STM import processes with progress tracking
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from config.db_pool import get_connection, return_connection


class STMImportRunner:
    """Manage background STM import processes with progress tracking (using database)"""

    def __init__(self):
        self.pid_file = Path('/tmp/eclaim_stm_import.pid')

    def is_running(self) -> bool:
        """Check if STM import is currently running"""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists using os.kill with signal 0
            os.kill(pid, 0)
            return True
        except (ValueError, OSError, ProcessLookupError):
            # PID file exists but process is dead
            self.pid_file.unlink(missing_ok=True)
            return False

    def get_progress(self) -> Dict:
        """
        Get current STM import progress from database

        Returns progress for most recent processing/pending STM import
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get most recent processing or pending STM import
            cursor.execute("""
                SELECT filename, status, total_records, imported_records,
                       failed_records, error_message, import_started_at,
                       import_completed_at
                FROM stm_imported_files
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
                    'running': self.is_running() and row[1] == 'processing',
                    'status': row[1],
                    'filename': row[0],
                    'total_records': row[2] or 0,
                    'imported_records': row[3] or 0,
                    'failed_records': row[4] or 0,
                    'error_message': row[5],
                    'started_at': row[6].isoformat() if row[6] else None,
                    'completed_at': row[7].isoformat() if row[7] else None
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

    def start_bulk_import(self, directory: str = 'downloads/stm') -> Dict:
        """
        Start importing all STM files in directory in background

        Args:
            directory: Path to directory containing STM files

        Returns:
            Dict with success status and PID
        """
        if self.is_running():
            return {
                'success': False,
                'error': 'STM import already running'
            }

        # Count files to import
        files = list(Path(directory).glob('STM_*.xls'))
        total_files = len(files)

        if total_files == 0:
            return {
                'success': True,
                'message': 'No STM files to import',
                'total': 0
            }

        # Initialize progress file
        progress = {
            'import_id': f"stm_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'type': 'stm_bulk',
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
            'stm_import_batch.py',
            '--directory', directory
        ]

        # Write to log file instead of PIPE to prevent deadlock
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"stm_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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
            'import_id': progress['import_id'],
            'total_files': total_files
        }

    def start_single_import(self, filepath: str) -> Dict:
        """
        Start importing a single STM file in background

        Args:
            filepath: Path to file to import

        Returns:
            Dict with success status and PID
        """
        if self.is_running():
            return {
                'success': False,
                'error': 'STM import already running'
            }

        # Initialize progress file
        progress = {
            'import_id': f"stm_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'type': 'stm_single',
            'filename': Path(filepath).name,
            'status': 'running',
            'total_files': 1,
            'completed_files': 0,
            'current_file': Path(filepath).name,
            'started_at': datetime.now().isoformat(),
            'records_imported': 0,
            'errors': []
        }

        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

        # Start import process in background
        cmd = [
            sys.executable,
            'stm_import_batch.py',
            '--file', filepath
        ]

        # Write to log file
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"stm_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        with open(log_file, 'w') as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.environ.get('APP_ROOT', str(Path(__file__).parent.parent)),
                start_new_session=True
            )

        # Save PID
        self.pid_file.write_text(str(process.pid))

        return {
            'success': True,
            'pid': process.pid,
            'import_id': progress['import_id']
        }

    def stop(self) -> bool:
        """Stop running STM import process"""
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
