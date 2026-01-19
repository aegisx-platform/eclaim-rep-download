#!/usr/bin/env python3
"""
Test Input Validation

Verifies that Pydantic schemas are working correctly:
1. Valid inputs are accepted
2. Invalid inputs are rejected
3. Edge cases are handled
4. Error messages are clear

Run: python test_validation.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.validation import (
    DownloadMonthSchema,
    BulkDownloadSchema,
    FileFilterSchema,
    FileDeleteSchema,
    CredentialsSchema,
    HospitalSettingsSchema,
    PasswordChangeSchema,
    UserCreateSchema
)


def test_download_month_schema():
    """Test DownloadMonthSchema."""
    print("\nTesting: DownloadMonthSchema...")

    # Valid input
    try:
        schema = DownloadMonthSchema(month=12, year=2567)
        print("✓ Valid input accepted")
        assert schema.month == 12
        assert schema.year == 2567
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Invalid month (too large)
    try:
        DownloadMonthSchema(month=13, year=2567)
        print("✗ Invalid month (13) was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid month correctly rejected")

    # Invalid year (too small)
    try:
        DownloadMonthSchema(month=12, year=2500)
        print("✗ Invalid year (2500) was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid year correctly rejected")

    return True


def test_bulk_download_schema():
    """Test BulkDownloadSchema."""
    print("\nTesting: BulkDownloadSchema...")

    # Valid input
    try:
        schema = BulkDownloadSchema(
            start_month=1, start_year=2567,
            end_month=12, end_year=2567
        )
        print("✓ Valid date range accepted")
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Invalid: end before start
    try:
        BulkDownloadSchema(
            start_month=12, start_year=2567,
            end_month=1, end_year=2567
        )
        print("✗ Invalid date range (end before start) was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid date range correctly rejected")

    # Invalid: range too large (> 10 years)
    try:
        BulkDownloadSchema(
            start_month=1, start_year=2560,
            end_month=12, end_year=2580
        )
        print("✗ Too large date range was accepted!")
        return False
    except Exception as e:
        print("✓ Large date range correctly rejected")

    return True


def test_file_filter_schema():
    """Test FileFilterSchema."""
    print("\nTesting: FileFilterSchema...")

    # Valid input
    try:
        schema = FileFilterSchema(page=1, per_page=50)
        print("✓ Valid pagination accepted")
        assert schema.page == 1
        assert schema.per_page == 50
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Invalid: negative page
    try:
        FileFilterSchema(page=-1, per_page=50)
        print("✗ Negative page was accepted!")
        return False
    except Exception as e:
        print("✓ Negative page correctly rejected")

    # Invalid: per_page too large (DoS prevention)
    try:
        FileFilterSchema(page=1, per_page=99999)
        print("✗ Huge per_page was accepted!")
        return False
    except Exception as e:
        print("✓ Large per_page correctly rejected")

    # Invalid file type
    try:
        FileFilterSchema(page=1, per_page=50, file_type='invalid')
        print("✗ Invalid file_type was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid file_type correctly rejected")

    return True


def test_file_delete_schema():
    """Test FileDeleteSchema (Security Critical)."""
    print("\nTesting: FileDeleteSchema (Security)...")

    # Valid input
    try:
        schema = FileDeleteSchema(filename='test.xls', confirm=True)
        print("✓ Valid filename accepted")
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Security: Path traversal attack
    try:
        FileDeleteSchema(filename='../../../etc/passwd', confirm=True)
        print("✗ Path traversal attack was accepted! SECURITY BREACH!")
        return False
    except Exception as e:
        print("✓ Path traversal correctly blocked")

    # Security: Invalid extension
    try:
        FileDeleteSchema(filename='malicious.exe', confirm=True)
        print("✗ Invalid extension was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid extension correctly rejected")

    # Must confirm deletion
    try:
        FileDeleteSchema(filename='test.xls', confirm=False)
        print("✗ Deletion without confirmation was accepted!")
        return False
    except Exception as e:
        print("✓ Deletion without confirmation correctly rejected")

    return True


def test_credentials_schema():
    """Test CredentialsSchema (Security Critical)."""
    print("\nTesting: CredentialsSchema (Security)...")

    # Valid input
    try:
        schema = CredentialsSchema(username='10670', password='secure_pass')
        print("✓ Valid credentials accepted")
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Security: Special characters in username (injection prevention)
    try:
        CredentialsSchema(username='admin\'; DROP TABLE users--', password='pass')
        print("✗ SQL injection attempt in username was accepted! SECURITY BREACH!")
        return False
    except Exception as e:
        print("✓ Malicious username correctly rejected")

    return True


def test_hospital_settings_schema():
    """Test HospitalSettingsSchema."""
    print("\nTesting: HospitalSettingsSchema...")

    # Valid input
    try:
        schema = HospitalSettingsSchema(hospital_code='10670', total_beds=120)
        print("✓ Valid hospital code accepted")
        assert schema.hospital_code == '10670'
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Invalid: wrong length
    try:
        HospitalSettingsSchema(hospital_code='123', total_beds=120)
        print("✗ Invalid hospital code length was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid hospital code length correctly rejected")

    # Invalid: non-numeric
    try:
        HospitalSettingsSchema(hospital_code='ABCDE', total_beds=120)
        print("✗ Non-numeric hospital code was accepted!")
        return False
    except Exception as e:
        print("✓ Non-numeric hospital code correctly rejected")

    return True


def test_password_change_schema():
    """Test PasswordChangeSchema (Security Critical)."""
    print("\nTesting: PasswordChangeSchema (Security)...")

    # Valid input
    try:
        schema = PasswordChangeSchema(
            current_password='old_pass',
            new_password='NewSecure123',
            confirm_password='NewSecure123'
        )
        print("✓ Valid password change accepted")
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Passwords don't match
    try:
        PasswordChangeSchema(
            current_password='old_pass',
            new_password='NewSecure123',
            confirm_password='Different123'
        )
        print("✗ Mismatched passwords were accepted!")
        return False
    except Exception as e:
        print("✓ Mismatched passwords correctly rejected")

    # Weak password (too short)
    try:
        PasswordChangeSchema(
            current_password='old_pass',
            new_password='Short1',
            confirm_password='Short1'
        )
        print("✗ Weak password was accepted!")
        return False
    except Exception as e:
        print("✓ Weak password correctly rejected")

    # Weak password (no uppercase)
    try:
        PasswordChangeSchema(
            current_password='old_pass',
            new_password='lowercase123',
            confirm_password='lowercase123'
        )
        print("✗ Password without uppercase was accepted!")
        return False
    except Exception as e:
        print("✓ Password without uppercase correctly rejected")

    return True


def test_user_create_schema():
    """Test UserCreateSchema."""
    print("\nTesting: UserCreateSchema...")

    # Valid input
    try:
        schema = UserCreateSchema(
            username='testuser',
            email='test@example.com',
            password='Secure123',
            role='user'
        )
        print("✓ Valid user creation accepted")
        assert schema.email == 'test@example.com'  # Should be lowercased
    except Exception as e:
        print(f"✗ Valid input rejected: {e}")
        return False

    # Invalid email
    try:
        UserCreateSchema(
            username='testuser',
            email='invalid_email',
            password='Secure123',
            role='user'
        )
        print("✗ Invalid email was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid email correctly rejected")

    # Invalid role
    try:
        UserCreateSchema(
            username='testuser',
            email='test@example.com',
            password='Secure123',
            role='hacker'
        )
        print("✗ Invalid role was accepted!")
        return False
    except Exception as e:
        print("✓ Invalid role correctly rejected")

    return True


def main():
    """Run all tests."""
    print("="*60)
    print("INPUT VALIDATION TEST")
    print("="*60)

    tests = [
        ("Download Month Schema", test_download_month_schema),
        ("Bulk Download Schema", test_bulk_download_schema),
        ("File Filter Schema", test_file_filter_schema),
        ("File Delete Schema (Security)", test_file_delete_schema),
        ("Credentials Schema (Security)", test_credentials_schema),
        ("Hospital Settings Schema", test_hospital_settings_schema),
        ("Password Change Schema (Security)", test_password_change_schema),
        ("User Create Schema", test_user_create_schema),
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
        print("\n🎉 All validation tests passed!")
        print("\n✅ Input validation is working correctly.")
        print("\n🛡️  Security features verified:")
        print("   - Path traversal prevention")
        print("   - SQL injection prevention")
        print("   - DoS prevention (pagination limits)")
        print("   - Password strength requirements")
        print("   - File extension validation")
        print("\n📚 See docs/technical/INPUT_VALIDATION.md for usage guide")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
