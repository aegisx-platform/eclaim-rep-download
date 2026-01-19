"""
REP Data Source API Routes

This blueprint handles all REP (E-Claim Reimbursement) data source specific endpoints:
- File type statistics
- REP records/claims data
- Database clearing
- Monthly reconciliation
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
import humanize
from collections import defaultdict
import re
from config.database import DB_TYPE
from config.db_pool import get_connection as get_pooled_connection

# Create blueprint
rep_api_bp = Blueprint('rep_api', __name__)


def get_db_connection():
    """Get database connection from pool"""
    try:
        conn = get_pooled_connection()
        if conn is None:
            current_app.logger.error("Failed to get connection from pool")
        return conn
    except Exception as e:
        current_app.logger.error(f"Database connection error: {e}")
        return None


@rep_api_bp.route('/api/rep/file-type-stats')
def get_file_type_stats():
    """Get file statistics grouped by file type"""
    try:
        from utils import FileManager
        from utils.history_manager_db import HistoryManagerDB

        # Get file manager instance
        file_manager = FileManager()

        # Get all files from downloads directory
        all_files = file_manager.history_manager.get_all_downloads()

        # Get import status from database
        import_status_map = {}
        try:
            with get_db_connection() as conn:
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT filename, status FROM eclaim_imported_files")
                    for row in cursor.fetchall():
                        import_status_map[row[0]] = row[1]
                    cursor.close()
        except Exception as e:
            current_app.logger.warning(f"Could not get import status: {e}")

        # File type definitions with descriptions
        file_type_info = {
            'OP': {'name': 'OP', 'description': 'ผู้ป่วยนอก (Outpatient)', 'category': 'ucs', 'icon': '🏥'},
            'IP': {'name': 'IP', 'description': 'ผู้ป่วยใน (Inpatient)', 'category': 'ucs', 'icon': '🛏️'},
            'OPLGO': {'name': 'OP-LGO', 'description': 'ผู้ป่วยนอก อปท.', 'category': 'lgo', 'icon': '🏛️'},
            'IPLGO': {'name': 'IP-LGO', 'description': 'ผู้ป่วยใน อปท.', 'category': 'lgo', 'icon': '🏛️'},
            'OPSSS': {'name': 'OP-SSS', 'description': 'ผู้ป่วยนอก ประกันสังคม', 'category': 'sss', 'icon': '👷'},
            'IPSSS': {'name': 'IP-SSS', 'description': 'ผู้ป่วยใน ประกันสังคม', 'category': 'sss', 'icon': '👷'},
            'ORF': {'name': 'ORF', 'description': 'Outpatient Referral', 'category': 'special', 'icon': '🔄'},
            'IP_APPEAL': {'name': 'IP Appeal', 'description': 'อุทธรณ์ผู้ป่วยใน', 'category': 'appeal', 'icon': '📝'},
            'IP_APPEAL_NHSO': {'name': 'IP Appeal NHSO', 'description': 'อุทธรณ์ ผป.ใน (ฝั่ง สปสช.)', 'category': 'appeal', 'icon': '📝'},
            'OP_APPEAL': {'name': 'OP Appeal', 'description': 'อุทธรณ์ผู้ป่วยนอก', 'category': 'appeal', 'icon': '📋'},
            'OP_APPEAL_CD': {'name': 'OP Appeal CD', 'description': 'อุทธรณ์ ผป.นอก (โรคเรื้อรัง)', 'category': 'appeal', 'icon': '📋'},
        }

        # Parse file types from filenames
        type_stats = defaultdict(lambda: {'count': 0, 'imported': 0, 'pending': 0, 'size': 0})
        pattern = re.compile(r'eclaim_\d+_([A-Z_]+)_\d{8}_\d+\.xls')

        for file_info in all_files:
            filename = file_info.get('filename', '')
            match = pattern.match(filename)
            if match:
                file_type = match.group(1)
                type_stats[file_type]['count'] += 1
                type_stats[file_type]['size'] += file_info.get('size', 0)

                # Check import status
                status = import_status_map.get(filename, 'pending')
                if status == 'completed':
                    type_stats[file_type]['imported'] += 1
                else:
                    type_stats[file_type]['pending'] += 1

        # Build response with descriptions
        result = []
        for file_type, stats in sorted(type_stats.items(), key=lambda x: x[1]['count'], reverse=True):
            info = file_type_info.get(file_type, {
                'name': file_type,
                'description': f'Unknown type: {file_type}',
                'category': 'unknown',
                'icon': '📄'
            })
            result.append({
                'type': file_type,
                'name': info['name'],
                'description': info['description'],
                'category': info['category'],
                'icon': info['icon'],
                'count': stats['count'],
                'imported': stats['imported'],
                'pending': stats['pending'],
                'size': stats['size'],
                'size_formatted': humanize.naturalsize(stats['size'])
            })

        return jsonify({
            'success': True,
            'file_types': result,
            'total_types': len(result)
        })

    except Exception as e:
        current_app.logger.error(f"Error getting file type stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@rep_api_bp.route('/api/rep/records')
def get_rep_records():
    """Get REP database records with reconciliation status"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit

        view_mode = request.args.get('view_mode', 'rep')  # 'rep' or 'tran'
        fiscal_year = request.args.get('fiscal_year', '')
        rep_no = request.args.get('rep_no', '')
        tran_id = request.args.get('tran_id', '')
        status = request.args.get('status', '')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build WHERE clause
        where_clauses = []
        params = []

        if fiscal_year:
            # Fiscal year filter based on dateadm (admission date)
            # FY 2569 = Oct 2568 to Sep 2569 in Thai calendar = Oct 2025 to Sep 2026 in Gregorian
            fy = int(fiscal_year)
            start_date = f"{fy - 544}-10-01"  # Convert BE to CE: 2569-544=2025
            end_date = f"{fy - 543}-09-30"
            where_clauses.append("c.dateadm BETWEEN %s AND %s")
            params.extend([start_date, end_date])

        if rep_no:
            where_clauses.append("c.rep_no LIKE %s")
            params.append(f"%{rep_no}%")

        if tran_id:
            where_clauses.append("c.tran_id LIKE %s")
            params.append(f"%{tran_id}%")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        if view_mode == 'rep':
            # Group by REP No
            count_sql = f"""
                SELECT COUNT(DISTINCT c.rep_no)
                FROM claim_rep_opip_nhso_item c
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            query = f"""
                SELECT
                    c.rep_no,
                    COUNT(*) as count,
                    SUM(COALESCE(c.reimb_nhso, 0)) as rep_amount,
                    (
                        SELECT SUM(COALESCE(s.paid_after_deduction, 0))
                        FROM stm_claim_item s
                        WHERE s.rep_no = c.rep_no
                    ) as stm_amount,
                    CASE
                        WHEN (SELECT COUNT(*) FROM stm_claim_item s WHERE s.rep_no = c.rep_no) = 0 THEN 'rep_only'
                        WHEN ABS(SUM(COALESCE(c.reimb_nhso, 0)) - COALESCE((SELECT SUM(COALESCE(s.paid_after_deduction, 0)) FROM stm_claim_item s WHERE s.rep_no = c.rep_no), 0)) < 1 THEN 'matched'
                        ELSE 'diff_amount'
                    END as status
                FROM claim_rep_opip_nhso_item c
                WHERE {where_sql}
                GROUP BY c.rep_no
                ORDER BY c.rep_no DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [limit, offset])
        else:
            # Individual transactions
            count_sql = f"""
                SELECT COUNT(*)
                FROM claim_rep_opip_nhso_item c
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            query = f"""
                SELECT
                    c.tran_id,
                    c.rep_no,
                    c.hn,
                    COALESCE(c.reimb_nhso, 0) as rep_amount,
                    (
                        SELECT COALESCE(s.paid_after_deduction, 0)
                        FROM stm_claim_item s
                        WHERE s.tran_id = c.tran_id
                        LIMIT 1
                    ) as stm_amount,
                    CASE
                        WHEN NOT EXISTS (SELECT 1 FROM stm_claim_item s WHERE s.tran_id = c.tran_id) THEN 'rep_only'
                        WHEN ABS(COALESCE(c.reimb_nhso, 0) - COALESCE((SELECT s.paid_after_deduction FROM stm_claim_item s WHERE s.tran_id = c.tran_id LIMIT 1), 0)) < 1 THEN 'matched'
                        ELSE 'diff_amount'
                    END as status
                FROM claim_rep_opip_nhso_item c
                WHERE {where_sql}
                ORDER BY c.rep_no DESC, c.tran_id
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [limit, offset])

        columns = [desc[0] for desc in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Convert Decimal to float for JSON serialization
        for rec in records:
            for key in ['rep_amount', 'stm_amount', 'count']:
                if key in rec and rec[key] is not None:
                    rec[key] = float(rec[key])

        # Apply status filter after fetch (for complex status calculation)
        if status:
            records = [r for r in records if r.get('status') == status]

        # Get stats - count by checking if STM exists
        stats_sql = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM stm_claim_item s
                    WHERE s.tran_id = c.tran_id
                    AND ABS(COALESCE(s.paid_after_deduction, 0) - COALESCE(c.reimb_nhso, 0)) < 1
                ) THEN 1 END) as matched,
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM stm_claim_item s
                    WHERE s.tran_id = c.tran_id
                    AND ABS(COALESCE(s.paid_after_deduction, 0) - COALESCE(c.reimb_nhso, 0)) >= 1
                ) THEN 1 END) as diff_amount
            FROM claim_rep_opip_nhso_item c
        """
        cursor.execute(stats_sql)
        stats_row = cursor.fetchone()
        total_all = stats_row[0] or 0
        matched = stats_row[1] or 0
        diff_amount = stats_row[2] or 0
        rep_only = total_all - matched - diff_amount

        stats = {
            'total': total_all,
            'matched': matched,
            'diff_amount': diff_amount,
            'rep_only': rep_only
        }

        cursor.close()
        conn.close()

        total_pages = (total + limit - 1) // limit

        return jsonify({
            'success': True,
            'records': records,
            'stats': stats,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total,
                'total_pages': total_pages
            }
        })

    except Exception as e:
        current_app.logger.error(f"Error fetching REP records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@rep_api_bp.route('/api/rep/clear-database', methods=['POST'])
@login_required
def clear_rep_database():
    """Clear all REP records from database (keep files)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete REP records
        cursor.execute("DELETE FROM claim_rep_opip_nhso_item")
        cursor.execute("DELETE FROM claim_rep_orf_nhso_item")
        cursor.execute("DELETE FROM eclaim_imported_files")

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'REP database cleared successfully'
        })

    except Exception as e:
        current_app.logger.error(f"Error clearing REP database: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@rep_api_bp.route('/api/reconciliation/rep-monthly')
def api_rep_monthly():
    """Get REP monthly summary by fund"""
    from utils.reconciliation import ReconciliationReport
    from utils.settings_manager import SettingsManager

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        settings_manager = SettingsManager()
        report = ReconciliationReport(conn, settings_manager.get_hospital_code())
        data = report.get_rep_monthly_summary()
        conn.close()

        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
