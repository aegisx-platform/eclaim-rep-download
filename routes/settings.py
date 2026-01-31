"""
Settings Blueprint

Handles all settings-related routes:
- Settings page and API
- License management
- Hospital configuration
- Schedule management
- Credentials management
- User management (Admin only)
"""

from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from utils.auth import require_admin
from utils.settings_manager import SettingsManager
from utils.scheduler import download_scheduler
from utils.logging_config import setup_logger
from utils.license_middleware import require_license_write_access_for_methods

# Create blueprint for API routes
settings_api_bp = Blueprint('settings_api', __name__)

# Initialize logger
logger = setup_logger('settings_routes')

# Get settings manager instance
settings_manager = SettingsManager()


# ===== Settings API =====
# Note: Page routes (/license, /settings) are in app.py
# Only API routes are in this blueprint

@settings_api_bp.route('/api/settings', methods=['GET', 'POST'])
@login_required
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


# ===== Multiple Credentials Management =====

@settings_api_bp.route('/api/settings/credentials', methods=['GET', 'POST'])
@login_required
@require_admin
@require_license_write_access_for_methods(['POST'])
def manage_credentials():
    """Manage multiple E-Claim credentials"""
    if request.method == 'GET':
        # Get all credentials (mask passwords)
        credentials = settings_manager.get_all_credentials()
        masked_creds = []
        for cred in credentials:
            masked_creds.append({
                'username': cred.get('username', ''),
                'password': '********',
                'note': cred.get('note', ''),
                'enabled': cred.get('enabled', True)
            })
        return jsonify({
            'success': True,
            'credentials': masked_creds,
            'count': settings_manager.get_credentials_count()
        })

    elif request.method == 'POST':
        # Add new credential
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        note = data.get('note', '').strip()
        enabled = data.get('enabled', True)

        if not username:
            return jsonify({'success': False, 'error': 'Username is required'}), 400
        if not password:
            return jsonify({'success': False, 'error': 'Password is required'}), 400

        success = settings_manager.add_credential(username, password, note, enabled)
        if success:
            return jsonify({'success': True, 'message': 'Credential added successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to add credential'}), 500


@settings_api_bp.route('/api/settings/credentials/<username>', methods=['PUT', 'DELETE'])
@login_required
@require_admin
@require_license_write_access_for_methods(['PUT', 'DELETE'])
def manage_credential(username):
    """Update or delete a specific credential"""
    if request.method == 'PUT':
        data = request.get_json()
        password = data.get('password')
        note = data.get('note')
        enabled = data.get('enabled')

        # Don't update password if it's the placeholder
        if password == '********':
            password = None

        success = settings_manager.update_credential(username, password, note, enabled)
        if success:
            return jsonify({'success': True, 'message': 'Credential updated successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to update credential'}), 500

    elif request.method == 'DELETE':
        success = settings_manager.remove_credential(username)
        if success:
            return jsonify({'success': True, 'message': 'Credential deleted successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete credential'}), 500


@settings_api_bp.route('/api/settings/credentials/bulk', methods=['POST'])
@login_required
@require_admin
def bulk_credentials():
    """Bulk operations on credentials"""
    data = request.get_json()
    action = data.get('action')
    usernames = data.get('usernames', [])

    if action == 'delete':
        success_count = 0
        for username in usernames:
            if settings_manager.remove_credential(username):
                success_count += 1

        return jsonify({
            'success': True,
            'message': f'Deleted {success_count}/{len(usernames)} credentials'
        })

    return jsonify({'success': False, 'error': 'Invalid action'}), 400


