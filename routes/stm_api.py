"""
STM Data Source API Routes

This blueprint handles all STM (Statement) data source specific endpoints:
- STM file downloads
- Download history
- Statistics and reconciliation
- Database management
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
import humanize
from pathlib import Path
from datetime import datetime
import subprocess
import threading
import re
from config.db_pool import get_connection as get_pooled_connection

# Create blueprint
stm_api_bp = Blueprint('stm_api', __name__)


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


@stm_api_bp.route('/api/stm/download', methods=['POST'])
@login_required
def trigger_stm_download():
    """Trigger STM (Statement) download with optional auto-import"""
    try:
        from utils.job_history_manager import job_history_manager

        data = request.get_json()

        year = data.get('year')
        month = data.get('month')  # Optional
        scheme = data.get('scheme', 'ucs')
        person_type = data.get('person_type', 'all')
        auto_import = data.get('auto_import', False)

        # Validate inputs
        if not year:
            return jsonify({'success': False, 'error': 'Year is required'}), 400

        year = int(year)

        # Validate scheme
        valid_schemes = ['ucs', 'ofc', 'sss', 'lgo']
        if scheme not in valid_schemes:
            return jsonify({'success': False, 'error': f'Invalid scheme. Valid: {valid_schemes}'}), 400

        # Validate person_type
        valid_types = ['ip', 'op', 'all']
        if person_type not in valid_types:
            return jsonify({'success': False, 'error': f'Invalid person_type. Valid: {valid_types}'}), 400

        # Start STM download in background
        def run_stm_download():
            # Start job tracking
            job_id = None
            try:
                job_id = job_history_manager.start_job(
                    job_type='download',
                    job_subtype='statement',
                    parameters={
                        'year': year,
                        'month': month,
                        'scheme': scheme,
                        'person_type': person_type,
                        'auto_import': auto_import
                    },
                    triggered_by='manual'
                )
            except Exception as e:
                current_app.logger.warning(f"Could not start job tracking: {e}")

            cmd = ['python3', 'stm_downloader_http.py', '--year', str(year), '--scheme', scheme, '--type', person_type]
            if month:
                cmd.extend(['--month', str(int(month))])

            log_file = Path('logs') / f"stm_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            log_file.parent.mkdir(exist_ok=True)

            try:
                with open(log_file, 'w') as f:
                    result = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)

                # Auto-import if enabled
                import_results = None
                if auto_import:
                    import_log_file = Path('logs') / f"stm_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
                    with open(import_log_file, 'w') as f:
                        subprocess.run(['python3', 'stm_import.py', 'downloads/stm/'], stdout=f, stderr=subprocess.STDOUT)

                # Complete job
                if job_id:
                    try:
                        job_history_manager.complete_job(
                            job_id=job_id,
                            status='completed',
                            results={
                                'scheme': scheme,
                                'year': year,
                                'month': month,
                                'person_type': person_type,
                                'auto_import': auto_import
                            }
                        )
                    except Exception as e:
                        current_app.logger.warning(f"Could not complete job tracking: {e}")

            except Exception as e:
                if job_id:
                    try:
                        job_history_manager.complete_job(
                            job_id=job_id,
                            status='failed',
                            error_message=str(e)
                        )
                    except Exception:
                        pass
                raise

        thread = threading.Thread(target=run_stm_download)
        thread.start()

        return jsonify({
            'success': True,
            'message': f'STM download started for {scheme.upper()} year {year}' + (' with auto-import' if auto_import else '')
        })

    except Exception as e:
        current_app.logger.error(f"STM download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@stm_api_bp.route('/api/stm/history')
@login_required
def get_stm_history():
    """Get STM download history from database"""
    try:
        from utils.download_history_db import DownloadHistoryDB

        db = DownloadHistoryDB()
        db.connect()

        # Get recent downloads (last 50)
        downloads = db.get_recent_downloads('stm', limit=50)
        stats = db.get_statistics('stm')

        db.disconnect()

        return jsonify({
            'success': True,
            'downloads': downloads,
            'total': stats.get('total_downloads', 0),
            'last_download': downloads[0]['downloaded_at'] if downloads else None
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@stm_api_bp.route('/api/stm/stats')
@login_required
def get_stm_stats():
    """Get Statement files statistics with optional filtering"""
    # Get filter params
    fiscal_year = request.args.get('fiscal_year', type=int)
    start_month = request.args.get('start_month', type=int)
    end_month = request.args.get('end_month', type=int)
    filter_status = request.args.get('status', '').strip().lower()

    # Calculate start/end year from fiscal year
    start_year = None
    end_year = None
    if fiscal_year:
        if start_month and start_month >= 10:
            start_year = fiscal_year - 1
        else:
            start_year = fiscal_year
        if end_month and end_month <= 9:
            end_year = fiscal_year
        else:
            end_year = fiscal_year - 1

    try:
        download_dir = Path('downloads/stm')
        stm_files = []
        total_size = 0
        imported_count = 0
        pending_count = 0

        # Get imported file list from database
        imported_filenames = set()
        import_info = {}
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """SELECT filename, status, imported_records, total_records,
                          import_completed_at, file_type, scheme
                   FROM stm_imported_files"""
            )
            for row in cursor.fetchall():
                imported_filenames.add(row[0])
                import_info[row[0]] = {
                    'status': row[1],
                    'imported_records': row[2],
                    'total_records': row[3],
                    'import_completed_at': row[4].isoformat() if row[4] else None,
                    'file_type': row[5],
                    'scheme': row[6]
                }
            cursor.close()
            conn.close()
        except Exception as e:
            current_app.logger.warning(f"Could not fetch STM import status: {e}")

        # Helper to convert month/year to comparable number
        def date_to_num(m, y):
            return y * 12 + m

        if download_dir.exists():
            for f in download_dir.glob('STM_*.xls'):
                # Parse date from filename: STM_10670_OPUCS256812_02.xls
                # 256812 = year 2568, month 12
                file_year = None
                file_month = None
                match = re.search(r'(\d{4})(\d{2})_\d+\.xls$', f.name)
                if match:
                    file_year = int(match.group(1))
                    file_month = int(match.group(2))

                # Apply date filter
                if fiscal_year and file_year and file_month:
                    file_date_num = date_to_num(file_month, file_year)
                    if start_month and start_year:
                        start_num = date_to_num(start_month, start_year)
                        if file_date_num < start_num:
                            continue
                    if end_month and end_year:
                        end_num = date_to_num(end_month, end_year)
                        if file_date_num > end_num:
                            continue

                stat = f.stat()
                file_size = stat.st_size

                is_imported = f.name in imported_filenames and import_info.get(f.name, {}).get('status') == 'completed'

                # Apply status filter
                if filter_status:
                    if filter_status == 'imported' and not is_imported:
                        continue
                    if filter_status == 'pending' and is_imported:
                        continue

                total_size += file_size

                if is_imported:
                    imported_count += 1
                else:
                    pending_count += 1

                file_info = {
                    'filename': f.name,
                    'size': file_size,
                    'size_formatted': humanize.naturalsize(file_size),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    'is_imported': is_imported,
                    'file_year': file_year,
                    'file_month': file_month
                }

                # Add import details if available
                if f.name in import_info:
                    file_info.update(import_info[f.name])

                stm_files.append(file_info)

        # Sort by modified date desc
        stm_files.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({
            'success': True,
            'total_files': len(stm_files),
            'imported_count': imported_count,
            'pending_count': pending_count,
            'total_size': humanize.naturalsize(total_size),
            'total_size_bytes': total_size,
            'files': stm_files[:100]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@stm_api_bp.route('/api/stm/clear', methods=['POST'])
@login_required
def clear_stm_files():
    """Clear all Statement files"""
    try:
        download_dir = Path('downloads/stm')
        deleted_count = 0

        # Delete all STM import records first
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stm_imported_files")
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            current_app.logger.warning(f"Could not clear STM import records: {e}")

        # Delete files
        for f in download_dir.glob('STM_*.xls'):
            f.unlink()
            deleted_count += 1

        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} Statement files'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@stm_api_bp.route('/api/stm/records')
@login_required
def get_stm_records():
    """Get Statement database records with reconciliation status using optimized view"""
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit

        view_mode = request.args.get('view_mode', 'rep')  # 'rep' or 'tran'
        fiscal_year = request.args.get('fiscal_year', '')
        rep_no = request.args.get('rep_no', '')
        status = request.args.get('status', '')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build WHERE clause using the v_stm_rep_reconciliation view
        where_clauses = []
        params = []

        if fiscal_year:
            # Fiscal year filter
            fy = int(fiscal_year)
            where_clauses.append("""
                ((statement_year = %s AND statement_month >= 10)
                 OR (statement_year = %s AND statement_month <= 9))
            """)
            params.extend([fy - 1, fy])

        if rep_no:
            where_clauses.append("rep_repno LIKE %s")
            params.append(f"%{rep_no}%")

        if status:
            where_clauses.append("reconcile_status = %s")
            params.append(status)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        if view_mode == 'rep':
            # Group by REP No - use aggregated query on the view
            count_sql = f"""
                SELECT COUNT(DISTINCT rep_repno)
                FROM v_stm_rep_reconciliation
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            query = f"""
                SELECT
                    rep_repno as rep_no,
                    COUNT(*) as count,
                    SUM(stm_compensation) as stm_amount,
                    SUM(rep_reimb_nhso) as rep_amount,
                    CASE
                        WHEN SUM(CASE WHEN reconcile_status = 'matched' THEN 1 ELSE 0 END) = COUNT(*) THEN 'matched'
                        WHEN SUM(CASE WHEN reconcile_status IN ('amount_diff', 'diff_amount') THEN 1 ELSE 0 END) > 0 THEN 'diff_amount'
                        ELSE 'stm_only'
                    END as status
                FROM v_stm_rep_reconciliation
                WHERE {where_sql}
                GROUP BY rep_repno
                ORDER BY rep_repno DESC
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [limit, offset])
        else:
            # Individual transactions from view
            count_sql = f"""
                SELECT COUNT(*)
                FROM v_stm_rep_reconciliation
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            query = f"""
                SELECT
                    tran_id,
                    rep_repno as rep_no,
                    patient_name,
                    hn,
                    stm_compensation as stm_amount,
                    rep_reimb_nhso as rep_amount,
                    reconcile_status as status
                FROM v_stm_rep_reconciliation
                WHERE {where_sql}
                ORDER BY rep_repno DESC, tran_id
                LIMIT %s OFFSET %s
            """
            cursor.execute(query, params + [limit, offset])

        columns = [desc[0] for desc in cursor.description]
        records = [dict(zip(columns, row)) for row in cursor.fetchall()]

        # Convert Decimal to float for JSON serialization
        for rec in records:
            for key in ['stm_amount', 'rep_amount', 'count']:
                if key in rec and rec[key] is not None:
                    rec[key] = float(rec[key])

        # Get stats from view (much faster than correlated subquery)
        stats_sql = """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN reconcile_status = 'matched' THEN 1 ELSE 0 END) as matched,
                SUM(CASE WHEN reconcile_status IN ('amount_diff', 'diff_amount') THEN 1 ELSE 0 END) as diff_amount,
                SUM(CASE WHEN reconcile_status = 'stm_only' OR reconcile_status IS NULL THEN 1 ELSE 0 END) as stm_only
            FROM v_stm_rep_reconciliation
        """
        cursor.execute(stats_sql)
        stats_row = cursor.fetchone()
        stats = {
            'total': int(stats_row[0] or 0),
            'matched': int(stats_row[1] or 0),
            'diff_amount': int(stats_row[2] or 0),
            'stm_only': int(stats_row[3] or 0)
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
        current_app.logger.error(f"Error fetching STM records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@stm_api_bp.route('/api/stm/clear-database', methods=['POST'])
@login_required
def clear_stm_database():
    """Clear all Statement records from database (keep files)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete claim items first (foreign key constraint)
        cursor.execute("DELETE FROM stm_claim_item")
        cursor.execute("DELETE FROM stm_rep_summary")
        cursor.execute("DELETE FROM stm_receivable_summary")
        cursor.execute("DELETE FROM stm_imported_files")

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'Statement database cleared successfully'
        })

    except Exception as e:
        current_app.logger.error(f"Error clearing STM database: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
