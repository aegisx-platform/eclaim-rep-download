#!/usr/bin/env python3
"""
Reconciliation Report - Compare E-Claim REP data with SMT Budget payments
"""

from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal

from config.database import DB_TYPE


# SQL helpers for cross-database compatibility
def sql_extract_year(column: str) -> str:
    """Generate SQL for extracting year as integer"""
    if DB_TYPE == 'mysql':
        return f"YEAR({column})"
    return f"EXTRACT(YEAR FROM {column})::int"


def sql_extract_month(column: str) -> str:
    """Generate SQL for extracting month"""
    if DB_TYPE == 'mysql':
        return f"MONTH({column})"
    return f"EXTRACT(MONTH FROM {column})"


def sql_extract_month_text(column: str) -> str:
    """Generate SQL for extracting month as zero-padded text"""
    if DB_TYPE == 'mysql':
        return f"LPAD(MONTH({column}), 2, '0')"
    return f"LPAD(EXTRACT(MONTH FROM {column})::text, 2, '0')"


def sql_year_month_format(column: str) -> str:
    """Generate SQL for YYYY-MM format"""
    if DB_TYPE == 'mysql':
        return f"DATE_FORMAT({column}, '%Y-%m')"
    return f"TO_CHAR({column}, 'YYYY-MM')"


def sql_be_month(column: str) -> str:
    """Generate SQL for Buddhist Era YYYYMM format"""
    if DB_TYPE == 'mysql':
        return f"CONCAT(YEAR({column}) + 543, LPAD(MONTH({column}), 2, '0'))"
    return f"(EXTRACT(YEAR FROM {column})::int + 543)::text || LPAD(EXTRACT(MONTH FROM {column})::text, 2, '0')"


# Fund code mapping: REP main_fund codes to SMT fund groups
FUND_MAPPING = {
    # Inpatient
    'IP01': 'กองทุนผู้ป่วยใน',
    'IP02': 'กองทุนผู้ป่วยใน',
    'IP03': 'กองทุนผู้ป่วยใน',
    # Outpatient
    'OP01': 'กองทุนผู้ป่วยนอก',
    'OP02': 'กองทุนผู้ป่วยนอก',
    # Health promotion
    'HC02': 'กองทุนสร้างเสริมสุขภาพและป้องกันโรค',
    'HC16': 'กองทุนค่าบริการทางการแพทย์',
    # Chronic diseases
    'DM14': 'บริการควบคุมป้องกันและรักษาผู้ป่วยโรคเบาหวานและความดันโลหิตสูง',
    # Kidney
    'KT01': 'กองทุนไตวายเรื้อรัง',
    # AIDS
    'AIDS': 'กองทุนเอดส์',
    # Rehabilitation
    'RH01': 'ค่าบริการฟื้นฟูสมรรถภาพด้านการแพทย์',
    # Traditional medicine
    'TM01': 'งบแพทย์แผนไทย',
    # Central reimburse (high cost)
    'ONTOP': 'กองทุน CENTRAL REIMBURSE',
}


def convert_be_to_gregorian(be_date: str) -> Optional[str]:
    """
    Convert Buddhist Era date (YYYYMMDD) to Gregorian (YYYY-MM-DD)

    Args:
        be_date: Date in YYYYMMDD format (Buddhist Era)

    Returns:
        Date in YYYY-MM-DD format (Gregorian) or None
    """
    if not be_date or len(be_date) < 8:
        return None

    try:
        be_year = int(be_date[:4])
        month = be_date[4:6]
        day = be_date[6:8]
        gregorian_year = be_year - 543
        return f"{gregorian_year}-{month}-{day}"
    except (ValueError, IndexError):
        return None


def convert_gregorian_to_be(gregorian_date) -> Optional[str]:
    """
    Convert Gregorian date to Buddhist Era YYYYMM format

    Args:
        gregorian_date: datetime or date object

    Returns:
        YYYYMM in Buddhist Era or None
    """
    if not gregorian_date:
        return None

    try:
        if isinstance(gregorian_date, str):
            gregorian_date = datetime.strptime(gregorian_date[:10], '%Y-%m-%d')
        be_year = gregorian_date.year + 543
        return f"{be_year}{gregorian_date.month:02d}"
    except (ValueError, AttributeError):
        return None


