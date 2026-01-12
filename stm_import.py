#!/usr/bin/env python3
"""
STM (Statement) Import CLI Tool
Import NHSO Statement files into database

Usage:
    python stm_import.py downloads/STM_10670_IPUCS256811_01.xls
    python stm_import.py downloads/  # Import all STM files in directory
"""

import os
import sys
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


def import_single_file(filepath: str, run_reconciliation: bool = False) -> dict:
    """Import a single STM file"""
    from config.database import get_db_config
    from utils.stm.importer import STMImporter

    db_config = get_db_config()
    importer = STMImporter(db_config)

    try:
        importer.connect()
        result = importer.import_file(filepath)

        if result['success'] and run_reconciliation:
            logger.info("Running reconciliation...")
            recon_result = importer.run_reconciliation(result.get('file_id'))
            result['reconciliation'] = recon_result

        return result
    finally:
        importer.disconnect()


def import_directory(dirpath: str, run_reconciliation: bool = False) -> dict:
    """Import all STM files in a directory"""
    path = Path(dirpath)
    if not path.is_dir():
        return {'success': False, 'error': f'{dirpath} is not a directory'}

    # Find all STM files
    stm_files = list(path.glob('STM_*.xls'))
    if not stm_files:
        return {'success': True, 'message': 'No STM files found', 'files': []}

    results = {
        'success': True,
        'total_files': len(stm_files),
        'imported': 0,
        'failed': 0,
        'files': []
    }

    for filepath in sorted(stm_files):
        logger.info(f"\nImporting: {filepath.name}")
        result = import_single_file(str(filepath), run_reconciliation=False)
        results['files'].append(result)

        if result['success']:
            results['imported'] += 1
            logger.info(f"  ✓ Imported {result.get('claim_records', 0)} claims")
        else:
            results['failed'] += 1
            logger.error(f"  ✗ Failed: {result.get('error', 'Unknown error')}")

    # Run reconciliation once after all imports
    if run_reconciliation and results['imported'] > 0:
        logger.info("\nRunning reconciliation for all imported files...")
        from config.database import get_db_config
        from utils.stm.importer import STMImporter

        db_config = get_db_config()
        importer = STMImporter(db_config)
        try:
            importer.connect()
            recon_result = importer.run_reconciliation()
            results['reconciliation'] = recon_result
        finally:
            importer.disconnect()

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Import NHSO Statement (STM) files into database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python stm_import.py downloads/STM_10670_IPUCS256811_01.xls
    python stm_import.py downloads/
    python stm_import.py downloads/ --reconcile
        """
    )
    parser.add_argument(
        'path',
        help='Path to STM file or directory containing STM files'
    )
    parser.add_argument(
        '--reconcile', '-r',
        action='store_true',
        help='Run reconciliation with REP data after import'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Check path exists
    path = Path(args.path)
    if not path.exists():
        logger.error(f"Path does not exist: {args.path}")
        sys.exit(1)

    start_time = datetime.now()
    logger.info(f"STM Import started at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    if path.is_file():
        result = import_single_file(str(path), run_reconciliation=args.reconcile)
        if result['success']:
            logger.info(f"\n✓ Import completed successfully")
            logger.info(f"  File ID: {result.get('file_id')}")
            logger.info(f"  Type: {result.get('file_type')} / {result.get('scheme')}")
            logger.info(f"  Summary records: {result.get('summary_records', 0)}")
            logger.info(f"  REP summary records: {result.get('rep_summary_records', 0)}")
            logger.info(f"  Claim records: {result.get('claim_records', 0)}")

            if 'reconciliation' in result:
                recon = result['reconciliation']
                if recon['success']:
                    logger.info(f"\n  Reconciliation:")
                    for status, data in recon.get('statistics', {}).items():
                        logger.info(f"    - {status}: {data['count']} records")
        else:
            logger.error(f"\n✗ Import failed: {result.get('error')}")
            sys.exit(1)
    else:
        result = import_directory(str(path), run_reconciliation=args.reconcile)
        logger.info(f"\n{'='*60}")
        logger.info(f"Import Summary:")
        logger.info(f"  Total files: {result['total_files']}")
        logger.info(f"  Imported: {result['imported']}")
        logger.info(f"  Failed: {result['failed']}")

        if 'reconciliation' in result:
            recon = result['reconciliation']
            if recon['success']:
                logger.info(f"\nReconciliation Summary:")
                for status, data in recon.get('statistics', {}).items():
                    logger.info(f"  - {status}: {data['count']} records")

        if result['failed'] > 0:
            sys.exit(1)

    elapsed = datetime.now() - start_time
    logger.info(f"\nTotal time: {elapsed}")


if __name__ == '__main__':
    main()