@settings_api_bp.route('/api/settings/test-connection', methods=['POST'])
@login_required
def test_connection():
    """Test E-Claim connection with credentials"""
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    # If no username/password provided, use random from settings
    if not username or not password:
        credentials = settings_manager.get_all_credentials()
        if not credentials:
            return jsonify({'success': False, 'error': 'No credentials configured'}), 400

        # Filter active credentials
        active_creds = [c for c in credentials if c.get('enabled', True)]
        if not active_creds:
            return jsonify({'success': False, 'error': 'No active credentials available'}), 400

        # Pick random credential
        import random
        selected = random.choice(active_creds)
        username = selected['username']
        password = selected['password']
        logger.info(f"Testing connection with random account: {username}")

    try:
        # Import here to avoid circular dependency
        from eclaim_downloader_http import EClaimDownloader

        downloader = EClaimDownloader(username, password)
        if downloader.login():
            return jsonify({
                'success': True,
                'message': f'Connection successful with account: {username}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Login failed with account: {username}'
            }), 401

    except Exception as e:
        logger.error(f"Connection test error: {e}")
        return jsonify({
            'success': False,
            'error': f'Connection error: {str(e)}'
        }), 500


# ===== Hospital Configuration =====

@settings_api_bp.route('/api/settings/hospital-code', methods=['GET', 'POST'])
@login_required
@require_admin
# NOTE: No license check - hospital code is required for SMT Budget (free tier feature)
def hospital_code():
    """Get or set hospital code (HCODE)"""
    if request.method == 'GET':
        # Priority 1: Get from license if available
        from utils.license_checker import get_license_checker
        license_checker = get_license_checker()
        license_info = license_checker.get_license_info()

        license_hcode = license_info.get('hospital_code')
        if license_hcode:
            # Hospital code comes from license (read-only)
            return jsonify({
                'success': True,
                'hospital_code': license_hcode,
                'hospital_name': license_info.get('hospital_name'),
                'source': 'license',
                'editable': False,
                'message': 'รหัสโรงพยาบาลมาจาก License (ไม่สามารถแก้ไขได้)'
            })

        # Priority 2: Get from settings (editable)
        code = settings_manager.get_hospital_code()
        return jsonify({
            'success': True,
            'hospital_code': code,
            'source': 'settings',
            'editable': True,
            'message': 'รหัสโรงพยาบาลจากการตั้งค่า (สามารถแก้ไขได้)' if code else None
        })

    elif request.method == 'POST':
        # Check if hospital code is locked by license
        from utils.license_checker import get_license_checker
        license_checker = get_license_checker()
        license_info = license_checker.get_license_info()

        if license_info.get('hospital_code'):
            return jsonify({
                'success': False,
                'error': 'รหัสโรงพยาบาลมาจาก License และไม่สามารถแก้ไขได้',
                'message': 'หากต้องการเปลี่ยนรหัสโรงพยาบาล กรุณาติดต่อผู้ให้บริการเพื่อออก License ใหม่'
            }), 403

        data = request.get_json()
        code = data.get('hospital_code', '').strip()

        if not code:
            return jsonify({'success': False, 'error': 'Hospital code is required'}), 400

        if not code.isdigit() or len(code) != 5:
            return jsonify({'success': False, 'error': 'Hospital code must be 5 digits'}), 400

        success = settings_manager.set_hospital_code(code)
        if success:
            return jsonify({
                'success': True,
                'message': 'Hospital code updated successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to save hospital code'}), 500


