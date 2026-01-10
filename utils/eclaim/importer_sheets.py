#!/usr/bin/env python3
"""
E-Claim Additional Sheets Importer
Import Summary, Drug, Instrument, Deny, and Zero Paid sheets
"""

import os
from datetime import datetime
from typing import Dict, List, Optional
import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Import database drivers
try:
    import psycopg2
    from psycopg2.extras import execute_batch as pg_execute_batch
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False


class AdditionalSheetsImporter:
    """
    Import additional sheets from E-Claim files:
    - Summary sheet
    - Data Drug sheet
    - Data Instrument sheet (IP only)
    - Data DENY sheet (IP only)
    - Data sheet 0 (zero paid items)
    """

    def __init__(self, conn, cursor, db_type: str = 'postgresql'):
        """
        Initialize with existing database connection

        Args:
            conn: Database connection
            cursor: Database cursor
            db_type: Database type ('postgresql' or 'mysql')
        """
        self.conn = conn
        self.cursor = cursor
        self.db_type = db_type

    def _parse_thai_date(self, value) -> Optional[datetime]:
        """Parse Thai date format to datetime"""
        if pd.isna(value) or value is None:
            return None
        if isinstance(value, datetime):
            return value
        if hasattr(value, 'to_pydatetime'):
            try:
                result = value.to_pydatetime()
                # Check for NaT
                if pd.isna(result):
                    return None
                return result
            except:
                return None
        if isinstance(value, str):
            value = value.strip()
            if not value or value == '-' or value.lower() == 'nat':
                return None
            try:
                # Try dd/mm/yyyy format
                result = pd.to_datetime(value, format='%d/%m/%Y', errors='coerce')
                if pd.isna(result):
                    return None
                return result
            except:
                return None
        return None

    def _safe_decimal(self, value, default=0):
        """Convert value to decimal safely"""
        if pd.isna(value) or value is None:
            return default
        if isinstance(value, str):
            value = value.strip().replace(',', '')
            if not value or value == '-':
                return default
        try:
            return float(value)
        except:
            return default

    def _safe_int(self, value, default=0):
        """Convert value to int safely"""
        if pd.isna(value) or value is None:
            return default
        try:
            return int(float(value))
        except:
            return default

    def _safe_string(self, value, max_length=None):
        """Convert value to string safely"""
        if pd.isna(value) or value is None:
            return None
        s = str(value).strip()
        if not s or s == '-' or s.lower() == 'nan':
            return None
        if max_length:
            s = s[:max_length]
        return s

    def import_summary(self, file_id: int, df: pd.DataFrame, file_type: str) -> int:
        """
        Import Summary sheet data

        Args:
            file_id: File ID
            df: DataFrame with Summary data (should have 1 data row after header)
            file_type: File type (OP, IP, ORF)

        Returns:
            Number of imported records
        """
        if df.empty:
            logger.warning("Summary DataFrame is empty")
            return 0

        # Summary sheet has multi-row header, data starts after
        # Column structure: งวด, HCODE, REP NO., then grouped fund columns

        try:
            # Get the data row (should be row 0 after proper header skip)
            row = df.iloc[0]

            # Map columns - Summary has complex structure
            # Columns are: งวด, HCODE, REP NO., then groups of (เรียกเก็บ, ชดเชย) for each fund
            record = {
                'file_id': file_id,
                'rep_period': self._safe_string(row.iloc[0] if len(row) > 0 else None, 20),
                'hcode': self._safe_string(row.iloc[1] if len(row) > 1 else None, 10),
                'rep_no': self._safe_string(row.iloc[2] if len(row) > 2 else None, 20),
                'file_type': file_type,
                # จำนวนราย
                'total_cases': self._safe_int(row.iloc[3] if len(row) > 3 else 0),
                'passed_cases': self._safe_int(row.iloc[4] if len(row) > 4 else 0),
                'failed_cases': self._safe_int(row.iloc[5] if len(row) > 5 else 0),
                # HC
                'hc_claim': self._safe_decimal(row.iloc[6] if len(row) > 6 else 0),
                'hc_reimb': self._safe_decimal(row.iloc[7] if len(row) > 7 else 0),
                # AE
                'ae_claim': self._safe_decimal(row.iloc[8] if len(row) > 8 else 0),
                'ae_reimb': self._safe_decimal(row.iloc[9] if len(row) > 9 else 0),
                # INST
                'inst_claim': self._safe_decimal(row.iloc[10] if len(row) > 10 else 0),
                'inst_reimb': self._safe_decimal(row.iloc[11] if len(row) > 11 else 0),
                # IP
                'ip_claim': self._safe_decimal(row.iloc[12] if len(row) > 12 else 0),
                'ip_reimb': self._safe_decimal(row.iloc[13] if len(row) > 13 else 0),
                # DMIS
                'dmis_claim': self._safe_decimal(row.iloc[14] if len(row) > 14 else 0),
                'dmis_reimb': self._safe_decimal(row.iloc[15] if len(row) > 15 else 0),
                # PP
                'pp_claim': self._safe_decimal(row.iloc[16] if len(row) > 16 else 0),
                'pp_reimb': self._safe_decimal(row.iloc[17] if len(row) > 17 else 0),
                # DRUG
                'drug_claim': self._safe_decimal(row.iloc[18] if len(row) > 18 else 0),
                'drug_reimb': self._safe_decimal(row.iloc[19] if len(row) > 19 else 0),
                # Totals
                'reimb_agency': self._safe_decimal(row.iloc[20] if len(row) > 20 else 0),
                'reimb_total': self._safe_decimal(row.iloc[21] if len(row) > 21 else 0),
            }

            columns = list(record.keys())
            placeholders = ', '.join(['%s'] * len(columns))
            column_str = ', '.join(columns)

            query = f"""
                INSERT INTO eclaim_summary ({column_str})
                VALUES ({placeholders})
            """

            values = [record[col] for col in columns]
            self.cursor.execute(query, values)
            self.conn.commit()

            logger.info(f"Imported 1 summary record for file_id={file_id}")
            return 1

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import summary: {e}")
            return 0

    def import_drug(self, file_id: int, df: pd.DataFrame) -> int:
        """
        Import Data Drug sheet

        Args:
            file_id: File ID
            df: DataFrame with drug data

        Returns:
            Number of imported records
        """
        if df.empty:
            return 0

        records = []
        for idx, row in df.iterrows():
            # Skip header rows and empty rows
            tran_id = self._safe_string(row.iloc[1] if len(row) > 1 else None, 20)
            if not tran_id:
                continue

            record = {
                'file_id': file_id,
                'row_number': idx,
                'tran_id': tran_id,
                'hn': self._safe_string(row.iloc[2] if len(row) > 2 else None, 15),
                'an': self._safe_string(row.iloc[3] if len(row) > 3 else None, 20),
                'dateadm': self._parse_thai_date(row.iloc[4] if len(row) > 4 else None),
                'pid': self._safe_string(row.iloc[5] if len(row) > 5 else None, 13),
                'patient_name': self._safe_string(row.iloc[6] if len(row) > 6 else None, 100),
                'drug_seq': self._safe_int(row.iloc[7] if len(row) > 7 else 0),
                'drug_code': self._safe_string(row.iloc[8] if len(row) > 8 else None, 20),
                'tmt_code': self._safe_string(row.iloc[9] if len(row) > 9 else None, 10),
                'generic_name': self._safe_string(row.iloc[10] if len(row) > 10 else None, 200),
                'trade_name': self._safe_string(row.iloc[11] if len(row) > 11 else None, 100),
                'drug_type': self._safe_string(row.iloc[12] if len(row) > 12 else None, 10),
                'drug_category': self._safe_string(row.iloc[13] if len(row) > 13 else None, 50),
                'dosage_form': self._safe_string(row.iloc[14] if len(row) > 14 else None, 50),
                'quantity': self._safe_decimal(row.iloc[15] if len(row) > 15 else 0),
                'unit_price': self._safe_decimal(row.iloc[16] if len(row) > 16 else 0),
                'claim_amount': self._safe_decimal(row.iloc[17] if len(row) > 17 else 0),
                'ceiling_price': self._safe_decimal(row.iloc[18] if len(row) > 18 else 0),
                'reimb_amount': self._safe_decimal(row.iloc[19] if len(row) > 19 else 0),
                'reimb_agency': self._safe_decimal(row.iloc[20] if len(row) > 20 else 0),
                'error_code': self._safe_string(row.iloc[21] if len(row) > 21 else None, 50),
            }
            records.append(record)

        if not records:
            return 0

        return self._batch_insert('eclaim_drug', records)

    def import_instrument(self, file_id: int, df: pd.DataFrame) -> int:
        """
        Import Data Instrument sheet (IP only)

        Args:
            file_id: File ID
            df: DataFrame with instrument data

        Returns:
            Number of imported records
        """
        if df.empty:
            return 0

        records = []
        for idx, row in df.iterrows():
            tran_id = self._safe_string(row.iloc[1] if len(row) > 1 else None, 20)
            if not tran_id:
                continue

            record = {
                'file_id': file_id,
                'row_number': idx,
                'tran_id': tran_id,
                'hn': self._safe_string(row.iloc[2] if len(row) > 2 else None, 15),
                'an': self._safe_string(row.iloc[3] if len(row) > 3 else None, 20),
                'dateadm': self._parse_thai_date(row.iloc[4] if len(row) > 4 else None),
                'pid': self._safe_string(row.iloc[5] if len(row) > 5 else None, 13),
                'patient_name': self._safe_string(row.iloc[6] if len(row) > 6 else None, 100),
                'inst_seq': self._safe_int(row.iloc[7] if len(row) > 7 else 0),
                'inst_code': self._safe_string(row.iloc[8] if len(row) > 8 else None, 10),
                'inst_name': self._safe_string(row.iloc[9] if len(row) > 9 else None, 200),
                'claim_qty': self._safe_int(row.iloc[10] if len(row) > 10 else 0),
                'claim_amount': self._safe_decimal(row.iloc[11] if len(row) > 11 else 0),
                'reimb_qty': self._safe_int(row.iloc[12] if len(row) > 12 else 0),
                'reimb_amount': self._safe_decimal(row.iloc[13] if len(row) > 13 else 0),
                'deny_flag': self._safe_string(row.iloc[14] if len(row) > 14 else None, 10),
                'error_code': self._safe_string(row.iloc[15] if len(row) > 15 else None, 50),
            }
            records.append(record)

        if not records:
            return 0

        return self._batch_insert('eclaim_instrument', records)

    def import_deny(self, file_id: int, df: pd.DataFrame) -> int:
        """
        Import Data DENY sheet (IP only)

        Args:
            file_id: File ID
            df: DataFrame with deny data

        Returns:
            Number of imported records
        """
        if df.empty:
            return 0

        records = []
        for idx, row in df.iterrows():
            tran_id = self._safe_string(row.iloc[1] if len(row) > 1 else None, 20)
            if not tran_id:
                continue

            record = {
                'file_id': file_id,
                'row_number': idx,
                'tran_id': tran_id,
                'hcode': self._safe_string(row.iloc[2] if len(row) > 2 else None, 10),
                'hn': self._safe_string(row.iloc[3] if len(row) > 3 else None, 15),
                'an': self._safe_string(row.iloc[4] if len(row) > 4 else None, 20),
                'dateadm': self._parse_thai_date(row.iloc[5] if len(row) > 5 else None),
                'pid': self._safe_string(row.iloc[6] if len(row) > 6 else None, 13),
                'patient_name': self._safe_string(row.iloc[7] if len(row) > 7 else None, 100),
                'fund_code': self._safe_string(row.iloc[8] if len(row) > 8 else None, 20),
                'claim_code': self._safe_string(row.iloc[9] if len(row) > 9 else None, 20),
                'expense_category': self._safe_int(row.iloc[10] if len(row) > 10 else None),
                'claim_amount': self._safe_decimal(row.iloc[11] if len(row) > 11 else 0),
                'deny_code': self._safe_string(row.iloc[12] if len(row) > 12 else None, 20),
            }
            records.append(record)

        if not records:
            return 0

        return self._batch_insert('eclaim_deny', records)

    def import_zero_paid(self, file_id: int, df: pd.DataFrame) -> int:
        """
        Import Data sheet 0 (zero paid items)

        Args:
            file_id: File ID
            df: DataFrame with zero paid data

        Returns:
            Number of imported records
        """
        if df.empty:
            return 0

        records = []
        for idx, row in df.iterrows():
            tran_id = self._safe_string(row.iloc[1] if len(row) > 1 else None, 20)
            if not tran_id:
                continue

            record = {
                'file_id': file_id,
                'row_number': idx,
                'tran_id': tran_id,
                'hcode': self._safe_string(row.iloc[2] if len(row) > 2 else None, 10),
                'hn': self._safe_string(row.iloc[3] if len(row) > 3 else None, 15),
                'an': self._safe_string(row.iloc[4] if len(row) > 4 else None, 20),
                'dateadm': self._parse_thai_date(row.iloc[5] if len(row) > 5 else None),
                'pid': self._safe_string(row.iloc[6] if len(row) > 6 else None, 13),
                'patient_name': self._safe_string(row.iloc[7] if len(row) > 7 else None, 100),
                'fund_code': self._safe_string(row.iloc[8] if len(row) > 8 else None, 20),
                'claim_code': self._safe_string(row.iloc[9] if len(row) > 9 else None, 20),
                'tmt_code': self._safe_string(row.iloc[10] if len(row) > 10 else None, 10),
                'expense_category': self._safe_int(row.iloc[11] if len(row) > 11 else None),
                'claim_qty': self._safe_int(row.iloc[12] if len(row) > 12 else 0),
                'paid_qty': self._safe_int(row.iloc[13] if len(row) > 13 else 0),
                'paid_amount': self._safe_decimal(row.iloc[14] if len(row) > 14 else 0),
                'reason': self._safe_string(row.iloc[15] if len(row) > 15 else None, 200),
            }
            records.append(record)

        if not records:
            return 0

        return self._batch_insert('eclaim_zero_paid', records)

    def _batch_insert(self, table_name: str, records: List[Dict]) -> int:
        """
        Batch insert records into table

        Args:
            table_name: Target table name
            records: List of record dicts

        Returns:
            Number of inserted records
        """
        if not records:
            return 0

        try:
            columns = list(records[0].keys())
            placeholders = ', '.join(['%s'] * len(columns))
            column_str = ', '.join(columns)

            query = f"""
                INSERT INTO {table_name} ({column_str})
                VALUES ({placeholders})
            """

            values = [[record[col] for col in columns] for record in records]

            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, values, page_size=100)
            else:
                self.cursor.executemany(query, values)

            self.conn.commit()
            logger.info(f"Imported {len(records)} records to {table_name}")
            return len(records)

        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to batch insert to {table_name}: {e}")
            return 0

    def import_all_sheets(self, filepath: str, file_id: int, file_type: str) -> Dict:
        """
        Import all additional sheets from an Excel file

        Args:
            filepath: Path to Excel file
            file_id: File ID from eclaim_imported_files
            file_type: File type (OP, IP, ORF)

        Returns:
            Dict with import results for each sheet
        """
        results = {
            'summary': 0,
            'drug': 0,
            'instrument': 0,
            'deny': 0,
            'zero_paid': 0
        }

        try:
            xls = pd.ExcelFile(filepath, engine='xlrd')
            sheet_names = xls.sheet_names
            logger.info(f"Found sheets: {sheet_names}")

            # Import Summary sheet
            if 'Summary' in sheet_names:
                try:
                    # Summary has header rows 0-4, data starts at row 5
                    df = pd.read_excel(filepath, sheet_name='Summary', header=None, skiprows=5)
                    results['summary'] = self.import_summary(file_id, df, file_type)
                except Exception as e:
                    logger.error(f"Error importing Summary: {e}")

            # Import Data Drug sheet
            if 'Data Drug' in sheet_names:
                try:
                    # Drug has header at row 3, empty rows 4-5, data starts row 6
                    df = pd.read_excel(filepath, sheet_name='Data Drug', header=None, skiprows=6)
                    results['drug'] = self.import_drug(file_id, df)
                except Exception as e:
                    logger.error(f"Error importing Data Drug: {e}")

            # Import Data Instrument sheet (IP only)
            if 'Data Instrument' in sheet_names:
                try:
                    # Data Instrument has header rows 0-5, data starts at row 6
                    df = pd.read_excel(filepath, sheet_name='Data Instrument', header=None, skiprows=6)
                    results['instrument'] = self.import_instrument(file_id, df)
                except Exception as e:
                    logger.error(f"Error importing Data Instrument: {e}")

            # Import Data DENY sheet (IP only)
            if 'Data DENY' in sheet_names:
                try:
                    df = pd.read_excel(filepath, sheet_name='Data DENY', header=None, skiprows=1)
                    results['deny'] = self.import_deny(file_id, df)
                except Exception as e:
                    logger.error(f"Error importing Data DENY: {e}")

            # Import Data sheet 0 (zero paid)
            if 'Data sheet 0' in sheet_names:
                try:
                    # Data sheet 0 has header rows 0-5, data starts at row 6
                    df = pd.read_excel(filepath, sheet_name='Data sheet 0', header=None, skiprows=6)
                    results['zero_paid'] = self.import_zero_paid(file_id, df)
                except Exception as e:
                    logger.error(f"Error importing Data sheet 0: {e}")

        except Exception as e:
            logger.error(f"Error processing Excel file: {e}")

        logger.info(f"Additional sheets import results: {results}")
        return results
