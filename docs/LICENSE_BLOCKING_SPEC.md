# License Blocking Specification - On-Premise System

## Overview

Simple license enforcement for on-premise deployment. The system uses a 3-state model with configurable grace period.

**Philosophy:**
- Core value = Automated downloads (manual download is painful)
- Block downloads/imports when expired = Strong incentive to renew
- Keep existing data accessible = No production breakage
- Grace period configurable via license = Future flexibility

---

## License States

### 1. ✅ Active License (Full Access)

**Conditions:**
- Valid license installed
- Not expired OR within expiration date
- Signature verification passes
- Hospital code matches (optional)

**Behavior:**
- All features enabled
- No warnings or restrictions
- Full read/write access

---

### 2. ⚠️ Grace Period (Full Access + Warning)

**Conditions:**
- License expired < {grace_period_days} days ago (default: 90 days)
- Grace period read from license token OR use default
- Signature still valid

**Behavior:**
- **All features still work** (download, import, settings, External API)
- Persistent warning banner on all pages (cannot dismiss)
- Warning shown on login
- Daily reminder in logs

**Grace Period Configuration:**
- Default: **90 days** (configurable in code)
- Can override via license token: `"grace_period_days": 60`
- Designed for hospital procurement process timeline

**Warning Message:**
```
⚠️ License Expired - Grace Period Active
Your license expired on {date}. You have {days} days remaining.
Please contact your vendor to renew your license.
Contact: sales@vendor.com
```

---

### 3. 🔒 Read-Only Mode (Expired)

**Conditions:**
- License expired > {grace_period_days} days ago (default: > 90 days)
- OR no valid license installed
- OR signature verification failed

**Behavior:**
- **Core pain point: Cannot download new files** (manual download is tedious)
- Cannot import data
- Can view all existing data
- Can export existing data
- External API still works (for HIS integration)

**Blocked Operations (Core Value):**
- ❌ **Download** (REP/STM/SMT) - Manual/Scheduled/Bulk ← Main pain point!
- ❌ **Import** files (no new data)
- ❌ **Settings** modifications
- ❌ **User management** (add/edit users)

**Allowed Operations (Data Access):**
- ✅ View Dashboard
- ✅ View Analytics/Reports
- ✅ View Files list
- ✅ Export data (CSV/Excel) with watermark
- ✅ View Settings (read-only)
- ✅ **External API** (HIS integration) - Read existing data only
- ✅ External API health check

**Error Message:**
```
🔒 Download Disabled - License Expired
Your license expired on {date} (over {grace_period_days} days ago).
Download and import features are disabled.

To download new files, please renew your license.
Contact: sales@vendor.com | support@vendor.com

You can still:
✓ View all existing data
✓ Generate reports and analytics
✓ Export data
✓ Use External API for HIS integration
```

---

## Feature Matrix

| Feature | Active | Grace Period | Read-Only |
|---------|--------|--------------|-----------|
| **Downloads** |
| Single download | ✅ | ✅ | ❌ |
| Bulk download | ✅ | ✅ | ❌ |
| Scheduled download | ✅ | ✅ | ❌ |
| Cancel download | ✅ | ✅ | ✅ (if running) |
| **Imports** |
| Import REP files | ✅ | ✅ | ❌ |
| Import STM files | ✅ | ✅ | ❌ |
| Import SMT data | ✅ | ✅ | ❌ |
| Scan files | ✅ | ✅ | ❌ |
| **Data Access** |
| View Dashboard | ✅ | ✅ | ✅ |
| View Analytics | ✅ | ✅ | ✅ |
| View Reports | ✅ | ✅ | ✅ |
| Export Data | ✅ | ✅ | ✅ |
| **Settings** |
| View Settings | ✅ | ✅ | ✅ (read-only) |
| Edit Settings | ✅ | ✅ | ❌ |
| Manage Users | ✅ | ✅ | ❌ |
| Install License | ✅ | ✅ | ✅ |
| **External API (HIS Integration)** |
| Health check (`/api/v1/health`) | ✅ | ✅ | ✅ |
| Get claims data (existing) | ✅ | ✅ | ✅ |
| Reconciliation (existing data) | ✅ | ✅ | ✅ |
| All read operations | ✅ | ✅ | ✅ |
| Write operations (if any) | ✅ | ✅ | ❌ |
| **Internal API** |
| Analytics/Reports (read) | ✅ | ✅ | ✅ |
| Export endpoints | ✅ | ✅ | ✅ |
| Download/Import (write) | ✅ | ✅ | ❌ |

