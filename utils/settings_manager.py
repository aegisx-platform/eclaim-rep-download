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
            'auto_import_default': False
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
