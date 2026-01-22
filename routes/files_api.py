"""
Blueprint for file management API routes

This blueprint handles all file-related API operations including:
- Listing files (REP, STM, SMT)
- Deleting files
- Uploading files
- Scanning files into history
- Re-downloading files
- Clearing all files by type
"""

import os
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
import humanize

from utils.logging_config import safe_format_exception

# Create blueprint
files_api_bp = Blueprint('files_api', __name__)


# ==================== General File API Routes ====================

@files_api_bp.route('/api/files')
def list_files_by_type():
    """
    List files from download_history with import status.

    Query parameters:
        type: 'rep' or 'stm' (required)
        per_page: number of files (default 100)

    Returns:
        {
            "success": true,
            "files": [
                {"filename": "...", "imported": true/false, "download_date": "..."}
            ]
        }
    """
    try:
        file_type = request.args.get('type', 'rep')
        per_page = request.args.get('per_page', 100, type=int)

        # Get database connection from app context
        from config.db_pool import get_connection as get_pooled_connection
        conn = get_pooled_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()
        db_type = os.environ.get('DB_TYPE', 'postgresql')

        # Get files from download_history with import status
        # Use different import tracking tables based on file type:
        # - REP files: eclaim_imported_files
        # - STM files: stm_imported_files
        if file_type == 'stm':
            # STM files use stm_imported_files table
            if db_type == 'mysql':
                query = """
                    SELECT dh.filename, dh.downloaded_at, dh.file_size,
                           COALESCE(dh.imported, 0) as imported,
                           sf.status as import_status,
                           sf.total_records
                    FROM download_history dh
                    LEFT JOIN stm_imported_files sf ON dh.filename = sf.filename
                    WHERE dh.download_type = %s
                    ORDER BY dh.downloaded_at DESC
                    LIMIT %s
                """
            else:
                query = """
                    SELECT dh.filename, dh.downloaded_at, dh.file_size,
                           COALESCE(dh.imported, false) as imported,
                           sf.status as import_status,
                           sf.total_records
                    FROM download_history dh
                    LEFT JOIN stm_imported_files sf ON dh.filename = sf.filename
                    WHERE dh.download_type = %s
                    ORDER BY dh.downloaded_at DESC
                    LIMIT %s
                """
        else:
            # REP files use eclaim_imported_files table
            if db_type == 'mysql':
                query = """
                    SELECT dh.filename, dh.downloaded_at, dh.file_size,
                           COALESCE(dh.imported, 0) as imported,
                           ef.status as import_status,
                           ef.total_records
                    FROM download_history dh
                    LEFT JOIN eclaim_imported_files ef ON dh.filename = ef.filename
                    WHERE dh.download_type = %s
                    ORDER BY dh.downloaded_at DESC
                    LIMIT %s
                """
            else:
                query = """
                    SELECT dh.filename, dh.downloaded_at, dh.file_size,
                           COALESCE(dh.imported, false) as imported,
                           ef.status as import_status,
                           ef.total_records
                    FROM download_history dh
                    LEFT JOIN eclaim_imported_files ef ON dh.filename = ef.filename
                    WHERE dh.download_type = %s
                    ORDER BY dh.downloaded_at DESC
                    LIMIT %s
                """

        cursor.execute(query, (file_type, per_page))
        rows = cursor.fetchall()

        files = []
        for row in rows:
            # Consider imported if either download_history.imported=true OR import table has completed status
            is_imported = bool(row[3]) or (row[4] == 'completed')
            files.append({
                'filename': row[0],
                'download_date': row[1].isoformat() if row[1] else None,
                'file_size': row[2],
                'imported': is_imported,
                'import_status': row[4],
                'total_records': row[5]
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'files': files,
            'total': len(files)
        })

    except Exception as e:
        current_app.logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการอ่านรายการไฟล์',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/files/scan', methods=['POST'])
