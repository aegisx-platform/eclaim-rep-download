"""Flask Web UI for E-Claim Downloader"""

import os
from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for, Response, stream_with_context
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import humanize
import psycopg2
from pathlib import Path
import subprocess
import sys
from utils import HistoryManager, FileManager, DownloaderRunner
from utils.import_runner import ImportRunner
from utils.log_stream import log_streamer
from utils.settings_manager import SettingsManager
from utils.scheduler import download_scheduler
from config.database import get_db_config
from config.db_pool import init_pool, close_pool, get_connection as get_pooled_connection, get_pool_status

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

# Initialize managers
history_manager = HistoryManager()
file_manager = FileManager()
downloader_runner = DownloaderRunner()
import_runner = ImportRunner()
settings_manager = SettingsManager()


def init_scheduler():
    """Initialize scheduler with saved settings"""
    try:
        schedule_settings = settings_manager.get_schedule_settings()

        if schedule_settings['schedule_enabled']:
            # Clear existing jobs
            download_scheduler.clear_all_jobs()

            # Add scheduled jobs
            auto_import = schedule_settings['schedule_auto_import']
            for time_config in schedule_settings['schedule_times']:
                hour = time_config.get('hour', 0)
                minute = time_config.get('minute', 0)
                download_scheduler.add_scheduled_download(hour, minute, auto_import)

            log_streamer.write_log(
                f"✓ Scheduler initialized with {len(schedule_settings['schedule_times'])} jobs",
                'success',
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
        file['size_formatted'] = humanize.naturalsize(file.get('file_size', 0))
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
        key=lambda d: d.get('download_date', ''),
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
        file['size_formatted'] = humanize.naturalsize(file.get('file_size', 0))
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

        # Start bulk import process in background
        downloads_dir = Path('downloads')
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
            import re
            match = re.search(r'_(\d{4})(\d{2})\d{2}_', file.get('filename', ''))
            if match:
                file_year = int(match.group(1))
                file_month = int(match.group(2))

        if file_month == filter_month and file_year == filter_year:
            filtered_files.append(file)

    # Sort by download date (most recent first)
    filtered_files = sorted(
        filtered_files,
        key=lambda d: d.get('download_date', ''),
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

    # Format for display and add import status
    for file in paginated_files:
        file['size_formatted'] = humanize.naturalsize(file.get('file_size', 0))
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

        # Add import status
        filename = file.get('filename', '')
        if filename in import_status_map:
            file['import_status'] = import_status_map[filename]
            file['imported'] = True
        else:
            file['import_status'] = None
            file['imported'] = False

    # Count imported vs not imported
    imported_count = sum(1 for f in all_files if f.get('filename', '') in import_status_map)
    not_imported_count = len(all_files) - imported_count

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
                cursor.execute("SELECT COUNT(*) FROM smt_budget_items")
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

    # Calculate stats
    stats = {
        'total_files': len(all_files),
        'total_size': humanize.naturalsize(sum(f.get('file_size', 0) for f in all_files)),
        'imported_count': imported_count,
        'not_imported_count': not_imported_count
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


@app.route('/download/trigger/single', methods=['POST'])
def trigger_single_download():
    """Trigger download for specific month/year"""
    try:
        data = request.get_json()
        month = data.get('month')
        year = data.get('year')
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

        # Start downloader with parameters
        result = downloader_runner.start(month=month, year=year, auto_import=auto_import)

        if result['success']:
            return jsonify(result), 200
        else:
            status_code = 409 if 'already running' in result.get('error', '').lower() else 500
            return jsonify(result), status_code

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/download/trigger/bulk', methods=['POST'])
def trigger_bulk_download():
    """Trigger bulk download for date range"""
    try:
        data = request.get_json()

        start_month = data.get('start_month')
        start_year = data.get('start_year')
        end_month = data.get('end_month')
        end_year = data.get('end_year')
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

        # Start bulk downloader
        result = downloader_runner.start_bulk(start_month, start_year, end_month, end_year, auto_import)

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


@app.route('/api/date-range-stats')
def date_range_stats():
    """Get statistics grouped by month/year"""
    try:
        stats = history_manager.get_date_range_statistics()
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


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


@app.route('/api/settings/test-connection', methods=['POST'])
def test_eclaim_connection():
    """Test E-Claim login credentials"""
    import requests

    try:
        # Get credentials from settings
        current_settings = settings_manager.load_settings()
        username = current_settings.get('eclaim_username', '')
        password = current_settings.get('eclaim_password', '')

        if not username or not password:
            return jsonify({
                'success': False,
                'error': 'Credentials not configured. Please enter username and password first.'
            }), 400

        log_streamer.write_log(
            f"Testing E-Claim connection for user: {username}",
            'info',
            'system'
        )

        # Test login
        login_url = "https://eclaim.nhso.go.th/webComponent/main/MainWebAction.do"

        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'th,en;q=0.9',
        })

        # First, get the login page
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
        # 1. Delete all files in downloads directory
        downloads_dir = Path('downloads')
        deleted_files = 0
        for file in downloads_dir.glob('*.*'):
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


@app.route('/api/schedule', methods=['GET', 'POST'])
def api_schedule():
    """Get or update schedule settings"""
    if request.method == 'GET':
        # Get current schedule settings
        schedule_settings = settings_manager.get_schedule_settings()

        # Get scheduled jobs info
        jobs = download_scheduler.get_all_jobs()

        return jsonify({
            'success': True,
            'settings': schedule_settings,
            'jobs': jobs
        })

    elif request.method == 'POST':
        # Update schedule settings
        try:
            data = request.get_json()

            enabled = data.get('schedule_enabled', False)
            times = data.get('schedule_times', [])
            auto_import = data.get('schedule_auto_import', True)

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
            success = settings_manager.update_schedule_settings(enabled, times, auto_import)

            if not success:
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

            # Reinitialize scheduler
            init_scheduler()

            log_streamer.write_log(
                f"✓ Schedule updated: {len(times)} times, enabled={enabled}",
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

        return jsonify({
            'success': True,
            'records': len(records),
            'saved': saved_count,
            'total_amount': summary['total_amount'],
            'export_path': export_path
        })

    except Exception as e:
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


@app.route('/api/smt/data')
def api_smt_data():
    """Get SMT budget data from database"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        fund_group = request.args.get('fund_group')

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Build query with parameterized values
        # Note: where_clause contains only static SQL with %s placeholders, never user input
        where_clause = ""
        params = []
        if fund_group:
            where_clause = "WHERE fund_group_desc = %s"
            params.append(fund_group)

        # Get total count (parameterized query)
        count_query = "SELECT COUNT(*) FROM smt_budget_transfers " + where_clause
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated data (parameterized query)
        offset = (page - 1) * per_page
        select_query = """
            SELECT id, run_date, posting_date, ref_doc_no, vendor_no,
                   fund_name, fund_group_desc, amount, total_amount,
                   bank_name, payment_status, created_at
            FROM smt_budget_transfers
            """ + where_clause + """
            ORDER BY posting_date DESC, id DESC
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
    cursor.execute("""
        SELECT DISTINCT
            CASE
                WHEN EXTRACT(MONTH FROM dateadm) >= 10 THEN EXTRACT(YEAR FROM dateadm)::int + 544
                ELSE EXTRACT(YEAR FROM dateadm)::int + 543
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
                COALESCE(SUM(claim_net), 0) as total_claim_net,
                COUNT(DISTINCT hn) as unique_patients,
                COUNT(DISTINCT DATE_TRUNC('month', dateadm)) as active_months
            FROM claim_rep_opip_nhso_item
            WHERE """ + base_where
        cursor.execute(query, filter_params)
        row = cursor.fetchone()
        overview = {
            'total_claims': row[0] or 0,
            'total_reimb': float(row[1] or 0),
            'total_paid': float(row[2] or 0),
            'total_claim_net': float(row[3] or 0),
            'unique_patients': row[4] or 0,
            'active_months': row[5] or 0,
            'reimb_rate': round(float(row[2] or 0) / float(row[3] or 1) * 100, 2) if row[3] else 0,
            'filter': filter_info
        }

        # Drug summary with date filter (parameterized query)
        drug_where = date_filter if date_filter else "1=1"
        drug_query = """
            SELECT
                COUNT(*) as total_drugs,
                COALESCE(SUM(claim_amount), 0) as total_drug_cost
            FROM eclaim_drug
            WHERE """ + drug_where
        cursor.execute(drug_query, filter_params)
        drug_row = cursor.fetchone()
        overview['total_drug_items'] = drug_row[0] or 0
        overview['total_drug_cost'] = float(drug_row[1] or 0)

        # Instrument summary with date filter (parameterized query)
        inst_query = """
            SELECT
                COUNT(*) as total_instruments,
                COALESCE(SUM(claim_amount), 0) as total_instrument_cost
            FROM eclaim_instrument
            WHERE """ + drug_where
        cursor.execute(inst_query, filter_params)
        inst_row = cursor.fetchone()
        overview['total_instrument_items'] = inst_row[0] or 0
        overview['total_instrument_cost'] = float(inst_row[1] or 0)

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
        query = f"""
            SELECT
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid,
                COALESCE(SUM(claim_net), 0) as claim_net,
                COUNT(DISTINCT hn) as patients
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
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
                'claim_net': float(row[4] or 0),
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

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "generic_name IS NOT NULL AND generic_name != ''"
        all_where = "1=1"
        if date_filter:
            base_where += f" AND {date_filter}"
            all_where = date_filter

        # Top drugs by cost - use generic_name or trade_name
        query = f"""
            SELECT
                COALESCE(generic_name, trade_name, drug_code) as drug_name,
                COUNT(*) as prescriptions,
                COALESCE(SUM(quantity), 0) as total_qty,
                COALESCE(SUM(claim_amount), 0) as total_cost
            FROM eclaim_drug
            WHERE {base_where}
            GROUP BY COALESCE(generic_name, trade_name, drug_code)
            ORDER BY SUM(claim_amount) DESC NULLS LAST
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

        # Summary by drug_type
        cat_query = f"""
            SELECT
                COALESCE(drug_type, 'ไม่ระบุ') as category,
                COUNT(*) as items,
                COALESCE(SUM(claim_amount), 0) as total_cost
            FROM eclaim_drug
            WHERE {all_where}
            GROUP BY drug_type
            ORDER BY SUM(claim_amount) DESC NULLS LAST
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

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        base_where = "inst_name IS NOT NULL AND inst_name != ''"
        if date_filter:
            base_where += f" AND {date_filter}"

        # Top instruments by cost
        query = f"""
            SELECT
                inst_name,
                COUNT(*) as uses,
                COALESCE(SUM(claim_qty), 0) as total_qty,
                COALESCE(SUM(claim_amount), 0) as total_cost
            FROM eclaim_instrument
            WHERE {base_where}
            GROUP BY inst_name
            ORDER BY SUM(claim_amount) DESC NULLS LAST
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

        # Get date filter
        date_filter, filter_params, filter_info = get_analytics_date_filter()
        deny_where = "1=1"
        error_where = "error_code IS NOT NULL AND error_code != ''"
        if date_filter:
            deny_where = date_filter
            error_where += f" AND {date_filter}"

        # Denials by deny_code
        query = f"""
            SELECT
                COALESCE(deny_code, 'ไม่ระบุรหัส') as reason,
                COUNT(*) as cases,
                COALESCE(SUM(claim_amount), 0) as total_amount
            FROM eclaim_deny
            WHERE {deny_where}
            GROUP BY deny_code
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

        # Error codes from main claims table
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
        query = f"""
            SELECT
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COALESCE(SUM(claim_net), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as approved,
                COALESCE(SUM(paid), 0) as paid
            FROM claim_rep_opip_nhso_item
            WHERE {base_where}
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
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
    - sort: Sort field (dateadm, claim_net, reimb_nhso, error_code)
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
        allowed_sorts = ['dateadm', 'datedsc', 'claim_net', 'reimb_nhso', 'paid', 'error_code', 'tran_id']
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

        # Fund filter
        if fund:
            where_clauses.append("main_fund = %s")
            params.append(fund)

        # Service type filter
        if service_type:
            where_clauses.append("service_type = %s")
            params.append(service_type)

        # Search filter (tran_id, hn, pid)
        if search:
            where_clauses.append("(tran_id ILIKE %s OR hn ILIKE %s OR pid ILIKE %s)")
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
                claim_net, reimb_nhso, reimb_agency, paid,
                drg, rw,
                error_code,
                file_id
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
                'claim_net': float(r[11] or 0),
                'reimb_nhso': float(r[12] or 0),
                'reimb_agency': float(r[13] or 0),
                'paid': float(r[14] or 0),
                'drg': r[15],
                'rw': float(r[16] or 0) if r[16] else None,
                'error_code': r[17],
                'file_id': r[18],
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
                COALESCE(SUM(claim_net), 0) as total_denied_amount,
                COALESCE(SUM(reimb_nhso), 0) as total_reimb_lost
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause
        cursor.execute(stats_query, params)
        stats_row = cursor.fetchone()

        # Get total claims for rate calculation
        total_query = """
            SELECT COUNT(*), COALESCE(SUM(claim_net), 0)
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
                COALESCE(SUM(claim_net), 0) as total_amount,
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
                COALESCE(SUM(claim_net), 0) as total_amount
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
                COALESCE(SUM(claim_net), 0) as total_amount
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
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COUNT(*) as count,
                COALESCE(SUM(claim_net), 0) as total_amount
            FROM claim_rep_opip_nhso_item
            WHERE """ + where_clause + """ AND dateadm IS NOT NULL
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
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
                COALESCE(SUM(claim_net), 0) as total_claimed,
                COALESCE(SUM(paid), 0) as total_paid
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= DATE_TRUNC('month', CURRENT_DATE)
        """)
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
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= DATE_TRUNC('month', CURRENT_DATE) - INTERVAL '2 months'
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
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
        cursor.execute("""
            SELECT COUNT(*)
            FROM claim_rep_opip_nhso_item
            WHERE (paid IS NULL OR paid = 0)
            AND claim_net > 0
            AND dateadm < CURRENT_DATE - INTERVAL '30 days'
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
                TO_CHAR(dateadm, 'YYYY-MM') as month,
                COUNT(*) as claims,
                COALESCE(SUM(claim_net), 0) as claimed,
                COALESCE(SUM(reimb_nhso), 0) as reimb,
                COALESCE(SUM(paid), 0) as paid
            FROM claim_rep_opip_nhso_item
            WHERE dateadm IS NOT NULL
              AND dateadm >= CURRENT_DATE - INTERVAL '24 months'
            GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
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
            cursor.execute("SELECT MAX(EXTRACT(YEAR FROM dateadm)) FROM claim_rep_opip_nhso_item WHERE dateadm IS NOT NULL")
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
                COALESCE(SUM(claim_net), 0) as claimed,
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
        monthly_query = """
            SELECT
                EXTRACT(MONTH FROM dateadm) as month,
                COUNT(*) as claims,
                COALESCE(SUM(reimb_nhso), 0) as reimb
            FROM claim_rep_opip_nhso_item
            WHERE dateadm >= %s AND dateadm <= %s
            GROUP BY EXTRACT(MONTH FROM dateadm)
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
                return round(((current_val - prev_val) / prev_val) * 100, 2)
            return 0

        current_denial_rate = (current[4] / current[0] * 100) if current[0] > 0 else 0
        prev_denial_rate = (previous[4] / previous[0] * 100) if previous[0] > 0 else 0

        current_reimb_rate = (current[2] / current[1] * 100) if current[1] > 0 else 0
        prev_reimb_rate = (previous[2] / previous[1] * 100) if previous[1] > 0 else 0

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
                       service_type, main_fund, drg, rw, claim_net, reimb_nhso, paid, error_code
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
                       SUM(claim_net) as total_amount,
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
            query = """
                SELECT TO_CHAR(dateadm, 'YYYY-MM') as month,
                       COUNT(*) as claims,
                       SUM(claim_net) as claimed,
                       SUM(reimb_nhso) as reimb,
                       SUM(paid) as paid,
                       COUNT(CASE WHEN error_code IS NOT NULL AND error_code != '' THEN 1 END) as denials
                FROM claim_rep_opip_nhso_item
                WHERE dateadm IS NOT NULL
                GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
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

    # Initialize schedulers on startup
    init_scheduler()
    init_smt_scheduler()
    app.run(host='0.0.0.0', port=5001, debug=True)
