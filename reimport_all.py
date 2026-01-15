#!/usr/bin/env python3
"""
Reimport All Files Script
Reimport all Excel files in downloads/ directory using the new index-based column mapping
"""

import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.database import get_db_config, DB_TYPE
from utils.eclaim.importer_v2 import import_eclaim_file

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/reimport_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


def find_excel_files(downloads_dir: str = 'downloads') -> list:
    """Find all E-Claim Excel files in downloads directory (recursive)"""
    files = []
    # Search recursively for eclaim xls files
    # Only import files starting with 'eclaim_' (not STM_ which are summary statements)
    for f in Path(downloads_dir).rglob('*.xls'):
        if f.name.lower().startswith('eclaim_'):
            files.append(str(f))
    for f in Path(downloads_dir).rglob('*.xlsx'):
        if f.name.lower().startswith('eclaim_'):
            files.append(str(f))
    return sorted(files)


def main():
    """Main function to reimport all files"""
    logger.info("=" * 60)
    logger.info("Starting Reimport All Files")
    logger.info("=" * 60)

    # Get database config
    db_config = get_db_config()
    db_type = DB_TYPE

    logger.info(f"Database type: {db_type}")
    logger.info(f"Database host: {db_config.get('host', 'localhost')}")
    logger.info(f"Database name: {db_config.get('database', db_config.get('dbname', 'unknown'))}")

    # Find all files
    files = find_excel_files()
    total_files = len(files)

    if total_files == 0:
        logger.warning("No Excel files found in downloads/ directory")
        return

    logger.info(f"Found {total_files} files to import")

    # Track statistics
    success_count = 0
    fail_count = 0
    total_records = 0
    errors = []

    # Import each file
    for idx, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        logger.info(f"[{idx}/{total_files}] Importing: {filename}")

        try:
            result = import_eclaim_file(filepath, db_config, db_type)

            if result.get('success'):
                records = result.get('imported_records', 0)
                total_records += records
                success_count += 1
                logger.info(f"  ✓ Success: {records} records imported")
            else:
                fail_count += 1
                error_msg = result.get('error', 'Unknown error')
                errors.append((filename, error_msg))
                logger.error(f"  ✗ Failed: {error_msg}")

        except Exception as e:
            fail_count += 1
            errors.append((filename, str(e)))
            logger.error(f"  ✗ Exception: {e}")

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("IMPORT SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total files: {total_files}")
    logger.info(f"Success: {success_count}")
    logger.info(f"Failed: {fail_count}")
    logger.info(f"Total records imported: {total_records}")

    if errors:
        logger.info("")
        logger.info("Failed files:")
        for filename, error in errors[:10]:  # Show first 10 errors
            logger.info(f"  - {filename}: {error[:100]}")
        if len(errors) > 10:
            logger.info(f"  ... and {len(errors) - 10} more")

    logger.info("=" * 60)

    return {
        'total_files': total_files,
        'success': success_count,
        'failed': fail_count,
        'total_records': total_records,
        'errors': errors
    }


if __name__ == '__main__':
    main()
