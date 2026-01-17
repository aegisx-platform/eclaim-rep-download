# CSRF Protection Guide

> Complete guide to CSRF (Cross-Site Request Forgery) protection in E-Claim System

**Status:** ✅ CSRF Protection Enabled
**Framework:** Flask-WTF 1.2.1
**Date:** 2026-01-17

---

## What is CSRF?

CSRF (Cross-Site Request Forgery) is an attack that tricks users into executing unwanted actions on a web application where they're authenticated.

### Example Attack Scenario:

1. User logs into E-Claim system (legitimate)
2. User visits malicious website in another tab
3. Malicious site sends hidden request to E-Claim system
4. Without CSRF protection, the request is executed as the logged-in user

**Our Protection:** Every state-changing request (POST, PUT, DELETE) requires a unique CSRF token that malicious sites cannot obtain.

---

## How It Works

### 1. Token Generation
When a page loads, Flask-WTF generates a unique CSRF token tied to the user's session.

### 2. Token Validation
Every POST/PUT/DELETE request must include this token. The server validates:
- Token exists
- Token matches the user's session
- Token hasn't been tampered with

### 3. Automatic Protection
- **HTML Forms:** Add `{{ csrf_token() }}` to forms
- **AJAX Requests:** Include `/static/js/csrf.js` - it handles everything automatically

---

## Usage Guide

### For HTML Forms

Add CSRF token to all forms with POST method:

```html
<form method="POST" action="/api/settings">
    <!-- Add CSRF token (REQUIRED) -->
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>

    <!-- Your form fields -->
    <input type="text" name="username">
    <button type="submit">Submit</button>
</form>
```

### For AJAX Requests (Fetch API)

#### Option 1: Automatic (Recommended)

Include `csrf.js` in your template (already in `base.html`):

```html
<script src="{{ url_for('static', filename='js/csrf.js') }}"></script>
```

Then use fetch() normally - CSRF token is added automatically:

```javascript
// CSRF token is automatically added to POST requests
fetch('/api/settings', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({ key: 'value' })
})
.then(response => response.json())
.then(data => console.log(data));
```

#### Option 2: Manual

```javascript
// Get CSRF token from meta tag
const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

// Include in request headers
fetch('/api/settings', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
    },
    body: JSON.stringify({ key: 'value' })
});
```

### For jQuery AJAX

If `csrf.js` is included, jQuery requests are protected automatically:

```javascript
$.ajax({
    url: '/api/settings',
    type: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({ key: 'value' }),
    success: function(data) {
        console.log(data);
    }
});
```

---

## Configuration

CSRF protection is configured in `app.py`:

```python
# CSRF Protection Configuration
app.config['WTF_CSRF_ENABLED'] = True              # Enable CSRF protection
app.config['WTF_CSRF_TIME_LIMIT'] = None           # No time limit
app.config['WTF_CSRF_SSL_STRICT'] = False          # Set True with HTTPS
app.config['WTF_CSRF_CHECK_DEFAULT'] = True        # Check all requests

# Initialize CSRF Protection
csrf = CSRFProtect(app)
```

### Configuration Options

| Option | Value | Description |
|--------|-------|-------------|
| `WTF_CSRF_ENABLED` | `True` | Enable/disable CSRF protection globally |
| `WTF_CSRF_TIME_LIMIT` | `None` | Token expiration (None = never expires) |
| `WTF_CSRF_SSL_STRICT` | `False` | Require HTTPS for cookies (enable in production) |
| `WTF_CSRF_CHECK_DEFAULT` | `True` | Validate CSRF on all POST/PUT/DELETE by default |

---

## Exempting Routes

Some routes may need to be exempt from CSRF (e.g., public APIs):

```python
from flask_wtf.csrf import csrf_exempt

@app.route('/api/public/webhook', methods=['POST'])
@csrf_exempt
def public_webhook():
    """Public webhook - no CSRF validation needed."""
    return jsonify({'status': 'received'})
```

**⚠️ Warning:** Only exempt routes that:
1. Are not user-facing
2. Use alternative authentication (API keys, OAuth)
3. Are read-only operations

---

## Error Handling

### CSRF Validation Failed

When CSRF validation fails, users see a helpful error page:

**For HTML Requests:**
- User-friendly error page (`templates/error.html`)
- Suggests refreshing the page
- Provides common solutions

**For AJAX Requests:**
- JSON response with `csrf_error: true`
- JavaScript automatically shows notification
- User can retry the request

### Common Causes

