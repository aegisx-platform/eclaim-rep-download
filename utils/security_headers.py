"""
Security Headers Configuration

Implements comprehensive security headers for Flask application.
Protects against XSS, clickjacking, MIME sniffing, and other web vulnerabilities.

Headers implemented:
- Content-Security-Policy (CSP)
- Permissions-Policy
- X-Content-Type-Options
- X-Frame-Options
- X-XSS-Protection
- Referrer-Policy
- Strict-Transport-Security (HSTS)

Usage:
    from utils.security_headers import setup_security_headers

    app = Flask(__name__)
    setup_security_headers(app)
"""

from flask import Flask


def get_csp_header(mode: str = 'strict') -> str:
    """
    Generate Content Security Policy header.

    CSP prevents XSS, clickjacking, and other code injection attacks
    by controlling which resources can be loaded.

    Args:
        mode: 'strict' (production) or 'permissive' (development)

    Returns:
        CSP header string
    """
    if mode == 'strict':
        # Production: Strict CSP for maximum security
        csp = {
            # Scripts
            'script-src': [
                "'self'",  # Only same-origin scripts
                "'unsafe-inline'",  # Allow inline scripts (needed for some frameworks)
                # Tailwind CDN
                "https://cdn.tailwindcss.com",
                # Chart.js CDN (for analytics)
                "https://cdn.jsdelivr.net",
            ],

            # Styles
            'style-src': [
                "'self'",
                "'unsafe-inline'",  # Allow inline styles
                "https://cdn.tailwindcss.com",
            ],

            # Images
            'img-src': [
                "'self'",
                "data:",  # Allow data URIs (base64 images)
                "https:",  # Allow HTTPS images
            ],

            # Fonts
            'font-src': [
                "'self'",
                "data:",
            ],

            # AJAX/Fetch requests
            'connect-src': [
                "'self'",  # Only same-origin requests
            ],

            # Frames/iframes
            'frame-src': [
                "'none'",  # No iframes allowed
            ],

            # Objects (Flash, etc.)
            'object-src': [
                "'none'",  # No plugins
            ],

            # Base URI (prevents base tag hijacking)
            'base-uri': [
                "'self'",
            ],

            # Form actions
            'form-action': [
                "'self'",  # Forms can only submit to same origin
            ],

            # Upgrade insecure requests (HTTP → HTTPS)
            'upgrade-insecure-requests': [],

            # Block mixed content
            'block-all-mixed-content': [],
        }
    else:
        # Development: Permissive CSP for easier debugging
        csp = {
            'default-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'", "https:", "data:"],
        }

    # Convert to CSP string
    parts = []
    for directive, sources in csp.items():
        if sources:
            parts.append(f"{directive} {' '.join(sources)}")
        else:
            parts.append(directive)

    return '; '.join(parts)


def get_permissions_policy_header() -> str:
    """
    Generate Permissions-Policy header.

    Controls which browser features can be used.
    Replaces deprecated Feature-Policy.

    Returns:
        Permissions-Policy header string
    """
    policies = {
        # Geolocation
        'geolocation': 'none',  # No geolocation access

        # Camera
        'camera': 'none',  # No camera access

        # Microphone
        'microphone': 'none',  # No microphone access

        # Payment
        'payment': 'none',  # No payment API

        # USB
        'usb': 'none',  # No USB access

        # Accelerometer
        'accelerometer': 'none',

        # Ambient light sensor
        'ambient-light-sensor': 'none',

        # Autoplay
        'autoplay': 'none',  # No media autoplay

        # Battery
        'battery': 'none',  # No battery API

        # Clipboard
        'clipboard-read': 'self',  # Allow clipboard read from same origin
        'clipboard-write': 'self',  # Allow clipboard write from same origin

        # Display capture (screen sharing)
        'display-capture': 'none',

        # Fullscreen
        'fullscreen': 'self',  # Allow fullscreen from same origin

        # Gyroscope
        'gyroscope': 'none',

        # Magnetometer
        'magnetometer': 'none',

        # MIDI
        'midi': 'none',

        # Picture-in-picture
        'picture-in-picture': 'none',

        # Speaker selection
        'speaker-selection': 'none',

        # Sync XHR (deprecated)
        'sync-xhr': 'none',  # Prevent synchronous AJAX (bad for performance)

        # Web share
        'web-share': 'none',
    }

    # Convert to Permissions-Policy string
    parts = []
    for feature, allowlist in policies.items():
        if allowlist == 'none':
            parts.append(f"{feature}=()")
        elif allowlist == 'self':
            parts.append(f"{feature}=(self)")
        elif allowlist == '*':
            parts.append(f"{feature}=*")
        else:
            parts.append(f"{feature}=({allowlist})")

    return ', '.join(parts)


