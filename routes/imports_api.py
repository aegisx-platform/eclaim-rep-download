"""Import API Blueprint - REP, STM, and SMT file import routes"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required
from werkzeug.utils import secure_filename
from pathlib import Path
from utils.license_middleware import require_rep_stm_access

# Create blueprint
imports_api_bp = Blueprint('imports_api', __name__)


# ============================================================================
# REP IMPORTS
# ============================================================================

@imports_api_bp.route('/api/imports/rep/<filename>', methods=['POST'])
@imports_api_bp.route('/import/file/<filename>', methods=['POST'])  # Legacy alias
@require_rep_stm_access
def import_file(filename):
    """Import single REP file to database"""
    try:
        # Get managers from app config
        file_manager = current_app.config['FILE_MANAGER']
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        # Validate filename
        file_path = file_manager.get_file_path(filename)

        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Start import process in background using unified runner
        result = unified_import_runner.start_single_file_import('rep', str(file_path))

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/rep', methods=['POST'])
@imports_api_bp.route('/import/all', methods=['POST'])  # Legacy alias
@require_rep_stm_access
def import_all_files():
    """Import all REP files that haven't been imported yet"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        # Start bulk import process in background using unified runner
        result = unified_import_runner.start_import('rep')

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/progress')
@imports_api_bp.route('/import/progress')  # Legacy alias
def import_progress():
    """Get real-time import progress (unified for all types)"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        progress = unified_import_runner.get_progress()
        return jsonify({'success': True, 'progress': progress})

    except Exception as e:
        return jsonify({'success': False, 'running': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/cancel', methods=['POST'])
def cancel_import():
    """Cancel currently running import"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        result = unified_import_runner.stop()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# STM IMPORTS
# ============================================================================

@imports_api_bp.route('/api/imports/stm/<filename>', methods=['POST'])
@imports_api_bp.route('/api/stm/import/<filename>', methods=['POST'])  # Legacy alias
@require_rep_stm_access
def import_stm_file_route(filename):
    """Import a single Statement file"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        file_path = Path('downloads/stm') / filename
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Check if file is a valid STM file
        if not filename.startswith('STM_'):
            return jsonify({'success': False, 'error': 'Not a valid STM file'}), 400

        # Start import process in background using unified runner
        result = unified_import_runner.start_single_file_import('stm', str(file_path))

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500

    except Exception as e:
        current_app.logger.error(f"STM import error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/stm', methods=['POST'])
@imports_api_bp.route('/api/stm/import-all', methods=['POST'])  # Legacy alias
@require_rep_stm_access
def import_all_stm_files():
    """Import all pending Statement files (background process)"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        # Start bulk import in background using unified runner
        result = unified_import_runner.start_import('stm')

        if result['success']:
            return jsonify(result), 200
        else:
            status_code = 409 if 'already running' in result.get('error', '').lower() else 500
            return jsonify(result), status_code

    except Exception as e:
        current_app.logger.error(f"STM import-all error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/stm/progress')
@imports_api_bp.route('/api/stm/import/progress')  # Legacy alias
def stm_import_progress():
    """Get real-time STM import progress (alias for unified progress)"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        # Use unified progress endpoint
        progress = unified_import_runner.get_progress()
        return jsonify({'success': True, 'progress': progress})
    except Exception as e:
        current_app.logger.error(f"STM import progress error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# SMT IMPORTS
# ============================================================================

@imports_api_bp.route('/api/imports/smt/<path:filename>', methods=['POST'])
@imports_api_bp.route('/api/smt/import/<path:filename>', methods=['POST'])  # Legacy alias
def api_smt_import_file(filename):
    """Import a specific SMT file to database"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        # Sanitize filename
        safe_filename = secure_filename(filename)
        file_path = Path('downloads/smt') / safe_filename

        if not file_path.exists():
            return jsonify({'success': False, 'error': 'File not found'}), 404

        # Start import process in background using unified runner
        result = unified_import_runner.start_single_file_import('smt', str(file_path))

        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 409 if 'already running' in result.get('error', '').lower() else 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/smt', methods=['POST'])
@imports_api_bp.route('/api/smt/import-all', methods=['POST'])  # Legacy alias
def api_smt_import_all():
    """Import all SMT files to database (background process)"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        smt_dir = Path('downloads/smt')
        if not smt_dir.exists():
            return jsonify({'success': False, 'error': 'No SMT files directory'}), 400

        # Start bulk import in background using unified runner
        result = unified_import_runner.start_import('smt')

        if result['success']:
            return jsonify(result), 200
        else:
            status_code = 409 if 'already running' in result.get('error', '').lower() else 500
            return jsonify(result), status_code

    except Exception as e:
        current_app.logger.error(f"SMT import-all error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@imports_api_bp.route('/api/imports/smt/progress')
@imports_api_bp.route('/api/smt/import/progress')  # Legacy alias
def smt_import_progress():
    """Get real-time SMT import progress (alias for unified progress)"""
    try:
        # Get manager from app config
        unified_import_runner = current_app.config['UNIFIED_IMPORT_RUNNER']

        # Use unified progress endpoint
        progress = unified_import_runner.get_progress()
        return jsonify({'success': True, 'progress': progress})
    except Exception as e:
        current_app.logger.error(f"SMT import progress error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
