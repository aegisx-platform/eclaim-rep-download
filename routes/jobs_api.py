"""
Jobs and History API Routes
Handles background job tracking and history
"""

from flask import Blueprint, jsonify, request
from utils.job_history_manager import job_history_manager
from utils.logging_config import setup_logger
import logging

# Setup logger
logger = setup_logger('jobs_api', logging.INFO, 'logs/jobs_api.log')

# Create blueprint
jobs_api_bp = Blueprint('jobs_api', __name__)


# ==================== Job History API ====================

@jobs_api_bp.route('/api/jobs')
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


@jobs_api_bp.route('/api/jobs/stats')
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


@jobs_api_bp.route('/api/jobs/<job_id>')
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
