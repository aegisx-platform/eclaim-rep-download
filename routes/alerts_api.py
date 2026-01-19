"""
Alert System API Routes
Handles system alerts and notifications
"""

from flask import Blueprint, jsonify, request
from utils.alert_manager import alert_manager
from utils.logging_config import setup_logger
import logging
import psutil
import shutil
from pathlib import Path
from config.database import DOWNLOADS_DIR

# Setup logger
logger = setup_logger('alerts_api', logging.INFO, 'logs/alerts_api.log')

# Create blueprint
alerts_api_bp = Blueprint('alerts_api', __name__)


# ==================== Alert System API ====================

@alerts_api_bp.route('/api/alerts')
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


@alerts_api_bp.route('/api/alerts/unread-count')
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


@alerts_api_bp.route('/api/alerts/<int:alert_id>/read', methods=['POST'])
def mark_alert_read(alert_id):
    """Mark an alert as read"""
    try:
        success = alert_manager.mark_as_read(alert_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_api_bp.route('/api/alerts/read-all', methods=['POST'])
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


@alerts_api_bp.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    """Dismiss an alert"""
    try:
        success = alert_manager.dismiss_alert(alert_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@alerts_api_bp.route('/api/alerts/dismiss-all', methods=['POST'])
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


@alerts_api_bp.route('/api/alerts/check-health', methods=['POST'])
def check_health_and_alert():
    """
    Check system health and create alerts for any issues found.
    This can be called periodically or manually to update alerts.
    """
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
