#!/usr/bin/env python3
"""
Test File Upload Security

Verifies that file upload security validation is working:
1. File type validation (whitelist)
2. File size limits
3. Filename sanitization
4. Magic number verification
5. Path traversal prevention

Run: python test_file_upload_security.py
"""

import sys
import io
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from werkzeug.datastructures import FileStorage
from utils.file_upload_security import (
    FileUploadValidator,
    validate_excel_file,
    validate_csv_file,
    MAGIC_NUMBERS
)


def create_mock_file(filename: str, content: bytes, mimetype: str = 'application/octet-stream'):
    """Create mock FileStorage object for testing."""
    return FileStorage(
        stream=io.BytesIO(content),
        filename=filename,
        content_type=mimetype
    )


def test_filename_sanitization():
    """Test filename sanitization."""
    print("\nTesting: Filename Sanitization...")

    validator = FileUploadValidator(allowed_extensions=['.xls'])

    tests = [
        # (input, expected)
        ('normal_file.xls', 'normal_file.xls'),
        ('file with spaces.xls', 'file_with_spaces.xls'),
        ('../../etc/passwd', 'etc_passwd'),
        ('file<script>.xls', 'file_script_.xls'),
        ('.hidden.xls', '_hidden.xls'),
        ('very' * 100 + '.xls', True),  # Should be truncated
    ]

    for input_name, expected in tests:
        result = validator.sanitize_filename(input_name)

        if expected is True:
            # Just check it's not too long
            if len(result) <= 250:
                print(f"✓ Long filename truncated: {len(input_name)} → {len(result)} chars")
            else:
                print(f"✗ Long filename not truncated: {len(result)}")
                return False
        elif result == expected:
            print(f"✓ Filename sanitized: '{input_name}' → '{result}'")
        else:
            print(f"✗ Sanitization failed: '{input_name}' → '{result}' (expected '{expected}')")
            return False

    return True


def test_path_traversal_prevention():
    """Test path traversal attack prevention."""
    print("\nTesting: Path Traversal Prevention...")

    validator = FileUploadValidator(allowed_extensions=['.xls'])

    # Path traversal attempts
    attacks = [
        '../../../etc/passwd',
        '..\\..\\..\\windows\\system32\\config\\sam',
        'normal/../../../etc/passwd',
    ]

    for attack in attacks:
        # Sanitize
        safe_name = validator.sanitize_filename(attack)

        # Should not contain path separators
        if '..' not in safe_name and '/' not in safe_name and '\\' not in safe_name:
            print(f"✓ Path traversal blocked: '{attack[:30]}...'")
        else:
            print(f"✗ Path traversal NOT blocked: '{attack}'")
            return False

    return True


def test_file_extension_validation():
    """Test file extension validation."""
    print("\nTesting: File Extension Validation...")

    validator = FileUploadValidator(allowed_extensions=['.xls', '.xlsx'])

    # Valid extensions
    valid_files = [
        'test.xls',
        'test.xlsx',
        'TEST.XLS',  # Case insensitive
    ]

    for filename in valid_files:
        file = create_mock_file(filename, b'dummy content')
        result = validator.validate(file)

        if result.is_valid or 'type not allowed' not in result.error_message:
            print(f"✓ Valid extension accepted: {filename}")
        else:
            print(f"✗ Valid extension rejected: {filename}")
            return False

    # Invalid extensions
    invalid_files = [
        'test.exe',
        'test.bat',
        'test.sh',
        'test',  # No extension
    ]

    for filename in invalid_files:
        file = create_mock_file(filename, b'dummy content')
        result = validator.validate(file)

        if not result.is_valid:
            print(f"✓ Invalid extension rejected: {filename}")
        else:
            print(f"✗ Invalid extension accepted: {filename}")
            return False

    return True


def test_file_size_validation():
    """Test file size limits."""
    print("\nTesting: File Size Validation...")

    validator = FileUploadValidator(
        allowed_extensions=['.xls'],
        max_size_mb=0.001,  # 1 KB for testing
        check_magic_numbers=False  # Disable for size testing
    )

    # Small file (should pass)
    small_file = create_mock_file('test.xls', b'x' * 500)
    result = validator.validate(small_file)

    if result.is_valid:
        print("✓ Small file accepted")
    else:
        print(f"✗ Small file rejected: {result.error_message}")
        return False

    # Large file (should fail)
    large_file = create_mock_file('test.xls', b'x' * 2000)
    result = validator.validate(large_file)

    if not result.is_valid and 'too large' in result.error_message.lower():
        print("✓ Large file rejected")
    else:
        print("✗ Large file accepted (should be rejected)")
        return False

    # Empty file (should fail)
    empty_file = create_mock_file('test.xls', b'')
    result = validator.validate(empty_file)

    if not result.is_valid and 'empty' in result.error_message.lower():
        print("✓ Empty file rejected")
    else:
        print("✗ Empty file accepted (should be rejected)")
        return False

    return True


