"""Flask Web UI for E-Claim Downloader"""

import os
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, Response, stream_with_context
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import humanize
import psycopg2
from pathlib import Path
import subprocess
import sys
import traceback
from utils import FileManager, DownloaderRunner
from utils.history_manager_db import HistoryManagerDB
from utils.import_runner import ImportRunner
from utils.log_stream import log_streamer
from utils.settings_manager import SettingsManager
from utils.scheduler import download_scheduler
from utils.job_history_manager import job_history_manager
from utils.alert_manager import alert_manager
from config.database import get_db_config, DB_TYPE
from config.db_pool import init_pool, close_pool, get_connection as get_pooled_connection, return_connection, get_pool_status


# Database-specific SQL helpers for PostgreSQL/MySQL compatibility
# Note: MySQL % in DATE_FORMAT must be escaped as %% when used with cursor.execute()
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


def sql_format_year_month(column: str) -> str:
    """Generate SQL for formatting date as YYYY-MM"""
    if DB_TYPE == 'mysql':
        return f"DATE_FORMAT({column}, '%%Y-%%m')"
    return f"TO_CHAR({column}, 'YYYY-MM')"


def sql_cast_numeric(expr: str) -> str:
    """Generate SQL for casting to numeric type"""
    if DB_TYPE == 'mysql':
        return f"CAST({expr} AS DECIMAL(15,2))"
    return f"({expr})::numeric"


def sql_interval_days(days: int) -> str:
    """Generate SQL for interval in days"""
    if DB_TYPE == 'mysql':
        return f"INTERVAL {days} DAY"
    return f"INTERVAL '{days} days'"


def sql_regex_match(column: str, pattern: str) -> str:
    """Generate SQL for regex matching (is numeric check)"""
    if DB_TYPE == 'mysql':
        return f"{column} REGEXP '{pattern}'"
    return f"{column} ~ '{pattern}'"


def sql_coalesce_numeric(column: str, default: int = 0) -> str:
    """Generate SQL for COALESCE with numeric cast"""
    if DB_TYPE == 'mysql':
        return f"CAST(COALESCE({column}, {default}) AS DECIMAL(15,2))"
    return f"COALESCE({column}, {default})::numeric"


def sql_cast_int(expr: str) -> str:
    """Generate SQL for casting to integer"""
    if DB_TYPE == 'mysql':
        return f"CAST({expr} AS SIGNED)"
    return f"({expr})::int"


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


def sql_full_outer_join(left_table: str, right_table: str, left_alias: str, right_alias: str, join_condition: str) -> str:
    """
    Generate SQL for FULL OUTER JOIN.
    MySQL doesn't support FULL OUTER JOIN, so we simulate it with UNION of LEFT and RIGHT JOINs.
    For PostgreSQL, use native FULL OUTER JOIN.

    Note: This returns a subquery that can be used in FROM clause.
    """
    if DB_TYPE == 'mysql':
        return f"""(
            SELECT * FROM {left_table} {left_alias}
            LEFT JOIN {right_table} {right_alias} ON {join_condition}
            UNION
            SELECT * FROM {left_table} {left_alias}
            RIGHT JOIN {right_table} {right_alias} ON {join_condition}
            WHERE {left_alias}.{join_condition.split('=')[0].strip().split('.')[-1]} IS NULL
        )"""
    return f"{left_table} {left_alias} FULL OUTER JOIN {right_table} {right_alias} ON {join_condition}"


def sql_ilike(column: str, pattern: str) -> str:
    """Generate SQL for case-insensitive LIKE"""
    if DB_TYPE == 'mysql':
        return f"{column} LIKE {pattern}"  # MySQL LIKE is case-insensitive by default with utf8mb4
    return f"{column} ILIKE {pattern}"


# Thailand timezone
TZ_BANGKOK = ZoneInfo('Asia/Bangkok')

app = Flask(__name__)

# Load SECRET_KEY from environment variable
# CRITICAL: Must be set in production for session security
secret_key = os.environ.get('SECRET_KEY')
if not secret_key:
    if os.environ.get('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY environment variable must be set in production')
    # Development fallback (not for production use)
    secret_key = 'dev-only-secret-key-do-not-use-in-production'
app.config['SECRET_KEY'] = secret_key

# Initialize managers - now using database-backed history
history_manager = HistoryManagerDB(download_type='rep')  # REP files
stm_history_manager = HistoryManagerDB(download_type='stm')  # Statement files
file_manager = FileManager()
downloader_runner = DownloaderRunner()
import_runner = ImportRunner()
settings_manager = SettingsManager()


