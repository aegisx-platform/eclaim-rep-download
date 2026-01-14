#!/usr/bin/env python3
"""
E-Claim Import CLI
Command-line tool to import E-Claim XLS files to database
"""

import argparse
import logging
import sys
import json
import threading
from pathlib import Path
from typing import List
from datetime import datetime

from config.database import get_db_config, DOWNLOADS_DIR, DB_TYPE
from utils.eclaim.importer_v2 import import_eclaim_file
from utils.eclaim.parser import EClaimFileParser
from utils.job_history_manager import job_history_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Progress file for real-time tracking
PROGRESS_FILE = Path('import_progress.json')

# Realtime log file (same as log_streamer uses)
REALTIME_LOG_FILE = Path('logs/realtime.log')
_log_lock = threading.Lock()


def stream_log(message: str, level: str = 'info', source: str = 'import'):
    """
    Write log entry to realtime log file for UI streaming

    Args:
        message: Log message
        level: Log level (info, success, error, warning)
        source: Source identifier
    """
    with _log_lock:
        try:
            REALTIME_LOG_FILE.parent.mkdir(exist_ok=True)
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'level': level,
                'source': source,
                'message': message
            }
            with open(REALTIME_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            print(f"Error writing to realtime log: {e}")


def update_progress(progress_data: dict):
    """
    Update import progress file for real-time tracking

    Args:
        progress_data: Progress dict to save
    """
    try:
        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress_data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not update progress file: {e}")


def import_single_file(filepath: str, db_config: dict, log_to_stream: bool = True) -> dict:
    """
    Import single XLS file

    Args:
        filepath: Path to XLS file
        db_config: Database configuration
        log_to_stream: Whether to write to realtime log stream

    Returns:
        Import result dict
    """
    filename = Path(filepath).name
    try:
        logger.info(f"Importing file: {filepath}")
        result = import_eclaim_file(filepath, db_config, DB_TYPE)

        if result['success']:
            msg = f"✓ {filename}: {result['imported_records']} records imported"
            logger.info(msg)
            if log_to_stream:
                stream_log(msg, 'success', 'import')
        else:
            msg = f"✗ {filename}: {result.get('error', 'Unknown error')}"
            logger.error(msg)
            if log_to_stream:
                stream_log(msg, 'error', 'import')

        return result

    except Exception as e:
        msg = f"✗ {filename}: {str(e)}"
        logger.error(msg)
        if log_to_stream:
            stream_log(msg, 'error', 'import')
        return {'success': False, 'error': str(e)}


def import_directory(directory: str, db_config: dict, file_pattern: str = '*.xls') -> dict:
    """
    Import all XLS files in directory

    Args:
        directory: Directory path
        db_config: Database configuration
        file_pattern: File pattern to match (default: *.xls)

    Returns:
        Summary dict
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory not found: {directory}")

    # Find all XLS files
    xls_files = list(dir_path.glob(file_pattern))

    if not xls_files:
        logger.warning(f"No files found matching pattern: {file_pattern}")
        stream_log(f"⚠ No files found in {directory}", 'warning', 'import')
        return {'total': 0, 'success': 0, 'failed': 0}

    logger.info(f"Found {len(xls_files)} files to import")
    stream_log(f"📥 Starting bulk import: {len(xls_files)} files", 'info', 'import')
    stream_log("=" * 50, 'info', 'import')

    # Record job start
    job_id = job_history_manager.start_job(
        job_type='import',
        job_subtype='bulk',
        parameters={
            'directory': directory,
            'file_pattern': file_pattern,
            'total_files': len(xls_files)
        },
        triggered_by='manual'
    )

    # Import each file
    results = {
        'total': len(xls_files),
        'success': 0,
        'failed': 0,
        'details': []
    }

    # Initialize progress tracking
    progress = {
        'import_id': job_id,  # Use job_id from history
        'type': 'bulk',
        'status': 'running',
        'total_files': len(xls_files),
        'completed_files': 0,
        'current_file': None,
        'current_file_index': 0,
        'started_at': datetime.now().isoformat(),
        'total_records_imported': 0,
        'failed_files': []
    }
    update_progress(progress)

    for idx, filepath in enumerate(xls_files, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{idx}/{len(xls_files)}] Importing: {filepath.name}")

        # Stream progress update every 10 files or on specific milestones
        if idx == 1 or idx % 10 == 0 or idx == len(xls_files):
            stream_log(f"[{idx}/{len(xls_files)}] Processing: {filepath.name}", 'info', 'import')

        # Update progress
        progress['current_file'] = filepath.name
        progress['current_file_index'] = idx
        progress['completed_files'] = idx - 1
        update_progress(progress)

        result = import_single_file(str(filepath), db_config, log_to_stream=True)

        if result['success']:
            results['success'] += 1
            progress['total_records_imported'] += result.get('imported_records', 0)
        else:
            results['failed'] += 1
            progress['failed_files'].append({
                'filename': filepath.name,
                'error': result.get('error')
            })

        results['details'].append({
            'filename': filepath.name,
            'success': result['success'],
            'imported_records': result.get('imported_records', 0),
            'error': result.get('error')
        })

        # Update progress after each file
        progress['completed_files'] = idx
        update_progress(progress)

    # Mark as completed
    progress['status'] = 'completed'
    progress['completed_at'] = datetime.now().isoformat()
    progress['current_file'] = None
    update_progress(progress)

    # Stream final summary
    stream_log("=" * 50, 'info', 'import')
    stream_log(f"📊 Import completed: {results['success']}/{results['total']} files successful",
               'success' if results['failed'] == 0 else 'warning', 'import')
    stream_log(f"   Total records: {progress['total_records_imported']}", 'info', 'import')
    if results['failed'] > 0:
        stream_log(f"   Failed files: {results['failed']}", 'error', 'import')

    # Record job completion
    job_history_manager.complete_job(
        job_id=job_id,
        status='completed' if results['failed'] == 0 else 'completed_with_errors',
        results={
            'total_files': results['total'],
            'success_files': results['success'],
            'failed_files': results['failed'],
            'total_records': progress['total_records_imported']
        },
        error_message=f"{results['failed']} files failed" if results['failed'] > 0 else None
    )

    return results


def analyze_file(filepath: str):
    """
    Analyze XLS file and print summary

    Args:
        filepath: Path to XLS file
    """
    try:
        parser = EClaimFileParser(filepath)
        parser.load_file()
        summary = parser.get_summary()

        print("\n" + "="*60)
        print("File Analysis")
        print("="*60)
        print(f"Filename:      {summary['filename']}")
        print(f"File Type:     {summary['file_type']}")
        print(f"Hospital Code: {summary['hospital_code']}")
        print(f"File Date:     {summary['file_date']}")
        print(f"Total Rows:    {summary['total_rows']}")
        print(f"Total Columns: {summary['total_columns']}")
        print(f"Header Row:    {summary['header_row']}")
        print("\nFirst 10 Columns:")
        for i, col in enumerate(summary['columns'][:10], 1):
            print(f"  {i:2d}. {col}")
        print("="*60)

    except Exception as e:
        logger.error(f"Error analyzing file: {e}")
        raise


def print_summary(results: dict):
    """Print import summary"""
    print("\n" + "="*60)
    print("Import Summary")
    print("="*60)
    print(f"Total Files:      {results['total']}")
    print(f"Successful:       {results['success']}")
    print(f"Failed:           {results['failed']}")

    if results.get('details'):
        print("\nDetails:")
        for detail in results['details']:
            status = "✓" if detail['success'] else "✗"
            print(f"  {status} {detail['filename']}: {detail['imported_records']} records")
            if not detail['success']:
                print(f"     Error: {detail['error']}")

    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description='Import E-Claim XLS files to database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Import single file
  python eclaim_import.py file.xls

  # Import all files in directory
  python eclaim_import.py --directory downloads/

  # Analyze file without importing
  python eclaim_import.py --analyze file.xls

  # Import all IP files
  python eclaim_import.py --directory downloads/ --pattern "*_IP_*.xls"
        """
    )

    parser.add_argument('filepath', nargs='?', help='Path to XLS file to import')
    parser.add_argument('--directory', '-d', help='Import all files in directory')
    parser.add_argument('--pattern', '-p', default='*.xls', help='File pattern (default: *.xls)')
    parser.add_argument('--analyze', '-a', action='store_true', help='Analyze file without importing')
    parser.add_argument('--db-type', choices=['postgresql', 'mysql'], help='Database type')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')

    args = parser.parse_args()

    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Analyze mode
    if args.analyze:
        if not args.filepath:
            parser.error("--analyze requires filepath argument")
        analyze_file(args.filepath)
        return 0

    # Get database config
    try:
        db_config = get_db_config(args.db_type)
    except Exception as e:
        logger.error(f"Database configuration error: {e}")
        return 1

    # Import mode
    try:
        if args.directory:
            # Import directory
            results = import_directory(args.directory, db_config, args.pattern)
            print_summary(results)
            return 0 if results['failed'] == 0 else 1

        elif args.filepath:
            # Import single file
            result = import_single_file(args.filepath, db_config)
            return 0 if result['success'] else 1

        else:
            # No arguments - import all files in downloads directory
            if DOWNLOADS_DIR.exists():
                results = import_directory(str(DOWNLOADS_DIR), db_config)
                print_summary(results)
                return 0 if results['failed'] == 0 else 1
            else:
                logger.error(f"Downloads directory not found: {DOWNLOADS_DIR}")
                return 1

    except KeyboardInterrupt:
        logger.info("\nImport interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
