#!/usr/bin/env python3
"""
Create User Script - Generate user accounts for development/production

Usage:
    # Create admin with random password
    python scripts/create_user.py

    # Create admin with specific password
    python scripts/create_user.py --password MyPassword123

    # Create user with specific role
    python scripts/create_user.py --username john --email john@example.com --role user

    # Create admin with all options
    python scripts/create_user.py --username admin --password Admin123 --email admin@local --role admin
"""

import argparse
import secrets
import string
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.database import get_db_config, DB_TYPE


def get_db_connection():
    """Get database connection based on DB_TYPE."""
    config = get_db_config()

    if DB_TYPE == 'mysql':
        import pymysql
        return pymysql.connect(**config)
    else:
        import psycopg2
        return psycopg2.connect(**config)


def generate_password(length=12):
    """Generate a secure random password."""
    chars = string.ascii_letters + string.digits + '!@#$%^&*'
    password = [
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.digits),
        secrets.choice('!@#$%^&*'),
    ]
    password.extend(secrets.choice(chars) for _ in range(length - 4))
    secrets.SystemRandom().shuffle(password)
    return ''.join(password)


def user_exists(cursor, username):
    """Check if username already exists."""
    cursor.execute('SELECT id FROM users WHERE username = %s', (username,))
    return cursor.fetchone() is not None


def create_user(username, password, email, role):
    """Create a new user in the database."""
    import bcrypt

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check if user exists
        if user_exists(cursor, username):
            print(f'❌ User "{username}" already exists')
            print(f'   Use --force to delete and recreate')
            return False

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # Insert user
        cursor.execute('''
            INSERT INTO users (username, password_hash, email, role, is_active)
            VALUES (%s, %s, %s, %s, %s)
        ''', (username, password_hash, email, role, True))

        conn.commit()
        return True

    finally:
        cursor.close()
        conn.close()


def delete_user(username):
    """Delete a user from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('DELETE FROM users WHERE username = %s', (username,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        cursor.close()
        conn.close()


def list_users():
    """List all users in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('SELECT id, username, email, role, is_active FROM users ORDER BY id')
        rows = cursor.fetchall()

        if not rows:
            print('No users found')
            return

        print(f'\n{"ID":<5} {"Username":<20} {"Email":<30} {"Role":<10} {"Active":<8}')
        print('-' * 75)
        for row in rows:
            active = '✓' if row[4] else '✗'
            print(f'{row[0]:<5} {row[1]:<20} {row[2]:<30} {row[3]:<10} {active:<8}')
        print()

    finally:
        cursor.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description='Create user accounts for the application',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python scripts/create_user.py                           # Create admin with random password
  python scripts/create_user.py --password MyPass123      # Create admin with specific password
  python scripts/create_user.py --username john --role user  # Create regular user
  python scripts/create_user.py --list                    # List all users
  python scripts/create_user.py --delete admin            # Delete user
        '''
    )

    parser.add_argument('--username', '-u', default='admin',
                        help='Username (default: admin)')
    parser.add_argument('--password', '-p',
                        help='Password (default: random generated)')
    parser.add_argument('--email', '-e',
                        help='Email (default: username@local.dev)')
    parser.add_argument('--role', '-r', choices=['admin', 'user'], default='admin',
                        help='User role (default: admin)')
    parser.add_argument('--force', '-f', action='store_true',
                        help='Force create (delete existing user first)')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all users')
    parser.add_argument('--delete', '-d', metavar='USERNAME',
                        help='Delete a user by username')

    args = parser.parse_args()

    # List users
    if args.list:
        list_users()
        return

    # Delete user
    if args.delete:
        if delete_user(args.delete):
            print(f'✓ Deleted user: {args.delete}')
        else:
            print(f'✗ User not found: {args.delete}')
        return

    # Generate password if not provided
    password = args.password or generate_password()

    # Default email
    email = args.email or f'{args.username}@local.dev'

    # Force delete if exists
    if args.force:
        delete_user(args.username)

    # Create user
    if create_user(args.username, password, email, args.role):
        print()
        print('=' * 50)
        print('✓ User created successfully!')
        print('=' * 50)
        print(f'  Username: {args.username}')
        print(f'  Password: {password}')
        print(f'  Email:    {email}')
        print(f'  Role:     {args.role}')
        print('=' * 50)
        print()


if __name__ == '__main__':
    main()