def test_magic_number_validation():
    """Test magic number (file signature) validation."""
    print("\nTesting: Magic Number Validation...")

    validator = FileUploadValidator(
        allowed_extensions=['.xls', '.xlsx'],
        check_magic_numbers=True
    )

    # Real .xls file (OLE2 signature)
    xls_magic = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1' + b'x' * 100
    real_xls = create_mock_file('test.xls', xls_magic)
    result = validator.validate(real_xls)

    if result.is_valid:
        print("✓ Real .xls file accepted (correct magic number)")
    else:
        print(f"✗ Real .xls file rejected: {result.error_message}")
        return False

    # Real .xlsx file (ZIP signature)
    xlsx_magic = b'PK\x03\x04' + b'x' * 100
    real_xlsx = create_mock_file('test.xlsx', xlsx_magic)
    result = validator.validate(real_xlsx)

    if result.is_valid:
        print("✓ Real .xlsx file accepted (correct magic number)")
    else:
        print(f"✗ Real .xlsx file rejected: {result.error_message}")
        return False

    # Fake .xls file (wrong magic number - file type spoofing)
    fake_xls = create_mock_file('virus.xls', b'MZ\x90\x00' + b'x' * 100)  # EXE signature
    result = validator.validate(fake_xls)

    if not result.is_valid and 'mismatch' in result.error_message.lower():
        print("✓ Fake .xls file rejected (wrong magic number)")
    else:
        print("✗ Fake .xls file accepted (should be rejected - file type spoofing)")
        return False

    return True


def test_convenience_validators():
    """Test convenience validator functions."""
    print("\nTesting: Convenience Validators...")

    # Test Excel validator
    xls_magic = b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1' + b'x' * 100
    excel_file = create_mock_file('test.xls', xls_magic)
    result = validate_excel_file(excel_file)

    if result.is_valid:
        print("✓ validate_excel_file() works")
    else:
        print(f"✗ validate_excel_file() failed: {result.error_message}")
        return False

    # Test CSV validator
    csv_file = create_mock_file('test.csv', b'name,age\nJohn,30')
    result = validate_csv_file(csv_file)

    if result.is_valid:
        print("✓ validate_csv_file() works")
    else:
        print(f"✗ validate_csv_file() failed: {result.error_message}")
        return False

    return True


def test_secure_save():
    """Test secure file saving."""
    print("\nTesting: Secure File Saving...")

    import tempfile
    import shutil

    # Create temporary directory
    temp_dir = tempfile.mkdtemp()

    try:
        validator = FileUploadValidator(allowed_extensions=['.xls'])

        # Create test file
        test_file = create_mock_file('test.xls', b'test content')

        # Save securely
        saved_path = validator.save_securely(test_file, temp_dir)

        # Check file exists
        if os.path.exists(saved_path):
            print(f"✓ File saved: {saved_path}")
        else:
            print("✗ File not saved")
            return False

        # Check permissions (should be 600 - owner read/write only)
        permissions = oct(os.stat(saved_path).st_mode)[-3:]
        if permissions == '600':
            print(f"✓ File permissions secure: {permissions}")
        else:
            print(f"⚠ File permissions: {permissions} (expected 600)")

        # Check content
        with open(saved_path, 'rb') as f:
            content = f.read()

        if content == b'test content':
            print("✓ File content correct")
        else:
            print("✗ File content incorrect")
            return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)

    return True


def main():
    """Run all tests."""
    print("="*60)
    print("FILE UPLOAD SECURITY TEST")
    print("="*60)

    tests = [
        ("Filename Sanitization", test_filename_sanitization),
        ("Path Traversal Prevention", test_path_traversal_prevention),
        ("File Extension Validation", test_file_extension_validation),
        ("File Size Validation", test_file_size_validation),
        ("Magic Number Validation", test_magic_number_validation),
        ("Convenience Validators", test_convenience_validators),
        ("Secure File Saving", test_secure_save),
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
        print("\n🎉 All file upload security tests passed!")
        print("\n✅ File upload security verified:")
        print("   - Filename sanitization")
        print("   - Path traversal prevention")
        print("   - File extension validation")
        print("   - File size limits")
        print("   - Magic number verification (file type spoofing prevention)")
        print("   - Secure file storage")
        print("\n🛡️  File upload attacks prevented:")
        print("   - Path traversal (../../../etc/passwd)")
        print("   - File type spoofing (virus.exe → virus.xls)")
        print("   - DoS via large files")
        print("   - Malicious filenames")
        print("\n📚 See docs/technical/FILE_UPLOAD_SECURITY.md for usage")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
