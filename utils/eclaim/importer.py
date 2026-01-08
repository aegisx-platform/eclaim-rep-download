#!/usr/bin/env python3
"""
E-Claim Database Importer
Import parsed E-Claim data into PostgreSQL/MySQL database
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Import database drivers
try:
    import psycopg2
    from psycopg2.extras import execute_batch as pg_execute_batch
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    logger.warning("psycopg2 not available - PostgreSQL support disabled")

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.warning("pymysql not available - MySQL support disabled")


class EClaimImporter:
    """Import E-Claim data into database (PostgreSQL or MySQL)"""

    def __init__(self, db_config: Dict, db_type: str = None):
        """
        Initialize importer

        Args:
            db_config: Database configuration dict
            db_type: Database type ('postgresql' or 'mysql')
        """
        self.db_config = db_config
        self.db_type = db_type or os.getenv('DB_TYPE', 'postgresql')
        self.conn = None
        self.cursor = None

        # Validate database type and driver availability
        if self.db_type == 'postgresql' and not POSTGRESQL_AVAILABLE:
            raise ImportError("psycopg2 not installed. Install with: pip install psycopg2-binary")
        elif self.db_type == 'mysql' and not MYSQL_AVAILABLE:
            raise ImportError("pymysql not installed. Install with: pip install pymysql")
        elif self.db_type not in ['postgresql', 'mysql']:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def connect(self):
        """Establish database connection"""
        try:
            if self.db_type == 'postgresql':
                self.conn = psycopg2.connect(**self.db_config)
                self.cursor = self.conn.cursor()
            elif self.db_type == 'mysql':
                self.conn = pymysql.connect(**self.db_config)
                self.cursor = self.conn.cursor()

            logger.info(f"Database connection established ({self.db_type})")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def disconnect(self):
        """Close database connection"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info("Database connection closed")

    def _get_last_insert_id(self) -> int:
        """Get last inserted ID (database-agnostic)"""
        if self.db_type == 'postgresql':
            # PostgreSQL uses RETURNING clause
            return self.cursor.fetchone()[0]
        elif self.db_type == 'mysql':
            # MySQL uses lastrowid
            return self.cursor.lastrowid

    def create_import_record(self, metadata: Dict) -> int:
        """
        Create record in eclaim_imported_files table

        Args:
            metadata: File metadata dict

        Returns:
            file_id of created record
        """
        if self.db_type == 'postgresql':
            query = """
                INSERT INTO eclaim_imported_files
                (filename, file_type, hospital_code, file_date, status, file_created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
            """
        elif self.db_type == 'mysql':
            query = """
                INSERT INTO eclaim_imported_files
                (filename, file_type, hospital_code, file_date, status, file_created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

        values = (
            metadata['filename'],
            metadata['file_type'],
            metadata.get('hospital_code'),
            metadata.get('file_date'),
            'processing',
            datetime.now()
        )

        try:
            self.cursor.execute(query, values)
            file_id = self._get_last_insert_id()
            self.conn.commit()
            logger.info(f"Created import record: file_id={file_id}")
            return file_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to create import record: {e}")
            raise

    def update_import_status(self, file_id: int, status: str,
                           total_records: int = 0,
                           imported_records: int = 0,
                           failed_records: int = 0,
                           error_message: str = None):
        """
        Update import status

        Args:
            file_id: File ID
            status: Import status (processing/completed/failed)
            total_records: Total records in file
            imported_records: Successfully imported records
            failed_records: Failed records
            error_message: Error message if failed
        """
        if self.db_type == 'postgresql':
            query = """
                UPDATE eclaim_imported_files
                SET status = %s,
                    total_records = %s,
                    imported_records = %s,
                    failed_records = %s,
                    error_message = %s,
                    import_completed_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """
        elif self.db_type == 'mysql':
            query = """
                UPDATE eclaim_imported_files
                SET status = %s,
                    total_records = %s,
                    imported_records = %s,
                    failed_records = %s,
                    error_message = %s,
                    import_completed_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """

        completed_at = datetime.now() if status in ['completed', 'failed'] else None

        values = (
            status,
            total_records,
            imported_records,
            failed_records,
            error_message,
            completed_at,
            file_id
        )

        try:
            self.cursor.execute(query, values)
            self.conn.commit()
            logger.info(f"Updated import status: file_id={file_id}, status={status}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to update import status: {e}")
            raise

    def import_claims_batch(self, file_id: int, records: List[Dict]) -> int:
        """
        Import batch of records into eclaim_claims table

        Args:
            file_id: File ID from eclaim_imported_files
            records: List of claim records

        Returns:
            Number of successfully imported records
        """
        if self.db_type == 'postgresql':
            query = """
                INSERT INTO eclaim_claims
                (file_id, row_number, rep_no, tran_id, hn, an, pid,
                 patient_name, patient_type, admission_date, discharge_date,
                 net_reimbursement, error_code, chk, created_at)
                VALUES (%(file_id)s, %(row_number)s, %(rep_no)s, %(tran_id)s,
                       %(hn)s, %(an)s, %(pid)s, %(patient_name)s, %(patient_type)s,
                       %(admission_date)s, %(discharge_date)s, %(net_reimbursement)s,
                       %(error_code)s, %(chk)s, CURRENT_TIMESTAMP)
                ON CONFLICT (tran_id, file_id) DO UPDATE SET
                    net_reimbursement = EXCLUDED.net_reimbursement,
                    error_code = EXCLUDED.error_code,
                    updated_at = CURRENT_TIMESTAMP
            """
        elif self.db_type == 'mysql':
            query = """
                INSERT INTO eclaim_claims
                (file_id, row_number, rep_no, tran_id, hn, an, pid,
                 patient_name, patient_type, admission_date, discharge_date,
                 net_reimbursement, error_code, chk, created_at)
                VALUES (%(file_id)s, %(row_number)s, %(rep_no)s, %(tran_id)s,
                       %(hn)s, %(an)s, %(pid)s, %(patient_name)s, %(patient_type)s,
                       %(admission_date)s, %(discharge_date)s, %(net_reimbursement)s,
                       %(error_code)s, %(chk)s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    net_reimbursement = VALUES(net_reimbursement),
                    error_code = VALUES(error_code),
                    updated_at = CURRENT_TIMESTAMP
            """

        # Add file_id to each record
        for record in records:
            record['file_id'] = file_id

        try:
            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, records, page_size=100)
            elif self.db_type == 'mysql':
                # MySQL doesn't have execute_batch, use executemany
                self.cursor.executemany(query, records)

            self.conn.commit()
            logger.info(f"Imported {len(records)} records")
            return len(records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import batch: {e}")
            raise

    def import_op_refer_batch(self, file_id: int, records: List[Dict]) -> int:
        """
        Import batch of records into eclaim_op_refer table

        Args:
            file_id: File ID from eclaim_imported_files
            records: List of OP refer records

        Returns:
            Number of successfully imported records
        """
        if self.db_type == 'postgresql':
            query = """
                INSERT INTO eclaim_op_refer
                (file_id, row_number, rep, tran_id, hn, pid,
                 patient_name, service_date, refer_doc_no,
                 dx, proc_code, total_claimable, created_at)
                VALUES (%(file_id)s, %(row_number)s, %(rep)s, %(tran_id)s,
                       %(hn)s, %(pid)s, %(patient_name)s, %(service_date)s,
                       %(refer_doc_no)s, %(dx)s, %(proc_code)s,
                       %(total_claimable)s, CURRENT_TIMESTAMP)
                ON CONFLICT (tran_id, file_id) DO UPDATE SET
                    total_claimable = EXCLUDED.total_claimable,
                    updated_at = CURRENT_TIMESTAMP
            """
        elif self.db_type == 'mysql':
            query = """
                INSERT INTO eclaim_op_refer
                (file_id, row_number, rep, tran_id, hn, pid,
                 patient_name, service_date, refer_doc_no,
                 dx, proc_code, total_claimable, created_at)
                VALUES (%(file_id)s, %(row_number)s, %(rep)s, %(tran_id)s,
                       %(hn)s, %(pid)s, %(patient_name)s, %(service_date)s,
                       %(refer_doc_no)s, %(dx)s, %(proc_code)s,
                       %(total_claimable)s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    total_claimable = VALUES(total_claimable),
                    updated_at = CURRENT_TIMESTAMP
            """

        # Add file_id to each record
        for record in records:
            record['file_id'] = file_id

        try:
            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, records, page_size=100)
            elif self.db_type == 'mysql':
                self.cursor.executemany(query, records)

            self.conn.commit()
            logger.info(f"Imported {len(records)} OP refer records")
            return len(records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import OP refer batch: {e}")
            raise

    def import_file(self, metadata: Dict, records: List[Dict]) -> Dict:
        """
        Import complete file

        Args:
            metadata: File metadata
            records: List of data records

        Returns:
            Dict with import results
        """
        file_type = metadata['file_type']
        total_records = len(records)
        imported_records = 0
        failed_records = 0
        error_message = None

        try:
            # Create import record
            file_id = self.create_import_record(metadata)

            # Import data based on file type
            if file_type == 'ORF':
                imported_records = self.import_op_refer_batch(file_id, records)
            else:  # OP, IP, APPEAL
                imported_records = self.import_claims_batch(file_id, records)

            # Update status to completed
            self.update_import_status(
                file_id=file_id,
                status='completed',
                total_records=total_records,
                imported_records=imported_records,
                failed_records=failed_records
            )

            return {
                'success': True,
                'file_id': file_id,
                'total_records': total_records,
                'imported_records': imported_records,
                'failed_records': failed_records
            }

        except Exception as e:
            error_message = str(e)
            failed_records = total_records - imported_records

            # Update status to failed
            if 'file_id' in locals():
                self.update_import_status(
                    file_id=file_id,
                    status='failed',
                    total_records=total_records,
                    imported_records=imported_records,
                    failed_records=failed_records,
                    error_message=error_message
                )

            return {
                'success': False,
                'error': error_message,
                'total_records': total_records,
                'imported_records': imported_records,
                'failed_records': failed_records
            }

    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


def import_eclaim_file(filepath: str, db_config: Dict, db_type: str = None) -> Dict:
    """
    Convenience function to import E-Claim file

    Args:
        filepath: Path to XLS file
        db_config: Database configuration
        db_type: Database type ('postgresql' or 'mysql')

    Returns:
        Import result dict
    """
    from .parser import parse_eclaim_file

    # Parse file
    logger.info(f"Parsing file: {filepath}")
    metadata, records = parse_eclaim_file(filepath)

    # Import to database
    logger.info(f"Importing {len(records)} records to database")
    with EClaimImporter(db_config, db_type) as importer:
        result = importer.import_file(metadata, records)

    return result


if __name__ == '__main__':
    import sys
    from config.database import get_db_config, DB_TYPE

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python importer.py <path_to_xls_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    db_config = get_db_config()

    result = import_eclaim_file(filepath, db_config, DB_TYPE)

    print("\n=== Import Result ===")
    for key, value in result.items():
        print(f"{key}: {value}")
