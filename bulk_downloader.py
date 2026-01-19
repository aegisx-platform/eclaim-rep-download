#!/usr/bin/env python3
"""
Bulk Downloader - Orchestrate sequential downloads across multiple months/years and schemes
"""

import json
import sys
import time
import threading
from datetime import datetime
from pathlib import Path
import subprocess

# Import the main downloader
from eclaim_downloader_http import EClaimDownloader
from utils.logging_config import setup_logger, safe_format_exception

# Set up secure logging with credential masking
logger = setup_logger('bulk_downloader', enable_masking=True)

# Job history tracking (optional - may not be available in all environments)
job_history_manager = None
try:
    from utils.job_history_manager import job_history_manager
except ImportError:
    pass  # Running standalone without job tracking

# Import schemes configuration
try:
    from config.schemes import (
        INSURANCE_SCHEMES,
        DEFAULT_ENABLED_SCHEMES,
        get_schemes_sorted_by_priority
    )
except ImportError:
    # Fallback if config not available
    INSURANCE_SCHEMES = {'ucs': {'code': 'ucs', 'name_th': 'บัตรทอง', 'priority': 1}}
    DEFAULT_ENABLED_SCHEMES = ['ucs']
    def get_schemes_sorted_by_priority(codes):
        return [INSURANCE_SCHEMES.get(c, {'code': c}) for c in codes]

# Direct log writing for real-time logs (works in subprocess)
import json as json_module
REALTIME_LOG_FILE = Path('logs/realtime.log')


