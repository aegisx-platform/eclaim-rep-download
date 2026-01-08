"""Downloader Runner - Run eclaim_downloader_http.py as background process"""

import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime
import psutil
from utils.log_stream import log_streamer


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

            # Check if process exists and is running (not zombie)
            try:
                process = psutil.Process(pid)

                # Check if process is still alive and not a zombie
                if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                    return True
                else:
                    # Process is zombie or terminated, cleanup PID file
                    self.pid_file.unlink()
                    return False

            except psutil.NoSuchProcess:
                # Process doesn't exist, cleanup stale PID file
                self.pid_file.unlink()
                return False

        except (ValueError, IOError):
            # Invalid PID file, cleanup
            if self.pid_file.exists():
                self.pid_file.unlink()
            return False

    def start(self, month=None, year=None, auto_import=False):
        """
        Start the downloader as a background process

        Args:
            month (int, optional): Month (1-12) to download. None = current month
            year (int, optional): Year in Buddhist Era. None = current year
            auto_import (bool): Auto-import files after download completes
        """
        if self.is_running():
            return {
                'success': False,
                'error': 'Downloader is already running'
            }

        # Use wrapper script if auto-import is enabled
        if auto_import:
            wrapper_script = self.script_path.parent / 'download_with_import.py'
            if not wrapper_script.exists():
                return {
                    'success': False,
                    'error': f'Wrapper script not found: {wrapper_script}'
                }
            script_to_run = wrapper_script
        else:
            if not self.script_path.exists():
                return {
                    'success': False,
                    'error': f'Downloader script not found: {self.script_path}'
                }
            script_to_run = self.script_path

        try:
            # Build command with optional month/year parameters
            cmd = [sys.executable, str(script_to_run)]

            if month is not None:
                cmd.extend(['--month', str(month)])
            if year is not None:
                cmd.extend(['--year', str(year)])
            if auto_import:
                cmd.append('--auto-import')

            # Log to realtime log
            log_streamer.write_log('='*60, 'info', 'system')
            log_streamer.write_log(f'Started at: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 'info', 'system')
            if month and year:
                log_streamer.write_log(f'Download for: Month {month}, Year {year} BE', 'info', 'system')
            if auto_import:
                log_streamer.write_log('Auto-import: ENABLED', 'info', 'system')
            log_streamer.write_log('='*60, 'info', 'system')

            # Open log file
            with open(self.log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*60}\n")
                log.write(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                if month and year:
                    log.write(f"Download for: Month {month}, Year {year} BE\n")
                if auto_import:
                    log.write(f"Auto-import: ENABLED\n")
                log.write(f"{'='*60}\n")

                # Start subprocess in detached mode
                # Use sys.executable to get current Python interpreter
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,  # Detach from parent
                    cwd=self.script_path.parent  # Set working directory
                )

            # Save PID to file
            self.pid_file.write_text(str(process.pid))

            result = {
                'success': True,
                'pid': process.pid,
                'start_time': datetime.now().isoformat(),
                'auto_import': auto_import
            }

            if month and year:
                result['month'] = month
                result['year'] = year

            return result

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

    def start_bulk(self, start_month, start_year, end_month, end_year):
        """
        Start bulk downloader for date range

        Args:
            start_month (int): Starting month (1-12)
            start_year (int): Starting year in BE
            end_month (int): Ending month (1-12)
            end_year (int): Ending year in BE
        """
        # Check if already running (check both regular and bulk)
        if self.is_running():
            return {
                'success': False,
                'error': 'Downloader is already running'
            }

        # Check if bulk downloader script exists
        bulk_script = self.script_path.parent / 'bulk_downloader.py'
        if not bulk_script.exists():
            return {
                'success': False,
                'error': f'Bulk downloader script not found: {bulk_script}'
            }

        try:
            # Build command for bulk downloader
            cmd = [
                sys.executable,
                str(bulk_script),
                f'{start_month},{start_year}',
                f'{end_month},{end_year}'
            ]

            # Open log file
            bulk_log_file = self.log_dir / 'bulk_downloader.log'
            with open(bulk_log_file, 'a', encoding='utf-8') as log:
                log.write(f"\n{'='*60}\n")
                log.write(f"Bulk Download Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log.write(f"Date range: {start_month}/{start_year} to {end_month}/{end_year}\n")
                log.write(f"{'='*60}\n")

                # Start subprocess in detached mode
                process = subprocess.Popen(
                    cmd,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    cwd=self.script_path.parent
                )

            # Save PID to file
            self.pid_file.write_text(str(process.pid))

            return {
                'success': True,
                'pid': process.pid,
                'start_time': datetime.now().isoformat(),
                'start_month': start_month,
                'start_year': start_year,
                'end_month': end_month,
                'end_year': end_year
            }

        except Exception as e:
            return {
                'success': False,
                'error': f'Failed to start bulk downloader: {str(e)}'
            }

    def get_bulk_progress(self):
        """Get progress of bulk download operation"""
        import json

        progress_file = self.script_path.parent / 'bulk_download_progress.json'

        if not progress_file.exists():
            return {
                'running': False,
                'error': 'No bulk download in progress'
            }

        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)

            # Add running status
            progress['running'] = self.is_running()

            return progress

        except Exception as e:
            return {
                'running': False,
                'error': f'Failed to read progress: {str(e)}'
            }