def scan_files_to_history():
    """
    Scan files in downloads directory and register them in download_history database.
    This is useful when files are manually added to the directory.

    Request body (optional):
        {
            "types": ["rep", "stm"]  // defaults to both
        }

    Returns:
        {
            "success": true,
            "reports": [
                {"directory": "downloads/rep", "added": 807, "skipped": 0, "errors": 0},
                {"directory": "downloads/stm", "added": 123, "skipped": 0, "errors": 0}
            ],
            "total_added": 930
        }
    """
    try:
        # Get types from request or default to both
        data = request.get_json(silent=True) or {}
        types = data.get('types', ['rep', 'stm'])

        # Get managers from app config
        history_manager = current_app.config['history_manager']
        stm_history_manager = current_app.config['stm_history_manager']

        reports = []
        total_added = 0

        # Scan REP files
        if 'rep' in types:
            report = history_manager.scan_and_register_files('downloads/rep')
            reports.append(report)
            total_added += report.get('added', 0)

        # Scan STM files
        if 'stm' in types:
            report = stm_history_manager.scan_and_register_files('downloads/stm')
            reports.append(report)
            total_added += report.get('added', 0)

        return jsonify({
            'success': True,
            'reports': reports,
            'total_added': total_added,
            'message': f'Scanned {len(types)} directories, added {total_added} files to history'
        })

    except Exception as e:
        current_app.logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการสแกนไฟล์',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    """
    Upload E-Claim files (REP/STM/SMT) manually

    Accepts multipart/form-data with:
    - file: The uploaded file
    - type: File type (rep, stm, smt)
    - auto_import: Whether to trigger import after upload (default: true)

    Supported formats:
    - REP: .xls
    - STM: .xls
    - SMT: .xlsx, .xls, .csv

    Returns:
        {
            "success": true,
            "filename": "uploaded_file.xls",
            "type": "rep",
            "path": "downloads/rep/uploaded_file.xls",
            "import_triggered": true,
            "import_result": {...}  // If auto_import=true
        }
    """
    try:
        # Check if file exists in request
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Get file type (rep/stm/smt)
        file_type = request.form.get('type', '').lower()
        if file_type not in ['rep', 'stm', 'smt']:
            return jsonify({'success': False, 'error': 'Invalid file type. Must be rep, stm, or smt'}), 400

        # Get flags
        auto_import = request.form.get('auto_import', 'true').lower() == 'true'
        replace = request.form.get('replace', 'false').lower() == 'true'

        # Validate file extension
        filename = secure_filename(file.filename)
        file_ext = Path(filename).suffix.lower()

        valid_extensions = {
            'rep': ['.xls'],
            'stm': ['.xls'],
            'smt': ['.xlsx', '.xls', '.csv']
        }

        if file_ext not in valid_extensions[file_type]:
            return jsonify({
                'success': False,
                'error': f'Invalid file extension for {file_type.upper()}. Allowed: {", ".join(valid_extensions[file_type])}'
            }), 400

        # Create target directory
        target_dir = Path(f'downloads/{file_type}')
        target_dir.mkdir(parents=True, exist_ok=True)

        # Check if file already exists
        target_path = target_dir / filename
        if target_path.exists() and not replace:
            # File exists and user hasn't confirmed replacement
            return jsonify({
                'success': False,
                'error': 'file_exists',
                'message': f'ไฟล์ "{filename}" มีอยู่แล้ว ต้องการแทนที่หรือไม่?',
                'filename': filename,
                'existing_path': str(target_path)
            }), 409  # 409 Conflict

        # If replace=true and file exists, delete old file first
        if target_path.exists() and replace:
            current_app.logger.info(f"Replacing existing file: {filename}")
            target_path.unlink()

        # Save file
        file.save(str(target_path))

        current_app.logger.info(f"Uploaded {file_type.upper()} file: {filename}")

        result = {
            'success': True,
            'filename': filename,
            'type': file_type,
            'path': str(target_path),
            'import_triggered': auto_import
        }

        # Trigger import if requested
        if auto_import:
            try:
                if file_type == 'rep':
                    # Trigger REP import
                    import_runner = current_app.config['import_runner']
                    import_result = import_runner.start(str(target_path))
                    result['import_result'] = import_result
                elif file_type == 'stm':
                    # Trigger STM import
                    stm_import_runner = current_app.config['stm_import_runner']
                    import_result = stm_import_runner.start(str(target_path))
                    result['import_result'] = import_result
                elif file_type == 'smt':
                    # Trigger SMT import
                    # SMT imports are handled differently (via smt_budget_fetcher.py)
                    result['import_result'] = {
                        'success': False,
                        'message': 'SMT auto-import not yet implemented. Please import manually.'
                    }
            except Exception as e:
                current_app.logger.error(f"Error triggering import: {e}")
                result['import_result'] = {
                    'success': False,
                    'error': str(e)
                }

        return jsonify(result)

    except Exception as e:
        current_app.logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการอัพโหลดไฟล์',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/files/update-status', methods=['GET'])
def get_files_update_status():
    """
    Get last update status for each file type and scheme combination.
    Returns information about when each type was last downloaded and if it's up-to-date.
    """
    try:
        from config.db_pool import get_connection as get_pooled_connection
        from zoneinfo import ZoneInfo

        TZ_BANGKOK = ZoneInfo('Asia/Bangkok')

        conn = get_pooled_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cursor = conn.cursor()

        # Current month/year in Thai Buddhist Era
        today = datetime.now(TZ_BANGKOK)
        current_year_be = today.year + 543
        current_month = today.month

        # Get last download for each type/scheme combination
        # Use CTE to get the actual latest month from the latest year (not just current year)
        # Check database type for appropriate query syntax
        db_type = os.environ.get('DB_TYPE', 'postgresql').lower()

        if db_type == 'mysql':
            # MySQL compatible query (no CTE with window functions)
            cursor.execute("""
                SELECT
                    download_type,
                    scheme,
                    MAX(downloaded_at) as last_download,
                    COUNT(*) as file_count,
                    MAX(fiscal_year) as latest_year,
                    MAX(CASE WHEN fiscal_year = (
                        SELECT MAX(fiscal_year) FROM download_history h2
                        WHERE h2.download_type = download_history.download_type
                        AND COALESCE(h2.scheme, '') = COALESCE(download_history.scheme, '')
                        AND h2.file_exists = TRUE
                    ) THEN service_month ELSE NULL END) as latest_month
                FROM download_history
                WHERE file_exists = TRUE
                GROUP BY download_type, scheme
                ORDER BY download_type, scheme
            """)
        else:
            # PostgreSQL query with CTE
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
                    WHERE file_exists = TRUE
                ),
                agg_info AS (
                    SELECT
                        download_type,
                        scheme,
                        MAX(downloaded_at) as last_download,
                        COUNT(*) as file_count
                    FROM download_history
                    WHERE file_exists = TRUE
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
                status_by_type[dtype] = {}

            # Determine if up-to-date (has current month)
            is_current = (latest_year == current_year_be and latest_month == current_month)

            status_by_type[dtype][scheme or 'default'] = {
                'last_download': last_download.isoformat() if last_download else None,
                'file_count': file_count,
                'latest_year': latest_year,
                'latest_month': latest_month,
                'is_current': is_current,
                'current_period': f"{current_year_be}/{current_month:02d}"
            }

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'status': status_by_type,
            'current_year': current_year_be,
            'current_month': current_month
        })

    except Exception as e:
        current_app.logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการตรวจสอบสถานะไฟล์',
            'error_detail': str(e)
        }), 500


# ==================== REP File Routes ====================

@files_api_bp.route('/api/files/rep/<filename>', methods=['DELETE'])
@files_api_bp.route('/files/<filename>/delete', methods=['POST'])  # Legacy alias
def delete_file(filename):
    """Delete file from disk and history"""
    try:
        file_manager = current_app.config['file_manager']
        success = file_manager.delete_file(filename)

        if success:
            return jsonify({'success': True, 'message': 'File deleted'}), 200
        else:
            return jsonify({'success': False, 'message': 'File not found'}), 404

    except ValueError as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@files_api_bp.route('/api/files/re-download/<filename>', methods=['POST'])
def re_download_file(filename):
    """
    Re-download a file by extracting date from filename and triggering download

    Filename format: eclaim_{hospcode}_{file_type}_{YYYYMMDD}_{timestamp}.xls
    Example: eclaim_10670_IP_APPEAL_NHSO_25680913_103449525.xls
             → Year: 2568, Month: 09
    """
    try:
        import re
        from datetime import datetime

        # Extract date from filename (YYYYMMDD format)
        # Pattern: eclaim_{hospcode}_{file_type}_{YYYYMMDD}_{timestamp}.xls
        match = re.search(r'_(\d{8})_\d+\.xls$', filename)

        if not match:
            return jsonify({
                'success': False,
                'error': 'Invalid filename format. Cannot extract date.'
            }), 400

        date_str = match.group(1)  # e.g., "25680913"

        # Parse date (Buddhist Era)
        year = int(date_str[:4])    # 2568
        month = int(date_str[4:6])  # 09
        day = int(date_str[6:8])    # 13

        # Validate date
        if year < 2500 or year > 2600:
            return jsonify({
                'success': False,
                'error': f'Invalid year: {year}. Expected Buddhist Era year (2500-2600)'
            }), 400

        if month < 1 or month > 12:
            return jsonify({
                'success': False,
                'error': f'Invalid month: {month}'
            }), 400

        # Determine file type
        file_type = 'unknown'
        if '_OP_' in filename:
            file_type = 'OP'
        elif '_IP_APPEAL_NHSO_' in filename:
            file_type = 'IP_APPEAL_NHSO'
        elif '_IP_APPEAL_' in filename:
            file_type = 'IP_APPEAL'
        elif '_IP_' in filename:
            file_type = 'IP'
        elif '_ORF_' in filename:
            file_type = 'ORF'

        # Extract scheme (default to 'ucs')
        scheme = 'ucs'
        if 'SSS' in filename:
            scheme = 'sss'
        elif 'OFC' in filename:
            scheme = 'ofc'

        current_app.logger.info(f"Re-download request: {filename} → Year={year}, Month={month}, Type={file_type}, Scheme={scheme}")

        # Delete existing file
        file_manager = current_app.config['file_manager']
        file_path = file_manager.get_file_path(filename)
        if file_path.exists():
            file_path.unlink()
            current_app.logger.info(f"Deleted existing file: {filename}")

        # Delete from database history (if exists)
        try:
            from utils.download_manager import get_download_manager
            db = get_download_manager()
            # Note: We don't have a delete method, but the download will overwrite
        except Exception as e:
            current_app.logger.warning(f"Could not clean history: {e}")

        # Trigger download for that month (use global downloader_runner instance)
        downloader_runner = current_app.config['downloader_runner']
        result = downloader_runner.start(month=month, year=year, schemes=[scheme])

        if result['success']:
            return jsonify({
                'success': True,
                'message': f'Re-download started for {file_type}',
                'year': year,
                'month': month,
                'file_type': file_type,
                'scheme': scheme
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to start download')
            }), 500

    except Exception as e:
        current_app.logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการดาวน์โหลดไฟล์ใหม่',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/rep/clear-files', methods=['POST'])
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
        history_manager = current_app.config['history_manager']
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
        current_app.logger.error(f"Error clearing REP files: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการลบไฟล์ REP',
            'error_detail': str(e)
        }), 500


# ==================== STM File Routes ====================

@files_api_bp.route('/api/stm/files')
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
        current_app.logger.error(f"Error listing STM files: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการอ่านรายการไฟล์ STM',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/files/stm/<filename>', methods=['DELETE'])
@files_api_bp.route('/api/stm/delete/<filename>', methods=['DELETE'])  # Legacy alias
def delete_stm_file(filename):
    """Delete a Statement file"""
    try:
        from config.db_pool import get_connection as get_pooled_connection

        file_path = Path('downloads/stm') / filename
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Delete import record if exists (cascade will delete related records)
        try:
            conn = get_pooled_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stm_imported_files WHERE filename = %s", (filename,))
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            current_app.logger.warning(f"Could not delete STM import record: {e}")

        # Delete file
        file_path.unlink()

        return jsonify({'success': True, 'message': f'Deleted {filename}'})

    except Exception as e:
        current_app.logger.error(f"Error deleting STM file: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการลบไฟล์ STM',
            'error_detail': str(e)
        }), 500


# ==================== SMT File Routes ====================

@files_api_bp.route('/api/smt/files')
def api_smt_files():
    """List SMT files in downloads/smt directory with pagination and filtering"""
    try:
        from config.db_pool import get_connection as get_pooled_connection

        # Get hospital code from settings (required for SMT)
        settings_manager = current_app.config['settings_manager']
        hospital_code = settings_manager.get_hospital_code()
        if not hospital_code:
            return jsonify({
                'success': False,
                'error': 'กรุณาตั้งค่า Hospital Code ก่อนใช้งาน SMT',
                'error_code': 'NO_HOSPITAL_CODE',
                'redirect_url': '/settings/hospital'
            }), 400

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)

        # Filter parameters
        fiscal_year = request.args.get('fiscal_year', type=int)
        start_month = request.args.get('start_month', type=int)
        end_month = request.args.get('end_month', type=int)
        filter_status = request.args.get('status', '').strip().lower()
        # Default to filtering by hospital's vendor_id (can be overridden by query param)
        filter_vendor = request.args.get('vendor_id', hospital_code).strip()

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
                rows = cursor.fetchall()
                imported_vendors = {str(row[0]) for row in rows}
                cursor.close()
                conn.close()
        except Exception as e:
            current_app.logger.warning(f"Could not check imported vendors: {e}")

        # Scan CSV files in downloads/smt
        import re
        for csv_file in smt_dir.glob('smt_budget_*.csv'):
            # Extract vendor_id from filename: smt_budget_10670.csv
            match = re.search(r'smt_budget_(\d+)\.csv$', csv_file.name)
            if not match:
                continue

            vendor_id = match.group(1)

            # Apply vendor filter if specified
            if filter_vendor and vendor_id != filter_vendor:
                continue

            stat = csv_file.stat()
            total_bytes += stat.st_size

            # Check if imported
            is_imported = vendor_id in imported_vendors

            # Apply status filter
            if filter_status:
                if filter_status == 'imported' and not is_imported:
                    continue
                elif filter_status == 'pending' and is_imported:
                    continue

            file_info = {
                'filename': csv_file.name,
                'vendor_id': vendor_id,
                'size': stat.st_size,
                'size_formatted': humanize.naturalsize(stat.st_size),
                'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'imported': is_imported,
                'status': 'imported' if is_imported else 'pending'
            }

            all_files.append(file_info)

        # Sort by modified date desc
        all_files.sort(key=lambda x: x['modified'], reverse=True)

        # Calculate stats
        total_files = len(all_files)
        imported_count = sum(1 for f in all_files if f['imported'])
        pending_count = total_files - imported_count

        # Pagination
        total_pages = (total_files + per_page - 1) // per_page if total_files > 0 else 0
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_files = all_files[start_idx:end_idx]

        return jsonify({
            'success': True,
            'files': paginated_files,
            'total': total_files,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_size': humanize.naturalsize(total_bytes),
            'stats': {
                'total': total_files,
                'imported': imported_count,
                'pending': pending_count
            }
        })

    except Exception as e:
        current_app.logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการอ่านรายการไฟล์ SMT Budget',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/files/smt/<path:filename>', methods=['DELETE'])
@files_api_bp.route('/api/smt/delete/<path:filename>', methods=['DELETE'])  # Legacy alias
def api_smt_delete_file(filename):
    """Delete a specific SMT file"""
    try:
        from utils.log_stream import log_streamer

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
        current_app.logger.error(f"Error deleting SMT file: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการลบไฟล์ SMT Budget',
            'error_detail': str(e)
        }), 500


@files_api_bp.route('/api/smt/clear-files', methods=['POST'])
def api_smt_clear_files():
    """Clear all SMT files from downloads/smt directory"""
    try:
        from utils.log_stream import log_streamer

        smt_dir = Path('downloads/smt')
        if not smt_dir.exists():
            return jsonify({'success': True, 'deleted_count': 0})

        deleted_count = 0
        for f in smt_dir.glob('smt_budget_*.csv'):
            try:
                f.unlink()
                deleted_count += 1
            except Exception as e:
                current_app.logger.error(f"Error deleting {f.name}: {e}")

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
        current_app.logger.error(f"Error clearing SMT files: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการลบไฟล์ SMT Budget ทั้งหมด',
            'error_detail': str(e)
        }), 500
