#!/usr/bin/env python3
"""
Test Security Headers

Verifies that security headers are configured correctly:
1. Content-Security-Policy (CSP)
2. Permissions-Policy
3. X-Content-Type-Options
4. X-Frame-Options
5. X-XSS-Protection
6. Referrer-Policy
7. HSTS (when HTTPS enabled)
8. Cross-Origin policies

Run: python test_security_headers.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from utils.security_headers import (
    setup_security_headers,
    get_csp_header,
    get_permissions_policy_header,
    get_feature_policy_header,
    test_security_headers
)


def test_csp_generation():
    """Test CSP header generation."""
    print("\nTesting: Content Security Policy Generation...")

    # Test strict mode
    csp_strict = get_csp_header(mode='strict')

    if 'script-src' in csp_strict:
        print("✓ CSP contains script-src directive")
    else:
        print("✗ CSP missing script-src")
        return False

    if "'self'" in csp_strict:
        print("✓ CSP allows same-origin resources")
    else:
        print("✗ CSP missing 'self'")
        return False

    if 'upgrade-insecure-requests' in csp_strict:
        print("✓ CSP enforces HTTPS upgrade")
    else:
        print("✗ CSP missing upgrade-insecure-requests")
        return False

    # Test permissive mode
    csp_permissive = get_csp_header(mode='permissive')

    if 'default-src' in csp_permissive:
        print("✓ Permissive CSP uses default-src")
    else:
        print("✗ Permissive CSP missing default-src")
        return False

    return True


def test_permissions_policy_generation():
    """Test Permissions-Policy header generation."""
    print("\nTesting: Permissions-Policy Generation...")

    policy = get_permissions_policy_header()

    required_features = [
        'geolocation',
        'camera',
        'microphone',
        'payment',
        'fullscreen',
    ]

    for feature in required_features:
        if feature in policy:
            print(f"✓ Permissions-Policy controls {feature}")
        else:
            print(f"✗ Permissions-Policy missing {feature}")
            return False

    # Check that sensitive features are disabled
    if 'geolocation=()' in policy:
        print("✓ Geolocation disabled")
    else:
        print("✗ Geolocation not properly disabled")
        return False

    if 'camera=()' in policy:
        print("✓ Camera disabled")
    else:
        print("✗ Camera not properly disabled")
        return False

    return True


def test_feature_policy_generation():
    """Test Feature-Policy header generation (deprecated)."""
    print("\nTesting: Feature-Policy Generation...")

    policy = get_feature_policy_header()

    if "geolocation 'none'" in policy:
        print("✓ Feature-Policy disables geolocation")
    else:
        print("✗ Feature-Policy geolocation not disabled")
        return False

    if "camera 'none'" in policy:
        print("✓ Feature-Policy disables camera")
    else:
        print("✗ Feature-Policy camera not disabled")
        return False

    return True


def test_flask_app_headers():
    """Test headers in actual Flask application."""
    print("\nTesting: Flask Application Headers...")

    # Create test Flask app
    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.route('/')
    def index():
        return 'OK'

    # Setup security headers
    setup_security_headers(app, mode='strict')

    # Test headers
    with app.test_client() as client:
        response = client.get('/')

        # Required headers
        required_headers = {
            'Content-Security-Policy': 'CSP',
            'Permissions-Policy': 'Permissions Policy',
            'X-Content-Type-Options': 'MIME sniffing protection',
            'X-Frame-Options': 'Clickjacking protection',
            'X-XSS-Protection': 'XSS filter',
            'Referrer-Policy': 'Referrer control',
            'Cross-Origin-Embedder-Policy': 'COEP',
            'Cross-Origin-Opener-Policy': 'COOP',
            'Cross-Origin-Resource-Policy': 'CORP',
        }

        for header, description in required_headers.items():
            if header in response.headers:
                print(f"✓ {description} header present")
            else:
                print(f"✗ {description} header missing ({header})")
                return False

        # Check specific values
        if response.headers.get('X-Content-Type-Options') == 'nosniff':
            print("✓ MIME sniffing correctly disabled")
        else:
            print("✗ X-Content-Type-Options value incorrect")
            return False

        if response.headers.get('X-Frame-Options') == 'SAMEORIGIN':
            print("✓ Clickjacking protection configured")
        else:
            print("✗ X-Frame-Options value incorrect")
            return False

    return True


def test_https_headers():
    """Test HTTPS-specific headers."""
    print("\nTesting: HTTPS Headers...")

    # Create test Flask app with HTTPS mode
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SESSION_COOKIE_SECURE'] = True  # Simulate HTTPS

    @app.route('/')
    def index():
        return 'OK'

    setup_security_headers(app, mode='strict')

    with app.test_client() as client:
        response = client.get('/')

        if 'Strict-Transport-Security' in response.headers:
            print("✓ HSTS header present for HTTPS")
        else:
            print("✗ HSTS header missing")
            return False

        hsts = response.headers.get('Strict-Transport-Security', '')
        if 'max-age=63072000' in hsts:
            print("✓ HSTS max-age set to 2 years")
        else:
            print("✗ HSTS max-age incorrect")
            return False

        if 'includeSubDomains' in hsts:
            print("✓ HSTS includes subdomains")
        else:
            print("✗ HSTS missing includeSubDomains")
            return False

    return True


def test_permissive_mode():
    """Test permissive mode (development)."""
    print("\nTesting: Permissive Mode (Development)...")

    app = Flask(__name__)
    app.config['TESTING'] = True

    @app.route('/')
    def index():
        return 'OK'

    setup_security_headers(app, mode='permissive')

    with app.test_client() as client:
        response = client.get('/')

        csp = response.headers.get('Content-Security-Policy', '')

        if "'unsafe-eval'" in csp:
            print("✓ Permissive mode allows unsafe-eval")
        else:
            print("✗ Permissive mode should allow unsafe-eval")
            return False

        print("✓ Permissive mode configured for development")

    return True


def main():
    """Run all tests."""
    print("="*60)
    print("SECURITY HEADERS TEST")
    print("="*60)

    tests = [
        ("CSP Generation", test_csp_generation),
        ("Permissions-Policy Generation", test_permissions_policy_generation),
        ("Feature-Policy Generation", test_feature_policy_generation),
        ("Flask App Headers", test_flask_app_headers),
        ("HTTPS Headers", test_https_headers),
        ("Permissive Mode", test_permissive_mode),
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
        print("\n🎉 All security header tests passed!")
        print("\n✅ Security headers are configured correctly.")
        print("\n🛡️  Protections enabled:")
        print("   - Content Security Policy (XSS prevention)")
        print("   - Permissions Policy (feature access control)")
        print("   - MIME sniffing prevention")
        print("   - Clickjacking protection")
        print("   - XSS filter (legacy browsers)")
        print("   - Referrer control")
        print("   - Cross-Origin isolation")
        print("   - HSTS (HTTPS mode)")
        print("\n📚 See docs/technical/SECURITY_HEADERS.md for details")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
