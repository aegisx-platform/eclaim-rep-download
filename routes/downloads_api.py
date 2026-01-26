"""
Download API Routes Blueprint

Extracted from app.py to modularize download-related endpoints.
Includes REP downloads (single, bulk, parallel) and download history management.
"""

from flask import Blueprint, request, jsonify, current_app as app
from flask_login import login_required
from datetime import datetime, timedelta
import threading
from pathlib import Path

# Import managers and utilities
from utils import DownloaderRunner
from utils.history_manager_db import HistoryManagerDB
from utils.settings_manager import SettingsManager
from utils.log_stream import log_streamer
from utils.job_history_manager import job_history_manager
from utils.license_middleware import require_license_write_access
from utils.logging_config import safe_format_exception
from utils.rate_limiter import limit_api
from config.db_pool import get_connection, return_connection

# Create blueprint
downloads_api_bp = Blueprint('downloads_api', __name__)

# Get logger
import logging
logger = logging.getLogger(__name__)


# ==================== Download Trigger Routes ====================

@downloads_api_bp.route('/api/downloads/single', methods=['POST'])
@downloads_api_bp.route('/download/trigger', methods=['POST'])  # Legacy alias
@require_license_write_access
def trigger_download():
    """Trigger downloader as background process"""
    # Get global downloader_runner from app context
    downloader_runner = app.config.get('downloader_runner')

    data = request.get_json() or {}
    auto_import = data.get('auto_import', False)

    result = downloader_runner.start(auto_import=auto_import)

    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500


@downloads_api_bp.route('/api/downloads/status')
@downloads_api_bp.route('/download/status')  # Legacy alias
def download_status():
    """Get downloader status"""
    downloader_runner = app.config.get('downloader_runner')
    status = downloader_runner.get_status()
    return jsonify(status)


@downloads_api_bp.route('/api/downloads/month', methods=['POST'])
@downloads_api_bp.route('/download/trigger/single', methods=['POST'])  # Legacy alias
@require_license_write_access
def trigger_single_download():
    """Trigger download for specific month/year and schemes"""
    try:
        downloader_runner = app.config.get('downloader_runner')
        settings_manager = app.config.get('settings_manager')

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


