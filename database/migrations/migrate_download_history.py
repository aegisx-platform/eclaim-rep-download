#!/usr/bin/env python3
"""
Migration Script: Move download history from JSON files to database

This script:
1. Creates the download_history table
2. Migrates data from JSON files to the database
3. Validates the migration
4. Optionally backs up and removes old JSON files

Usage:
    python database/migrations/migrate_download_history.py
    python database/migrations/migrate_download_history.py --dry-run
    python database/migrations/migrate_download_history.py --cleanup
"""

import os
import sys
import json
import argparse
import hashlib
from pathlib import Path
from datetime import datetime
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.database import get_db_config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database driver imports
try:
    import psycopg2
    from psycopg2.extras import execute_batch
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class DownloadHistoryMigration:
    """Migrate download history from JSON to database"""

    def __init__(self, db_config: dict, db_type: str = None):
        self.db_config = db_config
        from config.database import DB_TYPE
        self.db_type = db_type or DB_TYPE
        self.conn = None
        self.cursor = None
        self.project_root = Path(__file__).parent.parent.parent

    def connect(self):
        """Establish database connection"""
        if self.db_type == 'postgresql':
            self.conn = psycopg2.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        elif self.db_type == 'mysql':
            self.conn = pymysql.connect(**self.db_config)
            self.cursor = self.conn.cursor()
        logger.info(f"Connected to {self.db_type} database")

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")

    def create_table(self):
        """Create download_history table"""
        logger.info("Creating download_history table...")

        if self.db_type == 'postgresql':
            migration_file = self.project_root / 'database/migrations/001_create_download_history.sql'
        else:
            migration_file = self.project_root / 'database/migrations/001_create_download_history_mysql.sql'

        with open(migration_file, 'r') as f:
            sql = f.read()

        # Execute each statement separately
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

        for stmt in statements:
            if stmt:
                try:
                    self.cursor.execute(stmt)
                except Exception as e:
                    # Ignore errors for DROP IF EXISTS and CREATE OR REPLACE
                    if 'does not exist' not in str(e) and 'already exists' not in str(e):
                        logger.warning(f"Statement warning: {e}")

        self.conn.commit()
        logger.info("Table created successfully")

    def load_json_history(self, filepath: Path) -> dict:
        """Load JSON history file"""
        if not filepath.exists():
            return {'downloads': []}

        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_file_hash(self, filepath: Path) -> str:
        """Calculate SHA256 hash of file"""
        if not filepath.exists():
            return None

        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def migrate_rep_history(self, dry_run: bool = False) -> int:
        """Migrate REP download history"""
        json_file = self.project_root / 'download_history.json'
        data = self.load_json_history(json_file)
        downloads = data.get('downloads', [])

        if not downloads:
            logger.info("No REP download history to migrate")
            return 0

        logger.info(f"Migrating {len(downloads)} REP download records...")

        records = []
        for d in downloads:
            filename = d.get('filename', '')
            filepath = self.project_root / 'downloads' / 'rep' / filename
            file_exists = filepath.exists()

            records.append({
                'download_type': 'rep',
                'filename': filename,
                'document_no': d.get('rep_no'),
                'scheme': d.get('scheme'),
                'fiscal_year': d.get('year'),
                'service_month': d.get('month'),
                'patient_type': d.get('patient_type'),
                'rep_no': d.get('rep_no'),
                'file_size': d.get('size'),
                'file_path': str(filepath) if file_exists else None,
                'file_hash': self.get_file_hash(filepath) if file_exists else None,
                'downloaded_at': d.get('downloaded_at'),
                'file_exists': file_exists,
                'imported': d.get('imported', False),
                'download_params': json.dumps(d.get('download_params', {})),
            })

        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(records)} REP records")
            return len(records)

        self._insert_records(records)
        return len(records)

    def migrate_stm_history(self, dry_run: bool = False) -> int:
        """Migrate STM (Statement) download history"""
        json_file = self.project_root / 'stm_download_history.json'
        data = self.load_json_history(json_file)
        downloads = data.get('downloads', [])

        if not downloads:
            logger.info("No STM download history to migrate")
            return 0

        logger.info(f"Migrating {len(downloads)} STM download records...")

        records = []
        for d in downloads:
            filename = d.get('filename', '')
            filepath = self.project_root / 'downloads' / 'stm' / filename
            file_exists = filepath.exists()

            # Parse document_no to get patient_type
            doc_no = d.get('document_no', '')
            patient_type = None
            if 'IP' in doc_no:
                patient_type = 'ip'
            elif 'OP' in doc_no:
                patient_type = 'op'

            records.append({
                'download_type': 'stm',
                'filename': filename,
                'document_no': doc_no,
                'scheme': d.get('scheme'),
                'fiscal_year': d.get('year'),
                'service_month': d.get('month'),
                'patient_type': patient_type,
                'rep_no': None,
                'file_size': d.get('size'),
                'file_path': str(filepath) if file_exists else None,
                'file_hash': self.get_file_hash(filepath) if file_exists else None,
                'downloaded_at': d.get('downloaded_at'),
                'file_exists': file_exists,
                'imported': False,  # Will be updated by checking stm_imported_files
                'download_params': json.dumps({
                    'stmt_type': d.get('stmt_type'),
                    'service_month': d.get('service_month'),
                }),
            })

        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(records)} STM records")
            return len(records)

        self._insert_records(records)

        # Update imported status by checking stm_imported_files
        self._update_stm_import_status()

        return len(records)

    def migrate_smt_history(self, dry_run: bool = False) -> int:
        """Migrate SMT (Smart Money Transfer) download history"""
        json_file = self.project_root / 'smt_download_history.json'
        data = self.load_json_history(json_file)
        downloads = data.get('downloads', [])

        if not downloads:
            logger.info("No SMT download history to migrate")
            return 0

        logger.info(f"Migrating {len(downloads)} SMT download records...")

        records = []
        for d in downloads:
            filename = d.get('filename', '')
            filepath = self.project_root / 'downloads' / 'smt' / filename
            file_exists = filepath.exists()

            records.append({
                'download_type': 'smt',
                'filename': filename,
                'document_no': d.get('vendor_id'),
                'scheme': None,
                'fiscal_year': d.get('fiscal_year'),
                'service_month': None,
                'patient_type': None,
                'rep_no': None,
                'file_size': d.get('size'),
                'file_path': str(filepath) if file_exists else None,
                'file_hash': self.get_file_hash(filepath) if file_exists else None,
                'downloaded_at': d.get('downloaded_at'),
                'file_exists': file_exists,
                'imported': d.get('imported', False),
                'download_params': json.dumps({
                    'vendor_id': d.get('vendor_id'),
                    'start_date': d.get('start_date'),
                    'end_date': d.get('end_date'),
                }),
            })

        if dry_run:
            logger.info(f"[DRY RUN] Would insert {len(records)} SMT records")
            return len(records)

        self._insert_records(records)
        return len(records)

    def _insert_records(self, records: list):
        """Insert records into download_history table"""
        if not records:
            return

        if self.db_type == 'postgresql':
            query = """
                INSERT INTO download_history
                (download_type, filename, document_no, scheme, fiscal_year,
                 service_month, patient_type, rep_no, file_size, file_path,
                 file_hash, downloaded_at, file_exists, imported, download_params)
                VALUES
                (%(download_type)s, %(filename)s, %(document_no)s, %(scheme)s, %(fiscal_year)s,
                 %(service_month)s, %(patient_type)s, %(rep_no)s, %(file_size)s, %(file_path)s,
                 %(file_hash)s, %(downloaded_at)s, %(file_exists)s, %(imported)s, %(download_params)s)
                ON CONFLICT (download_type, filename) DO UPDATE SET
                    file_exists = EXCLUDED.file_exists,
                    file_size = EXCLUDED.file_size,
                    file_hash = EXCLUDED.file_hash,
                    updated_at = CURRENT_TIMESTAMP
            """
            execute_batch(self.cursor, query, records, page_size=100)
        else:
            query = """
                INSERT INTO download_history
                (download_type, filename, document_no, scheme, fiscal_year,
                 service_month, patient_type, rep_no, file_size, file_path,
                 file_hash, downloaded_at, file_exists, imported, download_params)
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    file_exists = VALUES(file_exists),
                    file_size = VALUES(file_size),
                    file_hash = VALUES(file_hash),
                    updated_at = CURRENT_TIMESTAMP
            """
            for r in records:
                self.cursor.execute(query, (
                    r['download_type'], r['filename'], r['document_no'], r['scheme'],
                    r['fiscal_year'], r['service_month'], r['patient_type'], r['rep_no'],
                    r['file_size'], r['file_path'], r['file_hash'], r['downloaded_at'],
                    r['file_exists'], r['imported'], r['download_params']
                ))

        self.conn.commit()
        logger.info(f"Inserted/updated {len(records)} records")

    def _update_stm_import_status(self):
        """Update imported status for STM files by checking stm_imported_files"""
        query = """
            UPDATE download_history dh
            SET imported = TRUE,
                imported_at = sif.import_completed_at,
                import_file_id = sif.id,
                import_table = 'stm_imported_files'
            FROM stm_imported_files sif
            WHERE dh.download_type = 'stm'
              AND dh.filename = sif.filename
              AND sif.status = 'completed'
        """ if self.db_type == 'postgresql' else """
            UPDATE download_history dh
            JOIN stm_imported_files sif ON dh.filename = sif.filename
            SET dh.imported = TRUE,
                dh.imported_at = sif.import_completed_at,
                dh.import_file_id = sif.id,
                dh.import_table = 'stm_imported_files'
            WHERE dh.download_type = 'stm'
              AND sif.status = 'completed'
        """

        self.cursor.execute(query)
        self.conn.commit()
        logger.info(f"Updated STM import status: {self.cursor.rowcount} records")

    def validate_migration(self) -> dict:
        """Validate migration by comparing JSON counts with DB counts"""
        results = {
            'rep': {'json': 0, 'db': 0, 'match': False},
            'stm': {'json': 0, 'db': 0, 'match': False},
            'smt': {'json': 0, 'db': 0, 'match': False},
        }

        # Count JSON records
        for dtype, filename in [
            ('rep', 'download_history.json'),
            ('stm', 'stm_download_history.json'),
            ('smt', 'smt_download_history.json'),
        ]:
            json_file = self.project_root / filename
            if json_file.exists():
                data = self.load_json_history(json_file)
                results[dtype]['json'] = len(data.get('downloads', []))

        # Count DB records
        for dtype in ['rep', 'stm', 'smt']:
            self.cursor.execute(
                "SELECT COUNT(*) FROM download_history WHERE download_type = %s",
                (dtype,)
            )
            results[dtype]['db'] = self.cursor.fetchone()[0]
            results[dtype]['match'] = results[dtype]['json'] == results[dtype]['db']

        return results

    def backup_json_files(self):
        """Backup JSON files before removal"""
        backup_dir = self.project_root / 'backup' / 'download_history'
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        for filename in ['download_history.json', 'stm_download_history.json', 'smt_download_history.json']:
            src = self.project_root / filename
            if src.exists():
                dst = backup_dir / f"{filename}.{timestamp}.bak"
                src.rename(dst)
                logger.info(f"Backed up {filename} to {dst}")

    def run(self, dry_run: bool = False, cleanup: bool = False):
        """Run the full migration"""
        logger.info("=" * 60)
        logger.info("Download History Migration")
        logger.info("=" * 60)

        if dry_run:
            logger.info("[DRY RUN MODE] No changes will be made")

        try:
            self.connect()

            # Step 1: Create table
            if not dry_run:
                self.create_table()

            # Step 2: Migrate each type
            rep_count = self.migrate_rep_history(dry_run)
            stm_count = self.migrate_stm_history(dry_run)
            smt_count = self.migrate_smt_history(dry_run)

            total = rep_count + stm_count + smt_count
            logger.info(f"\nMigration Summary:")
            logger.info(f"  REP records: {rep_count}")
            logger.info(f"  STM records: {stm_count}")
            logger.info(f"  SMT records: {smt_count}")
            logger.info(f"  Total: {total}")

            # Step 3: Validate
            if not dry_run:
                validation = self.validate_migration()
                logger.info("\nValidation Results:")
                all_match = True
                for dtype, result in validation.items():
                    status = "✓" if result['match'] else "✗"
                    logger.info(f"  {dtype.upper()}: JSON={result['json']}, DB={result['db']} {status}")
                    if not result['match']:
                        all_match = False

                if all_match:
                    logger.info("\n✓ Migration validated successfully!")
                else:
                    logger.warning("\n⚠ Migration validation found mismatches")

            # Step 4: Cleanup (optional)
            if cleanup and not dry_run:
                logger.info("\nBacking up and removing JSON files...")
                self.backup_json_files()
                logger.info("Cleanup completed")

        finally:
            self.disconnect()

        logger.info("\n" + "=" * 60)
        logger.info("Migration completed!")
        logger.info("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='Migrate download history from JSON to database')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--cleanup', action='store_true', help='Backup and remove JSON files after migration')
    args = parser.parse_args()

    db_config = get_db_config()
    migration = DownloadHistoryMigration(db_config)
    migration.run(dry_run=args.dry_run, cleanup=args.cleanup)


if __name__ == '__main__':
    main()
