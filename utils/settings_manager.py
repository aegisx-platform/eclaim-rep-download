#!/usr/bin/env python3
"""
Settings Manager - Manage application settings
"""

import json
import random
from pathlib import Path
from typing import Dict, Optional, List, Tuple


class SettingsManager:
    """Manage application settings"""

    def __init__(self, settings_file='config/settings.json'):
        self.settings_file = Path(settings_file)
        self.settings_file.parent.mkdir(exist_ok=True)

        # Default settings
        self.default_settings = {
            # Legacy single credential (for backward compatibility)
            'eclaim_username': '',
            'eclaim_password': '',
            # Multiple credentials support
            'eclaim_credentials': [],  # List of {"username": "", "password": "", "note": "", "enabled": true}
            'download_dir': 'downloads',
            'auto_import_default': False,
            # Global Hospital Settings
            'hospital_code': '',  # 5-digit hospital/vendor code (used for SMT and per-bed KPIs)
            # Unified schedule settings (applies to all data types)
            'schedule_enabled': False,
            'schedule_times': [],
            'schedule_auto_import': True,
            'schedule_schemes': ['ucs', 'ofc', 'sss', 'lgo'],  # Schemes for scheduled downloads
            'schedule_type_rep': True,   # Download REP files in schedule
            'schedule_type_stm': False,  # Download Statement files in schedule
            'schedule_type_smt': False,  # Download SMT Budget in schedule
            'schedule_smt_vendor_id': '', # Vendor ID for SMT schedule (uses hospital_code if empty)
            # Insurance scheme settings
            'enabled_schemes': ['ucs', 'ofc', 'sss', 'lgo'],  # Default 4 main schemes
            # SMT Budget settings
            'smt_enabled': False,
            'smt_vendor_id': '',  # Legacy field - prefer hospital_code
            'smt_schedule_enabled': False,
            'smt_schedule_times': [],
            'smt_auto_save_db': True
        }

    def load_settings(self) -> Dict:
        """Load settings from file"""
        if not self.settings_file.exists():
            return self.default_settings.copy()

        try:
            with open(self.settings_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
                # Merge with defaults to ensure all keys exist
                return {**self.default_settings, **settings}
        except Exception:
            return self.default_settings.copy()

    def save_settings(self, settings: Dict) -> bool:
        """
        Save settings to file

        Args:
            settings: Settings dict to save

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False

    def get_eclaim_credentials(self, random_select: bool = True) -> Tuple[str, str]:
        """
        Get E-Claim credentials (randomly selected if multiple available)

        Args:
            random_select: If True, randomly select from enabled credentials

        Returns:
            (username, password) tuple
        """
        settings = self.load_settings()
        credentials_list = settings.get('eclaim_credentials', [])

        # Filter only enabled credentials
        enabled_creds = [c for c in credentials_list if c.get('enabled', True)]

        if enabled_creds:
            if random_select and len(enabled_creds) > 1:
                cred = random.choice(enabled_creds)
            else:
                cred = enabled_creds[0]
            return (cred.get('username', ''), cred.get('password', ''))

        # Fallback to legacy single credential
        return (
            settings.get('eclaim_username', ''),
            settings.get('eclaim_password', '')
        )

    def get_all_credentials(self) -> List[Dict]:
        """
        Get all E-Claim credentials

        Returns:
            List of credential dicts with username, password, note, enabled
        """
        settings = self.load_settings()
        credentials_list = settings.get('eclaim_credentials', [])

        # If no multiple credentials but has legacy, convert it
        if not credentials_list:
            legacy_user = settings.get('eclaim_username', '')
            legacy_pass = settings.get('eclaim_password', '')
            if legacy_user and legacy_pass:
                return [{
                    'username': legacy_user,
                    'password': legacy_pass,
                    'note': 'Default Account',
                    'enabled': True
                }]

        return credentials_list

    def update_credentials(self, username: str, password: str) -> bool:
        """
        Update E-Claim credentials (legacy single credential mode)
        Also adds to credentials list if not exists

        Args:
            username: E-Claim username
            password: E-Claim password

        Returns:
            True if successful
        """
        settings = self.load_settings()
        settings['eclaim_username'] = username
        settings['eclaim_password'] = password

        # Also update in credentials list
        credentials_list = settings.get('eclaim_credentials', [])
        found = False
        for cred in credentials_list:
            if cred.get('username') == username:
                cred['password'] = password
                found = True
                break

        if not found and username and password:
            credentials_list.append({
                'username': username,
                'password': password,
                'note': 'Default Account',
                'enabled': True
            })
            settings['eclaim_credentials'] = credentials_list

        return self.save_settings(settings)

    def add_credential(self, username: str, password: str, note: str = '', enabled: bool = True) -> bool:
        """
        Add a new E-Claim credential

        Args:
            username: E-Claim username
            password: E-Claim password
            note: Optional note/label for this account
            enabled: Whether this credential is active

        Returns:
            True if successful
        """
        settings = self.load_settings()
        credentials_list = settings.get('eclaim_credentials', [])

        # Check if username already exists
        for cred in credentials_list:
            if cred.get('username') == username:
                # Update existing
                cred['password'] = password
                cred['note'] = note
                cred['enabled'] = enabled
                return self.save_settings(settings)

        # Add new
        credentials_list.append({
            'username': username,
            'password': password,
            'note': note,
            'enabled': enabled
        })
        settings['eclaim_credentials'] = credentials_list

        # Also set as legacy if it's the first one
        if len(credentials_list) == 1:
            settings['eclaim_username'] = username
            settings['eclaim_password'] = password

        return self.save_settings(settings)

    def remove_credential(self, username: str) -> bool:
        """
        Remove an E-Claim credential

        Args:
            username: E-Claim username to remove

        Returns:
            True if successful
        """
        settings = self.load_settings()
        credentials_list = settings.get('eclaim_credentials', [])

        # Filter out the credential
        credentials_list = [c for c in credentials_list if c.get('username') != username]
        settings['eclaim_credentials'] = credentials_list

        # Update legacy credential if needed
        if settings.get('eclaim_username') == username:
            if credentials_list:
                settings['eclaim_username'] = credentials_list[0].get('username', '')
                settings['eclaim_password'] = credentials_list[0].get('password', '')
            else:
                settings['eclaim_username'] = ''
                settings['eclaim_password'] = ''

        return self.save_settings(settings)

    def update_credential(self, username: str, password: str = None, note: str = None, enabled: bool = None) -> bool:
        """
        Update an existing E-Claim credential

        Args:
            username: E-Claim username to update
            password: New password (None to keep existing)
            note: New note (None to keep existing)
            enabled: New enabled state (None to keep existing)

        Returns:
            True if successful
        """
        settings = self.load_settings()
        credentials_list = settings.get('eclaim_credentials', [])

        for cred in credentials_list:
            if cred.get('username') == username:
                if password is not None:
                    cred['password'] = password
                if note is not None:
                    cred['note'] = note
                if enabled is not None:
                    cred['enabled'] = enabled
                return self.save_settings(settings)

        return False

    def set_all_credentials(self, credentials: List[Dict]) -> bool:
        """
        Set all E-Claim credentials (replace all)

        Args:
            credentials: List of credential dicts with username, password, note, enabled

        Returns:
            True if successful
        """
        settings = self.load_settings()

        # Validate and clean credentials
        clean_creds = []
        for cred in credentials:
            if cred.get('username') and cred.get('password'):
                clean_creds.append({
                    'username': cred.get('username', ''),
                    'password': cred.get('password', ''),
                    'note': cred.get('note', ''),
                    'enabled': cred.get('enabled', True)
                })

        settings['eclaim_credentials'] = clean_creds

        # Update legacy credential
        if clean_creds:
            settings['eclaim_username'] = clean_creds[0].get('username', '')
            settings['eclaim_password'] = clean_creds[0].get('password', '')
        else:
            settings['eclaim_username'] = ''
            settings['eclaim_password'] = ''

        return self.save_settings(settings)

    def has_credentials(self) -> bool:
        """Check if credentials are configured"""
        credentials = self.get_all_credentials()
        if credentials:
            enabled = [c for c in credentials if c.get('enabled', True)]
            return len(enabled) > 0

        # Fallback to legacy
        username, password = self.get_eclaim_credentials(random_select=False)
        return bool(username and password)

    def get_credentials_count(self) -> Dict:
        """
        Get count of credentials

        Returns:
            Dict with total and enabled counts
        """
        credentials = self.get_all_credentials()
        enabled = [c for c in credentials if c.get('enabled', True)]
        return {
            'total': len(credentials),
            'enabled': len(enabled)
        }

    def get_schedule_settings(self) -> Dict:
        """
        Get unified schedule settings

        Returns:
            Dict with schedule_enabled, schedule_times, schedule_auto_import,
            schedule_schemes, schedule_type_rep, schedule_type_stm, schedule_type_smt,
            schedule_smt_vendor_id, schedule_parallel_download, schedule_parallel_workers
        """
        settings = self.load_settings()
        # For SMT vendor ID, use schedule_smt_vendor_id first, then hospital_code
        smt_vendor = settings.get('schedule_smt_vendor_id', '')
        if not smt_vendor:
            smt_vendor = self.get_hospital_code()

        return {
            'schedule_enabled': settings.get('schedule_enabled', False),
            'schedule_times': settings.get('schedule_times', []),
            'schedule_auto_import': settings.get('schedule_auto_import', True),
            'schedule_schemes': settings.get('schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo']),
            'schedule_type_rep': settings.get('schedule_type_rep', True),
            'schedule_type_stm': settings.get('schedule_type_stm', False),
            'schedule_type_smt': settings.get('schedule_type_smt', False),
            'schedule_smt_vendor_id': smt_vendor,
            'schedule_parallel_download': settings.get('schedule_parallel_download', False),
            'schedule_parallel_workers': settings.get('schedule_parallel_workers', 3)
        }

    def update_schedule_settings(self, enabled: bool, times: list, auto_import: bool,
                                   type_rep: bool = True, type_stm: bool = False,
                                   type_smt: bool = False, smt_vendor_id: str = '',
                                   parallel_download: bool = False, parallel_workers: int = 3) -> bool:
        """
        Update unified schedule settings

        Args:
            enabled: Whether scheduling is enabled
            times: List of time dicts like [{"hour": 9, "minute": 0}, ...]
            auto_import: Whether to auto-import after download
            type_rep: Download REP files in schedule
            type_stm: Download Statement files in schedule
            type_smt: Download SMT Budget in schedule
            smt_vendor_id: Vendor ID for SMT schedule
            parallel_download: Whether to use parallel download for REP files
            parallel_workers: Number of parallel workers (2-5)

        Returns:
            True if successful
        """
        settings = self.load_settings()
        settings['schedule_enabled'] = enabled
        settings['schedule_times'] = times
        settings['schedule_auto_import'] = auto_import
        settings['schedule_type_rep'] = type_rep
        settings['schedule_type_stm'] = type_stm
        settings['schedule_type_smt'] = type_smt
        settings['schedule_smt_vendor_id'] = smt_vendor_id
        settings['schedule_parallel_download'] = parallel_download
        settings['schedule_parallel_workers'] = min(max(int(parallel_workers), 2), 5)  # Clamp 2-5
        return self.save_settings(settings)

    def get_smt_settings(self) -> Dict:
        """
        Get SMT Budget settings

        Returns:
            Dict with SMT settings
        """
        settings = self.load_settings()
        return {
            'smt_enabled': settings.get('smt_enabled', False),
            'smt_vendor_id': settings.get('smt_vendor_id', ''),
            'smt_schedule_enabled': settings.get('smt_schedule_enabled', False),
            'smt_schedule_times': settings.get('smt_schedule_times', []),
            'smt_auto_save_db': settings.get('smt_auto_save_db', True)
        }

    def update_smt_settings(self, vendor_id: str, schedule_enabled: bool,
                            times: list, auto_save_db: bool) -> bool:
        """
        Update SMT Budget settings

        Args:
            vendor_id: Hospital/Vendor ID
            schedule_enabled: Whether scheduling is enabled
            times: List of time dicts like [{"hour": 9, "minute": 0}, ...]
            auto_save_db: Whether to auto-save to database

        Returns:
            True if successful
        """
        settings = self.load_settings()
        settings['smt_enabled'] = bool(vendor_id)
        settings['smt_vendor_id'] = vendor_id
        settings['smt_schedule_enabled'] = schedule_enabled
        settings['smt_schedule_times'] = times
        settings['smt_auto_save_db'] = auto_save_db
        return self.save_settings(settings)

    # ===== Insurance Scheme Settings =====

    def get_enabled_schemes(self) -> list:
        """
        Get list of enabled insurance scheme codes

        Returns:
            List of scheme codes like ['ucs', 'ofc', 'sss', 'lgo']
        """
        settings = self.load_settings()
        return settings.get('enabled_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

    def update_enabled_schemes(self, schemes: list) -> bool:
        """
        Update enabled insurance schemes

        Args:
            schemes: List of scheme codes to enable

        Returns:
            True if successful
        """
        # Validate schemes
        valid_schemes = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']
        schemes = [s.lower() for s in schemes if s.lower() in valid_schemes]

        if not schemes:
            # Default to UCS if nothing selected
            schemes = ['ucs']

        settings = self.load_settings()
        settings['enabled_schemes'] = schemes
        return self.save_settings(settings)

    def is_scheme_enabled(self, scheme: str) -> bool:
        """
        Check if a specific scheme is enabled

        Args:
            scheme: Scheme code to check

        Returns:
            True if scheme is enabled
        """
        enabled = self.get_enabled_schemes()
        return scheme.lower() in [s.lower() for s in enabled]

    def get_setting(self, key: str, default=None):
        """
        Get a specific setting by key

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        settings = self.load_settings()
        return settings.get(key, default)

    # ===== Hospital Settings =====

    def get_hospital_code(self) -> str:
        """
        Get the global hospital code.
        Falls back to smt_vendor_id for backward compatibility.

        Returns:
            Hospital code (5-digit string) or empty string
        """
        settings = self.load_settings()
        hospital_code = settings.get('hospital_code', '').strip()
        if hospital_code:
            return hospital_code
        # Fallback to legacy smt_vendor_id
        return settings.get('smt_vendor_id', '').strip()

    def set_hospital_code(self, hospital_code: str) -> bool:
        """
        Set the global hospital code.
        Also updates smt_vendor_id for backward compatibility.

        Args:
            hospital_code: 5-digit hospital/vendor code

        Returns:
            True if successful
        """
        settings = self.load_settings()
        settings['hospital_code'] = hospital_code.strip()
        # Also update smt_vendor_id for backward compatibility
        settings['smt_vendor_id'] = hospital_code.strip()
        return self.save_settings(settings)

    # ===== STM (Statement) Schedule Settings =====

    def get_stm_schedule_settings(self) -> Dict:
        """
        Get STM (Statement) schedule settings

        Returns:
            Dict with stm_schedule_enabled, stm_schedule_times, stm_schedule_auto_import, stm_schedule_schemes
        """
        settings = self.load_settings()
        return {
            'stm_schedule_enabled': settings.get('stm_schedule_enabled', False),
            'stm_schedule_times': settings.get('stm_schedule_times', []),
            'stm_schedule_auto_import': settings.get('stm_schedule_auto_import', True),
            'stm_schedule_schemes': settings.get('stm_schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])
        }

    def update_stm_schedule_settings(self, enabled: bool, times: list,
                                      auto_import: bool, schemes: list) -> bool:
        """
        Update STM (Statement) schedule settings

        Args:
            enabled: Whether STM scheduling is enabled
            times: List of time dicts like [{"hour": 9, "minute": 0}, ...]
            auto_import: Whether to auto-import after download
            schemes: List of scheme codes to download

        Returns:
            True if successful
        """
        # Validate schemes
        valid_schemes = ['ucs', 'ofc', 'sss', 'lgo']
        schemes = [s.lower() for s in schemes if s.lower() in valid_schemes]
        if not schemes:
            schemes = ['ucs']  # Default fallback

        settings = self.load_settings()
        settings['stm_schedule_enabled'] = enabled
        settings['stm_schedule_times'] = times
        settings['stm_schedule_auto_import'] = auto_import
        settings['stm_schedule_schemes'] = schemes
        return self.save_settings(settings)

    # ===== Schedule Schemes Settings =====

    def get_schedule_schemes(self) -> list:
        """
        Get list of schemes for scheduled downloads

        Returns:
            List of scheme codes
        """
        settings = self.load_settings()
        return settings.get('schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo'])

    def update_schedule_schemes(self, schemes: list) -> bool:
        """
        Update schemes for scheduled downloads

        Args:
            schemes: List of scheme codes

        Returns:
            True if successful
        """
        # Validate schemes
        valid_schemes = ['ucs', 'ofc', 'sss', 'lgo', 'nhs', 'bkk', 'bmt', 'srt']
        schemes = [s.lower() for s in schemes if s.lower() in valid_schemes]

        if not schemes:
            schemes = ['ucs']  # Default fallback

        settings = self.load_settings()
        settings['schedule_schemes'] = schemes
        return self.save_settings(settings)
