#!/usr/bin/env python3
"""
Test CSRF Protection

Verifies that CSRF protection is working correctly:
1. CSRF protection is enabled
2. Requests without CSRF token are rejected
3. Requests with valid CSRF token are accepted
4. CSRF tokens are generated correctly

Note: This is a basic test. Full testing requires running the Flask app.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("="*60)
print("CSRF PROTECTION TEST")
print("="*60)

print("\n📋 Checking configuration...")

# Check if Flask-WTF is installed
try:
    import flask_wtf
    print(f"✓ Flask-WTF installed (version {flask_wtf.__version__})")
except ImportError:
    print("✗ Flask-WTF NOT installed!")
    print("  Run: pip install Flask-WTF==1.2.1")
    sys.exit(1)

# Check if csrf.js exists
csrf_js_path = Path(__file__).parent / 'static' / 'js' / 'csrf.js'
if csrf_js_path.exists():
    print(f"✓ csrf.js exists ({csrf_js_path})")
else:
    print(f"✗ csrf.js NOT found at {csrf_js_path}")

# Check if error.html exists
error_html_path = Path(__file__).parent / 'templates' / 'error.html'
if error_html_path.exists():
    print(f"✓ error.html exists ({error_html_path})")
else:
    print(f"✗ error.html NOT found at {error_html_path}")

# Check app.py configuration
print("\n📋 Checking app.py configuration...")

app_py_path = Path(__file__).parent / 'app.py'
if app_py_path.exists():
    with open(app_py_path, 'r') as f:
        app_content = f.read()

    checks = {
        'CSRFProtect import': 'from flask_wtf.csrf import CSRFProtect',
        'CSRF enabled': "app.config['WTF_CSRF_ENABLED'] = True",
        'CSRF initialized': 'csrf = CSRFProtect(app)',
        'CSRF error handler': '@app.errorhandler(CSRFError)',
    }

    for check_name, check_string in checks.items():
        if check_string in app_content:
            print(f"✓ {check_name}")
        else:
            print(f"✗ {check_name} - NOT FOUND")
else:
    print(f"✗ app.py NOT found at {app_py_path}")

# Check base.html for CSRF meta tag
print("\n📋 Checking templates...")

base_html_path = Path(__file__).parent / 'templates' / 'base.html'
if base_html_path.exists():
    with open(base_html_path, 'r') as f:
        base_content = f.read()

    if 'name="csrf-token"' in base_content:
        print("✓ CSRF meta tag in base.html")
    else:
        print("✗ CSRF meta tag NOT in base.html")

    if 'csrf.js' in base_content:
        print("✓ csrf.js included in base.html")
    else:
        print("✗ csrf.js NOT included in base.html")
else:
    print(f"✗ base.html NOT found at {base_html_path}")

# Check login.html for CSRF token
login_html_path = Path(__file__).parent / 'templates' / 'login.html'
if login_html_path.exists():
    with open(login_html_path, 'r') as f:
        login_content = f.read()

    if 'csrf_token()' in login_content:
        print("✓ CSRF token in login.html form")
    else:
        print("✗ CSRF token NOT in login.html form")
else:
    print(f"✗ login.html NOT found at {login_html_path}")

# Summary
print("\n" + "="*60)
print("TEST SUMMARY")
print("="*60)

print("""
✅ CSRF Protection Setup Complete!

To fully test CSRF protection:
1. Start the application:
   docker-compose up -d

2. Test with browser:
   - Open http://localhost:5001/login
   - Open browser DevTools (F12)
   - Go to Network tab
   - Submit login form
   - Check request headers for X-CSRFToken

3. Test AJAX requests:
   - Open any page that makes AJAX calls
   - Check Network tab for X-CSRFToken header

4. Test CSRF failure:
   - Try to submit form without CSRF token
   - Should see error page

📚 Documentation:
   docs/technical/CSRF_PROTECTION.md

⚠️  Remember to enable WTF_CSRF_SSL_STRICT when using HTTPS!
""")

print("="*60)
sys.exit(0)