---

## User Experience

### Warning Banner (Grace Period)

**Location:** Top of all pages (sticky)

**Design:**
```html
┌────────────────────────────────────────────────────────────┐
│ ⚠️ License Expired - {X} days remaining in grace period   │
│ Your license expired on {date}. Please renew to continue. │
│ [Contact Vendor] [Dismiss for 24h]                    [×] │
└────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Yellow/Orange background
- Dismissible for 24 hours (stored in localStorage)
- Reappears daily
- Shows days remaining in grace period

---

### Read-Only Mode Banner

**Location:** Top of all pages (sticky, cannot dismiss)

**Design:**
```html
┌────────────────────────────────────────────────────────────┐
│ 🔒 READ-ONLY MODE - License Expired                       │
│ Download and import features are disabled.                │
│ [View License Info] [Contact Vendor]                      │
└────────────────────────────────────────────────────────────┘
```

**Behavior:**
- Red background
- Cannot be dismissed
- Appears on all pages
- Links to license page

---

### Blocked Action UI

When user tries to perform blocked action:

**Download/Import Buttons:**
- Disabled state (grayed out)
- Tooltip on hover: "License expired - Read-only mode"
- Click shows modal:

```
┌─────────────────────────────────────────┐
│  🔒 License Required                    │
│                                         │
│  This feature requires an active        │
│  license. Your license expired on       │
│  {date}.                                │
│                                         │
│  Contact your vendor to renew.          │
│                                         │
│  [View License Info]  [Close]          │
└─────────────────────────────────────────┘
```

---

## Technical Implementation

### 1. License State Detection

**File:** `utils/license_checker.py`

**New Method:**
```python
def get_license_state(self) -> LicenseState:
    """
    Determine current license state

    Returns:
        'active' | 'grace_period' | 'read_only'
    """
    is_valid, payload, error = self.verify_license()

    if not is_valid:
        return 'read_only'

    exp = payload.get('exp')
    if not exp:
        return 'active'  # Perpetual license

    exp_date = datetime.fromtimestamp(exp)
    now = datetime.now()

    if now <= exp_date:
        return 'active'

    # Get grace period from license token or use default (90 days)
    grace_period_days = payload.get('grace_period_days', 90)
    grace_end = exp_date + timedelta(days=grace_period_days)

    if now <= grace_end:
        return 'grace_period'

    return 'read_only'
