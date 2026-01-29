"""
Settings Pages Blueprint - UI Routes for Settings Management
Separate from API routes (routes/settings.py)

Routes:
- /settings/                → Main settings page (overview/navigation)
- /settings/credentials     → Credentials management
- /settings/license         → License management
- /settings/hospital        → Hospital information
- /settings/system-health   → System health monitoring
- /settings/profile         → User profile and password management
- /settings/users           → User management (Admin only)
- /settings/api-keys        → API Keys management (Admin only)
- /settings/audit           → Audit log viewer (Admin only)

Note: Schedule route disabled - use Data Management page instead
"""

from flask import Blueprint, render_template, redirect, url_for, send_file
from flask_login import login_required
from utils.auth import require_admin
from utils.settings_manager import SettingsManager
import os

# Create blueprint with url_prefix
# Note: Use 'settings' as blueprint name (API blueprint uses different name)
settings_pages_bp = Blueprint('settings', __name__, url_prefix='/settings')

# Get settings manager instance
settings_manager = SettingsManager()


@settings_pages_bp.route('/')
@login_required
def index():
    """Settings main page - Overview with navigation menu"""
    current_settings = settings_manager.load_settings()
    return render_template('settings/index.html', settings=current_settings)


@settings_pages_bp.route('/credentials')
@login_required
def credentials():
    """Credentials management page - NHSO, HIS credentials"""
    current_settings = settings_manager.load_settings()
    return render_template('settings/credentials.html', settings=current_settings)


@settings_pages_bp.route('/license')
@login_required
@require_admin
def license():
    """License management page - Admin only"""
    # Get license portal URL from environment
    # Default: auto-detect based on FLASK_ENV
    flask_env = os.getenv('FLASK_ENV', 'production')
    default_portal_url = 'http://localhost:5002/portal' if flask_env == 'development' else 'https://license.aegisxplatform.com/portal'
    license_portal_url = os.getenv('LICENSE_PORTAL_URL', default_portal_url)

    return render_template('settings/license.html', license_portal_url=license_portal_url)


# Schedule route disabled - use Data Management page instead
# @settings_pages_bp.route('/schedule')
# @login_required
# def schedule():
#     """Download scheduler configuration page"""
#     current_settings = settings_manager.load_settings()
#     return render_template('settings/schedule.html', settings=current_settings)


@settings_pages_bp.route('/hospital')
@login_required
def hospital():
    """Hospital information and configuration page"""
    current_settings = settings_manager.load_settings()
    return render_template('settings/hospital.html', settings=current_settings)


@settings_pages_bp.route('/system-health')
@login_required
def system_health():
    """System health monitoring page"""
    return render_template('settings/system_health.html')


@settings_pages_bp.route('/profile')
@login_required
def profile():
    """User profile and password management page"""
    return render_template('settings/profile.html')


@settings_pages_bp.route('/users')
@login_required
@require_admin
def users():
    """User management page - Admin only"""
    from utils.auth import auth_manager
    all_users = auth_manager.get_all_users()
    return render_template('settings/users.html', users=all_users)


@settings_pages_bp.route('/api-keys')
@login_required
@require_admin
def api_keys():
    """API Keys management page - Admin only"""
    import os
    server_url = os.getenv('SERVER_URL', 'http://localhost:5001')
    return render_template('settings/api_keys.html', server_url=server_url)


@settings_pages_bp.route('/audit')
@login_required
@require_admin
def audit():
    """Audit log viewer page - Admin only"""
    return render_template('settings/audit_log.html')


@settings_pages_bp.route('/api-keys/download-postman')
@login_required
@require_admin
def download_postman_collection():
    """Download Postman Collection for External API"""
    import os
    from pathlib import Path

    # Get project root directory
    project_root = Path(__file__).parent.parent
    collection_path = project_root / 'docs' / 'E-Claim_External_API.postman_collection.json'

    if not collection_path.exists():
        return "Postman Collection not found", 404

    return send_file(
        collection_path,
        as_attachment=True,
        download_name='E-Claim_External_API.postman_collection.json',
        mimetype='application/json'
    )
