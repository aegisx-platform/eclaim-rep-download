#!/usr/bin/env python3
"""
Import Runner - Manage background import processes with progress tracking
"""

import subprocess
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class ImportRunner:
    """Manage background import processes with progress tracking"""

    def __init__(self):
        self.progress_file = Path('import_progress.json')
        self.pid_file = Path('/tmp/eclaim_import.pid')

    def is_running(self) -> bool:
        """Check if import is currently running"""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())
            # Check if process exists
            subprocess.run(['ps', '-p', str(pid)], check=True, capture_output=True)
            return True
        except (ValueError, subprocess.CalledProcessError):
            # PID file exists but process is dead
            self.pid_file.unlink(missing_ok=True)
            return False

    def get_progress(self) -> Dict:
        """Get current import progress"""
        if not self.progress_file.exists():
            return {
                'running': False,
                'status': 'idle'
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

        # Initialize progress file
        progress = {
            'import_id': f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'type': 'single',
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
            'eclaim_import.py',
            filepath
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
