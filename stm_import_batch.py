#!/usr/bin/env python3
"""
STM (Statement) Batch Import with Progress Tracking
Import NHSO Statement files into database with progress updates

Usage:
    python stm_import_batch.py --directory downloads/stm
    python stm_import_batch.py --file downloads/stm/STM_10670_IPUCS256811_01.xls
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Progress file path
PROGRESS_FILE = Path('stm_import_progress.json')


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


def get_imported_files() -> set:
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
        logger.warning(f"Could not check imported files: {e}")
        return set()


def import_single_file(filepath: str) -> dict:
    """Import a single STM file"""
    from config.database import get_db_config
    from utils.stm.importer import STMImporter

    db_config = get_db_config()
    importer = STMImporter(db_config)

    try:
        importer.connect()
        result = importer.import_file(filepath)
        return result
    finally:
        importer.disconnect()


def import_directory(dirpath: str) -> dict:
    """Import all STM files in a directory with progress tracking"""
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
    imported_files = get_imported_files()

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

        # Update progress - current file
        update_progress({
            'current_file': filename,
            'completed_files': idx,
            'records_imported': results['total_records']
        })

        try:
            result = import_single_file(str(filepath))

            if result.get('success'):
                results['imported'] += 1
                records = result.get('claim_records', 0) or result.get('records', 0) or 0
                results['total_records'] += records
                logger.info(f"  ✓ Imported {records} claims")
            else:
                results['failed'] += 1
                error = result.get('error', 'Unknown error')
                results['failed_files'].append({
                    'filename': filename,
                    'error': error
                })
                logger.error(f"  ✗ Failed: {error}")

        except Exception as e:
            results['failed'] += 1
            results['failed_files'].append({
                'filename': filename,
                'error': str(e)
            })
            logger.error(f"  ✗ Exception: {e}")

        # Update progress after each file
        update_progress({
            'completed_files': idx + 1,
            'records_imported': results['total_records'],
            'failed_files': results['failed_files']
        })

    # Final update
    update_progress({
        'status': 'completed',
        'completed_files': total_files,
        'records_imported': results['total_records'],
        'failed_files': results['failed_files'],
        'completed_at': datetime.now().isoformat()
    })

    logger.info(f"\n{'='*50}")
    logger.info(f"STM Import Complete!")
    logger.info(f"  Total: {total_files} files")
    logger.info(f"  Imported: {results['imported']}")
    logger.info(f"  Failed: {results['failed']}")
    logger.info(f"  Skipped: {results['skipped']}")
    logger.info(f"  Total Records: {results['total_records']}")
    logger.info(f"{'='*50}")

    return results


def import_file(filepath: str) -> dict:
    """Import a single file with progress tracking"""
    path = Path(filepath)
    if not path.exists():
        update_progress({
            'status': 'error',
            'error': f'File not found: {filepath}',
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': f'File not found: {filepath}'}

    filename = path.name
    logger.info(f"Importing: {filename}")

    update_progress({
        'current_file': filename,
        'completed_files': 0
    })

    try:
        result = import_single_file(filepath)

        if result.get('success'):
            records = result.get('claim_records', 0) or result.get('records', 0) or 0
            logger.info(f"  ✓ Imported {records} claims")
            update_progress({
                'status': 'completed',
                'completed_files': 1,
                'records_imported': records,
                'completed_at': datetime.now().isoformat()
            })
        else:
            error = result.get('error', 'Unknown error')
            logger.error(f"  ✗ Failed: {error}")
            update_progress({
                'status': 'completed',
                'completed_files': 1,
                'failed_files': [{'filename': filename, 'error': error}],
                'completed_at': datetime.now().isoformat()
            })

        return result

    except Exception as e:
        logger.error(f"  ✗ Exception: {e}")
        update_progress({
            'status': 'error',
            'error': str(e),
            'completed_at': datetime.now().isoformat()
        })
        return {'success': False, 'error': str(e)}


def main():
    parser = argparse.ArgumentParser(
        description='Import NHSO Statement (STM) files with progress tracking'
    )
    parser.add_argument('--directory', '-d', type=str,
                       help='Directory containing STM files')
    parser.add_argument('--file', '-f', type=str,
                       help='Single STM file to import')

    args = parser.parse_args()

    if args.file:
        result = import_file(args.file)
    elif args.directory:
        result = import_directory(args.directory)
    else:
        # Default to downloads/stm
        result = import_directory('downloads/stm')

    # Exit with appropriate code
    if result.get('success'):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