class ReconciliationReport:
    """Generate reconciliation report between REP claims and SMT payments"""

    def __init__(self, db_connection, hospital_code: str = None):
        self.conn = db_connection
        self.hospital_code = hospital_code

    def get_rep_monthly_summary(self) -> List[Dict]:
        """
        Get monthly summary of REP claims

        Returns:
            List of dicts with month, claim_count, claim_amount, by fund
        """
        cursor = self.conn.cursor()

        month_gregorian_sql = sql_year_month_format('dateadm')
        be_month_sql = sql_be_month('dateadm')

        query = f"""
        SELECT
            {month_gregorian_sql} as month_gregorian,
            {be_month_sql} as month_be,
            main_fund,
            COUNT(*) as claim_count,
            COALESCE(SUM(reimb_nhso), 0) as reimb_nhso,
            COALESCE(SUM(reimb_agency), 0) as reimb_agency
        FROM claim_rep_opip_nhso_item
        WHERE dateadm IS NOT NULL
        GROUP BY
            {month_gregorian_sql},
            {be_month_sql},
            main_fund
        ORDER BY month_gregorian DESC, main_fund
        """

        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            results.append({
                'month_gregorian': row[0],
                'month_be': row[1],
                'main_fund': row[2] or 'UNKNOWN',
                'claim_count': row[3],
                'reimb_nhso': float(row[4] or 0),
                'reimb_agency': float(row[5] or 0),
                'total_claim': float((row[4] or 0) + (row[5] or 0))
            })

        return results

    def get_smt_monthly_summary(self) -> List[Dict]:
        """
        Get monthly summary of SMT payments

        Returns:
            List of dicts with month, payment_count, payment_amount, by fund
        """
        cursor = self.conn.cursor()

        # Build WHERE clause with hospital filter
        where_clause = "WHERE posting_date IS NOT NULL"
        params = []
        if self.hospital_code:
            # Normalize vendor_no by removing leading zeros for comparison
            where_clause += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
            params.append(self.hospital_code)

        query = f"""
        SELECT
            LEFT(posting_date, 6) as month_be,
            fund_group_desc,
            fund_name,
            COUNT(*) as payment_count,
            COALESCE(SUM(amount), 0) as amount,
            COALESCE(SUM(total_amount), 0) as total_amount
        FROM smt_budget_transfers
        {where_clause}
        GROUP BY
            LEFT(posting_date, 6),
            fund_group_desc,
            fund_name
        ORDER BY month_be DESC, fund_group_desc
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()

        results = []
        for row in rows:
            # Convert BE month to gregorian for comparison
            be_month = row[0]
            if be_month and len(be_month) == 6:
                be_year = int(be_month[:4])
                month = be_month[4:6]
                gregorian_year = be_year - 543
                month_gregorian = f"{gregorian_year}-{month}"
            else:
                month_gregorian = None

            results.append({
                'month_be': row[0],
                'month_gregorian': month_gregorian,
                'fund_group': row[1],
                'fund_name': row[2],
                'payment_count': row[3],
                'amount': float(row[4] or 0),
                'total_amount': float(row[5] or 0)
            })

        return results

    def get_monthly_reconciliation(self) -> List[Dict]:
        """
        Get monthly reconciliation comparing REP claims vs SMT payments

        Returns:
            List of monthly reconciliation records
        """
        cursor = self.conn.cursor()

        # Get REP summary by month
        be_month_sql = sql_be_month('dateadm')
        rep_query = f"""
        SELECT
            {be_month_sql} as month_be,
            COUNT(*) as claim_count,
            COUNT(DISTINCT tran_id) as unique_claims,
            COALESCE(SUM(reimb_nhso), 0) as total_reimb_nhso,
            COALESCE(SUM(reimb_agency), 0) as total_reimb_agency
        FROM claim_rep_opip_nhso_item
        WHERE dateadm IS NOT NULL
        GROUP BY
            {be_month_sql}
        ORDER BY month_be DESC
        """

        cursor.execute(rep_query)
        rep_data = {row[0]: {
            'claim_count': row[1],
            'unique_claims': row[2],
            'reimb_nhso': float(row[3] or 0),
            'reimb_agency': float(row[4] or 0)
        } for row in cursor.fetchall()}

        # Get SMT summary by month
        smt_where = "WHERE posting_date IS NOT NULL"
        smt_params = []
        if self.hospital_code:
            smt_where += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
            smt_params.append(self.hospital_code)

        smt_query = f"""
        SELECT
            LEFT(posting_date, 6) as month_be,
            COUNT(*) as payment_count,
            COALESCE(SUM(amount), 0) as total_amount,
            COALESCE(SUM(wait_amount), 0) as wait_amount,
            COALESCE(SUM(debt_amount), 0) as debt_amount
        FROM smt_budget_transfers
        {smt_where}
        GROUP BY LEFT(posting_date, 6)
        ORDER BY month_be DESC
        """

        cursor.execute(smt_query, smt_params)
        smt_data = {row[0]: {
            'payment_count': row[1],
            'total_amount': float(row[2] or 0),
            'wait_amount': float(row[3] or 0),
            'debt_amount': float(row[4] or 0)
        } for row in cursor.fetchall()}

        cursor.close()

        # Merge data
        all_months = sorted(set(rep_data.keys()) | set(smt_data.keys()), reverse=True)

        results = []
        for month_be in all_months:
            rep = rep_data.get(month_be, {})
            smt = smt_data.get(month_be, {})

            # Convert to gregorian
            if month_be and len(month_be) == 6:
                be_year = int(month_be[:4])
                month = month_be[4:6]
                gregorian_year = be_year - 543
                month_gregorian = f"{gregorian_year}-{month}"
                month_display = f"{month}/{month_be[:4]}"
            else:
                month_gregorian = None
                month_display = month_be

            claim_total = rep.get('reimb_nhso', 0) + rep.get('reimb_agency', 0)
            payment_total = smt.get('total_amount', 0)

            results.append({
                'month_be': month_be,
                'month_gregorian': month_gregorian,
                'month_display': month_display,
                # REP data
                'claim_count': rep.get('claim_count', 0),
                'unique_claims': rep.get('unique_claims', 0),
                'reimb_nhso': rep.get('reimb_nhso', 0),
                'reimb_agency': rep.get('reimb_agency', 0),
                'claim_total': claim_total,
                # SMT data
                'payment_count': smt.get('payment_count', 0),
                'payment_amount': payment_total,
                'wait_amount': smt.get('wait_amount', 0),
                'debt_amount': smt.get('debt_amount', 0),
                # Comparison
                'difference': payment_total - claim_total,
                'has_rep_data': bool(rep),
                'has_smt_data': bool(smt)
            })

        return results

    def get_fund_reconciliation(self, month_be: str = None) -> List[Dict]:
        """
        Get reconciliation by fund type for a specific month or all time

        Args:
            month_be: Optional month filter in YYYYMM format (Buddhist Era)

        Returns:
            List of fund reconciliation records
        """
        cursor = self.conn.cursor()

        # Build WHERE clause
        rep_where = "WHERE dateadm IS NOT NULL"
        smt_where = "WHERE posting_date IS NOT NULL"
        smt_params = []

        if month_be:
            be_month_sql = sql_be_month('dateadm')
            rep_where += f" AND {be_month_sql} = '{month_be}'"
            smt_where += f" AND LEFT(posting_date, 6) = '{month_be}'"

        if self.hospital_code:
            smt_where += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
            smt_params.append(self.hospital_code)

        # Get REP by fund
        rep_query = f"""
        SELECT
            COALESCE(main_fund, 'UNKNOWN') as fund_code,
            COUNT(*) as claim_count,
            COALESCE(SUM(reimb_nhso), 0) as reimb_nhso
        FROM claim_rep_opip_nhso_item
        {rep_where}
        GROUP BY main_fund
        ORDER BY reimb_nhso DESC
        """

        cursor.execute(rep_query)
        rep_data = {row[0]: {
            'claim_count': row[1],
            'reimb_nhso': float(row[2] or 0)
        } for row in cursor.fetchall()}

        # Get SMT by fund
        smt_query = f"""
        SELECT
            fund_group_desc,
            COUNT(*) as payment_count,
            COALESCE(SUM(amount), 0) as amount
        FROM smt_budget_transfers
        {smt_where}
        GROUP BY fund_group_desc
        ORDER BY amount DESC
        """

        cursor.execute(smt_query, smt_params)
        smt_data = {row[0]: {
            'payment_count': row[1],
            'amount': float(row[2] or 0)
        } for row in cursor.fetchall()}

        cursor.close()

        # Build results with mapping
        results = []

        # Add REP funds with mapping
        for fund_code, rep in rep_data.items():
            mapped_fund = FUND_MAPPING.get(fund_code.split(',')[0] if fund_code else '', 'ไม่ระบุ')
            smt = smt_data.get(mapped_fund, {})

            results.append({
                'rep_fund_code': fund_code,
                'smt_fund_name': mapped_fund,
                'claim_count': rep.get('claim_count', 0),
                'claim_amount': rep.get('reimb_nhso', 0),
                'payment_count': smt.get('payment_count', 0),
                'payment_amount': smt.get('amount', 0),
                'difference': smt.get('amount', 0) - rep.get('reimb_nhso', 0),
                'matched': bool(smt)
            })

        # Add SMT funds not in REP
        rep_mapped_funds = {FUND_MAPPING.get(f.split(',')[0], '') for f in rep_data.keys()}
        for fund_name, smt in smt_data.items():
            if fund_name not in rep_mapped_funds:
                results.append({
                    'rep_fund_code': '-',
                    'smt_fund_name': fund_name,
                    'claim_count': 0,
                    'claim_amount': 0,
                    'payment_count': smt.get('payment_count', 0),
                    'payment_amount': smt.get('amount', 0),
                    'difference': smt.get('amount', 0),
                    'matched': False
                })

        # Sort by payment amount descending
        results.sort(key=lambda x: x['payment_amount'], reverse=True)

        return results

    def get_available_fiscal_years(self) -> List[int]:
        """
        Get list of available fiscal years from data

        Thai fiscal year: October 1 - September 30
        FY 2568 = Oct 2024 - Sep 2025

        Returns:
            List of fiscal years in Buddhist Era
        """
        cursor = self.conn.cursor()

        # Get fiscal years from REP data
        year_expr = sql_extract_year('dateadm')
        month_expr = sql_extract_month('dateadm')
        rep_query = f"""
        SELECT DISTINCT
            CASE
                WHEN {month_expr} >= 10
                THEN {year_expr} + 544
                ELSE {year_expr} + 543
            END as fiscal_year
        FROM claim_rep_opip_nhso_item
        WHERE dateadm IS NOT NULL
        """
        cursor.execute(rep_query)
        rep_years = set(row[0] for row in cursor.fetchall())

        # Get fiscal years from SMT data
        # MySQL uses SIGNED instead of INT for CAST
        int_type = "SIGNED" if DB_TYPE == 'mysql' else "INT"
        smt_query = f"""
        SELECT DISTINCT
            CASE
                WHEN CAST(SUBSTRING(posting_date, 5, 2) AS {int_type}) >= 10
                THEN CAST(SUBSTRING(posting_date, 1, 4) AS {int_type}) + 1
                ELSE CAST(SUBSTRING(posting_date, 1, 4) AS {int_type})
            END as fiscal_year
        FROM smt_budget_transfers
        WHERE posting_date IS NOT NULL AND LENGTH(posting_date) >= 6
        """
        cursor.execute(smt_query)
        smt_years = set(row[0] for row in cursor.fetchall())

        cursor.close()

        # Combine and sort descending
        all_years = sorted(rep_years | smt_years, reverse=True)
        return all_years

    def get_monthly_reconciliation_by_fy(self, fiscal_year: int) -> List[Dict]:
        """
        Get monthly reconciliation for a specific fiscal year

        Args:
            fiscal_year: Fiscal year in Buddhist Era (e.g., 2568)

        Returns:
            List of monthly reconciliation records for the fiscal year
        """
        cursor = self.conn.cursor()

        # Fiscal year date range
        # FY 2568 = Oct 2024 (2567-10) to Sep 2025 (2568-09)
        fy_start_year_be = fiscal_year - 1  # Start in previous calendar year
        fy_end_year_be = fiscal_year  # End in fiscal year

        # Get REP data for fiscal year
        be_month_sql = sql_be_month('dateadm')
        year_expr = sql_extract_year('dateadm')
        month_expr = sql_extract_month('dateadm')
        rep_query = f"""
        SELECT
            {be_month_sql} as month_be,
            COUNT(*) as claim_count,
            COUNT(DISTINCT tran_id) as unique_claims,
            COALESCE(SUM(reimb_nhso), 0) as total_reimb_nhso,
            COALESCE(SUM(reimb_agency), 0) as total_reimb_agency
        FROM claim_rep_opip_nhso_item
        WHERE dateadm IS NOT NULL
          AND (
            ({year_expr} + 543 = %s AND {month_expr} >= 10)
            OR
            ({year_expr} + 543 = %s AND {month_expr} <= 9)
          )
        GROUP BY
            {be_month_sql}
        ORDER BY month_be
        """
        cursor.execute(rep_query, (fy_start_year_be, fy_end_year_be))
        rep_data = {row[0]: {
            'claim_count': row[1],
            'unique_claims': row[2],
            'reimb_nhso': float(row[3] or 0),
            'reimb_agency': float(row[4] or 0)
        } for row in cursor.fetchall()}

        # Get SMT data for fiscal year
        # posting_date is already in BE format, but we need to adjust for fiscal year
        # FY 2569 = Oct 2024 - Sep 2025 = 256710-256809 (in BE posting_date)
        smt_fy_start_be = fy_start_year_be - 1  # 2568 - 1 = 2567
        smt_fy_end_be = fy_end_year_be - 1      # 2569 - 1 = 2568

        smt_where = """WHERE posting_date IS NOT NULL
          AND (
            (LEFT(posting_date, 4) = %s AND SUBSTRING(posting_date, 5, 2) >= '10')
            OR
            (LEFT(posting_date, 4) = %s AND SUBSTRING(posting_date, 5, 2) <= '09')
          )"""
        smt_params = [str(smt_fy_start_be), str(smt_fy_end_be)]

        if self.hospital_code:
            smt_where += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
            smt_params.append(self.hospital_code)

        smt_query = f"""
        SELECT
            LEFT(posting_date, 6) as month_be,
            COUNT(*) as payment_count,
            COALESCE(SUM(amount), 0) as total_amount,
            COALESCE(SUM(wait_amount), 0) as wait_amount,
            COALESCE(SUM(debt_amount), 0) as debt_amount
        FROM smt_budget_transfers
        {smt_where}
        GROUP BY LEFT(posting_date, 6)
        ORDER BY month_be
        """
        cursor.execute(smt_query, smt_params)
        smt_data = {row[0]: {
            'payment_count': row[1],
            'total_amount': float(row[2] or 0),
            'wait_amount': float(row[3] or 0),
            'debt_amount': float(row[4] or 0)
        } for row in cursor.fetchall()}

        cursor.close()

        # Generate all months in fiscal year order (Oct-Sep)
        fiscal_months = []
        for m in range(10, 13):  # Oct, Nov, Dec
            fiscal_months.append(f"{fy_start_year_be}{m:02d}")
        for m in range(1, 10):  # Jan-Sep
            fiscal_months.append(f"{fy_end_year_be}{m:02d}")

        results = []
        for month_be in fiscal_months:
            rep = rep_data.get(month_be, {})
            smt = smt_data.get(month_be, {})

            # Convert to gregorian
            if month_be and len(month_be) == 6:
                be_year = int(month_be[:4])
                month = month_be[4:6]
                gregorian_year = be_year - 543
                month_gregorian = f"{gregorian_year}-{month}"
                month_display = f"{month}/{month_be[:4]}"
            else:
                month_gregorian = None
                month_display = month_be

            claim_total = rep.get('reimb_nhso', 0) + rep.get('reimb_agency', 0)
            payment_total = smt.get('total_amount', 0)

            results.append({
                'month_be': month_be,
                'month_gregorian': month_gregorian,
                'month_display': month_display,
                # REP data
                'claim_count': rep.get('claim_count', 0),
                'unique_claims': rep.get('unique_claims', 0),
                'reimb_nhso': rep.get('reimb_nhso', 0),
                'reimb_agency': rep.get('reimb_agency', 0),
                'claim_total': claim_total,
                # SMT data
                'payment_count': smt.get('payment_count', 0),
                'payment_amount': payment_total,
                'wait_amount': smt.get('wait_amount', 0),
                'debt_amount': smt.get('debt_amount', 0),
                # Comparison
                'difference': payment_total - claim_total,
                'has_rep_data': bool(rep),
                'has_smt_data': bool(smt)
            })

        return results

    def get_summary_stats_by_fy(self, fiscal_year: int = None) -> Dict:
        """
        Get summary statistics for a specific fiscal year

        Args:
            fiscal_year: Optional fiscal year in Buddhist Era

        Returns:
            Dict with summary stats
        """
        cursor = self.conn.cursor()

        if fiscal_year:
            fy_start_year_be = fiscal_year - 1
            fy_end_year_be = fiscal_year

            year_expr = sql_extract_year('dateadm')
            month_expr = sql_extract_month('dateadm')

            # REP stats for FY
            cursor.execute(f"""
            SELECT
                COUNT(*) as total_claims,
                COUNT(DISTINCT tran_id) as unique_claims,
                COALESCE(SUM(reimb_nhso), 0) as total_reimb_nhso,
                COALESCE(SUM(reimb_agency), 0) as total_reimb_agency,
                MIN(dateadm) as earliest_date,
                MAX(dateadm) as latest_date
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
              AND (
                ({year_expr} + 543 = %s AND {month_expr} >= 10)
                OR
                ({year_expr} + 543 = %s AND {month_expr} <= 9)
              )
            """, (fy_start_year_be, fy_end_year_be))
            rep_row = cursor.fetchone()

            # SMT stats for FY
            # posting_date is already in BE, adjust for fiscal year
            smt_fy_start_be = fy_start_year_be - 1
            smt_fy_end_be = fy_end_year_be - 1

            smt_fy_where = """WHERE posting_date IS NOT NULL
              AND (
                (LEFT(posting_date, 4) = %s AND SUBSTRING(posting_date, 5, 2) >= '10')
                OR
                (LEFT(posting_date, 4) = %s AND SUBSTRING(posting_date, 5, 2) <= '09')
              )"""
            smt_fy_params = [str(smt_fy_start_be), str(smt_fy_end_be)]

            if self.hospital_code:
                smt_fy_where += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
                smt_fy_params.append(self.hospital_code)

            cursor.execute(f"""
            SELECT
                COUNT(*) as total_payments,
                COALESCE(SUM(amount), 0) as total_amount,
                COALESCE(SUM(wait_amount), 0) as total_wait,
                COALESCE(SUM(debt_amount), 0) as total_debt,
                MIN(posting_date) as earliest_date,
                MAX(posting_date) as latest_date
            FROM smt_budget_transfers
            {smt_fy_where}
            """, smt_fy_params)
            smt_row = cursor.fetchone()
        else:
            # All time stats
            cursor.execute("""
            SELECT
                COUNT(*) as total_claims,
                COUNT(DISTINCT tran_id) as unique_claims,
                COALESCE(SUM(reimb_nhso), 0) as total_reimb_nhso,
                COALESCE(SUM(reimb_agency), 0) as total_reimb_agency,
                MIN(dateadm) as earliest_date,
                MAX(dateadm) as latest_date
            FROM claim_rep_opip_nhso_item
            """)
            rep_row = cursor.fetchone()

            smt_all_where = "WHERE 1=1"
            smt_all_params = []
            if self.hospital_code:
                smt_all_where += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
                smt_all_params.append(self.hospital_code)

            cursor.execute(f"""
            SELECT
                COUNT(*) as total_payments,
                COALESCE(SUM(amount), 0) as total_amount,
                COALESCE(SUM(wait_amount), 0) as total_wait,
                COALESCE(SUM(debt_amount), 0) as total_debt,
                MIN(posting_date) as earliest_date,
                MAX(posting_date) as latest_date
            FROM smt_budget_transfers
            {smt_all_where}
            """, smt_all_params)
            smt_row = cursor.fetchone()

        cursor.close()

        return {
            'fiscal_year': fiscal_year,
            'rep': {
                'total_claims': rep_row[0] or 0,
                'unique_claims': rep_row[1] or 0,
                'total_reimb_nhso': float(rep_row[2] or 0),
                'total_reimb_agency': float(rep_row[3] or 0),
                'total_amount': float((rep_row[2] or 0) + (rep_row[3] or 0)),
                'earliest_date': rep_row[4].strftime('%Y-%m-%d') if rep_row[4] else None,
                'latest_date': rep_row[5].strftime('%Y-%m-%d') if rep_row[5] else None
            },
            'smt': {
                'total_payments': smt_row[0] or 0,
                'total_amount': float(smt_row[1] or 0),
                'total_wait': float(smt_row[2] or 0),
                'total_debt': float(smt_row[3] or 0),
                'earliest_date': convert_be_to_gregorian(smt_row[4]) if smt_row[4] else None,
                'latest_date': convert_be_to_gregorian(smt_row[5]) if smt_row[5] else None
            }
        }

    def get_summary_stats(self) -> Dict:
        """
        Get overall summary statistics

        Returns:
            Dict with summary stats
        """
        cursor = self.conn.cursor()

        # REP stats
        cursor.execute("""
        SELECT
            COUNT(*) as total_claims,
            COUNT(DISTINCT tran_id) as unique_claims,
            COALESCE(SUM(reimb_nhso), 0) as total_reimb_nhso,
            COALESCE(SUM(reimb_agency), 0) as total_reimb_agency,
            MIN(dateadm) as earliest_date,
            MAX(dateadm) as latest_date
        FROM claim_rep_opip_nhso_item
        """)
        rep_row = cursor.fetchone()

        # SMT stats
        smt_summary_where = "WHERE 1=1"
        smt_summary_params = []
        if self.hospital_code:
            smt_summary_where += " AND TRIM(LEADING '0' FROM vendor_no) = TRIM(LEADING '0' FROM %s)"
            smt_summary_params.append(self.hospital_code)

        cursor.execute(f"""
        SELECT
            COUNT(*) as total_payments,
            COALESCE(SUM(amount), 0) as total_amount,
            COALESCE(SUM(wait_amount), 0) as total_wait,
            COALESCE(SUM(debt_amount), 0) as total_debt,
            MIN(posting_date) as earliest_date,
            MAX(posting_date) as latest_date
        FROM smt_budget_transfers
        {smt_summary_where}
        """, smt_summary_params)
        smt_row = cursor.fetchone()

        cursor.close()

        return {
            'rep': {
                'total_claims': rep_row[0] or 0,
                'unique_claims': rep_row[1] or 0,
                'total_reimb_nhso': float(rep_row[2] or 0),
                'total_reimb_agency': float(rep_row[3] or 0),
                'total_amount': float((rep_row[2] or 0) + (rep_row[3] or 0)),
                'earliest_date': rep_row[4].strftime('%Y-%m-%d') if rep_row[4] else None,
                'latest_date': rep_row[5].strftime('%Y-%m-%d') if rep_row[5] else None
            },
            'smt': {
                'total_payments': smt_row[0] or 0,
                'total_amount': float(smt_row[1] or 0),
                'total_wait': float(smt_row[2] or 0),
                'total_debt': float(smt_row[3] or 0),
                'earliest_date': convert_be_to_gregorian(smt_row[4]) if smt_row[4] else None,
                'latest_date': convert_be_to_gregorian(smt_row[5]) if smt_row[5] else None
            }
        }