@downloads_api_bp.route('/api/downloads/bulk', methods=['POST'])
@downloads_api_bp.route('/download/trigger/bulk', methods=['POST'])  # Legacy alias
@require_license_write_access
def trigger_bulk_download():
    """Trigger bulk download for date range and schemes"""
    try:
        settings_manager = app.config.get('settings_manager')

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

        # IMPORTANT: Use ParallelDownloadBridge instead of downloader_runner
        # This ensures all downloads go through DownloadManager v2
        from utils.download_manager.parallel_bridge import get_parallel_bridge

        bridge = get_parallel_bridge()

        # Get credentials
        credentials = settings_manager.get_all_credentials()
        enabled_creds = [c for c in credentials if c.get('enabled', True)]

        if not enabled_creds:
            return jsonify({'success': False, 'error': 'E-Claim credentials not configured'}), 400

        # For bulk download: download first month only using Bridge
        # (Full bulk download with date range requires sequential session handling)
        # User should use "Parallel Download" checkbox for better performance
        params = {
            'fiscal_year': start_year,
            'service_month': start_month,
            'scheme': schemes[0],  # First scheme only
            'max_workers': 3,
            'auto_import': auto_import,
            'source_type': 'rep'
        }

        try:
            session_id = bridge.start_download(enabled_creds, params)

            # Start background thread
            from utils.parallel_downloader import ParallelDownloader

            def run_download():
                job_id = job_history_manager.start_job(
                    job_type='download',
                    job_subtype='bulk',
                    parameters={
                        'start_month': start_month,
                        'start_year': start_year,
                        'end_month': end_month,
                        'end_year': end_year,
                        'schemes': schemes,
                        'auto_import': auto_import,
                        'session_id': session_id
                    },
                    triggered_by='manual'
                )

                try:
                    downloader = bridge.active_downloaders.get(session_id)
                    if downloader:
                        result = downloader.run()

                        job_history_manager.complete_job(
                            job_id=job_id,
                            status='completed' if result.get('failed', 0) == 0 else 'completed_with_errors',
                            results={
                                'total_files': result.get('total', 0),
                                'success_files': result.get('completed', 0),
                                'failed_files': result.get('failed', 0),
                                'skipped_files': result.get('skipped', 0)
                            }
                        )
                except Exception as e:
                    app.logger.error(f"Error in bulk download: {e}", exc_info=True)
                    job_history_manager.complete_job(
                        job_id=job_id,
                        status='failed',
                        error_message=str(e)
                    )

            thread = threading.Thread(target=run_download, daemon=True)
            thread.start()

            return jsonify({
                'success': True,
                'message': f'Download started for month {start_month}/{start_year}',
                'session_id': session_id,
                'note': 'Bulk download now uses DownloadManager v2'
            }), 200

        except ValueError as e:
            return jsonify({'success': False, 'error': str(e)}), 409

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@downloads_api_bp.route('/api/downloads/bulk/progress')
@downloads_api_bp.route('/download/bulk/progress')  # Legacy alias
def bulk_progress():
    """Get real-time bulk download progress from DownloadManager v2"""
    try:
        from utils.download_manager.parallel_bridge import get_parallel_bridge

        bridge = get_parallel_bridge()
        active_sessions = bridge.get_active_sessions()

        # Find REP session (bulk download is REP)
        rep_sessions = [s for s in active_sessions if s.source_type == 'rep']

        if not rep_sessions:
            # No active REP download - return legacy format for UI compatibility
            return jsonify({
                'running': False,
                'status': 'idle',
                'message': 'No active download'
            })

        # Get progress for the most recent active session
        session = rep_sessions[0]
        progress = bridge.get_progress(session.id)

        if progress:
            # Add extra fields for UI compatibility
            progress['current_month'] = {
                'month': session.service_month,
                'year': session.fiscal_year
            }
            progress['completed_months'] = 1 if progress.get('status') == 'completed' else 0
            progress['total_months'] = 1

            # For iteration tracking (used by UI)
            progress['iteration_current_idx'] = progress.get('processed', 0)
            progress['iteration_total_files'] = progress.get('total', 0)
            progress['completed_iterations'] = progress.get('processed', 0)
            progress['total_iterations'] = progress.get('total', 0)
            progress['current_files'] = progress.get('iteration_current_idx', 0)

            return jsonify(progress)
        else:
            return jsonify({
                'running': True,
                'status': 'downloading',
                'session_id': session.id,
                'message': 'Fetching progress...'
            })

    except Exception as e:
        app.logger.error(f"Error getting bulk progress: {e}", exc_info=True)
        return jsonify({'running': False, 'error': str(e)}), 500


@downloads_api_bp.route('/api/downloads/cancel', methods=['POST'])
@downloads_api_bp.route('/download/bulk/cancel', methods=['POST'])  # Legacy alias
def cancel_bulk_download():
    """Cancel a running bulk download"""
    try:
        downloader_runner = app.config.get('downloader_runner')
        result = downloader_runner.stop()
        return jsonify(result)

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Parallel Download Routes ====================

@downloads_api_bp.route('/api/downloads/parallel', methods=['POST'])
@downloads_api_bp.route('/api/download/parallel', methods=['POST'])  # Legacy alias
@require_license_write_access
def trigger_parallel_download():
    """Trigger parallel download with multiple browser sessions (using DownloadManager v2)"""
    try:
        from utils.download_manager.parallel_bridge import get_parallel_bridge

        settings_manager = app.config.get('settings_manager')
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

        # Use ParallelDownloadBridge (creates session in database)
        bridge = get_parallel_bridge()

        params = {
            'fiscal_year': year,
            'service_month': month,
            'scheme': scheme,
            'max_workers': max_workers,
            'auto_import': auto_import,
            'source_type': 'rep'
        }

        # Start download (creates session in DownloadManager)
        try:
            session_id = bridge.start_download(enabled_creds, params)
            app.logger.info(f"Created download session: {session_id}")
        except ValueError as e:
            # Session already running
            return jsonify({'success': False, 'error': str(e)}), 409

        # Run in background thread
        from utils.parallel_downloader import ParallelDownloader

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
                    'auto_import': auto_import,
                    'session_id': session_id
                },
                triggered_by='manual'
            )

            try:
                # Get downloader from bridge (already monkey-patched)
                downloader = bridge.active_downloaders.get(session_id)
                if not downloader:
                    raise ValueError(f"Downloader not found for session {session_id}")

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


