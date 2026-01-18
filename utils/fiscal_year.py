"""
Fiscal Year Utilities - มาตรฐานการคำนวณปีงบประมาณ

ปีงบประมาณไทย (Thai Fiscal Year):
- เริ่ม: 1 ตุลาคม (October 1)
- สิ้นสุด: 30 กันยายน (September 30)
- ปีงบประมาณ 2569 = 1 ต.ค. 2568 - 30 ก.ย. 2569 (พ.ศ.)
                      = 1 Oct 2025 - 30 Sep 2026 (ค.ศ.)

มาตรฐานการใช้งาน:
1. เรียกด้วยปี พ.ศ. เท่านั้น (Buddhist Era)
2. Return ในรูปแบบ BE สำหรับ SMT (posting_date)
3. Return ในรูปแบบ Gregorian สำหรับ REP (dateadm)
"""

from datetime import datetime
from typing import Tuple, Optional


def get_fiscal_year_range_be(
    fiscal_year_be: int,
    to_current: bool = False
) -> Tuple[str, str]:
    """
    คำนวณช่วงวันที่ของปีงบประมาณในรูปแบบ พ.ศ. (YYYYMMDD)

    ใช้สำหรับ: SMT data (posting_date ที่เป็น BE format)

    Args:
        fiscal_year_be: ปีงบประมาณ พ.ศ. (เช่น 2569)
        to_current: ถ้า True จะใช้วันที่ปัจจุบันแทนวันสิ้นสุดปีงบ

    Returns:
        tuple: (start_date_be, end_date_be) ในรูปแบบ YYYYMMDD พ.ศ.
               เช่น ('25681001', '25690930') หรือ ('25681001', '25690118')

    Examples:
        >>> get_fiscal_year_range_be(2569, to_current=False)
        ('25681001', '25690930')  # FY 2569 = 1 ต.ค. 2568 - 30 ก.ย. 2569

        >>> get_fiscal_year_range_be(2569, to_current=True)  # ถ้าวันนี้ = 18 ม.ค. 2569
        ('25681001', '25690118')  # FY 2569 จนถึงวันนี้
    """
    # ปีงบประมาณ 2569 เริ่มต้นในเดือนตุลาคม 2568
    start_year_be = fiscal_year_be - 1
    start_date_be = f"{start_year_be}1001"  # 1 October

    if to_current:
        # ใช้วันที่ปัจจุบัน
        today = datetime.now()
        end_year_be = today.year + 543  # Convert to BE
        end_month = today.month
        end_day = today.day
        end_date_be = f"{end_year_be}{end_month:02d}{end_day:02d}"
    else:
        # ใช้วันสิ้นสุดปีงบ (30 กันยายน)
        end_year_be = fiscal_year_be
        end_date_be = f"{end_year_be}0930"  # 30 September

    return start_date_be, end_date_be


def get_fiscal_year_range_gregorian(
    fiscal_year_be: int,
    to_current: bool = False
) -> Tuple[str, str]:
    """
    คำนวณช่วงวันที่ของปีงบประมาณในรูปแบบ ค.ศ. (YYYY-MM-DD)

    ใช้สำหรับ: REP data (dateadm ที่เป็น Gregorian date)

    Args:
        fiscal_year_be: ปีงบประมาณ พ.ศ. (เช่น 2569)
        to_current: ถ้า True จะใช้วันที่ปัจจุบันแทนวันสิ้นสุดปีงบ

    Returns:
        tuple: (start_date, end_date) ในรูปแบบ YYYY-MM-DD ค.ศ.
               เช่น ('2025-10-01', '2026-09-30') หรือ ('2025-10-01', '2026-01-18')

    Examples:
        >>> get_fiscal_year_range_gregorian(2569, to_current=False)
        ('2025-10-01', '2026-09-30')  # FY 2569 = 1 Oct 2025 - 30 Sep 2026

        >>> get_fiscal_year_range_gregorian(2569, to_current=True)  # ถ้าวันนี้ = 18 Jan 2026
        ('2025-10-01', '2026-01-18')  # FY 2569 จนถึงวันนี้
    """
    # Convert BE to Gregorian (พ.ศ. - 543 = ค.ศ.)
    start_year_gregorian = (fiscal_year_be - 1) - 543
    start_date = f"{start_year_gregorian}-10-01"  # 1 October

    if to_current:
        # ใช้วันที่ปัจจุบัน
        today = datetime.now()
        end_date = today.strftime('%Y-%m-%d')
    else:
        # ใช้วันสิ้นสุดปีงบ (30 กันยายน)
        end_year_gregorian = fiscal_year_be - 543
        end_date = f"{end_year_gregorian}-09-30"  # 30 September

    return start_date, end_date