@settings_api_bp.route('/api/settings/hospital-info')
@login_required
def hospital_info():
    """Get hospital information from database"""
    try:
        hospital_code = settings_manager.get_hospital_code()

        if not hospital_code:
            return jsonify({
                'success': False,
                'error': 'Hospital code not configured'
            }), 400

        # Import here to avoid circular dependency
        from config.db_pool import get_connection, return_connection

        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT hcode, hname, province, region
                FROM health_offices
                WHERE hcode = %s
                LIMIT 1
            """, (hospital_code,))

            row = cursor.fetchone()
            cursor.close()

            if row:
                return jsonify({
                    'success': True,
                    'hospital': {
                        'hcode': row[0],
                        'hname': row[1],
                        'province': row[2],
                        'region': row[3]
                    }
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Hospital code {hospital_code} not found in database'
                }), 404

        finally:
            return_connection(conn)

    except Exception as e:
        logger.error(f"Error getting hospital info: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== License Management API =====

@settings_api_bp.route('/api/settings/license', methods=['GET'])
@login_required
def get_license():
    """Get current license information"""
    try:
        license_info = settings_manager.get_license_info()
        return jsonify({
            'success': True,
            'license': license_info
        })
    except Exception as e:
        logger.error(f"Error getting license: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_api_bp.route('/api/settings/license', methods=['POST'])
@login_required
@require_admin
def install_license():
    """Install a new license"""
    try:
        data = request.get_json()
        license_key = data.get('license_key', '').strip()
        license_token = data.get('license_token', '').strip()
        public_key_raw = data.get('public_key', '').strip()

        # Clean public key: trim whitespace from each line (fix PEM format issues from copy-paste)
        public_key = '\n'.join(line.strip() for line in public_key_raw.splitlines())

        if not license_key:
            return jsonify({'success': False, 'error': 'License key is required'}), 400
        if not license_token:
            return jsonify({'success': False, 'error': 'License token is required'}), 400
        if not public_key:
            return jsonify({'success': False, 'error': 'Public key is required'}), 400

        success, message = settings_manager.install_license(license_key, license_token, public_key)

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 400

    except Exception as e:
        logger.error(f"Error installing license: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_api_bp.route('/api/settings/license/upload', methods=['POST'])
@login_required
@require_admin
def upload_license_file():
    """Upload and install .lic license file from AegisX License Server"""
    try:
        if 'license_file' not in request.files:
            return jsonify({'success': False, 'error': 'No license file uploaded'}), 400

        file = request.files['license_file']

        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        if not file.filename.lower().endswith('.lic'):
            return jsonify({'success': False, 'error': 'Invalid file format. Please upload a .lic file'}), 400

        # Save to temp location first
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.lic') as tmp:
            file.save(tmp.name)
            temp_path = tmp.name

        try:
            # Install the license file
            from utils.license_checker import get_license_checker
            license_checker = get_license_checker()
            success, message = license_checker.install_license_file(temp_path)

            if success:
                # Clear settings manager cache too
                settings_manager.clear_license_cache()

                return jsonify({
                    'success': True,
                    'message': message
                })
            else:
                return jsonify({
                    'success': False,
                    'error': message
                }), 400

        finally:
            # Clean up temp file
            import os
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    except Exception as e:
        logger.error(f"Error uploading license file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@settings_api_bp.route('/api/settings/license', methods=['DELETE'])
@login_required
@require_admin
def remove_license():
    """Remove installed license"""
    try:
        success, message = settings_manager.remove_license()

        if success:
            return jsonify({
                'success': True,
                'message': message
            })
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 500

    except Exception as e:
        logger.error(f"Error removing license: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== Schedule Management =====

@settings_api_bp.route('/api/schedule', methods=['GET', 'POST'])
@login_required
@require_admin
@require_license_write_access_for_methods(['POST'])
def schedule_settings():
    """Get or update schedule settings"""
    if request.method == 'GET':
        settings = settings_manager.get_schedule_settings()
        jobs = download_scheduler.get_all_jobs()

        return jsonify({
            'success': True,
            'settings': settings,
            'jobs': jobs
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()
            logger.info(f"Received schedule settings: {data}")

            enabled = data.get('enabled', False)
            times = data.get('times', [])
            auto_import = data.get('auto_import', False)

            # Get additional settings
            data_types = data.get('data_types', {})
            type_rep = data_types.get('rep', True)
            type_stm = data_types.get('stm', False)
            type_smt = data_types.get('smt', False)

            rep_schemes = data.get('rep_schemes', ['ucs', 'ofc', 'sss', 'lgo'])
            parallel_download = data.get('parallel_download', False)
            parallel_workers = data.get('parallel_workers', 3)
            smt_vendor_id = data.get('smt_vendor_id', '')

            logger.info(f"Schedule times: {times}, enabled: {enabled}")

            # Update settings
            success = settings_manager.update_schedule_settings(
                enabled, times, auto_import,
                type_rep=type_rep,
                type_stm=type_stm,
                type_smt=type_smt,
                smt_vendor_id=smt_vendor_id,
                parallel_download=parallel_download,
                parallel_workers=parallel_workers,
                rep_schemes=rep_schemes
            )

            if not success:
                logger.error("Failed to save schedule settings")
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

            # Update scheduler
            if enabled and times:
                # Clear existing jobs first
                download_scheduler.clear_all_jobs()

                # Add jobs for each time slot based on selected data types
                for time in times:
                    hour = time.get('hour', 0)
                    minute = time.get('minute', 0)

                    # Add REP download job if enabled
                    if type_rep:
                        download_scheduler.add_scheduled_download(hour, minute, auto_import)

                    # Add Statement download job if enabled
                    if type_stm:
                        download_scheduler.add_stm_scheduled_download(hour, minute, auto_import)

                    # Add SMT fetch job if enabled
                    if type_smt:
                        download_scheduler.add_smt_scheduled_fetch(hour, minute, smt_vendor_id, auto_import)

                logger.info(f"Scheduled {len(times)} time slots with data types: REP={type_rep}, STM={type_stm}, SMT={type_smt}")
            else:
                download_scheduler.clear_all_jobs()

            return jsonify({
                'success': True,
                'message': 'Schedule updated successfully'
            })

        except Exception as e:
            logger.error(f"Error saving schedule settings: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500


@settings_api_bp.route('/api/schedule/test', methods=['POST'])
@login_required
@require_admin
def test_schedule():
    """Test schedule immediately"""
    try:
        # Trigger download now
        from utils.downloader_runner import DownloaderRunner
        downloader_runner = DownloaderRunner()

        if downloader_runner.is_running():
            return jsonify({
                'success': False,
                'error': 'Download already in progress'
            }), 400

        downloader_runner.start()

        return jsonify({
            'success': True,
            'message': 'Test download started'
        })

    except Exception as e:
        logger.error(f"Error testing schedule: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# ===== STM Schedule Management =====

@settings_api_bp.route('/api/stm/schedule', methods=['GET', 'POST'])
@login_required
@require_admin
def api_stm_schedule():
    """Get or update STM schedule settings"""
    if request.method == 'GET':
        stm_settings = settings_manager.get_stm_schedule_settings()
        stm_jobs = [j for j in download_scheduler.get_all_jobs() if j['id'].startswith('stm_')]

        return jsonify({
            'success': True,
            **stm_settings,
            'active_jobs': stm_jobs
        })

    elif request.method == 'POST':
        try:
            data = request.get_json()

            enabled = data.get('stm_schedule_enabled', False)
            times = data.get('stm_schedule_times', [])
            auto_import = data.get('stm_schedule_auto_import', True)
            schemes = data.get('stm_schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

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

            # Validate schemes
            valid_schemes = ['ucs', 'ofc', 'sss', 'lgo']
            schemes = [s.lower() for s in schemes if s.lower() in valid_schemes]
            if not schemes:
                schemes = ['ucs']

            # Save settings
            success = settings_manager.update_stm_schedule_settings(enabled, times, auto_import, schemes)
            if not success:
                return jsonify({'success': False, 'error': 'Failed to save settings'}), 500

            # Update scheduler
            download_scheduler.remove_stm_jobs()

            if enabled and times:
                for time_config in times:
                    download_scheduler.add_stm_scheduled_download(
                        hour=time_config['hour'],
                        minute=time_config['minute'],
                        auto_import=auto_import,
                        schemes=schemes
                    )

            logger.info(f"✓ STM Schedule updated: {len(times)} times, schemes={schemes}, enabled={enabled}")

            return jsonify({'success': True, 'message': 'STM schedule settings updated'})

        except Exception as e:
            logger.error(f"Error updating STM schedule: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


@settings_api_bp.route('/api/stm/schedule/test', methods=['POST'])
@login_required
@require_admin
def test_stm_schedule():
    """Trigger a test run of STM download"""
    try:
        stm_settings = settings_manager.get_stm_schedule_settings()
        auto_import = stm_settings.get('stm_schedule_auto_import', True)
        schemes = stm_settings.get('stm_schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

        # Run download manually in background
        import threading
        thread = threading.Thread(
            target=download_scheduler._run_stm_download,
            args=(auto_import, schemes)
        )
        thread.start()

        return jsonify({
            'success': True,
            'message': f'STM test download initiated for schemes: {", ".join(schemes)}'
        })
    except Exception as e:
        logger.error(f"Error testing STM schedule: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


# ===== SMT Settings Management =====

@settings_api_bp.route('/api/smt/settings', methods=['GET', 'POST'])
@login_required
@require_admin
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

            # Reinitialize SMT scheduler (will be called from app.py)
            # init_smt_scheduler()  # Comment out - should be called from main app

            logger.info(f"✓ SMT settings updated: vendor={vendor_id}, enabled={schedule_enabled}")

            return jsonify({'success': True, 'message': 'SMT settings updated'})

        except Exception as e:
            logger.error(f"Error updating SMT settings: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


# ===== User Management API =====

@settings_api_bp.route('/api/users', methods=['POST'])
@login_required
@require_admin
def create_user():
    """Create new user (Admin only)"""
    try:
        from utils.auth import auth_manager
        from flask_login import current_user

        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()
        role = data.get('role', 'user')

        # Validate required fields
        if not username or not email or not password:
            return jsonify({
                'success': False,
                'error': 'กรุณากรอก Username, Email และ Password'
            }), 400

        if len(password) < 6:
            return jsonify({
                'success': False,
                'error': 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร'
            }), 400

        # Create user
        user_id = auth_manager.create_user(
            username=username,
            email=email,
            password=password,
            full_name=full_name or None,
            role=role,
            created_by=current_user.username
        )

        if user_id:
            logger.info(f"User created: {username} by {current_user.username}")
            return jsonify({
                'success': True,
                'message': 'สร้างผู้ใช้สำเร็จ',
                'user_id': user_id
            }), 201
        else:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถสร้างผู้ใช้ได้ (Username หรือ Email อาจซ้ำ)'
            }), 400

    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการสร้างผู้ใช้'
        }), 500


@settings_api_bp.route('/api/users/<int:user_id>', methods=['PUT'])
@login_required
@require_admin
def update_user(user_id):
    """Update user information (Admin only)"""
    try:
        from utils.auth import auth_manager
        from flask_login import current_user

        data = request.get_json()
        email = data.get('email', '').strip() or None
        full_name = data.get('full_name', '').strip() or None
        role = data.get('role')

        # Update user
        success = auth_manager.update_user(
            user_id=user_id,
            email=email,
            full_name=full_name,
            role=role,
            updated_by=current_user.username
        )

        if success:
            logger.info(f"User {user_id} updated by {current_user.username}")
            return jsonify({
                'success': True,
                'message': 'อัปเดตข้อมูลผู้ใช้สำเร็จ'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถอัปเดตข้อมูลได้'
            }), 500

    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการอัปเดตข้อมูล'
        }), 500


@settings_api_bp.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
@require_admin
def delete_user(user_id):
    """Delete user (Admin only)"""
    try:
        from utils.auth import auth_manager
        from flask_login import current_user

        # Prevent self-deletion
        if user_id == current_user.id:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถลบผู้ใช้ตัวเองได้'
            }), 400

        # Delete user
        success = auth_manager.delete_user(
            user_id=user_id,
            deleted_by=current_user.username
        )

        if success:
            logger.info(f"User {user_id} deleted by {current_user.username}")
            return jsonify({
                'success': True,
                'message': 'ลบผู้ใช้สำเร็จ'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถลบผู้ใช้ได้'
            }), 500

    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการลบผู้ใช้'
        }), 500


@settings_api_bp.route('/api/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@require_admin
def toggle_user_status(user_id):
    """Toggle user active/inactive status (Admin only)"""
    try:
        from utils.auth import auth_manager
        from flask_login import current_user

        # Prevent self-deactivation
        if user_id == current_user.id:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถเปลี่ยนสถานะตัวเองได้'
            }), 400

        # Toggle status
        success = auth_manager.toggle_user_status(
            user_id=user_id,
            updated_by=current_user.username
        )

        if success:
            logger.info(f"User {user_id} status toggled by {current_user.username}")
            return jsonify({
                'success': True,
                'message': 'เปลี่ยนสถานะผู้ใช้สำเร็จ'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถเปลี่ยนสถานะได้'
            }), 500

    except Exception as e:
        logger.error(f"Error toggling user status: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการเปลี่ยนสถานะ'
        }), 500


@settings_api_bp.route('/api/users/<int:user_id>/reset-password', methods=['POST'])
@login_required
@require_admin
def reset_user_password(user_id):
    """Reset user password (Admin only)"""
    try:
        from utils.auth import auth_manager
        from flask_login import current_user

        data = request.get_json()
        new_password = data.get('new_password', '').strip()
        require_change = data.get('require_change', True)

        # Validate password
        if not new_password:
            return jsonify({
                'success': False,
                'error': 'กรุณากรอกรหัสผ่านใหม่'
            }), 400

        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'error': 'รหัสผ่านต้องมีอย่างน้อย 6 ตัวอักษร'
            }), 400

        # Reset password
        success = auth_manager.reset_user_password(
            user_id=user_id,
            new_password=new_password,
            require_change=require_change,
            reset_by=current_user.username
        )

        if success:
            logger.info(f"Password reset for user {user_id} by {current_user.username}")
            return jsonify({
                'success': True,
                'message': 'รีเซ็ตรหัสผ่านสำเร็จ'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'ไม่สามารถรีเซ็ตรหัสผ่านได้'
            }), 500

    except Exception as e:
        logger.error(f"Error resetting password: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการรีเซ็ตรหัสผ่าน'
        }), 500


# ===== Audit Log API =====

@settings_api_bp.route('/api/audit/logs', methods=['GET'])
@login_required
@require_admin
def get_audit_logs():
    """Get audit logs with filters"""
    try:
        from config.database import get_db_connection
        from flask_login import current_user

        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        user_filter = request.args.get('user', '')
        action_filter = request.args.get('action', '')
        resource_filter = request.args.get('resource', '')
        status_filter = request.args.get('status', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')

        # Limit per_page to prevent performance issues
        per_page = min(per_page, 200)
        offset = (page - 1) * per_page

        from config.database import DB_TYPE

        conn = get_db_connection()
        cursor = conn.cursor()

        # Build query with filters
        where_clauses = []
        params = []

        # Use ILIKE for PostgreSQL, LIKE for MySQL
        like_operator = "ILIKE" if DB_TYPE == "postgresql" else "LIKE"

        if user_filter:
            where_clauses.append(f"user_id {like_operator} %s")
            params.append(f"%{user_filter}%")

        if action_filter:
            where_clauses.append("action = %s")
            params.append(action_filter)

        if resource_filter:
            where_clauses.append(f"resource_type {like_operator} %s")
            params.append(f"%{resource_filter}%")

        if status_filter:
            where_clauses.append("status = %s")
            params.append(status_filter)

        if date_from:
            where_clauses.append("timestamp >= %s")
            params.append(date_from)

        if date_to:
            where_clauses.append("timestamp <= %s")
            params.append(date_to)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # Get total count
        count_query = f"SELECT COUNT(*) FROM audit_log WHERE {where_sql}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()[0]

        # Get paginated results
        query = f"""
            SELECT
                id,
                user_id,
                user_email,
                session_id,
                action,
                resource_type,
                resource_id,
                changes_summary,
                ip_address,
                user_agent,
                request_method,
                request_path,
                status,
                error_message,
                timestamp,
                duration_ms
            FROM audit_log
            WHERE {where_sql}
            ORDER BY timestamp DESC
            LIMIT %s OFFSET %s
        """

        cursor.execute(query, params + [per_page, offset])
        rows = cursor.fetchall()

        logs = []
        for row in rows:
            logs.append({
                'id': row[0],
                'user_id': row[1],
                'user_email': row[2],
                'session_id': row[3],
                'action': row[4],
                'resource_type': row[5],
                'resource_id': row[6],
                'changes_summary': row[7],
                'ip_address': row[8],
                'user_agent': row[9],
                'request_method': row[10],
                'request_path': row[11],
                'status': row[12],
                'error_message': row[13],
                'timestamp': row[14].isoformat() if row[14] else None,
                'duration_ms': row[15]
            })

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'logs': logs,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_count,
                'pages': (total_count + per_page - 1) // per_page
            }
        })

    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการดึงข้อมูล audit log'
        }), 500


@settings_api_bp.route('/api/audit/stats', methods=['GET'])
@login_required
@require_admin
def get_audit_stats():
    """Get audit log statistics"""
    try:
        from config.database import get_db_connection, DB_TYPE

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get statistics for last 7 days
        # Different syntax for PostgreSQL and MySQL
        if DB_TYPE == 'mysql':
            query = """
                SELECT
                    COUNT(*) as total_events,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(CASE WHEN status != 'success' THEN 1 END) as failed_events,
                    COUNT(CASE WHEN action IN ('LOGIN', 'LOGIN_FAILED') THEN 1 END) as login_attempts,
                    COUNT(CASE WHEN action = 'LOGIN_FAILED' THEN 1 END) as failed_logins,
                    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL 24 HOUR THEN 1 END) as events_last_24h,
                    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL 7 DAY THEN 1 END) as events_last_7d
                FROM audit_log
            """
            action_query = """
                SELECT action, COUNT(*) as count
                FROM audit_log
                WHERE timestamp >= NOW() - INTERVAL 7 DAY
                GROUP BY action
                ORDER BY count DESC
                LIMIT 10
            """
        else:  # PostgreSQL
            query = """
                SELECT
                    COUNT(*) as total_events,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(CASE WHEN status != 'success' THEN 1 END) as failed_events,
                    COUNT(CASE WHEN action IN ('LOGIN', 'LOGIN_FAILED') THEN 1 END) as login_attempts,
                    COUNT(CASE WHEN action = 'LOGIN_FAILED' THEN 1 END) as failed_logins,
                    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '24 hours' THEN 1 END) as events_last_24h,
                    COUNT(CASE WHEN timestamp >= NOW() - INTERVAL '7 days' THEN 1 END) as events_last_7d
                FROM audit_log
            """
            action_query = """
                SELECT action, COUNT(*) as count
                FROM audit_log
                WHERE timestamp >= NOW() - INTERVAL '7 days'
                GROUP BY action
                ORDER BY count DESC
                LIMIT 10
            """

        cursor.execute(query)
        row = cursor.fetchone()

        stats = {
            'total_events': row[0] or 0,
            'unique_users': row[1] or 0,
            'failed_events': row[2] or 0,
            'login_attempts': row[3] or 0,
            'failed_logins': row[4] or 0,
            'events_last_24h': row[5] or 0,
            'events_last_7d': row[6] or 0
        }

        # Get action distribution
        cursor.execute(action_query)

        action_dist = []
        for row in cursor.fetchall():
            action_dist.append({
                'action': row[0],
                'count': row[1]
            })

        stats['action_distribution'] = action_dist

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'stats': stats
        })

    except Exception as e:
        logger.error(f"Error getting audit stats: {e}")
        return jsonify({
            'success': False,
            'error': 'เกิดข้อผิดพลาดในการดึงสถิติ'
        }), 500
