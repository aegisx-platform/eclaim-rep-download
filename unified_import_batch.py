#!/usr/bin/env python3
"""
Unified Import Batch Script
Import REP, STM, or SMT files with progress tracking

Usage:
    python unified_import_batch.py --type rep --directory downloads/rep
    python unified_import_batch.py --type stm --file downloads/stm/STM_10670_IPUCS256811_01.xls
    python unified_import_batch.py --type smt --directory downloads/smt
"""

import os
import sys
import json
import csv
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Progress file path (shared with UnifiedImportRunner)
PROGRESS_FILE = Path('import_progress.json')

# Real-time log file for web UI
REALTIME_LOG_FILE = Path('logs/realtime.log')


def stream_log(message: str, level: str = 'info', source: str = 'import'):
    """Write log to realtime stream file for web UI"""
    print(message, flush=True)
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
    except Exception:
        pass


def update_progress(updates: dict):
    """Update progress file with new values"""
    try:
        if PROGRESS_FILE.exists():
            with open(PROGRESS_FILE, 'r') as f:
                progress = json.load(f)
        else:
            progress = {}

        progress.update(updates)

        with open(PROGRESS_FILE, 'w') as f:
            json.dump(progress, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not update progress file: {e}")


# === REP Import Functions ===

def get_rep_imported_files() -> set:
    """Get set of already imported REP filenames"""
    try:
        from config.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filename FROM eclaim_imported_files WHERE status = 'completed'"
        )
        imported = {row[0] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return imported
    except Exception as e:
        logger.warning(f"Could not check imported files: {e}")
        return set()


def import_rep_file(filepath: str) -> dict:
    """Import a single REP file"""
    from config.database import get_db_config, DB_TYPE
    from utils.eclaim.importer_v2 import import_eclaim_file

    db_config = get_db_config()
    return import_eclaim_file(filepath, db_config, DB_TYPE)


def import_rep_directory(dirpath: str) -> dict:
    """Import all REP files in directory with progress tracking"""
    path = Path(dirpath)
    if not path.is_dir():
        update_progress({
            'status': 'error',
            'error': f'{dirpath} is not a directory',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': f'{dirpath} is not a directory'}

    # Find all XLS files
    xls_files = sorted(path.glob('*.xls'))
    if not xls_files:
        update_progress({
            'status': 'completed',
            'message': 'No REP files found',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': True, 'message': 'No REP files found', 'total_files': 0}

    # Get already imported files
    imported_files = get_rep_imported_files()

    # Filter to only unimported files
    files_to_import = [f for f in xls_files if f.name not in imported_files]

    if not files_to_import:
        update_progress({
            'status': 'completed',
            'message': 'All files already imported',
            'total_files': len(xls_files),
            'skipped': len(xls_files),
            'completed_at': datetime.now().isoformat()
        })
        return {'success': True, 'message': 'All files already imported', 'skipped': len(xls_files)}

    total_files = len(files_to_import)
    update_progress({
        'total_files': total_files,
        'skipped_files': len(xls_files) - total_files
    })

    stream_log(f"Starting REP import: {total_files} files", 'info', 'import')
    stream_log("=" * 50, 'info', 'import')

    results = {
        'success': True,
        'total_files': total_files,
        'imported': 0,
        'failed': 0,
        'skipped': len(xls_files) - total_files,
        'total_records': 0,
        'failed_files': []
    }

    for idx, filepath in enumerate(files_to_import):
        filename = filepath.name
        logger.info(f"\n[{idx + 1}/{total_files}] Importing: {filename}")

        # Update progress
        update_progress({
            'current_file': filename,
            'completed_files': idx,
            'records_imported': results['total_records']
        })

        try:
            result = import_rep_file(str(filepath))

            if result.get('success'):
                results['imported'] += 1
                records = result.get('imported_records', 0) or result.get('records', 0) or 0
                results['total_records'] += records
                stream_log(f"[{idx + 1}/{total_files}] ✓ {filename}: {records} records", 'success', 'import')
            else:
                results['failed'] += 1
                error = result.get('error', 'Unknown error')
                results['failed_files'].append({
                    'filename': filename,
                    'error': error
                })
                stream_log(f"[{idx + 1}/{total_files}] ✗ {filename}: {error}", 'error', 'import')

        except Exception as e:
            results['failed'] += 1
            results['failed_files'].append({
                'filename': filename,
                'error': str(e)
            })
            stream_log(f"[{idx + 1}/{total_files}] ✗ {filename}: {e}", 'error', 'import')

        # Update progress after each file
        update_progress({
            'completed_files': idx + 1,
            'records_imported': results['total_records'],
            'failed_files': results['failed_files']
        })

    # Final update
    update_progress({
        'status': 'completed',
        'running': False,
        'completed_files': total_files,
        'records_imported': results['total_records'],
        'failed_files': results['failed_files'],
        'completed_at': datetime.now().isoformat()
    })

    stream_log("=" * 50, 'info', 'import')
    stream_log(f"REP Import Complete: {results['imported']}/{total_files} files, {results['total_records']} records",
               'success' if results['failed'] == 0 else 'warning', 'import')

    return results


# === STM Import Functions ===

def get_stm_imported_files() -> set:
    """Get set of already imported STM filenames"""
    try:
        from config.database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT filename FROM stm_imported_files WHERE status = 'completed'"
        )
        imported = {row[0] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        return imported
    except Exception as e:
        logger.warning(f"Could not check STM imported files: {e}")
        return set()


def import_stm_file(filepath: str) -> dict:
    """Import a single STM file"""
    from config.database import get_db_config, DB_TYPE
    from utils.stm.importer import STMImporter

    db_config = get_db_config()
    importer = STMImporter(db_config, DB_TYPE)

    try:
        importer.connect()
        result = importer.import_file(filepath)
        return result
    finally:
        importer.disconnect()


def import_stm_directory(dirpath: str) -> dict:
    """Import all STM files in directory with progress tracking"""
    path = Path(dirpath)
    if not path.is_dir():
        update_progress({
            'status': 'error',
            'error': f'{dirpath} is not a directory',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': f'{dirpath} is not a directory'}

    # Find all STM files
    stm_files = sorted(path.glob('STM_*.xls'))
    if not stm_files:
        update_progress({
            'status': 'completed',
            'message': 'No STM files found',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': True, 'message': 'No STM files found', 'total_files': 0}

    # Get already imported files
    imported_files = get_stm_imported_files()

    # Filter to only unimported files
    files_to_import = [f for f in stm_files if f.name not in imported_files]

    if not files_to_import:
        update_progress({
            'status': 'completed',
            'message': 'All files already imported',
            'total_files': len(stm_files),
            'skipped': len(stm_files),
            'completed_at': datetime.now().isoformat()
        })
        return {'success': True, 'message': 'All files already imported', 'skipped': len(stm_files)}

    total_files = len(files_to_import)
    update_progress({
        'total_files': total_files,
        'skipped_files': len(stm_files) - total_files
    })

    stream_log(f"Starting STM import: {total_files} files", 'info', 'import')
    stream_log("=" * 50, 'info', 'import')

    results = {
        'success': True,
        'total_files': total_files,
        'imported': 0,
        'failed': 0,
        'skipped': len(stm_files) - total_files,
        'total_records': 0,
        'failed_files': []
    }

    for idx, filepath in enumerate(files_to_import):
        filename = filepath.name
        logger.info(f"\n[{idx + 1}/{total_files}] Importing: {filename}")

        # Update progress
        update_progress({
            'current_file': filename,
            'completed_files': idx,
            'records_imported': results['total_records']
        })

        try:
            result = import_stm_file(str(filepath))

            if result.get('success'):
                results['imported'] += 1
                # STM returns claim_records for claim items
                records = result.get('claim_records', 0) or result.get('records', 0) or 0
                results['total_records'] += records
                stream_log(f"[{idx + 1}/{total_files}] ✓ {filename}: {records} records", 'success', 'import')
            else:
                results['failed'] += 1
                error = result.get('error', 'Unknown error')
                results['failed_files'].append({
                    'filename': filename,
                    'error': error
                })
                stream_log(f"[{idx + 1}/{total_files}] ✗ {filename}: {error}", 'error', 'import')

        except Exception as e:
            results['failed'] += 1
            results['failed_files'].append({
                'filename': filename,
                'error': str(e)
            })
            stream_log(f"[{idx + 1}/{total_files}] ✗ {filename}: {e}", 'error', 'import')

        # Update progress after each file
        update_progress({
            'completed_files': idx + 1,
            'records_imported': results['total_records'],
            'failed_files': results['failed_files']
        })

    # Final update
    update_progress({
        'status': 'completed',
        'running': False,
        'completed_files': total_files,
        'records_imported': results['total_records'],
        'failed_files': results['failed_files'],
        'completed_at': datetime.now().isoformat()
    })

    stream_log("=" * 50, 'info', 'import')
    stream_log(f"STM Import Complete: {results['imported']}/{total_files} files, {results['total_records']} records",
               'success' if results['failed'] == 0 else 'warning', 'import')

    return results


# === SMT Import Functions ===

def import_smt_file(filepath: str) -> dict:
    """
    Import a single SMT file to database

    Supports:
    - CSV files (.csv)
    - Excel files (.xlsx) - with header at row 5 (skip 4 rows)
    """
    from smt_budget_fetcher import SMTBudgetFetcher
    import pandas as pd

    try:
        fetcher = SMTBudgetFetcher()
        records = []

        filepath_obj = Path(filepath)
        file_ext = filepath_obj.suffix.lower()

        # Read file based on extension
        if file_ext == '.csv':
            # CSV format
            with open(filepath, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    records.append(row)

        elif file_ext in ['.xlsx', '.xls']:
            # Excel format - skip first 4 rows, header at row 5
            df = pd.read_excel(filepath, skiprows=4, engine='openpyxl' if file_ext == '.xlsx' else 'xlrd')

            # Convert DataFrame to list of dicts
            records = df.to_dict('records')

            # Filter out empty rows (all values are NaN)
            records = [r for r in records if not all(pd.isna(v) for v in r.values())]

        else:
            return {'success': False, 'error': f'Unsupported file format: {file_ext}. Use .csv, .xlsx, or .xls'}

        if not records:
            return {'success': False, 'error': 'No records in file'}

        saved_count = fetcher.save_to_database(records)

        return {
            'success': True,
            'records': saved_count,
            'message': f'Imported {saved_count} records from {file_ext} file'
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}


def import_smt_directory(dirpath: str) -> dict:
    """Import all SMT files (CSV and Excel) in directory with progress tracking"""
    path = Path(dirpath)
    if not path.is_dir():
        update_progress({
            'status': 'error',
            'error': f'{dirpath} is not a directory',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': f'{dirpath} is not a directory'}

    # Find all SMT files (CSV and Excel)
    smt_csv_files = list(path.glob('smt_budget_*.csv'))
    smt_xlsx_files = list(path.glob('smt_budget_*.xlsx'))
    smt_xls_files = list(path.glob('smt_budget_*.xls'))
    smt_files = sorted(smt_csv_files + smt_xlsx_files + smt_xls_files)
    if not smt_files:
        update_progress({
            'status': 'completed',
            'message': 'No SMT files found',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': True, 'message': 'No SMT files found', 'total_files': 0}

    total_files = len(smt_files)
    update_progress({
        'total_files': total_files
    })

    stream_log(f"Starting SMT import: {total_files} files", 'info', 'import')
    stream_log("=" * 50, 'info', 'import')

    results = {
        'success': True,
        'total_files': total_files,
        'imported': 0,
        'failed': 0,
        'total_records': 0,
        'failed_files': []
    }

    for idx, filepath in enumerate(smt_files):
        filename = filepath.name
        logger.info(f"\n[{idx + 1}/{total_files}] Importing: {filename}")

        # Update progress
        update_progress({
            'current_file': filename,
            'completed_files': idx,
            'records_imported': results['total_records']
        })

        try:
            result = import_smt_file(str(filepath))

            if result.get('success'):
                results['imported'] += 1
                records = result.get('records', 0)
                results['total_records'] += records
                stream_log(f"[{idx + 1}/{total_files}] ✓ {filename}: {records} records", 'success', 'import')
            else:
                results['failed'] += 1
                error = result.get('error', 'Unknown error')
                results['failed_files'].append({
                    'filename': filename,
                    'error': error
                })
                stream_log(f"[{idx + 1}/{total_files}] ✗ {filename}: {error}", 'error', 'import')

        except Exception as e:
            results['failed'] += 1
            results['failed_files'].append({
                'filename': filename,
                'error': str(e)
            })
            stream_log(f"[{idx + 1}/{total_files}] ✗ {filename}: {e}", 'error', 'import')

        # Update progress after each file
        update_progress({
            'completed_files': idx + 1,
            'records_imported': results['total_records'],
            'failed_files': results['failed_files']
        })

    # Final update
    update_progress({
        'status': 'completed',
        'running': False,
        'completed_files': total_files,
        'records_imported': results['total_records'],
        'failed_files': results['failed_files'],
        'completed_at': datetime.now().isoformat()
    })

    stream_log("=" * 50, 'info', 'import')
    stream_log(f"SMT Import Complete: {results['imported']}/{total_files} files, {results['total_records']} records",
               'success' if results['failed'] == 0 else 'warning', 'import')

    return results


# === Main Entry Point ===

def import_single_file(import_type: str, filepath: str) -> dict:
    """Import a single file based on type"""
    path = Path(filepath)
    if not path.exists():
        update_progress({
            'status': 'error',
            'error': f'File not found: {filepath}',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': f'File not found: {filepath}'}

    filename = path.name
    logger.info(f"Importing single {import_type.upper()} file: {filename}")

    update_progress({
        'current_file': filename,
        'completed_files': 0
    })

    try:
        if import_type == 'rep':
            result = import_rep_file(filepath)
        elif import_type == 'stm':
            result = import_stm_file(filepath)
        elif import_type == 'smt':
            result = import_smt_file(filepath)
        else:
            return {'success': False, 'error': f'Invalid import type: {import_type}'}

        if result.get('success'):
            records = (
                result.get('imported_records', 0) or
                result.get('claim_records', 0) or
                result.get('records', 0) or 0
            )
            stream_log(f"✓ {filename}: {records} records", 'success', 'import')
            update_progress({
                'status': 'completed',
                'running': False,
                'completed_files': 1,
                'records_imported': records,
                'completed_at': datetime.now().isoformat()
            })
        else:
            error = result.get('error', 'Unknown error')
            stream_log(f"✗ {filename}: {error}", 'error', 'import')
            update_progress({
                'status': 'completed',
                'running': False,
                'completed_files': 1,
                'failed_files': [{'filename': filename, 'error': error}],
                'completed_at': datetime.now().isoformat()
            })

        return result

    except Exception as e:
        logger.error(f"Exception: {e}")
        update_progress({
            'status': 'error',
            'running': False,
            'error': str(e),
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': str(e)}


def import_directory(import_type: str, dirpath: str) -> dict:
    """Import all files in directory based on type"""
    if import_type == 'rep':
        return import_rep_directory(dirpath)
    elif import_type == 'stm':
        return import_stm_directory(dirpath)
    elif import_type == 'smt':
        return import_smt_directory(dirpath)
    else:
        return {'success': False, 'error': f'Invalid import type: {import_type}'}


def main():
    parser = argparse.ArgumentParser(
        description='Unified Import Batch Script for REP, STM, and SMT files'
    )
    parser.add_argument('--type', '-t', type=str, required=True,
                        choices=['rep', 'stm', 'smt'],
                        help='Import type: rep, stm, or smt')
    parser.add_argument('--directory', '-d', type=str,
                        help='Directory containing files to import')
    parser.add_argument('--file', '-f', type=str,
                        help='Single file to import')
    parser.add_argument('--files', nargs='+',
                        help='List of specific files to import')

    args = parser.parse_args()

    stream_log(f"Unified Import Batch started: type={args.type}", 'info', 'import')

    if args.file:
        result = import_single_file(args.type, args.file)
    elif args.directory:
        result = import_directory(args.type, args.directory)
    else:
        # Default directories
        default_dirs = {
            'rep': 'downloads/rep',
            'stm': 'downloads/stm',
            'smt': 'downloads/smt'
        }
        result = import_directory(args.type, default_dirs[args.type])

    # Exit with appropriate code
    if result.get('success'):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