def get_fiscal_year_be_range_for_query(
    fiscal_year_be: int
) -> Tuple[int, int]:
    """
    คำนวณปี พ.ศ. เริ่มต้นและสิ้นสุดสำหรับใช้ใน SQL query

    ใช้สำหรับ: Query ที่ต้องการแยก year และ month

    Args:
        fiscal_year_be: ปีงบประมาณ พ.ศ. (เช่น 2569)

    Returns:
        tuple: (start_year_be, end_year_be)
               เช่น (2568, 2569) สำหรับ FY 2569

    Examples:
        >>> get_fiscal_year_be_range_for_query(2569)
        (2568, 2569)

        # ใช้ใน SQL:
        # WHERE (year_be = 2568 AND month >= 10) OR (year_be = 2569 AND month <= 9)
    """
    start_year_be = fiscal_year_be - 1  # ปีที่เริ่มต้น (ต.ค.)
    end_year_be = fiscal_year_be        # ปีที่สิ้นสุด (ก.ย.)
    return start_year_be, end_year_be


def get_current_fiscal_year_be() -> int:
    """
    คำนวณปีงบประมาณปัจจุบันในรูปแบบ พ.ศ.

    Returns:
        int: ปีงบประมาณปัจจุบัน พ.ศ.

    Examples:
        >>> get_current_fiscal_year_be()  # ถ้าวันนี้ = 18 Jan 2026
        2569

        >>> get_current_fiscal_year_be()  # ถ้าวันนี้ = 15 Oct 2025
        2569

        >>> get_current_fiscal_year_be()  # ถ้าวันนี้ = 25 Sep 2025
        2568
    """
    today = datetime.now()
    year_be = today.year + 543
    month = today.month

    # ถ้าเดือนปัจจุบัน >= ตุลาคม (10) ถือว่าอยู่ในปีงบถัดไป
    if month >= 10:
        fiscal_year_be = year_be + 1
    else:
        fiscal_year_be = year_be

    return fiscal_year_be


def format_fiscal_year_display(fiscal_year_be: int, lang: str = 'th') -> str:
    """
    แสดงผลปีงบประมาณในรูปแบบที่อ่านง่าย

    Args:
        fiscal_year_be: ปีงบประมาณ พ.ศ. (เช่น 2569)
        lang: ภาษาที่ต้องการแสดง ('th' หรือ 'en')

    Returns:
        str: ข้อความแสดงปีงบประมาณ

    Examples:
        >>> format_fiscal_year_display(2569, 'th')
        'ปีงบประมาณ 2569 (1 ต.ค. 2568 - 30 ก.ย. 2569)'

        >>> format_fiscal_year_display(2569, 'en')
        'FY 2569 (1 Oct 2025 - 30 Sep 2026)'
    """
    start_year_be = fiscal_year_be - 1
    start_year_ce = start_year_be - 543
    end_year_ce = fiscal_year_be - 543

    if lang == 'th':
        return f"ปีงบประมาณ {fiscal_year_be} (1 ต.ค. {start_year_be} - 30 ก.ย. {fiscal_year_be})"
    else:
        return f"FY {fiscal_year_be} (1 Oct {start_year_ce} - 30 Sep {end_year_ce})"


