"""Flask Web UI for E-Claim Downloader"""

from flask import Flask, render_template, jsonify, request, send_from_directory, redirect, url_for
from datetime import datetime
import humanize
from utils import HistoryManager, FileManager, DownloaderRunner

app = Flask(__name__)
app.config['SECRET_KEY'] = 'eclaim-downloader-secret-key-change-in-production'

# Initialize managers
history_manager = HistoryManager()
file_manager = FileManager()
downloader_runner = DownloaderRunner()


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
            dt = datetime.fromisoformat(file.get('download_date', ''))
            file['date_formatted'] = humanize.naturaltime(dt)
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

    # Sort by download date (most recent first)
    all_files = sorted(
        all_files,
        key=lambda d: d.get('download_date', ''),
        reverse=True
    )

    # Format for display
    for file in all_files:
        file['size_formatted'] = humanize.naturalsize(file.get('file_size', 0))
        try:
            dt = datetime.fromisoformat(file.get('download_date', ''))
            file['date_formatted'] = dt.strftime('%Y-%m-%d %H:%M:%S')
            file['date_relative'] = humanize.naturaltime(dt)
        except:
            file['date_formatted'] = file.get('download_date', 'Unknown')
            file['date_relative'] = 'Unknown'

    return render_template('files.html', files=all_files)


@app.route('/download/trigger', methods=['POST'])
def trigger_download():
    """Trigger downloader as background process"""
    result = downloader_runner.start()

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
