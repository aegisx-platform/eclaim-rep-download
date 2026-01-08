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
            except:
                print(f"Scheduled download error: {e}")


# Global scheduler instance
download_scheduler = DownloadScheduler()
