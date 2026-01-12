"""Scheduler Service - Manage scheduled download jobs"""

import os
import sys
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess


class DownloadScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

    def add_scheduled_download(self, hour, minute, auto_import=False):
        """
        Add a scheduled download job

        Args:
            hour (int): Hour (0-23)
            minute (int): Minute (0-59)
            auto_import (bool): Whether to auto-import after download

        Returns:
            str: Job ID
        """
        # Create unique job ID based on time
        job_id = f"download_{hour:02d}_{minute:02d}"

        # Remove existing job if it exists
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Add new job
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func=self._run_download,
            trigger=trigger,
            args=[auto_import],
            id=job_id,
            name=f"Daily download at {hour:02d}:{minute:02d}",
            replace_existing=True
        )

        return job_id

    def remove_scheduled_download(self, job_id):
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            return True
        except Exception as e:
            print(f"Error removing job {job_id}: {e}")
            return False

    def get_all_jobs(self):
        """Get all scheduled jobs"""
        jobs = []
        for job in self.scheduler.get_jobs():
            # Extract hour and minute from trigger
            trigger = job.trigger
            if hasattr(trigger, 'fields'):
                hour = str(trigger.fields[5])  # hour field
                minute = str(trigger.fields[6])  # minute field
            else:
                hour = minute = "?"

            jobs.append({
                'id': job.id,
                'name': job.name,
                'next_run_time': job.next_run_time.isoformat() if job.next_run_time else None,
                'hour': hour,
                'minute': minute
            })

        return jobs

    def clear_all_jobs(self):
        """Remove all scheduled jobs"""
        self.scheduler.remove_all_jobs()

    def shutdown(self):
        """Shutdown scheduler"""
        self.scheduler.shutdown()

    def _run_download(self, auto_import=False):
        """
        Execute download process

        This runs as a background job, so we need to use subprocess
        """
        try:
            # Import here to avoid circular dependency
            from utils.log_stream import log_streamer

            log_streamer.write_log(
                f"⏰ Scheduled download started (auto_import={auto_import})",
                'info',
                'scheduler'
            )

            # Get project root directory
            project_root = Path(__file__).parent.parent

            # Build command
            cmd = [
                sys.executable,
                str(project_root / 'download_with_import.py')
            ]

            if auto_import:
                cmd.append('--auto-import')

            # Run download in background
            process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            log_streamer.write_log(
                f"✓ Scheduled download initiated (PID: {process.pid})",
                'success',
                'scheduler'
            )

        except Exception as e:
            try:
                from utils.log_stream import log_streamer
                log_streamer.write_log(
                    f"✗ Scheduled download failed: {str(e)}",
                    'error',
                    'scheduler'
                )
            except Exception:
                # Fallback to print if log_streamer fails
                print(f"Scheduled download error: {e}")


    def add_stm_scheduled_download(self, hour, minute, auto_import=False, schemes=None):
        """
        Add a scheduled Statement (STM) download job

        Args:
            hour (int): Hour (0-23)
            minute (int): Minute (0-59)
            auto_import (bool): Whether to auto-import after download
            schemes (list): List of schemes to download (UCS, OFC, SSS, LGO)

        Returns:
            str: Job ID
        """
        # Create unique job ID
        job_id = f"stm_{hour:02d}_{minute:02d}"

        # Remove existing job if it exists
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Default to all schemes if not specified
        if schemes is None:
            schemes = ['UCS', 'OFC', 'SSS', 'LGO']

        # Add new job
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func=self._run_stm_download,
            trigger=trigger,
            args=[auto_import, schemes],
            id=job_id,
            name=f"STM download at {hour:02d}:{minute:02d}",
            replace_existing=True
        )

        return job_id

    def remove_stm_jobs(self):
        """Remove all STM scheduled jobs"""
        for job in self.scheduler.get_jobs():
            if job.id.startswith('stm_'):
                self.scheduler.remove_job(job.id)

    def _run_stm_download(self, auto_import=False, schemes=None):
        """
        Execute Statement download process

        This runs as a background job. Downloads each scheme separately.
        """
        try:
            from utils.log_stream import log_streamer

            # Default to all schemes if not specified
            if schemes is None:
                schemes = ['ucs', 'ofc', 'sss', 'lgo']

            schemes_str = ','.join(schemes)
            log_streamer.write_log(
                f"⏰ Scheduled STM download started (schemes={schemes_str}, auto_import={auto_import})",
                'info',
                'scheduler'
            )

            # Get project root directory
            project_root = Path(__file__).parent.parent
            download_success = 0
            download_failed = 0

            # Download each scheme separately
            for scheme in schemes:
                log_streamer.write_log(
                    f"📥 Downloading STM for scheme: {scheme.upper()}",
                    'info',
                    'scheduler'
                )

                cmd = [
                    sys.executable,
                    str(project_root / 'stm_downloader_http.py'),
                    '--scheme', scheme.lower()
                ]

                process = subprocess.Popen(
                    cmd,
                    cwd=project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )

                stdout, _ = process.communicate(timeout=300)  # 5 min per scheme

                if process.returncode == 0:
                    download_success += 1
                    log_streamer.write_log(
                        f"✓ STM {scheme.upper()} download completed",
                        'success',
                        'scheduler'
                    )
                else:
                    download_failed += 1
                    log_streamer.write_log(
                        f"✗ STM {scheme.upper()} download failed",
                        'error',
                        'scheduler'
                    )

            log_streamer.write_log(
                f"📊 STM download summary: {download_success} success, {download_failed} failed",
                'info',
                'scheduler'
            )

            # Auto import if enabled and at least one download succeeded
            if auto_import and download_success > 0:
                log_streamer.write_log(
                    f"⏰ Starting STM auto-import...",
                    'info',
                    'scheduler'
                )
                import_cmd = [
                    sys.executable,
                    str(project_root / 'stm_import.py'),
                    str(project_root / 'downloads')
                ]
                import_process = subprocess.Popen(
                    import_cmd,
                    cwd=project_root,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                import_stdout, _ = import_process.communicate(timeout=600)
                if import_process.returncode == 0:
                    log_streamer.write_log(
                        f"✓ STM import completed",
                        'success',
                        'scheduler'
                    )
                else:
                    log_streamer.write_log(
                        f"✗ STM import failed: {import_stdout[:200]}",
                        'error',
                        'scheduler'
                    )

        except Exception as e:
            try:
                from utils.log_stream import log_streamer
                log_streamer.write_log(
                    f"✗ STM download failed: {str(e)}",
                    'error',
                    'scheduler'
                )
            except Exception:
                print(f"STM download error: {e}")

    def add_smt_scheduled_fetch(self, hour, minute, vendor_id, auto_save_db=True):
        """
        Add a scheduled SMT budget fetch job

        Args:
            hour (int): Hour (0-23)
            minute (int): Minute (0-59)
            vendor_id (str): Hospital/Vendor ID
            auto_save_db (bool): Whether to auto-save to database

        Returns:
            str: Job ID
        """
        # Create unique job ID
        job_id = f"smt_{hour:02d}_{minute:02d}"

        # Remove existing job if it exists
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # Add new job
        trigger = CronTrigger(hour=hour, minute=minute)
        job = self.scheduler.add_job(
            func=self._run_smt_fetch,
            trigger=trigger,
            args=[vendor_id, auto_save_db],
            id=job_id,
            name=f"SMT fetch at {hour:02d}:{minute:02d}",
            replace_existing=True
        )

        return job_id

    def remove_smt_jobs(self):
        """Remove all SMT scheduled jobs"""
        for job in self.scheduler.get_jobs():
            if job.id.startswith('smt_'):
                self.scheduler.remove_job(job.id)

    def _run_smt_fetch(self, vendor_id, auto_save_db=True):
        """
        Execute SMT budget fetch

        This runs as a background job
        """
        try:
            from utils.log_stream import log_streamer

            log_streamer.write_log(
                f"⏰ Scheduled SMT fetch started (vendor={vendor_id}, save_db={auto_save_db})",
                'info',
                'scheduler'
            )

            # Get project root directory
            project_root = Path(__file__).parent.parent

            # Build command
            cmd = [
                sys.executable,
                str(project_root / 'smt_budget_fetcher.py'),
                '--vendor-id', str(vendor_id),
                '--quiet'
            ]

            if auto_save_db:
                cmd.append('--save-db')

            # Run fetch in background
            process = subprocess.Popen(
                cmd,
                cwd=project_root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                env={**os.environ, 'DB_HOST': os.getenv('DB_HOST', 'db')}
            )

            # Wait for completion and log result
            stdout, _ = process.communicate(timeout=300)

            if process.returncode == 0:
                log_streamer.write_log(
                    f"✓ SMT fetch completed (vendor={vendor_id})",
                    'success',
                    'scheduler'
                )
            else:
                log_streamer.write_log(
                    f"✗ SMT fetch failed: {stdout}",
                    'error',
                    'scheduler'
                )

        except Exception as e:
            try:
                from utils.log_stream import log_streamer
                log_streamer.write_log(
                    f"✗ SMT fetch failed: {str(e)}",
                    'error',
                    'scheduler'
                )
            except Exception:
                # Fallback to print if log_streamer fails
                print(f"SMT fetch error: {e}")


# Global scheduler instance
download_scheduler = DownloadScheduler()
