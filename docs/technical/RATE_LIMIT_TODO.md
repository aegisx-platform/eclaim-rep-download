# Rate Limiting TODO

> Routes that should have rate limiting applied

**Status:** Partial Implementation
**Applied:** 1/30+ routes
**Priority:** High

---

## Already Applied

- ✅ `/login` - 5 req/5min per IP (brute force protection)

---

## Should Apply

### Authentication Routes (High Priority)

```python
# Already done
@app.route('/login', methods=['GET', 'POST'])
@limit_login  # ✅ Applied
def login():
    pass

# TODO
@app.route('/change-password', methods=['GET', 'POST'])
@limit_api  # 60 req/min - password changes shouldn't be too frequent
def change_password():
    pass
```

### Download Routes (High Priority)

```python
@app.route('/api/downloads/single', methods=['POST'])
@login_required
@limit_download  # 10 req/hour - downloads are resource-intensive
def download_single():
    pass

@app.route('/api/downloads/month', methods=['POST'])
@login_required
@limit_download  # 10 req/hour
def download_month():
    pass

@app.route('/api/downloads/bulk', methods=['POST'])
@login_required
@limit_download  # 10 req/hour
def download_bulk():
    pass

@app.route('/api/downloads/parallel', methods=['POST'])
@login_required
@limit_download  # 10 req/hour
def download_parallel():
    pass
```

### Import Routes (High Priority)

```python
@app.route('/api/imports/rep', methods=['POST'])
@login_required
@limit_api  # 60 req/min - imports are heavy but users may batch import
def import_rep_all():
    pass

@app.route('/api/imports/rep/<filename>', methods=['POST'])
@login_required
@limit_api  # 60 req/min
def import_rep_file(filename):
    pass

# Similar for STM and SMT routes...
```

### Export/Analytics Routes (Medium Priority)

```python
@app.route('/api/analytics/export', methods=['POST'])
@login_required
@limit_export  # 5 req/hour - exports contain sensitive data
def export_data():
    pass

@app.route('/api/analytics/claims-detail', methods=['GET'])
@login_required
@limit_api  # 60 req/min - read-only but resource-intensive
def claims_detail():
    pass

@app.route('/api/analytics/reconciliation', methods=['GET'])
@login_required
@limit_api  # 60 req/min
def reconciliation():
    pass
```

### File Management Routes (Medium Priority)

```python
@app.route('/api/files', methods=['GET'])
@login_required
@limit_api  # 60 req/min - read-only
def list_files():
    pass

@app.route('/api/files/scan', methods=['POST'])
@login_required
@limit_api  # 60 req/min
def scan_files():
    pass

@app.route('/api/files/rep/<filename>', methods=['DELETE'])
@login_required
@limit_api  # 60 req/min
def delete_rep_file(filename):
    pass

# Similar for STM and SMT delete routes...
```

### Settings Routes (Low Priority - Admin Only)

```python
@app.route('/api/settings/credentials', methods=['POST'])
@login_required
@require_admin
@limit_api  # 60 req/min
def update_credentials():
    pass

@app.route('/api/settings/hospital', methods=['POST'])
@login_required
@require_admin
@limit_api  # 60 req/min
def update_hospital_settings():
    pass

@app.route('/api/schedule/enable', methods=['POST'])
@login_required
@require_admin
@limit_api  # 60 req/min
def enable_schedule():
    pass
```

### History/Stats Routes (Low Priority - Read-Only)

```python
@app.route('/api/history/downloads/stats', methods=['GET'])
@login_required
@limit_api  # 60 req/min
def download_stats():
    pass

@app.route('/api/history/downloads', methods=['GET'])
@login_required
@limit_api  # 60 req/min
def download_history():
    pass
```

---

## Implementation Strategy

### Option 1: Gradual Rollout (Recommended)

Apply rate limits gradually to monitor impact:

**Week 1:**
- ✅ Login route (done)
- Download routes (high impact)
- Import routes (high impact)

**Week 2:**
- Export routes
- File management routes

**Week 3:**
- Settings routes
- Remaining API routes

**Benefit:** Can adjust limits based on real usage patterns

### Option 2: Bulk Apply

Apply all at once with conservative limits:

```python
# Global default for all API routes
@app.before_request
def apply_rate_limit():
    if request.path.startswith('/api/'):
        # Apply default rate limit
        # (More complex - requires custom implementation)
        pass
```

**Benefit:** Complete protection immediately
**Risk:** May impact legitimate heavy users

---

## Testing

After applying rate limits:

```bash
# Test login rate limit
for i in {1..10}; do
    curl -X POST http://localhost:5001/login \
        -d "username=test&password=test" \
        -w "\nStatus: %{http_code}\n"
done
# Expected: 5 successes, 5 rate limited (429)

# Test API rate limit
for i in {1..100}; do
    curl http://localhost:5001/api/files \
        -H "Cookie: session=YOUR_SESSION" \
        -w "\nStatus: %{http_code}\n"
done
# Expected: 60 successes, 40 rate limited (429)
```

---

## Monitoring

```bash
# Watch rate limit logs
docker-compose logs -f web | grep "Rate limit exceeded"

# Count rate limits by endpoint
docker-compose logs web | \
    grep "Rate limit exceeded" | \
    awk '{print $NF}' | \
    sort | uniq -c | sort -nr
```

---

## Adjusting Limits

If users complain about limits being too strict:

```python
# Increase limits for specific routes
@app.route('/api/imports/rep', methods=['POST'])
@login_required
@rate_limiter.limit(requests=120, window=60, per='user')  # 2x normal limit
def import_rep_all():
    pass
```

Or create role-based limits:

```python
from flask_login import current_user

def get_user_limit():
    if current_user.role == 'admin':
        return 200  # Admins get higher limits
    elif current_user.role == 'analyst':
        return 100  # Analysts get moderate limits
    else:
        return 60  # Regular users get standard limits

@app.route('/api/analytics/claims', methods=['GET'])
@login_required
@rate_limiter.limit(
    requests=lambda: get_user_limit(),
    window=60,
    per='user'
)
def get_claims():
    pass
```

---

**Next Steps:**
1. Review this list with team
2. Decide on implementation strategy
3. Apply rate limits to high-priority routes
4. Monitor for 1 week
5. Adjust limits based on feedback
6. Apply to remaining routes

**Last Updated:** 2026-01-17