def init_scheduler():
    """Initialize unified scheduler with saved settings for all data types"""
    try:
        # Get unified schedule settings
        schedule_settings = settings_manager.get_schedule_settings()

        # Clear all existing scheduled jobs
        for job in download_scheduler.get_all_jobs():
            if job['id'].startswith('download_'):
                download_scheduler.remove_scheduled_download(job['id'])
        download_scheduler.remove_stm_jobs()
        download_scheduler.remove_smt_jobs()

        if not schedule_settings['schedule_enabled']:
            log_streamer.write_log(
                "⏸ Scheduler disabled",
                'info',
                'system'
            )
            return

        # Get common settings
        times = schedule_settings['schedule_times']
        auto_import = schedule_settings['schedule_auto_import']
        schemes = schedule_settings.get('schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])
        type_rep = schedule_settings.get('schedule_type_rep', True)
        type_stm = schedule_settings.get('schedule_type_stm', False)
        type_smt = schedule_settings.get('schedule_type_smt', False)
        smt_vendor_id = schedule_settings.get('schedule_smt_vendor_id', '')

        if not times:
            log_streamer.write_log(
                "⚠ Scheduler enabled but no times configured",
                'warning',
                'system'
            )
            return

        # Schedule REP jobs if enabled
        if type_rep:
            for time_config in times:
                hour = time_config.get('hour', 0)
                minute = time_config.get('minute', 0)
                download_scheduler.add_scheduled_download(hour, minute, auto_import)

            log_streamer.write_log(
                f"✓ REP Scheduler initialized with {len(times)} jobs",
                'success',
                'system'
            )

        # Schedule Statement (STM) jobs if enabled - UCS only
        if type_stm:
            for time_config in times:
                hour = time_config.get('hour', 0)
                minute = time_config.get('minute', 0)
                download_scheduler.add_stm_scheduled_download(hour, minute, auto_import)

            log_streamer.write_log(
                f"✓ UC Statement Scheduler initialized with {len(times)} jobs",
                'success',
                'system'
            )

        # Schedule SMT Budget jobs if enabled
        if type_smt and smt_vendor_id:
            for time_config in times:
                hour = time_config.get('hour', 0)
                minute = time_config.get('minute', 0)
                download_scheduler.add_smt_scheduled_fetch(hour, minute, smt_vendor_id, auto_import)

            log_streamer.write_log(
                f"✓ SMT Budget Scheduler initialized with {len(times)} jobs (vendor: {smt_vendor_id})",
                'success',
                'system'
            )

        # Log summary
        data_types = []
        if type_rep:
            data_types.append('REP')
        if type_stm:
            data_types.append('Statement')
        if type_smt:
            data_types.append('SMT')
        log_streamer.write_log(
            f"📅 Unified scheduler active: {len(times)} times, types=[{', '.join(data_types)}]",
            'info',
            'system'
        )

    except Exception as e:
        app.logger.error(f"Error initializing scheduler: {e}")


def get_db_connection():
    """Get database connection from pool"""
    try:
        conn = get_pooled_connection()
        if conn is None:
            app.logger.error("Failed to get connection from pool")
        return conn
    except Exception as e:
        app.logger.error(f"Database connection error: {e}")
        return None


def get_import_status_map():
    """
    Get mapping of filename -> import status from database

    Returns:
        dict: {filename: {'imported': bool, 'file_id': int, 'imported_at': str}}
    """
    status_map = {}
    conn = get_db_connection()

    if not conn:
        return status_map

    try:
        cursor = conn.cursor()
        query = """
            SELECT filename, id, status, import_completed_at, imported_records, total_records
            FROM eclaim_imported_files
            WHERE status = 'completed'
            ORDER BY import_completed_at DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            filename, file_id, status, completed_at, imported_records, total_records = row
            status_map[filename] = {
                'imported': True,
                'file_id': file_id,
                'imported_at': completed_at.isoformat() if completed_at else None,
                'imported_records': imported_records or 0,
                'total_records': total_records or 0
            }

        cursor.close()
        conn.close()

    except Exception as e:
        app.logger.error(f"Error getting import status: {e}")
        if conn:
            conn.close()

    return status_map


@app.route('/')
def index():
    """Redirect to dashboard"""
    return redirect(url_for('dashboard'))


@app.route('/dashboard')
def dashboard():
    """Main dashboard view with statistics"""
    stats = history_manager.get_statistics()
    latest_files = history_manager.get_latest(5)

    # Format file sizes and dates for display
    for file in latest_files:
        file['size_formatted'] = humanize.naturalsize(file.get('file_size') or 0)
        try:
            # Parse datetime (stored as UTC in Docker container)
            dt = datetime.fromisoformat(file.get('download_date', ''))
            # If naive datetime, assume it's UTC and convert to Bangkok time
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc).astimezone(TZ_BANGKOK)
            # Use current Bangkok time for relative time calculation
            now = datetime.now(TZ_BANGKOK)
            file['date_formatted'] = humanize.naturaltime(dt, when=now)
        except (ValueError, TypeError, AttributeError):
            file['date_formatted'] = file.get('download_date', 'Unknown')

    # Check if downloader is running
    downloader_status = downloader_runner.get_status()

    # Get schedule settings and jobs
    schedule_settings = settings_manager.get_schedule_settings()
    schedule_jobs = download_scheduler.get_all_jobs()

    return render_template(
        'dashboard.html',
        stats=stats,
        latest_files=latest_files,
        downloader_running=downloader_status['running'],
        schedule_settings=schedule_settings,
        schedule_jobs=schedule_jobs
    )


@app.route('/files')
def files():
    """File list view with all downloads"""
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    filter_month = request.args.get('month', type=int)
    filter_year = request.args.get('year', type=int)

    # Default to current month/year if not specified
    now = datetime.now(TZ_BANGKOK)
    if filter_month is None:
        filter_month = now.month
    if filter_year is None:
        filter_year = now.year + 543  # Convert to Buddhist Era

    all_files = history_manager.get_all_downloads()

    # Get import status from database
    import_status_map = get_import_status_map()

    # Filter by month/year
    filtered_files = []
    for file in all_files:
        file_month = file.get('month')
        file_year = file.get('year')

        # If month/year not in file metadata, try to extract from filename
        if file_month is None or file_year is None:
            # Filename format: eclaim_10670_OP_25690106_xxx.xls
            # Extract year (2569) and month (01) from 25690106
            import re
            match = re.search(r'_(\d{4})(\d{2})\d{2}_', file.get('filename', ''))
            if match:
                file_year = int(match.group(1))
                file_month = int(match.group(2))

        # Apply filter
        if file_month == filter_month and file_year == filter_year:
            filtered_files.append(file)

    # Sort by download date (most recent first)
    filtered_files = sorted(
        filtered_files,
        key=lambda d: d.get('download_date') or '',
        reverse=True
    )

    # Calculate pagination
    total_files = len(filtered_files)
    total_pages = (total_files + per_page - 1) // per_page  # Ceiling division
    page = max(1, min(page, total_pages if total_pages > 0 else 1))

    # Paginate
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_files = filtered_files[start_idx:end_idx]

    # Format for display and add import status
    for file in paginated_files:
        file['size_formatted'] = humanize.naturalsize(file.get('file_size') or 0)
        try:
            # Parse datetime (stored as UTC in Docker container)
            dt = datetime.fromisoformat(file.get('download_date', ''))
            # If naive datetime, assume it's UTC and convert to Bangkok time
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc).astimezone(TZ_BANGKOK)
            file['date_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            # Use current Bangkok time for relative time calculation
            now = datetime.now(TZ_BANGKOK)
            file['date_relative'] = humanize.naturaltime(dt, when=now)
        except (ValueError, TypeError, AttributeError):
            file['date_formatted'] = file.get('download_date', 'Unknown')
            file['date_relative'] = 'Unknown'

        # Add import status
        filename = file.get('filename', '')
        if filename in import_status_map:
            file['import_status'] = import_status_map[filename]
            file['imported'] = True
        else:
            file['import_status'] = None
            file['imported'] = False

    # Count imported vs not imported (from filtered files)
    imported_count = sum(1 for f in filtered_files if f.get('imported', False))
    not_imported_count = len(filtered_files) - imported_count

    # Get available months/years for filter dropdown
    available_dates = history_manager.get_available_dates()

    # Get schedule settings and jobs
    schedule_settings = settings_manager.get_schedule_settings()
    schedule_jobs = download_scheduler.get_all_jobs()

    return render_template(
        'files.html',
        files=paginated_files,
        imported_count=imported_count,
        not_imported_count=not_imported_count,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_files=total_files,
        filter_month=filter_month,
        filter_year=filter_year,
        available_dates=available_dates,
        schedule_settings=schedule_settings,
        schedule_jobs=schedule_jobs
    )


@app.route('/download/trigger', methods=['POST'])
def trigger_download():
    """Trigger downloader as background process"""
    data = request.get_json() or {}
    auto_import = data.get('auto_import', False)

    result = downloader_runner.start(auto_import=auto_import)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500


@app.route('/download/status')
def download_status():
    """Get downloader status"""
    status = downloader_runner.get_status()
    return jsonify(status)


@app.route('/files/<filename>/delete', methods=['POST'])
def delete_file(filename):
    """Delete file from disk and history"""
    try:
        success = file_manager.delete_file(filename)

        if success:
            return jsonify({'success': True, 'message': 'File deleted'}), 200
        else:
            return jsonify({'success': False, 'message': 'File not found'}), 404

    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/files/<filename>/download')
def download_file(filename):
    """Download file to user's computer"""
    try:
        # Validate filename
        file_path = file_manager.get_file_path(filename)

        if not file_path.exists():
            return jsonify({'error': 'File not found'}), 404

        return send_from_directory(
            file_manager.download_dir,
            filename,
            as_attachment=True
        )

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500


@app.route('/import/file/<filename>', methods=['POST'])
def import_file(filename):
    """Import single file to database"""
    try:
        # Validate filename
        file_path = file_manager.get_file_path(filename)

        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Check if already imported
        import_status_map = get_import_status_map()
        if filename in import_status_map:
            return jsonify({
                'success': False,
                'error': 'File already imported',
                'file_id': import_status_map[filename]['file_id']
            }), 409

        # Start import process in background
        result = import_runner.start_single_import(str(file_path))

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/import/all', methods=['POST'])
def import_all_files():
    """Import all files that haven't been imported yet"""
    try:
        all_files = history_manager.get_all_downloads()
        import_status_map = get_import_status_map()

        # Filter out already imported files
        not_imported = [
            f for f in all_files
            if f.get('filename', '') not in import_status_map
        ]

        if not not_imported:
            return jsonify({
                'success': True,
                'message': 'All files already imported',
                'total': 0,
                'skipped': len(all_files)
            }), 200

        # Start bulk import process in background (REP files in downloads/rep)
        downloads_dir = Path('downloads/rep')
        result = import_runner.start_bulk_import(str(downloads_dir))

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/import/progress')
def import_progress():
    """Get real-time import progress"""
    try:
        progress = import_runner.get_progress()
        return jsonify(progress)

    except Exception as e:
        return jsonify({'running': False, 'error': str(e)}), 500


@app.route('/api/stats')
def api_stats():
    """JSON API for statistics (for AJAX refresh)"""
    stats = history_manager.get_statistics()
    downloader_status = downloader_runner.get_status()

    return jsonify({
        'stats': stats,
        'downloader_running': downloader_status['running']
    })


@app.route('/download-config')
def download_config():
    """Download configuration page with date selection"""
    return render_template('download_config.html')


@app.route('/data-management')
def data_management():
    """
    Combined Data Management page with tabs for:
    - Download (single month, bulk download, scheduler)
    - Files (file list with import status)
    - SMT Budget sync
    - Settings (credentials, database info)
    """
    # Get filter parameters for files tab
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    # Fiscal year parameter (Thai Buddhist Era)
    # Fiscal year 2569 = Oct 2568 - Sep 2569
    fiscal_year = request.args.get('fiscal_year', type=int)

    # Support both old (month/year) and new (start_month/end_month) parameters
    start_month = request.args.get('start_month', type=int) or request.args.get('month', type=int)
    start_year = request.args.get('start_year', type=int) or request.args.get('year', type=int)
    end_month = request.args.get('end_month', type=int)
    end_year = request.args.get('end_year', type=int)

    # If fiscal year is set, calculate start/end years
    if fiscal_year:
        # Fiscal year X runs from Oct (year X-1) to Sep (year X)
        if start_month and start_month >= 10:
            start_year = start_year or (fiscal_year - 1)
        else:
            start_year = start_year or fiscal_year
        if end_month and end_month <= 9:
            end_year = end_year or fiscal_year
        else:
            end_year = end_year or (fiscal_year - 1)

    filter_scheme = request.args.get('scheme', '').strip().lower()
    filter_file_type = request.args.get('file_type', '').strip().lower()  # op, ip, orf, appeal
    filter_status = request.args.get('status', '').strip().lower()  # imported, pending, or empty for all

    # Default to show all if no date specified
    now = datetime.now(TZ_BANGKOK)
    show_all_dates = start_month is None and end_month is None and fiscal_year is None

    # For backward compatibility
    filter_month = start_month or now.month
    filter_year = start_year or (now.year + 543)

    all_files = history_manager.get_all_downloads()

    # Get import status from database
    import_status_map = get_import_status_map()

    # Helper function to convert month/year to comparable number
    def date_to_num(m, y):
        return y * 12 + m

    # Filter files
    filtered_files = []
    for file in all_files:
        file_month = file.get('month')
        file_year = file.get('year')

        # If month/year not in file metadata, try to extract from filename
        if file_month is None or file_year is None:
            import re
            match = re.search(r'_(\d{4})(\d{2})\d{2}_', file.get('filename', ''))
            if match:
                file_year = int(match.group(1))
                file_month = int(match.group(2))

        # Skip if still no date info
        if file_month is None or file_year is None:
            if not show_all_dates:
                continue
        else:
            # Date range filter
            if not show_all_dates:
                file_date_num = date_to_num(file_month, file_year)

                if start_month and start_year:
                    start_num = date_to_num(start_month, start_year)
                    if file_date_num < start_num:
                        continue

                if end_month and end_year:
                    end_num = date_to_num(end_month, end_year)
                    if file_date_num > end_num:
                        continue

        # Scheme filter (check filename)
        if filter_scheme:
            filename_lower = file.get('filename', '').lower()
            if filter_scheme not in filename_lower:
                continue

        # File type filter (op, ip, orf, appeal)
        if filter_file_type:
            filename_upper = file.get('filename', '').upper()
            if filter_file_type == 'op':
                # Match OP but not OPLGO, OPSSS, OP_APPEAL
                if '_OP_' not in filename_upper and not filename_upper.endswith('_OP.xls'):
                    continue
            elif filter_file_type == 'ip':
                # Match IP but not IPLGO, IPSSS, IP_APPEAL
                if '_IP_' not in filename_upper and not filename_upper.endswith('_IP.xls'):
                    continue
            elif filter_file_type == 'orf':
                if '_ORF_' not in filename_upper:
                    continue
            elif filter_file_type == 'appeal':
                if 'APPEAL' not in filename_upper:
                    continue

        # Add import status early for status filtering
        filename = file.get('filename', '')
        file['imported'] = filename in import_status_map
        if filename in import_status_map:
            file['import_status'] = import_status_map[filename]
        else:
            file['import_status'] = None

        # Status filter
        if filter_status:
            if filter_status == 'imported' and not file['imported']:
                continue
            if filter_status == 'pending' and file['imported']:
                continue

        filtered_files.append(file)

    # Sort by download date (most recent first)
    filtered_files = sorted(
        filtered_files,
        key=lambda d: d.get('download_date') or '',
        reverse=True
    )

    # Calculate pagination
    total_files_filtered = len(filtered_files)
    total_pages = (total_files_filtered + per_page - 1) // per_page
    page = max(1, min(page, total_pages if total_pages > 0 else 1))

    # Paginate
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_files = filtered_files[start_idx:end_idx]

    # Format for display (import status already added during filtering)
    for file in paginated_files:
        file['size_formatted'] = humanize.naturalsize(file.get('file_size') or 0)
        try:
            dt = datetime.fromisoformat(file.get('download_date', ''))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc).astimezone(TZ_BANGKOK)
            file['date_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            now_time = datetime.now(TZ_BANGKOK)
            file['date_relative'] = humanize.naturaltime(dt, when=now_time)
        except (ValueError, TypeError, AttributeError):
            file['date_formatted'] = file.get('download_date', 'Unknown')
            file['date_relative'] = 'Unknown'

    # Count imported vs not imported (from filtered files, not all files)
    filtered_imported_count = sum(1 for f in filtered_files if f.get('imported', False))
    filtered_not_imported_count = len(filtered_files) - filtered_imported_count

    # Get available months/years for filter
    available_dates = history_manager.get_available_dates()

    # Get settings
    current_settings = settings_manager.load_settings()

    # Get database info
    db_info = {
        'type': 'PostgreSQL',
        'claims_count': 0,
        'budget_count': 0
    }
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM claim_rep_opip_nhso_item")
            db_info['claims_count'] = cursor.fetchone()[0]
            try:
                cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
                db_info['budget_count'] = cursor.fetchone()[0]
            except Exception:
                # Table may not exist in all deployments
                pass
            cursor.close()
            conn.close()
        except Exception as e:
            app.logger.error(f"Error getting db stats: {e}")
            if conn:
                conn.close()

    # Calculate stats (from filtered files to match filter selection)
    stats = {
        'total_files': len(filtered_files),
        'total_size': humanize.naturalsize(sum((f.get('file_size') or 0) for f in filtered_files)),
        'imported_count': filtered_imported_count,
        'not_imported_count': filtered_not_imported_count
    }

    return render_template(
        'data_management.html',
        files=paginated_files,
        stats=stats,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total_files=total_files_filtered,
        filter_month=filter_month,
        filter_year=filter_year,
        available_dates=available_dates,
        settings=current_settings,
        db_info=db_info
    )


@app.route('/data-analysis')
def data_analysis():
    """
    Data Analysis page for viewing linked data across:
    - REP (E-Claim Reimbursement)
    - Statement (stm_claim_item)
    - SMT Budget
    """
    return render_template('data_analysis.html')


# ==============================================================================
# Data Analysis API Endpoints
# ==============================================================================

@app.route('/api/analysis/summary')
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
            # Convert to Gregorian: BE - 543 = CE
            gregorian_year = fiscal_year - 543
            fy_start = f"{gregorian_year - 1}-10-01"  # Oct of previous year
            fy_end = f"{gregorian_year}-09-30"  # Sep of fiscal year

            # SMT uses Thai BE format YYYYMMDD (e.g., "25681001" for Oct 1, 2568)
            smt_fy_start = f"{fiscal_year - 1}1001"  # Oct of previous BE year
            smt_fy_end = f"{fiscal_year}0930"  # Sep of fiscal BE year

            # If specific months are selected
            if start_month and end_month:
                # Adjust for fiscal year (Oct=1, Nov=2, ..., Sep=12 in fiscal terms)
                # But user selects calendar months (1=Jan, ..., 12=Dec)
                # So we need to convert calendar months to actual dates
                if start_month >= 10:
                    start_date = f"{gregorian_year - 1}-{start_month:02d}-01"
                    smt_start = f"{fiscal_year - 1}{start_month:02d}01"
                else:
                    start_date = f"{gregorian_year}-{start_month:02d}-01"
                    smt_start = f"{fiscal_year}{start_month:02d}01"

                if end_month >= 10:
                    end_date = f"{gregorian_year - 1}-{end_month:02d}-01"
                    smt_end_year = fiscal_year - 1
                else:
                    end_date = f"{gregorian_year}-{end_month:02d}-01"
                    smt_end_year = fiscal_year

                # Get last day of end month
                from calendar import monthrange
                end_year = gregorian_year if end_month < 10 else gregorian_year - 1
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
            app.logger.warning(f"Error getting REP summary: {e}")

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
            app.logger.warning(f"Error getting Statement summary: {e}")

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
            app.logger.warning(f"Error getting SMT summary: {e}")

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
        app.logger.error(f"Error in analysis summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/reconciliation')
def api_analysis_reconciliation():
    """
    Reconcile REP and Statement data by tran_id
    """
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
        app.logger.error(f"Error in reconciliation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/export')
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
        app.logger.error(f"Error in export: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/search')
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
            app.logger.warning(f"Error searching REP: {e}")

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
            app.logger.warning(f"Error searching Statement: {e}")

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
            app.logger.warning(f"Error searching SMT: {e}")

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
        app.logger.error(f"Error in search: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/files')
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
        app.logger.error(f"Error getting files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/file-items')
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
        app.logger.error(f"Error getting file items: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# =============================================================================
# NEW: Enhanced Data Analysis APIs
# =============================================================================

@app.route('/api/analysis/claims')
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
        app.logger.error(f"Error getting claims: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/financial-breakdown')
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
        app.logger.error(f"Error getting financial breakdown: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/errors')
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
        app.logger.error(f"Error getting error analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/scheme-summary')
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
        app.logger.error(f"Error getting scheme summary: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/facilities')
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
        app.logger.error(f"Error getting facility analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analysis/his-reconciliation')
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
        app.logger.error(f"Error getting HIS reconciliation: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/trigger/single', methods=['POST'])
def trigger_single_download():
    """Trigger download for specific month/year and schemes"""
    try:
        data = request.get_json()
        month = data.get('month')
        year = data.get('year')
        schemes = data.get('schemes', ['ucs'])  # Default to UCS if not specified
        auto_import = data.get('auto_import', False)

        # Validate inputs
        if not month or not year:
            return jsonify({'success': False, 'error': 'Month and year are required'}), 400

        month = int(month)
        year = int(year)

        if not (1 <= month <= 12):
            return jsonify({'success': False, 'error': 'Invalid month (must be 1-12)'}), 400

        if not (2561 <= year <= 2570):
            return jsonify({'success': False, 'error': 'Invalid year (must be 2561-2570 BE)'}), 400

        # Validate schemes
        valid_schemes = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']
        if schemes:
            schemes = [s for s in schemes if s in valid_schemes]
        if not schemes:
            schemes = ['ucs']  # Default fallback

        # Start downloader with parameters
        result = downloader_runner.start(month=month, year=year, schemes=schemes, auto_import=auto_import)

        if result['success']:
            return jsonify(result), 200
        else:
            status_code = 409 if 'already running' in result.get('error', '').lower() else 500
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/trigger/bulk', methods=['POST'])
def trigger_bulk_download():
    """Trigger bulk download for date range and schemes"""
    try:
        data = request.get_json()

        start_month = data.get('start_month')
        start_year = data.get('start_year')
        end_month = data.get('end_month')
        end_year = data.get('end_year')
        schemes = data.get('schemes', ['ucs', 'ofc', 'sss', 'lgo'])  # Default to 4 main schemes
        auto_import = data.get('auto_import', False)

        # Validate inputs
        if not all([start_month, start_year, end_month, end_year]):
            return jsonify({'success': False, 'error': 'All date fields are required'}), 400

        start_month = int(start_month)
        start_year = int(start_year)
        end_month = int(end_month)
        end_year = int(end_year)

        # Validate ranges
        if not (1 <= start_month <= 12) or not (1 <= end_month <= 12):
            return jsonify({'success': False, 'error': 'Invalid month (must be 1-12)'}), 400

        if not (2561 <= start_year <= 2570) or not (2561 <= end_year <= 2570):
            return jsonify({'success': False, 'error': 'Invalid year (must be 2561-2570 BE)'}), 400

        # Validate date order
        if start_year > end_year or (start_year == end_year and start_month > end_month):
            return jsonify({'success': False, 'error': 'Start date must be before or equal to end date'}), 400

        # Validate schemes
        valid_schemes = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']
        if schemes:
            schemes = [s for s in schemes if s in valid_schemes]
        if not schemes:
            schemes = ['ucs']  # Default fallback

        # Start bulk downloader with schemes
        result = downloader_runner.start_bulk(
            start_month, start_year,
            end_month, end_year,
            auto_import=auto_import,
            schemes=schemes
        )

        if result['success']:
            return jsonify(result), 200
        else:
            status_code = 409 if 'already running' in result.get('error', '').lower() else 500
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/bulk/progress')
def bulk_progress():
    """Get real-time bulk download progress"""
    try:
        progress = downloader_runner.get_bulk_progress()
        return jsonify(progress)

    except Exception as e:
        return jsonify({'running': False, 'error': str(e)}), 500


@app.route('/download/bulk/cancel', methods=['POST'])
def cancel_bulk_download():
    """Cancel a running bulk download"""
    try:
        result = downloader_runner.stop()
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Parallel Download Routes ====================

@app.route('/api/download/parallel', methods=['POST'])
def trigger_parallel_download():
    """Trigger parallel download with multiple browser sessions"""
    try:
        from utils.parallel_downloader import ParallelDownloader

        data = request.get_json()
        month = data.get('month')
        year = data.get('year')
        scheme = data.get('scheme', 'ucs')
        max_workers = data.get('max_workers', 3)
        auto_import = data.get('auto_import', False)

        # Validate
        if not month or not year:
            return jsonify({'success': False, 'error': 'month and year required'}), 400

        month = int(month)
        year = int(year)
        max_workers = min(int(max_workers), 5)  # Max 5 workers

        # Get all credentials (supports multiple accounts)
        credentials = settings_manager.get_all_credentials()
        enabled_creds = [c for c in credentials if c.get('enabled', True)]

        if not enabled_creds:
            return jsonify({'success': False, 'error': 'E-Claim credentials not configured'}), 400

        # Log how many accounts will be used
        num_accounts = len(enabled_creds)
        if num_accounts > 1:
            app.logger.info(f"Parallel download with {num_accounts} accounts, {max_workers} workers")
        else:
            app.logger.info(f"Parallel download with 1 account, {max_workers} workers")

        # Run in background thread
        import threading

        def run_parallel():
            # Start job tracking
            job_id = job_history_manager.start_job(
                job_type='download',
                job_subtype='parallel',
                parameters={
                    'month': month,
                    'year': year,
                    'scheme': scheme,
                    'max_workers': max_workers,
                    'auto_import': auto_import
                },
                triggered_by='manual'
            )

            try:
                downloader = ParallelDownloader(
                    credentials=enabled_creds,
                    month=month,
                    year=year,
                    scheme=scheme,
                    max_workers=max_workers
                )
                result = downloader.run()

                # Complete job with results
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='completed' if result.get('failed', 0) == 0 else 'completed_with_errors',
                    results={
                        'total_files': result.get('total', 0),
                        'success_files': result.get('completed', 0),
                        'failed_files': result.get('failed', 0),
                        'skipped_files': result.get('skipped', 0)
                    },
                    error_message=f"{result.get('failed', 0)} files failed" if result.get('failed', 0) > 0 else None
                )

                # Auto import if enabled - only import files that were just downloaded
                if auto_import and result.get('completed', 0) > 0:
                    from utils.eclaim.importer_v2 import import_eclaim_file
                    from config.database import get_db_config, DB_TYPE
                    from pathlib import Path
                    from utils.log_stream import log_streamer

                    # Get only the successfully downloaded files from this session
                    download_dir = Path('downloads/rep')
                    downloaded_files = []
                    for r in result.get('results', []):
                        if r.get('success') and not r.get('skipped'):
                            filepath = download_dir / r['filename']
                            if filepath.exists():
                                downloaded_files.append(str(filepath))

                    if downloaded_files:
                        log_streamer.write_log(f"\n📥 Auto-import: Starting import of {len(downloaded_files)} files...", 'info', 'import')
                        db_config = get_db_config()

                        import_success = 0
                        import_failed = 0
                        total_records = 0

                        for idx, filepath in enumerate(downloaded_files, 1):
                            filename = Path(filepath).name
                            log_streamer.write_log(f"[{idx}/{len(downloaded_files)}] Importing: {filename}", 'info', 'import')

                            try:
                                import_result = import_eclaim_file(filepath, db_config, DB_TYPE)
                                if import_result.get('success'):
                                    records = import_result.get('imported_records', 0)
                                    total_records += records
                                    import_success += 1
                                    log_streamer.write_log(f"  ✓ Imported: {records} records", 'success', 'import')
                                else:
                                    import_failed += 1
                                    error_msg = import_result.get('error', 'Unknown error')
                                    log_streamer.write_log(f"  ✗ Failed: {error_msg}", 'error', 'import')
                            except Exception as import_error:
                                import_failed += 1
                                log_streamer.write_log(f"  ✗ Import error: {str(import_error)}", 'error', 'import')

                        log_streamer.write_log(f"\n📊 Import complete: {import_success}/{len(downloaded_files)} files, {total_records} records", 'success', 'import')

            except Exception as e:
                app.logger.error(f"Parallel download error: {e}")
                # Mark job as failed
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='failed',
                    error_message=str(e)
                )

        thread = threading.Thread(target=run_parallel, daemon=True)
        thread.start()

        return jsonify({
            'success': True,
            'message': f'Parallel download started with {max_workers} workers, {num_accounts} account(s)',
            'month': month,
            'year': year,
            'scheme': scheme,
            'max_workers': max_workers,
            'num_accounts': num_accounts,
            'auto_import': auto_import
        })

    except Exception as e:
        app.logger.error(f"Error starting parallel download: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download/parallel/progress')
def parallel_download_progress():
    """Get parallel download progress"""
    try:
        import json
        from pathlib import Path
        from datetime import datetime

        progress_file = Path('parallel_download_progress.json')

        if not progress_file.exists():
            return jsonify({
                'running': False,
                'status': 'idle'
            })

        with open(progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)

        # Check if still running
        status = progress.get('status')
        running = status == 'downloading'

        # Auto-recovery: detect orphan/stale downloads
        # If status is "downloading" but file hasn't been updated in 60 seconds, mark as stale
        if running:
            file_mtime = progress_file.stat().st_mtime
            seconds_since_update = (datetime.now().timestamp() - file_mtime)
            if seconds_since_update > 60:  # No update in 60 seconds = likely orphaned
                progress['running'] = False
                progress['status'] = 'stale'
                progress['stale_reason'] = 'No progress update for 60+ seconds. Process may have crashed.'
                return jsonify(progress)

        progress['running'] = running

        return jsonify(progress)

    except Exception as e:
        return jsonify({'running': False, 'error': str(e)}), 500


@app.route('/api/download/parallel/cancel', methods=['POST'])
def cancel_parallel_download():
    """Cancel or force-clear parallel download progress"""
    try:
        import json
        from pathlib import Path

        progress_file = Path('parallel_download_progress.json')

        if not progress_file.exists():
            return jsonify({
                'success': True,
                'message': 'No download in progress'
            })

        # Read current progress
        with open(progress_file, 'r', encoding='utf-8') as f:
            progress = json.load(f)

        # Check if force cancel requested
        data = request.get_json() or {}
        force = data.get('force', False)

        # If actually running (recent update), try graceful cancel
        if progress.get('status') == 'downloading' and not force:
            file_mtime = progress_file.stat().st_mtime
            seconds_since_update = (datetime.now().timestamp() - file_mtime)

            if seconds_since_update < 30:
                # Process seems active, set cancel flag
                progress['cancel_requested'] = True
                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                return jsonify({
                    'success': True,
                    'message': 'Cancel signal sent to running download'
                })

        # Force cancel: delete progress file
        progress_file.unlink()

        return jsonify({
            'success': True,
            'message': 'Download progress cleared',
            'was_stale': progress.get('status') == 'downloading'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/date-range-stats')
def date_range_stats():
    """Get statistics grouped by month/year"""
    try:
        stats = history_manager.get_date_range_statistics()
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ==================== STM (Statement) Download Routes ====================

@app.route('/api/stm/download', methods=['POST'])
def trigger_stm_download():
    """Trigger STM (Statement) download with optional auto-import"""
    try:
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
        import subprocess
        import threading

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
                app.logger.warning(f"Could not start job tracking: {e}")

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
                        app.logger.warning(f"Could not complete job tracking: {e}")

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
        app.logger.error(f"STM download error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/history')
def get_stm_history():
    """Get STM download history"""
    try:
        history_file = Path('stm_download_history.json')
        if history_file.exists():
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
                return jsonify({
                    'success': True,
                    'last_run': history.get('last_run'),
                    'downloads': history.get('downloads', [])[-50:],  # Last 50
                    'total': len(history.get('downloads', []))
                })
        return jsonify({
            'success': True,
            'last_run': None,
            'downloads': [],
            'total': 0
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/files')
def list_stm_files():
    """List downloaded STM files"""
    try:
        download_dir = Path('downloads/stm')
        stm_files = []

        if download_dir.exists():
            for f in download_dir.glob('STM_*.xls'):
                stat = f.stat()
                stm_files.append({
                    'filename': f.name,
                    'size': stat.st_size,
                    'size_formatted': humanize.naturalsize(stat.st_size),
                    'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
                })

        # Sort by modified date desc
        stm_files.sort(key=lambda x: x['modified'], reverse=True)

        return jsonify({
            'success': True,
            'files': stm_files[:100],
            'total': len(stm_files)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/stats')
def get_stm_stats():
    """Get Statement files statistics with optional filtering"""
    import re

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
            app.logger.warning(f"Could not fetch STM import status: {e}")

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


@app.route('/api/stm/import/<filename>', methods=['POST'])
def import_stm_file_route(filename):
    """Import a single Statement file"""
    try:
        file_path = Path('downloads/stm') / filename
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Check if file is a valid STM file
        if not filename.startswith('STM_'):
            return jsonify({'success': False, 'error': 'Not a valid STM file'}), 400

        from config.database import get_db_config, DB_TYPE
        from utils.stm.importer import STMImporter

        db_config = get_db_config()
        importer = STMImporter(db_config, DB_TYPE)

        try:
            importer.connect()
            result = importer.import_file(str(file_path))
            return jsonify(result)
        finally:
            importer.disconnect()

    except Exception as e:
        app.logger.error(f"STM import error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/import-all', methods=['POST'])
def import_all_stm_files():
    """Import all pending Statement files"""
    try:
        download_dir = Path('downloads/stm')
        from config.database import get_db_config, DB_TYPE
        from utils.stm.importer import STMImporter

        db_config = get_db_config()
        results = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }

        # Get list of already imported files
        imported_files = set()
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT filename FROM stm_imported_files WHERE status = 'completed'"
            )
            imported_files = {row[0] for row in cursor.fetchall()}
            cursor.close()
            conn.close()
        except Exception as e:
            app.logger.warning(f"Could not check existing STM imports: {e}")

        importer = STMImporter(db_config, DB_TYPE)
        try:
            importer.connect()

            for f in sorted(download_dir.glob('STM_*.xls')):
                results['total'] += 1

                # Check if already imported
                if f.name in imported_files:
                    results['skipped'] += 1
                    continue

                # Import file
                try:
                    result = importer.import_file(str(f))
                    if result.get('success'):
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                    results['details'].append({
                        'filename': f.name,
                        'success': result.get('success', False),
                        'records': result.get('claim_records', 0),
                        'file_type': result.get('file_type'),
                        'scheme': result.get('scheme'),
                        'error': result.get('error')
                    })
                except Exception as e:
                    results['failed'] += 1
                    results['details'].append({
                        'filename': f.name,
                        'success': False,
                        'error': str(e)
                    })

        finally:
            importer.disconnect()

        return jsonify({'success': True, **results})

    except Exception as e:
        app.logger.error(f"STM import-all error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/delete/<filename>', methods=['DELETE'])
def delete_stm_file(filename):
    """Delete a Statement file"""
    try:
        file_path = Path('downloads/stm') / filename
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Delete import record if exists (cascade will delete related records)
        try:
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stm_imported_files WHERE filename = %s", (filename,))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            app.logger.warning(f"Could not delete STM import record: {e}")

        # Delete file
        file_path.unlink()

        return jsonify({'success': True, 'message': f'Deleted {filename}'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/clear', methods=['POST'])
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
            app.logger.warning(f"Could not clear STM import records: {e}")

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


@app.route('/api/stm/records')
def get_stm_records():
    """Get Statement database records with reconciliation status"""
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

        # Build WHERE clause
        where_clauses = []
        params = []

        if fiscal_year:
            # Fiscal year filter - statement_month (1-12) and statement_year stored separately
            # FY 2569 = Oct 2568 (year=2568, month>=10) to Sep 2569 (year=2569, month<=9)
            fy = int(fiscal_year)
            # Two ranges: Oct-Dec of previous year OR Jan-Sep of fiscal year
            where_clauses.append("""
                ((f.statement_year = %s AND f.statement_month >= 10)
                 OR (f.statement_year = %s AND f.statement_month <= 9))
            """)
            params.extend([fy - 1, fy])

        if rep_no:
            where_clauses.append("c.rep_no LIKE %s")
            params.append(f"%{rep_no}%")

        if status:
            where_clauses.append("c.reconcile_status = %s")
            params.append(status)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        if view_mode == 'rep':
            # Group by REP No
            count_sql = f"""
                SELECT COUNT(DISTINCT c.rep_no)
                FROM stm_claim_item c
                JOIN stm_imported_files f ON c.file_id = f.id
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            query = f"""
                SELECT
                    c.rep_no,
                    COUNT(*) as count,
                    SUM(COALESCE(c.paid_after_deduction, 0)) as stm_amount,
                    (
                        SELECT SUM(COALESCE(r.reimb_nhso, 0))
                        FROM claim_rep_opip_nhso_item r
                        WHERE r.rep_no = c.rep_no
                    ) as rep_amount,
                    CASE
                        WHEN COUNT(CASE WHEN c.reconcile_status = 'matched' THEN 1 END) = COUNT(*) THEN 'matched'
                        WHEN COUNT(CASE WHEN c.reconcile_status = 'diff_amount' THEN 1 END) > 0 THEN 'diff_amount'
                        ELSE 'stm_only'
                    END as status
                FROM stm_claim_item c
                JOIN stm_imported_files f ON c.file_id = f.id
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
                FROM stm_claim_item c
                JOIN stm_imported_files f ON c.file_id = f.id
                WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total = cursor.fetchone()[0]

            query = f"""
                SELECT
                    c.tran_id,
                    c.rep_no,
                    c.patient_name,
                    c.hn,
                    COALESCE(c.paid_after_deduction, 0) as stm_amount,
                    (
                        SELECT COALESCE(r.reimb_nhso, 0)
                        FROM claim_rep_opip_nhso_item r
                        WHERE r.tran_id = c.tran_id
                        LIMIT 1
                    ) as rep_amount,
                    c.reconcile_status as status
                FROM stm_claim_item c
                JOIN stm_imported_files f ON c.file_id = f.id
                WHERE {where_sql}
                ORDER BY c.rep_no DESC, c.tran_id
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

        # Get stats - count matched records by checking if REP exists
        stats_sql = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM claim_rep_opip_nhso_item r
                    WHERE r.tran_id = c.tran_id
                    AND ABS(COALESCE(r.reimb_nhso, 0) - COALESCE(c.paid_after_deduction, 0)) < 1
                ) THEN 1 END) as matched,
                COUNT(CASE WHEN EXISTS (
                    SELECT 1 FROM claim_rep_opip_nhso_item r
                    WHERE r.tran_id = c.tran_id
                    AND ABS(COALESCE(r.reimb_nhso, 0) - COALESCE(c.paid_after_deduction, 0)) >= 1
                ) THEN 1 END) as diff_amount
            FROM stm_claim_item c
        """
        cursor.execute(stats_sql)
        stats_row = cursor.fetchone()
        total = stats_row[0] or 0
        matched = stats_row[1] or 0
        diff_amount = stats_row[2] or 0
        stm_only = total - matched - diff_amount

        stats = {
            'total': total,
            'matched': matched,
            'diff_amount': diff_amount,
            'stm_only': stm_only
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
        app.logger.error(f"Error fetching STM records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/clear-database', methods=['POST'])
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
        app.logger.error(f"Error clearing STM database: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rep/file-type-stats')
def get_file_type_stats():
    """Get file statistics grouped by file type"""
    try:
        import re
        from collections import defaultdict

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
            app.logger.warning(f"Could not get import status: {e}")

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
        app.logger.error(f"Error getting file type stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rep/records')
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
        app.logger.error(f"Error fetching REP records: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rep/clear-database', methods=['POST'])
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
        app.logger.error(f"Error clearing REP database: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/rep/clear-files', methods=['POST'])
def clear_rep_files():
    """Clear all REP files (keep database records)"""
    try:
        deleted_count = 0
        rep_dir = Path('downloads/rep')

        if rep_dir.exists():
            for file in rep_dir.glob('*.*'):
                if file.is_file():
                    file.unlink()
                    deleted_count += 1

        # Also clear download history for REP
        history = history_manager.load_history()
        if 'downloads' in history:
            original_count = len(history['downloads'])
            history['downloads'] = [d for d in history['downloads'] if d.get('type') != 'rep']
            removed_history = original_count - len(history['downloads'])
            history_manager.save_history(history)

        return jsonify({
            'success': True,
            'message': f'Cleared {deleted_count} REP files',
            'deleted_files': deleted_count
        })

    except Exception as e:
        app.logger.error(f"Error clearing REP files: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/settings')
def settings():
    """Settings page"""
    current_settings = settings_manager.load_settings()
    return render_template('settings.html', settings=current_settings)


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    """Get or update settings"""
    if request.method == 'GET':
        settings = settings_manager.load_settings()
        # Don't send password to frontend
        settings['eclaim_password'] = '********' if settings.get('eclaim_password') else ''
        return jsonify(settings)

    elif request.method == 'POST':
        data = request.get_json()

        # Validate required fields
        username = data.get('eclaim_username', '').strip()
        password = data.get('eclaim_password', '').strip()

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400

        # Don't update password if it's the placeholder
        current_settings = settings_manager.load_settings()
        if password == '********':
            password = current_settings.get('eclaim_password', '')
        elif not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 400

        # Update settings
        success = settings_manager.update_credentials(username, password)

        if success:
            return jsonify({'success': True, 'message': 'Settings updated successfully'}), 200
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'}), 500


# ===== Multiple Credentials Management =====

@app.route('/api/settings/credentials', methods=['GET', 'POST'])
def manage_credentials():
    """Manage multiple E-Claim credentials"""
    if request.method == 'GET':
        # Get all credentials (mask passwords)
        credentials = settings_manager.get_all_credentials()
        masked_creds = []
        for cred in credentials:
            masked_creds.append({
                'username': cred.get('username', ''),
                'password': '********',
                'note': cred.get('note', ''),
                'enabled': cred.get('enabled', True)
            })
        return jsonify({
            'success': True,
            'credentials': masked_creds,
            'count': settings_manager.get_credentials_count()
        })

    elif request.method == 'POST':
        # Add new credential
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        note = data.get('note', '').strip()
        enabled = data.get('enabled', True)

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400
        if not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 400

        success = settings_manager.add_credential(username, password, note, enabled)
        if success:
            return jsonify({'success': True, 'message': 'Credential added successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to add credential'}), 500


@app.route('/api/settings/credentials/<username>', methods=['PUT', 'DELETE'])
def manage_credential(username):
    """Update or delete a specific credential"""
    if request.method == 'PUT':
        data = request.get_json()
        password = data.get('password')
        note = data.get('note')
        enabled = data.get('enabled')

        # Don't update password if it's the placeholder
        if password == '********':
            password = None

        success = settings_manager.update_credential(username, password, note, enabled)
        if success:
            return jsonify({'success': True, 'message': 'Credential updated successfully'})
        else:
            return jsonify({'success': False, 'error': 'Credential not found'}), 404

    elif request.method == 'DELETE':
        success = settings_manager.remove_credential(username)
        if success:
            return jsonify({'success': True, 'message': 'Credential removed successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to remove credential'}), 500


@app.route('/api/settings/credentials/bulk', methods=['POST'])
def bulk_update_credentials():
    """Bulk update all credentials"""
    data = request.get_json()
    credentials = data.get('credentials', [])

    # Preserve existing passwords for masked entries
    existing_creds = {c['username']: c for c in settings_manager.get_all_credentials()}

    for cred in credentials:
        if cred.get('password') == '********':
            existing = existing_creds.get(cred.get('username'))
            if existing:
                cred['password'] = existing.get('password', '')

    success = settings_manager.set_all_credentials(credentials)
    if success:
        return jsonify({'success': True, 'message': 'Credentials updated successfully'})
    else:
        return jsonify({'success': False, 'error': 'Failed to update credentials'}), 500


@app.route('/api/settings/test-connection', methods=['POST'])
def test_eclaim_connection():
    """Test E-Claim login credentials (randomly selected)"""
    import requests

    try:
        # Get credentials from settings (random selection)
        username, password = settings_manager.get_eclaim_credentials(random_select=True)

        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Credentials not configured. Please add at least one account.'
            }), 400

        # Mask username for log
        masked_user = f"{username[:4]}***{username[-4:]}" if len(username) > 8 else "***"
        log_streamer.write_log(
            f"Testing E-Claim connection for user: {masked_user}",
            'info',
            'system'
        )

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'th,en;q=0.9',
        })

        # First, check if NHSO service is alive
        health_check_url = "https://eclaim.nhso.go.th/webComponent/"
        try:
            health_response = session.get(health_check_url, timeout=15)
            health_response.raise_for_status()
            log_streamer.write_log(
                f"NHSO service is reachable",
                'info',
                'system'
            )
        except requests.exceptions.RequestException as e:
            log_streamer.write_log(
                f"NHSO service is not reachable: {str(e)}",
                'error',
                'system'
            )
            return jsonify({
                'success': False,
                'error': 'NHSO E-Claim service is not available. Please try again later.'
            }), 503

        # Test login
        login_url = "https://eclaim.nhso.go.th/webComponent/main/MainWebAction.do"

        # Get the login page
        response = session.get(login_url, timeout=30)
        response.raise_for_status()

        # Post login
        login_data = {
            'user': username,
            'pass': password
        }
        response = session.post(login_url, data=login_data, timeout=30, allow_redirects=True)
        response.raise_for_status()

        # Check login result
        if 'login' in response.url.lower() and 'error' in response.text.lower():
            log_streamer.write_log(
                f"E-Claim login failed: Invalid credentials",
                'error',
                'system'
            )
            return jsonify({
                'success': False,
                'error': 'Login failed - invalid username or password'
            })

        # Check if we got redirected to a valid page
        if 'logout' in response.text.lower() or 'menu' in response.text.lower():
            log_streamer.write_log(
                f"E-Claim connection test successful",
                'success',
                'system'
            )
            return jsonify({
                'success': True,
                'message': 'Connection successful! Credentials are valid.'
            })

        # Uncertain result
        log_streamer.write_log(
            f"E-Claim connection test: uncertain result",
            'warning',
            'system'
        )
        return jsonify({
            'success': True,
            'message': 'Connection established. Please verify by downloading.'
        })

    except requests.exceptions.Timeout:
        log_streamer.write_log(
            f"E-Claim connection timeout",
            'error',
            'system'
        )
        return jsonify({
            'success': False,
            'error': 'Connection timeout - NHSO server is not responding'
        }), 504

    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response else 'Unknown'
        log_streamer.write_log(
            f"E-Claim server error: HTTP {status_code}",
            'error',
            'system'
        )
        return jsonify({
            'success': False,
            'error': f'NHSO server error (HTTP {status_code}). Server may be down or under maintenance.'
        }), 502

    except requests.exceptions.ConnectionError:
        log_streamer.write_log(
            f"E-Claim connection failed: Network error",
            'error',
            'system'
        )
        return jsonify({
            'success': False,
            'error': 'Cannot connect to NHSO server. Check your internet connection.'
        }), 503

    except Exception as e:
        log_streamer.write_log(
            f"E-Claim connection test failed: {str(e)}",
            'error',
            'system'
        )
        return jsonify({
            'success': False,
            'error': f'Connection test failed: {str(e)}'
        }), 500


@app.template_filter('naturalsize')
def naturalsize_filter(value):
    """Template filter for human-readable file sizes"""
    return humanize.naturalsize(value)


@app.template_filter('naturaltime')
def naturaltime_filter(value):
    """Template filter for human-readable timestamps"""
    try:
        dt = datetime.fromisoformat(value)
        return humanize.naturaltime(dt)
    except (ValueError, TypeError, AttributeError):
        return value


@app.template_filter('number_format')
def number_format_filter(value):
    """Template filter for number formatting with commas"""
    try:
        return "{:,}".format(int(value))
    except (ValueError, TypeError):
        return value


@app.route('/api/clear-all', methods=['POST'])
def clear_all_data():
    """Clear all data: files, history, and database (DANGER!)"""
    try:
        # 1. Delete all files in downloads subdirectories
        deleted_files = 0
        for subdir in ['rep', 'stm', 'smt']:
            subdir_path = Path('downloads') / subdir
            if subdir_path.exists():
                for file in subdir_path.glob('*.*'):
                    if file.is_file():
                        file.unlink()
                        deleted_files += 1

        # 2. Reset download history
        history_manager.save_history({'last_run': None, 'downloads': []})

        # 3. Clear database tables
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("TRUNCATE TABLE claim_rep_opip_nhso_item, claim_rep_orf_nhso_item, eclaim_imported_files RESTART IDENTITY CASCADE;")
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                app.logger.error(f"Database clear error: {e}")
                if conn:
                    conn.close()
                return jsonify({
                    'success': False,
                    'error': f'Database clear failed: {str(e)}'
                }), 500

        # 4. Clear realtime logs
        log_streamer.clear_logs()

        return jsonify({
            'success': True,
            'deleted_files': deleted_files,
            'message': 'All data cleared successfully'
        }), 200

    except Exception as e:
        app.logger.error(f"Clear all data error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/logs/stream')
def stream_logs():
    """Stream real-time logs via Server-Sent Events (SSE)"""
    def generate():
        try:
            for log_entry in log_streamer.stream_logs(tail=50):
                yield log_entry
        except GeneratorExit:
            pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive'
        }
    )


@app.route('/api/logs/clear', methods=['POST'])
def clear_logs():
    """Clear realtime log file"""
    try:
        log_streamer.clear_logs()
        return jsonify({'success': True, 'message': 'Logs cleared'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Job History API ====================

@app.route('/api/jobs')
def get_jobs():
    """Get recent job history"""
    try:
        job_type = request.args.get('type')  # download, import, schedule
        status = request.args.get('status')  # running, completed, failed
        limit = request.args.get('limit', 50, type=int)
        date_from = request.args.get('date_from')  # YYYY-MM-DD
        date_to = request.args.get('date_to')  # YYYY-MM-DD

        jobs = job_history_manager.get_recent_jobs(
            job_type=job_type,
            status=status,
            limit=min(limit, 200),
            date_from=date_from,
            date_to=date_to
        )

        return jsonify({
            'success': True,
            'jobs': jobs,
            'total': len(jobs)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/jobs/stats')
def get_job_stats():
    """Get job statistics"""
    try:
        days = request.args.get('days', 7, type=int)
        stats = job_history_manager.get_job_stats(days=min(days, 30))

        return jsonify({
            'success': True,
            'stats': stats,
            'period_days': days
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/jobs/<job_id>')
def get_job_detail(job_id):
    """Get specific job details"""
    try:
        jobs = job_history_manager.get_recent_jobs(limit=500)
        job = next((j for j in jobs if j['job_id'] == job_id), None)

        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        return jsonify({
            'success': True,
            'job': job
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== System Health Dashboard ====================

@app.route('/api/system/health')
def get_system_health():
    """
    Comprehensive system health dashboard
    Returns status of all system components
    """
    import psutil
    import shutil
    from pathlib import Path
    from config.database import DOWNLOADS_DIR

    health = {
        'success': True,
        'timestamp': datetime.now(TZ_BANGKOK).isoformat(),
        'overall_status': 'healthy',  # healthy, warning, critical
        'components': {}
    }

    issues = []

    # === 1. Database Connection ===
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            conn.close()
            health['components']['database'] = {
                'status': 'healthy',
                'message': 'Connected to PostgreSQL'
            }
        else:
            health['components']['database'] = {
                'status': 'critical',
                'message': 'Cannot connect to database'
            }
            issues.append('database')
    except Exception as e:
        health['components']['database'] = {
            'status': 'critical',
            'message': f'Database error: {str(e)}'
        }
        issues.append('database')

    # === 2. Disk Space ===
    try:
        downloads_dir = Path(DOWNLOADS_DIR)
        if downloads_dir.exists():
            disk = shutil.disk_usage(str(downloads_dir))
            free_gb = disk.free / (1024**3)
            total_gb = disk.total / (1024**3)
            used_percent = (disk.used / disk.total) * 100

            disk_status = 'healthy'
            if used_percent > 90:
                disk_status = 'critical'
                issues.append('disk')
            elif used_percent > 80:
                disk_status = 'warning'

            health['components']['disk'] = {
                'status': disk_status,
                'free_gb': round(free_gb, 2),
                'total_gb': round(total_gb, 2),
                'used_percent': round(used_percent, 1),
                'message': f'{round(free_gb, 1)} GB free ({round(100-used_percent, 1)}%)'
            }
        else:
            health['components']['disk'] = {
                'status': 'warning',
                'message': 'Downloads directory not found'
            }
    except Exception as e:
        health['components']['disk'] = {
            'status': 'warning',
            'message': f'Cannot check disk: {str(e)}'
        }

    # === 3. Running Processes ===
    pid_files = {
        'downloader': Path('/tmp/eclaim_downloader.pid'),
        'import': Path('/tmp/eclaim_import.pid'),
        'parallel': Path('/tmp/eclaim_parallel_download.pid'),
        'stm': Path('/tmp/eclaim_stm_downloader.pid'),
        'smt': Path('/tmp/eclaim_smt_fetch.pid')
    }

    running_processes = []
    stale_processes = []

    for name, pid_file in pid_files.items():
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    running_processes.append({
                        'name': name,
                        'pid': pid,
                        'status': proc.status(),
                        'started': datetime.fromtimestamp(proc.create_time()).isoformat()
                    })
                else:
                    stale_processes.append(name)
            except (ValueError, psutil.NoSuchProcess):
                stale_processes.append(name)

    process_status = 'healthy'
    if stale_processes:
        process_status = 'warning'

    health['components']['processes'] = {
        'status': process_status,
        'running': running_processes,
        'running_count': len(running_processes),
        'stale_pids': stale_processes,
        'message': f'{len(running_processes)} active' + (f', {len(stale_processes)} stale PIDs' if stale_processes else '')
    }

    # === 4. Recent Jobs (last 24 hours) ===
    try:
        recent_jobs = job_history_manager.get_recent_jobs(limit=100)
        now = datetime.now()

        jobs_24h = {
            'total': 0,
            'running': 0,
            'completed': 0,
            'failed': 0
        }

        for job in recent_jobs:
            try:
                started = datetime.fromisoformat(job['started_at'].replace('Z', '+00:00')) if isinstance(job['started_at'], str) else job['started_at']
                if started.tzinfo:
                    started = started.replace(tzinfo=None)
                if (now - started).total_seconds() < 86400:  # 24 hours
                    jobs_24h['total'] += 1
                    if job['status'] == 'running':
                        jobs_24h['running'] += 1
                    elif job['status'] in ('completed', 'completed_with_errors'):
                        jobs_24h['completed'] += 1
                    elif job['status'] == 'failed':
                        jobs_24h['failed'] += 1
            except (ValueError, TypeError):
                pass

        jobs_status = 'healthy'
        if jobs_24h['failed'] > jobs_24h['completed']:
            jobs_status = 'critical'
            issues.append('jobs')
        elif jobs_24h['failed'] > 0:
            jobs_status = 'warning'

        health['components']['jobs'] = {
            'status': jobs_status,
            'last_24h': jobs_24h,
            'message': f"{jobs_24h['completed']} completed, {jobs_24h['failed']} failed in 24h"
        }
    except Exception as e:
        health['components']['jobs'] = {
            'status': 'warning',
            'message': f'Cannot check jobs: {str(e)}'
        }

    # === 5. Files Statistics ===
    try:
        downloads_dir = Path(DOWNLOADS_DIR)
        if downloads_dir.exists():
            # Search recursively in subdirectories (rep/, stm/, smt/)
            xls_files = list(downloads_dir.glob('**/*.xls'))
            total_size = sum(f.stat().st_size for f in xls_files if f.exists())

            health['components']['files'] = {
                'status': 'healthy',
                'count': len(xls_files),
                'total_size_mb': round(total_size / (1024**2), 2),
                'message': f'{len(xls_files)} files ({round(total_size / (1024**2), 1)} MB)'
            }
        else:
            health['components']['files'] = {
                'status': 'warning',
                'count': 0,
                'message': 'Downloads directory not found'
            }
    except Exception as e:
        health['components']['files'] = {
            'status': 'warning',
            'message': f'Cannot check files: {str(e)}'
        }

    # === 6. Memory Usage ===
    try:
        memory = psutil.virtual_memory()
        mem_status = 'healthy'
        if memory.percent > 90:
            mem_status = 'critical'
            issues.append('memory')
        elif memory.percent > 80:
            mem_status = 'warning'

        health['components']['memory'] = {
            'status': mem_status,
            'used_percent': round(memory.percent, 1),
            'available_gb': round(memory.available / (1024**3), 2),
            'message': f'{round(memory.percent, 1)}% used, {round(memory.available / (1024**3), 1)} GB available'
        }
    except Exception as e:
        health['components']['memory'] = {
            'status': 'warning',
            'message': f'Cannot check memory: {str(e)}'
        }

    # === Determine Overall Status ===
    if 'database' in issues or 'memory' in issues:
        health['overall_status'] = 'critical'
    elif 'disk' in issues or 'jobs' in issues:
        health['overall_status'] = 'warning'
    elif any(c.get('status') == 'warning' for c in health['components'].values()):
        health['overall_status'] = 'warning'

    health['issues'] = issues

    return jsonify(health)


# ==================== Alert System API ====================

@app.route('/api/alerts')
def get_alerts():
    """Get system alerts"""
    try:
        include_dismissed = request.args.get('include_dismissed', 'false').lower() == 'true'
        alert_type = request.args.get('type')
        severity = request.args.get('severity')
        limit = request.args.get('limit', 50, type=int)

        alerts = alert_manager.get_alerts(
            include_dismissed=include_dismissed,
            alert_type=alert_type,
            severity=severity,
            limit=min(limit, 200)
        )

        return jsonify({
            'success': True,
            'alerts': alerts,
            'total': len(alerts)
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/unread-count')
def get_alerts_unread_count():
    """Get count of unread alerts"""
    try:
        count = alert_manager.get_unread_count()
        return jsonify({
            'success': True,
            'count': count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/<int:alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    """Mark an alert as read"""
    try:
        success = alert_manager.mark_as_read(alert_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/read-all', methods=['POST'])
def mark_all_alerts_read():
    """Mark all alerts as read"""
    try:
        affected = alert_manager.mark_all_as_read()
        return jsonify({
            'success': True,
            'affected': affected
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    """Dismiss an alert"""
    try:
        success = alert_manager.dismiss_alert(alert_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/dismiss-all', methods=['POST'])
def dismiss_all_alerts():
    """Dismiss all alerts"""
    try:
        affected = alert_manager.dismiss_all()
        return jsonify({
            'success': True,
            'affected': affected
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/alerts/check-health', methods=['POST'])
def check_health_and_alert():
    """
    Check system health and create alerts for any issues found.
    This can be called periodically or manually to update alerts.
    """
    import psutil
    import shutil
    from pathlib import Path
    from config.database import DOWNLOADS_DIR

    alerts_created = []

    try:
        # Check disk space
        downloads_dir = Path(DOWNLOADS_DIR)
        if downloads_dir.exists():
            disk = shutil.disk_usage(str(downloads_dir))
            used_percent = (disk.used / disk.total) * 100
            free_gb = disk.free / (1024**3)

            if used_percent > 80:
                alert_id = alert_manager.alert_disk_warning(used_percent, free_gb)
                if alert_id:
                    alerts_created.append({'type': 'disk_warning', 'id': alert_id})

        # Check memory
        memory = psutil.virtual_memory()
        if memory.percent > 80:
            available_gb = memory.available / (1024**3)
            alert_id = alert_manager.alert_memory_warning(memory.percent, available_gb)
            if alert_id:
                alerts_created.append({'type': 'memory_warning', 'id': alert_id})

        # Check stale processes
        pid_files = {
            'downloader': Path('/tmp/eclaim_downloader.pid'),
            'import': Path('/tmp/eclaim_import.pid'),
            'parallel': Path('/tmp/eclaim_parallel_download.pid'),
        }

        stale_processes = []
        for name, pid_file in pid_files.items():
            if pid_file.exists():
                try:
                    pid = int(pid_file.read_text().strip())
                    if not psutil.pid_exists(pid):
                        stale_processes.append(name)
                except (ValueError, psutil.NoSuchProcess):
                    stale_processes.append(name)

        if stale_processes:
            alert_id = alert_manager.alert_stale_process(stale_processes)
            if alert_id:
                alerts_created.append({'type': 'stale_process', 'id': alert_id})

        return jsonify({
            'success': True,
            'alerts_created': len(alerts_created),
            'details': alerts_created
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/system/sync-status', methods=['POST'])
def sync_system_status():
    """
    Comprehensive system status check and sync:
    1. Check if download processes are actually running
    2. Reset stuck progress files if processes are dead
    3. Sync files in folders with history records
    4. Return detailed status report
    """
    import json
    import os
    import psutil
    from pathlib import Path

    report = {
        'success': True,
        'timestamp': datetime.now(TZ_BANGKOK).isoformat(),
        'actions': [],
        'summary': {
            'processes_checked': 0,
            'processes_reset': 0,
            'files_synced': 0,
            'files_added': 0,
            'files_removed': 0
        }
    }

    # PID files to check
    pid_files = {
        'downloader': Path('/tmp/eclaim_downloader.pid'),
        'import': Path('/tmp/eclaim_import.pid'),
        'parallel': Path('/tmp/eclaim_parallel_download.pid'),
        'stm': Path('/tmp/eclaim_stm_downloader.pid'),
        'smt': Path('/tmp/eclaim_smt_fetch.pid')
    }

    # Progress files to reset if process is dead
    progress_files = {
        'parallel_download': Path('parallel_download_progress.json'),
        'bulk_download': Path('bulk_download_progress.json'),
        'import': Path('import_progress.json'),
        'download_iteration': Path('download_iteration_progress.json')
    }

    # === STEP 1: Check PID files and reset if processes are dead ===
    for name, pid_file in pid_files.items():
        report['summary']['processes_checked'] += 1
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                try:
                    process = psutil.Process(pid)
                    if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                        report['actions'].append({
                            'type': 'process_check',
                            'name': name,
                            'pid': pid,
                            'status': 'running',
                            'action': 'none'
                        })
                    else:
                        # Process is zombie, cleanup
                        pid_file.unlink()
                        report['actions'].append({
                            'type': 'process_check',
                            'name': name,
                            'pid': pid,
                            'status': 'zombie',
                            'action': 'pid_file_removed'
                        })
                        report['summary']['processes_reset'] += 1
                except psutil.NoSuchProcess:
                    # Process doesn't exist, cleanup
                    pid_file.unlink()
                    report['actions'].append({
                        'type': 'process_check',
                        'name': name,
                        'pid': pid,
                        'status': 'dead',
                        'action': 'pid_file_removed'
                    })
                    report['summary']['processes_reset'] += 1
            except (ValueError, IOError) as e:
                pid_file.unlink()
                report['actions'].append({
                    'type': 'process_check',
                    'name': name,
                    'status': 'invalid_pid_file',
                    'action': 'pid_file_removed',
                    'error': str(e)
                })
                report['summary']['processes_reset'] += 1

    # === STEP 2: Reset stuck progress files ===
    # Only reset if no related process is running
    downloader_running = any(
        Path(f'/tmp/eclaim_{name}.pid').exists() and _check_pid_alive(f'/tmp/eclaim_{name}.pid')
        for name in ['downloader', 'parallel_download']
    )

    for name, progress_file in progress_files.items():
        if progress_file.exists():
            try:
                with open(progress_file, 'r', encoding='utf-8') as f:
                    progress = json.load(f)

                status = progress.get('status', '')
                # Check if stuck (running/downloading but no process)
                if status in ['running', 'downloading', 'processing'] and not downloader_running:
                    # Reset progress file
                    if 'parallel' in name:
                        new_progress = {'status': 'idle', 'total': 0, 'completed': 0, 'failed': 0, 'skipped': 0}
                    elif 'bulk' in name:
                        new_progress = {'status': 'completed', 'total_iterations': 0, 'completed_iterations': 0}
                    elif 'import' in name:
                        new_progress = {'status': 'idle', 'running': False}
                    else:
                        new_progress = {'status': 'idle'}

                    with open(progress_file, 'w', encoding='utf-8') as f:
                        json.dump(new_progress, f, indent=2)

                    report['actions'].append({
                        'type': 'progress_reset',
                        'file': str(progress_file),
                        'old_status': status,
                        'new_status': new_progress.get('status'),
                        'action': 'reset'
                    })
                    report['summary']['processes_reset'] += 1
            except (json.JSONDecodeError, IOError) as e:
                report['actions'].append({
                    'type': 'progress_reset',
                    'file': str(progress_file),
                    'status': 'error',
                    'error': str(e)
                })

    # === STEP 3: Sync REP files with database ===
    # REP files are stored in downloads/rep/ subfolder
    rep_dir = Path('downloads/rep')

    if rep_dir.exists():
        try:
            conn = get_pooled_connection()
            cursor = conn.cursor()

            # Get existing filenames in database
            cursor.execute("SELECT filename FROM download_history WHERE download_type = 'rep'")
            db_filenames = {row[0] for row in cursor.fetchall()}

            # Get actual files on disk
            disk_files = {f.name for f in rep_dir.glob('*.xls') if f.is_file() and f.stat().st_size > 0}

            # Files on disk but not in database -> add to database
            missing_from_db = disk_files - db_filenames
            for filename in missing_from_db:
                file_path = rep_dir / filename
                cursor.execute("""
                    INSERT INTO download_history
                    (download_type, filename, file_size, file_path, file_exists, download_status)
                    VALUES ('rep', %s, %s, %s, TRUE, 'success')
                    ON CONFLICT (download_type, filename) DO NOTHING
                """, (filename, file_path.stat().st_size, str(file_path)))
                report['summary']['files_added'] += 1

            # Files in database but not on disk -> mark as file_exists=FALSE
            missing_from_disk = db_filenames - disk_files
            if missing_from_disk:
                for filename in missing_from_disk:
                    cursor.execute("""
                        UPDATE download_history
                        SET file_exists = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE download_type = 'rep' AND filename = %s
                    """, (filename,))
                report['summary']['files_removed'] += len(missing_from_disk)

            conn.commit()
            cursor.close()
            return_connection(conn)

            if missing_from_db or missing_from_disk:
                report['actions'].append({
                    'type': 'history_sync',
                    'target': 'REP files (database)',
                    'added': len(missing_from_db),
                    'removed': len(missing_from_disk)
                })

            report['summary']['files_synced'] = len(disk_files)

        except Exception as e:
            report['actions'].append({
                'type': 'history_sync',
                'target': 'REP files',
                'status': 'error',
                'error': str(e)
            })

    # === STEP 4: Sync Statement files with database ===
    # Statement files are stored in downloads/stm/ subfolder
    stm_dir = Path('downloads/stm')

    if stm_dir.exists():
        try:
            conn = get_pooled_connection()
            cursor = conn.cursor()

            # Get existing filenames in database
            cursor.execute("SELECT filename FROM download_history WHERE download_type = 'stm'")
            stm_db_filenames = {row[0] for row in cursor.fetchall()}

            # Get actual files on disk
            stm_disk_files = {f.name for f in stm_dir.glob('*.xls') if f.is_file() and f.stat().st_size > 0}

            # Files on disk but not in database -> add to database
            stm_missing_from_db = stm_disk_files - stm_db_filenames
            for filename in stm_missing_from_db:
                file_path = stm_dir / filename
                cursor.execute("""
                    INSERT INTO download_history
                    (download_type, filename, file_size, file_path, file_exists, download_status)
                    VALUES ('stm', %s, %s, %s, TRUE, 'success')
                    ON CONFLICT (download_type, filename) DO NOTHING
                """, (filename, file_path.stat().st_size, str(file_path)))
                report['summary']['files_added'] += 1

            # Files in database but not on disk -> mark as file_exists=FALSE
            stm_missing_from_disk = stm_db_filenames - stm_disk_files
            if stm_missing_from_disk:
                for filename in stm_missing_from_disk:
                    cursor.execute("""
                        UPDATE download_history
                        SET file_exists = FALSE, updated_at = CURRENT_TIMESTAMP
                        WHERE download_type = 'stm' AND filename = %s
                    """, (filename,))
                report['summary']['files_removed'] += len(stm_missing_from_disk)

            conn.commit()
            cursor.close()
            return_connection(conn)

            if stm_missing_from_db or stm_missing_from_disk:
                report['actions'].append({
                    'type': 'history_sync',
                    'target': 'Statement files (database)',
                    'added': len(stm_missing_from_db),
                    'removed': len(stm_missing_from_disk)
                })

        except Exception as e:
            report['actions'].append({
                'type': 'history_sync',
                'target': 'Statement files',
                'status': 'error',
                'error': str(e)
            })

    # Generate summary message
    actions_taken = report['summary']['processes_reset'] + report['summary']['files_added'] + report['summary']['files_removed']
    if actions_taken > 0:
        report['message'] = f"Sync completed: Reset {report['summary']['processes_reset']} processes, " \
                           f"Added {report['summary']['files_added']} files, " \
                           f"Removed {report['summary']['files_removed']} orphaned records"
    else:
        report['message'] = "All systems are in sync. No actions needed."

    return jsonify(report), 200


def _check_pid_alive(pid_file_path):
    """Helper to check if PID in file is alive"""
    import psutil
    try:
        pid_file = Path(pid_file_path)
        if not pid_file.exists():
            return False
        pid = int(pid_file.read_text().strip())
        process = psutil.Process(pid)
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (ValueError, IOError, psutil.NoSuchProcess):
        return False


@app.route('/api/schedule', methods=['GET', 'POST'])
def api_schedule():
    """Get or update unified schedule settings for all data types"""
    if request.method == 'GET':
        # Get current unified schedule settings
        schedule_settings = settings_manager.get_schedule_settings()

        # Get scheduled jobs info
        jobs = download_scheduler.get_all_jobs()

        return jsonify({
            'success': True,
            'settings': schedule_settings,
            'jobs': jobs
        })

    elif request.method == 'POST':
        # Update unified schedule settings
        try:
            data = request.get_json()

            enabled = data.get('schedule_enabled', False)
            times = data.get('schedule_times', [])
            auto_import = data.get('schedule_auto_import', True)
            schemes = data.get('schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])
            type_rep = data.get('schedule_type_rep', True)
            type_stm = data.get('schedule_type_stm', False)
            type_smt = data.get('schedule_type_smt', False)
            smt_vendor_id = data.get('schedule_smt_vendor_id', '')
            parallel_download = data.get('schedule_parallel_download', False)
            parallel_workers = data.get('schedule_parallel_workers', 3)

            # Validate at least one data type is selected when enabled
            if enabled and not type_rep and not type_stm and not type_smt:
                return jsonify({'success': False, 'error': 'กรุณาเลือกอย่างน้อย 1 ประเภทข้อมูล'}), 400

            # Validate SMT vendor ID if SMT is selected
            if enabled and type_smt:
                # If no vendor ID provided, try to get from SMT settings
                if not smt_vendor_id:
                    smt_settings = settings_manager.get_smt_settings()
                    smt_vendor_id = smt_settings.get('smt_vendor_id', '')
                if not smt_vendor_id:
                    return jsonify({'success': False, 'error': 'กรุณาระบุ Vendor ID สำหรับ SMT Budget'}), 400

            # Validate times format
            for time_config in times:
                if not isinstance(time_config, dict):
                    return jsonify({'success': False, 'error': 'Invalid time format'}), 400

                hour = time_config.get('hour')
                minute = time_config.get('minute')

                if hour is None or minute is None:
                    return jsonify({'success': False, 'error': 'Missing hour or minute'}), 400

                if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                    return jsonify({'success': False, 'error': 'Invalid hour or minute value'}), 400

            # Validate schemes
            valid_schemes = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']
            schemes = [s for s in schemes if s in valid_schemes]
            if not schemes:
                schemes = ['ucs']  # Default fallback

            # Save unified settings (including all data type flags)
            success = settings_manager.update_schedule_settings(
                enabled, times, auto_import, type_rep, type_stm, type_smt, smt_vendor_id,
                parallel_download, parallel_workers
            )
            if success:
                # Save schedule_schemes separately
                settings_manager.update_schedule_schemes(schemes)

            if not success:
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

            # Reinitialize unified scheduler
            init_scheduler()

            # Build data types string for log
            data_types = []
            if type_rep:
                data_types.append('REP')
            if type_stm:
                data_types.append('Statement')
            if type_smt:
                data_types.append('SMT')
            data_types_str = ', '.join(data_types) if data_types else 'None'

            parallel_info = f", parallel={parallel_workers}w" if parallel_download else ""
            log_streamer.write_log(
                f"✓ Unified schedule updated: {len(times)} times, types=[{data_types_str}], {len(schemes)} schemes, enabled={enabled}{parallel_info}",
                'success',
                'system'
            )

            return jsonify({'success': True, 'message': 'Schedule settings updated'})

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/schedule/test', methods=['POST'])
def test_schedule():
    """Trigger a test run of the scheduled download"""
    try:
        schedule_settings = settings_manager.get_schedule_settings()
        auto_import = schedule_settings.get('schedule_auto_import', True)

        # Run download manually
        download_scheduler._run_download(auto_import)

        return jsonify({
            'success': True,
            'message': 'Test download initiated'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# STM (Statement) Schedule Routes
# ============================================

@app.route('/api/stm/schedule', methods=['GET', 'POST'])
def api_stm_schedule():
    """Get or update STM schedule settings"""
    if request.method == 'GET':
        stm_settings = settings_manager.get_stm_schedule_settings()
        stm_jobs = [j for j in download_scheduler.get_all_jobs() if j['id'].startswith('stm_')]

        return jsonify({
            'success': True,
            **stm_settings,
            'active_jobs': stm_jobs
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            enabled = data.get('stm_schedule_enabled', False)
            times = data.get('stm_schedule_times', [])
            auto_import = data.get('stm_schedule_auto_import', True)
            schemes = data.get('stm_schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

            # Validate times format
            for time_config in times:
                if not isinstance(time_config, dict):
                    return jsonify({'success': False, 'error': 'Invalid time format'}), 400

                hour = time_config.get('hour')
                minute = time_config.get('minute')

                if hour is None or minute is None:
                    return jsonify({'success': False, 'error': 'Missing hour or minute'}), 400

                if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                    return jsonify({'success': False, 'error': 'Invalid hour or minute value'}), 400

            # Validate schemes
            valid_schemes = ['ucs', 'ofc', 'sss', 'lgo']
            schemes = [s.lower() for s in schemes if s.lower() in valid_schemes]
            if not schemes:
                schemes = ['ucs']

            # Save settings
            success = settings_manager.update_stm_schedule_settings(enabled, times, auto_import, schemes)
            if not success:
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

            # Update scheduler
            download_scheduler.remove_stm_jobs()

            if enabled and times:
                for time_config in times:
                    download_scheduler.add_stm_scheduled_download(
                        hour=time_config['hour'],
                        minute=time_config['minute'],
                        auto_import=auto_import,
                        schemes=schemes
                    )

            log_streamer.write_log(
                f"✓ STM Schedule updated: {len(times)} times, schemes={schemes}, enabled={enabled}",
                'success',
                'system'
            )

            return jsonify({'success': True, 'message': 'STM schedule settings updated'})

        except Exception as e:
            app.logger.error(f"Error updating STM schedule: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stm/schedule/test', methods=['POST'])
def test_stm_schedule():
    """Trigger a test run of STM download"""
    try:
        stm_settings = settings_manager.get_stm_schedule_settings()
        auto_import = stm_settings.get('stm_schedule_auto_import', True)
        schemes = stm_settings.get('stm_schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

        # Run download manually in background
        import threading
        thread = threading.Thread(
            target=download_scheduler._run_stm_download,
            args=(auto_import, schemes)
        )
        thread.start()

        return jsonify({
            'success': True,
            'message': f'STM test download initiated for schemes: {", ".join(schemes)}'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# SMT Budget Routes
# ============================================

@app.route('/smt-budget')
def smt_budget():
    """SMT Budget Report page"""
    smt_settings = settings_manager.get_smt_settings()
    smt_jobs = [j for j in download_scheduler.get_all_jobs() if j['id'].startswith('smt_')]

    # Get latest SMT data from database
    smt_summary = get_smt_summary()

    return render_template(
        'smt_budget.html',
        smt_settings=smt_settings,
        smt_jobs=smt_jobs,
        smt_summary=smt_summary
    )


def get_smt_summary():
    """Get SMT budget summary from database"""
    conn = get_db_connection()
    if not conn:
        return None

    try:
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'smt_budget_transfers'
            );
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            cursor.close()
            conn.close()
            return None

        # Get summary
        cursor.execute("""
            SELECT
                COUNT(*) as total_records,
                COALESCE(SUM(amount), 0) as total_amount,
                MIN(posting_date) as earliest_date,
                MAX(posting_date) as latest_date,
                MAX(created_at) as last_updated
            FROM smt_budget_transfers
        """)
        row = cursor.fetchone()

        # Get summary by fund group
        cursor.execute("""
            SELECT
                fund_group_desc,
                COUNT(*) as record_count,
                SUM(amount) as total_amount
            FROM smt_budget_transfers
            GROUP BY fund_group_desc
            ORDER BY SUM(amount) DESC
            LIMIT 10
        """)
        fund_groups = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            'total_records': row[0] or 0,
            'total_amount': float(row[1] or 0),
            'earliest_date': row[2],
            'latest_date': row[3],
            'last_updated': row[4].isoformat() if row[4] else None,
            'fund_groups': [
                {'name': r[0], 'count': r[1], 'amount': float(r[2] or 0)}
                for r in fund_groups
            ]
        }

    except Exception as e:
        app.logger.error(f"Error getting SMT summary: {e}")
        if conn:
            conn.close()
        return None


@app.route('/api/smt/fetch', methods=['POST'])
def smt_fetch():
    """Trigger SMT budget fetch"""
    job_id = None
    try:
        data = request.get_json() or {}
        vendor_id = data.get('vendor_id')
        start_date = data.get('start_date')  # dd/mm/yyyy BE format
        end_date = data.get('end_date')  # dd/mm/yyyy BE format
        budget_year = data.get('budget_year')  # Buddhist Era year
        save_db = data.get('save_db', True)
        export_format = data.get('export_format')  # 'json' or 'csv' or None

        if not vendor_id:
            # Try to get from settings
            smt_settings = settings_manager.get_smt_settings()
            vendor_id = smt_settings.get('smt_vendor_id')

        if not vendor_id:
            return jsonify({'success': False, 'error': 'Vendor ID is required'}), 400

        # Start job tracking
        try:
            job_id = job_history_manager.start_job(
                job_type='download',
                job_subtype='smt_fetch',
                parameters={
                    'vendor_id': vendor_id,
                    'budget_year': budget_year,
                    'start_date': start_date,
                    'end_date': end_date,
                    'save_db': save_db
                },
                triggered_by='manual'
            )
        except Exception as e:
            app.logger.warning(f"Could not start job tracking: {e}")

        # Import and run fetcher
        from smt_budget_fetcher import SMTBudgetFetcher

        date_info = ""
        if start_date and end_date:
            date_info = f" ({start_date} - {end_date})"
        elif budget_year:
            date_info = f" (FY {budget_year})"

        log_streamer.write_log(
            f"Starting SMT fetch for vendor {vendor_id}{date_info}...",
            'info',
            'smt'
        )

        fetcher = SMTBudgetFetcher(vendor_id=vendor_id)
        result = fetcher.fetch_budget_summary(
            budget_year=int(budget_year) if budget_year else None,
            start_date=start_date,
            end_date=end_date
        )
        records = result.get('datas', [])

        if not records:
            log_streamer.write_log(
                f"No records found for vendor {vendor_id}",
                'warning',
                'smt'
            )
            return jsonify({
                'success': True,
                'message': 'No records found',
                'records': 0
            })

        # Calculate summary
        summary = fetcher.calculate_summary(records)

        # Debug: show vendor_no format from first record
        if records:
            first_record = records[0]
            print(f"[DEBUG] SMT fetch - vendor_no format from API: vndrNo='{first_record.get('vndrNo')}'")

        # Save to database if requested
        saved_count = 0
        if save_db:
            saved_count = fetcher.save_to_database(records)
            log_streamer.write_log(
                f"Saved {saved_count} records to database",
                'success',
                'smt'
            )

        # Export if requested
        export_path = None
        if export_format == 'json':
            export_path = fetcher.export_to_json(records)
        elif export_format == 'csv':
            export_path = fetcher.export_to_csv(records)

        log_streamer.write_log(
            f"✓ SMT fetch completed: {len(records)} records, {summary['total_amount']:,.2f} Baht",
            'success',
            'smt'
        )

        # Complete job tracking
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='completed',
                    results={
                        'records': len(records),
                        'saved': saved_count,
                        'total_amount': summary['total_amount'],
                        'vendor_id': vendor_id,
                        'budget_year': budget_year
                    }
                )
            except Exception as e:
                app.logger.warning(f"Could not complete job tracking: {e}")

        return jsonify({
            'success': True,
            'records': len(records),
            'saved': saved_count,
            'total_amount': summary['total_amount'],
            'export_path': export_path
        })

    except Exception as e:
        # Mark job as failed
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='failed',
                    error_message=str(e)
                )
            except Exception:
                pass
        log_streamer.write_log(
            f"✗ SMT fetch failed: {str(e)}",
            'error',
            'smt'
        )
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/settings', methods=['GET', 'POST'])
def api_smt_settings():
    """Get or update SMT settings"""
    if request.method == 'GET':
        smt_settings = settings_manager.get_smt_settings()
        smt_jobs = [j for j in download_scheduler.get_all_jobs() if j['id'].startswith('smt_')]
        return jsonify({
            'success': True,
            'settings': smt_settings,
            'jobs': smt_jobs
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            vendor_id = data.get('smt_vendor_id', '').strip()
            schedule_enabled = data.get('smt_schedule_enabled', False)
            times = data.get('smt_schedule_times', [])
            auto_save_db = data.get('smt_auto_save_db', True)

            # Validate times format
            for time_config in times:
                if not isinstance(time_config, dict):
                    return jsonify({'success': False, 'error': 'Invalid time format'}), 400

                hour = time_config.get('hour')
                minute = time_config.get('minute')

                if hour is None or minute is None:
                    return jsonify({'success': False, 'error': 'Missing hour or minute'}), 400

                if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                    return jsonify({'success': False, 'error': 'Invalid hour or minute value'}), 400

            # Save settings
            success = settings_manager.update_smt_settings(
                vendor_id, schedule_enabled, times, auto_save_db
            )

            if not success:
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

            # Reinitialize SMT scheduler
            init_smt_scheduler()

            log_streamer.write_log(
                f"✓ SMT settings updated: vendor={vendor_id}, enabled={schedule_enabled}",
                'success',
                'system'
            )

            return jsonify({'success': True, 'message': 'SMT settings updated'})

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/fiscal-years')
def api_smt_fiscal_years():
    """Get available fiscal years in database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get distinct fiscal years from posting_date
        # posting_date format can be:
        # - "25671227" (yyyymmdd in Buddhist Era) - 8 digits
        # - "13/01/2569" (dd/mm/yyyy in Buddhist Era) - 10 chars
        # Extract year and month, determine fiscal year (Oct-Sep)
        # Month >= 10 means it belongs to next fiscal year
        cursor.execute("""
            SELECT DISTINCT
                CASE
                    WHEN LENGTH(posting_date) = 8 THEN
                        CASE
                            WHEN CAST(SUBSTRING(posting_date, 5, 2) AS INTEGER) >= 10
                            THEN CAST(SUBSTRING(posting_date, 1, 4) AS INTEGER) + 1
                            ELSE CAST(SUBSTRING(posting_date, 1, 4) AS INTEGER)
                        END
                    WHEN LENGTH(posting_date) = 10 THEN
                        CASE
                            WHEN CAST(SUBSTRING(posting_date, 4, 2) AS INTEGER) >= 10
                            THEN CAST(RIGHT(posting_date, 4) AS INTEGER) + 1
                            ELSE CAST(RIGHT(posting_date, 4) AS INTEGER)
                        END
                    ELSE NULL
                END as fiscal_year
            FROM smt_budget_transfers
            WHERE posting_date IS NOT NULL AND LENGTH(posting_date) >= 8
            ORDER BY fiscal_year DESC
        """)

        rows = cursor.fetchall()
        fiscal_years = [r[0] for r in rows if r[0] and r[0] > 2500]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'fiscal_years': fiscal_years
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'fiscal_years': []}), 200


@app.route('/api/smt/data')
def api_smt_data():
    """Get SMT budget data from database with optional date filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        fund_group = request.args.get('fund_group')
        start_date = request.args.get('start_date')  # Format: dd/mm/yyyy BE
        end_date = request.args.get('end_date')      # Format: dd/mm/yyyy BE

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Helper function to convert dd/mm/yyyy to sortable yyyymmdd format
        def to_sortable(date_str):
            if not date_str or len(date_str) < 10:
                return None
            parts = date_str.split('/')
            if len(parts) == 3:
                return f"{parts[2]}{parts[1]}{parts[0]}"
            return None

        # Build query with parameterized values
        conditions = []
        params = []

        if fund_group:
            conditions.append("fund_group_desc = %s")
            params.append(fund_group)

        # Convert dates to sortable format for string comparison
        # posting_date can be stored as:
        # - "25671227" (yyyymmdd) - 8 digits, already sortable
        # - "27/12/2567" (dd/mm/yyyy) - 10 chars, need transformation
        # We use CASE to handle both formats
        sortable_posting_date_expr = """
            CASE
                WHEN LENGTH(posting_date) = 8 THEN posting_date
                WHEN LENGTH(posting_date) = 10 THEN CONCAT(RIGHT(posting_date, 4), SUBSTRING(posting_date, 4, 2), SUBSTRING(posting_date, 1, 2))
                ELSE posting_date
            END
        """

        if start_date:
            sortable_start = to_sortable(start_date)
            if sortable_start:
                conditions.append(f"({sortable_posting_date_expr}) >= %s")
                params.append(sortable_start)

        if end_date:
            sortable_end = to_sortable(end_date)
            if sortable_end:
                conditions.append(f"({sortable_posting_date_expr}) <= %s")
                params.append(sortable_end)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        # Get total count
        count_query = "SELECT COUNT(*) FROM smt_budget_transfers " + where_clause
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated data - order by sortable date format
        offset = (page - 1) * per_page
        sortable_order_expr = """
            CASE
                WHEN LENGTH(posting_date) = 8 THEN posting_date
                WHEN LENGTH(posting_date) = 10 THEN CONCAT(RIGHT(posting_date, 4), SUBSTRING(posting_date, 4, 2), SUBSTRING(posting_date, 1, 2))
                ELSE posting_date
            END
        """
        select_query = """
            SELECT id, run_date, posting_date, ref_doc_no, vendor_no,
                   fund_name, fund_group_desc, amount, total_amount,
                   bank_name, payment_status, created_at
            FROM smt_budget_transfers
            """ + where_clause + f"""
            ORDER BY ({sortable_order_expr}) DESC, id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(select_query, params + [per_page, offset])

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        data = [
            {
                'id': r[0],
                'run_date': str(r[1]) if r[1] else None,
                'posting_date': r[2],
                'ref_doc_no': r[3],
                'vendor_no': r[4],
                'fund_name': r[5],
                'fund_group_desc': r[6],
                'amount': float(r[7] or 0),
                'total_amount': float(r[8] or 0),
                'bank_name': r[9],
                'payment_status': r[10],
                'created_at': r[11].isoformat() if r[11] else None
            }
            for r in rows
        ]

        return jsonify({
            'success': True,
            'data': data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/stats')
def api_smt_stats():
    """Get SMT budget statistics (record count and last sync time)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': True, 'record_count': 0, 'last_sync': None})

        cursor = conn.cursor()

        # Get total record count
        cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
        record_count = cursor.fetchone()[0]

        # Get last sync time (most recent created_at)
        cursor.execute("SELECT MAX(created_at) FROM smt_budget_transfers")
        last_sync_result = cursor.fetchone()[0]
        last_sync = str(last_sync_result) if last_sync_result else None

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'record_count': record_count,
            'last_sync': last_sync
        })

    except Exception as e:
        return jsonify({'success': True, 'record_count': 0, 'last_sync': None})


@app.route('/api/smt/clear', methods=['POST'])
def api_smt_clear():
    """Clear all SMT budget data from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Delete all SMT budget transfers
        cursor.execute("DELETE FROM smt_budget_transfers")
        deleted_count = cursor.rowcount

        conn.commit()
        cursor.close()
        conn.close()

        log_streamer.write_log(f"Cleared {deleted_count} SMT budget records", 'info', 'smt')

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} records'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/files')
def api_smt_files():
    """List SMT files in downloads/smt directory with pagination and filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Filter parameters
        fiscal_year = request.args.get('fiscal_year', type=int)
        start_month = request.args.get('start_month', type=int)
        end_month = request.args.get('end_month', type=int)
        filter_status = request.args.get('status', '').strip().lower()

        smt_dir = Path('downloads/smt')
        if not smt_dir.exists():
            return jsonify({
                'success': True,
                'files': [],
                'total': 0,
                'page': 1,
                'per_page': per_page,
                'total_pages': 0,
                'total_size': '0 B',
                'stats': {'total': 0, 'imported': 0, 'pending': 0}
            })

        all_files = []
        total_bytes = 0

        # Check which files have been imported by querying database
        imported_vendors = set()
        try:
            conn = get_pooled_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT vendor_no FROM smt_budget_transfers")
                imported_vendors = {row[0] for row in cursor.fetchall()}
                cursor.close()
                conn.close()
        except Exception:
            pass

        # Helper function for date range comparison
        def date_to_num(year, month):
            return year * 12 + month

        # Calculate fiscal year date range if specified
        fy_start_num = None
        fy_end_num = None
        if fiscal_year:
            # Thai fiscal year: Oct of prev year to Sep of fiscal year
            # FY 2569 = Oct 2568 - Sep 2569
            fy_start_year = fiscal_year - 1
            fy_end_year = fiscal_year

            if start_month:
                if start_month >= 10:
                    fy_start_num = date_to_num(fy_start_year, start_month)
                else:
                    fy_start_num = date_to_num(fy_end_year, start_month)
            else:
                fy_start_num = date_to_num(fy_start_year, 10)  # Default Oct

            if end_month:
                if end_month >= 10:
                    fy_end_num = date_to_num(fy_start_year, end_month)
                else:
                    fy_end_num = date_to_num(fy_end_year, end_month)
            else:
                fy_end_num = date_to_num(fy_end_year, 9)  # Default Sep

        for f in smt_dir.glob('smt_budget_*.csv'):
            stat = f.stat()

            # Extract vendor_id and date from filename: smt_budget_0000010670_20260113_050850.csv
            parts = f.name.replace('.csv', '').split('_')
            vendor_id = parts[2] if len(parts) >= 3 else None
            is_imported = vendor_id in imported_vendors if vendor_id else False

            # Extract download date (CE format: 20260113)
            file_year = None
            file_month = None
            if len(parts) >= 4:
                date_str = parts[3]
                if len(date_str) == 8:
                    try:
                        file_year_ce = int(date_str[:4])
                        file_month = int(date_str[4:6])
                        # Convert CE to BE
                        file_year = file_year_ce + 543
                    except ValueError:
                        pass

            # Apply fiscal year/month filter
            if fiscal_year and file_year and file_month:
                file_num = date_to_num(file_year, file_month)
                if fy_start_num and fy_end_num:
                    if file_num < fy_start_num or file_num > fy_end_num:
                        continue

            # Apply status filter
            if filter_status:
                if filter_status == 'imported' and not is_imported:
                    continue
                elif filter_status == 'pending' and is_imported:
                    continue

            total_bytes += stat.st_size

            all_files.append({
                'filename': f.name,
                'size': humanize.naturalsize(stat.st_size),
                'size_bytes': stat.st_size,
                'modified': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M'),
                'imported': is_imported,
                'file_year': file_year,
                'file_month': file_month
            })

        # Sort by modified date, newest first
        all_files.sort(key=lambda x: x['modified'], reverse=True)

        # Calculate stats from filtered files
        imported_count = sum(1 for f in all_files if f['imported'])
        pending_count = len(all_files) - imported_count

        # Calculate pagination
        total = len(all_files)
        total_pages = (total + per_page - 1) // per_page if total > 0 else 0
        offset = (page - 1) * per_page
        files = all_files[offset:offset + per_page]

        return jsonify({
            'success': True,
            'files': files,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_size': humanize.naturalsize(total_bytes),
            'stats': {
                'total': total,
                'imported': imported_count,
                'pending': pending_count
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/download', methods=['POST'])
def api_smt_download():
    """Download SMT budget data and export to CSV, with optional auto-import to database"""
    job_id = None
    try:
        data = request.get_json() or {}
        vendor_id = data.get('vendor_id')
        start_date = data.get('start_date')  # dd/mm/yyyy BE format
        end_date = data.get('end_date')      # dd/mm/yyyy BE format
        budget_source = data.get('budget_source', '')  # UC, OF, SS, LG, or empty for all
        budget_type = data.get('budget_type', '')      # OP, IP, PP, or empty for all
        auto_import = data.get('auto_import', False)   # Auto-import to database after download

        # Vendor ID is optional - empty means all in region
        if not vendor_id:
            # Try to get from settings if user hasn't explicitly cleared it
            smt_settings = settings_manager.get_smt_settings()
            default_vendor = smt_settings.get('smt_vendor_id')
            # Only use default if vendor_id is not explicitly provided as empty string
            if vendor_id is None and default_vendor:
                vendor_id = default_vendor

        # Start job tracking
        try:
            job_id = job_history_manager.start_job(
                job_type='download',
                job_subtype='smt',
                parameters={
                    'vendor_id': vendor_id,
                    'start_date': start_date,
                    'end_date': end_date,
                    'budget_source': budget_source,
                    'auto_import': auto_import
                },
                triggered_by='manual'
            )
        except Exception as e:
            app.logger.warning(f"Could not start job tracking: {e}")

        # Import and run fetcher
        from smt_budget_fetcher import SMTBudgetFetcher

        vendor_display = vendor_id if vendor_id else 'ทั้งหมด (All)'
        log_streamer.write_log(
            f"Starting SMT download for vendor {vendor_display} ({start_date} - {end_date})...",
            'info',
            'smt'
        )

        fetcher = SMTBudgetFetcher(vendor_id=vendor_id if vendor_id else None)
        result = fetcher.fetch_budget_summary(
            start_date=start_date,
            end_date=end_date,
            budget_source=budget_source
        )
        records = result.get('datas', [])

        if not records:
            return jsonify({
                'success': True,
                'message': 'No records found',
                'records': 0
            })

        # Calculate summary
        summary = fetcher.calculate_summary(records)

        # Auto-import to database if requested
        imported_count = 0
        new_records = 0
        export_path = None

        if auto_import:
            # Count records before import to detect new records
            count_before = 0
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
                    count_before = cursor.fetchone()[0]
                    cursor.close()
                    conn.close()
            except Exception:
                pass

            log_streamer.write_log(
                f"Auto-importing {len(records)} records to database...",
                'info',
                'smt'
            )
            imported_count = fetcher.save_to_database(records)

            # Count after import to detect new records
            count_after = 0
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM smt_budget_transfers")
                    count_after = cursor.fetchone()[0]
                    cursor.close()
                    conn.close()
            except Exception:
                pass

            new_records = count_after - count_before

            # Only create CSV if there are new records
            if new_records > 0:
                export_path = fetcher.export_to_csv(records)
                log_streamer.write_log(
                    f"✓ {new_records} new records, exported to {export_path}",
                    'success',
                    'smt'
                )
            else:
                log_streamer.write_log(
                    f"✓ No new records (all {len(records)} already exist), skipping CSV export",
                    'info',
                    'smt'
                )

            message = f'Fetched {len(records)} records: {new_records} new, {len(records) - new_records} existing'
        else:
            # Without auto-import, always create CSV
            export_path = fetcher.export_to_csv(records)
            message = f'Downloaded {len(records)} records'

        log_streamer.write_log(
            f"✓ SMT download completed",
            'success',
            'smt'
        )

        # Complete job tracking
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='completed',
                    results={
                        'records': len(records),
                        'new_records': new_records,
                        'imported': imported_count,
                        'total_amount': summary['total_amount'],
                        'export_path': export_path
                    }
                )
            except Exception as e:
                app.logger.warning(f"Could not complete job tracking: {e}")

        return jsonify({
            'success': True,
            'message': message,
            'records': len(records),
            'new_records': new_records,
            'imported': imported_count,
            'total_amount': summary['total_amount'],
            'export_path': export_path
        })

    except Exception as e:
        # Mark job as failed
        if job_id:
            try:
                job_history_manager.complete_job(
                    job_id=job_id,
                    status='failed',
                    error_message=str(e)
                )
            except Exception:
                pass
        log_streamer.write_log(f"✗ SMT download failed: {str(e)}", 'error', 'smt')
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/import/<path:filename>', methods=['POST'])
def api_smt_import_file(filename):
    """Import a specific SMT file to database"""
    try:
        # Sanitize filename
        safe_filename = secure_filename(filename)
        file_path = Path('downloads/smt') / safe_filename

        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Import CSV to database
        from smt_budget_fetcher import SMTBudgetFetcher
        import csv

        fetcher = SMTBudgetFetcher()
        records = []

        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)

        if not records:
            return jsonify({'success': False, 'error': 'No records in file'}), 400

        saved_count = fetcher.save_to_database(records)

        log_streamer.write_log(
            f"✓ Imported {saved_count} records from {safe_filename}",
            'success',
            'smt'
        )

        return jsonify({
            'success': True,
            'message': f'Imported {saved_count} records',
            'imported': saved_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/import-all', methods=['POST'])
def api_smt_import_all():
    """Import all SMT files to database"""
    try:
        smt_dir = Path('downloads/smt')
        if not smt_dir.exists():
            return jsonify({'success': False, 'error': 'No SMT files directory'}), 400

        from smt_budget_fetcher import SMTBudgetFetcher
        import csv

        fetcher = SMTBudgetFetcher()
        total_imported = 0
        files_processed = 0

        for f in smt_dir.glob('smt_budget_*.csv'):
            try:
                records = []
                with open(f, 'r', encoding='utf-8-sig') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        records.append(row)

                if records:
                    saved = fetcher.save_to_database(records)
                    total_imported += saved
                    files_processed += 1
            except Exception as e:
                log_streamer.write_log(
                    f"Error importing {f.name}: {str(e)}",
                    'error',
                    'smt'
                )

        log_streamer.write_log(
            f"✓ Imported {total_imported} records from {files_processed} files",
            'success',
            'smt'
        )

        return jsonify({
            'success': True,
            'message': f'Imported {total_imported} records from {files_processed} files',
            'imported': total_imported,
            'files': files_processed
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/delete/<path:filename>', methods=['DELETE'])
def api_smt_delete_file(filename):
    """Delete a specific SMT file"""
    try:
        # Sanitize filename
        safe_filename = secure_filename(filename)
        file_path = Path('downloads/smt') / safe_filename

        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Delete the file
        file_path.unlink()

        log_streamer.write_log(
            f"Deleted SMT file: {safe_filename}",
            'info',
            'smt'
        )

        return jsonify({
            'success': True,
            'message': f'Deleted {safe_filename}'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/smt/clear-files', methods=['POST'])
def api_smt_clear_files():
    """Clear all SMT files from downloads/smt directory"""
    try:
        smt_dir = Path('downloads/smt')
        if not smt_dir.exists():
            return jsonify({'success': True, 'deleted_count': 0})

        deleted_count = 0
        for f in smt_dir.glob('smt_budget_*.csv'):
            try:
                f.unlink()
                deleted_count += 1
            except Exception as e:
                app.logger.error(f"Error deleting {f.name}: {e}")

        log_streamer.write_log(
            f"Cleared {deleted_count} SMT files from downloads/smt",
            'info',
            'smt'
        )

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Deleted {deleted_count} SMT files'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Download History API ====================

@app.route('/api/download-history/clear', methods=['POST'])
def clear_download_history():
    """Clear download history from database"""
    try:
        data = request.get_json() or {}
        download_type = data.get('download_type', 'all')

        # Validate download_type
        valid_types = ['rep', 'stm', 'smt', 'all']
        if download_type not in valid_types:
            return jsonify({
                'success': False,
                'error': f'Invalid download_type. Valid: {valid_types}'
            }), 400

        from utils.download_history_db import DownloadHistoryDB

        with DownloadHistoryDB() as db:
            if download_type == 'all':
                # Delete all types
                total_deleted = 0
                for dtype in ['rep', 'stm', 'smt']:
                    db.cursor.execute(
                        "DELETE FROM download_history WHERE download_type = %s",
                        (dtype,)
                    )
                    total_deleted += db.cursor.rowcount
                db.conn.commit()
                deleted_count = total_deleted
            else:
                # Delete specific type
                db.cursor.execute(
                    "DELETE FROM download_history WHERE download_type = %s",
                    (download_type,)
                )
                deleted_count = db.cursor.rowcount
                db.conn.commit()

        # Also clear JSON files for backward compatibility
        json_files = {
            'rep': 'download_history.json',
            'stm': 'stm_download_history.json',
            'smt': 'smt_download_history.json',
        }

        if download_type == 'all':
            for jf in json_files.values():
                json_path = Path(jf)
                if json_path.exists():
                    json_path.unlink()
        else:
            json_path = Path(json_files.get(download_type, ''))
            if json_path.exists():
                json_path.unlink()

        log_streamer.write_log(
            f"Cleared {deleted_count} download history records (type: {download_type})",
            'info',
            'system'
        )

        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'Cleared {deleted_count} records from {download_type} history'
        })

    except Exception as e:
        app.logger.error(f"Error clearing download history: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-history/stats')
def get_download_history_stats():
    """Get download history statistics"""
    try:
        from utils.download_history_db import DownloadHistoryDB

        with DownloadHistoryDB() as db:
            stats = db.get_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-history/failed')
def get_failed_downloads():
    """Get list of failed downloads that can be retried"""
    try:
        from utils.download_history_db import DownloadHistoryDB

        download_type = request.args.get('type')  # Optional filter: rep, stm, smt
        limit = request.args.get('limit', 100, type=int)

        with DownloadHistoryDB() as db:
            failed = db.get_failed_downloads(download_type, limit)
            failed_count = db.get_failed_count(download_type)

        # Convert datetime objects to strings for JSON serialization
        for item in failed:
            for key in ['downloaded_at', 'last_attempt_at', 'imported_at', 'created_at', 'updated_at']:
                if key in item and item[key]:
                    item[key] = item[key].isoformat() if hasattr(item[key], 'isoformat') else str(item[key])

        return jsonify({
            'success': True,
            'failed': failed,
            'count': failed_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-history/reset-failed', methods=['POST'])
def reset_failed_downloads():
    """Reset all failed downloads for retry (changes status from 'failed' to 'pending')"""
    try:
        from utils.download_history_db import DownloadHistoryDB

        data = request.get_json() or {}
        download_type = data.get('download_type')  # Optional: rep, stm, smt

        with DownloadHistoryDB() as db:
            count = db.reset_all_failed(download_type)

        type_name = download_type.upper() if download_type else 'ทุกประเภท'
        return jsonify({
            'success': True,
            'message': f'Reset {count} failed downloads ({type_name}) for retry',
            'count': count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-history/failed', methods=['DELETE'])
def delete_failed_downloads():
    """Delete all failed download records"""
    try:
        from utils.download_history_db import DownloadHistoryDB

        data = request.get_json() or {}
        download_type = data.get('download_type')  # Optional: rep, stm, smt

        with DownloadHistoryDB() as db:
            count = db.delete_failed(download_type)

        type_name = download_type.upper() if download_type else 'ทุกประเภท'
        return jsonify({
            'success': True,
            'message': f'Deleted {count} failed download records ({type_name})',
            'count': count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/download-history/reset/<download_type>/<filename>', methods=['POST'])
def reset_single_failed_download(download_type, filename):
    """Reset a single failed download for retry"""
    try:
        from utils.download_history_db import DownloadHistoryDB

        with DownloadHistoryDB() as db:
            success = db.reset_for_retry(download_type, filename)

        if success:
            return jsonify({
                'success': True,
                'message': f'Reset {filename} for retry'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'No failed record found for {filename}'
            }), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def init_smt_scheduler():
    """Initialize SMT scheduler with saved settings"""
    try:
        smt_settings = settings_manager.get_smt_settings()

        # Clear existing SMT jobs
        download_scheduler.remove_smt_jobs()

        if smt_settings['smt_schedule_enabled'] and smt_settings['smt_vendor_id']:
            vendor_id = smt_settings['smt_vendor_id']
            auto_save_db = smt_settings['smt_auto_save_db']

            for time_config in smt_settings['smt_schedule_times']:
                hour = time_config.get('hour', 0)
                minute = time_config.get('minute', 0)
                download_scheduler.add_smt_scheduled_fetch(hour, minute, vendor_id, auto_save_db)

            log_streamer.write_log(
                f"✓ SMT scheduler initialized with {len(smt_settings['smt_schedule_times'])} jobs",
                'success',
                'system'
            )
    except Exception as e:
        app.logger.error(f"Error initializing SMT scheduler: {e}")


# ============================================
# Analytics Dashboard Routes
# ============================================

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
    - fiscal_year: Buddhist Era fiscal year (e.g., 2568 = Oct 2024 - Sep 2025)
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
        # Thai fiscal year runs Oct 1 to Sep 30
        # FY 2568 BE = Oct 2024 CE - Sep 2025 CE
        gregorian_year = fiscal_year - 543
        fy_start = f"{gregorian_year - 1}-10-01"
        fy_end = f"{gregorian_year}-09-30"
        where_clauses.append("dateadm >= %s AND dateadm <= %s")
        params.extend([fy_start, fy_end])
        filter_info['fiscal_year'] = fiscal_year
        filter_info['date_range'] = f"{fy_start} to {fy_end}"
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


@app.route('/analytics')
def analytics():
    """Analytics Dashboard - Comprehensive claim analysis"""
    return render_template('analytics.html')


@app.route('/claims')
def claims():
    """Claims Viewer - Detailed claim list with filters and drill-down"""
    return render_template('claims.html')


@app.route('/denial')
def denial():
    """Denial Root Cause Analysis - Charts and recommendations"""
    return render_template('denial.html')


@app.route('/strategic')
def strategic():
    """Strategic Analytics - Forecasting and YoY comparison"""
    return render_template('strategic.html')


@app.route('/api/analytics/fiscal-years')
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


@app.route('/api/analytics/filter-options')
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
        app.logger.error(f"Error in filter options: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/overview')
def api_analytics_overview():
    """Get overview statistics for analytics dashboard"""
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

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': overview})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/monthly-trend')
def api_analytics_monthly_trend():
    """Get monthly trend data"""
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

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': monthly_data, 'filter': filter_info})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/service-type')
def api_analytics_service_type():
    """Get claims by service type"""
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
            ORDER BY SUM(reimb_nhso) DESC NULLS LAST
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

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': service_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/fund')
def api_analytics_fund():
    """Get claims by fund type"""
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
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid,
                COUNT(DISTINCT hn) as patients
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY main_fund
            ORDER BY SUM(reimb_nhso) DESC NULLS LAST
            LIMIT 10
        """
        cursor.execute(query, filter_params)
        rows = cursor.fetchall()

        fund_data = [
            {
                'fund': row[0],
                'claims': row[1],
                'reimb': float(row[2] or 0),
                'paid': float(row[3] or 0),
                'patients': row[4]
            }
            for row in rows
        ]

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'data': fund_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/drg')
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


@app.route('/api/analytics/drug')
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
            ORDER BY SUM(d.reimb_amount) DESC NULLS LAST
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
            ORDER BY SUM(d.claim_amount) DESC NULLS LAST
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


@app.route('/api/analytics/instrument')
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
            ORDER BY SUM(i.claim_amount) DESC NULLS LAST
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


@app.route('/api/analytics/denial')
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


@app.route('/api/analytics/comparison')
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

@app.route('/api/analytics/claims')
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
            gregorian_year = fiscal_year - 543
            fy_start = f"{gregorian_year - 1}-10-01"
            fy_end = f"{gregorian_year}-09-30"
            where_clauses.append("dateadm >= %s AND dateadm <= %s")
            params.extend([fy_start, fy_end])

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
        app.logger.error(f"Error in claims detail: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/claim/<tran_id>')
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
        app.logger.error(f"Error getting claim {tran_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/denial-root-cause')
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
            gregorian_year = fiscal_year - 543
            fy_start = f"{gregorian_year - 1}-10-01"
            fy_end = f"{gregorian_year}-09-30"
            where_clauses.append("dateadm >= %s AND dateadm <= %s")
            params.extend([fy_start, fy_end])

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
        app.logger.error(f"Error in denial root cause: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/alerts')
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
        app.logger.error(f"Error getting alerts: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Phase 2: Strategic Analytics APIs
# ============================================

@app.route('/api/analytics/forecast')
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
        app.logger.error(f"Error in revenue forecast: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/yoy-comparison')
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
        app.logger.error(f"Error in YoY comparison: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/export/<report_type>')
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
                gregorian_year = fiscal_year - 543
                where_clauses.append("dateadm >= %s AND dateadm <= %s")
                params.extend([f"{gregorian_year - 1}-10-01", f"{gregorian_year}-09-30"])

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
        app.logger.error(f"Error exporting report: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/analytics/benchmark')
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
        app.logger.error(f"Error in benchmark comparison: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/benchmark')
def benchmark_page():
    """Benchmark Comparison page"""
    return render_template('benchmark.html')


@app.route('/api/benchmark/hospitals')
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
            # Convert Buddhist Era to Gregorian
            gregorian_year = fiscal_year_int - 543
            # Fiscal year starts Oct of previous year, ends Sep of the year
            start_date = f"{gregorian_year - 1}-10-01"
            end_date = f"{gregorian_year}-09-30"
            where_clause = "WHERE s.run_date >= %s AND s.run_date <= %s"
            params = [start_date, end_date]

        # Get summary by vendor from smt_budget_transfers with hospital name lookup
        ltrim_expr = "TRIM(LEADING '0' FROM s.vendor_no)" if DB_TYPE == 'mysql' else "LTRIM(s.vendor_no, '0')"
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
                h.hcode5 = {ltrim_expr}
                OR h.hcode5 = s.vendor_no
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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/benchmark/timeseries')
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
            # Convert Buddhist Era to Gregorian
            gregorian_year = fiscal_year_int - 543
            # Fiscal year starts Oct of previous year, ends Sep of the year
            start_date = f"{gregorian_year - 1}-10-01"
            end_date = f"{gregorian_year}-09-30"
            where_clause = "WHERE run_date >= %s AND run_date <= %s"
            params = [start_date, end_date]

            # If specific month range is specified
            if start_month and end_month:
                start_m = int(start_month)
                end_m = int(end_month)
                # Adjust dates based on month in fiscal year
                if start_m >= 10:
                    start_date = f"{gregorian_year - 1}-{start_m:02d}-01"
                else:
                    start_date = f"{gregorian_year}-{start_m:02d}-01"
                if end_m >= 10:
                    end_date = f"{gregorian_year - 1}-{end_m:02d}-28"
                else:
                    end_date = f"{gregorian_year}-{end_m:02d}-28"
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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/benchmark/hospital-years')
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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/benchmark/my-hospital')
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

        # Convert fiscal year to date range
        gregorian_year = fiscal_year - 543
        start_date = f"{gregorian_year - 1}-10-01"
        end_date = f"{gregorian_year}-09-30"

        # Previous year for YoY comparison
        prev_start_date = f"{gregorian_year - 2}-10-01"
        prev_end_date = f"{gregorian_year - 1}-09-30"

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
        total_hospitals = rank_row[0] if rank_row else 0
        hospitals_above = rank_row[1] if rank_row else 0
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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/benchmark/region-average')
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

        # Convert fiscal year to date range
        gregorian_year = fiscal_year - 543
        start_date = f"{gregorian_year - 1}-10-01"
        end_date = f"{gregorian_year}-09-30"

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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/benchmark/hospitals/<vendor_no>', methods=['DELETE'])
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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/benchmark/available-years')
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
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Phase 3: Predictive & AI Analytics
# ============================================

@app.route('/predictive')
def predictive():
    """Phase 3: Predictive Analytics page"""
    return render_template('predictive.html')


@app.route('/api/predictive/denial-risk')
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
        app.logger.error(f"Error in denial risk analysis: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predictive/anomalies')
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
            app.logger.warning(f"RW anomaly detection skipped: {rw_error}")
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
        app.logger.error(f"Error in anomaly detection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predictive/opportunities')
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
            app.logger.warning(f"Coding opportunities analysis skipped: {rw_error}")
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
        app.logger.error(f"Error in revenue opportunities: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predictive/insights')
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
        app.logger.error(f"Error generating insights: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# ML Prediction Endpoints
# ============================================

@app.route('/api/predictive/ml-info')
def api_ml_info():
    """Get ML model information and performance metrics"""
    try:
        from utils.ml.predictor import get_model_info
        info = get_model_info()
        return jsonify({'success': True, 'data': info})
    except Exception as e:
        app.logger.error(f"Error getting ML info: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predictive/ml-predict', methods=['POST'])
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
        app.logger.error(f"Error in ML prediction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predictive/ml-predict-batch', methods=['POST'])
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
        app.logger.error(f"Error in batch ML prediction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/predictive/ml-high-risk')
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
        app.logger.error(f"Error in ML high risk prediction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Reconciliation Routes
# ============================================

@app.route('/reconciliation')
def reconciliation():
    """Reconciliation Report page - Compare REP claims vs SMT payments"""
    from utils.reconciliation import ReconciliationReport

    # Get fiscal year from query param
    fiscal_year = request.args.get('fy', type=int)

    conn = get_db_connection()
    if not conn:
        return render_template(
            'reconciliation.html',
            error='Database connection failed',
            summary=None,
            monthly_data=[],
            fund_data=[],
            fiscal_years=[],
            selected_fy=None
        )

    try:
        report = ReconciliationReport(conn)

        # Get available fiscal years
        fiscal_years = report.get_available_fiscal_years()

        # Default to current fiscal year if not specified
        if not fiscal_year and fiscal_years:
            fiscal_year = fiscal_years[0]

        # Get data for selected fiscal year
        if fiscal_year:
            summary = report.get_summary_stats_by_fy(fiscal_year)
            monthly_data = report.get_monthly_reconciliation_by_fy(fiscal_year)
        else:
            summary = report.get_summary_stats()
            monthly_data = report.get_monthly_reconciliation()

        fund_data = report.get_fund_reconciliation()
        conn.close()

        return render_template(
            'reconciliation.html',
            summary=summary,
            monthly_data=monthly_data,
            fund_data=fund_data,
            fiscal_years=fiscal_years,
            selected_fy=fiscal_year
        )
    except Exception as e:
        app.logger.error(f"Reconciliation error: {e}")
        if conn:
            conn.close()
        return render_template(
            'reconciliation.html',
            error=str(e),
            summary=None,
            monthly_data=[],
            fund_data=[],
            fiscal_years=[],
            selected_fy=None
        )


@app.route('/api/reconciliation/fiscal-years')
def api_reconciliation_fiscal_years():
    """Get available fiscal years"""
    from utils.reconciliation import ReconciliationReport

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        report = ReconciliationReport(conn)
        fiscal_years = report.get_available_fiscal_years()
        conn.close()

        return jsonify({
            'success': True,
            'data': fiscal_years
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reconciliation/monthly')
def api_reconciliation_monthly():
    """Get monthly reconciliation data"""
    from utils.reconciliation import ReconciliationReport

    try:
        fiscal_year = request.args.get('fy', type=int)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        report = ReconciliationReport(conn)

        if fiscal_year:
            data = report.get_monthly_reconciliation_by_fy(fiscal_year)
        else:
            data = report.get_monthly_reconciliation()

        conn.close()

        return jsonify({
            'success': True,
            'fiscal_year': fiscal_year,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reconciliation/fund')
def api_reconciliation_fund():
    """Get fund-based reconciliation data"""
    from utils.reconciliation import ReconciliationReport

    try:
        month_be = request.args.get('month')  # Optional: YYYYMM in Buddhist Era

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        report = ReconciliationReport(conn)
        data = report.get_fund_reconciliation(month_be)
        conn.close()

        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reconciliation/summary')
def api_reconciliation_summary():
    """Get overall reconciliation summary stats"""
    from utils.reconciliation import ReconciliationReport

    try:
        fiscal_year = request.args.get('fy', type=int)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        report = ReconciliationReport(conn)

        if fiscal_year:
            summary = report.get_summary_stats_by_fy(fiscal_year)
        else:
            summary = report.get_summary_stats()

        conn.close()

        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reconciliation/rep-monthly')
def api_rep_monthly():
    """Get REP monthly summary by fund"""
    from utils.reconciliation import ReconciliationReport

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        report = ReconciliationReport(conn)
        data = report.get_rep_monthly_summary()
        conn.close()

        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reconciliation/smt-monthly')
def api_smt_monthly():
    """Get SMT monthly summary by fund"""
    from utils.reconciliation import ReconciliationReport

    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        report = ReconciliationReport(conn)
        data = report.get_smt_monthly_summary()
        conn.close()

        return jsonify({
            'success': True,
            'data': data
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/db/pool-status')
def api_db_pool_status():
    """Get database connection pool status"""
    try:
        status = get_pool_status()
        return jsonify({
            'success': True,
            'pool': status
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================
# Health Offices Master Data Management
# ============================================

@app.route('/health-offices')
def health_offices_page():
    """Redirect to Data Management - Health Offices tab"""
    return redirect(url_for('data_management') + '?tab=offices')


@app.route('/api/health-offices')
def api_health_offices_list():
    """Get health offices with filtering and pagination"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Get filter parameters
        search = request.args.get('search', '').strip()
        province = request.args.get('province', '')
        status = request.args.get('status', '')
        level = request.args.get('level', '')
        region = request.args.get('region', '')
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        offset = (page - 1) * per_page

        # Build query
        where_clauses = []
        params = []

        if search:
            like_op = "LIKE" if DB_TYPE == 'mysql' else "ILIKE"
            where_clauses.append(f"(name {like_op} %s OR hcode5 {like_op} %s OR hcode9 {like_op} %s)")
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        if province:
            where_clauses.append("province = %s")
            params.append(province)
        if status:
            where_clauses.append("status = %s")
            params.append(status)
        if level:
            where_clauses.append("hospital_level = %s")
            params.append(level)
        if region:
            where_clauses.append("health_region = %s")
            params.append(region)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        cursor.execute(f"SELECT COUNT(*) FROM health_offices WHERE {where_sql}", params)
        total = cursor.fetchone()[0]

        # Get data
        cursor.execute(f"""
            SELECT id, name, hcode5, hcode9, org_type, service_type, hospital_level,
                   actual_beds, status, health_region, province, district, address
            FROM health_offices
            WHERE {where_sql}
            ORDER BY name
            LIMIT %s OFFSET %s
        """, params + [per_page, offset])

        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        offices = []
        for row in rows:
            offices.append({
                'id': row[0],
                'name': row[1],
                'hcode5': row[2],
                'hcode9': row[3],
                'org_type': row[4],
                'service_type': row[5],
                'hospital_level': row[6],
                'actual_beds': row[7],
                'status': row[8],
                'health_region': row[9],
                'province': row[10],
                'district': row[11],
                'address': row[12]
            })

        return jsonify({
            'success': True,
            'data': offices,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health-offices/stats')
def api_health_offices_stats():
    """Get health offices statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        stats = {}

        # Total count
        cursor.execute("SELECT COUNT(*) FROM health_offices")
        stats['total'] = cursor.fetchone()[0]

        # By status
        cursor.execute("""
            SELECT status, COUNT(*) FROM health_offices
            WHERE status IS NOT NULL
            GROUP BY status ORDER BY COUNT(*) DESC
        """)
        stats['by_status'] = [{'status': r[0], 'count': r[1]} for r in cursor.fetchall()]

        # By hospital level
        cursor.execute("""
            SELECT hospital_level, COUNT(*) FROM health_offices
            WHERE hospital_level IS NOT NULL
            GROUP BY hospital_level ORDER BY COUNT(*) DESC
        """)
        stats['by_level'] = [{'level': r[0], 'count': r[1]} for r in cursor.fetchall()]

        # By region
        cursor.execute("""
            SELECT health_region, COUNT(*) FROM health_offices
            WHERE health_region IS NOT NULL
            GROUP BY health_region ORDER BY health_region
        """)
        stats['by_region'] = [{'region': r[0], 'count': r[1]} for r in cursor.fetchall()]

        # By province (top 10)
        cursor.execute("""
            SELECT province, COUNT(*) FROM health_offices
            WHERE province IS NOT NULL
            GROUP BY province ORDER BY COUNT(*) DESC LIMIT 10
        """)
        stats['by_province_top10'] = [{'province': r[0], 'count': r[1]} for r in cursor.fetchall()]

        # Get distinct values for filters
        cursor.execute("SELECT DISTINCT province FROM health_offices WHERE province IS NOT NULL ORDER BY province")
        stats['provinces'] = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT health_region FROM health_offices WHERE health_region IS NOT NULL ORDER BY health_region")
        stats['regions'] = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT DISTINCT hospital_level FROM health_offices WHERE hospital_level IS NOT NULL ORDER BY hospital_level")
        stats['levels'] = [r[0] for r in cursor.fetchall()]

        # Last import info
        cursor.execute("""
            SELECT import_date, filename, total_records, imported, import_mode
            FROM health_offices_import_log
            ORDER BY import_date DESC LIMIT 1
        """)
        last_import = cursor.fetchone()
        if last_import:
            stats['last_import'] = {
                'date': last_import[0].strftime('%Y-%m-%d %H:%M') if last_import[0] else None,
                'filename': last_import[1],
                'total_records': last_import[2],
                'imported': last_import[3],
                'mode': last_import[4]
            }

        cursor.close()
        conn.close()

        return jsonify({'success': True, 'stats': stats})

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health-offices/import', methods=['POST'])
def api_health_offices_import():
    """Import health offices from uploaded Excel file"""
    import time
    import pandas as pd
    from openpyxl import load_workbook
    import re
    import io

    def parse_formula_value(val):
        """Parse Excel formula value like ='32045' or =\"32045\" to plain value"""
        if val is None:
            return None
        val_str = str(val)
        # Match ="xxx" or ='xxx' format
        match = re.match(r'^=["\'](.*)["\']\s*$', val_str)
        if match:
            return match.group(1)
        return val_str if val_str.lower() not in ('none', 'nan', '') else None

    try:
        start_time = time.time()

        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        import_mode = request.form.get('mode', 'upsert')  # 'upsert' or 'replace'

        # Read Excel file using openpyxl to handle formula values
        file_bytes = io.BytesIO(file.read())
        wb = load_workbook(file_bytes, data_only=False)
        ws = wb.active

        # Get headers from first row
        headers = [cell.value for cell in ws[1]]

        # Read data rows with formula parsing for code columns
        data = []
        formula_columns = {'รหัส 9 หลักใหม่', 'รหัส 9 หลัก', 'รหัส 5 หลัก', 'เลขอนุญาตให้ประกอบสถานบริการสุขภาพ 11 หลัก'}

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
            row_data = {}
            for col_idx, cell in enumerate(row):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    if header in formula_columns:
                        row_data[header] = parse_formula_value(cell.value)
                    else:
                        row_data[header] = cell.value
            data.append(row_data)

        df = pd.DataFrame(data)

        # Column mapping
        column_map = {
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
            'อัพเดตล่าสุด(เริ่ม 05/09/2566)': 'source_updated_at'
        }

        # Rename columns
        df = df.rename(columns=column_map)

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Clear existing data if replace mode
        if import_mode == 'replace':
            cursor.execute("TRUNCATE TABLE health_offices RESTART IDENTITY")

        imported = 0
        updated = 0
        skipped = 0
        errors = 0
        total_records = len(df)

        for idx, row in df.iterrows():
            try:
                # Convert codes to string (handle both formula-parsed strings and numbers)
                def clean_code(val):
                    if pd.isna(val) or val is None or str(val).lower() in ('none', 'nan', ''):
                        return None
                    # Remove any whitespace and convert to string
                    return str(val).strip()

                hcode5 = clean_code(row.get('hcode5'))
                hcode9 = clean_code(row.get('hcode9'))
                hcode9_new = clean_code(row.get('hcode9_new'))

                # Parse dates
                def parse_date(val):
                    if pd.isna(val):
                        return None
                    if isinstance(val, str):
                        try:
                            # Try dd/mm/yyyy format
                            parts = val.split('/')
                            if len(parts) == 3:
                                day, month, year = parts
                                if int(year) > 2500:
                                    year = str(int(year) - 543)
                                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        except:
                            pass
                    return None

                established = parse_date(row.get('established_date'))
                closed = parse_date(row.get('closed_date'))
                source_updated = parse_date(row.get('source_updated_at'))

                # Prepare values
                values = {
                    'name': row.get('name'),
                    'hcode9_new': hcode9_new,
                    'hcode9': hcode9,
                    'hcode5': hcode5,
                    'license_no': clean_code(row.get('license_no')),
                    'org_type': row.get('org_type'),
                    'service_type': row.get('service_type'),
                    'affiliation': row.get('affiliation'),
                    'department': row.get('department'),
                    'hospital_level': row.get('hospital_level'),
                    'actual_beds': int(row['actual_beds']) if pd.notna(row.get('actual_beds')) else 0,
                    'status': row.get('status'),
                    'health_region': row.get('health_region'),
                    'address': row.get('address'),
                    'province_code': str(int(row['province_code'])) if pd.notna(row.get('province_code')) else None,
                    'province': row.get('province'),
                    'district_code': str(int(row['district_code'])) if pd.notna(row.get('district_code')) else None,
                    'district': row.get('district'),
                    'subdistrict_code': str(int(row['subdistrict_code'])) if pd.notna(row.get('subdistrict_code')) else None,
                    'subdistrict': row.get('subdistrict'),
                    'moo': row.get('moo'),
                    'postal_code': row.get('postal_code'),
                    'parent_code': row.get('parent_code'),
                    'established_date': established,
                    'closed_date': closed,
                    'source_updated_at': source_updated
                }

                # Skip if no name
                if not values['name'] or pd.isna(values['name']):
                    skipped += 1
                    continue

                # Insert or update
                if import_mode == 'replace' or not hcode5:
                    # Insert only
                    cursor.execute("""
                        INSERT INTO health_offices (
                            name, hcode9_new, hcode9, hcode5, license_no, org_type, service_type,
                            affiliation, department, hospital_level, actual_beds, status, health_region,
                            address, province_code, province, district_code, district, subdistrict_code,
                            subdistrict, moo, postal_code, parent_code, established_date, closed_date,
                            source_updated_at
                        ) VALUES (
                            %(name)s, %(hcode9_new)s, %(hcode9)s, %(hcode5)s, %(license_no)s, %(org_type)s,
                            %(service_type)s, %(affiliation)s, %(department)s, %(hospital_level)s,
                            %(actual_beds)s, %(status)s, %(health_region)s, %(address)s, %(province_code)s,
                            %(province)s, %(district_code)s, %(district)s, %(subdistrict_code)s,
                            %(subdistrict)s, %(moo)s, %(postal_code)s, %(parent_code)s, %(established_date)s,
                            %(closed_date)s, %(source_updated_at)s
                        )
                    """, values)
                    imported += 1
                else:
                    # Upsert by hcode5
                    cursor.execute("""
                        INSERT INTO health_offices (
                            name, hcode9_new, hcode9, hcode5, license_no, org_type, service_type,
                            affiliation, department, hospital_level, actual_beds, status, health_region,
                            address, province_code, province, district_code, district, subdistrict_code,
                            subdistrict, moo, postal_code, parent_code, established_date, closed_date,
                            source_updated_at
                        ) VALUES (
                            %(name)s, %(hcode9_new)s, %(hcode9)s, %(hcode5)s, %(license_no)s, %(org_type)s,
                            %(service_type)s, %(affiliation)s, %(department)s, %(hospital_level)s,
                            %(actual_beds)s, %(status)s, %(health_region)s, %(address)s, %(province_code)s,
                            %(province)s, %(district_code)s, %(district)s, %(subdistrict_code)s,
                            %(subdistrict)s, %(moo)s, %(postal_code)s, %(parent_code)s, %(established_date)s,
                            %(closed_date)s, %(source_updated_at)s
                        )
                        ON CONFLICT (hcode5) DO UPDATE SET
                            name = EXCLUDED.name,
                            hcode9_new = EXCLUDED.hcode9_new,
                            hcode9 = EXCLUDED.hcode9,
                            license_no = EXCLUDED.license_no,
                            org_type = EXCLUDED.org_type,
                            service_type = EXCLUDED.service_type,
                            affiliation = EXCLUDED.affiliation,
                            department = EXCLUDED.department,
                            hospital_level = EXCLUDED.hospital_level,
                            actual_beds = EXCLUDED.actual_beds,
                            status = EXCLUDED.status,
                            health_region = EXCLUDED.health_region,
                            address = EXCLUDED.address,
                            province_code = EXCLUDED.province_code,
                            province = EXCLUDED.province,
                            district_code = EXCLUDED.district_code,
                            district = EXCLUDED.district,
                            subdistrict_code = EXCLUDED.subdistrict_code,
                            subdistrict = EXCLUDED.subdistrict,
                            moo = EXCLUDED.moo,
                            postal_code = EXCLUDED.postal_code,
                            parent_code = EXCLUDED.parent_code,
                            established_date = EXCLUDED.established_date,
                            closed_date = EXCLUDED.closed_date,
                            source_updated_at = EXCLUDED.source_updated_at,
                            updated_at = CURRENT_TIMESTAMP
                    """, values)
                    if cursor.rowcount > 0:
                        imported += 1

            except Exception as e:
                errors += 1
                if errors <= 5:
                    app.logger.error(f"Error importing row {idx}: {e}")

        # Log import
        duration = time.time() - start_time
        cursor.execute("""
            INSERT INTO health_offices_import_log
            (filename, total_records, imported, updated, skipped, errors, import_mode, duration_seconds)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (file.filename, total_records, imported, updated, skipped, errors, import_mode, duration))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Import completed',
            'total': total_records,
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'errors': errors,
            'duration': round(duration, 2)
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health-offices/clear', methods=['POST'])
def api_health_offices_clear():
    """Clear all health offices data"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE health_offices RESTART IDENTITY")
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM health_offices")
        count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': 'All health offices data cleared',
            'remaining': count
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health-offices/lookup/<code>')
def api_health_offices_lookup(code):
    """Lookup health office by code (hcode5 or hcode9)"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, hcode5, hcode9, hcode9_new, org_type, service_type,
                   hospital_level, actual_beds, status, health_region, province,
                   district, address
            FROM health_offices
            WHERE hcode5 = %s OR hcode9 = %s OR hcode5 = %s
            LIMIT 1
        """, (code, code, code.zfill(5)))

        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({'success': False, 'error': 'Not found'}), 404

        return jsonify({
            'success': True,
            'data': {
                'id': row[0],
                'name': row[1],
                'hcode5': row[2],
                'hcode9': row[3],
                'hcode9_new': row[4],
                'org_type': row[5],
                'service_type': row[6],
                'hospital_level': row[7],
                'actual_beds': row[8],
                'status': row[9],
                'health_region': row[10],
                'province': row[11],
                'district': row[12],
                'address': row[13]
            }
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/files/update-status', methods=['GET'])
def get_files_update_status():
    """
    Get last update status for each file type and scheme combination.
    Returns information about when each type was last downloaded and if it's up-to-date.
    """
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Current month/year in Thai Buddhist Era
        today = datetime.now(TZ_BANGKOK)
        current_year_be = today.year + 543
        current_month = today.month

        # Get last download for each type/scheme combination
        # Use CTE to get the actual latest month from the latest year (not just current year)
        cursor.execute("""
            WITH latest_info AS (
                SELECT
                    download_type,
                    scheme,
                    fiscal_year,
                    service_month,
                    ROW_NUMBER() OVER (
                        PARTITION BY download_type, scheme
                        ORDER BY fiscal_year DESC, service_month DESC
                    ) as rn
                FROM download_history
                WHERE download_status = 'success' AND file_exists = TRUE
            ),
            agg_info AS (
                SELECT
                    download_type,
                    scheme,
                    MAX(downloaded_at) as last_download,
                    COUNT(*) as file_count
                FROM download_history
                WHERE download_status = 'success' AND file_exists = TRUE
                GROUP BY download_type, scheme
            )
            SELECT
                a.download_type,
                a.scheme,
                a.last_download,
                a.file_count,
                l.fiscal_year as latest_year,
                l.service_month as latest_month
            FROM agg_info a
            LEFT JOIN latest_info l ON l.download_type = a.download_type
                AND COALESCE(l.scheme, '') = COALESCE(a.scheme, '')
                AND l.rn = 1
            ORDER BY a.download_type, a.scheme
        """)

        rows = cursor.fetchall()

        # Build result structure
        status_by_type = {}
        for row in rows:
            dtype = row[0]  # rep, stm, smt
            scheme = row[1]
            last_download = row[2]
            file_count = row[3]
            latest_year = row[4]
            latest_month = row[5]

            if dtype not in status_by_type:
                status_by_type[dtype] = {
                    'total_files': 0,
                    'last_update': None,
                    'schemes': {}
                }

            # Determine if up-to-date (has file from current month & year)
            is_current = False
            if latest_year and latest_month:
                is_current = (latest_year == current_year_be and latest_month == current_month)

            scheme_key = scheme or 'unknown'
            status_by_type[dtype]['schemes'][scheme_key] = {
                'file_count': file_count,
                'last_download': last_download.isoformat() if last_download else None,
                'latest_fiscal_year': latest_year,
                'latest_month': latest_month,
                'is_current_month': is_current
            }
            status_by_type[dtype]['total_files'] += file_count

            # Update overall last_update for type
            if last_download:
                if status_by_type[dtype]['last_update'] is None:
                    status_by_type[dtype]['last_update'] = last_download
                elif last_download > datetime.fromisoformat(status_by_type[dtype]['last_update'].replace('Z', '+00:00')) if isinstance(status_by_type[dtype]['last_update'], str) else status_by_type[dtype]['last_update']:
                    status_by_type[dtype]['last_update'] = last_download

        # Convert datetime to string
        for dtype in status_by_type:
            if status_by_type[dtype]['last_update'] and hasattr(status_by_type[dtype]['last_update'], 'isoformat'):
                status_by_type[dtype]['last_update'] = status_by_type[dtype]['last_update'].isoformat()

        # Get overall summary
        cursor.execute("""
            SELECT
                download_type,
                COUNT(*) as total,
                MAX(downloaded_at) as last_download
            FROM download_history
            WHERE download_status = 'success' AND file_exists = TRUE
            GROUP BY download_type
        """)
        summary_rows = cursor.fetchall()

        summary = {}
        for row in summary_rows:
            summary[row[0]] = {
                'total_files': row[1],
                'last_download': row[2].isoformat() if row[2] else None
            }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'current_period': {
                'year_be': current_year_be,
                'year_ad': today.year,
                'month': current_month
            },
            'by_type': status_by_type,
            'summary': summary
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


def recover_stale_downloads():
    """
    Auto-recovery: Clean up stale/orphaned download progress files on server startup.
    This prevents the UI from being stuck showing 'downloading' when the process crashed.
    """
    from pathlib import Path
    import json

    progress_files = [
        ('parallel_download_progress.json', 'Parallel Download'),
        ('stm_download_progress.json', 'STM Download'),
    ]

    for filename, name in progress_files:
        progress_file = Path(filename)
        if not progress_file.exists():
            continue

        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress = json.load(f)

            status = progress.get('status')

            # If status is 'downloading', it was interrupted by server restart
            if status == 'downloading':
                # Mark as interrupted instead of deleting (preserve history)
                progress['status'] = 'interrupted'
                progress['interrupted_reason'] = 'Server restarted while download was in progress'
                progress['interrupted_at'] = datetime.now().isoformat()

                with open(progress_file, 'w', encoding='utf-8') as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)

                app.logger.warning(f"[Auto-Recovery] {name} was interrupted - marked as 'interrupted'")
                print(f"⚠️  [Auto-Recovery] {name} was interrupted by server restart")

        except Exception as e:
            app.logger.error(f"[Auto-Recovery] Error processing {filename}: {e}")


if __name__ == '__main__':
    import atexit

    # Initialize database connection pool
    try:
        init_pool()
        app.logger.info("Database connection pool initialized")
    except Exception as e:
        app.logger.warning(f"Failed to initialize connection pool: {e}")

    # Register cleanup on shutdown
    atexit.register(close_pool)

    # Auto-recovery: clean up stale downloads from previous crashes
    recover_stale_downloads()

    # Initialize schedulers on startup
    init_scheduler()
    init_smt_scheduler()
    app.run(host='0.0.0.0', port=5001, debug=True)