def stream_log(message: str, level: str = 'info'):
    """Write log to both console and real-time stream file"""
    print(message, flush=True)
    try:
        REALTIME_LOG_FILE.parent.mkdir(exist_ok=True)
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'source': 'download',
            'message': message
        }
        with open(REALTIME_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(json_module.dumps(log_entry) + '\n')
    except Exception:
        pass  # Silently ignore log errors


class BulkDownloader:
    def __init__(self):
        self.progress_file = Path('bulk_download_progress.json')
        self.delay_between_months = 10  # seconds between each month download
        self.delay_between_schemes = 5  # seconds between each scheme download
        self.stop_monitoring = False  # Flag to stop monitoring thread
        self.delay_before_import = 2  # seconds to wait before starting import

    def import_downloaded_files(self, downloaded_files: list, progress: dict) -> dict:
        """
        Import downloaded files to database

        Args:
            downloaded_files: List of file paths to import
            progress: Progress dict to update

        Returns:
            dict: Import results with success count and errors
        """
        from config.database import get_db_config, DB_TYPE
        from utils.eclaim.importer_v2 import import_eclaim_file

        results = {
            'total': len(downloaded_files),
            'success': 0,
            'failed': 0,
            'records': 0,
            'errors': []
        }

        if not downloaded_files:
            return results

        stream_log(f"\n📥 Starting import of {len(downloaded_files)} files...")

        try:
            db_config = get_db_config()
        except Exception as e:
            stream_log(f"✗ Database config error: {e}", 'error')
            results['errors'].append(str(e))
            return results

        for idx, filepath in enumerate(downloaded_files, 1):
            filename = Path(filepath).name
            stream_log(f"[{idx}/{len(downloaded_files)}] Importing: {filename}")

            try:
                result = import_eclaim_file(filepath, db_config, DB_TYPE)

                if result.get('success'):
                    results['success'] += 1
                    records = result.get('imported_records', 0)
                    results['records'] += records
                    stream_log(f"  ✓ Imported: {records} records", 'success')
                else:
                    results['failed'] += 1
                    error_msg = result.get('error', 'Unknown error')
                    results['errors'].append(f"{filename}: {error_msg}")
                    stream_log(f"  ✗ Failed: {error_msg}", 'error')

            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"{filename}: {str(e)}")
                stream_log(f"  ✗ Error: {str(e)}", 'error')

        stream_log(f"📥 Import complete: {results['success']}/{results['total']} files, {results['records']} records", 'success')

        return results

    def generate_date_range(self, start_month, start_year, end_month, end_year):
        """
        Generate list of (month, year) tuples for the date range

        Args:
            start_month (int): Starting month (1-12)
            start_year (int): Starting year in Buddhist Era
            end_month (int): Ending month (1-12)
            end_year (int): Ending year in Buddhist Era

        Returns:
            list: List of (month, year) tuples

        Example:
            generate_date_range(1, 2568, 3, 2568) -> [(1,2568), (2,2568), (3,2568)]
            generate_date_range(11, 2567, 2, 2568) -> [(11,2567), (12,2567), (1,2568), (2,2568)]
        """
        date_range = []
        current_month = start_month
        current_year = start_year

        while True:
            date_range.append((current_month, current_year))

            # Check if we've reached the end
            if current_month == end_month and current_year == end_year:
                break

            # Move to next month
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

            # Safety check to prevent infinite loop
            if current_year > end_year + 1:
                break

        return date_range

    def load_progress(self):
        """Load progress from file"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def save_progress(self, progress):
        """Save progress to file"""
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

    def monitor_file_count(self, month, year, scheme, progress):
        """
        Background thread to update file count while downloading

        Args:
            month (int): Current month being downloaded
            year (int): Current year being downloaded
            scheme (str): Current scheme being downloaded
            progress (dict): Progress dictionary to update
        """
        from utils.history_manager import HistoryManager
        iteration_progress_file = Path('download_iteration_progress.json')

        while not self.stop_monitoring:
            try:
                # Count files for current month/year/scheme
                history_mgr = HistoryManager()
                current_files = len([
                    d for d in history_mgr.get_all_downloads()
                    if d.get('month') == month and d.get('year') == year
                    and d.get('scheme', 'ucs') == scheme
                ])

                # Update progress
                progress['current_files'] = current_files

                # Read iteration progress for current_idx and total_files
                if iteration_progress_file.exists():
                    try:
                        with open(iteration_progress_file, 'r', encoding='utf-8') as f:
                            iter_progress = json.load(f)
                            # Only update if it's for the current month/year/scheme
                            if (iter_progress.get('month') == month and
                                iter_progress.get('year') == year and
                                iter_progress.get('scheme') == scheme):
                                progress['iteration_current_idx'] = iter_progress.get('current_idx', 0)
                                progress['iteration_total_files'] = iter_progress.get('total_files', 0)
                                progress['iteration_current_file'] = iter_progress.get('current_file')
                    except Exception:
                        pass

                # Save progress (this will make UI update)
                self.save_progress(progress)

                # Sleep before next check
                time.sleep(2)  # Update every 2 seconds for more responsive UI

            except Exception as e:
                print(f"Monitor error: {e}", flush=True)
                break

    def run_bulk_download(self, start_month, start_year, end_month, end_year, schemes=None, auto_import=False):
        """
        Execute downloads sequentially for each month and scheme in the date range

        Args:
            start_month (int): Starting month (1-12)
            start_year (int): Starting year in BE
            end_month (int): Ending month (1-12)
            end_year (int): Ending year in BE
            schemes (list, optional): List of scheme codes to download.
                                     Defaults to DEFAULT_ENABLED_SCHEMES.
            auto_import (bool): Whether to auto-import files after each download iteration.
        """
        # Start job tracking
        job_id = None
        if job_history_manager:
            try:
                job_id = job_history_manager.start_job(
                    job_type='download',
                    job_subtype='bulk',
                    parameters={
                        'start_month': start_month,
                        'start_year': start_year,
                        'end_month': end_month,
                        'end_year': end_year,
                        'schemes': schemes,
                        'auto_import': auto_import
                    },
                    triggered_by='manual'
                )
                stream_log(f"Job ID: {job_id}")
            except Exception as e:
                stream_log(f"Warning: Could not start job tracking: {e}", 'warning')

        # Get schemes to download
        if schemes is None:
            schemes = DEFAULT_ENABLED_SCHEMES

        # Sort schemes by priority
        sorted_schemes = get_schemes_sorted_by_priority(schemes)
        scheme_codes = [s.get('code', s) if isinstance(s, dict) else s for s in sorted_schemes]

        # Generate date range
        date_range = self.generate_date_range(start_month, start_year, end_month, end_year)

        # Calculate total iterations (months * schemes)
        total_iterations = len(date_range) * len(scheme_codes)

        # Initialize progress tracking
        bulk_id = f"bulk_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"
        progress = {
            'bulk_id': bulk_id,
            'start_date': {'month': start_month, 'year': start_year},
            'end_date': {'month': end_month, 'year': end_year},
            'schemes': scheme_codes,
            'total_months': len(date_range),
            'total_schemes': len(scheme_codes),
            'total_iterations': total_iterations,
            'completed_iterations': 0,
            'completed_months': 0,
            'current_month': None,
            'current_scheme': None,
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'monthly_results': [],
            'scheme_progress': {s: {'completed_months': 0, 'files': 0} for s in scheme_codes}
        }

        # Add import tracking if auto_import is enabled
        if auto_import:
            progress['auto_import'] = True
            progress['import_results'] = {
                'total_files': 0,
                'success': 0,
                'failed': 0,
                'total_records': 0
            }

        self.save_progress(progress)

        stream_log("="*60)
        stream_log("Bulk Download Started (Multi-Scheme)")
        stream_log("="*60)
        stream_log(f"Date range: {start_month}/{start_year} to {end_month}/{end_year}")
        stream_log(f"Total months: {len(date_range)}")
        stream_log(f"Schemes: {', '.join(s.upper() for s in scheme_codes)}")
        stream_log(f"Total iterations: {total_iterations} (months × schemes)")
        stream_log(f"Bulk ID: {bulk_id}")
        if auto_import:
            stream_log(f"Auto-import: ENABLED", 'success')

        iteration = 0
        # Process each month
        for month_idx, (month, year) in enumerate(date_range, 1):
            stream_log(f"\n{'='*60}")
            stream_log(f"[Month {month_idx}/{len(date_range)}] Processing {month}/{year}...")
            stream_log(f"{'='*60}")

            # Process each scheme for this month
            for scheme_idx, scheme in enumerate(scheme_codes, 1):
                iteration += 1
                pct = int(iteration / total_iterations * 100)
                stream_log(f"\n[{iteration}/{total_iterations}] ({pct}%) {month}/{year} - Scheme: {scheme.upper()}")
                stream_log("-"*60)

                # Update progress
                progress['current_month'] = {'month': month, 'year': year}
                progress['current_scheme'] = scheme
                progress['completed_iterations'] = iteration - 1
                progress['current_files'] = 0
                self.save_progress(progress)

                result = {
                    'month': month,
                    'year': year,
                    'scheme': scheme,
                    'status': 'running',
                    'files': 0,
                    'started_at': datetime.now().isoformat()
                }

                try:
                    # Start monitoring thread
                    self.stop_monitoring = False
                    monitor_thread = threading.Thread(
                        target=self.monitor_file_count,
                        args=(month, year, scheme, progress),
                        daemon=True
                    )
                    monitor_thread.start()

                    # Create downloader for this specific month/year/scheme
                    downloader = EClaimDownloader(month=month, year=year, scheme=scheme)

                    # Get initial files list (using filenames)
                    from utils.history_manager import HistoryManager
                    history_mgr = HistoryManager()
                    initial_filenames = set(
                        d.get('filename') for d in history_mgr.get_all_downloads()
                        if d.get('month') == month and d.get('year') == year
                        and d.get('scheme', 'ucs') == scheme and d.get('filename')
                    )

                    # Run the download
                    downloader.run()

                    # Stop monitoring thread
                    self.stop_monitoring = True
                    monitor_thread.join(timeout=2)

                    # Get final files list and find new downloads
                    final_files = [
                        d for d in history_mgr.get_all_downloads()
                        if d.get('month') == month and d.get('year') == year
                        and d.get('scheme', 'ucs') == scheme and d.get('filename')
                    ]
                    new_downloads = [
                        d for d in final_files
                        if d.get('filename') not in initial_filenames
                    ]

                    # Use file_path from history directly (already contains correct path)
                    new_file_paths = [
                        d.get('file_path') for d in new_downloads
                        if d.get('file_path') and Path(d.get('file_path')).exists()
                    ]
                    files_downloaded = len(new_downloads)

                    # Update result
                    result['status'] = 'completed'
                    result['completed_at'] = datetime.now().isoformat()
                    result['files'] = files_downloaded

                    # Update scheme progress
                    progress['scheme_progress'][scheme]['completed_months'] += 1
                    progress['scheme_progress'][scheme]['files'] += files_downloaded

                    stream_log(f"✓ {scheme.upper()} {month}/{year}: {files_downloaded} files", 'success')

                    # Auto-import if enabled and files were downloaded
                    if auto_import and new_file_paths:
                        time.sleep(self.delay_before_import)
                        import_results = self.import_downloaded_files(new_file_paths, progress)

                        # Update import tracking
                        progress['import_results']['total_files'] += import_results['total']
                        progress['import_results']['success'] += import_results['success']
                        progress['import_results']['failed'] += import_results['failed']
                        progress['import_results']['total_records'] += import_results['records']

                        result['import'] = {
                            'files': import_results['total'],
                            'success': import_results['success'],
                            'records': import_results['records']
                        }
                        self.save_progress(progress)

                except Exception as e:
                    stream_log(f"✗ Error {scheme.upper()} {month}/{year}: {str(e)}", 'error')
                    result['status'] = 'failed'
                    result['error'] = str(e)
                    result['completed_at'] = datetime.now().isoformat()

                # Record result
                progress['monthly_results'].append(result)
                progress['completed_iterations'] = iteration
                self.save_progress(progress)

                # Delay between schemes (except for last scheme of last month)
                if scheme_idx < len(scheme_codes) or month_idx < len(date_range):
                    delay = self.delay_between_schemes if scheme_idx < len(scheme_codes) else self.delay_between_months
                    stream_log(f"Waiting {delay} seconds...")
                    time.sleep(delay)

            # Update completed months
            progress['completed_months'] = month_idx
            self.save_progress(progress)

        # Mark bulk operation as completed
        progress['status'] = 'completed'
        progress['completed_at'] = datetime.now().isoformat()
        self.save_progress(progress)

        # Summary
        stream_log("\n" + "="*60)
        stream_log("Bulk Download Summary (Multi-Scheme)", 'success')
        stream_log("="*60)
        stream_log(f"Total iterations: {total_iterations}")
        stream_log(f"Completed: {progress['completed_iterations']}", 'success')
        failed_count = sum(1 for r in progress['monthly_results'] if r['status'] == 'failed')
        stream_log(f"Failed: {failed_count}", 'error' if failed_count > 0 else 'info')
        stream_log("By Scheme:")
        for scheme, data in progress['scheme_progress'].items():
            stream_log(f"  {scheme.upper()}: {data['files']} files from {data['completed_months']} months")

        # Import summary if auto_import was enabled
        if auto_import and progress.get('import_results'):
            ir = progress['import_results']
            stream_log("\nImport Summary:")
            stream_log(f"  Files imported: {ir['success']}/{ir['total_files']}", 'success' if ir['failed'] == 0 else 'info')
            stream_log(f"  Total records: {ir['total_records']}")
            if ir['failed'] > 0:
                stream_log(f"  Failed imports: {ir['failed']}", 'error')

        stream_log(f"\nStarted at: {progress['started_at']}")
        stream_log(f"Completed at: {progress['completed_at']}", 'success')
        stream_log("="*60)

        # Complete job tracking
        if job_history_manager and job_id:
            try:
                total_files = sum(s.get('files', 0) for s in progress.get('scheme_progress', {}).values())
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='completed' if failed_count == 0 else 'completed_with_errors',
                    results={
                        'total_iterations': total_iterations,
                        'completed_iterations': progress['completed_iterations'],
                        'total_files': total_files,
                        'failed_iterations': failed_count,
                        'schemes': scheme_codes,
                        'months': len(date_range)
                    },
                    error_message=f"{failed_count} iterations failed" if failed_count > 0 else None
                )
            except Exception as e:
                stream_log(f"Warning: Could not complete job tracking: {e}", 'warning')


def main():
    """Entry point for bulk downloader"""
    import argparse

    # Valid scheme codes
    VALID_SCHEMES = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']

    parser = argparse.ArgumentParser(
        description='Bulk E-Claim Downloader - Download from multiple months and schemes',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download Jan-Dec 2568 with default schemes (UCS, OFC, SSS, LGO)
  python bulk_downloader.py 1,2568 12,2568

  # Download with specific schemes
  python bulk_downloader.py 1,2568 12,2568 --schemes ucs,ofc

  # Download all 8 schemes
  python bulk_downloader.py 1,2568 3,2568 --schemes ucs,ofc,sss,lgo,nhs,bkk,bmt,srt

Insurance Schemes:
  ucs  - Universal Coverage Scheme (บัตรทอง)
  ofc  - Government Officer (ข้าราชการ)
  sss  - Social Security Scheme (ประกันสังคม)
  lgo  - Local Government Organization (อปท.)
  nhs  - NHSO Staff (สปสช.)
  bkk  - Bangkok Metropolitan Staff (กทม.)
  bmt  - BMTA Staff (ขสมก.)
  srt  - State Railway of Thailand Staff (รฟท.)
        """
    )

    parser.add_argument(
        'start',
        type=str,
        help='Start date as month,year (e.g., 1,2568)'
    )

    parser.add_argument(
        'end',
        type=str,
        help='End date as month,year (e.g., 12,2568)'
    )

    parser.add_argument(
        '--schemes',
        type=str,
        default=None,
        help='Comma-separated list of scheme codes (default: ucs,ofc,sss,lgo)'
    )

    parser.add_argument(
        '--auto-import',
        action='store_true',
        help='Auto-import files to database after each download iteration'
    )

    args = parser.parse_args()

    try:
        # Parse start/end dates
        start_parts = args.start.split(',')
        end_parts = args.end.split(',')

        start_month = int(start_parts[0])
        start_year = int(start_parts[1])
        end_month = int(end_parts[0])
        end_year = int(end_parts[1])

        # Parse schemes
        schemes = None
        if args.schemes:
            schemes = [s.strip().lower() for s in args.schemes.split(',')]
            # Validate schemes
            invalid = [s for s in schemes if s not in VALID_SCHEMES]
            if invalid:
                print(f"Error: Invalid scheme codes: {', '.join(invalid)}")
                print(f"Valid schemes: {', '.join(VALID_SCHEMES)}")
                sys.exit(1)

        # Validate dates
        if not (1 <= start_month <= 12 and 1 <= end_month <= 12):
            print("Error: Month must be between 1 and 12")
            sys.exit(1)

        if start_year > end_year or (start_year == end_year and start_month > end_month):
            print("Error: Start date must be before or equal to end date")
            sys.exit(1)

        # Run bulk download
        bulk_downloader = BulkDownloader()
        bulk_downloader.run_bulk_download(
            start_month, start_year,
            end_month, end_year,
            schemes=schemes,
            auto_import=args.auto_import
        )

    except ValueError as e:
        print(f"Error parsing arguments: {e}")
        print("Use: python bulk_downloader.py month,year month,year")
        sys.exit(1)
    except Exception as e:
        stream_log(f"✗ Bulk download error: {str(e)}", 'error')
        logger.error(safe_format_exception())
        sys.exit(1)


if __name__ == '__main__':
    main()
