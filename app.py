"""Flask Web UI for E-Claim Downloader"""

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
from config.database import get_db_config

# Thailand timezone
TZ_BANGKOK = ZoneInfo('Asia/Bangkok')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'eclaim-downloader-secret-key-change-in-production'

# Initialize managers
history_manager = HistoryManager()
file_manager = FileManager()
downloader_runner = DownloaderRunner()
import_runner = ImportRunner()


def get_db_connection():
    """Get database connection"""
    try:
        db_config = get_db_config()
        return psycopg2.connect(**db_config)
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
        except:
            file['date_formatted'] = file.get('download_date', 'Unknown')

    # Check if downloader is running
    downloader_status = downloader_runner.get_status()

    return render_template(
        'dashboard.html',
        stats=stats,
        latest_files=latest_files,
        downloader_running=downloader_status['running']
    )


@app.route('/files')
def files():
    """File list view with all downloads"""
    all_files = history_manager.get_all_downloads()

    # Get import status from database
    import_status_map = get_import_status_map()

    # Sort by download date (most recent first)
    all_files = sorted(
        all_files,
        key=lambda d: d.get('download_date', ''),
        reverse=True
    )

    # Format for display and add import status
    for file in all_files:
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
        except:
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
    imported_count = sum(1 for f in all_files if f.get('imported', False))
    not_imported_count = len(all_files) - imported_count

    return render_template(
        'files.html',
        files=all_files,
        imported_count=imported_count,
        not_imported_count=not_imported_count
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


@app.route('/download/trigger/single', methods=['POST'])
def trigger_single_download():
    """Trigger download for specific month/year"""
    try:
        data = request.get_json()
        month = data.get('month')
        year = data.get('year')

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
        result = downloader_runner.start(month=month, year=year)

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
        result = downloader_runner.start_bulk(start_month, start_year, end_month, end_year)

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
    except:
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
                cursor.execute("TRUNCATE TABLE eclaim_claims, eclaim_op_refer, eclaim_imported_files RESTART IDENTITY CASCADE;")
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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