def get_feature_policy_header() -> str:
    """
    Generate Feature-Policy header (deprecated, but still supported by older browsers).

    Returns:
        Feature-Policy header string
    """
    policies = {
        'geolocation': "'none'",
        'camera': "'none'",
        'microphone': "'none'",
        'payment': "'none'",
        'usb': "'none'",
        'accelerometer': "'none'",
        'ambient-light-sensor': "'none'",
        'autoplay': "'none'",
        'battery': "'none'",
        'fullscreen': "'self'",
        'gyroscope': "'none'",
        'magnetometer': "'none'",
        'midi': "'none'",
        'picture-in-picture': "'none'",
        'speaker-selection': "'none'",
        'sync-xhr': "'none'",
        'vr': "'none'",
        'xr-spatial-tracking': "'none'",
    }

    parts = []
    for feature, allowlist in policies.items():
        parts.append(f"{feature} {allowlist}")

    return '; '.join(parts)


def setup_security_headers(app: Flask, mode: str = 'strict'):
    """
    Setup security headers for Flask application.

    Args:
        app: Flask application instance
        mode: 'strict' (production) or 'permissive' (development)
    """

    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""

        # Content Security Policy (XSS protection)
        response.headers['Content-Security-Policy'] = get_csp_header(mode)

        # Permissions Policy (feature access control)
        response.headers['Permissions-Policy'] = get_permissions_policy_header()

        # Feature Policy (deprecated, for older browsers)
        response.headers['Feature-Policy'] = get_feature_policy_header()

        # X-Content-Type-Options (prevent MIME sniffing)
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # X-Frame-Options (clickjacking protection)
        # SAMEORIGIN allows framing by same origin only
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'

        # X-XSS-Protection (legacy XSS filter for old browsers)
        # mode=block stops page load if XSS detected
        response.headers['X-XSS-Protection'] = '1; mode=block'

        # Referrer-Policy (control referrer information)
        # strict-origin-when-cross-origin: Send full URL for same-origin,
        # only origin for cross-origin, nothing for downgrade (HTTPS → HTTP)
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'

        # Strict-Transport-Security (HSTS) - only for HTTPS
        # Force HTTPS for 2 years, including subdomains
        if app.config.get('SESSION_COOKIE_SECURE'):
            response.headers['Strict-Transport-Security'] = (
                'max-age=63072000; includeSubDomains; preload'
            )

        # Cross-Origin-Embedder-Policy (COEP)
        # require-corp: Only load resources that explicitly allow it
        response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'

        # Cross-Origin-Opener-Policy (COOP)
        # same-origin: Isolate browsing context
        response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'

        # Cross-Origin-Resource-Policy (CORP)
        # same-origin: Only allow same-origin requests
        response.headers['Cross-Origin-Resource-Policy'] = 'same-origin'

        return response

    return app


def test_security_headers(app: Flask) -> dict:
    """
    Test security headers configuration.

    Args:
        app: Flask application instance

    Returns:
        Dict of header checks and their status
    """
    with app.test_client() as client:
        response = client.get('/')

        checks = {
            'Content-Security-Policy': 'Content-Security-Policy' in response.headers,
            'Permissions-Policy': 'Permissions-Policy' in response.headers,
            'X-Content-Type-Options': response.headers.get('X-Content-Type-Options') == 'nosniff',
            'X-Frame-Options': response.headers.get('X-Frame-Options') == 'SAMEORIGIN',
            'X-XSS-Protection': '1; mode=block' in response.headers.get('X-XSS-Protection', ''),
            'Referrer-Policy': 'Referrer-Policy' in response.headers,
            'Cross-Origin-Embedder-Policy': 'Cross-Origin-Embedder-Policy' in response.headers,
            'Cross-Origin-Opener-Policy': 'Cross-Origin-Opener-Policy' in response.headers,
            'Cross-Origin-Resource-Policy': 'Cross-Origin-Resource-Policy' in response.headers,
        }

        if app.config.get('SESSION_COOKIE_SECURE'):
            checks['Strict-Transport-Security'] = 'Strict-Transport-Security' in response.headers

        return checks
