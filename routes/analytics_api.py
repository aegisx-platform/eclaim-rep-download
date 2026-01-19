"""Analytics API Blueprint - Comprehensive claim analysis endpoints"""

import os
import csv
import io
from calendar import monthrange
from flask import Blueprint, request, jsonify, Response, g, current_app
from flask_login import login_required
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from zoneinfo import ZoneInfo
import traceback

from config.database import get_db_config, DB_TYPE
from config.db_pool import get_connection as get_pooled_connection
from utils.settings_manager import SettingsManager
from utils.fiscal_year import (
    get_fiscal_year_sql_filter_gregorian,
    get_fiscal_year_range_gregorian,
    get_fiscal_year_range_be
)
from utils.logging_config import safe_format_exception

# Initialize settings manager
settings_manager = SettingsManager()

# Create blueprint
analytics_api_bp = Blueprint('analytics_api', __name__)


# Database-specific SQL helpers for PostgreSQL/MySQL compatibility
def sql_date_trunc_month(column: str) -> str:
    """Generate SQL for truncating date to month start"""
    if DB_TYPE == 'mysql':
        return f"DATE_FORMAT({column}, '%%Y-%%m-01')"
    return f"DATE_TRUNC('month', {column})"


def sql_count_distinct_months(column: str) -> str:
    """Generate SQL for counting distinct months"""
    if DB_TYPE == 'mysql':
        return f"COUNT(DISTINCT DATE_FORMAT({column}, '%%Y-%%m'))"
    return f"COUNT(DISTINCT DATE_TRUNC('month', {column}))"


def sql_current_month_start() -> str:
    """Generate SQL for start of current month"""
    if DB_TYPE == 'mysql':
        return "DATE_FORMAT(CURRENT_DATE, '%%Y-%%m-01')"
    return "DATE_TRUNC('month', CURRENT_DATE)"


def sql_interval_months(months: int) -> str:
    """Generate SQL for interval in months"""
    if DB_TYPE == 'mysql':
        return f"INTERVAL {months} MONTH"
    return f"INTERVAL '{months} months'"


def sql_interval_days(days: int) -> str:
    """Generate SQL for interval in days"""
    if DB_TYPE == 'mysql':
        return f"INTERVAL {days} DAY"
    return f"INTERVAL '{days} days'"


def sql_format_year_month(column: str) -> str:
    """Generate SQL for formatting date as YYYY-MM"""
    if DB_TYPE == 'mysql':
        return f"DATE_FORMAT({column}, '%%Y-%%m')"
    return f"TO_CHAR({column}, 'YYYY-MM')"


def sql_format_month(column: str) -> str:
    """Generate SQL for formatting date as YYYY-MM (alias for sql_format_year_month)"""
    return sql_format_year_month(column)


def sql_cast_numeric(expr: str) -> str:
    """Generate SQL for casting to numeric type"""
    if DB_TYPE == 'mysql':
        return f"CAST({expr} AS DECIMAL(15,2))"
    return f"CAST({expr} AS NUMERIC)"


def sql_coalesce_numeric(column: str, default: str = "0") -> str:
    """Generate SQL for COALESCE with numeric default"""
    if DB_TYPE == 'mysql':
        return f"COALESCE(CAST({column} AS DECIMAL(15,2)), {default})"
    return f"COALESCE({column}, {default})"


def sql_extract_year(column: str) -> str:
    """Generate SQL for extracting year from date"""
    if DB_TYPE == 'mysql':
        return f"YEAR({column})"
    return f"EXTRACT(YEAR FROM {column})"


def sql_extract_month(column: str) -> str:
    """Generate SQL for extracting month from date"""
    if DB_TYPE == 'mysql':
        return f"MONTH({column})"
    return f"EXTRACT(MONTH FROM {column})"


def sql_regex_match(column: str, pattern: str) -> str:
    """Generate SQL for regex matching"""
    if DB_TYPE == 'mysql':
        return f"{column} REGEXP '{pattern}'"
    return f"{column} ~ '{pattern}'"


def get_db_connection():
    """Get database connection from pool"""
    try:
        conn = get_pooled_connection()
        if conn is None:
            current_current_app.logger.error("Failed to get connection from pool")
        return conn
    except Exception as e:
        current_current_app.logger.error(f"Database connection error: {e}")
        return None


def _validate_date_param(date_str):
    """
    Validate date parameter format (YYYY-MM-DD).
    Returns validated date string or None if invalid.
    """
    if not date_str:
        return None
    import re
    # Strict format: YYYY-MM-DD with valid ranges
    if not re.match(r'^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$', date_str):
        return None
    return date_str


def get_analytics_date_filter():
    """
    Get date filter parameters from request args.
    Returns tuple: (where_clause, params, filter_info)

    Supports:
    - fiscal_year: Buddhist Era fiscal year (e.g., 2569 = Oct 2025 - Sep 2026)
    - start_date: Start date in YYYY-MM-DD format
    - end_date: End date in YYYY-MM-DD format

    All parameters are validated and passed via parameterized queries.
    """
    fiscal_year = request.args.get('fiscal_year', type=int)
    start_date = _validate_date_param(request.args.get('start_date'))
    end_date = _validate_date_param(request.args.get('end_date'))

    where_clauses = []
    params = []
    filter_info = {}

    if fiscal_year:
        # Use standardized fiscal year calculation from utils/fiscal_year.py
        # FY 2569 BE = Oct 2025 CE - Sep 2026 CE (1 Oct 2025 - 30 Sep 2026)
        where_clause, where_params = get_fiscal_year_sql_filter_gregorian(fiscal_year, 'dateadm')
        where_clauses.append(where_clause)
        params.extend(where_params)
        filter_info['fiscal_year'] = fiscal_year
        filter_info['date_range'] = f"{where_params[0]} to {where_params[1]}"
    elif start_date or end_date:
        if start_date:
            where_clauses.append("dateadm >= %s")
            params.append(start_date)
            filter_info['start_date'] = start_date
        if end_date:
            where_clauses.append("dateadm <= %s")
            params.append(end_date)
            filter_info['end_date'] = end_date

    where_clause = " AND ".join(where_clauses) if where_clauses else ""
    return where_clause, params, filter_info


def get_available_fiscal_years(cursor):
    """Get list of available fiscal years from data"""
    year_expr = sql_extract_year('dateadm')
    month_expr = sql_extract_month('dateadm')
    cursor.execute(f"""
        SELECT DISTINCT
            CASE
                WHEN {month_expr} >= 10 THEN {year_expr} + 544
                ELSE {year_expr} + 543
            END as fiscal_year
        FROM claim_rep_opip_nhso_item
        WHERE dateadm IS NOT NULL
        ORDER BY fiscal_year DESC
    """)
    return [row[0] for row in cursor.fetchall()]


# ============================================================================
# Analytics Routes
# ============================================================================

