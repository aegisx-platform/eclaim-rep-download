#!/usr/bin/env python3
"""
STM (Statement) Parser
Parse NHSO Statement Excel files for import
"""

import os
import re
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class STMParser:
    """
    Parse NHSO Statement Excel files

    Handles both IP and OP statement files with multiple sheets:
    - รายงานพึงรับ (Receivable Summary)
    - รายงานสรุป (REP Summary)
    - รายละเอียด (Detail Records) - normal and appeal
    - ผู้พิการ D1 sheets (OP only)
    """

    def __init__(self, filepath: str):
        """
        Initialize parser

        Args:
            filepath: Path to STM Excel file
        """
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.metadata = self._parse_filename()
        self.xl = None

    def _parse_filename(self) -> Dict:
        """
        Parse metadata from STM filename

        Filename format: STM_{HCODE}_{TYPE}{SCHEME}{YYYYMM}_{SEQ}.xls
        Examples:
        - STM_10670_IPUCS256811_01.xls
        - STM_10670_OPUCS256812_02.xls

        Returns:
            Dict with parsed metadata
        """
        metadata = {
            'filename': self.filename,
            'file_type': None,      # IP_STM or OP_STM
            'scheme': None,         # UCS, OFC, SSS, LGO
            'hospital_code': None,
            'statement_month': None,
            'statement_year': None,
            'sequence': None
        }

        # Pattern: STM_HCODE_TYPESCHEMEYYYYMM_SEQ.xls
        match = re.match(
            r'STM_(\d+)_(IP|OP)(UCS|OFC|SSS|LGO)(\d{4})(\d{2})_(\d+)\.xls',
            self.filename,
            re.IGNORECASE
        )

        if match:
            metadata['hospital_code'] = match.group(1)
            metadata['file_type'] = f"{match.group(2).upper()}_STM"
            metadata['scheme'] = match.group(3).upper()
            metadata['statement_year'] = int(match.group(4))
            metadata['statement_month'] = int(match.group(5))
            metadata['sequence'] = match.group(6)

        return metadata

    def _open_file(self):
        """Open Excel file"""
        if self.xl is None:
            self.xl = pd.ExcelFile(self.filepath)

    def get_sheet_names(self) -> List[str]:
        """Get list of sheet names"""
        self._open_file()
        return self.xl.sheet_names

    def _parse_header_info(self, df: pd.DataFrame) -> Dict:
        """
        Parse header information from first rows

        Typical structure:
        Row 1: Report date/time
        Row 3: Hospital code and name
        Row 4: Province
        Row 6: Document number

        Returns:
            Dict with header info
        """
        info = {
            'report_date': None,
            'hospital_code': None,
            'hospital_name': None,
            'province_code': None,
            'province_name': None,
            'document_no': None
        }

        try:
            # Row 1: Report date (ออกรายงานวันที่ DD/MM/YYYY เวลา HH:MM)
            if len(df) > 1:
                date_str = str(df.iloc[1, 0])
                match = re.search(r'(\d{2}/\d{2}/\d{4})\s+เวลา\s+(\d{2}:\d{2})', date_str)
                if match:
                    try:
                        info['report_date'] = datetime.strptime(
                            f"{match.group(1)} {match.group(2)}",
                            '%d/%m/%Y %H:%M'
                        )
                    except ValueError:
                        pass

            # Row 3: Hospital (โรงพยาบาล HCODE ชื่อ)
            if len(df) > 3:
                hosp_str = str(df.iloc[3, 0])
                match = re.search(r'โรงพยาบาล\s+(\d+)\s+(.*)', hosp_str)
                if match:
                    info['hospital_code'] = match.group(1)
                    info['hospital_name'] = match.group(2).strip()

            # Row 4: Province (จังหวัด CODE ชื่อ)
            if len(df) > 4:
                prov_str = str(df.iloc[4, 0])
                match = re.search(r'จังหวัด\s+(\d+)\s+(.*)', prov_str)
                if match:
                    info['province_code'] = match.group(1)
                    info['province_name'] = match.group(2).strip()

            # Row 6: Document number (เลขที่เอกสาร ...)
            if len(df) > 6:
                doc_str = str(df.iloc[6, 0])
                match = re.search(r'เลขที่เอกสาร\s+(.+)', doc_str)
                if match:
                    info['document_no'] = match.group(1).strip()

        except Exception as e:
            logger.warning(f"Error parsing header info: {e}")

        return info

    def parse_receivable_summary(self) -> List[Dict]:
        """
        Parse รายงานพึงรับ sheet (Receivable Summary)

        Returns list of summary records (normal and appeal sections)
        """
        self._open_file()

        # Find the receivable summary sheet
        sheet_name = None
        for name in self.xl.sheet_names:
            if 'รายงานพึงรับ' in name and 'ผู้พิการ' not in name:
                sheet_name = name
                break

        if not sheet_name:
            logger.warning("Receivable summary sheet not found")
            return []

        df = pd.read_excel(self.filepath, sheet_name=sheet_name, header=None)

        # Parse header info
        header_info = self._parse_header_info(df)

        summaries = []
        current_data_type = 'normal'

        for idx, row in df.iterrows():
            # Check for data type markers
            cell0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''

            if 'ข้อมูลปกติ' in cell0:
                current_data_type = 'normal'
                continue
            elif 'ข้อมูลอุทธรณ์' in cell0:
                current_data_type = 'appeal'
                continue
            elif 'ผู้พิการ D1' in cell0:
                current_data_type = 'disabled_d1'
                continue

            # Check if this is a data row (ผู้ป่วยใน or ผู้ป่วยนอก)
            if cell0 in ['ผู้ป่วยใน', 'ผู้ป่วยนอก']:
                patient_type = 'inpatient' if cell0 == 'ผู้ป่วยใน' else 'outpatient'

                summary = {
                    'data_type': current_data_type,
                    'patient_type': patient_type,
                    'rep_count': self._parse_number(row.iloc[1]),
                    'patient_count': self._parse_number(row.iloc[2]),
                    'total_adjrw': self._parse_decimal(row.iloc[3]),
                    'total_paid': self._parse_decimal(row.iloc[4]),
                    'salary_deduction': self._parse_decimal(row.iloc[5]) if len(row) > 5 else 0,
                    'adjrw_paid_deduction': self._parse_decimal(row.iloc[6]) if len(row) > 6 else 0,
                    **header_info
                }
                summaries.append(summary)

        return summaries

    def parse_rep_summary(self) -> List[Dict]:
        """
        Parse รายงานสรุป sheet (REP Summary by REP NO)

        Returns list of REP summary records
        """
        self._open_file()

        # Find the REP summary sheet
        sheet_name = None
        file_type = self.metadata.get('file_type', '')

        for name in self.xl.sheet_names:
            if 'รายงานสรุป' in name and 'ผู้พิการ' not in name:
                # Match IP or OP based on file type
                if ('IP' in file_type and 'IP' in name) or ('OP' in file_type and 'OP' in name):
                    sheet_name = name
                    break

        if not sheet_name:
            logger.warning("REP summary sheet not found")
            return []

        df = pd.read_excel(self.filepath, sheet_name=sheet_name, header=None)

        summaries = []
        current_data_type = 'normal'
        data_start_row = 15  # Data typically starts at row 15 (0-indexed)

        for idx, row in df.iterrows():
            # Check for data type markers
            cell0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''

            if 'ข้อมูลปกติ' in cell0:
                current_data_type = 'normal'
                continue
            elif 'ข้อมูลอุทธรณ์' in cell0:
                current_data_type = 'appeal'
                continue
            elif 'ผู้พิการ D1' in cell0:
                current_data_type = 'disabled_d1'
                continue

            # Skip header rows and empty rows
            if idx < 15:
                continue

            # Check if this is a data row (has period format like 6811_IP_01)
            period = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not re.match(r'\d{4}_[IO]P_\d+', period):
                continue

            summary = {
                'data_type': current_data_type,
                'period': period,
                'hcode': str(row.iloc[1]) if pd.notna(row.iloc[1]) else None,
                'rep_no': str(row.iloc[2]) if pd.notna(row.iloc[2]) else None,
                'claim_type': str(row.iloc[3]) if pd.notna(row.iloc[3]) else None,
                'total_passed': self._parse_number(row.iloc[4]),
                'amount_claimed': self._parse_decimal(row.iloc[5]),
                'prb_amount': self._parse_decimal(row.iloc[6]),
                'receivable_op': self._parse_decimal(row.iloc[7]),
                'receivable_ip_calc': self._parse_decimal(row.iloc[8]) if len(row) > 8 else 0,
                'receivable_ip_paid': self._parse_decimal(row.iloc[9]) if len(row) > 9 else 0,
                'hc_amount': self._parse_decimal(row.iloc[10]) if len(row) > 10 else 0,
                'hc_drug': self._parse_decimal(row.iloc[11]) if len(row) > 11 else 0,
                'ae_amount': self._parse_decimal(row.iloc[12]) if len(row) > 12 else 0,
                'ae_drug': self._parse_decimal(row.iloc[13]) if len(row) > 13 else 0,
                'inst_amount': self._parse_decimal(row.iloc[14]) if len(row) > 14 else 0,
                'dmis_calc': self._parse_decimal(row.iloc[15]) if len(row) > 15 else 0,
                'dmis_paid': self._parse_decimal(row.iloc[16]) if len(row) > 16 else 0,
                'dmis_drug': self._parse_decimal(row.iloc[17]) if len(row) > 17 else 0,
                'palliative_care': self._parse_decimal(row.iloc[18]) if len(row) > 18 else 0,
                'dmishd_amount': self._parse_decimal(row.iloc[19]) if len(row) > 19 else 0,
                'pp_amount': self._parse_decimal(row.iloc[20]) if len(row) > 20 else 0,
                'fs_amount': self._parse_decimal(row.iloc[21]) if len(row) > 21 else 0,
                'opbkk_amount': self._parse_decimal(row.iloc[22]) if len(row) > 22 else 0,
                'total_receivable': self._parse_decimal(row.iloc[23]) if len(row) > 23 else 0,
                'covid_amount': self._parse_decimal(row.iloc[24]) if len(row) > 24 else 0,
                'data_source': str(row.iloc[25]).strip() if len(row) > 25 and pd.notna(row.iloc[25]) else None,
            }
            summaries.append(summary)

        return summaries

    def parse_claim_details(self, data_type: str = 'normal') -> Tuple[List[Dict], Dict]:
        """
        Parse รายละเอียด sheet (Detail Records)

        Args:
            data_type: 'normal', 'appeal', or 'disabled_d1'

        Returns:
            Tuple of (list of claim records, header info)
        """
        self._open_file()

        # Find the appropriate detail sheet
        sheet_name = None
        file_type = self.metadata.get('file_type', '')
        ip_or_op = 'IP' if 'IP' in file_type else 'OP'

        for name in self.xl.sheet_names:
            if data_type == 'normal' and 'รายละเอียด' in name and 'ข้อมูลปกติ' in name:
                if ip_or_op in name:
                    sheet_name = name
                    break
            elif data_type == 'appeal' and 'รายละเอียด' in name and 'อุทธรณ์' in name:
                if ip_or_op in name:
                    sheet_name = name
                    break
            elif data_type == 'disabled_d1' and 'รายละเอียด' in name and 'ผู้พิการ D1' in name:
                sheet_name = name
                break

        if not sheet_name:
            logger.warning(f"Detail sheet not found for data_type={data_type}")
            return [], {}

        df = pd.read_excel(self.filepath, sheet_name=sheet_name, header=None)

        # Parse header info
        header_info = self._parse_header_info(df)

        claims = []
        data_start_row = 14  # Data typically starts at row 14 (0-indexed)

        for idx, row in df.iterrows():
            if idx < data_start_row:
                continue

            # Check if this is a data row (has REP number format)
            rep_no = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ''
            if not rep_no or not re.match(r'\d+', rep_no):
                continue

            # Skip total rows
            if 'รวม' in rep_no or 'nan' in rep_no.lower():
                continue

            claim = {
                'data_type': data_type,
                'row_number': idx,
                'rep_no': rep_no,
                'seq': self._parse_number(row.iloc[1]),
                'tran_id': self._clean_id(row.iloc[2]),
                'hn': self._clean_id(row.iloc[3]),
                'an': self._clean_id(row.iloc[4]) if pd.notna(row.iloc[4]) else None,
                'pid': self._clean_id(row.iloc[5]),
                'patient_name': str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else None,
                'date_admit': self._parse_datetime(row.iloc[7]),
                'date_discharge': self._parse_datetime(row.iloc[8]) if pd.notna(row.iloc[8]) else None,
                'main_inscl': str(row.iloc[9]).strip() if pd.notna(row.iloc[9]) else None,
                'proj_code': str(row.iloc[10]).strip() if pd.notna(row.iloc[10]) else None,
                'amount_claimed': self._parse_decimal(row.iloc[11]),
                'fund_ip_prb': self._parse_decimal(row.iloc[12]),
                'adjrw': self._parse_decimal(row.iloc[13]),
                'late_penalty': self._parse_number(row.iloc[14]),
                # Column 15 is blank/NaN
                'ccuf': self._parse_decimal(row.iloc[16]) if len(row) > 16 else 0,
                'adjrw2': self._parse_decimal(row.iloc[17]) if len(row) > 17 else 0,
                'payment_rate': self._parse_decimal(row.iloc[18]) if len(row) > 18 else 0,
                'salary_deduction': self._parse_decimal(row.iloc[19]) if len(row) > 19 else 0,
                'paid_after_deduction': self._parse_decimal(row.iloc[20]) if len(row) > 20 else 0,
                'receivable_op': self._parse_decimal(row.iloc[21]) if len(row) > 21 else 0,
                'receivable_ip_calc': self._parse_decimal(row.iloc[22]) if len(row) > 22 else 0,
                'receivable_ip_paid': self._parse_decimal(row.iloc[23]) if len(row) > 23 else 0,
                'hc_amount': self._parse_decimal(row.iloc[24]) if len(row) > 24 else 0,
                'hc_drug': self._parse_decimal(row.iloc[25]) if len(row) > 25 else 0,
                'ae_amount': self._parse_decimal(row.iloc[26]) if len(row) > 26 else 0,
                'ae_drug': self._parse_decimal(row.iloc[27]) if len(row) > 27 else 0,
                'inst_amount': self._parse_decimal(row.iloc[28]) if len(row) > 28 else 0,
                'dmis_calc': self._parse_decimal(row.iloc[29]) if len(row) > 29 else 0,
                'dmis_paid': self._parse_decimal(row.iloc[30]) if len(row) > 30 else 0,
                'dmis_drug': self._parse_decimal(row.iloc[31]) if len(row) > 31 else 0,
                'palliative_care': self._parse_decimal(row.iloc[32]) if len(row) > 32 else 0,
                'dmishd_amount': self._parse_decimal(row.iloc[33]) if len(row) > 33 else 0,
                'pp_amount': self._parse_decimal(row.iloc[34]) if len(row) > 34 else 0,
                'fs_amount': self._parse_decimal(row.iloc[35]) if len(row) > 35 else 0,
                'opbkk_amount': self._parse_decimal(row.iloc[36]) if len(row) > 36 else 0,
                'total_compensation': self._parse_decimal(row.iloc[37]) if len(row) > 37 else 0,
                'va_amount': self._parse_decimal(row.iloc[38]) if len(row) > 38 else 0,
                'covid_amount': self._parse_decimal(row.iloc[39]) if len(row) > 39 else 0,
                'data_source': str(row.iloc[40]).strip() if len(row) > 40 and pd.notna(row.iloc[40]) else None,
                'seq_no': str(row.iloc[41]).strip() if len(row) > 41 and pd.notna(row.iloc[41]) else None,
            }

            # Only add if we have a valid tran_id
            if claim['tran_id']:
                claims.append(claim)

        return claims, header_info

    def parse_all(self) -> Dict:
        """
        Parse all data from the STM file

        Returns:
            Dict with all parsed data
        """
        result = {
            'metadata': self.metadata,
            'header_info': {},
            'receivable_summary': [],
            'rep_summary': [],
            'claims_normal': [],
            'claims_appeal': [],
            'claims_disabled_d1': []
        }

        # Parse receivable summary
        result['receivable_summary'] = self.parse_receivable_summary()

        # Parse REP summary
        result['rep_summary'] = self.parse_rep_summary()

        # Parse claim details
        claims_normal, header_info = self.parse_claim_details('normal')
        result['claims_normal'] = claims_normal
        result['header_info'] = header_info

        claims_appeal, _ = self.parse_claim_details('appeal')
        result['claims_appeal'] = claims_appeal

        # Parse disabled D1 for OP files
        if 'OP' in self.metadata.get('file_type', ''):
            claims_d1, _ = self.parse_claim_details('disabled_d1')
            result['claims_disabled_d1'] = claims_d1

        return result

    def _parse_number(self, value) -> int:
        """Parse integer from value"""
        if pd.isna(value):
            return 0
        try:
            # Remove commas and convert
            return int(float(str(value).replace(',', '').strip()))
        except (ValueError, TypeError):
            return 0

    def _parse_decimal(self, value) -> float:
        """Parse decimal from value"""
        if pd.isna(value):
            return 0.0
        try:
            # Remove commas and convert
            return float(str(value).replace(',', '').strip())
        except (ValueError, TypeError):
            return 0.0

    def _clean_id(self, value) -> Optional[str]:
        """Clean ID field (remove .0 suffix from float conversion)"""
        if pd.isna(value):
            return None
        str_value = str(value).strip()
        if str_value.endswith('.0'):
            str_value = str_value[:-2]
        if str_value.lower() == 'nan' or str_value == '':
            return None
        return str_value

    def _parse_datetime(self, value) -> Optional[datetime]:
        """Parse datetime from Thai format"""
        if pd.isna(value):
            return None

        # Handle datetime objects directly
        if hasattr(value, 'to_pydatetime'):
            return value.to_pydatetime()
        elif isinstance(value, datetime):
            return value

        try:
            str_value = str(value).strip()
            # Try format: DD/MM/YYYY HH:MM:SS
            return datetime.strptime(str_value, '%d/%m/%Y %H:%M:%S')
        except ValueError:
            try:
                # Try format: DD/MM/YYYY
                return datetime.strptime(str_value, '%d/%m/%Y')
            except ValueError:
                return None