| Error | Cause | Solution |
|-------|-------|----------|
| CSRF token missing | Form doesn't have `{{ csrf_token() }}` | Add CSRF token to form |
| CSRF token invalid | Page was open too long | Refresh the page |
| CSRF token mismatch | Multiple tabs/sessions | Logout and login again |
| No CSRF token in AJAX | `csrf.js` not included | Add script to template |

---

## Testing CSRF Protection

### Test 1: Form Submission

```html
<!-- This should FAIL (no CSRF token) -->
<form method="POST" action="/api/settings">
    <input type="text" name="username">
    <button type="submit">Submit</button>
</form>

<!-- This should SUCCEED -->
<form method="POST" action="/api/settings">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <input type="text" name="username">
    <button type="submit">Submit</button>
</form>
```

### Test 2: AJAX Request

```javascript
// This should FAIL (no CSRF token)
fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ key: 'value' })
});

// This should SUCCEED (csrf.js adds token automatically)
// Just include csrf.js in your page
```

### Test 3: Programmatic Test

```bash
# Without CSRF token (should fail)
curl -X POST http://localhost:5001/api/settings \
  -H "Content-Type: application/json" \
  -d '{"key":"value"}'
# Expected: 400 Bad Request

# With valid session (should succeed)
# Login first, then make request with session cookie
```

---

## Security Best Practices

### ✅ DO

1. **Always** add CSRF tokens to forms
2. **Always** include `csrf.js` for AJAX-heavy pages
3. **Always** use POST/PUT/DELETE for state-changing operations
4. **Enable** `WTF_CSRF_SSL_STRICT` when using HTTPS
5. **Validate** CSRF tokens on server-side (automatic with Flask-WTF)

### ❌ DON'T

1. **Don't** disable CSRF protection globally
2. **Don't** exempt routes unnecessarily
3. **Don't** use GET requests for state-changing operations
4. **Don't** expose CSRF tokens in URLs
5. **Don't** store CSRF tokens in localStorage (use meta tags)

---

## Troubleshooting

### Problem: "CSRF token missing"

**Cause:** Form doesn't have CSRF token
**Solution:**
```html
<form method="POST">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <!-- ... -->
</form>
```

### Problem: "CSRF validation failed" on AJAX

**Cause:** `csrf.js` not included or CSRF token not in request
**Solution:**
```html
<!-- Add to template -->
<script src="{{ url_for('static', filename='js/csrf.js') }}"></script>
```

### Problem: CSRF errors after long idle time

**Cause:** Session expired but page still open
**Solution:**
- Set appropriate session timeout
- Show warning before session expires
- Auto-refresh CSRF token periodically

### Problem: CSRF errors across multiple tabs

**Cause:** Different sessions in different tabs
**Solution:**
- Use single session across tabs (browser default)
- Logout from one tab logs out all tabs

---

## Migration Guide

### Updating Existing Forms

**Before (No CSRF):**
```html
<form method="POST" action="/api/settings">
    <input type="text" name="username">
    <button type="submit">Submit</button>
</form>
```

**After (With CSRF):**
```html
<form method="POST" action="/api/settings">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
    <input type="text" name="username">
    <button type="submit">Submit</button>
</form>
```

### Updating Existing AJAX

**Before (No CSRF):**
```html
<script>
fetch('/api/settings', { method: 'POST', ... });
</script>
```

**After (With CSRF):**
```html
<script src="{{ url_for('static', filename='js/csrf.js') }}"></script>
<script>
// csrf.js handles CSRF automatically
fetch('/api/settings', { method: 'POST', ... });
</script>
```

---

## API Reference

### Template Functions

| Function | Description | Usage |
|----------|-------------|-------|
| `{{ csrf_token() }}` | Generate CSRF token | `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>` |

### JavaScript Functions (csrf.js)

| Function | Description | Returns |
|----------|-------------|---------|
| `getCSRFToken()` | Get current CSRF token | String |
| `handleCSRFError(message)` | Show CSRF error to user | void |

### Python Decorators

| Decorator | Description | Usage |
|-----------|-------------|-------|
| `@csrf_exempt` | Exempt route from CSRF | Public APIs |

---

## Resources

### Internal Documentation
- Flask-WTF: https://flask-wtf.readthedocs.io/
- OWASP CSRF Guide: https://owasp.org/www-community/attacks/csrf

### Related Files
- Configuration: `app.py` (lines 174-210)
- JavaScript Helper: `static/js/csrf.js`
- Error Template: `templates/error.html`
- Base Template: `templates/base.html` (includes CSRF meta tag)

---

**Last Updated:** 2026-01-17
**Maintainer:** Security Team
**Review:** After any security changes
