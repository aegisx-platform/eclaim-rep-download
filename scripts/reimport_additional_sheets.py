#!/usr/bin/env python3
"""
Re-import additional sheets (deny, drug, instrument, zero_paid) from existing REP files.
This script will:
1. Truncate the 4 tables
2. Re-import from all completed files in eclaim_imported_files
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config.database import get_db_config
from utils.eclaim.importer_sheets import AdditionalSheetsImporter


def get_db_connection():
    """Get database connection using config"""
    db_config = get_db_config()
    return psycopg2.connect(**db_config)

DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'downloads')


def main():
    print("=" * 60)
    print("Re-import Additional Sheets (deny, drug, instrument, zero_paid)")
    print("=" * 60)

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Step 1: Get list of completed files
        print("\n[1/3] Getting list of completed files...")
        cursor.execute("""
            SELECT id, filename
            FROM eclaim_imported_files
            WHERE status = 'completed'
            ORDER BY import_completed_at
        """)
        files = cursor.fetchall()
        print(f"Found {len(files)} completed files")

        if not files:
            print("No completed files found. Nothing to re-import.")
            return

        # Step 2: Truncate tables
        print("\n[2/3] Truncating tables...")
        tables = ['eclaim_deny', 'eclaim_drug', 'eclaim_instrument', 'eclaim_zero_paid']
        for table in tables:
            try:
                cursor.execute(f"TRUNCATE TABLE {table} CASCADE")
                print(f"  ✓ Truncated {table}")
            except Exception as e:
                # Table might not exist
                print(f"  - Skipped {table}: {e}")
                conn.rollback()
        conn.commit()

        # Step 3: Re-import additional sheets
        print("\n[3/3] Re-importing additional sheets...")

        importer = AdditionalSheetsImporter(conn, cursor)

        total_results = {
            'drug': 0,
            'instrument': 0,
            'deny': 0,
            'zero_paid': 0,
            'files_processed': 0,
            'files_skipped': 0
        }

        for file_id, filename in files:
            filepath = os.path.join(DOWNLOADS_DIR, filename)

            if not os.path.exists(filepath):
                print(f"  - Skipped {filename} (file not found)")
                total_results['files_skipped'] += 1
                continue

            # Only process IP files (they have additional sheets)
            if '_IP_' not in filename.upper():
                continue

            print(f"  Processing: {filename}")

            try:
                results = importer.import_additional_sheets(file_id, filepath)

                for key in ['drug', 'instrument', 'deny', 'zero_paid']:
                    if key in results:
                        total_results[key] += results[key]

                total_results['files_processed'] += 1
                conn.commit()

                # Show per-file results
                parts = []
                if results.get('drug', 0) > 0:
                    parts.append(f"drug:{results['drug']}")
                if results.get('instrument', 0) > 0:
                    parts.append(f"inst:{results['instrument']}")
                if results.get('deny', 0) > 0:
                    parts.append(f"deny:{results['deny']}")
                if results.get('zero_paid', 0) > 0:
                    parts.append(f"zero:{results['zero_paid']}")

                if parts:
                    print(f"    → {', '.join(parts)}")

            except Exception as e:
                print(f"    ✗ Error: {e}")
                conn.rollback()

        # Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Files processed: {total_results['files_processed']}")
        print(f"Files skipped:   {total_results['files_skipped']}")
        print(f"")
        print(f"Records imported:")
        print(f"  - eclaim_drug:       {total_results['drug']:,}")
        print(f"  - eclaim_instrument: {total_results['instrument']:,}")
        print(f"  - eclaim_deny:       {total_results['deny']:,}")
        print(f"  - eclaim_zero_paid:  {total_results['zero_paid']:,}")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == '__main__':
    main()
