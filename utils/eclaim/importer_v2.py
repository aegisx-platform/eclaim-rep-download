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

    # Column mapping: E-Claim column name → Database column name (legacy, kept for compatibility)
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

    # OPIP Index-based column mapping (more reliable than name-based for multi-level headers)
    # Excel column INDEX → Database column name
    # Total: 120 columns mapped
    OPIP_COLUMN_INDEX_MAP = {
        # Basic Info (0-13)
        0: 'rep_no',                    # REP No.
        1: 'seq',                       # ลำดับที่
        2: 'tran_id',                   # TRAN_ID
        3: 'hn',                        # HN
        4: 'an',                        # AN
        5: 'pid',                       # PID
        6: 'name',                      # ชื่อ-สกุล
        7: 'ptype',                     # ประเภทผู้ป่วย
        8: 'dateadm',                   # วันเข้ารักษา
        9: 'datedsc',                   # วันจำหน่าย
        10: 'reimb_nhso',               # ชดเชยสุทธิ (สปสช.)
        11: 'reimb_agency',             # ชดเชยสุทธิ (หน่วยงาน)
        12: 'claim_from',               # ชดเชยจาก
        13: 'error_code',               # Error Code

        # Fund & Service Info (14-22)
        14: 'main_fund',                # กองทุนหลัก
        15: 'sub_fund',                 # กองทุนย่อย
        16: 'service_type',             # ประเภทบริการ
        17: 'chk_refer',                # การรับส่งต่อ
        18: 'chk_right',                # การมีสิทธิ
        19: 'chk_use_right',            # การใช้สิทธิ
        20: 'chk',                      # CHK
        21: 'main_inscl',               # สิทธิหลัก
        22: 'sub_inscl',                # สิทธิย่อย

        # Hospital Codes (23-34)
        23: 'href',                     # HREF
        24: 'hcode',                    # HCODE
        25: 'hmain',                    # HMAIN
        26: 'prov1',                    # PROV1
        27: 'rg1',                      # RG1
        28: 'hmain2',                   # HMAIN2
        29: 'prov2',                    # PROV2
        30: 'rg2',                      # RG2
        31: 'hmain3',                   # DMIS/HMAIN3
        32: 'da',                       # DA
        33: 'projcode',                 # PROJ
        34: 'pa',                       # PA

        # DRG Info (35-37)
        35: 'drg',                      # DRG
        36: 'rw',                       # RW
        37: 'ca_type',                  # CA_TYPE

        # Claim/Reimbursement (38-53)
        38: 'claim_drg',                # เรียกเก็บ (1) - กลุ่มที่ไม่ใช่ค่ารถ+ยา+อุปกรณ์
        39: 'claim_xdrg',               # เรียกเก็บ (1.2) - กลุ่มค่ารถ+ยา+อุปกรณ์
        40: 'claim_net',                # เรียกเก็บ (1.3) - รวมยอดเรียกเก็บ
        41: 'claim_central_reimb',      # เรียกเก็บ central reimburse (2)
        42: 'paid',                     # ชำระเอง (3)
        43: 'pay_point',                # อัตราจ่าย/Point (4)
        44: 'ps_chk',                   # ล่าช้า PS (5) - flag
        45: 'ps_percent',               # ล่าช้า PS (5) - เปอร์เซ็นต์
        46: 'ccuf',                     # CCUF (6)
        47: 'adjrw_nhso',               # AdjRW_NHSO (7)
        48: 'adjrw2',                   # AdjRW2 (8 = 6x7)
        49: 'reimb_amt',                # จ่ายชดเชย (9 = 4x5x8)
        50: 'act_amt',                  # ค่าพรบ. (10)
        51: 'salary_rate',              # เงินเดือน - ร้อยละ
        52: 'salary_amt',               # เงินเดือน - จำนวนเงิน (11)
        53: 'reimb_diff_salary',        # ยอดชดเชยหลังหักเงินเดือน (12 = 9-10-11)

        # HC - ค่าใช้จ่ายสูง (54-55)
        54: 'iphc',                     # IPHC
        55: 'ophc',                     # OPHC

        # AE - อุบัติเหตุฉุกเฉิน (56-63)
        56: 'ae_opae',                  # OPAE (1.1*4*5)
        57: 'ae_ipnb',                  # IPNB
        58: 'ae_ipuc',                  # IPUC
        59: 'ae_ip3sss',                # IP3SSS
        60: 'ae_ip7sss',                # IP7SSS
        61: 'ae_carae',                 # CARAE
        62: 'ae_caref',                 # CAREF
        63: 'ae_caref_puc',             # CAREF-PUC

        # INST - อวัยวะเทียม/อุปกรณ์ (64-65)
        64: 'opinst',                   # OPINST
        65: 'inst',                     # INST

        # IP - ผู้ป่วยใน (66-74)
        66: 'ipaec',                    # IPAEC
        67: 'ipaer',                    # IPAER
        68: 'ipinrgc',                  # IPINRGC
        69: 'ipinrgr',                  # IPINRGR
        70: 'ipinspsn',                 # IPINSPSN
        71: 'ipprcc',                   # IPPRCC
        72: 'ipprcc_puc',               # IPPRCC-PUC
        73: 'ipbkk_inst',               # IPBKK-INST
        74: 'ip_ontop',                 # IP-ONTOP

        # DMIS - โรคเฉพาะ (75-95)
        75: 'cataract_amt',             # CATARACT
        76: 'cataract_oth',             # CATARACT - ค่าภาระงาน(สสจ.)
        77: 'cataract_hosp',            # CATARACT - ค่าภาระงาน(รพ.)
        78: 'dmis_catinst',             # CATINST
        79: 'dmisrc_amt',               # DMISRC
        80: 'dmisrc_workload',          # DMISRC - ค่าภาระงาน
        81: 'rcuhosc_amt',              # RCUHOSC
        82: 'rcuhosc_workload',         # RCUHOSC - ค่าภาระงาน
        83: 'rcuhosr_amt',              # RCUHOSR
        84: 'rcuhosr_workload',         # RCUHOSR - ค่าภาระงาน
        85: 'dmis_llop',                # LLOP
        86: 'dmis_llrgc',               # LLRGC
        87: 'dmis_llrgr',               # LLRGR
        88: 'dmis_lp',                  # LP
        89: 'dmis_stroke_drug',         # STROKE-STEMI DRUG
        90: 'dmis_dmidml',              # DMIDML
        91: 'dmis_pp',                  # PP
        92: 'dmis_dmishd',              # DMISHD
        93: 'dmis_dmicnt',              # DMICNT
        94: 'dmis_paliative',           # Paliative Care
        95: 'dmis_dm',                  # DM

        # DRUG (96)
        96: 'drug',                     # DRUG

        # OPBKK - กรุงเทพ (97-103)
        97: 'opbkk_hc',                 # OPBKK - HC
        98: 'opbkk_dent',               # OPBKK - DENT
        99: 'opbkk_drug',               # OPBKK - DRUG
        100: 'opbkk_fs',                # OPBKK - FS
        101: 'opbkk_others',            # OPBKK - OTHERS
        102: 'opbkk_hsub',              # OPBKK - HSUB
        103: 'opbkk_nhso',              # OPBKK - NHSO

        # Deny (104-108)
        104: 'deny_hc',                 # Deny - HC
        105: 'deny_ae',                 # Deny - AE
        106: 'deny_inst',               # Deny - INST
        107: 'deny_ip',                 # Deny - IP
        108: 'deny_dmis',               # Deny - DMIS

        # Base Rate (109-111)
        109: 'baserate_old',            # base rate เดิม
        110: 'baserate_add',            # base rate ที่ได้รับเพิ่ม
        111: 'baserate_total',          # base rate สุทธิ

        # Others (112-119)
        112: 'fs',                      # FS
        113: 'va',                      # VA
        114: 'remark',                  # Remark
        115: 'audit_results',           # AUDIT RESULTS
        116: 'payment_type',            # รูปแบบการจ่าย
        117: 'seq_no',                  # SEQ NO
        118: 'invoice_no',              # INVOICE NO
        119: 'invoice_lt',              # INVOICE LT
    }

    # LGO Column mapping (อปท. - Local Government Organizations) - 58 columns
    # Note: 'REP' instead of 'REP No.', 'ชื่อ - สกุล' instead of 'ชื่อ-สกุล'
    LGO_COLUMN_MAP = {
        'REP': 'rep_no',
        'ลำดับที่': 'seq',
        'TRAN_ID': 'tran_id',
        'HN': 'hn',
        'AN': 'an',
        'PID': 'pid',
        'ชื่อ - สกุล': 'name',           # Note: spaces around dash
        'ประเภทผู้ป่วย': 'ptype',
        'วันเข้ารักษา': 'dateadm',
        'วันจำหน่าย': 'datedsc',
        'ชดเชยสุทธิ': 'reimb_nhso',
        'Error Code': 'error_code',
        'กองทุน': 'main_fund',           # Single fund column (maps to main_fund)
        'ประเภทบริการ': 'service_type',
        'การรับส่งต่อ': 'chk_refer',
        'การมีสิทธิ': 'chk_right',
        'การใช้สิทธิ': 'chk_use_right',
        'สิทธิหลัก': 'main_inscl',
        'สิทธิรอง': 'sub_inscl',          # LGO uses สิทธิรอง instead of สิทธิย่อย
        'HREF': 'href',
        'HCODE': 'hcode',
        'PROV1': 'prov1',
        'รหัสหน่วยงาน': 'org_code',       # LGO-specific
        'ชื่อหน่วยงาน': 'org_name',       # LGO-specific
        'PROJ': 'projcode',
        'PA': 'pa',
        'DRG': 'drg',
        'RW': 'rw',
        'เรียกเก็บ': 'claim_drg',
        'เบิกได้': 'claim_able',          # LGO-specific
        'เบิกไม่ได้': 'claim_unable',     # LGO-specific
        'ชำระเอง': 'paid',
        'อัตราจ่าย': 'pay_point',
        'ล่าช้า (PS)': 'ps_percent',
        'ล่าช้า (PS) เปอร์เซ็นต์': 'ps_percent2',
        'CCUF': 'ccuf',
        'AdjRW': 'adjrw_nhso',
        'พรบ.': 'act_amt',
        'กรณี': 'case_type',
        'Deny': 'deny_count',
        'ORS': 'ors',                     # LGO-specific (Override)
        'VA': 'va',
        'AUDIT RESULTS': 'audit_result',
        'SEQ NO': 'seq_no',
        'INVOICE NO': 'invoice_no',
        'INVOICE LT': 'invoice_lt',
    }

    # SSS Column mapping (ประกันสังคม - Social Security Scheme) - 74 columns
    SSS_COLUMN_MAP = {
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
        'กรณีที่เบิก': 'claim_case',       # SSS-specific
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
        'HMAIN2': 'hmain2',
        'PROV2': 'prov2',
        'PROJ': 'projcode',
        'HTYPE': 'htype',                 # SSS-specific
        'AESTATUS': 'ae_status',          # SSS-specific
        'IPTYPE': 'iptype',               # SSS-specific
        'HSEND': 'hsend',                 # SSS-specific
        'DRG': 'drg',
        'RW(1)': 'rw',
        'AdjRW\n(2)': 'adjrw_nhso',
        'ชำระเอง': 'paid',
        'อัตราจ่ายที่กำหนด\n(3)': 'pay_point',
        'ระยะเวลาส่งข้อมูล (PS)': 'ps_percent',
        'ขอเบิกค่าบริการ': 'claim_request',  # SSS-specific
        'IP': 'ip_amt',
        'OP': 'op_amt',
        'AE': 'ae_amt',
        'HC': 'hc_amt',
        'INT': 'int_amt',
        'ON TOP': 'on_top_amt',
        'PP': 'pp_amt',
        'รวมเงินค่าบริการทั้งหมด': 'total_service_amt',  # SSS-specific
        'Error Code': 'error_code',
        'Deny': 'deny_count',
        'VA': 'va',
        'REMARK': 'remark',
        'AUDIT RESULTS': 'audit_result',
        'SEQ NO': 'seq_no',
        'INVOICE NO': 'invoice_no',
        'INVOICE LT': 'invoice_lt',
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

    def get_column_map_for_type(self, file_type: str) -> Dict[str, str]:
        """
        Get the appropriate column mapping based on file type.

        Args:
            file_type: File type (OP, IP, OPLGO, IPLGO, OPSSS, IPSSS, etc.)

        Returns:
            Column mapping dict for the file type
        """
        # LGO variants (อปท.)
        if file_type in ['OPLGO', 'IPLGO']:
            return self.LGO_COLUMN_MAP

        # SSS variants (ประกันสังคม)
        if file_type in ['OPSSS', 'IPSSS']:
            return self.SSS_COLUMN_MAP

        # Default: UCS (OP, IP) and APPEAL types use OPIP_COLUMN_MAP
        return self.OPIP_COLUMN_MAP

    def _derive_scheme_from_file_type(self, file_type: str) -> str:
        """
        Derive insurance scheme from file type.

        Args:
            file_type: File type (OP, IP, OPLGO, IPLGO, OPSSS, IPSSS, ORF, etc.)

        Returns:
            Scheme code: 'UCS', 'LGO', 'SSS', 'OFC'
        """
        if not file_type:
            return 'UCS'

        file_type_upper = file_type.upper()

        # LGO variants (อปท.)
        if 'LGO' in file_type_upper:
            return 'LGO'

        # SSS variants (ประกันสังคม)
        if 'SSS' in file_type_upper:
            return 'SSS'

        # OFC variants (ข้าราชการ)
        if 'OFC' in file_type_upper:
            return 'OFC'

        # Default: UCS (หลักประกันสุขภาพถ้วนหน้า)
        return 'UCS'

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

    def _map_orf_row_by_index(self, df_row, file_id: int, row_number: int, scheme: str = None) -> Dict:
        """
        Map ORF DataFrame row to database columns using column INDEX (position-based)
        ORF files have complex multi-level headers that can't be reliably mapped by name

        Args:
            df_row: DataFrame row (Series) with integer position-based index
            file_id: File ID
            row_number: Row number
            scheme: Insurance scheme (UCS, OFC, SSS, LGO)

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
            'row_number': row_number,
            'scheme': scheme
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

    def _map_opip_row_by_index(self, df_row, file_id: int, row_number: int, scheme: str = None) -> Dict:
        """
        Map OP/IP DataFrame row to database columns using column INDEX (position-based)
        More reliable than name-based mapping for Excel files with multi-level headers

        Args:
            df_row: DataFrame row (Series) with integer position-based index
            file_id: File ID
            row_number: Row number
            scheme: Insurance scheme (UCS, OFC, SSS, LGO)

        Returns:
            Mapped dict
        """
        # Date columns that need parsing
        date_columns = ['dateadm', 'datedsc', 'inp_date']

        # String field max lengths (from schema)
        max_lengths = {
            'chk_refer': 1, 'chk_right': 1, 'chk_use_right': 1, 'chk': 1,
            'da': 1, 'pa': 1, 'ps_chk': 1,
            'service_type': 2, 'ca_type': 5, 'ptype': 5,
            'main_inscl': 5, 'sub_inscl': 5, 'prov1': 5, 'rg1': 5,
            'prov2': 5, 'rg2': 5, 'salary_rate': 5,
            'href': 10, 'hcode': 10, 'hmain': 10, 'hmain2': 10, 'hmain3': 10,
            'drg': 10, 'deny_hc': 10, 'deny_ae': 10, 'deny_inst': 10,
            'deny_ip': 10, 'deny_dmis': 10,
            'rep_no': 15, 'tran_id': 15, 'hn': 15, 'an': 15, 'seq_no': 15,
            'pid': 20, 'invoice_no': 20, 'invoice_lt': 20,
            'claim_from': 50, 'payment_type': 255,
            'name': 100, 'main_fund': 100, 'sub_fund': 100, 'projcode': 100,
            'error_code': 100, 'remark': 100, 'audit_results': 255,
            'opbkk_hsub': 100, 'opbkk_nhso': 100
        }

        mapped = {
            'file_id': file_id,
            'row_number': row_number,
            'scheme': scheme
        }

        for col_idx, db_col in self.OPIP_COLUMN_INDEX_MAP.items():
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
                    elif db_col in ['tran_id', 'hn', 'an', 'pid', 'rep_no', 'seq_no']:
                        str_value = str(value).strip()
                        # Remove .0 suffix if present (pandas converts int to float)
                        if str_value.endswith('.0'):
                            str_value = str_value[:-2]
                        # Apply max length
                        max_len = max_lengths.get(db_col, 20)
                        mapped[db_col] = str_value[:max_len] if str_value else None
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

    def import_opip_batch_by_index(self, file_id: int, df, start_row: int = 0, file_type: str = None) -> int:
        """
        Import batch of OP/IP records from DataFrame using index-based column mapping
        More reliable than name-based mapping for multi-level header Excel files

        Args:
            file_id: File ID
            df: DataFrame with claim data (read with header=None)
            start_row: Starting row number
            file_type: File type for determining scheme (OP, IP, etc.)

        Returns:
            Number of successfully imported records
        """
        if df.empty:
            return 0

        # Determine scheme based on file_type
        scheme = self.get_scheme_for_type(file_type) if file_type else 'UCS'

        # Map all rows using index-based mapping
        mapped_records = []
        for idx, row in df.iterrows():
            mapped = self._map_opip_row_by_index(row, file_id, start_row + idx, scheme=scheme)
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
            logger.info(f"Imported {len(mapped_records)} OP/IP records (index-based)")
            return len(mapped_records)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Failed to import OP/IP batch (index-based): {e}")
            raise

    def get_scheme_for_type(self, file_type: str) -> str:
        """
        Get the insurance scheme code based on file type.

        Args:
            file_type: File type (OP, IP, OPLGO, IPLGO, OPSSS, IPSSS, etc.)

        Returns:
            Scheme code: 'UCS', 'LGO', or 'SSS'
        """
        if file_type in ['OPLGO', 'IPLGO']:
            return 'LGO'
        elif file_type in ['OPSSS', 'IPSSS']:
            return 'SSS'
        else:
            return 'UCS'

    def import_opip_batch(self, file_id: int, df, start_row: int = 0, column_map: Dict = None, file_type: str = None) -> int:
        """
        Import batch of OP/IP/LGO/SSS records from DataFrame

        Args:
            file_id: File ID
            df: DataFrame with claim data
            start_row: Starting row number
            column_map: Column mapping dict (defaults to OPIP_COLUMN_MAP)
            file_type: File type for determining scheme (OP, IP, OPLGO, etc.)

        Returns:
            Number of successfully imported records
        """
        if df.empty:
            return 0

        # Use provided column_map or default to OPIP_COLUMN_MAP
        if column_map is None:
            column_map = self.OPIP_COLUMN_MAP

        # Determine scheme based on file_type
        scheme = self.get_scheme_for_type(file_type) if file_type else 'UCS'

        # Map all rows
        mapped_records = []
        for idx, row in df.iterrows():
            mapped = self._map_dataframe_row(row, column_map, file_id, start_row + idx)
            mapped['scheme'] = scheme  # Add scheme to each record
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

    def import_orf_batch(self, file_id: int, df, start_row: int = 0, file_type: str = 'ORF') -> int:
        """
        Import batch of ORF records from DataFrame
        Uses index-based column mapping for ORF's complex multi-level headers

        Args:
            file_id: File ID
            df: DataFrame with ORF data (read without header, columns are positional)
            start_row: Starting row number
            file_type: File type to derive scheme (ORF, ORFLGO, ORFSSS, etc.)

        Returns:
            Number of successfully imported records
        """
        if df.empty:
            return 0

        # Derive scheme from file_type
        scheme = self._derive_scheme_from_file_type(file_type)

        # Map all rows using index-based mapping
        mapped_records = []
        for idx, row in df.iterrows():
            mapped = self._map_orf_row_by_index(row, file_id, start_row + idx, scheme=scheme)
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
            if file_type == 'ORF' or 'ORF' in file_type:
                # ORF files have multi-level headers at rows 5, 7, and 8
                # Skip header rows (0-8) and read data starting from row 9
                # Use header=None to get positional column indices
                df = pd.read_excel(filepath, engine='xlrd', header=None, skiprows=9)

                # Filter out empty rows (check column 2 which is TRAN_ID)
                df = df[df.iloc[:, 2].notna()]

                # Also filter out footer/summary rows (usually have text in first column)
                # Check if column 0 (REP) looks like a valid REP number
                df = df[df.iloc[:, 0].apply(lambda x: str(x).strip() != '' and str(x).strip() != 'nan')]
            elif file_type in ['OP', 'IP']:
                # OP/IP UCS files: Use index-based mapping for complete column coverage
                # Skip first 5 rows (report header) + 2 header rows + 1 empty row
                # Header structure: row 5 = main header, row 6 = sub-header, row 7 = empty/units
                df = pd.read_excel(filepath, engine='xlrd', header=None, skiprows=8)

                # Filter out empty rows (check column 2 which is TRAN_ID)
                df = df[df.iloc[:, 2].notna()]

                # Filter out footer/summary rows
                df = df[df.iloc[:, 0].apply(lambda x: str(x).strip() != '' and str(x).strip() != 'nan')]
            else:
                # LGO/SSS/APPEAL files: Use name-based mapping (legacy support)
                df = pd.read_excel(filepath, engine='xlrd', skiprows=list(range(0,5)) + [6,7])
                # Remove empty rows
                if 'TRAN_ID' in df.columns:
                    df = df.dropna(subset=['TRAN_ID'])

            total_records = len(df)

            # Import data based on file type
            if file_type == 'ORF' or 'ORF' in file_type:
                imported_records = self.import_orf_batch(file_id, df, file_type=file_type)
            elif file_type in ['OP', 'IP']:
                # Use index-based mapping for complete 120-column coverage
                imported_records = self.import_opip_batch_by_index(file_id, df, file_type=file_type)
            else:  # OPLGO, IPLGO, OPSSS, IPSSS, APPEAL variants
                # Use name-based mapping for variants (legacy support)
                column_map = self.get_column_map_for_type(file_type)
                imported_records = self.import_opip_batch(file_id, df, column_map=column_map, file_type=file_type)

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


def import_files_parallel(
    filepaths: list,
    db_config: Dict,
    db_type: str = None,
    max_workers: int = 3,
    progress_callback = None
) -> Dict:
    """
    Import multiple E-Claim files in parallel

    Args:
        filepaths: List of file paths to import
        db_config: Database configuration
        db_type: Database type ('postgresql' or 'mysql')
        max_workers: Maximum number of parallel imports
        progress_callback: Optional callback for progress updates

    Returns:
        Dict with overall import results
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    total_files = len(filepaths)
    results = []
    completed = 0
    failed = 0
    total_records = 0

    logger.info(f"Starting parallel import of {total_files} files with {max_workers} workers")

    def import_single_file(filepath):
        """Import a single file"""
        try:
            with EClaimImporterV2(db_config, db_type) as importer:
                result = importer.import_file(filepath)
            return {'filepath': filepath, 'success': True, 'result': result}
        except Exception as e:
            logger.error(f"Error importing {filepath}: {e}")
            return {'filepath': filepath, 'success': False, 'error': str(e)}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(import_single_file, fp): fp for fp in filepaths}

        for future in as_completed(futures):
            result = future.result()
            results.append(result)

            if result['success']:
                completed += 1
                if result.get('result'):
                    total_records += result['result'].get('total_records', 0)
            else:
                failed += 1

            if progress_callback:
                try:
                    progress_callback({
                        'total': total_files,
                        'completed': completed,
                        'failed': failed,
                        'total_records': total_records,
                    })
                except Exception:
                    pass

    logger.info(f"Parallel import completed: {completed} success, {failed} failed, {total_records} total records")

    return {
        'total_files': total_files,
        'completed': completed,
        'failed': failed,
        'total_records': total_records,
        'results': results,
    }


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
