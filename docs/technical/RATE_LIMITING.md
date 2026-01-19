# API Rate Limiting Guide

> Complete guide to API rate limiting with token bucket algorithm

**Security Level:** 🛡️ Enhanced Security (Phase 2)
**Algorithm:** Token Bucket (Industry Standard)
**Date:** 2026-01-17

---

## Why Rate Limiting?

Rate limiting prevents:
- **DoS Attacks:** Resource exhaustion from excessive requests
- **Brute Force:** Login/password guessing attempts
- **API Abuse:** Scraping, automated attacks
- **Resource Starvation:** Fair allocation of server resources
- **Cost Control:** Prevents excessive cloud billing

**Without rate limiting:**
```python
# Attacker sends 10,000 requests/second
for i in range(10000):
    requests.post('https://eclaim.hospital.go.th/login', data={...})
# Server crashes, legitimate users locked out
```

**With rate limiting:**
```python
# First 5 requests succeed, rest blocked
# HTTP 429 Too Many Requests
# Retry-After: 300 seconds
```

---

## Quick Start

### 1. Import Rate Limiter

```python
from utils.rate_limiter import rate_limiter, limit_login, limit_api
```

### 2. Apply to Routes

```python
@app.route('/api/downloads', methods=['POST'])
@login_required
@rate_limiter.limit(requests=30, window=60, per='user')
def download():
    # Allows 30 requests per 60 seconds per user
    return jsonify({'success': True})
```

### 3. Use Convenience Decorators

```python
from utils.rate_limiter import limit_login, limit_api, limit_download, limit_export

@app.route('/login', methods=['POST'])
@limit_login  # 5 requests per 5 minutes per IP
def login():
    pass

@app.route('/api/data', methods=['GET'])
@login_required
@limit_api  # 60 requests per minute per user
def get_data():
    pass

@app.route('/api/downloads/bulk', methods=['POST'])
@login_required
@limit_download  # 10 requests per hour per user
def bulk_download():
    pass

@app.route('/api/export', methods=['POST'])
@login_required
@limit_export  # 5 requests per hour per user
def export_data():
    pass
```

---

## How It Works

### Token Bucket Algorithm

**Concept:**
1. Each user/IP has a "bucket" with tokens
2. Bucket starts with N tokens (capacity)
3. Each request consumes 1 token
4. Tokens refill at rate R per second
5. If no tokens available, request is rejected

**Example:**
```
Bucket: capacity=30, refill_rate=0.5 (30 requests/minute)

t=0s:  [●●●●●●●●●●●●●●●●●●●●●●●●●●●●●●] 30 tokens
       Request → consume 1 token
t=1s:  [●●●●●●●●●●●●●●●●●●●●●●●●●●●●●] 29 tokens
       ...10 more requests...
t=10s: [●●●●●●●●●●●●●●●●●●●] 19 tokens
       ...19 more requests...
t=38s: [●] 1 token (+ 19 refilled)
       Request → consume 1 token
t=39s: [] 0 tokens
       Request → REJECTED (HTTP 429)
```

**Advantages:**
- Allows bursts (up to capacity)
- Fair distribution over time
- Predictable behavior
- Industry standard (used by AWS, Stripe, GitHub)

---

## Configuration

### Custom Rate Limits

```python
@app.route('/api/expensive-operation', methods=['POST'])
@login_required
@rate_limiter.limit(
    requests=5,      # Allow 5 requests
    window=3600,     # Per hour (3600 seconds)
    per='user',      # Per authenticated user
    endpoint='/api/expensive'  # Optional custom name
)
def expensive_operation():
    pass
```

### Per-User vs Per-IP

**Per-User (authenticated):**
```python
@rate_limiter.limit(requests=60, window=60, per='user')
# Each authenticated user gets 60 requests/minute
# Requires user to be logged in
```

**Per-IP (anonymous):**
```python
@rate_limiter.limit(requests=10, window=60, per='ip')
# Each IP address gets 10 requests/minute
# Works for anonymous users
# Automatic fallback for unauthenticated requests
```

---

## Response Format

### Successful Request

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1705467600

{
  "success": true,
  "data": {...}
}
```

**Headers:**
- `X-RateLimit-Limit`: Total requests allowed
- `X-RateLimit-Remaining`: Requests remaining in current window
- `X-RateLimit-Reset`: Unix timestamp when limit resets

### Rate Limit Exceeded

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 45
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1705467600

{
  "success": false,
  "error": "Rate limit exceeded",
  "message": "Too many requests. Limit: 30 requests per 60 seconds.",
  "retry_after": 45,
  "limit": 30,
  "remaining": 0,
  "reset": 1705467600
}
```

