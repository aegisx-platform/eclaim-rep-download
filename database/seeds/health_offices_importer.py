#!/usr/bin/env python3
"""
Health Offices Seed Data Importer
Imports health offices from Excel file into the database.

Usage:
    python database/seeds/health_offices_importer.py [path_to_excel]

If no path provided, looks for:
    1. database/seeds/data/health_office.xlsx
    2. /app/database/seeds/data/health_office.xlsx (Docker)
"""

import os
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.database import get_db_config, DB_TYPE


# Column mapping: Excel column -> Database column
COLUMN_MAP = {
    'ชื่อ': 'name',
    'รหัส 9 หลักใหม่': 'hcode9_new',
    'รหัส 9 หลัก': 'hcode9',
    'รหัส 5 หลัก': 'hcode5',
    'เลขอนุญาตให้ประกอบสถานบริการสุขภาพ 11 หลัก': 'license_no',
    'ประเภทองค์กร': 'org_type',
    'ประเภทหน่วยบริการสุขภาพ': 'service_type',
    'สังกัด': 'affiliation',
    'แผนก/กรม': 'department',
    'ระดับโรงพยาบาล': 'hospital_level',
    'เตียงที่ใช้จริง': 'actual_beds',
    'สถานะการใช้งาน': 'status',
    'เขตบริการ': 'health_region',
    'ที่อยู่': 'address',
    'รหัสจังหวัด': 'province_code',
    'จังหวัด': 'province',
    'รหัสอำเภอ': 'district_code',
    'อำเภอ/เขต': 'district',
    'รหัสตำบล': 'subdistrict_code',
    'ตำบล/แขวง': 'subdistrict',
    'หมู่': 'moo',
    'รหัสไปรษณีย์': 'postal_code',
    'แม่ข่าย': 'parent_code',
    'วันที่ก่อตั้ง': 'established_date',
    'วันที่ปิดบริการ': 'closed_date',
    'อัพเดตล่าสุด(เริ่ม 05/09/2566)': 'source_updated_at',
}


