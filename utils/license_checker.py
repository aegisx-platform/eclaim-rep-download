#!/usr/bin/env python3
"""
License Checker - Offline JWT license validation
Implements client-side license verification using RS256 public key

Supports:
- JSON format (legacy): config/license.json
- Encrypted .lic format (new): config/license.lic from AegisX License Server
"""

import os
import jwt
import json
import base64
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet, InvalidToken


# Lazy import to avoid circular dependency
def get_settings_manager():
    """Get SettingsManager instance (lazy import)"""
    from utils.settings_manager import SettingsManager
    return SettingsManager()


class LicenseChecker:
    """
    Client-side license verification for Revenue Intelligence System

    Features:
    - Offline validation using RSA public key
    - JWT-based license tokens (RS256)
    - Tier-based feature restrictions
    - Grace period for expired licenses
    """

    # License tiers and their features
    TIER_FEATURES = {
        'free': {
            'tier_name': 'Free',
            'price_per_year': 0,
            'max_users': 9999,                     # Unlimited
            'max_records_per_import': 9999999,     # Unlimited
            'data_retention_years': 999,           # Unlimited
            'smt_budget': True,                    # ✅ SMT Budget (Download/Import/Analytics)
            'rep_access': False,                   # ❌ REP (E-Claim) blocked
            'stm_access': False,                   # ❌ STM (Statement) blocked
            'view_reports': True,                  # ✅ View all reports (read-only)
            'export_reports': True,                # ✅ Export to Excel/PDF
            'analytics_basic': True,               # ✅ Basic analytics (SMT only)
            'analytics_advanced': False,           # ❌ No forecasting, prediction
            'reconciliation': False,               # ❌ No HIS reconciliation
            'api_access': False,                   # ❌ No API
            'custom_reports': False,               # ❌ No custom report builder
            'scheduled_downloads': False,          # ❌ No automation
            'white_label': False,
            'priority_support': False,
            'dedicated_support': False,
            'custom_development': False,
            'sla_guarantee': False
        },
        'basic': {
            'tier_name': 'Basic',
            'price_per_year': 10000,
            'max_users': 9999,
            'max_records_per_import': 9999999,
            'data_retention_years': 3,
            'smt_budget': True,                    # ✅ SMT Budget
            'rep_access': True,                    # ✅ REP (E-Claim) download/import
            'stm_access': True,                    # ✅ STM (Statement) download/import
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,               # ✅ Summary, Trends, Denial analysis
            'analytics_advanced': False,           # ❌ No AI/ML features
            'reconciliation': False,               # ❌ No HIS reconciliation
            'api_access': False,                   # ❌ No API
            'custom_reports': False,               # ❌ No custom report builder
            'scheduled_downloads': True,           # ✅ Auto download
            'white_label': False,
            'priority_support': False,
            'dedicated_support': False,
            'custom_development': False,
            'sla_guarantee': False
        },
        'professional': {
            'tier_name': 'Professional',
            'price_per_year': 30000,
            'max_users': 9999,
            'max_records_per_import': 9999999,
            'data_retention_years': 5,
            'smt_budget': True,
            'rep_access': True,
            'stm_access': True,
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,
            'analytics_advanced': True,            # ✅ Forecasting, Prediction, DRG optimization
            'reconciliation': True,                # ✅ HIS reconciliation
            'api_access': True,                    # ✅ REST API + Webhook
            'custom_reports': True,                # ✅ Custom report builder
            'scheduled_downloads': True,
            'white_label': False,
            'priority_support': True,              # ✅ Email + Phone (1 day response)
            'dedicated_support': False,
            'custom_development': False,
            'sla_guarantee': False
        },
        'enterprise': {
            'tier_name': 'Enterprise',
            'price_per_year': 100000,
            'max_users': 9999,                     # Unlimited
            'max_records_per_import': 9999999,     # Unlimited
            'data_retention_years': 999,           # Unlimited
            'smt_budget': True,
            'rep_access': True,
            'stm_access': True,
            'view_reports': True,
            'export_reports': True,
            'analytics_basic': True,
            'analytics_advanced': True,
            'reconciliation': True,
            'api_access': True,
            'custom_reports': True,
            'scheduled_downloads': True,
            'white_label': True,                   # ✅ Custom branding
            'priority_support': True,
            'dedicated_support': True,             # ✅ Dedicated account manager
            'custom_development': True,            # ✅ 40 hours/year
            'sla_guarantee': True,                 # ✅ 99.5% uptime
            'multi_site': True                     # ✅ Multi-site support
        }
    }

    def __init__(self, license_file='config/license.json'):
        self.license_file = Path(license_file)
        self.license_lic_file = Path('config/license.lic')  # New encrypted format
        self.license_file.parent.mkdir(exist_ok=True)
        self._cached_license = None
        self._cache_time = None
        self._cache_ttl = 3600  # Cache for 1 hour

        # Encryption key for .lic files (must match license server)
        self.encryption_key = os.getenv(
            'LICENSE_ENCRYPTION_KEY',
            'aegisx-license-master-key-change-in-production'
        )

    def _decrypt_lic_file(self, encrypted_data: bytes) -> str:
        """
        Decrypt .lic file data using Fernet

        Args:
            encrypted_data: Encrypted bytes from .lic file

        Returns:
            str: Decrypted JSON string
        """
        # Generate encryption key from master key (same as license server)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'aegisx-license-salt',  # Fixed salt for consistency
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(self.encryption_key.encode()))

        # Decrypt
        fernet = Fernet(key)
        decrypted = fernet.decrypt(encrypted_data)

        return decrypted.decode()

    def _load_lic_file(self) -> Optional[Dict]:
        """
        Load and decrypt .lic file from license server

        Returns:
            License dict compatible with old format, or None if not found/invalid
        """
        if not self.license_lic_file.exists():
            return None

        try:
            # Read encrypted file
            with open(self.license_lic_file, 'rb') as f:
                encrypted_data = f.read()

            # Decrypt
            json_data = self._decrypt_lic_file(encrypted_data)

            # Parse JSON
            license_package = json.loads(json_data)

            # Convert to compatible format
            license_data = {
                'license_key': license_package.get('license_key'),
                'license_token': license_package.get('license_token'),
                'public_key': license_package.get('public_key'),
                'installed_at': license_package.get('metadata', {}).get('created_at'),
                # Additional metadata from .lic file
                '_metadata': license_package.get('metadata', {}),
                '_version': license_package.get('version', '1.0'),
                '_signature': license_package.get('signature')
            }

            return license_data

        except InvalidToken:
            print("Error: Invalid encryption key for .lic file")
            return None
        except json.JSONDecodeError as e:
            print(f"Error: Corrupted .lic file - {e}")
            return None
        except Exception as e:
            print(f"Error loading .lic file: {e}")
            return None

    def load_license(self) -> Optional[Dict]:
        """
        Load license from file with caching

        Tries in order:
        1. Encrypted .lic file (new format from AegisX License Server)
        2. JSON file (legacy format)

        Returns:
            License dict or None if not found
        """
        # Use cache if available and not expired
        if self._cached_license and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_ttl:
                return self._cached_license

        # Try .lic file first (new encrypted format)
        license_data = self._load_lic_file()
        if license_data:
            self._cached_license = license_data
            self._cache_time = datetime.now()
            return license_data

        # Fall back to JSON file (legacy format)
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
        Save license to file (legacy JSON format)

        Args:
            license_key: License key (e.g., REVINT-A1B2C3D4-E5F6G7H8)
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

    def install_license_file(self, lic_file_path: str) -> Tuple[bool, str]:
        """
        Install license from .lic file (encrypted format from AegisX License Server)

        Args:
            lic_file_path: Path to the .lic file to import

        Returns:
            Tuple of (success: bool, message: str)
        """
        import shutil

        try:
            source_path = Path(lic_file_path)

            if not source_path.exists():
                return False, f"File not found: {lic_file_path}"

            if not source_path.suffix.lower() == '.lic':
                return False, "Invalid file format. Expected .lic file"

            # Try to read and validate the file first
            with open(source_path, 'rb') as f:
                encrypted_data = f.read()

            # Try to decrypt to validate
            try:
                json_data = self._decrypt_lic_file(encrypted_data)
                license_package = json.loads(json_data)

                # Validate required fields
                if not license_package.get('license_token'):
                    return False, "Invalid license file: missing license token"
                if not license_package.get('public_key'):
                    return False, "Invalid license file: missing public key"

            except InvalidToken:
                return False, "Cannot decrypt license file. Please check LICENSE_ENCRYPTION_KEY in your .env"
            except json.JSONDecodeError:
                return False, "Invalid license file format"

            # Copy file to config directory
            shutil.copy2(source_path, self.license_lic_file)

            # Remove old JSON license if exists (prefer .lic format)
            if self.license_file.exists():
                self.license_file.unlink()

            # Clear cache
            self._cached_license = None
            self._cache_time = None

            # Get license info
            metadata = license_package.get('metadata', {})
            hospital_name = metadata.get('hospital_name', 'Unknown')
            tier = metadata.get('tier', 'unknown')
            expiry_date = metadata.get('expiry_date', 'Unknown')

            return True, f"License installed successfully for {hospital_name} (Tier: {tier}, Expires: {expiry_date})"

        except Exception as e:
            return False, f"Error installing license: {str(e)}"

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
            tier = payload.get('tier', 'free')
            payload['_features'] = self.TIER_FEATURES.get(tier, self.TIER_FEATURES['free'])

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
            # No license or invalid → Free tier (SMT only)
            return {
                'is_valid': False,
                'status': 'free',
                'error': error,
                'tier': 'free',
                'features': self.TIER_FEATURES['free'],
                'days_until_expiry': None,
                'grace_period': False,
                'grace_days_left': 0,
                'max_users': None,
                'expires_at': None,
                'issued_at': None,
                'license_key': None,
                'license_type': 'free',
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
            'tier': payload.get('tier', 'free'),
            'license_type': payload.get('license_type', 'free'),
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
        - 'active': License valid, all features available (REP, STM, SMT)
        - 'grace_period': License expired but within grace period, REP/STM blocked
        - 'free': No license or invalid, SMT only (REP/STM blocked)

        Returns:
            License state string ('active', 'grace_period', or 'free')
        """
        is_valid, payload, error = self.verify_license()

        # If verification failed completely (no license or invalid)
        if not is_valid:
            return 'free'

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
            # Free tier - limited features (SMT only)
            return self.TIER_FEATURES['free'].get(feature, False)

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
            'free': 'ฟรี',
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
        Remove installed license (both .lic and .json formats)

        Returns:
            True if successful
        """
        try:
            # Remove .lic file
            if self.license_lic_file.exists():
                self.license_lic_file.unlink()

            # Remove JSON file
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