**Headers:**
- `Retry-After`: Seconds to wait before retrying
- All `X-RateLimit-*` headers included

---

## Built-in Limits

| Decorator | Limit | Window | Per | Use Case |
|-----------|-------|--------|-----|----------|
| `limit_login` | 5 | 5 min | IP | Login attempts (brute force protection) |
| `limit_api` | 60 | 1 min | User | General API calls |
| `limit_download` | 10 | 1 hour | User | File downloads |
| `limit_export` | 5 | 1 hour | User | Data exports |

### Rationale

**Login (5 req / 5 min per IP):**
- Prevents brute force password attacks
- Legitimate users rarely need >5 login attempts
- IP-based to protect all accounts

**API (60 req / 1 min per user):**
- Balances usability and protection
- ~1 request per second for normal use
- Per-user to allow multiple users

**Download (10 req / 1 hour per user):**
- Downloads are resource-intensive
- Prevents bulk scraping
- 10 files/hour is reasonable for normal use

**Export (5 req / 1 hour per user):**
- Exports are very resource-intensive
- Often contain sensitive data
- Stricter limit for security

---

## Advanced Usage

### Manual Bucket Control

```python
from utils.rate_limiter import rate_limiter

# Get bucket for specific user/endpoint
bucket_key = rate_limiter._get_bucket_key('/api/test', 'user:123')
bucket = rate_limiter._get_bucket(bucket_key, capacity=10, refill_rate=1.0)

# Check remaining tokens
remaining = bucket.get_remaining()
print(f"Tokens available: {remaining}")

# Get reset time
reset_seconds = bucket.get_reset_time()
print(f"Full in {reset_seconds:.1f} seconds")

# Manual consumption
if bucket.consume(tokens=5):
    print("Consumed 5 tokens")
else:
    print("Not enough tokens")

# Reset limit (admin function)
rate_limiter.reset('/api/test', 'user:123')
```

### Custom Token Bucket

```python
from utils.rate_limiter import TokenBucket

# Create custom bucket
bucket = TokenBucket(capacity=100, refill_rate=10.0)  # 100 req, 10/sec refill

# Use in custom logic
if bucket.consume():
    process_request()
else:
    reject_request()
```

---

## Client-Side Handling

### JavaScript (Fetch API)

```javascript
async function makeRequest() {
    const response = await fetch('/api/data');

    if (response.status === 429) {
        // Rate limit exceeded
        const data = await response.json();
        const retryAfter = data.retry_after;

        console.log(`Rate limited. Retry in ${retryAfter} seconds`);

        // Wait and retry
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        return makeRequest();  // Retry
    }

    return response.json();
}
```

### Python Requests

```python
import requests
import time

def api_call(url):
    response = requests.get(url)

    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        print(f"Rate limited. Waiting {retry_after} seconds...")
        time.sleep(retry_after)
        return api_call(url)  # Retry

    return response.json()
```

### Exponential Backoff

```python
import time
import random

def api_call_with_backoff(url, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url)

        if response.status_code == 429:
            # Exponential backoff: 2^attempt * random(1-2) seconds
            wait = (2 ** attempt) * (1 + random.random())
            print(f"Attempt {attempt + 1}: Rate limited. Waiting {wait:.1f}s...")
            time.sleep(wait)
            continue

        return response.json()

    raise Exception("Max retries exceeded")
```

---

## Testing

### Run Rate Limit Tests

```bash
python test_rate_limit.py
```

**Expected output:**
```
================================
RATE LIMITING TEST
================================

Testing: TokenBucket...
✓ Initial capacity correct (5 tokens)
✓ Consumed 3 tokens correctly (2 remaining)
✓ Correctly rejected when tokens exhausted
  Waiting 2 seconds for token refill...
✓ Tokens refilled (now 2 tokens)
✓ Reset time calculated correctly (3.0s)

...

✓ PASS: Token Bucket
✓ PASS: Rate Limiter Basic
✓ PASS: Rate Limit Enforcement
✓ PASS: Bucket Cleanup
✓ PASS: Convenience Decorators

Result: 5/5 tests passed

🎉 All rate limiting tests passed!
```

### Manual Testing

