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
        'เลขประจำตัวประชาชน': 'pid',
        'ชื่อ-สกุล': 'name',
        'ประเภทผู้ป่วย': 'ptype',
        'วันเข้ารักษา': 'dateadm',
        'วันจำหน่าย': 'datedsc',
        'ชดเชยสุทธิ (บาท)\n(สปสช.)': 'reimb_nhso',
        'ชดเชยสุทธิ (บาท)\n(ต้นสังกัด)': 'reimb_agency',
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
        'DMIS/HMAIN3': 'hmain3',
        'DA': 'da',
        'PROJ': 'projcode',
        'PA': 'pa',
        'DRG': 'drg',
        'RW': 'rw',
        'CA_TYPE': 'ca_type',
        'เรียกเก็บ(1)\n(1.1)': 'claim_drg',
        'เรียกเก็บ(1)\n(1.2)': 'claim_xdrg',
        'เรียกเก็บ(1)\n(1.3)': 'claim_net',
        'เรียกเก็บ central reimburse (2)': 'claim_central_reimb',
        'ชำระเอง (3)': 'paid',
        'อัตราจ่าย/Point (4)': 'pay_point',
        'PS': 'ps_chk',
        'ล่าช้า PS (5)': 'ps_percent',
        'CCUF (6)': 'ccuf',
        'AdjRW_NHSO (7)': 'adjrw_nhso',
        'AdjRW2 (8)': 'adjrw2',
        'จ่ายชดเชย (9)': 'reimb_amt',
        'ค่าพรบ. (10)': 'act_amt',
        'เงินเดือน %': 'salary_rate',
        'จำนวนเงินเงินเดือน (11)': 'salary_amt',
        'ยอดชดเชยหลังหักเงินเดือน (12)': 'reimb_diff_salary',
        # High Cost
        'IPHC': 'iphc',
        'OPHC': 'ophc',
        # Accident & Emergency
        'OPAE': 'ae_opae',
        'IPNB': 'ae_ipnb',
        'IPUC': 'ae_ipuc',
        'IP3SSS': 'ae_ip3sss',
        'IP7SSS': 'ae_ip7sss',
        'CARAE': 'ae_carae',
        'CAREF': 'ae_caref',
        'CAREF-PUC': 'ae_caref_puc',
        # Prosthetics/Equipment
        'OPINST': 'opinst',
        'INST': 'inst',
        # Inpatient
        'IPAEC': 'ipaec',
        'IPAER': 'ipaer',
        'IPINRGC': 'ipinrgc',
        'IPINRGR': 'ipinrgr',
        'IPINSPSN': 'ipinspsn',
        'IPPRCC': 'ipprcc',
        'IPPRCC-PUC': 'ipprcc_puc',
        'IPBKK-INST': 'ipbkk_inst',
        'IP-ONTOP': 'ip_ontop',
        # DMIS
        'CATARACT': 'cataract_amt',
        'ค่าภาระงาน(สสจ.)': 'cataract_oth',
        'ค่าภาระงาน(รพ.)': 'cataract_hosp',
        'CATINST': 'dmis_catinst',
        'DMISRC\n(จำนวนเงิน)': 'dmisrc_amt',
        'DMISRC\n(ค่าภาระงาน)': 'dmisrc_workload',
        'RCUHOSC\n(จำนวนเงิน)': 'rcuhosc_amt',
        'RCUHOSC\n(ค่าภาระงาน)': 'rcuhosc_workload',
        'RCUHOSR\n(จำนวนเงิน)': 'rcuhosr_amt',
        'RCUHOSR\n(ค่าภาระงาน)': 'rcuhosr_workload',
        'LLOP': 'dmis_llop',
        'LLRGC': 'dmis_llrgc',
        'LLRGR': 'dmis_llrgr',
        'LP': 'dmis_lp',
        'STROKE-STEMI DRUG': 'dmis_stroke_drug',
        'DMIDML': 'dmis_dmidml',
        'PP': 'dmis_pp',
        'DMISHD': 'dmis_dmishd',
        'DMICNT': 'dmis_dmicnt',
        'Paliative Care': 'dmis_paliative',
        'DM': 'dmis_dm',
        # Drug
        'DRUG': 'drug',
        # OP Bangkok
        'OPBKK HC': 'opbkk_hc',
        'DENT': 'opbkk_dent',
        'DRUG.1': 'opbkk_drug',
        'FS': 'opbkk_fs',
        'OTHERS': 'opbkk_others',
        'HSUB': 'opbkk_hsub',
        'NHSO': 'opbkk_nhso',
        # Denial
        'Deny HC': 'deny_hc',
        'Deny AE': 'deny_ae',
        'Deny INST': 'deny_inst',
        'Deny IP': 'deny_ip',
        'Deny DMIS': 'deny_dmis',
        # Base Rate
        'base rate เดิม': 'baserate_old',
        'base rate ที่ได้รับเพิ่ม': 'baserate_add',
        'base rate สุทธิ': 'baserate_total',
        # Other
        'FS.1': 'fs',
        'VA': 'va',
        'Remark': 'remark',
        'AUDIT RESULTS': 'audit_results',
        'รูปแบบการจ่าย': 'payment_type',
        'SEQ NO': 'seq_no',
        'INVOICE NO': 'invoice_no',
        'INVOICE LT': 'invoice_lt',
    }

    ORF_COLUMN_MAP = {
        'REP': 'rep_no',
        'NO.': 'no',
        'TRAN_ID': 'tran_id',
        'HN': 'hn',
        'เลขประจำตัวประชาชน': 'pid',
        'ชื่อ': 'name',
        'ว/ด/ป ที่รับบริการ': 'service_date',
        'เลขที่ใบส่งต่อ': 'refer_no',
        # Hospital codes
        'รักษา(Htype1)': 'htype1',
        'รักษา(Prov1)': 'prov1',
        'รักษา(Hcode)': 'hcode',
        'รักษา(Htype2)': 'htype2',
        'รักษา(Prov2)': 'prov2',
        'ประจำ(Hmain2)': 'hmain2',
        'รับส่งต่อ(Href)': 'href',
        # Diagnosis & Procedure
        'DX': 'dx',
        'Proc.': 'proc',
        'DMIS': 'dmis',
        'HMAIN3': 'hmain3',
        'DAR': 'dar',
        'CA_TYPE': 'ca_type',
        # Billing Amounts
        'ยอดรวมค่าใช้จ่าย(เฉพาะเบิกได้) (1)': 'claim_amt',
        'เข้าเกณฑ์ central reimburse\nกรณี': 'central_reimb_case',
        'เข้าเกณฑ์ central reimburse\nจำนวนเงิน (2)': 'central_reimb_amt',
        'ชำระเอง (3)': 'paid',
        'พรบ. (4)': 'act_amt',
        # OP Refer Amounts
        'เข้าเกณฑ์ OP REFER\nรายการ OPREF (5)': 'opref_list',
        'เข้าเกณฑ์ OP REFER\nค่ารักษาอื่นๆ ก่อนปรับลด (6)': 'opref_bef_adj',
        'เข้าเกณฑ์ OP REFER\nค่ารักษาอื่นๆ หลังปรับลด (7)': 'opref_aft_adj',
        'ผลรวมทั้ง Case (8)': 'total',
        # Responsible Parties
        'ผู้รับผิดชอบ (9)=(8)\nCUP / จังหวัด (<=1600)': 'respon_cup',
        'ผู้รับผิดชอบ (9)=(8)\nสปสช (>1600)': 'respon_nhso',
        # Net Reimbursement
        'ชดเชยสุทธิ (บาท) (10=8)': 'reimb_total',
        'ชำระบัญชีโดย': 'pay_by',
        'PS': 'ps',
        # Central Reimburse Detail - OPHC
        'HC01': 'cr_ophc_hc01',
        'HC02': 'cr_ophc_hc02',
        'HC03': 'cr_ophc_hc03',
        'HC04': 'cr_ophc_hc04',
        'HC05': 'cr_ophc_hc05',
        'HC06': 'cr_ophc_hc06',
        'HC07': 'cr_ophc_hc07',
        'HC08': 'cr_ophc_hc08',
        # Other Funds
        'AE04': 'cr_ae04',
        'AE08': 'cr_carae_ae08',
        'HC09': 'cr_opinst_hc09',
        'DMISRC\n(จำนวนเงิน)': 'cr_dmisrc_amt',
        'DMISRC\n(ค่าภาระงาน)': 'cr_dmisrc_workload',
        'RCUHOSC\n(จำนวนเงิน)': 'cr_rcuhosc_amt',
        'RCUHOSC\n(ค่าภาระงาน)': 'cr_rcuhosc_workload',
        'RCUHOSR\n(จำนวนเงิน)': 'cr_rcuhosr_amt',
        'RCUHOSR\n(ค่าภาระงาน)': 'cr_rcuhosr_workload',
        'LLOP': 'cr_llop',
        'LP': 'cr_lp',
        'STROKE-STEMI DRUG': 'cr_stroke_drug',
        'DMIDML': 'cr_dmidml',
        'PP': 'cr_pp',
        'DMISHD': 'cr_dmishd',
        'Paliative Care': 'cr_paliative',
        'DRUG': 'cr_drug',
        'ONTOP': 'cr_ontop',
        'ชดเชยสุทธิ (บาท)': 'cr_total',
        'ชำระโดย': 'cr_by',
        # Detailed Expenses (19 categories x 2)
        'ค่าห้อง/ค่าอาหาร\nเบิกได้': 'oprefer_md01_claim',
        'ค่าห้อง/ค่าอาหาร\nเบิกไม่ได้': 'oprefer_md01_free',
        'อวัยวะเทียม\nเบิกได้': 'oprefer_md02_claim',
        'อวัยวะเทียม\nเบิกไม่ได้': 'oprefer_md02_free',
        'ยาและสารอาหารทางเส้นเลือด\nเบิกได้': 'oprefer_md03_claim',
        'ยาและสารอาหารทางเส้นเลือด\nเบิกไม่ได้': 'oprefer_md03_free',
        'ยาที่นำไปใช้ต่อที่บ้าน\nเบิกได้': 'oprefer_md04_claim',
        'ยาที่นำไปใช้ต่อที่บ้าน\nเบิกไม่ได้': 'oprefer_md04_free',
        'เวชภัณฑ์ที่ไม่ใช่ยา\nเบิกได้': 'oprefer_md05_claim',
        'เวชภัณฑ์ที่ไม่ใช่ยา\nเบิกไม่ได้': 'oprefer_md05_free',
        'บริการโลหิต\nเบิกได้': 'oprefer_md06_claim',
        'บริการโลหิต\nเบิกไม่ได้': 'oprefer_md06_free',
        'ตรวจวินิจฉัยทางเทคนิคการแพทย์\nเบิกได้': 'oprefer_md07_claim',
        'ตรวจวินิจฉัยทางเทคนิคการแพทย์\nเบิกไม่ได้': 'oprefer_md07_free',
        'ตรวจวินิจฉัยและรักษาทางรังสี\nเบิกได้': 'oprefer_md08_claim',
        'ตรวจวินิจฉัยและรักษาทางรังสี\nเบิกไม่ได้': 'oprefer_md08_free',
        'ตรวจวินิจฉัยโดยวิธีพิเศษ\nเบิกได้': 'oprefer_md09_claim',
        'ตรวจวินิจฉัยโดยวิธีพิเศษ\nเบิกไม่ได้': 'oprefer_md09_free',
        'อุปกรณ์และเครื่องมือทางการแพทย์\nเบิกได้': 'oprefer_md10_claim',
        'อุปกรณ์และเครื่องมือทางการแพทย์\nเบิกไม่ได้': 'oprefer_md10_free',
        'ทำหัตถการและบริการวิสัญญี\nเบิกได้': 'oprefer_md11_claim',
        'ทำหัตถการและบริการวิสัญญี\nเบิกไม่ได้': 'oprefer_md11_free',
        'ค่าบริการทางพยาบาล\nเบิกได้': 'oprefer_md12_claim',
        'ค่าบริการทางพยาบาล\nเบิกไม่ได้': 'oprefer_md12_free',
        'ค่าบริการทางทันตกรรม\nเบิกได้': 'oprefer_md13_claim',
        'ค่าบริการทางทันตกรรม\nเบิกไม่ได้': 'oprefer_md13_free',
        'ค่ากายภาพบำบัด\nเบิกได้': 'oprefer_md14_claim',
        'ค่ากายภาพบำบัด\nเบิกไม่ได้': 'oprefer_md14_free',
        'ค่าบริการฝังเข็ม\nเบิกได้': 'oprefer_md15_claim',
        'ค่าบริการฝังเข็ม\nเบิกไม่ได้': 'oprefer_md15_free',
        'ค่าห้องผ่าตัดและห้องคลอด\nเบิกได้': 'oprefer_md16_claim',
        'ค่าห้องผ่าตัดและห้องคลอด\nเบิกไม่ได้': 'oprefer_md16_free',
        'ค่าธรรมเนียมบุคลากร\nเบิกได้': 'oprefer_md17_claim',
        'ค่าธรรมเนียมบุคลากร\nเบิกไม่ได้': 'oprefer_md17_free',
        'บริการอื่นๆ และส่งเสริมป้องกัน\nเบิกได้': 'oprefer_md18_claim',
        'บริการอื่นๆ และส่งเสริมป้องกัน\nเบิกไม่ได้': 'oprefer_md18_free',
        'บริการอื่นๆ ที่ยังไม่ได้จัดหมวด\nเบิกได้': 'oprefer_md19_claim',
        'บริการอื่นๆ ที่ยังไม่ได้จัดหมวด\nเบิกไม่ได้': 'oprefer_md19_free',
        # Error & Status
        'Error Code': 'error_code',
        'Deny HC': 'deny_hc',
        'Deny AE': 'deny_ae',
        'Deny INST': 'deny_inst',
        'Deny DMIS': 'deny_dmis',
        # Other
        'VA': 'va',
        'Remark': 'remark',
        'AUDIT RESULTS': 'audit_results',
        'รูปแบบการจ่าย': 'payment_type',
        'SEQ NO': 'seq_no',
        'INVOICE NO': 'invoice_no',
        'INVOICE LT': 'invoice_lt',
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

        Args:
            file_id: File ID
            df: DataFrame with ORF data
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
            mapped = self._map_dataframe_row(row, self.ORF_COLUMN_MAP, file_id, start_row + idx)
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

    def import_file(self, filepath: str, metadata: Dict = None) -> Dict:
        """
        Import complete file

        Args:
            filepath: Path to Excel file
            metadata: Optional file metadata (will be parsed from filename if not provided)

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

        try:
            # Create import record
            file_id = self.create_import_record(metadata)

            # Read Excel file
            df = pd.read_excel(filepath, engine='xlrd')

            total_records = len(df)

            # Import data based on file type
            if file_type == 'ORF':
                imported_records = self.import_orf_batch(file_id, df)
            else:  # OP, IP, APPEAL
                imported_records = self.import_opip_batch(file_id, df)

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
