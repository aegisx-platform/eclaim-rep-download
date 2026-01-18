"""Benchmark API Blueprint - Hospital Comparison and Analytics"""

from flask import Blueprint, jsonify, request, current_app
from datetime import datetime
from zoneinfo import ZoneInfo
from utils.logging_config import setup_logger, safe_format_exception
from utils.fiscal_year import (
    get_fiscal_year_sql_filter_gregorian,
    get_fiscal_year_range_gregorian
)
from config.database import DB_TYPE
from config.db_pool import get_connection as get_pooled_connection

# Thailand timezone
TZ_BANGKOK = ZoneInfo('Asia/Bangkok')

# Set up logger
logger = setup_logger('benchmark_api', enable_masking=True)

# Create Blueprint
benchmark_api_bp = Blueprint('benchmark_api', __name__)


# Database connection helper
def get_db_connection():
    """Get database connection from pool"""
    try:
        conn = get_pooled_connection()
        if conn is None:
            logger.error("Failed to get connection from pool")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None


# Database-specific SQL helpers for PostgreSQL/MySQL compatibility
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


def sql_format_year_month(column: str) -> str:
    """Generate SQL for formatting date as YYYY-MM"""
    if DB_TYPE == 'mysql':
        return f"DATE_FORMAT({column}, '%%Y-%%m')"
    return f"TO_CHAR({column}, 'YYYY-MM')"


# ============================================
# Benchmark API Routes
# ============================================