```bash
# Test login rate limit (5 req/5min)
for i in {1..10}; do
    curl -X POST http://localhost:5001/login \
        -H "Content-Type: application/json" \
        -d '{"username":"test","password":"test"}' \
        -w "\nStatus: %{http_code}\n\n"
done

# Expected:
# Requests 1-5: 200 OK (or 401 if invalid credentials)
# Requests 6-10: 429 Too Many Requests
```

---

## Monitoring

### View Rate Limit Logs

```bash
docker-compose logs -f web | grep "Rate limit exceeded"
```

**Sample output:**
```
[2026-01-17 10:23:45] WARNING - Rate limit exceeded: ip:192.168.1.100 on /login (limit: 5/300s)
[2026-01-17 10:25:10] WARNING - Rate limit exceeded: user:5 on /api/downloads (limit: 10/3600s)
```

### Metrics to Track

1. **Rate limit hits per endpoint**
   - Which endpoints are being rate limited most?
   - Indicates potential abuse or need to adjust limits

2. **Users hitting limits**
   - Same user repeatedly hitting limits?
   - May indicate bot or malicious activity

3. **Time patterns**
   - Rate limit hits clustered at certain times?
   - May indicate automated attacks

---

## Security Considerations

### Bypass Attempts

**IP Spoofing:**
- Rate limiter uses `request.remote_addr` (can't be spoofed if behind proxy)
- Configure proxy to forward real client IP

**User Account Spam:**
- Per-user limits prevent single user abuse
- But attacker can create multiple accounts
- Mitigation: Email verification, CAPTCHA

**Distributed Attacks:**
- Attacker uses many IPs (botnet)
- Current implementation can't prevent this alone
- Mitigation: Use nginx rate limiting (already implemented), CDN, DDoS protection

### Privacy

**IP Address Hashing:**
```python
# Bucket keys are hashed (SHA-256) for privacy
bucket_key = hashlib.sha256(f"{endpoint}:{identifier}".encode()).hexdigest()[:16]
```

- Raw IPs/user IDs never stored in memory long-term
- Only short hash stored

---

## Performance

### Memory Usage

**Per bucket overhead:**
- TokenBucket object: ~200 bytes
- Cleanup after 1 hour of inactivity

**Estimate:**
- 1,000 active users = ~200 KB
- 10,000 active users = ~2 MB
- Negligible for modern servers

### CPU Overhead

**Per request:**
- Hash calculation: <1ms
- Token consumption: <0.1ms
- Negligible impact on response time

---

## Migration from nginx Rate Limiting

**nginx rate limiting (already implemented):**
- Network layer (more efficient)
- Protects all endpoints
- Coarse-grained (IP-based only)

**Application rate limiting (this implementation):**
- Application layer (more flexible)
- Per-user limits (requires authentication)
- Fine-grained (per-endpoint configuration)

**Best practice: Use both**
- nginx for DDoS protection (broad limits)
- App for business logic (specific limits per user/endpoint)

---

## Troubleshooting

### Issue: Legitimate users hitting limits

**Solution:**
```python
# Increase limits for specific endpoints
@rate_limiter.limit(requests=100, window=60, per='user')  # More generous
```

### Issue: Rate limits not enforced

**Check:**
1. Decorator applied to route?
   ```python
   @app.route('/api/endpoint')
   @rate_limiter.limit(...)  # Must be here
   def endpoint():
       pass
   ```

2. Import correct?
   ```python
   from utils.rate_limiter import rate_limiter  # Not rate_limit
   ```

### Issue: All users share same bucket

**Cause:** Not authenticated, fallback to IP-based

**Solution:**
```python
# Ensure user is authenticated
@login_required
@rate_limiter.limit(..., per='user')  # Requires authentication
```

---

## Future Enhancements

**Planned (Phase 3):**
1. Redis support for multi-server deployment
2. Database persistence for rate limit history
3. Admin UI for viewing/adjusting limits
4. Whitelist/blacklist IP ranges
5. Dynamic limits based on user role
6. Rate limit analytics dashboard

---

## Resources

- **Token Bucket Algorithm:** https://en.wikipedia.org/wiki/Token_bucket
- **RFC 6585 (HTTP 429):** https://tools.ietf.org/html/rfc6585
- **Rate Limiting Best Practices:** https://cloud.google.com/architecture/rate-limiting-strategies-techniques
- **OWASP API Security:** https://owasp.org/www-project-api-security/

---

**Last Updated:** 2026-01-17
**Maintainer:** Security Team

**Next:** [Security Headers](SECURITY_HEADERS.md) | [Phase 2 Complete](PHASE2_COMPLETE.md)
