#!/usr/bin/env python3
"""
Update health_offices table with correct NHSO hospital codes (hcode5)

The original seed data doesn't have hcode5 values, so this script updates
key hospitals with their correct NHSO 5-digit codes based on hospital names.

Source: https://hcode.moph.go.th/
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.database import get_db_config, DB_TYPE


# Mapping of hospital names to their NHSO hcode5
# Format: (exact_hospital_name, hcode5, province, hospital_level_keyword)
# Use exact name to avoid duplicates
HOSPITAL_CODES = [
    # เขตบริการสุขภาพที่ 8
    ('โรงพยาบาลอุดรธานี', '10670', 'อุดรธานี', 'ศูนย์'),
    ('โรงพยาบาลกุมภวาปี', '10671', 'อุดรธานี', 'ใหญ่'),
    ('โรงพยาบาลสมเด็จพระยุพราชบ้านดุง', '10672', 'อุดรธานี', 'แม่ข่าย'),
    ('โรงพยาบาลหนองคาย', '10676', 'หนองคาย', 'ทั่วไป'),
    ('โรงพยาบาลสกลนคร', '10681', 'สกลนคร', 'ศูนย์'),
    ('โรงพยาบาลนครพนม', '10686', 'นครพนม', 'ทั่วไป'),
    ('โรงพยาบาลเลย', '10692', 'เลย', 'ทั่วไป'),
    ('โรงพยาบาลหนองบัวลำภู', '10697', 'หนองบัวลำภู', 'ทั่วไป'),
    ('โรงพยาบาลบึงกาฬ', '14861', 'บึงกาฬ', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 7
    ('โรงพยาบาลขอนแก่น', '10699', 'ขอนแก่น', 'ศูนย์'),
    ('โรงพยาบาลมหาสารคาม', '10702', 'มหาสารคาม', 'ทั่วไป'),
    ('โรงพยาบาลร้อยเอ็ด', '10707', 'ร้อยเอ็ด', 'ศูนย์'),
    ('โรงพยาบาลกาฬสินธุ์', '10713', 'กาฬสินธุ์', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 9
    ('โรงพยาบาลมหาราชนครราชสีมา', '10720', 'นครราชสีมา', 'ศูนย์'),
    ('โรงพยาบาลชัยภูมิ', '10726', 'ชัยภูมิ', 'ทั่วไป'),
    ('โรงพยาบาลบุรีรัมย์', '10732', 'บุรีรัมย์', 'ทั่วไป'),
    ('โรงพยาบาลสุรินทร์', '10738', 'สุรินทร์', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 10
    ('โรงพยาบาลสรรพสิทธิประสงค์', '10744', 'อุบลราชธานี', 'ศูนย์'),
    ('โรงพยาบาลศรีสะเกษ', '10750', 'ศรีสะเกษ', 'ทั่วไป'),
    ('โรงพยาบาลยโสธร', '10756', 'ยโสธร', 'ทั่วไป'),
    ('โรงพยาบาลอำนาจเจริญ', '10762', 'อำนาจเจริญ', 'ทั่วไป'),
    ('โรงพยาบาลมุกดาหาร', '10768', 'มุกดาหาร', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 1
    ('โรงพยาบาลนครพิงค์', '11070', 'เชียงใหม่', 'ศูนย์'),
    ('โรงพยาบาลลำปาง', '10774', 'ลำปาง', 'ศูนย์'),
    ('โรงพยาบาลลำพูน', '10780', 'ลำพูน', 'ทั่วไป'),
    ('โรงพยาบาลเชียงรายประชานุเคราะห์', '10786', 'เชียงราย', 'ศูนย์'),
    ('โรงพยาบาลพะเยา', '10792', 'พะเยา', 'ทั่วไป'),
    ('โรงพยาบาลแม่ฮ่องสอน', '10798', 'แม่ฮ่องสอน', 'ทั่วไป'),
    ('โรงพยาบาลน่าน', '10804', 'น่าน', 'ทั่วไป'),
    ('โรงพยาบาลแพร่', '10810', 'แพร่', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 2
    ('โรงพยาบาลพุทธชินราช', '10816', 'พิษณุโลก', 'ศูนย์'),
    ('โรงพยาบาลสุโขทัย', '10822', 'สุโขทัย', 'ทั่วไป'),
    ('โรงพยาบาลอุตรดิตถ์', '10828', 'อุตรดิตถ์', 'ทั่วไป'),
    ('โรงพยาบาลตาก', '10834', 'ตาก', 'ทั่วไป'),
    ('โรงพยาบาลเพชรบูรณ์', '10840', 'เพชรบูรณ์', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 3
    ('โรงพยาบาลสวรรค์ประชารักษ์', '10846', 'นครสวรรค์', 'ศูนย์'),
    ('โรงพยาบาลกำแพงเพชร', '10852', 'กำแพงเพชร', 'ทั่วไป'),
    ('โรงพยาบาลพิจิตร', '10858', 'พิจิตร', 'ทั่วไป'),
    ('โรงพยาบาลชัยนาท', '10864', 'ชัยนาท', 'ทั่วไป'),
    ('โรงพยาบาลอุทัยธานี', '10870', 'อุทัยธานี', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 4
    ('โรงพยาบาลสระบุรี', '10876', 'สระบุรี', 'ศูนย์'),
    ('โรงพยาบาลพระนารายณ์มหาราช', '10882', 'ลพบุรี', 'ศูนย์'),
    ('โรงพยาบาลสิงห์บุรี', '10888', 'สิงห์บุรี', 'ทั่วไป'),
    ('โรงพยาบาลอ่างทอง', '10894', 'อ่างทอง', 'ทั่วไป'),
    ('โรงพยาบาลพระนครศรีอยุธยา', '10900', 'พระนครศรีอยุธยา', 'ศูนย์'),
    ('โรงพยาบาลปทุมธานี', '10906', 'ปทุมธานี', 'ทั่วไป'),
    ('โรงพยาบาลนนทบุรี', '10912', 'นนทบุรี', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 5
    ('โรงพยาบาลราชบุรี', '10918', 'ราชบุรี', 'ศูนย์'),
    ('โรงพยาบาลเพชรบุรี', '10924', 'เพชรบุรี', 'ทั่วไป'),
    ('โรงพยาบาลสมุทรสงคราม', '10930', 'สมุทรสงคราม', 'ทั่วไป'),
    ('โรงพยาบาลประจวบคีรีขันธ์', '10936', 'ประจวบคีรีขันธ์', 'ทั่วไป'),
    ('โรงพยาบาลกาญจนบุรี', '10942', 'กาญจนบุรี', 'ทั่วไป'),
    ('โรงพยาบาลสุพรรณบุรี', '10948', 'สุพรรณบุรี', 'ศูนย์'),
    ('โรงพยาบาลนครปฐม', '10954', 'นครปฐม', 'ทั่วไป'),
    ('โรงพยาบาลสมุทรสาคร', '10960', 'สมุทรสาคร', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 6
    ('โรงพยาบาลชลบุรี', '10966', 'ชลบุรี', 'ศูนย์'),
    ('โรงพยาบาลระยอง', '10972', 'ระยอง', 'ศูนย์'),
    ('โรงพยาบาลพระปกเกล้า', '10978', 'จันทบุรี', 'ศูนย์'),
    ('โรงพยาบาลตราด', '10984', 'ตราด', 'ทั่วไป'),
    ('โรงพยาบาลฉะเชิงเทรา', '10996', 'ฉะเชิงเทรา', 'ทั่วไป'),
    ('โรงพยาบาลปราจีนบุรี', '11002', 'ปราจีนบุรี', 'ทั่วไป'),
    ('โรงพยาบาลสมุทรปราการ', '11008', 'สมุทรปราการ', 'ทั่วไป'),
    ('โรงพยาบาลสระแก้ว', '11014', 'สระแก้ว', 'ทั่วไป'),

    # เขตบริการสุขภาพที่ 11
    ('โรงพยาบาลสุราษฎร์ธานี', '11020', 'สุราษฎร์ธานี', 'ศูนย์'),
    ('โรงพยาบาลมหาราชนครศรีธรรมราช', '11026', 'นครศรีธรรมราช', 'ศูนย์'),
    ('โรงพยาบาลชุมพรเขตอุดมศักดิ์', '11032', 'ชุมพร', 'ทั่วไป'),
    ('โรงพยาบาลระนอง', '11038', 'ระนอง', 'ทั่วไป'),
    ('โรงพยาบาลกระบี่', '11044', 'กระบี่', 'ทั่วไป'),
    ('โรงพยาบาลพังงา', '11050', 'พังงา', 'ทั่วไป'),
    ('โรงพยาบาลวชิระภูเก็ต', '11056', 'ภูเก็ต', 'ศูนย์'),

    # เขตบริการสุขภาพที่ 12
    ('โรงพยาบาลหาดใหญ่', '11062', 'สงขลา', 'ศูนย์'),
    ('โรงพยาบาลตรัง', '11068', 'ตรัง', 'ทั่วไป'),
    ('โรงพยาบาลสตูล', '11074', 'สตูล', 'ทั่วไป'),
    ('โรงพยาบาลปัตตานี', '11080', 'ปัตตานี', 'ทั่วไป'),
    ('โรงพยาบาลยะลา', '11086', 'ยะลา', 'ศูนย์'),
    ('โรงพยาบาลนราธิวาสราชนครินทร์', '11092', 'นราธิวาส', 'ศูนย์'),
    ('โรงพยาบาลพัทลุง', '11098', 'พัทลุง', 'ทั่วไป'),

    # กรุงเทพมหานคร - Special codes
    ('โรงพยาบาลศิริราช', '13756', 'กรุงเทพมหานคร', None),
    ('โรงพยาบาลจุฬาลงกรณ์', '13757', 'กรุงเทพมหานคร', None),
    ('โรงพยาบาลรามาธิบดี', '13758', 'กรุงเทพมหานคร', None),
    ('โรงพยาบาลราชวิถี', '13759', 'กรุงเทพมหานคร', None),
    ('โรงพยาบาลพระมงกุฎเกล้า', '13760', 'กรุงเทพมหานคร', None),
    ('สถาบันบำราศนราดูร', '13761', 'นนทบุรี', None),
    ('โรงพยาบาลธรรมศาสตร์เฉลิมพระเกียรติ', '14060', 'ปทุมธานี', None),
]


def update_hospital_codes():
    """Update health_offices table with correct NHSO hcode5 codes."""

    config = get_db_config()

    if DB_TYPE == 'postgresql':
        import psycopg2
        conn = psycopg2.connect(**config)
    else:
        import pymysql
        conn = pymysql.connect(**config)

    cursor = conn.cursor()

    updated = 0
    not_found = 0
    skipped = 0

    for item in HOSPITAL_CODES:
        name_pattern = item[0]
        hcode5 = item[1]
        province = item[2]
        level_keyword = item[3] if len(item) > 3 else None

        # Build query with exact name match (or close match with level)
        if level_keyword:
            cursor.execute("""
                SELECT id, hcode5, name, hospital_level
                FROM health_offices
                WHERE name = %s AND province = %s AND hospital_level LIKE %s
                LIMIT 1
            """, (name_pattern, province, f'%{level_keyword}%'))
        else:
            cursor.execute("""
                SELECT id, hcode5, name, hospital_level
                FROM health_offices
                WHERE name = %s AND province = %s
                LIMIT 1
            """, (name_pattern, province))

        row = cursor.fetchone()

        if not row:
            # Try fuzzy match if exact match fails
            cursor.execute("""
                SELECT id, hcode5, name, hospital_level
                FROM health_offices
                WHERE name LIKE %s AND province = %s
                ORDER BY CHAR_LENGTH(name) ASC
                LIMIT 1
            """, (f'{name_pattern}%', province))
            row = cursor.fetchone()

        if row:
            old_hcode5 = row[1]
            hospital_id = row[0]
            hospital_name = row[2]

            # Check if hcode5 already exists for another hospital
            cursor.execute("""
                SELECT id FROM health_offices WHERE hcode5 = %s AND id != %s
            """, (hcode5, hospital_id))
            if cursor.fetchone():
                print(f"[skip] {hospital_name}: hcode5 {hcode5} already assigned to another hospital")
                skipped += 1
                continue

            # Update hcode5
            cursor.execute("""
                UPDATE health_offices
                SET hcode5 = %s
                WHERE id = %s
            """, (hcode5, hospital_id))

            print(f"[update] {hospital_name}: {old_hcode5} -> {hcode5}")
            updated += 1
        else:
            print(f"[skip] Not found: {name_pattern} ({province})")
            not_found += 1

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\n=== Update Complete ===")
    print(f"Updated: {updated}")
    print(f"Not found: {not_found}")
    print(f"Skipped (duplicate): {skipped}")

    return {'updated': updated, 'not_found': not_found, 'skipped': skipped}


def verify_codes():
    """Verify that hospital codes were updated correctly."""

    config = get_db_config()

    if DB_TYPE == 'postgresql':
        import psycopg2
        conn = psycopg2.connect(**config)
    else:
        import pymysql
        conn = pymysql.connect(**config)

    cursor = conn.cursor()

    # Check some key hospitals
    test_codes = ['10670', '10720', '11062', '13756']

    print("\n=== Verification ===")
    for code in test_codes:
        cursor.execute("""
            SELECT name, hcode5, province, hospital_level
            FROM health_offices
            WHERE hcode5 = %s
            LIMIT 1
        """, (code,))
        row = cursor.fetchone()
        if row:
            print(f"[OK] {code}: {row[0]} ({row[2]}) - {row[3]}")
        else:
            print(f"[MISSING] {code}: Not found")

    cursor.close()
    conn.close()


if __name__ == '__main__':
    print(f"Database type: {DB_TYPE}")
    print(f"Updating hospital codes...\n")

    result = update_hospital_codes()
    verify_codes()
