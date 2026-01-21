#!/usr/bin/env python3
"""
Cleanup Expired Credentials File

Automatically removes .admin-credentials file after 7 days.
Can be run manually or via cron job.

Usage:
    python utils/cleanup_expired_credentials.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta


def cleanup_credentials_file():
    """Remove credentials file if older than 7 days."""
    project_root = Path(__file__).parent.parent
    creds_file = project_root / '.admin-credentials'

    if not creds_file.exists():
        print("[cleanup] No credentials file found")
        return 0

    # Check file age
    file_mtime = datetime.fromtimestamp(creds_file.stat().st_mtime)
    age_days = (datetime.now() - file_mtime).days
    expiry_days = 7

    print(f"[cleanup] Credentials file age: {age_days} days")
    print(f"[cleanup] Expiry threshold: {expiry_days} days")

    if age_days >= expiry_days:
        try:
            creds_file.unlink()
            print(f"[cleanup] ✓ Deleted expired credentials file (age: {age_days} days)")
            print("[cleanup] For security, initial admin credentials have been removed")
            print("[cleanup] If you need to reset password, use the admin panel or database")
            return 0
        except Exception as e:
            print(f"[cleanup] ✗ Error deleting file: {e}")
            return 1
    else:
        days_remaining = expiry_days - age_days
        print(f"[cleanup] Credentials file will expire in {days_remaining} days")
        print(f"[cleanup] Please save credentials to password manager and delete this file")
        return 0


if __name__ == '__main__':
    sys.exit(cleanup_credentials_file())
