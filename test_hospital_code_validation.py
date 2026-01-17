#!/usr/bin/env python3
"""
Test Hospital Code Validation in License System
"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from utils.license_checker import LicenseChecker
from utils.settings_manager import SettingsManager


def test_hospital_code_validation():
    """Test license validation with hospital code matching"""

    print("=" * 70)
    print("🧪 Testing Hospital Code Validation")
    print("=" * 70)
    print()

    # Initialize managers
    checker = LicenseChecker(license_file='config/license_test.json')
    settings_manager = SettingsManager()

    # Test 1: Load test license from test_licenses.json
    print("📋 Test 1: Load test license data")
    test_licenses_file = Path('config/test_licenses.json')

    if not test_licenses_file.exists():
        print("❌ test_licenses.json not found!")
        print("   Please run: python utils/generate_test_license.py")
        return False

    with open(test_licenses_file, 'r') as f:
        test_licenses = json.load(f)

    # Use professional license for testing
    professional_license = test_licenses.get('professional', {})
    license_key = professional_license.get('license_key')
    license_token = professional_license.get('license_token')
    public_key = professional_license.get('public_key')

    if not license_key or not license_token or not public_key:
        print("❌ Professional license data incomplete!")
        return False

    print(f"✅ Loaded professional license: {license_key}")
    print()

    # Test 2: Set matching hospital code
    print("📋 Test 2: Test with MATCHING hospital code")
    print("   Setting hospital code to: 10670")
    settings_manager.set_hospital_code('10670')

    # Save test license
    checker.save_license(license_key, license_token, public_key)

    # Verify license
    is_valid, payload, error = checker.verify_license()

    if is_valid:
        print(f"✅ PASS - License valid for hospital code: {payload.get('hospital_code')}")
        print(f"   Tier: {payload.get('tier')}")
    else:
        print(f"❌ FAIL - Expected valid, got error: {error}")
        return False

    print()

    # Test 3: Test with mismatched hospital code
    print("📋 Test 3: Test with MISMATCHED hospital code")
    print("   Changing hospital code to: 99999 (different from license)")
    settings_manager.set_hospital_code('99999')

    # Verify license again (should fail)
    is_valid, payload, error = checker.verify_license()

    if not is_valid:
        print(f"✅ PASS - License correctly rejected")
        print(f"   Error: {error}")
    else:
        print(f"❌ FAIL - Expected invalid, but license was accepted!")
        return False

    print()

    # Test 4: Test with no hospital code in settings
    print("📋 Test 4: Test with NO hospital code in settings")
    print("   Clearing hospital code from settings")
    settings_manager.set_hospital_code('')

    # Verify license (should pass - no code to match)
    is_valid, payload, error = checker.verify_license()

    if is_valid:
        print(f"✅ PASS - License valid when no hospital code configured")
    else:
        print(f"❌ FAIL - Expected valid, got error: {error}")
        return False

    print()

    # Cleanup
    print("🧹 Cleaning up test files...")
    if Path('config/license_test.json').exists():
        Path('config/license_test.json').unlink()

    # Restore hospital code
    settings_manager.set_hospital_code('10670')

    print()
    print("=" * 70)
    print("✅ All tests PASSED!")
    print("=" * 70)
    print()
    print("📖 What was tested:")
    print("1. ✅ License with matching hospital code → Valid")
    print("2. ✅ License with mismatched hospital code → Invalid")
    print("3. ✅ License with no hospital code configured → Valid (no enforcement)")
    print()

    return True


if __name__ == '__main__':
    try:
        success = test_hospital_code_validation()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
