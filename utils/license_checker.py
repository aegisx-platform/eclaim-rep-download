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
import socket
import requests
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


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
        self.license_lic_file = Path('config/license.lic')  # JWT RS256 format
        self.license_file.parent.mkdir(exist_ok=True)
        self._cached_license = None
        self._cache_time = None
        self._cache_ttl = 3600  # Cache for 1 hour

        # License server URL for activation notifications (hardcoded for production)
        self.license_server_url = 'https://license.aegisxplatform.com'

        # App info for activation tracking
        self.app_name = 'eclaim-rep-download'
        self.app_version = self._get_app_version()

    def _get_app_version(self) -> str:
        """Get app version from VERSION file"""
        try:
            version_file = Path(__file__).parent.parent / 'VERSION'
            if version_file.exists():
                return version_file.read_text().strip()
        except Exception:
            pass
        return 'unknown'

    def _get_hostname(self) -> str:
        """Get machine hostname"""
        try:
            return socket.gethostname()
        except Exception:
            return 'unknown'

    def _notify_server_activation(self, license_data: Dict) -> Tuple[bool, str]:
        """
        Notify license server that license has been activated

        Args:
            license_data: License data dict with license_key, hospital_code etc.

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            url = f"{self.license_server_url}/api/license/activate"

            payload = {
                'license_key': license_data.get('license_key'),
                'hospital_code': license_data.get('_metadata', {}).get('hospital_code') or license_data.get('hospital_code'),
                'hostname': self._get_hostname(),
                'app_name': self.app_name,
                'app_version': self.app_version
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ License activation reported to server")
                return True, "Activation recorded"
            elif response.status_code == 401:
                # Invalid license key - not found in server database
                logger.warning(f"⚠️ License key not found on server")
                return False, "License key not recognized by server"
            elif response.status_code == 403:
                # License has been revoked
                logger.warning(f"⚠️ License has been revoked")
                return False, "License has been revoked by administrator"
            else:
                logger.warning(f"⚠️ Failed to report activation: {response.status_code}")
                return True, "Activation recorded (server response unexpected)"

        except requests.exceptions.RequestException as e:
            # Don't fail license installation if server is unreachable
            logger.warning(f"⚠️ Could not notify license server: {e}")
            return True, "Activation recorded (server unreachable)"
        except Exception as e:
            logger.warning(f"⚠️ Error notifying license server: {e}")
            return True, "Activation recorded (notification error)"

    def _notify_server_deactivation(self, license_key: str, reason: str = 'user_removed') -> Tuple[bool, str]:
        """
        Notify license server that license has been deactivated/removed

        Args:
            license_key: License key being removed
            reason: Reason for deactivation

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            url = f"{self.license_server_url}/api/license/deactivate"

            payload = {
                'license_key': license_key,
                'hostname': self._get_hostname(),
                'reason': reason
            }

            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                logger.info(f"✅ License deactivation reported to server")
                return True, "Deactivation recorded"
            elif response.status_code == 401:
                logger.warning(f"⚠️ License key not found on server")
                return True, "Deactivation recorded (license not found on server)"
            else:
                logger.warning(f"⚠️ Failed to report deactivation: {response.status_code}")
                return True, "Deactivation recorded (server response unexpected)"

        except requests.exceptions.RequestException as e:
            logger.warning(f"⚠️ Could not notify license server: {e}")
            return True, "Deactivation recorded (server unreachable)"
        except Exception as e:
            logger.warning(f"⚠️ Error notifying license server: {e}")
            return True, "Deactivation recorded (notification error)"

    def _load_lic_file(self) -> Optional[Dict]:
        """
        Load .lic file (plain JSON with JWT RS256 token)

        The .lic file contains:
        - license_token: JWT signed with RS256 (private key on server)
        - public_key: RSA public key to verify JWT signature
        - metadata: License information

        Security: JWT signature prevents tampering. Public key can be safely distributed.
        Only the license server with private key can create valid licenses.

        Returns:
            License dict compatible with old format, or None if not found/invalid
        """
        if not self.license_lic_file.exists():
            return None

        try:
            # Read plain JSON file
            with open(self.license_lic_file, 'r', encoding='utf-8') as f:
                json_data = f.read()

            # Parse JSON
            license_package = json.loads(json_data)

            # Validate required fields
            if not license_package.get('license_token'):
                logger.error("Invalid license file: missing license_token")
                return None
            if not license_package.get('public_key'):
                logger.error("Invalid license file: missing public_key")
                return None

            # Convert to compatible format
            license_data = {
                'license_key': license_package.get('license_key'),
                'license_token': license_package.get('license_token'),
                'public_key': license_package.get('public_key'),
                'installed_at': license_package.get('metadata', {}).get('created_at'),
                # Additional metadata from .lic file
                '_metadata': license_package.get('metadata', {}),
                '_version': license_package.get('version', '2.0'),
                '_format': license_package.get('format', 'jwt-rs256'),
                '_checksum': license_package.get('checksum')
            }

            logger.info(f"✅ License loaded: {license_data.get('license_key')}")
            return license_data

        except json.JSONDecodeError as e:
            logger.error(f"Error: Invalid JSON in .lic file - {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading .lic file: {e}")
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
        Install license from .lic file (JWT RS256 format from AegisX License Server)

        The .lic file is plain JSON containing:
        - license_token: JWT signed with RS256
        - public_key: RSA public key to verify signature
        - metadata: License information

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

            # Read and validate the file
            try:
                with open(source_path, 'r', encoding='utf-8') as f:
                    json_data = f.read()

                license_package = json.loads(json_data)

                # Validate required fields
                if not license_package.get('license_token'):
                    return False, "Invalid license file: missing license token"
                if not license_package.get('public_key'):
                    return False, "Invalid license file: missing public key"

                # Verify JWT signature with embedded public key
                public_key_pem = license_package.get('public_key')
                license_token = license_package.get('license_token')

                public_key = serialization.load_pem_public_key(
                    public_key_pem.encode('utf-8'),
                    backend=default_backend()
                )

                # Decode and verify JWT
                payload = jwt.decode(
                    license_token,
                    public_key,
                    algorithms=['RS256']
                )

                logger.info(f"✅ License signature verified for: {payload.get('license_key')}")

            except json.JSONDecodeError:
                return False, "Invalid license file format (not valid JSON)"
            except jwt.InvalidSignatureError:
                return False, "Invalid license signature - file may be tampered or from unknown source"
            except jwt.ExpiredSignatureError:
                # Allow installation of expired license (will show in UI)
                logger.warning("⚠️ License has expired but will be installed")
            except Exception as e:
                return False, f"License verification failed: {str(e)}"

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

            # Notify license server about activation
            activation_data = {
                'license_key': license_package.get('license_key'),
                '_metadata': metadata
            }
            activation_success, activation_msg = self._notify_server_activation(activation_data)

            # If server says license is invalid or revoked, reject the installation
            if not activation_success:
                # Remove the installed file since server rejected it
                if self.license_lic_file.exists():
                    self.license_lic_file.unlink()
                return False, f"License rejected by server: {activation_msg}"

            # Build success message with activation status
            base_msg = f"License installed successfully for {hospital_name} (Tier: {tier}, Expires: {expiry_date})"

            # Add activation status to message
            if "server unreachable" in activation_msg.lower():
                activation_status = "Activation: Offline (server unreachable)"
            elif "recorded" in activation_msg.lower():
                activation_status = "Activation: Recorded successfully"
            else:
                activation_status = f"Activation: {activation_msg}"

            return True, f"{base_msg}. {activation_status}"

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
            # Get license key before removing for deactivation notification
            license_key = None
            current_license = self.load_license()
            if current_license:
                license_key = current_license.get('license_key')

            # Remove .lic file
            if self.license_lic_file.exists():
                self.license_lic_file.unlink()

            # Remove JSON file
            if self.license_file.exists():
                self.license_file.unlink()

            # Clear cache
            self._cached_license = None
            self._cache_time = None

            # Notify license server about deactivation
            if license_key:
                self._notify_server_deactivation(license_key, reason='user_removed')

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
