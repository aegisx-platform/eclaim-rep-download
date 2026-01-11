#!/usr/bin/env python3
"""
E-Claim Database Importer V2 - Complete Field Mapping
Import parsed E-Claim data into hospital's existing schema
Works with claim_rep_opip_nhso_item and claim_rep_orf_nhso_item tables
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
    logger.warning("psycopg2 not available - PostgreSQL support disabled")

try:
    import pymysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    logger.warning("pymysql not available - MySQL support disabled")


class EClaimImporterV2:
    """
    Import E-Claim data into hospital's existing schema
    Tables: claim_rep_opip_nhso_item, claim_rep_orf_nhso_item
    """

    # Column mapping: E-Claim column name → Database column name
    OPIP_COLUMN_MAP = {
        'REP No.': 'rep_no',
        'ลำดับที่': 'seq',
        'TRAN_ID': 'tran_id',
        'HN': 'hn',
        'AN': 'an',
        'PID': 'pid',
        'ชื่อ-สกุล': 'name',
        'ประเภทผู้ป่วย': 'ptype',
        'วันเข้ารักษา': 'dateadm',
        'วันจำหน่าย': 'datedsc',
        'ชดเชยสุทธิ': 'reimb_nhso',
        'ชดเชยจาก': 'claim_from',
        'Error Code': 'error_code',
        'กองทุนหลัก': 'main_fund',
        'กองทุนย่อย': 'sub_fund',
        'ประเภทบริการ': 'service_type',
        'การรับส่งต่อ': 'chk_refer',
        'การมีสิทธิ': 'chk_right',
        'การใช้สิทธิ': 'chk_use_right',
        'CHK': 'chk',
        'สิทธิหลัก': 'main_inscl',
        'สิทธิย่อย': 'sub_inscl',
        'HREF': 'href',
        'HCODE': 'hcode',
        'HMAIN': 'hmain',
        'PROV1': 'prov1',
        'RG1': 'rg1',
        'HMAIN2': 'hmain2',
        'PROV2': 'prov2',
        'RG2': 'rg2',
        'DMIS/ HMAIN3': 'hmain3',
        'DA': 'da',
        'PROJ': 'projcode',
        'PA': 'pa',
        'DRG': 'drg',
        'RW': 'rw',
        'CA_TYPE': 'ca_type',
        'เรียกเก็บ\n(1)': 'claim_drg',
        'เรียกเก็บ\ncentral reimburse\n(2)': 'claim_central_reimb',
        'ชำระเอง\n(3)': 'paid',
        'อัตราจ่าย/Point\n(4)': 'pay_point',
        'ล่าช้า (PS)\n(5)': 'ps_percent',
        'CCUF \n(6)': 'ccuf',
        'AdjRW_NHSO\n(7)': 'adjrw_nhso',
        'AdjRW2\n(8 = 6x7)': 'adjrw2',
        'จ่ายชดเชย\n(9 = 4x5x8)': 'reimb_amt',
        'ค่าพรบ.\n(10)': 'act_amt',
        'เงินเดือน': 'salary_rate',
        'ยอดชดเชยหลังหักเงินเดือน\n(12 = 9-10-11)': 'reimb_diff_salary',
    }

    # ORF Column mapping - Uses column INDEX because ORF files have complex multi-level headers
    # Headers span rows 5, 7, and 8 with merged cells
    # Format: Excel column INDEX -> Database column name
    ORF_COLUMN_INDEX_MAP = {
        0: 'rep_no',                # REP
        1: 'no',                    # NO.
        2: 'tran_id',               # TRAN_ID
        3: 'hn',                    # HN
        4: 'pid',                   # PID
        5: 'name',                  # ชื่อ
        6: 'service_date',          # ว/ด/ป ที่รับบริการ
        7: 'refer_no',              # เลขที่ใบส่งต่อ
        8: 'htype1',                # หน่วยบริการ_รักษา(Htype1)
        9: 'prov1',                 # รักษา(Prov1)
        10: 'hcode',                # รักษา(Hcode)
        11: 'htype2',               # รักษา(Htype2)
        12: 'prov2',                # รักษา(Prov2)
        13: 'hmain2',               # ประจำ(Hmain2)
        14: 'href',                 # รับส่งต่อ(Href)
        15: 'dx',                   # DX.
        16: 'proc',                 # Proc.
        17: 'dmis',                 # DMIS
        18: 'hmain3',               # HMAIN3
        19: 'dar',                  # DAR
        20: 'ca_type',              # CA_TYPE
        21: 'claim_amt',            # ยอดรวมค่าใช้จ่าย(เฉพาะเบิกได้)(1)
        22: 'central_reimb_case',   # เข้าเกณฑ์ central reimburse (2)
        23: 'central_reimb_amt',    # จำนวนเงิน
        24: 'paid',                 # ชำระเอง(3)
        25: 'act_amt',              # พรบ.(4)
        26: 'opref_list',           # เข้าเกณฑ์ OP REFER / รายการ OPREF(5)
        27: 'opref_bef_adj',        # ค่ารักษาอื่นๆ_ก่อนปรับลด(6)
        28: 'opref_aft_adj',        # หลังปรับลด(7)
        29: 'total',                # ผลรวมทั้ง Case(8=5+7)
        30: 'respon_cup',           # ผู้รับผิดชอบ(9)=(8)_<=1600
        31: 'respon_nhso',          # สปสช_>1600
        32: 'reimb_total',          # ชดเชยสุทธิ (บาท)(10=8)
        33: 'pay_by',               # ชำระบัญชีโดย
        34: 'ps',                   # PS
        35: 'cr_ophc_hc01',         # OPHC_HC01
        36: 'cr_ophc_hc02',         # HC02
        37: 'cr_ophc_hc03',         # HC03
        38: 'cr_ophc_hc04',         # HC04
        39: 'cr_ophc_hc05',         # HC05
        40: 'cr_ophc_hc06',         # HC06
        41: 'cr_ophc_hc07',         # HC07
        42: 'cr_ophc_hc08',         # HC08
        43: 'cr_ae04',              # อุบัติเหตุฉุกเฉิน_AE04
        44: 'cr_carae_ae08',        # CARAE_AE08
        45: 'cr_opinst_hc09',       # OPINST_HC09
        46: 'cr_dmisrc_amt',        # DMISRC_DMISRC
        47: 'cr_dmisrc_workload',   # ค่าภาระงาน (DMISRC)
        48: 'cr_rcuhosc_amt',       # RCUHOSC_RCUHOSC
        49: 'cr_rcuhosc_workload',  # ค่าภาระงาน (RCUHOSC)
        50: 'cr_rcuhosr_amt',       # RCUHOSR_RCUHOSR
        51: 'cr_rcuhosr_workload',  # ค่าภาระงาน (RCUHOSR)
        52: 'cr_llop',              # LLOP
        53: 'cr_lp',                # LP
        54: 'cr_stroke_drug',       # STROKE-STEMI DRUG
        55: 'cr_dmidml',            # DMIDML
        56: 'cr_pp',                # PP
        57: 'cr_dmishd',            # DMISHD
        58: 'cr_paliative',         # Paliative Care
        59: 'cr_drug',              # DRUG
        60: 'cr_ontop',             # ONTOP
        61: 'cr_total',             # ชดเชยสุทธิ (บาท) - CR section total
        62: 'cr_by',                # ชำระโดย
        63: 'oprefer_md01_claim',   # ค่าห้อง/ค่าอาหาร_เบิกได้
        64: 'oprefer_md01_free',    # ค่าห้อง/ค่าอาหาร_เบิกไม่ได้
        65: 'oprefer_md02_claim',   # อวัยวะเทียม/อุปกรณ์บำบัดรักษา_เบิกได้
        66: 'oprefer_md02_free',    # อวัยวะเทียม/อุปกรณ์บำบัดรักษา_เบิกไม่ได้
        67: 'oprefer_md03_claim',   # ยาและสารอาหารทางเส้นเลือดที่ใช้ในรพ._เบิกได้
        68: 'oprefer_md03_free',    # ยาและสารอาหารทางเส้นเลือดที่ใช้ในรพ._เบิกไม่ได้
        69: 'oprefer_md04_claim',   # ยาที่นำไปใช้ต่อที่บ้าน_เบิกได้
        70: 'oprefer_md04_free',    # ยาที่นำไปใช้ต่อที่บ้าน_เบิกไม่ได้
        71: 'oprefer_md05_claim',   # เวชภัณฑ์ที่ไม่ใช่ยา_เบิกได้
        72: 'oprefer_md05_free',    # เวชภัณฑ์ที่ไม่ใช่ยา_เบิกไม่ได้
        73: 'oprefer_md06_claim',   # บริการโลหิตและองค์ประกอบของโลหิต_เบิกได้
        74: 'oprefer_md06_free',    # บริการโลหิตและองค์ประกอบของโลหิต_เบิกไม่ได้
        75: 'oprefer_md07_claim',   # ตรวจวินิจฉัยทางเทคนิคการแพทย์และพยาธิวิทยา_เบิกได้
        76: 'oprefer_md07_free',    # ตรวจวินิจฉัยทางเทคนิคการแพทย์และพยาธิวิทยา_เบิกไม่ได้
        77: 'oprefer_md08_claim',   # ตรวจวินิจฉัยและรักษาทางรังสีวิทยา_เบิกได้
        78: 'oprefer_md08_free',    # ตรวจวินิจฉัยและรักษาทางรังสีวิทยา_เบิกไม่ได้
        79: 'oprefer_md09_claim',   # ตรวจวินิจฉัยโดยวิธีพิเศษอื่นๆ_เบิกได้
        80: 'oprefer_md09_free',    # ตรวจวินิจฉัยโดยวิธีพิเศษอื่นๆ_เบิกไม่ได้
        81: 'oprefer_md10_claim',   # อุปกรณ์และเครื่องมือทางการแพทย์_เบิกได้
        82: 'oprefer_md10_free',    # อุปกรณ์และเครื่องมือทางการแพทย์_เบิกไม่ได้
        83: 'oprefer_md11_claim',   # ทำหัตถการและบริการวิสัญญี_เบิกได้
        84: 'oprefer_md11_free',    # ทำหัตถการและบริการวิสัญญี_เบิกไม่ได้
        85: 'oprefer_md12_claim',   # ค่าบริการทางพยาบาล_เบิกได้
        86: 'oprefer_md12_free',    # ค่าบริการทางพยาบาล_เบิกไม่ได้
        87: 'oprefer_md13_claim',   # ค่าบริการทางทันตกรรม_เบิกได้
        88: 'oprefer_md13_free',    # ค่าบริการทางทันตกรรม_เบิกไม่ได้
        89: 'oprefer_md14_claim',   # ค่าบริการทางกายภาพบำบัดและเวชกรรมฟื้นฟู_เบิกได้
        90: 'oprefer_md14_free',    # ค่าบริการทางกายภาพบำบัดและเวชกรรมฟื้นฟู_เบิกไม่ได้
        91: 'oprefer_md15_claim',   # ค่าบริการฝังเข็ม_เบิกได้
        92: 'oprefer_md15_free',    # ค่าบริการฝังเข็ม_เบิกไม่ได้
        93: 'oprefer_md16_claim',   # ค่าห้องผ่าตัดและห้องคลอด_เบิกได้
        94: 'oprefer_md16_free',    # ค่าห้องผ่าตัดและห้องคลอด_เบิกไม่ได้
        95: 'oprefer_md17_claim',   # ค่าธรรมเนียมบุคลากรทางการแพทย์_เบิกได้
        96: 'oprefer_md17_free',    # ค่าธรรมเนียมบุคลากรทางการแพทย์_เบิกไม่ได้
        97: 'oprefer_md18_claim',   # บริการอื่นๆ และส่งเสริมป้องกันโรค_เบิกได้
        98: 'oprefer_md18_free',    # บริการอื่นๆ และส่งเสริมป้องกันโรค_เบิกไม่ได้
        99: 'oprefer_md19_claim',   # บริการอื่นๆ ที่ยังไม่ได้จัดหมวด_เบิกได้
        100: 'oprefer_md19_free',   # บริการอื่นๆ ที่ยังไม่ได้จัดหมวด_เบิกไม่ได้
        101: 'error_code',          # Error Code
        # 102-105: Deny columns (HC, AE, INST, DMIS) - not mapped to DB
        106: 'va',                  # VA
        107: 'remark',              # Remark
        108: 'audit_results',       # AUDIT RESULTS
        109: 'payment_type',        # รูปแบบการจ่าย
        110: 'seq_no',              # SEQ NO
        111: 'invoice_no',          # INVOICE NO
        112: 'invoice_lt',          # INVOICE LT
    }

    def __init__(self, db_config: Dict, db_type: str = None):
        """
        Initialize importer

        Args:
            db_config: Database configuration dict
            db_type: Database type ('postgresql' or 'mysql')
        """
        self.db_config = db_config
        self.db_type = db_type or os.getenv('DB_TYPE', 'mysql')
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
            return self.cursor.fetchone()[0]
        elif self.db_type == 'mysql':
            return self.cursor.lastrowid

    def create_import_record(self, metadata: Dict) -> int:
        """
        Create or update record in eclaim_imported_files table
        Uses UPSERT to handle duplicate filenames (e.g., retry after failed import)

        Args:
            metadata: File metadata dict

        Returns:
            file_id of created/updated record
        """
        if self.db_type == 'postgresql':
            # UPSERT: If filename exists, reset status to 'processing' and retry
            query = """
                INSERT INTO eclaim_imported_files
                (filename, file_type, hospital_code, file_date, status, file_created_at, import_started_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (filename) DO UPDATE SET
                    status = 'processing',
                    import_started_at = NOW(),
                    import_completed_at = NULL,
                    error_message = NULL,
                    updated_at = NOW()
                RETURNING id
            """
        elif self.db_type == 'mysql':
            # MySQL UPSERT using ON DUPLICATE KEY UPDATE
            query = """
                INSERT INTO eclaim_imported_files
                (filename, file_type, hospital_code, file_date, status, file_created_at, import_started_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                    status = 'processing',
                    import_started_at = NOW(),
                    import_completed_at = NULL,
                    error_message = NULL,
                    updated_at = NOW()
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

            if self.db_type == 'postgresql':
                file_id = self.cursor.fetchone()[0]
            elif self.db_type == 'mysql':
                # For MySQL, get the ID from the insert or existing record
                file_id = self.cursor.lastrowid
                if file_id == 0:  # ON DUPLICATE KEY UPDATE doesn't return lastrowid
                    # Query to get existing file_id
                    self.cursor.execute(
                        "SELECT id FROM eclaim_imported_files WHERE filename = %s",
                        (metadata['filename'],)
                    )
                    file_id = self.cursor.fetchone()[0]

            self.conn.commit()
            logger.info(f"Created/updated import record: file_id={file_id}, filename={metadata['filename']}")
            return file_id
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to create/update import record: {e}")
            raise

    def update_import_status(self, file_id: int, status: str,
                           total_records: int = 0,
                           imported_records: int = 0,
                           failed_records: int = 0,
                           error_message: str = None):
        """Update import status"""
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

    def _map_dataframe_row(self, df_row, column_map: Dict, file_id: int, row_number: int) -> Dict:
        """
        Map DataFrame row to database columns using column map

        Args:
            df_row: DataFrame row (Series)
            column_map: Column mapping dict
            file_id: File ID
            row_number: Row number

        Returns:
            Mapped dict
        """
        # Date columns that need parsing
        date_columns = ['dateadm', 'datedsc', 'service_date', 'inp_date']

        # String field max lengths (from schema)
        max_lengths = {
            'chk_refer': 1, 'chk_right': 1, 'chk_use_right': 1, 'chk': 1,
            'da': 1, 'pa': 1, 'ps_chk': 1, 'ps': 1,
            'service_type': 2, 'ca_type': 5, 'ptype': 5,
            'main_inscl': 5, 'sub_inscl': 5, 'prov1': 5, 'rg1': 5,
            'prov2': 5, 'rg2': 5, 'ps_percent': 5, 'salary_rate': 5,
            'htype1': 5, 'htype2': 5,
            'href': 10, 'hcode': 10, 'hmain': 10, 'hmain2': 10, 'hmain3': 10,
            'drg': 10, 'dx': 10, 'proc': 10, 'deny_hc': 10, 'deny_ae': 10,
            'deny_inst': 10, 'deny_ip': 10, 'deny_dmis': 10,
            'rep_no': 15, 'tran_id': 15, 'hn': 15, 'an': 15, 'seq_no': 15,
            'pid': 20, 'invoice_no': 20, 'invoice_lt': 20, 'his_vn': 20,
            'reconcile_status': 20, 'refer_no': 20, 'central_reimb_case': 20,
            'claim_from': 50, 'pay_by': 50
        }

        mapped = {
            'file_id': file_id,
            'row_number': row_number
        }

        for excel_col, db_col in column_map.items():
            if excel_col in df_row.index:
                value = df_row[excel_col]
                # Convert NaN to None
                if pd.isna(value):
                    mapped[db_col] = None
                # Handle empty strings and "-" as NULL
                elif isinstance(value, str) and value.strip() in ['', '-', 'N/A', 'n/a']:
                    mapped[db_col] = None
                else:
                    # Handle date parsing for date columns
                    if db_col in date_columns and isinstance(value, str):
                        try:
                            # Try to parse Thai date format: dd/mm/yyyy hh:mm:ss
                            parsed_date = pd.to_datetime(value, format='%d/%m/%Y %H:%M:%S', errors='coerce')
                            if pd.isna(parsed_date):
                                # Try without time
                                parsed_date = pd.to_datetime(value, format='%d/%m/%Y', errors='coerce')
                            mapped[db_col] = parsed_date if not pd.isna(parsed_date) else None
                        except (ValueError, TypeError, AttributeError):
                            mapped[db_col] = None
                    # Clean ID fields - remove .0 suffix from float conversion
                    elif db_col in ['tran_id', 'hn', 'an', 'pid']:
                        str_value = str(value).strip()
                        # Remove .0 suffix if present (pandas converts int to float)
                        if str_value.endswith('.0'):
                            str_value = str_value[:-2]
                        # Apply max length
                        max_len = {'tran_id': 15, 'hn': 15, 'an': 15, 'pid': 20}.get(db_col, 20)
                        mapped[db_col] = str_value[:max_len]
                    # Truncate strings to max length
                    elif db_col in max_lengths:
                        # Convert to string first if needed
                        str_value = str(value) if not isinstance(value, str) else value
                        mapped[db_col] = str_value[:max_lengths[db_col]]
                    else:
                        mapped[db_col] = value
            else:
                mapped[db_col] = None

        return mapped

    def _map_orf_row_by_index(self, df_row, file_id: int, row_number: int) -> Dict:
        """
        Map ORF DataFrame row to database columns using column INDEX (position-based)
        ORF files have complex multi-level headers that can't be reliably mapped by name

        Args:
            df_row: DataFrame row (Series) with integer position-based index
            file_id: File ID
            row_number: Row number

        Returns:
            Mapped dict
        """
        # Date columns that need parsing
        date_columns = ['service_date', 'inp_date']

        # String field max lengths (from schema)
        max_lengths = {
            'ps': 1,
            'ca_type': 5, 'prov1': 5, 'prov2': 5, 'htype1': 5, 'htype2': 5,
            'dx': 10, 'proc': 10,
            'rep_no': 15, 'tran_id': 15, 'hn': 15, 'seq_no': 15,
            'pid': 20, 'invoice_no': 20, 'invoice_lt': 20, 'refer_no': 20,
            'central_reimb_case': 20,
            'pay_by': 50,
            'name': 100, 'hcode': 100, 'hmain2': 100, 'href': 100, 'dmis': 100,
            'hmain3': 100, 'dar': 100, 'cr_by': 100, 'error_code': 100, 'remark': 100
        }

        mapped = {
            'file_id': file_id,
            'row_number': row_number
        }

        for col_idx, db_col in self.ORF_COLUMN_INDEX_MAP.items():
            # Get value by position (iloc)
            if col_idx < len(df_row):
                value = df_row.iloc[col_idx]

                # Convert NaN to None
                if pd.isna(value):
                    mapped[db_col] = None
                # Handle empty strings and "-" as NULL
                elif isinstance(value, str) and value.strip() in ['', '-', 'N/A', 'n/a']:
                    mapped[db_col] = None
                else:
                    # Handle multi-line values (some cells have newline-separated data)
                    # For numeric columns, take first value; for text, take first non-empty line
                    if isinstance(value, str) and '\n' in value:
                        lines = [l.strip() for l in value.split('\n') if l.strip()]
                        value = lines[0] if lines else None
                        if value is None:
                            mapped[db_col] = None
                            continue

                    # Handle date parsing for date columns
                    if db_col in date_columns:
                        if isinstance(value, str):
                            try:
                                # Try to parse Thai date format: dd/mm/yyyy hh:mm:ss
                                parsed_date = pd.to_datetime(value, format='%d/%m/%Y %H:%M:%S', errors='coerce')
                                if pd.isna(parsed_date):
                                    # Try without time
                                    parsed_date = pd.to_datetime(value, format='%d/%m/%Y', errors='coerce')
                                mapped[db_col] = parsed_date if not pd.isna(parsed_date) else None
                            except (ValueError, TypeError, AttributeError):
                                mapped[db_col] = None
                        elif hasattr(value, 'to_pydatetime'):
                            # Already a datetime-like object
                            mapped[db_col] = value
                        else:
                            mapped[db_col] = None
                    # Clean ID fields - remove .0 suffix from float conversion
                    elif db_col in ['tran_id', 'hn', 'an', 'pid']:
                        str_value = str(value).strip()
                        # Remove .0 suffix if present (pandas converts int to float)
                        if str_value.endswith('.0'):
                            str_value = str_value[:-2]
                        # Apply max length
                        max_len = {'tran_id': 15, 'hn': 15, 'an': 15, 'pid': 20}.get(db_col, 20)
                        mapped[db_col] = str_value[:max_len]
                    # Truncate strings to max length
                    elif db_col in max_lengths:
                        # Convert to string first if needed
                        str_value = str(value) if not isinstance(value, str) else value
                        mapped[db_col] = str_value[:max_lengths[db_col]]
                    else:
                        mapped[db_col] = value
            else:
                mapped[db_col] = None

        return mapped

    def import_opip_batch(self, file_id: int, df, start_row: int = 0) -> int:
        """
        Import batch of OP/IP records from DataFrame

        Args:
            file_id: File ID
            df: DataFrame with claim data
            start_row: Starting row number

        Returns:
            Number of successfully imported records
        """
        import pandas as pd

        if df.empty:
            return 0

        # Map all rows
        mapped_records = []
        for idx, row in df.iterrows():
            mapped = self._map_dataframe_row(row, self.OPIP_COLUMN_MAP, file_id, start_row + idx)
            mapped_records.append(mapped)

        if not mapped_records:
            return 0

        # Get column names from first mapped record
        columns = list(mapped_records[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_str = ', '.join(columns)

        if self.db_type == 'mysql':
            # Build UPDATE clause for ON DUPLICATE KEY
            update_clause = ', '.join([f"{col} = VALUES({col})" for col in columns if col not in ['id', 'file_id', 'tran_id', 'row_number']])

            query = f"""
                INSERT INTO claim_rep_opip_nhso_item
                ({column_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE
                {update_clause}
            """
        else:  # postgresql
            update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['id', 'file_id', 'tran_id', 'row_number']])

            query = f"""
                INSERT INTO claim_rep_opip_nhso_item
                ({column_str})
                VALUES ({placeholders})
                ON CONFLICT (tran_id, file_id) DO UPDATE SET
                {update_clause}
            """

        try:
            # Convert dicts to tuples in correct column order
            values = [[record[col] for col in columns] for record in mapped_records]

            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, values, page_size=100)
            else:
                self.cursor.executemany(query, values)

            self.conn.commit()
            logger.info(f"Imported {len(mapped_records)} OP/IP records")
            return len(mapped_records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import OP/IP batch: {e}")
            raise

    def import_orf_batch(self, file_id: int, df, start_row: int = 0) -> int:
        """
        Import batch of ORF records from DataFrame
        Uses index-based column mapping for ORF's complex multi-level headers

        Args:
            file_id: File ID
            df: DataFrame with ORF data (read without header, columns are positional)
            start_row: Starting row number

        Returns:
            Number of successfully imported records
        """
        import pandas as pd

        if df.empty:
            return 0

        # Map all rows using index-based mapping
        mapped_records = []
        for idx, row in df.iterrows():
            mapped = self._map_orf_row_by_index(row, file_id, start_row + idx)
            mapped_records.append(mapped)

        if not mapped_records:
            return 0

        columns = list(mapped_records[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_str = ', '.join(columns)

        if self.db_type == 'mysql':
            update_clause = ', '.join([f"{col} = VALUES({col})" for col in columns if col not in ['id', 'file_id', 'tran_id', 'row_number']])

            query = f"""
                INSERT INTO claim_rep_orf_nhso_item
                ({column_str})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE
                {update_clause}
            """
        else:
            update_clause = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns if col not in ['id', 'file_id', 'tran_id', 'row_number']])

            query = f"""
                INSERT INTO claim_rep_orf_nhso_item
                ({column_str})
                VALUES ({placeholders})
                ON CONFLICT (tran_id, file_id) DO UPDATE SET
                {update_clause}
            """

        try:
            values = [[record[col] for col in columns] for record in mapped_records]

            if self.db_type == 'postgresql':
                pg_execute_batch(self.cursor, query, values, page_size=100)
            else:
                self.cursor.executemany(query, values)

            self.conn.commit()
            logger.info(f"Imported {len(mapped_records)} ORF records")
            return len(mapped_records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import ORF batch: {e}")
            raise

    def import_file(self, filepath: str, metadata: Dict = None, import_additional_sheets: bool = True) -> Dict:
        """
        Import complete file including all sheets

        Args:
            filepath: Path to Excel file
            metadata: Optional file metadata (will be parsed from filename if not provided)
            import_additional_sheets: Whether to import Summary, Drug, Instrument, Deny, Zero sheets

        Returns:
            Dict with import results
        """
        import pandas as pd
        from pathlib import Path

        # Parse metadata from filename if not provided
        if metadata is None:
            from .parser import EClaimFileParser
            parser = EClaimFileParser(filepath)
            metadata = parser.metadata
            metadata['filename'] = Path(filepath).name

        file_type = metadata.get('file_type', '')
        total_records = 0
        imported_records = 0
        failed_records = 0
        error_message = None
        additional_results = {}

        try:
            # Create import record
            file_id = self.create_import_record(metadata)

            # Read Excel file based on type
            if file_type == 'ORF':
                # ORF files have multi-level headers at rows 5, 7, and 8
                # Skip header rows (0-8) and read data starting from row 9
                # Use header=None to get positional column indices
                df = pd.read_excel(filepath, engine='xlrd', header=None, skiprows=9)

                # Filter out empty rows (check column 2 which is TRAN_ID)
                df = df[df.iloc[:, 2].notna()]

                # Also filter out footer/summary rows (usually have text in first column)
                # Check if column 0 (REP) looks like a valid REP number
                df = df[df.iloc[:, 0].apply(lambda x: str(x).strip() != '' and str(x).strip() != 'nan')]
            else:
                # OP/IP files: Skip first 5 rows (report header), then skip 2 empty rows after column headers
                df = pd.read_excel(filepath, engine='xlrd', skiprows=list(range(0,5)) + [6,7])
                # Remove empty rows
                if 'TRAN_ID' in df.columns:
                    df = df.dropna(subset=['TRAN_ID'])

            total_records = len(df)

            # Import data based on file type
            if file_type == 'ORF':
                imported_records = self.import_orf_batch(file_id, df)
            else:  # OP, IP, APPEAL
                imported_records = self.import_opip_batch(file_id, df)

            # Import additional sheets (Summary, Drug, Instrument, Deny, Zero)
            if import_additional_sheets:
                try:
                    from .importer_sheets import AdditionalSheetsImporter
                    sheets_importer = AdditionalSheetsImporter(self.conn, self.cursor, self.db_type)
                    additional_results = sheets_importer.import_all_sheets(filepath, file_id, file_type)
                    logger.info(f"Additional sheets imported: {additional_results}")
                except Exception as e:
                    logger.warning(f"Failed to import additional sheets: {e}")
                    additional_results = {'error': str(e)}

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
                'failed_records': failed_records,
                'additional_sheets': additional_results
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
                'failed_records': failed_records,
                'additional_sheets': additional_results
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
    logger.info(f"Importing file: {filepath}")

    with EClaimImporterV2(db_config, db_type) as importer:
        result = importer.import_file(filepath)

    return result


if __name__ == '__main__':
    import sys
    from config.database import get_db_config, DB_TYPE

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) < 2:
        print("Usage: python importer_v2.py <path_to_xls_file>")
        sys.exit(1)

    filepath = sys.argv[1]
    db_config = get_db_config()

    result = import_eclaim_file(filepath, db_config, DB_TYPE)

    print("\n=== Import Result ===")
    for key, value in result.items():
        print(f"{key}: {value}")
