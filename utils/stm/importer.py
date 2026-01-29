#!/usr/bin/env python3
"""
STM (Statement) Database Importer
Import NHSO Statement data into database for reconciliation with REP data
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


class STMImporter:
    """
    Import STM (Statement) data into database

    Tables:
    - stm_imported_files: Track imported files
    - stm_receivable_summary: Summary from รายงานพึงรับ
    - stm_rep_summary: Summary by REP from รายงานสรุป
    - stm_claim_item: Detail records from รายละเอียด
    """

    def __init__(self, db_config: Dict, db_type: str = None):
        """
        Initialize importer

        Args:
            db_config: Database configuration dict
            db_type: Database type ('postgresql' or 'mysql')
        """
        self.db_config = db_config
        from config.database import DB_TYPE
        self.db_type = db_type or DB_TYPE
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

    def create_import_record(self, metadata: Dict, header_info: Dict = None) -> int:
        """
        Create or update record in stm_imported_files table

        Args:
            metadata: File metadata from parser
            header_info: Header info from parsed file

        Returns:
            file_id of created/updated record
        """
        header_info = header_info or {}

        if self.db_type == 'postgresql':
            query = """
                INSERT INTO stm_imported_files
                (filename, file_type, scheme, hospital_code, hospital_name,
                 province_code, province_name, document_no, statement_month,
                 statement_year, report_date, status, import_started_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (filename) DO UPDATE SET
                    status = 'processing',
                    import_started_at = NOW(),
                    import_completed_at = NULL,
                    error_message = NULL,
                    updated_at = NOW()
                RETURNING id
            """
        elif self.db_type == 'mysql':
            query = """
                INSERT INTO stm_imported_files
                (filename, file_type, scheme, hospital_code, hospital_name,
                 province_code, province_name, document_no, statement_month,
                 statement_year, report_date, status, import_started_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    status = 'processing',
                    import_started_at = NOW(),
                    import_completed_at = NULL,
                    error_message = NULL,
                    updated_at = NOW()
            """

        values = (
            metadata.get('filename'),
            metadata.get('file_type'),
            metadata.get('scheme'),
            header_info.get('hospital_code') or metadata.get('hospital_code'),
            header_info.get('hospital_name'),
            header_info.get('province_code'),
            header_info.get('province_name'),
            header_info.get('document_no'),
            metadata.get('statement_month'),
            metadata.get('statement_year'),
            header_info.get('report_date'),
            'processing'
        )

        try:
            self.cursor.execute(query, values)

            if self.db_type == 'postgresql':
                file_id = self.cursor.fetchone()[0]
            elif self.db_type == 'mysql':
                file_id = self.cursor.lastrowid
                if file_id == 0:
                    self.cursor.execute(
                        "SELECT id FROM stm_imported_files WHERE filename = %s",
                        (metadata.get('filename'),)
                    )
                    file_id = self.cursor.fetchone()[0]

            self.conn.commit()
            logger.info(f"Created/updated STM import record: file_id={file_id}")
            return file_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to create STM import record: {e}")
            raise

    def update_import_status(self, file_id: int, status: str,
                           total_records: int = 0,
                           imported_records: int = 0,
                           failed_records: int = 0,
                           error_message: str = None):
        """Update import status"""
        query = """
            UPDATE stm_imported_files
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
            logger.info(f"Updated STM import status: file_id={file_id}, status={status}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to update import status: {e}")
            raise

    def import_receivable_summary(self, file_id: int, summaries: List[Dict]) -> int:
        """
        Import receivable summary records

        Args:
            file_id: File ID
            summaries: List of summary records from parser

        Returns:
            Number of imported records
        """
        if not summaries:
            return 0

        columns = [
            'file_id', 'data_type', 'patient_type', 'rep_count', 'patient_count',
            'total_adjrw', 'total_paid', 'salary_deduction', 'adjrw_paid_deduction',
            'net_receivable'
        ]

        placeholders = ', '.join(['%s'] * len(columns))
        column_str = ', '.join(columns)

        query = f"""
            INSERT INTO stm_receivable_summary ({column_str})
            VALUES ({placeholders})
        """

        records = []
        for s in summaries:
            # Calculate net receivable (total_paid - salary_deduction - adjrw_paid_deduction)
            net = (s.get('total_paid', 0) or 0) - (s.get('salary_deduction', 0) or 0) - (s.get('adjrw_paid_deduction', 0) or 0)

            records.append((
                file_id,
                s.get('data_type', 'normal'),
                s.get('patient_type'),
                s.get('rep_count', 0),
                s.get('patient_count', 0),
                s.get('total_adjrw', 0),
                s.get('total_paid', 0),
                s.get('salary_deduction', 0),
                s.get('adjrw_paid_deduction', 0),
                net
            ))

        try:
            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, records, page_size=100)
            else:
                self.cursor.executemany(query, records)

            self.conn.commit()
            logger.info(f"Imported {len(records)} receivable summary records")
            return len(records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import receivable summary: {e}")
            raise

    def import_rep_summary(self, file_id: int, summaries: List[Dict]) -> int:
        """
        Import REP summary records

        Args:
            file_id: File ID
            summaries: List of REP summary records from parser

        Returns:
            Number of imported records
        """
        if not summaries:
            return 0

        columns = [
            'file_id', 'data_type', 'period', 'hcode', 'rep_no', 'claim_type',
            'total_passed', 'amount_claimed', 'prb_amount',
            'receivable_op', 'receivable_ip_calc', 'receivable_ip_paid',
            'hc_amount', 'hc_drug', 'ae_amount', 'ae_drug', 'inst_amount',
            'dmis_calc', 'dmis_paid', 'dmis_drug', 'palliative_care',
            'dmishd_amount', 'pp_amount', 'fs_amount', 'opbkk_amount',
            'total_receivable', 'covid_amount', 'data_source'
        ]

        placeholders = ', '.join(['%s'] * len(columns))
        column_str = ', '.join(columns)

        if self.db_type == 'mysql':
            update_clause = ', '.join([f"{col} = VALUES({col})" for col in columns if col not in ['file_id', 'rep_no', 'data_type']])
            query = f"""
                INSERT INTO stm_rep_summary ({column_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_clause}
            """
        else:
            update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['file_id', 'rep_no', 'data_type']])
            query = f"""
                INSERT INTO stm_rep_summary ({column_str})
                VALUES ({placeholders})
                ON CONFLICT (file_id, rep_no, data_type) DO UPDATE SET {update_clause}
            """

        records = []
        for s in summaries:
            records.append((
                file_id,
                s.get('data_type', 'normal'),
                s.get('period'),
                s.get('hcode'),
                s.get('rep_no'),
                s.get('claim_type'),
                s.get('total_passed', 0),
                s.get('amount_claimed', 0),
                s.get('prb_amount', 0),
                s.get('receivable_op', 0),
                s.get('receivable_ip_calc', 0),
                s.get('receivable_ip_paid', 0),
                s.get('hc_amount', 0),
                s.get('hc_drug', 0),
                s.get('ae_amount', 0),
                s.get('ae_drug', 0),
                s.get('inst_amount', 0),
                s.get('dmis_calc', 0),
                s.get('dmis_paid', 0),
                s.get('dmis_drug', 0),
                s.get('palliative_care', 0),
                s.get('dmishd_amount', 0),
                s.get('pp_amount', 0),
                s.get('fs_amount', 0),
                s.get('opbkk_amount', 0),
                s.get('total_receivable', 0),
                s.get('covid_amount', 0),
                s.get('data_source')
            ))

        try:
            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, records, page_size=100)
            else:
                self.cursor.executemany(query, records)

            self.conn.commit()
            logger.info(f"Imported {len(records)} REP summary records")
            return len(records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import REP summary: {e}")
            raise

    def import_claim_items(self, file_id: int, claims: List[Dict]) -> int:
        """
        Import claim detail records

        Args:
            file_id: File ID
            claims: List of claim records from parser

        Returns:
            Number of imported records
        """
        if not claims:
            return 0

        columns = [
            'file_id', 'row_number', 'data_type', 'rep_no', 'seq', 'tran_id',
            'hn', 'an', 'pid', 'patient_name', 'date_admit', 'date_discharge',
            'main_inscl', 'proj_code', 'amount_claimed', 'fund_ip_prb',
            'adjrw', 'late_penalty', 'ccuf', 'adjrw2', 'payment_rate',
            'salary_deduction', 'paid_after_deduction',
            'receivable_op', 'receivable_ip_calc', 'receivable_ip_paid',
            'hc_amount', 'hc_drug', 'ae_amount', 'ae_drug', 'inst_amount',
            'dmis_calc', 'dmis_paid', 'dmis_drug', 'palliative_care',
            'dmishd_amount', 'pp_amount', 'fs_amount', 'opbkk_amount',
            'total_compensation', 'va_amount', 'covid_amount',
            'data_source', 'seq_no'
        ]

        placeholders = ', '.join(['%s'] * len(columns))

        # Quote column names for MySQL (row_number is a reserved keyword in MySQL 8.0)
        if self.db_type == 'mysql':
            column_str = ', '.join([f'`{col}`' for col in columns])
            update_clause = ', '.join([f"`{col}` = VALUES(`{col}`)" for col in columns if col not in ['file_id', 'tran_id']])
            query = f"""
                INSERT INTO stm_claim_item ({column_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_clause}
            """
        else:
            column_str = ', '.join(columns)
            update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['file_id', 'tran_id']])
            query = f"""
                INSERT INTO stm_claim_item ({column_str})
                VALUES ({placeholders})
                ON CONFLICT (file_id, tran_id) DO UPDATE SET {update_clause}
            """

        records = []
        for c in claims:
            records.append((
                file_id,
                c.get('row_number'),
                c.get('data_type', 'normal'),
                c.get('rep_no'),
                c.get('seq'),
                c.get('tran_id'),
                c.get('hn'),
                c.get('an'),
                c.get('pid'),
                c.get('patient_name'),
                c.get('date_admit'),
                c.get('date_discharge'),
                c.get('main_inscl'),
                c.get('proj_code'),
                c.get('amount_claimed', 0),
                c.get('fund_ip_prb', 0),
                c.get('adjrw', 0),
                c.get('late_penalty', 0),
                c.get('ccuf', 0),
                c.get('adjrw2', 0),
                c.get('payment_rate', 0),
                c.get('salary_deduction', 0),
                c.get('paid_after_deduction', 0),
                c.get('receivable_op', 0),
                c.get('receivable_ip_calc', 0),
                c.get('receivable_ip_paid', 0),
                c.get('hc_amount', 0),
                c.get('hc_drug', 0),
                c.get('ae_amount', 0),
                c.get('ae_drug', 0),
                c.get('inst_amount', 0),
                c.get('dmis_calc', 0),
                c.get('dmis_paid', 0),
                c.get('dmis_drug', 0),
                c.get('palliative_care', 0),
                c.get('dmishd_amount', 0),
                c.get('pp_amount', 0),
                c.get('fs_amount', 0),
                c.get('opbkk_amount', 0),
                c.get('total_compensation', 0),
                c.get('va_amount', 0),
                c.get('covid_amount', 0),
                c.get('data_source'),
                c.get('seq_no')
            ))

        try:
            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, records, page_size=100)
            else:
                self.cursor.executemany(query, records)

            self.conn.commit()
            logger.info(f"Imported {len(records)} claim item records")
            return len(records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import claim items: {e}")
            raise

    def import_file(self, filepath: str) -> Dict:
        """
        Import complete STM file

        Args:
            filepath: Path to STM Excel file

        Returns:
            Dict with import results
        """
        from .parser import STMParser

        parser = STMParser(filepath)
        parsed = parser.parse_all()

        total_records = 0
        imported_records = 0
        failed_records = 0
        error_message = None

        try:
            # Create import record
            file_id = self.create_import_record(
                parsed['metadata'],
                parsed.get('header_info', {})
            )

            # Import receivable summary
            recv_count = self.import_receivable_summary(
                file_id,
                parsed['receivable_summary']
            )
            imported_records += recv_count

            # Import REP summary
            rep_count = self.import_rep_summary(
                file_id,
                parsed['rep_summary']
            )
            imported_records += rep_count

            # Combine all claims
            all_claims = (
                parsed['claims_normal'] +
                parsed['claims_appeal'] +
                parsed['claims_disabled_d1']
            )
            total_records = len(all_claims)

            # Import claim items
            claim_count = self.import_claim_items(file_id, all_claims)
            imported_records += claim_count

            # Update status
            status = 'completed'
            self.update_import_status(
                file_id,
                status,
                total_records=total_records,
                imported_records=imported_records,
                failed_records=failed_records
            )

            return {
                'success': True,
                'file_id': file_id,
                'filename': parsed['metadata']['filename'],
                'file_type': parsed['metadata']['file_type'],
                'scheme': parsed['metadata']['scheme'],
                'total_records': total_records,
                'imported_records': imported_records,
                'failed_records': failed_records,
                'summary_records': recv_count,
                'rep_summary_records': rep_count,
                'claim_records': claim_count
            }

        except Exception as e:
            logger.error(f"Failed to import STM file {filepath}: {e}")
            if 'file_id' in locals():
                self.update_import_status(
                    file_id,
                    'failed',
                    total_records=total_records,
                    imported_records=imported_records,
                    failed_records=total_records - imported_records,
                    error_message=str(e)
                )

            return {
                'success': False,
                'filename': os.path.basename(filepath),
                'error': str(e)
            }

    def run_reconciliation(self, file_id: int = None) -> Dict:
        """
        Run reconciliation between STM and REP data

        Args:
            file_id: Optional file_id to reconcile specific file (None = all)

        Returns:
            Dict with reconciliation results
        """
        # Build WHERE clause
        where = "WHERE s.file_id = %s" if file_id else ""
        params = (file_id,) if file_id else ()

        # Update reconciliation status
        if self.db_type == 'postgresql':
            query = f"""
                UPDATE stm_claim_item s
                SET
                    rep_matched = (r.id IS NOT NULL),
                    rep_tran_id = r.id,
                    reconcile_status = CASE
                        WHEN r.id IS NULL THEN 'missing_rep'
                        WHEN ABS(COALESCE(s.total_compensation, 0) - COALESCE(r.paid, 0)) < 1 THEN 'matched'
                        ELSE 'amount_diff'
                    END,
                    reconcile_diff = COALESCE(s.total_compensation, 0) - COALESCE(r.paid, 0),
                    reconcile_date = NOW(),
                    updated_at = NOW()
                FROM (
                    SELECT s2.id as stm_id, r2.id, r2.paid
                    FROM stm_claim_item s2
                    LEFT JOIN claim_rep_opip_nhso_item r2 ON s2.tran_id = r2.tran_id
                    {where.replace('s.file_id', 's2.file_id') if where else ''}
                ) AS subq
                LEFT JOIN claim_rep_opip_nhso_item r ON subq.id = r.id
                WHERE s.id = subq.stm_id
            """
        else:
            # MySQL version with JOIN UPDATE
            query = f"""
                UPDATE stm_claim_item s
                LEFT JOIN claim_rep_opip_nhso_item r ON s.tran_id = r.tran_id
                SET
                    s.rep_matched = (r.id IS NOT NULL),
                    s.rep_tran_id = r.id,
                    s.reconcile_status = CASE
                        WHEN r.id IS NULL THEN 'missing_rep'
                        WHEN ABS(COALESCE(s.total_compensation, 0) - COALESCE(r.paid, 0)) < 1 THEN 'matched'
                        ELSE 'amount_diff'
                    END,
                    s.reconcile_diff = COALESCE(s.total_compensation, 0) - COALESCE(r.paid, 0),
                    s.reconcile_date = NOW(),
                    s.updated_at = NOW()
                {where}
            """

        try:
            self.cursor.execute(query, params)
            affected = self.cursor.rowcount
            self.conn.commit()

            # Get statistics
            stats_query = """
                SELECT
                    reconcile_status,
                    COUNT(*) as count,
                    SUM(ABS(reconcile_diff)) as total_diff
                FROM stm_claim_item
                WHERE reconcile_status IS NOT NULL
                GROUP BY reconcile_status
            """
            if file_id:
                stats_query = stats_query.replace(
                    'WHERE reconcile_status IS NOT NULL',
                    f'WHERE reconcile_status IS NOT NULL AND file_id = {file_id}'
                )

            self.cursor.execute(stats_query)
            stats = {row[0]: {'count': row[1], 'total_diff': float(row[2] or 0)}
                    for row in self.cursor.fetchall()}

            logger.info(f"Reconciliation completed: {affected} records updated")
            return {
                'success': True,
                'records_updated': affected,
                'statistics': stats
            }

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Reconciliation failed: {e}")
            return {
                'success': False,
                'error': str(e)
            }


def import_stm_file(filepath: str, db_config: Dict = None, db_type: str = None) -> Dict:
    """
    Convenience function to import a single STM file

    Args:
        filepath: Path to STM Excel file
        db_config: Optional database config (uses config.database if not provided)
        db_type: Optional database type

    Returns:
        Dict with import results
    """
    if db_config is None:
        from config.database import get_db_config
        db_config = get_db_config()

    importer = STMImporter(db_config, db_type)

    try:
        importer.connect()
        result = importer.import_file(filepath)
        return result
    finally:
        importer.disconnect()
