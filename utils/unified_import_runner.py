#!/usr/bin/env python3
"""
Unified Import Runner - Manage background import processes for all types (REP, STM, SMT)
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from config.db_pool import get_connection, return_connection


class UnifiedImportRunner:
    """Unified runner for all import types with consistent progress tracking (using database)"""

    VALID_TYPES = ['rep', 'stm', 'smt']

    # Configuration for each import type
    CONFIG = {
        'rep': {
            'directory': 'downloads/rep',
            'pattern': '*.xls',
            'description': 'REP (Reimbursement)',
            'table': 'eclaim_imported_files'
        },
        'stm': {
            'directory': 'downloads/stm',
            'pattern': 'STM_*.xls',
            'description': 'STM (Statement)',
            'table': 'stm_imported_files'
        },
        'smt': {
            'directory': 'downloads/smt',
            'pattern': 'smt_budget_*.csv',
            'description': 'SMT (Budget Transfer)',
            'table': 'smt_budget_import_history'
        }
    }

    def __init__(self):
        # Single PID file - only one import at a time
        self.pid_file = Path('/tmp/eclaim_import.pid')

    def is_running(self) -> bool:
        """Check if any import is currently running"""
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

    def get_progress(self, import_type: str = None) -> Dict:
        """
        Get current import progress from database

        Args:
            import_type: Optional filter by type (rep, stm, smt)

        Returns progress for most recent processing/pending import
        """
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Query from appropriate table based on import_type
            # If no type specified, check all tables and return most recent
            if import_type == 'stm':
                table = 'stm_imported_files'
            elif import_type == 'smt':
                # SMT doesn't have tracking table yet - return idle
                return_connection(conn)
                return {
                    'running': False,
                    'status': 'idle',
                    'import_type': 'smt'
                }
            else:
                # REP or None - use eclaim_imported_files
                table = 'eclaim_imported_files'

            cursor.execute(f"""
                SELECT filename, status, total_records, imported_records,
                       failed_records, error_message, import_started_at,
                       import_completed_at
                FROM {table}
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
                    'import_type': import_type or 'rep',
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
                    'status': 'idle',
                    'import_type': import_type
                }

        except Exception as e:
            if conn:
                return_connection(conn)
            return {
                'running': False,
                'status': 'error',
                'error': f'Database error: {str(e)}'
            }

    def get_current_import_type(self) -> Optional[str]:
        """Get the type of currently running import"""
        progress = self.get_progress()
        if progress.get('running'):
            return progress.get('import_type')
        return None

    def start_import(self, import_type: str, files: Optional[List[str]] = None) -> Dict:
        """
        Start import for any type

        Args:
            import_type: 'rep', 'stm', or 'smt'
            files: Optional list of specific files to import

        Returns:
            Dict with success status and PID
        """
        # Validate import type
        if import_type not in self.VALID_TYPES:
            return {
                'success': False,
                'error': f'Invalid import type: {import_type}. Must be one of: {", ".join(self.VALID_TYPES)}'
            }

        # Check if already running
        if self.is_running():
            current_type = self.get_current_import_type()
            return {
                'success': False,
                'error': f'Import already running (type: {current_type or "unknown"})'
            }

        config = self.CONFIG[import_type]
        directory = Path(config['directory'])

        # Count files to import
        if files:
            total_files = len(files)
        else:
            pattern = config['pattern']
            all_files = list(directory.glob(pattern))
            total_files = len(all_files)

        if total_files == 0:
            return {
                'success': True,
                'message': f'No {import_type.upper()} files to import',
                'total': 0
            }
        # Progress tracking via database (eclaim_imported_files table)
        # Generate import_id for tracking
        import_id = f"import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Build command
        cmd = [
            sys.executable,
            'unified_import_batch.py',
            '--type', import_type,
            '--directory', str(directory)
        ]

        # Add specific files if provided
        if files:
            cmd.extend(['--files'] + files)

        # Write to log file
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        with open(log_file, 'w') as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True  # Detach from parent
            )

        # Save PID
        self.pid_file.write_text(str(process.pid))

        return {
            'success': True,
            'pid': process.pid,
            'import_id': import_id,
            'import_type': import_type,
            'total_files': total_files
        }

    def start_single_file_import(self, import_type: str, filepath: str) -> Dict:
        """
        Start importing a single file

        Args:
            import_type: 'rep', 'stm', or 'smt'
            filepath: Path to file to import

        Returns:
            Dict with success status and PID
        """
        # Validate import type
        if import_type not in self.VALID_TYPES:
            return {
                'success': False,
                'error': f'Invalid import type: {import_type}'
            }

        # Check if already running
        if self.is_running():
            current_type = self.get_current_import_type()
            return {
                'success': False,
                'error': f'Import already running (type: {current_type or "unknown"})'
            }

        file_path = Path(filepath)
        if not file_path.exists():
            return {
                'success': False,
                'error': f'File not found: {filepath}'
            }
        # Progress tracking via database (eclaim_imported_files table)
        # Generate import_id for tracking
        import_id = f"import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Build command
        cmd = [
            sys.executable,
            'unified_import_batch.py',
            '--type', import_type,
            '--file', str(filepath)
        ]

        # Write to log file
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / f"import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        with open(log_file, 'w') as log_f:
            process = subprocess.Popen(
                cmd,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=True
            )

        # Save PID
        self.pid_file.write_text(str(process.pid))

        return {
            'success': True,
            'pid': process.pid,
            'import_id': import_id,
            'import_type': import_type,
            'filename': Path(filepath).name
        }

    def stop(self) -> Dict:
        """Stop running import process"""
        if not self.is_running():
            return {
                'success': False,
                'error': 'No import running'
            }

        try:
            pid = int(self.pid_file.read_text().strip())
            subprocess.run(['kill', str(pid)], check=True)
            self.pid_file.unlink(missing_ok=True)            # Progress is tracked in database

            return {
                'success': True,
                'message': 'Import cancelled'
            }

        except (ValueError, subprocess.CalledProcessError) as e:
            return {
                'success': False,
                'error': str(e)
            }

    def cleanup(self):
        """Cleanup old progress files and PID files"""
        self.pid_file.unlink(missing_ok=True)

        # Keep progress file for history, but mark as completed if stale
        # Progress is tracked in database, no JSON cleanup needed


# Singleton instance for use across app
unified_import_runner = UnifiedImportRunner()