def get_fiscal_year_sql_filter_gregorian(
    fiscal_year_be: int,
    date_column: str = 'dateadm',
    to_current: bool = False
) -> tuple:
    """
    สร้าง SQL WHERE clause สำหรับ filter ปีงบประมาณ (Gregorian date column)

    ใช้สำหรับ: REP data (dateadm, datedsc), SMT run_date

    Args:
        fiscal_year_be: ปีงบประมาณ พ.ศ. (เช่น 2569)
        date_column: ชื่อ column ที่เป็น date (Gregorian)
        to_current: ถ้า True จะใช้วันที่ปัจจุบันแทนวันสิ้นสุดปีงบ

    Returns:
        tuple: (where_clause, params)
            - where_clause: SQL WHERE condition string
            - params: list of parameters for query

    Examples:
        >>> get_fiscal_year_sql_filter_gregorian(2569, 'dateadm')
        ('dateadm >= %s AND dateadm <= %s', ['2025-10-01', '2026-09-30'])

        >>> get_fiscal_year_sql_filter_gregorian(2569, 'run_date', to_current=True)
        ('run_date >= %s AND run_date <= %s', ['2025-10-01', '2026-01-18'])
    """
    start_date, end_date = get_fiscal_year_range_gregorian(fiscal_year_be, to_current)
    where_clause = f"{date_column} >= %s AND {date_column} <= %s"
    params = [start_date, end_date]
    return where_clause, params


def get_fiscal_year_sql_filter_be(
    fiscal_year_be: int,
    date_column: str = 'posting_date',
    to_current: bool = False
) -> tuple:
    """
    สร้าง SQL WHERE clause สำหรับ filter ปีงบประมาณ (BE varchar column)

    ใช้สำหรับ: SMT posting_date (format: YYYYMMDD ใน BE)

    Args:
        fiscal_year_be: ปีงบประมาณ พ.ศ. (เช่น 2569)
        date_column: ชื่อ column ที่เป็น varchar BE format
        to_current: ถ้า True จะใช้วันที่ปัจจุบันแทนวันสิ้นสุดปีงบ

    Returns:
        tuple: (where_clause, params)
            - where_clause: SQL WHERE condition string
            - params: list of parameters for query

    Examples:
        >>> get_fiscal_year_sql_filter_be(2569, 'posting_date')
        ("(LEFT(posting_date, 4) = %s AND SUBSTRING(posting_date, 5, 2) >= '10') OR (LEFT(posting_date, 4) = %s AND SUBSTRING(posting_date, 5, 2) <= '09')", ['2568', '2569'])
    """
    start_year_be, end_year_be = get_fiscal_year_be_range_for_query(fiscal_year_be)

    if to_current:
        # ใช้วันที่ปัจจุบัน
        today = datetime.now()
        current_year_be = today.year + 543
        current_month = today.month
        current_day = today.day

        # ถ้าอยู่ในปีแรกของ FY (Oct-Dec)
        if current_year_be == start_year_be and current_month >= 10:
            where_clause = f"""(
                (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) >= '10' AND {date_column} <= %s)
            )"""
            end_date_be = f"{current_year_be}{current_month:02d}{current_day:02d}"
            params = [str(start_year_be), end_date_be]
        # ถ้าอยู่ในปีสุดท้ายของ FY (Jan-Sep)
        elif current_year_be == end_year_be and current_month <= 9:
            where_clause = f"""(
                (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) >= '10')
                OR
                (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) <= '09' AND {date_column} <= %s)
            )"""
            end_date_be = f"{current_year_be}{current_month:02d}{current_day:02d}"
            params = [str(start_year_be), str(end_year_be), end_date_be]
        else:
            # ถ้า current date อยู่นอก FY range ใช้ range ปกติ
            where_clause = f"""(
                (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) >= '10')
                OR
                (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) <= '09')
            )"""
            params = [str(start_year_be), str(end_year_be)]
    else:
        # ใช้ range ปกติ (เต็มปีงบ)
        where_clause = f"""(
            (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) >= '10')
            OR
            (LEFT({date_column}, 4) = %s AND SUBSTRING({date_column}, 5, 2) <= '09')
        )"""
        params = [str(start_year_be), str(end_year_be)]

    return where_clause, params
