/**
 * CSRF Protection Helper for AJAX Requests
 *
 * Automatically adds CSRF tokens to all AJAX requests.
 * Include this file in your HTML templates to enable CSRF protection for fetch/XMLHttpRequest.
 *
 * Usage:
 *   <script src="{{ url_for('static', filename='js/csrf.js') }}"></script>
 *
 * The script will automatically:
 * 1. Add CSRF token to all fetch() requests
 * 2. Add CSRF token to all XMLHttpRequest requests
 * 3. Handle CSRF errors gracefully
 */

// Get CSRF token from meta tag or cookie
function getCSRFToken() {
    // Try to get from meta tag first
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }

    // Try to get from cookie
    const cookieMatch = document.cookie.match(/csrf_token=([^;]+)/);
    if (cookieMatch) {
        return cookieMatch[1];
    }

    // Try to get from form (fallback)
    const formToken = document.querySelector('input[name="csrf_token"]');
    if (formToken) {
        return formToken.value;
    }

    console.warn('CSRF token not found! AJAX requests may fail.');
    return null;
}

// Store original fetch function
const originalFetch = window.fetch;

// Override fetch to automatically add CSRF token
window.fetch = function(url, options = {}) {
    // Don't add CSRF token to GET requests
    if (!options.method || options.method.toUpperCase() === 'GET') {
        return originalFetch(url, options);
    }

    // Get CSRF token
    const csrfToken = getCSRFToken();

    if (csrfToken) {
        // Add CSRF token to headers
        options.headers = options.headers || {};

        // If headers is a Headers object
        if (options.headers instanceof Headers) {
            options.headers.set('X-CSRFToken', csrfToken);
        } else {
            // If headers is a plain object
            options.headers['X-CSRFToken'] = csrfToken;
        }
    }

    // Call original fetch and handle CSRF errors
    return originalFetch(url, options)
        .then(response => {
            // Check for CSRF error
            if (response.status === 400) {
                return response.json().then(data => {
                    if (data.csrf_error) {
                        handleCSRFError(data.error);
                        throw new Error(data.error);
                    }
                    return response;
                }).catch(err => {
                    // If response is not JSON, return it as-is
                    if (err.message && err.message.includes('csrf')) {
                        throw err;
                    }
                    return response;
                });
            }
            return response;
        });
};

// Store original XMLHttpRequest
const originalXHROpen = XMLHttpRequest.prototype.open;
const originalXHRSend = XMLHttpRequest.prototype.send;

// Override XMLHttpRequest to add CSRF token
XMLHttpRequest.prototype.open = function(method, url, ...args) {
    this._method = method;
    this._url = url;
    return originalXHROpen.call(this, method, url, ...args);
};

XMLHttpRequest.prototype.send = function(body) {
    // Add CSRF token to non-GET requests
    if (this._method && this._method.toUpperCase() !== 'GET') {
        const csrfToken = getCSRFToken();
        if (csrfToken) {
            this.setRequestHeader('X-CSRFToken', csrfToken);
        }
    }

    // Add event listener for CSRF errors
    const originalOnLoad = this.onload;
    this.onload = function() {
        if (this.status === 400) {
            try {
                const data = JSON.parse(this.responseText);
                if (data.csrf_error) {
                    handleCSRFError(data.error);
                }
            } catch (e) {
                // Not JSON or parsing error, ignore
            }
        }

        if (originalOnLoad) {
            originalOnLoad.call(this);
        }
    };

    return originalXHRSend.call(this, body);
};

// Handle CSRF errors
function handleCSRFError(message) {
    console.error('CSRF Error:', message);

    // Show user-friendly error message
    if (typeof showNotification === 'function') {
        // If you have a notification system
        showNotification('error', message || 'Security validation failed. Please refresh the page.');
    } else {
        // Fallback to alert
        alert(message || 'Security validation failed. Please refresh the page and try again.');
    }
}

// jQuery AJAX setup (if jQuery is loaded)
if (typeof jQuery !== 'undefined') {
    jQuery.ajaxSetup({
        beforeSend: function(xhr, settings) {
            // Add CSRF token to non-GET requests
            if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type)) {
                const csrfToken = getCSRFToken();
                if (csrfToken) {
                    xhr.setRequestHeader('X-CSRFToken', csrfToken);
                }
            }
        },
        error: function(xhr, status, error) {
            // Handle CSRF errors
            if (xhr.status === 400) {
                try {
                    const data = JSON.parse(xhr.responseText);
                    if (data.csrf_error) {
                        handleCSRFError(data.error);
                    }
                } catch (e) {
                    // Not JSON or parsing error, ignore
                }
            }
        }
    });
}

// Log that CSRF protection is active
console.log('✓ CSRF protection enabled for AJAX requests');

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { getCSRFToken, handleCSRFError };
}
