#!/usr/bin/env python3
"""
Parallel Download Runner for Scheduled Downloads

This script is used by the scheduler to run parallel downloads for REP files.
It reads the schedule settings and downloads files for all enabled schemes.
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

from utils.log_stream import log_streamer, stream_log
from utils.settings_manager import SettingsManager
from utils.parallel_downloader import ParallelDownloader


def get_current_month_year():
    """Get current month and year in Buddhist Era"""
    now = datetime.now()
    return now.month, now.year + 543


def main():
    parser = argparse.ArgumentParser(description='Parallel Download Runner for Scheduled Downloads')
    parser.add_argument('--workers', type=int, default=3, help='Number of parallel workers (default: 3)')
    parser.add_argument('--auto-import', action='store_true', help='Auto-import after download')
    parser.add_argument('--month', type=int, help='Month to download (default: current month)')
    parser.add_argument('--year', type=int, help='Year to download in BE (default: current year)')
    args = parser.parse_args()

    # Get current month/year if not specified
    month, year = get_current_month_year()
    if args.month:
        month = args.month
    if args.year:
        year = args.year

    # Load settings
    settings_manager = SettingsManager()
    schedule_settings = settings_manager.get_schedule_settings()
    credentials = settings_manager.get_all_credentials()

    # Filter enabled credentials
    enabled_creds = [c for c in credentials if c.get('enabled', True)]
    if not enabled_creds:
        stream_log("No enabled credentials found. Please configure credentials first.", 'error')
        sys.exit(1)

    # Get schemes from schedule settings
    schemes = schedule_settings.get('schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

    workers = min(max(args.workers, 2), 5)  # Clamp 2-5

    stream_log("=" * 60)
    stream_log("Parallel Download Runner (Scheduled)")
    stream_log("=" * 60)
    stream_log(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    stream_log(f"Month/Year: {month}/{year} BE")
    stream_log(f"Schemes: {', '.join(schemes)}")
    stream_log(f"Workers: {workers}")
    stream_log(f"Accounts: {len(enabled_creds)}")
    stream_log(f"Auto-import: {args.auto_import}")
    stream_log("=" * 60)

    total_downloaded = 0
    total_skipped = 0
    total_failed = 0

    # Download for each scheme
    for scheme in schemes:
        stream_log(f"\n{'='*40}")
        stream_log(f"Processing scheme: {scheme.upper()}")
        stream_log(f"{'='*40}")

        try:
            downloader = ParallelDownloader(
                credentials=enabled_creds,
                month=month,
                year=year,
                scheme=scheme,
                max_workers=workers
            )

            result = downloader.run()

            total_downloaded += result.get('completed', 0)
            total_skipped += result.get('skipped', 0)
            total_failed += result.get('failed', 0)

        except Exception as e:
            stream_log(f"Error downloading {scheme}: {e}", 'error')
            total_failed += 1

    # Summary
    stream_log("\n" + "=" * 60)
    stream_log("PARALLEL DOWNLOAD SUMMARY")
    stream_log("=" * 60)
    stream_log(f"Total Downloaded: {total_downloaded}")
    stream_log(f"Total Skipped: {total_skipped}")
    stream_log(f"Total Failed: {total_failed}")

    # Auto-import if enabled and there were successful downloads
    if args.auto_import and total_downloaded > 0:
        stream_log("\n" + "=" * 60)
        stream_log("Starting Auto-Import...")
        stream_log("=" * 60)

        try:
            from utils.eclaim.importer_v2 import import_files_parallel
            from config.database import get_db_config, DB_TYPE

            download_dir = Path('downloads/rep')
            files = sorted([str(f) for f in download_dir.glob('*.xls')])

            if files:
                db_config = get_db_config()
                import_result = import_files_parallel(files, db_config, DB_TYPE, max_workers=3)
                stream_log(f"Import completed: {import_result}", 'success')
            else:
                stream_log("No files to import", 'warning')

        except Exception as e:
            stream_log(f"Import error: {e}", 'error')

    stream_log("\nParallel download runner completed!")
    stream_log(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