@downloads_api_bp.route('/api/downloads/parallel/progress')
@downloads_api_bp.route('/api/download/parallel/progress')  # Legacy alias
def parallel_download_progress():
    """Get parallel download progress from DownloadManager (database)"""
    try:
        from utils.download_manager import get_download_manager
        from datetime import datetime, timedelta

        manager = get_download_manager()
        active_sessions = manager.get_active_sessions()

        # Find active REP session (parallel download is typically REP)
        for progress_info in active_sessions:
            if progress_info.source_type == 'rep':
                # Return progress in legacy format for UI compatibility
                return jsonify({
                    'running': True,
                    'status': progress_info.status.value,
                    'total': progress_info.total_discovered,
                    'completed': progress_info.downloaded,
                    'skipped': progress_info.skipped,
                    'failed': progress_info.failed,
                    'processed': progress_info.processed,
                    'session_id': progress_info.session_id
                })

        # Check for recently completed REP session (within last 10 seconds)
        # This ensures UI shows final 100% progress before switching to idle
        conn = None
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get most recent completed REP session
            cursor.execute("""
                SELECT id, total_discovered, downloaded, skipped, failed,
                       processed, status, completed_at
                FROM download_sessions
                WHERE source_type = 'rep'
                  AND status IN ('completed', 'failed', 'cancelled')
                  AND completed_at >= %s
                ORDER BY completed_at DESC
                LIMIT 1
            """, (datetime.now() - timedelta(seconds=10),))

            row = cursor.fetchone()
            cursor.close()

            if row:
                # Return final progress (running=False so UI stops polling after showing 100%)
                return_connection(conn)
                return jsonify({
                    'running': False,
                    'status': row[6] or 'completed',
                    'total': row[1] or 0,
                    'completed': row[2] or 0,
                    'skipped': row[3] or 0,
                    'failed': row[4] or 0,
                    'processed': row[5] or 0,
                    'session_id': row[0]
                })

            return_connection(conn)
        except Exception as e:
            if conn:
                return_connection(conn)
            logger.warning(f"Could not check recent sessions: {e}")

        # No active or recent REP session
        return jsonify({
            'running': False,
            'status': 'idle'
        })

    except Exception as e:
        logger.error(f"Error getting download progress: {e}", exc_info=True)
        return jsonify({'running': False, 'error': str(e)})


