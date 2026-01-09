#!/usr/bin/env python3
"""
Generate correct column mapping from actual Excel files
Run this to fix column mapping issues
"""
import pandas as pd
from pathlib import Path

# Find an OP file
op_files = list(Path('downloads').glob('*_OP_*.xls'))
if not op_files:
    print("ERROR: No OP files found in downloads/")
    exit(1)

filepath = op_files[0]
print(f"Analyzing: {filepath.name}")

# Read Excel with correct skiprows
df = pd.read_excel(filepath, engine='xlrd', skiprows=5, nrows=2)

print(f"\nFound {len(df.columns)} columns in Excel file\n")

# Define correct mapping based on actual columns
CORRECT_OPIP_MAP = {
    # Basic columns (always present)
    'REP No.': 'rep_no',
    'ลำดับที่': 'seq',
    'TRAN_ID': 'tran_id',
    'HN': 'hn',
    'AN': 'an',
    'PID': 'pid',  # NOT 'เลขประจำตัวประชาชน'!
    'ชื่อ-สกุล': 'name',
    'ประเภทผู้ป่วย': 'ptype',
    'วันเข้ารักษา': 'dateadm',
    'วันจำหน่าย': 'datedsc',
    'ชดเชยสุทธิ': 'reimb_nhso',  # Single column
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
    # Claims with newlines
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

# Check which columns exist
existing_cols = {}
missing_cols = []

for excel_col, db_col in CORRECT_OPIP_MAP.items():
    if excel_col in df.columns:
        existing_cols[excel_col] = db_col
    else:
        missing_cols.append(excel_col)

print(f"✓ Found {len(existing_cols)}/{len(CORRECT_OPIP_MAP)} mapped columns")
if missing_cols:
    print(f"✗ Missing {len(missing_cols)} columns:")
    for col in missing_cols[:10]:
        print(f"  - {repr(col)}")

# Show sample data
print("\nSample data (first row, first 10 mapped columns):")
if len(df) > 0:
    row = df.iloc[0]
    count = 0
    for excel_col, db_col in existing_cols.items():
        if count >= 10:
            break
        val = row[excel_col] if excel_col in df.columns else None
        if pd.notna(val):
            print(f"  {db_col}: {val}")
            count += 1

print(f"\n✓ Column mapping is {'CORRECT' if len(missing_cols) == 0 else 'PARTIALLY CORRECT'}")
print(f"\nTo fix importer_v2.py: Replace OPIP_COLUMN_MAP with the mapping above")
