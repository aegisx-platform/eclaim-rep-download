#!/usr/bin/env python3
"""
License Checker - Offline JWT license validation
Implements client-side license verification using RS256 public key
"""

import jwt
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend


# Lazy import to avoid circular dependency
def get_settings_manager():
    """Get SettingsManager instance (lazy import)"""
    from utils.settings_manager import SettingsManager
    return SettingsManager()


class LicenseChecker:
    """
    Client-side license verification for NHSO Revenue Intelligence

    Features:
    - Offline validation using RSA public key
    - JWT-based license tokens (RS256)
    - Tier-based feature restrictions
    - Grace period for expired licenses
    """

    # License tiers and their features
    TIER_FEATURES = {
        'trial': {
            'max_users': 2,
            'max_records_per_import': 1000,
            'smt_budget': False,
            'analytics_advanced': False,
            'reconciliation': False,
            'api_access': False,
            'priority_support': False,
            'custom_reports': False
        },
        'basic': {
            'max_users': 5,
            'max_records_per_import': 50000,
            'smt_budget': True,
            'analytics_advanced': False,
            'reconciliation': True,
            'api_access': False,
            'priority_support': False,
            'custom_reports': False
        },
        'professional': {
            'max_users': 20,
            'max_records_per_import': 500000,
            'smt_budget': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'priority_support': True,
            'custom_reports': True
        },
        'enterprise': {
            'max_users': 9999,  # Unlimited
            'max_records_per_import': 9999999,  # Unlimited
            'smt_budget': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'priority_support': True,
            'custom_reports': True,
            'white_label': True,
            'dedicated_support': True
        }
    }

    def __init__(self, license_file='config/license.json'):
        self.license_file = Path(license_file)
        self.license_file.parent.mkdir(exist_ok=True)
        self._cached_license = None
        self._cache_time = None
        self._cache_ttl = 3600  # Cache for 1 hour

    def load_license(self) -> Optional[Dict]:
        """
        Load license from file with caching

        Returns:
            License dict or None if not found
        """
        # Use cache if available and not expired
        if self._cached_license and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_ttl:
                return self._cached_license

        if not self.license_file.exists():
            return None

        try:
            with open(self.license_file, 'r', encoding='utf-8') as f:
                license_data = json.load(f)
                self._cached_license = license_data
                self._cache_time = datetime.now()
                return license_data
        except Exception as e:
            print(f"Error loading license: {e}")
            return None

    def save_license(self, license_key: str, license_token: str, public_key: str) -> bool:
        """
        Save license to file

        Args:
            license_key: License key (e.g., AEGISX-A1B2C3D4-E5F6G7H8)
            license_token: JWT license token
            public_key: RSA public key (PEM format)

        Returns:
            True if successful
        """
        try:
            license_data = {
                'license_key': license_key,
                'license_token': license_token,
                'public_key': public_key,
                'installed_at': datetime.now().isoformat()
            }

            with open(self.license_file, 'w', encoding='utf-8') as f:
                json.dump(license_data, f, ensure_ascii=False, indent=2)

            # Clear cache
            self._cached_license = None
            self._cache_time = None

            return True
        except Exception as e:
            print(f"Error saving license: {e}")
            return False

    def verify_license(self) -> Tuple[bool, Dict, Optional[str]]:
        """
        Verify license token using public key

        Returns:
            (is_valid, license_info, error_message)
            - is_valid: True if license is valid
            - license_info: Decoded license payload
            - error_message: Error description if invalid
        """
        license_data = self.load_license()

        if not license_data:
            return False, {}, "No license installed"

        license_token = license_data.get('license_token')
        public_key_pem = license_data.get('public_key')

        if not license_token or not public_key_pem:
            return False, {}, "Invalid license file format"

        try:
            # Load public key
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8'),
                backend=default_backend()
            )

            # Verify and decode JWT
            payload = jwt.decode(
                license_token,
                public_key,
                algorithms=['RS256']
            )

            # ===== Hospital Code Validation =====
            # License must match the hospital code configured in settings
            license_hospital_code = payload.get('hospital_code', '').strip()

            if license_hospital_code:
                # Get current hospital code from settings
                settings_manager = get_settings_manager()
                current_hospital_code = settings_manager.get_hospital_code()

                # If hospital code is configured, it must match the license
                if current_hospital_code and license_hospital_code != current_hospital_code:
                    return False, payload, (
                        f"License mismatch: This license is issued for hospital code '{license_hospital_code}' "
                        f"but your system is configured for '{current_hospital_code}'. "
                        f"Please contact your vendor for the correct license."
                    )

            # Check expiration (with configurable grace period)
            exp = payload.get('exp')
            if exp:
                exp_date = datetime.fromtimestamp(exp)
                grace_period_days = payload.get('grace_period_days', 90)  # Default 90 days, configurable
                grace_date = exp_date + timedelta(days=grace_period_days)

                if datetime.now() > grace_date:
                    return False, payload, f"License expired on {exp_date.strftime('%Y-%m-%d')} (grace period ended)"
                elif datetime.now() > exp_date:
                    # In grace period
                    days_left = (grace_date - datetime.now()).days
                    payload['_grace_period'] = True
                    payload['_grace_days_left'] = days_left
                    payload['_grace_period_days'] = grace_period_days

            # Add tier features to payload
            tier = payload.get('tier', 'trial')
            payload['_features'] = self.TIER_FEATURES.get(tier, self.TIER_FEATURES['trial'])

            return True, payload, None

        except jwt.ExpiredSignatureError:
            return False, {}, "License has expired"
        except jwt.InvalidSignatureError:
            return False, {}, "Invalid license signature (tampered or wrong key)"
        except jwt.DecodeError:
            return False, {}, "Invalid license token format"
        except Exception as e:
            return False, {}, f"License verification error: {str(e)}"

    def get_license_info(self) -> Dict:
        """
        Get license information with validation

        Returns:
            Dict with license status, tier, features, expiration, etc.
        """
        is_valid, payload, error = self.verify_license()

        if not is_valid:
            return {
                'is_valid': False,
                'status': 'invalid',
                'error': error,
                'tier': 'trial',
                'features': self.TIER_FEATURES['trial'],
                'days_until_expiry': None,
                'grace_period': False,
                'grace_days_left': 0,
                'max_users': None,
                'expires_at': None,
                'issued_at': None,
                'license_key': None,
                'license_type': 'trial',
                'hospital_code': None,
                'hospital_name': None,
                'custom_limits': {}
            }

        # Calculate days until expiration
        exp = payload.get('exp')
        days_until_expiry = None
        if exp:
            exp_date = datetime.fromtimestamp(exp)
            days_until_expiry = (exp_date - datetime.now()).days

        # Determine status
        status = 'active'
        if payload.get('_grace_period'):
            status = 'grace_period'
        elif days_until_expiry is not None and days_until_expiry <= 30:
            status = 'expiring_soon'

        return {
            'is_valid': True,
            'status': status,
            'license_key': payload.get('license_key'),
            'tier': payload.get('tier', 'trial'),
            'license_type': payload.get('license_type', 'trial'),
            'hospital_code': payload.get('hospital_code'),
            'hospital_name': payload.get('hospital_name'),
            'features': payload.get('_features', {}),
            'issued_at': datetime.fromtimestamp(payload.get('iat')).isoformat() if payload.get('iat') else None,
            'expires_at': datetime.fromtimestamp(payload.get('exp')).isoformat() if payload.get('exp') else None,
            'days_until_expiry': days_until_expiry,
            'grace_period': payload.get('_grace_period', False),
            'grace_days_left': payload.get('_grace_days_left', 0),
            'max_users': payload.get('max_users'),
            'custom_limits': payload.get('limits', {})
        }

    def get_license_state(self) -> str:
        """
        Get current license state for access control

        States:
        - 'active': License valid, all features available
        - 'grace_period': License expired but within grace period, downloads blocked
        - 'read_only': License expired beyond grace period or invalid, downloads blocked

        Returns:
            License state string ('active', 'grace_period', or 'read_only')
        """
        is_valid, payload, error = self.verify_license()

        # If verification failed completely (expired beyond grace or invalid)
        if not is_valid:
            return 'read_only'

        # Check if in grace period
        if payload.get('_grace_period', False):
            return 'grace_period'

        # Valid and not expired
        return 'active'

    def check_feature_access(self, feature: str) -> bool:
        """
        Check if current license allows access to a feature

        Args:
            feature: Feature name (e.g., 'smt_budget', 'analytics_advanced')

        Returns:
            True if feature is accessible
        """
        info = self.get_license_info()

        if not info['is_valid']:
            # Trial mode - limited features
            return self.TIER_FEATURES['trial'].get(feature, False)

        features = info.get('features', {})
        return features.get(feature, False)

    def check_limit(self, limit_name: str, value: int) -> bool:
        """
        Check if value is within license limits

        Args:
            limit_name: Limit name (e.g., 'max_users', 'max_records_per_import')
            value: Value to check

        Returns:
            True if within limits
        """
        info = self.get_license_info()

        # Check custom limits first
        custom_limits = info.get('custom_limits', {})
        if limit_name in custom_limits:
            return value <= custom_limits[limit_name]

        # Check tier limits
        features = info.get('features', {})
        limit = features.get(limit_name, 0)

        return value <= limit

    def get_tier_name(self, tier: str) -> str:
        """Get localized tier name"""
        tier_names = {
            'trial': 'ทดลองใช้งาน',
            'basic': 'พื้นฐาน',
            'professional': 'มืออาชีพ',
            'enterprise': 'องค์กร'
        }
        return tier_names.get(tier, tier)

    def get_status_badge_class(self, status: str) -> str:
        """Get CSS class for status badge"""
        classes = {
            'active': 'bg-green-100 text-green-800',
            'expiring_soon': 'bg-yellow-100 text-yellow-800',
            'grace_period': 'bg-orange-100 text-orange-800',
            'invalid': 'bg-red-100 text-red-800'
        }
        return classes.get(status, 'bg-gray-100 text-gray-800')

    def get_status_text(self, status: str) -> str:
        """Get localized status text"""
        texts = {
            'active': 'ใช้งานได้ปกติ',
            'expiring_soon': 'ใกล้หมดอายุ',
            'grace_period': 'พ้นกำหนด (ช่วงผ่อนผัน)',
            'invalid': 'ไม่ถูกต้อง'
        }
        return texts.get(status, status)

    def remove_license(self) -> bool:
        """
        Remove installed license

        Returns:
            True if successful
        """
        try:
            if self.license_file.exists():
                self.license_file.unlink()

            # Clear cache
            self._cached_license = None
            self._cache_time = None

            return True
        except Exception as e:
            print(f"Error removing license: {e}")
            return False


# Global instance
_license_checker = None


def get_license_checker() -> LicenseChecker:
    """Get global license checker instance"""
    global _license_checker
    if _license_checker is None:
        _license_checker = LicenseChecker()
    return _license_checker
