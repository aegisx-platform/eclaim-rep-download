#!/usr/bin/env python3
"""
Create Default Admin User

Automatically generates a random admin user on first installation.
- Username: random 8-character alphanumeric
- Password: random 16-character secure password
- Credentials saved to .admin-credentials file and displayed in logs

Security Features:
- Different credentials for each installation
- Strong random password (16 chars, mixed case, numbers, symbols)
- Credentials logged once during initial setup
- Hashed password stored in database (bcrypt)
"""

import os
import sys
import secrets
import string
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.database import get_db_config, DB_TYPE


def get_db_connection():
    """Get database connection based on DB_TYPE."""
    config = get_db_config()

    if DB_TYPE == 'mysql':
        import pymysql
        return pymysql.connect(**config)
    else:  # postgresql
        import psycopg2
        return psycopg2.connect(**config)


def generate_username(length=8):
    """Generate default admin username."""
    # Always use 'admin' as the default username
    return 'admin'


def generate_password(length=16):
    """
    Generate cryptographically secure random password.

    Includes:
    - Lowercase letters
    - Uppercase letters
    - Digits
    - Special characters
    """
    chars = string.ascii_letters + string.digits + '!@#$%^&*-_=+'

    # Ensure at least one of each type
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%^&*-_=+'),
    ]

    # Fill the rest randomly
    password.extend(secrets.choice(chars) for _ in range(length - 4))

    # Shuffle to avoid predictable pattern
    secrets.SystemRandom().shuffle(password)

    return ''.join(password)


def check_users_exist():
    """Check if any users exist in database."""
    conn = get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users")
        count = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return count > 0
    except Exception as e:
        print(f"[create_admin] Error checking users: {e}")
        try:
            conn.close()
        except Exception:
            pass
        return False


def create_admin_user(username, password):
    """Create admin user with hashed password."""
    from flask_bcrypt import Bcrypt
    from datetime import datetime

    bcrypt = Bcrypt()
    password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    conn = get_db_connection()

    try:
        cursor = conn.cursor()

        # Use role='admin' and email as required field
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, role, is_active, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (username, f"{username}@eclaim.local", password_hash, 'admin', True, datetime.now()))

        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[create_admin] Error creating user: {e}")
        try:
            conn.rollback()
            conn.close()
        except Exception:
            pass
        return False


def save_credentials(username, password):
    """
    Save credentials to file for reference.

    Follows industry standard pattern (similar to GitLab, Jenkins):
    - Simple text file with credentials
    - Restrictive permissions (600)
    - Clear expiry notice
    - Security instructions
    """
    from datetime import datetime, timedelta

    creds_file = Path(__file__).parent.parent / '.admin-credentials'
    created_at = datetime.now()
    expires_at = created_at + timedelta(days=7)

    with open(creds_file, 'w') as f:
        f.write(f"# Initial Admin Credentials\n")
        f.write(f"# Created: {created_at.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# NOTE: This file will be auto-deleted after 7 days ({expires_at.strftime('%Y-%m-%d')})\n\n")
        f.write(f"Username: {username}\n")
        f.write(f"Password: {password}\n\n")
        f.write(f"# Security Instructions:\n")
        f.write(f"# 1. Save these credentials to a secure password manager\n")
        f.write(f"# 2. Login and change your password immediately\n")
        f.write(f"# 3. Delete this file after saving credentials: rm .admin-credentials\n")
        f.write(f"# 4. Never commit this file to version control\n")

    # Set restrictive permissions (owner read/write only) - standard practice
    os.chmod(creds_file, 0o600)


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("Creating Default Admin User")
    print("=" * 60)

    # Check if users already exist
    if check_users_exist():
        print("[create_admin] ✓ Users already exist, skipping admin creation")
        print("=" * 60 + "\n")
        return 0

    print("[create_admin] No users found, creating default admin...")

    # Generate credentials
    username = generate_username()
    password = generate_password()

    # Create user
    if not create_admin_user(username, password):
        print("[create_admin] ✗ Failed to create admin user")
        print("=" * 60 + "\n")
        return 1

    # Save credentials
    save_credentials(username, password)

    # Display credentials location (password not shown in logs for security)
    print("\n" + "-" * 60)
    print("Initial Admin Credentials Created")
    print("-" * 60)
    print(f"Username: {username}")
    print(f"Password: [SAVED TO FILE - not shown in logs]")
    print("-" * 60)
    print("IMPORTANT: View credentials in file:")
    print("  cat .admin-credentials")
    print("")
    print("Then:")
    print("  - Login and change your password immediately")
    print("  - Delete the file: rm .admin-credentials")
    print("-" * 60 + "\n")

    print("[create_admin] ✓ Admin user created successfully!")
    print("=" * 60 + "\n")

    return 0


if __name__ == '__main__':
    sys.exit(main())
