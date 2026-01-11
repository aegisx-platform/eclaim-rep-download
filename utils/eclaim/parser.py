#!/usr/bin/env python3
"""
E-Claim XLS File Parser
Parse E-Claim Excel files (OP, IP, ORF, Appeal) and extract structured data
"""

import pandas as pd
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class EClaimFileParser:
    """Parse E-Claim XLS files and extract metadata and data"""

    # File type patterns
    FILE_TYPES = ['OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO']

    # Expected header keywords for detection
    HEADER_KEYWORDS = ['HN', 'PID', 'TRAN_ID', 'AN', 'REP No.']

    def __init__(self, filepath: str):
        """
        Initialize parser

        Args:
            filepath: Path to XLS file
        """
        self.filepath = Path(filepath)
        self.filename = self.filepath.name
        self.metadata = self.parse_filename()
        self.df = None
        self.header_row = None

    def parse_filename(self) -> Dict[str, str]:
        """
        Extract metadata from filename

        Filename format: eclaim_{hospital_code}_{type}_{date_BE}_{sequence}.xls
        Example: eclaim_10670_IP_25680122_205506156.xls

        Returns:
            Dict with: hospital_code, file_type, file_date, sequence
        """
        pattern = r'eclaim_(\d+)_([A-Z_]+)_(\d{8})_(\d+)\.xls'
        match = re.match(pattern, self.filename)

        if not match:
            logger.warning(f"Filename doesn't match pattern: {self.filename}")
            return {
                'hospital_code': None,
                'file_type': None,
                'file_date': None,
                'sequence': None
            }

        file_date = self._parse_be_date(match.group(3))

        return {
            'hospital_code': match.group(1),
            'file_type': match.group(2),
            'file_date': file_date,
            'sequence': match.group(4)
        }

    @staticmethod
    def _parse_thai_date(date_str: str) -> Optional[str]:
        """
        Parse Thai date format to ISO format for PostgreSQL

        Handles formats:
        - DD/MM/YYYY HH:MM:SS -> YYYY-MM-DD HH:MM:SS
        - DD/MM/YYYY -> YYYY-MM-DD
        - "-" -> None

        Args:
            date_str: Date string from Excel

        Returns:
            ISO formatted date string or None
        """
        if not date_str or date_str == '-' or pd.isna(date_str):
            return None

        try:
            date_str = str(date_str).strip()

            # Try DD/MM/YYYY HH:MM:SS format
            if ' ' in date_str:
                date_part, time_part = date_str.split(' ', 1)
                day, month, year = date_part.split('/')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)} {time_part}"
            # Try DD/MM/YYYY format
            elif '/' in date_str:
                day, month, year = date_str.split('/')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                return None
        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse date: {date_str} - {e}")
            return None

    @staticmethod
    def _parse_be_date(date_str: str) -> Optional[datetime]:
        """
        Convert Buddhist Era date to CE date

        Args:
            date_str: Date in format YYYYMMDD (Buddhist Era)
                     Example: 25680122 = Jan 22, 2568 BE = Jan 22, 2025 CE

        Returns:
            datetime object or None if invalid
        """
        try:
            be_year = int(date_str[:4])
            ce_year = be_year - 543
            month = int(date_str[4:6])
            day = int(date_str[6:8])
            return datetime(ce_year, month, day)
        except (ValueError, IndexError) as e:
            logger.error(f"Invalid date format: {date_str} - {e}")
            return None

    def detect_header_row(self, max_rows: int = 10) -> int:
        """
        Detect which row contains column headers

        E-Claim files typically have:
        - OP/IP: Headers at row 6 (index 5)
        - ORF: Headers at row 8 (index 7)

        Args:
            max_rows: Maximum rows to search

        Returns:
            Row index (0-based) of header row
        """
        if self.df is None:
            raise ValueError("Must call load_file() first")

        file_type = self.get_file_type()

        # ORF files have headers at row 8 (index 7)
        if file_type == 'ORF':
            logger.info(f"ORF file detected, using header row 8 (index 7)")
            return 7

        # For other types, detect automatically
        for i in range(max_rows):
            if i >= len(self.df):
                break

            row_values = self.df.iloc[i].astype(str).tolist()
            row_str = ' '.join(row_values)

            # Check if this row contains header keywords
            keyword_count = sum(1 for keyword in self.HEADER_KEYWORDS
                              if keyword in row_str)

            if keyword_count >= 2:  # At least 2 keywords found
                logger.info(f"Header row detected at row {i+1} (index {i})")
                return i

        # Default to row 6 (index 5) if not detected
        logger.warning("Could not detect header row, defaulting to row 6")
        return 5

    def load_file(self) -> pd.DataFrame:
        """
        Load XLS file and detect header row

        Returns:
            DataFrame with headers properly set
        """
        try:
            # Read file without headers first
            self.df = pd.read_excel(
                self.filepath,
                engine='xlrd',
                header=None
            )

            logger.info(f"Loaded file: {self.filename} ({len(self.df)} rows)")

            # Detect header row
            self.header_row = self.detect_header_row()

            # Re-read with correct header
            self.df = pd.read_excel(
                self.filepath,
                engine='xlrd',
                header=self.header_row
            )

            # Clean column names
            self.df.columns = [str(col).strip() for col in self.df.columns]

            logger.info(f"Parsed {len(self.df)} data rows with {len(self.df.columns)} columns")

            return self.df

        except Exception as e:
            logger.error(f"Error loading file {self.filename}: {e}")
            raise

    def get_file_type(self) -> str:
        """Get file type (OP, IP, ORF, etc.)"""
        return self.metadata.get('file_type', 'UNKNOWN')

    def get_column_mapping(self) -> Dict[str, str]:
        """
        Get column mapping for database fields

        Returns:
            Dict mapping XLS columns to database fields
        """
        file_type = self.get_file_type()

        # Common columns for all types
        common_mapping = {
            'REP No.': 'rep_no',
            'TRAN_ID': 'tran_id',
            'HN': 'hn',
            'AN': 'an',
            'PID': 'pid',
            'ชื่อ-สกุล': 'patient_name',
            'ประเภทผู้ป่วย': 'patient_type',
            'วันเข้ารักษา': 'admission_date',
            'วันจำหน่าย': 'discharge_date',
            'ชดเชยสุทธิ': 'net_reimbursement',
            'Error Code': 'error_code',
            'CHK': 'chk'
        }

        if file_type in ['OP', 'IP', 'IP_APPEAL', 'IP_APPEAL_NHSO']:
            return common_mapping
        elif file_type == 'ORF':
            # ORF has different columns and multi-row headers at row 8
            orf_mapping = {
                'REP': 'rep',
                'TRAN_ID': 'tran_id',
                'HN': 'hn',
                'PID': 'pid',
                'ชื่อ': 'patient_name',
                'ว/ด/ป ที่รับบริการ': 'service_date',
                'เลขที่ใบส่งต่อ': 'refer_doc_no',
                'DX.': 'dx',
                'Proc.': 'proc_code',
                'รายการ OPREF\n(5)': 'total_claimable'
            }
            return orf_mapping

        return common_mapping

    def extract_data_records(self) -> List[Dict]:
        """
        Extract data records from DataFrame

        Returns:
            List of dicts, each representing one record
        """
        if self.df is None:
            raise ValueError("Must call load_file() first")

        records = []
        column_mapping = self.get_column_mapping()
        skipped_rows = 0

        for idx, row in self.df.iterrows():
            record = {
                'row_number': idx + self.header_row + 2,  # +2 for 1-based and header
                'file_type': self.get_file_type()
            }

            # Map columns
            for xls_col, db_field in column_mapping.items():
                if xls_col in self.df.columns:
                    value = row[xls_col]

                    # Handle NaN/None
                    if pd.isna(value):
                        value = None
                    # Convert "-" to None (common placeholder in E-Claim)
                    elif value == '-':
                        value = None
                    # Convert date strings to ISO format for PostgreSQL
                    elif db_field in ['admission_date', 'discharge_date', 'service_date'] and value:
                        value = self._parse_thai_date(value)
                    # Clean numeric fields
                    elif db_field in ['total_claimable', 'net_reimbursement'] and value:
                        # Remove commas and convert to number
                        try:
                            value = str(value).replace(',', '').strip()
                            if value == '' or value == '-':
                                value = None
                        except (AttributeError, TypeError):
                            value = None

                    record[db_field] = value

            # Skip rows without TRAN_ID (empty rows or invalid data)
            if not record.get('tran_id') or pd.isna(record.get('tran_id')):
                skipped_rows += 1
                continue

            records.append(record)

        if skipped_rows > 0:
            logger.info(f"Skipped {skipped_rows} empty/invalid rows")

        return records

    def get_summary(self) -> Dict:
        """
        Get file summary

        Returns:
            Dict with file statistics
        """
        if self.df is None:
            raise ValueError("Must call load_file() first")

        return {
            'filename': self.filename,
            'file_type': self.get_file_type(),
            'hospital_code': self.metadata.get('hospital_code'),
            'file_date': self.metadata.get('file_date'),
            'total_rows': len(self.df),
            'total_columns': len(self.df.columns),
            'header_row': self.header_row + 1,  # 1-based for display
            'columns': list(self.df.columns)
        }


def parse_eclaim_file(filepath: str) -> Tuple[Dict, List[Dict]]:
    """
    Convenience function to parse E-Claim file

    Args:
        filepath: Path to XLS file

    Returns:
        Tuple of (metadata dict, list of data records)
    """
    parser = EClaimFileParser(filepath)
    parser.load_file()

    metadata = parser.get_summary()
    records = parser.extract_data_records()

    return metadata, records


if __name__ == '__main__':
    # Test parser
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parser.py <path_to_xls_file>")
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)

    filepath = sys.argv[1]
    parser = EClaimFileParser(filepath)
    parser.load_file()

    summary = parser.get_summary()
    print("\n=== File Summary ===")
    for key, value in summary.items():
        if key != 'columns':
            print(f"{key}: {value}")

    print(f"\n=== First 5 Columns ===")
    print(summary['columns'][:5])

    records = parser.extract_data_records()
    print(f"\n=== First Record ===")
    if records:
        for key, value in list(records[0].items())[:10]:
            print(f"{key}: {value}")
