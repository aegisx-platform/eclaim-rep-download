#!/usr/bin/env python3
"""
Settings Manager - Manage application settings
"""

import json
from pathlib import Path
from typing import Dict, Optional


class SettingsManager:
    """Manage application settings"""

    def __init__(self, settings_file='config/settings.json'):
        self.settings_file = Path(settings_file)
        self.settings_file.parent.mkdir(exist_ok=True)

        # Default settings
        self.default_settings = {
            'eclaim_username': '',
            'eclaim_password': '',
            'download_dir': 'downloads',
            'auto_import_default': False,
            # Unified schedule settings (applies to all data types)
            'schedule_enabled': False,
            'schedule_times': [],
            'schedule_auto_import': True,
            'schedule_schemes': ['ucs', 'ofc', 'sss', 'lgo'],  # Schemes for scheduled downloads
            'schedule_type_rep': True,   # Download REP files in schedule
            'schedule_type_stm': False,  # Download Statement files in schedule
            # Insurance scheme settings
            'enabled_schemes': ['ucs', 'ofc', 'sss', 'lgo'],  # Default 4 main schemes
            # SMT Budget settings
            'smt_enabled': False,
            'smt_vendor_id': '',
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

    def get_eclaim_credentials(self) -> tuple:
        """
        Get E-Claim credentials

        Returns:
            (username, password) tuple
        """
        settings = self.load_settings()
        return (
            settings.get('eclaim_username', ''),
            settings.get('eclaim_password', '')
        )

    def update_credentials(self, username: str, password: str) -> bool:
        """
        Update E-Claim credentials

        Args:
            username: E-Claim username
            password: E-Claim password

        Returns:
            True if successful
        """
        settings = self.load_settings()
        settings['eclaim_username'] = username
        settings['eclaim_password'] = password
        return self.save_settings(settings)

    def has_credentials(self) -> bool:
        """Check if credentials are configured"""
        username, password = self.get_eclaim_credentials()
        return bool(username and password)

    def get_schedule_settings(self) -> Dict:
        """
        Get unified schedule settings

        Returns:
            Dict with schedule_enabled, schedule_times, schedule_auto_import,
            schedule_schemes, schedule_type_rep, schedule_type_stm
        """
        settings = self.load_settings()
        return {
            'schedule_enabled': settings.get('schedule_enabled', False),
            'schedule_times': settings.get('schedule_times', []),
            'schedule_auto_import': settings.get('schedule_auto_import', True),
            'schedule_schemes': settings.get('schedule_schemes', ['ucs', 'ofc', 'sss', 'lgo']),
            'schedule_type_rep': settings.get('schedule_type_rep', True),
            'schedule_type_stm': settings.get('schedule_type_stm', False)
        }

    def update_schedule_settings(self, enabled: bool, times: list, auto_import: bool,
                                   type_rep: bool = True, type_stm: bool = False) -> bool:
        """
        Update unified schedule settings

        Args:
            enabled: Whether scheduling is enabled
            times: List of time dicts like [{"hour": 9, "minute": 0}, ...]
            auto_import: Whether to auto-import after download
            type_rep: Download REP files in schedule
            type_stm: Download Statement files in schedule

        Returns:
            True if successful
        """
        settings = self.load_settings()
        settings['schedule_enabled'] = enabled
        settings['schedule_times'] = times
        settings['schedule_auto_import'] = auto_import
        settings['schedule_type_rep'] = type_rep
        settings['schedule_type_stm'] = type_stm
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