def import_health_offices(excel_path: str, batch_size: int = 1000) -> dict:
    """
    Import health offices from Excel file.

    Returns:
        dict with import statistics
    """
    import pandas as pd
    import hashlib

    print(f"[seed] Reading Excel file: {excel_path}")
    df = pd.read_excel(excel_path)
    print(f"[seed] Found {len(df)} records")

    # Rename columns
    df = df.rename(columns=COLUMN_MAP)

    # Keep only mapped columns
    valid_cols = [c for c in COLUMN_MAP.values() if c in df.columns]
    df = df[valid_cols]

    # Clean data
    df = df.fillna('')

    # Convert numeric columns
    for col in ['actual_beds', 'province_code', 'district_code', 'subdistrict_code']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)

    # Convert code columns to string and clean
    for col in ['hcode5', 'hcode9', 'hcode9_new', 'postal_code', 'moo']:
        if col in df.columns:
            df[col] = df[col].astype(str).replace('nan', '').replace('0.0', '').replace('0', '')

    # Convert date columns (Thai format DD/MM/YYYY to YYYY-MM-DD)
    for col in ['established_date', 'closed_date', 'source_updated_at']:
        if col in df.columns:
            def parse_date(val):
                if pd.isna(val) or val in ['', 'nan', 'NaT']:
                    return None
                try:
                    # Try DD/MM/YYYY format
                    if isinstance(val, str) and '/' in val:
                        parts = val.split('/')
                        if len(parts) == 3:
                            day, month, year = parts
                            # Convert Buddhist Era to Gregorian if needed
                            year = int(year)
                            if year > 2500:
                                year -= 543
                            return f"{year:04d}-{int(month):02d}-{int(day):02d}"
                    return None
                except:
                    return None
            df[col] = df[col].apply(parse_date)

    # Generate hcode5 for records without one (using hash of name + province + district + address)
    def generate_hcode5(row, idx):
        if row.get('hcode5') and row['hcode5'] not in ['', 'nan']:
            return row['hcode5']
        # Generate unique code from name + location + address + index for uniqueness
        key = f"{row.get('name', '')}-{row.get('province', '')}-{row.get('district', '')}-{row.get('address', '')}-{idx}"
        hash_val = hashlib.md5(key.encode()).hexdigest()[:8]
        return f"G{hash_val}"  # G prefix = Generated

    df['hcode5'] = [generate_hcode5(row, idx) for idx, row in df.iterrows()]

    # Verify no duplicates
    dupes = df['hcode5'].duplicated().sum()
    if dupes > 0:
        print(f"[seed] Warning: {dupes} duplicate hcode5 found, making unique...")
        # Add suffix for duplicates
        seen = {}
        new_codes = []
        for code in df['hcode5']:
            if code in seen:
                seen[code] += 1
                new_codes.append(f"{code}_{seen[code]}")
            else:
                seen[code] = 0
                new_codes.append(code)
        df['hcode5'] = new_codes

    # Connect to database
    config = get_db_config()

    if DB_TYPE == 'postgresql':
        import psycopg2
        conn = psycopg2.connect(**config)
    else:
        import pymysql
        conn = pymysql.connect(**config)

    cursor = conn.cursor()

    # Stats
    stats = {
        'total': len(df),
        'imported': 0,
        'updated': 0,
        'skipped': 0,
        'errors': 0
    }

    start_time = datetime.now()

    # Build upsert query
    columns = valid_cols

    if DB_TYPE == 'postgresql':
        placeholders = ', '.join(['%s'] * len(columns))
        update_set = ', '.join([f"{c} = EXCLUDED.{c}" for c in columns if c != 'hcode5'])

        upsert_sql = f"""
            INSERT INTO health_offices ({', '.join(columns)})
            VALUES ({placeholders})
            ON CONFLICT (hcode5) DO UPDATE SET {update_set}
        """
    else:
        placeholders = ', '.join(['%s'] * len(columns))
        update_set = ', '.join([f"{c} = VALUES({c})" for c in columns if c != 'hcode5'])

        upsert_sql = f"""
            INSERT INTO health_offices ({', '.join(columns)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_set}
        """

    # Process in batches
    for i in range(0, len(df), batch_size):
        batch = df.iloc[i:i+batch_size]

        for idx, row in batch.iterrows():
            # Skip if no name (required field)
            if not row.get('name') or row.get('name') in ['', 'nan']:
                stats['skipped'] += 1
                continue

            try:
                values = [row.get(c, '') for c in columns]
                # Clean empty strings to None for proper NULL handling
                values = [None if v == '' else v for v in values]

                cursor.execute(upsert_sql, values)
                stats['imported'] += 1

            except Exception as e:
                stats['errors'] += 1
                if stats['errors'] <= 5:
                    print(f"[seed] Error row {idx}: {e}")
                    print(f"[seed] Values: {values[:5]}...")
                    print(f"[seed] hcode5 value: {row.get('hcode5')}")

        conn.commit()
        print(f"[seed] Processed {min(i + batch_size, len(df))}/{len(df)} records...")

    # Log import
    duration = (datetime.now() - start_time).total_seconds()

    log_sql = """
        INSERT INTO health_offices_import_log
        (filename, total_records, imported, updated, skipped, errors, import_mode, status, duration_seconds)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    cursor.execute(log_sql, (
        Path(excel_path).name,
        stats['total'],
        stats['imported'],
        stats['updated'],
        stats['skipped'],
        stats['errors'],
        'seed',
        'completed',
        duration
    ))
    conn.commit()

    cursor.close()
    conn.close()

    stats['duration_seconds'] = duration
    return stats


def main():
    # Find Excel file
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        # Default locations
        candidates = [
            Path(__file__).parent / 'data' / 'health_office.xlsx',
            Path('/app/database/seeds/data/health_office.xlsx'),
            Path(__file__).parent.parent.parent / 'downloads' / 'health_office.xlsx',
        ]

        excel_path = None
        for p in candidates:
            if p.exists():
                excel_path = str(p)
                break

        if not excel_path:
            print("[seed] ERROR: health_office.xlsx not found")
            print("[seed] Please provide path: python health_offices_importer.py /path/to/file.xlsx")
            print("[seed] Or place file in: database/seeds/data/health_office.xlsx")
            sys.exit(1)

    if not Path(excel_path).exists():
        print(f"[seed] ERROR: File not found: {excel_path}")
        sys.exit(1)

    print(f"[seed] Starting health offices import...")
    print(f"[seed] Database type: {DB_TYPE}")

    stats = import_health_offices(excel_path)

    print(f"\n[seed] ===== Import Complete =====")
    print(f"[seed] Total records: {stats['total']}")
    print(f"[seed] Imported: {stats['imported']}")
    print(f"[seed] Skipped (no hcode5): {stats['skipped']}")
    print(f"[seed] Errors: {stats['errors']}")
    print(f"[seed] Duration: {stats['duration_seconds']:.2f}s")


if __name__ == '__main__':
    main()
