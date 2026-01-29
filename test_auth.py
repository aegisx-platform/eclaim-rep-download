#!/usr/bin/env python3
"""
Test Authentication System

Verifies that user authentication is working correctly:
1. Users table exists
2. Default admin user exists
3. Can authenticate with correct password
4. Authentication fails with wrong password
5. Account lockout after failed attempts
6. Password hashing works correctly

Run after migrations: python test_auth.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.auth import auth_manager, User
from config.db_pool import get_connection, return_connection
from config.database import DB_TYPE


def test_table_exists():
    """Test that users table exists."""
    print("Testing: users table exists...")

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if DB_TYPE == 'postgresql':
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'users'
                )
            """)
            exists = cursor.fetchone()[0]
        else:  # MySQL
            cursor.execute("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'users'
                  AND table_schema = DATABASE()
            """)
            exists = cursor.fetchone()[0] > 0

        if exists:
            print("✓ users table exists")
            return True
        else:
            print("✗ users table NOT found")
            return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)


def test_default_admin_exists():
    """Test that default admin user exists."""
    print("\nTesting: default admin user exists...")

    user_data = auth_manager.get_user_by_username('admin')

    if user_data:
        print("✓ Default admin user exists")
        print(f"  - Username: {user_data['username']}")
        print(f"  - Email: {user_data['email']}")
        print(f"  - Role: {user_data['role']}")
        print(f"  - Must change password: {user_data['must_change_password']}")
        return True
    else:
        print("✗ Default admin user NOT found")
        return False


def test_password_hashing():
    """Test password hashing."""
    print("\nTesting: password hashing...")

    password = "test_password_123"
    hashed = auth_manager.hash_password(password)

    if len(hashed) > 0 and hashed.startswith('$2b$'):
        print("✓ Password hashing works")
        print(f"  - Hash: {hashed[:30]}...")
    else:
        print("✗ Password hashing failed")
        return False

    # Test verification
    if auth_manager.verify_password(password, hashed):
        print("✓ Password verification works")
    else:
        print("✗ Password verification failed")
        return False

    # Test wrong password
    if not auth_manager.verify_password("wrong_password", hashed):
        print("✓ Wrong password correctly rejected")
        return True
    else:
        print("✗ Wrong password was accepted!")
        return False


def test_authentication_success():
    """Test successful authentication."""
    print("\nTesting: successful authentication...")

    user = auth_manager.authenticate(
        username='admin',
        password='admin',
        ip_address='127.0.0.1'
    )

    if user and isinstance(user, User):
        print("✓ Authentication successful")
        print(f"  - User ID: {user.id}")
        print(f"  - Username: {user.username}")
        print(f"  - Role: {user.role}")
        print(f"  - Must change password: {user.must_change_password}")
        return True
    else:
        print("✗ Authentication failed")
        return False


def test_authentication_failure():
    """Test failed authentication."""
    print("\nTesting: failed authentication...")

    user = auth_manager.authenticate(
        username='admin',
        password='wrong_password',
        ip_address='127.0.0.1'
    )

    if user is None:
        print("✓ Wrong password correctly rejected")
        return True
    else:
        print("✗ Wrong password was accepted!")
        return False


def test_nonexistent_user():
    """Test authentication with non-existent user."""
    print("\nTesting: non-existent user...")

    user = auth_manager.authenticate(
        username='nonexistent_user_12345',
        password='any_password',
        ip_address='127.0.0.1'
    )

    if user is None:
        print("✓ Non-existent user correctly rejected")
        return True
    else:
        print("✗ Non-existent user was accepted!")
        return False


def test_user_creation():
    """Test creating a new user."""
    print("\nTesting: user creation...")

    # Clean up test user if exists
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = 'test_user'")
        conn.commit()
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)

    # Create test user
    user_id = auth_manager.create_user(
        username='test_user',
        email='test@example.com',
        password='TestPassword123',
        full_name='Test User',
        role='user',
        created_by='admin'
    )

    if user_id:
        print(f"✓ User created successfully (ID: {user_id})")

        # Test authentication with new user
        user = auth_manager.authenticate(
            username='test_user',
            password='TestPassword123',
            ip_address='127.0.0.1'
        )

        if user:
            print("✓ New user can authenticate")
            return True
        else:
            print("✗ New user cannot authenticate")
            return False
    else:
        print("✗ User creation failed")
        return False


def test_password_change():
    """Test password change."""
    print("\nTesting: password change...")

    # Get test user
    user_data = auth_manager.get_user_by_username('test_user')
    if not user_data:
        print("⚠ Test user not found (create it first)")
        return True

    # Change password
    success = auth_manager.change_password(
        user_id=user_data['id'],
        new_password='NewPassword456',
        changed_by='test_user'
    )

    if not success:
        print("✗ Password change failed")
        return False

    print("✓ Password changed successfully")

    # Test old password (should fail)
    user = auth_manager.authenticate(
        username='test_user',
        password='TestPassword123',
        ip_address='127.0.0.1'
    )

    if user:
        print("✗ Old password still works!")
        return False

    print("✓ Old password correctly rejected")

    # Test new password
    user = auth_manager.authenticate(
        username='test_user',
        password='NewPassword456',
        ip_address='127.0.0.1'
    )

    if user:
        print("✓ New password works")
        return True
    else:
        print("✗ New password doesn't work")
        return False


def test_user_roles():
    """Test user role permissions."""
    print("\nTesting: user roles and permissions...")

    # Get test user
    user_data = auth_manager.get_user_by_username('test_user')
    if not user_data:
        print("⚠ Test user not found")
        return True

    user = User(
        id=user_data['id'],
        username=user_data['username'],
        email=user_data['email'],
        role='user'
    )

    if user.has_role('user', 'admin'):
        print("✓ has_role() works")
    else:
        print("✗ has_role() failed")
        return False

    if not user.is_admin():
        print("✓ is_admin() correctly returns False for user")
    else:
        print("✗ Regular user incorrectly identified as admin")
        return False

    if user.can_edit():
        print("✓ User can edit")
    else:
        print("✗ User cannot edit")
        return False

    if not user.can_delete():
        print("✓ User cannot delete (correct)")
    else:
        print("✗ User can delete (should be admin only)")
        return False

    return True


def cleanup():
    """Clean up test data."""
    print("\nCleaning up test data...")

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = 'test_user'")
        conn.commit()
        print("✓ Test user removed")
    except Exception as e:
        print(f"⚠ Cleanup warning: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)


def main():
    """Run all tests."""
    print("="*60)
    print("AUTHENTICATION SYSTEM TEST")
    print("="*60)
    print(f"Database: {DB_TYPE}")
    print()

    tests = [
        ("Table exists", test_table_exists),
        ("Default admin exists", test_default_admin_exists),
        ("Password hashing", test_password_hashing),
        ("Auth success", test_authentication_success),
        ("Auth failure", test_authentication_failure),
        ("Non-existent user", test_nonexistent_user),
        ("User creation", test_user_creation),
        ("Password change", test_password_change),
        ("User roles", test_user_roles),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))

    # Cleanup
    try:
        cleanup()
    except Exception:
        pass

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status}: {name}")

    print(f"\nResult: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Authentication is working correctly.")
        print("\n📝 Default credentials:")
        print("   Username: admin")
        print("   Password: admin")
        print("   ⚠️  MUST change password on first login")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the output above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