```

---

### 2. Middleware for Blocking

**File:** `utils/license_middleware.py` (new)

```python
def require_license_write_access(f):
    """
    Decorator to block write operations in read-only mode

    Usage:
        @app.route('/api/downloads/single', methods=['POST'])
        @require_license_write_access
        def download_single():
            ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from utils.settings_manager import SettingsManager

        settings_mgr = SettingsManager()
        license_info = settings_mgr.get_license_info()
        license_state = license_info.get('license_state', 'read_only')

        if license_state == 'read_only':
            return jsonify({
                'success': False,
                'error': 'License expired - System is in read-only mode',
                'license_state': 'read_only',
                'expired_date': license_info.get('expires_at'),
                'contact': 'Please contact your vendor to renew your license'
            }), 403

        return f(*args, **kwargs)

    return decorated_function
```

---

### 3. Endpoints to Block

**Download Endpoints:**
```python
@app.route('/api/downloads/single', methods=['POST'])
@require_license_write_access  # ← Add decorator
def download_single():
    ...

@app.route('/api/downloads/bulk', methods=['POST'])
@require_license_write_access  # ← Add decorator
def download_bulk():
    ...
```

**Import Endpoints:**
```python
@app.route('/api/imports/rep', methods=['POST'])
@require_license_write_access  # ← Add decorator
def import_rep_all():
    ...

@app.route('/api/imports/stm', methods=['POST'])
@require_license_write_access  # ← Add decorator
def import_stm_all():
    ...
```

**Settings Endpoints:**
```python
@app.route('/api/settings/update', methods=['POST'])
@require_license_write_access  # ← Add decorator
def update_settings():
    ...
```

**External API Endpoints (HIS Integration):**
```python
# File: routes/external_api.py
# External API still works in read-only mode (for HIS integration)
# Only block write operations (if any exist in the future)

# NO BLOCKING for External API in read-only mode
# Rationale: HIS integration must not break when license expires
# Hospital can still query existing data for patient care
```

**Total: ~20-25 endpoints** to protect (15-20 internal + External API blueprint)

---

### 4. Frontend Changes

**A. Global License State**

**File:** `templates/base.html`

```html
<!-- License State (passed to all templates) -->
<script>
    window.LICENSE_STATE = {
        state: '{{ license_state }}',  // 'active' | 'grace_period' | 'read_only'
        expires_at: '{{ license_expires_at }}',
        days_remaining: {{ license_days_remaining }},
        grace_days_left: {{ license_grace_days_left }}
    };
</script>
```

**B. Warning Banners**

**File:** `templates/base.html`

```html
{% if license_state == 'grace_period' %}
<div id="grace-period-banner" class="fixed top-0 left-0 right-0 bg-yellow-500 text-white py-3 px-4 z-50">
    <div class="container mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
            <svg class="w-6 h-6"><!-- Warning icon --></svg>
            <div>
                <strong>License Expired</strong> - {{ license_grace_days_left }} days remaining in grace period.
                <span class="text-sm">Expired on {{ license_expires_at|date }}</span>
            </div>
        </div>
        <div class="flex items-center gap-2">
            <a href="/license" class="underline">View License</a>
            <button onclick="dismissBanner()" class="hover:opacity-80">×</button>
        </div>
    </div>
</div>
{% endif %}

{% if license_state == 'read_only' %}
<div class="fixed top-0 left-0 right-0 bg-red-600 text-white py-3 px-4 z-50">
    <div class="container mx-auto flex items-center justify-between">
        <div class="flex items-center gap-3">
            <svg class="w-6 h-6"><!-- Lock icon --></svg>
            <div>
                <strong>READ-ONLY MODE</strong> - License expired on {{ license_expires_at|date }}.
                Download and import features are disabled.
            </div>
        </div>
        <a href="/license" class="underline">View License Info</a>
    </div>
</div>
{% endif %}
```

**C. Disable Buttons**

**File:** `static/js/app.js`

```javascript
// Disable download/import buttons in read-only mode
if (window.LICENSE_STATE.state === 'read_only') {
    // Disable all download buttons
    document.querySelectorAll('[data-action="download"]').forEach(btn => {
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        btn.title = 'License expired - Read-only mode';
    });

    // Disable all import buttons
    document.querySelectorAll('[data-action="import"]').forEach(btn => {
        btn.disabled = true;
        btn.classList.add('opacity-50', 'cursor-not-allowed');
        btn.title = 'License expired - Read-only mode';
    });

    // Show modal if user clicks disabled button
    document.querySelectorAll('[disabled][data-action]').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            showLicenseExpiredModal();
        });
    });
}
```

---

## Implementation Plan

### Phase 1: Core License State (1-2 hours)

- [ ] Update `license_checker.py`:
  - [ ] Add `get_license_state()` method
  - [ ] Update `get_license_info()` to include state
  - [ ] Add grace period calculation (30 days)

- [ ] Update `settings_manager.py`:
  - [ ] Add `get_license_state()` wrapper
  - [ ] Update cached license info

### Phase 2: Backend Blocking (2-3 hours)

- [ ] Create `utils/license_middleware.py`:
  - [ ] Implement `@require_license_write_access` decorator

- [ ] Apply decorator to endpoints:
  - [ ] Download endpoints (5 routes) ← Main blocking
  - [ ] Import endpoints (6 routes) ← Main blocking
  - [ ] Settings endpoints (4 routes)
  - [ ] User management endpoints (3 routes)

- [ ] **Skip External API blocking**:
  - External API continues to work in read-only mode
  - Rationale: HIS integration must not break

### Phase 3: Frontend UI (2-3 hours)

- [ ] Update `base.html`:
  - [ ] Add license state to global JS variable
  - [ ] Add grace period banner
  - [ ] Add read-only mode banner

- [ ] Update `app.js`:
  - [ ] Disable buttons in read-only mode
  - [ ] Add license expired modal
  - [ ] Handle blocked API responses

- [ ] Update pages:
  - [ ] Downloads page - disable forms
  - [ ] Files page - disable import buttons
  - [ ] Settings page - disable edit forms

### Phase 4: Testing (1-2 hours)

- [ ] Test with active license
- [ ] Test with expired license (grace period)
- [ ] Test with expired license (read-only)
- [ ] Test with no license
- [ ] Test API endpoints blocking
- [ ] Test UI button states

### Phase 5: Documentation (30 mins)

- [ ] Update CLAUDE.md with license blocking info
- [ ] Add license troubleshooting guide
- [ ] Update README with license requirements

---

## Testing Scenarios

### Test 1: Active License
```bash
# Install Professional license
docker-compose exec web python install_test_license.py professional

# Expected: All features work, no warnings
```

### Test 2: Grace Period (Day 1)
```bash
# Install expired license (5 days ago)
docker-compose exec web python install_test_license.py expired

# Expected:
# - Yellow warning banner
# - All features still work (download, import, External API)
# - "85 days remaining" message (90 - 5 = 85)
```

### Test 3: Read-Only Mode (Day 91+)
```bash
# Manually edit license to expire 91 days ago
# OR remove license file

# Expected:
# - Red banner "Download Disabled - License Expired"
# - Download button disabled ← Main pain point!
# - Import button disabled
# - Dashboard/Analytics still work
# - Export still works (with watermark)
# - External API still works
```

### Test 4: Internal API Blocking
```bash
# Test download endpoint in read-only mode
curl -X POST http://localhost:5001/api/downloads/single \
  -H "Content-Type: application/json" \
  -d '{"month": 12, "year": 2568}'

# Expected: HTTP 403
# {
#   "success": false,
#   "error": "License expired - System is in read-only mode",
#   "license_state": "read_only"
# }
```

### Test 5: External API Still Works (HIS Integration)
```bash
# Test External API in read-only mode (should still work!)
curl -X GET http://localhost:5001/api/v1/claims?date_from=2025-01-01&date_to=2025-01-31 \
  -H "X-API-Key: your-api-key"

# Expected: HTTP 200 (NOT blocked!)
# {
#   "success": true,
#   "data": [...existing claims data...],
#   "note": "License expired - showing existing data only"
# }

# Health check always works
curl http://localhost:5001/api/v1/health

# Expected: HTTP 200
# {
#   "success": true,
#   "message": "API is healthy"
# }
```

---

## Success Criteria

✅ **Active License:**
- No warnings displayed
- All features functional
- Clean user experience

✅ **Grace Period:**
- Warning banner visible
- All features still work
- Clear expiration date shown
- Days remaining displayed

✅ **Read-Only Mode:**
- Red banner always visible
- **Download buttons disabled** ← Core pain point!
- **Import buttons disabled**
- Settings are read-only
- **External API still works** (HIS integration preserved)
- Analytics/Reports still work
- Export still works (with watermark)
- Clear error messages

✅ **Technical:**
- ~15-18 endpoints protected (download/import/settings)
- External API NOT blocked (HIS integration safe)
- Grace period configurable via license token
- Consistent error responses (403 with license_state)
- No false positives
- Performance not impacted

---

## Notes

- Grace period **default: 90 days**, configurable via `grace_period_days` in license token
- No tier-based restrictions (all licenses have same features)
- **Core value = Automated downloads** - blocking this creates strong renewal incentive
- External API NOT blocked - HIS integration must remain stable
- System never "stops working" - existing data always accessible
- License page always accessible (to install new license)
- No telemetry or phone-home (pure on-premise)
- Watermark in exports reminds users to renew without blocking functionality

---

**Total Estimated Time:** 6-8 hours
**Priority:** P1 (High) - Core licensing functionality
**Complexity:** Medium - Straightforward implementation
