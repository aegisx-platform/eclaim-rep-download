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

Note: Schedule route disabled - use Data Management page instead
"""

from flask import Blueprint, render_template, redirect, url_for
from flask_login import login_required
from utils.auth import require_admin
from utils.settings_manager import SettingsManager

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
    return render_template('settings/license.html')


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
    return render_template('settings/api_keys.html')
