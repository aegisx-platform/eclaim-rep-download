#!/usr/bin/env python3
"""
License Middleware - Flask decorators for license-based access control
"""

from functools import wraps
from flask import jsonify, request
from utils.license_checker import get_license_checker


def require_license_write_access(f):
    """
    Decorator to block write operations when license is expired or in grace period

    Blocked operations:
    - Downloads (auto/manual/scheduled)
    - Settings modifications
    - User management

    Allowed operations:
    - View data (analytics, reports, etc.)
    - Export data
    - External API (HIS integration)
    - Import (for manually uploaded files)
    - Upload files

    Usage:
        @app.route('/api/downloads/single', methods=['POST'])
        @require_license_write_access
        def download_single():
            # ... code ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        license_checker = get_license_checker()
        state = license_checker.get_license_state()

        # Only allow write operations if license is active
        if state != 'active':
            # Get license info for error message
            info = license_checker.get_license_info()

            if state == 'grace_period':
                message = (
                    f"ไลเซนส์หมดอายุแล้ว แต่ยังอยู่ในช่วงผ่อนผัน ({info['grace_days_left']} วันที่เหลือ)\n"
                    f"ฟีเจอร์ดาวน์โหลดอัตโนมัติถูกปิดการใช้งาน กรุณาดาวน์โหลดไฟล์จาก NHSO ด้วยตนเอง "
                    f"แล้วอัปโหลดเข้าระบบ หรือติดต่อผู้ให้บริการเพื่อต่ออายุไลเซนส์"
                )
            else:  # free tier
                message = (
                    f"Free Tier - ใช้งาน SMT Budget ได้เท่านั้น\n"
                    f"การดาวน์โหลด REP และ STM ต้องมี Enterprise License "
                    f"กรุณาติดต่อผู้ให้บริการเพื่อซื้อ License"
                )

            return jsonify({
                'success': False,
                'error': 'license_expired',
                'message': message,
                'license_state': state,
                'license_info': {
                    'status': info['status'],
                    'tier': info['tier'],
                    'expires_at': info['expires_at'],
                    'grace_days_left': info.get('grace_days_left', 0)
                }
            }), 403

        # License is active, allow operation
        return f(*args, **kwargs)

    return decorated_function


def require_license_write_access_for_methods(methods=None):
    """
    Decorator to block write operations for specific HTTP methods only

    Args:
        methods: List of HTTP methods to block (e.g., ['POST', 'PUT', 'DELETE'])
                 If None, block all methods (same as require_license_write_access)

    Usage:
        @app.route('/api/settings/credentials', methods=['GET', 'POST'])
        @require_license_write_access_for_methods(['POST'])
        def manage_credentials():
            # GET is allowed, POST is blocked if license expired
            # ... code ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # If methods specified, only check for those methods
            if methods and request.method not in methods:
                return f(*args, **kwargs)

            license_checker = get_license_checker()
            state = license_checker.get_license_state()

            # Only allow write operations if license is active
            if state != 'active':
                # Get license info for error message
                info = license_checker.get_license_info()

                if state == 'grace_period':
                    message = (
                        f"ไลเซนส์หมดอายุแล้ว แต่ยังอยู่ในช่วงผ่อนผัน ({info['grace_days_left']} วันที่เหลือ)\n"
                        f"ฟีเจอร์ดาวน์โหลดอัตโนมัติถูกปิดการใช้งาน กรุณาดาวน์โหลดไฟล์จาก NHSO ด้วยตนเอง "
                        f"แล้วอัปโหลดเข้าระบบ หรือติดต่อผู้ให้บริการเพื่อต่ออายุไลเซนส์"
                    )
                else:  # free tier
                    message = (
                        f"Free Tier - ใช้งาน SMT Budget ได้เท่านั้น\n"
                        f"การแก้ไขตั้งค่าต้องมี Enterprise License "
                        f"กรุณาติดต่อผู้ให้บริการเพื่อซื้อ License"
                    )

                return jsonify({
                    'success': False,
                    'error': 'license_expired',
                    'message': message,
                    'license_state': state,
                    'license_info': {
                        'status': info['status'],
                        'tier': info['tier'],
                        'expires_at': info['expires_at'],
                        'grace_days_left': info.get('grace_days_left', 0)
                    }
                }), 403

            # License is active, allow operation
            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_rep_stm_access(f):
    """
    Decorator to block REP/STM operations in free tier

    Free tier can only use SMT Budget.
    REP and STM require Enterprise license.

    Usage:
        @app.route('/api/downloads/rep', methods=['POST'])
        @require_rep_stm_access
        def download_rep():
            # ... code ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        license_checker = get_license_checker()

        # Check if REP/STM access is allowed
        has_rep_access = license_checker.check_feature_access('rep_access')
        has_stm_access = license_checker.check_feature_access('stm_access')

        if not (has_rep_access or has_stm_access):
            # Free tier - block REP/STM
            info = license_checker.get_license_info()
            return jsonify({
                'success': False,
                'error': 'upgrade_required',
                'message': (
                    'Free Tier - ใช้งาน SMT Budget ได้เท่านั้น\n'
                    'การดาวน์โหลด/นำเข้า REP และ STM ต้องมี Enterprise License\n'
                    'กรุณาติดต่อผู้ให้บริการเพื่อซื้อ License'
                ),
                'license_state': 'free',
                'license_info': {
                    'tier': info['tier'],
                    'features': {
                        'smt_budget': True,
                        'rep_access': False,
                        'stm_access': False
                    }
                },
                'upgrade_url': '/license'
            }), 403

        # Has license, proceed
        return f(*args, **kwargs)

    return decorated_function


def get_license_status_banner() -> dict:
    """
    Get license status for UI banner display

    Returns:
        Dict with banner info (show, type, message)
    """
    license_checker = get_license_checker()
    state = license_checker.get_license_state()
    info = license_checker.get_license_info()

    if state == 'active':
        # Check if expiring soon (within 30 days)
        days_until_expiry = info.get('days_until_expiry')
        if days_until_expiry is not None and days_until_expiry <= 30:
            return {
                'show': True,
                'type': 'warning',
                'message': f'ไลเซนส์ใกล้หมดอายุ ({days_until_expiry} วันที่เหลือ) กรุณาติดต่อผู้ให้บริการเพื่อต่ออายุ',
                'state': 'expiring_soon'
            }
        return {
            'show': False,
            'type': 'success',
            'message': '',
            'state': 'active'
        }

    elif state == 'grace_period':
        grace_days = info.get('grace_days_left', 0)
        return {
            'show': True,
            'type': 'warning',
            'message': (
                f'⚠️ ไลเซนส์หมดอายุแล้ว (ช่วงผ่อนผัน: {grace_days} วันที่เหลือ)\n'
                f'ฟีเจอร์ดาวน์โหลดอัตโนมัติถูกปิดการใช้งาน กรุณาดาวน์โหลดไฟล์ด้วยตนเองแล้วอัปโหลดเข้าระบบ '
                f'หรือติดต่อผู้ให้บริการเพื่อต่ออายุไลเซนส์'
            ),
            'state': 'grace_period'
        }

    else:  # free tier
        return {
            'show': True,
            'type': 'info',
            'message': (
                f'ℹ️ Free Tier - ใช้งาน SMT Budget ได้เท่านั้น\n'
                f'ต้องการดาวน์โหลด REP และ STM? ติดต่อผู้ให้บริการเพื่อซื้อ Enterprise License'
            ),
            'state': 'free'
        }