@analytics_api_bp.route('/api/analytics/summary')
@analytics_api_bp.route('/api/analysis/summary')  # Legacy alias
def api_analysis_summary():
    """Get summary statistics for all data types with optional filters"""
    # Get filter parameters
    fiscal_year = request.args.get('fiscal_year', type=int)
    start_month = request.args.get('start_month', type=int)
    end_month = request.args.get('end_month', type=int)
    scheme = request.args.get('scheme', '').strip()
    service_type = request.args.get('service_type', '').strip()

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Build date range for filtering (fiscal year starts in October)
        # fiscal_year 2568 means Oct 2024 - Sep 2025 (Gregorian: Oct 2024 = Oct 2024)
        where_clauses_rep = []
        where_clauses_stm = []
        date_filter_smt = ""
        params_rep = []
        params_stm = []
        params_smt = []

        # Add scheme filter (REP only - stm_claim_item doesn't have scheme)
        if scheme:
            where_clauses_rep.append("scheme = %s")
            params_rep.append(scheme)

        # Add service_type filter (OP or IP - matches file_type prefix)
        if service_type:
            where_clauses_rep.append("file_type LIKE %s")
            params_rep.append(f"{service_type}%")

        if fiscal_year:
            # Fiscal year in Thai BE: FY 2569 = Oct 2568 to Sep 2569 (Gregorian: Oct 2025 to Sep 2026)
            # Use standardized fiscal year calculation
            fy_start, fy_end = get_fiscal_year_range_gregorian(fiscal_year)

            # SMT uses Thai BE format YYYYMMDD (e.g., "25681001" for Oct 1, 2568)
            smt_fy_start, smt_fy_end = get_fiscal_year_range_be(fiscal_year)

            # Calculate Gregorian years for fiscal year
            # FY 2569 = Oct 2025 - Sep 2026
            # Start year (for Oct-Dec months): fiscal_year - 543 - 1
            # End year (for Jan-Sep months): fiscal_year - 543
            fy_start_gregorian_year = fiscal_year - 543 - 1  # e.g., 2569 - 543 - 1 = 2025
            fy_end_gregorian_year = fiscal_year - 543        # e.g., 2569 - 543 = 2026

            # If specific months are selected
            if start_month and end_month:
                # Adjust for fiscal year (Oct=1, Nov=2, ..., Sep=12 in fiscal terms)
                # But user selects calendar months (1=Jan, ..., 12=Dec)
                # So we need to convert calendar months to actual dates
                if start_month >= 10:
                    start_date = f"{fy_start_gregorian_year}-{start_month:02d}-01"
                    smt_start = f"{fiscal_year - 1}{start_month:02d}01"
                else:
                    start_date = f"{fy_end_gregorian_year}-{start_month:02d}-01"
                    smt_start = f"{fiscal_year}{start_month:02d}01"

                if end_month >= 10:
                    end_year = fy_start_gregorian_year
                    smt_end_year = fiscal_year - 1
                else:
                    end_year = fy_end_gregorian_year
                    smt_end_year = fiscal_year

                # Get last day of end month
                from calendar import monthrange
                _, last_day = monthrange(end_year, end_month)
                end_date = f"{end_year}-{end_month:02d}-{last_day:02d}"
                smt_end = f"{smt_end_year}{end_month:02d}{last_day:02d}"

                where_clauses_rep.append("dateadm >= %s AND dateadm <= %s")
                params_rep.extend([start_date, end_date])
                where_clauses_stm.append("date_admit >= %s AND date_admit <= %s")
                params_stm.extend([start_date, end_date])
                date_filter_smt = " WHERE posting_date >= %s AND posting_date <= %s"
                params_smt = [smt_start, smt_end]
            else:
                where_clauses_rep.append("dateadm >= %s AND dateadm <= %s")
                params_rep.extend([fy_start, fy_end])
                where_clauses_stm.append("date_admit >= %s AND date_admit <= %s")
                params_stm.extend([fy_start, fy_end])
                date_filter_smt = " WHERE posting_date >= %s AND posting_date <= %s"
                params_smt = [smt_fy_start, smt_fy_end]

        # Build WHERE clauses
        date_filter_rep = ""
        if where_clauses_rep:
            date_filter_rep = " WHERE " + " AND ".join(where_clauses_rep)
        date_filter_stm = ""
        if where_clauses_stm:
            date_filter_stm = " WHERE " + " AND ".join(where_clauses_stm)

        # REP data summary
        rep_data = {'total_records': 0, 'total_amount': 0, 'files_count': 0}
        try:
            query = f"""
                SELECT COUNT(*), COALESCE(SUM(reimb_nhso), 0)
                FROM claim_rep_opip_nhso_item
                {date_filter_rep}
            """
            cursor.execute(query, params_rep)
            row = cursor.fetchone()
            rep_data['total_records'] = row[0] or 0
            rep_data['total_amount'] = float(row[1] or 0)

            if date_filter_rep:
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT file_id) FROM claim_rep_opip_nhso_item
                    {date_filter_rep}
                """, params_rep)
                rep_data['files_count'] = cursor.fetchone()[0] or 0
            else:
                cursor.execute("SELECT COUNT(*) FROM eclaim_imported_files WHERE status = 'completed'")
                rep_data['files_count'] = cursor.fetchone()[0] or 0
        except Exception as e:
            current_app.logger.warning(f"Error getting REP summary: {e}")

        # Statement data summary
        stm_data = {'total_records': 0, 'total_amount': 0, 'files_count': 0}
        try:
            query = f"""
                SELECT COUNT(*), COALESCE(SUM(paid_after_deduction), 0)
                FROM stm_claim_item
                {date_filter_stm}
            """
            cursor.execute(query, params_stm)
            row = cursor.fetchone()
            stm_data['total_records'] = row[0] or 0
            stm_data['total_amount'] = float(row[1] or 0)

            if date_filter_stm:
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT file_id) FROM stm_claim_item
                    {date_filter_stm}
                """, params_stm)
                stm_data['files_count'] = cursor.fetchone()[0] or 0
            else:
                cursor.execute("SELECT COUNT(*) FROM stm_imported_files WHERE status = 'completed'")
                stm_data['files_count'] = cursor.fetchone()[0] or 0
        except Exception as e:
            current_app.logger.warning(f"Error getting Statement summary: {e}")

        # SMT Budget summary
        smt_data = {'total_records': 0, 'total_amount': 0, 'files_count': 0}
        try:
            query = f"""
                SELECT COUNT(*), COALESCE(SUM(total_amount), 0)
                FROM smt_budget_transfers
                {date_filter_smt}
            """
            cursor.execute(query, params_smt)
            row = cursor.fetchone()
            smt_data['total_records'] = row[0] or 0
            smt_data['total_amount'] = float(row[1] or 0)

            if date_filter_smt:
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT run_date) FROM smt_budget_transfers
                    {date_filter_smt}
                """, params_smt)
                smt_data['files_count'] = cursor.fetchone()[0] or 0
            else:
                cursor.execute("SELECT COUNT(DISTINCT run_date) FROM smt_budget_transfers")
                smt_data['files_count'] = cursor.fetchone()[0] or 0
        except Exception as e:
            current_app.logger.warning(f"Error getting SMT summary: {e}")

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'rep': rep_data,
            'stm': stm_data,
            'smt': smt_data,
            'filters': {
                'fiscal_year': fiscal_year,
                'start_month': start_month,
                'end_month': end_month,
                'scheme': scheme,
                'service_type': service_type
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error in analysis summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/reconciliation')
@analytics_api_bp.route('/api/analysis/reconciliation')  # Legacy alias
def api_analysis_reconciliation():
    """
    Reconcile REP and Statement data by tran_id
    """
    # Check license feature access
    if not settings_manager.check_feature_access('reconciliation'):
        return jsonify({
            'success': False,
            'error': 'Reconciliation feature requires Basic tier or higher license',
            'upgrade_required': True,
            'current_tier': settings_manager.get_license_info().get('tier', 'trial')
        }), 403

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        rep_no_filter = request.args.get('rep_no', '').strip()
        status_filter = request.args.get('status', '').strip()
        group_by = request.args.get('group_by', 'rep_no').strip()  # 'rep_no' or 'tran_id'
        limit = request.args.get('limit', 100, type=int)

        # New filter parameters
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        diff_threshold = request.args.get('diff_threshold', 0, type=float)
        has_error = request.args.get('has_error', '').strip() == 'true'

        # Build CTE WHERE clauses
        rep_cte_where = ["tran_id IS NOT NULL"]
        stm_cte_where = ["tran_id IS NOT NULL"]
        cte_params_rep = []
        cte_params_stm = []

        if date_from:
            rep_cte_where.append("dateadm >= %s")
            cte_params_rep.append(date_from)
            stm_cte_where.append("date_admit >= %s")
            cte_params_stm.append(date_from)

        if date_to:
            rep_cte_where.append("dateadm <= %s")
            cte_params_rep.append(date_to)
            stm_cte_where.append("date_admit <= %s")
            cte_params_stm.append(date_to)

        if has_error:
            rep_cte_where.append("error_code IS NOT NULL AND error_code != ''")

        where_clauses = []
        params = []

        if group_by == 'tran_id':
            # Transaction-level reconciliation by tran_id
            if DB_TYPE == 'mysql':
                # MySQL doesn't support FULL OUTER JOIN, use UNION of LEFT and RIGHT JOINs
                query = f"""
                    WITH rep_data AS (
                        SELECT
                            tran_id,
                            rep_no,
                            name as patient_name,
                            hn,
                            COALESCE(reimb_nhso, 0) as rep_amount
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_cte_where)}
                    ),
                    stm_data AS (
                        SELECT
                            tran_id,
                            rep_no,
                            patient_name,
                            hn,
                            COALESCE(paid_after_deduction, 0) as stm_amount
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_cte_where)}
                    ),
                    combined AS (
                        SELECT
                            COALESCE(r.tran_id, s.tran_id) as tran_id,
                            COALESCE(r.rep_no, s.rep_no) as rep_no,
                            COALESCE(r.patient_name, s.patient_name) as patient_name,
                            COALESCE(r.hn, s.hn) as hn,
                            COALESCE(r.rep_amount, 0) as rep_amount,
                            COALESCE(s.stm_amount, 0) as stm_amount,
                            COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0) as diff,
                            CASE
                                WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL
                                     AND ABS(COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0)) < 0.01 THEN 'matched'
                                WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL THEN 'diff_amount'
                                WHEN r.tran_id IS NOT NULL THEN 'rep_only'
                                ELSE 'stm_only'
                            END as status
                        FROM rep_data r
                        LEFT JOIN stm_data s ON r.tran_id = s.tran_id
                        UNION
                        SELECT
                            s.tran_id as tran_id,
                            s.rep_no as rep_no,
                            s.patient_name as patient_name,
                            s.hn as hn,
                            0 as rep_amount,
                            COALESCE(s.stm_amount, 0) as stm_amount,
                            0 - COALESCE(s.stm_amount, 0) as diff,
                            'stm_only' as status
                        FROM stm_data s
                        LEFT JOIN rep_data r ON r.tran_id = s.tran_id
                        WHERE r.tran_id IS NULL
                    )
                    SELECT * FROM combined
                """
            else:
                # PostgreSQL supports FULL OUTER JOIN natively
                query = f"""
                    WITH rep_data AS (
                        SELECT
                            tran_id,
                            rep_no,
                            name as patient_name,
                            hn,
                            COALESCE(reimb_nhso, 0) as rep_amount
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_cte_where)}
                    ),
                    stm_data AS (
                        SELECT
                            tran_id,
                            rep_no,
                            patient_name,
                            hn,
                            COALESCE(paid_after_deduction, 0) as stm_amount
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_cte_where)}
                    )
                    SELECT
                        COALESCE(r.tran_id, s.tran_id) as tran_id,
                        COALESCE(r.rep_no, s.rep_no) as rep_no,
                        COALESCE(r.patient_name, s.patient_name) as patient_name,
                        COALESCE(r.hn, s.hn) as hn,
                        COALESCE(r.rep_amount, 0) as rep_amount,
                        COALESCE(s.stm_amount, 0) as stm_amount,
                        COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0) as diff,
                        CASE
                            WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL
                                 AND ABS(COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0)) < 0.01 THEN 'matched'
                            WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL THEN 'diff_amount'
                            WHEN r.tran_id IS NOT NULL THEN 'rep_only'
                            ELSE 'stm_only'
                        END as status
                    FROM rep_data r
                    FULL OUTER JOIN stm_data s ON r.tran_id = s.tran_id
                """

            # CTE params first
            params.extend(cte_params_rep)
            params.extend(cte_params_stm)

            # ILIKE is PostgreSQL-specific, MySQL LIKE is case-insensitive by default
            like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
            if rep_no_filter:
                # In tran_id mode, search by both tran_id and rep_no
                where_clauses.append(f"(tran_id {like_op} %s OR rep_no {like_op} %s)")
                params.extend([f'%{rep_no_filter}%', f'%{rep_no_filter}%'])

            if status_filter:
                where_clauses.append("status = %s")
                params.append(status_filter)

            if diff_threshold > 0:
                where_clauses.append("ABS(diff) >= %s")
                params.append(diff_threshold)

        else:
            # REP-level reconciliation by rep_no (aggregate)
            # Build WHERE clauses for rep_no mode
            rep_where = ["rep_no IS NOT NULL AND rep_no != ''"]
            stm_where = ["rep_no IS NOT NULL AND rep_no != ''"]

            if date_from:
                rep_where.append("dateadm >= %s")
                stm_where.append("date_admit >= %s")
            if date_to:
                rep_where.append("dateadm <= %s")
                stm_where.append("date_admit <= %s")
            if has_error:
                rep_where.append("error_code IS NOT NULL AND error_code != ''")

            if DB_TYPE == 'mysql':
                # MySQL doesn't support FULL OUTER JOIN
                query = f"""
                    WITH rep_data AS (
                        SELECT
                            rep_no,
                            SUM(COALESCE(reimb_nhso, 0)) as rep_amount,
                            COUNT(*) as rep_count
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_where)}
                        GROUP BY rep_no
                    ),
                    stm_data AS (
                        SELECT
                            rep_no,
                            SUM(COALESCE(paid_after_deduction, 0)) as stm_amount,
                            COUNT(*) as stm_count
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_where)}
                        GROUP BY rep_no
                    ),
                    combined AS (
                        SELECT
                            COALESCE(r.rep_no, s.rep_no) as rep_no,
                            COALESCE(r.rep_count, 0) as rep_count,
                            COALESCE(s.stm_count, 0) as stm_count,
                            COALESCE(r.rep_amount, 0) as rep_amount,
                            COALESCE(s.stm_amount, 0) as stm_amount,
                            COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0) as diff,
                            CASE
                                WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL
                                     AND ABS(COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0)) < 0.01 THEN 'matched'
                                WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL THEN 'diff_amount'
                                WHEN r.rep_no IS NOT NULL THEN 'rep_only'
                                ELSE 'stm_only'
                            END as status
                        FROM rep_data r
                        LEFT JOIN stm_data s ON r.rep_no = s.rep_no
                        UNION
                        SELECT
                            s.rep_no as rep_no,
                            0 as rep_count,
                            COALESCE(s.stm_count, 0) as stm_count,
                            0 as rep_amount,
                            COALESCE(s.stm_amount, 0) as stm_amount,
                            0 - COALESCE(s.stm_amount, 0) as diff,
                            'stm_only' as status
                        FROM stm_data s
                        LEFT JOIN rep_data r ON r.rep_no = s.rep_no
                        WHERE r.rep_no IS NULL
                    )
                    SELECT * FROM combined
                """
            else:
                # PostgreSQL supports FULL OUTER JOIN
                query = f"""
                    WITH rep_data AS (
                        SELECT
                            rep_no,
                            SUM(COALESCE(reimb_nhso, 0)) as rep_amount,
                            COUNT(*) as rep_count
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_where)}
                        GROUP BY rep_no
                    ),
                    stm_data AS (
                        SELECT
                            rep_no,
                            SUM(COALESCE(paid_after_deduction, 0)) as stm_amount,
                            COUNT(*) as stm_count
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_where)}
                        GROUP BY rep_no
                    )
                    SELECT
                        COALESCE(r.rep_no, s.rep_no) as rep_no,
                        COALESCE(r.rep_count, 0) as rep_count,
                        COALESCE(s.stm_count, 0) as stm_count,
                        COALESCE(r.rep_amount, 0) as rep_amount,
                        COALESCE(s.stm_amount, 0) as stm_amount,
                        COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0) as diff,
                        CASE
                            WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL
                                 AND ABS(COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0)) < 0.01 THEN 'matched'
                            WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL THEN 'diff_amount'
                            WHEN r.rep_no IS NOT NULL THEN 'rep_only'
                            ELSE 'stm_only'
                        END as status
                    FROM rep_data r
                    FULL OUTER JOIN stm_data s ON r.rep_no = s.rep_no
                """

            # Add CTE params for rep_no mode
            if date_from:
                params.append(date_from)
                params.append(date_from)
            if date_to:
                params.append(date_to)
                params.append(date_to)

            like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
            if rep_no_filter:
                where_clauses.append(f"rep_no {like_op} %s")
                params.append(f'%{rep_no_filter}%')

            if status_filter:
                where_clauses.append("status = %s")
                params.append(status_filter)

            if diff_threshold > 0:
                where_clauses.append("ABS(diff) >= %s")
                params.append(diff_threshold)

        if where_clauses:
            query = f"SELECT * FROM ({query}) sub WHERE " + " AND ".join(where_clauses)

        query += f" LIMIT {limit}"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        records = []
        if group_by == 'tran_id':
            # Transaction-level records
            for row in rows:
                records.append({
                    'tran_id': row[0],
                    'rep_no': row[1],
                    'patient_name': row[2],
                    'hn': row[3],
                    'rep_amount': float(row[4] or 0),
                    'stm_amount': float(row[5] or 0),
                    'diff': float(row[6] or 0),
                    'status': row[7]
                })

            # Stats for tran_id mode
            if DB_TYPE == 'mysql':
                # MySQL doesn't support FULL OUTER JOIN, use UNION of LEFT and RIGHT JOINs
                stats_query = """
                    WITH rep_data AS (
                        SELECT tran_id, COALESCE(reimb_nhso, 0) as amount
                        FROM claim_rep_opip_nhso_item WHERE tran_id IS NOT NULL
                    ),
                    stm_data AS (
                        SELECT tran_id, COALESCE(paid_after_deduction, 0) as amount
                        FROM stm_claim_item WHERE tran_id IS NOT NULL
                    ),
                    combined AS (
                        SELECT r.tran_id as r_tran_id, r.amount as r_amount, s.tran_id as s_tran_id, s.amount as s_amount
                        FROM rep_data r LEFT JOIN stm_data s ON r.tran_id = s.tran_id
                        UNION
                        SELECT r.tran_id as r_tran_id, r.amount as r_amount, s.tran_id as s_tran_id, s.amount as s_amount
                        FROM stm_data s LEFT JOIN rep_data r ON r.tran_id = s.tran_id
                        WHERE r.tran_id IS NULL
                    )
                    SELECT
                        COUNT(CASE WHEN r_tran_id IS NOT NULL AND s_tran_id IS NOT NULL AND ABS(r_amount - s_amount) < 0.01 THEN 1 END) as matched,
                        COUNT(CASE WHEN r_tran_id IS NOT NULL AND s_tran_id IS NULL THEN 1 END) as rep_only,
                        COUNT(CASE WHEN r_tran_id IS NULL AND s_tran_id IS NOT NULL THEN 1 END) as stm_only,
                        COUNT(CASE WHEN r_tran_id IS NOT NULL AND s_tran_id IS NOT NULL AND ABS(r_amount - s_amount) >= 0.01 THEN 1 END) as diff_amount
                    FROM combined
                """
            else:
                # PostgreSQL supports FULL OUTER JOIN natively
                stats_query = """
                    WITH rep_data AS (
                        SELECT tran_id, COALESCE(reimb_nhso, 0) as amount
                        FROM claim_rep_opip_nhso_item WHERE tran_id IS NOT NULL
                    ),
                    stm_data AS (
                        SELECT tran_id, COALESCE(paid_after_deduction, 0) as amount
                        FROM stm_claim_item WHERE tran_id IS NOT NULL
                    )
                    SELECT
                        COUNT(CASE WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL AND ABS(r.amount - s.amount) < 0.01 THEN 1 END) as matched,
                        COUNT(CASE WHEN r.tran_id IS NOT NULL AND s.tran_id IS NULL THEN 1 END) as rep_only,
                        COUNT(CASE WHEN r.tran_id IS NULL AND s.tran_id IS NOT NULL THEN 1 END) as stm_only,
                        COUNT(CASE WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL AND ABS(r.amount - s.amount) >= 0.01 THEN 1 END) as diff_amount
                    FROM rep_data r
                    FULL OUTER JOIN stm_data s ON r.tran_id = s.tran_id
                """
        else:
            # REP-level records
            for row in rows:
                records.append({
                    'rep_no': row[0],
                    'rep_count': int(row[1] or 0),
                    'stm_count': int(row[2] or 0),
                    'rep_amount': float(row[3] or 0),
                    'stm_amount': float(row[4] or 0),
                    'diff': float(row[5] or 0),
                    'status': row[6]
                })

            # Stats for rep_no mode
            if DB_TYPE == 'mysql':
                # MySQL doesn't support FULL OUTER JOIN
                stats_query = """
                    WITH rep_data AS (
                        SELECT rep_no, SUM(COALESCE(reimb_nhso, 0)) as amount
                        FROM claim_rep_opip_nhso_item
                        WHERE rep_no IS NOT NULL AND rep_no != ''
                        GROUP BY rep_no
                    ),
                    stm_data AS (
                        SELECT rep_no, SUM(COALESCE(paid_after_deduction, 0)) as amount
                        FROM stm_claim_item
                        WHERE rep_no IS NOT NULL AND rep_no != ''
                        GROUP BY rep_no
                    ),
                    combined AS (
                        SELECT r.rep_no as r_rep_no, r.amount as r_amount, s.rep_no as s_rep_no, s.amount as s_amount
                        FROM rep_data r LEFT JOIN stm_data s ON r.rep_no = s.rep_no
                        UNION
                        SELECT r.rep_no as r_rep_no, r.amount as r_amount, s.rep_no as s_rep_no, s.amount as s_amount
                        FROM stm_data s LEFT JOIN rep_data r ON r.rep_no = s.rep_no
                        WHERE r.rep_no IS NULL
                    )
                    SELECT
                        COUNT(CASE WHEN r_rep_no IS NOT NULL AND s_rep_no IS NOT NULL AND ABS(r_amount - s_amount) < 0.01 THEN 1 END) as matched,
                        COUNT(CASE WHEN r_rep_no IS NOT NULL AND s_rep_no IS NULL THEN 1 END) as rep_only,
                        COUNT(CASE WHEN r_rep_no IS NULL AND s_rep_no IS NOT NULL THEN 1 END) as stm_only,
                        COUNT(CASE WHEN r_rep_no IS NOT NULL AND s_rep_no IS NOT NULL AND ABS(r_amount - s_amount) >= 0.01 THEN 1 END) as diff_amount
                    FROM combined
                """
            else:
                # PostgreSQL supports FULL OUTER JOIN natively
                stats_query = """
                    WITH rep_data AS (
                        SELECT rep_no, SUM(COALESCE(reimb_nhso, 0)) as amount
                        FROM claim_rep_opip_nhso_item
                        WHERE rep_no IS NOT NULL AND rep_no != ''
                        GROUP BY rep_no
                    ),
                    stm_data AS (
                        SELECT rep_no, SUM(COALESCE(paid_after_deduction, 0)) as amount
                        FROM stm_claim_item
                        WHERE rep_no IS NOT NULL AND rep_no != ''
                        GROUP BY rep_no
                    )
                    SELECT
                        COUNT(CASE WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL AND ABS(r.amount - s.amount) < 0.01 THEN 1 END) as matched,
                        COUNT(CASE WHEN r.rep_no IS NOT NULL AND s.rep_no IS NULL THEN 1 END) as rep_only,
                        COUNT(CASE WHEN r.rep_no IS NULL AND s.rep_no IS NOT NULL THEN 1 END) as stm_only,
                        COUNT(CASE WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL AND ABS(r.amount - s.amount) >= 0.01 THEN 1 END) as diff_amount
                    FROM rep_data r
                    FULL OUTER JOIN stm_data s ON r.rep_no = s.rep_no
                """

        cursor.execute(stats_query)
        stats_row = cursor.fetchone()

        stats = {
            'matched': stats_row[0] or 0,
            'rep_only': stats_row[1] or 0,
            'stm_only': stats_row[2] or 0,
            'diff_amount': stats_row[3] or 0
        }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'group_by': group_by,
            'records': records,
            'stats': stats
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error in reconciliation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/export')
@analytics_api_bp.route('/api/analysis/export')  # Legacy alias
def api_analysis_export():
    """
    Export reconciliation data to CSV
    """
    import csv
    import io

    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        rep_no_filter = request.args.get('rep_no', '').strip()
        status_filter = request.args.get('status', '').strip()
        group_by = request.args.get('group_by', 'rep_no').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()
        diff_threshold = request.args.get('diff_threshold', 0, type=float)
        has_error = request.args.get('has_error', '').strip() == 'true'

        # Build CTE WHERE clauses
        rep_where = ["tran_id IS NOT NULL"] if group_by == 'tran_id' else ["rep_no IS NOT NULL AND rep_no != ''"]
        stm_where = ["tran_id IS NOT NULL"] if group_by == 'tran_id' else ["rep_no IS NOT NULL AND rep_no != ''"]
        params = []

        if date_from:
            rep_where.append("dateadm >= %s")
            stm_where.append("date_admit >= %s")
            params.extend([date_from, date_from])
        if date_to:
            rep_where.append("dateadm <= %s")
            stm_where.append("date_admit <= %s")
            params.extend([date_to, date_to])
        if has_error:
            rep_where.append("error_code IS NOT NULL AND error_code != ''")

        where_clauses = []

        if group_by == 'tran_id':
            if DB_TYPE == 'mysql':
                # MySQL doesn't support FULL OUTER JOIN
                query = f"""
                    WITH rep_data AS (
                        SELECT tran_id, rep_no, name as patient_name, hn, dateadm,
                               COALESCE(reimb_nhso, 0) as rep_amount, error_code
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_where)}
                    ),
                    stm_data AS (
                        SELECT tran_id, rep_no, patient_name, hn, date_admit,
                               COALESCE(paid_after_deduction, 0) as stm_amount
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_where)}
                    ),
                    combined AS (
                        SELECT r.tran_id as r_tran_id, r.rep_no as r_rep_no, r.patient_name as r_patient_name,
                               r.hn as r_hn, r.dateadm as r_dateadm, r.rep_amount, r.error_code,
                               s.tran_id as s_tran_id, s.rep_no as s_rep_no, s.patient_name as s_patient_name,
                               s.hn as s_hn, s.date_admit as s_date_admit, s.stm_amount
                        FROM rep_data r LEFT JOIN stm_data s ON r.tran_id = s.tran_id
                        UNION
                        SELECT r.tran_id as r_tran_id, r.rep_no as r_rep_no, r.patient_name as r_patient_name,
                               r.hn as r_hn, r.dateadm as r_dateadm, r.rep_amount, r.error_code,
                               s.tran_id as s_tran_id, s.rep_no as s_rep_no, s.patient_name as s_patient_name,
                               s.hn as s_hn, s.date_admit as s_date_admit, s.stm_amount
                        FROM stm_data s LEFT JOIN rep_data r ON r.tran_id = s.tran_id
                        WHERE r.tran_id IS NULL
                    )
                    SELECT
                        COALESCE(r_tran_id, s_tran_id) as tran_id,
                        COALESCE(r_rep_no, s_rep_no) as rep_no,
                        COALESCE(r_patient_name, s_patient_name) as patient_name,
                        COALESCE(r_hn, s_hn) as hn,
                        COALESCE(r_dateadm, s_date_admit) as date,
                        COALESCE(rep_amount, 0) as rep_amount,
                        COALESCE(stm_amount, 0) as stm_amount,
                        COALESCE(rep_amount, 0) - COALESCE(stm_amount, 0) as diff,
                        CASE
                            WHEN r_tran_id IS NOT NULL AND s_tran_id IS NOT NULL
                                 AND ABS(COALESCE(rep_amount, 0) - COALESCE(stm_amount, 0)) < 0.01 THEN 'matched'
                            WHEN r_tran_id IS NOT NULL AND s_tran_id IS NOT NULL THEN 'diff_amount'
                            WHEN r_tran_id IS NOT NULL THEN 'rep_only'
                            ELSE 'stm_only'
                        END as status,
                        error_code
                    FROM combined
                """
            else:
                # PostgreSQL supports FULL OUTER JOIN natively
                query = f"""
                    WITH rep_data AS (
                        SELECT tran_id, rep_no, name as patient_name, hn, dateadm,
                               COALESCE(reimb_nhso, 0) as rep_amount, error_code
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_where)}
                    ),
                    stm_data AS (
                        SELECT tran_id, rep_no, patient_name, hn, date_admit,
                               COALESCE(paid_after_deduction, 0) as stm_amount
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_where)}
                    )
                    SELECT
                        COALESCE(r.tran_id, s.tran_id) as tran_id,
                        COALESCE(r.rep_no, s.rep_no) as rep_no,
                        COALESCE(r.patient_name, s.patient_name) as patient_name,
                        COALESCE(r.hn, s.hn) as hn,
                        COALESCE(r.dateadm, s.date_admit) as date,
                        COALESCE(r.rep_amount, 0) as rep_amount,
                        COALESCE(s.stm_amount, 0) as stm_amount,
                        COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0) as diff,
                        CASE
                            WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL
                                 AND ABS(COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0)) < 0.01 THEN 'matched'
                            WHEN r.tran_id IS NOT NULL AND s.tran_id IS NOT NULL THEN 'diff_amount'
                            WHEN r.tran_id IS NOT NULL THEN 'rep_only'
                            ELSE 'stm_only'
                        END as status,
                        r.error_code
                    FROM rep_data r
                    FULL OUTER JOIN stm_data s ON r.tran_id = s.tran_id
                """
            columns = ['TRAN_ID', 'REP_NO', 'PATIENT_NAME', 'HN', 'DATE', 'REP_AMOUNT', 'STM_AMOUNT', 'DIFF', 'STATUS', 'ERROR_CODE']
        else:
            if DB_TYPE == 'mysql':
                # MySQL doesn't support FULL OUTER JOIN
                query = f"""
                    WITH rep_data AS (
                        SELECT rep_no, SUM(COALESCE(reimb_nhso, 0)) as rep_amount, COUNT(*) as rep_count
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_where)}
                        GROUP BY rep_no
                    ),
                    stm_data AS (
                        SELECT rep_no, SUM(COALESCE(paid_after_deduction, 0)) as stm_amount, COUNT(*) as stm_count
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_where)}
                        GROUP BY rep_no
                    ),
                    combined AS (
                        SELECT r.rep_no as r_rep_no, r.rep_amount, r.rep_count,
                               s.rep_no as s_rep_no, s.stm_amount, s.stm_count
                        FROM rep_data r LEFT JOIN stm_data s ON r.rep_no = s.rep_no
                        UNION
                        SELECT r.rep_no as r_rep_no, r.rep_amount, r.rep_count,
                               s.rep_no as s_rep_no, s.stm_amount, s.stm_count
                        FROM stm_data s LEFT JOIN rep_data r ON r.rep_no = s.rep_no
                        WHERE r.rep_no IS NULL
                    )
                    SELECT
                        COALESCE(r_rep_no, s_rep_no) as rep_no,
                        COALESCE(rep_count, 0) as rep_count,
                        COALESCE(stm_count, 0) as stm_count,
                        COALESCE(rep_amount, 0) as rep_amount,
                        COALESCE(stm_amount, 0) as stm_amount,
                        COALESCE(rep_amount, 0) - COALESCE(stm_amount, 0) as diff,
                        CASE
                            WHEN r_rep_no IS NOT NULL AND s_rep_no IS NOT NULL
                                 AND ABS(COALESCE(rep_amount, 0) - COALESCE(stm_amount, 0)) < 0.01 THEN 'matched'
                            WHEN r_rep_no IS NOT NULL AND s_rep_no IS NOT NULL THEN 'diff_amount'
                            WHEN r_rep_no IS NOT NULL THEN 'rep_only'
                            ELSE 'stm_only'
                        END as status
                    FROM combined
                """
            else:
                # PostgreSQL supports FULL OUTER JOIN natively
                query = f"""
                    WITH rep_data AS (
                        SELECT rep_no, SUM(COALESCE(reimb_nhso, 0)) as rep_amount, COUNT(*) as rep_count
                        FROM claim_rep_opip_nhso_item
                        WHERE {' AND '.join(rep_where)}
                        GROUP BY rep_no
                    ),
                    stm_data AS (
                        SELECT rep_no, SUM(COALESCE(paid_after_deduction, 0)) as stm_amount, COUNT(*) as stm_count
                        FROM stm_claim_item
                        WHERE {' AND '.join(stm_where)}
                        GROUP BY rep_no
                    )
                    SELECT
                        COALESCE(r.rep_no, s.rep_no) as rep_no,
                        COALESCE(r.rep_count, 0) as rep_count,
                        COALESCE(s.stm_count, 0) as stm_count,
                        COALESCE(r.rep_amount, 0) as rep_amount,
                        COALESCE(s.stm_amount, 0) as stm_amount,
                        COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0) as diff,
                        CASE
                            WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL
                                 AND ABS(COALESCE(r.rep_amount, 0) - COALESCE(s.stm_amount, 0)) < 0.01 THEN 'matched'
                            WHEN r.rep_no IS NOT NULL AND s.rep_no IS NOT NULL THEN 'diff_amount'
                            WHEN r.rep_no IS NOT NULL THEN 'rep_only'
                            ELSE 'stm_only'
                        END as status
                    FROM rep_data r
                    FULL OUTER JOIN stm_data s ON r.rep_no = s.rep_no
                """
            columns = ['REP_NO', 'REP_COUNT', 'STM_COUNT', 'REP_AMOUNT', 'STM_AMOUNT', 'DIFF', 'STATUS']

        if rep_no_filter:
            like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
            if group_by == 'tran_id':
                where_clauses.append(f"(tran_id {like_op} %s OR rep_no {like_op} %s)")
                params.extend([f'%{rep_no_filter}%', f'%{rep_no_filter}%'])
            else:
                where_clauses.append(f"rep_no {like_op} %s")
                params.append(f'%{rep_no_filter}%')

        if status_filter:
            where_clauses.append("status = %s")
            params.append(status_filter)

        if diff_threshold > 0:
            where_clauses.append("ABS(diff) >= %s")
            params.append(diff_threshold)

        if where_clauses:
            query = f"SELECT * FROM ({query}) sub WHERE " + " AND ".join(where_clauses)

        query += " LIMIT 10000"  # Limit export size

        cursor.execute(query, params)
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow(row)

        # Return CSV file
        from flask import make_response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename=reconciliation_{group_by}.csv'
        return response

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error in export: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/search')
@analytics_api_bp.route('/api/analysis/search')  # Legacy alias
def api_analysis_search():
    """
    Search across all data sources by TRAN_ID, HN, AN, or PID
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        query_term = request.args.get('q', '').strip()

        if not query_term:
            return jsonify({'success': False, 'error': 'Search query required'}), 400

        # Search in REP data
        like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
        rep_results = []
        try:
            cursor.execute(f"""
                SELECT tran_id, rep_no, hn, name, dateadm, reimb_nhso
                FROM claim_rep_opip_nhso_item
                WHERE tran_id {like_op} %s OR hn {like_op} %s OR an {like_op} %s OR pid {like_op} %s
                LIMIT 50
            """, (f'%{query_term}%', f'%{query_term}%', f'%{query_term}%', f'%{query_term}%'))
            for row in cursor.fetchall():
                rep_results.append({
                    'tran_id': row[0],
                    'rep_no': row[1],
                    'hn': row[2],
                    'name': row[3],
                    'dateadm': str(row[4]) if row[4] else None,
                    'reimb_nhso': float(row[5] or 0)
                })
        except Exception as e:
            current_app.logger.warning(f"Error searching REP: {e}")

        # Search in Statement data
        stm_results = []
        try:
            cursor.execute(f"""
                SELECT tran_id, rep_no, hn, patient_name, date_admit, paid_after_deduction
                FROM stm_claim_item
                WHERE tran_id {like_op} %s OR hn {like_op} %s OR an {like_op} %s OR pid {like_op} %s
                LIMIT 50
            """, (f'%{query_term}%', f'%{query_term}%', f'%{query_term}%', f'%{query_term}%'))
            for row in cursor.fetchall():
                stm_results.append({
                    'tran_id': row[0],
                    'rep_no': row[1],
                    'hn': row[2],
                    'patient_name': row[3],
                    'date_admit': str(row[4]) if row[4] else None,
                    'paid_after_deduction': float(row[5] or 0)
                })
        except Exception as e:
            current_app.logger.warning(f"Error searching Statement: {e}")

        # Search in SMT Budget data
        smt_results = []
        try:
            cursor.execute(f"""
                SELECT posting_date, ref_doc_no, fund_group_desc, total_amount, payment_status
                FROM smt_budget_transfers
                WHERE ref_doc_no {like_op} %s OR fund_group_desc {like_op} %s
                LIMIT 50
            """, (f'%{query_term}%', f'%{query_term}%'))
            for row in cursor.fetchall():
                smt_results.append({
                    'posting_date': str(row[0]) if row[0] else None,
                    'ref_doc_no': row[1],
                    'fund_group_desc': row[2],
                    'total_amount': float(row[3] or 0),
                    'payment_status': row[4]
                })
        except Exception as e:
            current_app.logger.warning(f"Error searching SMT: {e}")

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'rep': rep_results,
            'stm': stm_results,
            'smt': smt_results
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error in search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/files')
@analytics_api_bp.route('/api/analysis/files')  # Legacy alias
def api_analysis_files():
    """
    Get list of imported files by data type
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        data_type = request.args.get('type', 'rep').strip().lower()

        files = []

        if data_type == 'rep':
            cursor.execute("""
                SELECT id, filename, imported_records
                FROM eclaim_imported_files
                WHERE status = 'completed'
                ORDER BY import_completed_at DESC
                LIMIT 100
            """)
            for row in cursor.fetchall():
                files.append({
                    'id': row[0],
                    'filename': row[1],
                    'record_count': row[2] or 0
                })

        elif data_type == 'stm':
            cursor.execute("""
                SELECT id, filename, imported_records
                FROM stm_imported_files
                WHERE status = 'completed'
                ORDER BY import_completed_at DESC
                LIMIT 100
            """)
            for row in cursor.fetchall():
                files.append({
                    'id': row[0],
                    'filename': row[1],
                    'record_count': row[2] or 0
                })

        elif data_type == 'smt':
            cursor.execute("""
                SELECT run_date, COUNT(*) as record_count
                FROM smt_budget_transfers
                GROUP BY run_date
                ORDER BY run_date DESC
                LIMIT 100
            """)
            for row in cursor.fetchall():
                run_date = row[0]
                files.append({
                    'id': str(run_date) if run_date else '0',
                    'filename': f'SMT {run_date.strftime("%Y-%m-%d") if run_date else "Unknown"}',
                    'record_count': row[1] or 0
                })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'files': files
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/file-items')
@analytics_api_bp.route('/api/analysis/file-items')  # Legacy alias
def api_analysis_file_items():
    """
    Get items in a specific file
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()
        data_type = request.args.get('type', 'rep').strip().lower()
        file_id = request.args.get('file_id', 0, type=int)
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        if not file_id:
            return jsonify({'success': False, 'error': 'file_id required'}), 400

        items = []
        columns = []

        if data_type == 'rep':
            columns = ['tran_id', 'rep_no', 'hn', 'name', 'dateadm', 'datedsc', 'reimb_nhso']
            cursor.execute(f"""
                SELECT {', '.join(columns)}
                FROM claim_rep_opip_nhso_item
                WHERE file_id = %s
                ORDER BY row_number
                LIMIT %s OFFSET %s
            """, (file_id, limit, offset))

            for row in cursor.fetchall():
                item = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    if hasattr(value, 'isoformat'):
                        value = value.strftime('%Y-%m-%d')
                    elif isinstance(value, (int, float)) and col in ['reimb_nhso']:
                        value = float(value) if value else 0
                    item[col] = value
                items.append(item)

        elif data_type == 'stm':
            columns = ['tran_id', 'rep_no', 'hn', 'patient_name', 'date_admit', 'date_discharge', 'paid_after_deduction']
            cursor.execute(f"""
                SELECT {', '.join(columns)}
                FROM stm_claim_item
                WHERE file_id = %s
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (file_id, limit, offset))

            for row in cursor.fetchall():
                item = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    if hasattr(value, 'isoformat'):
                        value = value.strftime('%Y-%m-%d')
                    elif isinstance(value, (int, float)) and col in ['paid_after_deduction']:
                        value = float(value) if value else 0
                    item[col] = value
                items.append(item)

        elif data_type == 'smt':
            columns = ['posting_date', 'ref_doc_no', 'fund_group_desc', 'total_amount', 'payment_status']
            # For SMT, file_id is actually the run_date string (YYYY-MM-DD)
            run_date = request.args.get('file_id', '').strip()
            cursor.execute(f"""
                SELECT {', '.join(columns)}
                FROM smt_budget_transfers
                WHERE run_date = %s
                ORDER BY id
                LIMIT %s OFFSET %s
            """, (run_date, limit, offset))

            for row in cursor.fetchall():
                item = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    if hasattr(value, 'isoformat'):
                        value = value.strftime('%Y-%m-%d')
                    elif isinstance(value, (int, float)) and col in ['total_amount']:
                        value = float(value) if value else 0
                    item[col] = value
                items.append(item)

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'columns': columns,
            'items': items
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting file items: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Enhanced Data Analysis APIs
# =============================================================================


@analytics_api_bp.route('/api/analytics/claims-detail')
@analytics_api_bp.route('/api/analysis/claims')  # Legacy alias
def api_analysis_claims():
    """
    Get detailed claims data with filters
    Supports: scheme, ptype, date_from, date_to, error_code, reconcile_status
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        scheme = request.args.get('scheme', '').strip() or None
        ptype = request.args.get('ptype', '').strip() or None
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None
        has_error = request.args.get('has_error', '').strip().lower() == 'true'
        reconcile_status = request.args.get('reconcile_status', '').strip() or None
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page

        # Build WHERE clause
        conditions = ["1=1"]
        params = []

        if scheme:
            conditions.append("main_inscl = %s")
            params.append(scheme.upper())

        if ptype:
            conditions.append("ptype = %s")
            params.append(ptype.upper())

        if date_from:
            conditions.append("dateadm >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("dateadm <= %s")
            params.append(date_to)

        if has_error:
            conditions.append("error_code IS NOT NULL AND error_code != '-' AND error_code != ''")

        if reconcile_status:
            conditions.append("reconcile_status = %s")
            params.append(reconcile_status)

        where_clause = " AND ".join(conditions)

        # Count total
        count_query = f"SELECT COUNT(*) FROM claim_rep_opip_nhso_item WHERE {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get data
        data_query = f"""
            SELECT tran_id, hn, name, ptype, main_inscl as scheme, dateadm,
                   claim_net, reimb_nhso, error_code, reconcile_status
            FROM claim_rep_opip_nhso_item
            WHERE {where_clause}
            ORDER BY dateadm DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(data_query, params + [per_page, offset])

        claims = []
        for row in cursor.fetchall():
            claims.append({
                'tran_id': row[0],
                'hn': row[1],
                'name': row[2],
                'ptype': row[3],
                'scheme': row[4],
                'dateadm': row[5].strftime('%Y-%m-%d') if row[5] else None,
                'claim_net': float(row[6]) if row[6] else 0,
                'reimb_nhso': float(row[7]) if row[7] else 0,
                'error_code': row[8],
                'reconcile_status': row[9]
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'claims': claims,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            },
            'filters': {
                'scheme': scheme,
                'ptype': ptype,
                'date_from': date_from,
                'date_to': date_to,
                'has_error': has_error,
                'reconcile_status': reconcile_status
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting claims: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/financial-breakdown')
@analytics_api_bp.route('/api/analysis/financial-breakdown')  # Legacy alias
def api_analysis_financial_breakdown():
    """
    Get financial breakdown by service category
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        scheme = request.args.get('scheme', '').strip() or None
        ptype = request.args.get('ptype', '').strip() or None
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None

        # Build WHERE clause
        conditions = ["1=1"]
        params = []

        if scheme:
            conditions.append("main_inscl = %s")
            params.append(scheme.upper())

        if ptype:
            conditions.append("ptype = %s")
            params.append(ptype.upper())

        if date_from:
            conditions.append("dateadm >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("dateadm <= %s")
            params.append(date_to)

        where_clause = " AND ".join(conditions)

        # Get breakdown by scheme and ptype
        query = f"""
            SELECT
                COALESCE(main_inscl, 'UNKNOWN') as scheme,
                COALESCE(ptype, 'UNKNOWN') as ptype,
                COUNT(*) as total_cases,
                COALESCE(SUM(COALESCE(iphc, 0) + COALESCE(ophc, 0)), 0) as high_cost_care,
                COALESCE(SUM(COALESCE(ae_opae, 0) + COALESCE(ae_ipnb, 0) + COALESCE(ae_ipuc, 0)), 0) as emergency,
                COALESCE(SUM(COALESCE(inst, 0) + COALESCE(opinst, 0)), 0) as prosthetics,
                COALESCE(SUM(COALESCE(drug, 0)), 0) as drug_costs,
                COALESCE(SUM(claim_net), 0) as total_claimed,
                COALESCE(SUM(reimb_nhso), 0) as total_reimbursed
            FROM claim_rep_opip_nhso_item
            WHERE {where_clause}
            GROUP BY main_inscl, ptype
            ORDER BY total_cases DESC
        """
        cursor.execute(query, params)

        breakdown = []
        totals = {
            'total_cases': 0,
            'high_cost_care': 0,
            'emergency': 0,
            'prosthetics': 0,
            'drug_costs': 0,
            'total_claimed': 0,
            'total_reimbursed': 0
        }

        for row in cursor.fetchall():
            item = {
                'scheme': row[0],
                'ptype': row[1],
                'total_cases': int(row[2]),
                'high_cost_care': float(row[3]),
                'emergency': float(row[4]),
                'prosthetics': float(row[5]),
                'drug_costs': float(row[6]),
                'total_claimed': float(row[7]),
                'total_reimbursed': float(row[8])
            }
            breakdown.append(item)

            # Accumulate totals
            for key in totals:
                totals[key] += item[key]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'breakdown': breakdown,
            'totals': totals,
            'filters': {
                'scheme': scheme,
                'ptype': ptype,
                'date_from': date_from,
                'date_to': date_to
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting financial breakdown: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/errors-detail')
@analytics_api_bp.route('/api/analysis/errors')  # Legacy alias
def api_analysis_errors():
    """
    Get error and denial analytics
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        scheme = request.args.get('scheme', '').strip() or None
        ptype = request.args.get('ptype', '').strip() or None
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None

        # Build WHERE clause
        conditions = ["1=1"]
        params = []

        if scheme:
            conditions.append("main_inscl = %s")
            params.append(scheme.upper())

        if ptype:
            conditions.append("ptype = %s")
            params.append(ptype.upper())

        if date_from:
            conditions.append("dateadm >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("dateadm <= %s")
            params.append(date_to)

        where_clause = " AND ".join(conditions)

        # Top error codes
        error_query = f"""
            SELECT error_code, COUNT(*) as count, COALESCE(SUM(claim_net), 0) as affected_amount
            FROM claim_rep_opip_nhso_item
            WHERE {where_clause}
              AND error_code IS NOT NULL AND error_code != '-' AND error_code != ''
            GROUP BY error_code
            ORDER BY count DESC
            LIMIT 15
        """
        cursor.execute(error_query, params)

        top_errors = []
        for row in cursor.fetchall():
            top_errors.append({
                'error_code': row[0],
                'count': int(row[1]),
                'affected_amount': float(row[2])
            })

        # Overall stats
        stats_query = f"""
            SELECT
                COUNT(*) as total_records,
                SUM(CASE WHEN error_code IS NOT NULL AND error_code != '-' AND error_code != '' THEN 1 ELSE 0 END) as error_count,
                COALESCE(SUM(CASE WHEN error_code IS NOT NULL AND error_code != '-' AND error_code != '' THEN claim_net ELSE 0 END), 0) as error_amount,
                COALESCE(SUM(claim_net), 0) as total_claimed
            FROM claim_rep_opip_nhso_item
            WHERE {where_clause}
        """
        cursor.execute(stats_query, params)
        stats_row = cursor.fetchone()

        stats = {
            'total_records': int(stats_row[0]) if stats_row[0] else 0,
            'error_count': int(stats_row[1]) if stats_row[1] else 0,
            'error_amount': float(stats_row[2]) if stats_row[2] else 0,
            'total_claimed': float(stats_row[3]) if stats_row[3] else 0,
            'error_rate': round((int(stats_row[1]) / int(stats_row[0]) * 100), 2) if stats_row[0] and stats_row[0] > 0 else 0
        }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'top_errors': top_errors,
            'stats': stats,
            'filters': {
                'scheme': scheme,
                'ptype': ptype,
                'date_from': date_from,
                'date_to': date_to
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting error analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/scheme-summary')
@analytics_api_bp.route('/api/analysis/scheme-summary')  # Legacy alias
def api_analysis_scheme_summary():
    """
    Get summary by insurance scheme
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None

        # Build WHERE clause
        conditions = ["1=1"]
        params = []

        if date_from:
            conditions.append("dateadm >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("dateadm <= %s")
            params.append(date_to)

        where_clause = " AND ".join(conditions)

        # Get summary by scheme
        query = f"""
            SELECT
                COALESCE(main_inscl, 'UNKNOWN') as scheme,
                COUNT(*) as total_cases,
                SUM(CASE WHEN ptype = 'OP' THEN 1 ELSE 0 END) as op_cases,
                SUM(CASE WHEN ptype = 'IP' THEN 1 ELSE 0 END) as ip_cases,
                COALESCE(SUM(claim_net), 0) as total_claimed,
                COALESCE(SUM(reimb_nhso), 0) as total_reimbursed,
                SUM(CASE WHEN error_code IS NOT NULL AND error_code != '-' AND error_code != '' THEN 1 ELSE 0 END) as error_count
            FROM claim_rep_opip_nhso_item
            WHERE {where_clause}
            GROUP BY main_inscl
            ORDER BY total_cases DESC
        """
        cursor.execute(query, params)

        schemes = []
        for row in cursor.fetchall():
            schemes.append({
                'scheme': row[0],
                'scheme_name': {
                    'UCS': 'บัตรทอง (UCS)',
                    'OFC': 'ข้าราชการ (OFC)',
                    'SSS': 'ประกันสังคม (SSS)',
                    'LGO': 'อปท. (LGO)',
                    'UNKNOWN': 'ไม่ระบุ'
                }.get(row[0], row[0]),
                'total_cases': int(row[1]),
                'op_cases': int(row[2]),
                'ip_cases': int(row[3]),
                'total_claimed': float(row[4]),
                'total_reimbursed': float(row[5]),
                'error_count': int(row[6])
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'schemes': schemes,
            'filters': {
                'date_from': date_from,
                'date_to': date_to
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting scheme summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/facilities')
@analytics_api_bp.route('/api/analysis/facilities')  # Legacy alias
def api_analysis_facilities():
    """
    Get facility analysis - summary by treating facility (hcode)
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None
        scheme = request.args.get('scheme', '').strip() or None
        ptype = request.args.get('ptype', '').strip() or None
        limit = int(request.args.get('limit', 50))

        # Build WHERE clause
        conditions = ["1=1"]
        params = []

        if date_from:
            conditions.append("c.dateadm >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("c.dateadm <= %s")
            params.append(date_to)

        if scheme:
            conditions.append("c.main_inscl = %s")
            params.append(scheme)

        if ptype:
            conditions.append("c.ptype = %s")
            params.append(ptype)

        where_clause = " AND ".join(conditions)

        # Get facility summary with join to health_offices
        query = f"""
            SELECT
                c.hcode,
                COALESCE(h.name, 'ไม่ทราบชื่อ') as facility_name,
                COALESCE(h.province, '-') as province,
                COUNT(*) as total_cases,
                SUM(CASE WHEN c.ptype = 'OP' THEN 1 ELSE 0 END) as op_cases,
                SUM(CASE WHEN c.ptype = 'IP' THEN 1 ELSE 0 END) as ip_cases,
                COALESCE(SUM(c.claim_net), 0) as total_claimed,
                COALESCE(SUM(c.reimb_nhso), 0) as total_reimbursed,
                SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-' AND c.error_code != '' THEN 1 ELSE 0 END) as error_count
            FROM claim_rep_opip_nhso_item c
            LEFT JOIN health_offices h ON c.hcode = h.hcode5
            WHERE {where_clause}
            GROUP BY c.hcode, h.name, h.province
            ORDER BY total_cases DESC
            LIMIT %s
        """
        params.append(limit)
        cursor.execute(query, params)

        facilities = []
        for row in cursor.fetchall():
            total_cases = int(row[3])
            error_count = int(row[8])
            facilities.append({
                'hcode': row[0] or '-',
                'facility_name': row[1],
                'province': row[2],
                'total_cases': total_cases,
                'op_cases': int(row[4]),
                'ip_cases': int(row[5]),
                'total_claimed': float(row[6]),
                'total_reimbursed': float(row[7]),
                'error_count': error_count,
                'error_rate': round((error_count / total_cases * 100), 2) if total_cases > 0 else 0
            })

        # Get totals
        total_query = f"""
            SELECT
                COUNT(DISTINCT c.hcode) as facility_count,
                COUNT(*) as total_cases,
                COALESCE(SUM(c.claim_net), 0) as total_claimed,
                COALESCE(SUM(c.reimb_nhso), 0) as total_reimbursed
            FROM claim_rep_opip_nhso_item c
            WHERE {where_clause}
        """
        # Remove limit param for totals query
        cursor.execute(total_query, params[:-1])
        totals_row = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'facilities': facilities,
            'totals': {
                'facility_count': int(totals_row[0]) if totals_row else 0,
                'total_cases': int(totals_row[1]) if totals_row else 0,
                'total_claimed': float(totals_row[2]) if totals_row else 0,
                'total_reimbursed': float(totals_row[3]) if totals_row else 0
            },
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'scheme': scheme,
                'ptype': ptype
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting facility analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/his-reconciliation')
@analytics_api_bp.route('/api/analysis/his-reconciliation')  # Legacy alias
def api_analysis_his_reconciliation():
    """
    Get HIS reconciliation status summary
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({'success': False, 'error': 'Database connection failed'}), 500

    try:
        cursor = conn.cursor()

        # Get filter parameters
        date_from = request.args.get('date_from', '').strip() or None
        date_to = request.args.get('date_to', '').strip() or None
        scheme = request.args.get('scheme', '').strip() or None
        status = request.args.get('status', '').strip() or None
        diff_threshold = float(request.args.get('diff_threshold', 0))
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page

        # Build WHERE clause for summary
        conditions = ["1=1"]
        params = []

        if date_from:
            conditions.append("dateadm >= %s")
            params.append(date_from)

        if date_to:
            conditions.append("dateadm <= %s")
            params.append(date_to)

        if scheme:
            conditions.append("main_inscl = %s")
            params.append(scheme)

        where_clause = " AND ".join(conditions)

        # Get summary by reconcile_status
        summary_query = f"""
            SELECT
                COALESCE(reconcile_status, 'pending') as status,
                COUNT(*) as count,
                COALESCE(SUM(claim_net), 0) as total_amount,
                SUM(CASE WHEN his_amount_diff IS NOT NULL AND his_amount_diff != 0 THEN 1 ELSE 0 END) as diff_count,
                COALESCE(SUM(ABS(COALESCE(his_amount_diff, 0))), 0) as total_diff
            FROM claim_rep_opip_nhso_item
            WHERE {where_clause}
            GROUP BY reconcile_status
        """
        cursor.execute(summary_query, params)

        status_summary = []
        total_records = 0
        for row in cursor.fetchall():
            count = int(row[1])
            total_records += count
            status_summary.append({
                'status': row[0],
                'status_name': {
                    'pending': 'รอตรวจสอบ',
                    'matched': 'ตรงกัน',
                    'mismatched': 'ไม่ตรง',
                    'manual': 'ตรวจสอบด้วยตนเอง'
                }.get(row[0], row[0]),
                'count': count,
                'total_amount': float(row[2]),
                'diff_count': int(row[3]),
                'total_diff': float(row[4])
            })

        # Build WHERE clause for records list (with status filter)
        list_conditions = conditions.copy()
        list_params = params.copy()

        if status:
            if status == 'pending':
                list_conditions.append("(reconcile_status IS NULL OR reconcile_status = 'pending')")
            else:
                list_conditions.append("reconcile_status = %s")
                list_params.append(status)

        if diff_threshold > 0:
            list_conditions.append("ABS(COALESCE(his_amount_diff, 0)) >= %s")
            list_params.append(diff_threshold)

        list_where_clause = " AND ".join(list_conditions)

        # Get records with differences
        records_query = f"""
            SELECT
                tran_id,
                hn,
                name,
                ptype,
                main_inscl as scheme,
                dateadm,
                claim_net,
                reimb_nhso,
                his_vn,
                his_matched,
                his_amount_diff,
                reconcile_status
            FROM claim_rep_opip_nhso_item
            WHERE {list_where_clause}
            ORDER BY ABS(COALESCE(his_amount_diff, 0)) DESC, dateadm DESC
            LIMIT %s OFFSET %s
        """
        list_params.extend([per_page, offset])
        cursor.execute(records_query, list_params)

        records = []
        for row in cursor.fetchall():
            records.append({
                'tran_id': row[0],
                'hn': row[1],
                'name': row[2],
                'ptype': row[3],
                'scheme': row[4],
                'dateadm': str(row[5]) if row[5] else None,
                'claim_net': float(row[6]) if row[6] else 0,
                'reimb_nhso': float(row[7]) if row[7] else 0,
                'his_vn': row[8],
                'his_matched': row[9],
                'his_amount_diff': float(row[10]) if row[10] else 0,
                'reconcile_status': row[11] or 'pending'
            })

        # Get total count for pagination
        count_query = f"""
            SELECT COUNT(*) FROM claim_rep_opip_nhso_item
            WHERE {list_where_clause}
        """
        cursor.execute(count_query, list_params[:-2])  # Exclude limit and offset
        filtered_total = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'summary': status_summary,
            'records': records,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': filtered_total,
                'total_pages': (filtered_total + per_page - 1) // per_page
            },
            'filters': {
                'date_from': date_from,
                'date_to': date_to,
                'scheme': scheme,
                'status': status,
                'diff_threshold': diff_threshold
            }
        })

    except Exception as e:
        if conn:
            conn.close()
        current_app.logger.error(f"Error getting HIS reconciliation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/fiscal-years')
def api_analytics_fiscal_years():
    """Get available fiscal years for filter dropdown"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        fiscal_years = get_available_fiscal_years(cursor)
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': fiscal_years})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/filter-options')
def api_analytics_filter_options():
    """
    Get dynamic filter options from database for Claims Viewer.
    Returns distinct values for scheme (กองทุน), service_type, and main_fund.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Service type mapping for display
        service_type_labels = {
            '': 'ไม่ระบุ',
            'E': 'ฉุกเฉิน (E)',
            'R': 'ส่งต่อ (R)',
            'P': 'ป้องกัน (P)',
            'A': 'อุบัติเหตุ (A)',
            'C': 'เรื้อรัง (C)',
            'N': 'ทั่วไป (N)'
        }

        # Get distinct schemes (กองทุนหลัก)
        cursor.execute("""
            SELECT scheme, COUNT(*) as cnt
            FROM claim_rep_opip_nhso_item
            WHERE scheme IS NOT NULL AND scheme != ''
            GROUP BY scheme
            ORDER BY cnt DESC
        """)
        schemes = [{'value': row[0], 'label': row[0], 'count': row[1]} for row in cursor.fetchall()]

        # Get distinct service types
        cursor.execute("""
            SELECT COALESCE(service_type, '') as stype, COUNT(*) as cnt
            FROM claim_rep_opip_nhso_item
            GROUP BY COALESCE(service_type, '')
            ORDER BY cnt DESC
        """)
        service_types = []
        for row in cursor.fetchall():
            stype = row[0]
            service_types.append({
                'value': stype,
                'label': service_type_labels.get(stype, stype or 'ไม่ระบุ'),
                'count': row[1]
            })

        # Get distinct main_fund (กองทุนย่อย) - top 20
        cursor.execute("""
            SELECT main_fund, COUNT(*) as cnt
            FROM claim_rep_opip_nhso_item
            WHERE main_fund IS NOT NULL AND main_fund != ''
            GROUP BY main_fund
            ORDER BY cnt DESC
            LIMIT 20
        """)
        main_funds = [{'value': row[0], 'label': row[0], 'count': row[1]} for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'schemes': schemes,
                'service_types': service_types,
                'main_funds': main_funds
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in filter options: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/dashboard/reconciliation-status')
def api_dashboard_reconciliation_status():
    """Phase 3: Get reconciliation status for dashboard"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        result = {
            'rep_status': {'total': 0, 'imported': 0, 'failed': 0, 'pending': 0},
            'stm_status': {'total': 0, 'imported': 0, 'failed': 0, 'pending': 0},
            'smt_status': {'total_records': 0, 'total_amount': 0, 'last_sync': None},
            'reconciliation': {'matched': 0, 'unmatched': 0, 'total': 0}
        }

        # REP Import Status
        try:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM eclaim_imported_files
                GROUP BY status
            """)
            for row in cursor.fetchall():
                status, count = row[0], row[1]
                result['rep_status']['total'] += count
                if status == 'completed':
                    result['rep_status']['imported'] += count
                elif status == 'failed':
                    result['rep_status']['failed'] += count
                else:
                    result['rep_status']['pending'] += count
        except Exception:
            pass

        # STM Import Status
        try:
            cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM stm_imported_files
                GROUP BY status
            """)
            for row in cursor.fetchall():
                status, count = row[0], row[1]
                result['stm_status']['total'] += count
                if status == 'completed':
                    result['stm_status']['imported'] += count
                elif status == 'failed':
                    result['stm_status']['failed'] += count
                else:
                    result['stm_status']['pending'] += count
        except Exception:
            pass

        # SMT Budget Status
        try:
            cursor.execute("""
                SELECT COUNT(*), COALESCE(SUM(total_amount), 0), MAX(created_at)
                FROM smt_budget_transfers
            """)
            row = cursor.fetchone()
            if row:
                result['smt_status']['total_records'] = row[0] or 0
                result['smt_status']['total_amount'] = float(row[1] or 0)
                result['smt_status']['last_sync'] = str(row[2]) if row[2] else None
        except Exception:
            pass

        # STM-REP Reconciliation Status (using stm_claim_item)
        try:
            cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN rep_matched = TRUE OR rep_matched = 1 THEN 1 ELSE 0 END) as matched
                FROM stm_claim_item
            """)
            row = cursor.fetchone()
            if row:
                result['reconciliation']['total'] = row[0] or 0
                result['reconciliation']['matched'] = row[1] or 0
                result['reconciliation']['unmatched'] = (row[0] or 0) - (row[1] or 0)
        except Exception:
            pass

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/overview')
def api_analytics_overview():
    """Get overview statistics for analytics dashboard"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter (returns only static SQL with %s placeholders)
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "dateadm IS NOT NULL"
        if date_filter:
            base_where = base_where + " AND " + date_filter

        # Total claims and amounts (parameterized query)
        query = """
            SELECT
                COUNT(*) as total_claims,
                COALESCE(SUM(reimb_nhso), 0) as total_reimb,
                COALESCE(SUM(paid), 0) as total_paid,
                COALESCE(SUM(claim_drg), 0) as total_claim_drg,
                COUNT(DISTINCT hn) as unique_patients,
                """ + sql_count_distinct_months('dateadm') + """ as active_months
            FROM claim_rep_opip_nhso_item
            WHERE """ + base_where
        cursor.execute(query, filter_params)
        row = cursor.fetchone()
        total_claims = row[0] or 0
        total_reimb = float(row[1] or 0)
        total_paid = float(row[2] or 0)
        total_claim_drg = float(row[3] or 0)
        unique_patients = row[4] or 0

        overview = {
            'total_claims': total_claims,
            'total_reimb': total_reimb,  # ยอดชดเชย (ตัวใหญ่)
            'total_paid': total_paid,
            'total_claim_drg': total_claim_drg,  # ยอดเรียกเก็บ (ตัวเล็ก)
            'unique_patients': unique_patients,
            'active_months': row[5] or 0,
            # อัตราชดเชย = ยอดชดเชย / ยอดเรียกเก็บ * 100
            'reimb_rate': round(total_reimb / total_claim_drg * 100, 2) if total_claim_drg > 0 else 0,
            # เฉลี่ย/case
            'avg_claim_per_case': round(total_claim_drg / total_claims, 2) if total_claims > 0 else 0,
            'avg_reimb_per_case': round(total_reimb / total_claims, 2) if total_claims > 0 else 0,
            'filter': filter_info
        }

        # OPD/IPD breakdown (AN = IPD, no AN = OPD)
        # Also separate by error_code (ผ่าน = no error, ไม่ผ่าน = has error)
        opd_ipd_query = """
            SELECT
                CASE WHEN an IS NOT NULL AND an != '' THEN 'IPD' ELSE 'OPD' END as visit_type,
                CASE WHEN error_code IS NULL OR error_code = '' THEN 'pass' ELSE 'fail' END as status,
                COUNT(*) as claims,
                COALESCE(SUM(claim_drg), 0) as total_claim,
                COALESCE(SUM(reimb_nhso), 0) as total_reimb
            FROM claim_rep_opip_nhso_item
            WHERE """ + base_where + """
            GROUP BY
                CASE WHEN an IS NOT NULL AND an != '' THEN 'IPD' ELSE 'OPD' END,
                CASE WHEN error_code IS NULL OR error_code = '' THEN 'pass' ELSE 'fail' END
        """
        cursor.execute(opd_ipd_query, filter_params)
        opd_ipd_rows = cursor.fetchall()

        # Initialize OPD/IPD data
        opd_data = {'pass': {'claims': 0, 'claim': 0, 'reimb': 0}, 'fail': {'claims': 0, 'claim': 0, 'reimb': 0}}
        ipd_data = {'pass': {'claims': 0, 'claim': 0, 'reimb': 0}, 'fail': {'claims': 0, 'claim': 0, 'reimb': 0}}

        for row in opd_ipd_rows:
            visit_type, status, claims, claim, reimb = row
            data = opd_data if visit_type == 'OPD' else ipd_data
            data[status] = {'claims': claims, 'claim': float(claim), 'reimb': float(reimb)}

        # Calculate OPD stats
        opd_pass_claims = opd_data['pass']['claims']
        opd_fail_claims = opd_data['fail']['claims']
        opd_total_claims = opd_pass_claims + opd_fail_claims
        opd_pass_claim = opd_data['pass']['claim']  # ยอดเรียกเก็บที่ผ่าน
        opd_fail_claim = opd_data['fail']['claim']  # ยอดเรียกเก็บที่ไม่ผ่าน
        opd_total_claim = opd_pass_claim + opd_fail_claim  # ยอดเรียกเก็บรวมทั้งหมด
        opd_reimb = opd_data['pass']['reimb']
        overview['opd'] = {
            'claims': opd_pass_claims,  # จำนวนที่ผ่าน
            'total_claims': opd_total_claims,  # จำนวนทั้งหมดที่ส่ง
            'claim': opd_pass_claim,  # ยอดเรียกเก็บที่ผ่าน
            'total_claim': opd_total_claim,  # ยอดเรียกเก็บรวมทั้งหมด (ผ่าน+ไม่ผ่าน)
            'reimb': opd_reimb,
            'reimb_rate': round(opd_reimb / opd_pass_claim * 100, 2) if opd_pass_claim > 0 else 0,
            'avg_claim': round(opd_pass_claim / opd_pass_claims, 2) if opd_pass_claims > 0 else 0,
            'avg_reimb': round(opd_reimb / opd_pass_claims, 2) if opd_pass_claims > 0 else 0,
            'fail_claims': opd_fail_claims,
            'fail_claim': opd_fail_claim,
            # อัตราความสำเร็จ = ผ่าน / ส่งทั้งหมด * 100
            'success_rate': round(opd_pass_claims / opd_total_claims * 100, 2) if opd_total_claims > 0 else 0
        }

        # Calculate IPD stats
        ipd_pass_claims = ipd_data['pass']['claims']
        ipd_fail_claims = ipd_data['fail']['claims']
        ipd_total_claims = ipd_pass_claims + ipd_fail_claims
        ipd_pass_claim = ipd_data['pass']['claim']  # ยอดเรียกเก็บที่ผ่าน
        ipd_fail_claim = ipd_data['fail']['claim']  # ยอดเรียกเก็บที่ไม่ผ่าน
        ipd_total_claim = ipd_pass_claim + ipd_fail_claim  # ยอดเรียกเก็บรวมทั้งหมด
        ipd_reimb = ipd_data['pass']['reimb']
        overview['ipd'] = {
            'claims': ipd_pass_claims,  # จำนวนที่ผ่าน
            'total_claims': ipd_total_claims,  # จำนวนทั้งหมดที่ส่ง
            'claim': ipd_pass_claim,  # ยอดเรียกเก็บที่ผ่าน
            'total_claim': ipd_total_claim,  # ยอดเรียกเก็บรวมทั้งหมด (ผ่าน+ไม่ผ่าน)
            'reimb': ipd_reimb,
            'reimb_rate': round(ipd_reimb / ipd_pass_claim * 100, 2) if ipd_pass_claim > 0 else 0,
            'avg_claim': round(ipd_pass_claim / ipd_pass_claims, 2) if ipd_pass_claims > 0 else 0,
            'avg_reimb': round(ipd_reimb / ipd_pass_claims, 2) if ipd_pass_claims > 0 else 0,
            'fail_claims': ipd_fail_claims,
            'fail_claim': ipd_fail_claim,
            # อัตราความสำเร็จ = ผ่าน / ส่งทั้งหมด * 100
            'success_rate': round(ipd_pass_claims / ipd_total_claims * 100, 2) if ipd_total_claims > 0 else 0
        }

        # Phase 1 KPIs: Total denied amount and loss calculation (for dashboard)
        # จำนวนรายการที่ถูกปฏิเสธ (OPD + IPD)
        total_denied_claims = opd_fail_claims + ipd_fail_claims
        # ยอดเงินที่ถูกปฏิเสธ (ยอดเรียกเก็บที่ไม่ผ่าน)
        total_denied_amount = opd_fail_claim + ipd_fail_claim
        # ส่วนต่าง (Loss) = ยอดเรียกเก็บรวม - ยอดชดเชยรวม
        total_loss = total_claim_drg - total_reimb
        # อัตราการปฏิเสธ % = (จำนวนไม่ผ่าน / จำนวนทั้งหมด) x 100
        denial_rate = round(total_denied_claims / total_claims * 100, 2) if total_claims > 0 else 0

        overview['total_denied_claims'] = total_denied_claims
        overview['total_denied_amount'] = total_denied_amount
        overview['total_loss'] = total_loss
        overview['denial_rate'] = denial_rate

        # Per-Bed KPIs: Get hospital info from health_offices table
        hospital_code = settings_manager.get_hospital_code()
        active_months = overview['active_months'] or 1  # Avoid division by zero

        hospital_info = {
            'hospital_code': hospital_code,
            'hospital_name': None,
            'hospital_level': None,
            'actual_beds': 0,
            'province': None,
            'health_region': None
        }

        if hospital_code:
            try:
                # Query health_offices table
                hospital_query = """
                    SELECT name, hospital_level, actual_beds, province, health_region
                    FROM health_offices
                    WHERE hcode5 = %s OR hcode9 LIKE %s
                    LIMIT 1
                """
                cursor.execute(hospital_query, (hospital_code, f'%{hospital_code}'))
                hospital_row = cursor.fetchone()

                if hospital_row:
                    hospital_info['hospital_name'] = hospital_row[0]
                    hospital_info['hospital_level'] = hospital_row[1]
                    hospital_info['actual_beds'] = hospital_row[2] or 0
                    hospital_info['province'] = hospital_row[3]
                    hospital_info['health_region'] = hospital_row[4]
            except Exception as e:
                current_app.logger.warning(f"Could not fetch hospital info: {e}")

        overview['hospital'] = hospital_info

        # Calculate per-bed metrics
        beds = hospital_info['actual_beds'] or 0
        per_bed = {
            'beds': beds,
            'reimb_per_bed_month': 0,
            'loss_per_bed_month': 0,
            'claims_per_bed': 0,
            'avg_per_claim': round(total_reimb / total_claims, 2) if total_claims > 0 else 0
        }

        if beds > 0:
            per_bed['reimb_per_bed_month'] = round(total_reimb / beds / active_months, 2)
            per_bed['loss_per_bed_month'] = round(total_loss / beds / active_months, 2)
            per_bed['claims_per_bed'] = round(total_claims / beds, 2)

        overview['per_bed'] = per_bed

        # Drug summary with date filter (parameterized query)
        # Show both reimb_amount (ยอดชดเชย) and claim_amount (ยอดเรียกเก็บ)
        # Include count of distinct cases and calculate rates
        drug_where = date_filter if date_filter else "1=1"
        drug_query = """
            SELECT
                COUNT(*) as total_drugs,
                COALESCE(SUM(reimb_amount), 0) as total_drug_reimb,
                COALESCE(SUM(claim_amount), 0) as total_drug_claim,
                COUNT(DISTINCT tran_id) as total_drug_cases
            FROM eclaim_drug
            WHERE """ + drug_where
        cursor.execute(drug_query, filter_params)
        drug_row = cursor.fetchone()
        total_drug_items = drug_row[0] or 0
        total_drug_reimb = float(drug_row[1] or 0)
        total_drug_claim = float(drug_row[2] or 0)
        total_drug_cases = drug_row[3] or 0

        overview['total_drug_items'] = total_drug_items
        overview['total_drug_cost'] = total_drug_reimb  # ยอดชดเชย (ตัวใหญ่)
        overview['total_drug_claim'] = total_drug_claim  # ยอดเรียกเก็บ (ตัวเล็ก)
        overview['total_drug_cases'] = total_drug_cases
        # อัตราได้รับชดเชย % = (ยอดชดเชย / ยอดเรียกเก็บ) x 100
        overview['drug_reimb_rate'] = round((total_drug_reimb / total_drug_claim * 100), 2) if total_drug_claim > 0 else 0
        # ยอดเฉลี่ยต่อ case
        overview['drug_avg_claim_per_case'] = round(total_drug_claim / total_drug_cases, 2) if total_drug_cases > 0 else 0
        overview['drug_avg_reimb_per_case'] = round(total_drug_reimb / total_drug_cases, 2) if total_drug_cases > 0 else 0

        # Instrument summary with date filter (parameterized query)
        # Show both reimb_amount (ยอดชดเชย) and claim_amount (ยอดเรียกเก็บ)
        inst_query = """
            SELECT
                COUNT(*) as total_instruments,
                COALESCE(SUM(reimb_amount), 0) as total_instrument_reimb,
                COALESCE(SUM(claim_amount), 0) as total_instrument_claim
            FROM eclaim_instrument
            WHERE """ + drug_where
        cursor.execute(inst_query, filter_params)
        inst_row = cursor.fetchone()
        overview['total_instrument_items'] = inst_row[0] or 0
        overview['total_instrument_cost'] = float(inst_row[1] or 0)  # ยอดชดเชย (ตัวใหญ่)
        overview['total_instrument_claim'] = float(inst_row[2] or 0)  # ยอดเรียกเก็บ (ตัวเล็ก)

        # Denial summary with date filter (parameterized query)
        deny_query = "SELECT COUNT(*) FROM eclaim_deny WHERE " + drug_where
        cursor.execute(deny_query, filter_params)
        overview['total_denials'] = cursor.fetchone()[0] or 0

        return jsonify({'success': True, 'data': overview})

    except Exception as e:
        current_app.logger.error(f"Error in analytics overview: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@analytics_api_bp.route('/api/analytics/monthly-trend')
def api_analytics_monthly_trend():
    """Get monthly trend data"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "dateadm IS NOT NULL"
        if date_filter:
            base_where += f" AND {date_filter}"

        # Monthly claims and amounts
        year_month_col = sql_format_year_month('dateadm')
        query = f"""
            SELECT
                {year_month_col} as month,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid,
                COALESCE(SUM(claim_drg), 0) as claim_drg,
                COUNT(DISTINCT hn) as patients
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY {year_month_col}
            ORDER BY month DESC
            LIMIT 12
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        monthly_data = [
            {
                'month': row[0],
                'claims': row[1],
                'reimb': float(row[2] or 0),
                'paid': float(row[3] or 0),
                'claim_drg': float(row[4] or 0),
                'patients': row[5]
            }
            for row in reversed(rows)
        ]

        return jsonify({'success': True, 'data': monthly_data, 'filter': filter_info})

    except Exception as e:
        current_app.logger.error(f"Error in monthly trend: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@analytics_api_bp.route('/api/analytics/service-type')
def api_analytics_service_type():
    """Get claims by service type"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "1=1"
        if date_filter:
            base_where = date_filter

        # Service type mapping
        service_names = {
            '': 'OP/IP ทั่วไป',
            'R': 'Refer (ส่งต่อ)',
            'E': 'Emergency (ฉุกเฉิน)',
            'C': 'Chronic (เรื้อรัง)',
            'P': 'PP (ส่งเสริมป้องกัน)'
        }

        query = f"""
            SELECT
                COALESCE(service_type, '') as stype,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid,
                COUNT(DISTINCT hn) as patients
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY service_type
            ORDER BY SUM(reimb_nhso) DESC
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        service_data = [
            {
                'type': row[0] or 'OP/IP',
                'name': service_names.get(row[0] or '', row[0] or 'OP/IP'),
                'claims': row[1],
                'reimb': float(row[2] or 0),
                'paid': float(row[3] or 0),
                'patients': row[4]
            }
            for row in rows
        ]

        return jsonify({'success': True, 'data': service_data})

    except Exception as e:
        current_app.logger.error(f"Error in service type analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@analytics_api_bp.route('/api/analytics/fund')
def api_analytics_fund():
    """Get claims by fund type"""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "1=1"
        if date_filter:
            base_where = date_filter

        query = f"""
            SELECT
                COALESCE(main_fund, 'ไม่ระบุ') as fund,
                COUNT(*) as claims,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid,
                COUNT(DISTINCT hn) as patients
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY main_fund
            ORDER BY SUM(reimb_nhso) DESC
            LIMIT 10
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        fund_data = [
            {
                'fund': row[0],
                'claims': row[1],
                'claimed': float(row[2] or 0),
                'reimb': float(row[3] or 0),
                'paid': float(row[4] or 0),
                'patients': row[5]
            }
            for row in rows
        ]

        return jsonify({'success': True, 'data': fund_data})

    except Exception as e:
        current_app.logger.error(f"Error in fund analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@analytics_api_bp.route('/api/analytics/drg')
def api_analytics_drg():
    """Get DRG analysis for IP claims"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "drg IS NOT NULL AND drg != ''"
        rw_where = "rw IS NOT NULL AND rw > 0"
        if date_filter:
            base_where += f" AND {date_filter}"
            rw_where += f" AND {date_filter}"

        # Top DRGs
        query = f"""
            SELECT
                drg,
                COUNT(*) as cases,
                COALESCE(AVG(rw), 0) as avg_rw,
                COALESCE(SUM(claim_drg), 0) as total_drg,
                COALESCE(SUM(paid), 0) as total_paid
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY drg
            ORDER BY COUNT(*) DESC
            LIMIT 15
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        drg_data = [
            {
                'drg': row[0],
                'cases': row[1],
                'avg_rw': round(float(row[2] or 0), 4),
                'total_drg': float(row[3] or 0),
                'total_paid': float(row[4] or 0)
            }
            for row in rows
        ]

        # RW distribution
        rw_query = f"""
            SELECT rw_range, cases FROM (
                SELECT
                    CASE
                        WHEN rw < 0.5 THEN '< 0.5'
                        WHEN rw < 1.0 THEN '0.5-1.0'
                        WHEN rw < 2.0 THEN '1.0-2.0'
                        WHEN rw < 3.0 THEN '2.0-3.0'
                        WHEN rw < 5.0 THEN '3.0-5.0'
                        ELSE '>= 5.0'
                    END as rw_range,
                    CASE
                        WHEN rw < 0.5 THEN 1
                        WHEN rw < 1.0 THEN 2
                        WHEN rw < 2.0 THEN 3
                        WHEN rw < 3.0 THEN 4
                        WHEN rw < 5.0 THEN 5
                        ELSE 6
                    END as sort_order,
                    COUNT(*) as cases
                FROM claim_rep_opip_nhso_item
                WHERE {rw_where}
                GROUP BY rw_range, sort_order
            ) t
            ORDER BY sort_order
        """
        cursor.execute(rw_query, filter_params)
        rw_rows = cursor.fetchall()

        rw_distribution = [
            {'range': row[0], 'cases': row[1]}
            for row in rw_rows
        ]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'top_drg': drg_data,
                'rw_distribution': rw_distribution
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/drug')
def api_analytics_drug():
    """Get drug analysis"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter - use c.dateadm since we JOIN with claims table
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        # Replace dateadm with c.dateadm for JOIN query
        date_filter_joined = date_filter.replace('dateadm', 'c.dateadm') if date_filter else ''

        base_where = "d.generic_name IS NOT NULL AND d.generic_name != ''"
        all_where = "1=1"
        if date_filter_joined:
            base_where += f" AND {date_filter_joined}"
            all_where = date_filter_joined

        # Top drugs by reimb - JOIN with claims table to get dateadm
        # Use reimb_amount (ยอดชดเชย) instead of claim_amount (ยอดเรียกเก็บ)
        query = f"""
            SELECT
                COALESCE(d.generic_name, d.trade_name, d.drug_code) as drug_name,
                COUNT(*) as prescriptions,
                COALESCE(SUM(d.quantity), 0) as total_qty,
                COALESCE(SUM(d.reimb_amount), 0) as total_reimb
            FROM eclaim_drug d
            INNER JOIN claim_rep_opip_nhso_item c ON d.tran_id = c.tran_id
            WHERE {base_where}
            GROUP BY COALESCE(d.generic_name, d.trade_name, d.drug_code)
            ORDER BY SUM(d.reimb_amount) DESC
            LIMIT 15
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        drug_data = [
            {
                'name': row[0][:50] if row[0] else 'ไม่ระบุ',
                'prescriptions': row[1],
                'total_qty': float(row[2] or 0),
                'total_cost': float(row[3] or 0)
            }
            for row in rows
        ]

        # Summary by drug_type - also JOIN with claims table
        cat_query = f"""
            SELECT
                COALESCE(d.drug_type, 'ไม่ระบุ') as category,
                COUNT(*) as items,
                COALESCE(SUM(d.claim_amount), 0) as total_cost
            FROM eclaim_drug d
            INNER JOIN claim_rep_opip_nhso_item c ON d.tran_id = c.tran_id
            WHERE {all_where}
            GROUP BY d.drug_type
            ORDER BY SUM(d.claim_amount) DESC
            LIMIT 10
        """
        cursor.execute(cat_query, filter_params)
        cat_rows = cursor.fetchall()

        category_data = [
            {
                'category': row[0],
                'items': row[1],
                'total_cost': float(row[2] or 0)
            }
            for row in cat_rows
        ]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'top_drugs': drug_data,
                'categories': category_data
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/instrument')
def api_analytics_instrument():
    """Get instrument/procedure analysis"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter - use c.dateadm since we JOIN with claims table
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        date_filter_joined = date_filter.replace('dateadm', 'c.dateadm') if date_filter else ''

        base_where = "i.inst_name IS NOT NULL AND i.inst_name != ''"
        if date_filter_joined:
            base_where += f" AND {date_filter_joined}"

        # Top instruments by cost - JOIN with claims table to get dateadm
        query = f"""
            SELECT
                i.inst_name,
                COUNT(*) as uses,
                COALESCE(SUM(i.claim_qty), 0) as total_qty,
                COALESCE(SUM(i.claim_amount), 0) as total_cost
            FROM eclaim_instrument i
            INNER JOIN claim_rep_opip_nhso_item c ON i.tran_id = c.tran_id
            WHERE {base_where}
            GROUP BY i.inst_name
            ORDER BY SUM(i.claim_amount) DESC
            LIMIT 15
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        instrument_data = [
            {
                'name': row[0][:50] if row[0] else 'ไม่ระบุ',
                'uses': row[1],
                'total_qty': float(row[2] or 0),
                'total_cost': float(row[3] or 0)
            }
            for row in rows
        ]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': instrument_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/denial')
def api_analytics_denial():
    """Get denial analysis"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter - use c.dateadm since we JOIN with claims table
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        date_filter_joined = date_filter.replace('dateadm', 'c.dateadm') if date_filter else ''

        deny_where = "1=1"
        error_where = "error_code IS NOT NULL AND error_code != ''"
        if date_filter_joined:
            deny_where = date_filter_joined
        if date_filter:
            error_where += f" AND {date_filter}"

        # Denials by deny_code - JOIN with claims table to get dateadm
        query = f"""
            SELECT
                COALESCE(d.deny_code, 'ไม่ระบุรหัส') as reason,
                COUNT(*) as cases,
                COALESCE(SUM(d.claim_amount), 0) as total_amount
            FROM eclaim_deny d
            INNER JOIN claim_rep_opip_nhso_item c ON d.tran_id = c.tran_id
            WHERE {deny_where}
            GROUP BY d.deny_code
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        denial_data = [
            {
                'reason': row[0][:80] if row[0] else 'ไม่ระบุ',
                'cases': row[1],
                'total_amount': float(row[2] or 0)
            }
            for row in rows
        ]

        # Error codes from main claims table (this already uses dateadm directly)
        error_query = f"""
            SELECT
                COALESCE(error_code, 'ไม่มี') as error,
                COUNT(*) as cases
            FROM claim_rep_opip_nhso_item
            WHERE {error_where}
            GROUP BY error_code
            ORDER BY COUNT(*) DESC
            LIMIT 10
        """
        cursor.execute(error_query, filter_params)
        error_rows = cursor.fetchall()

        error_data = [
            {'error': row[0], 'cases': row[1]}
            for row in error_rows
        ]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'denials': denial_data,
                'errors': error_data
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/comparison')
def api_analytics_comparison():
    """Get claim vs payment comparison by month"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "dateadm IS NOT NULL"
        if date_filter:
            base_where += f" AND {date_filter}"

        # Monthly comparison
        year_month_col = sql_format_year_month('dateadm')
        query = f"""
            SELECT
                {year_month_col} as month,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as approved,
                COALESCE(SUM(paid), 0) as paid
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY {year_month_col}
            ORDER BY month DESC
            LIMIT 12
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        comparison_data = [
            {
                'month': row[0],
                'claimed': float(row[1] or 0),
                'approved': float(row[2] or 0),
                'paid': float(row[3] or 0),
                'approval_rate': round(float(row[2] or 0) / float(row[1] or 1) * 100, 2) if row[1] else 0
            }
            for row in reversed(rows)
        ]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': comparison_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Phase 1: Decision Support APIs
# ============================================


@analytics_api_bp.route('/api/analytics/claims')
def api_claims_detail():
    """
    Phase 1.1: Claim Detail Viewer
    Paginated claim-level details with filters for drill-down analysis.

    Query params:
    - page: Page number (default: 1)
    - per_page: Items per page (default: 50, max: 100)
    - status: Filter by status (denied, error, success, all)
    - fiscal_year: Filter by fiscal year (BE)
    - start_date, end_date: Date range filter (YYYY-MM-DD)
    - fund: Filter by main_fund
    - service_type: Filter by service type
    - search: Search in tran_id, hn, pid
    - sort: Sort field (dateadm, claim_drg, reimb_nhso, error_code)
    - order: Sort order (asc, desc)
    """
    try:
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 50, type=int), 100)
        offset = (page - 1) * per_page

        # Filters
        status = request.args.get('status', 'all')
        fiscal_year = request.args.get('fiscal_year', type=int)
        start_date = _validate_date_param(request.args.get('start_date'))
        end_date = _validate_date_param(request.args.get('end_date'))
        fund = request.args.get('fund')
        service_type = request.args.get('service_type')
        search = request.args.get('search', '').strip()

        # Sorting
        sort_field = request.args.get('sort', 'dateadm')
        sort_order = request.args.get('order', 'desc')

        # Validate sort field (prevent SQL injection)
        allowed_sorts = ['dateadm', 'datedsc', 'claim_drg', 'reimb_nhso', 'paid', 'error_code', 'tran_id']
        if sort_field not in allowed_sorts:
            sort_field = 'dateadm'
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Build WHERE clause
        where_clauses = ["1=1"]
        params = []

        # Status filter
        if status == 'denied':
            where_clauses.append("(error_code IS NOT NULL AND error_code != '')")
        elif status == 'error':
            where_clauses.append("(error_code IS NOT NULL AND error_code != '')")
        elif status == 'success':
            where_clauses.append("(error_code IS NULL OR error_code = '')")

        # Fiscal year filter
        if fiscal_year:
            where_clause, where_params = get_fiscal_year_sql_filter_gregorian(fiscal_year, 'dateadm')
            where_clauses.append(where_clause)
            params.extend(where_params)

        # Date range filter
        if start_date:
            where_clauses.append("dateadm >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("dateadm <= %s")
            params.append(end_date)

        # Fund filter (use scheme column for main fund categories like UCS, LGO, SSS)
        if fund:
            where_clauses.append("scheme = %s")
            params.append(fund)

        # Service type filter (handle empty string for 'ไม่ระบุ')
        if service_type is not None and service_type != '':
            if service_type == 'EMPTY':
                where_clauses.append("(service_type IS NULL OR service_type = '')")
            else:
                where_clauses.append("service_type = %s")
                params.append(service_type)

        # Search filter (tran_id, hn, pid)
        if search:
            like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
            where_clauses.append(f"(tran_id {like_op} %s OR hn {like_op} %s OR pid {like_op} %s)")
            search_pattern = f"%{search}%"
            params.extend([search_pattern, search_pattern, search_pattern])

        where_clause = " AND ".join(where_clauses)

        # Get total count
        count_query = "SELECT COUNT(*) FROM claim_rep_opip_nhso_item WHERE " + where_clause
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated data
        select_query = """
            SELECT
                tran_id, rep_no, hn, an, pid, name,
                dateadm, datedsc,
                service_type, main_fund, sub_fund,
                claim_drg, reimb_nhso, reimb_agency, paid,
                drg, rw,
                error_code,
                file_id,
                scheme
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause + """
            ORDER BY """ + sort_field + " " + sort_order + """
            LIMIT %s OFFSET %s
        """
        cursor.execute(select_query, params + [per_page, offset])
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Format results
        claims = []
        for r in rows:
            claim = {
                'tran_id': r[0],
                'rep_no': r[1],
                'hn': r[2],
                'an': r[3],
                'pid': r[4],
                'name': r[5],
                'dateadm': str(r[6]) if r[6] else None,
                'datedsc': str(r[7]) if r[7] else None,
                'service_type': r[8],
                'main_fund': r[9],
                'sub_fund': r[10],
                'claim_drg': float(r[11] or 0),
                'reimb_nhso': float(r[12] or 0),
                'reimb_agency': float(r[13] or 0),
                'paid': float(r[14] or 0),
                'drg': r[15],
                'rw': float(r[16] or 0) if r[16] else None,
                'error_code': r[17],
                'file_id': r[18],
                'scheme': r[19],
                'has_error': bool(r[17] and r[17].strip()),
                'reimb_rate': round(float(r[14] or 0) / float(r[11]) * 100, 1) if r[11] and float(r[11]) > 0 else 0
            }
            claims.append(claim)

        # Calculate pagination info
        total_pages = (total + per_page - 1) // per_page

        return jsonify({
            'success': True,
            'data': claims,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages,
                'has_next': page < total_pages,
                'has_prev': page > 1
            },
            'filters': {
                'status': status,
                'fiscal_year': fiscal_year,
                'start_date': start_date,
                'end_date': end_date,
                'fund': fund,
                'service_type': service_type,
                'search': search
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in claims detail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/claim/<tran_id>')
def api_claim_single(tran_id):
    """
    Get single claim details by tran_id
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get main claim data
        cursor.execute("""
            SELECT *
            FROM claim_rep_opip_nhso_item
            WHERE tran_id = %s
            ORDER BY file_id DESC
            LIMIT 1
        """, [tran_id])

        row = cursor.fetchone()
        if not row:
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'error': 'Claim not found'}), 404

        # Get column names
        columns = [desc[0] for desc in cursor.description]
        claim = dict(zip(columns, row))

        # Convert decimal/date types
        for key, value in claim.items():
            if hasattr(value, 'isoformat'):
                claim[key] = value.isoformat()
            elif hasattr(value, '__float__'):
                claim[key] = float(value)

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': claim
        })

    except Exception as e:
        current_app.logger.error(f"Error getting claim {tran_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/denial-root-cause')
def api_denial_root_cause():
    """
    Phase 1.2: Denial Root Cause Analysis
    Analyze denial patterns and identify root causes.

    Query params:
    - fiscal_year: Filter by fiscal year (BE)
    - start_date, end_date: Date range filter
    - error_code: Filter by specific error code
    """
    try:
        fiscal_year = request.args.get('fiscal_year', type=int)
        start_date = _validate_date_param(request.args.get('start_date'))
        end_date = _validate_date_param(request.args.get('end_date'))
        error_code_filter = request.args.get('error_code')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Build date filter
        where_clauses = ["error_code IS NOT NULL", "error_code != ''"]
        params = []

        if fiscal_year:
            where_clause, where_params = get_fiscal_year_sql_filter_gregorian(fiscal_year, 'dateadm')
            where_clauses.append(where_clause)
            params.extend(where_params)

        if start_date:
            where_clauses.append("dateadm >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("dateadm <= %s")
            params.append(end_date)

        if error_code_filter:
            where_clauses.append("error_code = %s")
            params.append(error_code_filter)

        where_clause = " AND ".join(where_clauses)

        # 1. Overall denial statistics
        stats_query = """
            SELECT
                COUNT(*) as total_denials,
                COUNT(DISTINCT error_code) as unique_error_codes,
                COALESCE(SUM(claim_drg), 0) as total_denied_amount,
                COALESCE(SUM(reimb_nhso), 0) as total_reimb_lost
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause
        cursor.execute(stats_query, params)
        stats_row = cursor.fetchone()

        # Get total claims for rate calculation
        total_query = """
            SELECT COUNT(*), COALESCE(SUM(claim_drg), 0)
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
        """
        if fiscal_year:
            total_query += " AND dateadm >= %s AND dateadm <= %s"
            cursor.execute(total_query, [fy_start, fy_end])
        elif start_date or end_date:
            date_params = []
            if start_date:
                total_query += " AND dateadm >= %s"
                date_params.append(start_date)
            if end_date:
                total_query += " AND dateadm <= %s"
                date_params.append(end_date)
            cursor.execute(total_query, date_params)
        else:
            cursor.execute(total_query)
        total_row = cursor.fetchone()

        denial_rate = round(stats_row[0] / total_row[0] * 100, 2) if total_row[0] > 0 else 0

        # 2. Error code breakdown
        error_query = """
            SELECT
                error_code,
                COUNT(*) as count,
                COALESCE(SUM(claim_drg), 0) as total_amount,
                ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 2) as percentage
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause + """
            GROUP BY error_code
            ORDER BY count DESC
            LIMIT 15
        """
        cursor.execute(error_query, params)
        error_rows = cursor.fetchall()

        error_breakdown = [
            {
                'error_code': r[0],
                'count': r[1],
                'amount': float(r[2]),
                'percentage': float(r[3]) if r[3] else 0
            }
            for r in error_rows
        ]

        # 3. Denial by service type
        service_query = """
            SELECT
                COALESCE(service_type, 'Unknown') as service_type,
                COUNT(*) as count,
                COALESCE(SUM(claim_drg), 0) as total_amount
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause + """
            GROUP BY service_type
            ORDER BY count DESC
        """
        cursor.execute(service_query, params)
        service_rows = cursor.fetchall()

        by_service = [
            {
                'service_type': r[0],
                'count': r[1],
                'amount': float(r[2])
            }
            for r in service_rows
        ]

        # 4. Denial by fund
        fund_query = """
            SELECT
                COALESCE(main_fund, 'Unknown') as fund,
                COUNT(*) as count,
                COALESCE(SUM(claim_drg), 0) as total_amount
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause + """
            GROUP BY main_fund
            ORDER BY count DESC
            LIMIT 10
        """
        cursor.execute(fund_query, params)
        fund_rows = cursor.fetchall()

        by_fund = [
            {
                'fund': r[0],
                'count': r[1],
                'amount': float(r[2])
            }
            for r in fund_rows
        ]

        # 5. Monthly trend
        trend_query = """
            SELECT
                """ + sql_format_year_month('dateadm') + """ as month,
                COUNT(*) as count,
                COALESCE(SUM(claim_drg), 0) as total_amount
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause + """ AND dateadm IS NOT NULL
            GROUP BY """ + sql_format_year_month('dateadm') + """
            ORDER BY month DESC
            LIMIT 12
        """
        cursor.execute(trend_query, params)
        trend_rows = cursor.fetchall()

        monthly_trend = [
            {
                'month': r[0],
                'count': r[1],
                'amount': float(r[2])
            }
            for r in reversed(trend_rows)
        ]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'summary': {
                    'total_denials': stats_row[0],
                    'unique_error_codes': stats_row[1],
                    'total_denied_amount': float(stats_row[2]),
                    'total_reimb_lost': float(stats_row[3]),
                    'denial_rate': denial_rate,
                    'total_claims': total_row[0],
                    'total_claims_amount': float(total_row[1])
                },
                'by_error_code': error_breakdown,
                'by_service_type': by_service,
                'by_fund': by_fund,
                'monthly_trend': monthly_trend
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in denial root cause: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/efficiency')
def api_analytics_efficiency():
    """
    Claims Efficiency Metrics - วัดประสิทธิภาพการส่งเคลม

    Metrics:
    - First-Pass Rate: % เคลมที่ผ่านรอบแรก (ไม่มี error_code)
    - Denial Rate: % เคลมที่ถูกปฏิเสธ
    - Reimbursement Rate: % ที่ได้คืนจากยอดเคลม
    - Efficiency by Fund: ประสิทธิภาพตามสิทธิ
    - OP vs IP Efficiency: เปรียบเทียบ OPD/IPD
    - Monthly Trend: trend ประสิทธิภาพรายเดือน
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "dateadm IS NOT NULL"
        if date_filter:
            base_where = base_where + " AND " + date_filter

        # 1. Overall Efficiency Metrics
        overall_query = """
            SELECT
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NULL OR error_code = '' THEN 1 END) as passed_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as denied_claims,
                COALESCE(SUM(claim_drg), 0) as total_claimed,
                COALESCE(SUM(reimb_nhso), 0) as total_reimbursed,
                COALESCE(SUM(CASE WHEN error_code IS NULL OR error_code = '' THEN claim_drg ELSE 0 END), 0) as passed_claimed,
                COALESCE(SUM(CASE WHEN error_code IS NULL OR error_code = '' THEN reimb_nhso ELSE 0 END), 0) as passed_reimbursed
            FROM claim_rep_opip_nhso_item
            WHERE """ + base_where
        cursor.execute(overall_query, filter_params)
        row = cursor.fetchone()

        total_claims = row[0] or 0
        passed_claims = row[1] or 0
        denied_claims = row[2] or 0
        total_claimed = float(row[3] or 0)
        total_reimbursed = float(row[4] or 0)

        # Calculate rates
        first_pass_rate = round(passed_claims / total_claims * 100, 1) if total_claims > 0 else 0
        denial_rate = round(denied_claims / total_claims * 100, 1) if total_claims > 0 else 0
        reimb_rate = round(total_reimbursed / total_claimed * 100, 1) if total_claimed > 0 else 0
        loss_amount = total_claimed - total_reimbursed

        overall = {
            'total_claims': total_claims,
            'passed_claims': passed_claims,
            'denied_claims': denied_claims,
            'total_claimed': total_claimed,
            'total_reimbursed': total_reimbursed,
            'loss_amount': loss_amount,
            'first_pass_rate': first_pass_rate,
            'denial_rate': denial_rate,
            'reimb_rate': reimb_rate
        }

        # 2. Efficiency by Service Type (OP vs IP)
        service_query = """
            SELECT
                CASE WHEN an IS NOT NULL AND an != '' THEN 'IP' ELSE 'OP' END as service_type,
                COUNT(*) as claims,
                COUNT(CASE WHEN error_code IS NULL OR error_code = '' THEN 1 END) as passed,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimbursed
            FROM claim_rep_opip_nhso_item
            WHERE """ + base_where + """
            GROUP BY CASE WHEN an IS NOT NULL AND an != '' THEN 'IP' ELSE 'OP' END
            ORDER BY service_type
        """
        cursor.execute(service_query, filter_params)
        service_rows = cursor.fetchall()

        by_service = []
        for row in service_rows:
            svc_type, claims, passed, claimed, reimbursed = row
            claimed = float(claimed or 0)
            reimbursed = float(reimbursed or 0)
            by_service.append({
                'type': svc_type,
                'claims': claims,
                'passed': passed,
                'first_pass_rate': round(passed / claims * 100, 1) if claims > 0 else 0,
                'claimed': claimed,
                'reimbursed': reimbursed,
                'reimb_rate': round(reimbursed / claimed * 100, 1) if claimed > 0 else 0,
                'loss': claimed - reimbursed
            })

        # 3. Efficiency by Fund (สิทธิ)
        fund_query = """
            SELECT
                COALESCE(main_fund, 'ไม่ระบุ') as fund,
                COUNT(*) as claims,
                COUNT(CASE WHEN error_code IS NULL OR error_code = '' THEN 1 END) as passed,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimbursed
            FROM claim_rep_opip_nhso_item
            WHERE """ + base_where + """
            GROUP BY COALESCE(main_fund, 'ไม่ระบุ')
            ORDER BY SUM(claim_drg) DESC
            LIMIT 10
        """
        cursor.execute(fund_query, filter_params)
        fund_rows = cursor.fetchall()

        by_fund = []
        for row in fund_rows:
            fund, claims, passed, claimed, reimbursed = row
            claimed = float(claimed or 0)
            reimbursed = float(reimbursed or 0)
            by_fund.append({
                'fund': fund,
                'claims': claims,
                'passed': passed,
                'first_pass_rate': round(passed / claims * 100, 1) if claims > 0 else 0,
                'claimed': claimed,
                'reimbursed': reimbursed,
                'reimb_rate': round(reimbursed / claimed * 100, 1) if claimed > 0 else 0,
                'loss': claimed - reimbursed
            })

        # 4. Monthly Efficiency Trend (last 6 months)
        monthly_query = """
            SELECT
                """ + sql_format_month('dateadm') + """ as month,
                COUNT(*) as claims,
                COUNT(CASE WHEN error_code IS NULL OR error_code = '' THEN 1 END) as passed,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimbursed
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
            GROUP BY """ + sql_format_month('dateadm') + """
            ORDER BY """ + sql_format_month('dateadm') + """ DESC
            LIMIT 6
        """
        cursor.execute(monthly_query)
        monthly_rows = cursor.fetchall()

        monthly_trend = []
        for row in monthly_rows:
            month, claims, passed, claimed, reimbursed = row
            claimed = float(claimed or 0)
            reimbursed = float(reimbursed or 0)
            monthly_trend.append({
                'month': month,
                'claims': claims,
                'first_pass_rate': round(passed / claims * 100, 1) if claims > 0 else 0,
                'reimb_rate': round(reimbursed / claimed * 100, 1) if claimed > 0 else 0
            })

        # Reverse to show oldest first
        monthly_trend.reverse()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'overall': overall,
                'by_service': by_service,
                'by_fund': by_fund,
                'monthly_trend': monthly_trend,
                'filter': filter_info
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in efficiency metrics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/alerts')
def api_alerts():
    """
    Phase 1.3: Alert System
    Get active alerts based on predefined thresholds.

    Alerts checked:
    - Denial Rate > 10%
    - Reimb Rate < 85%
    - Fund variance > 15%
    - Monthly decline > 20%
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        alerts = []

        # Get current month data
        cursor.execute("""
            SELECT
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as denied_claims,
                COALESCE(SUM(claim_drg), 0) as total_claimed,
                COALESCE(SUM(paid), 0) as total_paid
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= """ + sql_current_month_start())
        current = cursor.fetchone()

        if current[0] > 0:
            # Alert 1: High Denial Rate
            denial_rate = round(current[1] / current[0] * 100, 2)
            if denial_rate > 10:
                alerts.append({
                    'id': 'denial_rate_high',
                    'type': 'error',
                    'severity': 'critical',
                    'title': 'Denial Rate สูงเกินเกณฑ์',
                    'message': f'Denial Rate เดือนนี้ {denial_rate}% (เกณฑ์: <10%)',
                    'metric': 'denial_rate',
                    'value': denial_rate,
                    'threshold': 10,
                    'action': 'ตรวจสอบ Error Codes และแก้ไขด่วน'
                })
            elif denial_rate > 5:
                alerts.append({
                    'id': 'denial_rate_warning',
                    'type': 'warning',
                    'severity': 'warning',
                    'title': 'Denial Rate เริ่มสูง',
                    'message': f'Denial Rate เดือนนี้ {denial_rate}% (ควรต่ำกว่า 5%)',
                    'metric': 'denial_rate',
                    'value': denial_rate,
                    'threshold': 5,
                    'action': 'ติดตามและเฝ้าระวัง'
                })

            # Alert 2: Low Reimbursement Rate
            if current[2] > 0:
                reimb_rate = round(current[3] / current[2] * 100, 2)
                if reimb_rate < 85:
                    alerts.append({
                        'id': 'reimb_rate_low',
                        'type': 'error',
                        'severity': 'critical',
                        'title': 'Reimbursement Rate ต่ำ',
                        'message': f'Reimb Rate เดือนนี้ {reimb_rate}% (เกณฑ์: >85%)',
                        'metric': 'reimb_rate',
                        'value': reimb_rate,
                        'threshold': 85,
                        'action': 'ตรวจสอบ Claims ที่ยังไม่ได้รับเงิน'
                    })
                elif reimb_rate < 90:
                    alerts.append({
                        'id': 'reimb_rate_warning',
                        'type': 'warning',
                        'severity': 'warning',
                        'title': 'Reimbursement Rate ต่ำกว่าเป้า',
                        'message': f'Reimb Rate เดือนนี้ {reimb_rate}% (เป้า: >90%)',
                        'metric': 'reimb_rate',
                        'value': reimb_rate,
                        'threshold': 90,
                        'action': 'ติดตาม Claims ค้างรับ'
                    })

        # Alert 3: Month-over-Month decline
        cursor.execute("""
            SELECT
                """ + sql_format_year_month('dateadm') + """ as month,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= """ + sql_current_month_start() + """ - """ + sql_interval_months(2) + """
            GROUP BY """ + sql_format_year_month('dateadm') + """
            ORDER BY month DESC
            LIMIT 2
        """)
        monthly = cursor.fetchall()

        if len(monthly) >= 2:
            current_reimb = float(monthly[0][2])
            prev_reimb = float(monthly[1][2])
            if prev_reimb > 0:
                change_pct = round((current_reimb - prev_reimb) / prev_reimb * 100, 2)
                if change_pct < -20:
                    alerts.append({
                        'id': 'revenue_decline',
                        'type': 'error',
                        'severity': 'critical',
                        'title': 'รายได้ลดลงมาก',
                        'message': f'Reimb ลดลง {abs(change_pct)}% จากเดือนก่อน',
                        'metric': 'mom_change',
                        'value': change_pct,
                        'threshold': -20,
                        'action': 'วิเคราะห์สาเหตุและดำเนินการแก้ไข'
                    })
                elif change_pct < -10:
                    alerts.append({
                        'id': 'revenue_decline_warning',
                        'type': 'warning',
                        'severity': 'warning',
                        'title': 'รายได้ลดลง',
                        'message': f'Reimb ลดลง {abs(change_pct)}% จากเดือนก่อน',
                        'metric': 'mom_change',
                        'value': change_pct,
                        'threshold': -10,
                        'action': 'ติดตามแนวโน้ม'
                    })

        # Alert 4: Pending claims (no payment)
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM claim_rep_opip_nhso_item
            WHERE (paid IS NULL OR paid = 0)
            AND claim_drg > 0
            AND dateadm < CURRENT_DATE - {sql_interval_days(30)}
        """)
        pending = cursor.fetchone()[0]
        if pending > 100:
            alerts.append({
                'id': 'pending_claims',
                'type': 'warning',
                'severity': 'warning',
                'title': 'Claims รอการชำระเงินมาก',
                'message': f'มี {pending:,} claims ที่ยังไม่ได้รับเงิน (>30 วัน)',
                'metric': 'pending_claims',
                'value': pending,
                'threshold': 100,
                'action': 'ติดตามกับ สปสช.'
            })

        cursor.close()
        conn.close()

        # Sort alerts by severity
        severity_order = {'critical': 0, 'warning': 1, 'info': 2}
        alerts.sort(key=lambda x: severity_order.get(x['severity'], 99))

        return jsonify({
            'success': True,
            'data': {
                'alerts': alerts,
                'total': len(alerts),
                'critical_count': sum(1 for a in alerts if a['severity'] == 'critical'),
                'warning_count': sum(1 for a in alerts if a['severity'] == 'warning')
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error getting alerts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Phase 2: Strategic Analytics APIs
# ============================================


@analytics_api_bp.route('/api/analytics/forecast')
def api_revenue_forecast():
    """
    Phase 2.1: Revenue Projection
    Forecast revenue for next 6 months based on historical trends.

    Uses simple linear regression on monthly data.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get historical monthly data (last 24 months)
        query = """
            SELECT
                """ + sql_format_year_month('dateadm') + """ as month,
                COUNT(*) as claims,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
              AND dateadm >= CURRENT_DATE - """ + sql_interval_months(24) + """
            GROUP BY """ + sql_format_year_month('dateadm') + """
            ORDER BY month ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        historical = [
            {
                'month': r[0],
                'claims': r[1],
                'claimed': float(r[2]),
                'reimb': float(r[3]),
                'paid': float(r[4])
            }
            for r in rows
        ]

        # Simple forecasting using moving average and trend
        forecast = []
        if len(historical) >= 6:
            # Calculate average growth rate from last 6 months
            recent = historical[-6:]
            reimb_values = [h['reimb'] for h in recent]

            # Average monthly value
            avg_reimb = sum(reimb_values) / len(reimb_values)

            # Calculate trend (simple linear)
            n = len(reimb_values)
            if n > 1:
                x_mean = (n - 1) / 2
                y_mean = avg_reimb
                numerator = sum((i - x_mean) * (reimb_values[i] - y_mean) for i in range(n))
                denominator = sum((i - x_mean) ** 2 for i in range(n))
                slope = numerator / denominator if denominator != 0 else 0
            else:
                slope = 0

            # Generate forecast for next 6 months
            from datetime import datetime
            from dateutil.relativedelta import relativedelta

            last_month = datetime.strptime(historical[-1]['month'], '%Y-%m')

            for i in range(1, 7):
                future_month = last_month + relativedelta(months=i)
                projected_value = avg_reimb + (slope * (n + i - 1))

                # Confidence decreases with distance
                confidence = max(50, 95 - (i * 7))

                # Seasonality adjustment (simple: same month last year if available)
                seasonal_adjustment = 1.0
                target_month_str = future_month.strftime('%Y-%m')
                last_year_month = (future_month - relativedelta(years=1)).strftime('%Y-%m')
                for h in historical:
                    if h['month'] == last_year_month:
                        if avg_reimb > 0:
                            seasonal_adjustment = h['reimb'] / avg_reimb
                        break

                adjusted_value = projected_value * seasonal_adjustment

                forecast.append({
                    'month': future_month.strftime('%Y-%m'),
                    'month_name': future_month.strftime('%b %Y'),
                    'projected_reimb': round(adjusted_value, 2),
                    'projected_claims': round(sum(h['claims'] for h in recent) / len(recent)),
                    'confidence': confidence,
                    'lower_bound': round(adjusted_value * 0.85, 2),
                    'upper_bound': round(adjusted_value * 1.15, 2)
                })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'historical': historical[-12:],  # Last 12 months
                'forecast': forecast,
                'method': 'linear_regression_with_seasonality',
                'data_points': len(historical)
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in revenue forecast: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/yoy-comparison')
def api_yoy_comparison():
    """
    Phase 2.2: Year-over-Year Comparison
    Compare current fiscal year with previous fiscal year.
    """
    try:
        fiscal_year = request.args.get('fiscal_year', type=int)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # If no fiscal year specified, get current
        if not fiscal_year:
            cursor.execute(f"SELECT MAX({sql_extract_year('dateadm')}) FROM claim_rep_opip_nhso_item WHERE dateadm IS NOT NULL")
            max_year = cursor.fetchone()[0]
            if max_year:
                # Convert to fiscal year (Thai Buddhist Era)
                fiscal_year = int(max_year) + 543
                # Adjust for fiscal year (Oct-Sep)
                cursor.execute("SELECT MAX(dateadm) FROM claim_rep_opip_nhso_item")
                max_date = cursor.fetchone()[0]
                if max_date and max_date.month >= 10:
                    fiscal_year += 1

        if not fiscal_year:
            return jsonify({'success': False, 'error': 'No data available'}), 404

        # Current fiscal year dates
        current_gregorian = fiscal_year - 543
        current_start = f"{current_gregorian - 1}-10-01"
        current_end = f"{current_gregorian}-09-30"

        # Previous fiscal year dates
        prev_start = f"{current_gregorian - 2}-10-01"
        prev_end = f"{current_gregorian - 1}-09-30"

        # Get current year stats
        current_query = """
            SELECT
                COUNT(*) as claims,
                COALESCE(SUM(claim_drg), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as denials
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= %s AND dateadm <= %s
        """
        cursor.execute(current_query, [current_start, current_end])
        current = cursor.fetchone()

        # Get previous year stats
        cursor.execute(current_query, [prev_start, prev_end])
        previous = cursor.fetchone()

        # Get monthly breakdown for both years
        month_expr = sql_extract_month('dateadm')
        monthly_query = f"""
            SELECT
                {month_expr} as month,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= %s AND dateadm <= %s
            GROUP BY {month_expr}
            ORDER BY month
        """

        cursor.execute(monthly_query, [current_start, current_end])
        current_monthly = {int(r[0]): {'claims': r[1], 'reimb': float(r[2])} for r in cursor.fetchall()}

        cursor.execute(monthly_query, [prev_start, prev_end])
        prev_monthly = {int(r[0]): {'claims': r[1], 'reimb': float(r[2])} for r in cursor.fetchall()}

        cursor.close()
        conn.close()

        # Calculate changes
        def calc_change(current_val, prev_val):
            if prev_val and prev_val > 0:
                return round(float((current_val - prev_val) / prev_val) * 100, 2)
            return 0

        current_denial_rate = float(current[4] / current[0] * 100) if current[0] > 0 else 0
        prev_denial_rate = float(previous[4] / previous[0] * 100) if previous[0] > 0 else 0

        current_reimb_rate = float(current[2] / current[1] * 100) if current[1] > 0 else 0
        prev_reimb_rate = float(previous[2] / previous[1] * 100) if previous[1] > 0 else 0

        # Monthly comparison (fiscal year months: Oct=10, Nov=11, ..., Sep=9)
        fiscal_months = [10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        month_names = ['ต.ค.', 'พ.ย.', 'ธ.ค.', 'ม.ค.', 'ก.พ.', 'มี.ค.', 'เม.ย.', 'พ.ค.', 'มิ.ย.', 'ก.ค.', 'ส.ค.', 'ก.ย.']

        monthly_comparison = []
        for i, m in enumerate(fiscal_months):
            curr = current_monthly.get(m, {'claims': 0, 'reimb': 0})
            prev = prev_monthly.get(m, {'claims': 0, 'reimb': 0})
            monthly_comparison.append({
                'month': month_names[i],
                'month_num': m,
                'current_claims': curr['claims'],
                'current_reimb': curr['reimb'],
                'prev_claims': prev['claims'],
                'prev_reimb': prev['reimb'],
                'claims_change': calc_change(curr['claims'], prev['claims']),
                'reimb_change': calc_change(curr['reimb'], prev['reimb'])
            })

        return jsonify({
            'success': True,
            'data': {
                'fiscal_year': fiscal_year,
                'previous_year': fiscal_year - 1,
                'summary': {
                    'current': {
                        'claims': current[0],
                        'claimed': float(current[1]),
                        'reimb': float(current[2]),
                        'paid': float(current[3]),
                        'denials': current[4],
                        'denial_rate': round(current_denial_rate, 2),
                        'reimb_rate': round(current_reimb_rate, 2)
                    },
                    'previous': {
                        'claims': previous[0],
                        'claimed': float(previous[1]),
                        'reimb': float(previous[2]),
                        'paid': float(previous[3]),
                        'denials': previous[4],
                        'denial_rate': round(prev_denial_rate, 2),
                        'reimb_rate': round(prev_reimb_rate, 2)
                    },
                    'changes': {
                        'claims': calc_change(current[0], previous[0]),
                        'claimed': calc_change(current[1], previous[1]),
                        'reimb': calc_change(current[2], previous[2]),
                        'denial_rate': round(current_denial_rate - prev_denial_rate, 2),
                        'reimb_rate': round(current_reimb_rate - prev_reimb_rate, 2)
                    }
                },
                'monthly': monthly_comparison
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in YoY comparison: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/export/<report_type>')
def api_export_report(report_type):
    """
    Phase 2.4: Export Reports to CSV
    Supported types: claims, denial, forecast, yoy
    """
    import csv
    import io

    try:
        fiscal_year = request.args.get('fiscal_year', type=int)
        start_date = _validate_date_param(request.args.get('start_date'))
        end_date = _validate_date_param(request.args.get('end_date'))

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == 'claims':
            # Export claims data
            where_clauses = ["dateadm IS NOT NULL"]
            params = []

            if fiscal_year:
                where_clause, where_params = get_fiscal_year_sql_filter_gregorian(fiscal_year, 'dateadm')
                where_clauses.append(where_clause)
                params.extend(where_params)

            if start_date:
                where_clauses.append("dateadm >= %s")
                params.append(start_date)
            if end_date:
                where_clauses.append("dateadm <= %s")
                params.append(end_date)

            query = """
                SELECT tran_id, rep_no, hn, an, pid, name, dateadm, datedsc,
                       service_type, main_fund, drg, rw, claim_drg, reimb_nhso, paid, error_code
                FROM claim_rep_opip_nhso_item
                WHERE """ + " AND ".join(where_clauses) + """
                ORDER BY dateadm DESC
                LIMIT 10000
            """
            cursor.execute(query, params)

            # Write header
            writer.writerow(['TRAN_ID', 'REP_NO', 'HN', 'AN', 'PID', 'ชื่อผู้ป่วย',
                           'วันที่รับ', 'วันที่จำหน่าย', 'ประเภทบริการ', 'กองทุน',
                           'DRG', 'RW', 'ยอดเบิก', 'Reimb NHSO', 'ยอดได้รับ', 'Error Code'])

            for row in cursor.fetchall():
                writer.writerow(row)

            filename = f"claims_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        elif report_type == 'denial':
            # Export denial analysis
            query = """
                SELECT error_code, COUNT(*) as count,
                       SUM(claim_drg) as total_amount,
                       ROUND(COUNT(*) * 100.0 / NULLIF(SUM(COUNT(*)) OVER(), 0), 2) as percentage
                FROM claim_rep_opip_nhso_item
                WHERE error_code IS NOT NULL AND error_code != ''
                GROUP BY error_code
                ORDER BY count DESC
            """
            cursor.execute(query)

            writer.writerow(['Error Code', 'จำนวน', 'ยอดเงิน', 'สัดส่วน (%)'])
            for row in cursor.fetchall():
                writer.writerow(row)

            filename = f"denial_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        elif report_type == 'monthly':
            # Export monthly summary
            year_month_col = sql_format_year_month('dateadm')
            query = f"""
                SELECT {year_month_col} as month,
                       COUNT(*) as claims,
                       SUM(claim_drg) as claimed,
                       SUM(reimb_nhso) as reimb,
                       SUM(paid) as paid,
                       COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as denials
                FROM claim_rep_opip_nhso_item
                WHERE dateadm IS NOT NULL
                GROUP BY {year_month_col}
                ORDER BY month DESC
            """
            cursor.execute(query)

            writer.writerow(['เดือน', 'จำนวน Claims', 'ยอดเบิก', 'Reimb', 'ยอดได้รับ', 'Denials'])
            for row in cursor.fetchall():
                writer.writerow(row)

            filename = f"monthly_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        else:
            return jsonify({'success': False, 'error': f'Unknown report type: {report_type}'}), 400

        cursor.close()
        conn.close()

        # Create response with CSV
        output.seek(0)
        response = Response(
            '\ufeff' + output.getvalue(),  # BOM for Excel UTF-8
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        return response

    except Exception as e:
        current_app.logger.error(f"Error exporting report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/analytics/benchmark')
def api_benchmark():
    """
    Benchmark Comparison API
    Compare hospital metrics with national/regional/level averages

    Parameters:
    - region: national, central, north, northeast, south
    - hospital_level: level_community, level_general, level_regional, level_university, level_private
    - fiscal_year: Buddhist Era year (e.g., 2568)
    - start_date: YYYY-MM-DD format
    - end_date: YYYY-MM-DD format
    """
    try:
        region = request.args.get('region', 'national')
        hospital_level = request.args.get('hospital_level', '')
        fiscal_year = request.args.get('fiscal_year', 2568, type=int)
        start_date = _validate_date_param(request.args.get('start_date'))
        end_date = _validate_date_param(request.args.get('end_date'))

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Build date filter for hospital metrics
        date_filter = "claim_drg IS NOT NULL AND claim_drg > 0"
        date_params = []
        if start_date:
            date_filter += " AND dateadm >= %s"
            date_params.append(start_date)
        if end_date:
            date_filter += " AND dateadm <= %s"
            date_params.append(end_date)

        # Get hospital's actual metrics
        query = f"""
            SELECT
                ROUND(SUM(COALESCE(reimb_nhso, 0)) * 100.0 / NULLIF(SUM(COALESCE(claim_drg, 0)), 0), 2) as reimb_rate,
                ROUND(COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' AND error_code != '0' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0), 2) as denial_rate,
                ROUND(AVG(CASE WHEN service_type = 'IP' THEN claim_drg END), 2) as avg_claim_ip,
                ROUND(AVG(CASE WHEN service_type = 'OP' THEN claim_drg END), 2) as avg_claim_op,
                ROUND(AVG(CASE WHEN rw IS NOT NULL THEN rw END), 4) as avg_rw,
                COUNT(*) as total_claims,
                MIN(dateadm) as min_date,
                MAX(dateadm) as max_date
            FROM claim_rep_opip_nhso_item
            WHERE {date_filter}
        """
        cursor.execute(query, date_params)
        hospital_row = cursor.fetchone()

        hospital_metrics = {
            'reimb_rate': float(hospital_row[0]) if hospital_row[0] else 0,
            'denial_rate': float(hospital_row[1]) if hospital_row[1] else 0,
            'avg_claim_ip': float(hospital_row[2]) if hospital_row[2] else 0,
            'avg_claim_op': float(hospital_row[3]) if hospital_row[3] else 0,
            'avg_rw': float(hospital_row[4]) if hospital_row[4] else 0,
            'total_claims': hospital_row[5] or 0,
            'date_range': {
                'min_date': hospital_row[6].strftime('%Y-%m-%d') if hospital_row[6] else None,
                'max_date': hospital_row[7].strftime('%Y-%m-%d') if hospital_row[7] else None
            }
        }

        # Determine which benchmark to use: hospital_level takes precedence over region
        benchmark_region = hospital_level if hospital_level else region

        # Get benchmark data
        cursor.execute("""
            SELECT metric_name, value, unit, description
            FROM analytics_benchmarks
            WHERE (region = %s OR region = 'national')
            AND fiscal_year = %s
            ORDER BY metric_name, CASE WHEN region = %s THEN 0 ELSE 1 END
        """, (benchmark_region, fiscal_year, benchmark_region))

        benchmarks = {}
        for row in cursor.fetchall():
            metric_name = row[0]
            if metric_name not in benchmarks:
                benchmarks[metric_name] = {
                    'value': float(row[1]),
                    'unit': row[2],
                    'description': row[3]
                }

        # Calculate comparison
        comparisons = []

        # Reimbursement Rate
        if 'reimb_rate' in benchmarks:
            benchmark_val = benchmarks['reimb_rate']['value']
            hospital_val = hospital_metrics['reimb_rate']
            diff = hospital_val - benchmark_val
            comparisons.append({
                'metric': 'Reimbursement Rate',
                'metric_th': 'อัตราได้รับชดเชย',
                'hospital_value': hospital_val,
                'benchmark_value': benchmark_val,
                'difference': round(diff, 2),
                'unit': '%',
                'status': 'above' if diff > 0 else 'below' if diff < 0 else 'equal',
                'is_good': diff >= 0
            })

        # Denial Rate (lower is better)
        if 'denial_rate' in benchmarks:
            benchmark_val = benchmarks['denial_rate']['value']
            hospital_val = hospital_metrics['denial_rate']
            diff = hospital_val - benchmark_val
            comparisons.append({
                'metric': 'Denial Rate',
                'metric_th': 'อัตราปฏิเสธเคลม',
                'hospital_value': hospital_val,
                'benchmark_value': benchmark_val,
                'difference': round(diff, 2),
                'unit': '%',
                'status': 'above' if diff > 0 else 'below' if diff < 0 else 'equal',
                'is_good': diff <= 0  # Lower is better for denial rate
            })

        # Average Claim IP
        if 'avg_claim_ip' in benchmarks:
            benchmark_val = benchmarks['avg_claim_ip']['value']
            hospital_val = hospital_metrics['avg_claim_ip']
            diff = hospital_val - benchmark_val
            diff_pct = (diff / benchmark_val * 100) if benchmark_val > 0 else 0
            comparisons.append({
                'metric': 'Avg Claim (IP)',
                'metric_th': 'ค่าเฉลี่ยเคลม IP',
                'hospital_value': hospital_val,
                'benchmark_value': benchmark_val,
                'difference': round(diff, 2),
                'difference_pct': round(diff_pct, 1),
                'unit': 'baht',
                'status': 'above' if diff > 0 else 'below' if diff < 0 else 'equal',
                'is_good': None  # Neutral - depends on context
            })

        # Average Claim OP
        if 'avg_claim_op' in benchmarks:
            benchmark_val = benchmarks['avg_claim_op']['value']
            hospital_val = hospital_metrics['avg_claim_op']
            diff = hospital_val - benchmark_val
            diff_pct = (diff / benchmark_val * 100) if benchmark_val > 0 else 0
            comparisons.append({
                'metric': 'Avg Claim (OP)',
                'metric_th': 'ค่าเฉลี่ยเคลม OP',
                'hospital_value': hospital_val,
                'benchmark_value': benchmark_val,
                'difference': round(diff, 2),
                'difference_pct': round(diff_pct, 1),
                'unit': 'baht',
                'status': 'above' if diff > 0 else 'below' if diff < 0 else 'equal',
                'is_good': None
            })

        # Average RW
        if 'avg_rw' in benchmarks:
            benchmark_val = benchmarks['avg_rw']['value']
            hospital_val = hospital_metrics['avg_rw']
            diff = hospital_val - benchmark_val
            comparisons.append({
                'metric': 'Average RW',
                'metric_th': 'ค่า RW เฉลี่ย',
                'hospital_value': hospital_val,
                'benchmark_value': benchmark_val,
                'difference': round(diff, 4),
                'unit': 'RW',
                'status': 'above' if diff > 0 else 'below' if diff < 0 else 'equal',
                'is_good': diff >= 0
            })

        # Get available regions (geographic)
        cursor.execute("""
            SELECT DISTINCT region FROM analytics_benchmarks
            WHERE region NOT LIKE 'level_%'
            ORDER BY region
        """)
        available_regions = [row[0] for row in cursor.fetchall()]

        # Get available hospital levels
        cursor.execute("""
            SELECT DISTINCT region FROM analytics_benchmarks
            WHERE region LIKE 'level_%'
            ORDER BY region
        """)
        available_levels = [row[0] for row in cursor.fetchall()]

        # Get available fiscal years
        cursor.execute("""
            SELECT DISTINCT fiscal_year FROM analytics_benchmarks ORDER BY fiscal_year DESC
        """)
        available_years = [row[0] for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        # Calculate overall score
        good_count = sum(1 for c in comparisons if c.get('is_good') == True)
        bad_count = sum(1 for c in comparisons if c.get('is_good') == False)
        total_scored = good_count + bad_count

        if total_scored > 0:
            score = round(good_count / total_scored * 100)
            if score >= 80:
                overall_status = 'excellent'
            elif score >= 60:
                overall_status = 'good'
            elif score >= 40:
                overall_status = 'fair'
            else:
                overall_status = 'needs_improvement'
        else:
            score = 0
            overall_status = 'unknown'

        return jsonify({
            'success': True,
            'data': {
                'hospital_metrics': hospital_metrics,
                'comparisons': comparisons,
                'overall_score': score,
                'overall_status': overall_status,
                'region': region,
                'hospital_level': hospital_level,
                'fiscal_year': fiscal_year,
                'date_filter': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'available_regions': available_regions,
                'available_levels': available_levels,
                'available_years': available_years
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in benchmark comparison: {e}")
        logger.error(safe_format_exception())
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/denial-risk')
def api_denial_risk():
    """
    Phase 3.1: Denial Risk Prediction
    Analyze claim characteristics to predict denial risk
    Uses historical error patterns to calculate risk scores
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get risk factors from historical data
        # 1. Error rate by service type
        cursor.execute("""
            SELECT
                service_type,
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as error_claims,
                ROUND(
                    COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0), 2
                ) as error_rate
            FROM claim_rep_opip_nhso_item
            WHERE service_type IS NOT NULL AND service_type != ''
            GROUP BY service_type
            HAVING COUNT(*) >= 10
            ORDER BY error_rate DESC
        """)
        service_type_risk = []
        for row in cursor.fetchall():
            service_type_risk.append({
                'service_type': row[0],
                'total_claims': row[1],
                'error_claims': row[2],
                'error_rate': float(row[3]) if row[3] else 0,
                'risk_level': 'high' if (row[3] or 0) > 10 else 'medium' if (row[3] or 0) > 5 else 'low'
            })

        # 2. Error rate by fund type
        cursor.execute("""
            SELECT
                main_fund,
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as error_claims,
                ROUND(
                    COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0), 2
                ) as error_rate
            FROM claim_rep_opip_nhso_item
            WHERE main_fund IS NOT NULL AND main_fund != ''
            GROUP BY main_fund
            HAVING COUNT(*) >= 5
            ORDER BY error_rate DESC
        """)
        fund_risk = []
        for row in cursor.fetchall():
            fund_risk.append({
                'fund': row[0],
                'total_claims': row[1],
                'error_claims': row[2],
                'error_rate': float(row[3]) if row[3] else 0,
                'risk_level': 'high' if (row[3] or 0) > 10 else 'medium' if (row[3] or 0) > 5 else 'low'
            })

        # 3. Error rate by DRG groups
        cursor.execute("""
            SELECT
                LEFT(drg, 3) as drg_group,
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as error_claims,
                ROUND(
                    COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0), 2
                ) as error_rate
            FROM claim_rep_opip_nhso_item
            WHERE drg IS NOT NULL AND drg != ''
            GROUP BY LEFT(drg, 3)
            HAVING COUNT(*) >= 5
            ORDER BY error_rate DESC
            LIMIT 20
        """)
        drg_risk = []
        for row in cursor.fetchall():
            drg_risk.append({
                'drg_group': row[0],
                'total_claims': row[1],
                'error_claims': row[2],
                'error_rate': float(row[3]) if row[3] else 0,
                'risk_level': 'high' if (row[3] or 0) > 10 else 'medium' if (row[3] or 0) > 5 else 'low'
            })

        # 4. Error rate by claim amount ranges
        claim_numeric = sql_coalesce_numeric('claim_drg', 0)
        cursor.execute(f"""
            SELECT
                CASE
                    WHEN {claim_numeric} < 1000 THEN 'Under 1,000'
                    WHEN {claim_numeric} < 5000 THEN '1,000-5,000'
                    WHEN {claim_numeric} < 10000 THEN '5,000-10,000'
                    WHEN {claim_numeric} < 50000 THEN '10,000-50,000'
                    ELSE 'Over 50,000'
                END as amount_range,
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as error_claims,
                ROUND(
                    COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0), 2
                ) as error_rate,
                CASE
                    WHEN {claim_numeric} < 1000 THEN 1
                    WHEN {claim_numeric} < 5000 THEN 2
                    WHEN {claim_numeric} < 10000 THEN 3
                    WHEN {claim_numeric} < 50000 THEN 4
                    ELSE 5
                END as sort_order
            FROM claim_rep_opip_nhso_item
            GROUP BY 1, 5
            ORDER BY sort_order
        """)
        amount_risk = []
        for row in cursor.fetchall():
            amount_risk.append({
                'amount_range': row[0],
                'total_claims': row[1],
                'error_claims': row[2],
                'error_rate': float(row[3]) if row[3] else 0,
                'risk_level': 'high' if (row[3] or 0) > 10 else 'medium' if (row[3] or 0) > 5 else 'low'
            })

        # 5. Overall risk summary
        cursor.execute("""
            SELECT
                COUNT(*) as total_claims,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as total_errors,
                ROUND(
                    COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                    NULLIF(COUNT(*), 0), 2
                ) as overall_error_rate
            FROM claim_rep_opip_nhso_item
        """)
        summary_row = cursor.fetchone()
        overall_summary = {
            'total_claims': summary_row[0],
            'total_errors': summary_row[1],
            'overall_error_rate': float(summary_row[2]) if summary_row[2] else 0
        }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'summary': overall_summary,
                'service_type_risk': service_type_risk,
                'fund_risk': fund_risk,
                'drg_risk': drg_risk,
                'amount_risk': amount_risk
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in denial risk analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/anomalies')
def api_anomalies():
    """
    Phase 3.2: Anomaly Detection
    Detect unusual claim amounts and patterns
    Uses statistical analysis to identify outliers
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        claim_numeric = sql_coalesce_numeric('claim_drg', 0)
        reimb_numeric = sql_coalesce_numeric('reimb_nhso', 0)

        # 1. Calculate statistical metrics for claim amounts
        if DB_TYPE == 'mysql':
            # MySQL: Calculate basic stats, then compute percentiles via subqueries
            cursor.execute(f"""
                SELECT
                    AVG({claim_numeric}) as mean_amount,
                    STDDEV({claim_numeric}) as std_amount,
                    MIN({claim_numeric}) as min_amount,
                    MAX({claim_numeric}) as max_amount,
                    COUNT(*) as total_count
                FROM claim_rep_opip_nhso_item
                WHERE claim_drg IS NOT NULL
            """)
            basic_stats = cursor.fetchone()
            total_count = basic_stats[4] if basic_stats[4] else 0

            # Compute percentiles using LIMIT/OFFSET for MySQL
            median = 0
            q1 = 0
            q3 = 0
            if total_count > 0:
                # Median (50th percentile)
                offset_50 = max(0, int(total_count * 0.5) - 1)
                cursor.execute(f"""
                    SELECT {claim_numeric}
                    FROM claim_rep_opip_nhso_item
                    WHERE claim_drg IS NOT NULL
                    ORDER BY claim_drg
                    LIMIT 1 OFFSET {offset_50}
                """)
                median_row = cursor.fetchone()
                median = float(median_row[0]) if median_row and median_row[0] else 0

                # Q1 (25th percentile)
                offset_25 = max(0, int(total_count * 0.25) - 1)
                cursor.execute(f"""
                    SELECT {claim_numeric}
                    FROM claim_rep_opip_nhso_item
                    WHERE claim_drg IS NOT NULL
                    ORDER BY claim_drg
                    LIMIT 1 OFFSET {offset_25}
                """)
                q1_row = cursor.fetchone()
                q1 = float(q1_row[0]) if q1_row and q1_row[0] else 0

                # Q3 (75th percentile)
                offset_75 = max(0, int(total_count * 0.75) - 1)
                cursor.execute(f"""
                    SELECT {claim_numeric}
                    FROM claim_rep_opip_nhso_item
                    WHERE claim_drg IS NOT NULL
                    ORDER BY claim_drg
                    LIMIT 1 OFFSET {offset_75}
                """)
                q3_row = cursor.fetchone()
                q3 = float(q3_row[0]) if q3_row and q3_row[0] else 0

            stats = {
                'mean': float(basic_stats[0]) if basic_stats[0] else 0,
                'median': median,
                'std': float(basic_stats[1]) if basic_stats[1] else 0,
                'min': float(basic_stats[2]) if basic_stats[2] else 0,
                'max': float(basic_stats[3]) if basic_stats[3] else 0,
                'q1': q1,
                'q3': q3
            }
        else:
            # PostgreSQL: Use PERCENTILE_CONT
            cursor.execute(f"""
                SELECT
                    AVG({claim_numeric}) as mean_amount,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {claim_numeric}) as median_amount,
                    STDDEV({claim_numeric}) as std_amount,
                    MIN({claim_numeric}) as min_amount,
                    MAX({claim_numeric}) as max_amount,
                    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {claim_numeric}) as q1,
                    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {claim_numeric}) as q3
                FROM claim_rep_opip_nhso_item
                WHERE claim_drg IS NOT NULL
            """)
            stats_row = cursor.fetchone()
            stats = {
                'mean': float(stats_row[0]) if stats_row[0] else 0,
                'median': float(stats_row[1]) if stats_row[1] else 0,
                'std': float(stats_row[2]) if stats_row[2] else 0,
                'min': float(stats_row[3]) if stats_row[3] else 0,
                'max': float(stats_row[4]) if stats_row[4] else 0,
                'q1': float(stats_row[5]) if stats_row[5] else 0,
                'q3': float(stats_row[6]) if stats_row[6] else 0
            }

        # Calculate IQR bounds for outliers
        iqr = stats['q3'] - stats['q1']
        lower_bound = stats['q1'] - (1.5 * iqr)
        upper_bound = stats['q3'] + (1.5 * iqr)

        # 2. Find high-value anomalies (claims above upper bound)
        cursor.execute(f"""
            SELECT
                tran_id, hn, name, dateadm, service_type, drg,
                claim_drg, reimb_nhso, error_code
            FROM claim_rep_opip_nhso_item
            WHERE {claim_numeric} > %s
            ORDER BY claim_drg DESC
            LIMIT 20
        """, (upper_bound,))
        high_value_anomalies = []
        for row in cursor.fetchall():
            high_value_anomalies.append({
                'tran_id': row[0],
                'hn': row[1],
                'name': row[2],
                'dateadm': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'service_type': row[4],
                'drg': row[5],
                'claim_drg': float(row[6]) if row[6] else 0,
                'reimb_nhso': float(row[7]) if row[7] else 0,
                'error_code': row[8],
                'anomaly_type': 'high_value',
                'deviation': round((float(row[6] or 0) - stats['mean']) / stats['std'], 2) if stats['std'] > 0 else 0
            })

        # 3. Find claims with large reimbursement variance
        cursor.execute(f"""
            SELECT
                tran_id, hn, name, dateadm, service_type, drg,
                claim_drg, reimb_nhso, paid,
                {claim_numeric} - {reimb_numeric} as variance
            FROM claim_rep_opip_nhso_item
            WHERE claim_drg IS NOT NULL
              AND reimb_nhso IS NOT NULL
              AND ABS({claim_numeric} - {reimb_numeric}) >
                  (SELECT AVG(ABS({claim_numeric} - {reimb_numeric})) * 3
                   FROM claim_rep_opip_nhso_item
                   WHERE claim_drg IS NOT NULL AND reimb_nhso IS NOT NULL)
            ORDER BY ABS({claim_numeric} - {reimb_numeric}) DESC
            LIMIT 20
        """)
        variance_anomalies = []
        for row in cursor.fetchall():
            variance_anomalies.append({
                'tran_id': row[0],
                'hn': row[1],
                'name': row[2],
                'dateadm': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'service_type': row[4],
                'drg': row[5],
                'claim_drg': float(row[6]) if row[6] else 0,
                'reimb_nhso': float(row[7]) if row[7] else 0,
                'paid': float(row[8]) if row[8] else 0,
                'variance': float(row[9]) if row[9] else 0,
                'anomaly_type': 'high_variance'
            })

        # 4. Find unusual RW (relative weight) values
        # Skip RW analysis if data has non-numeric values
        rw_anomalies = []
        rw_cast = sql_cast_numeric('rw')
        rw_regex = sql_regex_match('rw', '^[0-9]+\\.?[0-9]*$')
        try:
            cursor.execute(f"""
                SELECT
                    AVG({rw_cast}) as mean_rw,
                    STDDEV({rw_cast}) as std_rw
                FROM claim_rep_opip_nhso_item
                WHERE rw IS NOT NULL
                  AND rw <> ''
                  AND {rw_regex}
            """)
            rw_stats = cursor.fetchone()
            rw_mean = float(rw_stats[0]) if rw_stats[0] else 0
            rw_std = float(rw_stats[1]) if rw_stats[1] else 1

            if rw_mean > 0:
                cursor.execute(f"""
                    SELECT
                        tran_id, hn, name, dateadm, drg, rw, claim_drg
                    FROM claim_rep_opip_nhso_item
                    WHERE rw IS NOT NULL
                      AND rw <> ''
                      AND {rw_regex}
                      AND {rw_cast} > %s
                    ORDER BY {rw_cast} DESC
                    LIMIT 15
                """, (rw_mean + (2 * rw_std),))
                for row in cursor.fetchall():
                    rw_anomalies.append({
                        'tran_id': row[0],
                        'hn': row[1],
                        'name': row[2],
                        'dateadm': row[3].strftime('%Y-%m-%d') if row[3] else None,
                        'drg': row[4],
                        'rw': float(row[5]) if row[5] else 0,
                        'claim_drg': float(row[6]) if row[6] else 0,
                        'anomaly_type': 'high_rw'
                    })
        except Exception as rw_error:
            current_app.logger.warning(f"RW anomaly detection skipped: {rw_error}")
            conn.rollback()  # Reset transaction state

        # 5. Anomaly summary
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_claims,
                COUNT(CASE WHEN {claim_numeric} > %s THEN 1 END) as high_value_count,
                COUNT(CASE WHEN {claim_numeric} < %s THEN 1 END) as low_value_count
            FROM claim_rep_opip_nhso_item
        """, (upper_bound, lower_bound if lower_bound > 0 else 0))
        anomaly_summary = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'statistics': stats,
                'bounds': {
                    'lower': max(0, lower_bound),
                    'upper': upper_bound,
                    'iqr': iqr
                },
                'summary': {
                    'total_claims': anomaly_summary[0],
                    'high_value_anomalies': anomaly_summary[1],
                    'low_value_anomalies': anomaly_summary[2]
                },
                'high_value_claims': high_value_anomalies,
                'variance_anomalies': variance_anomalies,
                'rw_anomalies': rw_anomalies
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in anomaly detection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/opportunities')
def api_opportunities():
    """
    Phase 3.3: Revenue Opportunities
    Identify potential revenue recovery and optimization opportunities
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        claim_numeric = sql_coalesce_numeric('claim_drg', 0)
        paid_numeric = sql_coalesce_numeric('paid', 0)

        # 1. Under-reimbursed claims (claimed more than received)
        cursor.execute(f"""
            SELECT
                tran_id, hn, name, dateadm, service_type, drg,
                claim_drg, reimb_nhso, paid,
                {claim_numeric} - {paid_numeric} as potential_recovery,
                error_code
            FROM claim_rep_opip_nhso_item
            WHERE {claim_numeric} > {paid_numeric} + 100
              AND (error_code IS NULL OR error_code = '')
            ORDER BY {claim_numeric} - {paid_numeric} DESC
            LIMIT 30
        """)
        under_reimbursed = []
        for row in cursor.fetchall():
            under_reimbursed.append({
                'tran_id': row[0],
                'hn': row[1],
                'name': row[2],
                'dateadm': row[3].strftime('%Y-%m-%d') if row[3] else None,
                'service_type': row[4],
                'drg': row[5],
                'claim_drg': float(row[6]) if row[6] else 0,
                'reimb_nhso': float(row[7]) if row[7] else 0,
                'paid': float(row[8]) if row[8] else 0,
                'potential_recovery': float(row[9]) if row[9] else 0,
                'error_code': row[10]
            })

        # 2. Summary of potential recovery by fund
        cursor.execute(f"""
            SELECT
                main_fund,
                COUNT(*) as claims,
                SUM({claim_numeric} - {paid_numeric}) as total_gap,
                AVG({claim_numeric} - {paid_numeric}) as avg_gap
            FROM claim_rep_opip_nhso_item
            WHERE {claim_numeric} > {paid_numeric} + 100
              AND main_fund IS NOT NULL AND main_fund != ''
            GROUP BY main_fund
            ORDER BY total_gap DESC
        """)
        fund_gaps = []
        for row in cursor.fetchall():
            fund_gaps.append({
                'fund': row[0],
                'claims': row[1],
                'total_gap': float(row[2]) if row[2] else 0,
                'avg_gap': float(row[3]) if row[3] else 0
            })

        # 3. Claims with potential coding improvements (low RW vs high claim)
        coding_opportunities = []
        rw_cast = sql_cast_numeric('rw')
        rw_regex = sql_regex_match('rw', '^[0-9]+\\.?[0-9]*$')
        c_rw_cast = sql_cast_numeric('c.rw')
        c_rw_regex = sql_regex_match('c.rw', '^[0-9]+\\.?[0-9]*$')
        c_claim_numeric = sql_coalesce_numeric('c.claim_drg', 0)
        try:
            cursor.execute(f"""
                WITH rw_stats AS (
                    SELECT
                        LEFT(drg, 3) as drg_group,
                        AVG({rw_cast}) as avg_rw
                    FROM claim_rep_opip_nhso_item
                    WHERE drg IS NOT NULL
                      AND rw IS NOT NULL
                      AND rw <> ''
                      AND {rw_regex}
                    GROUP BY LEFT(drg, 3)
                )
                SELECT
                    c.tran_id, c.hn, c.name, c.dateadm, c.drg, c.rw,
                    c.claim_drg, r.avg_rw,
                    r.avg_rw - {c_rw_cast} as rw_gap
                FROM claim_rep_opip_nhso_item c
                JOIN rw_stats r ON LEFT(c.drg, 3) = r.drg_group
                WHERE c.rw IS NOT NULL
                  AND c.rw <> ''
                  AND {c_rw_regex}
                  AND {c_rw_cast} < r.avg_rw * 0.7
                  AND c.claim_drg IS NOT NULL
                  AND {c_claim_numeric} > 5000
                ORDER BY c.claim_drg DESC
                LIMIT 20
            """)
            for row in cursor.fetchall():
                coding_opportunities.append({
                    'tran_id': row[0],
                    'hn': row[1],
                    'name': row[2],
                    'dateadm': row[3].strftime('%Y-%m-%d') if row[3] else None,
                    'drg': row[4],
                    'rw': float(row[5]) if row[5] else 0,
                    'claim_drg': float(row[6]) if row[6] else 0,
                    'avg_rw_for_drg': round(float(row[7]), 3) if row[7] else 0,
                    'rw_gap': round(float(row[8]), 3) if row[8] else 0
                })
        except Exception as rw_error:
            current_app.logger.warning(f"Coding opportunities analysis skipped: {rw_error}")
            conn.rollback()  # Reset transaction state

        # 4. Error claims that could be resubmitted
        cursor.execute(f"""
            SELECT
                error_code,
                COUNT(*) as count,
                SUM({claim_numeric}) as total_value,
                AVG({claim_numeric}) as avg_value
            FROM claim_rep_opip_nhso_item
            WHERE error_code IS NOT NULL AND error_code != ''
            GROUP BY error_code
            ORDER BY total_value DESC
            LIMIT 15
        """)
        resubmit_opportunities = []
        for row in cursor.fetchall():
            resubmit_opportunities.append({
                'error_code': row[0],
                'count': row[1],
                'total_value': float(row[2]) if row[2] else 0,
                'avg_value': float(row[3]) if row[3] else 0
            })

        # 5. Overall opportunity summary
        cursor.execute(f"""
            SELECT
                COUNT(*) as total_claims,
                SUM({claim_numeric}) as total_claimed,
                SUM({paid_numeric}) as total_paid,
                SUM({claim_numeric}) - SUM({paid_numeric}) as total_gap,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as error_claims,
                SUM(CASE WHEN error_code IS NOT NULL AND error_code != ''
                    THEN {claim_numeric} ELSE 0 END) as error_claim_value
            FROM claim_rep_opip_nhso_item
        """)
        summary_row = cursor.fetchone()
        summary = {
            'total_claims': summary_row[0],
            'total_claimed': float(summary_row[1]) if summary_row[1] else 0,
            'total_paid': float(summary_row[2]) if summary_row[2] else 0,
            'total_gap': float(summary_row[3]) if summary_row[3] else 0,
            'reimbursement_rate': round(float(summary_row[2] or 0) / float(summary_row[1] or 1) * 100, 2),
            'error_claims': summary_row[4],
            'error_claim_value': float(summary_row[5]) if summary_row[5] else 0
        }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': {
                'summary': summary,
                'under_reimbursed': under_reimbursed,
                'fund_gaps': fund_gaps,
                'coding_opportunities': coding_opportunities,
                'resubmit_opportunities': resubmit_opportunities
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in revenue opportunities: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/insights')
def api_insights():
    """
    Phase 3.4: AI-Generated Insights
    Generate actionable recommendations based on data patterns
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        insights = []
        priority_score = 0

        # 1. Check overall denial rate trend
        cursor.execute("""
            SELECT
                """ + sql_format_year_month('dateadm') + """ as month,
                COUNT(*) as total,
                COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as errors,
                ROUND(COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                      NULLIF(COUNT(*), 0), 2) as error_rate
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
            GROUP BY """ + sql_format_year_month('dateadm') + """
            ORDER BY month DESC
            LIMIT 6
        """)
        monthly_rates = cursor.fetchall()
        if len(monthly_rates) >= 2:
            recent_rate = float(monthly_rates[0][3] or 0)
            prev_rate = float(monthly_rates[1][3] or 0)
            if recent_rate > prev_rate * 1.2:
                insights.append({
                    'type': 'warning',
                    'category': 'Denial Rate',
                    'title': 'อัตรา Denial เพิ่มขึ้น',
                    'description': f'อัตรา Denial เดือนล่าสุด ({recent_rate}%) เพิ่มขึ้นจากเดือนก่อน ({prev_rate}%) ควรตรวจสอบสาเหตุ',
                    'action': 'ตรวจสอบ Error Code ที่พบบ่อยและปรับปรุงกระบวนการ coding',
                    'priority': 'high',
                    'metric': {'current': recent_rate, 'previous': prev_rate}
                })
                priority_score += 30
            elif recent_rate < prev_rate * 0.8:
                insights.append({
                    'type': 'success',
                    'category': 'Denial Rate',
                    'title': 'อัตรา Denial ลดลง',
                    'description': f'อัตรา Denial เดือนล่าสุด ({recent_rate}%) ลดลงจากเดือนก่อน ({prev_rate}%)',
                    'action': 'รักษามาตรฐานการทำงานปัจจุบัน',
                    'priority': 'low',
                    'metric': {'current': recent_rate, 'previous': prev_rate}
                })

        # 2. Check for specific high-error service types
        cursor.execute("""
            SELECT service_type,
                   COUNT(*) as total,
                   ROUND(COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                         NULLIF(COUNT(*), 0), 2) as error_rate
            FROM claim_rep_opip_nhso_item
            WHERE service_type IS NOT NULL AND service_type != ''
            GROUP BY service_type
            HAVING COUNT(*) >= 20 AND
                   COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) * 100.0 /
                   NULLIF(COUNT(*), 0) > 15
            ORDER BY error_rate DESC
            LIMIT 3
        """)
        high_error_services = cursor.fetchall()
        for service in high_error_services:
            insights.append({
                'type': 'warning',
                'category': 'Service Type',
                'title': f'ประเภทบริการ {service[0]} มี Error สูง',
                'description': f'พบอัตรา Error {service[2]}% จาก {service[1]} claims',
                'action': f'ทบทวนกระบวนการบันทึกข้อมูลสำหรับบริการประเภท {service[0]}',
                'priority': 'medium',
                'metric': {'service_type': service[0], 'error_rate': float(service[2])}
            })
            priority_score += 15

        # 3. Check reimbursement rate
        cursor.execute("""
            SELECT
                SUM(COALESCE(claim_drg, 0)) as claimed,
                SUM(COALESCE(paid, 0)) as paid
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= NOW() - """ + sql_interval_months(3))
        reimb_row = cursor.fetchone()
        if reimb_row[0] and reimb_row[0] > 0:
            reimb_rate = float(reimb_row[1] or 0) / float(reimb_row[0]) * 100
            if reimb_rate < 85:
                insights.append({
                    'type': 'warning',
                    'category': 'Reimbursement',
                    'title': 'อัตราการชดเชยต่ำกว่าเป้าหมาย',
                    'description': f'อัตราการชดเชย 3 เดือนล่าสุดอยู่ที่ {reimb_rate:.1f}% ต่ำกว่าเป้าหมาย 85%',
                    'action': 'ตรวจสอบ claims ที่ยังไม่ได้รับการชดเชยและติดตามการ resubmit',
                    'priority': 'high',
                    'metric': {'rate': round(reimb_rate, 2), 'target': 85}
                })
                priority_score += 25
            elif reimb_rate >= 95:
                insights.append({
                    'type': 'success',
                    'category': 'Reimbursement',
                    'title': 'อัตราการชดเชยดีเยี่ยม',
                    'description': f'อัตราการชดเชย 3 เดือนล่าสุดอยู่ที่ {reimb_rate:.1f}%',
                    'action': 'รักษามาตรฐานการทำงาน',
                    'priority': 'low',
                    'metric': {'rate': round(reimb_rate, 2)}
                })

        # 4. Check for common error codes
        cursor.execute("""
            SELECT error_code, COUNT(*) as count,
                   SUM(COALESCE(claim_drg, 0)) as total_value
            FROM claim_rep_opip_nhso_item
            WHERE error_code IS NOT NULL AND error_code != ''
              AND dateadm >= NOW() - """ + sql_interval_months(3) + """
            GROUP BY error_code
            ORDER BY count DESC
            LIMIT 3
        """)
        common_errors = cursor.fetchall()
        if common_errors:
            top_error = common_errors[0]
            insights.append({
                'type': 'info',
                'category': 'Error Analysis',
                'title': f'Error Code {top_error[0]} พบบ่อยที่สุด',
                'description': f'พบ {top_error[1]} ครั้ง มูลค่ารวม {top_error[2]:,.0f} บาท',
                'action': 'ศึกษาสาเหตุของ Error Code นี้และหาแนวทางป้องกัน',
                'priority': 'medium',
                'metric': {'error_code': top_error[0], 'count': top_error[1], 'value': float(top_error[2] or 0)}
            })
            priority_score += 10

        # 5. Check for pending long-duration claims
        paid_numeric = sql_coalesce_numeric('paid', 0)
        cursor.execute(f"""
            SELECT COUNT(*)
            FROM claim_rep_opip_nhso_item
            WHERE dateadm < NOW() - {sql_interval_days(60)}
              AND (paid IS NULL OR {paid_numeric} = 0)
              AND (error_code IS NULL OR error_code = '')
        """)
        pending_count = cursor.fetchone()[0]
        if pending_count > 10:
            insights.append({
                'type': 'warning',
                'category': 'Pending Claims',
                'title': 'มี Claims ค้างนานเกิน 60 วัน',
                'description': f'พบ {pending_count} claims ที่ยังไม่ได้รับการชำระเกิน 60 วัน',
                'action': 'ติดตามสถานะกับ สปสช. และตรวจสอบว่ามีปัญหาเอกสารหรือไม่',
                'priority': 'medium',
                'metric': {'pending_count': pending_count}
            })
            priority_score += 15

        cursor.close()
        conn.close()

        # Sort insights by priority
        priority_order = {'high': 0, 'medium': 1, 'low': 2}
        insights.sort(key=lambda x: priority_order.get(x['priority'], 3))

        return jsonify({
            'success': True,
            'data': {
                'insights': insights,
                'total_insights': len(insights),
                'priority_score': min(100, priority_score),
                'health_status': 'critical' if priority_score >= 60 else 'warning' if priority_score >= 30 else 'good'
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error generating insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# ML Prediction Endpoints
# ============================================


@analytics_api_bp.route('/api/predictive/ml-info')
def api_ml_info():
    """Get ML model information and performance metrics"""
    try:
        from utils.ml.predictor import get_model_info
        info = get_model_info()
        return jsonify({'success': True, 'data': info})
    except Exception as e:
        current_app.logger.error(f"Error getting ML info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/ml-predict', methods=['POST'])
def api_ml_predict():
    """
    ML-based denial risk prediction for a single claim

    Request body:
    {
        "service_type": "IP",
        "drg": "A15",
        "main_fund": "UC",
        "main_inscl": "UCS",
        "ptype": "1",
        "error_code": "",
        "claim_amount": 5000,
        "rw": 1.5,
        "adjrw": 1.2
    }
    """
    try:
        from utils.ml.predictor import predict_denial_risk
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        result = predict_denial_risk(data)
        return jsonify({'success': True, 'data': result})

    except Exception as e:
        current_app.logger.error(f"Error in ML prediction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/ml-predict-batch', methods=['POST'])
def api_ml_predict_batch():
    """
    ML-based denial risk prediction for multiple claims

    Request body:
    {
        "claims": [
            {"service_type": "IP", "drg": "A15", ...},
            {"service_type": "OP", "drg": "B20", ...}
        ]
    }
    """
    try:
        from utils.ml.predictor import predict_denial_risk_batch
        data = request.get_json()

        if not data or 'claims' not in data:
            return jsonify({'success': False, 'error': 'No claims data provided'}), 400

        results = predict_denial_risk_batch(data['claims'])
        return jsonify({'success': True, 'data': results})

    except Exception as e:
        current_app.logger.error(f"Error in batch ML prediction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500



@analytics_api_bp.route('/api/predictive/ml-high-risk')
def api_ml_high_risk():
    """
    Get claims with highest predicted denial risk using ML model
    Returns top claims that need attention based on ML prediction
    """
    try:
        from utils.ml.predictor import get_predictor

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get recent claims without errors for prediction
        cursor.execute("""
            SELECT
                tran_id,
                COALESCE(service_type, 'UN') as service_type,
                COALESCE(error_code, '0') as error_code,
                COALESCE(drg, 'UNKNOWN') as drg,
                COALESCE(main_fund, 'UNKNOWN') as main_fund,
                COALESCE(main_inscl, 'UNKNOWN') as main_inscl,
                COALESCE(ptype, 'UNKNOWN') as ptype,
                COALESCE(claim_drg, 0) as claim_amount,
                COALESCE(rw, 0) as rw,
                COALESCE(adjrw_nhso, 0) as adjrw,
                hn, name
            FROM claim_rep_opip_nhso_item
            WHERE claim_drg IS NOT NULL AND claim_drg > 0
            AND (error_code IS NULL OR error_code = '' OR error_code = '0')
            ORDER BY claim_drg DESC
            LIMIT 100
        """)

        claims = []
        for row in cursor.fetchall():
            claims.append({
                'tran_id': row[0],
                'service_type': row[1],
                'error_code': row[2],
                'drg': row[3],
                'main_fund': row[4],
                'main_inscl': row[5],
                'ptype': row[6],
                'claim_amount': float(row[7]) if row[7] else 0,
                'rw': float(row[8]) if row[8] else 0,
                'adjrw': float(row[9]) if row[9] else 0,
                'hn': row[10],
                'name': row[11]
            })

        cursor.close()
        conn.close()

        # Predict denial risk for each claim
        predictor = get_predictor()
        high_risk_claims = []

        for claim in claims:
            prediction = predictor.predict(claim)
            if prediction.get('risk_score', 0) >= 0.3:  # Medium or high risk
                high_risk_claims.append({
                    'tran_id': claim['tran_id'],
                    'hn': claim['hn'],
                    'name': claim['name'],
                    'service_type': claim['service_type'],
                    'drg': claim['drg'],
                    'main_fund': claim['main_fund'],
                    'claim_amount': claim['claim_amount'],
                    'risk_score': prediction['risk_score'],
                    'risk_level': prediction['risk_level'],
                    'confidence': prediction['confidence'],
                    'factors': prediction.get('factors', [])
                })

        # Sort by risk score descending
        high_risk_claims.sort(key=lambda x: x['risk_score'], reverse=True)

        return jsonify({
            'success': True,
            'data': {
                'high_risk_claims': high_risk_claims[:20],  # Top 20
                'total_analyzed': len(claims),
                'high_risk_count': len(high_risk_claims),
                'model_info': predictor.get_model_info()
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error in ML high risk prediction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Reconciliation Routes
# ============================================

def calculate_performance_metrics(summary, monthly_data):
    """
    Calculate Claims Performance Metrics
    Returns dict with:
    - payment_accuracy: % of months with matched amounts
    - claim_to_payment_ratio: SMT/REP amount ratio
    - underpayment_rate: % of months underpaid
    - pending_rate: % of months pending payment
    - avg_difference: Average difference per claim
    - top_month: Month with highest claim amount
    - matched_months: Count of matched months
    - underpaid_months: Count of underpaid months
    - pending_months: Count of pending months
    - total_months: Total months with data
    - data_quality: Data quality metrics
    """
    if not summary or not monthly_data:
        return {
            'payment_accuracy': 0,
            'claim_to_payment_ratio': 0,
            'underpayment_rate': 0,
            'pending_rate': 0,
            'avg_difference': 0,
            'top_month': None,
            'matched_months': 0,
            'underpaid_months': 0,
            'pending_months': 0,
            'total_months': 0,
            'data_quality': {
                'coverage_rate': 0,
                'alert_level': 'unknown',
                'missing_amount': 0,
                'expected_claims': 0,
                'actual_claims': 0,
                'missing_claims': 0,
                'avg_claim_amount': 0
            }
        }

    total_months = len(monthly_data)
    matched_months = 0
    underpaid_months = 0
    pending_months = 0
    top_month = None
    max_claim_total = 0

    for month in monthly_data:
        has_rep = month.get('has_rep_data', False)
        has_smt = month.get('has_smt_data', False)
        difference = month.get('difference', 0)
        claim_total = month.get('claim_total', 0)

        # Count matched months (difference < 1% of claim total)
        if has_rep and has_smt and claim_total > 0:
            diff_percent = abs(difference / claim_total)
            if diff_percent < 0.01:  # Less than 1%
                matched_months += 1

        # Count underpaid months
        if has_rep and has_smt and difference < 0:
            underpaid_months += 1

        # Count pending months (has REP but no SMT)
        if has_rep and not has_smt:
            pending_months += 1

        # Find top month
        if has_rep and claim_total > max_claim_total:
            max_claim_total = claim_total
            top_month = month

    # Calculate ratios
    payment_accuracy = (matched_months / total_months * 100) if total_months > 0 else 0
    underpayment_rate = (underpaid_months / total_months * 100) if total_months > 0 else 0
    pending_rate = (pending_months / total_months * 100) if total_months > 0 else 0

    rep_total = summary.get('rep', {}).get('total_amount', 0)
    smt_total = summary.get('smt', {}).get('total_amount', 0)
    total_claims = summary.get('rep', {}).get('total_claims', 0)

    claim_to_payment_ratio = (smt_total / rep_total * 100) if rep_total > 0 else 0
    avg_difference = ((smt_total - rep_total) / total_claims) if total_claims > 0 else 0

    # Calculate Data Quality Metrics
    # Coverage Rate: REP / SMT (%)
    coverage_rate = (rep_total / smt_total * 100) if smt_total > 0 else 0

    # Determine alert level based on coverage
    if coverage_rate < 20:
        alert_level = 'critical'  # Red - Very low coverage
    elif coverage_rate < 50:
        alert_level = 'warning'   # Yellow - Low coverage
    elif coverage_rate < 80:
        alert_level = 'caution'   # Orange - Moderate coverage
    else:
        alert_level = 'good'      # Green - Good coverage

    # Estimate missing claims
    avg_claim_amount = rep_total / total_claims if total_claims > 0 else 0
    expected_claims = int(smt_total / avg_claim_amount) if avg_claim_amount > 0 else 0
    missing_claims = max(0, expected_claims - total_claims)
    missing_amount = smt_total - rep_total if smt_total > rep_total else 0

    data_quality = {
        'coverage_rate': coverage_rate,
        'alert_level': alert_level,
        'missing_amount': missing_amount,
        'expected_claims': expected_claims,
        'actual_claims': total_claims,
        'missing_claims': missing_claims,
        'avg_claim_amount': avg_claim_amount
    }

    return {
        'payment_accuracy': payment_accuracy,
        'claim_to_payment_ratio': claim_to_payment_ratio,
        'underpayment_rate': underpayment_rate,
        'pending_rate': pending_rate,
        'avg_difference': avg_difference,
        'top_month': top_month,
        'matched_months': matched_months,
        'underpaid_months': underpaid_months,
        'pending_months': pending_months,
        'total_months': total_months,
        'data_quality': data_quality
    }