@downloads_api_bp.route('/api/downloads/parallel/cancel', methods=['POST'])
@downloads_api_bp.route('/api/download/parallel/cancel', methods=['POST'])  # Legacy alias
def cancel_parallel_download():
    """Cancel parallel download session via DownloadManager"""
    try:
        from utils.download_manager import get_download_manager

        manager = get_download_manager()
        active_sessions = manager.get_active_sessions()

        # Find active REP session
        for progress_info in active_sessions:
            if progress_info.source_type == 'rep':
                # Cancel the session
                manager.cancel_session(progress_info.session_id)
                return jsonify({
                    'success': True,
                    'message': 'Download cancelled',
                    'session_id': progress_info.session_id
                })

        # No active download
        return jsonify({
            'success': True,
            'message': 'No download in progress'
        })

    except Exception as e:
        logger.error(f"Error cancelling download: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


# ==================== Download History Routes ====================

@downloads_api_bp.route('/api/history/downloads/clear', methods=['POST'])
@downloads_api_bp.route('/api/download-history/clear', methods=['POST'])  # Legacy alias
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


@downloads_api_bp.route('/api/history/downloads/stats')
@downloads_api_bp.route('/api/download-history/stats')  # Legacy alias
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


@downloads_api_bp.route('/api/history/downloads/failed')
@downloads_api_bp.route('/api/download-history/failed')  # Legacy alias
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


@downloads_api_bp.route('/api/history/downloads/reset-failed', methods=['POST'])
@downloads_api_bp.route('/api/download-history/reset-failed', methods=['POST'])  # Legacy alias
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


@downloads_api_bp.route('/api/history/downloads/failed', methods=['DELETE'])
@downloads_api_bp.route('/api/download-history/failed', methods=['DELETE'])  # Legacy alias
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


@downloads_api_bp.route('/api/history/downloads/reset/<download_type>/<filename>', methods=['POST'])
@downloads_api_bp.route('/api/download-history/reset/<download_type>/<filename>', methods=['POST'])  # Legacy alias
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


# ==================== Download Manager V2 Routes ====================

@downloads_api_bp.route('/api/v2/downloads/sessions', methods=['POST'])
@login_required
@limit_api
def api_v2_create_session():
    """Create new download session (v2 API)"""
    try:
        from utils.download_manager import get_download_manager

        data = request.get_json()
        source_type = data.get('source_type')  # rep, stm, smt
        params = {
            'fiscal_year': data.get('fiscal_year'),
            'service_month': data.get('service_month'),
            'scheme': data.get('scheme'),
            'max_workers': data.get('max_workers', 1),
            'auto_import': data.get('auto_import', False)
        }

        # Validate source type
        if source_type not in ('rep', 'stm', 'smt'):
            return jsonify({
                'success': False,
                'error': 'Invalid source_type. Must be: rep, stm, or smt'
            }), 400

        # Check if can start
        manager = get_download_manager()
        can_start, reason = manager.can_start_download(source_type)

        if not can_start:
            return jsonify({
                'success': False,
                'error': reason,
                'existing_sessions': [
                    p.to_dict() for p in manager.get_active_sessions()
                    if p.source_type == source_type
                ]
            }), 409  # Conflict

        # Create session
        session_id = manager.create_session(source_type, params)

        return jsonify({
            'success': True,
            'session_id': session_id,
            'message': f'{source_type.upper()} download session created',
            'progress_url': f'/api/v2/downloads/sessions/{session_id}/progress'
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@downloads_api_bp.route('/api/v2/downloads/sessions/<session_id>/progress')
@login_required
def api_v2_get_session_progress(session_id):
    """Get progress for a specific session"""
    try:
        from utils.download_manager import get_download_manager

        manager = get_download_manager()
        progress = manager.get_progress(session_id)

        if not progress:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        return jsonify({
            'success': True,
            **progress.to_dict()
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@downloads_api_bp.route('/api/v2/downloads/sessions/<session_id>/cancel', methods=['POST'])
@login_required
def api_v2_cancel_session(session_id):
    """Cancel active session"""
    try:
        from utils.download_manager import get_download_manager

        manager = get_download_manager()
        session = manager.get_session(session_id)

        if not session:
            return jsonify({
                'success': False,
                'error': 'Session not found'
            }), 404

        manager.cancel_session(session_id)

        return jsonify({
            'success': True,
            'message': 'Session cancelled',
            'session_id': session_id
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@downloads_api_bp.route('/api/v2/downloads/active')
@login_required
def api_v2_get_active_sessions():
    """Get all active download sessions"""
    try:
        from utils.download_manager import get_download_manager

        manager = get_download_manager()
        active_sessions = manager.get_active_sessions()

        return jsonify({
            'success': True,
            'active_sessions': [p.to_dict() for p in active_sessions],
            'count': len(active_sessions)
        })

    except Exception as e:
        logger.error(safe_format_exception())
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ==================== Date Range Statistics ====================

@downloads_api_bp.route('/api/date-range-stats')
def date_range_stats():
    """Get statistics grouped by month/year"""
    try:
        history_manager = app.config.get('history_manager')
        stats = history_manager.get_date_range_statistics()
        return jsonify(stats)

    except Exception as e:
        return jsonify({'error': str(e)}), 500
