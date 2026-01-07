"""Downloader Runner - Run eclaim_downloader_http.py as background process"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime


class DownloaderRunner:
    def __init__(self):
        self.pid_file = Path('/tmp/eclaim_downloader.pid')
        self.log_dir = Path('logs')
        self.log_file = self.log_dir / 'downloader.log'
        self.script_path = Path(__file__).parent.parent / 'eclaim_downloader_http.py'

        # Ensure log directory exists
        self.log_dir.mkdir(exist_ok=True)

    def is_running(self):
        """Check if downloader process is currently running"""
        if not self.pid_file.exists():
            return False

        try:
            pid = int(self.pid_file.read_text().strip())

            # Check if process with this PID exists
            try:
                os.kill(pid, 0)  # Signal 0 just checks if process exists
                return True
            except OSError:
                # Process doesn't exist, cleanup stale PID file
                self.pid_file.unlink()
                return False

        except (ValueError, IOError):
            # Invalid PID file, cleanup
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False

    def start(self):
        """Start the downloader as a background process"""
        if self.is_running():
            return {
                'success': False,
                'error': 'Downloader is already running'
            }

        if not self.script_path.exists():
            return {
                'success': False,
                'error': f'Downloader script not found: {self.script_path}'
            }

        try:
            # Open log file
            with open(self.log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*60}\n")
                log.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log.write(f"{'='*60}\n")

                # Start subprocess in detached mode
                # Use sys.executable to get current Python interpreter
                process = subprocess.Popen(
                    [sys.executable, str(self.script_path)],
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from parent
                    cwd=self.script_path.parent  # Set working directory
                )

            # Save PID to file
            self.pid_file.write_text(str(process.pid))

            return {
                'success': True,
                'pid': process.pid,
                'start_time': datetime.now().isoformat()
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to start downloader: {str(e)}'
            }

    def get_status(self):
        """Get current status of downloader process"""
        if self.is_running():
            pid = int(self.pid_file.read_text().strip())

            return {
                'running': True,
                'pid': pid,
                'message': 'Downloader is running'
            }
        else:
            return {
                'running': False,
                'pid': None,
                'message': 'Downloader is not running'
            }

    def get_log_tail(self, lines=50):
        """Get last N lines from log file"""
        if not self.log_file.exists():
            return []

        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        except Exception as e:
            print(f"Error reading log: {e}")
            return []
