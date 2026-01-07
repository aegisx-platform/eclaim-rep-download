#!/usr/bin/env python3
"""
E-Claim Import CLI
Command-line tool to import E-Claim XLS files to database
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List

from config.database import get_db_config, DOWNLOADS_DIR
from utils.eclaim.importer import import_eclaim_file
from utils.eclaim.parser import EClaimFileParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def import_single_file(filepath: str, db_config: dict) -> dict:
    """
    Import single XLS file

    Args:
        filepath: Path to XLS file
        db_config: Database configuration

    Returns:
        Import result dict
    """
    try:
        logger.info(f"Importing file: {filepath}")
        result = import_eclaim_file(filepath, db_config)

        if result['success']:
            logger.info(f"✓ Import successful: {result['imported_records']}/{result['total_records']} records")
        else:
            logger.error(f"✗ Import failed: {result.get('error')}")

        return result

    except Exception as e:
        logger.error(f"✗ Error importing file: {e}")
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
        return {'total': 0, 'success': 0, 'failed': 0}

    logger.info(f"Found {len(xls_files)} files to import")

    # Import each file
    results = {
        'total': len(xls_files),
        'success': 0,
        'failed': 0,
        'details': []
    }

    for filepath in xls_files:
        logger.info(f"\n{'='*60}")
        result = import_single_file(str(filepath), db_config)

        if result['success']:
            results['success'] += 1
        else:
            results['failed'] += 1

        results['details'].append({
            'filename': filepath.name,
            'success': result['success'],
            'imported_records': result.get('imported_records', 0),
            'error': result.get('error')
        })

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