@benchmark_api_bp.route('/api/benchmark/hospitals')
def api_benchmark_hospitals():
    """Get list of hospitals from SMT data for comparison"""
    try:
        fiscal_year = request.args.get('fiscal_year')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Build date filter based on fiscal year
        # Thai fiscal year: Oct (year-1) to Sep (year)
        where_clause = ""
        params = []

        if fiscal_year:
            fiscal_year_int = int(fiscal_year)
            # Use fiscal year utility for Gregorian date filtering (run_date is Gregorian)
            sql_filter, filter_params = get_fiscal_year_sql_filter_gregorian(fiscal_year_int, 's.run_date')
            where_clause = f"WHERE {sql_filter}"
            params = filter_params

        # Get summary by vendor from smt_budget_transfers with hospital name lookup
        ltrim_expr = "TRIM(LEADING '0' FROM s.vendor_no)" if DB_TYPE == 'mysql' else "LTRIM(s.vendor_no, '0')"

        # Fix collation mismatch for MySQL
        if DB_TYPE == 'mysql':
            join_condition = f"""
                h.hcode5 COLLATE utf8mb4_unicode_ci = {ltrim_expr} COLLATE utf8mb4_unicode_ci
                OR h.hcode5 COLLATE utf8mb4_unicode_ci = s.vendor_no COLLATE utf8mb4_unicode_ci
            """
        else:
            join_condition = f"""
                h.hcode5 = {ltrim_expr}
                OR h.hcode5 = s.vendor_no
            """

        query = f"""
            SELECT
                s.vendor_no,
                COUNT(*) as records,
                COALESCE(SUM(s.total_amount), 0) as total_amount,
                COALESCE(SUM(s.wait_amount), 0) as wait_amount,
                COALESCE(SUM(s.debt_amount), 0) as debt_amount,
                COALESCE(SUM(s.bond_amount), 0) as bond_amount,
                MIN(s.run_date) as first_date,
                MAX(s.run_date) as last_date,
                h.name as hospital_name
            FROM smt_budget_transfers s
            LEFT JOIN health_offices h ON (
                {join_condition}
            )
            {where_clause}
            GROUP BY s.vendor_no, h.name
            ORDER BY total_amount DESC
        """
        cursor.execute(query, params)

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        hospitals = []
        for row in rows:
            vendor_no = row[0]
            hospital_name = row[8] if row[8] else None
            hospitals.append({
                'vendor_no': vendor_no,
                'records': row[1],
                'total_amount': float(row[2]) if row[2] else 0,
                'wait_amount': float(row[3]) if row[3] else 0,
                'debt_amount': float(row[4]) if row[4] else 0,
                'bond_amount': float(row[5]) if row[5] else 0,
                'first_date': row[6].strftime('%Y-%m-%d') if row[6] else None,
                'last_date': row[7].strftime('%Y-%m-%d') if row[7] else None,
                'hospital_name': hospital_name
            })

        return jsonify({
            'success': True,
            'hospitals': hospitals,
            'count': len(hospitals)
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@benchmark_api_bp.route('/api/benchmark/timeseries')
def api_benchmark_timeseries():
    """Get time-series data for hospital comparison charts"""
    try:
        fiscal_year = request.args.get('fiscal_year')
        start_month = request.args.get('start_month')
        end_month = request.args.get('end_month')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Build date filter based on fiscal year and month range
        # Thai fiscal year: Oct (year-1) to Sep (year)
        where_clause = ""
        params = []

        if fiscal_year:
            fiscal_year_int = int(fiscal_year)
            # Use fiscal year utility for Gregorian date filtering (run_date is Gregorian)
            sql_filter, filter_params = get_fiscal_year_sql_filter_gregorian(fiscal_year_int, 'run_date')
            where_clause = f"WHERE {sql_filter}"
            params = filter_params

            # If specific month range is specified
            if start_month and end_month:
                start_m = int(start_month)
                end_m = int(end_month)
                # Adjust dates based on month in fiscal year
                # Convert Buddhist Era to Gregorian for month range calculation
                gregorian_year = fiscal_year_int - 543
                if start_m >= 10:
                    start_date = f"{gregorian_year - 1}-{start_m:02d}-01"
                else:
                    start_date = f"{gregorian_year}-{start_m:02d}-01"
                if end_m >= 10:
                    end_date = f"{gregorian_year - 1}-{end_m:02d}-28"
                else:
                    end_date = f"{gregorian_year}-{end_m:02d}-28"
                # Override with month-specific range
                where_clause = "WHERE run_date >= %s AND run_date <= %s"
                params = [start_date, end_date]

        # Get monthly summary by vendor
        year_expr = sql_extract_year('s.run_date')
        month_expr = sql_extract_month('s.run_date')
        # LTRIM syntax differs between databases
        ltrim_expr = "TRIM(LEADING '0' FROM s.vendor_no)" if DB_TYPE == 'mysql' else "LTRIM(s.vendor_no, '0')"
        query = f"""
            SELECT
                s.vendor_no,
                h.name as hospital_name,
                {year_expr} as year,
                {month_expr} as month,
                COUNT(*) as records,
                COALESCE(SUM(s.total_amount), 0) as total_amount,
                COALESCE(SUM(s.wait_amount), 0) as wait_amount,
                COALESCE(SUM(s.debt_amount), 0) as debt_amount
            FROM smt_budget_transfers s
            LEFT JOIN health_offices h ON (
                h.hcode5 = {ltrim_expr}
                OR h.hcode5 = s.vendor_no
            )
            {where_clause}
            GROUP BY s.vendor_no, h.name, {year_expr}, {month_expr}
            ORDER BY s.vendor_no, year, month
        """

        cursor.execute(query, params)
        rows = cursor.fetchall()

        # Also get available fiscal years
        fy_year_expr = sql_extract_year('run_date')
        fy_month_expr = sql_extract_month('run_date')
        cursor.execute(f"""
            SELECT DISTINCT
                CASE
                    WHEN {fy_month_expr} >= 10 THEN {fy_year_expr} + 544
                    ELSE {fy_year_expr} + 543
                END as fiscal_year
            FROM smt_budget_transfers
            ORDER BY fiscal_year DESC
        """)
        fiscal_years = [int(r[0]) for r in cursor.fetchall()]

        cursor.close()
        conn.close()

        # Organize data by vendor
        vendors = {}
        months = set()

        for row in rows:
            vendor_no = row[0]
            hospital_name = row[1]
            year = int(row[2])
            month = int(row[3])
            month_key = f"{year}-{month:02d}"
            months.add(month_key)

            if vendor_no not in vendors:
                vendors[vendor_no] = {
                    'vendor_no': vendor_no,
                    'hospital_name': hospital_name or f'รพ. {vendor_no.lstrip("0")}',
                    'data': {}
                }

            vendors[vendor_no]['data'][month_key] = {
                'records': row[4],
                'total_amount': float(row[5]) if row[5] else 0,
                'wait_amount': float(row[6]) if row[6] else 0,
                'debt_amount': float(row[7]) if row[7] else 0
            }

        return jsonify({
            'success': True,
            'vendors': list(vendors.values()),
            'months': sorted(list(months)),
            'fiscal_years': fiscal_years
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@benchmark_api_bp.route('/api/benchmark/hospital-years')
def api_benchmark_hospital_years():
    """Get which fiscal years have data for a specific hospital"""
    try:
        vendor_id = request.args.get('vendor_id')

        if not vendor_id:
            return jsonify({'success': False, 'error': 'vendor_id is required'}), 400

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Normalize vendor_id
        vendor_id_10 = vendor_id.zfill(10)
        vendor_id_5 = vendor_id.lstrip('0') or vendor_id  # Keep original if all zeros

        print(f"[DEBUG] hospital-years: vendor_id={vendor_id}, vendor_id_10={vendor_id_10}, vendor_id_5={vendor_id_5}")

        # First check what vendor_no values exist in DB for debugging
        cursor.execute("""
            SELECT DISTINCT vendor_no FROM smt_budget_transfers
            WHERE vendor_no LIKE %s OR vendor_no LIKE %s
            LIMIT 5
        """, (f'%{vendor_id_5}%', f'%{vendor_id}%'))
        debug_vendors = cursor.fetchall()
        print(f"[DEBUG] Found vendor_nos in DB matching pattern: {debug_vendors}")

        # Get all fiscal years that have data for this hospital
        # Use flexible matching: cast to numeric and compare to handle different padding
        fy_year_expr = sql_extract_year('run_date')
        fy_month_expr = sql_extract_month('run_date')
        # MySQL and PostgreSQL have different REGEXP_REPLACE syntax
        if DB_TYPE == 'mysql':
            vendor_cast = "CAST(REGEXP_REPLACE(vendor_no, '[^0-9]', '') AS UNSIGNED)"
        else:
            vendor_cast = "CAST(NULLIF(REGEXP_REPLACE(vendor_no, '[^0-9]', '', 'g'), '') AS BIGINT)"
        cursor.execute(f"""
            SELECT
                CASE
                    WHEN {fy_month_expr} >= 10 THEN {fy_year_expr} + 544
                    ELSE {fy_year_expr} + 543
                END as fiscal_year,
                COUNT(*) as records,
                COALESCE(SUM(total_amount), 0) as total_amount
            FROM smt_budget_transfers
            WHERE {vendor_cast} = %s
            GROUP BY fiscal_year
            ORDER BY fiscal_year DESC
        """, (int(vendor_id_5),))
        rows = cursor.fetchall()
        print(f"[DEBUG] Found {len(rows)} years with data for vendor {vendor_id_5}")

        # Get all available years in the system (from any hospital)
        cursor.execute(f"""
            SELECT DISTINCT
                CASE
                    WHEN {fy_month_expr} >= 10 THEN {fy_year_expr} + 544
                    ELSE {fy_year_expr} + 543
                END as fiscal_year
            FROM smt_budget_transfers
            WHERE run_date IS NOT NULL
            ORDER BY fiscal_year DESC
        """)
        all_years = [int(r[0]) for r in cursor.fetchall()]

        cursor.close()
        conn.close()

        # Build response with status for each year
        hospital_years = {}
        for row in rows:
            year = int(row[0])
            hospital_years[year] = {
                'year': year,
                'has_data': True,
                'records': row[1],
                'total_amount': float(row[2])
            }

        # Add years that don't have data for this hospital
        # Include years from 2565 to current fiscal year
        today = datetime.now(TZ_BANGKOK)
        current_fiscal = today.year + 544 if today.month >= 10 else today.year + 543

        for year in range(2565, current_fiscal + 1):
            if year not in hospital_years:
                hospital_years[year] = {
                    'year': year,
                    'has_data': False,
                    'records': 0,
                    'total_amount': 0
                }

        # Sort by year descending
        years_list = sorted(hospital_years.values(), key=lambda x: x['year'], reverse=True)

        return jsonify({
            'success': True,
            'vendor_id': vendor_id,
            'years': years_list,
            'all_system_years': all_years
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@benchmark_api_bp.route('/api/benchmark/my-hospital')
def api_benchmark_my_hospital():
    """Get detailed analytics for a single hospital"""
    try:
        vendor_id = request.args.get('vendor_id')
        fiscal_year = request.args.get('fiscal_year')

        if not vendor_id:
            return jsonify({'success': False, 'error': 'vendor_id is required'}), 400

        # Default to current fiscal year
        if not fiscal_year:
            today = datetime.now(TZ_BANGKOK)
            fiscal_year = today.year + 543 if today.month >= 10 else today.year + 542

        fiscal_year = int(fiscal_year)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Convert fiscal year to date range using standardized calculation
        start_date, end_date = get_fiscal_year_range_gregorian(fiscal_year)

        # Previous year for YoY comparison
        prev_start_date, prev_end_date = get_fiscal_year_range_gregorian(fiscal_year - 1)

        # Normalize vendor_id (can be 5 or 10 digits)
        vendor_id_10 = vendor_id.zfill(10)
        vendor_id_5 = vendor_id.lstrip('0')

        # Get hospital info from health_offices (including bed count)
        cursor.execute("""
            SELECT name, hospital_level, province, health_region, hcode5, COALESCE(actual_beds, 0) as actual_beds
            FROM health_offices
            WHERE hcode5 = %s OR hcode5 = %s
            LIMIT 1
        """, (vendor_id_5, vendor_id))
        hospital_row = cursor.fetchone()

        actual_beds = int(hospital_row[5]) if hospital_row and hospital_row[5] else 0
        hospital_info = {
            'vendor_no': vendor_id_10,
            'name': hospital_row[0] if hospital_row else f'รพ. {vendor_id_5}',
            'level': hospital_row[1] if hospital_row else None,
            'province': hospital_row[2] if hospital_row else None,
            'health_region': hospital_row[3] if hospital_row else None,
            'actual_beds': actual_beds
        }

        # Get current year summary
        cursor.execute("""
            SELECT
                COUNT(*) as records,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(wait_amount), 0) as wait_amount,
                COALESCE(SUM(debt_amount), 0) as debt_amount,
                COALESCE(SUM(bond_amount), 0) as bond_amount
            FROM smt_budget_transfers
            WHERE (vendor_no = %s OR vendor_no = %s)
              AND run_date >= %s AND run_date <= %s
        """, (vendor_id_10, vendor_id_5, start_date, end_date))
        summary_row = cursor.fetchone()

        # Get previous year total for YoY
        cursor.execute("""
            SELECT COALESCE(SUM(total_amount), 0) as prev_total
            FROM smt_budget_transfers
            WHERE (vendor_no = %s OR vendor_no = %s)
              AND run_date >= %s AND run_date <= %s
        """, (vendor_id_10, vendor_id_5, prev_start_date, prev_end_date))
        prev_row = cursor.fetchone()
        prev_total = float(prev_row[0]) if prev_row and prev_row[0] else 0

        total_amount = float(summary_row[1]) if summary_row else 0
        wait_amount = float(summary_row[2]) if summary_row else 0
        debt_amount = float(summary_row[3]) if summary_row else 0

        growth_yoy = ((total_amount - prev_total) / prev_total * 100) if prev_total > 0 else 0

        # Calculate per-bed metrics
        revenue_per_bed = (total_amount / actual_beds) if actual_beds > 0 else 0
        wait_per_bed = (wait_amount / actual_beds) if actual_beds > 0 else 0
        debt_per_bed = (debt_amount / actual_beds) if actual_beds > 0 else 0

        # Get fund breakdown by category
        # Categories: OPD, IPD, CR (Central Reimburse), PP (Prevention/Promotion), OTHER
        # Note: %% escapes % for Python string formatting in psycopg2
        like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
        fund_case = f"""CASE
                    WHEN fund_name {like_op} '%%ผู้ป่วยใน%%' OR fund_name = 'IP_CF' THEN 'IPD'
                    WHEN fund_name {like_op} '%%ผู้ป่วยนอก%%' OR fund_name = 'OP_CF' THEN 'OPD'
                    WHEN fund_name {like_op} '%%CENTRAL REIMBURSE%%' THEN 'CR'
                    WHEN fund_name {like_op} '%%สร้างเสริมสุขภาพ%%'
                         OR fund_name {like_op} '%%ป้องกันโรค%%'
                         OR fund_name {like_op} '%%ควบคุม%%ป้องกัน%%' THEN 'PP'
                    ELSE 'OTHER'
                END"""
        cursor.execute(f"""
            SELECT
                {fund_case} as fund_category,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(wait_amount), 0) as wait_amount,
                COALESCE(SUM(debt_amount), 0) as debt_amount,
                COUNT(*) as records
            FROM smt_budget_transfers
            WHERE (vendor_no = %s OR vendor_no = %s)
              AND run_date >= %s AND run_date <= %s
            GROUP BY {fund_case}
        """, (vendor_id_10, vendor_id_5, start_date, end_date))

        # Initialize fund categories
        fund_categories = {
            'OPD': {'total_amount': 0, 'wait_amount': 0, 'debt_amount': 0, 'records': 0, 'label': 'ผู้ป่วยนอก'},
            'IPD': {'total_amount': 0, 'wait_amount': 0, 'debt_amount': 0, 'records': 0, 'label': 'ผู้ป่วยใน'},
            'CR': {'total_amount': 0, 'wait_amount': 0, 'debt_amount': 0, 'records': 0, 'label': 'Central Reimburse'},
            'PP': {'total_amount': 0, 'wait_amount': 0, 'debt_amount': 0, 'records': 0, 'label': 'ส่งเสริมป้องกัน'},
            'OTHER': {'total_amount': 0, 'wait_amount': 0, 'debt_amount': 0, 'records': 0, 'label': 'อื่นๆ'}
        }

        ipd_total = 0
        ipd_wait = 0
        ipd_debt = 0
        opd_total = 0
        for row in cursor.fetchall():
            cat = row[0]
            if cat in fund_categories:
                fund_categories[cat]['total_amount'] = float(row[1]) if row[1] else 0
                fund_categories[cat]['wait_amount'] = float(row[2]) if row[2] else 0
                fund_categories[cat]['debt_amount'] = float(row[3]) if row[3] else 0
                fund_categories[cat]['records'] = row[4]
            if cat == 'IPD':
                ipd_total = float(row[1]) if row[1] else 0
                ipd_wait = float(row[2]) if row[2] else 0
                ipd_debt = float(row[3]) if row[3] else 0
            elif cat == 'OPD':
                opd_total = float(row[1]) if row[1] else 0

        # Calculate per-bed metrics from IPD only (beds are for inpatients)
        ipd_revenue_per_bed = (ipd_total / actual_beds) if actual_beds > 0 else 0
        ipd_wait_per_bed = (ipd_wait / actual_beds) if actual_beds > 0 else 0
        ipd_debt_per_bed = (ipd_debt / actual_beds) if actual_beds > 0 else 0

        # Calculate ratios for each fund category
        for cat in fund_categories:
            cat_amount = fund_categories[cat]['total_amount']
            fund_categories[cat]['ratio'] = round((cat_amount / total_amount * 100) if total_amount > 0 else 0, 1)

        summary = {
            'total_amount': total_amount,
            'wait_amount': wait_amount,
            'debt_amount': debt_amount,
            'bond_amount': float(summary_row[4]) if summary_row else 0,
            'wait_ratio': (wait_amount / total_amount * 100) if total_amount > 0 else 0,
            'debt_ratio': (debt_amount / total_amount * 100) if total_amount > 0 else 0,
            'record_count': summary_row[0] if summary_row else 0,
            'growth_yoy': round(growth_yoy, 1),
            # Per-bed metrics (all from IPD since beds are for inpatients)
            'actual_beds': actual_beds,
            'revenue_per_bed': round(ipd_revenue_per_bed, 2),  # IPD revenue per bed
            'ipd_revenue_per_bed': round(ipd_revenue_per_bed, 2),  # same as above (for backward compat)
            'wait_per_bed': round(ipd_wait_per_bed, 2),  # IPD wait per bed
            'debt_per_bed': round(ipd_debt_per_bed, 2),  # IPD debt per bed
            # Fund category breakdown (OPD, IPD, CR, PP, OTHER)
            'fund_categories': fund_categories,
            # Legacy OPD/IPD fields for backward compatibility
            'ipd_amount': ipd_total,
            'opd_amount': opd_total,
            'ipd_ratio': round((ipd_total / total_amount * 100) if total_amount > 0 else 0, 1),
            'opd_ratio': round((opd_total / total_amount * 100) if total_amount > 0 else 0, 1)
        }

        # Get fund breakdown
        cursor.execute("""
            SELECT
                fund_name,
                fund_group,
                fund_group_desc,
                COALESCE(SUM(total_amount), 0) as amount,
                COUNT(*) as records
            FROM smt_budget_transfers
            WHERE (vendor_no = %s OR vendor_no = %s)
              AND run_date >= %s AND run_date <= %s
            GROUP BY fund_name, fund_group, fund_group_desc
            ORDER BY amount DESC
        """, (vendor_id_10, vendor_id_5, start_date, end_date))

        fund_rows = cursor.fetchall()
        fund_breakdown = []
        for row in fund_rows:
            amount = float(row[3]) if row[3] else 0
            fund_breakdown.append({
                'fund_name': row[0] or 'ไม่ระบุ',
                'fund_group': row[1],
                'fund_group_desc': row[2],
                'amount': amount,
                'percentage': (amount / total_amount * 100) if total_amount > 0 else 0,
                'records': row[4]
            })

        # Get monthly trend
        cursor.execute("""
            SELECT
                """ + sql_format_year_month('run_date') + """ as month,
                COALESCE(SUM(total_amount), 0) as total_amount,
                COALESCE(SUM(wait_amount), 0) as wait_amount,
                COALESCE(SUM(debt_amount), 0) as debt_amount,
                COUNT(*) as records
            FROM smt_budget_transfers
            WHERE (vendor_no = %s OR vendor_no = %s)
              AND run_date >= %s AND run_date <= %s
            GROUP BY """ + sql_format_year_month('run_date') + """
            ORDER BY month
        """, (vendor_id_10, vendor_id_5, start_date, end_date))

        monthly_rows = cursor.fetchall()
        monthly_trend = []
        for row in monthly_rows:
            monthly_trend.append({
                'month': row[0],
                'total_amount': float(row[1]) if row[1] else 0,
                'wait_amount': float(row[2]) if row[2] else 0,
                'debt_amount': float(row[3]) if row[3] else 0,
                'records': row[4]
            })

        # Calculate risk score
        wait_ratio = summary['wait_ratio']
        debt_ratio = summary['debt_ratio']

        wait_score = min(100, (wait_ratio / 20) * 100)  # 20% = max risk
        debt_score = min(100, (debt_ratio / 15) * 100)  # 15% = max risk
        # Growth score: positive growth = no risk, negative growth = risk (capped at 100)
        if growth_yoy >= 0:
            growth_score = 0
        else:
            growth_score = min(100, abs(growth_yoy) * 2)  # -50% growth = 100 risk

        risk_score = int(wait_score * 0.3 + debt_score * 0.4 + growth_score * 0.3)
        risk_level = 'low' if risk_score < 40 else ('medium' if risk_score < 70 else 'high')

        risk_assessment = {
            'score': risk_score,
            'level': risk_level,
            'indicators': [
                {'name': 'Wait Ratio', 'value': round(wait_ratio, 1), 'threshold': 10, 'status': 'pass' if wait_ratio < 10 else 'fail'},
                {'name': 'Debt Ratio', 'value': round(debt_ratio, 1), 'threshold': 5, 'status': 'pass' if debt_ratio < 5 else 'fail'},
                {'name': 'Growth YoY', 'value': round(growth_yoy, 1), 'threshold': 0, 'status': 'pass' if growth_yoy > 0 else 'fail'}
            ]
        }

        # Get ranking (national)
        cursor.execute("""
            WITH hospital_totals AS (
                SELECT
                    vendor_no,
                    SUM(total_amount) as total
                FROM smt_budget_transfers
                WHERE run_date >= %s AND run_date <= %s
                GROUP BY vendor_no
            )
            SELECT
                COUNT(*) as total_hospitals,
                SUM(CASE WHEN total > %s THEN 1 ELSE 0 END) as hospitals_above
            FROM hospital_totals
        """, (start_date, end_date, total_amount))
        rank_row = cursor.fetchone()
        total_hospitals = int(rank_row[0]) if rank_row and rank_row[0] else 0
        hospitals_above = int(rank_row[1]) if rank_row and rank_row[1] else 0
        national_rank = hospitals_above + 1

        ranking = {
            'national': {
                'rank': national_rank,
                'total': total_hospitals,
                'percentile': int((1 - national_rank / total_hospitals) * 100) if total_hospitals > 0 else 0
            }
        }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'fiscal_year': fiscal_year,
            'hospital': hospital_info,
            'summary': summary,
            'fund_breakdown': fund_breakdown,
            'monthly_trend': monthly_trend,
            'risk_score': risk_assessment,
            'ranking': ranking
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@benchmark_api_bp.route('/api/benchmark/region-average')
def api_benchmark_region_average():
    """Get regional average for comparison"""
    try:
        health_region = request.args.get('health_region')
        fiscal_year = request.args.get('fiscal_year')

        if not health_region:
            return jsonify({'success': False, 'error': 'health_region is required'}), 400

        # Default to current fiscal year
        if not fiscal_year:
            today = datetime.now(TZ_BANGKOK)
            fiscal_year = today.year + 543 if today.month >= 10 else today.year + 542

        fiscal_year = int(fiscal_year)
        # health_region in DB is "เขตสุขภาพที่ X", build match pattern
        health_region_pattern = f"เขตสุขภาพที่ {health_region}"

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Convert fiscal year to date range using standardized calculation
        start_date, end_date = get_fiscal_year_range_gregorian(fiscal_year)

        # Get regional averages
        ltrim_expr = "TRIM(LEADING '0' FROM s.vendor_no)" if DB_TYPE == 'mysql' else "LTRIM(s.vendor_no, '0')"
        cursor.execute(f"""
            WITH hospital_totals AS (
                SELECT
                    s.vendor_no,
                    SUM(s.total_amount) as total_amount,
                    SUM(s.wait_amount) as wait_amount,
                    SUM(s.debt_amount) as debt_amount
                FROM smt_budget_transfers s
                JOIN health_offices h ON (
                    h.hcode5 = {ltrim_expr}
                    OR h.hcode5 = s.vendor_no
                )
                WHERE h.health_region = %s
                  AND s.run_date >= %s AND s.run_date <= %s
                GROUP BY s.vendor_no
            )
            SELECT
                COUNT(*) as hospital_count,
                COALESCE(AVG(total_amount), 0) as avg_total,
                COALESCE(AVG(wait_amount), 0) as avg_wait,
                COALESCE(AVG(debt_amount), 0) as avg_debt,
                COALESCE(SUM(total_amount), 0) as sum_total
            FROM hospital_totals
        """, (health_region_pattern, start_date, end_date))
        avg_row = cursor.fetchone()

        averages = {
            'hospital_count': avg_row[0] if avg_row else 0,
            'avg_total_amount': float(avg_row[1]) if avg_row else 0,
            'avg_wait_amount': float(avg_row[2]) if avg_row else 0,
            'avg_debt_amount': float(avg_row[3]) if avg_row else 0,
            'total_amount': float(avg_row[4]) if avg_row else 0
        }

        avg_total = averages['avg_total_amount']
        averages['avg_wait_ratio'] = (averages['avg_wait_amount'] / avg_total * 100) if avg_total > 0 else 0
        averages['avg_debt_ratio'] = (averages['avg_debt_amount'] / avg_total * 100) if avg_total > 0 else 0

        # Get fund breakdown averages for region
        cursor.execute(f"""
            WITH hospital_funds AS (
                SELECT
                    s.vendor_no,
                    s.fund_name,
                    s.fund_group,
                    SUM(s.total_amount) as amount
                FROM smt_budget_transfers s
                JOIN health_offices h ON (
                    h.hcode5 = {ltrim_expr}
                    OR h.hcode5 = s.vendor_no
                )
                WHERE h.health_region = %s
                  AND s.run_date >= %s AND s.run_date <= %s
                GROUP BY s.vendor_no, s.fund_name, s.fund_group
            )
            SELECT
                fund_name,
                fund_group,
                AVG(amount) as avg_amount,
                SUM(amount) as total_amount
            FROM hospital_funds
            GROUP BY fund_name, fund_group
            ORDER BY total_amount DESC
        """, (health_region_pattern, start_date, end_date))

        fund_rows = cursor.fetchall()
        fund_breakdown = []
        for row in fund_rows:
            fund_breakdown.append({
                'fund_name': row[0] or 'ไม่ระบุ',
                'fund_group': row[1],
                'avg_amount': float(row[2]) if row[2] else 0,
                'total_amount': float(row[3]) if row[3] else 0
            })

        # Get monthly trend for region
        month_format = sql_format_year_month('s.run_date')
        cursor.execute(f"""
            SELECT
                {month_format} as month,
                COALESCE(SUM(s.total_amount), 0) as total_amount,
                COALESCE(AVG(s.total_amount), 0) as avg_amount
            FROM smt_budget_transfers s
            JOIN health_offices h ON (
                h.hcode5 = {ltrim_expr}
                OR h.hcode5 = s.vendor_no
            )
            WHERE h.health_region = %s
              AND s.run_date >= %s AND s.run_date <= %s
            GROUP BY {month_format}
            ORDER BY month
        """, (health_region_pattern, start_date, end_date))

        monthly_rows = cursor.fetchall()
        monthly_trend = []
        for row in monthly_rows:
            monthly_trend.append({
                'month': row[0],
                'total_amount': float(row[1]) if row[1] else 0,
                'avg_amount': float(row[2]) if row[2] else 0
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'region': request.args.get('health_region'),
            'fiscal_year': fiscal_year,
            'averages': averages,
            'fund_breakdown': fund_breakdown,
            'monthly_trend': monthly_trend
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@benchmark_api_bp.route('/api/benchmark/hospitals/<vendor_no>', methods=['DELETE'])
def api_benchmark_delete_hospital(vendor_no):
    """Delete SMT data for a specific hospital"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Delete all records for this vendor
        cursor.execute("""
            DELETE FROM smt_budget_transfers
            WHERE vendor_no = %s OR vendor_no = %s
        """, (vendor_no, vendor_no.zfill(10)))

        deleted = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Deleted {deleted} records for vendor {vendor_no}'
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500


@benchmark_api_bp.route('/api/benchmark/available-years')
def api_benchmark_available_years():
    """Get list of fiscal years that have SMT data in the database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get distinct fiscal years from smt_budget_transfers
        # Fiscal year is determined by run_date: Oct-Dec = next year, Jan-Sep = current year
        year_expr = sql_extract_year('run_date')
        month_expr = sql_extract_month('run_date')
        cursor.execute(f"""
            SELECT DISTINCT
                CASE
                    WHEN {month_expr} >= 10 THEN {year_expr} + 544
                    ELSE {year_expr} + 543
                END as fiscal_year
            FROM smt_budget_transfers
            WHERE run_date IS NOT NULL
            ORDER BY fiscal_year DESC
        """)

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        years = [int(row[0]) for row in rows]

        return jsonify({
            'success': True,
            'years': years
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500
