#!/usr/bin/env python3
"""
Unified Import Runner - Manage background import processes for all types (REP, STM, SMT)
"""

import subprocess
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class UnifiedImportRunner:
    """Unified runner for all import types with consistent progress tracking"""

    VALID_TYPES = ['rep', 'stm', 'smt']

    # Configuration for each import type
    CONFIG = {
        'rep': {
            'directory': 'downloads/rep',
            'pattern': '*.xls',
            'description': 'REP (Reimbursement)'
        },
        'stm': {
            'directory': 'downloads/stm',
            'pattern': 'STM_*.xls',
            'description': 'STM (Statement)'
        },
        'smt': {
            'directory': 'downloads/smt',
            'pattern': 'smt_budget_*.csv',
            'description': 'SMT (Budget Transfer)'
        }
    }

    def __init__(self):
        # Single progress file for all imports
        self.progress_file = Path('import_progress.json')
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

    def get_progress(self) -> Dict:
        """Get current import progress (any type)"""
        if not self.progress_file.exists():
            return {
                'running': False,
                'status': 'idle',
                'import_type': None
            }

        try:
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)

            # Add running status based on PID
            progress['running'] = self.is_running()

            return progress

        except (json.JSONDecodeError, IOError):
            return {
                'running': False,
                'status': 'error',
                'error': 'Could not read progress file'
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

        # Initialize progress file with standardized format
        progress = {
            'import_type': import_type,
            'import_id': f"import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'status': 'running',
            'running': True,
            'total_files': total_files,
            'completed_files': 0,
            'current_file': None,
            'records_imported': 0,
            'failed_files': [],
            'started_at': datetime.now().isoformat(),
            'completed_at': None
        }

        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

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
            'import_id': progress['import_id'],
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

        # Initialize progress file
        progress = {
            'import_type': import_type,
            'import_id': f"import_{import_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'status': 'running',
            'running': True,
            'total_files': 1,
            'completed_files': 0,
            'current_file': file_path.name,
            'records_imported': 0,
            'failed_files': [],
            'started_at': datetime.now().isoformat(),
            'completed_at': None
        }

        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2)

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
            'import_id': progress['import_id'],
            'import_type': import_type,
            'filename': file_path.name
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
            self.pid_file.unlink(missing_ok=True)

            # Update progress file
            if self.progress_file.exists():
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)

                progress['status'] = 'cancelled'
                progress['running'] = False
                progress['completed_at'] = datetime.now().isoformat()

                with open(self.progress_file, 'w') as f:
                    json.dump(progress, f, indent=2)

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
        if self.progress_file.exists() and not self.is_running():
            try:
                with open(self.progress_file, 'r') as f:
                    progress = json.load(f)

                if progress.get('status') == 'running':
                    progress['status'] = 'interrupted'
                    progress['running'] = False
                    progress['completed_at'] = datetime.now().isoformat()

                    with open(self.progress_file, 'w') as f:
                        json.dump(progress, f, indent=2)
            except (json.JSONDecodeError, IOError):
                pass


# Singleton instance for use across app
unified_import_runner = UnifiedImportRunner()
